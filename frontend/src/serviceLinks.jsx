import React from 'react';
import { tiktokLogo, tiktokStudioLogo } from './serviceLogos';
import { isMobileDevice } from './device';
export { isMobileDevice } from './device';

// A versao online (Vercel) nao roda Chrome/Playwright no servidor - so a
// versao local (no computador da pessoa) tem esse "atalho automatico".
// Na nuvem os botoes de Grok/Flow/TikTok Studio sempre viram links diretos,
// do mesmo jeito que ja acontece no celular.
let cloudMode = false;
export function setCloudMode(value) { cloudMode = !!value; }

function TikTokBrand({studio = false}) {
  // Crop only the presentation viewport; keep the supplied PNGs intact.
  return studio ? <span className="tiktok-studio-wordmark" aria-hidden="true"><img src={tiktokStudioLogo} alt=""/></span> :
    <><span className="tiktok-note" aria-hidden="true"><img src={tiktokLogo} alt=""/></span><span>TikTok</span></>;
}

// Grok and TikTok associate these HTTPS links with their iOS apps.
// Keep the native link click synchronous so iOS can hand it to the app.
export function mobileServiceUrl(service, nav = globalThis.navigator) {
  if (!isMobileDevice(nav) && !cloudMode) return null;
  return {grok: 'https://grok.com/imagine', flow: 'https://labs.google/fx/tools/flow'}[service] || null;
}

export function TikTokLaunchButtons({onOpenStudio, disabled, className = 'button', opening = false}) {
  const mobile = isMobileDevice() || cloudMode;
  // On mobile, use a native link without invoking the PC-launch callback.
  // On desktop, keep the configured Chrome profile for manual publication.
  return <span className="tiktok-launch-buttons">
    {mobile && !disabled ? <a className={`service-launch-link ${className} tiktok-brand-button is-tiktok-studio`}
      href="https://www.tiktok.com/" rel="noopener noreferrer" aria-label="TikTok Studio" title="Abrir TikTok neste aparelho"><TikTokBrand studio/></a> :
    <button type="button" className={`${className} tiktok-brand-button is-tiktok-studio`} disabled={disabled} onClick={onOpenStudio} aria-label={opening?'Abrindo TikTok Studio':'TikTok Studio'} title="TikTok Studio">
      {opening?'Abrindo…':<TikTokBrand studio/>}
    </button>}
    {disabled?<button type="button" className={`${className} tiktok-brand-button is-tiktok`} disabled aria-label="TikTok"><TikTokBrand/></button>:
      <a className={`service-launch-link ${className} tiktok-brand-button is-tiktok`} href="https://www.tiktok.com/"
        target={mobile?undefined:'_blank'} rel="noopener noreferrer" aria-label="TikTok" title="TikTok"><TikTokBrand/></a>}
  </span>;
}

export function ServiceLaunch({service, onClick, disabled, children, className = '', ...props}) {
  const href = mobileServiceUrl(service);
  if (!href || disabled) {
    return <button {...props} type="button" className={className} disabled={disabled} onClick={onClick}>{children}</button>;
  }
  return <a {...props} className={`service-launch-link ${className}`} href={href}
    target={service === 'flow' ? '_blank' : undefined} rel="noopener noreferrer"
    onClick={onClick}>{children}</a>;
}
