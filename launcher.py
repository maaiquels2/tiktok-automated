"""Local Windows launcher: reuse our server or start it, then open the workspace."""
import json
import os
import sys
import threading
import urllib.request
import webbrowser
from pathlib import Path
from werkzeug.serving import make_server
from app import create_app

def main():
    root=Path(sys.executable).parent if getattr(sys,'frozen',False) else Path(__file__).resolve().parent
    (root/'data').mkdir(exist_ok=True)
    if sys.stdout is None:
        sys.stdout=open(root/'data'/'server.log','a',encoding='utf-8')
        sys.stderr=sys.stdout
    port=None
    for candidate in range(5050,5060):
        url=f'http://127.0.0.1:{candidate}'
        try:
            with urllib.request.urlopen(url+'/api/health',timeout=2) as response:
                health=json.load(response)
                if health.get('app')=='fabrica-tiktok' and health.get('version')==6:
                    webbrowser.open(url)
                    return
                # A previous Fábrica TikTok process owns this port. Leave it
                # running and try the next one for the current backend.
                if health.get('app')=='fabrica-tiktok':
                    continue
                continue
        except Exception:
            port=candidate
            break
    if port is None:
        port=5060
    url=f'http://127.0.0.1:{port}'
    app=create_app()
    try:
        server=make_server(('0.0.0.0' if os.environ.get('FABRICA_LAN','1')!='0' else '127.0.0.1'),port,app,threaded=True)
    except (OSError,SystemExit):
        if os.name=='nt':
            import ctypes
            ctypes.windll.user32.MessageBoxW(0,'A porta 5050 já está ocupada. Feche a versão antiga do aplicativo e tente novamente.','Fábrica TikTok',0x10)
        return
    def _print_lan(port):
        try:
            import ipaddress, socket
            print(f'Fabrica local: http://127.0.0.1:{port}', flush=True)
            for info in socket.getaddrinfo(socket.gethostname(), None, family=socket.AF_INET):
                ip = info[4][0]
                try:
                    addr = ipaddress.ip_address(ip)
                except ValueError:
                    continue
                if addr.is_private and not addr.is_loopback:
                    print(f'Fabrica na LAN (mesmo Wi-Fi): http://{ip}:{port}', flush=True)
        except Exception as exc:
            print(f'LAN URL skip: {exc}', flush=True)
    _print_lan(port)
    threading.Timer(.5,lambda:webbrowser.open(url)).start()
    server.serve_forever()

if __name__=='__main__':
    main()
