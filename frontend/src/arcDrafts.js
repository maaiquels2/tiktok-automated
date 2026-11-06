// Falas que o operador digitou na caixa de cada clipe da sequencia e que ainda nao viraram prompt.
// O prompt, o Guia, o Extend Video e a mensagem do agente so mudam quando o servidor monta de novo com as falas
// editadas; enquanto a caixa difere do que foi montado, copiar qualquer um deles leva a fala ANTIGA.

export const clipBase = clip => (clip.lines || []).join('\n');

// Um booleano por clipe: a caixa difere do que foi montado?
export const dirtyClips = (clips, drafts) =>
  (clips || []).map((clip, index) => (drafts?.[index] ?? clipBase(clip)) !== clipBase(clip));

export const anyDirty = (clips, drafts) => dirtyClips(clips, drafts).some(Boolean);

// Sem a lista de rascunhos, a caixa mostra as falas montadas.
export const baseDrafts = clips => (clips || []).map(clipBase);

// Os rascunhos nao aplicados sobrevivem a troca de cor (o componente remonta): ficam guardados por campanha, cor, arco e
// numero de clipes, e voltam quando a mesma sequencia e montada de novo.
export const draftKey = (campaignId, variantId, arc, clips, seconds) =>
  `${campaignId}|${variantId || 'base'}|${arc}|${clips}${seconds === 10 ? '|10s' : ''}`;

export const restoreDrafts = (clips, stashed) =>
  Array.isArray(stashed) && stashed.length === (clips || []).length ? stashed : baseDrafts(clips);
