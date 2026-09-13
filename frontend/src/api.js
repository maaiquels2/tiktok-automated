export async function api(path, options = {}) {

  const form = options.body instanceof FormData;

  const response = await fetch('/api' + path, {...options, headers: {

    'X-Local-App': 'fabrica-tiktok', ...(!form && options.body ? {'Content-Type':'application/json'} : {}),

    ...options.headers,

  }, body: form ? options.body : options.body ? JSON.stringify(options.body) : undefined});

  const data = await response.json().catch(() => ({}));

  if (!response.ok) throw new Error(data.error || 'Não foi possível acessar o aplicativo local.');

  return data;

}

export const health=()=>api('/health');

// Upload direto ao Supabase Storage (usado na versao online, no lugar do
// FormData de sempre): o navegador manda o arquivo para o Storage sem
// passar pelo servidor, contornando o limite de 4,5 MB por requisicao das
// funcoes do Vercel. Em 3 passos: pede o link assinado, envia o arquivo
// direto pra la, e avisa o servidor que terminou (pra ele validar e salvar
// no banco).
export const requestAssetUploadUrl = (cid, body) => api(`/campaigns/${cid}/assets/upload-url`,{method:'POST',body});
export const confirmAssetUpload = (cid, body) => api(`/campaigns/${cid}/assets/confirm`,{method:'POST',body});

export async function uploadAssetDirect(cid, kind, file, extra = {}) {
  const {upload_url, path} = await requestAssetUploadUrl(cid, {kind, filename: file.name, ...extra});
  const put = await fetch(upload_url, {method:'PUT', headers:{'Content-Type': file.type || 'application/octet-stream'}, body: file});
  if (!put.ok) throw new Error('Não foi possível enviar o arquivo para o armazenamento.');
  return confirmAssetUpload(cid, {kind, path, original_name: file.name, ...extra});
}

export async function uploadProductPhotosDirect(cid, briefing, removed, files) {
  const photos = [];
  for (const file of files) {
    const {upload_url, path} = await requestAssetUploadUrl(cid, {kind:'product', filename:file.name});
    const put = await fetch(upload_url, {method:'PUT', headers:{'Content-Type': file.type || 'application/octet-stream'}, body:file});
    if (!put.ok) throw new Error('Não foi possível enviar uma das fotos para o armazenamento.');
    photos.push({path, original_name:file.name});
  }
  return api(`/campaigns/${cid}/look/confirm`, {method:'POST', body:{briefing, removed, photos}});
}

export const states = ['briefing','image_ready','image_approved','script_ready','video_ready','video_approved','ready_to_publish','published'];

export const statusLabels = {briefing:'Em preparação',image_ready:'Imagem para revisar',image_approved:'Imagem aprovada',script_ready:'Roteiro pronto',video_ready:'Vídeo para revisar',video_approved:'Vídeo aprovado',ready_to_publish:'Pronta para publicar',published:'Publicada'};

export const stageInfo = [
  {id:'model', title:'Modelo fixa', subtitle:'Sua referência de identidade', icon:'user'},
  {id:'look', title:'Definir look', subtitle:'Produto, roupa e intenção', icon:'shirt'},
  {id:'image', title:'Criar imagem', subtitle:'Prompt + referência da modelo', icon:'image'},
  {id:'image_approval', title:'Aprovar imagem', subtitle:'Revisão de identidade e look', icon:'check'},
  {id:'script', title:'Roteiro de 15s', subtitle:'Hook, desenvolvimento e CTA', icon:'text'},
  {id:'video', title:'Criar vídeo', subtitle:'Movimento a partir da imagem', icon:'video'},
  {id:'video_approval', title:'Aprovar vídeo', subtitle:'Imagem, áudio e duração', icon:'check'},
  {id:'studio', title:'TikTok Studio', subtitle:'Preparar e publicar manualmente', icon:'upload'},
  {id:'performance', title:'Performance', subtitle:'Metricas, insights e Critico', icon:'chart'},
];

export const produceStages = stageInfo.filter(s => s.id !== 'performance');

export function nextStage(c) {

  if (!c.assets.some(a=>a.kind==='reference')) return 'model';

  if (!c.prompts.image) return 'look';

  return {briefing:'image',image_ready:'image_approval',image_approved:'script',script_ready:'video',video_ready:'video_approval',video_approved:'studio',ready_to_publish:'studio',published:'studio'}[c.status];

}

export const studioAudit=(body={days:7,min_views:100})=>api('/studio/audit',{method:'POST',body});

export const studioAuditLatest=()=>api('/studio/audit/latest');

export const studioPlaybook=()=>api('/studio/playbook');

export const studioPlaybookBuild=(body={})=>api('/studio/playbook',{method:'POST',body});

export const productivityQueue=()=>api('/productivity');

export const playbookCreateCampaign=(body={})=>api('/studio/playbook/campaign',{method:'POST',body});

export const studioIdentity=()=>api('/studio/identity');
export const setupStatus=()=>api('/setup-status');

export const saveStudioIdentity=(body={})=>api('/studio/identity',{method:'PATCH',body});



export const NICHES = [

  {id:'praia',label:'Moda praia'},

  {id:'academia',label:'Moda academia'},

  {id:'casual',label:'Moda casual'},

  {id:'dia-a-dia',label:'Moda dia a dia'},

  {id:'intima',label:'Moda íntima'},

  {id:'fantasia',label:'Fantasia'},

];

export const modelLibrary = (model_name='Micaela') => api('/model-library?model_name='+encodeURIComponent(model_name));

export const uploadModelLibrary = (form) => api('/model-library',{method:'POST',body:form});
export const renameModelLibraryLabel = (body) => api('/model-library/label',{method:'PATCH',body});

export const requestModelLibraryUploadUrl = (body) => api('/model-library/upload-url',{method:'POST',body});
export const confirmModelLibraryUpload = (body) => api('/model-library/confirm',{method:'POST',body});

export async function uploadModelLibraryPhotoDirect(model_name, niche, file) {
  const {upload_url, path} = await requestModelLibraryUploadUrl({model_name, niche, filename:file.name});
  const put = await fetch(upload_url, {method:'PUT', headers:{'Content-Type': file.type || 'application/octet-stream'}, body:file});
  if (!put.ok) throw new Error('Não foi possível enviar a foto para o armazenamento.');
  return confirmModelLibraryUpload({model_name, niche, path, original_name:file.name});
}

export const referenceFromLibrary = (cid, body) => api(`/campaigns/${cid}/reference-from-library`,{method:'POST',body});



export const openStudioFree = () => api('/studio/open',{method:'POST',body:{confirmed:true}});
export const openBrowserFree = (service) => api('/browser/open-free',{method:'POST',body:{service,confirmed:true}});

export const analyzePublishedLink = (body) => api('/studio/analyze-link',{method:'POST',body});

export const listLinkAnalyses = () => api('/studio/link-analyses');

export const characterSheet = (model_name='Micaela', niche='') => {
  const q = new URLSearchParams({ model_name });
  if (niche) q.set('niche', niche);
  return api('/model-library/character-sheet?' + q.toString());
};

export const openCharacterSheet = (body={}) =>
  api('/model-library/character-sheet/open', { method: 'POST', body });

export const writerSettings = () => api('/writer');
export const saveWriterSettings = (body) => api('/writer',{method:'PATCH',body});
export const testWriter = () => api('/writer/test',{method:'POST',body:{}});
