"""Publicacao de video no TikTok pela Content Posting API (inicializacao, upload e status).

So roda quando a usuaria clica em Publicar na Fabrica. Sem aprovacao do TikTok para postagem publica,
o envio sai como privacidade SELF_ONLY (so a propria conta ve).
Token vem da tabela tiktok_connections; nunca e devolvido ao navegador.
"""
import json
import urllib.error
import urllib.request

API = 'https://open.tiktokapis.com'
INIT_URL = API + '/v2/post/publish/video/init/'
STATUS_URL = API + '/v2/post/publish/status/fetch/'
MAX_BYTES = 64 * 1024 * 1024  # envio em um unico pedaco (limite do TikTok para FILE_UPLOAD)


class TikTokPublishError(Exception):
    pass


def _post_json(url, token, payload):
    req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'), method='POST',
                                 headers={'Authorization': f'Bearer {token}',
                                          'Content-Type': 'application/json; charset=UTF-8'})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8', 'replace')[:300]
        raise TikTokPublishError(f'TikTok recusou o pedido (HTTP {e.code}): {body}')
    except Exception as e:
        raise TikTokPublishError(f'Falha ao falar com o TikTok: {type(e).__name__}.')


def init_video(token: str, caption: str, video_size: int) -> dict:
    if video_size <= 0 or video_size > MAX_BYTES:
        raise TikTokPublishError('Video precisa ter entre 1 byte e 64 MB.')
    payload = {
        'post_info': {
            'title': caption[:2200],
            'privacy_level': 'SELF_ONLY',
            'disable_duet': True,
            'disable_comment': False,
            'disable_stitch': True,
        },
        'source_info': {
            'source': 'FILE_UPLOAD',
            'video_size': video_size,
            'chunk_size': video_size,
            'total_chunk_count': 1,
        },
    }
    data = _post_json(INIT_URL, token, payload)
    err = (data.get('error') or {}).get('code', 'ok')
    if err != 'ok' or not (data.get('data') or {}).get('upload_url'):
        raise TikTokPublishError(f"TikTok nao iniciou a publicacao: {err}")
    return {'publish_id': data['data']['publish_id'], 'upload_url': data['data']['upload_url']}


def status(token: str, publish_id: str) -> dict:
    data = _post_json(STATUS_URL, token, {'publish_id': publish_id})
    return {'status': (data.get('data') or {}).get('status', 'UNKNOWN'),
            'fail_reason': (data.get('data') or {}).get('fail_reason', '')}
