let activeDeal = null;
let apiAvailable = false;
let creatingDeal = false;

const API_BASE = (location.protocol === 'file:')
  ? 'http://127.0.0.1:8000'
  : '';

async function api(path, options={}) {
  const r = await fetch(API_BASE + path, {
    ...options,
    headers: {'Content-Type':'application/json', ...(options.headers||{})}
  });
  if(!r.ok) {
    let detail = '';
    try { detail = await r.text(); } catch (_) {}
    throw new Error(detail || `Request failed (${r.status})`);
  }
  return r.json();
}
function money(v){return new Intl.NumberFormat('en-US',{style:'currency',currency:'USD',maximumFractionDigits:0}).format(Number(v||0));}
function escapeHtml(s=''){return String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[c]));}
function toast(message,type='success'){const el=document.getElementById('toast');if(!el)return;el.textContent=message;el.className='toast show '+type;clearTimeout(window.__toast);window.__toast=setTimeout(()=>el.className='toast',3200);}

function setHealth(health){
  const badge=document.getElementById('healthBadge');
  if(!badge)return;
  badge.innerHTML=`<i></i> ${health.hindsight_configured?'HINDSIGHT LIVE':'BACKEND ONLINE'}`;
  badge.className='status-pill '+(health.hindsight_configured?'live':'fallback');
}

async function init(){
  const badge=document.getElementById('healthBadge');

  // Health is independent from the rest of dashboard rendering.
  try{
    const health=await api('/api/health');
    apiAvailable=true;
    setHealth(health);
  }catch(e){
    apiAvailable=false;
    if(badge){
      badge.innerHTML='<i></i> BACKEND OFFLINE';
      badge.className='status-pill fallback';
    }
    console.error('Backend health check failed:',e);
    setInitialExperienceState();
    return;
  }

  // A secondary endpoint failing must NOT turn a healthy backend red.
  try{
    const deals=await api('/api/deals');
    if(!deals.length){
      activeDeal=await api('/api/deals',{
        method:'POST',
        body:JSON.stringify({
          name:'Enterprise Revenue Intelligence',
          company:'Northstar Analytics',
          value:185000,
          stage:'Negotiation',
          owner:'Sales Rep',
          summary:'Enterprise analytics deal. Current concerns: price, Competitor X and implementation risk.'
        })
      });
    }else{
      activeDeal=deals[0];
    }
    renderDeal();
  }catch(e){
    console.error('Deal loading failed:',e);
    toast('Backend is online, but the deal workspace could not be loaded.','error');
    setInitialExperienceState();
    return;
  }

  // Dashboard widgets are independent; one broken widget should not break the page.
  const results=await Promise.allSettled([
    refreshStats(),
    refreshTimeline(),
    refreshPlaybook()
  ]);
  results.forEach((r,i)=>{
    if(r.status==='rejected') console.error(`Dashboard widget ${i+1} failed:`,r.reason);
  });
  setInitialExperienceState();
}
function setInitialExperienceState(){
  const count=document.getElementById('memoryCount');
  if(count && activeDeal===null) count.textContent='—';
}

function renderDeal(){
  if(!activeDeal)return;
  const name=document.getElementById('dealName'); if(name) name.textContent=activeDeal.name;
  const company=document.getElementById('dealCompany'); if(company) company.textContent=activeDeal.company;
  const value=document.getElementById('dealMeta'); if(value) value.textContent=money(activeDeal.value);
  const stage=document.getElementById('dealStage'); if(stage) stage.textContent=String(activeDeal.stage||'').toUpperCase();
  const owner=document.getElementById('dealOwner'); if(owner) owner.textContent=String(activeDeal.owner||'').toUpperCase();
  const summary=document.getElementById('dealSummary'); if(summary) summary.textContent=activeDeal.summary||'No summary yet.';
}

async function refreshStats(){
  if(!activeDeal)return;
  const s=await api('/api/stats/'+activeDeal.id);
  const exp=document.getElementById('expCount'); if(exp) exp.textContent=s.experiences;
  const pos=document.getElementById('posCount'); if(pos) pos.textContent=s.positive;
  const neg=document.getElementById('negCount'); if(neg) neg.textContent=s.negative;
  const learn=document.getElementById('learnCount'); if(learn) learn.textContent=Math.round(s.learning_ratio*100)+'%';
  const count=document.getElementById('memoryCount'); if(count) count.textContent=s.experiences;
}

async function seedExperiences(){
  if(!activeDeal)return;
  try{
    const r=await api('/api/seed',{method:'POST',body:JSON.stringify({deal_id:activeDeal.id,count:12})});
    toast(`Loaded ${r.seeded} realistic experiences.`);
    await refreshStats(); await refreshTimeline(); await refreshPlaybook();
  }catch(e){toast('Could not seed experiences.','error');}
}

async function generate(){
  if(!activeDeal)return toast('Create or load a deal first.','error');
  const situationEl=document.getElementById('situation');
  const situation=(situationEl?.value||'').trim();
  const rec=document.getElementById('recommendation');
  if(!rec)return;
  rec.classList.remove('empty');
  rec.innerHTML='<div class="loading">↻ Recalling experience and reflecting on outcomes…</div>';
  try{
    const r=await api('/api/recommend',{method:'POST',body:JSON.stringify({deal_id:activeDeal.id,situation})});
    const badge=document.getElementById('sourceBadge');
    if(badge){badge.textContent=r.source==='hindsight-reflect'?'HINDSIGHT RECALL + REFLECT':(r.source==='hindsight-recall'?'HINDSIGHT RECALL':'LOCAL EXPERIENCE EVIDENCE');badge.className='source-badge';}
    rec.innerHTML=formatRecommendation(r.answer);
    renderMemories(r.memories||[]);
    const proof=document.getElementById('memoryProof');
    if(proof){
      const live=r.source==='hindsight-reflect' || r.source==='hindsight-recall';
      proof.innerHTML=`<div class="proof-stat ${live?'live':''}><span>MEMORY SOURCE</span><b>${live?'HINDSIGHT':'LOCAL'}</b></div><div class="proof-stat"><span>RECALLED</span><b>${escapeHtml(r.memory_count||0)}</b></div><div class="proof-stat ${r.source==='hindsight-reflect'?'live':''}"><span>REFLECTION</span><b>${r.source==='hindsight-reflect'?'USED':'FALLBACK'}</b></div><div class="proof-stat"><span>RISK</span><b>${escapeHtml(r.risk||'—')}</b></div>`;
    }
    if(r.risk)setRisk(r.risk);
    document.getElementById('memory')?.scrollIntoView({behavior:'smooth',block:'center'});
  }catch(e){
    rec.innerHTML=`<div class="empty">${escapeHtml(e.message)}</div>`;
    toast('Recommendation failed. Check the backend/API.','error');
  }
}

function formatRecommendation(text=''){
  const sections=text.split(/\n(?=[A-Z][A-Z \-]+$)/);
  return sections.map(s=>{
    const idx=s.indexOf('\n');
    if(idx>0){
      const title=s.slice(0,idx).trim(),body=s.slice(idx+1).trim();
      return `<div class="rec-block"><div class="rec-title">${escapeHtml(title)}</div><div>${escapeHtml(body).replace(/\n/g,'<br>')}</div></div>`;
    }
    return `<div class="rec-text">${escapeHtml(s).replace(/\n/g,'<br>')}</div>`;
  }).join('');
}

function renderMemories(rows){
  const box=document.getElementById('memories');
  const meta=document.getElementById('evidenceMeta');
  const count=document.getElementById('memoryCount');
  if(!box)return;
  if(!rows.length){
    if(meta)meta.textContent='NO MATCHING EVIDENCE';
    box.innerHTML='<div class="empty">No matching evidence returned. Seed experiences and run the decision engine again.</div>';
    return;
  }
  if(meta)meta.textContent=`${rows.length} RELEVANT EXPERIENCES`;
  if(count)count.textContent=rows.length;
  box.innerHTML=rows.map((m,i)=>{
    const raw=typeof m==='string'?m:(m.content||m.title||'Memory');
    const signal=/failed|stalled|lost|rejected|poorly/i.test(raw)?'negative':'positive';
    return `<div class="memory-evidence ${signal}">
      <div class="memory-top"><span>MEMORY ${String(i+1).padStart(2,'0')}</span><em>${signal==='positive'?'WORKED':'FAILED'}</em></div>
      <p>${escapeHtml(raw)}</p>
    </div>`;
  }).join('');
}

function setRisk(risk){
  const pill=document.getElementById('riskPill');
  if(pill){pill.textContent=String(risk||'unknown').toUpperCase();pill.className='risk '+String(risk||'').toLowerCase();}
}

async function refreshTimeline(){
  if(!activeDeal)return;
  const r=await api('/api/learning/'+activeDeal.id);
  const box=document.getElementById('timeline');
  if(!box)return;
  box.innerHTML=r.timeline.length
    ? r.timeline.slice(0,8).map(x=>`<div class="event ${x.signal}"><span>${escapeHtml(x.title)}</span><small>${escapeHtml(x.outcome)}</small></div>`).join('')
    : '<div class="empty">No experiences yet.</div>';
}

async function refreshPlaybook(){
  if(!activeDeal)return;
  const r=await api('/api/playbook/'+activeDeal.id);
  const box=document.getElementById('playbook');
  if(!box)return;
  box.innerHTML=`<div class="play-row"><span>WINNING PATTERNS</span>${(r.winning_patterns||[]).map(x=>`<div class="pattern positive">✓ ${escapeHtml(x)}</div>`).join('')||'<div class="empty">No positive pattern yet.</div>'}</div><div class="play-row"><span>FAILED PATTERNS</span>${(r.failed_patterns||[]).map(x=>`<div class="pattern negative">× ${escapeHtml(x)}</div>`).join('')||'<div class="empty">No failed pattern yet.</div>'}</div>`;
}

async function retainAutopsy(){
  if(!activeDeal)return toast('Create or load a deal first.','error');
  const title=document.getElementById('autopsyTitle')?.value.trim()||'Deal autopsy';
  const content=document.getElementById('autopsyContent')?.value.trim()||'';
  const outcome=document.getElementById('autopsyOutcome')?.value||'Failed / stalled';
  if(!content)return toast('Add what happened first.','error');
  try{
    const r=await api('/api/autopsy',{method:'POST',body:JSON.stringify({deal_id:activeDeal.id,title,content,outcome})});
    toast(r.hindsight==='retained-in-hindsight'?'Experience retained in Hindsight.':'Experience saved locally.');
    document.getElementById('autopsyContent').value='';
    await refreshStats();await refreshTimeline();await refreshPlaybook();
  }catch(e){toast('Could not retain experience.','error');}
}

async function runLearningExperiment(){
  if(!activeDeal)return toast('Create or load a deal first.','error');
  const panel=document.getElementById('experimentPanel');
  if(!panel)return;
  panel.innerHTML='<div class="experiment-placeholder"><div class="big-icon">↻</div><div><strong>Running the learning loop…</strong><span>Evaluating cold-start advice, retaining the outcome, then running the same situation again.</span></div></div>';
  try{
    const r=await api('/api/learning-experiment',{method:'POST',body:JSON.stringify({
      deal_id:activeDeal.id,
      situation:document.getElementById('situation')?.value.trim()||'The customer says our price is too high and Competitor X is cheaper.'
    })});
    const hs=r.hindsight||{};
    const hsStatus=hs.used?'LIVE HINDSIGHT':'LOCAL FALLBACK';
    panel.innerHTML=`<div class="experiment-grid">
      <div class="exp-box before"><div class="exp-label">BEFORE MEMORY</div><h3>${escapeHtml(r.before.label)}</h3><p class="action-quote">“${escapeHtml(r.before.action)}”</p><p class="why">${escapeHtml(r.before.why)}</p></div>
      <div class="exp-arrow">→</div>
      <div class="exp-box after"><div class="exp-label">AFTER HINDSIGHT</div><h3>${escapeHtml(r.after.label)}</h3><p class="action-quote">“${escapeHtml(r.after.action)}”</p><p class="why">${escapeHtml(r.after.why)}</p><div class="after-meta">${escapeHtml(r.after.memory_count)} recalled · ${escapeHtml(r.after.wins)} positive · ${escapeHtml(r.after.fails)} negative</div></div>
      <div class="retained-strip"><span>01 RETAIN · ${escapeHtml(r.retained.status)}</span><strong>${escapeHtml(r.retained.outcome)}</strong></div>
      <div class="lesson-strip"><span>02 RECALL → 03 REFLECT · ${escapeHtml(hsStatus)}</span><p>${escapeHtml(r.retained.lesson)}</p></div>
      <div class="delta ${r.changed?'changed':''}">${r.changed?'✓ MEMORY CHANGED THE DECISION':'• Experience retained for the next recall cycle'}</div>
      <div class="hindsight-proof">
        <div class="proof-stat ${hs.used?'live':''}"><span>HINDSIGHT</span><b>${hs.used?'LIVE':'OFF'}</b></div>
        <div class="proof-stat"><span>RECALLED</span><b>${escapeHtml(hs.recall_count||r.after.memory_count||0)}</b></div>
        <div class="proof-stat ${hs.reflect_used?'live':''}"><span>REFLECT</span><b>${hs.reflect_used?'USED':'FALLBACK'}</b></div>
        <div class="proof-stat ${r.changed?'live':''}"><span>DECISION DELTA</span><b>${r.changed?'YES':'NO'}</b></div>
      </div>
    </div>`;
    toast(r.changed?'Learning demonstrated: the recommendation changed.':'Experience retained; recommendation remained stable.');
    await refreshStats();await refreshTimeline();await refreshPlaybook();
  }catch(e){
    panel.innerHTML=`<div class="empty">${escapeHtml(e.message)}</div>`;
    toast('Learning experiment failed.','error');
  }
}

function openDealModal(){
  const modal=document.getElementById('modal');
  if(!modal)return;
  modal.classList.remove('hidden');
  setTimeout(()=>document.getElementById('dName')?.focus(),50);
}
function closeDealModal(){document.getElementById('modal')?.classList.add('hidden');}
async function createDeal(){
  if(creatingDeal)return;
  const nameEl=document.getElementById('dName');
  const companyEl=document.getElementById('dCompany');
  const valueEl=document.getElementById('dValue');
  const stageEl=document.getElementById('dStage');
  const ownerEl=document.getElementById('dOwner');
  const summaryEl=document.getElementById('dSummary');

  const deal={
    name:(nameEl?.value||'').trim(),
    company:(companyEl?.value||'').trim(),
    value:Number(valueEl?.value||0),
    stage:stageEl?.value||'Discovery',
    owner:(ownerEl?.value||'Sales Rep').trim()||'Sales Rep',
    summary:(summaryEl?.value||'').trim()
  };

  if(!deal.name)return toast('Enter a deal name.','error');
  if(!deal.company)return toast('Enter a company name.','error');
  if(!Number.isFinite(deal.value)||deal.value<0)return toast('Enter a valid deal value.','error');

  creatingDeal=true;
  const button=document.querySelector('#modal .decision-btn');
  const original=button?.innerHTML;
  if(button){button.disabled=true;button.innerHTML='Creating deal…';}

  try{
    activeDeal=await api('/api/deals',{method:'POST',body:JSON.stringify(deal)});
    closeDealModal();
    renderDeal();
    await Promise.allSettled([refreshStats(),refreshTimeline(),refreshPlaybook()]);
    document.getElementById('decision')?.scrollIntoView({behavior:'smooth',block:'start'});
    toast(`Deal "${deal.name}" created successfully.`);
    if(nameEl)nameEl.value='';
    if(companyEl)companyEl.value='';
    if(valueEl)valueEl.value='';
    if(stageEl)stageEl.value='Discovery';
    if(ownerEl)ownerEl.value='Sales Rep';
    if(summaryEl)summaryEl.value='';
  }catch(e){
    console.error('Create deal failed:',e);
    toast(`Could not create deal: ${e.message}`,'error');
  }finally{
    creatingDeal=false;
    if(button){button.disabled=false;button.innerHTML=original||'Create deal <span>→</span>';}
  }
}

document.addEventListener('keydown',e=>{
  if((e.ctrlKey||e.metaKey)&&e.key==='Enter')generate();
  if(e.key==='Escape')closeDealModal();
});

function bootExperienceUI(){
  document.documentElement.classList.add('js-reveal');
  const reduced=window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const revealEls=document.querySelectorAll('.reveal');
  if(!reduced && 'IntersectionObserver' in window){
    const io=new IntersectionObserver(entries=>entries.forEach(entry=>{
      if(entry.isIntersecting){entry.target.classList.add('in-view');io.unobserve(entry.target);}
    }),{threshold:0.12,rootMargin:'0px 0px -8% 0px'});
    revealEls.forEach(el=>io.observe(el));
  } else revealEls.forEach(el=>el.classList.add('in-view'));

  const glow=document.querySelector('.cursor-glow');
  if(glow && !reduced){
    let gx=innerWidth/2,gy=innerHeight/2,tx=gx,ty=gy;
    addEventListener('pointermove',e=>{tx=e.clientX;ty=e.clientY},{passive:true});
    const tick=()=>{gx+=(tx-gx)*.12;gy+=(ty-gy)*.12;glow.style.transform=`translate3d(${gx-180}px,${gy-180}px,0)`;requestAnimationFrame(tick)};tick();
  }

  document.querySelectorAll('.magnetic').forEach(el=>{
    el.addEventListener('pointermove',e=>{
      const r=el.getBoundingClientRect();
      el.style.transform=`translate3d(${(e.clientX-r.left-r.width/2)*.12}px,${(e.clientY-r.top-r.height/2)*.12}px,0)`;
    });
    el.addEventListener('pointerleave',()=>el.style.transform='');
  });

  const parallaxEls=document.querySelectorAll('[data-parallax]');
  const loop=document.querySelector('.loop-scene');
  const loopPath=document.getElementById('loopPath');
  const loopNodes=document.querySelectorAll('.loop-node');
  if(loopPath){ const len=loopPath.getTotalLength(); loopPath.style.strokeDasharray=`${len} ${len}`; loopPath.style.strokeDashoffset=len; }
  const updateScroll=()=>{
    const vh=innerHeight;
    parallaxEls.forEach(el=>{
      const rect=el.getBoundingClientRect();
      const speed=Number(el.dataset.parallax||0);
      el.style.setProperty('--parallax-y',`${(-rect.top+vh*.5)*speed}px`);
    });
    if(loop){
      const r=loop.getBoundingClientRect();
      const p=Math.max(0,Math.min(1,(vh-r.top)/(vh+r.height*.45)));
      loop.style.setProperty('--scroll-progress',p.toFixed(3));
      if(loopPath){ const len=loopPath.getTotalLength(); loopPath.style.strokeDashoffset=(1-p)*len; }
      loopNodes.forEach((node,i)=>node.classList.toggle('active',p>=Math.min(0.99,(i+1)/4)));
    }
  };
  let raf=0;
  addEventListener('scroll',()=>{if(!raf)raf=requestAnimationFrame(()=>{raf=0;updateScroll();})},{passive:true});
  updateScroll();
}

window.DealRescueUI={boot:bootExperienceUI};

if(document.readyState==='loading') document.addEventListener('DOMContentLoaded',()=>{init();bootExperienceUI();});
else {init();bootExperienceUI();}
