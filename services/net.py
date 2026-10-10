"""Diagnostico de rede do Storage (``/api/health?deep=1``).

Em 10/10/2026 toda chamada do servidor ao Storage falhava antes de sair da
maquina ("Name or service not known" / "[Errno 16] Device or resource busy"):
a variavel FABRICA_SUPABASE_URL apontava para um projeto Supabase que nao
existia mais, enquanto o banco (FABRICA_DATABASE_URL) ja estava no projeto
atual. O erro so aparecia como "Nao foi possivel concluir a operacao" na
biblioteca de fotos. Este diagnostico mostra a causa em uma chamada, sem
expor host nem chave.
"""
import socket
import urllib.request
from urllib.parse import urlsplit


def _probe(fn):
    try:
        fn()
        return 'ok'
    except OSError as exc:
        status = getattr(exc, 'code', None)  # HTTPError: a rede chegou ao servidor
        if status:
            return f'http {status}'
        return f'erro {exc.errno}: {exc.strerror or exc}'
    except Exception as exc:
        return f'erro: {exc.__class__.__name__}'


def _resolves(host, family=socket.AF_INET):
    return _probe(lambda: socket.getaddrinfo(host, 443, family, socket.SOCK_STREAM))


def diagnose(url: str, expected_ref: str = '') -> dict:
    """Testa se o servidor alcanca o host de ``url``.

    ``expected_ref`` (o id do projeto, ex.: o que aparece no painel do
    Supabase) permite conferir se a variavel aponta para ele, sem devolver o
    valor configurado.
    """
    host = urlsplit(url).hostname or ''
    if not host:
        return {'configurado': False}

    def http():
        with urllib.request.urlopen(url.rstrip('/') + '/storage/v1/version', timeout=10):
            pass

    report = {
        'configurado': True,
        'tipo_de_host': ('banco direto (db.*, so IPv6) -- deveria ser o Project URL'
                         if host.startswith('db.') and host.endswith('.supabase.co')
                         else 'Project URL do Supabase' if host.endswith('.supabase.co') else 'outro'),
        'dns_referencia_ipv4': _resolves('supabase.com'),
        'dns_ipv4': _resolves(host),
        'conexao_https': _probe(http),
    }
    if expected_ref.isalnum():
        expected = f'{expected_ref}.supabase.co'
        report['igual_ao_projeto_informado'] = host == expected
        report['dns_projeto_informado_ipv4'] = _resolves(expected)
    return report
