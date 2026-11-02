// O aviso de erro e desenhado como texto. Um objeto Error (ou qualquer outra coisa) como filho do React derruba a pagina
// inteira ("Objects are not valid as a React child"): era o que acontecia ao tocar em "Experimental: Agente do Grok" quando a
// montagem da mensagem falhava.
export const errorText = value => {
  if (typeof value === 'string') return value;
  if (value && typeof value.message === 'string' && value.message) return value.message;
  return value ? 'Algo deu errado. Tente de novo.' : '';
};
