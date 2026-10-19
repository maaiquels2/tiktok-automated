import { afterEach, describe, expect, it, vi } from 'vitest';
import { getDeviceInfo, isMobileDevice } from './device.js';
import { mobileServiceUrl, setCloudMode } from './serviceLinks.jsx';

const IPHONE = { userAgent: 'Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148' };
const IPAD_COMO_MAC = { userAgent: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15', platform: 'MacIntel', maxTouchPoints: 5 };
const MAC = { userAgent: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15', platform: 'MacIntel', maxTouchPoints: 0 };
const ANDROID_CELULAR = { userAgent: 'Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 Chrome/126 Mobile Safari/537.36' };
const ANDROID_TABLET = { userAgent: 'Mozilla/5.0 (Linux; Android 14; SM-X900) AppleWebKit/537.36 Chrome/126 Safari/537.36' };
const WINDOWS = { userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126 Safari/537.36', platform: 'Win32' };

describe('getDeviceInfo', () => {
  it.each([
    ['iPhone', IPHONE, 'phone', true],
    ['iPad que se apresenta como Mac (toque)', IPAD_COMO_MAC, 'tablet', true],
    ['Mac de verdade (sem toque)', MAC, 'desktop', false],
    ['Android celular', ANDROID_CELULAR, 'phone', true],
    ['Android tablet (sem "Mobile")', ANDROID_TABLET, 'tablet', true],
    ['Windows', WINDOWS, 'desktop', false],
    ['userAgentData.mobile = true', { userAgent: '', userAgentData: { mobile: true } }, 'phone', true],
    ['navegador desconhecido', { userAgent: 'curl/8', platform: '' }, 'unknown', false],
  ])('%s -> %s', (_nome, nav, tipo, movel) => {
    const info = getDeviceInfo(nav);
    expect(info.type).toBe(tipo);
    expect(info.isMobile).toBe(movel);
    expect(isMobileDevice(nav)).toBe(movel);
  });

  it('sem navigator não quebra', () => {
    // Node 21+ tem um navigator global ("Node.js/22"): sem tirar, o teste passava no Node 20 e falhava no CI.
    vi.stubGlobal('navigator', undefined);
    try {
      expect(getDeviceInfo(undefined).type).toBe('unknown');
    } finally {
      vi.unstubAllGlobals();
    }
  });
});

describe('mobileServiceUrl', () => {
  afterEach(() => setCloudMode(false));

  it('no computador, fora da nuvem, não devolve link (usa o atalho automático)', () => {
    expect(mobileServiceUrl('grok', WINDOWS)).toBeNull();
  });

  it('no celular devolve os links diretos do Grok e do Flow', () => {
    expect(mobileServiceUrl('grok', IPHONE)).toBe('https://grok.com/imagine');
    expect(mobileServiceUrl('flow', IPHONE)).toBe('https://labs.google/fx/tools/flow');
  });

  it('na nuvem (Vercel) vale o link direto até no computador', () => {
    setCloudMode(true);
    expect(mobileServiceUrl('grok', WINDOWS)).toBe('https://grok.com/imagine');
  });

  it('serviço desconhecido não devolve nada', () => {
    expect(mobileServiceUrl('tiktok', IPHONE)).toBeNull();
  });
});
