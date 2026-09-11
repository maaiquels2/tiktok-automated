import { useEffect, useRef, useState } from 'react';
import { Copy, Check, Download, Upload, X, ImagePlus, Film, ExternalLink } from 'lucide-react';
export function Dialog({title,children,onClose}){
  const ref=useRef(null);
  useEffect(()=>{ref.current.showModal();const el=ref.current;return()=>el.close()},[]);
  return <dialog ref={ref} className="dialog" onCancel={e=>{e.preventDefault();onClose()}} aria-label={title}><div className="dialog-heading"><h2>{title}</h2><button className="icon-button" onClick={onClose} aria-label="Fechar"><X size={20}/></button></div>{children}</dialog>;
}
export function CopyButton({text,onError,label='Copiar'}){
  const [copied,setCopied]=useState(false);
  const timer=useRef();
  useEffect(()=>()=>clearTimeout(timer.current),[]);
  return <button className="copy-button" disabled={!text} onClick={async()=>{try{await navigator.clipboard.writeText(text);setCopied(true);clearTimeout(timer.current);timer.current=setTimeout(()=>setCopied(false),1800)}catch{onError('Não foi possível copiar. Selecione o texto e pressione Ctrl+C.')}}}>{copied?<Check size={14}/>:<Copy size={14}/>} {copied?'Copiado':label}</button>;
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
export const emptyBrief={name:'',model_name:'Micaela',product:'',outfit:'',color:'',audience:'',benefit:'',angle:'',tone:'Conversacional',style:'Natural e realista',details:'',movements:'',generator:'flow'};
export function ProductGallery({photos=[]}){
  if(!photos.length)return null;
  return <section className="product-gallery"><h3>Fotos do produto</h3><p>Anexe estas fotos depois da referência fixa da modelo.</p><div className="product-photo-grid">{photos.map((photo,i)=><AssetView key={photo.id} asset={photo} title={`Produto · foto ${i+1}`} compact/>)}</div></section>;
}
export function VariantList({variants=[],onError,focus,images=[],videos=[],onUpload,busy,disabled,onSaveVariant,onRefreshVariant,immutable}){
  if(!variants.length)return null;
  const byImage=Object.fromEntries((images||[]).filter(a=>a.kind==='image').map(a=>[a.slot||a.metadata?.color||'',a]));
  const byVideo=Object.fromEntries((videos||[]).filter(a=>a.kind==='video').map(a=>[a.slot||a.metadata?.color||'',a]));
  const title=focus==='image'?'Imagens por cor':focus==='video'?'Vídeos por cor':focus==='script'?'Roteiros 15s por cor':'Prompts por cor';
  const help=focus==='image'
    ?'Gere e anexe uma imagem por cor. Todas ficam disponíveis para aprovação.'
    :focus==='video'
      ?'Use a imagem aprovada da mesma cor, copie o prompt de vídeo e anexe o MP4 de 15s. Precisa de um vídeo por cor.'
      :focus==='script'
        ?'Cada cor tem falas diferentes. Se não gostar, use Atualizar fala para gerar outra variação.'
        :'Abra cada cor para copiar os prompts e o roteiro correspondentes.';
  return <section className="variant-list"><div className="section-title"><h3>{title}</h3><span className="help">{variants.length} variações</span></div>
    <p>{help}</p>
    {variants.map((variant,idx)=>{
      const p=variant.prompts||{};
      const img=byImage[variant.color];
      const vid=byVideo[variant.color];
      const status=focus==='image'?(img?(img.approved_at?'Imagem aprovada':'Imagem anexada'):'Falta anexar')
        :focus==='video'?(vid?(vid.approved_at?'Vídeo aprovado':'Vídeo anexado'):'Falta anexar')
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
              <p><strong>0–2s:</strong> {p.hook||'-'}</p>
              <p><strong>2–12s:</strong> {p.development||'-'}</p>
              <p><strong>12–15s:</strong> {p.cta||'-'}</p>
            </div>
            {vid?<AssetView asset={vid} title={`Vídeo · ${variant.color}`} compact/>:null}
            {onUpload&&!immutable&&<Uploader kind="video" color={variant.color} exists={!!vid} busy={busy} disabled={disabled} onUpload={onUpload}/>}
          </>}
          {focus==='script'&&<>
            <div className="variant-actions">
              {onRefreshVariant&&!immutable&&<>
                <button type="button" disabled={busy} onClick={()=>onRefreshVariant(variant.id,['hook','caption'])}>Atualizar hook + legenda</button>
                <button type="button" disabled={busy} onClick={()=>onRefreshVariant(variant.id,['hook','development','cta','caption'])}>Atualizar fala inteira</button>
              </>}
            </div>
            {[['hook','Hook · 0-2s'],['development','Desenvolvimento · 2-12s'],['cta','CTA · 12-15s'],['caption','Legenda'],['video','Prompt de vídeo']].map(([key,title])=>
              <div className="variant-prompt" key={key}>
                <div className="section-title"><strong>{title}</strong><CopyButton text={p[key]||''} onError={onError}/></div>
                {onSaveVariant&&!immutable
                  ?<VariantScriptField variant={variant} field={key} value={p[key]||''} busy={busy} onSave={onSaveVariant}/>
                  :<p>{p[key]||'-'}</p>}
              </div>)}
          </>}
          {!['image','video','script'].includes(focus)&&[['image','Prompt de imagem'],['video','Prompt de vídeo'],['hook','Hook · 0-2s'],['development','Desenvolvimento · 2-12s'],['cta','CTA · 12-15s'],['caption','Legenda']].map(([key,title])=>
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
  const videos=(c.assets||[]).filter(a=>a.kind==='video');
  const colorSlots=((c.color||'').split(/[,;|\n]+/).map(v=>v.trim()).filter(Boolean));
  const slotOptions=[...colorSlots, 'Mix'].filter((v,i,arr)=>arr.indexOf(v)===i);
  const [order,setOrder]=useState(()=>videos.map(v=>v.id));
  const [seconds,setSeconds]=useState({});
  const [slot,setSlot]=useState(slotOptions[0]||'Mix');
  const [duration,setDuration]=useState(15);
  const [working,setWorking]=useState(false);
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
  async function runMix(){
    if(ordered.length<2){onError?.('Selecione pelo menos 2 videos.');return}
    setWorking(true);
    try{
      const clips=ordered.map(v=>({
        asset_id:v.id,
        seconds: seconds[v.id] ? Number(seconds[v.id]) : undefined,
      }));
      await onMix({clips, slot, duration:Number(duration)||15});
    }catch(e){onError?.(e.message||String(e))}
    finally{setWorking(false)}
  }
  if(!videos.length) return <div className="notice">Anexe ao menos 2 MP4s (por cor) para misturar.</div>;
  return <section className="video-mixer">
    <div className="section-title"><h3>Misturar videos</h3></div>
    <p className="help">Ordene os clips, defina quantos segundos pegar de cada um (ou deixe vazio para dividir ~15s) e gere um MP4 unico 9:16.</p>
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
      <label>Duracao total (s)<input type="number" min="10" max="60" step="0.5" value={duration} disabled={busy||immutable||working} onChange={e=>setDuration(e.target.value)}/></label>
    </div>
    <button className="primary full" disabled={busy||immutable||working||ordered.length<2} onClick={runMix}>{working?'Misturando…':'Gerar mix MP4'}</button>
    {ordered.length>=2&&<p className="help">Ordem: {ordered.map(v=>v.slot||v.id).join(' · ')}</p>}
  </section>;
}

export function PublishQueue({c,busy,immutable,onError,onOpen,onPublishSlot,onRefreshVariant}){
  const videos=c.assets.filter(a=>a.kind==='video');
  const variants=c.variants?.length?c.variants:[{color:c.color||'Produto',prompts:c.prompts,id:'main'}];
  const slotMap=(c.checklist&&c.checklist.slots)||{};
  const [active,setActive]=useState(()=>{
    const pending=variants.find(v=>!slotMap[v.color||'default']?.published);
    return pending?.color || variants[0]?.color || '';
  });
  const [checks,setChecks]=useState({});
  const [publishedUrl,setPublishedUrl]=useState('');
  useEffect(()=>{
    const pending=variants.find(v=>!slotMap[v.color||'default']?.published);
    if(pending&&slotMap[active||'default']?.published) setActive(pending.color);
  },[c.checklist,c.version]);
  const variant=variants.find(v=>v.color===active)||variants[0];
  const video=videos.find(v=>(v.slot||v.metadata?.color)===variant?.color) || videos[0];
  const done=!!slotMap[variant?.color||'default']?.published;
  const caption=variant?.prompts?.caption||c.prompts?.caption||'';
  const remaining=variants.filter(v=>!slotMap[v.color||'default']?.published).length;
  const check=(key,label)=><label className="check-row" key={key}><input type="checkbox" checked={!!checks[key]} disabled={busy||immutable||done} onChange={e=>setChecks(old=>({...old,[key]:e.target.checked}))}/><span>{label}</span></label>;
  return <section className="publish-queue">
    <div className="notice"><strong>Publique uma cor por vez.</strong> Escolha o produto/cor, copie a legenda, suba o MP4 no Studio e registre. Depois passe para a próxima.</div>
    <div className="publish-slot-tabs">
      {variants.map(v=>{
        const key=v.color||'default';
        const ok=!!slotMap[key]?.published;
        return <button type="button" key={key} className={'slot-tab'+(active===v.color?' active':'')+(ok?' done':'')} disabled={busy} onClick={()=>{setActive(v.color);setChecks({});setPublishedUrl(slotMap[key]?.url||'')}}>
          {ok?'✓ ':''}{v.color||'Produto'}
        </button>;
      })}
    </div>
    <div className="service-box"><strong>TikTok Studio · Micaela</strong>
      <button disabled={busy} onClick={()=>onOpen('studio','publish')}><ExternalLink size={16}/> Abrir perfil da Micaela</button>
      <p>Um botão só para o Studio. Troque o vídeo/legenda conforme a cor selecionada acima.</p>
    </div>
    {video?<AssetView asset={video} title={`MP4 · ${variant?.color||''}`}/>:<div className="notice">Sem vídeo para esta cor.</div>}
    <div className="variant-prompt">
      <div className="section-title"><strong>Legenda TikTok · {variant?.color}</strong>
        <span className="publish-caption-actions">
          <CopyButton text={caption} onError={onError}/>
          {onRefreshVariant&&variant?.id&&variant.id!=='main'&&!immutable&&!done&&
            <button type="button" disabled={busy} onClick={()=>onRefreshVariant(variant.id,['caption'])}>Nova legenda</button>}
        </span>
      </div>
      <p className="caption-preview">{caption||'-'}</p>
      <small className="help">Legenda alinhada ao produto, benefício e hashtags do nicho. Atualize se quiser outra variação.</small>
    </div>
    <CopyButton text={video?.local_path} label="Copiar caminho do MP4" onError={onError}/>
    {immutable&&variants.every(v=>slotMap[v.color||'default']?.published)?
      <div className="notice success"><Check size={18}/><strong>Todas as cores foram publicadas.</strong>
        <div className="publish-links">{variants.map(v=>{
          const info=slotMap[v.color||'default'];
          const url=info?.url||c.published_url;
          return url?<a key={v.color||'default'} href={url} target="_blank" rel="noreferrer">Ver {v.color||'publicação'} <ExternalLink size={14}/></a>:null;
        })}</div>
      </div>:
      done?<div className="notice success"><Check size={16}/> Cor <strong>{variant?.color}</strong> já registrada. Escolha a próxima ({remaining} restante{remaining===1?'':'s'}).</div>:
      <><h3>Checklist · {variant?.color}</h3>
        {check('account','Conferi que estou na conta da Micaela.')}
        {check('product',`Selecionei manualmente o produto no Shop: ${c.product} (${variant?.color}).`)}
        {check('caption','Subi este MP4 e colei a legenda desta cor.')}
        {check('review','Revisei vídeo, áudio, produto e direitos de uso.')}
        {check('published','Já publiquei manualmente no TikTok Studio esta cor.')}
        <label>Link do vídeo (opcional)<input type="url" value={publishedUrl} onChange={e=>setPublishedUrl(e.target.value)} placeholder="https://www.tiktok.com/@…/video/…"/></label>
        <button className="primary full" disabled={busy||!['account','product','caption','review','published'].every(k=>checks[k])}
          onClick={()=>onPublishSlot({color:variant?.color,checklist:checks,published_url:publishedUrl})}>
          Registrar publicação · {variant?.color}
        </button>
        <small className="help">Registra só esta cor. Quando todas estiverem feitas, a campanha fecha como publicada.</small>
      </>}
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
  const [photos,setPhotos]=useState([]),[removed,setRemoved]=useState([]);
  const published=campaign?.status==='published';
  const labels=[['name','Nome da campanha','Ex.: Look de verão'],['model_name','Modelo','Nome da modelo fixa'],['product','O que é o produto?','Ex.: Calça legging de cintura alta'],['outfit','Roupa','Ex.: Legging com top branco'],['color','Cores / variações','Ex.: azul, branco, preto, rosa pink'],['audience','Público','Para quem é o produto?'],['benefit','Benefício','Um benefício que você pode demonstrar'],['angle','Ângulo','Ex.: Mostrar caimento e detalhes'],['tone','Tom','Ex.: Conversacional'],['style','Estilo visual','Ex.: Natural e realista']];
  const change=(key,value)=>{setDraft(d=>({...d,[key]:value}));onDirty?.(true)};
  return <form className="brief-form" onSubmit={e=>{e.preventDefault();onSave(Object.fromEntries(Object.keys(emptyBrief).map(k=>[k,draft[k]||''])),photos,removed)}}>
    <fieldset disabled={busy||published}><div className="form-grid">{labels.map(([key,label,placeholder])=><div key={key} className={key==='product'?'product-field':''}><label>{label}{['name','model_name'].includes(key)&&' *'}<input value={draft[key]||''} onChange={e=>change(key,e.target.value)} placeholder={placeholder} required={['name','model_name'].includes(key)} maxLength={500}/>{key==='color'&&<small className="help">Separe as cores por vírgulas para criar uma variação de cada uma.</small>}</label>{key==='product'&&campaign&&(published?<ProductGallery photos={campaign.product_assets}/>:<ProductPhotoPicker saved={campaign.product_assets||[]} files={photos} removed={removed} onFiles={value=>{setPhotos(value);onDirty?.(true)}} onRemoved={value=>{setRemoved(value);onDirty?.(true)}}/>)}</div>)}</div>
    <label>Gerador<select value={draft.generator} onChange={e=>change('generator',e.target.value)}><option value="flow">Google Flow · alvo 1080p</option><option value="grok">Grok Imagine · alvo 720p</option></select></label>
    <label>Detalhes adicionais<textarea rows={3} value={draft.details||''} onChange={e=>change('details',e.target.value)} maxLength={5000} placeholder="Enquadramento, gestos e detalhes do produto"/></label>
    <label>Movimentos para mostrar<textarea rows={3} value={draft.movements||''} onChange={e=>change('movements',e.target.value)} maxLength={1500} placeholder="Ex.: caminhar dois passos, virar de lado, ajustar o cós e mostrar o bolso lateral"/><small className="help">Descreva os movimentos que devem aparecer no vídeo deste produto.</small></label></fieldset>
    {campaign?.prompts?.image&&!published&&<div className="notice">Alterar o briefing reinicia a produção e pede novas aprovações. Os arquivos anteriores permanecem na pasta local.</div>}
    {!published&&<div className="form-actions">{onCancel&&<button type="button" onClick={onCancel} disabled={busy}>Cancelar</button>}<button className="primary" type="submit" disabled={busy}>{busy?'Salvando…':campaign?'Salvar briefing':'Criar campanha'}</button></div>}
  </form>;
}
