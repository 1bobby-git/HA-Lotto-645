import fs from 'node:fs';
import assert from 'node:assert/strict';
const source=fs.readFileSync('custom_components/lotto_645/www/lotto-result-notifications.js','utf8');
const {installResultNotifications}=await import('data:text/javascript;base64,'+Buffer.from(source).toString('base64'));
const saved=new Map();const notifications=[];let permissions=0;
globalThis.localStorage={getItem:k=>saved.get(k)||null,setItem:(k,v)=>saved.set(k,v),removeItem:k=>saved.delete(k)};
class NotificationFake {
 static permission='default';
 static async requestPermission(){permissions++;this.permission='granted';return 'granted';}
 constructor(title,options){notifications.push({title,options});}
 close(){}
}
globalThis.Notification=NotificationFake;
globalThis.window={isSecureContext:true,Notification:NotificationFake,focus(){}};
globalThis.document={hidden:true};
const queues=new Map();
Object.defineProperty(globalThis,'navigator',{value:{locks:{request(key,fn){const next=(queues.get(key)||Promise.resolve()).then(fn);queues.set(key,next);return next;}}},configurable:true});
class Panel {
 constructor(){this.isConnected=true;this._hass={user:{id:'user-a'}};this.entry={value:'entry-a'};this.button={setAttribute(){}};}
 node(id){return id==='entry'?this.entry:id==='result-notifications'?this.button:null;}
 render(){} updateResults(){} message(text){this.error=text;}
}
installResultNotifications(Panel);
const a=new Panel();a.render();assert.equal(permissions,0);
await a._toggleResultNotifications();assert.equal(permissions,1);
const alert={round:1244,key:'1244:1,2,3,4,5,6+7',title:'발표',message:'언론 임시 결과'};
await a._notifyLottoAnnouncement(alert);assert.equal(notifications.length,1); // background tab allowed
await a._notifyLottoAnnouncement(alert);assert.equal(notifications.length,1);
const b=new Panel();await b._notifyLottoAnnouncement(alert);assert.equal(notifications.length,1); // reload
const correction={...alert,key:'1244:1,2,3,4,5,6+8',title:'정정'};
await Promise.all([a._notifyLottoAnnouncement(correction),b._notifyLottoAnnouncement(correction)]);
assert.equal(notifications.length,2);assert.equal(notifications[0].options.tag,notifications[1].options.tag);
await a._toggleResultNotifications();await a._notifyLottoAnnouncement({...alert,key:'next'});assert.equal(notifications.length,2);
assert.equal(permissions,1);
console.log('browser notification opt-in, background, restart, multi-tab and correction tests passed');
