/* Geometry-only OCR grouping. Images and OCR output never leave this browser. */
const numeric = text => /^\d{1,2}$/.test(text);
const numberLike = text => /^[\dIl|]{1,2}$/.test(text);
const valid = tokens => tokens.length===6 && tokens.every(t=>numeric(t)&&Number(t)>=1&&Number(t)<=45) && new Set(tokens.map(Number)).size===6;

export function ticketRowsFromOcr(data) {
  const nested=(data?.blocks||[]).flatMap(b=>(b.paragraphs||[]).flatMap(p=>(p.lines||[]).flatMap(l=>l.words||[])));
  const words=(data?.words?.length?data.words:nested).filter(w=>w&&typeof w.text==='string'&&w.bbox)
    .map(w=>({text:w.text.trim(),...w.bbox}))
    .filter(w=>w.text&&[w.x0,w.x1,w.y0,w.y1].every(Number.isFinite)&&w.x1>w.x0&&w.y1>w.y0);
  const heights=words.filter(w=>numberLike(w.text)).map(w=>w.y1-w.y0).sort((a,b)=>a-b);
  const tolerance=Math.max(4,(heights[Math.floor(heights.length/2)]||16)*.6);
  const rows=[];
  for(const word of words.sort((a,b)=>(a.y0+a.y1)-(b.y0+b.y1)||a.x0-b.x0)) {
    const center=(word.y0+word.y1)/2;
    const row=rows.at(-1);
    if(row&&Math.abs(row.center-center)<=tolerance) {
      row.words.push(word);
      row.center=row.words.reduce((sum,w)=>sum+(w.y0+w.y1)/2,0)/row.words.length;
    } else rows.push({center,words:[word]});
  }
  return rows.map(row=>{
    row.words.sort((a,b)=>a.x0-b.x0);
    // English OCR often joins the A-E marker to the Korean purchase mode.
    const marker=/^([A-E])(?:[^\d]|$)/.exec(row.words[0]?.text||'');
    const digits=row.words.filter(w=>numberLike(w.text));
    if(digits.length<4||digits.length>7)return null;
    const tokens=digits.map(w=>w.text);
    return {slot:marker?.[1]||null,tokens,valid:valid(tokens),columns:digits.map(w=>({x0:w.x0,x1:w.x1})),
      box:{x0:Math.min(...digits.map(w=>w.x0)),x1:Math.max(...digits.map(w=>w.x1)),
        y0:Math.min(...row.words.map(w=>w.y0)),y1:Math.max(...row.words.map(w=>w.y1))}};
  }).filter(Boolean);
}

export function ticketLinesFromRows(rows) {
  // A provisional position is useful in the editor, but must carry its '?' all
  // the way to server validation. Never disguise inferred slots as read labels.
  return rows.map((row,index)=>[row.slot&&!row.conflict?row.slot:`?${row.slot||String.fromCharCode(65+index)}`,...row.tokens]);
}

export function ticketExpectedGames(data) {
  // A printed 1,000-5,000 KRW total permits genuine shorter tickets. Without
  // a readable total, leave the count unknown and require manual review.
  const amounts=[...String(data?.text||'').matchAll(/\b([1-5])[,\.]000\b/g)].map(m=>Number(m[1]));
  return amounts.length&&new Set(amounts).size===1?amounts[0]:null;
}

export function retryDisagrees(previous,tokens) {
  const read=previous.filter(t=>numeric(t)&&Number(t)>=1&&Number(t)<=45).map(Number);
  return read.some(n=>!tokens.map(Number).includes(n));
}

export function singleGameTokens(data) {
  const tokens=String(data?.text||'').trim().split(/\s+/).filter(Boolean);
  return valid(tokens)?tokens:null;
}
