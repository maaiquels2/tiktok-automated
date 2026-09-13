import { ServiceLaunch, TikTokLaunchButtons, isMobileDevice, isCloudMode } from './serviceLinks';
import { useEffect, useRef, useState } from 'react';
import { NICHE_DEFAULTS } from './nicheDefaults';
import { modelLibrary, uploadModelLibrary, uploadModelLibraryPhotoDirect, renameModelLibraryLabel, openStudioFree, analyzePublishedLink, listLinkAnalyses, studioAudit, studioAuditLatest, studioPlaybook, studioPlaybookBuild, productivityQueue, playbookCreateCampaign, studioIdentity, saveStudioIdentity, setupStatus, characterSheet, openCharacterSheet, writerSettings, saveWriterSettings, testWriter } from './api';
import { Copy, Check, Download, Upload, X, ImagePlus, Film, ExternalLink, Pencil, Sparkles } from 'lucide-react';
export function Dialog({title,children,onClose}){
  const ref=useRef(null);
  useEffect(()=>{ref.current.showModal();const el=ref.current;return()=>el.close()},[]);
  return <dialog ref={ref} className="dialog" onCancel={e=>{e.preventDefault();onClose()}} aria-label={title}><div className="dialog-heading"><h2>{title}</h2><button className="icon-button" onClick={onClose} aria-label="Fechar"><X size={20}/></button></div>{children}</dialog>;
}
export async function copyText(text){
  if(!text) return false;
  try{
    if(navigator.clipboard?.writeText){
      await navigator.clipboard.writeText(text);
      return true;
    }
  }catch(_){ /* LAN pages on phones are usually not a secure context. */ }
  // Some mobile browsers still allow the legacy command during the tap.
  try{
    const field=document.createElement('textarea');
    field.value=text;
    field.setAttribute('readonly','');
    field.style.position='fixed';
    field.style.top='0';
    field.style.left='0';
    field.style.opacity='0.01';
    document.body.appendChild(field);
    field.focus();
    field.select();
    field.setSelectionRange(0,field.value.length);
    const copied=document.execCommand?.('copy')===true;
    field.remove();
    return copied;
  }catch(_){ return false; }
}

export function CopyButton({text,onError,label='Copiar'}){
  const [copied,setCopied]=useState(false);
  const timer=useRef();
  useEffect(()=>()=>clearTimeout(timer.current),[]);
  const markCopied=()=>{setCopied(true);clearTimeout(timer.current);timer.current=setTimeout(()=>setCopied(false),1800)};
  return <button className="copy-button" disabled={!text} onClick={async()=>{
    if(await copyText(text)){markCopied();return}
    const manual=window.prompt('Toque e segure no campo para selecionar e copiar:',text);
    if(manual!==null) markCopied();
    else onError?.('Toque e segure no texto para selecionar e copiar.');
  }}>{copied?<Check size={14}/>:<Copy size={14}/>} {copied?'Copiado':label}</button>;
}
export function TextEditor({title,value,field,onSave,busy,onError,onDirty,readOnly=false,rows=5}){
  const [draft,setDraft]=useState(value||'');
  const changed=draft!==value;
  return <section className="text-editor"><div className="section-title"><h3>{title}</h3><CopyButton text={draft} onError={onError}/></div><textarea aria-label={title} value={draft} rows={rows} readOnly={readOnly} onChange={e=>{setDraft(e.target.value);onDirty(true)}} maxLength={12000}/>{changed&&<button disabled={busy||!draft.trim()} onClick={()=>onSave({[field]:draft})}>Salvar texto</button>}</section>;
}
export function AssetView({asset,title,compact=false}){
  if(!asset)return <div className="media-empty">{title}</div>;
  return <div className={'asset-view '+(compact?'compact':'')}>
    {asset.kind==='video'?<video key={asset.id} controls playsInline preload="metadata" src={asset.url}/>:<a href={asset.url} target="_blank" rel="noreferrer" title="Abrir imagem em tamanho completo"><img src={asset.url} alt={title}/></a>}
    <div className="asset-meta"><span>{asset.metadata.width} × {asset.metadata.height}{asset.metadata.duration?` · ${asset.metadata.duration}s`:''}</span><a href={asset.url+'?download=1'} aria-label={'Baixar '+title}><Download size={16}/></a></div>
    <div className="asset-name">{asset.original_name}</div>
    {asset.approved_at&&<span className="approved-label"><Check size={13}/>Aprovado por você</span>}
  </div>;
}
export function Uploader({kind,busy,onUpload,exists=false,disabled=false,color}){
  const ref=useRef();
  const names={reference:'referência da modelo',image:color?`imagem · ${color}`:'imagem gerada',video:color?`vídeo · ${color}`:'vídeo MP4'};
  return <><input ref={ref} type="file" hidden accept={kind==='video'?'video/mp4,.mp4':'image/jpeg,image/png,image/webp'} onChange={e=>{const f=e.target.files?.[0];if(f)onUpload(kind,f,color);e.target.value=''}}/><button className="upload-button" onClick={()=>ref.current.click()} disabled={busy||disabled}>{kind==='video'?<Film size={18}/>:<ImagePlus size={18}/>} {exists?'Substituir':'Anexar'} {names[kind]}</button><small className="help">{kind==='video'?'MP4 · até 250 MB · 15s · vertical 9:16':'JPG, PNG ou WebP · até 40 MB'}</small></>;
}
export function DeviceVideoPicker({busy,onSelect,record,disabled=false,color}){
  const ref=useRef();
  return <div className="device-video-picker">
    <input ref={ref} type="file" hidden accept="video/mp4,.mp4" onChange={e=>{const file=e.target.files?.[0];if(file)onSelect(file,color);e.target.value=''}}/>
    <button type="button" className="upload-button device-only" disabled={busy||disabled} onClick={()=>ref.current?.click()}>
      <Film size={18}/> {record?'Trocar':'Usar'} vídeo da galeria{color?` · ${color}`:''}
    </button>
    <small className="help">O MP4 permanece neste dispositivo. A Fábrica salva somente nome, tamanho, duração e aprovação.</small>
  </div>;
}

export function DeviceVideoCard({record,localFile}){
  if(!record)return null;
  const meta=record.metadata||{};
  return <div className="device-video-card">
    {localFile?.url?<video controls playsInline preload="metadata" src={localFile.url}/>:<div className="device-video-placeholder"><Film size={28}/><strong>Vídeo guardado na galeria</strong><span>Selecione novamente para assistir neste navegador.</span></div>}
    <div className="asset-meta"><span>{meta.width||'—'} × {meta.height||'—'}{meta.duration?` · ${meta.duration}s`:''}</span><span>{record.size?`${(record.size/1024/1024).toFixed(1)} MB`:''}</span></div>
    <div className="asset-name">{record.original_name}</div>
    {record.approved_at&&<span className="approved-label"><Check size={13}/>Aprovação registrada</span>}
  </div>;
}
export const emptyBrief={name:'',model_name:'Micaela',niche:'casual',product:'',outfit:'',color:'',audience:'',benefit:'',angle:'',tone:'Conversacional',style:'Natural e realista',details:'',movements:'',objection:'',offer:'',generator:'flow'};
// Objecoes mais comuns no TikTok Shop de moda. O campo aceita texto livre: a
// lista so evita digitacao e mantem o texto no formato que o gerador reconhece.
export const OBJECTIONS=['Fica transparente no agachamento','A peça desce ou escorrega','Não sei se serve em mim','Parece barata de perto','Não dura / desbota na lavagem','Incomoda ou aperta no uso','Acho caro para uma peça só','Marca o corpo'];
export const NICHES=[{id:'praia',label:'Moda praia'},{id:'academia',label:'Moda academia'},{id:'casual',label:'Moda casual'},{id:'dia-a-dia',label:'Moda dia a dia'},{id:'intima',label:'Moda íntima'},{id:'fantasia',label:'Fantasia'}];
export function ProductGallery({photos=[]}){
  if(!photos.length)return null;
  return <section className="product-gallery"><h3>Fotos do produto</h3><p>Anexe estas fotos depois da referência fixa da modelo.</p><div className="product-photo-grid">{photos.map((photo,i)=><AssetView key={photo.id} asset={photo} title={`Produto · foto ${i+1}`} compact/>)}</div></section>;
}
export function VariantList({variants=[],onError,focus,images=[],videos=[],deviceVideos=[],deviceFiles={},onUpload,onDeviceVideo,busy,disabled,onSaveVariant,onRefreshVariant,onConfigureWriter,immutable}){
  const [writer,setWriter]=useState(null);
  useEffect(()=>{
    if(focus!=='script') return;
    writerSettings().then(setWriter).catch(()=>setWriter({enabled:false,provider:''}));
  },[focus]);
  if(!variants.length)return null;
  const byImage=Object.fromEntries((images||[]).filter(a=>a.kind==='image').map(a=>[a.slot||a.metadata?.color||'',a]));
  const byVideo=Object.fromEntries((videos||[]).filter(a=>a.kind==='video').map(a=>[a.slot||a.metadata?.color||'',a]));
  const byDeviceVideo=Object.fromEntries((deviceVideos||[]).map(a=>[a.slot||'',a]));
  const title=focus==='image'?'Imagens por cor':focus==='video'?'Vídeos por cor':focus==='script'?'Roteiros 15s por cor':'Prompts por cor';
  const help=focus==='image'
    ?'Gere e anexe uma imagem por cor. Todas ficam disponíveis para aprovação.'
    :focus==='video'
      ?'Use a imagem aprovada da mesma cor, copie o prompt de vídeo e anexe o MP4 de 15s. Precisa de um vídeo por cor.'
      :focus==='script'
        ?'Cada cor tem falas (hook, desenvolvimento, CTA). A legenda do TikTok fica na etapa Studio.'
        :'Abra cada cor para copiar os prompts e o roteiro correspondentes.';
  return <section className="variant-list"><div className="section-title"><h3>{title}</h3><span className="help">{variants.length} variações</span></div>
    <p>{help}</p>
    {variants.map((variant,idx)=>{
      const p=variant.prompts||{};
      const img=byImage[variant.color];
      const vid=byVideo[variant.color];
      const deviceVid=byDeviceVideo[variant.color];
      const status=focus==='image'?(img?(img.approved_at?'Imagem aprovada':'Imagem anexada'):'Falta anexar')
        :focus==='video'?((vid||deviceVid)?((vid||deviceVid).approved_at?'Vídeo aprovado':deviceVid?'Vídeo na galeria':'Vídeo anexado'):'Falta selecionar')
        :'Roteiro';
      return <details className="variant-card" key={variant.id||variant.color} open={focus==='image'||focus==='video'||focus==='script'||idx===0}>
        <summary><strong>{variant.color}</strong><span>{status}</span></summary>
        <div className="variant-content">
          {focus==='image'&&<>
            <div className="variant-prompt"><div className="section-title"><strong>Prompt de imagem — use só esta cor</strong><CopyButton text={p.image||''} onError={onError}/></div><p>{p.image||'-'}</p></div>
            {img?<AssetView asset={img} title={`Resultado · ${variant.color}`} compact/>:null}
            {onUpload&&!immutable&&<Uploader kind="image" color={variant.color} exists={!!img} busy={busy} disabled={disabled} onUpload={onUpload}/>}
          </>}
          {focus==='video'&&<>
            {img?<AssetView asset={img} title={`Imagem aprovada · ${variant.color}`} compact/>:<div className="notice">Falta a imagem desta cor.</div>}
            <div className="variant-prompt"><div className="section-title"><strong>Prompt de vídeo — {variant.color}</strong><CopyButton text={p.video||''} onError={onError}/></div><p>{p.video||'-'}</p></div>
            <div className="variant-prompt"><div className="section-title"><strong>Falas 15s</strong></div>
              <p><strong>0–4s:</strong> {p.hook||'-'}</p>
              <p><strong>4–12s:</strong> {p.development||'-'}</p>
              <p><strong>12–15s:</strong> {p.cta||'-'}</p>
            </div>
            {vid?<AssetView asset={vid} title={`Vídeo · ${variant.color}`} compact/>:null}
            {deviceVid?<DeviceVideoCard record={deviceVid} localFile={deviceFiles[variant.color]}/>:null}
            {onUpload&&!immutable&&<Uploader kind="video" color={variant.color} exists={!!vid} busy={busy} disabled={disabled} onUpload={onUpload}/>}
            {onDeviceVideo&&!immutable&&<DeviceVideoPicker color={variant.color} record={deviceVid} busy={busy} disabled={disabled} onSelect={onDeviceVideo}/>}
          </>}
          {focus==='script'&&<>
            {!immutable&&<section className={'script-ai-action '+(writer?.enabled?'is-ready':'is-off')}>
              <div><span className="eyebrow">ESCRITA POR API · {variant.color}</span><strong>{writer?.enabled?(writer.provider==='gemini'?'Gemini está configurado':'ChatGPT está configurado'):'ChatGPT ainda não está ativo'}</strong><small>{writer?.enabled?'Gera e audita as três falas desta cor.':'Configure a chave para chamar a API nesta etapa.'}</small></div>
              {writer?.enabled
                ?<button type="button" className="primary" disabled={busy} onClick={()=>onRefreshVariant?.(variant.id,['hook','development','cta','caption'],{writerMode:'ai'})}><Sparkles size={16}/> Gerar esta cor com {writer.provider==='gemini'?'Gemini':'ChatGPT'}</button>
                :<button type="button" className="primary" disabled={busy} onClick={onConfigureWriter}><Sparkles size={16}/> Configurar ChatGPT</button>}
            </section>}
            <div className="variant-actions">
              <span className="help">Alternativas locais, sem usar API:</span>
              {onRefreshVariant&&!immutable&&<>
                <button type="button" disabled={busy} onClick={()=>onRefreshVariant(variant.id,['hook'],{writerMode:'local'})}>Criar outro hook</button>
                <button type="button" disabled={busy} onClick={()=>onRefreshVariant(variant.id,['hook','development','cta'],{writerMode:'local'})}>Criar outra fala inteira</button>
              </>}
            </div>
            <p className="help">Legenda do TikTok fica na etapa <strong>Studio</strong> (publicação). Aqui só as falas do vídeo.</p>
            {[['hook','Hook · 0-4s'],['development','Desenvolvimento · 4-12s'],['cta','CTA · 12-15s']].map(([key,title])=>
              <div className="variant-prompt" key={key}>
                <div className="section-title"><strong>{title}</strong><CopyButton text={p[key]||''} onError={onError}/></div>
                {onSaveVariant&&!immutable
                  ?<VariantScriptField variant={variant} field={key} value={p[key]||''} busy={busy} onSave={onSaveVariant}/>
                  :<p>{p[key]||'-'}</p>}
              </div>)}
          </>}
          {!['image','video','script'].includes(focus)&&[['image','Prompt de imagem'],['video','Prompt de vídeo'],['hook','Hook · 0-4s'],['development','Desenvolvimento · 4-12s'],['cta','CTA · 12-15s'],['caption','Legenda']].map(([key,title])=>
            <div className="variant-prompt" key={key}>
              <div className="section-title"><strong>{title}</strong><CopyButton text={p[key]||''} onError={onError}/></div>
              <p>{p[key]||'-'}</p>
            </div>)}
        </div>
      </details>;
    })}
  </section>;
}


function VariantScriptField({variant,field,value,busy,onSave}){
  const [draft,setDraft]=useState(value);
  useEffect(()=>setDraft(value),[value]);
  const dirty=draft!==value;
  return <div className="variant-script-field">
    <textarea rows={field==='video'?6:3} maxLength={12000} value={draft} disabled={busy} onChange={e=>setDraft(e.target.value)}/>
    {dirty&&<button type="button" className="full" disabled={busy||!draft.trim()} onClick={()=>onSave(variant.id,{[field]:draft})}>Salvar {field}</button>}
  </div>;
}



export function VideoMixer({c, busy, immutable, onError, onMix}){
  const [openMixer,setOpenMixer]=useState(false);
  const videos=(c.assets||[]).filter(a=>a.kind==='video');
  const colorSlots=((c.color||'').split(/[,;|\n]+/).map(v=>v.trim()).filter(Boolean));
  const slotOptions=[...colorSlots, 'Mix'].filter((v,i,arr)=>arr.indexOf(v)===i);
  const [order,setOrder]=useState(()=>videos.map(v=>v.id));
  const [seconds,setSeconds]=useState({});
  const [slot,setSlot]=useState(slotOptions[0]||'Mix');
  const [duration,setDuration]=useState(22);
  const [working,setWorking]=useState(false);
  const [autoBrief,setAutoBrief]=useState('');
  const [autoGate,setAutoGate]=useState(null);
  const [autoNote,setAutoNote]=useState('');
  useEffect(()=>{
    setOrder(prev=>{
      const ids=videos.map(v=>v.id);
      const keep=prev.filter(id=>ids.includes(id));
      const add=ids.filter(id=>!keep.includes(id));
      return [...keep,...add];
    });
  },[videos.map(v=>v.id).join(',')]);
  const ordered=order.map(id=>videos.find(v=>v.id===id)).filter(Boolean);
  function move(id,dir){
    setOrder(prev=>{
      const i=prev.indexOf(id); if(i<0) return prev;
      const j=i+dir; if(j<0||j>=prev.length) return prev;
      const next=prev.slice(); [next[i],next[j]]=[next[j],next[i]]; return next;
    });
  }
  function toggle(id){
    setOrder(prev=>prev.includes(id)?prev.filter(x=>x!==id):[...prev,id]);
  }
  function buildAutoCutBrief(){
    const lines=[
      'AUTO-CUT TikTok Shop — rode a skill Auto-cut TikTok Shop takes',
      `Campanha: ${c.name||c.id} (id ${c.id})`,
      `Produto: ${c.product||'—'} · Cores: ${c.color||'—'}`,
      `Slot destino sugerido: ${slot} · duracao livre (pode >15s), priorizar continuidade`,
      '',
      'Takes (ordem preferida):'
    ];
    ordered.forEach((v,i)=>{
      const label=v.slot||v.metadata?.color||`Video #${v.id}`;
      const path=v.local_path||v.path||`(asset id ${v.id} — anexe o MP4 no chat do Critico)`;
      const sec=seconds[v.id]?` · pedaco ~${seconds[v.id]}s do inicio`:'';
      lines.push(`${i+1}) ${label}${sec}`);
      lines.push(`   path: ${path}`);
    });
    lines.push('');
    lines.push('Pedido: assista cada take, KEEP/DROP com timecodes, monte hook→prova→objecao→CTA sem corte seco, passe ao Editor de Mix, rode o gate GO/REWORK/KILL e devolva o MP4 final.');
    lines.push('Regras: sem eco/overlap; sem frase cortada; legendas minimas (beneficio+CTA) ou nenhuma; match cut / dissolve 0.2-0.25s.');
    return lines.join('\n');
  }
  async function runAutoCut(){
    if(ordered.length<1){onError?.('Selecione ao menos 1 video.');return}
    const brief=buildAutoCutBrief();
    setAutoBrief(brief);
    setAutoGate({
      fileName:`auto-cut - ${ordered.length} takes`,
      scores:[1,1,1,1,1,1,1],
      note:'Pipeline preparado. Cole o brief no Critico de Vendas (ou anexe os MP4s la). Ele assiste, corta com o Editor e devolve GO/REWORK/KILL.'
    });
    setAutoNote(`Auto-cut enfileirado: ${ordered.length} take(s). O Critico de Vendas sera avisado automaticamente.`);
    try{
      await fetch(`/api/campaigns/${c.id}/autocut`,{
        method:'POST',
        headers:{'Content-Type':'application/json'},
        body:JSON.stringify({version:c.version, brief, clips:ordered.map(v=>({asset_id:v.id, slot:v.slot||v.metadata?.color, local_path:v.local_path||null, seconds:seconds[v.id]?Number(seconds[v.id]):null})), slot})
      });
    }catch(_){ /* endpoint opcional */ }
  }
  async function runMix(){
    if(ordered.length<2){onError?.('Selecione pelo menos 2 videos.');return}
    setWorking(true);
    try{
      const clips=ordered.map(v=>({
        asset_id:v.id,
        seconds: seconds[v.id] ? Number(seconds[v.id]) : undefined,
      }));
      await onMix({clips, slot, duration:Number(duration)||22});
    }catch(e){onError?.(e.message||String(e))}
    finally{setWorking(false)}
  }
  if(!videos.length) return <div className="notice">Anexe ao menos 2 MP4s (por cor) para misturar ou usar Auto-cut.</div>;
  return <section className="video-mixer">
    <div className="section-title">
      <h3>Montagem automática (opcional)</h3>
      <button type="button" className="button" disabled={busy||immutable} onClick={()=>setOpenMixer(v=>!v)}>{openMixer?'Ocultar':'Abrir'}</button>
    </div>
    <p className="help"><strong>Fluxo normal:</strong> 1 MP4 por cor na lista abaixo — não misture preto+branco+azul num único arquivo. <strong>Use isto</strong> só quando uma cor tiver vários takes e você quiser um corte tipo CapCut (IA escolhe trechos fortes).</p>
    {!openMixer ? null : (<>

    <div className="section-title"><h3>Misturar videos</h3></div>
    <p className="help">Ordene os clips. <strong>Auto-cut</strong> prepara o pacote pro Critico (assiste, KEEP/DROP, Editor costura, gate). <strong>Gerar mix</strong> e o FFmpeg local rapido sem critica visual.</p>
    <div className="mixer-list">
      {videos.map(v=>{
        const on=order.includes(v.id);
        const label=v.slot||v.metadata?.color||`Video #${v.id}`;
        return <div className={'mixer-row'+(on?' on':'')} key={v.id}>
          <label className="check-row" style={{margin:0}}><input type="checkbox" checked={on} disabled={busy||immutable||working} onChange={()=>toggle(v.id)}/><span>{label}</span></label>
          {on&&<>
            <input type="number" min="0.2" step="0.1" placeholder="seg" title="Segundos a partir do inicio" value={seconds[v.id]??''} disabled={busy||immutable||working} onChange={e=>setSeconds(s=>({...s,[v.id]:e.target.value}))}/>
            <button type="button" disabled={busy||immutable||working} onClick={()=>move(v.id,-1)} title="Subir">↑</button>
            <button type="button" disabled={busy||immutable||working} onClick={()=>move(v.id,1)} title="Descer">↓</button>
          </>}
        </div>;
      })}
    </div>
    <div className="mixer-controls">
      <label>Salvar no slot<select value={slot} disabled={busy||immutable||working} onChange={e=>setSlot(e.target.value)}>{slotOptions.map(s=><option key={s} value={s}>{s}</option>)}</select></label>
      <label>Duracao mix local (s)<input type="number" min="10" max="60" step="0.5" value={duration} disabled={busy||immutable||working} onChange={e=>setDuration(e.target.value)}/></label>
    </div>
    <div className="mixer-actions">
      <button type="button" className="primary" disabled={busy||immutable||working||ordered.length<1} onClick={runAutoCut}>Auto-cut (Critico)</button>
      <button type="button" disabled={busy||immutable||working||ordered.length<2} onClick={runMix}>{working?'Misturando…':'Gerar mix MP4 local'}</button>
    </div>
    {ordered.length>=1&&<p className="help">Ordem: {ordered.map(v=>v.slot||v.id).join(' · ')}</p>}
    {autoNote&&<p className="notice success">{autoNote}</p>}
    {autoBrief&&<div className="autocut-brief"><div className="section-title"><strong>Brief pro Critico</strong><CopyButton text={autoBrief} label="Copiar brief" onError={onError}/></div><pre>{autoBrief}</pre></div>}
    {autoGate&&<GateCriticoPanel fileName={autoGate.fileName} scores={autoGate.scores} note={autoGate.note} autoStart/>}
    </>)}
  </section>;
}
export function PublishQueue({c,busy,immutable,onError,onOpen,onPublishSlot,onRefreshVariant,onSaveCaption,onRefreshCaption}){
  const videos=c.assets.filter(a=>a.kind==='video');
  const variants=c.variants?.length?c.variants:[{color:c.color||'Produto',prompts:c.prompts,id:'main'}];
  const slotMap=(c.checklist&&c.checklist.slots)||{};
  const [active,setActive]=useState(()=>{
    const pending=variants.find(v=>!slotMap[v.color||'default']?.published);
    return pending?.color || variants[0]?.color || '';
  });
  const [checks,setChecks]=useState({});
  const [publishedUrl,setPublishedUrl]=useState('');
  const [captionDraft,setCaptionDraft]=useState('');
  const [editingCaption,setEditingCaption]=useState(false);
  useEffect(()=>{
    const pending=variants.find(v=>!slotMap[v.color||'default']?.published);
    if(pending&&slotMap[active||'default']?.published) setActive(pending.color);
  },[c.checklist,c.version]);
  const variant=variants.find(v=>v.color===active)||variants[0];
  const video=videos.find(v=>(v.slot||v.metadata?.color)===variant?.color) || videos[0];
  const done=!!slotMap[variant?.color||'default']?.published;
  const caption=variant?.prompts?.caption||c.prompts?.caption||'';
  useEffect(()=>{ setCaptionDraft(caption||''); setEditingCaption(false); },[caption, variant?.color, c.id, c.version]);
  const remaining=variants.filter(v=>!slotMap[v.color||'default']?.published).length;
  const check=(key,label)=><label className="check-row" key={key}><input type="checkbox" checked={!!checks[key]} disabled={busy||immutable||done} onChange={e=>setChecks(old=>({...old,[key]:e.target.checked}))}/><span>{label}</span></label>;
  const canRegister = ['account','product','caption','review','published'].every(k=>checks[k]);
  return <section className="publish-queue publish-queue-compact">
    <div className="publish-topbar">
      <div className="publish-slot-tabs">
        {variants.map(v=>{
          const key=v.color||'default';
          const ok=!!slotMap[key]?.published;
          return <button type="button" key={key} className={'slot-tab'+(active===v.color?' active':'')+(ok?' done':'')} disabled={busy} onClick={()=>{setActive(v.color);setChecks({});setPublishedUrl(slotMap[key]?.url||'')}}>
            {ok?'✓ ':''}{v.color||'Produto'}
          </button>;
        })}
      </div>
      <TikTokLaunchButtons className="button publish-open-studio" disabled={busy} onOpenStudio={event=>onOpen('studio','publish',event)}/>
    </div>
    <p className="publish-hint">{isMobileDevice()?'Salve o vídeo no celular e copie a legenda. Abra o TikTok, confira a conta e publique; depois volte para registrar o link.':'Uma cor por vez: copie legenda → suba o MP4 no Studio → registre o link.'}</p>

    <div className="publish-grid">
      <div className="publish-media">
        {video?<AssetView asset={video} title={`MP4 · ${variant?.color||''}`} compact/>:<div className="notice">Sem vídeo para esta cor.</div>}
        <CopyButton text={video?.local_path} label="Copiar caminho do MP4" onError={onError}/>
      </div>
      <div className="publish-copy">
        <div className="section-title"><strong>Legenda · {variant?.color}</strong>
          <span className="publish-caption-actions">
            <CopyButton text={editingCaption?captionDraft:caption} onError={onError}/>
            {!immutable&&!done&&!editingCaption&&
              <button type="button" disabled={busy} onClick={()=>{setCaptionDraft(caption||'');setEditingCaption(true)}}>Editar</button>}
            {!immutable&&!done&&(
              (onRefreshVariant&&variant?.id&&variant.id!=='main')
                ? <button type="button" disabled={busy||editingCaption} onClick={()=>onRefreshVariant(variant.id,['caption'])}>Nova</button>
                : (onRefreshCaption
                    ? <button type="button" disabled={busy||editingCaption} onClick={()=>onRefreshCaption(['caption'])}>Nova</button>
                    : null)
            )}
          </span>
        </div>
        {editingCaption && !immutable && !done ? (
          <>
            <textarea className="caption-editor" aria-label="Legenda TikTok" rows={4} maxLength={12000} value={captionDraft} disabled={busy} onChange={e=>setCaptionDraft(e.target.value)}/>
            <div className="publish-caption-edit-actions">
              <button type="button" className="primary" disabled={busy||!captionDraft.trim()||captionDraft.trim()===caption}
                onClick={()=>{
                  if(variant?.id && variant.id!=='main') onSaveCaption?.({caption: captionDraft.trim(), _variantId: variant.id});
                  else onSaveCaption?.({caption: captionDraft.trim()});
                  setEditingCaption(false);
                }}>Salvar</button>
              <button type="button" disabled={busy} onClick={()=>{setCaptionDraft(caption||'');setEditingCaption(false)}}>Cancelar</button>
            </div>
          </>
        ) : (
          <p className="caption-preview">{caption||'-'}</p>
        )}
      </div>
    </div>

    {immutable&&variants.every(v=>slotMap[v.color||'default']?.published)?
      <div className="notice success"><Check size={18}/><strong>Todas as cores foram publicadas.</strong>
        <div className="publish-links">{variants.map(v=>{
          const info=slotMap[v.color||'default'];
          const url=info?.url||c.published_url;
          return url?<a key={v.color||'default'} href={url} target="_blank" rel="noreferrer">Ver {v.color||'publicação'} <ExternalLink size={14}/></a>:null;
        })}</div>
      </div>:
      done?<div className="notice success"><Check size={16}/> Cor <strong>{variant?.color}</strong> já registrada. Escolha a próxima ({remaining} restante{remaining===1?'':'s'}).</div>:
      <div className="publish-register">
        <div className="publish-checks">
          {check('account','Conta TikTok certa')}
          {check('product',`Produto Shop: ${c.product} (${variant?.color})`)}
          {check('caption','MP4 + legenda desta cor')}
          {check('review','Revisei vídeo/áudio/direitos')}
          {check('published','Já publiquei no Studio')}
        </div>
        <label className="publish-link-field">Link do vídeo (opcional)<input type="url" value={publishedUrl} onChange={e=>setPublishedUrl(e.target.value)} placeholder="https://www.tiktok.com/@…/video/…"/></label>
        <button className="primary full" disabled={busy||!canRegister}
          onClick={()=>onPublishSlot({color:variant?.color,checklist:checks,published_url:publishedUrl})}>
          Registrar publicação · {variant?.color}
        </button>
      </div>}
  </section>;

}



export function VideoTimelinePreview({asset,variant,c}){
  const videoRef=useRef(null);
  const [t,setT]=useState(0);
  const [dur,setDur]=useState(15);
  const prompts=(variant?.prompts)||c?.prompts||{};
  const src=asset?.url||asset?.href||(asset?.id?`/api/assets/${asset.id}/file`:'');
  const beat=t<4?'Hook':t<12?'Desenvolvimento':'CTA';
  const overlay=beat==='Hook'?(prompts.hook||''):beat==='Desenvolvimento'?(prompts.development||''):(prompts.cta||'');
  const marks=[0,4,12,Math.min(15,dur||15)].filter((v,i,a)=>a.indexOf(v)===i&&v<=(dur||15));
  if(!asset)return null;
  return <section className="video-timeline-preview">
    <div className="phone-frame">
      <video ref={videoRef} src={src} controls playsInline onTimeUpdate={e=>setT(e.currentTarget.currentTime||0)} onLoadedMetadata={e=>setDur(e.currentTarget.duration||15)}/>
      <div className="beat-overlay"><span className="beat-label">{beat}</span><p>{overlay||'—'}</p></div>
    </div>
    <div className="timeline-scrub">
      <input type="range" min={0} max={dur||15} step={0.05} value={Math.min(t,dur||15)} onChange={e=>{const v=Number(e.target.value);setT(v);if(videoRef.current)videoRef.current.currentTime=v;}}/>
      <div className="timeline-marks">{marks.map(m=><span key={m} style={{left:`${(m/(dur||15))*100}%`}}>{m}s</span>)}</div>
      <small className="help">Marcadores 0 / 2 / 12 / 15s · beat ativo: <strong>{beat}</strong></small>
    </div>
  </section>;
}


const GATE_LABELS=["Áudio contínuo","Cortes conectados","Legendas","Hook 0–3s","Prova do produto","CTA final","Clareza / conversão"];
function gateVerdict(scores){
  const total=scores.reduce((a,b)=>a+b,0);
  const autoFail=scores[0]===0;
  if(total<=5)return{total,kind:"kill",label:"KILL"};
  if(total<=10||autoFail)return{total,kind:"rework",label:"REWORK"};
  return{total,kind:"go",label:"GO"};
}
function _gateText(v){return (v||"").toString().trim()}
/** Heurística local leve (sem assistir o MP4). Scores 0–2; Critico agente faz o gate visual real. */
export function estimateGateScores({duration,prompts={},caption="",hasVideo=false}={}){
  const hook=_gateText(prompts.hook),dev=_gateText(prompts.development),cta=_gateText(prompts.cta),cap=_gateText(caption);
  const scores=[1,1,1,1,1,1,1];
  if(!hasVideo){return{scores:[0,0,0,0,0,0,0],note:"Sem MP4 anexado — anexe o vídeo da cor antes do gate."};}
  if(hook.length<8)scores[3]=0; else if(/\?|cansa|olha|presta/i.test(hook)&&hook.length<90)scores[3]=2; else scores[3]=1;
  if(dev.length<20)scores[4]=0; else if(/bolso|caimento|transpar|leve|movimento|poliamida/i.test(dev))scores[4]=2; else scores[4]=1;
  if(/toc[ae]|salva|coment|produto marcado|compra/i.test(cta+" "+cap))scores[5]=2; else if(cta.length>6)scores[5]=1; else scores[5]=0;
  const captionHeavy=/BOLSO|NÃO TRANSPARENTA|NAO TRANSPARENTA|TOCA NO PRODUTO/i.test(cap)&&cap.length>40;
  scores[2]=captionHeavy?0:(cap.trim()?1:2);
  const clarityBits=[/bolso|caimento|transpar|leve/i.test(dev+hook), /toc[ae]|produto marcado/i.test(cta+cap)];
  scores[6]=clarityBits.filter(Boolean).length===2?2:clarityBits.some(Boolean)?1:0;
  scores[0]=1; scores[1]=1;
  if(duration&&(duration<8||duration>45))scores[1]=0;
  const v=gateVerdict(scores);
  const note=v.label==="GO"
    ? "Heurística local ok — confirme áudio/cortes no Critico de Vendas."
    : "Heurística local: "+v.label+" · "+v.total+"/14. Áudio e cortes reais só com o agente Critico assistindo o MP4.";
  return{scores,note};
}

export function GateCriticoPanel({fileName,scores,note,autoStart=true,onDone}){
  const rootRef=useRef(null);
  const [running,setRunning]=useState(false);
  const [idx,setIdx]=useState(-1);
  const [shown,setShown]=useState(Array(GATE_LABELS.length).fill(null));
  const [live,setLive]=useState(0);
  const [done,setDone]=useState(false);
  const [tick,setTick]=useState(0);
  const [isFs,setIsFs]=useState(false);
  const result=gateVerdict(scores||[]);
  useEffect(()=>{
    const onFs=()=>setIsFs(!!document.fullscreenElement);
    document.addEventListener('fullscreenchange',onFs);
    return()=>document.removeEventListener('fullscreenchange',onFs);
  },[]);
  async function toggleFullscreen(){
    const el=rootRef.current;
    if(!el)return;
    try{
      if(!document.fullscreenElement){await el.requestFullscreen();setTick(t=>t+1);}
      else{await document.exitFullscreen();}
    }catch(e){console.error(e);alert('Nao foi possivel abrir fullscreen neste navegador.');}
  }
  useEffect(()=>{
    if(!autoStart||!scores?.length)return;
    let cancelled=false;
    async function play(){
      setRunning(true);setDone(false);setShown(Array(GATE_LABELS.length).fill(null));setLive(0);setIdx(-1);
      let sum=0;
      for(let i=0;i<GATE_LABELS.length;i++){
        if(cancelled)return;
        setIdx(i);
        await new Promise(r=>setTimeout(r,420));
        if(cancelled)return;
        const s=scores[i]|0; sum+=s;
        setShown(prev=>{const n=[...prev];n[i]=s;return n;});
        setLive(sum);
        await new Promise(r=>setTimeout(r,220));
      }
      if(cancelled)return;
      setIdx(-1);setRunning(false);setDone(true);
      onDone&&onDone({...gateVerdict(scores),note});
    }
    play();
    return()=>{cancelled=true};
  },[JSON.stringify(scores),fileName,autoStart,tick]);
  const dots=(score)=>{
    if(score==null)return[0,0,0];
    if(score>=2)return[2,2,2];
    if(score===1)return[2,1,0];
    return[-1,0,0];
  };
  return <section ref={rootRef} className={"gate-critico"+(isFs?" is-fullscreen":"")} aria-label="Gate Critico de video">
    <div className="gate-top">
      <div className="gate-brand">
        <span className={"gate-logo"+(running?" spin":" done")}>{done?(result.kind==="go"?"✓":result.kind==="rework"?"!":"×"):""}</span>
        <div>
          <strong>Gate · Critico</strong>
          <p className="help">{running?"Avaliando critérios…":done?"Avaliação concluída":"Pronto para avaliar"}</p>
        </div>
      </div>
      <span className={"status-pill"+(done?" "+result.kind:(running?" evaluating":""))}>{done?result.label:(running?"AVALIANDO":"GATE")}</span>
    </div>
    <div className="gate-score-wrap">
      <div className="gate-bar"><i style={{width:((live/14)*100).toFixed(1)+"%"}}/></div>
      <div className="score-num">{live}<span>/14</span></div>
    </div>
    <div className="gate-criteria">
      {GATE_LABELS.map((label,i)=>{
        const s=shown[i];
        const cls="gate-row"+(idx===i?" active":"")+(s!=null?" done":"")+(s===0?" fail":"");
        return <div className={cls} key={label}>
          <span className="label">{label}</span>
          <span className="dots">{dots(s).map((d,j)=><i key={j} className={"dot"+(d===2?" on":d===1?" mid":d===-1?" bad":"")}/>)}</span>
        </div>;
      })}
    </div>
    <div className={"gate-verdict "+(done?result.kind:"")}>
      <div className="eyebrow">Veredito</div>
      <div className={"gate-verdict-big"+(done?" show":"")}>{done?`${result.label} · ${result.total}/14`:"—"}</div>
      <p>{done?(note||""):"Animação alinhada à Fábrica TikTok · skill TikTok Shop video gate."}</p>
    </div>
    <small className="help file">{fileName?`arquivo: ${fileName}`:"arquivo: —"}</small>
    <div className="gate-actions">
      <button type="button" disabled={!scores?.length||running} onClick={()=>setTick(t=>t+1)}>Rever animação</button>
      <button type="button" className="button" onClick={toggleFullscreen}>{isFs?"Sair do fullscreen":"Abrir card fullscreen"}</button>
    </div>
  </section>;
}


export function PerformancePanel({c,busy,immutable,onError,onSavePerformance,onGenerateInsights,onRefreshVariant,onGotoScript,onOpenStudio,onFetchStudioMetrics,onAuditStudioPosts,studioAuditReport,onSavePublishedLink}){
  const variants=c.variants?.length?c.variants:[{color:c.color||'Produto',prompts:c.prompts,id:'main'}];
  const perfMap=(c.checklist&&c.checklist.performance)||{};
  const insightsMap=(c.checklist&&c.checklist.insights)||{};
  const videos=c.assets.filter(a=>a.kind==='video');
  const hasUrl=videos.some(v=>v.url||v.href||v.id);
  const [active,setActive]=useState(variants[0]?.color||'');
  const [metrics,setMetrics]=useState({});
  const [criticoNote,setCriticoNote]=useState('');
  const [gateRun,setGateRun]=useState(null);
  const slotUrl=((c.checklist&&c.checklist.slots)||{})[active||'']?.url||((c.checklist&&c.checklist.slots)||{})[active||'default']?.url||'';
  const [tiktokLink,setTiktokLink]=useState(c.published_url||slotUrl||'');
  useEffect(()=>{const su=((c.checklist&&c.checklist.slots)||{})[active||'']?.url||((c.checklist&&c.checklist.slots)||{})[active||'default']?.url||'';setTiktokLink(c.published_url||su||'');},[c.id,c.version,c.published_url,active]);
  useEffect(()=>{
    const key=active||'default';
    const prev=perfMap[key]||perfMap[active]||{};
    setMetrics({
      views_24h:prev.views_24h??'',views_7d:prev.views_7d??'',watch_pct:prev.watch_pct??'',
      likes:prev.likes??'',comments:prev.comments??'',saves:prev.saves??'',shares:prev.shares??'',
      orders:prev.orders??'',notes:prev.notes??''
    });
  },[active,c.version]);
  const variant=variants.find(v=>v.color===active)||variants[0];
  const key=variant?.color||'default';
  const card=insightsMap[key]||insightsMap['default'];
  const video=videos.find(v=>(v.slot||v.metadata?.color)===variant?.color)||videos[0];
  const field=(name,label,step='1')=><label className="metric-field" key={name}>{label}<input type={name==='notes'?'text':'number'} step={step} value={metrics[name]??''} disabled={busy}
    onChange={e=>setMetrics(m=>({...m,[name]:e.target.value}))}/></label>;
  const num=v=>v===''||v==null?undefined:Number(v);
  const save=()=>onSavePerformance&&onSavePerformance({color:variant?.color,metrics:{
    views_24h:num(metrics.views_24h),views_7d:num(metrics.views_7d),watch_pct:num(metrics.watch_pct),
    likes:num(metrics.likes),comments:num(metrics.comments),saves:num(metrics.saves),shares:num(metrics.shares),
    orders:num(metrics.orders),notes:metrics.notes||undefined
  }});
  const scoreBox=(title,block)=><div className="score-card"><strong>{title}</strong><div className="score-num">{block?.score??'—'}</div><p>{block?.note||''}</p></div>;
  return <section className="performance-panel">
    <div className="section-title"><h3>Performance & Insights</h3><span className="help">métricas manuais · crítico local</span></div>
    <div className="publish-slot-tabs">{variants.map(v=><button type="button" key={v.color||'x'} className={'slot-tab'+(active===v.color?' active':'')} disabled={busy} onClick={()=>setActive(v.color)}>{v.color||'Produto'}</button>)}</div>
    <div className="metric-form">
      {field('views_24h','Views 24h')}{field('views_7d','Views 7d')}{field('watch_pct','Watch %','0.1')}
      {field('likes','Likes')}{field('comments','Comentários')}{field('saves','Saves')}{field('shares','Shares')}{field('orders','Pedidos')}
      {field('notes','Notas')}
      <button type="button" className="primary" disabled={busy||!onSavePerformance} onClick={save}>Salvar métricas</button>
      <button type="button" disabled={busy||!onGenerateInsights} onClick={()=>onGenerateInsights({color:variant?.color})}>Gerar insights</button>
    </div>
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
        <input type="url" placeholder="https://www.tiktok.com/@conta/video/123..." value={tiktokLink} disabled={busy} onChange={e=>setTiktokLink(e.target.value)}/>
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



function ProductPhotoPicker({saved,files,removed,onFiles,onRemoved}){
  const input=useRef();
  const [previews,setPreviews]=useState([]),[error,setError]=useState('');
  useEffect(()=>{const urls=files.map(file=>URL.createObjectURL(file));setPreviews(urls);return()=>urls.forEach(url=>URL.revokeObjectURL(url))},[files]);
  const active=saved.filter(photo=>!removed.includes(photo.id));
  function select(list){
    const added=Array.from(list||[]);
    if(active.length+files.length+added.length>8){setError('Escolha até 8 fotos do produto.');return}
    if(added.some(file=>file.size>40*1024*1024)){setError('Cada foto deve ter no máximo 40 MB.');return}
    if([...files,...added].reduce((total,file)=>total+file.size,0)>240*1024*1024){setError('Envie até 240 MB de fotos de cada vez.');return}
    if(added.some(file=>!/^image\/(jpeg|png|webp)$/.test(file.type))){setError('Use fotos JPG, PNG ou WebP.');return}
    setError('');onFiles([...files,...added]);
  }
  return <section className="product-photo-picker" aria-label="Fotos do produto"><div className="section-title"><h3>Fotos do produto</h3><span className="help">{active.length+files.length}/8</span></div><p>Mostre a frente, as costas e os detalhes da peça. A identidade continua vindo da modelo fixa.</p>
    <div className="product-photo-grid">{active.map((photo,i)=><div className="product-photo" key={photo.id}><a href={photo.url} target="_blank" rel="noreferrer"><img src={photo.url} alt={`Foto salva do produto ${i+1}`}/></a><small>{photo.original_name}</small><button type="button" onClick={()=>onRemoved([...removed,photo.id])} aria-label={`Remover ${photo.original_name}`}><X size={13}/>Remover</button></div>)}
      {files.map((file,i)=><div className="product-photo" key={i}>{previews[i]&&<img src={previews[i]} alt={`Nova foto do produto ${i+1}`}/>}<small>{file.name}</small><span className="pending-photo">A salvar</span><button type="button" onClick={()=>onFiles(files.filter((_,index)=>index!==i))} aria-label={`Retirar ${file.name}`}><X size={13}/>Retirar</button></div>)}</div>
    <input ref={input} type="file" multiple hidden accept="image/jpeg,image/png,image/webp" onChange={e=>{select(e.target.files);e.target.value=''}}/>
    <button type="button" className="upload-button" disabled={active.length+files.length>=8} onClick={()=>input.current.click()}><ImagePlus size={18}/>Adicionar fotos do produto</button>
    <small className="help">JPG, PNG ou WebP · até 40 MB por foto. As fotos serão enviadas ao clicar em Salvar briefing.</small>
    {!!removed.length&&<button type="button" className="undo-photos" onClick={()=>onRemoved([])}>Desfazer remoções ({removed.length})</button>}
    {error&&<p className="inline-error" role="alert">{error}</p>}
  </section>;
}
export function BriefForm({campaign,onSave,busy,onDirty,onCancel}){
  const [draft,setDraft]=useState({...emptyBrief,...campaign});
  const [nicheOptions,setNicheOptions]=useState(NICHES);
  useEffect(()=>{let alive=true;(async()=>{try{const mn=draft?.model_name||campaign?.model_name||'Micaela'; const data=await modelLibrary(mn); if(!alive)return; const rows=data.niches||[]; if(rows.length) setNicheOptions(rows.map(n=>({id:n.niche,label:n.label})));}catch(_){}})(); return()=>{alive=false}; },[draft?.model_name, campaign?.model_name]);
  const [photos,setPhotos]=useState([]),[removed,setRemoved]=useState([]);
  const [descriptionPhoto,setDescriptionPhoto]=useState(null);
  const [showAdvanced,setShowAdvanced]=useState(false);
  const published=campaign?.status==='published';
  const essential=[['name','Nome da campanha','Ex.: Look de verão'],['product','O que é o produto?','Ex.: Calça legging de cintura alta'],['color','Cores / variações','Ex.: azul, branco, preto, rosa pink']];
  const advanced=[['model_name','Modelo','Nome da modelo fixa'],['outfit','Roupa','Ex.: Legging com top branco'],['audience','Público','Para quem é o produto?'],['benefit','Benefício','Um benefício que você pode demonstrar'],['angle','Ângulo','Ex.: Mostrar caimento e detalhes'],['tone','Tom','Ex.: Conversacional'],['style','Estilo visual','Ex.: Natural e realista']];
  const change=(key,value)=>{setDraft(d=>({...d,[key]:value}));onDirty?.(true)};
  function applyNiche(niche){
    const defaults=NICHE_DEFAULTS[niche]||{};
    const label=({praia:'Praia',academia:'Academia',casual:'Casual','dia-a-dia':'Dia a dia',intima:'Íntima',fantasia:'Fantasia'})[niche]||niche;
    setDraft(d=>{
      const model=d.model_name||'Micaela';
      const next={...d,niche,...defaults,model_name:model,generator:d.generator||'flow'};
      // Always keep campaign name in sync with niche (auto pattern or empty).
      // If the user typed a fully custom name, still update when it looks like the auto "Modelo · Nicho" pattern.
      const prev=String(d.name||'').trim();
      const autoRe=/^.+\s·\s.+$/;
      const modelLow=(model||'').toLowerCase();
      if(niche && (!prev || autoRe.test(prev) || (modelLow && prev.toLowerCase().startsWith(modelLow)) || prev.toLowerCase().startsWith('micaela'))){
        next.name=`${model} · ${label}`;
      }
      return next;
    });
    onDirty?.(true);
  }
  // on first mount for create (no campaign), apply current niche defaults once
  useEffect(()=>{
    if(!campaign && draft.niche && !(draft.audience||draft.benefit||draft.movements)){
      applyNiche(draft.niche);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  },[]);
  const field=(key,label,placeholder)=>(
    <div key={key} className={key==='product'?'product-field':''}>
      <label>{label}{['name','model_name','product'].includes(key)&&' *'}
        <input value={draft[key]||''} onChange={e=>change(key,e.target.value)} placeholder={placeholder} required={['name','model_name'].includes(key)} maxLength={500}/>
        {key==='color'&&<small className="help">Separe as cores por vírgulas para criar uma variação de cada uma.</small>}
      </label>
      {key==='product'&&(published?<ProductGallery photos={campaign?.product_assets||[]}/>:<ProductPhotoPicker saved={campaign?.product_assets||[]} files={photos} removed={removed} onFiles={value=>{setPhotos(value);onDirty?.(true)}} onRemoved={value=>{setRemoved(value);onDirty?.(true)}}/>)}
    </div>
  );
  return <form className="brief-form" onSubmit={e=>{e.preventDefault();onSave(Object.fromEntries(Object.keys(emptyBrief).map(k=>[k,draft[k]||''])),photos,removed,descriptionPhoto);setDescriptionPhoto(null)}}>
    <fieldset disabled={busy||published}>
      <label>Nicho da modelo *
        <select value={draft.niche||''} onChange={e=>applyNiche(e.target.value)} required>
          <option value="">Escolha o nicho</option>
          {nicheOptions.map(n=><option key={n.id} value={n.id}>{n.label}</option>)}
        </select>
        <small className="help">Ao escolher o nicho, público, benefício, ângulo, tom, estilo, detalhes e movimentos são preenchidos automaticamente. Você só ajusta produto, cores e nome.</small>
      </label>
      <div className="form-grid">{essential.map(([k,l,p])=>field(k,l,p))}</div>
      <section className="ai-analysis-field" aria-label="Análise automática do produto">
        <div className="section-title"><h3>Análise automática do produto</h3><span className="help">Opcional</span></div>
        <label>Foto da descrição do produto (print da página da loja/TikTok Shop)
          <input type="file" accept="image/*" onChange={e=>setDescriptionPhoto(e.target.files?.[0]||null)}/>
          <small className="help">Ao salvar, a IA lê essa foto (e a primeira foto do produto, se houver) e preenche automaticamente benefício, ângulo, movimentos e detalhes — sem sobrescrever o que você já preencheu. Precisa da IA configurada em "Configurações de Escrita com IA".</small>
        </label>
        {descriptionPhoto&&<small className="help">Selecionada: {descriptionPhoto.name}</small>}
      </section>
      <section className="sell-fields" aria-label="Argumento de venda">
        <div className="section-title"><h3>Argumento de venda</h3><span className="help">Opcional, mas muda muito o roteiro</span></div>
        <label>O que mais segura a compra?
          <input list="objection-options" value={draft.objection||''} onChange={e=>change('objection',e.target.value)} placeholder="Escolha ou escreva a dúvida do cliente" maxLength={500}/>
          <datalist id="objection-options">{OBJECTIONS.map(o=><option key={o} value={o}/>)}</datalist>
          <small className="help">Com esse campo preenchido, o hook passa a falar da dor do cliente e o meio do roteiro mostra a prova que derruba a dúvida.</small>
        </label>
        <label>Oferta real (se existir)
          <input value={draft.offer||''} onChange={e=>change('offer',e.target.value)} placeholder="Ex.: 20% até domingo · últimas peças do P" maxLength={500}/>
          <small className="help">Só preencha se for verdade. É o único caso em que o roteiro usa urgência — prazo ou estoque inventado é propaganda enganosa e queima o perfil.</small>
        </label>
      </section>
      <section className="generator-choice" aria-label="Escolha do gerador">
        <div className="section-title"><h3>Gerador</h3><span className="help">Escolha como criar imagem e vídeo</span></div>
        <p className="help generator-choice-help">A opção fica visível para você trocar entre os dois serviços antes de salvar o briefing.</p>
        <div className="generator-options" role="radiogroup" aria-label="Gerador de imagem e vídeo">
          <label className={'generator-option '+(draft.generator==='flow'?'selected':'')}>
            <input type="radio" name="generator" value="flow" checked={(draft.generator||'flow')==='flow'} onChange={e=>change('generator',e.target.value)}/>
            <span><strong>Google Flow</strong><small>Imagem e vídeo em 1080p</small></span>
          </label>
          <label className={'generator-option '+(draft.generator==='grok'?'selected':'')}>
            <input type="radio" name="generator" value="grok" checked={draft.generator==='grok'} onChange={e=>change('generator',e.target.value)}/>
            <span><strong>Grok Imagine</strong><small>Imagem em 720p</small></span>
          </label>
        </div>
      </section>
      <button type="button" className="button full" disabled={busy||published} onClick={()=>setShowAdvanced(v=>!v)}>{showAdvanced?'Ocultar ajustes do nicho':'Ver / editar o que o nicho preencheu'}</button>
      {showAdvanced && (
        <div className="niche-advanced">
          <div className="notice"><strong>Preenchido pelo nicho.</strong> Pode editar se quiser — o padrão já está otimizado pra TikTok Shop.</div>
          <div className="form-grid">{advanced.map(([k,l,p])=>field(k,l,p))}</div>
          <label>Detalhes adicionais<textarea rows={3} value={draft.details||''} onChange={e=>change('details',e.target.value)} placeholder="Enquadramento, gestos e detalhes do produto" maxLength={5000}/></label>
          <label>Movimentos para mostrar<textarea rows={3} value={draft.movements||''} onChange={e=>change('movements',e.target.value)} placeholder="Ex.: caminhar dois passos, virar de lado, ajustar o cós" maxLength={1500}/><small className="help">Movimentos que devem aparecer no vídeo deste produto</small></label>
        </div>
      )}
      {!showAdvanced && (
        <div className="notice niche-summary">
          <strong>Já preenchido:</strong> {(draft.audience||'—').slice(0,70)}… · tom {draft.tone||'—'} · estilo {draft.style||'—'}
        </div>
      )}
    </fieldset>
    <div className="form-actions">
      {onCancel&&<button type="button" disabled={busy} onClick={onCancel}>Cancelar</button>}
      <button className="primary" disabled={busy||!draft.name?.trim()||!draft.model_name?.trim()||!draft.niche}>{campaign?'Salvar':'Criar campanha'}</button>
    </div>
  </form>;
}


export function StudioIdentityPanel({identity,setIdentity,busy,onError,onFlash,onSaved}){
  const [draft,setDraft]=useState(()=>({...(identity||{})}));
  const [saving,setSaving]=useState(false);
  useEffect(()=>{ if(identity) setDraft({...identity}); },[identity]);
  function set(k,v){ setDraft(d=>({...d,[k]:v})); }
  async function save(){
    if(busy||saving)return;
    setSaving(true);
    try{
      const res=await saveStudioIdentity({
        studio_name:draft.studio_name||'',
        brand_name:draft.brand_name||'',
        model_name:draft.model_name||'',
        tiktok_handle:(draft.tiktok_handle||'').replace(/^@/,''),
        chrome_profile_hint:draft.chrome_profile_hint||'',
        grok_account_hint:draft.grok_account_hint||'',
        flow_account_hint:draft.flow_account_hint||'',
        notes:draft.notes||'',
      });
      const next=res.identity||res;
      setIdentity(next);
      onFlash?.('Identidade do estudio salva neste PC.');
      onSaved?.(next);
    }catch(e){ onError?.(e.message); }
    finally{ setSaving(false); }
  }
  return (
    <div className="identity-modal-body">
      <p className="help">Cada PC tem a propria identidade. No outro notebook, troque nome, @handle e perfil Chrome — nao copie browser_profiles nem data desta conta.</p>
      <div className="identity-grid">
        <label>Nome do estudio<input value={draft.studio_name||''} disabled={busy||saving} onChange={e=>set('studio_name',e.target.value)} placeholder="Estudio da Ana"/></label>
        <label>Marca / app<input value={draft.brand_name||''} disabled={busy||saving} onChange={e=>set('brand_name',e.target.value)} placeholder="Fabrica TikTok"/></label>
        <label>Nome da modelo<input value={draft.model_name||''} disabled={busy||saving} onChange={e=>set('model_name',e.target.value)} placeholder="Ana"/></label>
        <label>@ TikTok<input value={draft.tiktok_handle||''} disabled={busy||saving} onChange={e=>set('tiktok_handle',e.target.value.replace(/^@/,''))} placeholder="handle_sem_arroba"/></label>
        <label>Perfil Chrome<input value={draft.chrome_profile_hint||''} disabled={busy||saving} onChange={e=>set('chrome_profile_hint',e.target.value)} placeholder="Profile 7 ou nome no Chrome (ex.: Micaela)"/></label>
        <label>Conta Grok (lembrete)<input value={draft.grok_account_hint||''} disabled={busy||saving} onChange={e=>set('grok_account_hint',e.target.value)} placeholder="email@…"/></label>
        <label>Conta Flow (lembrete)<input value={draft.flow_account_hint||''} disabled={busy||saving} onChange={e=>set('flow_account_hint',e.target.value)} placeholder="email@…"/></label>
        <label className="span-2">Notas<textarea rows={2} value={draft.notes||''} disabled={busy||saving} onChange={e=>set('notes',e.target.value)} placeholder="Lembretes locais"/></label>
      </div>
      {draft.tiktok_handle ? <p className="help">URL: https://www.tiktok.com/@{(draft.tiktok_handle||'').replace(/^@/,'')} · pasta CDP: {draft.cdp_folder||'…'}</p> : null}
      <div className="form-actions">
        <button type="button" className="primary" disabled={busy||saving} onClick={save}>{saving?'Salvando…':'Salvar identidade'}</button>
      </div>
    </div>
  );
}


export function WriterSettingsPanel({busy,onError,onFlash,onSaved}){
  const [data,setData]=useState(null);
  const [open,setOpen]=useState(false);
  const [key,setKey]=useState('');
  const [saving,setSaving]=useState(false);
  const [testing,setTesting]=useState(false);
  const [sample,setSample]=useState(null);
  useEffect(()=>{writerSettings().then(setData).catch(e=>onError?.(e.message))},[]);
  if(!data) return null;
  const change=(patch)=>setData(d=>({...d,...patch}));
  async function save(extra={}){
    setSaving(true);setSample(null);
    try{
      const payload={provider:data.provider||'',model:data.model||'',enabled:!!data.enabled,...extra};
      if(key.trim()) payload.api_key=key.trim();
      const saved=await saveWriterSettings(payload);
      setData(saved);setKey('');
      onFlash?.(saved.enabled?'Escrita por IA ligada. A identidade tem o botão próprio, acima.':'Configuração da escrita salva.');
      onSaved?.(saved);
    }catch(e){onError?.(e.message)}finally{setSaving(false)}
  }
  async function test(){
    setTesting(true);setSample(null);
    try{
      const r=await testWriter();
      if(r.ok){setSample(r.sample);onFlash?.('Conexão funcionando.')}
      else onError?.('O provedor recusou: '+(r.message||'motivo não informado'));
    }catch(e){onError?.(e.message)}finally{setTesting(false)}
  }
  return <section className={'writer-panel card-panel'+(open?' is-open':' is-collapsed')}>
    <div className="setup-head">
      <button type="button" className="identity-toggle" onClick={()=>setOpen(o=>!o)}>
        <span className="eyebrow">ESCRITA DAS FALAS</span>
        <strong>{data.enabled?`Por IA · ${data.provider==='gemini'?'Gemini':'OpenAI'}`:'Texto local (sem IA)'}</strong>
      </button>
      <button type="button" className="button" onClick={()=>setOpen(o=>!o)}>{open?'Recolher':'Configurar'}</button>
    </div>
    {open && <>
    <p className="help">
      Com isto ligado, o hook, o desenvolvimento, o CTA e a legenda passam a ser escritos por um
      modelo de linguagem. O app continua conferindo cada texto: orçamento de palavras, nenhum
      atributo fora do briefing e urgência só com oferta real. Reprovado duas vezes, ele volta
      sozinho para o texto local — e sem chave configurada nada muda.
    </p>
    <label>Provedor
      <select value={data.provider||''} disabled={busy||saving} onChange={e=>change({provider:e.target.value,model:(data.default_models||{})[e.target.value]||''})}>
        <option value="">Desligado (texto local)</option>
        <option value="openai">OpenAI (ChatGPT)</option>
        <option value="gemini">Google Gemini</option>
      </select>
    </label>
    {data.provider && <>
      <label>Modelo
        <input value={data.model||''} disabled={busy||saving} onChange={e=>change({model:e.target.value})} placeholder={(data.default_models||{})[data.provider]||''} maxLength={120}/>
      </label>
      <label>Chave de API
        <input type="password" value={key} disabled={busy||saving} onChange={e=>setKey(e.target.value)}
          placeholder={data.has_key?`Chave guardada ${data.key_hint} — deixe vazio para manter`:'Cole a chave aqui'} maxLength={400} autoComplete="off"/>
        <small className="help">Fica só neste computador, em data/llm.json. Nunca é enviada para o GitHub nem aparece na tela depois de salva.</small>
      </label>
      <label className="check-row">
        <input type="checkbox" checked={!!data.enabled} disabled={busy||saving||!data.has_key&&!key.trim()} onChange={e=>change({enabled:e.target.checked})}/>
        Usar a IA para escrever as falas
      </label>
    </>}
    <div className="form-actions">
      {data.has_key&&<button type="button" disabled={busy||saving} onClick={()=>save({clear_key:true,enabled:false})}>Remover chave</button>}
      {data.provider&&data.has_key&&<button type="button" disabled={busy||testing} onClick={test}>{testing?'Testando…':'Testar conexão'}</button>}
      <button type="button" className="primary" disabled={busy||saving} onClick={()=>save()}>{saving?'Salvando…':'Salvar escrita por IA'}</button>
    </div>
    {sample&&<div className="notice writer-sample">
      <strong>Exemplo gerado agora:</strong>
      <p><em>Hook:</em> {sample.hook}</p>
      <p><em>Desenvolvimento:</em> {sample.development}</p>
      <p><em>CTA:</em> {sample.cta}</p>
    </div>}
    </>}
  </section>;
}

export function SetupChecklist({busy,onError}){
  const [data,setData]=useState(null);
  const [open,setOpen]=useState(true);
  useEffect(()=>{ setupStatus().then(d=>{setData(d); if((d.ready_score||0)>=80) setOpen(false);}).catch(e=>onError?.(e.message)); },[]);
  if(!data) return null;
  const score=data.ready_score||0;
  return (
    <section className={'setup-checklist card-panel'+(open?' is-open':' is-collapsed')}>
      <div className="setup-head">
        <button type="button" className="identity-toggle" onClick={()=>setOpen(o=>!o)}>
          <span className="eyebrow">SETUP DESTE PC</span>
          <strong>Pronto {score}% · {data.niches_filled}/{data.niches_total} nichos</strong>
        </button>
        <button type="button" className="button" onClick={()=>setOpen(o=>!o)}>{open?'Recolher':'Ver checklist'}</button>
      </div>
      {open && (
        <ul className="setup-list">
          <li className={data.identity_ok?'ok':'todo'}>{data.identity_ok?'Identidade preenchida':'Preencher identidade (icone no header)'}</li>
          <li className={data.gen_profile_ready?'ok':'todo'}>{data.gen_profile_ready?'Perfil Grok/Flow (abas) pronto':'Abrir Grok ou Flow uma vez e fazer login'}</li>
          <li className={data.cdp_ready?'ok':'todo'}>{data.cdp_ready?'Chrome CDP Studio pronto':'Abrir TikTok Studio / coletar metricas 1x'}</li>
          {(data.next_steps||[]).map((s,i)=><li key={i} className="hint">{s}</li>)}
        </ul>
      )}
    </section>
  );
}

export function DailyQueueCard({busy,onError,onFlash,onCreate}){
  const [q,setQ]=useState(null);
  useEffect(()=>{ productivityQueue().then(setQ).catch(e=>onError?.(e.message)); },[]);
  if(!q) return null;
  const items=q.daily_queue||[];
  const prog=q.daily_progress||{};
  return (
    <section className="daily-queue card-panel">
      <div className="daily-head">
        <div>
          <span className="eyebrow">FILA DE HOJE</span>
          <h2>5 posts · {prog.in_flight||0} em producao · faltam ~{prog.remaining??5}</h2>
          <p className="help">Do playbook. Crie a campanha e siga no Produzir.</p>
        </div>
      </div>
      {!items.length && <p className="help">Rode um lote 7/15/30 em Resultados e gere o playbook para encher a fila.</p>}
      <div className="daily-grid">
        {items.map((it,i)=>(
          <article className="daily-card" key={i}>
            <span className="campaign-id">POST {i+1}/5</span>
            <strong>{it.title||'Ideia do playbook'}</strong>
            <small>{it.niche||'nicho'}{it.spoken_hook?` · ${String(it.spoken_hook).slice(0,70)}`:''}</small>
            <button type="button" className="primary" disabled={busy} onClick={()=>onCreate?.(typeof it.index==='number'?it.index:i)}>{it.action||'Criar campanha'}</button>
          </article>
        ))}
      </div>
    </section>
  );
}

export function ModelLibraryPanel({modelName='Micaela',busy,onError,onFlash}){
  const [items,setItems]=useState([]);
  const [loading,setLoading]=useState(true);
  const [selectedNiche,setSelectedNiche]=useState('');
  const [sheetBusy,setSheetBusy]=useState(false);
  const [lightbox,setLightbox]=useState(null);
  const [renaming,setRenaming]=useState(null);
  const [renameDraft,setRenameDraft]=useState('');
  const fileRefs=useRef({});
  async function load(){
    setLoading(true);
    try{
      const data=await modelLibrary(modelName);
      const niches=data.niches||[];
      setItems(niches);
      setSelectedNiche(prev=>{
        if(prev && niches.some(n=>n.niche===prev && n.has_photo)) return prev;
        const first=niches.find(n=>n.has_photo);
        return first?first.niche:'';
      });
    }catch(e){onError?.(e.message||String(e))}
    finally{setLoading(false)}
  }
  useEffect(()=>{load()},[modelName]);
  useEffect(()=>{
    if(!lightbox) return;
    const onKey=e=>{ if(e.key==='Escape') setLightbox(null); };
    window.addEventListener('keydown', onKey);
    return ()=>window.removeEventListener('keydown', onKey);
  },[lightbox]);
  async function onPick(niche,file,inputEl){
    if(!file)return;
    try{
      if(isCloudMode()){
        await uploadModelLibraryPhotoDirect(modelName,niche,file);
      }else{
        const form=new FormData();
        form.set('model_name',modelName);
        form.set('niche',niche);
        form.set('file',file);
        await uploadModelLibrary(form);
      }
      onFlash?.('Foto padrão salva: '+niche);
      await load();
      setSelectedNiche(niche);
    }catch(e){onError?.(e.message||String(e))}
    finally{
      if(inputEl) inputEl.value='';
      else if(fileRefs.current[niche]) fileRefs.current[niche].value='';
    }
  }
  function beginRename(item,e){
    e?.stopPropagation?.();
    setRenaming(item.niche);
    setRenameDraft(item.label||'');
  }
  async function saveRename(e){
    e?.preventDefault?.();
    e?.stopPropagation?.();
    if(!renaming) return;
    const label=(renameDraft||'').trim();
    if(!label){onError?.('Informe o nome da moda.');return}
    try{
      await renameModelLibraryLabel({model_name:modelName,niche:renaming,label});
      onFlash?.('Moda renomeada: '+label);
      setRenaming(null);
      await load();
    }catch(err){onError?.(err.message||String(err))}
  }
  async function copySheet(){
    if(!selectedNiche){onError?.('Selecione um nicho com foto.');return}
    setSheetBusy(true);
    try{
      const data=await characterSheet(modelName,selectedNiche);
      const text=data.prompt||'';
      try{
        await navigator.clipboard.writeText(text);
        onFlash?.(data.message||'Ficha de consistência copiada.');
      }catch(_){
        window.prompt('Toque e segure no campo para selecionar e copiar:', text);
        onFlash?.('Prompt exibido para cópia manual.');
      }
    }catch(e){onError?.(e.message||String(e))}
    finally{setSheetBusy(false)}
  }
  async function openSheetGrok(){
    if(isMobileDevice())return;
    if(!selectedNiche){onError?.('Selecione um nicho com foto.');return}
    const ok=window.confirm(
      'Abrir o Grok com a ficha de consistência?\n\n'+
      'O prompt será copiado para a área de transferência. No Grok, anexe a foto da biblioteca e cole o prompt.'
    );
    if(!ok)return;
    setSheetBusy(true);
    try{
      const data=await openCharacterSheet({model_name:modelName,niche:selectedNiche,confirmed:true});
      onFlash?.(data.message||'Grok aberto. Anexe a foto e cole o prompt.');
      if(data.prompt){
        try{await navigator.clipboard.writeText(data.prompt)}catch(_){/* backend may already have copied */}
      }
    }catch(e){onError?.(e.message||String(e))}
    finally{setSheetBusy(false)}
  }
  const selected=items.find(x=>x.niche===selectedNiche);
  return (
    <section className="model-library">
      <div className="home-hero" style={{marginBottom:12}}>
        <div>
          <span className="eyebrow">MODELO FIXA · {(items.filter(x=>x.has_photo).length)}/{(items.length||6)} nichos</span>
          <h2>Fotos padrão por nicho — {modelName}</h2>
          <p>Uma foto por nicho. Clique na foto para ver em tela cheia. Pode renomear cada moda.</p>
        </div>
      </div>
      {loading && <div className="notice">Carregando biblioteca…</div>}
      <div className="model-library-grid">
        {items.map(item=>(
          <article
            className={'model-niche-card'+(item.has_photo?' has-photo':'')+(selectedNiche===item.niche?' is-selected':'')}
            key={item.niche}
            onClick={()=>{ if(item.has_photo) setSelectedNiche(item.niche); }}
            role={item.has_photo?'button':undefined}
            tabIndex={item.has_photo?0:undefined}
            onKeyDown={e=>{ if(item.has_photo && (e.key==='Enter'||e.key===' ')){ e.preventDefault(); setSelectedNiche(item.niche);} }}
          >
            {renaming===item.niche ? (
              <form className="niche-rename-row" onClick={e=>e.stopPropagation()} onSubmit={saveRename}>
                <input
                  autoFocus
                  value={renameDraft}
                  maxLength={60}
                  aria-label="Novo nome da moda"
                  onChange={e=>setRenameDraft(e.target.value)}
                  onKeyDown={e=>{ if(e.key==='Escape'){ e.preventDefault(); setRenaming(null);} }}
                />
                <button type="submit" className="primary" disabled={busy||loading}>Salvar</button>
                <button type="button" disabled={busy||loading} onClick={()=>setRenaming(null)}>Cancelar</button>
              </form>
            ) : (
              <div className="niche-title-row" onClick={e=>e.stopPropagation()}>
                <strong>{item.label}</strong>
                <button type="button" className="icon-button btn-rename" title="Renomear moda" aria-label="Renomear moda" disabled={busy||loading} onClick={e=>beginRename(item,e)}>
                  <Pencil size={14}/>
                </button>
              </div>
            )}
            <div className="model-niche-preview">
              {item.has_photo ? (
                <button
                  type="button"
                  className="model-niche-thumb"
                  title="Ver em tela cheia"
                  onClick={e=>{e.stopPropagation();setSelectedNiche(item.niche);setLightbox({url:item.url,label:item.label,name:item.original_name||''});}}
                >
                  <img key={item.url||item.updated_at||item.niche} src={item.url} alt={item.label}/>
                </button>
              ) : <span className="help">Sem foto ainda</span>}
            </div>
            <small className="help">{item.original_name||'Envie a foto padrão deste look'}{item.updated_at?` · atualizada`:''}</small>
            <input ref={el=>{fileRefs.current[item.niche]=el}} type="file" accept="image/jpeg,image/png,image/webp" hidden onChange={e=>onPick(item.niche,e.target.files?.[0],e.target)}/>
            <button type="button" className="button" disabled={busy||loading} onClick={e=>{e.stopPropagation();fileRefs.current[item.niche]?.click()}}>{item.has_photo?'Trocar foto':'Enviar foto padrão'}</button>
          </article>
        ))}
      </div>
      <div className="character-sheet-box">
        <div>
          <strong>Gerar ficha de consistência</strong>
          <p className="help">
            Selecione um nicho com foto. Copie o prompt mestre de identidade ou abra o Grok:
            cole o prompt e anexe a foto da biblioteca como referência.
            {selected ? <> Nicho selecionado: <em>{selected.label}</em>.</> : <> Nenhum nicho com foto selecionado.</>}
          </p>
        </div>
        <div className="character-sheet-actions">
          <button type="button" className="button" disabled={busy||loading||sheetBusy||!selectedNiche} onClick={copySheet}>
            Copiar ficha de consistência
          </button>
          <ServiceLaunch service="grok" className="button primary" disabled={busy||loading||sheetBusy||!selectedNiche} onClick={openSheetGrok}>
            {isMobileDevice()?'Abrir Grok no celular':'Abrir no Grok'}
          </ServiceLaunch>
        </div>
        {isMobileDevice()&&<p className="help">Copie a ficha primeiro. Depois abra o Grok, cole o texto e anexe a foto da biblioteca.</p>}
      </div>
      {lightbox && (
        <div className="photo-lightbox" role="dialog" aria-modal="true" aria-label={lightbox.label} onClick={()=>setLightbox(null)}>
          <div className="photo-lightbox-inner" onClick={e=>e.stopPropagation()}>
            <div className="photo-lightbox-bar">
              <div>
                <strong>{lightbox.label}</strong>
                {lightbox.name ? <small className="help">{lightbox.name}</small> : null}
              </div>
              <div className="photo-lightbox-actions">
                <a className="button" href={lightbox.url} target="_blank" rel="noreferrer">Abrir original</a>
                <button type="button" className="icon-button" aria-label="Fechar" onClick={()=>setLightbox(null)}><X size={20}/></button>
              </div>
            </div>
            <img src={lightbox.url} alt={lightbox.label}/>
          </div>
        </div>
      )}
    </section>
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
    try{
      const data=await listLinkAnalyses();
      setItems(data.items||[]);
    }catch(e){/* ignore empty */}
    try{
      const latest=await studioAuditLatest();
      if(latest?.report) setBatchReport(latest);
    }catch(e){/* ignore */}
    try{
      const pb=await studioPlaybook();
      if(pb?.playbook) setPlaybook(pb.playbook);
    }catch(e){/* ignore */}
    try{
      const q=await productivityQueue();
      setQueue(q);
    }catch(e){/* ignore */}
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

  function pctNum(r){
    if(r==null) return 0;
    if(typeof r==='number') return r;
    const n=Number(String(r.pct_raw||r.pct||'').replace('%','').replace('<','').replace(',','.'));
    return Number.isFinite(n)?n:0;
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

  const batchRows=batchReport?.report?sortedBatchRows():[];
  const histRows=sortedHistItems();
  const activeTab = tab || 'studio';
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
            <span className="collapse-chevron">{open?'▾':'▸'}</span>
            <strong>{title}</strong>
            {badge!=null?<span className="count">{badge}</span>:null}
          </button>
          <button type="button" className="button analysis-action collapse-btn" onClick={toggle}>{open?'Comprimir':'Expandir'}</button>
        </div>
        {open && <div className="collapse-body">{children}</div>}
      </div>
    );
  }

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
              <Collapse id="prod-continue" title={`Continuar producao (${(queue.continue||[]).length})`} defaultOpen={true} badge={(queue.continue||[]).length}>
                {(queue.continue||[]).length===0 && <p className="help">Nenhuma campanha em andamento. Crie uma do playbook abaixo.</p>}
                <ul className="prod-list">
                  {(queue.continue||[]).map((c,i)=>(
                    <li key={c.campaign_id||i} className="prod-card">
                      <div>
                        <strong>{c.name}</strong>
                        <div className="help">{c.label} · {c.status}{c.niche?` · ${c.niche}`:''}</div>
                        <div className="help"><em>Como:</em> {c.how}</div>
                      </div>
                      <button type="button" className="primary" disabled={busy} onClick={()=>onOpenProduce?.(c.campaign_id)}>Abrir Produzir</button>
                    </li>
                  ))}
                </ul>
              </Collapse>
              <Collapse id="prod-next" title={`Criar do playbook (${(queue.produce_next||[]).length})`} defaultOpen={true} badge={(queue.produce_next||[]).length}>
                {(queue.produce_next||[]).length===0 && <p className="help">Sem briefs. Va em Playbook → Atualizar, ou rode o lote 30d.</p>}
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
              <Collapse id="prod-improve" title={`Espaco para melhorar (${(queue.improve||[]).length})`} defaultOpen={true} badge={(queue.improve||[]).length}>
                <ul className="prod-list improve">
                  {(queue.improve||[]).map((x,i)=>(
                    <li key={i} className="prod-card">
                      <div>
                        <span className={'chip tone-'+(x.kind==='evitar'?'pink':'purple')}>{x.kind}</span>
                        <strong> {x.title}</strong>
                        <div className="help"><em>Acao:</em> {x.action}</div>
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
                <input type="url" placeholder="https://www.tiktok.com/@conta/video/123..." value={url} disabled={busy||loading} onChange={e=>setUrl(e.target.value)}/>
              </label>
              <label className="metric-field full">Nota (opcional)
                <input type="text" placeholder="Ex.: post de junho, nao veio da fabrica" value={note} disabled={busy||loading} onChange={e=>setNote(e.target.value)}/>
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
            <h3>Historico de links</h3>
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
                <button type="button" className="button analysis-action" onClick={()=>setOpenId(null)}>Comprimir todos</button>
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
                          <button type="button" className="button analysis-action" onClick={()=>setOpenId(open?null:id)}>{open?'Comprimir':'Expandir detalhes'}</button>
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
