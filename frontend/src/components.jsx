import { ServiceLaunch, TikTokLaunchButtons, isMobileDevice, isCloudMode } from './serviceLinks';
import { useEffect, useRef, useState } from 'react';
import { NICHE_DEFAULTS } from './nicheDefaults';
import { scorePrompt } from './promptScore';
// Regras de formato do servidor (services/formats.py; um teste confere).
import FORMAT_RULES from './formatRules.json';
import { swatchFor } from './ui';
import { isFewFacts, pointToFacts } from './sequenceText';
import { modelLibrary, uploadModelLibrary, uploadModelLibraryPhotoDirect, renameModelLibraryLabel, listModelLibraryModels, deleteModelLibraryPhoto, productivityQueue, setupStatus, characterSheet, openCharacterSheet, writerSettings, storySequence, homeReveal, storyArc, persuasionPreview, savePromptToLibrary } from './api';
import { Copy, Check, Download, Upload, X, ImagePlus, Film, ExternalLink, Pencil, Sparkles, Trash2, RefreshCw, BookOpen, BookmarkPlus } from 'lucide-react';
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
  const [manualHint,setManualHint]=useState(false);
  const timer=useRef();
  useEffect(()=>()=>clearTimeout(timer.current),[]);
  const markCopied=()=>{setCopied(true);setManualHint(false);clearTimeout(timer.current);timer.current=setTimeout(()=>setCopied(false),1800)};
  return <button className="copy-button" disabled={!text} onClick={async()=>{
    if(await copyText(text)){markCopied();return}
    // Fechar esse prompt não prova que o usuário copiou nada - por isso o
    // rótulo fica neutro ("Copie manualmente"), nunca "Copiado".
    window.prompt('Não foi possível copiar automaticamente. Toque e segure no campo abaixo para selecionar e copiar manualmente:',text);
    setCopied(false);setManualHint(true);
    clearTimeout(timer.current);timer.current=setTimeout(()=>setManualHint(false),4000);
    onError?.('Toque e segure no texto para selecionar e copiar.');
  }}>{copied?<Check size={14}/>:<Copy size={14}/>} {copied?'Copiado':(manualHint?'Copie manualmente':label)}</button>;
}
export function TextEditor({title,value,field,onSave,busy,onError,onDirty,readOnly=false,rows=5}){
  const [draft,setDraft]=useState(value||'');
  const changed=draft!==value;
  return <section className="text-editor"><div className="section-title"><h3>{title}</h3><CopyButton text={draft} onError={onError}/></div><textarea autoComplete="off" aria-label={title} value={draft} rows={rows} readOnly={readOnly} onChange={e=>{setDraft(e.target.value);onDirty(true)}} maxLength={12000}/>{changed&&<button disabled={busy||!draft.trim()} onClick={()=>onSave({[field]:draft})}>Salvar texto</button>}</section>;
}
export function AssetView({asset,title,compact=false}){
  if(!asset)return <div className="media-empty">{title}</div>;
  // Sem largura e altura a imagem so ocupa espaco depois de carregar e o conteudo abaixo pula.
  const w=Number(asset.metadata?.width),h=Number(asset.metadata?.height);
  const size=w>0&&h>0?{width:w,height:h}:{};
  return <div className={'asset-view '+(compact?'compact':'')}>
    {asset.kind==='video'?<video key={asset.id} controls playsInline preload="metadata" src={asset.url}/>:<a href={asset.url} target="_blank" rel="noreferrer" title="Abrir imagem em tamanho completo"><img src={asset.url} alt={title} {...size}/></a>}
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
export const emptyBrief={name:'',model_name:'Micaela',niche:'casual',product:'',outfit:'',color:'',audience:'',benefit:'',angle:'',tone:'Conversacional',style:'Natural e realista',details:'',movements:'',body_turns:'',objection:'',offer:'',generator:'flow',motor:'',video_mode:'',social_proof:'',video_style:'',sequence_clips:'',sequence_arc:''};
// Objecoes mais comuns no TikTok Shop de moda. O campo aceita texto livre: a
// lista so evita digitacao e mantem o texto no formato que o gerador reconhece.
export const OBJECTIONS=['Fica transparente no agachamento','A peça desce ou escorrega','Não sei se serve em mim','Parece barata de perto','Não dura / desbota na lavagem','Incomoda ou aperta no uso','Acho caro para uma peça só','Marca o corpo'];
export const NICHES=[{id:'praia',label:'Moda praia'},{id:'academia',label:'Moda academia'},{id:'casual',label:'Moda casual'},{id:'dia-a-dia',label:'Moda dia a dia'},{id:'intima',label:'Moda íntima'},{id:'fantasia',label:'Fantasia'}];
export function ProductGallery({photos=[]}){
  if(!photos.length)return null;
  return <section className="product-gallery"><h3>Fotos do produto</h3><p>Anexe estas fotos depois da referência fixa da modelo.</p><div className="product-photo-grid">{photos.map((photo,i)=><AssetView key={photo.id} asset={photo} title={`Produto · foto ${i+1}`} compact/>)}</div></section>;
}
// Nota do prompt de video, ao lado do contador de caracteres. Clicar mostra
// o que pesou na nota.
export function PromptScore({text,maxChars}){
  const [open,setOpen]=useState(false);
  const result=scorePrompt(text,{maxChars});
  if(!result)return null;
  return <span className="prompt-score-wrap">
    <button type="button" className={'prompt-score tone-'+result.tone} aria-expanded={open} onClick={()=>setOpen(v=>!v)} title="Ver o que pesou na nota">Nota {result.score}/10 · {result.label}</button>
    {open&&<div className="prompt-score-panel" role="dialog" aria-label="Detalhes da nota do prompt">
      {result.issues.length
        ?<ul>{result.issues.map(item=><li key={item}>{item}</li>)}</ul>
        :<p>Nenhum problema encontrado: tamanho, fala, ações e regras estão equilibrados.</p>}
      <small>A nota é uma checagem automática do texto. Ela aponta riscos, mas não garante o resultado do vídeo.</small>
    </div>}
  </span>;
}

// Menu suspenso (conta, ⋯ da campanha). Abre no clique e fecha ao clicar
// fora, no Esc ou ao escolher um item. Itens: {label, icon, onClick, href,
// danger, disabled} | {divider:true} | {node} para um bloco so de leitura.
export function Menu({label,trigger,items,align='end',iconOnly=false}){
  const [open,setOpen]=useState(false);
  const ref=useRef(null);
  useEffect(()=>{
    if(!open)return;
    const away=e=>{if(!ref.current?.contains(e.target))setOpen(false)};
    const esc=e=>{if(e.key==='Escape')setOpen(false)};
    document.addEventListener('pointerdown',away);
    document.addEventListener('keydown',esc);
    return()=>{document.removeEventListener('pointerdown',away);document.removeEventListener('keydown',esc)};
  },[open]);
  return <div className="rd-menu" ref={ref}>
    <button type="button" className={'rd-menu-trigger'+(iconOnly?' is-icon':'')} aria-label={label} aria-haspopup="menu" aria-expanded={open} onClick={()=>setOpen(v=>!v)}>{trigger}</button>
    {open&&<div className={'rd-menu-list align-'+align} role="menu">
      {items.filter(Boolean).map((item,i)=>item.divider?<hr key={i}/>
        :item.node?<div key={i} className="rd-menu-info">{item.node}</div>
        :item.href?<a key={i} role="menuitem" href={item.href} className={item.danger?'is-danger':''} onClick={()=>setOpen(false)}>{item.icon}{item.label}</a>
        :<button key={i} type="button" role="menuitem" className={item.danger?'is-danger':''} disabled={item.disabled} onClick={e=>{setOpen(false);item.onClick?.(e)}}>{item.icon}{item.label}</button>)}
    </div>}
  </div>;
}

// Sequencia de 3 partes para o Extend Video do Grok (gancho, prova,
// fechamento) e o passo a passo do CapCut. So leitura: busca quando o usuario
// abre e nao grava nada na campanha. Quem usa passa key com as falas, para o
// painel recomecar quando o roteiro muda.
export function StorySequence({campaignId,variantId=null,onError}){
  const [open,setOpen]=useState(false);
  const [seq,setSeq]=useState(null);
  const [loading,setLoading]=useState(false);
  async function toggle(){
    if(seq){setOpen(v=>!v);return}
    setLoading(true);
    try{setSeq(await storySequence(campaignId,variantId));setOpen(true)}
    catch(e){onError?.(e.message)}
    finally{setLoading(false)}
  }
  return <section className="story-sequence">
    <button type="button" onClick={toggle} disabled={loading} aria-expanded={open}>
      <span className="rd-story-eyebrow">MESMAS FALAS · EXTEND VIDEO</span>
      <strong>{loading?'Montando as partes…':open?'Fechar mesmas falas em 3 partes':'Mesmas falas em 3 partes (Extend)'}</strong>
      <small>Divide o roteiro de 15 s em gancho, prova e fechamento para emendar com o Extend Video, e o passo a passo do CapCut. Não cria falas novas: para isso, use “Sequência em 2 ou 3 clipes”.</small>
    </button>
    {open&&seq&&<div className="story-sequence-body">
      <div className="section-title"><strong>3 partes · cerca de {seq.total_seconds}s</strong><CopyButton text={seq.text} onError={onError} label="Copiar tudo"/></div>
      {seq.clips.map(clip=><div key={clip.index} className="variant-prompt story-clip">
        <div className="section-title"><strong>Parte {clip.index} · {clip.role} <small>{clip.kind==='image'?'imagem → vídeo':'Extend Video'} · ~{clip.seconds}s</small></strong><CopyButton text={clip.prompt} onError={onError}/></div>
        <small className="help">{clip.why}</small>
        <p>{clip.prompt}</p>
        {clip.screen_text&&<p className="story-screen-text"><strong>Texto na tela (CapCut):</strong> {clip.screen_text}</p>}
      </div>)}
      <h4>Como gerar no Grok</h4>
      <ul>{seq.tips.map(tip=><li key={tip}>{tip}</li>)}</ul>
      <h4>Montagem no CapCut</h4>
      <ol>{seq.capcut.map(step=><li key={step}>{step}</li>)}</ol>
    </div>}
  </section>;
}

// Formato "Recebi em casa" (services/home_reveal.py): Cena 1 abrindo a caixa de pijama, terminando com a mao na
// lente; Cena 2 ja no corpo, comecando com a mao saindo da lente. So leitura, como a StorySequence.
export function HomeReveal({campaignId,variantId=null,onError}){
  const [open,setOpen]=useState(false);
  const [seq,setSeq]=useState(null);
  const [loading,setLoading]=useState(false);
  async function toggle(){
    if(seq){setOpen(v=>!v);return}
    setLoading(true);
    try{setSeq(await homeReveal(campaignId,variantId));setOpen(true)}
    catch(e){onError?.(e.message)}
    finally{setLoading(false)}
  }
  return <section className="story-sequence">
    <button type="button" onClick={toggle} disabled={loading} aria-expanded={open}>
      <span className="rd-story-eyebrow">2 CENAS · TRANSIÇÃO COM A MÃO</span>
      <strong>{loading?'Montando as cenas…':open?'Fechar Recebi em casa':'Recebi em casa → no corpo'}</strong>
      <small>Cena 1: ela abre a caixa de pijama, vibra e tampa a lente. Cena 2: a mão sai da lente e ela já está com a peça, usando as falas do roteiro.</small>
    </button>
    {open&&seq&&<div className="story-sequence-body">
      <div className="section-title"><strong>2 cenas · cerca de {seq.total_seconds}s</strong><CopyButton text={seq.text} onError={onError} label="Copiar tudo"/></div>
      {seq.clips.map(clip=><div key={clip.index} className="variant-prompt story-clip">
        <div className="section-title"><strong>Passo {clip.index} · {clip.role} <small>{clip.kind==='image'?'imagem':`vídeo · ${clip.seconds}s`}</small></strong><CopyButton text={clip.prompt} onError={onError}/></div>
        <small className="help">{clip.why} Anexe: {clip.attach}.</small>
        <p>{clip.prompt}</p>
      </div>)}
      <h4>Como gerar no Grok</h4>
      <ul>{seq.tips.map(tip=><li key={tip}>{tip}</li>)}</ul>
      <h4>Montagem no CapCut</h4>
      <ol>{seq.capcut.map(step=><li key={step}>{step}</li>)}</ol>
    </div>}
  </section>;
}

// Sequencia STORYTELLING de 2 ou 3 clipes (services/story_arcs.py): arcos Motivos e Questionada, com falas novas em
// cada clipe. As falas chegam como RASCUNHO editavel; "Atualizar prompts" manda as editadas de volta. So leitura:
// nao grava nada na campanha. Todos os clipes partem da MESMA imagem aprovada (e como foi validado no Grok).
const ARC_OPTIONS=[
  ['motivos','Motivos','“Três motivos pra essa peça estar no seu guarda-roupa”'],
  ['questionada','Questionada','“Sabe o que dizem por aí? Que ela não te valoriza”, e a resposta'],
];
const ARC_CLIPS=[[2,'2 clipes','cerca de 30 s'],[3,'3 clipes','cerca de 45 s']];
// Espelho (validado no Grok) e os formatos com a modelo de frente falando (services/story_arcs.py). POV e so
// movimento nao tem fala de frente; Na mesa nao e roupa.
const ARC_FORMATS=FORMAT_RULES.arc_formats;
const wordCount=text=>(text||'').trim().split(/\s+/).filter(Boolean).length;
// Tipo de video escolhido na CRIACAO: a sequencia envolve prompts novos e 3 fatos da peca, entao a escolha
// fica no inicio (pedido real: o painel no fim da etapa de video passava despercebido).
export const SEQUENCE_FORMATS=ARC_FORMATS;
const SEQUENCE_TYPES=[['','Clipe único','Um vídeo de 15 s'],['2','Sequência de 2 clipes','Cerca de 30 s, falas novas em cada clipe'],
  ['3','Sequência de 3 clipes','Cerca de 45 s, falas novas em cada clipe']];
export const factCount=text=>String(text||'').split(/[,;\n]+/).map(s=>s.trim()).filter(s=>s&&s.split(/\s+/).length<=5).length;
export function SequenceChoice({clips,arc,format,onClips,onArc,idPrefix='seq'}){
  const foraDoFormato=clips&&!SEQUENCE_FORMATS.includes(format||'');
  return <div className="option-field sequence-choice">
    <span className="option-field-title" id={`${idPrefix}-type`}>Tipo de vídeo</span>
    <div className="generator-options" role="radiogroup" aria-labelledby={`${idPrefix}-type`}>
      {SEQUENCE_TYPES.map(([id,label,hint])=><label key={id||'unico'} className={'generator-option '+((clips||'')===id?'selected':'')}>
        <input type="radio" name={`${idPrefix}-type`} value={id} checked={(clips||'')===id} onChange={()=>onClips(id)}/>
        <span><strong>{label}</strong><small>{hint}</small></span>
      </label>)}
    </div>
    {clips&&<>
      <span className="option-field-title" id={`${idPrefix}-arc`}>Arco da sequência</span>
      <div className="generator-options" role="radiogroup" aria-labelledby={`${idPrefix}-arc`}>
        {ARC_OPTIONS.map(([id,label,hint])=><label key={id} className={'generator-option '+((arc||'motivos')===id?'selected':'')}>
          <input type="radio" name={`${idPrefix}-arc`} value={id} checked={(arc||'motivos')===id} onChange={()=>onArc(id)}/>
          <span><strong>{label}</strong><small>{hint}</small></span>
        </label>)}
      </div>
      <small className="help">Todos os clipes partem da mesma imagem aprovada: a etapa de imagem não muda. Os prompts de cada clipe ficam prontos na etapa de vídeo.</small>
      {foraDoFormato&&<small className="help story-arc-problem">⚠ A sequência funciona em Celular no espelho e nos formatos com a modelo de frente falando (Com fala, Teste de prova, Respondendo comentário, Troca de cor, 3 jeitos). Troque o formato do vídeo.</small>}
    </>}
  </div>;
}

export function StoryArcs({campaignId,variantId=null,initialArc='',initialClips=0,autoBuild=false}){
  // Escolhida na criacao da campanha: ja abre com o arco e os clipes marcados e monta sozinha.
  const [open,setOpen]=useState(autoBuild);
  const [arc,setArc]=useState(initialArc||'motivos');
  const [clips,setClips]=useState(Number(initialClips)||3);
  const [data,setData]=useState(null);
  const [drafts,setDrafts]=useState([]);
  const [loading,setLoading]=useState(false);
  const [message,setMessage]=useState('');
  const [facts,setFacts]=useState('');
  // ai=true so pelo botao proprio: gasta tokens. A montagem automatica ao abrir a etapa reaproveita as falas que
  // a IA ja escreveu (guardadas no servidor) e nunca chama a IA sozinha.
  async function build(lines,ai=false){
    setLoading(ai?'ai':true);setMessage('');
    try{
      const res=await storyArc(campaignId,{arc,clips,variant:variantId||undefined,lines,facts:facts.trim()||undefined,ai:ai||undefined});
      setData(res);setDrafts(res.clips.map(clip=>clip.lines.join('\n')));
    }catch(e){if(!ai)setData(null);setMessage(e.message)}
    finally{setLoading(false)}
  }
  const choose=(setter,value)=>{setter(value);setData(null);setMessage('')};
  useEffect(()=>{if(autoBuild)build()},[]);
  return <section className="story-sequence story-arcs">
    <button type="button" onClick={()=>setOpen(v=>!v)} aria-expanded={open}>
      <span className="rd-story-eyebrow">STORYTELLING EM VÁRIOS CLIPES</span>
      <strong>{open?'Fechar sequência em 2 ou 3 clipes':'Sequência em 2 ou 3 clipes'}</strong>
      <small>Falas novas em cada clipe (motivos ou pergunta e resposta), os prompts e a montagem no CapCut.</small>
    </button>
    {open&&<div className="story-sequence-body">
      <div className="option-field">
        <span className="option-field-title" id="story-arc-title">Arco</span>
        <div className="generator-options" role="radiogroup" aria-labelledby="story-arc-title">
          {ARC_OPTIONS.map(([id,label,hint])=><label key={id} className={'generator-option '+(arc===id?'selected':'')}>
            <input type="radio" name="story-arc" value={id} checked={arc===id} onChange={()=>choose(setArc,id)}/>
            <span><strong>{label}</strong><small>{hint}</small></span>
          </label>)}
        </div>
      </div>
      <div className="option-field">
        <span className="option-field-title" id="story-clips-title">Quantos clipes</span>
        <div className="generator-options" role="radiogroup" aria-labelledby="story-clips-title">
          {ARC_CLIPS.map(([id,label,hint])=><label key={id} className={'generator-option '+(clips===id?'selected':'')}>
            <input type="radio" name="story-clips" value={id} checked={clips===id} onChange={()=>choose(setClips,id)}/>
            <span><strong>{label}</strong><small>{hint}</small></span>
          </label>)}
        </div>
      </div>
      {message&&<p className="help story-arc-message" role="alert">{pointToFacts(message,'abaixo')}</p>}
      {(isFewFacts(message)||facts)&&<label className="sequence-facts">Fatos da peça só para esta sequência<input autoComplete="off" value={facts} onChange={e=>setFacts(e.target.value)} placeholder="Ex.: capuz, zíper frontal, bolsos laterais" maxLength={500}/><small className="help">Não muda o briefing: a imagem aprovada e os prompts continuam. Escreva fatos verdadeiros, separados por vírgula, e monte de novo.</small></label>}
      <div className="story-arc-actions">
        <button type="button" className="primary" disabled={!!loading} onClick={()=>build()}>{loading===true?'Montando…':data?'Montar de novo':'Montar sequência'}</button>
        <button type="button" disabled={!!loading} onClick={()=>build(undefined,true)}><Sparkles size={16}/> {loading==='ai'?'A IA está escrevendo…':'Escrever as falas com IA'}</button>
      </div>
      <small className="help">A IA escreve falas novas para cada clipe com os mesmos fatos e passa pela mesma conferência do rascunho. Gasta tokens da OpenAI (entra no teto de gasto) e fica guardada: reabrir a etapa não gasta de novo.</small>
      {data?.ai_error&&<p className="help story-arc-message" role="alert">A IA tentou e foi recusada: {data.ai_error}. Ficou o rascunho por regras.</p>}
      {data?.written_by&&<p className="writer-badge is-ai"><strong>{data.written_by==='ai'?'Falas escritas pela IA agora':'Falas escritas pela IA (guardadas)'}</strong></p>}
      {data&&<>
        <div className="section-title"><strong>{data.label} · {data.clips_count} clipes · cerca de {data.total_seconds}s</strong><CopyButton text={data.text} label="Copiar tudo"/></div>
        <small className="help">Motivos usados: {data.facts.join(' · ')}</small>
        {data.notes.map(note=><small key={note} className="help">{note}</small>)}
        {data.clips.map((clip,index)=>{
          const draft=drafts[index]??clip.lines.join('\n');
          const words=wordCount(draft);
          return <div key={clip.index} className="variant-prompt story-clip">
            <div className="section-title"><strong>Clipe {clip.index} · {clip.role} <small>{clip.start} · ~{clip.seconds}s</small></strong></div>
            <label className="story-arc-lines">
              <span className="help">Falas (uma linha por trecho: 0–4 s, 4–12 s e 12–15 s) · {words} palavras</span>
              <textarea autoComplete="off" rows={5} value={draft} onChange={e=>setDrafts(list=>list.map((text,i)=>i===index?e.target.value:text))}/>
            </label>
            {clip.problems.map(problem=><small key={problem} className="help story-arc-problem">⚠ {problem}</small>)}
            <div className="story-arc-copy">
              <CopyButton text={clip.prompt} label="Copiar prompt completo"/>
              <CopyButton text={clip.guide} label="Copiar Guia do Grok"/>
              {clip.extend&&<CopyButton text={clip.extend} label="Copiar Extend Video"/>}
            </div>
            <p className="story-screen-text"><strong>Texto na tela (CapCut):</strong> {clip.screen_text}</p>
          </div>;
        })}
        <button type="button" disabled={loading} onClick={()=>build(drafts)}>Atualizar prompts com as falas editadas</button>
        <h4>Como gerar no Grok</h4>
        <ul>{data.tips.map(tip=><li key={tip}>{tip}</li>)}</ul>
        <h4>Montagem no CapCut</h4>
        <ol>{data.capcut.map(step=><li key={step}>{step}</li>)}</ol>
      </>}
    </div>}
  </section>;
}

// Formatos de video (services/formats.py): os quatro de base e os que rodam
// sobre eles. Abrindo o pacote usa a base POV; Close ASMR, a de so movimento.
export const FORMAT_OPTIONS=[
  ['','Com fala','Modelo de frente falando com a câmera'],
  ['espelho','Celular no espelho','Ela grava o próprio look no espelho'],
  ['movimento','Só movimento','Sem fala: puxa, gira e ajusta a peça'],
  ['comentario','Respondendo comentário','Responde a dúvida da cliente e prova na hora'],
  ['teste','Teste de prova','Agacha, pula ou gira para provar a peça'],
  ['troca_cor','Troca de cor','Termina com a mão na lente para emendar as cores'],
  ['tres_jeitos','3 jeitos de usar','A mesma peça em três looks (experimental)'],
  ['unboxing','Abrindo o pacote','POV tirando a peça da caixa (experimental)'],
  ['asmr','Close ASMR','Sem fala: closes e o som do tecido'],
  ['mesa','Na mesa, de perto','Sentada à mesa, mostra o produto e traz perto da lente (experimental)'],
  // Ultimo da lista de proposito: nos testes reais o Grok errou as maos (terceira mao) e o giro da peca em POV.
  ['pov','POV (último caso)','Só mãos e produto, sem rosto. Nos testes o Grok errou mãos e giro da peça'],
];
const VIDEO_FORMATS=FORMAT_OPTIONS.map(([id,label])=>[id,label]);
const CAMERA_OPTIONS=[['closes','Closes no produto'],['ousado','Movimentos ousados']];
const TECHNIQUE_OPTIONS=[['acao','Começar em movimento'],['aproxima','Aproximação rápida'],['revela','Mão revelando'],['loop','Loop'],['estica','Esticar o tecido']];
const STYLE_ORDER=['closes','ousado','acao','aproxima','revela','loop','estica'];
const MAX_TECHNIQUES=FORMAT_RULES.max_techniques;
// Camera e tecnicas de retencao. Mais de duas tecnicas no mesmo video de 15 s
// viram lista de tarefas para o Grok: a terceira fica bloqueada.
export function StyleChips({value,onChange,labelledBy}){
  const set=new Set(String(value||'').split(',').filter(Boolean));
  const tecnicas=TECHNIQUE_OPTIONS.filter(([id])=>set.has(id)).length;
  const toggle=id=>{const next=new Set(set);next.has(id)?next.delete(id):next.add(id);onChange(STYLE_ORDER.filter(k=>next.has(k)).join(','))};
  const chip=([id,label],limit)=>{const on=set.has(id);const blocked=limit&&!on&&tecnicas>=MAX_TECHNIQUES;
    return <button type="button" key={id} className="rd-chip-tab" aria-pressed={on} aria-checked={on} role="checkbox" disabled={blocked}
      title={blocked?`Escolha no máximo ${MAX_TECHNIQUES} técnicas`:undefined} onClick={()=>toggle(id)}>{label}</button>};
  return <>
    <div className="quick-niches" role="group" aria-labelledby={labelledBy}>{CAMERA_OPTIONS.map(o=>chip(o,false))}</div>
    <div className="quick-niches" role="group" aria-label="Técnicas de retenção (até 2)">{TECHNIQUE_OPTIONS.map(o=>chip(o,true))}</div>
  </>;
}

// Bancada da etapa Criar video: imagem aprovada ao lado, prompt no topo com a
// acao principal (copiar e abrir o gerador), falas como linha do tempo, o
// passo a passo e, por ultimo, o envio do MP4. No celular a acao principal
// fica presa no rodape, na altura do polegar.
export function VideoWorkbench({campaign,prompts,color,variantId=null,image,video,deviceVideo,deviceFile,busy,disabled,immutable,onError,onUpload,onDeviceVideo,onRefreshVideoPrompt,onImproveVideoPrompt,onChangeVideoMode,onOpenGenerator,videoPromptLimit}){
  const p=prompts||{};
  const [copied,setCopied]=useState(false);
  const dropRef=useRef(null);
  const mode=campaign?.video_mode||'';
  const guia=String(p.video||'').startsWith('Vídeo vertical');
  const gen=campaign?.generator==='flow'?'Flow':'Grok';
  const length=p.video?.length||0;
  const over=!!videoPromptLimit&&length>videoPromptLimit;
  const hasVideo=!!(video||deviceVideo);
  const name=color||'este vídeo';
  const launch=className=><ServiceLaunch service={campaign?.generator||'grok'} className={className} disabled={busy||!p.video}
    onClick={event=>{copyText(p.video||'');setCopied(true);onOpenGenerator?.(event)}}>
    <Copy size={18} aria-hidden="true"/> Copiar prompt e abrir o {gen}
  </ServiceLaunch>;
  const pickFormat=value=>{if(value!==mode&&!immutable)onChangeVideoMode?.(value,guia)};
  return <div className="rd-workbench">
    <aside className="rd-wb-media" aria-label="Imagem aprovada">
      {image?<AssetView asset={image} title={`Imagem aprovada · ${name}`} compact/>:<div className="notice">Falta a imagem aprovada de {name}.</div>}
    </aside>
    <div className="rd-wb-main">
      {campaign?.id&&campaign.sequence_clips&&ARC_FORMATS.includes(campaign.video_mode||'')&&<div className="rd-story rd-story-top">
        <StoryArcs key={`arcs-top-${variantId||'base'}`} campaignId={campaign.id} variantId={variantId}
          initialArc={campaign.sequence_arc} initialClips={campaign.sequence_clips} autoBuild/></div>}
      <section className="rd-card" aria-label="Prompt de vídeo">
        <div className="rd-card-head"><h3>Prompt de vídeo{color?` · ${color}`:''}</h3><PromptScore text={p.video} maxChars={videoPromptLimit}/></div>
        <div className="rd-segments">
          <div><span className="rd-segmented-label">Formato</span>
            <select className="rd-format-select" aria-label="Formato do vídeo" value={mode} disabled={busy||immutable} onChange={e=>pickFormat(e.target.value)}>
              {VIDEO_FORMATS.map(([value,label])=><option key={value||'fala'} value={value}>{label}</option>)}
            </select>
          </div>
          <div><span className="rd-segmented-label">Versão do prompt</span>
            <div className="rd-segmented" role="radiogroup" aria-label="Versão do prompt">
              <button type="button" role="radio" aria-checked={guia} disabled={busy||immutable||!onImproveVideoPrompt} onClick={()=>{if(!guia)onImproveVideoPrompt?.(variantId)}}>Guia do Grok</button>
              <button type="button" role="radio" aria-checked={!guia} disabled={busy||immutable||!onRefreshVideoPrompt} onClick={()=>{if(guia)onRefreshVideoPrompt?.(variantId)}}>Completo</button>
            </div>
          </div>
        </div>
        {campaign?.edit_tip&&<p className="help rd-format-tip"><strong>Na edição:</strong> {campaign.edit_tip}</p>}
        <pre className="rd-prompt-box">{p.video||'Gere os prompts em Definir look.'}</pre>
        <div className="rd-prompt-actions">
          {launch('rd-cta')}
          <CopyButton text={p.video||''} onError={onError} label="Só copiar"/>
          <SaveToLibrary kind="video" prompt={p.video} product={campaign?.product} onError={onError}
            format={(FORMAT_OPTIONS.find(([id])=>id===mode)||[,'Com fala'])[1]} version={guia?'Guia do Grok':'Completo'}
            note={campaign?.id?`Guardado da campanha #${campaign.id}${color?` · cor ${color}`:''}.`:''}/>
          {!immutable&&onRefreshVideoPrompt&&<button type="button" className="button" disabled={busy} onClick={()=>(guia?onImproveVideoPrompt:onRefreshVideoPrompt)?.(variantId)}><RefreshCw size={15}/> Recriar</button>}
          <span className={'rd-prompt-count'+(over?' is-over':'')}>{length.toLocaleString('pt-BR')}{videoPromptLimit?` / ${videoPromptLimit.toLocaleString('pt-BR')}`:''} caracteres</span>
        </div>
      </section>

      <section className="rd-card" aria-label="Falas">
        <div className="rd-card-head"><h3>Falas em 15 segundos</h3></div>
        {mode==='movimento'&&<p className="help">Formato sem fala: o vídeo não usa estas frases. Elas seguem valendo para a legenda e o texto na tela.</p>}
        <div className="rd-timeline">
          <div><i/><span>0–4s · Gancho</span><p>{p.hook||'—'}</p></div>
          <div><i/><span>4–12s · Prova</span><p>{p.development||'—'}</p></div>
          <div><i/><span>12–15s · Chamada</span><p>{p.cta||'—'}</p></div>
        </div>
      </section>

      <div className="rd-wb-grid">
        <section className="rd-card" aria-label="Como gerar">
          <div className="rd-card-head"><h3>Como gerar</h3></div>
          <ol className="rd-steps">
            <li className={copied?'is-done':'is-next'}><b>{copied?'✓':'1'}</b>Copiar o prompt</li>
            <li className={hasVideo?'is-done':copied?'is-next':''}><b>{hasVideo?'✓':'2'}</b>No {gen}, anexar a imagem aprovada e colar o prompt</li>
            <li className={hasVideo?'is-done':''}><b>{hasVideo?'✓':'3'}</b>Gerar 2 ou 3 vezes e trazer o melhor MP4</li>
          </ol>
        </section>
        {campaign?.id&&p.hook&&p.development&&p.cta&&<div className="rd-story"><StorySequence key={[p.hook,p.development,p.cta].join('|')} campaignId={campaign.id} variantId={variantId} onError={onError}/>
          {campaign.video_mode!=='mesa'&&<HomeReveal key={['casa',variantId||'base',p.hook,p.development,p.cta].join('|')} campaignId={campaign.id} variantId={variantId} onError={onError}/>}
          {ARC_FORMATS.includes(campaign.video_mode||'')&&!campaign.sequence_clips&&<StoryArcs key={`arcs-${variantId||'base'}`} campaignId={campaign.id} variantId={variantId}/>}</div>}
      </div>

      <section className="rd-drop" ref={dropRef} aria-label={`Vídeo de ${name}`}>
        <div className="rd-drop-head"><strong>{hasVideo?`Vídeo de ${name}`:`Traga o vídeo de ${name}`}</strong><span>MP4 vertical 9:16, cerca de 15 s. No celular, “usar da galeria” valida sem enviar o arquivo.</span></div>
        {video&&<AssetView asset={video} title={`Vídeo · ${name}`} compact/>}
        {deviceVideo&&<DeviceVideoCard record={deviceVideo} localFile={deviceFile}/>}
        {onUpload&&!immutable&&<Uploader kind="video" color={color||undefined} exists={!!video} busy={busy} disabled={disabled} onUpload={onUpload}/>}
        {onDeviceVideo&&!immutable&&<DeviceVideoPicker color={color||undefined} record={deviceVideo} busy={busy} disabled={disabled} onSelect={onDeviceVideo}/>}
      </section>

      {!immutable&&<div className="rd-actionbar">
        <button type="button" className="rd-upload-jump" aria-label="Ir para o envio do vídeo" onClick={()=>dropRef.current?.scrollIntoView({behavior:'smooth',block:'center'})}><Upload size={20}/></button>
        {launch('rd-cta')}
      </div>}
    </div>
  </div>;
}

// Cor aberta por etapa. O painel remonta a cada gravacao (ex.: "Recriar
// prompt"), e sem isto voltava a abrir a primeira cor em vez da que o
// usuario estava mexendo.
const openVariantByFocus={};
export function VariantList({variants=[],onError,focus,images=[],videos=[],deviceVideos=[],deviceFiles={},onUpload,onDeviceVideo,busy,disabled,onSaveVariant,onRefreshVariant,onRefreshAllVariants,onRefreshVideoPrompt,onImproveVideoPrompt,onConfigureWriter,videoPromptLimit,immutable,campaign,onChangeVideoMode,onOpenGenerator,onSaveToBank,onOpenBank}){
  const [writer,setWriter]=useState(null);
  useEffect(()=>{
    if(focus!=='script') return;
    writerSettings().then(setWriter).catch(()=>setWriter({enabled:false,provider:''}));
  },[focus]);
  // Abas de cor: abre na primeira cor pendente desta etapa (ou na que estava
  // aberta antes de o painel remontar).
  const [openColor,setOpenColorState]=useState(()=>{
    if(!variants.length) return null;
    const remembered=openVariantByFocus[(focus||'')+'|'+variants.map(v=>v.id).join(',')];
    if(remembered&&variants.some(v=>v.color===remembered)) return remembered;
    const byImg=Object.fromEntries((images||[]).filter(a=>a.kind==='image').map(a=>[a.slot||a.metadata?.color||'',a]));
    const byVid=Object.fromEntries((videos||[]).filter(a=>a.kind==='video').map(a=>[a.slot||a.metadata?.color||'',a]));
    const byDev=Object.fromEntries((deviceVideos||[]).map(a=>[a.slot||'',a]));
    if(focus==='image') return (variants.find(v=>!byImg[v.color])||variants[0]).color;
    if(focus==='video') return (variants.find(v=>!byVid[v.color]&&!byDev[v.color])||variants[0]).color;
    return variants[0].color;
  });
  const setOpenColor=color=>{openVariantByFocus[(focus||'')+'|'+variants.map(v=>v.id).join(',')]=color;setOpenColorState(color)};
  if(!variants.length)return null;
  const byImage=Object.fromEntries((images||[]).filter(a=>a.kind==='image').map(a=>[a.slot||a.metadata?.color||'',a]));
  const byVideo=Object.fromEntries((videos||[]).filter(a=>a.kind==='video').map(a=>[a.slot||a.metadata?.color||'',a]));
  const byDeviceVideo=Object.fromEntries((deviceVideos||[]).map(a=>[a.slot||'',a]));
  const title=focus==='image'?'Imagens por cor':focus==='script'?'Roteiros 15s por cor':'Prompts por cor';
  const help=focus==='image'
    ?'Gere e anexe uma imagem por cor. Todas ficam disponíveis para aprovação.'
    :focus==='script'
      ?'Cada cor tem falas (hook, desenvolvimento, CTA). A legenda do TikTok fica na etapa Studio.'
      :'Escolha a cor para copiar os prompts e o roteiro correspondentes.';
  const variant=variants.find(v=>v.color===openColor)||variants[0];
  const tabState=v=>{
    const img=byImage[v.color],vid=byVideo[v.color]||byDeviceVideo[v.color];
    if(focus==='image')return img?[img.approved_at?'aprovada':'anexada',true]:['falta imagem',false];
    if(focus==='video')return vid?[vid.approved_at?'aprovado':'vídeo pronto',true]:['falta vídeo',false];
    return ['',true];
  };
  const p=variant.prompts||{};
  const img=byImage[variant.color];
  const vid=byVideo[variant.color];
  const deviceVid=byDeviceVideo[variant.color];
  return <section className={'variant-list rd-variants is-'+(focus||'all')}>
    {focus!=='video'&&<><div className="section-title"><h3>{title}</h3><span className="help">{variants.length} {variants.length===1?'cor':'cores'}</span></div><p>{help}</p></>}
    <div className="rd-color-tabs" role="tablist" aria-label="Cores">
      {variants.map(v=>{const [label,ok]=tabState(v);return <button key={v.id||v.color} type="button" role="tab" className="rd-color-tab" aria-selected={v.color===variant.color} onClick={()=>setOpenColor(v.color)}>
        <span className="rd-swatch" style={{background:swatchFor(v.color)}} aria-hidden="true"/>{v.color}{label&&<small className={ok?'is-ok':''}>{label}</small>}
      </button>})}
    </div>
    <div className="variant-content" role="tabpanel" aria-label={variant.color}>
      {focus==='image'&&<>
        <div className="variant-prompt"><div className="section-title"><strong>Prompt de imagem — use só esta cor</strong><CopyButton text={p.image||''} onError={onError}/></div><p>{p.image||'-'}</p></div>
        {img?<AssetView asset={img} title={`Resultado · ${variant.color}`} compact/>:null}
        {onUpload&&!immutable&&<Uploader kind="image" color={variant.color} exists={!!img} busy={busy} disabled={disabled} onUpload={onUpload}/>}
      </>}
      {focus==='video'&&<VideoWorkbench campaign={campaign} prompts={p} color={variant.color} variantId={variant.id} image={img} video={vid} deviceVideo={deviceVid} deviceFile={deviceFiles[variant.color]}
        busy={busy} disabled={disabled} immutable={immutable} onError={onError} onUpload={onUpload} onDeviceVideo={onDeviceVideo}
        onRefreshVideoPrompt={onRefreshVideoPrompt} onImproveVideoPrompt={onImproveVideoPrompt} onChangeVideoMode={onChangeVideoMode} onOpenGenerator={onOpenGenerator} videoPromptLimit={videoPromptLimit}/>}
      {focus==='script'&&<>
        {!immutable&&<section className={'script-ai-action '+(writer?.enabled?'is-ready':'is-off')}>
          <div><span className="eyebrow">ESCRITA POR API · {variant.color}</span><strong>{writer?.enabled?(writer.provider==='gemini'?'Gemini está configurado':'ChatGPT está configurado'):'ChatGPT ainda não está ativo'}</strong><small>{writer?.enabled?`Escolha entre gerar somente ${variant.color} ou os roteiros das ${variants.length} cores em uma solicitação.`:'Configure a chave para chamar a API nesta etapa.'}</small></div>
          {writer?.enabled
            ?<div className="script-ai-buttons">
              <button type="button" disabled={busy} onClick={()=>onRefreshVariant?.(variant.id,['hook','development','cta'],{writerMode:'ai'})}><Sparkles size={16}/><span className="button-label-desktop">Gerar esta cor</span><span className="button-label-mobile">Esta cor</span></button>
              {variants.length>1&&<button type="button" className="primary" disabled={busy} onClick={()=>onRefreshAllVariants?.(['hook','development','cta'],{writerMode:'ai'})}><Sparkles size={16}/><span className="button-label-desktop">Gerar todas as {variants.length} cores</span><span className="button-label-mobile">Todas ({variants.length})</span></button>}
            </div>
            :<button type="button" className="primary" disabled={busy} onClick={onConfigureWriter}><Sparkles size={16}/> Configurar ChatGPT</button>}
        </section>}
        <div className="variant-actions">
          <span className="help">Alternativas locais, sem usar API:</span>
          {onRefreshVariant&&!immutable&&<>
            <button type="button" disabled={busy} onClick={()=>onRefreshVariant(variant.id,['hook'],{writerMode:'local'})}>Criar outro hook</button>
            <button type="button" disabled={busy} onClick={()=>onRefreshVariant(variant.id,['hook','development','cta'],{writerMode:'local'})}>Criar outra fala inteira</button>
          </>}
        </div>
        {(onSaveToBank||onOpenBank)&&<div className="variant-actions speech-bank-actions">
          <span className="help">Banco de falas:</span>
          {onSaveToBank&&<button type="button" disabled={busy||!p.hook||!p.development||!p.cta} onClick={()=>onSaveToBank(variant.id,{hook:p.hook,development:p.development,cta:p.cta})}><BookmarkPlus size={16}/> Guardar no banco</button>}
          {onOpenBank&&!immutable&&<button type="button" disabled={busy} onClick={()=>onOpenBank(variant.id)}><BookOpen size={16}/> Ver falas aprovadas</button>}
        </div>}
        <p className="help">Legenda do TikTok fica na etapa <strong>Studio</strong> (publicação). Aqui só as falas do vídeo.</p>
        <div className="script-budget" aria-label="Palavras por trecho">{[['hook','abertura'],['development','meio'],['cta','fechamento']].map(([key,time])=>{const words=String(p[key]||'').trim().split(/\s+/).filter(Boolean).length;return <span key={key} className={'budget-chip is-'+(!words?'off':'ok')} title={`${time}: sem limite de palavras`}><em>{time}</em>{words}<small> palavras</small></span>})}</div>
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
  </section>;
}


function VariantScriptField({variant,field,value,busy,onSave}){
  const [draft,setDraft]=useState(value);
  useEffect(()=>setDraft(value),[value]);
  const dirty=draft!==value;
  return <div className="variant-script-field">
    <textarea autoComplete="off" rows={field==='video'?6:3} maxLength={12000} value={draft} disabled={busy} onChange={e=>setDraft(e.target.value)}/>
    {dirty&&<button type="button" className="full" disabled={busy||!draft.trim()} onClick={()=>onSave(variant.id,{[field]:draft})}>Salvar {field}</button>}
  </div>;
}



export function VideoMixer({c, busy, immutable, onError, onMix}){
  const [openMixer,setOpenMixer]=useState(false);
  const videos=(c.assets||[]).filter(a=>a.kind==='video');
  const colorSlots=c.colors||[];
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
            <input autoComplete="off" type="number" min="0.2" step="0.1" placeholder="seg" title="Segundos a partir do inicio" value={seconds[v.id]??''} disabled={busy||immutable||working} onChange={e=>setSeconds(s=>({...s,[v.id]:e.target.value}))}/>
            <button type="button" disabled={busy||immutable||working} onClick={()=>move(v.id,-1)} title="Subir">↑</button>
            <button type="button" disabled={busy||immutable||working} onClick={()=>move(v.id,1)} title="Descer">↓</button>
          </>}
        </div>;
      })}
    </div>
    <div className="mixer-controls">
      <label>Salvar no slot<select value={slot} disabled={busy||immutable||working} onChange={e=>setSlot(e.target.value)}>{slotOptions.map(s=><option key={s} value={s}>{s}</option>)}</select></label>
      <label>Duracao mix local (s)<input autoComplete="off" type="number" min="10" max="60" step="0.5" value={duration} disabled={busy||immutable||working} onChange={e=>setDuration(e.target.value)}/></label>
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
  // O clique em "Marcar como publicado" vale como confirmação; o backend ainda exige as 5 chaves.
  const PUBLISH_CHECKS={account:true,product:true,caption:true,review:true,published:true};
  return <section className="publish-queue publish-queue-compact">
    <div className="publish-topbar">
      <div className="publish-slot-tabs">
        {variants.map(v=>{
          const key=v.color||'default';
          const ok=!!slotMap[key]?.published;
          return <button type="button" key={key} className={'slot-tab'+(active===v.color?' active':'')+(ok?' done':'')} disabled={busy} onClick={()=>{setActive(v.color);setPublishedUrl(slotMap[key]?.url||'')}}>
            {ok?'✓ ':''}{v.color||'Produto'}
          </button>;
        })}
      </div>
      <TikTokLaunchButtons className="button publish-open-studio" disabled={busy} onOpenStudio={event=>onOpen('studio','publish',event)}/>
    </div>
    <p className="publish-hint">{isMobileDevice()?'Salve o vídeo no celular e copie a legenda. Abra o TikTok, confira a conta e publique; depois volte e marque como publicado.':'Uma cor por vez: copie legenda → suba o MP4 no Studio → marque como publicado.'}</p>

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
            <textarea autoComplete="off" className="caption-editor" aria-label="Legenda TikTok" rows={4} maxLength={12000} value={captionDraft} disabled={busy} onChange={e=>setCaptionDraft(e.target.value)}/>
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
        <label className="publish-link-field">Link do vídeo (opcional)<input autoComplete="off" type="url" value={publishedUrl} onChange={e=>setPublishedUrl(e.target.value)} placeholder="https://www.tiktok.com/@…/video/…"/></label>
        <button className="primary full" disabled={busy||immutable}
          onClick={()=>onPublishSlot({color:variant?.color,checklist:PUBLISH_CHECKS,published_url:publishedUrl})}>
          Marcar como publicado · {variant?.color}
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
    <div className="product-photo-grid">{active.map((photo,i)=><div className="product-photo" key={photo.id}><a href={photo.url} target="_blank" rel="noreferrer"><img src={photo.url} alt={`Foto salva do produto ${i+1}`} loading="lazy" decoding="async"/></a><small>{photo.original_name}</small><button type="button" onClick={()=>onRemoved([...removed,photo.id])} aria-label={`Remover ${photo.original_name}`}><X size={13}/>Remover</button></div>)}
      {files.map((file,i)=><div className="product-photo" key={i}>{previews[i]&&<img src={previews[i]} alt={`Nova foto do produto ${i+1}`}/>}<small>{file.name}</small><span className="pending-photo">A salvar</span><button type="button" onClick={()=>onFiles(files.filter((_,index)=>index!==i))} aria-label={`Retirar ${file.name}`}><X size={13}/>Retirar</button></div>)}</div>
    <input ref={input} type="file" multiple hidden accept="image/jpeg,image/png,image/webp" onChange={e=>{select(e.target.files);e.target.value=''}}/>
    <button type="button" className="upload-button" disabled={active.length+files.length>=8} onClick={()=>input.current.click()}><ImagePlus size={18}/>Adicionar fotos do produto</button>
    <small className="help">JPG, PNG ou WebP · até 40 MB por foto. As fotos serão enviadas ao clicar em Salvar briefing.</small>
    {!!removed.length&&<button type="button" className="undo-photos" onClick={()=>onRemoved([])}>Desfazer remoções ({removed.length})</button>}
    {error&&<p className="inline-error" role="alert">{error}</p>}
  </section>;
}
const MOTOR_LABELS={'':'Motor automático',necessidade:'Necessidade',escassez:'Escassez',desejo_posse:'Desejo de posse'};
const BODY_TURN_LABELS={'':'De frente',leve_lado:'Leve de lado',lado:'De lado',costas:'De costas'};
// Campos sem os quais o servidor nao gera prompts. Antes so nome, modelo e
// produto eram exigidos aqui, e a falta de cor ou publico so aparecia depois,
// como erro, ao clicar em Gerar.
const REQUIRED_BRIEF={name:'nome da campanha',product:'produto',color:'cores',model_name:'modelo',outfit:'roupa',audience:'público',benefit:'benefício'};
export function BriefForm({campaign,onSave,busy,onDirty,onCancel}){
  const [draft,setDraft]=useState({...emptyBrief,...campaign});
  const [briefError,setBriefError]=useState('');
  const [nicheOptions,setNicheOptions]=useState(NICHES);
  const [nicheError,setNicheError]=useState(false);
  const [modelOptions,setModelOptions]=useState([]);
  useEffect(()=>{let alive=true;listModelLibraryModels().then(data=>{if(alive)setModelOptions(data.models||[])}).catch(()=>{});return()=>{alive=false}},[]);
  useEffect(()=>{let alive=true;(async()=>{try{const mn=draft?.model_name||campaign?.model_name||'Micaela'; const data=await modelLibrary(mn); if(!alive)return; const rows=data.niches||[]; if(rows.length) setNicheOptions(rows.map(n=>({id:n.niche,label:n.label,url:n.has_photo?n.url:''})));}catch(_){}})(); return()=>{alive=false}; },[draft?.model_name, campaign?.model_name]);
  const [photos,setPhotos]=useState([]),[removed,setRemoved]=useState([]);
  const [descriptionPhoto,setDescriptionPhoto]=useState(null);
  const [showAdvanced,setShowAdvanced]=useState(false);
  const [moreOpen,setMoreOpen]=useState(()=>!!(campaign?.motor||campaign?.body_turns));
  const published=campaign?.status==='published';
  const essential=[['name','Nome da campanha','Ex.: Look de verão'],['product','O que é o produto?','Ex.: Calça legging de cintura alta'],['color','Cores / variações','Ex.: azul, branco, preto, rosa pink']];
  const advanced=[['model_name','Modelo','Nome da modelo fixa'],['outfit','Roupa','Ex.: Legging com top branco'],['audience','Público','Para quem é o produto?'],['benefit','Benefício','Um benefício que você pode demonstrar'],['angle','Ângulo','Ex.: Mostrar caimento e detalhes'],['tone','Tom','Ex.: Conversacional'],['style','Estilo visual','Ex.: Natural e realista']];
  const change=(key,value)=>{setDraft(d=>({...d,[key]:value}));onDirty?.(true)};
  // Trocar a modelo aqui troca tambem as fotos dos nichos logo abaixo, e o
  // nome automatico ("Modelo · Nicho") acompanha.
  function chooseModel(model){
    setDraft(d=>{
      const prev=String(d.name||'').trim();
      const old=String(d.model_name||'').trim().toLowerCase();
      const next={...d,model_name:model};
      if(!prev||(old&&prev.toLowerCase().startsWith(old+' · '))){
        const rest=prev.includes(' · ')?prev.slice(prev.indexOf(' · ')+3):'';
        next.name=rest?`${model} · ${rest}`:model;
      }
      return next;
    });
    onDirty?.(true);
  }
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
  // on first mount for create (no campaign salva ainda, ou seja sem id),
  // aplica os padroes do nicho atual uma vez. Antes a checagem era
  // "!campaign", mas o modal de criacao sempre passa um objeto
  // ({model_name:...}) mesmo antes de existir uma campanha - isso fazia
  // esse efeito nunca rodar, e como o <select> de nicho ja nasce com
  // "Moda casual" selecionado, o onChange (que so preenche ao trocar de
  // opcao) tambem nunca disparava: a campanha era criada com roupa/publico
  // vazios sem o usuario perceber, ate a etapa de gerar prompts falhar.
  useEffect(()=>{
    if(!campaign?.id && draft.niche && !(draft.audience||draft.benefit||draft.movements)){
      applyNiche(draft.niche);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  },[]);
  const field=(key,label,placeholder)=>(
    <div key={key} className={key==='product'?'product-field':''}>
      <label>{label}{REQUIRED_BRIEF[key]&&' *'}
        <input autoComplete="off" value={draft[key]||''} onChange={e=>change(key,e.target.value)} placeholder={placeholder} required={['name','model_name'].includes(key)} maxLength={500}/>
        {key==='color'&&<small className="help">Separe as cores por vírgulas para criar uma variação de cada uma.</small>}
      </label>
      {key==='product'&&(published?<ProductGallery photos={campaign?.product_assets||[]}/>:<ProductPhotoPicker saved={campaign?.product_assets||[]} files={photos} removed={removed} onFiles={value=>{setPhotos(value);onDirty?.(true)}} onRemoved={value=>{setRemoved(value);onDirty?.(true)}}/>)}
    </div>
  );
  return <form className="brief-form" onSubmit={e=>{e.preventDefault();if(!draft.niche){setNicheError(true);return}
    const missing=Object.entries(REQUIRED_BRIEF).filter(([key])=>!String(draft[key]||'').trim());
    if(missing.length){
      setBriefError('Preencha antes de salvar: '+missing.map(([,label])=>label).join(', ')+'.');
      if(missing.some(([key])=>advanced.some(([k])=>k===key)))setShowAdvanced(true);
      return;
    }
    setBriefError('');onSave(Object.fromEntries(Object.keys(emptyBrief).map(k=>[k,draft[k]||''])),photos,removed,descriptionPhoto);setDescriptionPhoto(null)}}>
    <fieldset disabled={busy||published}>
      {/* Antes era um <select>: a lista nativa do navegador não mostra
          imagem, e ficava difícil lembrar qual roupa cada moda usa. */}
      {(()=>{
        const current=(draft.model_name||'').trim();
        const names=[...modelOptions];
        if(current&&!names.some(n=>n.toLocaleLowerCase()===current.toLocaleLowerCase()))names.unshift(current);
        if(names.length<2)return null;
        return <div className="option-field model-pick-field">
          <span className="option-field-title" id="brief-model-title">Modelo</span>
          <div className="model-pick" role="radiogroup" aria-labelledby="brief-model-title">
            {names.map(n=>{
              const active=n.toLocaleLowerCase()===current.toLocaleLowerCase();
              return <button type="button" key={n} role="radio" aria-checked={active} className={'objection-chip'+(active?' selected':'')} onClick={()=>chooseModel(n)}>{n}</button>;
            })}
          </div>
        </div>;
      })()}
      <div className="niche-picker-field">
        <span className="field-label">Nicho da modelo *</span>
        <div className="niche-picker" role="radiogroup" aria-label="Nicho da modelo">
          {nicheOptions.map(n=>{
            const active=draft.niche===n.id;
            return <button type="button" key={n.id} role="radio" aria-checked={active} className={'niche-pick'+(active?' selected':'')} onClick={()=>applyNiche(n.id)}>
              {n.url?<img src={n.url} alt="" loading="lazy"/>:<span className="niche-pick-empty">Sem foto</span>}
              <span>{n.label}</span>
            </button>;
          })}
        </div>
        {nicheError&&!draft.niche&&<small className="field-error">Escolha o nicho da modelo.</small>}
        <small className="help">Ao escolher o nicho, público, benefício, ângulo, tom, estilo, detalhes e movimentos são preenchidos automaticamente. Você só ajusta produto, cores e nome.</small>
      </div>
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
        {/* Antes era um <datalist>: no computador a lista abre ao clicar, mas no
            celular (Safari do iPhone e boa parte dos Android) ela nao aparece,
            entao as opcoes "nao carregavam". Botoes funcionam em qualquer tela. */}
        <div className="objection-field">
          <label htmlFor="objection-input">O que mais segura a compra?</label>
          <div className="objection-chips" role="group" aria-label="Dúvidas mais comuns do cliente">
            {OBJECTIONS.map(o=>{
              const active=draft.objection===o;
              return <button type="button" key={o} className={'objection-chip'+(active?' selected':'')} aria-pressed={active} onClick={()=>change('objection',active?'':o)}>{o}</button>;
            })}
          </div>
          <input autoComplete="off" id="objection-input" value={draft.objection||''} onChange={e=>change('objection',e.target.value)} placeholder="Toque numa dúvida acima ou escreva a sua" maxLength={500}/>
          <small className="help">Com esse campo preenchido, o hook passa a falar da dor do cliente e o meio do roteiro mostra a prova que derruba a dúvida. Toque de novo na dúvida escolhida para limpar.</small>
        </div>
        <label>Oferta real (se existir)
          <input autoComplete="off" value={draft.offer||''} onChange={e=>change('offer',e.target.value)} placeholder="Ex.: 20% até domingo · últimas peças do P" maxLength={500}/>
          <small className="help">Só preencha se for verdade. É o único caso em que o roteiro usa urgência — prazo ou estoque inventado é propaganda enganosa e queima o perfil.</small>
        </label>
        <label>Prova social real (se existir)
          <input autoComplete="off" value={draft.social_proof||''} onChange={e=>change('social_proof',e.target.value)} placeholder="Ex.: mais de 2 mil vendidos · nota 4,8" maxLength={500}/>
          <small className="help">Copie da página do produto. Sem isso, o roteiro nunca fala em vendidos, nota ou avaliações.</small>
        </label>
        <PersuasionPreview offer={draft.offer||''} social={draft.social_proof||''}/>
        {/* O formato (UGC, POV, Só movimento) muda o vídeo inteiro: fica sempre
            à vista. Escondido em "Mais opções" parecia que tinha sumido. */}
        <div className="option-field">
          <span className="option-field-title" id="video-mode-title">Formato do vídeo</span>
          <div className="generator-options pov-options" role="radiogroup" aria-labelledby="video-mode-title">
            {FORMAT_OPTIONS.map(([id,label,hint])=><label key={id||'fala'} className={'generator-option '+((draft.video_mode||'')===id?'selected':'')}>
              <input type="radio" name="video_mode" value={id} checked={(draft.video_mode||'')===id} onChange={()=>change('video_mode',id)}/>
              <span><strong>{label}</strong><small>{hint}</small></span>
            </label>)}
          </div>
          {draft.video_mode==='pov'&&<small className="help">No modo POV a câmera vira ponto de vista em primeira pessoa: nunca mostra o rosto, só as mãos testando o produto na mesma referência aprovada. O hook, o desenvolvimento e o CTA continuam os mesmos — só a direção de câmera e a atuação mudam para um tom espontâneo, sem parecer anúncio.</small>}
          {draft.video_mode==='movimento'&&<small className="help">Em "Só movimento" ninguém fala: a modelo mostra e ajusta a peça no corpo seguindo a orientação escolhida abaixo. O quadro fica limpo, sem voz e sem texto na tela — o som é a trend que você escolhe ao publicar e a mensagem fica na legenda. O roteiro continua sendo gerado (ele alimenta a legenda e os outros formatos), mas não é falado neste vídeo.</small>}
        </div>
        <SequenceChoice clips={draft.sequence_clips} arc={draft.sequence_arc} format={draft.video_mode} idPrefix="brief-seq"
          onArc={id=>change('sequence_arc',id)}
          onClips={id=>{change('sequence_clips',id);if(id&&!draft.sequence_arc)change('sequence_arc','motivos');
            // O Detalhes nasce com a direcao de cena da moda: na sequencia ele vira os "motivos", entao comeca vazio.
            if(id&&String(draft.details||'').trim()===String((NICHE_DEFAULTS[draft.niche]||{}).details||'').trim())change('details','')}}/>
        {draft.sequence_clips&&<label className="sequence-facts">Fatos da peça (os motivos da sequência)
          <textarea autoComplete="off" rows={2} value={draft.details||''} onChange={e=>change('details',e.target.value)}
            placeholder="Ex.: capuz, zíper frontal, bolsos laterais" maxLength={5000}/>
          <small className="help">Pelo menos 3 fatos verdadeiros da peça, separados por vírgula ({factCount(draft.details)} escritos). É o mesmo campo Detalhes.</small>
        </label>}
        {/* Motor, formato e orientacao ocupavam boa parte do formulario, cada um
            com um paragrafo de ajuda. Ficam recolhidos, com a escolha atual no
            titulo; abrem sozinhos se ja tiver algo diferente do padrao. */}
        <details className="more-options" open={moreOpen} onToggle={e=>setMoreOpen(e.currentTarget.open)}>
        <summary><strong>Mais opções do vídeo</strong><small>{MOTOR_LABELS[draft.motor||'']} · {BODY_TURN_LABELS[draft.body_turns||'']}</small></summary>
        <div className="option-field">
          <span className="option-field-title" id="motor-title">Motor de persuasão</span>
          <div className="generator-options motor-options" role="radiogroup" aria-labelledby="motor-title">
            <label className={'generator-option '+((!draft.motor)?'selected':'')}>
              <input type="radio" name="motor" value="" checked={!draft.motor} onChange={()=>change('motor','')}/>
              <span><strong>Automático</strong><small>Escolhe pelo que você preencheu</small></span>
            </label>
            <label className={'generator-option '+(draft.motor==='necessidade'?'selected':'')}>
              <input type="radio" name="motor" value="necessidade" checked={draft.motor==='necessidade'} onChange={()=>change('motor','necessidade')}/>
              <span><strong>Necessidade</strong><small>"Isso é um problema meu"</small></span>
            </label>
            <label className={'generator-option '+(draft.motor==='escassez'?'selected':'')}>
              <input type="radio" name="motor" value="escassez" checked={draft.motor==='escassez'} onChange={()=>change('motor','escassez')}/>
              <span><strong>Escassez</strong><small>"Posso perder isso"</small></span>
            </label>
            <label className={'generator-option '+(draft.motor==='desejo_posse'?'selected':'')}>
              <input type="radio" name="motor" value="desejo_posse" checked={draft.motor==='desejo_posse'} onChange={()=>change('motor','desejo_posse')}/>
              <span><strong>Desejo de posse</strong><small>"Eu quero ter isso"</small></span>
            </label>
          </div>
          <small className="help">Necessidade: dor → agitação → prova. Desejo: encanto → "imagina…" → posse. Escassez: novidade → prova → prazo/estoque. O motor também muda a expressão da modelo no vídeo. Sem oferta real, "Escassez" usa só descoberta honesta — nunca prazo ou estoque inventado.</small>
        </div>
        <div className="option-field">
          <span className="option-field-title" id="body-turns-title">Orientação corporal no vídeo</span>
          <div className="generator-options turn-options" role="radiogroup" aria-labelledby="body-turns-title">
            <label className={'generator-option '+(!draft.body_turns?'selected':'')}>
              <input type="radio" name="body_turns" value="" checked={!draft.body_turns} onChange={()=>change('body_turns','')}/>
              <span><strong>De frente</strong><small>Sem virar o corpo</small></span>
            </label>
            <label className={'generator-option '+(draft.body_turns==='leve_lado'?'selected':'')}>
              <input type="radio" name="body_turns" value="leve_lado" checked={draft.body_turns==='leve_lado'} onChange={()=>change('body_turns','leve_lado')}/>
              <span><strong>Leve de lado</strong><small>Giro curto de até 30°</small></span>
            </label>
            <label className={'generator-option '+(draft.body_turns==='lado'?'selected':'')}>
              <input type="radio" name="body_turns" value="lado" checked={draft.body_turns==='lado'} onChange={()=>change('body_turns','lado')}/>
              <span><strong>De lado</strong><small>Perfil de 90°, volta de frente</small></span>
            </label>
            <label className={'generator-option '+(draft.body_turns==='costas'?'selected':'')}>
              <input type="radio" name="body_turns" value="costas" checked={draft.body_turns==='costas'} onChange={()=>change('body_turns','costas')}/>
              <span><strong>De costas</strong><small>Somente quando a peça exige</small></span>
            </label>
          </div>
          <span className="option-field-title" id="video-style-title">Câmera e movimento</span>
          <StyleChips value={draft.video_style} onChange={v=>change('video_style',v)} labelledBy="video-style-title"/>
          <small className="help">Closes: no meio do vídeo a câmera mostra o material de perto por 1 a 2 s e volta ao rosto. Ousados: giro completo em vestido e saia, agachamento em legging, passos firmes em calça.</small>
          <small className="help">Técnicas de retenção (até 2): começar já em movimento; aproximação rápida até a lente; mão cobrindo a lente e revelando a peça; loop (o fim emenda no começo); esticar o tecido perto da lente.</small>
          <small className="help">Essa escolha tem prioridade sobre os movimentos automáticos do nicho. “De frente” impede giros inesperados; costas só aparecem quando você autorizar.</small>
        </div>
        </details>
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
          <label>Detalhes adicionais<textarea autoComplete="off" rows={3} value={draft.details||''} onChange={e=>change('details',e.target.value)} placeholder="Enquadramento, gestos e detalhes do produto" maxLength={5000}/></label>
          <label>Movimentos para mostrar<textarea autoComplete="off" rows={3} value={draft.movements||''} onChange={e=>change('movements',e.target.value)} placeholder="Ex.: caminhar dois passos, virar de lado, ajustar o cós" maxLength={1500}/><small className="help">Um movimento por vírgula ou por linha. O "Melhorar prompt" usa todos, até 4, na ordem escrita. Para 15 segundos, 2 ou 3 costumam ficar mais naturais.</small></label>
        </div>
      )}
      {!showAdvanced && (
        <div className="notice niche-summary">
          <strong>Já preenchido:</strong> {(draft.audience||'—').slice(0,70)}… · tom {draft.tone||'—'} · estilo {draft.style||'—'}
        </div>
      )}
    </fieldset>
    {briefError&&<p className="rd-alert" role="alert">{briefError}</p>}
    <div className="form-actions">
      {onCancel&&<button type="button" disabled={busy} onClick={onCancel}>Cancelar</button>}
      <button className="primary" disabled={busy||!draft.name?.trim()||!draft.model_name?.trim()||!draft.niche}>{campaign?.id?'Salvar':'Criar campanha'}</button>
    </div>
  </form>;
}



export function SetupChecklist({busy,onError}){
  const [data,setData]=useState(null);
  const [open,setOpen]=useState(!isMobileDevice());
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
          <h2>5 posts · {prog.in_flight||0} em produção · faltam ~{prog.remaining??5}</h2>
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

// Guarda a modelo escolhida na biblioteca pra ela continuar selecionada
// depois de recarregar a pagina (antes voltava sempre pra modelo padrao).
const MODEL_LIBRARY_KEY='fabrica.modelLibrary.activeModel';
export function readStoredModel(){
  try{return (localStorage.getItem(MODEL_LIBRARY_KEY)||'').trim()}catch(_){return ''}
}

export function ModelLibraryPanel({modelName='Micaela',busy,onError,onFlash}){
  const [activeModel,setActiveModel]=useState(()=>readStoredModel()||modelName);
  // Previa local (a propria foto escolhida) enquanto a foto enviada ainda
  // nao chegou do armazenamento - fotos do celular tem varios MB.
  const [previews,setPreviews]=useState({});
  const [knownModels,setKnownModels]=useState([]);
  const [newModelDraft,setNewModelDraft]=useState('');
  const [addingModel,setAddingModel]=useState(false);
  const [items,setItems]=useState([]);
  const [loading,setLoading]=useState(true);
  const [selectedNiche,setSelectedNiche]=useState('');
  const [sheetBusy,setSheetBusy]=useState(false);
  const [lightbox,setLightbox]=useState(null);
  const [renaming,setRenaming]=useState(null);
  const [renameDraft,setRenameDraft]=useState('');
  const fileRefs=useRef({});
  const firstModelName=useRef(modelName);
  useEffect(()=>{
    // So segue a modelo padrao quando ela muda de verdade (ex.: identidade
    // carregou depois); no primeiro carregamento vale a que ficou salva.
    if(firstModelName.current===modelName) return;
    firstModelName.current=modelName;
    setActiveModel(modelName);
  },[modelName]);
  useEffect(()=>{
    try{ if(activeModel) localStorage.setItem(MODEL_LIBRARY_KEY,activeModel); }catch(_){}
  },[activeModel]);
  useEffect(()=>()=>{Object.values(previews).forEach(url=>URL.revokeObjectURL(url))},[]);
  async function loadModels(preferred){
    try{
      const data=await listModelLibraryModels();
      let names=data.models||[];
      if(preferred && !names.some(n=>n.toLocaleLowerCase()===preferred.toLocaleLowerCase())) names=[preferred,...names];
      setKnownModels(names);
    }catch(_){/* seletor e so um atalho, nao trava a tela se falhar */}
  }
  async function load(){
    setLoading(true);
    try{
      const data=await modelLibrary(activeModel);
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
  useEffect(()=>{load();loadModels(activeModel)},[activeModel]);
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
        await uploadModelLibraryPhotoDirect(activeModel,niche,file);
      }else{
        const form=new FormData();
        form.set('model_name',activeModel);
        form.set('niche',niche);
        form.set('file',file);
        await uploadModelLibrary(form);
      }
      const key=activeModel+'|'+niche;
      const local=URL.createObjectURL(file);
      setPreviews(prev=>{ if(prev[key]) URL.revokeObjectURL(prev[key]); return {...prev,[key]:local}; });
      onFlash?.('Foto padrão de '+activeModel+' salva: '+niche);
      await load();
      await loadModels(activeModel);
      setSelectedNiche(niche);
    }catch(e){onError?.(e.message||String(e))}
    finally{
      if(inputEl) inputEl.value='';
      else if(fileRefs.current[niche]) fileRefs.current[niche].value='';
    }
  }
  async function onDelete(niche,e){
    e?.stopPropagation?.();
    const ok=window.confirm('Excluir a foto padrão deste nicho ('+activeModel+')? A foto some da biblioteca, mas campanhas já criadas continuam com a cópia que já tinham.');
    if(!ok)return;
    try{
      await deleteModelLibraryPhoto({model_name:activeModel,niche});
      const key=activeModel+'|'+niche;
      setPreviews(prev=>{ if(!prev[key]) return prev; URL.revokeObjectURL(prev[key]); const next={...prev}; delete next[key]; return next; });
      onFlash?.('Foto padrão excluída: '+niche);
      if(selectedNiche===niche) setSelectedNiche('');
      await load();
    }catch(e){onError?.(e.message||String(e))}
  }
  function confirmNewModel(e){
    e?.preventDefault?.();
    const name=(newModelDraft||'').trim();
    if(!name){onError?.('Informe o nome do novo modelo.');return}
    setActiveModel(name);
    setNewModelDraft('');
    setAddingModel(false);
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
      await renameModelLibraryLabel({model_name:activeModel,niche:renaming,label});
      onFlash?.('Moda renomeada: '+label);
      setRenaming(null);
      await load();
    }catch(err){onError?.(err.message||String(err))}
  }
  async function copySheet(){
    if(!selectedNiche){onError?.('Selecione um nicho com foto.');return}
    setSheetBusy(true);
    try{
      const data=await characterSheet(activeModel,selectedNiche);
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
      const data=await openCharacterSheet({model_name:activeModel,niche:selectedNiche,confirmed:true});
      onFlash?.(data.message||'Grok aberto. Anexe a foto e cole o prompt.');
      if(data.prompt){
        try{await navigator.clipboard.writeText(data.prompt)}catch(_){/* backend may already have copied */}
      }
    }catch(e){onError?.(e.message||String(e))}
    finally{setSheetBusy(false)}
  }
  const selected=items.find(x=>x.niche===selectedNiche);
  const anyPhoto=items.some(x=>x.has_photo);
  return (
    <section className="model-library">
      <div className="home-hero" style={{marginBottom:12}}>
        <div>
          <span className="eyebrow">MODELO FIXA · {(items.filter(x=>x.has_photo).length)}/{(items.length||6)} nichos</span>
          <h2>Fotos padrão — {activeModel}</h2>
          <p className="help">{anyPhoto?'Toque na foto pra ampliar.':'Envie uma foto da modelo para cada estilo. Ela vira a referência fixa das campanhas desse nicho.'}</p>
        </div>
      </div>
      <div className="model-picker-row" style={{display:'flex',gap:8,flexWrap:'wrap',alignItems:'center',marginBottom:16}}>
        <label style={{display:'flex',flexDirection:'column',gap:4}}>
          <span className="help">Modelo</span>
          {knownModels.length>0 ? (
            <select value={activeModel} disabled={busy||loading} onChange={e=>{ if(e.target.value==='__new__'){setAddingModel(true);return} setAddingModel(false); setActiveModel(e.target.value); }}>
              {knownModels.map(n=><option key={n} value={n}>{n}</option>)}
              <option value="__new__">+ Criar novo modelo…</option>
            </select>
          ) : (
            <input autoComplete="off" value={activeModel} disabled={busy||loading} onChange={e=>setActiveModel(e.target.value)} placeholder="Ana"/>
          )}
        </label>
        {addingModel && (
          <form onSubmit={confirmNewModel} style={{display:'flex',gap:6,alignItems:'flex-end'}}>
            <label style={{display:'flex',flexDirection:'column',gap:4}}>
              <input autoComplete="off" autoFocus value={newModelDraft} maxLength={80} onChange={e=>setNewModelDraft(e.target.value)} placeholder="Nome do novo modelo"/>
            </label>
            <button type="submit" className="primary" disabled={busy||loading}>Usar</button>
            <button type="button" disabled={busy||loading} onClick={()=>{setAddingModel(false);setNewModelDraft('')}}>Cancelar</button>
          </form>
        )}
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
                <input autoComplete="off"
                  autoFocus
                  value={renameDraft}
                  maxLength={60}
                  aria-label="Novo nome da moda"
                  onChange={e=>setRenameDraft(e.target.value)}
                  onKeyDown={e=>{ e.stopPropagation(); if(e.key==='Escape'){ e.preventDefault(); setRenaming(null);} }}
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
                  onClick={e=>{e.stopPropagation();setSelectedNiche(item.niche);setLightbox({url:previews[activeModel+'|'+item.niche]||item.url,label:item.label,name:item.original_name||''});}}
                >
                  <img key={item.url||item.updated_at||item.niche} src={previews[activeModel+'|'+item.niche]||item.url} alt={item.label} loading="lazy" decoding="async"/>
                </button>
              ) : <span className="help">Sem foto ainda</span>}
            </div>
            <small className="help">{item.original_name||'Envie a foto padrão deste look'}{item.updated_at?` · atualizada`:''}</small>
            <input ref={el=>{fileRefs.current[item.niche]=el}} type="file" accept="image/jpeg,image/png,image/webp" hidden onChange={e=>onPick(item.niche,e.target.files?.[0],e.target)}/>
            <div className="niche-card-actions" style={{display:'flex',gap:6}}>
              <button type="button" className="button" disabled={busy||loading} onClick={e=>{e.stopPropagation();fileRefs.current[item.niche]?.click()}}>{item.has_photo?'Trocar foto':'Enviar foto padrão'}</button>
              {item.has_photo && <button type="button" className="button danger-action" title="Excluir foto padrão" aria-label={`Excluir foto padrão de ${item.label}`} disabled={busy||loading} onClick={e=>onDelete(item.niche,e)}><Trash2 size={14}/></button>}
            </div>
          </article>
        ))}
      </div>
      {/* A ficha de consistencia precisa de uma foto: sem nenhuma, o bloco so
          mostrava dois botoes desativados. */}
      {anyPhoto&&<div className="character-sheet-box">
        <div>
          <strong>Gerar ficha de consistência</strong>
          <p className="help">
            {isMobileDevice()
              ? (selected ? <>Nicho: <em>{selected.label}</em>.</> : <>Selecione um nicho com foto.</>)
              : <>Selecione um nicho com foto. Copie o prompt mestre de identidade ou abra o Grok: cole o prompt e anexe a foto da biblioteca como referência.{selected ? <> Nicho selecionado: <em>{selected.label}</em>.</> : <> Nenhum nicho com foto selecionado.</>}</>}
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
      </div>}
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



// Guarda o prompt que deu certo na biblioteca (fica no banco do app).
export function SaveToLibrary({kind,prompt,product,format,version,note,onError}){
  const [state,setState]=useState('');
  if(!prompt||String(prompt).length<40)return null;
  const save=async()=>{
    setState('saving');
    try{await savePromptToLibrary({kind,prompt,product:product||'',format:format||'',version:version||'',note:note||''});setState('saved')}
    catch(e){setState('');onError?.(e.message||String(e))}
  };
  return <button type="button" className="button" disabled={state==='saving'||state==='saved'} onClick={save}
    title="Guarda este prompt na Biblioteca de prompts para reaproveitar">
    {state==='saved'?<><Check size={15}/> Guardado na biblioteca</>:<><BookmarkPlus size={15}/> Guardar na biblioteca</>}
  </button>;
}

// Uso da IA desta campanha: tokens (o que a OpenAI cobra) e custo, se houver
// tabela de precos configurada no servidor.
export function AiUsage({usage}){
  if(!usage||!usage.calls)return null;
  const n=v=>Number(v||0).toLocaleString('pt-BR');
  const custo=usage.cost_usd==null?'':` · ~US$ ${Number(usage.cost_usd).toLocaleString('pt-BR',{minimumFractionDigits:2,maximumFractionDigits:4})}`;
  return <p className="help ai-usage" title={usage.by_model.map(m=>`${m.model}: ${m.calls} chamadas, ${n(m.input_tokens)} + ${n(m.output_tokens)} tokens`).join('\n')}>
    <strong>IA nesta campanha:</strong> {n(usage.calls)} {usage.calls===1?'chamada':'chamadas'} · {n(usage.input_tokens+usage.output_tokens)} tokens ({n(usage.input_tokens)} de entrada, {n(usage.output_tokens)} de saída){custo}
  </p>;
}


// Mostra o que o gerador entendeu da oferta e da prova social: so esses
// fatos viram urgencia ou "ja vendeu" no roteiro.
export function PersuasionPreview({offer,social}){
  const [data,setData]=useState(null);
  useEffect(()=>{
    if(!offer.trim()&&!social.trim()){setData(null);return}
    let alive=true;
    const timer=setTimeout(()=>{persuasionPreview({offer,social_proof:social}).then(res=>{if(alive)setData(res)}).catch(()=>{})},400);
    return()=>{alive=false;clearTimeout(timer)};
  },[offer,social]);
  if(!data)return null;
  return <div className="persuasion-preview" aria-live="polite">
    {(data.offer.length>0||data.offer_unread)&&<div><span>O roteiro pode usar</span>{data.offer.map(x=><em key={x}>{x}</em>)}{data.offer_unread&&<small className="field-error">Não entendi a oferta. Escreva como “20% até domingo”, “últimas 30 peças” ou “frete grátis”.</small>}</div>}
    {(data.social.length>0||data.social_unread)&&<div><span>Prova social</span>{data.social.map(x=><em key={x}>{x}</em>)}{data.social_unread&&<small className="field-error">Não entendi. Escreva como “2 mil vendidos” ou “nota 4,8”.</small>}</div>}
  </div>;
}
