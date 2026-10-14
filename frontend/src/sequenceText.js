// O aviso de poucos fatos vem do servidor e manda escrever "no campo Detalhes" (certo no formulario manual).
// No painel da sequencia e na criacao automatica o campo e outro: editar o Detalhes de campanha com imagem
// aprovada apaga a imagem e os prompts. Teste real: o aviso mandava a pessoa justamente para esse campo.
export const FEW_FACTS='no campo Detalhes';
export const isFewFacts=message=>String(message||'').includes(FEW_FACTS);
export const pointToFacts=(message,where)=>String(message||'').split(FEW_FACTS).join(`no campo Fatos da peça ${where}`);
