"""ZIP do pacote da campanha (texto, imagens e videos).

No teste de estresse, um video de 100 MB gerou um ZIP de 100 MB que passou por 282 MB de memoria (4 downloads
juntos: 853 MB). Aqui os arquivos nao sao lidos inteiros: vao do disco para o ZIP em pedacos e sem recomprimir
(video e foto ja vem comprimidos). Na nuvem a funcao tem limite de 4,5 MB de resposta e pouca memoria, entao o ZIP leva
so o texto e links assinados, validos por um tempo, para baixar cada arquivo direto do armazenamento.
"""
import tempfile
import zipfile

LINKS_FILE = 'links-dos-arquivos.txt'


def build_zip(text, entries, local_path=None, sign=None, device_lines=None, expires_in=3600):
    """``entries``: [(nome dentro do ZIP, registro do arquivo)].

    Modo local: ``local_path(registro)`` devolve o caminho no disco. Nuvem: ``sign(registro, nome)`` devolve o link
    assinado (e nenhum arquivo e lido). Devolve o ZIP pronto para enviar (em memoria ate 8 MB, depois em disco).
    """
    bundle = tempfile.SpooledTemporaryFile(max_size=8 * 1024 * 1024)
    with zipfile.ZipFile(bundle, 'w', zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('pacote-tiktok.txt', text.encode('utf-8-sig'))
        if sign is not None:
            lines = [f'Links para baixar os arquivos (valem por {max(1, expires_in // 60)} minutos; '
                     'baixe o pacote de novo para gerar links novos):', '']
            lines += [f'{name}: {sign(record, name)}' for name, record in entries]
            archive.writestr(LINKS_FILE, '\n'.join(lines).encode('utf-8-sig'))
        else:
            for name, record in entries:
                archive.write(local_path(record), name, compress_type=zipfile.ZIP_STORED)
        if device_lines:
            archive.writestr('videos-no-dispositivo.txt', '\n'.join(device_lines).encode('utf-8-sig'))
    bundle.seek(0)
    return bundle
