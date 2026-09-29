import { getDeviceInfo } from './device';
import { ServiceLaunch, TikTokLaunchButtons, isMobileDevice, mobileServiceUrl, setCloudMode, isCloudMode } from './serviceLinks';
import { useEffect, useRef, useState } from 'react';
import { Smartphone, Monitor, Tablet, Plus, ArrowRight, Download, FolderHeart, Check, ArrowLeft, ExternalLink, RefreshCw, AlertCircle, X, ShieldCheck, Copy as CopyIcon, Pencil, Trash2, UserCog, Sparkles, Wand2, Clapperboard, LogOut, UserPlus, KeyRound, Users } from 'lucide-react';
import Canvas from './Canvas';
import { api, health, openBrowserFree, states, statusLabels, stageInfo, produceStages, nextStage, studioAudit, studioIdentity, uploadAssetDirect, uploadProductPhotosDirect, uploadModelLibraryPhotoDirect, analyzeProductPhotoLocal, analyzeProductPhotoDirect } from './api';
import {Dialog, BriefForm, CopyButton, AssetView, Uploader, DeviceVideoPicker, DeviceVideoCard, TextEditor, ProductGallery, VariantList, PublishQueue, VideoMixer, VideoTimelinePreview, PerformancePanel, ModelLibraryPanel, StudioIdentityPanel, WriterSettingsPanel, NICHES, ResultsQuickTools, readStoredModel, PromptScore} from './components';
import { NICHE_DEFAULTS } from './nicheDefaults';


function BrandMark({kind='grok', size=22, tone='auto'}){
  // Os logos ficam em public/brand (os mesmos arquivos que antes vinham
  // escritos por extenso aqui dentro, pesando ~15 KB a mais no app).
  const labsSrc = '/brand/labs.png';
  const grokDark = '/brand/grok-mark.png';
  const grokLight = '/brand/grok-mark-white.png';
  if(kind==='labs'||kind==='flow'){
    return <img className="brand-mark brand-labs" src={labsSrc} alt="" width={size} height={size} draggable={false}/>;
  }
  const src = (tone==='light'||tone==='white') ? grokLight : grokDark;
  return <img className="brand-mark brand-grok" src={src} alt="" width={size} height={size} draggable={false}/>;
}

export default function App(){
  const [campaigns,setCampaigns]=useState([]),[c,setC]=useState(null),[references,setReferences]=useState([]);
  const [selected,setSelected]=useState('model'),[loading,setLoading]=useState(true),[busy,setBusy]=useState(false);
  const [studioAuditReport,setStudioAuditReport]=useState(null);
  const [mode,setMode]=useState('home'); // home | produce | results
  const [homeView,setHomeView]=useState('ativas'); // ativas | publicadas (so no Inicio)
  const [resultsTab,setResultsTab]=useState('agora'); // agora | studio | lote | playbook | historico | campanha
  const bootHash=useRef(true);
  const [error,setError]=useState(''),[notice,setNotice]=useState(''),[modal,setModal]=useState(null),[dirty,setDirty]=useState(false);
  const [renaming,setRenaming]=useState(false),[renameDraft,setRenameDraft]=useState('');
  const [showCampaignList,setShowCampaignList]=useState(false);
  const [identity,setIdentity]=useState(null);
  const [auth,setAuth]=useState(null);
  const [writerRevision,setWriterRevision]=useState(0);
  const [lanUrls,setLanUrls]=useState([]),[lanPin,setLanPin]=useState('');
  const [deviceFiles,setDeviceFiles]=useState({});
  const lock=useRef(false),noticeTimer=useRef();
  useEffect(()=>{
    let active=true;
    (async()=>{try{
      const authState=await api('/auth/session');
      if(active)setAuth(authState);
      if(authState.required&&!authState.authenticated)return;
      const [list,refs,ident,h]=await Promise.all([api('/campaigns'),api('/references'),studioIdentity().catch(()=>null),health().catch(()=>null)]);
      if(ident) setIdentity(ident);
      if(h?.lan_urls?.length) setLanUrls(h.lan_urls);
      setCloudMode(h?.cloud===true);
      // O PIN da rede local so existe na versao do computador; na nuvem o
      // pedido sempre falharia e so atrasaria a abertura.
      if(h?.cloud!==true) api('/lan-pin').then(d=>setLanPin(d?.pin||'')).catch(()=>{});
      const route=parseRoute();
      // Quando o endereco ja aponta uma campanha, abre so ela (antes a primeira
      // da lista era baixada e descartada logo em seguida).
      const first=!route.campaignId&&list[0]?await api('/campaigns/'+list[0].id):null;
      if(active){
        setCampaigns(list);setReferences(refs);
        let camp=first;
        let notFound=false;
        if(route.campaignId){
          const hit=list.find(x=>x.id===route.campaignId);
          if(hit){try{camp=await api('/campaigns/'+hit.id)}catch(e){camp=null;notFound=true}}
          else{camp=null;notFound=true}
        }
        setC(camp);
        if(camp){
          if(route.mode==='produce'&&route.stage&&produceStages.some(s=>s.id===route.stage)) setSelected(route.stage);
          else setSelected(nextStage(camp)==='performance'?'studio':(nextStage(camp)||'model'));
        }
        setMode(notFound?'home':route.mode);
        setHomeView(route.homeView||'ativas');
        setResultsTab(route.resultsTab||'studio');
        if(location.pathname==='/creator')setModal({type:'create'});
        if(notFound){
          setError(`Campanha ${route.campaignId} não encontrada. Mostrando a lista de campanhas.`);
          try{history.replaceState(null,'','#/inicio')}catch(e){location.hash='/inicio'}
        }
        bootHash.current=false;
      }
    }catch(e){if(active)setError(e.message)}finally{if(active)setLoading(false)}})();
    return()=>{active=false;clearTimeout(noticeTimer.current)};
  },[]);
  useEffect(()=>{const prevent=e=>{if(dirty){e.preventDefault();e.returnValue=''}};window.addEventListener('beforeunload',prevent);return()=>window.removeEventListener('beforeunload',prevent)},[dirty]);

  function parseRoute(){
    const raw=(location.hash||'#/inicio').replace(/^#\/?/,'').replace(/\/$/,'');
    const parts=raw.split('/').filter(Boolean);
    const top=(parts[0]||'inicio').toLowerCase();
    if(top==='produzir'||top==='produce'){
      const cid=parts[1]&&/^\d+$/.test(parts[1])?Number(parts[1]):null;
      const stage=parts[2]||null;
      return {mode:'produce', resultsTab:'studio', campaignId:cid, stage};
    }
    if(top==='resultados'||top==='results'){
      const tab=(parts[1]||'studio').toLowerCase();
      const allowed=new Set(['agora','studio','lote','playbook','historico','campanha']);
      const cid=parts[2]&&/^\d+$/.test(parts[2])?Number(parts[2]):null;
      return {mode:'results', resultsTab:allowed.has(tab)?tab:'agora', campaignId:cid, stage:null};
    }
    // #/publicadas: pagina so com as campanhas ja publicadas, para o Inicio
    // mostrar apenas o que ainda esta em andamento.
    return {mode:'home', homeView:top==='publicadas'?'publicadas':'ativas', resultsTab:'studio', campaignId:null, stage:null};
  }
  function syncHash(next={}){
    const m=next.mode??mode;
    const tab=next.resultsTab??resultsTab;
    const cid=next.campaignId!==undefined?next.campaignId:(c?.id||null);
    const stage=next.stage!==undefined?next.stage:selected;
    let path=(next.homeView??homeView)==='publicadas'?'#/publicadas':'#/inicio';
    if(m==='produce'){
      path='#/produzir'+(cid?`/${cid}`:'')+(cid&&stage&&stage!=='performance'?`/${stage}`:'');
    }else if(m==='results'){
      path='#/resultados/'+tab+(cid&&tab==='campanha'?`/${cid}`:'');
    }
    if(location.hash!==path){
      try{history.replaceState(null,'',path)}catch(e){location.hash=path.slice(1)}
    }
  }
  function goMode(m, tab){
    if(busy)return;
    if(!discard())return;
    if(m==='produce'&&!c){setMode('home');syncHash({mode:'home'});return}
    setMode(m);
    if(m==='results'){
      const rt=tab||resultsTab||'studio';
      setResultsTab(rt);
      setSelected('performance');
      syncHash({mode:'results', resultsTab:rt, campaignId:c?.id||null});
    }else if(m==='produce'){
      if(selected==='performance')setSelected(nextStage(c)==='performance'?'studio':(nextStage(c)||'studio'));
      syncHash({mode:'produce', campaignId:c?.id||null, stage:selected});
    }else{
      // O botao Inicio do topo sempre volta para as campanhas em andamento.
      setHomeView('ativas');
      syncHash({mode:'home',homeView:'ativas'});
    }
    setError('');
  }
  function goHomeView(view){
    if(busy||!discard())return;
    setMode('home');setHomeView(view);setError('');
    syncHash({mode:'home',homeView:view});
    window.scrollTo(0,0);
  }

  
  useEffect(()=>{
    if(loading||bootHash.current)return;
    syncHash({});
  },[mode,homeView,resultsTab,c?.id,selected,loading]);
  // Rede de seguranca: se por algum motivo "selected" ficar com um valor que
  // nao existe em stageInfo (ex: link direto com etapa invalida, ou estado
  // que sobrou de outra campanha), a tela de Produzir travava em branco ao
  // tentar ler stage.title. Em vez de travar, volta pra uma etapa valida.
  useEffect(()=>{
    if(loading||mode!=='produce'||!c)return;
    if(!stageInfo.some(s=>s.id===selected)){
      setSelected(nextStage(c)==='performance'?'studio':(nextStage(c)||'model'));
    }
  },[loading,mode,c,selected]);
  useEffect(()=>{
    function onHash(){
      if(busy||!discard()) { syncHash({}); return; }
      const route=parseRoute();
      setMode(route.mode);
      setHomeView(route.homeView||'ativas');
      setResultsTab(route.resultsTab||'studio');
      if(route.mode==='produce'&&route.stage&&produceStages.some(s=>s.id===route.stage)) setSelected(route.stage);
      if(route.campaignId&&c?.id!==route.campaignId){
        const hit=campaigns.find(x=>x.id===route.campaignId);
        const naoEncontrada=()=>{
          setError(`Campanha ${route.campaignId} não encontrada. Mostrando a lista de campanhas.`);
          setC(null);setMode('home');
          try{history.replaceState(null,'','#/inicio')}catch(e){location.hash='/inicio'}
        };
        if(hit){ api('/campaigns/'+hit.id).then(result=>{setC(result); if(route.mode==='produce'){const st=route.stage||nextStage(result); setSelected(st==='performance'?'studio':st)}}).catch(naoEncontrada); }
        else{ naoEncontrada(); }
      }
    }
    window.addEventListener('hashchange', onHash);
    return ()=>window.removeEventListener('hashchange', onHash);
  },[busy,dirty,campaigns,c?.id]);

  function flash(text){setNotice(text);clearTimeout(noticeTimer.current);noticeTimer.current=setTimeout(()=>setNotice(''),7000)}
  function discard(){if(!dirty)return true;if(window.confirm('Há alterações sem salvar. Deseja descartá-las?')){setDirty(false);return true}return false}
  async function refresh(){const [list,refs]=await Promise.all([api('/campaigns'),api('/references')]);setCampaigns(list);setReferences(refs)}
  async function run(action,message='Salvo localmente.',next){
    if(lock.current)return false;
    lock.current=true;setBusy(true);setError('');
    // O painel remonta a cada gravacao (a chave inclui a versao da campanha),
    // o que garante texto sempre atual mas jogava o scroll de volta ao topo.
    const scroller=document.querySelector('.inspector');
    const keepScroll=scroller?scroller.scrollTop:0;
    try{const result=await action();if(result?.id){setC(result);setDirty(false);if(next)setSelected(next)}await refresh();flash(message);return true}
    catch(e){setError(e.message);return false}
    finally{
      lock.current=false;setBusy(false);
      if(keepScroll>0&&!next){
        requestAnimationFrame(()=>{const el=document.querySelector('.inspector');if(el)el.scrollTop=keepScroll});
      }
    }
  }
  function choose(stage){if(!busy&&discard()){if(stage==='performance'){setMode('results');setSelected('performance');setError('');return}setMode('produce');setSelected(stage);setError('')}}
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

  
  async function createFromPlaybook(indexOrItem){
    if(busy)return;
    setBusy(true);setError('');
    try{
      const body = typeof indexOrItem==='number' ? {index:indexOrItem} : {item:indexOrItem};
      const created = await api('/studio/playbook/campaign',{method:'POST',body});
      await refresh();
      setC(created);
      setMode('produce');
      setSelected('look');
      syncHash({mode:'produce', campaignId:created.id, stage:'look'});
      flash('Campanha criada do playbook. Complete cores/produto e gere os textos.');
    }catch(e){setError(e.message||String(e))}
    finally{setBusy(false)}
  }

  async function openResults(){goMode('results','campanha')}
  function openProduce(){goMode('produce')}
  async function chooseCampaign(id,{openResults=false}={}){if(busy||!discard())return;setShowCampaignList(false);await run(async()=>{const result=await api('/campaigns/'+id);if(openResults){setMode('results');setResultsTab('campanha');setSelected('performance');syncHash({mode:'results',resultsTab:'campanha',campaignId:result.id})}else{setMode('produce');const st=nextStage(result);setSelected(st==='performance'?'studio':st);syncHash({mode:'produce',campaignId:result.id,stage:st==='performance'?'studio':st})}return result},'Campanha carregada.')}
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
  const ANALYSIS_FIELD_LABELS={benefit:'Benefício',angle:'Ângulo',movements:'Movimentos',details:'Detalhes'};
  const ENRICHABLE_FIELDS=['benefit','angle','movements','details'];
  function saveBrief(values,photos=[],removed=[],descriptionPhoto=null){
    const next=(c.assets.some(a=>a.kind==='reference')&&values.model_name===c.model_name)?'look':'model';
    let analysisOutcome=null;
    // Mesma regra da criacao: com foto de descricao anexada, deixa ela
    // ganhar de beneficio/angulo/movimentos/detalhes quando esses campos
    // ainda estao com o texto generico do nicho; o nicho so volta como
    // reserva depois, pro que a IA nao conseguir preencher.
    const nicheDefaults=NICHE_DEFAULTS[values.niche]||{};
    const submitValues={...values};
    if(descriptionPhoto){
      ENRICHABLE_FIELDS.forEach(k=>{
        if(nicheDefaults[k]&&(submitValues[k]||'')===nicheDefaults[k])submitValues[k]='';
      });
    }
    const action=()=>run(async()=>{
      let result;
      if(photos.length||removed.length){
        const briefing={...submitValues,version:c.version};
        result=isCloudMode()?await uploadProductPhotosDirect(c.id,briefing,removed,photos):await(async()=>{
          const form=new FormData();form.set('briefing',JSON.stringify(briefing));form.set('removed',JSON.stringify(removed));photos.forEach(file=>form.append('files',file));
          return api(`/campaigns/${c.id}/look`,{method:'POST',body:form});
        })();
      }else{
        result=await api(`/campaigns/${c.id}`,{method:'PATCH',body:{...submitValues,version:c.version}});
      }
      if(descriptionPhoto){
        const fillFromNiche=async()=>{
          const fallback={};
          ENRICHABLE_FIELDS.forEach(k=>{ if(nicheDefaults[k]&&!(result[k]||'').trim())fallback[k]=nicheDefaults[k]; });
          if(Object.keys(fallback).length){
            result=await api(`/campaigns/${result.id}`,{method:'PATCH',body:{...fallback,version:result.version}});
          }
        };
        try{
          result=isCloudMode()?await analyzeProductPhotoDirect(result.id,descriptionPhoto):await analyzeProductPhotoLocal(result.id,descriptionPhoto);
          analysisOutcome={filled:result.analysis?.filled||[]};
          await fillFromNiche();
        }catch(e){
          analysisOutcome={error:e.message};
          await fillFromNiche();
        }
      }
      return result;
    },'Briefing e fotos do produto salvos.',next).then(ok=>{
      if(ok&&analysisOutcome){
        if(analysisOutcome.error)setError(`Briefing e fotos salvos, mas a análise da IA da foto de descrição falhou: ${analysisOutcome.error}`);
        else if(analysisOutcome.filled.length)flash(`Briefing salvo. A IA leu a foto da descrição e preencheu: ${analysisOutcome.filled.map(k=>ANALYSIS_FIELD_LABELS[k]||k).join(', ')}.`);
        else flash('Briefing e fotos salvos. A IA não encontrou nada de novo pra preencher com a foto da descrição.');
      }
      return ok;
    });
    const changed=photos.length||removed.length||!!descriptionPhoto||Object.keys(submitValues).some(k=>k!=='name'&&submitValues[k]!==(c[k]||''));
    if(changed&&c.prompts.image)confirm('Iniciar uma nova versão?','A alteração do briefing retira as mídias do fluxo atual e solicita novas aprovações. Os arquivos anteriores ficam guardados na pasta da campanha.',action,'Salvar e reiniciar');else action();
  }
  function saveTexts(values){
    const action=()=>run(()=>api(`/campaigns/${c.id}/prompts`,{method:'PATCH',body:{prompts:values,version:c.version}}),'Textos salvos.');
    if(c.status!=='briefing')confirm('Salvar a revisão do texto?','Alterar o prompt da imagem reinicia a produção. Alterar o roteiro refaz o prompt de vídeo com as novas falas. Alterar roteiro ou prompt de vídeo exige um novo vídeo. Alterar a legenda pede nova preparação da publicação.',action,'Salvar revisão');else action();
  }
  function upload(kind,file,color){
    if(!discard())return;
    if(file.size>(kind==='video'?250:40)*1024*1024){setError('Arquivo acima do limite permitido.');return}
    const action=()=>{
      const stay=kind==='image'?'image':kind==='video'?'video':'look';
      // Na nuvem, o arquivo vai direto pro Supabase Storage (o navegador nao
      // manda mais pro nosso servidor) - contorna o limite de 4,5 MB por
      // requisicao das funcoes do Vercel. No computador, continua igual.
      const doUpload=()=>{
        if(isCloudMode()){
          const extra=color?{color,version:c.version}:{version:c.version};
          return uploadAssetDirect(c.id,kind,file,extra);
        }
        const form=new FormData();form.set('kind',kind);form.set('file',file);form.set('version',c.version);if(color)form.set('color',color);
        return api(`/campaigns/${c.id}/assets`,{method:'POST',body:form});
      };
      return run(doUpload,color?`Imagem ${color} salva.`:'Mídia salva localmente.',stay);
    };
    const existsSame=c.assets.some(a=>a.kind===kind && (!color || a.slot===color || a.metadata?.color===color));
    if(existsSame)confirm('Substituir esta mídia?',color?`Substituir a imagem da cor ${color}? A versão anterior continua guardada localmente.`:'A nova mídia precisa ser revisada e invalida as etapas seguintes. A versão anterior continua guardada localmente.',action,'Substituir');else action();
  }
  function inspectVideo(file){
    return new Promise((resolve,reject)=>{
      const url=URL.createObjectURL(file);
      const probe=document.createElement('video');
      probe.preload='metadata';
      probe.onloadedmetadata=()=>{
        const metadata={duration:Number(probe.duration.toFixed(3)),width:probe.videoWidth,height:probe.videoHeight};
        URL.revokeObjectURL(url);resolve(metadata);
      };
      probe.onerror=()=>{URL.revokeObjectURL(url);reject(new Error('Não foi possível ler este MP4 no navegador.'))};
      probe.src=url;
    });
  }
  async function registerDeviceVideo(file,color=''){
    if(!c||busy)return false;
    if(file.size>250*1024*1024){setError('O vídeo deve ter até 250 MB.');return false}
    if(!file.name.toLowerCase().endsWith('.mp4')){setError('Selecione um vídeo MP4.');return false}
    try{
      const metadata=await inspectVideo(file);
      const ok=await run(()=>api(`/campaigns/${c.id}/device-video`,{method:'POST',body:{
        version:c.version,color,original_name:file.name,mime:file.type||'video/mp4',size:file.size,metadata,
      }}),'Vídeo validado. O arquivo continua somente neste dispositivo.','video_approval');
      if(ok){
        const url=URL.createObjectURL(file);
        setDeviceFiles(old=>{
          const campaign={...(old[c.id]||{})};
          if(campaign[color]?.url)URL.revokeObjectURL(campaign[color].url);
          campaign[color]={file,url,metadata};
          return {...old,[c.id]:campaign};
        });
      }
      return ok;
    }catch(e){setError(e.message||String(e));return false}
  }
  async function logout(){
    try{await api('/auth/logout',{method:'POST',body:{}});location.reload()}catch(e){setError(e.message)}
  }
  function saveVariantPrompts(variantId,prompts){
    return run(()=>api(`/campaigns/${c.id}/variants/${variantId}/prompts`,{method:'PATCH',body:{prompts,version:c.version}}),'Roteiro da cor atualizado.');
  }
  function refreshSingleScript(fields,options={}){
    if(dirty){setError('Salve as alterações do roteiro antes de gerar outras frases.');return}
    const list = Array.isArray(fields) ? fields : ['hook','caption'];
    const onlyCaption = list.length === 1 && list[0] === 'caption';
    if(onlyCaption){
      // Studio: swap caption only — stay on publish step, no roteiro rewind.
      return run(()=>post('/prompts/refresh',{fields:list,writer_mode:options.writerMode||'local'}),'Nova legenda gerada.','studio');
    }
    const byAI=options.writerMode==='ai';
    const action=()=>run(()=>post('/prompts/refresh',{fields:list,writer_mode:options.writerMode||'local'}),byAI?'Novo roteiro gerado pelo ChatGPT. Revise as falas.':'Novas frases locais geradas. Revise o roteiro.','script');
    if(states.indexOf(c.status)>=3)confirm(byAI?'Gerar novo roteiro com ChatGPT?':'Gerar novas frases locais?','A imagem aprovada será mantida. O roteiro e o vídeo precisarão de nova revisão.',action,byAI?'Gerar com ChatGPT':'Gerar frases');else action();
  }
  function refreshVariant(variantId,fields,options={}){
    const list = Array.isArray(fields) ? fields : ['hook','caption'];
    const onlyCaption = list.length === 1 && list[0] === 'caption';
    return run(
      ()=>api(`/campaigns/${c.id}/variants/${variantId}/refresh`,{method:'POST',body:{fields:list,writer_mode:options.writerMode||'local',version:c.version}}),
      onlyCaption ? 'Nova legenda gerada.' : options.writerMode==='ai'?'Roteiro desta cor gerado pelo ChatGPT.':'Nova variação local de fala gerada.',
      onlyCaption ? 'studio' : undefined
    );
  }
  function refreshAllVariants(fields,options={}){
    const list=Array.isArray(fields)?fields:['hook','development','cta'];
    const action=()=>run(
      ()=>api(`/campaigns/${c.id}/variants/refresh-all`,{method:'POST',body:{fields:list,writer_mode:options.writerMode||'ai',version:c.version}}),
      `Roteiros de ${c.variants?.length||0} cores gerados pelo ChatGPT. Revise as falas.`,
      'script'
    );
    if(states.indexOf(c.status)>=3){
      confirm('Gerar novos roteiros para todas as cores?','As imagens aprovadas serão mantidas. As falas e os vídeos de todas as cores precisarão de nova revisão.',action,'Gerar todas as cores');
    }else action();
  }
  function refreshVideoPrompt(variantId=null){
    const variant=variantId?c.variants?.find(item=>item.id===variantId):null;
    const slot=variant?.color||'';
    const hasVideo=(c.assets||[]).some(a=>a.kind==='video'&&(a.slot||a.metadata?.color||'')===slot)
      ||(c.device_videos||[]).some(a=>(a.slot||'')===slot);
    const endpoint=variantId
      ?`/campaigns/${c.id}/variants/${variantId}/refresh-video`
      :`/campaigns/${c.id}/prompts/refresh-video`;
    const action=()=>run(
      ()=>api(endpoint,{method:'POST',body:{version:c.version}}),
      c.generator==='grok'?'Prompt de vídeo recriado dentro do limite de 4.000 caracteres.':'Prompt de vídeo recriado.',
      // Ja estando na etapa de video, nao "navega" de novo: assim a rolagem
      // fica onde estava, no prompt que acabou de ser recriado.
      selected==='video'?undefined:'video'
    );
    if(hasVideo){
      confirm('Recriar o prompt de vídeo?',`O vídeo${slot?` da cor ${slot}`:''} já anexado será removido porque precisará ser gerado novamente. A imagem e o roteiro serão preservados.`,action,'Recriar prompt');
    }else action();
  }
  function improveVideoPrompt(variantId=null){
    const variant=variantId?c.variants?.find(item=>item.id===variantId):null;
    const slot=variant?.color||'';
    const hasVideo=(c.assets||[]).some(a=>a.kind==='video'&&(a.slot||a.metadata?.color||'')===slot)
      ||(c.device_videos||[]).some(a=>(a.slot||'')===slot);
    const endpoint=variantId
      ?`/campaigns/${c.id}/variants/${variantId}/improve-video`
      :`/campaigns/${c.id}/prompts/improve-video`;
    const action=()=>run(
      ()=>api(endpoint,{method:'POST',body:{version:c.version}}),
      'Prompt de vídeo melhorado: versão curta e descritiva. "Recriar prompt" volta ao completo.',
      selected==='video'?undefined:'video'
    );
    if(hasVideo){
      confirm('Melhorar o prompt de vídeo?',`O vídeo${slot?` da cor ${slot}`:''} já anexado será removido porque precisará ser gerado novamente. A imagem e o roteiro serão preservados.`,action,'Melhorar prompt');
    }else action();
  }
  function mixVideos(payload){
    return run(()=>api(`/campaigns/${c.id}/videos/mix`,{method:'POST',body:{...payload,version:c.version}}),'Mix gerado. Revise o MP4 no slot escolhido.','video');
  }
  function savePerformance(payload){
    return run(()=>api(`/campaigns/${c.id}/performance`,{method:'POST',body:{...payload,version:c.version}}),'Métricas salvas.','studio');
  }
  function saveExperiment(experiment){
    return run(()=>api(`/campaigns/${c.id}/experiment`,{method:'POST',body:{experiment,version:c.version}}),'Teste marcado.','performance');
  }
  function generateInsights(payload={}){
    return run(()=>api(`/campaigns/${c.id}/insights`,{method:'POST',body:{...payload,version:c.version}}),'Insights gerados.','studio');
  }
  function gotoScript(){choose('script')}
  async function auditStudioPosts(){
    if(lock.current)return false;
    lock.current=true;setBusy(true);setError('');
    try{
      const result=await studioAudit({limit:8,viewers_top:3});
      setStudioAuditReport(result);
      flash(result?.message||'Auditoria dos publicados pronta.');
      setSelected('performance');
      return true;
    }catch(e){setError(e.message);return false}
    finally{lock.current=false;setBusy(false)}
  }
  function applyLibraryReference(niche){
    return run(()=>api(`/campaigns/${c.id}/reference-from-library`,{method:'POST',body:{niche,version:c.version}}),'Foto padrão do nicho aplicada.','model');
  }
  function saveNichePhoto(niche,file){
    if(!file)return;
    const modelName=c.model_name||identity?.model_name||'Micaela';
    if(isCloudMode())return run(()=>uploadModelLibraryPhotoDirect(modelName,niche,file),'Foto padrão do nicho salva.');
    const form=new FormData();form.set('model_name',modelName);form.set('niche',niche);form.set('file',file);
    return run(()=>api('/model-library',{method:'POST',body:form}),'Foto padrão do nicho salva.');
  }
    function savePublishedLink(payload){
    return run(()=>api(`/campaigns/${c.id}/published-link`,{method:'POST',body:{...payload,version:c.version}}),'Link do TikTok salvo.','performance');
  }
    function fetchStudioMetrics(color){
    return run(()=>api(`/campaigns/${c.id}/performance/fetch`,{method:'POST',body:{color,version:c.version}}),'Métricas coletadas do Studio.','performance');
  }

  function publishSlot(payload){
    return run(()=>api(`/campaigns/${c.id}/publish-slot`,{method:'POST',body:{...payload,version:c.version}}),`Publicação de ${payload.color||'produto'} registrada.`,'studio');
  }
  function transition(target,extra={}){
    if(dirty){setError('Salve os textos alterados antes de avançar.');return}
    return run(()=>post('/transition',{target,confirmed:true,...extra}),'Etapa concluída.',{image_approved:'script',script_ready:'video',video_approved:'studio',ready_to_publish:'studio',published:'studio'}[target]);
  }
  function openFreeService(service,event){
    if(mobileServiceUrl(service))return;
    event?.preventDefault();
    const label = service==='studio'?'TikTok Studio':service==='flow'?'Google Flow (Labs)':'Grok Imagine';
    const account = service==='studio'
      ?(identity?.chrome_profile_hint?`perfil Chrome "${identity.chrome_profile_hint}"`:'perfil Chrome da creator')
      :(service==='grok'?(identity?.grok_account_hint||'conta Grok'):(identity?.flow_account_hint||'conta Flow'));
    confirm(
      `Abrir ${label}?`,
      `Abre no perfil dedicado (${account}), sem campanha. ${service==='studio'?'Studio usa o Chrome da Micaela.':'Grok e Flow abrem como abas na mesma janela do perfil de geracao.'}`,
      ()=>run(async()=>{
        const result = await openBrowserFree(service);
        flash(result.message|| (label+' aberto.'));
        return null;
      }, label+' solicitado.'),'Abrir'
    );
  }
    function openService(service,stage,event){
    if(dirty){event?.preventDefault();setError('Salve o texto antes de abrir o serviço.');return}
    if(mobileServiceUrl(service))return;
    event?.preventDefault();
    const account=service==='studio'
      ?(identity?.chrome_profile_hint?`perfil Chrome "${identity.chrome_profile_hint}"`:'perfil Chrome da creator')
      :(service==='grok'?(identity?.grok_account_hint||'conta Grok configurada'):(identity?.flow_account_hint||'conta Flow configurada'));
    confirm(`Abrir ${service==='studio'?'TikTok Studio':service==='flow'?'Google Flow':'Grok Imagine'}?`,
      `O serviço será aberto no perfil dedicado de ${account}. Confira a conta e faça login manualmente, se necessário. ${service==='grok'?'Grok e Flow abrem como abas na mesma janela do perfil dedicado.':'Cole o texto e anexe o arquivo na página.'} Gerar conteúdo, gastar créditos, selecionar produto e publicar dependem dos seus cliques.`,
      ()=>run(async()=>{const result=await post('/browser',{service,stage,confirmed:true});flash(result.message);return null},'Navegador solicitado. Confira a janela do perfil dedicado.'),'Abrir perfil dedicado');
  }
  async function persistLayout(layout){
    if(busy)return;
    try{await api(`/campaigns/${c.id}/layout`,{method:'PATCH',body:{layout}});setC(old=>({...old,layout}));}catch(e){setError(e.message)}
  }
  if(auth?.required&&!auth.authenticated){
    return <AuthScreen setup={auth.setup_required} onDone={()=>location.reload()}/>;
  }
  const device=getDeviceInfo();
  const DeviceIcon=device.type==='phone'?Smartphone:device.type==='tablet'?Tablet:Monitor;
  const current=c?stageInfo.find(s=>s.id===nextStage(c)):null;
  const activeCampaigns=campaigns.filter(x=>x.status!=='published');
  const publishedCampaigns=campaigns.filter(x=>x.status==='published');
  // Cartao de campanha do Inicio. Na campanha publicada o botao principal e
  // Resultados (lancar metricas), porque a producao dela ja terminou.
  const homeCard=item=>{
    const done=item.status==='published';
    return <article className={'home-card'+(c?.id===item.id?' active':'')} key={item.id}>
      <span className="campaign-id">CAMPANHA {String(item.id).padStart(4,'0')}</span>
      <strong>{item.name}</strong>
      <small>{item.product||item.model_name}</small>
      <span className={'status-pill '+(done?'success':'')}>{statusLabels[item.status]}</span>
      <div className="home-card-actions">
        <button type="button" className={done?'button':'primary'} disabled={busy} onClick={()=>chooseCampaign(item.id)}>Produzir</button>
        <button type="button" className={done?'primary':'button'} disabled={busy} onClick={()=>chooseCampaign(item.id,{openResults:true})}>Resultados</button>
        <button type="button" className="icon-button" title="Editar" aria-label={`Editar ${item.name}`} disabled={busy} onClick={()=>editCampaignById(item.id)}><Pencil size={14}/></button>
        <button type="button" className="icon-button" title="Copiar" aria-label={`Copiar ${item.name}`} disabled={busy} onClick={()=>copyCampaign(item.id)}><CopyIcon size={14}/></button>
        <button type="button" className="icon-button danger-action" title="Excluir" aria-label={`Excluir ${item.name}`} disabled={busy} onClick={()=>deleteCampaign(item.id)}><Trash2 size={14}/></button>
      </div>
    </article>;
  };
  const stage=stageInfo.find(s=>s.id===selected);
  return <><header className="header"><div className="brand"><span className="logo" aria-hidden="true"><Clapperboard size={18}/></span><span>Fábrica TikTok</span><span className="brand-divider"/><span className="workspace-name">{identity?.studio_name||'Estúdio'}</span></div>
    <nav className="mode-nav" aria-label="Navegação principal">
      <button type="button" className={mode==='home'?'active':''} disabled={busy} onClick={()=>goMode('home')}>Início</button>
      <button type="button" className={mode==='produce'?'active':''} disabled={busy||!c} onClick={()=>goMode('produce')}>Produzir</button>
      <button type="button" className={mode==='results'?'active':''} disabled={busy} onClick={()=>goMode('results','agora')}>Resultados</button>
    </nav>
    <div className="header-right">
      {auth?.authenticated&&<button type="button" className="identity-icon-btn" title="Acessos do estúdio" aria-label="Acessos do estúdio" onClick={()=>setModal({type:'users',title:'Acessos do estúdio'})}><Users size={17}/><span className="identity-icon-label">{auth.user.display_name}</span></button>}
      <span className="device-badge" aria-label={`Dispositivo de acesso: ${device.label}`} title={isCloudMode()?`Acessando por ${device.label}. Os dados ficam salvos na nuvem (Supabase).`:`Acessando por ${device.label}. Os dados ficam no computador que executa a fábrica.`}><DeviceIcon size={15} aria-hidden="true"/><span>{device.label}</span></span>
      <button type="button" className="identity-icon-btn" title="Identidade do estúdio" aria-label="Identidade do estúdio" disabled={busy} onClick={()=>{if(!busy)setModal({type:'identity', title:'Identidade do estúdio'})}}>
        <UserCog size={18}/>
        <span className="identity-icon-label">{identity?.model_name||'Identidade'}</span>
      </button>
      <span className="local-badge" title={busy?'Salvando…':(isCloudMode()?'Dados salvos na nuvem':'Dados no computador')}><ShieldCheck size={15} aria-hidden="true"/> <span className="local-badge-text">{busy?'Salvando…':(isCloudMode()?'Dados salvos na nuvem':'Dados no computador')}</span></span>
      {lanUrls[0] && ['localhost','127.0.0.1'].includes(location.hostname) ? <button type="button" className="lan-chip" title="Copia o link pra abrir no celular (mesmo Wi-Fi). Nao mostra o IP na tela." onClick={()=>{navigator.clipboard?.writeText(lanUrls[0]); flash(lanPin?`Link copiado. No celular, o PIN e ${lanPin}.`:'Link do celular copiado. Cole no navegador do phone (mesmo Wi-Fi).')}}>Link do celular</button> : null}
      {lanPin && lanUrls[0] && ['localhost','127.0.0.1'].includes(location.hostname) ? <span className="lan-pin" title="Quem abrir pela rede local precisa digitar este PIN. Fica em data/lan_pin.txt.">PIN {lanPin}</span> : null}
      {auth?.authenticated&&<button type="button" className="icon-button" title="Sair" aria-label="Sair" onClick={logout}><LogOut size={17}/></button>}
    </div></header>
    
    {mode==='home' && homeView==='ativas' && (
    <main className="workspace home-workspace" aria-busy={loading}>
      <section className="home-panel">
        <div className="home-hero">
          <div>
            <span className="eyebrow">{(identity?.studio_name||'ESTÚDIO').toUpperCase()}</span>
            <h1>O que você quer fazer agora?</h1>
            <p className="home-hero-sub">Separe produção e resultados. Escolha uma campanha para continuar, ou veja o que já performou no TikTok.</p>
          </div>
          <div className="home-actions">
            <button type="button" className="primary" disabled={busy||loading} onClick={()=>{if(discard()){setError('');setModal({type:'create'})}}}><Plus size={17}/> Nova campanha</button>
            <button type="button" className="button" disabled={busy} onClick={()=>goMode('results','agora')}>Ir para Resultados</button>
            <button type="button" className="button" disabled={busy||!campaigns.length} onClick={()=>{const pub=campaigns.find(x=>x.status==='published')||campaigns[0]; if(pub) chooseCampaign(pub.id,{openResults:true})}}>Auditar / métricas</button>
          </div>
        </div>

        <div className="home-launchers" aria-label="Atalhos de servicos">
          <span className="home-launchers-label">Abrir serviços</span>
          <div className="home-launchers-row">
            <ServiceLaunch service="grok" className="home-launch-btn is-grok" disabled={busy||loading} onClick={event=>openFreeService('grok',event)} title="Grok Imagine">
              <BrandMark kind="grok" size={20} tone="white"/>
              <span>Grok</span>
            </ServiceLaunch>
            <ServiceLaunch service="flow" className="home-launch-btn is-flow" disabled={busy||loading} onClick={event=>openFreeService('flow',event)} title="Google Flow / Labs">
              <BrandMark kind="labs" size={20}/>
              <span>Flow Labs</span>
            </ServiceLaunch>
            <TikTokLaunchButtons className="home-launch-btn is-studio" bare disabled={busy||loading} onOpenStudio={event=>openFreeService('studio',event)}/>
          </div>
          <small className="help">{isMobileDevice()?'Os serviços abrem neste aparelho. TikTok Studio e TikTok usam o aplicativo TikTok; Flow abre no navegador.':(isCloudMode()?'TikTok Studio e TikTok abrem em novas abas deste navegador.':'TikTok Studio abre no perfil dedicado do Chrome. TikTok abre pelo navegador deste aparelho.')}</small>
        </div>
        {/* No Inicio ficam so as campanhas em andamento (qualquer status que
            nao seja "Publicada"). As publicadas vao para #/publicadas, senao a
            lista cresce a cada video e a pagina fica enorme no celular. */}
        {!loading && campaigns.length>0 && <div className="home-section-title">
          <h2>Em andamento <span className="count">{activeCampaigns.length}</span></h2>
          {publishedCampaigns.length>0&&<button type="button" className="button" disabled={busy} onClick={()=>goHomeView('publicadas')}>Publicadas ({publishedCampaigns.length}) <ArrowRight size={14}/></button>}
        </div>}
        <div className="home-grid">
          {loading && <div className="empty-state"><RefreshCw className="spinning"/><h1>Carregando campanhas…</h1></div>}
          {!loading && !campaigns.length && (
            <div className="empty-state"><div className="empty-icon"><FolderHeart size={34}/></div><h1>Crie sua primeira campanha</h1><p>Do briefing à publicação, depois analise em Resultados.</p><button className="primary" onClick={()=>setModal({type:'create'})}><Plus size={17}/> Nova campanha</button></div>
          )}
          {!loading && campaigns.length>0 && !activeCampaigns.length && (
            <div className="notice home-empty-active">Nenhuma campanha em andamento. Todas já foram publicadas. Crie uma nova campanha ou veja as publicadas.</div>
          )}
          {!loading && activeCampaigns.map(homeCard)}
        </div>
        <ModelLibraryPanel modelName={identity?.model_name||'Micaela'} busy={busy} onError={setError} onFlash={flash}/>
      </section>
    </main>
    )}

    {mode==='home' && homeView==='publicadas' && (
    <main className="workspace home-workspace" aria-busy={loading}>
      <section className="home-panel">
        <button type="button" className="button home-back" disabled={busy} onClick={()=>goHomeView('ativas')}><ArrowLeft size={14}/> Início</button>
        <div className="home-hero">
          <div>
            <span className="eyebrow">CAMPANHAS</span>
            <h1>Publicadas <span className="count">{publishedCampaigns.length}</span></h1>
            <p className="home-hero-sub">Campanhas que já foram ao ar. Abra Resultados para lançar as métricas, ou copie uma para fazer uma nova versão.</p>
          </div>
        </div>
        <div className="home-grid">
          {loading && <div className="empty-state"><RefreshCw className="spinning"/><h1>Carregando campanhas…</h1></div>}
          {!loading && !publishedCampaigns.length && <div className="notice">Nenhuma campanha publicada ainda.</div>}
          {!loading && publishedCampaigns.map(homeCard)}
        </div>
      </section>
    </main>
    )}

{mode==='produce' && (<main className="workspace produce-workspace produce-dense" aria-busy={loading}>
      <aside className={'queue produce-queue'+(c&&!showCampaignList?' queue-collapsed':'')}><div className="queue-heading"><div><span className="eyebrow">PRODUÇÃO</span><h2>Campanhas <span className="count">{campaigns.length}</span></h2></div></div><button className="primary" disabled={busy||loading} onClick={()=>{if(discard()){setError('');setModal({type:'create'})}}}><Plus size={17}/> Nova campanha</button>
        {c&&<button type="button" className="campaign-list-compact" onClick={()=>setShowCampaignList(v=>!v)} aria-expanded={showCampaignList}>
          <span className="campaign-id">CAMPANHA {String(c.id).padStart(4,'0')}</span><strong>{c.name}</strong>
          <span className="campaign-list-compact-toggle">{showCampaignList?'Fechar':'Trocar'} <ArrowRight size={13}/></span>
        </button>}
        <div className="campaign-list">{campaigns.map(item=><div className={'campaign '+(c?.id===item.id?'active':'')} key={item.id}><button className="campaign-select" disabled={busy} onClick={()=>chooseCampaign(item.id)} aria-pressed={c?.id===item.id}><span className="campaign-id">CAMPANHA {String(item.id).padStart(4,'0')}</span><strong>{item.name}</strong><small>{item.product||item.model_name}</small><span className={'status-pill '+(item.status==='published'?'success':'')}>{statusLabels[item.status]}</span></button><div className="campaign-actions"><button type="button" title="Editar campanha" aria-label={`Editar ${item.name}`} disabled={busy} onClick={()=>editCampaignById(item.id)}><Pencil size={14}/></button><button type="button" title="Copiar campanha" aria-label={`Copiar ${item.name}`} disabled={busy} onClick={()=>copyCampaign(item.id)}><CopyIcon size={14}/></button><button type="button" className="danger-action" title="Excluir campanha" aria-label={`Excluir ${item.name}`} disabled={busy} onClick={()=>deleteCampaign(item.id)}><Trash2 size={14}/></button></div></div>)}</div>
        <div className="queue-bottom"><FolderHeart size={20}/><strong>Uma modelo, novos looks.</strong><p>Reutilize a referência para preservar a identidade em cada campanha.</p></div>
      </aside>
      <section className="canvas-panel">{loading?<div className="empty-state"><RefreshCw className="spinning"/><h1>Carregando seu estúdio…</h1></div>:c?<>
        <div className="canvas-header produce-chrome">
          <div className="produce-chrome-main">
            <span className="eyebrow produce-chrome-eyebrow">#{String(c.id).padStart(4,'0')} · {c.model_name} · {c.generator==='flow'?'Flow':'Grok'} · 15s</span>
            {renaming?(
              <div className="campaign-rename">
                <input autoFocus value={renameDraft} disabled={busy} onChange={e=>setRenameDraft(e.target.value)} onKeyDown={e=>{if(e.key==='Enter')saveRename();if(e.key==='Escape')setRenaming(false)}} aria-label="Novo nome da campanha"/>
                <button type="button" className="primary" disabled={busy} onClick={saveRename}>Salvar</button>
                <button type="button" disabled={busy} onClick={()=>setRenaming(false)}>Cancelar</button>
              </div>
            ):(
              <h1 className="campaign-title-row">{c.name}<button type="button" className="icon-button btn-rename" title="Renomear" aria-label="Renomear campanha" disabled={busy} onClick={beginRename}><Pencil size={14}/></button></h1>
            )}
            {/* Lembrete da roupa: a foto de referencia da modelo e a roupa
                padrao que ela veste em todos os videos desta campanha. */}
            <LookReminder c={c}/>
          </div>
          <div className="export-actions produce-chrome-actions">
            <button className="button" onClick={editCampaign} disabled={busy} title={c.status==='published'?'Criar versão editável':'Editar briefing'}><RefreshCw size={14}/> Editar</button>
            <a className="button export-download" href={`/api/campaigns/${c.id}/package.txt`} title="Baixar textos">TXT</a>
            <a className="button export-download" href={`/api/campaigns/${c.id}/package.zip`} title="Baixar pacote"><Download size={14}/> ZIP</a>
            <button type="button" className="button danger-action" onClick={()=>deleteCampaign(c.id)} disabled={busy} title="Excluir campanha" aria-label={`Excluir ${c.name}`}><Trash2 size={14}/> Excluir</button>
            <ServiceLaunch service={c.generator} className={'generator-open-btn compact '+(c.generator==='flow'?'is-flow':'is-grok')} disabled={busy||c.status==='published'} onClick={event=>openService(c.generator, selected==='video'||selected==='video_approval'?'video':'image',event)} title={c.generator==='flow'?'Abrir Flow':'Abrir Grok'}>
              <BrandMark kind={c.generator==='flow'?'labs':'grok'} size={18} tone={c.generator==='flow'?'auto':'white'}/>
              <span className="generator-open-text"><strong>{c.generator==='flow'?'Flow':'Grok'}</strong></span>
            </ServiceLaunch>
          </div>
        </div>
        {c.migration_note&&<div className="migration-note"><AlertCircle size={15}/>{c.migration_note}</div>}
        {/* A faixa "Agora" repetia o titulo da etapa aberta logo abaixo, e o
            botao "Continuar" dela nao fazia nada quando voce ja estava nessa
            etapa. So aparece quando voce olha outra etapa ou a campanha ja foi
            publicada, que e quando o botao leva a algum lugar. */}
        {(c.status==='published'||(current&&current.id!==selected))&&<div className={'produce-toolbar'+(c.status==='published'?' produce-toolbar-done':' produce-toolbar-next')}>
          <div className="produce-toolbar-next">
            <span className="eyebrow">{c.status==='published'?'CONCLUÍDA':'AGORA'}</span>
            <strong>{c.status==='published'?'Publicada':(current?.title||stage?.title||'Continuar')}</strong>
          </div>
          <button type="button" className="button produce-continue" disabled={busy} onClick={()=>c.status==='published'?openPublication():choose(current.id)}>
            {c.status==='published'?'Ver publicação':'Ir para a etapa atual'}<ArrowRight size={14}/>
          </button>
        </div>}
        <Canvas key={c.id} campaign={c} selected={selected} onSelect={choose} busy={busy} stages={produceStages}/>
        </>:<div className="empty-state"><div className="empty-icon"><FolderHeart size={34}/></div><span className="eyebrow">SEU CANVAS DE PRODUÇÃO</span><h1>Crie sua primeira campanha</h1><p>Defina o produto e o look, anexe a modelo e acompanhe cada aprovação até o TikTok.</p><button className="primary" onClick={()=>setModal({type:'create'})}><Plus size={17}/> Nova campanha</button></div>}</section>
      <aside className="inspector"><div className="inspector-heading produce-inspector-head"><div><span className="eyebrow">{c?'ETAPA':'INÍCIO'}</span><h2>{c?(stage?.title||'Etapa'):'Produção'}</h2></div>{c&&<span className="status-pill">{statusLabels[c.status]}</span>}</div>
        {c?<Panel key={`${c.id}-${c.version}-${selected}-${writerRevision}`} c={c} identity={identity} selected={selected} busy={busy} references={references} deviceFiles={deviceFiles[c.id]||{}} onDirty={setDirty} onError={setError} onSaveBrief={saveBrief} onSaveTexts={saveTexts} onUpload={upload} onDeviceVideo={registerDeviceVideo} onTransition={transition} onOpen={openService}
          onGenerate={()=>{if(dirty){setError('Salve o briefing antes de gerar os textos.');return}run(()=>post('/generate'),'Prompts, roteiro e legenda gerados localmente.','image')}}
          onGenerateVariants={generateVariants}
            onSaveVariant={saveVariantPrompts}
            onRefreshVariant={refreshVariant}
            onRefreshAllVariants={refreshAllVariants}
            onRefreshVideoPrompt={refreshVideoPrompt} onImproveVideoPrompt={improveVideoPrompt}
            onRefreshScript={refreshSingleScript}
            onConfigureWriter={()=>setModal({type:'identity',title:'Configurar escrita com ChatGPT'})}
            onPublishSlot={publishSlot}
            onMixVideos={mixVideos}
            onSavePerformance={savePerformance}
            onGenerateInsights={generateInsights}
            onGotoScript={gotoScript}
            onOpenStudio={event=>openService('studio','publish',event)}
            onFetchStudioMetrics={fetchStudioMetrics} onAuditStudioPosts={auditStudioPosts} studioAuditReport={studioAuditReport}
          onApplyLibraryReference={applyLibraryReference} onSaveNichePhoto={saveNichePhoto}
           onReuse={id=>confirm('Reutilizar esta referência?','A mesma imagem será copiada para esta campanha. Esta ação reinicia a produção e as aprovações seguintes.',()=>run(()=>post('/reference',{asset_id:Number(id)}),'Referência reutilizada.','look'),'Usar referência')}/>:<div className="notice">Crie uma campanha, use a referência fixa da modelo e revise imagem e vídeo antes de preparar a publicação.</div>}
      </aside>
    </main>
    )}

    {mode==='results' && (
    <main className="workspace results-workspace" aria-busy={loading}>
      <aside className="queue results-queue">
        <div className="queue-heading"><div><span className="eyebrow">RESULTADOS</span><h2>Campanhas</h2></div></div>
        <div className="campaign-list">{campaigns.map(item=><div className={'campaign '+(c?.id===item.id?'active':'')} key={item.id}><button className="campaign-select" disabled={busy} onClick={()=>chooseCampaign(item.id,{openResults:true})} aria-pressed={c?.id===item.id}><span className="campaign-id">CAMPANHA {String(item.id).padStart(4,'0')}</span><strong>{item.name}</strong><span className={'status-pill '+(item.status==='published'?'success':'')}>{statusLabels[item.status]}</span></button></div>)}</div>
        <button type="button" className="button full" disabled={busy||!c} onClick={()=>openProduce()}>Voltar a Produzir</button>
      </aside>
      <section className="results-panel">
        <nav className="results-subnav" aria-label="Seções de Resultados">
          {[
            ['agora','O que fazer'],
            ['studio','Studio / link'],
            ['lote','Lote 7/15/30'],
            ['playbook','Playbook'],
            ['historico','Histórico'],
            ['campanha','Campanha'],
          ].map(([id,lab])=>(
            <button key={id} type="button" className={resultsTab===id?'active':''} disabled={busy} onClick={()=>goMode('results',id)}>{lab}</button>
          ))}
        </nav>

        {resultsTab!=='campanha' && (
          <ResultsQuickTools busy={busy} onBusy={setBusy} onError={setError} onFlash={flash} tab={resultsTab} onTab={(id)=>goMode('results',id)} onCreateFromPlaybook={createFromPlaybook} onOpenProduce={(id)=>chooseCampaign(id)} onOpenCampaignResults={(id)=>chooseCampaign(id,{openResults:true})}/>
        )}

        {resultsTab==='campanha' && (!c ? (
          <div className="empty-state"><h1>Campanha opcional</h1><p>Escolha uma campanha na lista ao lado, ou use as outras abas (Studio, Lote, Playbook, Histórico) sem campanha.</p><button className="button" onClick={()=>goMode('home')}>Ir ao Início</button></div>
        ) : (
          <>
            <div className="results-header">
              <div>
                <span className="eyebrow">PERFORMANCE · CAMPANHA {String(c.id).padStart(4,'0')}</span>
                <h1>{c.name}</h1>
                <p className="help">Métricas e insights desta campanha, separados da produção.</p>
              </div>
              <div className="export-actions">
                <button type="button" className="button" disabled={busy} onClick={()=>goMode('produce')}>Produzir</button>
                {publicationLinks(c).length>0 && <button type="button" className="button" onClick={openPublication}>Ver publicação</button>}
              </div>
            </div>
            {c.assets.some(a=>a.kind==='video') && <VideoTimelinePreview asset={c.assets.filter(a=>a.kind==='video')[0]} variant={(c.variants||[])[0]} c={c}/>}
            <PerformancePanel c={c} busy={busy} immutable={c.status==='published'} onError={setError} onSavePerformance={savePerformance} onSaveExperiment={saveExperiment} onGenerateInsights={generateInsights} onRefreshVariant={refreshVariant} onGotoScript={()=>{goMode('produce');gotoScript()}} onOpenStudio={event=>openService('studio','publish',event)} onFetchStudioMetrics={fetchStudioMetrics} onAuditStudioPosts={auditStudioPosts} studioAuditReport={studioAuditReport} onSavePublishedLink={savePublishedLink}/>
          </>
        ))}
      </section>
    </main>
    )}

    {error&&<div className="toast error" role="alert"><AlertCircle size={19}/><span>{error}</span><button className="icon-button" onClick={()=>setError('')} aria-label="Fechar erro"><X size={16}/></button><button onClick={()=>{if(discard())location.reload()}}>Recarregar</button></div>}
    {notice&&!error&&<div className="toast" role="status"><Check size={19}/>{notice}</div>}
    {modal&&<Dialog title={modal.type==='create'?'Nova campanha':modal.title} onClose={()=>{if(!busy){setModal(null);setError('')}}}>
      {modal.type==='users'?<UserAccessPanel auth={auth} busy={busy} onError={setError} onFlash={flash}/>:modal.type==='identity'?<><StudioIdentityPanel identity={identity} setIdentity={setIdentity} busy={busy} onError={setError} onFlash={flash} onSaved={()=>setModal(null)}/><WriterSettingsPanel busy={busy} onError={setError} onFlash={flash} onSaved={()=>{setWriterRevision(v=>v+1);setModal(null)}}/></>:modal.type==='create'?<BriefForm busy={busy} campaign={{model_name:readStoredModel()||identity?.model_name||'Micaela'}} onCancel={()=>setModal(null)} onSave={async (values,photos=[],removed=[],descriptionPhoto=null)=>{
        let analysisOutcome=null;
        // Se uma foto de descricao foi anexada, deixa ela "ganhar" de
        // beneficio/angulo/movimentos/detalhes: esses 4 campos, se ainda
        // estiverem com o texto generico do nicho (ninguem editou a mao),
        // vao vazios pro backend, pra IA poder preencher a partir da foto.
        // O texto do nicho so volta como reserva depois, pros campos que
        // a IA nao conseguir preencher (ou se a analise falhar).
        const nicheDefaults=NICHE_DEFAULTS[values.niche]||{};
        const enrichableFields=['benefit','angle','movements','details'];
        const submitValues={...values};
        if(descriptionPhoto){
          enrichableFields.forEach(k=>{
            if(nicheDefaults[k]&&(submitValues[k]||'')===nicheDefaults[k])submitValues[k]='';
          });
        }
        const created=await run(async()=>{
          let result=await api('/campaigns',{method:'POST',body:submitValues});
          if(photos?.length){
            const briefing={...submitValues,version:result.version};
            if(isCloudMode()){
              result=await uploadProductPhotosDirect(result.id,briefing,removed||[],photos);
            }else{
              const form=new FormData();
              form.set('briefing',JSON.stringify(briefing));
              form.set('removed',JSON.stringify(removed||[]));
              photos.forEach(file=>form.append('files',file));
              result=await api(`/campaigns/${result.id}/look`,{method:'POST',body:form});
            }
          }
          if(descriptionPhoto){
            const fillFromNiche=async()=>{
              const fallback={};
              enrichableFields.forEach(k=>{ if(nicheDefaults[k]&&!(result[k]||'').trim())fallback[k]=nicheDefaults[k]; });
              if(Object.keys(fallback).length){
                result=await api(`/campaigns/${result.id}`,{method:'PATCH',body:{...fallback,version:result.version}});
              }
            };
            try{
              result=isCloudMode()?await analyzeProductPhotoDirect(result.id,descriptionPhoto):await analyzeProductPhotoLocal(result.id,descriptionPhoto);
              analysisOutcome={filled:result.analysis?.filled||[]};
              await fillFromNiche();
            }catch(e){
              analysisOutcome={error:e.message};
              await fillFromNiche();
            }
          }
          setMode('produce');
          const st=nextStage(result)||'model';
          // Sempre respeitar o proximo passo real (nextStage): pular "Definir
          // look" so porque ja tem fotos do produto anexadas fazia a campanha
          // cair direto em "Criar imagem" sem prompt gerado, travando o fluxo
          // com um aviso pedindo pra voltar e gerar o prompt.
          const go=st==='performance'?'look':st;
          setSelected(go);
          syncHash({mode:'produce',campaignId:result.id,stage:go});
          return result;
        }, photos?.length ? 'Campanha criada com fotos do produto.' : 'Campanha criada. Continue a produção.');
        if(created&&analysisOutcome){
          if(analysisOutcome.error)setError(`Campanha criada, mas a análise da IA da foto de descrição falhou: ${analysisOutcome.error}`);
          else if(analysisOutcome.filled.length)flash(`Campanha criada. A IA leu a foto da descrição e preencheu: ${analysisOutcome.filled.map(k=>ANALYSIS_FIELD_LABELS[k]||k).join(', ')}.`);
          else flash('Campanha criada. A IA não encontrou nada de novo pra preencher com a foto da descrição.');
        }
        if(created)setModal(null);
      }}/>:<><p>{modal.description}</p><div className="form-actions"><button disabled={busy} onClick={()=>setModal(null)}>Cancelar</button><button className="primary" disabled={busy} onClick={async()=>{if(await modal.action())setModal(null)}}>{busy?'Aguarde…':modal.label}</button></div></>}
      {error&&<p className="inline-error" role="alert">{error}</p>}
    </Dialog>}
  </>;
}

function AuthScreen({setup,onDone}){
  const [form,setForm]=useState({display_name:'',username:'',password:''});
  const [busy,setBusy]=useState(false),[error,setError]=useState('');
  async function submit(event){
    event.preventDefault();setBusy(true);setError('');
    try{await api(setup?'/auth/setup':'/auth/login',{method:'POST',body:form});onDone()}
    catch(e){setError(e.message||String(e));setBusy(false)}
  }
  return <main className="auth-shell"><section className="auth-card">
    <div className="auth-brand"><span className="logo" aria-hidden="true"><Clapperboard size={18}/></span><div><strong>Fábrica TikTok</strong><small>Estúdio compartilhado</small></div></div>
    <span className="eyebrow">{setup?'PRIMEIRO ACESSO':'ENTRAR'}</span>
    <h1>{setup?'Crie o acesso principal':'Entre no estúdio'}</h1>
    <p>{setup?'Este usuário poderá criar o segundo acesso para sua parceira.':'Campanhas, prompts e aprovações ficam no mesmo espaço compartilhado.'}</p>
    <form onSubmit={submit} className="auth-form">
      {setup&&<label>Nome exibido<input name="display_name" required maxLength={80} autoComplete="name" value={form.display_name} onChange={e=>setForm(v=>({...v,display_name:e.target.value}))}/></label>}
      <label>Usuário ou e-mail<input name="username" required maxLength={80} autoCapitalize="none" autoComplete="username" value={form.username} onChange={e=>setForm(v=>({...v,username:e.target.value}))}/></label>
      <label>Senha<input name="password" required minLength={8} type="password" autoComplete={setup?'new-password':'current-password'} value={form.password} onChange={e=>setForm(v=>({...v,password:e.target.value}))}/></label>
      {error&&<p className="inline-error" role="alert">{error}</p>}
      <button className="primary full" disabled={busy}>{busy?'Aguarde…':setup?'Criar estúdio':'Entrar'}</button>
    </form>
  </section></main>;
}

function UserAccessPanel({auth,onError,onFlash}){
  const [users,setUsers]=useState([]),[saving,setSaving]=useState(false);
  const [form,setForm]=useState({display_name:'',username:'',password:''});
  const [resetTarget,setResetTarget]=useState(null);
  const [resetDraft,setResetDraft]=useState('');
  const [resetSaving,setResetSaving]=useState(false);
  const load=()=>api('/users').then(setUsers).catch(e=>onError(e.message));
  useEffect(()=>{load()},[]);
  async function add(event){
    event.preventDefault();setSaving(true);
    try{await api('/users',{method:'POST',body:form});setForm({display_name:'',username:'',password:''});await load();onFlash('Segundo acesso criado.')}
    catch(e){onError(e.message)}finally{setSaving(false)}
  }
  function beginReset(user){
    setResetTarget(user);
    setResetDraft('');
  }
  async function resetPassword(event){
    event.preventDefault();
    if(!resetTarget)return;
    setResetSaving(true);
    try{
      await api(`/users/${resetTarget.id}/reset-password`,{method:'POST',body:{password:resetDraft}});
      onFlash('Senha de '+resetTarget.display_name+' redefinida.');
      setResetTarget(null);setResetDraft('');
    }catch(e){onError(e.message)}
    finally{setResetSaving(false)}
  }
  return <div className="user-access-panel">
    <p className="help">Acesso compartilhado: as duas pessoas veem as mesmas campanhas.</p>
    <div className="user-list">{users.map(user=><div key={user.id}><UserCog size={17}/><span><strong>{user.display_name}</strong><small>{user.username} · {user.role==='owner'?'responsável':'editora'}</small></span>
      {auth?.user?.role==='owner'&&<button type="button" className="icon-button" title={`Redefinir senha de ${user.display_name}`} aria-label={`Redefinir senha de ${user.display_name}`} disabled={saving||resetSaving} onClick={()=>beginReset(user)}><KeyRound size={16}/></button>}
    </div>)}</div>
    {resetTarget&&<form className="auth-form" onSubmit={resetPassword}>
      <h3><KeyRound size={17}/> Nova senha de {resetTarget.display_name}</h3>
      <label><input name="new_password" autoFocus required minLength={8} type="password" autoComplete="new-password" placeholder="Mínimo 8 caracteres" value={resetDraft} onChange={e=>setResetDraft(e.target.value)}/></label>
      <div style={{display:'flex',gap:8}}>
        <button className="primary" disabled={resetSaving}>{resetSaving?'Salvando…':'Salvar'}</button>
        <button type="button" disabled={resetSaving} onClick={()=>{setResetTarget(null);setResetDraft('')}}>Cancelar</button>
      </div>
    </form>}
    {auth?.user?.role==='owner'&&users.length<2&&<form className="auth-form" onSubmit={add}>
      <h3><UserPlus size={18}/> Criar segundo acesso</h3>
      <label><input name="new_display_name" required maxLength={80} placeholder="Nome (ex.: Ana)" value={form.display_name} onChange={e=>setForm(v=>({...v,display_name:e.target.value}))}/></label>
      <label><input name="new_username" required maxLength={80} autoCapitalize="none" autoComplete="off" placeholder="Usuário ou e-mail" value={form.username} onChange={e=>setForm(v=>({...v,username:e.target.value}))}/></label>
      <label><input name="new_user_password" required minLength={8} type="password" autoComplete="new-password" placeholder="Senha inicial (mín. 8 caracteres)" value={form.password} onChange={e=>setForm(v=>({...v,password:e.target.value}))}/></label>
      <button className="primary" disabled={saving}>{saving?'Criando…':'Criar acesso'}</button>
    </form>}
    {users.length>=2&&<div className="notice success"><Check size={16}/> Acessos configurados.</div>}
  </div>;
}

function LookReminder({c}){
  const reference=c.assets.find(a=>a.kind==='reference');
  const outfit=(c.outfit||'').trim();
  if(!reference&&!outfit)return null;
  return <div className="look-reminder">
    {reference&&<a href={reference.url} target="_blank" rel="noreferrer" title="Abrir a foto da modelo"><img src={reference.url} alt={`Roupa padrão de ${c.model_name}`} loading="lazy"/></a>}
    <span><small>Roupa da modelo</small><strong>{outfit||'Veja na foto de referência'}</strong></span>
  </div>;
}
function Panel({c,identity,selected,busy,references,deviceFiles,onDirty,onError,onSaveBrief,onSaveTexts,onUpload,onDeviceVideo,onTransition,onOpen,onGenerate,onGenerateVariants,onSaveVariant,onRefreshVariant,onRefreshAllVariants,onRefreshVideoPrompt,onImproveVideoPrompt,onRefreshScript,onConfigureWriter,onPublishSlot,onMixVideos,onSavePerformance,onGenerateInsights,onGotoScript,onOpenStudio,onFetchStudioMetrics,onReuse,onAuditStudioPosts,studioAuditReport,onApplyLibraryReference,onSaveNichePhoto}){
  const reference=c.assets.find(a=>a.kind==='reference'),image=c.assets.find(a=>a.kind==='image'),video=c.assets.find(a=>a.kind==='video');
  const [reuse,setReuse]=useState(''),[checks,setChecks]=useState(c.checklist||{}),[publishedUrl,setPublishedUrl]=useState(c.published_url||'');
  const immutable=c.status==='published',index=states.indexOf(c.status),colorCount=(c.color||'').split(/[,;|\n]+/).map(v=>v.trim()).filter(Boolean).length;
  const check=(key,label)=><label className="check-row" key={key}><input type="checkbox" checked={!!checks[key]} disabled={busy||immutable} onChange={e=>setChecks(old=>({...old,[key]:e.target.checked}))}/><span>{label}</span></label>;
  const editor=(field,title,rows=7)=><TextEditor title={title} field={field} value={c.prompts[field]} onSave={onSaveTexts} onDirty={onDirty} onError={onError} busy={busy} readOnly={immutable} rows={rows}/>;
  const service=stage=><div className={'service-box service-box-gen '+(c.generator==='flow'?'is-flow':'is-grok')}><div className="service-box-head"><BrandMark kind={c.generator==='flow'?'labs':'grok'} size={26} tone={c.generator==='flow'?'auto':'auto'}/><div><strong>{c.generator==='flow'?'Google Flow · Labs':'Grok Imagine'}</strong><small>{isMobileDevice()?'Conta conectada no celular':'Perfil: '}{!isMobileDevice()&&(c.generator==='flow'?(identity?.flow_account_hint||'conta Flow'):(identity?.grok_account_hint||'conta Grok'))}</small></div></div><ServiceLaunch service={c.generator} disabled={busy||immutable} onClick={event=>onOpen(c.generator,stage,event)}><BrandMark kind={c.generator==='flow'?'labs':'grok'} size={18} tone={c.generator==='flow'?'auto':'white'}/> <span>{isMobileDevice()?(c.generator==='grok'?'Abrir Grok no celular':'Abrir Flow no navegador'):`Abrir ${c.generator==='flow'?'Flow':'Grok'} para ${stage==='image'?'imagem':'vídeo'}`}</span> <ExternalLink size={15}/></ServiceLaunch><p>{isMobileDevice()?(c.generator==='grok'?'Copie o prompt e anexe as referências no Grok.':'Cole o prompt e anexe as referências no Flow.'):c.generator==='grok'?'Mesma janela do Flow (abas). Interação manual no Grok.':'Mesma janela do Grok (abas). Cole o prompt e anexe os arquivos.'}</p></div>;
  if(selected==='model')return <><AssetView asset={reference} title="Referência fixa da modelo"/>
    <div className="notice"><strong>Nicho:</strong> {c.niche||'não definido'}. Use a foto padrão deste nicho para manter o mesmo rosto/corpo.</div>
    {c.niche && onApplyLibraryReference && <button type="button" className="primary full" disabled={busy||immutable} onClick={()=>onApplyLibraryReference(c.niche)}>Usar foto padrão do nicho ({c.niche})</button>}
    <Uploader kind="reference" exists={!!reference} busy={busy} disabled={immutable} onUpload={onUpload}/><div className="notice">Preserve rosto, cabelo, corpo e tom de pele. Mude apenas roupa e cor.</div>{!immutable&&<section className="reuse-section"><h3>Reutilizar referência</h3><label>Referências de {c.model_name}<select value={reuse} onChange={e=>setReuse(e.target.value)}><option value="">Escolha uma imagem salva</option>{references.filter(r=>r.model_name.toLocaleLowerCase()===c.model_name.toLocaleLowerCase()&&r.id!==reference?.id).map(r=><option key={r.id} value={r.id}>{r.campaign_name} · {r.original_name}</option>)}</select></label><button disabled={!reuse||busy} onClick={()=>onReuse(reuse)}>Usar a mesma imagem</button></section>}</>;
  if(selected==='look')return <><BriefForm campaign={c} onSave={onSaveBrief} onDirty={onDirty} busy={busy}/>{!immutable&&<section className="generate-section"><h3>Prompts e roteiro</h3><p>Preencha roupa, cor, produto, público e benefício. Com várias cores, o app gera um pacote separado por cor (a IA não recebe todas juntas).</p><button className="primary full" disabled={busy||!reference||c.status!=='briefing'} onClick={onGenerate}>{c.prompts.image?'Gerar textos novamente':'Gerar prompts e roteiro'}</button>{colorCount>=2&&<small className="help">Detectamos {colorCount} cores: cada uma terá prompt de imagem, vídeo, roteiro e legenda próprios.</small>}{colorCount<2&&<small className="help">Separe as cores por vírgulas (ex.: Branco, Preto, Azul Marinho) para gerar uma variação de cada.</small>}{!reference&&<small className="help">Anexe a referência na etapa Modelo fixa.</small>}</section>}{c.variants?.length>0&&<VariantList variants={c.variants} onError={onError}/>}</>;
  if(selected==='image')return <>{(c.variants?.length>0||c.prompts.image)?<><div className="notice"><strong>Uma imagem por cor.</strong> Anexe todas aqui. Só avance para aprovação quando cada cor tiver arquivo.</div><div className="notice"><strong>Confira a fotografia-base antes de gerar.</strong> Ela precisa mostrar toda a peça que você quer apresentar. Se a roupa estiver cortada, escolha outra referência na etapa Modelo fixa antes de gerar os prompts. A edição preserva o enquadramento, a pose, o cenário e a iluminação. Siga a ordem dos anexos indicada no prompt de cada cor.</div>{c.variants?.length>0?<VariantList variants={c.variants} images={c.assets} onError={onError} focus="image" onUpload={onUpload} busy={busy} disabled={immutable} immutable={immutable}/>:<>{editor('image','Prompt de imagem')}{image&&<AssetView asset={image} title="Imagem gerada" compact/>}<Uploader kind="image" exists={!!image} busy={busy} disabled={immutable} onUpload={onUpload}/></>}<AssetView asset={reference} title="Referência fixa da modelo para anexar" compact/><ProductGallery photos={c.product_assets}/>{service('image')}</>:<div className="notice">Anexe a referência e gere os prompts na etapa Definir look.</div>}</>;
  if(selected==='image_approval')return <>{c.assets.filter(a=>a.kind==='image').length?<><div className="notice">Confira cada cor. A aprovação libera os roteiros de 15s personalizados por imagem.</div><div className="comparison-grid">{c.assets.filter(a=>a.kind==='image').map(img=><div key={img.id} className="comparison-card"><span>{img.slot||img.metadata?.color||'Imagem'}</span><AssetView asset={img} title={img.slot||'Imagem'} compact/>{img.approved_at&&<p className="approved-label"><Check size={14}/>Aprovada</p>}</div>)}</div><div className="comparison"><div><span>Referência</span><AssetView asset={reference} title="Modelo fixa" compact/></div></div>{c.assets.filter(a=>a.kind==='image').every(a=>a.approved_at)?<div className="notice success"><Check size={17}/> Todas as imagens aprovadas.</div>:<><h3>Confira antes de aprovar</h3>{check('identity','Rosto, cabelo, corpo e tom de pele correspondem à referência em todas as cores.')}{check('look','Roupa, cor, produto e mãos estão corretos em cada imagem.')}<button className="primary full" disabled={busy||c.status!=='image_ready'||!checks.identity||!checks.look} onClick={()=>onTransition('image_approved')}><Check size={17}/> Aprovar todas as imagens</button>{c.status!=='image_ready'&&<small className="help">Anexe a imagem de cada cor na etapa Criar imagem.</small>}</>}</>:<div className="notice">Anexe o resultado de cada cor na etapa Criar imagem.</div>}</>;
  if(selected==='script')return <>{(c.variants?.length>0||c.prompts.hook)?<>{c.variants?.length>0?<><WriterBadge c={c}/><VariantList variants={c.variants} onError={onError} focus="script" onSaveVariant={onSaveVariant} onRefreshVariant={onRefreshVariant} onRefreshAllVariants={onRefreshAllVariants} onConfigureWriter={onConfigureWriter} busy={busy} immutable={immutable}/></>:<ScriptEditor c={c} busy={busy} onDirty={onDirty} onError={onError} onSave={onSaveTexts} onRefresh={onRefreshScript} onConfigureWriter={onConfigureWriter}/>}<div className="notice">Leia em voz alta. Em campanhas com várias cores, você pode gerar <strong>todas em uma única solicitação</strong> ou somente a cor aberta. A legenda continua na etapa Studio.</div>{index>=3?<p className="approved-label"><Check size={16}/>Roteiro revisado</p>:<>{check('script','Revisei as falas de cada cor, o benefício e a duração de 15 segundos.')}<button className="primary full" disabled={busy||c.status!=='image_approved'||!checks.script} onClick={()=>onTransition('script_ready')}>Concluir roteiros <ArrowRight size={16}/></button>{index<2&&<small className="help">Aprove as imagens para concluir o roteiro.</small>}</>}</>:<div className="notice">Gere os textos na etapa Definir look.</div>}</>;
  if(selected==='video')return <>{index>=3?<>{c.assets.some(a=>a.kind==='video')&&<VideoTimelinePreview asset={c.assets.filter(a=>a.kind==='video')[0]} variant={(c.variants||[])[0]} c={c}/>}<div className="notice"><strong>Escolha onde guardar o vídeo.</strong> No celular, use “vídeo da galeria” para validar sem enviar o MP4. O anexo tradicional continua disponível para compartilhar ou incluir no ZIP.</div>{service('video')}{!immutable&&onMixVideos&&<VideoMixer c={c} busy={busy} immutable={immutable} onError={onError} onMix={onMixVideos}/>}{c.variants?.length>0?<VariantList variants={c.variants} images={c.assets} videos={c.assets} deviceVideos={c.device_videos} deviceFiles={deviceFiles} onError={onError} focus="video" onUpload={onUpload} onDeviceVideo={onDeviceVideo} onRefreshVideoPrompt={onRefreshVideoPrompt} onImproveVideoPrompt={onImproveVideoPrompt} videoPromptLimit={c.generator==='grok'?4000:null} busy={busy} disabled={immutable} immutable={immutable}/>:<><div className="video-prompt-refresh"><small className={'prompt-length '+(c.generator==='grok'&&c.prompts.video?.length>4000?'is-over':'')}>{c.prompts.video?.length||0}{c.generator==='grok'?' / 4000':''} caracteres</small><PromptScore text={c.prompts.video}/>{!immutable&&onImproveVideoPrompt&&<button type="button" disabled={busy} onClick={()=>onImproveVideoPrompt()}><Sparkles size={15}/> Melhorar prompt</button>}{!immutable&&<button type="button" disabled={busy} onClick={()=>onRefreshVideoPrompt()}><RefreshCw size={15}/> Recriar prompt de vídeo</button>}</div>{editor('video','Prompt de vídeo')}<AssetView asset={image} title="Imagem aprovada para anexar" compact/>{c.device_videos?.[0]&&<DeviceVideoCard record={c.device_videos[0]} localFile={deviceFiles['']}/>}<Uploader kind="video" exists={!!video} busy={busy} disabled={immutable} onUpload={onUpload}/><DeviceVideoPicker record={c.device_videos?.[0]} busy={busy} disabled={immutable} onSelect={onDeviceVideo}/></>}<div className="notice">Exporte cada vídeo com 15 segundos em {c.generator==='flow'?'1080 × 1920':'720 × 1280'}.</div></>:<div className="notice">Aprove as imagens e conclua o roteiro antes de criar o vídeo.</div>}</>;
  if(selected==='video_approval'){
    const colorSlots=(c.color||'').split(/[,;|\n]+/).map(v=>v.trim()).filter(Boolean);
    const slots=colorSlots.length?colorSlots:[''];
    const uploadedVids=c.assets.filter(a=>a.kind==='video');
    const deviceVids=c.device_videos||[];
    const vids=[...uploadedVids,...deviceVids];
    const bySlot=Object.fromEntries(vids.map(v=>[(v.slot||v.metadata?.color||''),v]));
    const missing=slots.filter(s=>s && !bySlot[s]);
    const allPresent=slots.length===1 && !slots[0] ? vids.length>0 : (slots.length?slots.every(s=>!!bySlot[s]):vids.length>0);
    const statusOk=c.status==='video_ready';
    const alreadyAdvanced=['video_approved','ready_to_publish','published'].includes(c.status);
    const needsLegacyRepair=alreadyAdvanced&&allPresent&&vids.some(a=>!a.approved_at);
    const approveLabel=vids.length===1?'Aprovar vídeo':'Aprovar todos os vídeos';
    const firstUploaded=uploadedVids[0];
    return <>{vids.length?<>{firstUploaded&&<VideoTimelinePreview asset={firstUploaded} variant={(c.variants||[])[0]} c={c}/>} 
      <div className="notice">Confira <strong>cada cor</strong>. ~15s e 9:16 são recomendadas, mas não bloqueiam.</div>
      <div className="comparison-grid">{vids.map((vid,i)=><div key={vid.id||`device-${vid.slot}-${i}`} className="comparison-card"><span>{vid.slot||vid.metadata?.color||'Vídeo'}</span>{vid.device_only?<DeviceVideoCard record={vid} localFile={deviceFiles[vid.slot||'']}/>:<AssetView asset={vid} title={vid.slot||'Vídeo'} compact/>}{vid.approved_at&&<p className="approved-label"><Check size={14}/>Aprovado</p>}</div>)}</div>
      {!!slots.filter(Boolean).length && <ul className="color-checklist">{slots.filter(Boolean).map(s=><li key={s}>{bySlot[s]?`✓ ${s}: vídeo anexado`:`✗ ${s}: falta anexar`}</li>)}</ul>}
      {vids.every(a=>a.approved_at)?<div className="notice success"><Check size={16}/>{vids.length===1?'Vídeo aprovado.':'Todos os vídeos aprovados.'}</div>:needsLegacyRepair?<div className="notice success"><Check size={16}/><div><strong>Esta aprovação já foi registrada.</strong><p>O arquivo ficou sem a marca de aprovação por uma versão anterior da fábrica. Continue para a publicação para corrigir o registro.</p>{c.status==='video_approved'&&<button type="button" className="primary" disabled={busy} onClick={()=>onTransition('ready_to_publish')}>Continuar para publicação <ArrowRight size={16}/></button>}</div></div>:<><p>Alvo: 15 segundos · {c.generator==='flow'?'1080 × 1920':'720 × 1280'} · MP4.</p>
      {check('visual','Assisti a todos os vídeos. Identidade, look, produto e movimentos estão corretos em cada cor.')}
      {check('audio','Revisei áudio, falas, sincronização e duração em cada cor.')}
      <button className="primary full" disabled={busy||!allPresent||!statusOk||!checks.visual||!checks.audio} onClick={()=>onTransition('video_approved',{approved_by:identity?.model_name||'Usuário'})}><Check size={17}/> {approveLabel}</button>
      {!allPresent&&<small className="help">Falta vídeo em: {missing.join(', ')||'—'}. Em <strong>Criar vídeo</strong>, anexe 1 MP4 por cor. Não misture cores diferentes no Misturar.</small>}
      {allPresent&&!statusOk&&<small className="help">Os arquivos estão aí, mas o status ainda não é video_ready (agora: {c.status}). Reanexe um dos MP4s em Criar vídeo ou recarregue.</small>}
      {allPresent&&statusOk&&(!checks.visual||!checks.audio)&&<small className="help">Marque as duas caixas acima para liberar o botão.</small>}
      </>}</>:<div className="notice">Selecione o MP4 de cada cor na etapa Criar vídeo. Você pode mantê-lo na galeria ou enviá-lo para a Fábrica.</div>}</>;
  }
  if(selected==='performance')return <>
    <div className="notice"><strong>Métricas ficam em Resultados.</strong> Use a aba Resultados no topo para coletar do Studio, auditar publicados e gerar insights.</div>
    <p className="help">Produzir fica só com briefing, imagem, roteiro, vídeo e publicação.</p>
  </>;
  return <>{index<5?<div className="notice">Aprove o vídeo antes de preparar a publicação.</div>:<>{c.status==='video_approved'&&<button className="primary full" disabled={busy} onClick={()=>onTransition('ready_to_publish')}>Preparar publicação <ArrowRight size={17}/></button>}{index>=6&&<PublishQueue c={c} busy={busy} immutable={immutable} onError={onError} onOpen={onOpen} onPublishSlot={onPublishSlot} onRefreshVariant={onRefreshVariant} onRefreshCaption={onRefreshScript} onSaveCaption={(prompts)=>prompts?._variantId?onSaveVariant?.(prompts._variantId,{caption:prompts.caption}):onSaveTexts(prompts)}/>}{index>=6&&<div className="notice">Métricas e Crítico: abra <strong>Resultados</strong> no topo da página.</div>}{c.status==='video_approved'&&<div className="notice">Depois de preparar, você escolhe cada cor/produto para subir no Studio.</div>}</>}</>;
}

// Portugues falado rende ~2,8 palavras por segundo. O total sozinho nao diz
// onde esta o excesso: um hook de 16 palavras estoura os 4 segundos mesmo num
// roteiro de 44 palavras.
const SCRIPT_BUDGET={hook:[10,12,'0–4s'],development:[20,24,'4–12s'],cta:[7,9,'12–15s']};
function countWords(value){const clean=String(value||'').trim();return clean?clean.split(/\s+/).length:0}
function ScriptBudget({draft}){
  const rows=Object.entries(SCRIPT_BUDGET).map(([key,[low,high,time]])=>{
    const words=countWords(draft[key]);
    const state=words>=low&&words<=high?'ok':(words<low?(words>=low-2?'near':'off'):(words<=high+2?'near':'off'));
    return {key,words,low,high,time,state};
  });
  const total=rows.reduce((sum,row)=>sum+row.words,0);
  const totalState=total>=38&&total<=45?'ok':(total<=47?'near':'off');
  return <div className="script-budget">
    {rows.map(row=><span key={row.key} className={'budget-chip is-'+row.state} title={`${row.time}: alvo ${row.low} a ${row.high} palavras`}>
      <em>{row.time}</em>{row.words}<small>/{row.low}–{row.high}</small>
    </span>)}
    <span className={'budget-chip is-total is-'+totalState} title="15 segundos cabem entre 38 e 45 palavras faladas">
      <em>total</em>{total}<small>/38–45</small>
    </span>
  </div>;
}
// Quem escreveu este roteiro: o modelo de linguagem ou o gerador local. Sem
// isto na tela, nao ha como o operador saber qual dos dois ele esta lendo.
function WriterBadge({c}){
  const info=(c.checklist||{}).writer;
  if(!info) return null;
  const nomes={openai:'OpenAI',gemini:'Gemini',ia:'IA'};
  const porIA=info.by&&info.by!=='local';
  // A auditoria agora julga tambem o texto local, que e o que realmente vai ao
  // ar quando a IA nao responde. Se ela reprovou, isso aparece aqui: publicar
  // sem saber que o roteiro esta abaixo da regua era o problema.
  const reprovas=Array.isArray(info.local_audit)?info.local_audit:[];
  return <div className={'writer-badge '+(reprovas.length?'is-flagged':porIA?'is-ai':'is-local')}>
    <strong>{porIA?`Escrito por IA · ${nomes[info.by]||info.by}`:'Texto local (sem IA)'}</strong>
    {!porIA&&info.reason&&<small>A IA tentou e foi recusada: {info.reason}. Use “Atualizar fala inteira” para tentar de novo.</small>}
    {!porIA&&!info.reason&&<small>Ligue a escrita por IA no ícone de Identidade, no topo.</small>}
    {reprovas.length>0&&<small className="writer-audit-fail"><strong>A auditoria reprovou este roteiro:</strong> {reprovas.join('; ')}. Gere outra fala antes de publicar.</small>}
    {reprovas.length===0&&<small className="writer-audit-ok">Auditoria: aprovado.</small>}
  </div>;
}
function ScriptEditor({c,busy,onDirty,onError,onSave,onRefresh,onConfigureWriter}){
  const [draft,setDraft]=useState({hook:c.prompts.hook,development:c.prompts.development,cta:c.prompts.cta,
    cover_text:c.prompts.cover_text||'',screen_text:c.prompts.screen_text||''});
  const [writer,setWriter]=useState(null);
  useEffect(()=>{api('/writer').then(setWriter).catch(()=>setWriter({enabled:false,provider:''}))},[]);
  const fields=[['hook','Hook','0–4s'],['development','Desenvolvimento','4–12s'],['cta','Chamada para ação','12–15s']];
  // Texto de capa e texto de tela nao entram no video gerado (a IA escreve
  // letra torta): sao colados no CapCut ou no editor do TikTok. Quem assiste
  // sem som so recebe o gancho por aqui.
  const postFields=[['cover_text','Texto da capa','antes do play'],['screen_text','Texto na tela','0–3s']];
  const changed=Object.keys(draft).some(k=>draft[k]!==(c.prompts[k]||''));
  const falasVazias=['hook','development','cta'].some(k=>!(draft[k]||'').trim());
  const aiName=writer?.provider==='gemini'?'Gemini':'ChatGPT';
  return <div className="script-editor"><WriterBadge c={c}/>{c.status!=='published'&&onRefresh&&<><section className={'script-ai-action '+(writer?.enabled?'is-ready':'is-off')}><div><span className="eyebrow">ESCRITA POR API</span><strong>{writer?.enabled?`${aiName} está configurado`:'ChatGPT ainda não está ativo'}</strong><small>{writer?.enabled?'Gera hook, desenvolvimento, CTA e legenda; o app audita o resultado antes de aceitar.':'Configure a chave uma vez para liberar a geração nesta etapa.'}</small></div>{writer?.enabled?<button className="primary" disabled={busy||changed} onClick={()=>onRefresh(['hook','development','cta','caption'],{writerMode:'ai'})}><Sparkles size={16}/> Gerar roteiro com {aiName}</button>:<button type="button" className="primary" disabled={busy} onClick={onConfigureWriter}><Sparkles size={16}/> Configurar ChatGPT</button>}</section><div className="script-refresh-actions"><span className="help">Alternativas locais, sem usar API:</span><button disabled={busy||changed} onClick={()=>onRefresh(['hook','caption'],{writerMode:'local'})}>Criar outro hook</button><button disabled={busy||changed} onClick={()=>onRefresh(['hook','development','cta','caption'],{writerMode:'local'})}>Criar outra fala inteira</button>{changed&&<small className="help">Salve o roteiro antes de gerar novas frases.</small>}</div></>}{fields.map(([key,title,time])=><section className="script-part" key={key}><div className="section-title"><div><span className="time-label">{time}</span><h3>{title}</h3></div><CopyButton text={draft[key]} onError={onError}/></div><textarea aria-label={title} value={draft[key]} readOnly={c.status==='published'} rows={3} maxLength={12000} onChange={e=>{setDraft(d=>({...d,[key]:e.target.value}));onDirty(true)}}/></section>)}<section className="post-text-block"><div className="section-title"><div><span className="time-label">POSTAGEM</span><h3>Para colar no CapCut</h3></div></div><p className="help">O prompt de vídeo proíbe texto dentro do quadro de propósito — gerador de IA escreve letra torta. Estes dois textos entram na postagem, onde a tipografia sai correta. Boa parte do TikTok roda sem som: sem eles, quem assiste mudo não recebe o gancho.</p>{postFields.map(([key,title,time])=><div className="script-part" key={key}><div className="section-title"><div><span className="time-label">{time}</span><h3>{title}</h3></div><CopyButton text={draft[key]} onError={onError}/></div><input aria-label={title} value={draft[key]||''} readOnly={c.status==='published'} maxLength={120} onChange={e=>{setDraft(d=>({...d,[key]:e.target.value}));onDirty(true)}}/></div>)}</section>{changed&&<button className="full" disabled={busy||falasVazias} onClick={()=>onSave(draft)}>Salvar roteiro</button>}<ScriptBudget draft={draft}/></div>;
}
