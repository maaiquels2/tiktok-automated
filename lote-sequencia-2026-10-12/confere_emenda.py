"""Confere uma EMENDA: o clipe 2 partiu do ÚLTIMO QUADRO do clipe 1, ou recomeçou da imagem-base?

Num teste real, os clipes 2 e 3 começaram todos no mesmo quadro (a imagem-base do K2), então a emenda
reiniciava a pose e o enquadramento. Esta ferramenta compara três quadros e avisa:
  - o FIM do clipe 1;  - o INÍCIO do clipe 2;  - a imagem-base (opcional).

É um indicativo, não um juiz: ele mede o quanto os quadros se parecem (0 = iguais, 255 = opostos).
Sempre abra a imagem gerada e confira com os olhos.

Uso (na pasta Fabrica_TikTok, no PowerShell):
    .venv\\Scripts\\python.exe lote-sequencia-2026-10-12\\confere_emenda.py clipe1.mp4 clipe2.mp4 [imagem_base.jpg]

Gera ao lado do clipe 2: <nome>-emenda.png (fim do 1 | início do 2 | imagem-base).
Precisa do ffmpeg (winget install Gyan.FFmpeg) e do Pillow (já está no .venv do projeto).
"""
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageStat

# Abaixo disto, os dois quadros são praticamente a mesma cena (partiu do último quadro). Calibrado nos vídeos
# do primeiro teste: o mesmo quadro de partida (imagem-base x início do clipe) dá cerca de 5 (ruído de
# compressão em 480p); clipes que NÃO partiram do último quadro deram de 15 a 35.
LIMITE_PARECIDO = 10.0
# A imagem-base tem que ser claramente MAIS parecida com o início do que o fim do clipe anterior.
MARGEM_BASE = 4.0


def quadro(video, destino, fim=False):
    ffmpeg = shutil.which('ffmpeg')
    if not ffmpeg:
        sys.exit('ffmpeg não encontrado no PATH. Instale com: winget install Gyan.FFmpeg')
    args = [ffmpeg, '-v', 'error', '-y']
    if fim:
        args += ['-sseof', '-0.1']
    args += ['-i', str(video), '-frames:v', '1', '-update', '1', str(destino)]
    subprocess.run(args, check=True)
    return Image.open(destino).convert('RGB')


def distancia(a, b):
    """Diferença média por pixel (0 a 255) entre duas imagens, em escala de cinza e tamanho comum."""
    ga, gb = (im.convert('L').resize((72, 128)) for im in (a, b))
    return ImageStat.Stat(ImageChops.difference(ga, gb)).mean[0]


def folha(imagens, destino):
    altura = 420
    celulas = []
    for rotulo, im in imagens:
        largura = int(im.width * altura / im.height)
        celula = Image.new('RGB', (largura, altura + 18), 'white')
        celula.paste(im.resize((largura, altura)), (0, 18))
        ImageDraw.Draw(celula).text((3, 3), rotulo, fill='black')
        celulas.append(celula)
    total = Image.new('RGB', (sum(c.width + 4 for c in celulas), altura + 18), 'white')
    x = 0
    for c in celulas:
        total.paste(c, (x, 0))
        x += c.width + 4
    total.save(destino)


def main():
    if len(sys.argv) not in (3, 4):
        sys.exit(__doc__)
    clipe1, clipe2 = Path(sys.argv[1]), Path(sys.argv[2])
    base = Path(sys.argv[3]) if len(sys.argv) == 4 else None
    for caminho in (clipe1, clipe2, *( [base] if base else [] )):
        if not caminho.is_file():
            sys.exit(f'Arquivo não encontrado: {caminho}')
    with tempfile.TemporaryDirectory() as tmp:
        fim1 = quadro(clipe1, Path(tmp) / 'fim.png', fim=True)
        ini2 = quadro(clipe2, Path(tmp) / 'ini.png')
        img_base = Image.open(base).convert('RGB') if base else None
        d_fim = distancia(fim1, ini2)
        d_base = distancia(img_base, ini2) if img_base else None
        imagens = [('FIM do clipe 1', fim1), ('INICIO do clipe 2', ini2)]
        if img_base:
            imagens.append(('imagem-base', img_base))
        saida = clipe2.with_name(f'{clipe2.stem}-emenda.png')
        folha(imagens, saida)

    print(f'Fim do clipe 1  x  início do clipe 2 : {d_fim:5.1f}')
    if d_base is not None:
        print(f'Imagem-base     x  início do clipe 2 : {d_base:5.1f}')
    if d_base is not None and d_base + MARGEM_BASE < d_fim:
        veredito = ('ATENÇÃO: o clipe 2 parece ter partido da IMAGEM-BASE, não do último quadro do clipe 1. '
                    'A pose e o enquadramento reiniciam na emenda.')
    elif d_fim <= LIMITE_PARECIDO:
        veredito = 'OK: o início do clipe 2 é parecido com o fim do clipe 1 (partiu do último quadro).'
    else:
        veredito = ('Salto visível: o início do clipe 2 não se parece com o fim do clipe 1. Confira a imagem '
                    'gerada; se o clipe 2 partiu de outro quadro, a emenda vai aparecer no corte.')
    print(veredito)
    print(f'Imagem para conferir: {saida}')


if __name__ == '__main__':
    main()
