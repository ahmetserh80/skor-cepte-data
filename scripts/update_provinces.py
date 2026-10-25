"""Read public youth-league records with strict province and score validation."""
from datetime import datetime,timezone
from pathlib import Path
import json,re,sys
from source_reader import PublicSession,selected_value,clean,SourceError
from html_tables import serialize
from import_province import convert_province

YOUTH=re.compile(r'\b(Mini|Minik|Midi|Küçük|Yıldız|Genç)\b')
GENDER=re.compile(r'\b(Kızlar?|Erkekler?)\b')

def capture_tables(doc):
 # A layout table may wrap the actual standings and match tables. Serializing
 # every table and concatenating the HTML duplicates its nested child tables.
 return [{'html':serialize(t)} for t in doc.root.find('table') if t.attrs.get('id','').startswith('icerik_GvTemplate') or t.attrs.get('id')=='icerik_gvmusabakaliste']

def collect(previous):
 source=previous['source'];pid=previous['province_id'];session=PublicSession(source);session.prime()
 def fresh(sex=None):
  doc=session.request(source)
  if previous['season'] not in clean(doc.root.text()):raise SourceError('Season changed')
  if selected_value(doc,'icerik_ddlSil')!=pid:raise SourceError('Province changed')
  if sex:doc=session.select(doc,'icerik_ddlsbe',sex)
  return doc
 doc=fresh();sexes=[o.attrs['value'] for o in doc.one('select','icerik_ddlsbe').find('option') if o.attrs.get('value') in ('E','B')]
 captured=[]
 for sex in sexes:
  doc=fresh(sex)
  options=[{'label':clean(o.text()),'value':o.attrs.get('value')} for o in doc.one('select','icerik_ddlSyarismaadi').find('option') if o.attrs.get('value') not in ('0','',None) and YOUTH.search(clean(o.text())) and GENDER.search(clean(o.text()))]
  for co in options:
   doc=session.select(doc,'icerik_ddlSyarismaadi',co['value'])
   if selected_value(doc,'icerik_ddlSil')!=pid or selected_value(doc,'icerik_ddlsbe')!=sex:raise SourceError('Source filter drift')
   captured.append({'_sex':sex,'competition':co,'checked_at':datetime.now(timezone.utc).isoformat(),'tables':capture_tables(doc)})
 try:data=convert_province({'province':previous['province'],'province_id':pid,'source':source,'groups':captured})
 except SourceError as e:
  if not previous['groups'] and str(e)=='No verified populated youth groups':return None
  raise
 # Some ASP.NET competition templates retain hidden standings controls after
 # switching template types in one page. Retry only the structurally ambiguous
 # groups once from an independent fresh form, then apply the same strict parser.
 retry={e['value'] for e in data.get('unverified_competitions',[]) if e.get('reason','').startswith('Ambiguous standings:')}
 if retry:
  for entry in captured:
   if entry['competition']['value'] not in retry:continue
   isolated=session.select(fresh(entry['_sex']),'icerik_ddlSyarismaadi',entry['competition']['value'])
   if selected_value(isolated,'icerik_ddlSil')!=pid or selected_value(isolated,'icerik_ddlsbe')!=entry['_sex']:raise SourceError('Isolated source filter drift')
   entry.update(checked_at=datetime.now(timezone.utc).isoformat(),tables=capture_tables(isolated))
  data=convert_province({'province':previous['province'],'province_id':pid,'source':source,'groups':captured})
  print(json.dumps({'province':previous['province'],'isolated_rechecks':len(retry),'remaining_unverified':len(data.get('unverified_competitions',[]))},ensure_ascii=False),flush=True)
 known={g['competition']['value'] for g in previous['groups']}
 if not known.issubset({g['competition']['value'] for g in data['groups']}):raise SourceError('Known group disappeared; preserve prior snapshot: '+json.dumps({'missing':[g['title'] for g in previous['groups'] if g['competition']['value'] not in {n['competition']['value'] for n in data['groups']}],'unverified':data.get('unverified_competitions',[])},ensure_ascii=False))
 return data

if __name__=='__main__':
 registry_path=Path('dist/data/provinces.json');registry=json.loads(registry_path.read_text());errors=[]
 for p in registry:
  target=Path('dist/data/provinces')/(p['id']+'.json')
  previous=json.loads(target.read_text()) if p['status']=='ready' else {'source':p['url'].rstrip('/')+'/PuanDurumu','province':p['name'],'province_id':p['id'],'season':'2026-2027','groups':[]}
  try:
   data=collect(previous)
   if data is not None:
    tmp=target.with_suffix('.tmp');tmp.write_text(json.dumps(data,ensure_ascii=False,separators=(',',':')));tmp.replace(target)
    p.update(status='ready',snapshot='/data/provinces/'+p['id']+'.json')
   else:p.update(status='source_empty',snapshot=None)
   p['last_checked_at']=datetime.now(timezone.utc).isoformat()
   print(p['name']+': validated')
  except Exception as e:errors.append(p['name']);print(p['name']+': preserved previous snapshot: '+str(e),file=sys.stderr)
 tmp=registry_path.with_suffix('.tmp');tmp.write_text(json.dumps(registry,ensure_ascii=False,separators=(',',':')));tmp.replace(registry_path)
 if errors:sys.exit(1)
