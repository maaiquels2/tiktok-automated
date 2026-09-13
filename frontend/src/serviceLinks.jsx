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
  const realMobile = isMobileDevice();
  const mobile = realMobile || cloudMode;
  // On a real phone/tablet, keep the same-tab handoff (so iOS/Android can
  // switch to the native app). On a desktop browser - even in cloud mode,
  // where we still skip the server automation - open in a new tab instead,
  // so people do not lose the Fabrica TikTok page they were on.
  const target = realMobile ? undefined : '_blank';
  // On mobile, use a native link without invoking the PC-launch callback.
  // On desktop, keep the configured Chrome profile for manual publication.
  return <span className="tiktok-launch-buttons">
    {mobile && !disabled ? <a className={`service-launch-link ${className} tiktok-brand-button is-tiktok-studio`}
      href="https://www.tiktok.com/" target={target} rel="noopener noreferrer" aria-label="TikTok Studio" title="Abrir TikTok neste aparelho"><TikTokBrand studio/></a> :
    <button type="button" className={`${className} tiktok-brand-button is-tiktok-studio`} disabled={disabled} onClick={onOpenStudio} aria-label={opening?'Abrindo TikTok Studio':'TikTok Studio'} title="TikTok Studio">
      {opening?'Abrindo…':<TikTokBrand studio/>}
    </button>}
    {disabled?<button type="button" className={`${className} tiktok-brand-button is-tiktok`} disabled aria-label="TikTok"><TikTokBrand/></button>:
      <a className={`service-launch-link ${className} tiktok-brand-button is-tiktok`} href="https://www.tiktok.com/"
        target={target} rel="noopener noreferrer" aria-label="TikTok" title="TikTok"><TikTokBrand/></a>}
  </span>;
}

export function ServiceLaunch({service, onClick, disabled, children, className = '', ...props}) {
  const href = mobileServiceUrl(service);
  if (!href || disabled) {
    return <button {...props} type="button" className={className} disabled={disabled} onClick={onClick}>{children}</button>;
  }
  // On a real phone, Grok keeps a same-tab handoff (so iOS can switch to the
  // app) while Flow already opened a new tab; on desktop (cloud mode included)
  // every service opens in a new tab, so the person does not lose this page.
  const realMobile = isMobileDevice();
  const target = realMobile ? (service === 'flow' ? '_blank' : undefined) : '_blank';
  return <a {...props} className={`service-launch-link ${className}`} href={href}
    target={target} rel="noopener noreferrer"
    onClick={onClick}>{children}</a>;
}
