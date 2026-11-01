// Opcoes opt-in e experimentais da sequencia de 2 e 3 clipes (services/story_arcs.py): giro do corpo POR CLIPE
// (CLIP_TURNS) e close de textura. Vao so no pedido da sequencia, sem gravar no briefing (mudar o briefing apagaria a
// imagem aprovada). '' = o giro da campanha, como sempre.
export const CLIP_TURN_OPTIONS=[['','Igual à campanha'],['frente','Sempre de frente'],['leve_lado','Leve de lado (20 a 30°)'],
  ['lado','De lado, até o perfil'],['costas','De costas por no máximo 1 s'],['costas_pausa','De costas 3 a 6 s, olhando por cima do ombro uma vez']];

export const resizeTurns=(turns,count)=>Array.from({length:count},(_,i)=>(turns||[])[i]||'');

// So manda as opcoes quando ligadas: desligadas, o pedido (e os prompts) ficam iguais aos de antes.
export const arcOptions=(turns,count,texture)=>{
  const list=resizeTurns(turns,count);
  return {clip_turns:list.some(Boolean)?list:undefined,texture:texture?true:undefined};
};
