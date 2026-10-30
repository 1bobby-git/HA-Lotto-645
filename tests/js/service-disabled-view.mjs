// A Lotto Lab number service the user turned off must read as a choice, not a fault.
import fs from 'node:fs';
import assert from 'node:assert/strict';

const source = fs.readFileSync('custom_components/lotto_645/www/lotto-panel-view.js', 'utf8');
const view = await import('data:text/javascript;base64,' + Buffer.from(source).toString('base64'));

const off = view.currentRecommendationText('service_disabled');
for (const text of [...off.empty, off.note]) {
  assert.ok(!text.includes('service_disabled'), `raw status code shown: ${text}`);
  assert.ok(!text.includes('서비스 연결을 확인'), `connection hint shown: ${text}`);
}
assert.match(off.empty[0], /번호 생성 서비스가 꺼져/);
for (const text of [off.empty[1], off.note]) {
  // Both the empty state and the note above saved numbers say where to turn it back on.
  assert.ok(text.includes('추첨 공식 · AI · 데이터 소스'), text);
  assert.ok(text.includes('Lotto Lab 번호 생성 서비스 사용'), text);
}

// Every other status keeps the previous wording.
assert.deepEqual(view.currentRecommendationText('ready'), {
  empty: ['현재 생성번호가 없습니다.', '공식 선택과 서비스 연결을 확인하세요. 기존 리뷰 기록은 보존됩니다.'],
  note: '',
});
assert.equal(view.currentRecommendationText(undefined).note, '');
assert.equal(view.currentRecommendationText('generating').note, '새 번호를 생성 중입니다. 이전 생성번호를 유지합니다. ');
assert.equal(view.currentRecommendationText('usage_limited').note, '서비스 상태: usage_limited · 저장된 생성번호를 표시합니다. ');
assert.match(view.currentRecommendationText('connection_unavailable').empty[1], /서비스 연결을 확인/);
