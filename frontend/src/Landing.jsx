import { useEffect, useState } from 'react';
import { ArrowLeft, ArrowRight, Camera, Clapperboard, Footprints, Hand, Mic, Scissors, ShoppingBag } from 'lucide-react';
import { tiktokLogo } from './serviceLogos';
import { isMobileDevice } from './device';

// Pagina de entrada para quem ainda nao entrou: o nome do estudio, o botao
// de acesso e atalhos para as ferramentas usadas em volta da Fabrica. Os
// atalhos sao links simples -- nenhum depende de login nem do servidor.
const SERVICES = [
  {id: 'grok', label: 'Grok Imagine', hint: 'Gerar imagem e vídeo', href: 'https://grok.com/imagine', img: '/brand/grok-mark.png'},
  {id: 'flow', label: 'Google Flow', hint: 'Vídeo em 1080p', href: 'https://labs.google/fx/tools/flow', img: '/brand/labs.png'},
  {id: 'capcut', label: 'CapCut', hint: 'Montar e legendar', href: 'https://www.capcut.com/', icon: Scissors},
  {id: 'studio', label: 'TikTok Studio', hint: 'Publicar e medir', href: 'https://www.tiktok.com/tiktokstudio', img: tiktokLogo},
  {id: 'instagram', label: 'Instagram', hint: 'Reels', href: 'https://www.instagram.com/', icon: Camera},
  {id: 'shopee', label: 'Shopee', hint: 'Central do vendedor', href: 'https://seller.shopee.com.br/', icon: ShoppingBag},
];

const FORMATS = [
  {icon: Mic, title: 'Com fala', text: 'A modelo apresenta o produto com gancho, prova e chamada.'},
  {icon: Footprints, title: 'Só movimento', text: 'Fit check sem fala: o caimento conta a história.'},
  {icon: Hand, title: 'POV', text: 'Primeira pessoa, só as mãos e o produto em foco.'},
];

export function Landing({setup, renderLogin}){
  // "#/entrar" abre direto no formulario (link salvo, botao Voltar do navegador).
  const [login,setLogin]=useState(()=>location.hash==='#/entrar');
  useEffect(()=>{
    const sync=()=>setLogin(location.hash==='#/entrar');
    window.addEventListener('hashchange',sync);
    return()=>window.removeEventListener('hashchange',sync);
  },[]);
  const open=value=>{location.hash=value?'/entrar':'/';setLogin(value)};
  if(login) return renderLogin(()=>open(false));
  const target=isMobileDevice()?undefined:'_blank';
  const cta=setup?'Criar acesso':'Entrar no estúdio';
  return <main className="landing">
    <header className="landing-top">
      <span className="landing-brand"><span className="logo" aria-hidden="true"><Clapperboard size={18}/></span><strong>Fábrica TikTok</strong></span>
      <button type="button" className="primary" onClick={()=>open(true)}>{setup?'Criar acesso':'Entrar'}</button>
    </header>

    <section className="landing-hero">
      <span className="eyebrow">ESTÚDIO DE VÍDEOS DE PRODUTO</span>
      <h1>Fábrica TikTok</h1>
      <p>Prompts realistas para vídeos que vendem no TikTok, no Reels e na Shopee, do briefing à publicação.</p>
      <button type="button" className="primary landing-cta" onClick={()=>open(true)}>{cta} <ArrowRight size={18}/></button>
    </section>

    <section className="landing-formats" aria-label="Formatos de vídeo">
      {FORMATS.map(({icon:Icon,title,text})=><div key={title}><Icon size={20} aria-hidden="true"/><strong>{title}</strong><small>{text}</small></div>)}
    </section>

    <section className="landing-services">
      <h2>Acesso rápido</h2>
      <div className="landing-service-grid">
        {SERVICES.map(({id,label,hint,href,img,icon:Icon})=><a key={id} className={'landing-service landing-'+id} href={href} target={target} rel="noopener noreferrer">
          <span className="landing-service-mark" aria-hidden="true">{img?<img src={img} alt=""/>:<Icon size={20}/>}</span>
          <span><strong>{label}</strong><small>{hint}</small></span>
        </a>)}
      </div>
    </section>
  </main>;
}

export function BackToLanding({onBack}){
  return <button type="button" className="landing-back" onClick={onBack}><ArrowLeft size={16}/> Voltar</button>;
}
