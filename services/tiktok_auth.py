"""Login com TikTok (Login Kit, OAuth 2.0). So troca de codigo e montagem de URL; nada posta no TikTok aqui.

As credenciais vem das variaveis de ambiente TIKTOK_CLIENT_KEY e TIKTOK_CLIENT_SECRET (Vercel).
Nunca gravar nem logar os valores.
"""
import json
import os
import urllib.error
import urllib.parse
import urllib.request

AUTHORIZE_URL = 'https://www.tiktok.com/v2/auth/authorize/'
TOKEN_URL = 'https://open.tiktokapis.com/v2/oauth/token/'
REDIRECT_URI = os.environ.get('TIKTOK_REDIRECT_URI', 'https://tiktok-automated.vercel.app/api/tiktok/callback')
SCOPES = 'user.info.basic,video.publish'


class TikTokAuthError(Exception):
    pass


def credentials():
    key = os.environ.get('TIKTOK_CLIENT_KEY', '').strip()
    secret = os.environ.get('TIKTOK_CLIENT_SECRET', '').strip()
    if not key or not secret:
        raise TikTokAuthError('TIKTOK_CLIENT_KEY ou TIKTOK_CLIENT_SECRET nao configurada na Vercel.')
    return key, secret


def authorize_url(state: str) -> str:
    key, _ = credentials()
    q = urllib.parse.urlencode({'client_key': key, 'scope': SCOPES, 'response_type': 'code',
                                'redirect_uri': REDIRECT_URI, 'state': state})
    return f'{AUTHORIZE_URL}?{q}'


def exchange_code(code: str) -> dict:
    key, secret = credentials()
    body = urllib.parse.urlencode({'client_key': key, 'client_secret': secret, 'code': code,
                                   'grant_type': 'authorization_code', 'redirect_uri': REDIRECT_URI}).encode()
    req = urllib.request.Request(TOKEN_URL, data=body, method='POST',
                                 headers={'Content-Type': 'application/x-www-form-urlencoded', 'Cache-Control': 'no-cache'})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            data = json.loads(r.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        raise TikTokAuthError(f'TikTok recusou a troca do codigo (HTTP {e.code}).')
    except Exception as e:
        raise TikTokAuthError(f'Falha ao falar com o TikTok: {type(e).__name__}.')
    if not data.get('access_token'):
        raise TikTokAuthError(f"TikTok nao devolveu token: {data.get('error', 'resposta sem access_token')}")
    return data
