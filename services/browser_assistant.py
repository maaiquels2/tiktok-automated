"""Assisted navigation only. No generation clicks, login, product selection or posting.

Flow/Studio use persistent Playwright contexts. Grok is opened by a normal browser
process without Playwright, CDP, DOM access or scripted interaction.
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
    """Resolve the user's existing Chrome profile by its visible Micaela name.

    Only Local State profile labels are read; cookies, passwords and session data
    are never opened by the application.
    """
    root_value = os.environ.get('FABRICA_CHROME_USER_DATA')
    root = Path(root_value).expanduser() if root_value else Path(os.environ.get('LOCALAPPDATA', ''))/'Google'/'Chrome'/'User Data'
    requested = os.environ.get('FABRICA_MICAELA_PROFILE')
    if requested:
        profile = Path(requested)
        if profile.is_absolute() and profile.parent.name == 'User Data':
            return profile.parent, profile.name
        if profile.is_absolute() and profile.parent == root:
            return root, profile.name
        return root, requested
    state_path = root/'Local State'
    if not state_path.is_file():
        raise RuntimeError('Não encontrei os perfis do Chrome. Defina FABRICA_CHROME_USER_DATA com a pasta User Data do Chrome.')
    try:
        state = json.loads(state_path.read_text(encoding='utf-8'))
        cache = state.get('profile', {}).get('info_cache', {})
    except (OSError, ValueError) as exc:
        raise RuntimeError('Não foi possível ler os nomes dos perfis do Chrome. Feche o Chrome e tente novamente.') from exc
    matches=[]
    for directory, info in cache.items():
        values=' '.join(str(info.get(key,'')) for key in ('name','user_name','gaia_name','gaia_given_name')).casefold()
        if 'micaela' in values or 'mica' in values:
            matches.append(directory)
    if len(matches)!=1:
        if not matches:
            raise RuntimeError('Não encontrei um perfil do Chrome identificado como Micaela. Defina FABRICA_MICAELA_PROFILE com o diretório do perfil, por exemplo Profile 6.')
        raise RuntimeError('Encontrei mais de um perfil possível da Micaela. Defina FABRICA_MICAELA_PROFILE com o diretório exato do perfil.')
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
            profile='tiktok-micaela' if service=='studio' else 'flow-maaiquels'
            directory=self.profile_root/profile
            if service != 'studio':
                directory.mkdir(parents=True,exist_ok=True)
            if service=='grok':
                if profile in self.contexts:
                    raise RuntimeError('Feche todas as janelas do Flow deste perfil antes de abrir o Grok manualmente.')
                proc=self.native.get(profile)
                if proc and proc.poll() is None:
                    return dict(message='O perfil manual já está aberto. Use a aba do Grok nessa janela.',url=URLS[service],profile=profile,mode='manual')
                # No remote debugging port, automation flags, or connection to this process.
                args=[executable,f'--user-data-dir={directory}',
                      '--no-first-run','--no-default-browser-check',URLS[service]]
                self.native[profile]=subprocess.Popen(args,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
                await asyncio.sleep(.8)
                if self.native[profile].poll() not in (None,0):
                    raise RuntimeError('Não foi possível abrir o perfil manual. Feche a janela dedicada e tente novamente.')
            elif service=='studio':
                # TikTok/Google login must run in the user's already trusted Chrome
                # profile. Playwright contexts are intentionally not used here.
                chrome_root, chrome_profile = existing_chrome_profile()
                profile='tiktok-micaela-existing'
                proc=self.native.get(profile)
                if proc and proc.poll() is None:
                    return dict(message='O perfil existente da Micaela já está aberto. Use a aba do TikTok Studio nessa janela.',url=URLS[service],profile=chrome_profile,mode='existing')
                args=[executable,f'--user-data-dir={chrome_root}',f'--profile-directory={chrome_profile}',
                      '--new-window','--no-first-run','--no-default-browser-check',URLS[service]]
                self.native[profile]=subprocess.Popen(args,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
                await asyncio.sleep(.8)
                if self.native[profile].poll() not in (None,0):
                    raise RuntimeError('Não foi possível abrir o perfil existente da Micaela. Feche o Chrome e tente novamente.')
                return dict(message='Perfil existente da Micaela aberto. Confira a conta e conclua o TikTok Studio manualmente.',url=URLS[service],profile=chrome_profile,mode='existing')
            else:
                proc=self.native.get(profile)
                if proc and proc.poll() is None:
                    raise RuntimeError('Feche o navegador manual do Grok antes de abrir o Flow neste perfil.')
                if self.playwright is None:
                    from playwright.async_api import async_playwright
                    self.playwright=await async_playwright().start()
                context=self.contexts.get(profile)
                if context is None:
                    context=await self.playwright.chromium.launch_persistent_context(str(directory),executable_path=executable,headless=False,
                        accept_downloads=True,no_viewport=True,args=['--start-maximized'],timeout=25000)
                    self.contexts[profile]=context
                    context.on('close',lambda *_: self.contexts.pop(profile,None))
                pages=[p for p in context.pages if not p.is_closed()]
                page=next((p for p in pages if p.url.startswith(URLS[service]) and self.page_campaigns.get(p)==campaign_id),None)
                if page is None:
                    page=next((p for p in pages if p.url=='about:blank'),None) or await context.new_page()
                    await page.goto(URLS[service],wait_until='domcontentloaded',timeout=20000)
                if page not in self.page_campaigns:
                    page.on('download',lambda download: self._download(download,page))
                    page.on('close',lambda *_: self.page_campaigns.pop(page,None))
                self.page_campaigns[page]=campaign_id
                await page.bring_to_front()
            return dict(message='Perfil dedicado aberto. Faça login e confira a conta. Cole o prompt e anexe os arquivos manualmente.',
                        url=URLS[service],profile=profile,mode='manual' if service=='grok' else 'assisted')
        except RuntimeError:
            raise
        except OSError as exc:
            code = getattr(exc, 'winerror', None) or exc.errno
            if code == 14001:
                raise RuntimeError('O Windows não conseguiu iniciar o navegador (erro 14001). Repare a instalação do Chrome ou Edge e tente novamente.') from exc
            raise RuntimeError(f'O Windows não conseguiu abrir o perfil dedicado (erro {code}). Verifique as permissões da pasta browser_profiles e tente novamente.') from exc
        except Exception as exc:
            raise RuntimeError('Não foi possível abrir o serviço. Verifique a conexão, feche outras janelas do perfil dedicado e confirme a instalação do Chrome ou Edge e do Playwright (instalar.ps1).') from exc


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
                return task.result(timeout=180)
            except TimeoutError as exc:
                task.cancel()
                raise RuntimeError('A coleta de metricas demorou demais. Feche a janela do Studio e tente de novo.') from exc
        finally:
            self.lock.release()

    async def _fetch_studio_metrics(self, campaign_id, video_url=None, caption_hint=None):
        """Open real Chrome (Micaela) with remote debugging, then scrape via CDP."""
        from services.studio_metrics import collect_metrics, CONTENT_URL
        executable = installed_browser()
        chrome_root, chrome_profile = existing_chrome_profile()
        profile_key = "tiktok-micaela-metrics"
        cdp_port = int(os.environ.get("FABRICA_METRICS_CDP_PORT") or "9333")

        native = self.native.get("tiktok-micaela-existing")
        if native and native.poll() is None:
            raise RuntimeError(
                "O Chrome da Micaela (aberto pela fabrica) ainda esta rodando. "
                "Feche essa janela do Studio/Chrome completamente e tente Coletar metricas de novo."
            )

        # Reuse an already-launched metrics Chrome if still up
        proc = self.native.get(profile_key)
        browser = self.contexts.get(profile_key)  # store CDP browser here
        need_launch = True
        if proc and proc.poll() is None and browser is not None:
            need_launch = False
        elif chrome_profile_busy(chrome_root) and not (proc and proc.poll() is None):
            raise RuntimeError(
                "O Chrome ainda esta aberto (ou travou o perfil). Feche TODAS as janelas do Google Chrome "
                f"(perfil {chrome_profile}) e tente novamente. A coleta precisa abrir o Chrome com depuracao."
            )

        if self.playwright is None:
            from playwright.async_api import async_playwright
            self.playwright = await async_playwright().start()

        if need_launch:
            # Kill stale CDP browser handle
            old = self.contexts.pop(profile_key, None)
            if old is not None:
                try:
                    await old.close()
                except Exception:
                    pass
            from services.studio_metrics import video_id_from_url, ANALYTICS_URL
            open_url = CONTENT_URL
            vid0 = video_id_from_url(video_url)
            if vid0:
                open_url = ANALYTICS_URL.format(vid=vid0)
            args = [
                executable,
                f"--user-data-dir={chrome_root}",
                f"--profile-directory={chrome_profile}",
                f"--remote-debugging-port={cdp_port}",
                "--remote-allow-origins=*",
                "--no-first-run",
                "--no-default-browser-check",
                "--new-window",
                open_url,
            ]
            self.native[profile_key] = subprocess.Popen(
                args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
            await asyncio.sleep(1.2)
            if self.native[profile_key].poll() not in (None, 0):
                raise RuntimeError(
                    "Nao foi possivel abrir o Chrome da Micaela para metricas. "
                    "Feche o Chrome e tente de novo."
                )
            try:
                await asyncio.to_thread(wait_cdp_ready, cdp_port, 30)
            except Exception as exc:
                raise RuntimeError(
                    "O Chrome abriu, mas a porta de depuracao nao respondeu. "
                    "Feche o Chrome e tente Coletar metricas de novo."
                ) from exc
            try:
                browser = await self.playwright.chromium.connect_over_cdp(
                    f"http://127.0.0.1:{cdp_port}"
                )
            except Exception as exc:
                raise RuntimeError(
                    f"Nao conectei no Chrome da Micaela via CDP (:{cdp_port}). Detalhe: {exc}"
                ) from exc
            self.contexts[profile_key] = browser

        browser = self.contexts[profile_key]
        contexts = browser.contexts
        if not contexts:
            raise RuntimeError("Chrome conectado, mas sem contexto de abas. Feche e tente de novo.")
        context = contexts[0]
        from services.studio_metrics import video_id_from_url as _vid_from
        want = (_vid_from(video_url) or "").casefold()
        # Prefer the analytics tab for this video, then any Studio tab, else new page
        page = None
        ranked = []
        for p in context.pages:
            if p.is_closed():
                continue
            try:
                u = (p.url or "").casefold()
            except Exception:
                u = ""
            score = 0
            if want and want in u and "analytics" in u:
                score = 3
            elif "tiktokstudio/analytics" in u:
                score = 2
            elif "tiktokstudio" in u or "tiktok.com" in u:
                score = 1
            if score:
                ranked.append((score, p))
        if ranked:
            ranked.sort(key=lambda x: -x[0])
            page = ranked[0][1]
        if page is None:
            page = await context.new_page()
        await page.bring_to_front()
        try:
            metrics = await collect_metrics(page, video_url=video_url, caption_hint=caption_hint)
        except Exception as first_exc:
            page2 = await context.new_page()
            await page2.bring_to_front()
            try:
                metrics = await collect_metrics(page2, video_url=video_url, caption_hint=caption_hint)
            except Exception as second_exc:
                raise RuntimeError(str(second_exc) or str(first_exc)) from second_exc
        return dict(
            message=f"Metricas coletadas do TikTok Studio (Chrome {chrome_profile} via CDP).",
            metrics=metrics,
            url=metrics.get("raw", {}).get("analytics_url") if isinstance(metrics.get("raw"), dict) else CONTENT_URL,
            profile=chrome_profile,
            mode="playwright_cdp_micaela",
            campaign_id=campaign_id,
        )


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
