import {readFile} from 'node:fs/promises';
import {providerToken,sendAPNS} from './apns.mjs';
const base=process.env.SKOR_DATA_BASE_URL?.replace(/\/$/,'');
if(base!=='https://skor-cepte-service.spry-whale-0977.chatgpt.site')throw Error('Unexpected service origin');
async function runnerToken(){
 const url=new URL(process.env.ACTIONS_ID_TOKEN_REQUEST_URL);url.searchParams.set('audience',base);
 const r=await fetch(url,{headers:{authorization:'Bearer '+process.env.ACTIONS_ID_TOKEN_REQUEST_TOKEN},signal:AbortSignal.timeout(20000)});
 if(!r.ok)throw Error('GitHub OIDC request failed');return (await r.json()).value;
}
async function api(path,{method='GET',body}={}){
 const token=await runnerToken();
 const r=await fetch(base+path,{method,headers:{authorization:'Bearer '+token,...(body?{'content-type':'application/json'}:{})},body:body?JSON.stringify(body):undefined,signal:AbortSignal.timeout(120000)});
 if(!r.ok || !r.headers.get('content-type')?.includes('application/json'))throw Error('Service request failed: '+path+' ('+r.status+')');
 return r.json();
}
const mode=process.argv[2]||'--all';
if(!['--all','--publish-only','--push-only'].includes(mode))throw Error('Unknown delivery mode');
if(mode!=='--push-only'){
const registry=JSON.parse(await readFile('dist/data/provinces.json','utf8'));
const snapshots=await Promise.all(registry.filter(p=>p.status==='ready').map(p=>readFile('dist'+p.snapshot,'utf8').then(JSON.parse)));
const published=await api('/api/admin/publish',{method:'POST',body:{registry,snapshots}});
console.log(JSON.stringify({published_at:published.published_at,snapshots:published.snapshots,changes:published.changes}));
}
if(mode==='--publish-only')process.exit(0);
const keyId=process.env.APNS_KEY_ID,keyBase64=process.env.APNS_KEY_P8_BASE64,teamId=process.env.APPLE_TEAM_ID;
if(!keyId||!keyBase64||!teamId)throw Error('Data is published. Push delivery is not enabled: APNs secrets missing.');
let after='',accepted=0,invalid=0,checkedDevices=0,eligibleDevices=0,eligibleEvents=0;const failures=[];
const jwt=providerToken({keyId,keyBase64,teamId});
do{
 const batch=await api('/api/admin/push'+(after?'?after='+encodeURIComponent(after):''));
 checkedDevices+=batch.checkedDevices??batch.targets.length;
 eligibleDevices+=batch.targets.length;
 for(const target of batch.targets){
  eligibleEvents+=target.events.length;
  try{
   const result=await sendAPNS(target,jwt);
   const state=result.status===200?'accepted':result.status===410||['BadDeviceToken','DeviceTokenNotForTopic','Unregistered'].includes(result.reason)?'invalid':null;
   if(!state){failures.push(result.status+':'+result.reason);continue;}
   await api('/api/admin/ack',{method:'POST',body:{device:target.id,events:target.events.map(e=>e.id),state,token:target.token}});
   state==='accepted'?accepted++:invalid++;
  }catch{failures.push('APNs delivery or acknowledgement failed');}
 }
 after=batch.next??'';
}while(after);
console.log(JSON.stringify({checkedDevices,eligibleDevices,eligibleEvents,accepted,invalid,failed:failures.length}));
if(failures.length)throw Error('Some notifications remain pending for retry: '+[...new Set(failures)].join(', '));
