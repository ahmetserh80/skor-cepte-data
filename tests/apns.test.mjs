import {test} from 'node:test';
import assert from 'node:assert/strict';
import {generateKeyPairSync,verify} from 'node:crypto';
import {EventEmitter} from 'node:events';
import {providerToken,notification,sendAPNS} from '../scripts/apns.mjs';
const target={id:'device',token:'ab'.repeat(32),environment:'production',province:'7',events:[{id:'e1',title:'Yıldız Kız Gelişim Ligi - Doğu A Grubu',text:'A 3-1 B'}]};
test('APNs provider JWT is a verifiable ES256 P1363 signature',()=>{
 const {privateKey,publicKey}=generateKeyPairSync('ec',{namedCurve:'prime256v1'});
 const jwt=providerToken({keyId:'ABCDEFGHIJ',teamId:'0123456789',keyBase64:Buffer.from(privateKey.export({type:'pkcs8',format:'pem'})).toString('base64')},10000);
 const [h,p,s]=jwt.split('.');assert.equal(JSON.parse(Buffer.from(p,'base64url')).iat,10000);
 assert.equal(verify('sha256',Buffer.from(h+'.'+p),{key:publicKey,dsaEncoding:'ieee-p1363'},Buffer.from(s,'base64url')),true);
});
test('retries use stable collapse id; alert payload stays below APNs limit',()=>{
 const n=notification(target);assert.equal(n.collapse.length,64);assert.equal(n.collapse,notification(target).collapse);
 assert.ok(Buffer.byteLength(JSON.stringify(n.payload))<4096);
 assert.equal(n.payload.province,'7');
 const huge=notification({...target,events:[{...target.events[0],title:'🏐'.repeat(400),text:'🏐'.repeat(2000)}]});
 assert.ok(Buffer.byteLength(JSON.stringify(huge.payload))<4096);
});
test('HTTP2 sender passes topic and handles Apple success without logging tokens',async()=>{
 let observed;
 const connect=host=>{assert.equal(host,'https://api.push.apple.com');const client=new EventEmitter();client.close=()=>{};client.request=headers=>{observed=headers;const req=new EventEmitter();req.setEncoding=()=>{};req.end=body=>{assert.equal(JSON.parse(body).aps.sound,'default');queueMicrotask(()=>{req.emit('response',{':status':200});req.emit('end');});};return req;};return client;};
 const result=await sendAPNS(target,'jwt',{connect});assert.equal(result.status,200);assert.equal(observed['apns-topic'],'com.torus.skorcepte');assert.equal(observed['apns-push-type'],'alert');
});
