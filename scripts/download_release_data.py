"""Bundle verified live records into a release; never silently ship stale data."""
from datetime import datetime,timezone,timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.request import build_opener,HTTPRedirectHandler,Request
import argparse,json,os

ORIGIN='https://skor-cepte-service.spry-whale-0977.chatgpt.site'
class RejectRedirect(HTTPRedirectHandler):
 def redirect_request(self,*args,**kwargs):raise ValueError('Unexpected live data redirect')

def remote(path):
 request=Request(ORIGIN+path,headers={'Accept':'application/json','User-Agent':'Skor-Cepte-release/0.6'})
 with build_opener(RejectRedirect()).open(request,timeout=30) as response:
  if response.status!=200 or response.headers.get_content_type()!='application/json':raise ValueError('Live data did not return JSON')
  data=response.read(12000001)
  if len(data)>12000000:raise ValueError('Live data exceeds limit')
  return json.loads(data)

def download(root=Path('dist/data'),fetch=remote,now=None,allow_preserved=False):
 now=now or datetime.now(timezone.utc)
 original=json.loads((root/'provinces.json').read_text());registry=fetch('/data/provinces.json')
 if not isinstance(registry,list) or len(registry)!=81 or {p['id'] for p in registry}!={str(i) for i in range(1,82)}:raise ValueError('Invalid registry')
 names={p['id']:p['name'] for p in original};snapshots={}
 for p in registry:
  if p['name']!=names.get(p['id']) or p['status'] not in ('ready','source_empty','pending'):raise ValueError('Registry identity/status mismatch')
  if p['status']!='ready':continue
  expected='/data/provinces/'+p['id']+'.json'
  if p['snapshot']!=expected:raise ValueError('Foreign snapshot path')
  data=fetch(expected)
  if data.get('schema_version')!=1 or data.get('province_id')!=p['id'] or data.get('province')!=p['name'] or not data.get('groups'):raise ValueError('Snapshot identity/shape mismatch')
  timestamp=datetime.fromisoformat(data['last_success_at'].replace('Z','+00:00'))
  maximum_age=timedelta(hours=6)
  if allow_preserved and p.get('last_error_at'):
   failure_at=datetime.fromisoformat(p['last_error_at'].replace('Z','+00:00'))
   if failure_at>now+timedelta(minutes=5):raise ValueError('Future source failure date')
   maximum_age=timedelta(days=30)
  if not -timedelta(minutes=5)<=now-timestamp<=maximum_age:raise ValueError('Stale/future live data: '+p['name'])
  for group in data['groups']:
   if not group.get('standings') or not isinstance(group.get('matches'),list):raise ValueError('Incomplete group')
   for match in group['matches']:
    score=match.get('score')
    if score is not None and (not isinstance(score,list) or len(score)!=2 or not all(type(n) is int for n in score) or max(score) not in (2,3) or min(score)<0 or min(score)>=max(score) or len(match.get('sets',[]))!=sum(score)):raise ValueError('Invalid match score')
  snapshots[p['id']]=data
 if not snapshots:raise ValueError('No verified populated province')
 # All records are checked before any bundled source file is replaced.
 with TemporaryDirectory(prefix='skor-release-',dir=root.parent) as temp:
  staging=Path(temp);(root/'provinces').mkdir(exist_ok=True)
  for pid,data in snapshots.items():(staging/(pid+'.json')).write_text(json.dumps(data,ensure_ascii=False,separators=(',',':')))
  (staging/'provinces.json').write_text(json.dumps(registry,ensure_ascii=False,separators=(',',':')))
  for pid in snapshots:(staging/(pid+'.json')).replace(root/'provinces'/(pid+'.json'))
  (staging/'provinces.json').replace(root/'provinces.json')
 return len(snapshots)
if __name__=='__main__':
 if os.environ.get('SKOR_DATA_BASE_URL',ORIGIN).rstrip('/')!=ORIGIN:raise ValueError('Unexpected feed origin')
 parser=argparse.ArgumentParser();parser.add_argument('--allow-preserved',action='store_true',help='Verify explicitly failed sources at their preserved timestamp; release builds stay strict by default')
 options=parser.parse_args()
 print('Verified published records for '+str(download(allow_preserved=options.allow_preserved))+' provinces.')
