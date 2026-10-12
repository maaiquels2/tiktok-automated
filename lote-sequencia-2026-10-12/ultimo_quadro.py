"""Tira o ÚLTIMO QUADRO de um vídeo, para usar como primeiro quadro do clipe seguinte da sequência.

Gera 3 candidatos (a 0,1 s, 0,4 s e 0,8 s do fim): escolha o mais nítido, com ela de frente, a boca
mexendo e a mão no lugar descrito em "Último quadro esperado" de 4-falas.txt.

Uso (na pasta Fabrica_TikTok, no PowerShell):
    .venv\\Scripts\\python.exe lote-sequencia-2026-10-12\\ultimo_quadro.py CAMINHO\\video.mp4

Cria ao lado do vídeo: <nome>-ultimo-quadro-a.png, -b.png e -c.png.
Precisa do ffmpeg instalado (winget install Gyan.FFmpeg).
"""
import shutil
import subprocess
import sys
from pathlib import Path

# segundos antes do fim do vídeo
CANDIDATOS = (('a', 0.1), ('b', 0.4), ('c', 0.8))


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    video = Path(sys.argv[1])
    if not video.is_file():
        sys.exit(f'Vídeo não encontrado: {video}')
    ffmpeg = shutil.which('ffmpeg')
    if not ffmpeg:
        sys.exit('ffmpeg não encontrado no PATH. Instale com: winget install Gyan.FFmpeg')
    for letra, antes in CANDIDATOS:
        saida = video.with_name(f'{video.stem}-ultimo-quadro-{letra}.png')
        subprocess.run([ffmpeg, '-v', 'error', '-y', '-sseof', f'-{antes}', '-i', str(video),
                        '-frames:v', '1', '-update', '1', str(saida)], check=True)
        print(saida)


if __name__ == '__main__':
    main()
