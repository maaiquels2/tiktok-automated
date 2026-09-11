"""Assisted navigation only. No generation clicks, login, product selection or posting.

Flow and Grok share one Playwright persistent Chromium (tabs). Studio uses the Micaela CDP clone.
Interaction on Grok/Flow stays manual (no scripted generation).
"""
import asyncio
import atexit
import os
import socket
import json
import subprocess
import threading
import uuid
from pathlib import Path
from werkzeug.utils import secure_filename
from concurrent.futures import TimeoutError

URLS = {'flow':'https://labs.google/fx/tools/flow', 'grok':'https://grok.com/imagine',
        'studio':'https://www.tiktok.com/tiktokstudio/upload',
        'studio_content':'https://www.tiktok.com/tiktokstudio/content'}


def installed_browser():
    """Use a system browser executable, always with our separate user-data directory."""
    roots = [os.environ.get('PROGRAMFILES'), os.environ.get('PROGRAMFILES(X86)'),
             os.environ.get('LOCALAPPDATA')]
    for relative in ['Google/Chrome/Application/chrome.exe', 'Microsoft/Edge/Application/msedge.exe']:
        for root in roots:
            if root:
                candidate = Path(root)/relative
                if candidate.is_file():
                    return str(candidate)
    raise RuntimeError('Chrome ou Edge não encontrado. Instale um desses navegadores e tente novamente. O aplicativo usará um perfil separado.')


def existing_chrome_profile():
    """Resolve Chrome profile folder from env, identity hint, or Local State labels.

    Hint may be a folder ("Profile 7") OR a visible Chrome name ("Micaela").
    Only Local State labels are read; cookies/passwords are never opened.
    """
    root_value = os.environ.get('FABRICA_CHROME_USER_DATA')
    root = Path(root_value).expanduser() if root_value else Path(os.environ.get('LOCALAPPDATA', ''))/'Google'/'Chrome'/'User Data'
    requested = os.environ.get('FABRICA_CHROME_PROFILE') or os.environ.get('FABRICA_MICAELA_PROFILE')
    if not requested:
        try:
            from services.studio_identity import load_identity
            requested = (load_identity().get('chrome_profile_hint') or '').strip() or None
        except Exception:
            requested = None

    def _load_cache():
        state_path = root / 'Local State'
        if not state_path.is_file():
            raise RuntimeError('Nao encontrei os perfis do Chrome. Defina FABRICA_CHROME_USER_DATA com a pasta User Data do Chrome.')
        try:
            state = json.loads(state_path.read_text(encoding='utf-8'))
            return state.get('profile', {}).get('info_cache', {}) or {}
        except (OSError, ValueError) as exc:
            raise RuntimeError('Nao foi possivel ler os nomes dos perfis do Chrome. Feche o Chrome e tente novamente.') from exc

    def _resolve_hint(hint: str):
        profile = Path(hint)
        if profile.is_absolute() and profile.parent.name == 'User Data':
            if profile.is_dir():
                return profile.parent, profile.name
            raise RuntimeError(f'Perfil Chrome nao encontrado: {profile}')
        if profile.is_absolute() and profile.parent == root:
            if profile.is_dir():
                return root, profile.name
            raise RuntimeError(f'Perfil Chrome nao encontrado: {profile}')
        # Exact folder under User Data
        folder = root / hint
        if folder.is_dir() and (folder / 'Preferences').exists() or folder.is_dir():
            # Prefer real profile dirs
            if hint in ('Default',) or hint.startswith('Profile ') or (folder / 'Preferences').exists():
                return root, hint
        cache = _load_cache()
        needle = hint.casefold().lstrip('@').strip()
        matches = []
        for directory, info in cache.items():
            labels = [
                directory,
                str(info.get('name') or ''),
                str(info.get('user_name') or ''),
                str(info.get('gaia_name') or ''),
                str(info.get('gaia_given_name') or ''),
            ]
            blob = ' '.join(labels).casefold()
            if needle == directory.casefold() or needle in [x.casefold() for x in labels if x]:
                matches.append(directory)
            elif needle and needle in blob:
                matches.append(directory)
        # de-dupe preserve order
        seen = set(); uniq = []
        for m in matches:
            if m not in seen:
                seen.add(m); uniq.append(m)
        if len(uniq) == 1:
            return root, uniq[0]
        if len(uniq) > 1:
            opts = ', '.join(f'{d} ({(cache.get(d) or {}).get("name") or d})' for d in uniq[:6])
            raise RuntimeError(f'Varios perfis Chrome batem com "{hint}": {opts}. Use a pasta exata (ex.: Profile 7).')
        # list available for help
        avail = ', '.join(f'{d}={(cache.get(d) or {}).get("name") or "?"}' for d in list(cache)[:12]) or '(nenhum)'
        raise RuntimeError(f'Perfil Chrome "{hint}" nao encontrado. Disponiveis: {avail}')

    if requested:
        return _resolve_hint(requested)

    cache = _load_cache()
    matches = []
    for directory, info in cache.items():
        values = ' '.join(str(info.get(key, '')) for key in ('name', 'user_name', 'gaia_name', 'gaia_given_name')).casefold()
        if 'micaela' in values or 'micamaierttk' in values:
            matches.append(directory)
    if len(matches) != 1:
        if not matches:
            raise RuntimeError('Nao encontrei um perfil Chrome da Micaela. Em Identidade, preencha Perfil Chrome (ex.: Profile 7) ou o nome que aparece no Chrome.')
        raise RuntimeError('Encontrei mais de um perfil possivel da Micaela. Em Identidade, use a pasta exata (ex.: Profile 7).')
    return root, matches[0]



def chrome_profile_busy(chrome_root):
    """True if Chrome appears to hold the User Data lock (must be closed for Playwright)."""
    root = Path(chrome_root)
    for name in ('SingletonLock', 'lockfile'):
        if (root / name).exists():
            return True
    try:
        import subprocess
        out = subprocess.check_output(
            ['tasklist', '/FI', 'IMAGENAME eq chrome.exe', '/FO', 'CSV', '/NH'],
            stderr=subprocess.DEVNULL, text=True, encoding='utf-8', errors='ignore'
        )
        if 'chrome.exe' in out.casefold():
            return True
    except Exception:
        pass
    return False





def kill_micaela_cdp_chrome(user_data_dir):
    """Best-effort: stop Chrome processes that hold the factory micaela-cdp profile."""
    import time
    ud = str(Path(user_data_dir)).replace("/", "\\")
    killed = 0
    # PowerShell is reliable; wmic CSV breaks on commas inside CommandLine
    ps = (
        "$ud = [regex]::Escape('" + ud.replace("'", "''") + "');"
        "Get-CimInstance Win32_Process -Filter \"Name='chrome.exe'\" |"
        " Where-Object { $_.CommandLine -and ("
        "   $_.CommandLine -match 'micaela-cdp' -or $_.CommandLine -match $ud"
        " )} | ForEach-Object {"
        "  try { Stop-Process -Id $_.ProcessId -Force -ErrorAction Stop; $_.ProcessId } catch {}"
        "}"
    )
    try:
        out = subprocess.check_output(
            ["powershell", "-NoProfile", "-Command", ps],
            stderr=subprocess.DEVNULL, text=True, encoding="utf-8", errors="ignore",
            timeout=30,
        )
        killed = sum(1 for line in out.splitlines() if line.strip().isdigit())
    except Exception:
        killed = 0
    if killed:
        time.sleep(1.5)
    # clear stale DevTools port file ONLY after processes are gone
    dt = Path(user_data_dir) / "DevToolsActivePort"
    if dt.exists():
        try:
            dt.unlink()
        except OSError:
            pass
    # Singleton lock leftovers that block a new Chrome
    for name in ("SingletonLock", "SingletonCookie", "SingletonSocket", "lockfile"):
        p = Path(user_data_dir) / name
        if p.exists() or p.is_symlink():
            try:
                p.unlink()
            except OSError:
                pass
    return killed


def pick_free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def wait_devtools_active_port(user_data_dir, timeout=50):
    """Chrome writes DevToolsActivePort inside user-data-dir when CDP is up."""
    import time
    path = Path(user_data_dir) / "DevToolsActivePort"
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        try:
            if path.is_file():
                lines = path.read_text(encoding="utf-8", errors="ignore").strip().splitlines()
                if lines:
                    port = int(lines[0].strip())
                    with socket.create_connection(("127.0.0.1", port), timeout=1):
                        return port
        except (OSError, ValueError) as exc:
            last = exc
        time.sleep(0.35)
    raise RuntimeError(
        f"Chrome nao publicou DevToolsActivePort em {user_data_dir}. Detalhe: {last}"
    )


def ensure_micaela_cdp_user_data(profile_root, chrome_root, chrome_profile):
    """Clone Micaela profile into a factory-owned user-data-dir that accepts --remote-debugging-port.

    Chrome often ignores CDP when launched against the live User Data folder. A dedicated
    clone under browser_profiles keeps the TikTok/Google session and enables debugging.
    """
    import shutil
    try:
        from services.studio_identity import load_identity
        _folder = load_identity().get("cdp_folder") or "creator-cdp"
    except Exception:
        _folder = "creator-cdp"
    dest = Path(profile_root) / _folder
    dest.mkdir(parents=True, exist_ok=True)
    default_dir = dest / "Default"
    marker = dest / ".seeded_from"
    src = Path(chrome_root) / chrome_profile
    if not src.is_dir():
        raise RuntimeError(f"Perfil Chrome nao encontrado: {src}. Ajuste Perfil Chrome na Identidade (pasta ex.: Profile 7).")
    need_seed = (not marker.exists()) or (not (default_dir / "Cookies").exists() and not (default_dir / "Network" / "Cookies").exists())
    if need_seed:
        if chrome_profile_busy(chrome_root):
            raise RuntimeError(
                "Na primeira coleta preciso copiar a sessao da Micaela. "
                "Feche TODAS as janelas do Google Chrome e tente de novo."
            )
        if default_dir.exists():
            shutil.rmtree(default_dir, ignore_errors=True)
        ignore = shutil.ignore_patterns(
            "Cache", "Code Cache", "GPUCache", "GrShaderCache", "ShaderCache",
            "Service Worker", "VideoDecodeStats", "Crashpad", "BrowserMetrics",
            "optimization_guide*", "DawnCache", "Media Cache", "Safe Browsing",
        )
        shutil.copytree(str(src), str(default_dir), ignore=ignore, dirs_exist_ok=True)
        # Minimal Local State so Chrome treats this as a normal user-data-dir
        local_state = dest / "Local State"
        if not local_state.exists():
            local_state.write_text('{"profile":{"last_used":"Default","info_cache":{"Default":{"name":"Micaela CDP"}}}}', encoding="utf-8")
        marker.write_text(f"{chrome_root}|{chrome_profile}", encoding="utf-8")
    return dest


def wait_cdp_ready(port, timeout=25):
    """Wait until Chrome remote debugging port accepts TCP."""
    import time
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=1):
                return True
        except OSError as exc:
            last = exc
            time.sleep(0.35)
    raise RuntimeError(f"Chrome nao abriu a porta de depuracao {port}. Detalhe: {last}")



def profile_dir_busy(directory):
    """True if a Chromium instance appears to lock this user-data-dir."""
    root = Path(directory)
    for name in ("SingletonLock", "SingletonCookie", "SingletonSocket", "lockfile"):
        if (root / name).exists():
            return True
    return False


class BrowserAssistant:
    def __init__(self, profile_root, media_root):
        self.profile_root = profile_root.resolve()
        self.media_root = media_root.resolve()
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self.loop.run_forever,daemon=True)
        self.thread.start()
        self.contexts = {}
        self.native = {}
        self.page_campaigns = {}
        self.download_tasks = set()
        self.playwright = None
        self.lock = threading.Lock()
        self.closed = False
        atexit.register(self.close)

    def open_flow_for_image(self,campaign_id):
        return self._request('flow',campaign_id)

    def open_flow_for_video(self,campaign_id):
        return self._request('flow',campaign_id)

    def open_grok_for_image(self,campaign_id):
        return self._request('grok',campaign_id)

    def open_grok_for_video(self,campaign_id):
        return self._request('grok',campaign_id)

    def open_tiktok_studio(self,campaign_id):
        return self._request('studio',campaign_id)

    def _request(self,service,campaign_id):
        if self.closed:
            raise RuntimeError('O assistente foi encerrado. Reinicie o aplicativo.')
        # A single browser job at a time prevents competing launches on one profile.
        if not self.lock.acquire(blocking=False):
            raise RuntimeError('Um navegador está abrindo. Aguarde e tente novamente.')
        try:
            task=asyncio.run_coroutine_threadsafe(self._open(service,campaign_id),self.loop)
            try:
                result=task.result(timeout=50)
            except TimeoutError as exc:
                task.cancel()
                raise RuntimeError('O navegador demorou para abrir. Feche a janela do perfil dedicado e tente novamente.') from exc
            result['campaign_id']=campaign_id
            return result
        finally:
            self.lock.release()

    async def _save_download(self,download,campaign_id):
        folder=self.media_root/f'campanha-{campaign_id:04d}'/'downloads'
        folder.mkdir(parents=True,exist_ok=True)
        name=secure_filename(download.suggested_filename) or 'download.bin'
        try:
            await download.save_as(folder/f'{uuid.uuid4().hex[:8]}-{name}')
        except Exception:
            import logging
            logging.getLogger(__name__).exception('Não foi possível guardar o download da campanha %s',campaign_id)

    def _download(self,download,page):
        task=asyncio.create_task(self._save_download(download,self.page_campaigns[page]))
        self.download_tasks.add(task)
        task.add_done_callback(self.download_tasks.discard)

    async def _open(self,service,campaign_id):
        try:
            executable = installed_browser()
            if service == 'studio':
                page, browser, user_data, chrome_profile = await self._connect_micaela_cdp(
                    URLS[service], new_tab=True
                )
                return dict(
                    message='TikTok Studio aberto no Chrome da fabrica (perfil Micaela). Pode deixar aberto — Analisar link abre outra aba.',
                    url=URLS[service],
                    profile=str(user_data),
                    mode='cdp_micaela',
                )

            # Grok + Flow share ONE dedicated Chromium window (tabs).
            # Prefer existing Flow profile folder so login cookies stay; else gen-maaiquels.
            profile = 'gen-maaiquels'
            flow_legacy = self.profile_root / 'flow-maaiquels'
            gen_dir = self.profile_root / profile
            if flow_legacy.is_dir() and not gen_dir.is_dir():
                profile = 'flow-maaiquels'
                directory = flow_legacy
            else:
                directory = gen_dir
                directory.mkdir(parents=True, exist_ok=True)

            # Stale native Chrome (old Grok-only launcher) locks the folder for Playwright.
            for key in list(self.native):
                proc = self.native.get(key)
                if proc and proc.poll() is None and key in (profile, 'flow-maaiquels', 'grok-maaiquels', 'gen-maaiquels'):
                    raise RuntimeError(
                        'Ha um Chrome antigo do perfil dedicado ainda aberto. '
                        'Feche essa janela uma vez e clique de novo — Grok e Flow passam a abrir como abas na mesma janela.'
                    )

            if profile_dir_busy(directory) and profile not in self.contexts:
                raise RuntimeError(
                    'O perfil dedicado de geracao esta em uso por outro Chrome. '
                    'Feche janelas extras desse perfil (nao o Chrome normal da Micaela) e tente de novo.'
                )

            if self.playwright is None:
                from playwright.async_api import async_playwright
                self.playwright = await async_playwright().start()

            context = self.contexts.get(profile)
            if context is None:
                context = await self.playwright.chromium.launch_persistent_context(
                    str(directory),
                    executable_path=executable,
                    headless=False,
                    accept_downloads=True,
                    no_viewport=True,
                    args=['--start-maximized'],
                    timeout=25000,
                )
                self.contexts[profile] = context
                context.on('close', lambda *_: self.contexts.pop(profile, None))

            url = URLS[service]
            pages = [p for p in context.pages if not p.is_closed()]
            # Reuse an existing tab for the same service URL when possible.
            page = next((p for p in pages if (p.url or '').startswith(url)), None)
            if page is None:
                # Prefer campaign-tagged blank/about for this campaign
                page = next(
                    (p for p in pages if p.url.startswith(url) and self.page_campaigns.get(p) == campaign_id),
                    None,
                )
            if page is None:
                blank = next((p for p in pages if (p.url or '') in ('about:blank', 'chrome://newtab/', 'chrome://new-tab-page/')), None)
                page = blank or await context.new_page()
                await page.goto(url, wait_until='domcontentloaded', timeout=20000)

            if page not in self.page_campaigns:
                page.on('download', lambda download: self._download(download, page))
                page.on('close', lambda *_: self.page_campaigns.pop(page, None))
            self.page_campaigns[page] = campaign_id
            await page.bring_to_front()

            label = 'Grok Imagine' if service == 'grok' else 'Google Flow'
            other = 'Flow' if service == 'grok' else 'Grok'
            return dict(
                message=(
                    f'{label} aberto na mesma janela do perfil dedicado. '
                    f'Pode abrir o {other} depois — vira outra aba, sem segundo navegador. '
                    'Gerar conteudo continua manual (cole o prompt e anexe os arquivos).'
                ),
                url=url,
                profile=profile,
                mode='assisted_tabs',
            )
        except RuntimeError:
            raise
        except OSError as exc:
            code = getattr(exc, 'winerror', None) or exc.errno
            if code == 14001:
                raise RuntimeError('O Windows nao conseguiu iniciar o navegador (erro 14001). Repare a instalacao do Chrome ou Edge e tente novamente.') from exc
            raise RuntimeError(f'O Windows nao conseguiu abrir o perfil dedicado (erro {code}). Verifique as permissoes da pasta browser_profiles e tente novamente.') from exc
        except Exception as exc:
            raise RuntimeError(
                f'Nao foi possivel abrir o servico: {exc}. '
                'Feche janelas extras do perfil dedicado de geracao e confira Chrome/Playwright (instalar.ps1).'
            ) from exc


    async def _connect_micaela_cdp(self, open_url=None, *, new_tab=False):
        """Reuse (or launch) the factory CDP clone of Micaela Chrome. Optionally open a URL in a new tab."""
        from services.studio_metrics import CONTENT_URL
        executable = installed_browser()
        chrome_root, chrome_profile = existing_chrome_profile()
        profile_key = "tiktok-micaela-metrics"
        user_data = ensure_micaela_cdp_user_data(self.profile_root, chrome_root, chrome_profile)
        target_url = open_url or CONTENT_URL

        if self.playwright is None:
            from playwright.async_api import async_playwright
            self.playwright = await async_playwright().start()

        async def try_attach_existing():
            """Attach to a live CDP port without launching. Returns browser or None."""
            port_file = Path(user_data) / "DevToolsActivePort"
            if not port_file.is_file():
                return None
            try:
                port = int(port_file.read_text(encoding="utf-8", errors="ignore").splitlines()[0].strip())
            except Exception:
                return None
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=1):
                    pass
            except OSError:
                return None
            # Drop stale Playwright handle — reconnect_over_cdp is cheap and safe
            old = self.contexts.pop(profile_key, None)
            if old is not None:
                try:
                    await old.close()
                except Exception:
                    pass
            try:
                browser = await self.playwright.chromium.connect_over_cdp(
                    f"http://127.0.0.1:{port}"
                )
                # Prove the session is alive
                _ = browser.contexts
                self.contexts[profile_key] = browser
                return browser
            except Exception:
                self.contexts.pop(profile_key, None)
                return None

        browser = await try_attach_existing()
        if browser is None:
            # Profile may be held by zombie Chrome without a working CDP port
            kill_micaela_cdp_chrome(user_data)
            old_proc = self.native.pop(profile_key, None)
            if old_proc and old_proc.poll() is None:
                try:
                    old_proc.terminate()
                except Exception:
                    pass
            await asyncio.sleep(0.8)

            last_exc = None
            for attempt in range(2):
                cdp_port = pick_free_port()
                args = [
                    executable,
                    f"--remote-debugging-port={cdp_port}",
                    "--remote-allow-origins=*",
                    f"--user-data-dir={user_data}",
                    "--profile-directory=Default",
                    "--no-first-run",
                    "--no-default-browser-check",
                    "--disable-session-crashed-bubble",
                    "--disable-features=TranslateUI",
                    "--new-window",
                    target_url,
                ]
                self.native[profile_key] = subprocess.Popen(
                    args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                )
                try:
                    actual_port = await asyncio.to_thread(wait_devtools_active_port, user_data, 45)
                except Exception as exc1:
                    try:
                        await asyncio.to_thread(wait_cdp_ready, cdp_port, 15)
                        actual_port = cdp_port
                    except Exception as exc2:
                        last_exc = exc2 or exc1
                        kill_micaela_cdp_chrome(user_data)
                        await asyncio.sleep(1.0)
                        continue
                try:
                    browser = await self.playwright.chromium.connect_over_cdp(
                        f"http://127.0.0.1:{actual_port}"
                    )
                    _ = browser.contexts
                    self.contexts[profile_key] = browser
                    new_tab = False  # launch already opened target_url
                    break
                except Exception as exc:
                    last_exc = exc
                    kill_micaela_cdp_chrome(user_data)
                    await asyncio.sleep(1.0)
                    browser = None
            if browser is None:
                raise RuntimeError(
                    "O Chrome da fabrica nao publicou a porta CDP. "
                    "Feche TODAS as janelas Chrome da fabrica (micaela-cdp), "
                    "clique Abrir TikTok Studio de novo e tente o lote."
                ) from last_exc

        browser = self.contexts[profile_key]
        contexts = browser.contexts
        if not contexts:
            raise RuntimeError("Chrome conectado, mas sem contexto de abas. Feche e tente de novo.")
        context = contexts[0]
        page = None
        if new_tab or open_url:
            page = await context.new_page()
            try:
                await page.goto(target_url, wait_until="domcontentloaded", timeout=25000)
            except Exception:
                pass
        else:
            for p in context.pages:
                if not p.is_closed():
                    page = p
                    break
            if page is None:
                page = await context.new_page()
                try:
                    await page.goto(target_url, wait_until="domcontentloaded", timeout=25000)
                except Exception:
                    pass
        await page.bring_to_front()
        return page, browser, user_data, chrome_profile


    def fetch_studio_metrics(self, campaign_id, video_url=None, caption_hint=None):
        """Open dedicated Playwright profile, scrape Studio content+analytics."""
        if self.closed:
            raise RuntimeError('O assistente foi encerrado. Reinicie o aplicativo.')
        if not self.lock.acquire(blocking=False):
            raise RuntimeError('Um navegador esta abrindo. Aguarde e tente novamente.')
        try:
            task = asyncio.run_coroutine_threadsafe(
                self._fetch_studio_metrics(campaign_id, video_url, caption_hint), self.loop
            )
            try:
                return task.result(timeout=90)
            except TimeoutError as exc:
                task.cancel()
                raise RuntimeError('A coleta de metricas demorou demais. Feche a janela do Studio e tente de novo.') from exc
        finally:
            self.lock.release()


    def audit_studio_posts(self, limit=20, viewers_top=5, days=7, min_views=100):
        """Batch-audit recent Studio uploads via the CDP Micaela clone."""
        if self.closed:
            raise RuntimeError('O assistente foi encerrado. Reinicie o aplicativo.')
        if not self.lock.acquire(blocking=False):
            raise RuntimeError('Um navegador esta abrindo. Aguarde e tente novamente.')
        try:
            task = asyncio.run_coroutine_threadsafe(
                self._audit_studio_posts(limit=limit, viewers_top=viewers_top, days=days, min_views=min_views), self.loop
            )
            try:
                return task.result(timeout=max(300, int(limit) * 70))
            except TimeoutError as exc:
                task.cancel()
                raise RuntimeError('A auditoria demorou demais. Feche o Chrome da coleta e tente com menos videos.') from exc
        finally:
            self.lock.release()

    async def _fetch_studio_metrics(self, campaign_id, video_url=None, caption_hint=None):
        """Reuse the same Micaela CDP Chrome; open analytics once, then scrape (no double goto)."""
        from services.studio_metrics import collect_metrics, CONTENT_URL, video_id_from_url, ANALYTICS_URL

        vid0 = video_id_from_url(video_url)
        open_url = ANALYTICS_URL.format(vid=vid0) if vid0 else CONTENT_URL
        page, browser, user_data, chrome_profile = await self._connect_micaela_cdp(
            open_url, new_tab=True
        )
        try:
            metrics = await collect_metrics(
                page,
                video_url=video_url,
                caption_hint=caption_hint,
                already_on_analytics=bool(vid0),
            )
        except Exception as first_exc:
            page2 = await browser.contexts[0].new_page()
            await page2.bring_to_front()
            try:
                if vid0:
                    await page2.goto(
                        ANALYTICS_URL.format(vid=vid0),
                        wait_until="domcontentloaded",
                        timeout=25000,
                    )
                metrics = await collect_metrics(
                    page2,
                    video_url=video_url,
                    caption_hint=caption_hint,
                    already_on_analytics=bool(vid0),
                )
            except Exception as second_exc:
                raise RuntimeError(str(second_exc) or str(first_exc)) from second_exc
        return dict(
            message=(
                "Metricas coletadas numa nova aba do mesmo Chrome da Micaela "
                f"(sem sleeps extras). Perfil: {chrome_profile}."
            ),
            metrics=metrics,
            url=(
                metrics.get("raw", {}).get("analytics_url")
                if isinstance(metrics.get("raw"), dict)
                else open_url
            ),
            profile=str(user_data),
            mode="playwright_cdp_micaela_same_window",
            campaign_id=campaign_id,
        )


    async def _audit_studio_posts(self, limit=20, viewers_top=5, days=7, min_views=100):
        from services.studio_metrics import audit_published_videos, CONTENT_URL

        async def reconnect():
            # Fresh page on (possibly relaunched) CDP Chrome
            return await self._ensure_metrics_page(open_url=CONTENT_URL)

        page = await reconnect()
        report = await audit_published_videos(
            page,
            limit=int(limit or 20),
            viewers_top=int(viewers_top or 5),
            days=int(days) if days is not None else None,
            min_views=int(min_views or 100),
            reconnect=reconnect,
            prefer_direct_url=True,
        )
        days_lbl = f" ({days}d, >={min_views} views)" if days else f" (>= {min_views} views)"
        return dict(
            message=f"Auditoria de {report.get('audited', 0)} videos do Studio concluida{days_lbl}.",
            report=report,
            mode="studio_audit",
        )

    async def _ensure_metrics_page(self, open_url=None):
        """Ensure CDP Micaela Chrome is up; return a usable page (may open a new tab)."""
        from services.studio_metrics import CONTENT_URL
        page, _browser, _user_data, _chrome_profile = await self._connect_micaela_cdp(
            open_url or CONTENT_URL, new_tab=bool(open_url)
        )
        return page


    async def _close(self):
        for context in list(self.contexts.values()):
            await context.close()
        if self.playwright:
            await self.playwright.stop()

    def close(self):
        if self.closed:
            return
        self.closed = True
        atexit.unregister(self.close)
        if self.loop.is_running():
            task = asyncio.run_coroutine_threadsafe(self._close(),self.loop)
            try:
                task.result(timeout=5)
            except Exception:
                task.cancel()
            self.loop.call_soon_threadsafe(self.loop.stop)
            self.thread.join(timeout=2)
        if not self.loop.is_running():
            self.loop.close()
