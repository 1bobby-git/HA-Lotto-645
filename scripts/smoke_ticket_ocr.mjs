/* Run with Node 22+ and LOTTO_TEST_NODE_MODULES pointing at a temporary install
 * of tesseract.js@5.1.1 and @napi-rs/canvas@0.1.80. No network or user fixtures.
 * Executes the production OCR method against synthetic pixels using the exact
 * bundled WASM/traineddata. A Node canvas adapter is not a browser/HA UI test.
 */
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {mkdtempSync,writeFileSync,rmSync} from 'node:fs';
import {tmpdir} from 'node:os';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const modules=process.env.LOTTO_TEST_NODE_MODULES;
if(!modules)throw Error('Set LOTTO_TEST_NODE_MODULES to an isolated dependency directory');
const require=createRequire(import.meta.url);
const {Canvas,loadImage}=require(path.join(modules,'@napi-rs/canvas'));
const {createWorker}=require(path.join(modules,'tesseract.js'));
const scratch=mkdtempSync(path.join(tmpdir(),'lotto-ocr-smoke-'));
const core=path.join(root,'custom_components/lotto_645/www/ocr');
const adapter=path.join(modules,'tesseract.js/src/worker-script/node');
const workerPath=path.join(scratch,'worker.cjs');
writeFileSync(workerPath,`const p=${JSON.stringify(path.join(adapter,'getCore.js'))};require.cache[require.resolve(p)]={id:p,filename:p,loaded:true,exports:async()=>require(${JSON.stringify(path.join(core,'tesseract-core-lstm.wasm.js'))})};require(${JSON.stringify(path.join(adapter,'index.js'))});`);
globalThis.HTMLElement=class{};
globalThis.self=globalThis;
const elements=new Map();globalThis.customElements={get:n=>elements.get(n),define:(n,c)=>elements.set(n,c)};
globalThis.document={createElement:tag=>{assert.equal(tag,'canvas');return new Canvas(1,1);}};
await import(path.join(root,'custom_components/lotto_645/www/lotto-panel-core.js'));
const prototype=elements.get('lotto-ticket-panel').prototype;
const worker=await createWorker('eng',1,{workerPath,langPath:core,cacheMethod:'none'});
const games=[[1,7,12,24,33,45],[2,11,17,25,34,42],[1,7,12,24,33,45],[5,10,18,27,36,44],[3,11,19,28,32,41]];
function fixture(count=5){
  const c=new Canvas(942,2048),ctx=c.getContext('2d');
  ctx.fillStyle='#777';ctx.fillRect(0,0,942,2048);ctx.fillStyle='white';ctx.fillRect(120,400,704,1300);
  ctx.fillStyle='black';ctx.font='bold 40px sans-serif';ctx.fillText('LOTTO 6/45',180,520);ctx.fillText('2000',400,700);
  ctx.font='22px sans-serif';ctx.fillText('2030/01/01',300,820);
  for(let i=0;i<count;i++){
    const y=1040+i*82;ctx.font='28px sans-serif';ctx.fillText('ABCDE'[i]+' Manual',175,y);
    ctx.font='bold 32px sans-serif';games[i].forEach((n,col)=>ctx.fillText(String(n),400+col*64,y));
  }
  ctx.font='bold 48px sans-serif';ctx.fillText(`${count},000`,530,1540);return c;
}
try {
  let calls=0,inject=false;
  const wrapper={setParameters:p=>worker.setParameters(p),recognize:async canvas=>{
    calls++;const result=await worker.recognize(canvas.toBuffer('image/png'));
    if(inject){
      inject=false;
      // Deterministic simulation of a lost first E number in the first pass.
      // The retry still uses real pixels and the shipped OCR engine.
      for(const w of result.data.words||[])if(w.bbox.y0>1330&&w.bbox.y0<1380&&w.bbox.x0>390&&w.bbox.x0<450)w.text='';
    }
    return result;
  }};
  const owner={loadOcrEngine:async()=>({}),ocrAssetBase:()=>'',_ocrWorker:wrapper};
  for(const count of [5,1,2,3,4]){
    calls=0;
    const result=await prototype.ocrLines.call(owner,await loadImage(fixture(count).toBuffer('image/png')));
    assert.equal(result.expected_games,count);
    assert.deepEqual(result.lines,['A','B','C','D','E'].slice(0,count).map((s,i)=>[s,...games[i].map(String)]));
    console.log(`PASS: ${count} physical games, duplicate numbers preserved (${calls} OCR calls)`);
  }
  calls=0;inject=true;
  const recovered=await prototype.ocrLines.call(owner,await loadImage(fixture().toBuffer('image/png')));
  assert.deepEqual(recovered.lines[4],['E',...games[4].map(String)]);
  assert(calls>1,'the incomplete row must trigger an actual crop reread');
  console.log('PASS: incomplete E row recovered by real numeric-column crop OCR');

  // Real production draft/save methods: no writes at preview, all five values
  // on one explicit save; ticket identity and optimistic revision survive.
  const fields=Object.fromEntries('abcde'.split('').map(s=>[`game_${s}`,{value:''}]));
  let saved=null;
  const form={_newTicket:false,_revision:'revision-1',_ticketId:'synthetic-ticket',_loadedRound:2000,
    _touched:new Set(),node:id=>fields[id],selectedRound:()=>2000,
    request:async(type,payload)=>{
      if(type==='purchases_import_ocr'){assert.equal(payload.preview,true);return {imported:{values:Object.fromEntries(games.map((g,i)=>[`game_${'abcde'[i]}`,g.join(', ')])),game_count:5,needs_review:false,missing_slots:[]}};}
      assert.equal(type,'purchases_save');saved=payload;return {};
    },showGameSlots:()=>{},updateFormStatus:()=>({filled:5,valid:5}),showEditorStep:()=>{},message:()=>{},
    updateResults:()=>{},applyWallet:()=>{},restoreForm:()=>{},finishClose:()=>{},showScreen:()=>{}};
  globalThis.window={confirm:()=>true};
  await prototype.importOcrLines.call(form,recovered.lines,5);
  assert.equal(saved,null);assert.equal(form._editing,true);
  await prototype.save.call(form);
  assert.equal(Object.keys(saved.values).length,5);
  assert.equal(saved.values.game_a,saved.values.game_c);
  assert.equal(saved.ticket_id,'synthetic-ticket');assert.equal(saved.revision,'revision-1');
  console.log('PASS: draft only until explicit atomic save, ticket ID/revision retained');
  saved=null;form._photoExpectedGames=5;form.updateFormStatus=()=>({filled:4,valid:4});
  globalThis.window.confirm=()=>false;
  await prototype.save.call(form);assert.equal(saved,null);
  fields.round={value:''};fields.qr={value:''};form._busy=true;
  form.request=async()=>({round:2000,values:{game_a:games[0].join(', ')},game_count:1});
  globalThis.window.confirm=()=>true;
  await prototype.preview.call(form,'synthetic-qr');assert.equal(form._photoExpectedGames,null);
  console.log('PASS: declining partial save preserves storage; QR clears photo-count state');
} finally {await worker.terminate();rmSync(scratch,{recursive:true,force:true});}
