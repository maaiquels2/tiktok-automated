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
  const re = /(?:Fala[^:]*|Ela diz|O que ela diz[^:]*|Narração|She says|says):\s*["“]([^"”]+)["”]/gi;
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

  // Limite real do Grok. O prompt completo usa ~3.900 de proposito: no teste
  // real ele gerou videos melhores que o Guia curto.
  if (prompt.length > 4000) hit(2, `Passa do limite do Grok (${prompt.length} de 4.000 caracteres): o fim do prompt é cortado.`);

  const speech = speechLines(prompt);
  const outsideSpeech = speech.reduce((acc, line) => acc.split(line.toLowerCase()).join(' '), low);
  const totalWords = speech.reduce((n, line) => n + words(line), 0);
  // Teste real: com 33 a 46 palavras sobraram 2 a 3 s de silencio. Quem vende
  // fala o clipe inteiro: 45 a 56 palavras ocupam os 15 s (acima de ~57 o
  // segundo teste real ja saiu um pouco acelerado).
  if (speech.length && totalWords < 40) hit(4, `Fala curta: ${totalWords} palavras. Vão sobrar segundos de silêncio no fim dos 15 s; o ideal é de 45 a 56.`);
  else if (speech.length && totalWords < 44) hit(2, `Fala um pouco curta: ${totalWords} palavras. Pode sobrar silêncio no fim; o ideal é de 45 a 56.`);
  else if (totalWords > 64) hit(2, `Fala longa demais: ${totalWords} palavras em 15s. A voz corre ou é cortada.`);
  else if (totalWords > 58) hit(1, `Fala um pouco acelerada: ${totalWords} palavras em 15s; o ideal é até 56.`);
  if (speech.length > 1 && words(speech[0]) > 20) hit(1, `O gancho tem ${words(speech[0])} palavras. Acima de 20 ele demora a prender.`);

  const actions = ACTIONS.filter(([needle]) => outsideSpeech.includes(needle)).map(([, label]) => label);
  if (actions.length >= 6) hit(3, `Ações e ângulos demais para 15s (${actions.length}): ${actions.join(', ')}. Escolha 2 ou 3.`);
  else if (actions.length >= 4) hit(1, `Muitas ações e ângulos para 15s (${actions.length}): ${actions.join(', ')}.`);

  // Teste real (biquíni com argolas, "Com fala"): a fala dizia "saída de praia amarrada na cintura" e "short jeans", e o
  // prompt pedia para mostrar a "regulagem lateral" e ajustar a barra. O Grok encenou tudo isso e amarrou laços na
  // calcinha. Só o formato "3 jeitos de usar" mostra outras peças de propósito.
  const threeLooks = /3 jeitos de usar|três looks/.test(low);
  const otherPieces = [...new Set(speech.flatMap(line => line.toLowerCase()
    .match(/saída de praia|canga|kimono|short(?:inho)? jeans|(?:camisa|jaqueta|blusa|calça|saia) (?:aberta )?por cima|camisa aberta/g) || []))];
  if (otherPieces.length && !threeLooks)
    hit(2, `A fala cita outras peças (${otherPieces.join(', ')}) fora do formato "3 jeitos de usar": o gerador costuma encenar isso e trocar ou amarrar a peça. Fale só da peça da imagem.`);
  if (/regulagem lateral|regula(?:r|gem) (?:d[ao] |na )?(?:lateral|calcinha)|ajust\w+ (?:a |as |o |os )?(?:\w+ )?(?:lateral|laterais|calcinha|tiras?|cord[ãa]o)|desamarr\w*|tocando a barra d[oa] (?:biqu|maiô)/.test(outsideSpeech))
    hit(3, 'O prompt cita regulagem ou ajuste da lateral da peça (ex.: "regulagem lateral", "ajustar a calcinha"): o gerador costuma amarrar um laço que a peça não tem. Descreva só o que se vê (ex.: "argolas douradas nas laterais, sem laço").');

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

  // Guia oficial do Grok: sem movimento de câmera e luz nomeados, a decisão
  // mais importante do vídeo fica por conta do acaso.
  if (!/dolly|travelling|acompanhamento|aproximação|pan\b|panorâmica|tilt|órbita|orbit|zoom|câmera fixa|fixa na altura|câmera na mão|na mão|tripé/.test(outsideSpeech))
    hit(1, 'Movimento de câmera não nomeado. O guia do Grok pede para dizer como a câmera se move (ex.: "dolly-in lento", "câmera fixa", "câmera na mão").');
  if (!/\bluz\b|ilumina|golden hour|contraluz/.test(outsideSpeech))
    hit(1, 'Luz não nomeada. Diga qual luz usar (ex.: "a mesma luz da imagem", "luz natural de janela").');

  // Contradicao real (nao contagem de palavras): uma mao presa no celular e
  // uma acao que pede as duas. Foi o que gerou a terceira mao no teste real.
  if (/celular (sempre )?na mão|segura o celular/.test(outsideSpeech) && /com as duas mãos/.test(outsideSpeech))
    hit(2, 'Contradição de mãos: uma mão segura o celular e uma ação pede as duas mãos. O gerador costuma inventar uma terceira mão.');

  score = Math.max(1, Math.min(10, Math.round(score)));
  const tone = score >= 8 ? 'good' : score >= 5 ? 'warn' : 'bad';
  const label = score >= 8 ? 'Bom' : score >= 5 ? 'Atenção' : 'Arriscado';
  return { score, tone, label, issues };
}
