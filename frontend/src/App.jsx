import { getDeviceInfo } from './device';
import { ServiceLaunch, TikTokLaunchButtons, isMobileDevice, mobileServiceUrl, setCloudMode } from './serviceLinks';
import { useEffect, useRef, useState } from 'react';
import { Smartphone, Monitor, Tablet, Plus, ArrowRight, Download, FolderHeart, Check, ExternalLink, RefreshCw, AlertCircle, X, ShieldCheck, Copy as CopyIcon, Pencil, Trash2, UserCog, Sparkles, Wand2, Clapperboard, LogOut, UserPlus } from 'lucide-react';
import Canvas from './Canvas';
import { api, health, openBrowserFree, states, statusLabels, stageInfo, produceStages, nextStage, studioAudit, studioIdentity } from './api';
import {Dialog, BriefForm, CopyButton, AssetView, Uploader, DeviceVideoPicker, DeviceVideoCard, TextEditor, ProductGallery, VariantList, PublishQueue, VideoMixer, VideoTimelinePreview, PerformancePanel, ModelLibraryPanel, StudioIdentityPanel, WriterSettingsPanel, SetupChecklist, DailyQueueCard, NICHES, ResultsQuickTools} from './components';


function BrandMark({kind='grok', size=22, tone='auto'}){
  const labsSrc = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAb8AAAG/CAMAAAD/zSlAAAAAY1BMVEX/se4AAAD/s/Hfm9DFiLf/tfTupd73q+Z8VnQVDhPSksQJBwmUZ4qfb5T7rur/uPg4JzSxe6Xln9ZBLT0oHCUvISyKYIFmR1+/hbIeFRxWPFAaEhhsS2VdQVdLNEa5gKyodJ3zWcT6AAAMGUlEQVR4nO3d6XriOgyA4UbBCWVLoYVuFLj/qzzQzszpYpHNdmrne//OQztEjeNFkW5uAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAABuiE9Df7nkiRSziS+zzQ0R9EqK9X6b+XL7uMyH/oZJk3w/9xa9d4fJ0N8xYZIf/EbvbEsAvVm9eQ/feRAteAb6YRYBwne+A83QXzRREiR8WTbjBvRBZoHiN+UG9CHQ8Jll99XQXzVJ1T5Q/B4YP32oQsw+3+O3GvqrJinc/cf46YPZBYrfHfHzgfln5OQhTPxY//lh1kHC98Lw6Un5GCB825zbzxOZ3fmP33Hob5kwyX3fgdsJd59Hslq/PLzezj9Yrv+8zpXP3D7c7wrmnn6ZKl8vF++mlli8La7bWQJ4+Pin5WkmhrvPOzEfKtt6cFmZa6ry9udnpqs//0rwQrKu55fXxz8pbPErA/2P8Rnxixvxixvxixvxixvxixvxixvxixvxixvxixvxixvxixvxixvxixvxixvxixvxixvxixvxixvxixvxixvxixvxixvxixvxixvxixvxixvxixvxixvxixvxixvxixvxixvxixvxixvxi5tMfoZivq6p/2GrX7AnfoM4WuJ3rIlf9frzQ2/EbwgrSz3seV35JFv87uj4MITSUr9nXlf7sbJ0T3omfkMoLM10apunVLYOPMRvAFJYhsLXuvJl1iLoFGwdgBSWSNS2brAW0V4Sv/DkyRKJ2tq55mT7FPELT2ztBBZ146fklk9lFI0MT2ylPOufZMYWP0omB2fvJlDfOUWeLR+jY0BwlW0i8lwfB+uwe0f8grO1Md7Xj4Nia0JQu+yHY/ZeEMcG8dvYPtgg8HCptDYj2zSIX2HrQXDHDRiUOdp66RyKBh+1bXtn2Y6mKwFJYe0DsW70Wcux4fkGpO9DQHKy9nFotIyT3NrEZVoSwFBkY3367ZudI5TWAfSZvjnBlPZOjo2Gz8vGqeXg4vzwZBMmlJlt9MzuG84hJbc30p3S9jYIKW1L9yxbNP4BS+vnsyduwBCMvY9x09vvcgO+2APIFCYAo7TBbZHFWS2sA3A2JX7eWTNwzx7qMge//Ix7+9/AhH1s72xd4872bX5GpTwBD2QyeWaelCbU7TYwS9sp4NmOOahX6tRj2u7nGEvu9sUDI6hf1r2TrMPU0ZYHevbW4AgDXRnr3nPW6ODvK2v24cWCEdQb2SjzxpcOKzdb+uEFJ4H+KKPnw6T9j5JCmcjeMwf1xGi3zKLLC2CSK4/ABUe5fqyUpcNjxznHSVlEzJiD+lApA9629eTlg5T2jdTshSmMB+Zo37TMdl1/omzsBxmMoB6I7XW/ix57XkbZRnt4YgR1Thk95312TCplN+eROahjctR2LPuMdbKxH2awindMyVjqfWIgttcBz7YdVpTQKRlL2WvPtE11DvrGCOqQ/WUxJ+PcTJuDuvh/44O2cn/pn/OnjaC80+lOZc2Wvzyl+s/z1X3QVxaBjmgZS25miWamHGrsuAGdkEIZPR2dtVbWlynONyD7oG4oA5yzXAf7u4TnpytzUAfsr/plPfY9v9Nmt3PmoP2pGUu37rKljXIu7GJ+NHrKHrPLUzoplSlM15NF/GV/WzZrnTBY81usVZnOluyD9iIb5dTIcZbKSlvFk83Uj/JkenW8v6y8UJ9lB95J6kHN99y5LlktE+tb8ZzF97JSLuqL+3nFSnmnjH3Q7qw1zs6eT+6vqRTaWTzx68g8KWfuXi6pzKxlDRhBu1LviDs/c4pKmStRW6ublTJ6Zi3etG1FlFV8w7oy+EK0NzX3vsYzmSnZTKzi21MzlrYe7wZlr655aQv8Za9ylXV41a85dRW/ZxXfkthrLHlYuX/5rRNlzPb4R5MmUdLCPA9l9uKgWTZnCtOKUc7cvc09/5BCeyeJk8AW1Iwl7/U9zES58dfcgI2p9ZHu/W9GinYWzz5oc8rKvba7pgNSahVmmIM2pI5hQar8a2P3MyNoM+rKPVB9R6U+ZXZgFd9MgIyla+ytQbLL0pMA1pOZcmrkNGPpyu+3tnh817DA9qhJoYyeIbpEi9wUGy1ngzloE1px6tsn379YTDmbrKfK9PPdnoOIGkY7w/E8fTdSTE67e2XT9Z812zDXrbR8T5+Tv/Odd5w+KrlSXzyQkH2VlsNwu/T3O02V7w7KucMPNJq7xmjnN28rT9ftPGM51o6an/+QToygKnXu6WviJ6uNulhQcBavU3NoT15SXkyZa4f8V7APqtJy2F98XLHzamHXYuD855VVvJ16dvrqYcgSmUybzlm+CXCIFaWVtu/pfu4pVT5tslywa9GpZ0TU7Ev3Jf1NsesevYxsJitRVu5b16On3KyV88XGyGb6QbSJvOPRU8pZr3vvHav479SMJbclBOQmb7vgs6JA71f6yt1pCQ/ZaDXnW7pnH/QLdeXusoSOrI5aZkZrzEE/M9rK3WX5AJPv+85b/vccIBUuGrJRVu4OU16k2rmLXuak9Ggy1JX7zlX4RBzMOr/93xhB/1Azlt4cpSvITetjhgZ6lt5Ohp6xNHP0C8q1ko/fS4iEqhho1f+yk5vbr5ppLzP15Gx0j5rR3tR0s3I35cnHzfeO8pJn2vsi2dJB+EQm2tTWgXvSCdWMJSeJCqZcdDzka6ZX854kqG+cO+ghJTdaaXlXRr+KV+eeWTbt+7ctRYfslpbG3m58tVRTUHrO7qT0ffN9/C/H/QjU9j3PFr3iJ/lOKUfnVpfW18lQM5b6xk9unq69huLSqBuVafuePeNnyq65ZR2Mt9Wj5NfyLzs//6TS3p/3Y7QHEVq9xg/TrvHTipj5Mh9p/LRKK390m5pLeQx6811MRxlA9U3NP7ZP7S+LmJmHg6I6vVpgx+rKyv2P9vufpji5PqVt5DDCVbyasfRP2/MHv3vVV42vUZlpkM/QbgA1G7cJLm04a0UYCz1j6ZM2/RNFToNFLxvfPqiasfRF46WxrLQUmlDGVeJczVj6plmaupS5pwyJFsaUzaR25vghrw+g3HR7j9axw4j2QdUz959XpS6A5+gtBlkz/DCes3g1Y8ni5eq4ZGQyDXHK18ho9kHVjCWb7VqU6yJVuXb4RkNvXqos/ELNR89387eZ+XFlRMzlFfbrO3ChjaNRmdrXSHfIy9U5ZH+tyrIYbKvliu0Y5qBqj5qr7naTPN+c5Xk+O+1/x4zlh/4pc7/flYylGvO7u7vtwMv0GiNYxYc9Gw8s+VaP3UbPeCTf6rHRvmfE0i6OJvnQ19e7pG9A+aUTR4cOCZ8E1mQspSHdNjtm6EO6IJ5T3QdNfe75V6rNcuszltJwe0oyfibI+1y/wX2gRltByWYco+fFNMFFRLOMpUSchr7azkme8r7ndwk2KhvD0u9/qSVky2Ycc89/EltDqD1JU7VMawpapb/x+dVrUrkwUgx9PYNLagZjTkNfzuD6lT/5ZapfmC3m2VtKA2il9FZJ2H1K9185psX7h21Ce2iShyun81s8JJSKJpMxHNx+9dyhfMZvJU/EL2bEL27EL26jfP4l9DIS88+4STHC9V9KFWHM2I4fsuwupf2XKlQ149/jJaX9TzN8fZ3QOpef/Y3kaejLGVxCy4ez1dCXM7i0ujuO7gBpm9Lj7/wAHFP27kVi+UujS4BJ6PTv3WqAuuIDSq4tkmx+V60rv25T2nz5UI4pgX6R1uzzQvLxTEG3Ce1d/+80lhF0vkzv9qtpFpeURMvYyWYcI2iyRdCM2qs4Ja/rtLZePqnWI3gEnpIN3zmAp9QTYeZpF1GWddpD6Lx907TIrFNOhXk4pbZv9sMqr+v7F6/t8Sb12+/SrSjVZIrDZuhrG4RU4VvUBvC8rNK/+T4YWRwSqyey3W+Snnh+I/nyMaGlxMtuMoIn32diiuPiJYmbcDtd51qPpoSJWeWz4+5x+zp0ALrbHqanyaz42Z9pHM5/tWXx3hMnUptNsRrhrfeZxG3oywcAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAACk7D8FMcgzF+dTzAAAAABJRU5ErkJggg==";
  const grokDark = "data:image/png;base64,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";
  const grokLight = "data:image/png;base64,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";
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
  const [resultsTab,setResultsTab]=useState('agora'); // agora | studio | lote | playbook | historico | campanha
  const bootHash=useRef(true);
  const [error,setError]=useState(''),[notice,setNotice]=useState(''),[modal,setModal]=useState(null),[dirty,setDirty]=useState(false);
  const [renaming,setRenaming]=useState(false),[renameDraft,setRenameDraft]=useState('');
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
      api('/lan-pin').then(d=>setLanPin(d?.pin||'')).catch(()=>{});
      const first=list[0]?await api('/campaigns/'+list[0].id):null;
      if(active){
        setCampaigns(list);setReferences(refs);
        const route=parseRoute();
        let camp=first;
        if(route.campaignId){
          const hit=list.find(x=>x.id===route.campaignId);
          if(hit){try{camp=await api('/campaigns/'+hit.id)}catch(e){camp=first}}
        }
        setC(camp);
        if(camp){
          if(route.mode==='produce'&&route.stage&&produceStages.some(s=>s.id===route.stage)) setSelected(route.stage);
          else setSelected(nextStage(camp)==='performance'?'studio':(nextStage(camp)||'model'));
        }
        setMode(route.mode);
        setResultsTab(route.resultsTab||'studio');
        if(location.pathname==='/creator')setModal({type:'create'});
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
    return {mode:'home', resultsTab:'studio', campaignId:null, stage:null};
  }
  function syncHash(next={}){
    const m=next.mode??mode;
    const tab=next.resultsTab??resultsTab;
    const cid=next.campaignId!==undefined?next.campaignId:(c?.id||null);
    const stage=next.stage!==undefined?next.stage:selected;
    let path='#/inicio';
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
    if(m!=='home'&&!discard())return;
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
      syncHash({mode:'home'});
    }
    setError('');
  }

  
  useEffect(()=>{
    if(loading||bootHash.current)return;
    syncHash({});
  },[mode,resultsTab,c?.id,selected,loading]);
  useEffect(()=>{
    function onHash(){
      if(busy||!discard()) { syncHash({}); return; }
      const route=parseRoute();
      setMode(route.mode);
      setResultsTab(route.resultsTab||'studio');
      if(route.mode==='produce'&&route.stage) setSelected(route.stage);
      if(route.campaignId&&c?.id!==route.campaignId){
        const hit=campaigns.find(x=>x.id===route.campaignId);
        if(hit){ api('/campaigns/'+hit.id).then(result=>{setC(result); if(route.mode==='produce'){const st=route.stage||nextStage(result); setSelected(st==='performance'?'studio':st)}}).catch(()=>{}); }
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
  async function chooseCampaign(id,{openResults=false}={}){if(busy||!discard())return;await run(async()=>{const result=await api('/campaigns/'+id);if(openResults){setMode('results');setResultsTab('campanha');setSelected('performance');syncHash({mode:'results',resultsTab:'campanha',campaignId:result.id})}else{setMode('produce');const st=nextStage(result);setSelected(st==='performance'?'studio':st);syncHash({mode:'produce',campaignId:result.id,stage:st==='performance'?'studio':st})}return result},'Campanha carregada.')}
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
  function mixVideos(payload){
    return run(()=>api(`/campaigns/${c.id}/videos/mix`,{method:'POST',body:{...payload,version:c.version}}),'Mix gerado. Revise o MP4 no slot escolhido.','video');
  }
  function savePerformance(payload){
    return run(()=>api(`/campaigns/${c.id}/performance`,{method:'POST',body:{...payload,version:c.version}}),'Metricas salvas.','studio');
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
    return run(()=>api(`/campaigns/${c.id}/reference-from-library`,{method:'POST',body:{niche,version:c.version}}),'Foto padrao do nicho aplicada.','model');
  }
  function saveNichePhoto(niche,file){
    if(!file)return;
    const form=new FormData();form.set('model_name',c.model_name||identity?.model_name||'Micaela');form.set('niche',niche);form.set('file',file);
    return run(()=>api('/model-library',{method:'POST',body:form}),'Foto padrao do nicho salva.');
  }
    function savePublishedLink(payload){
    return run(()=>api(`/campaigns/${c.id}/published-link`,{method:'POST',body:{...payload,version:c.version}}),'Link do TikTok salvo.','performance');
  }
    function fetchStudioMetrics(color){
    return run(()=>api(`/campaigns/${c.id}/performance/fetch`,{method:'POST',body:{color,version:c.version}}),'Metricas coletadas do Studio.','performance');
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
  const stage=stageInfo.find(s=>s.id===selected);
  return <><header className="header"><div className="brand"><span className="logo">?</span><span>Fábrica TikTok</span><span className="brand-divider"/><span className="workspace-name">{identity?.studio_name||'Estúdio'}</span></div>
    <nav className="mode-nav" aria-label="Navegação principal">
      <button type="button" className={mode==='home'?'active':''} disabled={busy} onClick={()=>goMode('home')}>Início</button>
      <button type="button" className={mode==='produce'?'active':''} disabled={busy||!c} onClick={()=>goMode('produce')}>Produzir</button>
      <button type="button" className={mode==='results'?'active':''} disabled={busy} onClick={()=>goMode('results','agora')}>Resultados</button>
    </nav>
    <div className="header-right">
      {auth?.authenticated&&<button type="button" className="identity-icon-btn" title="Acessos do estúdio" onClick={()=>setModal({type:'users',title:'Acessos do estúdio'})}><UserCog size={17}/><span className="identity-icon-label">{auth.user.display_name}</span></button>}
      <span className="device-badge" aria-label={`Dispositivo de acesso: ${device.label}`} title={`Acessando por ${device.label}. Os dados ficam no computador que executa a fábrica.`}><DeviceIcon size={15} aria-hidden="true"/><span>{device.label}</span></span>
      <button type="button" className="identity-icon-btn" title="Identidade do estudio" aria-label="Identidade do estudio" disabled={busy} onClick={()=>{if(!busy)setModal({type:'identity', title:'Identidade do estudio'})}}>
        <UserCog size={18}/>
        <span className="identity-icon-label">{identity?.model_name||'Identidade'}</span>
      </button>
      <span className="local-badge"><ShieldCheck size={15}/> {busy?'Salvando.':'Dados no computador'}</span>
      {lanUrls[0] && ['localhost','127.0.0.1'].includes(location.hostname) ? <button type="button" className="lan-chip" title="Copia o link pra abrir no celular (mesmo Wi-Fi). Nao mostra o IP na tela." onClick={()=>{navigator.clipboard?.writeText(lanUrls[0]); flash(lanPin?`Link copiado. No celular, o PIN e ${lanPin}.`:'Link do celular copiado. Cole no navegador do phone (mesmo Wi-Fi).')}}>Link do celular</button> : null}
      {lanPin && lanUrls[0] && ['localhost','127.0.0.1'].includes(location.hostname) ? <span className="lan-pin" title="Quem abrir pela rede local precisa digitar este PIN. Fica em data/lan_pin.txt.">PIN {lanPin}</span> : null}
      {auth?.authenticated&&<button type="button" className="icon-button" title="Sair" aria-label="Sair" onClick={logout}><LogOut size={17}/></button>}
    </div></header>
    
    {mode==='home' && (
    <main className="workspace home-workspace" aria-busy={loading}>
      <section className="home-panel">
        <div className="home-hero">
          <div>
            <span className="eyebrow">{(identity?.studio_name||'ESTÚDIO').toUpperCase()}</span>
            <h1>O que você quer fazer agora?</h1>
            <p>Separe produção e resultados. Escolha uma campanha para continuar, ou veja o que já performou no TikTok.</p>
          </div>
          <div className="home-actions">
            <button type="button" className="primary" disabled={busy||loading} onClick={()=>{if(discard()){setError('');setModal({type:'create'})}}}><Plus size={17}/> Nova campanha</button>
            <button type="button" className="button" disabled={busy||!c} onClick={()=>openResults()}>Ir para Resultados</button>
            <button type="button" className="button" disabled={busy||!campaigns.length} onClick={()=>{const pub=campaigns.find(x=>x.status==='published')||campaigns[0]; if(pub) chooseCampaign(pub.id,{openResults:true})}}>Auditar / métricas</button>
          </div>
        </div>

        <div className="home-launchers" aria-label="Atalhos de servicos">
          <span className="home-launchers-label">Abrir serviços</span>
          <div className="home-launchers-row">
            <ServiceLaunch service="grok" className="home-launch-btn is-grok" disabled={busy} onClick={event=>openFreeService('grok',event)} title="Grok Imagine">
              <BrandMark kind="grok" size={20} tone="white"/>
              <span>Grok</span>
            </ServiceLaunch>
            <ServiceLaunch service="flow" className="home-launch-btn is-flow" disabled={busy} onClick={event=>openFreeService('flow',event)} title="Google Flow / Labs">
              <BrandMark kind="labs" size={20}/>
              <span>Flow Labs</span>
            </ServiceLaunch>
            <TikTokLaunchButtons className="home-launch-btn is-studio" disabled={busy} onOpenStudio={event=>openFreeService('studio',event)}/>
          </div>
          <small className="help">{isMobileDevice()?'Os serviços abrem neste aparelho. TikTok Studio e TikTok usam o aplicativo TikTok; Flow abre no navegador.':'TikTok Studio abre no perfil dedicado do Chrome. TikTok abre pelo navegador deste aparelho.'}</small>
        </div>
<SetupChecklist busy={busy} onError={setError}/>
        <DailyQueueCard busy={busy} onError={setError} onFlash={flash} onCreate={createFromPlaybook}/>
        <ModelLibraryPanel modelName={identity?.model_name||'Micaela'} busy={busy} onError={setError} onFlash={flash}/>
        <div className="home-grid">
          {loading && <div className="empty-state"><RefreshCw className="spinning"/><h1>Carregando campanhas…</h1></div>}
          {!loading && !campaigns.length && (
            <div className="empty-state"><div className="empty-icon"><FolderHeart size={34}/></div><h1>Crie sua primeira campanha</h1><p>Do briefing à publicação, depois analise em Resultados.</p><button className="primary" onClick={()=>setModal({type:'create'})}><Plus size={17}/> Nova campanha</button></div>
          )}
          {!loading && campaigns.map(item=>(
            <article className={'home-card'+(c?.id===item.id?' active':'')} key={item.id}>
              <span className="campaign-id">CAMPANHA {String(item.id).padStart(4,'0')}</span>
              <strong>{item.name}</strong>
              <small>{item.product||item.model_name}</small>
              <span className={'status-pill '+(item.status==='published'?'success':'')}>{statusLabels[item.status]}</span>
              <div className="home-card-actions">
                <button type="button" className="primary" disabled={busy} onClick={()=>chooseCampaign(item.id)}>Produzir</button>
                <button type="button" className="button" disabled={busy} onClick={()=>chooseCampaign(item.id,{openResults:true})}>Resultados</button>
                <button type="button" className="icon-button" title="Editar" disabled={busy} onClick={()=>editCampaignById(item.id)}><Pencil size={14}/></button>
                <button type="button" className="icon-button" title="Copiar" disabled={busy} onClick={()=>copyCampaign(item.id)}><CopyIcon size={14}/></button>
                <button type="button" className="icon-button danger-action" title="Excluir" disabled={busy} onClick={()=>deleteCampaign(item.id)}><Trash2 size={14}/></button>
              </div>
            </article>
          ))}
        </div>
      </section>
    </main>
    )}

{mode==='produce' && (<main className="workspace produce-workspace produce-dense" aria-busy={loading}>
      <aside className="queue produce-queue"><div className="queue-heading"><div><span className="eyebrow">PRODUÇÃO</span><h2>Campanhas <span className="count">{campaigns.length}</span></h2></div></div><button className="primary" disabled={busy||loading} onClick={()=>{if(discard()){setError('');setModal({type:'create'})}}}><Plus size={17}/> Nova campanha</button>
        <div className="campaign-list">{campaigns.map(item=><div className={'campaign '+(c?.id===item.id?'active':'')} key={item.id}><button className="campaign-select" disabled={busy} onClick={()=>chooseCampaign(item.id)} aria-pressed={c?.id===item.id}><span className="campaign-id">CAMPANHA {String(item.id).padStart(4,'0')}</span><strong>{item.name}</strong><small>{item.product||item.model_name}</small><span className={'status-pill '+(item.status==='published'?'success':'')}>{statusLabels[item.status]}</span></button><div className="campaign-actions"><button type="button" title="Editar campanha" aria-label={`Editar ${item.name}`} disabled={busy} onClick={()=>editCampaignById(item.id)}><Pencil size={14}/></button><button type="button" title="Copiar campanha" aria-label={`Copiar ${item.name}`} disabled={busy} onClick={()=>copyCampaign(item.id)}><CopyIcon size={14}/></button><button type="button" className="danger-action" title="Excluir campanha" aria-label={`Excluir ${item.name}`} disabled={busy} onClick={()=>deleteCampaign(item.id)}><Trash2 size={14}/></button></div></div>)}</div>
        <div className="queue-bottom"><FolderHeart size={20}/><strong>Uma modelo, novos looks.</strong><p>Reutilize a referência para preservar a identidade em cada campanha.</p></div>
      </aside>
      <section className="canvas-panel">{loading?<div className="empty-state"><RefreshCw className="spinning"/><h1>Carregando seu estúdio…</h1></div>:c?<>
        <div className="canvas-header produce-chrome">
          <div className="produce-chrome-main">
            <span className="eyebrow">#{String(c.id).padStart(4,'0')} · {c.model_name} · {c.generator==='flow'?'Flow':'Grok'} · 15s</span>
            {renaming?(
              <div className="campaign-rename">
                <input autoFocus value={renameDraft} disabled={busy} onChange={e=>setRenameDraft(e.target.value)} onKeyDown={e=>{if(e.key==='Enter')saveRename();if(e.key==='Escape')setRenaming(false)}} aria-label="Novo nome da campanha"/>
                <button type="button" className="primary" disabled={busy} onClick={saveRename}>Salvar</button>
                <button type="button" disabled={busy} onClick={()=>setRenaming(false)}>Cancelar</button>
              </div>
            ):(
              <h1 className="campaign-title-row">{c.name}<button type="button" className="icon-button btn-rename" title="Renomear" aria-label="Renomear campanha" disabled={busy} onClick={beginRename}><Pencil size={14}/></button></h1>
            )}
          </div>
          <div className="export-actions produce-chrome-actions">
            <button className="button" onClick={editCampaign} disabled={busy} title={c.status==='published'?'Criar versão editável':'Editar briefing'}><RefreshCw size={14}/> Editar</button>
            <a className="button" href={`/api/campaigns/${c.id}/package.txt`} title="Baixar textos">TXT</a>
            <a className="button" href={`/api/campaigns/${c.id}/package.zip`} title="Baixar pacote"><Download size={14}/> ZIP</a>
            <ServiceLaunch service={c.generator} className={'generator-open-btn compact '+(c.generator==='flow'?'is-flow':'is-grok')} disabled={busy||c.status==='published'} onClick={event=>openService(c.generator, selected==='video'||selected==='video_approval'?'video':'image',event)} title={c.generator==='flow'?'Abrir Flow':'Abrir Grok'}>
              <BrandMark kind={c.generator==='flow'?'labs':'grok'} size={18} tone={c.generator==='flow'?'auto':'white'}/>
              <span className="generator-open-text"><strong>{c.generator==='flow'?'Flow':'Grok'}</strong></span>
            </ServiceLaunch>
          </div>
        </div>
        {c.migration_note&&<div className="migration-note"><AlertCircle size={15}/>{c.migration_note}</div>}
        <div className="produce-toolbar">
          <div className="produce-toolbar-next">
            <span className="eyebrow">{c.status==='published'?'CONCLUÍDA':'AGORA'}</span>
            <strong>{c.status==='published'?'Publicada':(current?.title||stage?.title||'Continuar')}</strong>
          </div>
          <button type="button" className="button produce-continue" disabled={busy||(c.status!=='published'&&!current)} onClick={()=>c.status==='published'?openPublication():choose(current.id)}>
            {c.status==='published'?'Ver publicação':'Continuar'}<ArrowRight size={14}/>
          </button>
        </div>
        <Canvas key={c.id} campaign={c} selected={selected} onSelect={choose} busy={busy} stages={produceStages}/>
        </>:<div className="empty-state"><div className="empty-icon"><FolderHeart size={34}/></div><span className="eyebrow">SEU CANVAS DE PRODUÇÃO</span><h1>Crie sua primeira campanha</h1><p>Defina o produto e o look, anexe a modelo e acompanhe cada aprovação até o TikTok.</p><button className="primary" onClick={()=>setModal({type:'create'})}><Plus size={17}/> Nova campanha</button></div>}</section>
      <aside className="inspector"><div className="inspector-heading produce-inspector-head"><div><span className="eyebrow">{c?'ETAPA':'INÍCIO'}</span><h2>{c?stage.title:'Produção'}</h2></div>{c&&<span className="status-pill">{statusLabels[c.status]}</span>}</div>
        {c?<Panel key={`${c.id}-${c.version}-${selected}-${writerRevision}`} c={c} identity={identity} selected={selected} busy={busy} references={references} deviceFiles={deviceFiles[c.id]||{}} onDirty={setDirty} onError={setError} onSaveBrief={saveBrief} onSaveTexts={saveTexts} onUpload={upload} onDeviceVideo={registerDeviceVideo} onTransition={transition} onOpen={openService}
          onGenerate={()=>{if(dirty){setError('Salve o briefing antes de gerar os textos.');return}run(()=>post('/generate'),'Prompts, roteiro e legenda gerados localmente.','image')}}
          onGenerateVariants={generateVariants}
            onSaveVariant={saveVariantPrompts}
            onRefreshVariant={refreshVariant}
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
        <nav className="results-subnav" aria-label="Subpaginas de Resultados">
          {[
            ['agora','O que fazer'],
            ['studio','Studio / link'],
            ['lote','Lote 7/15/30'],
            ['playbook','Playbook'],
            ['historico','Historico'],
            ['campanha','Campanha'],
          ].map(([id,lab])=>(
            <button key={id} type="button" className={resultsTab===id?'active':''} disabled={busy} onClick={()=>goMode('results',id)}>{lab}</button>
          ))}
        </nav>

        {resultsTab!=='campanha' && (
          <ResultsQuickTools busy={busy} onBusy={setBusy} onError={setError} onFlash={flash} tab={resultsTab} onTab={(id)=>goMode('results',id)} onCreateFromPlaybook={createFromPlaybook} onOpenProduce={(id)=>chooseCampaign(id)} onOpenCampaignResults={(id)=>chooseCampaign(id,{openResults:true})}/>
        )}

        {resultsTab==='campanha' && (!c ? (
          <div className="empty-state"><h1>Campanha opcional</h1><p>Escolha uma campanha na lista ao lado, ou use as outras abas (Studio, Lote, Playbook, Historico) sem campanha.</p><button className="button" onClick={()=>goMode('home')}>Ir ao Inicio</button></div>
        ) : (
          <>
            <div className="results-header">
              <div>
                <span className="eyebrow">PERFORMANCE · CAMPANHA {String(c.id).padStart(4,'0')}</span>
                <h1>{c.name}</h1>
                <p className="help">Metricas e insights desta campanha — separados da producao.</p>
              </div>
              <div className="export-actions">
                <button type="button" className="button" disabled={busy} onClick={()=>goMode('produce')}>Produzir</button>
                {publicationLinks(c).length>0 && <button type="button" className="button" onClick={openPublication}>Ver publicacao</button>}
              </div>
            </div>
            {c.assets.some(a=>a.kind==='video') && <VideoTimelinePreview asset={c.assets.filter(a=>a.kind==='video')[0]} variant={(c.variants||[])[0]} c={c}/>}
            <PerformancePanel c={c} busy={busy} immutable={c.status==='published'} onError={setError} onSavePerformance={savePerformance} onGenerateInsights={generateInsights} onRefreshVariant={refreshVariant} onGotoScript={()=>{goMode('produce');gotoScript()}} onOpenStudio={event=>openService('studio','publish',event)} onFetchStudioMetrics={fetchStudioMetrics} onAuditStudioPosts={auditStudioPosts} studioAuditReport={studioAuditReport} onSavePublishedLink={savePublishedLink}/>
          </>
        ))}
      </section>
    </main>
    )}

    {error&&<div className="toast error" role="alert"><AlertCircle size={19}/><span>{error}</span><button className="icon-button" onClick={()=>setError('')} aria-label="Fechar erro"><X size={16}/></button><button onClick={()=>{if(discard())location.reload()}}>Recarregar</button></div>}
    {notice&&!error&&<div className="toast" role="status"><Check size={19}/>{notice}</div>}
    {modal&&<Dialog title={modal.type==='create'?'Nova campanha':modal.title} onClose={()=>{if(!busy){setModal(null);setError('')}}}>
      {modal.type==='users'?<UserAccessPanel auth={auth} busy={busy} onError={setError} onFlash={flash}/>:modal.type==='identity'?<><StudioIdentityPanel identity={identity} setIdentity={setIdentity} busy={busy} onError={setError} onFlash={flash} onSaved={()=>setModal(null)}/><WriterSettingsPanel busy={busy} onError={setError} onFlash={flash} onSaved={()=>{setWriterRevision(v=>v+1);setModal(null)}}/></>:modal.type==='create'?<BriefForm busy={busy} campaign={{model_name:identity?.model_name||'Micaela'}} onCancel={()=>setModal(null)} onSave={async (values,photos=[],removed=[])=>{
        const created=await run(async()=>{
          let result=await api('/campaigns',{method:'POST',body:values});
          if(photos?.length){
            const form=new FormData();
            form.set('briefing',JSON.stringify({...values,version:result.version}));
            form.set('removed',JSON.stringify(removed||[]));
            photos.forEach(file=>form.append('files',file));
            result=await api(`/campaigns/${result.id}/look`,{method:'POST',body:form});
          }
          setMode('produce');
          const st=nextStage(result)||'model';
          // If product photos already attached, skip asking again on look when possible
          const hasPhotos=(result.product_assets||[]).length>0;
          let go=st==='performance'?'look':st;
          if(go==='look'&&hasPhotos&&(result.assets||[]).some(a=>a.kind==='reference')) go='image';
          setSelected(go);
          syncHash({mode:'produce',campaignId:result.id,stage:go});
          return result;
        }, photos?.length ? 'Campanha criada com fotos do produto.' : 'Campanha criada. Continue a producao.');
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
    <div className="auth-brand"><span className="logo">?</span><div><strong>Fábrica TikTok</strong><small>Estúdio compartilhado</small></div></div>
    <span className="eyebrow">{setup?'PRIMEIRO ACESSO':'ENTRAR'}</span>
    <h1>{setup?'Crie o acesso principal':'Entre no estúdio'}</h1>
    <p>{setup?'Este usuário poderá criar o segundo acesso para sua parceira.':'Campanhas, prompts e aprovações ficam no mesmo espaço compartilhado.'}</p>
    <form onSubmit={submit} className="auth-form">
      {setup&&<label>Nome exibido<input required maxLength={80} autoComplete="name" value={form.display_name} onChange={e=>setForm(v=>({...v,display_name:e.target.value}))}/></label>}
      <label>Usuário ou e-mail<input required maxLength={80} autoCapitalize="none" autoComplete="username" value={form.username} onChange={e=>setForm(v=>({...v,username:e.target.value}))}/></label>
      <label>Senha<input required minLength={8} type="password" autoComplete={setup?'new-password':'current-password'} value={form.password} onChange={e=>setForm(v=>({...v,password:e.target.value}))}/></label>
      {error&&<p className="inline-error" role="alert">{error}</p>}
      <button className="primary full" disabled={busy}>{busy?'Aguarde…':setup?'Criar estúdio':'Entrar'}</button>
    </form>
  </section></main>;
}

function UserAccessPanel({auth,onError,onFlash}){
  const [users,setUsers]=useState([]),[saving,setSaving]=useState(false);
  const [form,setForm]=useState({display_name:'',username:'',password:''});
  const load=()=>api('/users').then(setUsers).catch(e=>onError(e.message));
  useEffect(()=>{load()},[]);
  async function add(event){
    event.preventDefault();setSaving(true);
    try{await api('/users',{method:'POST',body:form});setForm({display_name:'',username:'',password:''});await load();onFlash('Segundo acesso criado.')}
    catch(e){onError(e.message)}finally{setSaving(false)}
  }
  return <div className="user-access-panel">
    <p>Os dois usuários trabalham nas mesmas campanhas. As senhas ficam protegidas e não aparecem nesta tela.</p>
    <div className="user-list">{users.map(user=><div key={user.id}><UserCog size={17}/><span><strong>{user.display_name}</strong><small>{user.username} · {user.role==='owner'?'responsável':'editora'}</small></span></div>)}</div>
    {auth?.user?.role==='owner'&&users.length<2&&<form className="auth-form" onSubmit={add}>
      <h3><UserPlus size={18}/> Criar segundo acesso</h3>
      <label>Nome exibido<input required maxLength={80} value={form.display_name} onChange={e=>setForm(v=>({...v,display_name:e.target.value}))}/></label>
      <label>Usuário ou e-mail<input required maxLength={80} autoCapitalize="none" value={form.username} onChange={e=>setForm(v=>({...v,username:e.target.value}))}/></label>
      <label>Senha inicial<input required minLength={8} type="password" value={form.password} onChange={e=>setForm(v=>({...v,password:e.target.value}))}/></label>
      <button className="primary" disabled={saving}>{saving?'Criando…':'Criar acesso'}</button>
    </form>}
    {users.length>=2&&<div className="notice success"><Check size={16}/> Os dois acessos do protótipo estão configurados.</div>}
  </div>;
}

function Panel({c,identity,selected,busy,references,deviceFiles,onDirty,onError,onSaveBrief,onSaveTexts,onUpload,onDeviceVideo,onTransition,onOpen,onGenerate,onGenerateVariants,onSaveVariant,onRefreshVariant,onRefreshScript,onConfigureWriter,onPublishSlot,onMixVideos,onSavePerformance,onGenerateInsights,onGotoScript,onOpenStudio,onFetchStudioMetrics,onReuse,onAuditStudioPosts,studioAuditReport,onApplyLibraryReference,onSaveNichePhoto}){
  const reference=c.assets.find(a=>a.kind==='reference'),image=c.assets.find(a=>a.kind==='image'),video=c.assets.find(a=>a.kind==='video');
  const [reuse,setReuse]=useState(''),[checks,setChecks]=useState(c.checklist||{}),[publishedUrl,setPublishedUrl]=useState(c.published_url||'');
  const immutable=c.status==='published',index=states.indexOf(c.status),colorCount=(c.color||'').split(/[,;|\n]+/).map(v=>v.trim()).filter(Boolean).length;
  const check=(key,label)=><label className="check-row" key={key}><input type="checkbox" checked={!!checks[key]} disabled={busy||immutable} onChange={e=>setChecks(old=>({...old,[key]:e.target.checked}))}/><span>{label}</span></label>;
  const editor=(field,title,rows=7)=><TextEditor title={title} field={field} value={c.prompts[field]} onSave={onSaveTexts} onDirty={onDirty} onError={onError} busy={busy} readOnly={immutable} rows={rows}/>;
  const service=stage=><div className={'service-box service-box-gen '+(c.generator==='flow'?'is-flow':'is-grok')}><div className="service-box-head"><BrandMark kind={c.generator==='flow'?'labs':'grok'} size={26} tone={c.generator==='flow'?'auto':'auto'}/><div><strong>{c.generator==='flow'?'Google Flow · Labs':'Grok Imagine'}</strong><small>{isMobileDevice()?'Conta conectada no celular':'Perfil: '}{!isMobileDevice()&&(c.generator==='flow'?(identity?.flow_account_hint||'conta Flow'):(identity?.grok_account_hint||'conta Grok'))}</small></div></div><ServiceLaunch service={c.generator} disabled={busy||immutable} onClick={event=>onOpen(c.generator,stage,event)}><BrandMark kind={c.generator==='flow'?'labs':'grok'} size={18} tone={c.generator==='flow'?'auto':'white'}/> <span>{isMobileDevice()?(c.generator==='grok'?'Abrir Grok no celular':'Abrir Flow no navegador'):`Abrir ${c.generator==='flow'?'Flow':'Grok'} para ${stage==='image'?'imagem':'vídeo'}`}</span> <ExternalLink size={15}/></ServiceLaunch><p>{isMobileDevice()?(c.generator==='grok'?'Abre o app Grok quando permitido pelo iOS; caso contrário, abre o site. Copie o prompt e anexe as referências no Grok.':'Abre no navegador do celular. Cole o prompt e anexe as referências.'):c.generator==='grok'?'Mesma janela do Flow (abas). Interacao manual no Grok.':'Mesma janela do Grok (abas). Cole o prompt e anexe os arquivos.'}</p></div>;
  if(selected==='model')return <><AssetView asset={reference} title="Referência fixa da modelo"/>
    <div className="notice"><strong>Nicho:</strong> {c.niche||'nao definido'} — use a foto padrao deste nicho para manter o mesmo rosto/corpo.</div>
    {c.niche && onApplyLibraryReference && <button type="button" className="primary full" disabled={busy||immutable} onClick={()=>onApplyLibraryReference(c.niche)}>Usar foto padrao do nicho ({c.niche})</button>}
    <Uploader kind="reference" exists={!!reference} busy={busy} disabled={immutable} onUpload={onUpload}/><div className="notice">Preserve rosto, cabelo, corpo e tom de pele. Mude apenas roupa e cor.</div>{!immutable&&<section className="reuse-section"><h3>Reutilizar referência</h3><label>Referências de {c.model_name}<select value={reuse} onChange={e=>setReuse(e.target.value)}><option value="">Escolha uma imagem salva</option>{references.filter(r=>r.model_name.toLocaleLowerCase()===c.model_name.toLocaleLowerCase()&&r.id!==reference?.id).map(r=><option key={r.id} value={r.id}>{r.campaign_name} · {r.original_name}</option>)}</select></label><button disabled={!reuse||busy} onClick={()=>onReuse(reuse)}>Usar a mesma imagem</button></section>}</>;
  if(selected==='look')return <><BriefForm campaign={c} onSave={onSaveBrief} onDirty={onDirty} busy={busy}/>{!immutable&&<section className="generate-section"><h3>Prompts e roteiro</h3><p>Preencha roupa, cor, produto, público e benefício. Com várias cores, o app gera um pacote separado por cor (a IA não recebe todas juntas).</p><button className="primary full" disabled={busy||!reference||c.status!=='briefing'} onClick={onGenerate}>{c.prompts.image?'Gerar textos novamente':'Gerar prompts e roteiro'}</button>{colorCount>=2&&<small className="help">Detectamos {colorCount} cores: cada uma terá prompt de imagem, vídeo, roteiro e legenda próprios.</small>}{colorCount<2&&<small className="help">Separe as cores por vírgulas (ex.: Branco, Preto, Azul Marinho) para gerar uma variação de cada.</small>}{!reference&&<small className="help">Anexe a referência na etapa Modelo fixa.</small>}</section>}{c.variants?.length>0&&<VariantList variants={c.variants} onError={onError}/>}</>;
  if(selected==='image')return <>{(c.variants?.length>0||c.prompts.image)?<><div className="notice"><strong>Uma imagem por cor.</strong> Anexe todas aqui. Só avance para aprovação quando cada cor tiver arquivo.</div>{c.variants?.length>0?<VariantList variants={c.variants} images={c.assets} onError={onError} focus="image" onUpload={onUpload} busy={busy} disabled={immutable} immutable={immutable}/>:<>{editor('image','Prompt de imagem')}{image&&<AssetView asset={image} title="Imagem gerada" compact/>}<Uploader kind="image" exists={!!image} busy={busy} disabled={immutable} onUpload={onUpload}/></>}<AssetView asset={reference} title="Referência fixa da modelo para anexar" compact/><ProductGallery photos={c.product_assets}/>{service('image')}</>:<div className="notice">Anexe a referência e gere os prompts na etapa Definir look.</div>}</>;
  if(selected==='image_approval')return <>{c.assets.filter(a=>a.kind==='image').length?<><div className="notice">Confira cada cor. A aprovação libera os roteiros de 15s personalizados por imagem.</div><div className="comparison-grid">{c.assets.filter(a=>a.kind==='image').map(img=><div key={img.id} className="comparison-card"><span>{img.slot||img.metadata?.color||'Imagem'}</span><AssetView asset={img} title={img.slot||'Imagem'} compact/>{img.approved_at&&<p className="approved-label"><Check size={14}/>Aprovada</p>}</div>)}</div><div className="comparison"><div><span>Referência</span><AssetView asset={reference} title="Modelo fixa" compact/></div></div>{c.assets.filter(a=>a.kind==='image').every(a=>a.approved_at)?<div className="notice success"><Check size={17}/> Todas as imagens aprovadas.</div>:<><h3>Confira antes de aprovar</h3>{check('identity','Rosto, cabelo, corpo e tom de pele correspondem à referência em todas as cores.')}{check('look','Roupa, cor, produto e mãos estão corretos em cada imagem.')}<button className="primary full" disabled={busy||c.status!=='image_ready'||!checks.identity||!checks.look} onClick={()=>onTransition('image_approved')}><Check size={17}/> Aprovar todas as imagens</button>{c.status!=='image_ready'&&<small className="help">Anexe a imagem de cada cor na etapa Criar imagem.</small>}</>}</>:<div className="notice">Anexe o resultado de cada cor na etapa Criar imagem.</div>}</>;
  if(selected==='script')return <>{(c.variants?.length>0||c.prompts.hook)?<>{c.variants?.length>0?<><WriterBadge c={c}/><VariantList variants={c.variants} onError={onError} focus="script" onSaveVariant={onSaveVariant} onRefreshVariant={onRefreshVariant} onConfigureWriter={onConfigureWriter} busy={busy} immutable={immutable}/></>:<ScriptEditor c={c} busy={busy} onDirty={onDirty} onError={onError} onSave={onSaveTexts} onRefresh={onRefreshScript} onConfigureWriter={onConfigureWriter}/>}<div className="notice">Leia em voz alta. Para pedir um texto novo à API, use <strong>Gerar roteiro com ChatGPT</strong>. Os botões menores criam alternativas locais sem gastar API.</div>{index>=3?<p className="approved-label"><Check size={16}/>Roteiro revisado</p>:<>{check('script','Revisei as falas de cada cor, o benefício e a duração de 15 segundos.')}<button className="primary full" disabled={busy||c.status!=='image_approved'||!checks.script} onClick={()=>onTransition('script_ready')}>Concluir roteiros <ArrowRight size={16}/></button>{index<2&&<small className="help">Aprove as imagens para concluir o roteiro.</small>}</>}</>:<div className="notice">Gere os textos na etapa Definir look.</div>}</>;
  if(selected==='video')return <>{index>=3?<>{c.assets.some(a=>a.kind==='video')&&<VideoTimelinePreview asset={c.assets.filter(a=>a.kind==='video')[0]} variant={(c.variants||[])[0]} c={c}/>}<div className="notice"><strong>Escolha onde guardar o vídeo.</strong> No celular, use “vídeo da galeria” para validar sem enviar o MP4. O anexo tradicional continua disponível para compartilhar ou incluir no ZIP.</div>{service('video')}{!immutable&&onMixVideos&&<VideoMixer c={c} busy={busy} immutable={immutable} onError={onError} onMix={onMixVideos}/>}{c.variants?.length>0?<VariantList variants={c.variants} images={c.assets} videos={c.assets} deviceVideos={c.device_videos} deviceFiles={deviceFiles} onError={onError} focus="video" onUpload={onUpload} onDeviceVideo={onDeviceVideo} busy={busy} disabled={immutable} immutable={immutable}/>:<>{editor('video','Prompt de vídeo')}<AssetView asset={image} title="Imagem aprovada para anexar" compact/>{c.device_videos?.[0]&&<DeviceVideoCard record={c.device_videos[0]} localFile={deviceFiles['']}/>}<Uploader kind="video" exists={!!video} busy={busy} disabled={immutable} onUpload={onUpload}/><DeviceVideoPicker record={c.device_videos?.[0]} busy={busy} disabled={immutable} onSelect={onDeviceVideo}/></>}<div className="notice">Exporte cada vídeo com 15 segundos em {c.generator==='flow'?'1080 × 1920':'720 × 1280'}.</div></>:<div className="notice">Aprove as imagens e conclua o roteiro antes de criar o vídeo.</div>}</>;
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
    <div className="notice"><strong>Metricas ficam em Resultados.</strong> Use a aba Resultados no topo para coletar do Studio, auditar publicados e gerar insights.</div>
    <p className="help">Produzir fica so com briefing, imagem, roteiro, video e publicacao.</p>
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
  return <div className={'writer-badge '+(porIA?'is-ai':'is-local')}>
    <strong>{porIA?`Escrito por IA · ${nomes[info.by]||info.by}`:'Texto local (sem IA)'}</strong>
    {!porIA&&info.reason&&<small>A IA tentou e foi recusada: {info.reason}. Use “Atualizar fala inteira” para tentar de novo.</small>}
    {!porIA&&!info.reason&&<small>Ligue a escrita por IA no ícone de Identidade, no topo.</small>}
  </div>;
}
function ScriptEditor({c,busy,onDirty,onError,onSave,onRefresh,onConfigureWriter}){
  const [draft,setDraft]=useState({hook:c.prompts.hook,development:c.prompts.development,cta:c.prompts.cta});
  const [writer,setWriter]=useState(null);
  useEffect(()=>{api('/writer').then(setWriter).catch(()=>setWriter({enabled:false,provider:''}))},[]);
  const fields=[['hook','Hook','0–4s'],['development','Desenvolvimento','4–12s'],['cta','Chamada para ação','12–15s']];
  const changed=Object.keys(draft).some(k=>draft[k]!==c.prompts[k]);
  const aiName=writer?.provider==='gemini'?'Gemini':'ChatGPT';
  return <div className="script-editor"><WriterBadge c={c}/>{c.status!=='published'&&onRefresh&&<><section className={'script-ai-action '+(writer?.enabled?'is-ready':'is-off')}><div><span className="eyebrow">ESCRITA POR API</span><strong>{writer?.enabled?`${aiName} está configurado`:'ChatGPT ainda não está ativo'}</strong><small>{writer?.enabled?'Gera hook, desenvolvimento, CTA e legenda; o app audita o resultado antes de aceitar.':'Configure a chave uma vez para liberar a geração nesta etapa.'}</small></div>{writer?.enabled?<button className="primary" disabled={busy||changed} onClick={()=>onRefresh(['hook','development','cta','caption'],{writerMode:'ai'})}><Sparkles size={16}/> Gerar roteiro com {aiName}</button>:<button type="button" className="primary" disabled={busy} onClick={onConfigureWriter}><Sparkles size={16}/> Configurar ChatGPT</button>}</section><div className="script-refresh-actions"><span className="help">Alternativas locais, sem usar API:</span><button disabled={busy||changed} onClick={()=>onRefresh(['hook','caption'],{writerMode:'local'})}>Criar outro hook</button><button disabled={busy||changed} onClick={()=>onRefresh(['hook','development','cta','caption'],{writerMode:'local'})}>Criar outra fala inteira</button>{changed&&<small className="help">Salve o roteiro antes de gerar novas frases.</small>}</div></>}{fields.map(([key,title,time])=><section className="script-part" key={key}><div className="section-title"><div><span className="time-label">{time}</span><h3>{title}</h3></div><CopyButton text={draft[key]} onError={onError}/></div><textarea aria-label={title} value={draft[key]} readOnly={c.status==='published'} rows={3} maxLength={12000} onChange={e=>{setDraft(d=>({...d,[key]:e.target.value}));onDirty(true)}}/></section>)}{changed&&<button className="full" disabled={busy||Object.values(draft).some(v=>!v.trim())} onClick={()=>onSave(draft)}>Salvar roteiro</button>}<ScriptBudget draft={draft}/></div>;
}
