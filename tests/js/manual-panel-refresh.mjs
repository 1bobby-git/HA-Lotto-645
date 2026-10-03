import fs from 'node:fs';
import vm from 'node:vm';
import assert from 'node:assert/strict';
const read = name => fs.readFileSync('custom_components/lotto_645/www/'+name,'utf8');
const tick = async () => {for(let i=0;i<8;i++) await Promise.resolve();};
const timers=[]; const listeners=[]; const notices=[];
globalThis.document={hidden:false,addEventListener:(...a)=>listeners.push(a),removeEventListener(){}};
globalThis.window={addEventListener:(...a)=>listeners.push(a),removeEventListener(){}};
globalThis.setTimeout=(fn,delay)=>{timers.push({fn,delay});return timers.length;};
globalThis.clearTimeout=()=>{};
let eventCallback;let loads=0;let refreshes=0;
class Panel {
 constructor(){this.isConnected=true;this.entry={value:'a'};this.status={};this.check={};this._hass={connection:{subscribeMessage:async cb=>{eventCallback=cb;return ()=>{};},addEventListener:(...a)=>listeners.push(a)}};}
 node(id){return id==='entry'?this.entry:id==='sync-status'?this.status:id==='check'?this.check:null;}
 _start(){} render(){} updateResults(){} syncAvailability(){} message(){}
 async request(){return {result_verification:{status:'official_history'}};}
 async operation(action){await action();}
 async load(){loads++;} async refreshStatus(){refreshes++;}
 _notifyLottoAnnouncement(alert){notices.push(alert);}
}
const {installLiveSync}=await import('data:text/javascript;base64,'+Buffer.from(read('lotto-panel-live.js')).toString('base64'));
globalThis.customElements={get:()=>Panel};globalThis.PANEL_TAG='test';globalThis.installLiveSync=installLiveSync;
vm.runInThisContext(read('lotto-panel.js').replace(/^import .*;\n/gm,''));
const panel=new Panel();panel._ensureLiveSubscription();await tick();
assert.equal(loads+refreshes,0,'subscription must not reload visible data');
for(let i=0;i<5;i++)eventCallback({entry_id:'a'});
eventCallback({entry_id:'a',announcement:{key:'result'}});
eventCallback({entry_id:'other',announcement:{key:'wrong'}});
await tick();assert.equal(loads+refreshes,0);assert.equal(notices.length,1);
assert.equal(listeners.length,0,'no ready/focus/visibility/pageshow auto refresh listeners');
assert.equal(timers.length,0,'no polling/wake timers on a healthy subscription');
panel.updateResults({result_verification:{status:'official_history'}});
panel.updateResults({result_verification:{status:'waiting'}});
assert.equal(timers.length,0,'neither waiting nor official result schedules refresh');
panel._queueLiveRefresh();await tick();assert.equal(loads+refreshes,0);
panel._queueLiveRefresh(true);await tick();assert.equal(loads,1,'explicit entry change still loads');
panel.render();await panel.check.onclick();assert.equal(refreshes,1,'manual result check still refreshes');
// The core itself must never create a legacy interval before a wrapper cancels it.
assert.ok(!read('lotto-panel-core.js').includes('setInterval('));
// Execute finalization completion to verify it no longer rearms a five-second poll.
let Finalization;
globalThis.HTMLElement=class {};
globalThis.customElements={get:()=>null,define:(name,cls)=>{assert.equal(name,'lotto-finalization-panel-v2-4-23');Finalization=cls;}};
vm.runInThisContext(read('finalization-panel.js'));
const finalPanel=new Finalization();finalPanel.isConnected=true;let finalCalls=0;
finalPanel.adapter=async()=>{finalCalls++;return {};};finalPanel.availability=()=>{};finalPanel.render=()=>{};
await finalPanel.perform('refresh');assert.equal(finalCalls,1);assert.equal(timers.length,0);
finalPanel.built=true;finalPanel.connectedCallback();await tick();assert.equal(finalCalls,1,'reconnect must not fetch');
console.log('manual page refresh: passive events/timers quiet, announcements and user actions preserved');
// Integration changes clear the old finalization display and disable its actions.
const widgets=['results','source','resultSelect','blocked'];
for(const id of widgets)finalPanel[id]={replaceChildren(){this.cleared=true;}};
for(const id of ['start','additional','cancel','refresh','useNew'])finalPanel[id]={};
finalPanel.count={value:'5'};finalPanel.message={};finalPanel.data={state:{pending:true}};
finalPanel.availability=Finalization.prototype.availability;
const contextPanel={shadowRoot:{querySelector:()=>({}),getElementById:id=>id==='screen-review'?{querySelector:()=>finalPanel}:null}};
const {applyFinalizationPanel}=await import('data:text/javascript;base64,'+Buffer.from(read('finalization-ha.js').replace(/^import .*;\n/gm,'')).toString('base64'));
applyFinalizationPanel(contextPanel);contextPanel._resetFinalizationContext();
assert.equal(finalPanel.data,null);
assert.equal(finalPanel.cancel.disabled,true);assert.equal(finalPanel.start.disabled,true);
assert.equal(finalPanel.useNew.disabled,true);assert.equal(finalPanel.results.cleared,true);
