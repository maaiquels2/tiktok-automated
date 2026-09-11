import { useEffect, useRef, useState } from 'react';
import { Plus, ArrowRight, Download, FolderHeart, Check, ExternalLink, RefreshCw, AlertCircle, X, ShieldCheck, Copy as CopyIcon, Pencil, Trash2 } from 'lucide-react';
import Canvas from './Canvas';
import { api, states, statusLabels, stageInfo, nextStage } from './api';
import {Dialog, BriefForm, CopyButton, AssetView, Uploader, TextEditor, ProductGallery, VariantList, PublishQueue, VideoMixer} from './components';

export default function App(){
  const [campaigns,setCampaigns]=useState([]),[c,setC]=useState(null),[references,setReferences]=useState([]);
  const [selected,setSelected]=useState('model'),[loading,setLoading]=useState(true),[busy,setBusy]=useState(false);
  const [error,setError]=useState(''),[notice,setNotice]=useState(''),[modal,setModal]=useState(null),[dirty,setDirty]=useState(false);
  const [renaming,setRenaming]=useState(false),[renameDraft,setRenameDraft]=useState('');
  const lock=useRef(false),noticeTimer=useRef();
  useEffect(()=>{
    let active=true;
    (async()=>{try{
      const [list,refs]=await Promise.all([api('/campaigns'),api('/references')]);
      const first=list[0]?await api('/campaigns/'+list[0].id):null;
      if(active){setCampaigns(list);setReferences(refs);setC(first);if(first)setSelected(nextStage(first));if(location.pathname==='/creator')setModal({type:'create'});}
    }catch(e){if(active)setError(e.message)}finally{if(active)setLoading(false)}})();
    return()=>{active=false;clearTimeout(noticeTimer.current)};
  },[]);
  useEffect(()=>{const prevent=e=>{if(dirty){e.preventDefault();e.returnValue=''}};window.addEventListener('beforeunload',prevent);return()=>window.removeEventListener('beforeunload',prevent)},[dirty]);
  function flash(text){setNotice(text);clearTimeout(noticeTimer.current);noticeTimer.current=setTimeout(()=>setNotice(''),7000)}
  function discard(){if(!dirty)return true;if(window.confirm('Há alterações sem salvar. Deseja descartá-las?')){setDirty(false);return true}return false}
  async function refresh(){const [list,refs]=await Promise.all([api('/campaigns'),api('/references')]);setCampaigns(list);setReferences(refs)}
  async function run(action,message='Salvo localmente.',next){
    if(lock.current)return false;
    lock.current=true;setBusy(true);setError('');
    try{const result=await action();if(result?.id){setC(result);setDirty(false);if(next)setSelected(next)}await refresh();flash(message);return true}
    catch(e){setError(e.message);return false}finally{lock.current=false;setBusy(false)}
  }
  function choose(stage){if(!busy&&discard()){setSelected(stage);setError('')}}
  function publicationLinks(campaign){
    const slots=(campaign?.checklist&&campaign.checklist.slots)||{};
    const links=[];
    if(campaign?.published_url) links.push({color:'Geral',url:campaign.published_url});
    Object.entries(slots).forEach(([color,info])=>{if(info?.url) links.push({color,url:info.url})});
    // dedupe by url
    const seen=new Set();
    return links.filter(l=>{if(seen.has(l.url))return false;seen.add(l.url);return true});
  }
  function openPublication(){
    if(!c)return;
    const links=publicationLinks(c);
    if(!links.length){
      setError('Nenhum link do TikTok foi salvo nesta campanha. Abra o Studio e registre o link ao publicar a cor.');
      choose('studio');
      return;
    }
    // open first link; if several, also jump to studio so user sees all colors
    window.open(links[0].url,'_blank','noopener,noreferrer');
    if(links.length>1) choose('studio');
  }

  function beginRename(){if(!c||busy)return;setRenameDraft(c.name||'');setRenaming(true);setError('')}
  async function saveRename(){
    if(!c)return;
    const name=(renameDraft||'').trim();
    if(!name){setError('Digite um nome para a campanha.');return}
    if(name===c.name){setRenaming(false);return}
    const ok=await run(()=>api(`/campaigns/${c.id}`,{method:'PATCH',body:{name,version:c.version}}),'Campanha renomeada.');
    if(ok)setRenaming(false);
  }

  async function chooseCampaign(id){if(busy||!discard())return;await run(async()=>{const result=await api('/campaigns/'+id);setSelected(nextStage(result));return result},'Campanha carregada.')}
  function editCampaign(){
    if(!c||busy)return;
    if(c.status!=='published'){choose('look');return}
    confirm('Criar versão editável?','A campanha publicada continuará preservada. Será criada uma nova versão com o briefing, a referência da modelo e as fotos do produto para você editar e revisar novamente.',()=>run(()=>post('/duplicate',{confirmed:true,mode:'edit'}),'Nova versão editável criada.','look'),'Criar versão');
  }
  function editCampaignById(id){
    const item=campaigns.find(entry=>entry.id===id);
    if(!item||busy)return;
    if(item.status==='published'){
      confirm('Criar versão editável?',`A campanha publicada “${item.name}” continuará preservada. Será criada uma nova versão para editar e revisar novamente.`,()=>run(()=>api(`/campaigns/${id}/duplicate`,{method:'POST',body:{confirmed:true,mode:'edit'}}),'Nova versão editável criada.','look'),'Criar versão');
      return;
    }
    if(!discard())return;
    run(async()=>{const result=await api(`/campaigns/${id}`);setSelected(nextStage(result));return result},'Campanha aberta para edição.');
  }
  function copyCampaign(id){
    const item=campaigns.find(entry=>entry.id===id);
    if(!item||busy)return;
    confirm('Copiar campanha?',`Será criada uma nova campanha editável a partir de “${item.name}”. A original continuará preservada.`,()=>run(()=>api(`/campaigns/${id}/copy`,{method:'POST',body:{confirmed:true}}),'Cópia criada.','look'),'Copiar campanha');
  }
  function deleteCampaign(id){
    const item=campaigns.find(entry=>entry.id===id);
    if(!item||busy)return;
    confirm('Excluir campanha?',`A campanha “${item.name}” e os arquivos dela serão excluídos permanentemente.`,()=>run(async()=>{const result=await api(`/campaigns/${id}`,{method:'DELETE',body:{confirmed:true}});if(c?.id===id){setC(null);setSelected('model');setDirty(false)}return result},'Campanha excluída.'),'Excluir');
  }
  function generateVariants(){
    if(dirty){setError('Salve o briefing antes de gerar as variações.');return}
    run(()=>post('/variants/generate'),'Prompts múltiplos gerados por cor.','look');
  }
  function confirm(title,description,action,label='Confirmar'){setError('');setModal({type:'confirm',title,description,action,label})}
  function post(suffix,body={}){return api(`/campaigns/${c.id}${suffix}`,{method:'POST',body:{...body,version:c.version}})}
  function saveBrief(values,photos=[],removed=[]){
    const next=(c.assets.some(a=>a.kind==='reference')&&values.model_name===c.model_name)?'look':'model';
    const action=()=>run(()=>{
      if(photos.length||removed.length){
        const form=new FormData();form.set('briefing',JSON.stringify({...values,version:c.version}));form.set('removed',JSON.stringify(removed));photos.forEach(file=>form.append('files',file));
        return api(`/campaigns/${c.id}/look`,{method:'POST',body:form});
      }
      return api(`/campaigns/${c.id}`,{method:'PATCH',body:{...values,version:c.version}});
    },'Briefing e fotos do produto salvos.',next);
    const changed=photos.length||removed.length||Object.keys(values).some(k=>k!=='name'&&values[k]!==(c[k]||''));
    if(changed&&c.prompts.image)confirm('Iniciar uma nova versão?','A alteração do briefing retira as mídias do fluxo atual e solicita novas aprovações. Os arquivos anteriores ficam guardados na pasta da campanha.',action,'Salvar e reiniciar');else action();
  }
  function saveTexts(values){
    const action=()=>run(()=>api(`/campaigns/${c.id}/prompts`,{method:'PATCH',body:{prompts:values,version:c.version}}),'Textos salvos.');
    if(c.status!=='briefing')confirm('Salvar a revisão do texto?','Alterar o prompt da imagem reinicia a produção. Alterar o roteiro refaz o prompt de vídeo com as novas falas. Alterar roteiro ou prompt de vídeo exige um novo vídeo. Alterar a legenda pede nova preparação da publicação.',action,'Salvar revisão');else action();
  }
  function upload(kind,file,color){
    if(!discard())return;
    if(file.size>(kind==='video'?250:40)*1024*1024){setError('Arquivo acima do limite permitido.');return}
    const action=()=>{const form=new FormData();form.set('kind',kind);form.set('file',file);form.set('version',c.version);if(color)form.set('color',color);const stay=kind==='image'?'image':kind==='video'?'video':'look';return run(()=>api(`/campaigns/${c.id}/assets`,{method:'POST',body:form}),color?`Imagem ${color} salva.`:'Mídia salva localmente.',stay)};
    const existsSame=c.assets.some(a=>a.kind===kind && (!color || a.slot===color || a.metadata?.color===color));
    if(existsSame)confirm('Substituir esta mídia?',color?`Substituir a imagem da cor ${color}? A versão anterior continua guardada localmente.`:'A nova mídia precisa ser revisada e invalida as etapas seguintes. A versão anterior continua guardada localmente.',action,'Substituir');else action();
  }
  function saveVariantPrompts(variantId,prompts){
    return run(()=>api(`/campaigns/${c.id}/variants/${variantId}/prompts`,{method:'PATCH',body:{prompts,version:c.version}}),'Roteiro da cor atualizado.');
  }
  function refreshVariant(variantId,fields){
    return run(()=>api(`/campaigns/${c.id}/variants/${variantId}/refresh`,{method:'POST',body:{fields,version:c.version}}),'Nova variação de fala gerada.');
  }
  function mixVideos(payload){
    return run(()=>api(`/campaigns/${c.id}/videos/mix`,{method:'POST',body:{...payload,version:c.version}}),'Mix gerado. Revise o MP4 no slot escolhido.','video');
  }
  function publishSlot(payload){
    return run(()=>api(`/campaigns/${c.id}/publish-slot`,{method:'POST',body:{...payload,version:c.version}}),`Publicação de ${payload.color||'produto'} registrada.`,'studio');
  }
  function transition(target,extra={}){
    if(dirty){setError('Salve os textos alterados antes de avançar.');return}
    return run(()=>post('/transition',{target,confirmed:true,...extra}),'Etapa concluída.',{image_approved:'script',script_ready:'video',video_approved:'studio',ready_to_publish:'studio',published:'studio'}[target]);
  }
  function openService(service,stage){
    if(dirty){setError('Salve o texto antes de abrir o serviço.');return}
    const account=service==='studio'?'perfil existente do Chrome da Micaela':'maaiquels@gmail.com';
    confirm(`Abrir ${service==='studio'?'TikTok Studio':service==='flow'?'Google Flow':'Grok Imagine'}?`,
      `O serviço será aberto no perfil separado de ${account}. Confira a conta e faça login manualmente, se necessário. ${service==='grok'?'No Grok, toda interação é manual. Feche as janelas do Flow desse perfil antes de continuar.':'Cole o texto e anexe o arquivo na página.'} Gerar conteúdo, gastar créditos, selecionar produto e publicar dependem dos seus cliques.`,
      ()=>run(async()=>{const result=await post('/browser',{service,stage,confirmed:true});flash(result.message);return null},'Navegador solicitado. Confira a janela do perfil dedicado.'),'Abrir perfil dedicado');
  }
  async function persistLayout(layout){
    if(busy)return;
    try{await api(`/campaigns/${c.id}/layout`,{method:'PATCH',body:{layout}});setC(old=>({...old,layout}));}catch(e){setError(e.message)}
  }
  const current=c?stageInfo.find(s=>s.id===nextStage(c)):null;
  const stage=stageInfo.find(s=>s.id===selected);
  return <><header className="header"><div className="brand"><span className="logo">▶</span><span>Fábrica TikTok</span><span className="brand-divider"/><span className="workspace-name">Estúdio da Micaela</span></div><span className="local-badge"><ShieldCheck size={15}/> {busy?'Salvando…':'Dados neste computador'}</span></header>
    <main className="workspace" aria-busy={loading}>
      <aside className="queue"><div className="queue-heading"><div><span className="eyebrow">PRODUÇÃO</span><h2>Campanhas <span className="count">{campaigns.length}</span></h2></div></div><button className="primary" disabled={busy||loading} onClick={()=>{if(discard()){setError('');setModal({type:'create'})}}}><Plus size={17}/> Nova campanha</button>
        <div className="campaign-list">{campaigns.map(item=><div className={'campaign '+(c?.id===item.id?'active':'')} key={item.id}><button className="campaign-select" disabled={busy} onClick={()=>chooseCampaign(item.id)} aria-pressed={c?.id===item.id}><span className="campaign-id">CAMPANHA {String(item.id).padStart(4,'0')}</span><strong>{item.name}</strong><small>{item.product||item.model_name}</small><span className={'status-pill '+(item.status==='published'?'success':'')}>{statusLabels[item.status]}</span></button><div className="campaign-actions"><button type="button" title="Editar campanha" aria-label={`Editar ${item.name}`} disabled={busy} onClick={()=>editCampaignById(item.id)}><Pencil size={14}/></button><button type="button" title="Copiar campanha" aria-label={`Copiar ${item.name}`} disabled={busy} onClick={()=>copyCampaign(item.id)}><CopyIcon size={14}/></button><button type="button" className="danger-action" title="Excluir campanha" aria-label={`Excluir ${item.name}`} disabled={busy} onClick={()=>deleteCampaign(item.id)}><Trash2 size={14}/></button></div></div>)}</div>
        <div className="queue-bottom"><FolderHeart size={20}/><strong>Uma modelo, novos looks.</strong><p>Reutilize a referência para preservar a identidade em cada campanha.</p></div>
      </aside>
      <section className="canvas-panel">{loading?<div className="empty-state"><RefreshCw className="spinning"/><h1>Carregando seu estúdio…</h1></div>:c?<>
        <div className="canvas-header"><div><span className="eyebrow">CANVAS DE PRODUÇÃO <span className="slash">/</span> {String(c.id).padStart(4,'0')}</span>{renaming?(
            <div className="campaign-rename">
              <input autoFocus value={renameDraft} disabled={busy} onChange={e=>setRenameDraft(e.target.value)} onKeyDown={e=>{if(e.key==='Enter')saveRename();if(e.key==='Escape')setRenaming(false)}} aria-label="Novo nome da campanha"/>
              <button type="button" className="primary" disabled={busy} onClick={saveRename}>Salvar</button>
              <button type="button" disabled={busy} onClick={()=>setRenaming(false)}>Cancelar</button>
            </div>
          ):(
            <h1 className="campaign-title-row">{c.name}<button type="button" className="icon-button btn-rename" title="Renomear campanha" aria-label="Renomear campanha" disabled={busy} onClick={beginRename}><Pencil size={16}/></button></h1>
          )}<div className="campaign-facts"><span>{c.model_name}</span><span>15s · 9:16</span><span>{c.generator==='flow'?'Flow · 1080p':'Grok · 720p'}</span></div></div><div className="export-actions"><button className="button" onClick={editCampaign} disabled={busy} title={c.status==='published'?'Criar uma nova versão editável':'Editar o briefing'}><RefreshCw size={16}/> Editar campanha</button><button className="button" onClick={beginRename} disabled={busy||renaming} title="Renomear esta campanha"><Pencil size={16}/> Renomear</button><a className="button" href={`/api/campaigns/${c.id}/package.txt`} title="Baixar prompts, roteiro e legenda">TXT</a><a className="button" href={`/api/campaigns/${c.id}/package.zip`} title="Baixar textos, referência e mídias aprovadas"><Download size={16}/> Pacote ZIP</a></div></div>
        {c.migration_note&&<div className="migration-note"><AlertCircle size={17}/>{c.migration_note}</div>}
        <div className="next-action"><div><span className="eyebrow">{c.status==='published'?'CONCLUÍDA':'PRÓXIMA AÇÃO'}</span><strong>{c.status==='published'?'Publicação registrada':current?.title}</strong></div><button disabled={busy||(c.status!=='published'&&!current)} onClick={()=>c.status==='published'?openPublication():choose(current.id)}>{c.status==='published'?'Ver publicação':'Continuar'}<ArrowRight size={16}/></button></div>
        <Canvas key={c.id} campaign={c} selected={selected} onSelect={choose} onLayout={persistLayout} busy={busy}/>
        <div className="stage-navigation" aria-label="Etapas da campanha">{stageInfo.map((s,i)=><button key={s.id} disabled={busy} className={s.id===selected?'active':''} aria-pressed={s.id===selected} onClick={()=>choose(s.id)}>{i+1}. {s.title}</button>)}</div>
      </>:<div className="empty-state"><div className="empty-icon"><FolderHeart size={34}/></div><span className="eyebrow">SEU CANVAS DE PRODUÇÃO</span><h1>Crie sua primeira campanha</h1><p>Defina o produto e o look, anexe a modelo e acompanhe cada aprovação até o TikTok.</p><button className="primary" onClick={()=>setModal({type:'create'})}><Plus size={17}/> Nova campanha</button></div>}</section>
      <aside className="inspector"><div className="inspector-heading"><span className="eyebrow">{c?'ETAPA SELECIONADA':'COMECE POR AQUI'}</span><h2>{c?stage.title:'Do briefing à publicação'}</h2><p>{c?stage.subtitle:'Toda a produção organizada em um só lugar.'}</p>{c&&<span className="status-pill">{statusLabels[c.status]}</span>}</div>
        {c?<Panel key={`${c.id}-${c.version}-${selected}`} c={c} selected={selected} busy={busy} references={references} onDirty={setDirty} onError={setError} onSaveBrief={saveBrief} onSaveTexts={saveTexts} onUpload={upload} onTransition={transition} onOpen={openService}
          onGenerate={()=>{if(dirty){setError('Salve o briefing antes de gerar os textos.');return}run(()=>post('/generate'),'Prompts, roteiro e legenda gerados localmente.','image')}}
          onGenerateVariants={generateVariants}
            onSaveVariant={saveVariantPrompts}
            onRefreshVariant={refreshVariant}
            onPublishSlot={publishSlot}
          onReuse={id=>confirm('Reutilizar esta referência?','A mesma imagem será copiada para esta campanha. Esta ação reinicia a produção e as aprovações seguintes.',()=>run(()=>post('/reference',{asset_id:Number(id)}),'Referência reutilizada.','look'),'Usar referência')}/>:<div className="notice">Crie uma campanha, use a referência fixa da modelo e revise imagem e vídeo antes de preparar a publicação.</div>}
      </aside>
    </main>
    {error&&<div className="toast error" role="alert"><AlertCircle size={19}/><span>{error}</span><button className="icon-button" onClick={()=>setError('')} aria-label="Fechar erro"><X size={16}/></button><button onClick={()=>{if(discard())location.reload()}}>Recarregar</button></div>}
    {notice&&!error&&<div className="toast" role="status"><Check size={19}/>{notice}</div>}
    {modal&&<Dialog title={modal.type==='create'?'Nova campanha':modal.title} onClose={()=>{if(!busy){setModal(null);setError('')}}}>
      {modal.type==='create'?<BriefForm busy={busy} onCancel={()=>setModal(null)} onSave={async values=>{if(await run(()=>api('/campaigns',{method:'POST',body:values}),'Campanha criada.','model'))setModal(null)}}/>:<><p>{modal.description}</p><div className="form-actions"><button disabled={busy} onClick={()=>setModal(null)}>Cancelar</button><button className="primary" disabled={busy} onClick={async()=>{if(await modal.action())setModal(null)}}>{busy?'Aguarde…':modal.label}</button></div></>}
      {error&&<p className="inline-error" role="alert">{error}</p>}
    </Dialog>}
  </>;
}

function Panel({c,selected,busy,references,onDirty,onError,onSaveBrief,onSaveTexts,onUpload,onTransition,onOpen,onGenerate,onGenerateVariants,onSaveVariant,onRefreshVariant,onPublishSlot,onMixVideos,onReuse}){
  const reference=c.assets.find(a=>a.kind==='reference'),image=c.assets.find(a=>a.kind==='image'),video=c.assets.find(a=>a.kind==='video');
  const [reuse,setReuse]=useState(''),[checks,setChecks]=useState(c.checklist||{}),[publishedUrl,setPublishedUrl]=useState(c.published_url||'');
  const immutable=c.status==='published',index=states.indexOf(c.status),colorCount=(c.color||'').split(/[,;|\n]+/).map(v=>v.trim()).filter(Boolean).length;
  const check=(key,label)=><label className="check-row" key={key}><input type="checkbox" checked={!!checks[key]} disabled={busy||immutable} onChange={e=>setChecks(old=>({...old,[key]:e.target.checked}))}/><span>{label}</span></label>;
  const editor=(field,title,rows=7)=><TextEditor title={title} field={field} value={c.prompts[field]} onSave={onSaveTexts} onDirty={onDirty} onError={onError} busy={busy} readOnly={immutable} rows={rows}/>;
  const service=stage=><div className="service-box"><strong>{c.generator==='flow'?'Google Flow':'Grok Imagine'}</strong><small>Perfil: maaiquels@gmail.com</small><button disabled={busy||immutable} onClick={()=>onOpen(c.generator,stage)}><ExternalLink size={16}/> Abrir {c.generator==='flow'?'Flow':'Grok'} para {stage==='image'?'imagem':'vídeo'}</button><p>{c.generator==='grok'?'Interação manual. Feche o Flow desse perfil antes de abrir o Grok.':'Cole o prompt, anexe a referência e revise antes de gerar.'}</p></div>;
  if(selected==='model')return <><AssetView asset={reference} title="Referência fixa da modelo"/><Uploader kind="reference" exists={!!reference} busy={busy} disabled={immutable} onUpload={onUpload}/><div className="notice">Preserve rosto, cabelo, corpo e tom de pele. Mude apenas roupa e cor.</div>{!immutable&&<section className="reuse-section"><h3>Reutilizar referência</h3><label>Referências de {c.model_name}<select value={reuse} onChange={e=>setReuse(e.target.value)}><option value="">Escolha uma imagem salva</option>{references.filter(r=>r.model_name.toLocaleLowerCase()===c.model_name.toLocaleLowerCase()&&r.id!==reference?.id).map(r=><option key={r.id} value={r.id}>{r.campaign_name} · {r.original_name}</option>)}</select></label><button disabled={!reuse||busy} onClick={()=>onReuse(reuse)}>Usar a mesma imagem</button></section>}</>;
  if(selected==='look')return <><BriefForm campaign={c} onSave={onSaveBrief} onDirty={onDirty} busy={busy}/>{!immutable&&<section className="generate-section"><h3>Prompts e roteiro</h3><p>Preencha roupa, cor, produto, público e benefício. Com várias cores, o app gera um pacote separado por cor (a IA não recebe todas juntas).</p><button className="primary full" disabled={busy||!reference||c.status!=='briefing'} onClick={onGenerate}>{c.prompts.image?'Gerar textos novamente':'Gerar prompts e roteiro'}</button>{colorCount>=2&&<small className="help">Detectamos {colorCount} cores: cada uma terá prompt de imagem, vídeo, roteiro e legenda próprios.</small>}{colorCount<2&&<small className="help">Separe as cores por vírgulas (ex.: Branco, Preto, Azul Marinho) para gerar uma variação de cada.</small>}{!reference&&<small className="help">Anexe a referência na etapa Modelo fixa.</small>}</section>}{c.variants?.length>0&&<VariantList variants={c.variants} onError={onError}/>}</>;
  if(selected==='image')return <>{(c.variants?.length>0||c.prompts.image)?<><div className="notice"><strong>Uma imagem por cor.</strong> Anexe todas aqui. Só avance para aprovação quando cada cor tiver arquivo.</div>{c.variants?.length>0?<VariantList variants={c.variants} images={c.assets} onError={onError} focus="image" onUpload={onUpload} busy={busy} disabled={immutable} immutable={immutable}/>:<>{editor('image','Prompt de imagem')}<AssetView asset={reference} title="Referência fixa da modelo para anexar" compact/><ProductGallery photos={c.product_assets}/>{service('image')}<Uploader kind="image" exists={!!image} busy={busy} disabled={immutable} onUpload={onUpload}/></>}<AssetView asset={reference} title="Referência fixa da modelo para anexar" compact/><ProductGallery photos={c.product_assets}/>{service('image')}</>:<div className="notice">Anexe a referência e gere os prompts na etapa Definir look.</div>}</>;
  if(selected==='image_approval')return <>{c.assets.filter(a=>a.kind==='image').length?<><div className="notice">Confira cada cor. A aprovação libera os roteiros de 15s personalizados por imagem.</div><div className="comparison-grid">{c.assets.filter(a=>a.kind==='image').map(img=><div key={img.id} className="comparison-card"><span>{img.slot||img.metadata?.color||'Imagem'}</span><AssetView asset={img} title={img.slot||'Imagem'} compact/>{img.approved_at&&<p className="approved-label"><Check size={14}/>Aprovada</p>}</div>)}</div><div className="comparison"><div><span>Referência</span><AssetView asset={reference} title="Modelo fixa" compact/></div></div>{c.assets.filter(a=>a.kind==='image').every(a=>a.approved_at)?<div className="notice success"><Check size={17}/> Todas as imagens aprovadas.</div>:<><h3>Confira antes de aprovar</h3>{check('identity','Rosto, cabelo, corpo e tom de pele correspondem à referência em todas as cores.')}{check('look','Roupa, cor, produto e mãos estão corretos em cada imagem.')}<button className="primary full" disabled={busy||c.status!=='image_ready'||!checks.identity||!checks.look} onClick={()=>onTransition('image_approved')}><Check size={17}/> Aprovar todas as imagens</button>{c.status!=='image_ready'&&<small className="help">Anexe a imagem de cada cor na etapa Criar imagem.</small>}</>}</>:<div className="notice">Anexe o resultado de cada cor na etapa Criar imagem.</div>}</>;
  if(selected==='script')return <>{(c.variants?.length>0||c.prompts.hook)?<>{c.variants?.length>0?<VariantList variants={c.variants} onError={onError} focus="script" onSaveVariant={onSaveVariant} onRefreshVariant={onRefreshVariant} busy={busy} immutable={immutable}/>:<ScriptEditor c={c} busy={busy} onDirty={onDirty} onError={onError} onSave={onSaveTexts}/>}<div className="notice">Leia em voz alta. Se a fala não servir, use <strong>Atualizar hook + legenda</strong> ou <strong>Atualizar fala inteira</strong>.</div>{index>=3?<p className="approved-label"><Check size={16}/>Roteiro revisado</p>:<>{check('script','Revisei as falas de cada cor, o benefício e a duração de 15 segundos.')}<button className="primary full" disabled={busy||c.status!=='image_approved'||!checks.script} onClick={()=>onTransition('script_ready')}>Concluir roteiros <ArrowRight size={16}/></button>{index<2&&<small className="help">Aprove as imagens para concluir o roteiro.</small>}</>}</>:<div className="notice">Gere os textos na etapa Definir look.</div>}</>;
  if(selected==='video')return <>{index>=3?<><div className="notice"><strong>Um vídeo por cor.</strong> Anexe todos os MP4 de 15s. Use a imagem da mesma cor como referência.</div>{service('video')}{!immutable&&onMixVideos&&<VideoMixer c={c} busy={busy} immutable={immutable} onError={onError} onMix={onMixVideos}/>}{c.variants?.length>0?<VariantList variants={c.variants} images={c.assets} videos={c.assets} onError={onError} focus="video" onUpload={onUpload} busy={busy} disabled={immutable} immutable={immutable}/>:<>{editor('video','Prompt de vídeo')}<AssetView asset={image} title="Imagem aprovada para anexar" compact/><Uploader kind="video" exists={!!video} busy={busy} disabled={immutable} onUpload={onUpload}/></>}<div className="notice">Exporte cada vídeo com 15 segundos em {c.generator==='flow'?'1080 × 1920':'720 × 1280'}.</div></>:<div className="notice">Aprove as imagens e conclua o roteiro antes de criar o vídeo.</div>}</>;
  if(selected==='video_approval')return <>{c.assets.filter(a=>a.kind==='video').length?<><div className="notice">Confira cada cor. A aprovação exige 15s e a resolução do gerador em todos os vídeos.</div><div className="comparison-grid">{c.assets.filter(a=>a.kind==='video').map(vid=><div key={vid.id} className="comparison-card"><span>{vid.slot||vid.metadata?.color||'Vídeo'}</span><AssetView asset={vid} title={vid.slot||'Vídeo'} compact/>{vid.approved_at&&<p className="approved-label"><Check size={14}/>Aprovado</p>}</div>)}</div>{c.assets.filter(a=>a.kind==='video').every(a=>a.approved_at)?<div className="notice success"><Check size={16}/>Todos os vídeos aprovados.</div>:<><p>Alvo: 15 segundos · {c.generator==='flow'?'1080 × 1920':'720 × 1280'} · MP4.</p>{check('visual','Assisti a todos os vídeos. Identidade, look, produto e movimentos estão corretos em cada cor.')}{check('audio','Revisei áudio, falas, sincronização e duração em cada cor.')}<button className="primary full" disabled={busy||c.status!=='video_ready'||!checks.visual||!checks.audio} onClick={()=>onTransition('video_approved')}><Check size={17}/> Aprovar todos os vídeos</button>{c.status!=='video_ready'&&<small className="help">Anexe o vídeo de cada cor na etapa Criar vídeo.</small>}</>}</>:<div className="notice">Anexe o MP4 de cada cor na etapa Criar vídeo.</div>}</>;
  return <>{index<5?<div className="notice">Aprove o vídeo antes de preparar a publicação.</div>:<>{c.status==='video_approved'&&<button className="primary full" disabled={busy} onClick={()=>onTransition('ready_to_publish')}>Preparar publicação <ArrowRight size={17}/></button>}{index>=6&&<PublishQueue c={c} busy={busy} immutable={immutable} onError={onError} onOpen={onOpen} onPublishSlot={onPublishSlot} onMixVideos={mixVideos} onRefreshVariant={onRefreshVariant}/>}{c.status==='video_approved'&&<div className="notice">Depois de preparar, você escolhe cada cor/produto para subir no Studio.</div>}</>}</>;
}

function ScriptEditor({c,busy,onDirty,onError,onSave}){
  const [draft,setDraft]=useState({hook:c.prompts.hook,development:c.prompts.development,cta:c.prompts.cta});
  const fields=[['hook','Hook','0–2s'],['development','Desenvolvimento','2–12s'],['cta','Chamada para ação','12–15s']];
  const changed=Object.keys(draft).some(k=>draft[k]!==c.prompts[k]);
  return <div className="script-editor">{fields.map(([key,title,time])=><section className="script-part" key={key}><div className="section-title"><div><span className="time-label">{time}</span><h3>{title}</h3></div><CopyButton text={draft[key]} onError={onError}/></div><textarea aria-label={title} value={draft[key]} readOnly={c.status==='published'} rows={3} maxLength={12000} onChange={e=>{setDraft(d=>({...d,[key]:e.target.value}));onDirty(true)}}/></section>)}{changed&&<button className="full" disabled={busy||Object.values(draft).some(v=>!v.trim())} onClick={()=>onSave(draft)}>Salvar roteiro</button>}<div className="script-word-count">{Object.values(draft).join(' ').trim().split(/\s+/).length} palavras · confirme o tempo com uma leitura</div></div>;
}

