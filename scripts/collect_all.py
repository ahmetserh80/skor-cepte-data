"""Collect each independent province with bounded concurrency, preserving failures.
The source filters and score parser must verify every accepted group. No old
snapshot gets a new success timestamp when its source could not be read.
"""
from concurrent.futures import ThreadPoolExecutor,as_completed
from datetime import datetime,timezone
from pathlib import Path
import json,os,time
from update_provinces import collect
from download_release_data import ORIGIN,remote as fetch_live

BASE=os.environ.get('SKOR_DATA_BASE_URL','').rstrip('/')
ROOT=Path('dist/data')

def remote(path):
 if BASE!=ORIGIN:
  print(json.dumps({'feed_path':path,'error':'Unexpected feed origin'}),flush=True)
  return None
 try:
  # Use the same explicit JSON client as the verified release download.
  # It identifies this application, rejects redirects and bounds response size.
  return fetch_live('/'+path.lstrip('/'))
 except Exception as error:
  print(json.dumps({'feed_path':path,'error':type(error).__name__,'status':getattr(error,'code',None)}),flush=True)
  return None

def one(p,collection_started_at):
 start=time.monotonic();target=ROOT/'provinces'/(p['id']+'.json')
 target.parent.mkdir(parents=True,exist_ok=True)
 prior=remote('data/provinces/'+p['id']+'.json') if p['status']=='ready' else None
 if prior is None and p['status']=='ready':
  # This placeholder carries no success clock or source data. The authenticated
  # publisher preserves this province from its own verified storage.
  target.write_text(json.dumps({'province_id':p['id'],'province':p['name']}))
  p['last_error_at']=datetime.now(timezone.utc).isoformat()
  return p,'Latest verified snapshot is unavailable; server preservation required',round(time.monotonic()-start,1)
 if prior is None:prior={'source':p['url'].rstrip('/')+'/PuanDurumu','province':p['name'],'province_id':p['id'],'season':'2026-2027','groups':[]}
 if prior.get('province_id')!=p['id'] or prior.get('province')!=p['name']:raise ValueError('Prior province mismatch')
 try:
  data=collect(prior)
  checked=datetime.now(timezone.utc).isoformat()
  if data:
   # Existing app versions display last_success_at. Use the real batch start
   # only after a successful source read; failed provinces keep their old clock.
   data['source_checked_at']=data['last_success_at']
   data['collection_started_at']=collection_started_at
   data['last_success_at']=collection_started_at
   target.parent.mkdir(parents=True,exist_ok=True);tmp=target.with_suffix('.tmp');tmp.write_text(json.dumps(data,ensure_ascii=False,separators=(',',':')));tmp.replace(target)
   p.update(status='ready',snapshot='/data/provinces/'+p['id']+'.json')
  else:p.update(status='source_empty',snapshot=None)
  p['last_checked_at']=checked;p.pop('last_error_at',None)
  return p,None,round(time.monotonic()-start,1)
 except Exception as e:
  # A remotely fetched prior snapshot may be newer than the checkout.
  if prior.get('groups'):
   target.write_text(json.dumps(prior,ensure_ascii=False,separators=(',',':')))
   p.update(status='ready',snapshot='/data/provinces/'+p['id']+'.json')
  p['last_error_at']=datetime.now(timezone.utc).isoformat()
  return p,str(e),round(time.monotonic()-start,1)

def main():
 collection_started_at=datetime.now(timezone.utc).isoformat()
 registry=remote('data/provinces.json')
 if registry is None:raise ValueError('Live registry is unavailable; publication stopped')
 if len(registry)!=81 or len({p['id'] for p in registry})!=81:raise ValueError('Incomplete registry')
 results=[];errors=[];started=time.monotonic()
 with ThreadPoolExecutor(max_workers=3) as executor:
  futures=[executor.submit(one,dict(p),collection_started_at) for p in registry]
  for f in as_completed(futures):
   p,error,elapsed=f.result();results.append(p)
   print(json.dumps({'province':p['name'],'status':'preserved' if error else 'verified','seconds':elapsed,'error':error},ensure_ascii=False),flush=True)
   if error:errors.append({'province':p['name'],'error':error})
 results.sort(key=lambda p:int(p['id']))
 (ROOT/'provinces.json').write_text(json.dumps(results,ensure_ascii=False,separators=(',',':')))
 report={'started_at':collection_started_at,'finished_at':datetime.now(timezone.utc).isoformat(),'seconds':round(time.monotonic()-started,1),'checked':81-len(errors),'errors':errors}
 Path('collection-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
 print(json.dumps(report,ensure_ascii=False),flush=True)
if __name__=='__main__':main()
