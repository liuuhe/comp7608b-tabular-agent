"""UI for explicit human decisions; local saving has no browser downloads."""

HTML = r'''<!doctype html><html lang="zh-CN"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>最终评分裁决</title>
<style>
*{box-sizing:border-box}body{margin:0;background:#f5f5f1;color:#20342f;font:16px/1.65 system-ui,sans-serif}
header{background:#fff;border-bottom:1px solid #d8dfd8;padding:22px 5vw;display:flex;gap:24px;justify-content:space-between;align-items:center}
h1{font-size:27px;margin:0}h2{font-size:21px;margin:0 0 14px}h3{font-size:17px;margin:0 0 10px}
p{margin:8px 0}button{font:inherit;cursor:pointer}button:disabled{opacity:.5;cursor:default}
.muted{color:#65736d;font-size:14px}.layout{display:grid;grid-template-columns:235px minmax(0,1fr);max-width:1540px;margin:auto}
nav{padding:30px 16px 30px 25px;position:sticky;top:0;align-self:start}nav button{display:block;text-align:left;width:100%;border:0;border-left:3px solid transparent;background:none;padding:16px 12px;margin-bottom:7px;color:inherit}
nav button.active{background:#e5eee6;border-color:#31694f}nav small{display:block;font:12px/1.7 ui-monospace,monospace;color:#68786e}
main{padding:30px 35px;min-width:0}.columns{display:grid;grid-template-columns:minmax(0,1fr) 340px;gap:30px}
.evidence{background:white;padding:26px;border:1px solid #e1e5dc;min-width:0}.decisions{align-self:start;position:sticky;top:25px}
.question{white-space:pre-wrap;margin-bottom:22px}.report{white-space:pre-wrap;overflow-wrap:anywhere;font-size:14px;background:#f6f7f3;padding:15px}
details{border-top:1px solid #e2e6df;padding:13px 0}summary{cursor:pointer;font-weight:600}pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:13px}
.chart{width:100%;height:auto;margin:15px 0;border:1px solid #e0e6de}.scroll{overflow:auto}table{border-collapse:collapse;font-size:13px;white-space:nowrap}td,th{border-bottom:1px solid #dce3da;padding:5px 10px;text-align:left}
.decision{margin-bottom:20px;padding-bottom:22px;border-bottom:1px solid #d2dbd0}.finding{font-size:14px;white-space:pre-wrap;overflow-wrap:anywhere;max-height:230px;overflow:auto;margin-bottom:14px;color:#3d5147}
.scores{display:flex;gap:10px;margin:14px 0}.scores label{flex:1}.scores input{position:absolute;opacity:0;width:1px;height:1px}.scores span{display:block;border:1px solid #acbdae;border-radius:5px;text-align:center;padding:9px;font-size:19px;background:#fff;cursor:pointer}
.scores input:checked+span{border:2px solid #286045;padding:8px;background:#e2eee4;color:#154e30}.scores input:focus-visible+span{outline:3px solid #92bda3}
textarea{width:100%;min-height:64px;padding:9px;font:14px/1.5 inherit;border:1px solid #bac7b8;border-radius:4px;resize:vertical}
.clear{background:none;border:0;text-decoration:underline;color:#65736d;padding:0;font-size:13px}.bottom{display:flex;gap:12px;margin:22px 0;justify-content:space-between}.secondary{padding:8px 16px;border:1px solid #aabaaa;border-radius:5px;background:white;color:#304f3d}
#finish{width:100%;padding:13px;background:#275d41;color:white;border:0;border-radius:5px;font-weight:600;margin-top:8px}#notice{max-width:1540px;margin:0 auto;padding:12px 5vw;color:#356448}#notice.error{color:#a63227}#progress{font-weight:600;color:#275d41}#done{background:#e2eee4;padding:24px;border:1px solid #9cb69f;margin-bottom:20px}
@media(max-width:1100px){.columns{grid-template-columns:minmax(0,1fr) 300px;gap:18px}main{padding:25px 18px}.layout{grid-template-columns:195px minmax(0,1fr)}}
@media(max-width:820px){.layout,.columns{display:block}nav{position:static;display:flex;overflow:auto;padding:12px}nav button{min-width:170px}.decisions{position:static;margin-top:22px}header{align-items:start}main{padding:15px}.evidence{padding:18px}}
</style><header><div><h1>最终评分裁决</h1><p class="muted">只需决定有分歧的评分。选择后自动保存到本机，随时可回来继续。</p></div><div id="progress" role="status"></div></header>
<div id="notice" role="status">正在加载题目与初始评分…</div>
<div class="layout"><nav id="nav" aria-label="待裁决输出"></nav><main><div id="done" hidden></div><div class="columns"><section class="evidence" id="evidence"></section><aside class="decisions"><div id="decisions"></div><button id="finish" disabled>确认全部裁决并保存</button><p class="muted">两位评分者的初始记录会保留，最终裁决单独保存。</p></aside></div><div class="bottom"><button id="prev" class="secondary">上一份</button><button id="next" class="secondary">下一份</button></div></main></div>
<script>
const TOKEN='__TOKEN__';let state,index=0,decisions=[],queue=Promise.resolve(),saving=false,failed=false;
const $=id=>document.getElementById(id),key=r=>[r.id,r.finding,r.dimension].join('|');
const names={usefulness:'实用性',type:'图表类型',correctness:'正确性',grounding:'证据支撑',answer_correct:'答案正确',constraints_met:'明确要求',data:'图表数据',labels:'轴和标签',readability:'可读性',causal_overstatement:'因果夸大',clarification_justified:'澄清合理'};
function el(tag,text,parent){const e=document.createElement(tag);if(text!==undefined)e.textContent=text;if(parent)parent.appendChild(e);return e;}
function notice(text,error=false){$('notice').textContent=text;$('notice').className=error?'error':'';}
async function request(path,payload){const r=await fetch(path,payload?{method:'POST',headers:{'Content-Type':'application/json','X-Adjudication-Token':TOKEN},body:JSON.stringify(payload)}:{});const value=await r.json();if(!r.ok)throw Error(value.error||'无法连接本机服务');return value;}
function count(){return decisions.filter(r=>r.score!==null).length;}
function progress(){const n=count();$('progress').textContent=`已决定 ${n} / ${decisions.length} 项`;$('finish').disabled=n!==decisions.length||saving||failed||state.finalized;[...$('nav').children].forEach((b,i)=>{const rows=decisions.filter(r=>r.id===state.outputs[i].id);b.querySelector('.number').textContent=`${rows.filter(r=>r.score!==null).length}/${rows.length}`;});}
function saveDraft(){const snapshot=decisions.map(r=>({...r}));saving=true;progress();notice('正在保存…');queue=queue.then(async()=>{if(failed)return;const r=await request('/api/draft',{revision:state.revision,decisions:snapshot});state.revision=r.revision;notice('进度已保存到本机。');}).catch(e=>{failed=true;notice(e.message+' 请刷新页面后检查已保存进度。',true);}).finally(()=>{saving=false;progress();});}
function render(){const output=state.outputs[index],area=$('evidence');area.replaceChildren();[...$('nav').children].forEach((b,i)=>b.classList.toggle('active',i===index));
 el('h2',`第 ${index+1} 份输出`,area);el('div',output.id,area).className='muted';el('h3','原始题目',area);el('div',output.question,area).className='question';
 const docs=el('details',undefined,area);el('summary','字段说明',docs);el('pre',output.documentation,docs);
 if(output.charts.length){el('h3','输出图表',area);for(const c of output.charts){const img=el('img',undefined,area);img.src=c.src;img.alt=c.name;img.className='chart';}}
 const report=el('details',undefined,area);report.open=true;el('summary','完整报告',report);el('div',output.report,report).className='report';
 for(const t of output.tables){const detail=el('details',undefined,area);el('summary',`${t.name}（${t.total_rows} 行）`,detail);const scroll=el('div',undefined,detail);scroll.className='scroll';const table=el('table',undefined,scroll);t.rows.forEach((row,i)=>{const tr=el('tr',undefined,table);for(const value of row)el(i===0?'th':'td',value,tr);});if(t.total_rows>500)el('p','预览前500行；完整表保留在原评分材料中。',detail);}
 const target=$('decisions');target.replaceChildren();
 for(const d of state.disputes.filter(r=>r.id===output.id)){const row=decisions.find(r=>key(r)===key(d)),box=el('section',undefined,target);box.className='decision';
  el('h3',`${d.finding?'发现 '+d.finding+' · ':''}${names[d.dimension]||d.dimension}`,box);
  if(d.finding&&output.findings[d.finding-1]){const snippet=output.findings[d.finding-1].split('\n  Evidence:')[0];el('div',snippet,box).className='finding';}
  el('p',`评分者 1：${d.rater_1} 分　评分者 2：${d.rater_2} 分`,box);
  el('p',d.dimension==='usefulness'?'0 无关　1 相关但泛泛　2 具体且有信息':d.dimension==='type'?'0 缺失或明显错误　1 部分满足　2 完全满足':`按原评分标准选择 0–${d.maximum} 分`,box).className='muted';
  const scores=el('div',undefined,box);scores.className='scores';
  for(let value=0;value<=d.maximum;value++){const label=el('label',undefined,scores),input=el('input',undefined,label);input.type='radio';input.name=key(d);input.value=String(value);input.checked=row.score===value;input.disabled=state.finalized;input.setAttribute('aria-label',`${output.id} 发现${d.finding} ${d.dimension} 最终${value}分`);el('span',String(value),label);input.addEventListener('change',()=>{row.score=value;saveDraft();});}
  if(!state.finalized){const clear=el('button','暂不决定',box);clear.className='clear';clear.addEventListener('click',()=>{row.score=null;render();saveDraft();});}
  const noteLabel=el('label',undefined,box);el('div','裁决理由（可选）',noteLabel).className='muted';const reason=el('textarea',undefined,noteLabel);reason.value=row.reason;reason.disabled=state.finalized;reason.maxLength=4000;reason.addEventListener('change',()=>{row.reason=reason.value;saveDraft();});
 }
 $('prev').disabled=index===0;$('next').disabled=index===state.outputs.length-1;progress();
}
async function start(){try{state=await request('/api/state');decisions=state.disputes.map(d=>state.decisions.find(r=>key(r)===key(d))||{id:d.id,finding:d.finding,dimension:d.dimension,score:null,reason:''});
 state.outputs.forEach((o,i)=>{const b=el('button',undefined,$('nav'));el('span',`第 ${i+1} 份 · `,b);el('span','',b).className='number';el('small',o.id,b);b.addEventListener('click',()=>{index=i;render();});});
 $('prev').addEventListener('click',()=>{index--;render();});$('next').addEventListener('click',()=>{index++;render();});
 $('finish').addEventListener('click',async()=>{await queue;if(failed)return;saving=true;progress();notice('正在保存最终裁决并汇总样本，请稍候…');try{const r=await request('/api/finalize',{revision:state.revision,decisions});state.finalized=r.finalized;showDone();render();}catch(e){notice(e.message,true);}finally{saving=false;progress();}});
 render();if(state.finalized)showDone();else notice(state.updated_at?'已恢复你保存的裁决进度。':'尚未预选分数。请根据证据决定每项最终评分。');
 }catch(e){notice(e.message,true);}}
function showDone(){$('done').hidden=false;$('done').textContent='最终裁决已保存，27份样本已完成汇总。回到对话告诉我“已完成”，我会继续更新报告。';notice('已保存完成。');}
start();
</script></html>'''
