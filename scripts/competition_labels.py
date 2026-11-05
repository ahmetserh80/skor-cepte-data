"""Recognize official youth labels without changing source identities or scores."""
import re
import unicodedata

_TR = str.maketrans('ÇĞİÖŞÜçğıöşü', 'CGIOSUcgiosu')
_AGE = re.compile(r'\b(mini(?:ler)?|minik(?:ler)?|midi(?:ler)?|kucuk(?:ler)?|yildiz(?:lar)?|genc(?:ler)?)\b')
_GENDER = re.compile(r'\b(kiz(?:lar)?|kadin(?:lar)?|bayan(?:lar)?|erkek(?:ler)?)\b')
_SCHOOL = re.compile(r'\b(okul(?:lar(?:i|arasi)?)?|ortaokul(?:lar(?:i|arasi)?)?|lise(?:ler(?:i|arasi)?)?)\b')
_CATEGORIES = {'mini':'Mini', 'minik':'Minik', 'midi':'Midi', 'kucuk':'Küçük', 'yildiz':'Yıldız', 'genc':'Genç'}

def normalized(value):
    return unicodedata.normalize('NFC', str(value)).translate(_TR).lower()

def classify(label, source_gender=None, province=None):
    """Gender may come from the verified E/B form, never from a club name."""
    text = unicodedata.normalize('NFC', str(label))
    key = normalized(text)
    ages = list(_AGE.finditer(key))
    sexes = list(_GENDER.finditer(key))
    if len(ages) != 1 or re.search(r'\bbuyuk(?:ler)?\b', key):
        return None
    explicit = {'Erkek' if m.group().startswith('erkek') else 'Kız' for m in sexes}
    if len(explicit) > 1:
        return None
    gender = next(iter(explicit), {'E':'Erkek','B':'Kız'}.get(source_gender))
    if gender is None:
        return None
    expected = {'E':'Erkek','B':'Kız'}.get(source_gender)
    if expected and expected != gender:
        raise ValueError('Competition gender differs from the selected source filter')
    age = ages[0]
    stem = next(k for k in sorted(_CATEGORIES, key=len, reverse=True) if age.group().startswith(k))
    remaining = text
    for match in sorted([age, *sexes], key=lambda m:m.start(), reverse=True):
        remaining = remaining[:match.start()] + ' ' + remaining[match.end():]
    remaining = ' '.join(remaining.split()).strip(' -–—()')
    if province and normalized(remaining).startswith(normalized(province) + ' '):
        remaining = remaining[len(province):].lstrip(' -–—')
    return {'category':_CATEGORIES[stem], 'gender':gender,
            'scope':'school' if _SCHOOL.search(key) else 'club',
            'remaining':remaining}

def is_youth(label, source_gender=None):
    return classify(label, source_gender) is not None
