"""Resolucao de nomes resistente ao ambiente da Vercel.

Em 10/10/2026, depois que a Vercel passou a compilar com o CLI 62, toda
chamada do servidor ao Storage do Supabase falhava antes de sair da maquina:
``socket.getaddrinfo`` devolvia ``OSError: [Errno 16] Device or resource
busy``. O banco continuava funcionando porque o psycopg2 resolve o nome pela
propria libpq; so o ``urllib`` do Python quebrava -- e com ele a biblioteca
de fotos da modelo, os arquivos de campanha e a escrita por IA.

A consulta que falha e a "mista" (IPv4 + IPv6, ``family=0``). Aqui ela ganha
uma segunda chance pedindo so IPv4 quando o erro e esse. Em qualquer outro
erro (nome inexistente, rede fora) nada muda.
"""
import errno
import socket
import urllib.request
from urllib.parse import urlsplit

_original_getaddrinfo = socket.getaddrinfo


def _getaddrinfo_with_ipv4_fallback(host, port, family=0, type=0, proto=0, flags=0):
    try:
        return _original_getaddrinfo(host, port, family, type, proto, flags)
    except OSError as exc:
        if family != socket.AF_UNSPEC or exc.errno != errno.EBUSY:
            raise
        return _original_getaddrinfo(host, port, socket.AF_INET, type, proto, flags)


def install_ipv4_fallback():
    """Instala a segunda chance uma vez so, para o processo inteiro."""
    socket.getaddrinfo = _getaddrinfo_with_ipv4_fallback


def _probe(fn):
    try:
        fn()
        return 'ok'
    except OSError as exc:
        return f'erro {exc.errno}: {exc.strerror or exc}'
    except Exception as exc:  # resposta HTTP de erro tambem prova que a rede funciona
        status = getattr(exc, 'code', None)
        return f'http {status}' if status else f'erro: {exc.__class__.__name__}'


def diagnose(url: str, expected_ref: str = '') -> dict:
    """Testa, sem credenciais, se o servidor alcanca o host de ``url``.

    Nao devolve o host nem nenhum segredo: so o resultado de cada tentativa.
    """
    host = urlsplit(url).hostname or ''
    if not host:
        return {'configurado': False}

    def http():
        with urllib.request.urlopen(url.rstrip('/') + '/storage/v1/version', timeout=10):
            pass

    if host.startswith('db.') and host.endswith('.supabase.co'):
        tipo = 'banco direto (db.*, so IPv6) -- deveria ser o Project URL'
    elif host.endswith('.supabase.co'):
        tipo = 'Project URL do Supabase'
    else:
        tipo = 'outro'
    return {
        'configurado': True,
        'tipo_de_host': tipo,
        **({'igual_ao_projeto_informado': host == f'{expected_ref}.supabase.co',
            'dns_projeto_informado_ipv4': _probe(lambda: _original_getaddrinfo(
                f'{expected_ref}.supabase.co', 443, socket.AF_INET, socket.SOCK_STREAM)),
            'tamanho_do_host': len(host)} if expected_ref.isalnum() else {}),
        'dns_referencia_ipv4': _probe(lambda: _original_getaddrinfo('supabase.com', 443, socket.AF_INET, socket.SOCK_STREAM)),
        'dns_misto': _probe(lambda: _original_getaddrinfo(host, 443, 0, socket.SOCK_STREAM)),
        'dns_ipv4': _probe(lambda: _original_getaddrinfo(host, 443, socket.AF_INET, socket.SOCK_STREAM)),
        'dns_ipv6': _probe(lambda: _original_getaddrinfo(host, 443, socket.AF_INET6, socket.SOCK_STREAM)),
        'correcao_ativa': socket.getaddrinfo is _getaddrinfo_with_ipv4_fallback,
        'conexao_https': _probe(http),
    }
