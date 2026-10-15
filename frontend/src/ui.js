// Vocabulario visual do redesenho "Estudio de producao": as 9 etapas viram 4
// fases com cor propria, e cada status da campanha diz qual e a proxima acao.

export const PHASES = [
  {id: 'preparar', title: 'Preparar', stages: ['model', 'look']},
  {id: 'imagem', title: 'Imagem', stages: ['image', 'image_approval']},
  {id: 'video', title: 'Vídeo', stages: ['script', 'video', 'video_approval']},
  {id: 'publicar', title: 'Publicar', stages: ['studio']},
];

export function phaseOfStage(stageId) {
  const index = PHASES.findIndex(p => p.stages.includes(stageId));
  return index < 0 ? PHASES.length - 1 : index;
}

// A lista de campanhas nao traz imagens nem prompts: a fase sai do status.
const STATUS_INFO = {
  briefing: {phase: 0, action: 'Continuar'},
  image_ready: {phase: 1, action: 'Aprovar imagens'},
  image_approved: {phase: 2, action: 'Revisar roteiro'},
  script_ready: {phase: 2, action: 'Criar vídeo'},
  video_ready: {phase: 2, action: 'Aprovar vídeos'},
  video_approved: {phase: 3, action: 'Publicar'},
  ready_to_publish: {phase: 3, action: 'Publicar'},
  published: {phase: 4, action: 'Ver resultados'},
};

export function statusInfo(status) {
  return STATUS_INFO[status] || STATUS_INFO.briefing;
}

// Proximo passo concreto do cartao "Continue de onde parou". Em preparacao,
// "continuar" nao dizia nada: aqui sai a referencia, os prompts ou as cores.
export function nextStepLabel(c) {
  if (!c) return '';
  if (c.status !== 'briefing') return statusInfo(c.status).action.toLowerCase();
  if (!Number(c.has_reference)) return 'enviar a foto de referência da modelo';
  if (!Number(c.has_prompts)) return 'gerar os prompts em Definir look';
  const total = colorList(c.color).length || 1;
  const feitas = Math.min(Number(c.images || 0), total);
  if (total === 1) return 'criar a imagem no gerador';
  return feitas ? `criar as imagens (${feitas} de ${total} cores prontas)` : `criar as imagens das ${total} cores`;
}

// Fase atual (0-3) ou 4 quando publicada; a cor da etiqueta segue a fase.
export function phaseTone(status) {
  const {phase} = statusInfo(status);
  return phase >= 4 ? 'done' : PHASES[phase].id;
}

export function colorList(value) {
  return String(value || '').split(/[,;|\n]+/).map(v => v.trim()).filter(Boolean);
}

const SWATCHES = [
  [/off.?white|gelo|creme|marfim|natural|cru/, '#F1ECE2'],
  [/branc/, '#FFFFFF'],
  [/pret|black|grafite escuro/, '#17141F'],
  [/grafite|chumbo|cinza|mescla/, '#8A8794'],
  [/marinho|navy/, '#1F2D5C'],
  [/azul|jeans|denim|celeste/, '#5B85D9'],
  [/verde.?militar|oliva|musgo/, '#5E6B3A'],
  [/verde|menta/, '#3FA66A'],
  [/vinho|bord[oô]|marsala/, '#7A1F35'],
  [/vermelh|red/, '#D93A3A'],
  [/pink|rosa.?choque|magenta/, '#E0408A'],
  [/rosa|ros[eé]|blush/, '#E89BB5'],
  [/lil[aá]s|lavanda|roxo|violeta/, '#9C86E0'],
  [/amarel|mostarda/, '#E8B931'],
  [/laranja|coral|terracota/, '#E8743B'],
  [/caramelo|camel|marrom|chocolate|caf[eé]/, '#8B5A3C'],
  [/bege|nude|areia|cappuccino|taupe/, '#D8C3A5'],
  [/tie.?dye|estampad|colorid|multi/, 'conic-gradient(#E89BB5, #9C86E0, #5B85D9, #3FA66A, #E8B931, #E89BB5)'],
];

// Cor aproximada pelo nome. Sem correspondencia, a bolinha fica neutra e o
// nome escrito continua sendo a informacao principal.
export function swatchFor(name) {
  const key = String(name || '').toLocaleLowerCase('pt-BR');
  const hit = SWATCHES.find(([pattern]) => pattern.test(key));
  return hit ? hit[1] : '#C9C4D6';
}
