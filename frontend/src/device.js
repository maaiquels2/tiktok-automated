export function getDeviceInfo(nav = globalThis.navigator) {
  const ua = nav?.userAgent || '';
  const platform = nav?.platform || '';
  const result = (type, label) => ({type, label, isMobile: type === 'phone' || type === 'tablet'});
  if (/iPhone|iPod/i.test(ua)) return result('phone', 'iPhone');
  // iPadOS can identify as a Mac when requesting desktop websites.
  if (/iPad/i.test(ua) || (platform === 'MacIntel' && nav?.maxTouchPoints > 1)) {
    return result('tablet', 'iPad');
  }
  if (/Android/i.test(ua)) {
    return /Mobile/i.test(ua) || nav?.userAgentData?.mobile === true
      ? result('phone', 'Celular Android') : result('tablet', 'Tablet Android');
  }
  if (nav?.userAgentData?.mobile === true || /Mobile|Windows Phone/i.test(ua)) {
    return result('phone', 'Celular');
  }
  // A small window or a touch screen alone does not make a computer a phone.
  if (/Windows|Macintosh|Mac OS|Linux|CrOS|X11/i.test(ua) || /Win|Mac|Linux/i.test(platform)) {
    return result('desktop', 'Computador');
  }
  return result('unknown', 'Dispositivo');
}

export function isMobileDevice(nav = globalThis.navigator) {
  return getDeviceInfo(nav).isMobile;
}
