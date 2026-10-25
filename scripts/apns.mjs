import {createPrivateKey,sign,createHash} from 'node:crypto';
import http2 from 'node:http2';
import {notificationCards,notificationTitle} from './notification_text.mjs';
export function providerToken({keyBase64,keyId,teamId},now=Math.floor(Date.now()/1000)) {
 if(!/^[A-Z0-9]{10}$/.test(keyId||'')||!/^[A-Z0-9]{10}$/.test(teamId||''))throw Error('APNs key configuration is missing');
 const key=createPrivateKey(Buffer.from(keyBase64||'','base64').toString('utf8'));
 if(key.asymmetricKeyType!=='ec' || key.asymmetricKeyDetails?.namedCurve!=='prime256v1')throw Error('APNs requires an EC P-256 private key');
 const encode=v=>Buffer.from(JSON.stringify(v)).toString('base64url');
 const value=encode({alg:'ES256',kid:keyId})+'.'+encode({iss:teamId,iat:now});
 return value+'.'+sign('sha256',Buffer.from(value),{key,dsaEncoding:'ieee-p1363'}).toString('base64url');
}
export function notification(target) {
 const latest=target.events.at(-1),cards=notificationCards(target.events);
 const title=notificationTitle(target.events);
 const shown=cards.slice(-3);
 const body=cards.length===1?cards[0].body:shown.map(c=>c.subtitle+'\n'+c.body).join('\n\n')+(cards.length>shown.length?'\n+'+(cards.length-shown.length)+' gelişme daha. Uygulamayı aç.':'');
 const collapse=createHash('sha256').update(target.id+target.events.map(e=>e.id).sort().join(',')).digest('hex');
 const payload={aps:{alert:{title,...(cards.length===1?{subtitle:cards[0].subtitle.slice(0,300)}:{}),body:Array.from(body).slice(0,1400).join('')},sound:'default','thread-id':'skor-'+target.province},province:target.province,group:cards.length===1?latest.group??null:null,event:latest.id};
 while(Buffer.byteLength(JSON.stringify(payload))>3900)payload.aps.alert.body=Array.from(payload.aps.alert.body).slice(0,-50).join('');
 return {collapse,payload};
}
export function sendAPNS(target,jwt,{connect=http2.connect}={}) {
 const host=target.environment==='sandbox'?'https://api.sandbox.push.apple.com':'https://api.push.apple.com';
 const {collapse,payload}=notification(target);
 return new Promise((resolve,reject)=>{
  const client=connect(host);let settled=false;
  const finish=(error,value)=>{if(settled)return;settled=true;clearTimeout(timer);client.close();error?reject(error):resolve(value);};
  const timer=setTimeout(()=>{client.destroy();finish(Error('APNs timed out'));},15000);
  client.on('error',()=>finish(Error('APNs connection failed')));
  const request=client.request({':method':'POST',':path':'/3/device/'+target.token,'authorization':'bearer '+jwt,'apns-topic':'com.torus.skorcepte','apns-push-type':'alert','apns-priority':'10','apns-expiration':String(Math.floor(Date.now()/1000)+21600),'apns-collapse-id':collapse});
  let status=0,body='';request.on('response',headers=>{status=Number(headers[':status']);});
  request.setEncoding('utf8');request.on('data',chunk=>{body+=chunk;if(body.length>4096)request.close();});
  request.on('error',()=>finish(Error('APNs request failed')));
  request.on('end',()=>{let reason='';try{reason=JSON.parse(body).reason??'';}catch{}finish(null,{status,reason});});
  request.end(JSON.stringify(payload));
 });
}
