// Paineis que so aparecem em Resultados. Ficam fora de components.jsx para o App
// carrega-los sob demanda (React.lazy): quem so produz nao baixa este codigo.
import { useEffect, useState } from 'react';
import { TikTokLaunchButtons, isMobileDevice } from './serviceLinks';
import { analyzePublishedLink, listExperiments, listLinkAnalyses, openStudioFree, playbookCreateCampaign, productivityQueue, statusLabels, studioAudit, studioAuditLatest, studioPlaybook, studioPlaybookBuild } from './api';
import { CopyButton, GateCriticoPanel, estimateGateScores } from './components';
// Nomes em portugues para o tipo de cada ponto a melhorar (o servidor manda
// a chave tecnica, que aparecia crua na tela, ex.: "search").
const IMPROVE_KIND_LABELS={evitar:'Evitar',retencao:'Retenção',watch_pct:'% assistido',search:'Busca'};
export function PerformancePanel({c,busy,immutable,onError,onSavePerformance,onSaveExperiment,onGenerateInsights,onRefreshVariant,onGotoScript,onOpenStudio,onFetchStudioMetrics,onAuditStudioPosts,studioAuditReport,onSavePublishedLink}){
  const perfMap=(c.checklist&&c.checklist.performance)||{};
  // Sem variacoes geradas ainda, uma campanha "Rosa, Azul, Branco" aparecia
  // como uma aba so com as tres cores juntas. Agora vira uma aba por cor. Se
  // ja existir metrica salva com o nome junto (versao antiga), mantem a aba
  // antiga para nao esconder o que foi lancado.
  const colorList=c.colors||[];
  const variants=c.variants?.length?c.variants
    :(colorList.length>1&&!perfMap[c.color]&&!(c.checklist?.insights||{})[c.color])
      ?colorList.map(color=>({color,prompts:c.prompts,id:'main-'+color}))
      :[{color:c.color||'Produto',prompts:c.prompts,id:'main'}];
  const insightsMap=(c.checklist&&c.checklist.insights)||{};
  const videos=c.assets.filter(a=>a.kind==='video');
  const hasUrl=videos.some(v=>v.url||v.href||v.id);
  const [active,setActive]=useState(variants[0]?.color||'');
  const [metrics,setMetrics]=useState({});
  const [criticoNote,setCriticoNote]=useState('');
  const [gateRun,setGateRun]=useState(null);
  // Teste de gancho: agrupa campanhas que mudaram UMA coisa e mostra qual
  // rendeu mais por mil visualizacoes. Sem isso nao da para saber se o video
  // foi bem por causa do gancho, da peca, da cor ou do horario.
  const [experimento,setExperimento]=useState((c.checklist||{}).experiment||'');
  const [grupos,setGrupos]=useState([]);
  useEffect(()=>{setExperimento((c.checklist||{}).experiment||'')},[c.id,c.version]);
  useEffect(()=>{listExperiments().then(setGrupos).catch(()=>setGrupos([]))},[c.version]);
  const meuGrupo=grupos.find(g=>g.experiment===((c.checklist||{}).experiment||''));
  const slotUrl=((c.checklist&&c.checklist.slots)||{})[active||'']?.url||((c.checklist&&c.checklist.slots)||{})[active||'default']?.url||'';
  const [tiktokLink,setTiktokLink]=useState(c.published_url||slotUrl||'');
  useEffect(()=>{const su=((c.checklist&&c.checklist.slots)||{})[active||'']?.url||((c.checklist&&c.checklist.slots)||{})[active||'default']?.url||'';setTiktokLink(c.published_url||su||'');},[c.id,c.version,c.published_url,active]);
  useEffect(()=>{
    const key=active||'default';
    const prev=perfMap[key]||perfMap[active]||{};
    setMetrics({
      views_24h:prev.views_24h??'',views_7d:prev.views_7d??'',watch_pct:prev.watch_pct??'',
      likes:prev.likes??'',comments:prev.comments??'',saves:prev.saves??'',shares:prev.shares??'',
      orders:prev.orders??'',product_clicks:prev.product_clicks??'',revenue:prev.revenue??'',
      notes:prev.notes??''
    });
  },[active,c.version]);
  const variant=variants.find(v=>v.color===active)||variants[0];
  const key=variant?.color||'default';
  const card=insightsMap[key]||insightsMap['default'];
  const video=videos.find(v=>(v.slot||v.metadata?.color)===variant?.color)||videos[0];
  // inputMode abre o teclado numerico no celular (type=number sozinho abre o
  // teclado completo em varios Android).
  const field=(name,label,step='1')=><label className="metric-field" key={name}>{label}<input autoComplete="off" type={name==='notes'?'text':'number'} inputMode={name==='notes'?undefined:(step==='1'?'numeric':'decimal')} min={name==='notes'?undefined:'0'} step={step} value={metrics[name]??''} disabled={busy}
    onChange={e=>setMetrics(m=>({...m,[name]:e.target.value}))}/></label>;
  const num=v=>v===''||v==null?undefined:Number(v);
  const save=()=>onSavePerformance&&onSavePerformance({color:variant?.color,metrics:{
    views_24h:num(metrics.views_24h),views_7d:num(metrics.views_7d),watch_pct:num(metrics.watch_pct),
    likes:num(metrics.likes),comments:num(metrics.comments),saves:num(metrics.saves),shares:num(metrics.shares),
    orders:num(metrics.orders),product_clicks:num(metrics.product_clicks),
    revenue:num(metrics.revenue),notes:metrics.notes||undefined
  }});
  const scoreBox=(title,block)=><div className="score-card"><strong>{title}</strong><div className="score-num">{block?.score??'—'}</div><p>{block?.note||''}</p></div>;
  return <section className="performance-panel">
    <div className="section-title"><h3>Performance & Insights</h3><span className="help">métricas manuais · crítico local</span></div>
    <div className="publish-slot-tabs">{variants.map(v=><button type="button" key={v.color||'x'} className={'slot-tab'+(active===v.color?' active':'')} disabled={busy} onClick={()=>setActive(v.color)}>{v.color||'Produto'}</button>)}</div>
    {(() => {
      // Alcance nao paga comissao. R$/1k views e o unico numero que compara
      // um video de 200 mil views sem clique com um de 8 mil que vendeu.
      const atual=perfMap[active||'default']||perfMap[active]||{};
      const rpm=atual.revenue_per_1k;
      if(rpm==null) return <p className="help">Preencha comissão e views para o app calcular R$ por mil visualizações — é por esse número que vale ranquear o que repetir.</p>;
      return <div className="revenue-pill"><span>R$ por mil views</span><strong>{`R$ ${Number(rpm).toFixed(2)}`}</strong></div>;
    })()}
    <div className="metric-form">
      {field('views_24h','Visualizações 24h')}{field('views_7d','Visualizações 7 dias')}{field('watch_pct','% assistido','0.1')}
      {field('likes','Curtidas')}{field('comments','Comentários')}{field('saves','Salvamentos')}{field('shares','Compartilhamentos')}
      {field('product_clicks','Cliques no produto')}{field('orders','Pedidos')}{field('revenue','Comissão R$','0.01')}
      {field('notes','Notas')}
      <button type="button" className="primary" disabled={busy||!onSavePerformance} onClick={save}>Salvar métricas</button>
      <button type="button" disabled={busy||!onGenerateInsights} onClick={()=>onGenerateInsights({color:variant?.color})}>Gerar insights</button>
    </div>
    <section className="experiment-block">
      <div className="section-title"><h3>Teste de gancho</h3><span className="help">compare uma coisa por vez</span></div>
      <p className="help">Dê o mesmo nome a duas ou três campanhas da mesma peça em que só o gancho muda. O app ranqueia por R$ por mil visualizações — e usa retenção só enquanto não houver comissão lançada.</p>
      <div className="experiment-form">
        <input autoComplete="off" aria-label="Nome do teste" value={experimento} maxLength={80} disabled={busy}
          placeholder="ex.: gancho-legging-bolso" onChange={e=>setExperimento(e.target.value)}/>
        <button type="button" disabled={busy||!onSaveExperiment} onClick={()=>onSaveExperiment(experimento)}>Marcar campanha</button>
      </div>
      {meuGrupo&&meuGrupo.items.length>1&&<table className="experiment-table">
        <thead><tr><th>Gancho</th><th>{meuGrupo.ranked_by==='revenue_per_1k'?'R$/1k views':'Watch %'}</th></tr></thead>
        <tbody>{meuGrupo.items.map(item=><tr key={item.campaign_id} className={item.campaign_id===c.id?'is-current':''}>
          <td>{item.hook||'—'}</td>
          <td>{meuGrupo.ranked_by==='revenue_per_1k'
            ? (item.revenue_per_1k==null?'—':`R$ ${Number(item.revenue_per_1k).toFixed(2)}`)
            : (item.watch_pct==null?'—':`${item.watch_pct}%`)}</td>
        </tr>)}</tbody>
      </table>}
      {meuGrupo&&!meuGrupo.complete&&<small className="help">Falta lançar resultado de alguma campanha deste teste — só compare quando todas tiverem número.</small>}
    </section>
    {card?<>
      <div className="score-grid">
        {scoreBox('Hook',card.hook)}
        {scoreBox('Desenvolvimento',card.development)}
        {scoreBox('CTA',card.cta)}
        <div className="score-card overall"><strong>Geral</strong><div className="score-num">{card.overall??'—'}</div></div>
      </div>
      <div className="insight-actions">
        <strong>Ações</strong>
        <ul>{(card.actions||[]).map((a,i)=><li key={i}><button type="button" className="linkish" disabled={busy} onClick={()=>{
          if(onRefreshVariant&&variant?.id&&variant.id!=='main') onRefreshVariant(variant.id,['hook','development','cta','caption']);
          else if(onGotoScript) onGotoScript();
        }}>{a}</button></li>)}</ul>
      </div>
      <div className="insight-psych"><strong>Psicologia</strong><ul>{(card.psychology||[]).map((p,i)=><li key={i}>{p}</li>)}</ul></div>
    </>:<div className="notice">Salve métricas (opcional) e clique em <strong>Gerar insights</strong>.</div>}

      {(() => {
        const prev = perfMap[key] || perfMap[active] || {};
        const traffic = prev.traffic_source || [];
        const queries = prev.search_queries || [];
        const viewers = prev.viewers || {};
        const actions = prev.smart_actions || [];
        if (!traffic.length && !queries.length && !actions.length && viewers.total_viewers == null) return null;
        const g0 = (viewers.gender || [])[0];
        const a0 = (viewers.age || [])[0];
        const viewerBits = [];
        if (viewers.total_viewers != null) viewerBits.push('Total ' + viewers.total_viewers);
        if (viewers.new_viewers_pct != null) viewerBits.push('novos ' + viewers.new_viewers_pct + '%');
        if (g0) viewerBits.push((g0.label || '') + ' ' + (g0.pct_raw || ((g0.pct != null ? g0.pct + '%' : ''))));
        if (a0) viewerBits.push('idade ' + (a0.label || '') + ' ' + (a0.pct_raw || ''));
        return (
          <div className="audience-insights">
            <strong>Insights da coleta</strong>
            {traffic.length > 0 && (
              <div className="audience-block">
                <span className="audience-label">Traffic source</span>
                <ul>{traffic.slice(0,6).map((r,i) => <li key={i}><span>{r.label}</span><b>{r.pct_raw || (r.pct != null ? r.pct + '%' : '')}</b></li>)}</ul>
              </div>
            )}
            {queries.length > 0 && (
              <div className="audience-block">
                <span className="audience-label">Search queries</span>
                <ul>{queries.slice(0,6).map((r,i) => <li key={i}><span>{r.label}</span><b>{r.pct_raw || (r.pct != null ? r.pct + '%' : '')}</b></li>)}</ul>
              </div>
            )}
            {viewerBits.length > 0 && (
              <div className="audience-block">
                <span className="audience-label">Viewers</span>
                <p className="help" style={{margin:0}}>{viewerBits.join(' · ')}</p>
              </div>
            )}
            {actions.length > 0 && (
              <div className="audience-block audience-actions">
                <span className="audience-label">Melhorias da semana</span>
                <ul>{actions.map((a,i) => <li key={i}>{a}</li>)}</ul>
              </div>
            )}
          </div>
        );
      })()}

    
      {studioAuditReport?.report && (
        <div className="studio-audit-report">
          <strong>Auditoria dos publicados</strong>
          <p className="help">{studioAuditReport.message} · {studioAuditReport.created_at || ''}</p>
          {(studioAuditReport.report.summary?.patterns || []).length > 0 && (
            <ul className="audit-patterns">{(studioAuditReport.report.summary.patterns).map((p,i)=><li key={i}>{p}</li>)}</ul>
          )}
          <div className="audit-table-wrap">
            <table className="audit-table">
              <thead><tr><th>Video</th><th>Views</th><th>Watch%</th><th>Search</th><th>FYP</th><th>Score</th></tr></thead>
              <tbody>
                {(studioAuditReport.report.summary?.ranked || studioAuditReport.report.results || []).slice(0,10).map((r,i)=>{
                  const search=(r.traffic_source||[]).find(t=>(t.label||'').toLowerCase()==='search');
                  const fyp=(r.traffic_source||[]).find(t=>(t.label||'').toLowerCase()==='for you');
                  const title=(r.caption||r.tiktok_video_id||'').slice(0,42);
                  return (
                    <tr key={r.tiktok_video_id||i}>
                      <td title={r.caption||''}>{title}{r.error?' ⚠':''}</td>
                      <td>{r.views_7d ?? '—'}</td>
                      <td>{r.watch_pct ?? '—'}</td>
                      <td>{r.search_pct ?? search?.pct_raw ?? search?.pct ?? '—'}</td>
                      <td>{r.fyp_pct ?? fyp?.pct_raw ?? fyp?.pct ?? '—'}</td>
                      <td>{r.score ?? '—'}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

    <div className="studio-metrics-box">
      <div className="studio-metrics-head">
        <strong>Métricas do Studio</strong>
        <span className="help">Puxa views e % do TikTok Studio com o Chrome CDP desta creator.</span>
      </div>
      
    <div className="published-link-box">
      <div className="section-title"><h3>Link da publicacao no TikTok</h3><span className="help">cole o link do video ja publicado</span></div>
      <label className="metric-field full">URL do video
        <input autoComplete="off" type="url" placeholder="https://www.tiktok.com/@conta/video/123..." value={tiktokLink} disabled={busy} onChange={e=>setTiktokLink(e.target.value)}/>
      </label>
      <div className="studio-metrics-actions">
        <button type="button" className="primary" disabled={busy||!onSavePublishedLink||!tiktokLink.trim()} onClick={()=>onSavePublishedLink({published_url:tiktokLink.trim(),color:active||variants[0]?.color})}>Salvar link</button>
      </div>
      <p className="help">Com o link salvo, <strong>Coletar metricas</strong> abre o analytics desse video. Sem link, use <strong>Auditar publicados</strong> para comparar varios posts do Studio.</p>
      {c.published_url && <p className="help"><a href={c.published_url} target="_blank" rel="noreferrer">Abrir link salvo</a></p>}
    </div>

      <div className="studio-metrics-actions">
        <button type="button" className="primary" disabled={busy||!onFetchStudioMetrics} onClick={()=>onFetchStudioMetrics&&onFetchStudioMetrics(active||variants[0]?.color)}>Coletar métricas</button>
        <TikTokLaunchButtons disabled={busy||!onOpenStudio} onOpenStudio={event=>onOpenStudio?.(event)}/>
        <button type="button" className="button" disabled={busy||!onAuditStudioPosts} onClick={()=>onAuditStudioPosts&&onAuditStudioPosts()}>Auditar publicados (8)</button>
      </div>
      <p className="studio-metrics-tip">Na 1ª coleta, feche o Chrome (copia a sessão do perfil configurado). Depois pode deixar o Chrome normal aberto.</p>
    </div>
    <div className="critico-box">
      <button type="button" className="primary" disabled={busy} onClick={()=>{
        const prompts=(variant?.prompts)||c.prompts||{};
        const est=estimateGateScores({
          duration:video?.metadata?.duration,
          prompts,
          caption:(variant?.prompts&&variant.prompts.caption)||c.prompts?.caption||'',
          hasVideo:!!video
        });
        setGateRun({fileName:video?.original_name||video?.local_path||'video.mp4',...est});
        setCriticoNote(video?.local_path
          ?`Gate local rodou. Para áudio/cortes de verdade, mande o MP4 ao Critico de Vendas: ${video.local_path}`
          :'Gate local rodou (heurística de roteiro). Anexe o MP4 e/ou envie ao Critico de Vendas para gate visual.');
      }}>Rodar Gate - Critico</button>
      <button type="button" disabled={busy||!onGenerateInsights} onClick={()=>{
        onGenerateInsights({color:variant?.color});
        setCriticoNote(video?.local_path
          ?`Insights de texto gerados. Gate visual: use Rodar Gate ou o agente Critico com ${video.local_path}`
          :'Insights de texto gerados. Use Rodar Gate - Critico para o card animado.');
      }}>Gerar insights (texto)</button>
      {gateRun&&<GateCriticoPanel fileName={gateRun.fileName} scores={gateRun.scores} note={gateRun.note} autoStart/>}
      {criticoNote&&<p className="notice">{criticoNote}</p>}
      {video?.local_path&&<CopyButton text={video.local_path} label="Copiar caminho do MP4" onError={onError}/>}
      <small className="help">Gate no visual da Fábrica. Áudio/cortes reais = agente Critico assistindo o MP4 (skill TikTok Shop video gate).</small>
    </div>
  </section>;
}


// Fora do ResultsQuickTools: declarados dentro dele, viravam um componente novo a cada
// render e o React remontava os blocos (o campo de link perdia o foco a cada letra).
function pctNum(r){
  if(r==null) return 0;
  if(typeof r==='number') return r;
  const n=Number(String(r.pct_raw||r.pct||'').replace('%','').replace('<','').replace(',','.'));
  return Number.isFinite(n)?n:0;
}
function BarList({rows, limit=6, tone='purple'}){
  if(!rows||!rows.length) return <p className="help">Sem dados nesta coleta.</p>;
  const top=Math.max(...rows.map(pctNum), 1);
  return (
    <ul className={'metric-bars tone-'+tone}>
      {rows.slice(0,limit).map((r,i)=>{
        const p=pctNum(r);
        const w=Math.max(4, Math.round((p/top)*100));
        return (
          <li key={i}>
            <div className="metric-bar-meta"><span>{r.label}</span><strong>{r.pct_raw||`${p}%`}</strong></div>
            <div className="metric-bar-track"><i style={{width:w+'%'}}/></div>
          </li>
        );
      })}
    </ul>
  );
}
function StatPills({item}){
  const pills=[
    {k:'Views', v:item.views_7d??item.views_24h, tone:'purple'},
    {k:'Likes', v:item.likes, tone:'pink'},
    {k:'Comments', v:item.comments, tone:'purple'},
    {k:'Saves', v:item.saves, tone:'green'},
    {k:'Shares', v:item.shares, tone:'pink'},
    {k:'Watch', v:item.watch_pct!=null?item.watch_pct+'%':null, tone:item.watch_pct!=null&&item.watch_pct<10?'warn':'green'},
  ];
  return (
    <div className="analysis-pills">
      {pills.map(p=>(
        <div key={p.k} className={'analysis-pill tone-'+p.tone}>
          <span>{p.k}</span><strong>{p.v??'\u2014'}</strong>
        </div>
      ))}
    </div>
  );
}
function Collapse({id, title, defaultOpen=false, badge, children}){
  const key='rq-collapse-'+id;
  const [open,setOpen]=useState(()=>{
    try{
      const v=localStorage.getItem(key);
      if(v==='1') return true;
      if(v==='0') return false;
    }catch(e){}
    return defaultOpen;
  });
  function toggle(){
    setOpen(o=>{
      const n=!o;
      try{localStorage.setItem(key, n?'1':'0')}catch(e){}
      return n;
    });
  }
  return (
    <div className={'collapse-block'+(open?' open':'')}>
      <div className="collapse-head">
        <button type="button" className="collapse-toggle" onClick={toggle} aria-expanded={open}>
          <span className="collapse-chevron" aria-hidden="true">{open?'▾':'▸'}</span>
          <strong>{title}</strong>
          {badge!=null?<span className="count">{badge}</span>:null}
        </button>
        <button type="button" className="button analysis-action collapse-btn" onClick={toggle}>{open?'Recolher':'Expandir'}</button>
      </div>
      {open && <div className="collapse-body">{children}</div>}
    </div>
  );
}
export function ResultsQuickTools({busy,onBusy,onError,onFlash,tab='studio',onTab,onCreateFromPlaybook,onOpenProduce,onOpenCampaignResults}){
  const [url,setUrl]=useState('');
  const [note,setNote]=useState('');
  const [items,setItems]=useState([]);
  const [loading,setLoading]=useState(false);
  const [opening,setOpening]=useState(false);
  const [openId,setOpenId]=useState(null);
  const [batchReport,setBatchReport]=useState(null);
  const [batchDays,setBatchDays]=useState(null);
  const [batchSort,setBatchSort]=useState({key:'views',dir:'desc'});
  const [histSort,setHistSort]=useState({key:'views',dir:'desc'});
  const [playbook,setPlaybook]=useState(null);
  const [pbBusy,setPbBusy]=useState(false);
  const [queue,setQueue]=useState(null);
  const [creatingIdx,setCreatingIdx]=useState(null);

  async function refresh(){
    // As quatro leituras sao independentes: em paralelo, e a falha de uma nao esconde as outras.
    const [links,latest,pb,q]=await Promise.allSettled([listLinkAnalyses(),studioAuditLatest(),studioPlaybook(),productivityQueue()]);
    if(links.status==='fulfilled') setItems(links.value?.items||[]);
    if(latest.status==='fulfilled'&&latest.value?.report) setBatchReport(latest.value);
    if(pb.status==='fulfilled'&&pb.value?.playbook) setPlaybook(pb.value.playbook);
    if(q.status==='fulfilled') setQueue(q.value);
  }
  useEffect(()=>{refresh()},[]);

  async function runPeriodAudit(days){
    setBatchDays(days);
    setLoading(true);
    try{
      const r=await studioAudit({days,min_views:100});
      setBatchReport(r);
      await refresh();
      const n=r.report?.audited??0;
      const skip=r.report?.skipped_low_views??0;
      onFlash?.(r.message||`Lote ${days}d: ${n} videos (>=100 views).`);
      if(r.report?.date_filter_fallback){
        onFlash?.(`Janela ${days}d sem posts datados — usei os mais recentes com >=100 views (${n}).`);
      }
      if(skip) onFlash?.(`Ignorei ${skip} videos com menos de 100 views (Studio nao gera analytics).`);
      try{
        const built=await studioPlaybookBuild({days});
        if(built?.playbook) setPlaybook(built.playbook);
      }catch(e){/* optional */}
    }catch(e){onError?.(e.message||String(e))}
    finally{setLoading(false);setBatchDays(null)}
  }

  async function createBrief(index){
    if(onCreateFromPlaybook){ onCreateFromPlaybook(index); return; }
    setCreatingIdx(index); onBusy?.(true);
    try{
      const created=await playbookCreateCampaign({index});
      onFlash?.('Campanha criada do playbook: '+(created.name||created.id));
      await refresh();
    }catch(e){onError?.(e.message||String(e))}
    finally{setCreatingIdx(null); onBusy?.(false)}
  }
  async function buildPlaybook(){
    setPbBusy(true);
    try{
      const built=await studioPlaybookBuild({days:batchReport?.days});
      setPlaybook(built.playbook);
      onFlash?.(`Playbook atualizado com ${built.playbook?.sample_n||0} videos do lote.`);
    }catch(e){onError?.(e.message||String(e))}
    finally{setPbBusy(false)}
  }

  async function openStudio(){
    setOpening(true);
    try{
      const r=await openStudioFree();
      onFlash?.(r.message||'TikTok Studio aberto.');
    }catch(e){onError?.(e.message||String(e))}
    finally{setOpening(false)}
  }
  async function analyze(){
    if(!url.trim()){onError?.('Cole o link do video no TikTok.');return}
    await runAnalyze(url.trim(), note.trim());
    setUrl('');
  }
  async function reanalyze(item){
    const u=(item?.url||'').trim();
    if(!u){onError?.('Este item nao tem URL para reanalisar.');return}
    await runAnalyze(u, (item.note||'').trim());
  }
  async function runAnalyze(link, noteText){
    setLoading(true);
    try{
      const r=await analyzePublishedLink({url:link,note:noteText||''});
      const list=r.items||[r.item].filter(Boolean);
      setItems(list);
      if(list[0]) setOpenId(list[0].id||list[0].url);
      onFlash?.(r.item?.message||'Metricas do link coletadas.');
    }catch(e){onError?.(e.message||String(e))}
    finally{setLoading(false)}
  }

  function trafficPct(row, label){
    const t=(row.traffic_source||[]).find(x=>(x.label||'').toLowerCase()===label.toLowerCase());
    return t?pctNum(t):0;
  }
  function num(v){
    const n=Number(v);
    return Number.isFinite(n)?n:0;
  }
  function toggleSort(setSort, key){
    setSort(prev=>{
      if(prev.key===key) return {key, dir: prev.dir==='desc'?'asc':'desc'};
      return {key, dir:'desc'};
    });
  }
  function sortMark(sort, key){
    if(sort.key!==key) return '';
    return sort.dir==='desc'?' \u2193':' \u2191';
  }
  function sortedBatchRows(){
    const raw=(batchReport?.report?.summary?.ranked||batchReport?.report?.results||[]).slice();
    const {key,dir}=batchSort;
    const mul=dir==='desc'?-1:1;
    const val=(row)=>{
      if(key==='views') return num(row.views_7d??row.list_views);
      if(key==='watch') return num(row.watch_pct);
      if(key==='likes') return num(row.likes);
      if(key==='comments') return num(row.comments);
      if(key==='search') return num(row.search_pct??trafficPct(row,'search'));
      if(key==='fyp') return num(row.fyp_pct??trafficPct(row,'for you'));
      if(key==='score') return num(row.score);
      return 0;
    };
    raw.sort((a,b)=>{
      const av=val(a), bv=val(b);
      if(av===bv) return 0;
      return av>bv?mul:-mul;
    });
    return raw;
  }
  function sortedHistItems(){
    const raw=items.slice();
    const {key,dir}=histSort;
    const mul=dir==='desc'?-1:1;
    const val=(row)=>{
      if(key==='views') return num(row.views_7d??row.views_24h);
      if(key==='likes') return num(row.likes);
      if(key==='comments') return num(row.comments);
      if(key==='saves') return num(row.saves);
      if(key==='watch') return num(row.watch_pct);
      if(key==='date') return Date.parse(row.collected_at||0)||0;
      return 0;
    };
    raw.sort((a,b)=>{
      const av=val(a), bv=val(b);
      if(av===bv) return 0;
      return av>bv?mul:-mul;
    });
    return raw;
  }


  const batchRows=batchReport?.report?sortedBatchRows():[];
  const histRows=sortedHistItems();
  const activeTab = tab || 'studio';

  return (
    <section className="results-quick-tools">

      {activeTab==='agora' && (
        <div className="productivity-box">
          <div className="results-quick-header">
            <div>
              <span className="eyebrow">PRODUTIVIDADE</span>
              <h2>O que fazer agora</h2>
              <p className="help">Continuar campanhas, criar do playbook e pontos a melhorar — sem scroll infinito.</p>
            </div>
            <button type="button" className="button analysis-action" disabled={busy||loading} onClick={refresh}>Atualizar fila</button>
          </div>
          {!queue && <p className="help">Carregando fila… Rode um lote e gere o playbook se estiver vazio.</p>}
          {queue && (
            <>
              <Collapse id="prod-continue" title="Continuar produção" defaultOpen={true} badge={(queue.continue||[]).length}>
                {(queue.continue||[]).length===0 && <p className="help">Nenhuma campanha em andamento. Crie uma do playbook abaixo.</p>}
                <ul className="prod-list">
                  {(queue.continue||[]).map((c,i)=>(
                    <li key={c.campaign_id||i} className="prod-card">
                      <div>
                        <strong>{c.name}</strong>
                        <div className="help">{c.label} · {statusLabels[c.status]||c.status}{c.niche?` · ${c.niche}`:''}</div>
                        <div className="help"><em>Como:</em> {c.how}</div>
                      </div>
                      <button type="button" className="primary" disabled={busy} onClick={()=>onOpenProduce?.(c.campaign_id)}>Abrir Produzir</button>
                    </li>
                  ))}
                </ul>
              </Collapse>
              <Collapse id="prod-next" title="Criar do playbook" defaultOpen={true} badge={(queue.produce_next||[]).length}>
                {(queue.produce_next||[]).length===0 && <p className="help">Nenhuma sugestão ainda. Vá em Playbook e toque em Atualizar, ou rode o lote de 30 dias.</p>}
                <ul className="prod-list">
                  {(queue.produce_next||[]).map((v,i)=>(
                    <li key={i} className="prod-card">
                      <div>
                        <strong>[{v.niche}] {v.title}</strong>
                        <div className="help">Hook: <code>{v.spoken_hook}</code></div>
                        <div className="help">{v.shot_list}</div>
                        <ol className="howto-mini">{(v.howto_15s||[]).map((h,j)=><li key={j}>{h}</li>)}</ol>
                      </div>
                      <button type="button" className="primary" disabled={busy||creatingIdx===i} onClick={()=>createBrief(v.index??i)}>
                        {creatingIdx===i?'Criando…':'Criar campanha'}
                      </button>
                    </li>
                  ))}
                </ul>
              </Collapse>
              <Collapse id="prod-improve" title="Espaço para melhorar" defaultOpen={true} badge={(queue.improve||[]).length}>
                <ul className="prod-list improve">
                  {(queue.improve||[]).map((x,i)=>(
                    <li key={i} className="prod-card">
                      <div>
                        <span className={'chip tone-'+(x.kind==='evitar'?'pink':'purple')}>{IMPROVE_KIND_LABELS[x.kind]||x.kind}</span>
                        <strong> {x.title}</strong>
                        <div className="help"><em>O que fazer:</em> {x.action}</div>
                      </div>
                    </li>
                  ))}
                </ul>
                {(queue.do||[]).length>0 && (
                  <div className="playbook-panel tone-green" style={{marginTop:10}}>
                    <h4>Lembretes do playbook</h4>
                    <ul>{queue.do.map((d,i)=><li key={i}>{d}</li>)}</ul>
                  </div>
                )}
              </Collapse>
            </>
          )}
        </div>
      )}

      {activeTab==='studio' && (
        <>
          <div className="results-quick-header">
            <div>
              <span className="eyebrow">STUDIO</span>
              <h2>{isMobileDevice()?'Abrir TikTok e analisar link':'Abrir Studio e analisar link'}</h2>
              <p className="help">{isMobileDevice()?'Abra o TikTok na conta conectada no celular ou cole o link de um vídeo publicado para analisar.':'Sem passar por Produzir. Abra o TikTok Studio desta creator ou analise qualquer video ja publicado so com o link.'}</p>
            </div>
            <TikTokLaunchButtons className="button primary" disabled={busy||opening} opening={opening} onOpenStudio={openStudio}/>
          </div>
          <Collapse id="analyze-link" title="Analisar link antigo" defaultOpen={true}>
            <div className="analyze-link-box flat">
              <label className="metric-field full">Link do video publicado
                <input autoComplete="off" type="url" placeholder="https://www.tiktok.com/@conta/video/123..." value={url} disabled={busy||loading} onChange={e=>setUrl(e.target.value)}/>
              </label>
              <label className="metric-field full">Nota (opcional)
                <input autoComplete="off" type="text" placeholder="Ex.: post de junho, nao veio da fabrica" value={note} disabled={busy||loading} onChange={e=>setNote(e.target.value)}/>
              </label>
              <button type="button" className="primary" disabled={busy||loading||!url.trim()} onClick={analyze}>{loading?'Coletando do Studio…':'Analisar link'}</button>
              <p className="help">Abre analytics numa nova aba do Chrome da fabrica.</p>
            </div>
          </Collapse>
        </>
      )}

      {activeTab==='lote' && (
        <div className="period-audit-box flat">
          <div className="section-title">
            <h3>Analisar publicados do Studio</h3>
            <span className="help">Content → so videos com ≥100 views</span>
          </div>
          <p className="help">Filtra o periodo, pula &lt;100 views e coleta overview + viewers.</p>
          <div className="period-audit-actions">
            {[7,15,30].map(d=>(
              <button key={d} type="button" className="button analysis-action" disabled={busy||loading} onClick={()=>runPeriodAudit(d)}>
                {batchDays===d?'Coletando…':`Ultimos ${d} dias`}
              </button>
            ))}
          </div>
          {batchReport?.report && (
            <Collapse id="lote-table" title={`Tabela do lote (${batchRows.length})`} defaultOpen={true} badge={batchRows.length}>
              <div className="period-audit-summary">
                <p className="help">{batchReport.message} · {batchReport.created_at?String(batchReport.created_at).replace('T',' ').replace('Z',''):''}</p>
                {(batchReport.report.summary?.patterns||[]).length>0 && (
                  <ul className="period-patterns">{(batchReport.report.summary.patterns).map((p,i)=><li key={i}>{p}</li>)}</ul>
                )}
                <p className="help sort-hint">Clique no cabecalho para ordenar (maior→menor por padrao).</p>
                <div className="period-audit-table-wrap">
                  <table className="period-audit-table sortable">
                    <thead>
                      <tr>
                        <th>#</th>
                        <th>Video</th>
                        {[
                          ['views','Views'],
                          ['watch','Watch'],
                          ['likes','Likes'],
                          ['comments','Comments'],
                          ['search','Search'],
                          ['fyp','FYP'],
                          ['score','Score'],
                        ].map(([k,lab])=>(
                          <th key={k}>
                            <button type="button" className={'sort-th'+(batchSort.key===k?' active':'')} onClick={()=>toggleSort(setBatchSort,k)}>
                              {lab}{sortMark(batchSort,k)}
                            </button>
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {batchRows.map((r,i)=>{
                        const search=(r.traffic_source||[]).find(t=>(t.label||'').toLowerCase()==='search');
                        const fyp=(r.traffic_source||[]).find(t=>(t.label||'').toLowerCase()==='for you');
                        return (
                          <tr key={r.tiktok_video_id||i} className={r.error?'is-error':''}>
                            <td>{i+1}</td>
                            <td><a href={r.published_url||r.analytics_url} target="_blank" rel="noreferrer">{(r.caption||r.tiktok_video_id||'—').toString().slice(0,48)}</a>{r.error?<small className="help">{r.error}</small>:null}</td>
                            <td>{r.views_7d??r.list_views??'—'}</td>
                            <td>{r.watch_pct!=null?r.watch_pct+'%':'—'}</td>
                            <td>{r.likes??'—'}</td>
                            <td>{r.comments??'—'}</td>
                            <td>{search?.pct_raw||(search?.pct!=null?search.pct+'%':(r.search_pct!=null?r.search_pct+'%':'—'))}</td>
                            <td>{fyp?.pct_raw||(fyp?.pct!=null?fyp.pct+'%':(r.fyp_pct!=null?r.fyp_pct+'%':'—'))}</td>
                            <td>{r.score??'—'}</td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>
            </Collapse>
          )}
        </div>
      )}

      {activeTab==='playbook' && (
        <div className="playbook-box flat">
          <div className="section-title">
            <h3>Playbook do lote</h3>
            <button type="button" className="button analysis-action" disabled={busy||pbBusy||!batchReport?.report} onClick={buildPlaybook}>
              {pbBusy?'Gerando…':(playbook?'Atualizar playbook':'Gerar playbook')}
            </button>
          </div>
          {!playbook && <p className="help">Rode um lote em Lote 7/15/30 e clique em Gerar playbook.</p>}
          {playbook && (
            <>
              <p className="help">Base: {playbook.sample_n} videos · {playbook.days||'?'}d · {playbook.created_at?String(playbook.created_at).replace('T',' ').replace('Z',''):''}</p>
              <Collapse id="pb-do" title="Fazer / Evitar" defaultOpen={true}>
                <div className="playbook-grid">
                  <div className="playbook-panel tone-green">
                    <h4>Fazer</h4>
                    <ul>{(playbook.do||[]).map((x,i)=><li key={i}>{x}</li>)}</ul>
                  </div>
                  <div className="playbook-panel tone-pink">
                    <h4>Evitar</h4>
                    <ul>{(playbook.dont||[]).map((x,i)=><li key={i}>{x}</li>)}</ul>
                  </div>
                </div>
              </Collapse>
              <Collapse id="pb-queries" title={`Queries quentes (${(playbook.hot_queries||[]).length})`} defaultOpen={false} badge={(playbook.hot_queries||[]).length}>
                <div className="query-chips">
                  {(playbook.hot_queries||[]).slice(0,12).map((q,i)=>(
                    <span key={i} className="chip" title={`${q.videos} videos`}>“{q.query}” · {Math.round(q.avg_views)} views</span>
                  ))}
                </div>
              </Collapse>
              <Collapse id="pb-niches" title="Nichos no lote" defaultOpen={false}>
                <ul className="niche-stat-list">
                  {(playbook.niche_stats||[]).map((n,i)=>(
                    <li key={i}><strong>{n.niche}</strong> · {n.n} vids · media {Math.round(n.avg_views)} views · watch {n.avg_watch}% · FYP {n.avg_fyp}%</li>
                  ))}
                </ul>
              </Collapse>
              <Collapse id="pb-next" title={`Proximos videos (${(playbook.next_videos||[]).length})`} defaultOpen={true}>
                <ol>
                  {(playbook.next_videos||[]).map((v,i)=>(
                    <li key={i} className="playbook-next-item">
                      <div>
                        <strong>[{v.niche}] {v.title}</strong>
                        <div className="help">Hook falado: <code>{v.spoken_hook}</code></div>
                        <div className="help">{v.shot_list}</div>
                        {(v.howto_15s||[]).length>0 && <ol className="howto-mini">{v.howto_15s.map((h,j)=><li key={j}>{h}</li>)}</ol>}
                      </div>
                      <button type="button" className="primary" disabled={busy||creatingIdx===i} onClick={()=>createBrief(i)}>
                        {creatingIdx===i?'Criando…':'Criar campanha'}
                      </button>
                    </li>
                  ))}
                </ol>
              </Collapse>
            </>
          )}
        </div>
      )}

      {activeTab==='historico' && (
        <div className="link-analysis-list">
          <div className="section-title">
            <h3>Histórico de links</h3>
            <span className="count">{items.length}</span>
          </div>
          {items.length===0 && <p className="help">Nenhum link analisado ainda. Use Studio / link ou rode um lote.</p>}
          {items.length>0 && (
            <>
              <div className="hist-sort-bar">
                <span className="help">Ordenar:</span>
                {[
                  ['views','Views'],
                  ['likes','Likes'],
                  ['comments','Comments'],
                  ['saves','Saves'],
                  ['watch','Watch'],
                  ['date','Data'],
                ].map(([k,lab])=>(
                  <button key={k} type="button" className={'button analysis-action sort-chip'+(histSort.key===k?' active':'')} onClick={()=>toggleSort(setHistSort,k)}>
                    {lab}{sortMark(histSort,k)}
                  </button>
                ))}
                <button type="button" className="button analysis-action" onClick={()=>setOpenId(null)}>Recolher todos</button>
              </div>
              <ul>
                {histRows.map(item=>{
                  const id=item.id||item.url;
                  const open=openId===id;
                  const v=item.viewers||{};
                  return (
                    <li key={id} className={'analysis-card'+(open?' open':'')}>
                      <div className="analysis-summary">
                        <div className="analysis-title-row">
                          <a href={item.url} target="_blank" rel="noreferrer">{(item.note||item.tiktok_video_id||item.url||'').toString().slice(0,64)}</a>
                          <span className="analysis-when">{item.collected_at?String(item.collected_at).replace('T',' ').replace('Z',''):''}</span>
                        </div>
                        {item.tiktok_video_id?<strong className="analysis-note">{item.tiktok_video_id}</strong>:null}
                        <StatPills item={item}/>
                        <div className="analysis-actions-row">
                          <button type="button" className="button analysis-action" onClick={()=>setOpenId(open?null:id)}>{open?'Recolher':'Expandir detalhes'}</button>
                          <button type="button" className="button analysis-action" disabled={busy||loading} onClick={()=>reanalyze(item)}>{loading?'Coletando…':'Analisar de novo'}</button>
                        </div>
                      </div>
                      {open && (
                        <div className="analysis-details">
                          <div className="analysis-grid">
                            <div className="analysis-panel tone-purple">
                              <h4>Traffic source</h4>
                              <BarList rows={item.traffic_source} tone="purple"/>
                            </div>
                            <div className="analysis-panel tone-pink">
                              <h4>Search queries</h4>
                              <BarList rows={item.search_queries} limit={8} tone="pink"/>
                            </div>
                            <div className="analysis-panel tone-green">
                              <h4>Viewers</h4>
                              {(v.total_viewers!=null||v.new_viewers_pct!=null)?(
                                <>
                                  <div className="viewer-chips">
                                    <span className="chip">Total <strong>{v.total_viewers??'—'}</strong></span>
                                    <span className="chip">Novos <strong>{v.new_viewers_pct!=null?v.new_viewers_pct+'%':'—'}</strong></span>
                                    <span className="chip">Recorrentes <strong>{v.returning_viewers_pct!=null?v.returning_viewers_pct+'%':'—'}</strong></span>
                                    <span className="chip">Nao-seguidores <strong>{v.non_followers_pct!=null?v.non_followers_pct+'%':'—'}</strong></span>
                                  </div>
                                  <h5>Genero</h5>
                                  <BarList rows={v.gender} tone="green"/>
                                  <h5>Idade</h5>
                                  <BarList rows={v.age} tone="purple"/>
                                  <h5>Local</h5>
                                  <BarList rows={v.locations} limit={5} tone="pink"/>
                                </>
                              ):<p className="help">Sem viewers nesta coleta.</p>}
                            </div>
                          </div>
                          {(item.smart_actions||[]).length>0 && (
                            <div className="analysis-actions">
                              <h4>Acoes sugeridas</h4>
                              <ul>{(item.smart_actions||[]).map((a,i)=><li key={i}>{a}</li>)}</ul>
                            </div>
                          )}
                          {item.analytics_url && <p className="help analysis-link"><a href={item.analytics_url} target="_blank" rel="noreferrer">Abrir analytics no Studio</a></p>}
                        </div>
                      )}
                    </li>
                  );
                })}
              </ul>
            </>
          )}
        </div>
      )}
    </section>
  );
}
