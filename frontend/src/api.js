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
];
export function nextStage(c) {
  if (!c.assets.some(a=>a.kind==='reference')) return 'model';
  if (!c.prompts.image) return 'look';
  return {briefing:'image',image_ready:'image_approval',image_approved:'script',script_ready:'video',video_ready:'video_approval',video_approved:'studio',ready_to_publish:'studio',published:'studio'}[c.status];
}
