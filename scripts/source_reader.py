"""Antalya public standings reader. One-shot only; no scheduler or push.

Uses Python standard library, verified TLS, same-origin forms, memory cookies.
HTTP execution still requires a separate real-host acceptance test.
"""
import argparse
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from html.parser import HTMLParser
from http.cookiejar import CookieJar
import json
from pathlib import Path
import re
import sys
import time
from urllib.parse import urlencode, urljoin, urlparse
from urllib.request import Request, build_opener, HTTPCookieProcessor, HTTPRedirectHandler

URL = 'https://antalya.voleyboliltemsilciligi.com/PuanDurumu'
TEAM_LABELS = {'Murat Akar S.K.', 'Murat Akar S.K. (A)', 'Murat Akar S.K. (B)'}


class SourceError(ValueError):
    pass


@dataclass
class Node:
    tag: str
    attrs: dict = field(default_factory=dict)
    children: list = field(default_factory=list)

    def find(self, tag=None, ident=None):
        result = []
        for child in self.children:
            if isinstance(child, Node):
                if (tag is None or child.tag == tag) and (ident is None or child.attrs.get('id') == ident):
                    result.append(child)
                result.extend(child.find(tag, ident))
        return result

    def text(self):
        return ''.join(c.text() if isinstance(c, Node) else c for c in self.children)


class Document(HTMLParser):
    VOID = {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'param', 'source', 'track', 'wbr'}

    def __init__(self, html):
        super().__init__(convert_charrefs=True)
        self.root = Node('root')
        self.stack = [self.root]
        self.feed(html)
        self.close()

    def handle_starttag(self, tag, attrs):
        n = Node(tag, dict(attrs))
        self.stack[-1].children.append(n)
        if tag not in self.VOID:
            self.stack.append(n)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in self.VOID:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        for i in range(len(self.stack)-1, 0, -1):
            if self.stack[i].tag == tag:
                del self.stack[i:]
                break

    def handle_data(self, data):
        self.stack[-1].children.append(data)

    def one(self, tag, ident):
        nodes = self.root.find(tag, ident)
        if len(nodes) != 1:
            raise SourceError('Missing or ambiguous element: ' + ident)
        return nodes[0]


def clean(value):
    return ' '.join(value.replace('\xa0', ' ').split())


def table_rows(table):
    rows = []
    for tr in table.find('tr'):
        cells = [c for c in tr.children if isinstance(c, Node) and c.tag in ('td', 'th')]
        if not cells:
            continue
        if any(c.find('table') for c in cells):
            raise SourceError('Nested table/pagination must be handled explicitly')
        expanded = []
        for cell in cells:
            if cell.attrs.get('rowspan', '1') != '1':
                raise SourceError('Unexpected rowspan')
            colspan = int(cell.attrs.get('colspan', '1'))
            if not 1 <= colspan <= 2:
                raise SourceError('Unexpected colspan')
            # Logo/name cells may span both columns in rows without a logo.
            expanded.extend([''] * (colspan - 1))
            expanded.append(clean(cell.text()))
        rows.append(expanded)
    return rows


def nullable_date(value):
    if not value:
        return None
    try:
        return datetime.strptime(value, '%d.%m.%Y').strftime('%Y-%m-%d')
    except ValueError as e:
        raise SourceError('Invalid date: ' + value) from e


def parse_results(rows):
    if not rows or len(rows[0]) != 9 or rows[0][1:5] != ['Tarih', 'Saat', 'Salon Adı', 'Ev Sahibi (A)'] or rows[0][7:] != ['Misafir (B)', 'Set Sonuçları']:
        raise SourceError('Changed results table header')
    result, seen = [], set()
    for row in rows[1:]:
        if len(row) != 9:
            raise SourceError('Unexpected match row width')
        number, date, clock, venue, home, a, b, away, sets_text = row
        if not number.isdecimal() or number in seen or not home or not away or home == away:
            raise SourceError('Invalid or repeated source row')
        seen.add(number)
        date = nullable_date(date)
        if clock:
            if date is None or not re.fullmatch(r'\d{2}:\d{2}', clock):
                raise SourceError('Time without date or invalid time')
            datetime.strptime(clock, '%H:%M')
        score = None
        sets = []
        # The Istanbul source uses 0 / 0 on an undated, unplayed fixture.
        # Keep it pending, without fabricating a completed result.
        if a == b == '0' and not sets_text and date is None and not clock:
            a = b = ''
        if a or b or sets_text:
            if not (a.isdecimal() and b.isdecimal()):
                raise SourceError('Incomplete score')
            score = [int(a), int(b)]
            pairs = re.findall(r'\((\d+)-(\d+)\)', sets_text)
            remainder = re.sub(r'\(\d+-\d+\)', '', sets_text).strip()
            if remainder:
                raise SourceError('Unknown set score format')
            sets = [[int(x), int(y)] for x, y in pairs]
            if max(score) not in (2, 3) or min(score) >= max(score) or len(sets) != sum(score):
                raise SourceError('Invalid completed match / set count')
            wins = [0, 0]
            for x, y in sets:
                if x == y:
                    raise SourceError('Tied completed set')
                wins[y > x] += 1
            if wins != score:
                raise SourceError('Set winners differ from match score')
        # Source adds this literal marker to a displayed match label. Preserve
        # both original labels and marker; do not use fuzzy name matching.
        raw_home, raw_away = home, away
        home_marker = 'H' if home.startswith('(H) - ') else None
        away_marker = 'H' if away.startswith('(H) - ') else None
        home = home[6:] if home_marker else home
        away = away[6:] if away_marker else away
        result.append(dict(source_row=number, match_id=None, date=date, time=clock or None,
                           venue=venue or None, home=home, away=away, score=score, sets=sets,
                           source_home=raw_home, source_away=raw_away,
                           home_marker=home_marker, away_marker=away_marker))
    if not result:
        raise SourceError('Empty result snapshot is ambiguous')
    return result


def parse_group(doc):
    matches = parse_results(table_rows(doc.one('table', 'icerik_gvmusabakaliste')))
    candidates = [t for t in doc.root.find('table') if t.attrs.get('id') in ('icerik_GvTemplate_1', 'icerik_GvTemplate_2')]
    if len(candidates) != 1:
        raise SourceError('Missing or ambiguous standings table')
    rows = table_rows(candidates[0])
    if not rows or rows[0][:8] != ['Logo', 'Takım Adı', 'O', 'G', 'M', 'A', 'V', 'P'] or len(rows[0]) not in (15, 18):
        raise SourceError('Changed standings table header')
    standings, teams = [], set()
    for rank, row in enumerate(rows[1:], 1):
        if len(row) != len(rows[0]) or not row[1] or row[1] in teams:
            raise SourceError('Malformed or duplicated standings row')
        teams.add(row[1])
        if any(not value.isdecimal() for value in row[2:8]):
            raise SourceError('Invalid standings counters')
        standings.append(dict(rank=rank, team=row[1], played=int(row[2]), won=int(row[3]),
                              lost=int(row[4]), sets_for=int(row[5]), sets_against=int(row[6]),
                              points=int(row[7]), source_cells=row))
    completed = Counter()
    for m in matches:
        if m['home'] not in teams or m['away'] not in teams:
            raise SourceError('Match team missing from standings')
        if m['score'] is not None:
            completed.update([m['home'], m['away']])
    for s in standings:
        if s['played'] != s['won'] + s['lost'] or s['played'] != completed[s['team']]:
            raise SourceError('Standings / completed matches disagree; preserve previous snapshot')
    return dict(standings=standings, matches=matches)


def compare_fixtures(group, fixture_rows, league, letter):
    expected = Counter(tuple(r[:5]) for r in fixture_rows if r[6] == league and r[9] == letter)
    def key(m):
        date = datetime.strptime(m['date'], '%Y-%m-%d').strftime('%d.%m.%Y') if m['date'] else ''
        return date, m['time'] or '', m['venue'] or '', m['home'], m['away']
    actual = Counter(key(m) for m in group['matches'] if m['home'] in TEAM_LABELS or m['away'] in TEAM_LABELS)
    return dict(exact_match=expected == actual, expected=sum(expected.values()), actual=sum(actual.values()),
                missing=list((expected-actual).elements()), extra=list((actual-expected).elements()))


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise SourceError('Unexpected redirect; stop this attempt')


class PublicSession:
    def __init__(self, source_url=URL):
        parsed = urlparse(source_url)
        if parsed.scheme != 'https' or not re.fullmatch(r'[a-z]+\.voleyboliltemsilciligi\.com', parsed.netloc) or parsed.path != '/PuanDurumu' or parsed.query or parsed.fragment:
            raise SourceError('Unapproved source URL')
        self.source_url = source_url
        self.opener = build_opener(HTTPCookieProcessor(CookieJar()), NoRedirect())
        self.last_request = 0

    def prime(self):
        # Some public province sites establish the province/session cookie on the
        # home page before PuanDurumu is available. This is an ordinary public GET;
        # unexpected redirects and explicit access denials still stop the attempt.
        return self._send(self.source_url.rsplit('/PuanDurumu', 1)[0] + '/')

    def request(self, url, fields=None):
        if urlparse(url)._replace(fragment='') != urlparse(self.source_url):
            raise SourceError('Unexpected form destination')
        return self._send(url, fields)

    def _send(self, url, fields=None):
        time.sleep(max(0, 1 - (time.monotonic() - self.last_request)))
        self.last_request = time.monotonic()
        data = urlencode(fields).encode() if fields is not None else None
        req = Request(url, data=data, headers={'User-Agent': 'Skor-Cepte/0.6 (read-only public fixture data)', 'Accept': 'text/html'})
        with self.opener.open(req, timeout=20) as response:
            if response.status != 200 or response.headers.get_content_type() != 'text/html':
                raise SourceError('Unexpected HTTP response')
            payload = response.read(4_000_001)
            if len(payload) > 4_000_000:
                raise SourceError('Page exceeds size limit')
            html = payload.decode(response.headers.get_content_charset() or 'utf-8')
        if re.search(r'error code:\s*1010|<title>\s*(Just a moment|Access Denied)', html, re.I):
            raise SourceError('Source access denied; no retry or bypass')
        return Document(html)

    def select(self, doc, ident, value):
        target = doc.one('select', ident)
        if value not in [o.attrs.get('value', clean(o.text())) for o in target.find('option')]:
            raise SourceError('Requested option is not present: ' + ident)
        forms = doc.root.find('form')
        if len(forms) != 1:
            raise SourceError('Unexpected form count')
        fields = {n.attrs['name']: n.attrs.get('value', '') for n in forms[0].find('input')
                  if n.attrs.get('type') == 'hidden' and n.attrs.get('name')}
        for select in forms[0].find('select'):
            if 'disabled' in select.attrs:
                continue
            options = select.find('option')
            chosen = next((o for o in options if 'selected' in o.attrs), options[0] if options else None)
            if chosen is not None:
                fields[select.attrs['name']] = chosen.attrs.get('value', clean(chosen.text()))
        fields[target.attrs['name']] = value
        fields.update(__EVENTTARGET=target.attrs['name'], __EVENTARGUMENT='')
        updated = self.request(urljoin(self.source_url, forms[0].attrs.get('action', '')), fields)
        selected = selected_value(updated, ident)
        if selected != value:
            raise SourceError('Filter was reset: ' + ident)
        return updated


def selected_value(doc, ident):
    options = doc.one('select', ident).find('option')
    chosen = next((o for o in options if 'selected' in o.attrs), options[0] if options else None)
    return chosen.attrs.get('value', clean(chosen.text())) if chosen else ''


def collect(config):
    session = PublicSession()
    doc = session.request(URL)
    # Source has a current-season banner and no standings season selector.
    # Reject a changed banner instead of labelling current data as an old season.
    if config['season'] not in clean(doc.root.text()):
        raise SourceError('Requested season absent from source page')
    doc = session.select(doc, 'icerik_ddlsbe', 'B')
    groups = []
    for mapping in config['groups']:
        doc = session.select(doc, 'icerik_ddlSyarismaadi', mapping['competition']['value'])
        if selected_value(doc, 'icerik_ddlSil') != '7' or selected_value(doc, 'icerik_ddlsbe') != 'B':
            raise SourceError('Province or gender drift')
        group = parse_group(doc)
        if not any(s['team'] in TEAM_LABELS for s in group['standings']):
            raise SourceError('Mapped group does not contain MASK')
        group.update(mapping=mapping, checked_at=datetime.now(timezone.utc).isoformat())
        groups.append(group)
    return dict(source=URL, method='direct HTTP on executing host', season=config['season'],
                province='7', club='2047', identity_status='match/team stable IDs unverified',
                notifications_enabled=False, groups=groups)


def main():
    parser = argparse.ArgumentParser(description='One-shot public MASK standings test; no installation')
    parser.add_argument('--config', default=str(Path(__file__).with_name('mask_groups.json')))
    parser.add_argument('--output', required=True, help='New JSON file; refuses to overwrite')
    args = parser.parse_args()
    output = Path(args.output)
    if output.exists():
        parser.error('Output already exists; previous data will not be overwritten')
    try:
        data = collect(json.loads(Path(args.config).read_text(encoding='utf-8')))
        # Do not create output until every group has passed validation.
        with output.open('x', encoding='utf-8') as stream:
            json.dump(data, stream, ensure_ascii=False, indent=2)
        print('OK:', len(data['groups']), 'groups;', sum(len(g['matches']) for g in data['groups']), 'matches')
    except Exception as e:
        print('FAILED (no source snapshot accepted):', type(e).__name__, str(e), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
