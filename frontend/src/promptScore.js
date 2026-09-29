// Nota do prompt de video. Nao chama IA: sao checagens rapidas do texto que
// explicam por que um gerador (Grok ou Flow) costuma se perder. A nota e um
// alerta, nao uma garantia de que o video vai sair bom.

const ACTIONS = [
  ['aproxima', 'aproximar da câmera'],
  ['caminh', 'caminhar'],
  ['agach', 'agachar'],
  ['along', 'alongar'],
  ['de costas', 'virar de costas'],
  ['gir', 'girar'],
  ['contra a luz', 'mostrar contra a luz'],
  ['detalhe de perto', 'close no detalhe'],
  ['ângulo baixo', 'câmera baixa'],
  ['pula', 'pular'],
  ['senta', 'sentar'],
];

// Atributos que o proprio prompt costuma proibir de inventar.
const ATTRIBUTES = [
  ['compress', 'compressão'],
  ['elastic', 'elasticidade'],
  ['stretch', 'elasticidade (stretch)'],
  ['suporte', 'suporte'],
  ['conforto', 'conforto'],
  ['macie', 'maciez'],
];

function speechLines(text) {
  const lines = [];
  const re = /(?:Fala[^:]*|Ela diz|Narração|She says|says):\s*["“]([^"”]+)["”]/gi;
  let m;
  while ((m = re.exec(text))) lines.push((m[1] || '').trim());
  return lines;
}

const words = s => (s.match(/[\p{L}\p{N}]+/gu) || []).length;

export function scorePrompt(text) {
  const prompt = String(text || '');
  if (!prompt.trim()) return null;
  const low = prompt.toLowerCase();
  const issues = [];
  let score = 10;
  const hit = (points, message) => { score -= points; issues.push(message); };

  if (prompt.length > 3000) hit(2, `Texto muito longo (${prompt.length} caracteres). Acima de 3.000 o gerador costuma ignorar partes.`);
  else if (prompt.length > 2000) hit(1, `Texto longo (${prompt.length} caracteres). Prompts mais curtos são seguidos com mais fidelidade.`);

  const speech = speechLines(prompt);
  const outsideSpeech = speech.reduce((acc, line) => acc.split(line.toLowerCase()).join(' '), low);
  const totalWords = speech.reduce((n, line) => n + words(line), 0);
  if (totalWords > 50) hit(2, `Fala longa demais: ${totalWords} palavras em 15s. A voz corre ou é cortada. O ideal é até 46.`);
  else if (totalWords > 46) hit(1, `Fala no limite: ${totalWords} palavras em 15s.`);
  if (speech[0] && words(speech[0]) > 14) hit(1, `O gancho (0–4s) tem ${words(speech[0])} palavras. Em 4 segundos cabem até 14.`);

  const actions = ACTIONS.filter(([needle]) => outsideSpeech.includes(needle)).map(([, label]) => label);
  if (actions.length >= 6) hit(3, `Ações e ângulos demais para 15s (${actions.length}): ${actions.join(', ')}. Escolha 2 ou 3.`);
  else if (actions.length >= 4) hit(1, `Muitas ações e ângulos para 15s (${actions.length}): ${actions.join(', ')}.`);

  const forbidIdx = low.search(/não inventar|nao inventar/);
  if (forbidIdx >= 0) {
    const forbidEnd = low.indexOf('.', forbidIdx);
    const before = low.slice(0, forbidIdx);
    const after = forbidEnd >= 0 ? low.slice(forbidEnd) : '';
    const clash = ATTRIBUTES.filter(([needle]) => (before + after).includes(needle)).map(([, label]) => label);
    if (clash.length) hit(2, `Contradição: o prompt pede para mostrar ${clash.join(', ')} e depois proíbe inventar isso. Revise as notas do operador.`);
  }

  const spokenScenes = [['contra a luz', 'contra a luz'], ['transparên', 'transparência'], ['cobertura', 'cobertura']];
  const promised = spokenScenes.filter(([needle]) => speech.some(line => line.toLowerCase().includes(needle)))
    .filter(([needle]) => !outsideSpeech.includes(needle)).map(([, label]) => label);
  if (promised.length) hit(1, `A fala cita ${promised.join(' e ')}, mas nenhuma cena mostra isso.`);

  const handRules = (low.match(/\bmãos?\b/g) || []).length;
  if (handRules >= 7) hit(1, `Regras demais para as mãos (${handRules} menções). O gerador costuma travar os gestos.`);

  score = Math.max(1, Math.min(10, Math.round(score)));
  const tone = score >= 8 ? 'good' : score >= 5 ? 'warn' : 'bad';
  const label = score >= 8 ? 'Bom' : score >= 5 ? 'Atenção' : 'Arriscado';
  return { score, tone, label, issues };
}
