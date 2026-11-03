// O que salvar o briefing apaga. O servidor (apply_brief) zera textos, falas, imagens e videos quando QUALQUER campo
// (menos o nome) ou as fotos do produto mudam; a pergunta de confirmacao precisa dizer isso com numeros.

const LABELS = {
  video_mode: 'Formato do vídeo', color: 'Cores', product: 'Produto', outfit: 'Roupa', model_name: 'Modelo',
  niche: 'Nicho', audience: 'Público', benefit: 'Benefício', angle: 'Ângulo', tone: 'Tom', style: 'Estilo',
  movements: 'Movimentos', details: 'Detalhes', generator: 'Gerador', objection: 'Objeção', offer: 'Oferta',
  body_turns: 'Giro do corpo', social_proof: 'Prova social', size_proof: 'Prova de tamanho',
};

// Formatos que a etapa Criar vídeo troca sem apagar nada (usam a mesma imagem-base, de frente).
const SAME_BASE = ['', 'movimento'];

export const changedFields = (campaign, values) =>
  Object.keys(values || {}).filter(k => k !== 'name' && k in campaign && String(values[k] ?? '') !== String(campaign[k] ?? ''));

const plural = (n, one, many) => `${n} ${n === 1 ? one : many}`;

// Texto do aviso, ou null quando nao ha nada a perder.
export function briefResetMessage(campaign, values, { photos = 0, removed = 0, description = false } = {}) {
  const fields = changedFields(campaign, values);
  if (!fields.length && !photos && !removed && !description) return null;
  const assets = campaign.assets || [];
  const images = assets.filter(a => a.kind === 'image').length;
  const videos = assets.filter(a => a.kind === 'video').length + (campaign.device_videos || []).length;
  const scripts = (campaign.variants || []).length || (campaign.prompts?.hook ? 1 : 0);
  if (!images && !videos && !scripts) return null;
  const lost = [];
  if (scripts) lost.push(`os textos e as falas de ${plural(scripts, 'cor', 'cores')}, inclusive as que você editou fora do app`);
  if (images) lost.push(plural(images, 'imagem', 'imagens'));
  if (videos) lost.push(plural(videos, 'vídeo', 'vídeos'));
  const what = fields.length ? ` (${fields.map(k => LABELS[k] || k).join(', ')})` : '';
  const onlyFormat = fields.length === 1 && fields[0] === 'video_mode' && !photos && !removed && !description;
  const dica = onlyFormat && SAME_BASE.includes(campaign.video_mode || '') && SAME_BASE.includes(values.video_mode || '')
    ? ' Para trocar só entre "Com fala" e "Só movimento", use o formato na etapa Criar vídeo: ali nada é apagado.'
    : '';
  return `Esta alteração${what} apaga ${lost.join(', ')}. Isso não volta: copie as falas que quiser guardar antes. `
    + `Depois é preciso gerar os textos de novo e aprovar de novo.${dica}`;
}
