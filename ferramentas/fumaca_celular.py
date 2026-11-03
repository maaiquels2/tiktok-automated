"""Teste de fumaca da interface em tamanho de celular (375x812), com o agent-browser.

Sobe o app com dados temporarios (nao toca em data/ nem media/), abre as telas principais e falha se houver erro de
pagina, rolagem horizontal ou se o botao "Agente do Grok" nao abrir a mensagem (o travamento que ja aconteceu no celular).

Uso: python ferramentas/fumaca_celular.py        (precisa do agent-browser no PATH e de frontend/dist construido)
"""
import io
import json
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
from PIL import Image  # noqa: E402
from werkzeug.serving import make_server  # noqa: E402

from app import create_app  # noqa: E402

H = {'X-Local-App': 'fabrica-tiktok'}
BROWSER = shutil.which('agent-browser')
JS_BOTAO = "[...document.querySelectorAll('button')].find(b=>/AGENTE DO GROK/i.test(b.innerText))"


def ab(*args):
    r = subprocess.run([BROWSER, *args], capture_output=True, text=True, encoding='utf-8', timeout=60)
    return (r.stdout or '').strip()


def avaliar(js):
    """Roda JS na pagina e devolve o valor (o agent-browser imprime o resultado como JSON)."""
    saida = ab('eval', js)
    try:
        return json.loads(saida)
    except ValueError:
        return saida


def main():
    if not BROWSER:
        sys.exit('agent-browser nao encontrado no PATH.')
    if not (RAIZ / 'frontend' / 'dist' / 'index.html').exists():
        sys.exit('Falta construir o front: cd frontend && npm run build')
    falhas = []
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        app = create_app(dict(DATA_DIR=base / 'data', MEDIA_DIR=base / 'media', PROFILE_DIR=base / 'profiles'))
        brief = dict(name='Fumaca blusa', model_name='Micaela', niche='casual', outfit='blusa frente unica',
                     product='Blusa feminina frente unica em crepinho', color='Preto, Off-white', audience='mulheres adultas',
                     benefit='caimento fluido', angle='detalhes', tone='conversacional', style='natural',
                     details='crepinho, alca regulavel, barra assimetrica', generator='grok')
        cliente = app.test_client()
        cid = cliente.post('/api/campaigns', json=brief, headers=H).json['id']
        # O botao do agente so aparece com os prompts de imagem prontos: precisa de uma referencia e do "gerar".
        foto = io.BytesIO()
        Image.new('RGB', (540, 960), '#bfa58f').save(foto, 'PNG')
        foto.seek(0)
        cliente.post(f'/api/campaigns/{cid}/assets', data={'kind': 'reference', 'file': (foto, 'ref.png')}, headers=H)
        cliente.post(f'/api/campaigns/{cid}/generate', json={}, headers=H)
        servidor = make_server('127.0.0.1', 0, app, threaded=True)
        url = f'http://127.0.0.1:{servidor.server_port}'
        threading.Thread(target=servidor.serve_forever, daemon=True).start()
        try:
            ab('set', 'viewport', '375', '812')
            ab('open', url + '/')
            ab('errors', '--clear')
            time.sleep(1.5)
            if 'Nova campanha' not in str(avaliar('document.body.innerText')):
                falhas.append('tela inicial nao mostrou "Nova campanha"')
            if avaliar('document.documentElement.scrollWidth>innerWidth') is True:
                falhas.append('rolagem horizontal na tela inicial')
            ab('eval', "[...document.querySelectorAll('button')].find(b=>b.innerText.trim()==='Nova campanha').click()")
            time.sleep(0.8)
            if 'Automática' not in str(avaliar('document.body.innerText')):
                falhas.append('modal de nova campanha nao abriu')
            ab('press', 'Escape')
            ab('open', f'{url}/#/produzir/{cid}/image')
            time.sleep(1.5)
            if avaliar(f'!!({JS_BOTAO})') is not True:
                falhas.append('botao do Agente do Grok nao apareceu na etapa de imagem')
            else:
                ab('eval', f'({JS_BOTAO}).click()')
                time.sleep(1.5)
                if 'Copiar' not in str(avaliar('document.body.innerText')):
                    falhas.append('Agente do Grok nao abriu a mensagem para copiar')
            if avaliar('document.documentElement.scrollWidth>innerWidth') is True:
                falhas.append('rolagem horizontal na etapa de imagem')
            erros = ab('errors')
            if erros:
                falhas.append('erros de pagina: ' + erros[:300])
        finally:
            ab('close')
            servidor.shutdown()
    if falhas:
        print('FALHOU:\n- ' + '\n- '.join(falhas))
        sys.exit(1)
    print('Fumaca no celular: ok')


if __name__ == '__main__':
    main()
