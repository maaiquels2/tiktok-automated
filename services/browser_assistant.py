"""Assisted navigation only. No generation clicks, login, product selection or posting.

Flow and Grok open in plain Chrome (no Playwright) so downloads never crash the window.
Studio still uses the Micaela CDP clone. Interaction on Grok/Flow stays manual.
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
    # `lockfile` is left behind by some Chrome builds in dedicated profiles
    # even after the browser closes. The Singleton files are the reliable
    # indicators that a live Chrome process still owns the directory.
    for name in ('SingletonLock', 'SingletonCookie', 'SingletonSocket'):
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
    expected_marker = f"{Path(chrome_root).resolve()}|{chrome_profile}"
    try:
        marker_value = marker.read_text(encoding="utf-8").strip()
    except OSError:
        marker_value = ""
    need_seed = (
        marker_value != expected_marker
        or (not (default_dir / "Cookies").exists() and not (default_dir / "Network" / "Cookies").exists())
    )
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
        marker.write_text(expected_marker, encoding="utf-8")
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
        self.active_gen_campaign_id = 0
        self._dl_watch_task = None
        self._dl_seen = set()
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

    def open_grok_character_sheet(self):
        """Open Grok Imagine for consistency sheet; downloads land in campanha-0000."""
        return self._request('grok', 0)
    def open_grok_free(self):
        """Open Grok Imagine in the gen profile (no campaign)."""
        return self._request('grok', 0)

    def open_flow_free(self):
        """Open Google Flow / Labs in the gen profile (no campaign)."""
        return self._request('flow', 0)


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

    def _sniff_ext(self, path):
        """Guess extension from magic bytes when Grok omits one. Never raises."""
        try:
            with open(path, 'rb') as fh:
                head = fh.read(16)
        except Exception:
            return ''
        if not head:
            return ''
        if head.startswith(b'\xff\xd8\xff'):
            return '.jpg'
        if head.startswith(b'\x89PNG\r\n\x1a\n'):
            return '.png'
        if len(head) >= 12 and head[:4] == b'RIFF' and head[8:12] == b'WEBP':
            return '.webp'
        if len(head) >= 8 and head[4:8] == b'ftyp':
            return '.mp4'
        if head.startswith(b'PK\x03\x04'):
            return '.zip'
        return ''

    def _ensure_ext(self, dest):
        """Rename dest in-place only when it has no usable suffix. Soft-fail."""
        try:
            dest = Path(dest)
            if not dest.is_file():
                return dest
            suffix = (dest.suffix or '').lower()
            if suffix and suffix not in {'.bin', '.download', '.tmp', '.crdownload'}:
                return dest
            ext = self._sniff_ext(dest)
            if not ext:
                return dest
            renamed = dest.with_name(dest.stem + ext) if suffix else dest.with_name(dest.name + ext)
            if renamed == dest:
                return dest
            if renamed.exists():
                renamed = dest.with_name(f'{dest.stem}-{uuid.uuid4().hex[:4]}{ext}')
            dest.replace(renamed)
            return renamed
        except Exception:
            return Path(dest)

    def _native_dl_dir(self):
        folder = self.media_root / '_browser_downloads'
        folder.mkdir(parents=True, exist_ok=True)
        return folder

    def _seed_chrome_download_prefs(self, user_data_dir, dl_dir):
        """Point Chromium Default profile at our folder; never prompt. Soft-fail."""
        import json
        try:
            prefs_path = Path(user_data_dir) / 'Default' / 'Preferences'
            prefs_path.parent.mkdir(parents=True, exist_ok=True)
            data = {}
            if prefs_path.is_file():
                try:
                    data = json.loads(prefs_path.read_text(encoding='utf-8'))
                except Exception:
                    data = {}
            download = data.setdefault('download', {})
            download['default_directory'] = str(Path(dl_dir).resolve())
            download['prompt_for_download'] = False
            download['directory_upgrade'] = True
            # Also disable dangerous "open pdf externally" flakiness
            data.setdefault('plugins', {})['always_open_pdf_externally'] = False
            prefs_path.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
        except Exception:
            import logging
            logging.getLogger(__name__).exception('seed chrome download prefs failed')

    async def _enable_native_downloads(self, context, dl_dir):
        """CDP allow + path. Do NOT use Playwright Download artifacts (they crash Grok)."""
        import logging
        log = logging.getLogger(__name__)
        path = str(Path(dl_dir).resolve())
        for page in list(context.pages):
            if page.is_closed():
                continue
            try:
                client = await context.new_cdp_session(page)
                try:
                    await client.send(
                        'Browser.setDownloadBehavior',
                        {'behavior': 'allow', 'downloadPath': path, 'eventsEnabled': False},
                    )
                except Exception:
                    await client.send(
                        'Page.setDownloadBehavior',
                        {'behavior': 'allow', 'downloadPath': path},
                    )
            except Exception as exc:
                log.warning('native download CDP failed: %s', exc)

    def _route_native_file(self, src: Path):
        """Copy a finished Chrome download into the active campaign downloads folder."""
        import logging
        import shutil
        log = logging.getLogger(__name__)
        try:
            if not src.is_file():
                return
            name = src.name.lower()
            if name.endswith(('.crdownload', '.tmp', '.partial')):
                return
            key = str(src.resolve())
            if key in self._dl_seen:
                return
            # Wait until size stable
            size = src.stat().st_size
            if size <= 0:
                return
            self._dl_seen.add(key)
            cid = int(self.active_gen_campaign_id or 0)
            dest_dir = self.media_root / f'campanha-{cid:04d}' / 'downloads'
            dest_dir.mkdir(parents=True, exist_ok=True)
            suggested = secure_filename(src.name) or f'download-{uuid.uuid4().hex[:8]}'
            dest = dest_dir / f'{uuid.uuid4().hex[:8]}-{suggested}'
            shutil.copy2(src, dest)
            dest = self._ensure_ext(dest)
            log.info('native download routed -> %s', dest)
        except Exception:
            log.exception('route native download failed')

    async def _watch_native_downloads(self):
        """Poll Chrome's download folder; never touch Playwright Download APIs."""
        import logging
        log = logging.getLogger(__name__)
        folder = self._native_dl_dir()
        while True:
            try:
                await asyncio.sleep(1.5)
                for src in folder.iterdir():
                    if not src.is_file():
                        continue
                    # size must be stable across a short pause
                    try:
                        s1 = src.stat().st_size
                    except OSError:
                        continue
                    await asyncio.sleep(0.35)
                    try:
                        s2 = src.stat().st_size
                    except OSError:
                        continue
                    if s1 != s2 or s1 <= 0:
                        continue
                    self._route_native_file(src)
            except asyncio.CancelledError:
                raise
            except Exception:
                log.exception('download watcher tick failed')

    def _ensure_dl_watcher(self):
        try:
            if self._dl_watch_task and not self._dl_watch_task.done():
                return
            self._dl_watch_task = asyncio.create_task(self._watch_native_downloads())
        except Exception:
            import logging
            logging.getLogger(__name__).exception('could not start download watcher')

    def _gen_profile_dir(self):
        """Shared Grok+Flow profile (prefer legacy flow-maaiquels if gen missing)."""
        flow_legacy = self.profile_root / 'flow-maaiquels'
        gen_dir = self.profile_root / 'gen-maaiquels'
        if flow_legacy.is_dir() and not gen_dir.is_dir():
            return 'flow-maaiquels', flow_legacy
        gen_dir.mkdir(parents=True, exist_ok=True)
        return 'gen-maaiquels', gen_dir

    def _shared_generation_profile(self):
        """Find the app-owned profile already used by Flow/Grok.

        Studio normally clones the user's real Chrome profile. When Windows
        denies access to Chrome's global User Data/Local State, reuse the
        same app-owned Flow/Grok profile instead of forcing an environment
        variable that the user should not need to know about.
        """
        for name in ('flow-maaiquels', 'gen-maaiquels', 'grok-maaiquels'):
            directory = self.profile_root / name
            if (directory / 'Default').is_dir() and (directory / 'Local State').is_file():
                return directory, 'Default'
        return None

    def _existing_factory_cdp_profile(self):
        """Return an already-seeded Studio clone when one is available."""
        try:
            from services.studio_identity import load_identity
            folder = load_identity().get('cdp_folder') or 'micaela-cdp'
        except Exception:
            folder = 'micaela-cdp'
        directory = self.profile_root / folder
        default = directory / 'Default'
        has_cookies = (default / 'Cookies').is_file() or (default / 'Network' / 'Cookies').is_file()
        return directory if default.is_dir() and has_cookies else None

    def _kill_gen_chrome_processes(self):
        """Force-stop Chromium holding the gen/flow/grok factory profiles."""
        import logging
        log = logging.getLogger(__name__)
        needles = (
            'browser_profiles\\flow-maaiquels',
            'browser_profiles\\gen-maaiquels',
            'browser_profiles\\grok-maaiquels',
            'browser_profiles/flow-maaiquels',
            'browser_profiles/gen-maaiquels',
            'browser_profiles/grok-maaiquels',
        )
        try:
            ps = (
                "$needles=@('flow-maaiquels','gen-maaiquels','grok-maaiquels');"
                "Get-CimInstance Win32_Process -Filter \"Name='chrome.exe'\" | ForEach-Object {"
                "  $c=$_.CommandLine; if(-not $c){return};"
                "  foreach($n in $needles){ if($c -like ('*browser_profiles*'+$n+'*')){"
                "    Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue; break }}}"
            )
            subprocess.run(
                ["powershell", "-NoProfile", "-Command", ps],
                capture_output=True, text=True, timeout=25,
            )
        except Exception:
            log.exception('kill gen chrome failed')
        # Drop tracked native handles
        for key in list(self.native):
            if key in ('flow-maaiquels', 'gen-maaiquels', 'grok-maaiquels'):
                proc = self.native.pop(key, None)
                if proc and proc.poll() is None:
                    try:
                        proc.terminate()
                    except Exception:
                        pass

    async def _close_playwright_gen_contexts(self):
        """Detach any Playwright-owned gen windows (they are the crash source)."""
        for key in list(self.contexts):
            if key not in ('flow-maaiquels', 'gen-maaiquels', 'grok-maaiquels'):
                continue
            ctx = self.contexts.pop(key, None)
            if ctx is None:
                continue
            try:
                await ctx.close()
            except Exception:
                pass

    async def _open_gen_native_chrome(self, service, campaign_id):
        """Open Grok/Flow with system Chrome — zero Playwright attachment."""
        import logging
        log = logging.getLogger(__name__)
        executable = installed_browser()
        profile, directory = self._gen_profile_dir()
        dl_dir = self._native_dl_dir()

        # If a Playwright context still owns this profile, close it first.
        await self._close_playwright_gen_contexts()

        # Preferences only apply on a fresh Chrome start for that user-data-dir.
        busy = profile_dir_busy(directory)
        if busy:
            self._kill_gen_chrome_processes()
            await asyncio.sleep(1.0)

        self._seed_chrome_download_prefs(directory, dl_dir)
        try:
            self.active_gen_campaign_id = int(campaign_id or 0)
        except Exception:
            self.active_gen_campaign_id = 0

        url = URLS[service]
        # Grok e Flow dividem a mesma janela: com o Chrome do perfil de geracao
        # ja aberto, pedir --new-window criaria uma segunda janela em vez de uma
        # aba, que e justamente o que o fluxo quer evitar.
        running = self.native.get(profile)
        already_open = bool(running and running.poll() is None) or bool(busy)
        args = [
            executable,
            f'--user-data-dir={directory}',
            '--profile-directory=Default',
            '--no-first-run',
            '--no-default-browser-check',
            '--disable-session-crashed-bubble',
        ]
        if not already_open:
            args.append('--new-window')
        args.append(url)
        try:
            proc = subprocess.Popen(
                args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
            self.native[profile] = proc
        except OSError as exc:
            code = getattr(exc, 'winerror', None) or exc.errno
            raise RuntimeError(
                f'O Windows nao conseguiu abrir o Chrome do gerador (erro {code}).'
            ) from exc

        # Watcher runs on our asyncio loop (no Playwright needed).
        self._ensure_dl_watcher()
        # Also watch the Windows Downloads folder as fallback if prefs were ignored.
        self._ensure_user_downloads_fallback()

        label = 'Grok Imagine' if service == 'grok' else 'Google Flow'
        other = 'Flow' if service == 'grok' else 'Grok'
        log.info('opened %s via native Chrome profile=%s cid=%s', service, profile, campaign_id)
        return dict(
            message=(
                f'{label} aberto no Chrome da fabrica (sem Playwright). '
                f'Downloads vao para a pasta da campanha e para media/_browser_downloads. '
                f'Pode abrir o {other} depois na mesma conta.'
            ),
            url=url,
            profile=profile,
            mode='native_chrome',
            downloads=str(dl_dir),
        )

    def _user_downloads_dir(self):
        home = Path.home() / 'Downloads'
        return home if home.is_dir() else None

    def _ensure_user_downloads_fallback(self):
        """Also poll ~/Downloads for brand-new image/video files (Grok sometimes ignores prefs)."""
        try:
            if getattr(self, '_dl_user_watch_task', None) and not self._dl_user_watch_task.done():
                return
            self._dl_user_watch_task = asyncio.create_task(self._watch_user_downloads())
        except Exception:
            import logging
            logging.getLogger(__name__).exception('user downloads watcher failed to start')

    async def _watch_user_downloads(self):
        import logging
        import time
        log = logging.getLogger(__name__)
        folder = self._user_downloads_dir()
        if folder is None:
            return
        # Only consider files created after watcher start
        started = time.time()
        while True:
            try:
                await asyncio.sleep(2.0)
                for src in folder.iterdir():
                    if not src.is_file():
                        continue
                    name = src.name.lower()
                    if not name.endswith(('.jpg', '.jpeg', '.png', '.webp', '.mp4', '.gif', '.bin')):
                        # Grok often saves extensionless UUID files
                        if '.' in src.name and not name.endswith(('.crdownload', '.tmp')):
                            continue
                    try:
                        st = src.stat()
                    except OSError:
                        continue
                    if st.st_mtime < started - 2:
                        continue
                    if name.endswith(('.crdownload', '.tmp', '.partial')):
                        continue
                    await asyncio.sleep(0.4)
                    try:
                        if src.stat().st_size != st.st_size:
                            continue
                    except OSError:
                        continue
                    self._route_native_file(src)
            except asyncio.CancelledError:
                raise
            except Exception:
                log.exception('user downloads watcher tick failed')

    def _open_studio_native(self):
        """Open the manual publishing page without waiting for metrics automation."""
        executable = installed_browser()
        try:
            directory, profile = existing_chrome_profile()
        except RuntimeError:
            if os.environ.get('FABRICA_CHROME_USER_DATA'):
                raise
            directory = self._existing_factory_cdp_profile()
            profile = 'Default'
            if directory is None:
                shared = self._shared_generation_profile()
                if shared is None:
                    raise
                directory, profile = shared
        args = [executable, f'--user-data-dir={directory}',
                f'--profile-directory={profile}', '--no-first-run',
                '--no-default-browser-check', URLS['studio']]
        # Chrome forwards this URL to the running profile when it is already open.
        # Do not terminate Chrome, copy cookies or attach Playwright for this action.
        subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return dict(message='Abertura do TikTok Studio solicitada ao Chrome.',
                    url=URLS['studio'], profile=str(directory), mode='existing')

    async def _open(self,service,campaign_id):

        try:
            executable = installed_browser()
            if service == 'studio':
                return self._open_studio_native()

            # Grok + Flow: PLAIN Chrome only. Playwright download hooks kill the window.
            return await self._open_gen_native_chrome(service, campaign_id)

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
        direct_cdp = None
        try:
            chrome_root, chrome_profile = existing_chrome_profile()
        except RuntimeError:
            # Only fall back when the user did not explicitly configure a
            # different Chrome User Data directory. The shared generation
            # profile is the same account used by Flow and Grok in this app.
            if os.environ.get('FABRICA_CHROME_USER_DATA'):
                raise
            direct_cdp = self._existing_factory_cdp_profile()
            if direct_cdp is not None:
                # This clone is already isolated and can be opened directly;
                # do not copy it onto itself or ask for the global User Data.
                chrome_root, chrome_profile = direct_cdp, 'Default'
            else:
                fallback = self._shared_generation_profile()
                if fallback is None:
                    raise
                chrome_root, chrome_profile = fallback
        profile_key = "tiktok-micaela-metrics"
        user_data = direct_cdp or ensure_micaela_cdp_user_data(self.profile_root, chrome_root, chrome_profile)
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
