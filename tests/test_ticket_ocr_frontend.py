"""Execute the shipped OCR grouping helpers, not source-string assertions."""
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_physical_rows_preserve_slot_order_and_same_number_purchases():
    if not shutil.which('node'):
        pytest.skip('Node is required for the frontend grouping execution test')
    result = subprocess.run(['node', '--input-type=module', '-'], cwd=ROOT, text=True,
                            capture_output=True, input=r'''
import fs from 'node:fs';
import assert from 'node:assert/strict';
const source=fs.readFileSync('custom_components/lotto_645/www/lotto-ticket-ocr.js','utf8');
const {ticketRowsFromOcr,ticketLinesFromRows,ticketExpectedGames,singleGameTokens,retryDisagrees}=await import('data:text/javascript;base64,'+Buffer.from(source).toString('base64'));
const values=['1','7','12','24','33','45'];
const word=(text,x,y,height=24)=>({text,bbox:{x0:x,y0:y,x1:x+30,y1:y+height}});
const row=(slot,y)=>[word(slot+'Manual',100,y-4,28),...values.map((n,i)=>word(n,300+i*60,y+(i%2)*5))];
const data={text:'Total 5,000',words:[...row('E',420),...row('A',100),...row('C',260),...row('D',340),...row('B',180)].reverse()};
let lines=ticketLinesFromRows(ticketRowsFromOcr(data));
assert.deepEqual(lines,['A','B','C','D','E'].map(s=>[s,...values]));
assert.equal(ticketExpectedGames(data),5);
for(let count=1;count<=4;count++)assert.equal(ticketExpectedGames({text:`Total ${count},000`}),count);
assert.equal(ticketExpectedGames({text:'Unclear total'}),null);
assert.equal(ticketExpectedGames({text:'1,000 5,000'}),null);
assert.deepEqual(singleGameTokens({text:values.join(' ')}),values);
assert.equal(singleGameTokens({text:'1 7 l2 24 33 45'}),null);
assert.equal(singleGameTokens({text:'1 7 12 24 33 45 42'}),null);
// A missing middle row leaves C, D and E in their original slots.
lines=ticketLinesFromRows(ticketRowsFromOcr({words:[...row('A',100),...row('C',260),...row('D',340),...row('E',420)]}));
assert.deepEqual(lines.map(r=>r[0]),['A','C','D','E']);
// Short numeric metadata cannot become a game. Bad boxes are rejected.
assert.deepEqual(ticketRowsFromOcr({words:[word('2026/10/02',30,50),word('5,000',60,600),word('12345',100,60),{text:'12',bbox:{x0:NaN}}]}),[]);
assert.deepEqual(ticketLinesFromRows([{slot:null,tokens:values},{slot:'B',tokens:values,conflict:true}]),[['?A',...values],['?B',...values]]);
assert.equal(retryDisagrees(['1','7','12','24','33'],['1','7','13','24','33','45']),true);
assert.equal(retryDisagrees(['1','7','12','24','33'],values),false);
console.log('physical OCR row helpers passed');
''')
    assert result.returncode == 0, result.stdout + result.stderr
