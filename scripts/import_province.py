"""Import a province from fresh-page captures; preserve unpublished schedules."""
from collections import Counter
from html import escape
import json,re,sys
from pathlib import Path
from source_reader import Document,table_rows,parse_results,SourceError

def table_html(t):
 if 'html' in t:return t['html']
 rows=[]
 for row in t['rows']:
  cells=[]
  for c in row:
   attrs=''.join(f' {k}="{escape(str(c[k]))}"' for k in ('rowspan','colspan') if c.get(k))
   cells.append(f"<{c['tag']}{attrs}>{escape(c['text'])}</{c['tag']}>")
  rows.append('<tr>'+''.join(cells)+'</tr>')
 return f'<table id="{t["id"]}">'+''.join(rows)+'</table>'

def name_key(s):return ' '.join(s.replace('I','ı').replace('İ','i').casefold().split())

def convert_province_strict(raw):
 groups=[];empty=[];excluded=[]
 for entry in raw['groups']:
  label=entry['competition']['label']
  age=re.search(r'\b(Mini|Minik|Midi|Küçük|Yıldız|Genç)\b',label)
  gender=re.search(r'\b(Kızlar?|Erkekler?)\b',label)
  if not age or not gender:excluded.append(entry['competition']);continue
  age=age.group();gender='Kız' if gender.group().startswith('Kız') else 'Erkek'
  rem=re.sub(r'\b(Mini|Minik|Midi|Küçük|Yıldız|Genç)\s+(Kızlar?|Erkekler?)\b','',label).strip()
  rem=re.sub(r'\bSüperlig\b','Süper Lig',rem,flags=re.I)
  rem=re.sub(r'\bGr\.?$', 'Grubu', rem)
  region=re.search(r'((?:Doğu|Batı|Kuzey|Güney)\s*)?(?:[A-ZÇĞİÖŞÜ]\s+)?Grubu$',rem)
  if region:region=region.group().strip();league=rem[:-len(region)].strip(' -')
  else:region='';league=rem
  doc=Document(''.join(table_html(t) for t in entry['tables']))
  st=[t for t in doc.root.find('table') if t.attrs.get('id','').startswith('icerik_GvTemplate')]
  if len(st)!=1:raise SourceError('Ambiguous standings: '+label)
  if 'Tanımlı Müsabaka Bulunamadı' in st[0].text() or 'Tanımlı Puantaj Bulunamadı' in st[0].text():empty.append(entry['competition']);continue
  rows=table_rows(st[0]);standings=[]
  if rows[0][:8]!=['Logo','Takım Adı','O','G','M','A','V','P']:raise SourceError('Changed columns: '+label)
  names={}
  for rank,row in enumerate(rows[1:],1):
   if len(row)!=len(rows[0]) or any(not v.isdecimal() for v in row[2:7]) or not re.fullmatch(r'-?\d+',row[7]):raise SourceError('Invalid counters: '+label)
   name=row[1];key=name_key(name)
   if key in names:raise SourceError('Ambiguous team identity: '+label)
   names[key]=name
   standings.append(dict(rank=rank,team=name,played=int(row[2]),won=int(row[3]),lost=int(row[4]),sets_for=int(row[5]),sets_against=int(row[6]),points=int(row[7]),source_cells=row))
  mt=doc.root.find('table','icerik_gvmusabakaliste')
  matches=parse_results(table_rows(mt[0])) if mt else []
  cancelled=[m for m in matches if not m['score'] and any('(Çekildi)' in m[s] for s in ('home','away'))]
  matches=[m for m in matches if m not in cancelled]
  completed=Counter()
  for m in matches:
   for side in ('home','away'):
    key=name_key(m[side])
    if key not in names:raise SourceError('Unmatched team in '+label+': '+m[side])
    m[side]=names[key]
   if m['score']:completed.update([m['home'],m['away']])
  if any(s['played']!=s['won']+s['lost'] or s['played']!=completed[s['team']] for s in standings):raise SourceError('Incomplete source result history: '+label)
  groups.append(dict(id=entry['competition']['value'].split('*')[0],competition=entry['competition'],category=age,gender=gender,league=league,title=' '.join((f'{age} {gender} {league}'+(' - '+region if region else '')).split()),checked_at=entry['checked_at'],standings=standings,matches=matches,matches_published=bool(mt),cancelled_matches=cancelled))
 groups.sort(key=lambda g:(0 if g['league'].startswith('Süper Lig') else 1 if g['league'].startswith('Gelişim Lig') else 2,{'Mini':0,'Minik':0,'Midi':1,'Küçük':2,'Yıldız':3,'Genç':4}[g['category']],g['gender'],re.sub(r'\d+',lambda m:m.group().zfill(5),g['title'])))
 if not groups:raise SourceError('No verified populated youth groups')
 return dict(schema_version=1,source=raw['source'],province=raw['province'],province_id=raw['province_id'],season='2026-2027',scope='Altyapı ligleri',last_success_at=min(g['checked_at'] for g in groups),collection_finished_at=max(g['checked_at'] for g in groups),automation_active=False,push_active=False,empty_competitions=empty,excluded_competitions=excluded,groups=groups)
def convert_province(raw):
 try:return convert_province_strict(raw)
 except SourceError as initial:
  if str(initial)=='No verified populated youth groups':raise
 groups=[];empty=[];unverified=[];excluded=[]
 for entry in raw['groups']:
  try:
   result=convert_province_strict({**raw,'groups':[entry]});groups.extend(result['groups'])
  except SourceError as e:
   if str(e)=='No verified populated youth groups':
    label=entry['competition']['label']
    target=empty if re.search(r'\b(Mini|Minik|Midi|Küçük|Yıldız|Genç)\b',label) and re.search(r'\b(Kızlar?|Erkekler?)\b',label) else excluded
    target.append(entry['competition'])
   else:unverified.append({**entry['competition'],'reason':str(e)})
 if not groups:raise SourceError('No usable groups; source validation failed: '+str(unverified))
 groups.sort(key=lambda g:(0 if g['league'].startswith('Süper Lig') else 1 if g['league'].startswith('Gelişim Lig') else 2,{'Mini':0,'Minik':0,'Midi':1,'Küçük':2,'Yıldız':3,'Genç':4}[g['category']],g['gender'],re.sub(r'\d+',lambda m:m.group().zfill(5),g['title'])))
 return dict(schema_version=1,source=raw['source'],province=raw['province'],province_id=raw['province_id'],season='2026-2027',scope='Altyapı ligleri',last_success_at=min(g['checked_at'] for g in groups),collection_finished_at=max(g['checked_at'] for g in groups),automation_active=False,push_active=False,empty_competitions=empty,excluded_competitions=excluded,unverified_competitions=unverified,groups=groups)

if __name__=='__main__':
 data=convert_province(json.loads(Path(sys.argv[1]).read_text()));dest=Path(sys.argv[2]);dest.parent.mkdir(parents=True,exist_ok=True);dest.write_text(json.dumps(data,ensure_ascii=False,separators=(',',':')));print({'province':data['province'],'groups':len(data['groups']),'matches':sum(len(g['matches']) for g in data['groups']),'empty':len(data['empty_competitions'])})
