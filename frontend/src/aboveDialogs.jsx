import { useEffect, useState } from 'react';
import { createPortal } from 'react-dom';

// Janela aberta com showModal() vai para a camada de cima da página: tudo que fica fora dela, aviso incluso, fica
// atrás do fundo escurecido e não recebe clique. Teste real: o aviso de versão nova apareceu com a "Nova campanha"
// aberta, mas escondido, e o computador continuou na versão antiga. Com uma janela aberta, o aviso vai para dentro dela.
function openDialog() {
  const all = document.querySelectorAll('dialog[open]');
  return all.length ? all[all.length - 1] : null;
}

export function useOpenDialog() {
  const [dialog, setDialog] = useState(() => (typeof document === 'undefined' ? null : openDialog()));
  useEffect(() => {
    const update = () => setDialog(openDialog());
    const observer = new MutationObserver(update);
    observer.observe(document.body, { subtree: true, childList: true, attributes: true, attributeFilter: ['open'] });
    update();
    return () => observer.disconnect();
  }, []);
  return dialog;
}

export function AboveDialogs({ children }) {
  const dialog = useOpenDialog();
  return dialog ? createPortal(children, dialog) : children;
}
