// Conteudo dos modais (identidade, escrita por IA, banco de falas, campanha automatica).
// Fora de components.jsx para o App carregar sob demanda (React.lazy), so quando o modal abre.
import { useEffect, useState } from 'react';
import { ImagePlus, Palette, RefreshCw, Sparkles, Trash2, Upload } from 'lucide-react';
import { NICHE_DEFAULTS } from './nicheDefaults';
import { deleteFromSpeechBank, quickBrief, saveStudioIdentity, saveWriterSettings, speechBank, testWriter, writerSettings } from './api';
import { isCloudMode } from './serviceLinks';
import { pointToFacts } from './sequenceText';
import { CopyButton, FORMAT_OPTIONS, SequenceChoice, StyleChips, emptyBrief } from './components';

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
        <label>Nome do estudio<input autoComplete="off" value={draft.studio_name||''} disabled={busy||saving} onChange={e=>set('studio_name',e.target.value)} placeholder="Estudio da Ana"/></label>
        <label>Marca / app<input autoComplete="off" value={draft.brand_name||''} disabled={busy||saving} onChange={e=>set('brand_name',e.target.value)} placeholder="Fabrica TikTok"/></label>
        <label>Nome da modelo<input autoComplete="off" value={draft.model_name||''} disabled={busy||saving} onChange={e=>set('model_name',e.target.value)} placeholder="Ana"/></label>
        <label>@ TikTok<input autoComplete="off" value={draft.tiktok_handle||''} disabled={busy||saving} onChange={e=>set('tiktok_handle',e.target.value.replace(/^@/,''))} placeholder="handle_sem_arroba"/></label>
        <label>Perfil Chrome<input autoComplete="off" value={draft.chrome_profile_hint||''} disabled={busy||saving} onChange={e=>set('chrome_profile_hint',e.target.value)} placeholder="Profile 7 ou nome no Chrome (ex.: Micaela)"/></label>
        <label>Conta Grok (lembrete)<input autoComplete="off" value={draft.grok_account_hint||''} disabled={busy||saving} onChange={e=>set('grok_account_hint',e.target.value)} placeholder="email@…"/></label>
        <label>Conta Flow (lembrete)<input autoComplete="off" value={draft.flow_account_hint||''} disabled={busy||saving} onChange={e=>set('flow_account_hint',e.target.value)} placeholder="email@…"/></label>
        <label className="span-2">Notas<textarea autoComplete="off" rows={2} value={draft.notes||''} disabled={busy||saving} onChange={e=>set('notes',e.target.value)} placeholder="Lembretes locais"/></label>
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
  // Formato conferido enquanto digita; a conferencia de verdade (a chave
  // existe e o modelo esta disponivel) acontece no servidor ao salvar.
  const typed=key.trim();
  const keyError=!typed||!data.provider?''
    :data.provider==='openai'&&!/^sk-[A-Za-z0-9_-]{20,}$/.test(typed)?'A chave da OpenAI começa com "sk-" e é bem mais longa. Confira se copiou a chave inteira.'
    :data.provider==='gemini'&&!/^AIza[0-9A-Za-z_-]{30,}$/.test(typed)?'A chave do Gemini começa com "AIza". Confira se copiou a chave inteira.'
    :'';
  const missingKey=data.enabled&&!data.has_key&&!typed;
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
        <input autoComplete="off" value={data.model||''} disabled={busy||saving} onChange={e=>change({model:e.target.value})} placeholder={(data.default_models||{})[data.provider]||''} maxLength={120}/>
      </label>
      <label>Chave de API
        <input type="password" value={key} disabled={busy||saving} onChange={e=>setKey(e.target.value)}
          placeholder={data.has_key?(data.key_source==='env'?`Chave da Vercel ${data.key_hint} em uso — cole outra só para trocar`:`Chave guardada ${data.key_hint} — deixe vazio para manter`):'Cole a chave aqui'} maxLength={400} autoComplete="off"/>
        {keyError&&<small className="field-error" role="alert">{keyError}</small>}
        <small className="help">{isCloudMode()?'Fica guardada no armazenamento privado da Fábrica.':'Fica só neste computador, em data/llm.json.'} Nunca aparece na tela depois de salva. Ao salvar, a Fábrica confere a chave e o modelo direto no provedor.</small>
      </label>
      <label className="check-row">
        <input type="checkbox" checked={!!data.enabled} disabled={busy||saving||!data.has_key&&!key.trim()} onChange={e=>change({enabled:e.target.checked})}/>
        Usar a IA para escrever as falas
      </label>
    </>}
    <div className="form-actions">
      {data.has_key&&<button type="button" disabled={busy||saving} onClick={()=>save({clear_key:true,enabled:false})}>Remover chave</button>}
      {data.provider&&data.has_key&&<button type="button" disabled={busy||testing} onClick={test}>{testing?'Testando…':'Testar conexão'}</button>}
      <button type="button" className="primary" disabled={busy||saving||!!keyError||missingKey} onClick={()=>save()}>{saving?'Conferindo a chave…':'Salvar escrita por IA'}</button>
    </div>
    {missingKey&&<small className="field-error">Cole a chave da API para ligar a escrita por IA.</small>}
    {sample&&<div className="notice writer-sample">
      <strong>Exemplo gerado agora:</strong>
      <p><em>Hook:</em> {sample.hook}</p>
      <p><em>Desenvolvimento:</em> {sample.development}</p>
      <p><em>CTA:</em> {sample.cta}</p>
    </div>}
    </>}
  </section>;
}
// Banco de falas: como uma pessoa real fala de cada tipo de peca, mais os
// roteiros que o estudio aprovou. As falas aprovadas viram exemplo de voz
// para a escrita por IA nas proximas campanhas da mesma categoria.
export function SpeechBankPanel({campaignId,onApply,onError,onFlash}){
  const [data,setData]=useState(null);
  const [loading,setLoading]=useState(true);
  const [working,setWorking]=useState('');
  const [confirmId,setConfirmId]=useState('');
  const load=async(category)=>{
    setLoading(true);
    try{
      const query=category?`category=${encodeURIComponent(category)}`:(campaignId&&category===undefined?`campaign=${campaignId}`:'');
      setData(await speechBank(query));
    }catch(e){onError?.(e.message||String(e))}
    finally{setLoading(false)}
  };
  useEffect(()=>{load(undefined)},[campaignId]);
  const remove=async item=>{
    if(confirmId!==item.id){setConfirmId(item.id);return}
    setWorking(item.id);
    try{await deleteFromSpeechBank(item.id);setConfirmId('');onFlash?.('Fala removida do banco.');await load(data?.category||'')}
    catch(e){onError?.(e.message||String(e))}
    finally{setWorking('')}
  };
  const apply=async item=>{
    setWorking('apply');
    try{await onApply?.(item)}finally{setWorking('')}
  };
  const current=data?.category||'';
  const detail=data?.detail;
  const saved=data?.saved||[];
  const card=(item,key,extra)=>{
    const full=[item.hook,item.development,item.cta].filter(Boolean).join(' ');
    return <article className="speech-card" key={key}>
      <p><em>0–4s</em>{item.hook}</p>
      <p><em>4–12s</em>{item.development}</p>
      <p><em>12–15s</em>{item.cta}</p>
      {extra}
      <div className="speech-card-actions">
        <CopyButton text={full} onError={onError} label="Copiar fala"/>
        {onApply&&<button type="button" disabled={!!working} onClick={()=>apply(item)}>Usar no roteiro</button>}
        {item.id&&<button type="button" className={confirmId===item.id?'danger':''} disabled={!!working} onClick={()=>remove(item)}><Trash2 size={15}/>{confirmId===item.id?'Confirmar remoção':'Remover'}</button>}
      </div>
    </article>;
  };
  return <div className="speech-bank">
    <p className="help">Cada tipo de peça tem um jeito próprio de ser falado. O gerador local usa estas vozes, e a IA recebe as falas aprovadas pelo estúdio como exemplo de ritmo.</p>
    <div className="rd-tabs speech-bank-tabs" role="tablist" aria-label="Categoria">
      <button type="button" role="tab" className="rd-chip-tab" aria-selected={!current} disabled={loading} onClick={()=>load('')}>Todas{data?` · ${data.total}`:''}</button>
      {(data?.categories||[]).map(cat=><button type="button" role="tab" key={cat.id} className="rd-chip-tab" aria-selected={current===cat.id} disabled={loading} onClick={()=>load(cat.id)}>{cat.label}{cat.saved?` · ${cat.saved}`:''}</button>)}
    </div>
    {loading&&!data?<p className="help">Carregando o banco de falas…</p>:<>
      {detail&&<section className="speech-bank-voice">
        <strong>Como falar de {detail.label.toLowerCase()}</strong>
        <p>{detail.tone}</p>
        <p className="help">Cuidado: {detail.avoid}</p>
        <div className="speech-bank-tags"><span>Ocasiões</span>{detail.occasions.map(o=><em key={o}>{o}</em>)}</div>
        <div className="speech-bank-tags"><span>Objeções comuns</span>{detail.objections.map(o=><em key={o}>{o}</em>)}</div>
      </section>}
      {onApply&&<p className="rd-alert">Ao usar uma fala, confira se cada detalhe citado (bojo, forro, bolso…) existe neste produto. Falas de outras peças podem citar o que esta não tem.</p>}
      <h3 className="speech-bank-heading">Aprovadas pelo estúdio · {saved.length}</h3>
      {saved.length?saved.map(item=>card(item,item.id,<small className="speech-card-meta">{[item.product,item.color,item.author,item.note].filter(Boolean).join(' · ')}</small>))
        :<p className="help">Nenhuma fala guardada{detail?` para ${detail.label.toLowerCase()}`:''} ainda. Na etapa Roteiro, use “Guardar no banco” nas falas que soaram naturais.</p>}
      {(data?.showcase||[]).length>0&&<>
        <h3 className="speech-bank-heading">Exemplos da categoria</h3>
        <p className="help">Exemplos ilustrativos. Os que citam um detalhe só são usados pelo gerador quando o briefing confirma esse detalhe.</p>
        {data.showcase.map((item,i)=>card({...item,id:''},`ex-${i}`,item.needs?<small className="speech-card-meta">Precisa no briefing: {item.needs}</small>:null))}
      </>}
    </>}
  </div>;
}
// Campanha automatica: a pessoa escolhe a moda e sobe a foto do produto e o
// print da descricao; a IA le tudo e o app vai ate os prompts do Grok. No
// maximo a pessoa informa as cores.
const NICHE_SHORT={praia:'Praia',academia:'Academia',casual:'Casual','dia-a-dia':'Dia a dia',intima:'Íntima',fantasia:'Fantasia'};

function briefFromAI(brief,model,niche,colors){
  const d=NICHE_DEFAULTS[niche]||{};
  return {...emptyBrief,...d,niche,model_name:model,generator:'grok',
    name:`${model} · ${brief.product||NICHE_SHORT[niche]}`,
    product:brief.product||'',outfit:brief.product||d.outfit||'',color:(colors||'').trim()||brief.colors||'',
    details:brief.details||d.details||'',benefit:brief.benefit||d.benefit||'',angle:brief.angle||d.angle||'',
    movements:brief.movements||d.movements||'',objection:brief.objection||'',offer:brief.offer||'',
    social_proof:brief.social_proof||''};
}

export function AutoCreatePanel({modelName='Micaela',busy,onCreate,onError}){
  const [niche,setNiche]=useState('');
  const [products,setProducts]=useState([]);
  const [description,setDescription]=useState(null);
  const [colorsPhoto,setColorsPhoto]=useState(null);
  const [colors,setColors]=useState('');
  const [format,setFormat]=useState('');
  const [turn,setTurn]=useState(true);
  const [style,setStyle]=useState('');
  const [seqClips,setSeqClips]=useState('');
  const [seqArc,setSeqArc]=useState('motivos');
  const [facts,setFacts]=useState('');
  const [reading,setReading]=useState(false);
  const [urls,setUrls]=useState([]);
  useEffect(()=>{
    const list=[...products,...(description?[description]:[]),...(colorsPhoto?[colorsPhoto]:[])].map(f=>URL.createObjectURL(f));
    setUrls(list);
    return()=>list.forEach(u=>URL.revokeObjectURL(u));
  },[products,description,colorsPhoto]);
  const start=async()=>{
    onError?.('');setReading(true);
    try{
      const {brief}=await quickBrief(products,description,niche,colorsPhoto);
      const values={...briefFromAI(brief,modelName,niche,colors),video_mode:format,body_turns:turn?'leve_lado':'',
        video_style:style,sequence_clips:seqClips,sequence_arc:seqClips?seqArc:''};
      if(seqClips){
        // Os fatos escritos aqui vem primeiro; os que a IA leu da foto e do print completam.
        const lidos=String(brief.details||'').trim();
        values.details=[facts.trim(),lidos].filter(Boolean).join(', ');
      }
      if(!values.color){onError?.('A IA não achou as cores. Suba a foto das cores ou escreva as cores e tente de novo.');return}
      const lidos=[values.offer&&`oferta “${values.offer}”`,values.social_proof&&`prova social “${values.social_proof}”`].filter(Boolean);
      const message='Campanha automática criada: roteiro e prompts do Grok prontos. Cores: '+values.color+'.'+(lidos.length?` Do print: ${lidos.join(' e ')} — confira no briefing se ainda valem.`:'');
      await onCreate?.(values,products,message);
    }catch(e){const m=e.message||String(e);onError?.(seqClips?pointToFacts(m,'acima'):m)}
    finally{setReading(false)}
  };
  if(reading||busy)return <div className="quick-create quick-reading" aria-live="polite">
    <RefreshCw className="spinning" size={28}/><strong>{reading&&!busy?'A IA está lendo as fotos…':'Criando a campanha e escrevendo o roteiro…'}</strong>
    <small>Leva em torno de 30 a 60 segundos. Não feche esta janela.</small>
  </div>;
  return <div className="quick-create">
    <p className="help">Escolha a moda e suba as duas fotos. A IA lê tudo, escreve o roteiro e deixa os prompts do Grok prontos.</p>
    <span className="option-field-title" id="auto-niche">Moda</span>
    <div className="quick-niches" role="radiogroup" aria-labelledby="auto-niche">
      {Object.entries(NICHE_SHORT).map(([id,label])=><button type="button" key={id} role="radio" aria-checked={niche===id}
        className="rd-chip-tab" aria-selected={niche===id} onClick={()=>setNiche(id)}>{label}</button>)}
    </div>
    <label className="quick-tile">
      <input type="file" accept="image/*" multiple onChange={e=>setProducts(Array.from(e.target.files||[]).slice(0,3))}/>
      <ImagePlus size={22}/><strong>Foto do produto</strong><small>1 a 3 fotos da peça</small>
      {products.length>0&&<span className="quick-thumbs">{urls.slice(0,products.length).map(u=><img key={u} src={u} alt=""/>)}</span>}
    </label>
    <label className="quick-tile">
      <input type="file" accept="image/*" onChange={e=>setDescription(e.target.files?.[0]||null)}/>
      <Upload size={22}/><strong>Print da descrição</strong><small>Página do produto com tecido, preço e avaliações</small>
      {description&&<span className="quick-thumbs"><img src={urls[products.length]} alt=""/></span>}
    </label>
    <label className="quick-tile">
      <input type="file" accept="image/*" onChange={e=>setColorsPhoto(e.target.files?.[0]||null)}/>
      <Palette size={22}/><strong>Foto das cores (opcional)</strong><small>Print do seletor de cores ou as cores lado a lado: a IA descreve cada uma com os detalhes</small>
      {colorsPhoto&&<span className="quick-thumbs"><img src={urls[products.length+(description?1:0)]} alt=""/></span>}
    </label>
    <span className="option-field-title" id="auto-format">Formato do vídeo</span>
    <div className="quick-niches" role="radiogroup" aria-labelledby="auto-format">
      {FORMAT_OPTIONS.map(([id,label])=>
        <button type="button" key={id||'fala'} role="radio" aria-checked={format===id} className="rd-chip-tab"
          aria-selected={format===id} onClick={()=>setFormat(id)}>{label}</button>)}
    </div>
    <SequenceChoice clips={seqClips} arc={seqArc} format={format} onClips={setSeqClips} onArc={setSeqArc} idPrefix="auto-seq"/>
    {seqClips&&<label>Fatos da peça (opcional, completam o que a IA lê)<input autoComplete="off" value={facts} onChange={e=>setFacts(e.target.value)} placeholder="Ex.: capuz, zíper frontal, bolsos laterais" maxLength={300}/></label>}
    {seqClips&&<small className="help">A sequência precisa de 3 fatos da peça. Se a IA não achar 3 na foto e no print, a campanha não é criada e o aviso diz o que faltou: escreva aqui e tente de novo.</small>}
    <label className="quick-confirm"><input type="checkbox" checked={turn} onChange={e=>setTurn(e.target.checked)}/> Girar um pouco de lado para mostrar a peça (sem mostrar as costas)</label>
    <span className="option-field-title" id="auto-style">Câmera e técnicas (opcional)</span>
    <StyleChips value={style} onChange={setStyle} labelledBy="auto-style"/>
    <small className="help">Até 2 técnicas por vídeo. Closes: o rosto sai do quadro por 1 a 2 s para mostrar o material.</small>
    <label>Cores (opcional)<input autoComplete="off" value={colors} onChange={e=>setColors(e.target.value)} placeholder="Ex.: laranja com floral branco; verde com floral branco" maxLength={300}/></label>
    <small className="help">Separe as cores com ponto e vírgula. Vazio: a IA lê da foto das cores ou do print. Escrito aqui, vale o que você escreveu.</small>
    <button type="button" className="primary full" disabled={busy||!niche||!products.length||!description} onClick={start}><Sparkles size={16}/> Criar campanha automática</button>
    {(!niche||!products.length||!description)&&<small className="help">Falta: {[!niche&&'a moda',!products.length&&'a foto do produto',!description&&'o print da descrição'].filter(Boolean).join(', ')}.</small>}
  </div>;
}
