// Opcoes opt-in e experimentais da sequencia de 2 e 3 clipes (services/story_arcs.py): giro do corpo POR CLIPE
// (CLIP_TURNS) e close de textura. Vao so no pedido da sequencia, sem gravar no briefing (mudar o briefing apagaria a
// imagem aprovada). '' = o giro da campanha, como sempre.
export const CLIP_TURN_OPTIONS=[['','Igual à campanha'],['frente','Sempre de frente'],['leve_lado','Leve de lado (20 a 30°)'],
  ['lado','De lado, até o perfil'],['costas','De costas por no máximo 1 s'],['costas_pausa','De costas 3 a 6 s, olhando por cima do ombro uma vez']];

export const resizeTurns=(turns,count)=>Array.from({length:count},(_,i)=>(turns||[])[i]||'');

// So manda as opcoes quando ligadas: desligadas, o pedido (e os prompts) ficam iguais aos de antes.
export const arcOptions=(turns,count,texture,seconds,hookVisual)=>{
  const list=resizeTurns(turns,count);
  return {clip_turns:list.some(Boolean)?list:undefined,texture:texture?true:undefined,
    seconds:seconds===10?10:undefined,hook_visual:hookVisual||undefined};
};

// Clipe de 10 s para o Flow (Gemini Omni Flash, 720p): falas de 33 a 40 palavras, sem TikTok nos prompts e convite em
// "link aqui embaixo". O arco "Dor e FOMO" so existe nesse modo, com 3 clipes (30 s).
export const SECONDS_OPTIONS=[[15,'15 s','Grok ou Flow: o formato de sempre'],[10,'10 s (Flow)','Gemini Omni Flash, 720p: 3 clipes = 30 s']];
export const ARC_10S_OPTIONS=[['dor','Dor e FOMO','“Eu tinha medo de…” e um último motivo que quase ninguém repara, fechado no clipe 3']];
// Ganchos de CAMERA do clipe 1 (so no espelho): o clipe abre num primeiro quadro proprio (a mao cobrindo o quadro, o ambiente
// vazio...) e ela revela a peca; as falas e os clipes 2 e 3 nao mudam. Os ids sao os de HOOK_VISUALS (services/story_arcs.py).
export const HOOK_VISUAL_OPTIONS=[['','Sem gancho de câmera (o de sempre)'],['espia','Espia pela borda (não testado)'],
  ['corre','Vem correndo até o espelho (não testado)'],['dedo','Dedo na câmera (não testado)']];
// O arco de 10 s so tem 3 clipes; ao voltar para 15 s ele sai da lista.
export const arcsFor=(seconds,base)=>seconds===10?[...base,...ARC_10S_OPTIONS]:base;
export const clipsFor=(arc,clips)=>arc==='dor'?3:clips;
export const arcFor=(seconds,arc)=>seconds!==10&&arc==='dor'?'motivos':arc;
export const windowsLabel=seconds=>seconds===10?'0–3 s, 3–8 s e 8–10 s':'0–4 s, 4–12 s e 12–15 s';
