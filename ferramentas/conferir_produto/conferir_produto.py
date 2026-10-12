"""Confere se a PEÇA continua a mesma ao longo de um vídeo gerado (DINOv2, roda só no seu computador).

Pega os patches da peça na imagem aprovada (ou no primeiro quadro) e, para cada quadro do vídeo, mede o quanto eles ainda
aparecem em algum lugar do quadro. Pose, zoom e posição não pesam; só importa se o que era a peça (bordados, estampa,
tecido) continua visível. Por segundo, usamos o PIOR 20% dos patches da peça.

O que ela pega: peça que PERDE detalhes (bordado some, estampa muda, a peça vira outra).
O que ela NÃO pega: coisa NOVA que aparece na peça (um laço, um nó, uma tira). Ver o README.

Uso:
    python conferir_produto.py VIDEO [--ref IMAGEM] [--regiao topo|calcinha|tronco|pernas ...] [--caixa x0,y0,x1,y1]
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

# Regiões da peça no enquadramento "plano americano" dos vídeos do app (frações da largura e da altura da IMAGEM
# de referência). Se o seu enquadramento for outro, use --caixa e confira com --saida (salva a referência com a caixa).
REGIOES = {
    'topo': (0.27, 0.40, 0.73, 0.66),
    'calcinha': (0.27, 0.68, 0.73, 0.86),
    'tronco': (0.22, 0.38, 0.78, 0.70),
    'pernas': (0.20, 0.50, 0.80, 0.92),
}

# Calibração (12/10/2026, 2 vídeos bons de biquíni + 3 controles de calça jeans + 4 vídeos ruins): giros de lado e
# close-ups derrubam a cobertura por 1 a 3 s mesmo com a peça intacta; a perda real não se recupera.
LIMITE_QUEDA = 65        # cobertura (x100) abaixo disso conta como "peça sumiu" naquele segundo
SEGUNDOS_MINIMOS = 4     # quantos segundos assim, somados, para alertar
LIMITE_FINAL = 70        # média dos últimos segundos abaixo disso também alerta (a peça não voltou ao normal)
SEGUNDOS_FINAIS = 3

FPS = 4
PATCH = 14
LADO = 448
MODELO = 'facebook/dinov2-small'


# ---------------------------------------------------------------- lógica pura (sem torch, testável) ---------------

def parse_caixa(texto: str) -> tuple[float, float, float, float]:
    partes = [p.strip() for p in str(texto).split(',')]
    if len(partes) != 4:
        raise ValueError('a caixa tem 4 números: x0,y0,x1,y1 (frações de 0 a 1)')
    x0, y0, x1, y1 = (float(p) for p in partes)
    if not all(0 <= v <= 1 for v in (x0, y0, x1, y1)):
        raise ValueError('os números da caixa ficam entre 0 e 1')
    if x0 >= x1 or y0 >= y1:
        raise ValueError('a caixa precisa ter x0 < x1 e y0 < y1')
    return x0, y0, x1, y1


def por_segundo(valores: list[float], fps: int = FPS) -> list[float]:
    """Média dos quadros de cada segundo inteiro."""
    return [sum(valores[s * fps:(s + 1) * fps]) / fps for s in range(len(valores) // fps)]


def avaliar(serie: list[float], limite_queda: float = LIMITE_QUEDA, segundos_minimos: int = SEGUNDOS_MINIMOS,
            limite_final: float = LIMITE_FINAL, segundos_finais: int = SEGUNDOS_FINAIS) -> dict:
    """Decide se uma região perdeu a peça. `serie` é a cobertura por segundo, de 0 a 1."""
    baixos = [s for s, v in enumerate(serie) if v * 100 < limite_queda]
    final = serie[-segundos_finais:] if len(serie) >= segundos_finais else serie
    media_final = sum(final) / len(final) if final else 0.0
    motivos = []
    if len(baixos) >= segundos_minimos:
        motivos.append(f'{len(baixos)} s com cobertura abaixo de {limite_queda} (a partir de {baixos[0]} s)')
    if media_final * 100 < limite_final:
        motivos.append(f'no final do vídeo a cobertura é {media_final * 100:.1f} (abaixo de {limite_final:g}): a peça não voltou ao normal')
    return dict(alerta=bool(motivos), motivos=motivos, segundos_baixos=baixos, media_final=media_final,
                primeiro_segundo=baixos[0] if baixos else None)


# ---------------------------------------------------------------- parte pesada (torch, ffmpeg) --------------------

def extrair_quadros(video: Path, destino: Path, fps: int = FPS) -> list[Path]:
    if not shutil.which('ffmpeg'):
        raise SystemExit('ffmpeg não encontrado no PATH. Instale o ffmpeg (winget install Gyan.FFmpeg) e tente de novo.')
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', str(video), '-vf', f'fps={fps},scale={LADO}:-2',
                    str(destino / 'q%03d.png')], check=True)
    quadros = sorted(destino.glob('q*.png'))
    if not quadros:
        raise SystemExit(f'não consegui extrair quadros de {video}')
    return quadros


def carregar_modelo():
    try:
        import torch  # noqa: F401
        from transformers import AutoImageProcessor, AutoModel
    except ImportError as erro:
        raise SystemExit(f'faltam dependências ({erro}). Veja o README desta pasta.')
    return AutoImageProcessor.from_pretrained(MODELO), AutoModel.from_pretrained(MODELO).eval()


def patches(proc, modelo, imagem):
    import torch
    from PIL import Image
    w, h = imagem.size
    esc = LADO / min(w, h)
    nw, nh = max(PATCH, int(round(w * esc / PATCH)) * PATCH), max(PATCH, int(round(h * esc / PATCH)) * PATCH)
    entrada = proc(images=imagem.resize((nw, nh), Image.BICUBIC), return_tensors='pt', do_resize=False, do_center_crop=False)
    with torch.no_grad():
        saida = modelo(**entrada).last_hidden_state[0, 1:]
    return torch.nn.functional.normalize(saida, dim=-1), nw // PATCH, nh // PATCH


def patches_da_caixa(feats, gw, gh, caixa):
    import torch
    xs = (torch.arange(gw) + .5) / gw
    ys = (torch.arange(gh) + .5) / gh
    cx, cy = xs.repeat(gh), ys.repeat_interleave(gw)
    dentro = (cx >= caixa[0]) & (cx <= caixa[2]) & (cy >= caixa[1]) & (cy <= caixa[3])
    return feats[dentro]


def cobertura(ref_peca, frame_feats) -> float:
    """Pior 20% dos patches da peça: para cada um, o melhor par que ele tem no quadro."""
    import numpy as np
    melhor = (ref_peca @ frame_feats.T).max(dim=1).values
    return float(np.percentile(melhor.numpy(), 20))


def analisar(video: Path, ref: Path | None, caixas: dict[str, tuple], fps: int = FPS, **limites) -> dict:
    from PIL import Image
    proc, modelo = carregar_modelo()
    with tempfile.TemporaryDirectory(prefix='conferir-') as tmp:
        quadros = extrair_quadros(video, Path(tmp), fps)
        imagem_ref = Image.open(ref if ref else quadros[0]).convert('RGB')
        ref_feats, gw, gh = patches(proc, modelo, imagem_ref)
        pecas = {nome: patches_da_caixa(ref_feats, gw, gh, caixa) for nome, caixa in caixas.items()}
        series = {nome: [] for nome in caixas}
        for quadro in quadros:
            feats, _, _ = patches(proc, modelo, Image.open(quadro).convert('RGB'))
            for nome, peca in pecas.items():
                series[nome].append(cobertura(peca, feats))
    resultado = {}
    for nome, valores in series.items():
        seg = por_segundo(valores, fps)
        resultado[nome] = dict(caixa=caixas[nome], por_segundo=seg, **avaliar(seg, **limites))
    return dict(video=str(video), referencia=str(ref) if ref else 'primeiro quadro', quadros=len(series[next(iter(series))]),
                fps=fps, regioes=resultado, alerta=any(r['alerta'] for r in resultado.values()))


def salvar_referencia_com_caixas(ref: Path, caixas: dict[str, tuple], destino: Path) -> None:
    from PIL import Image, ImageDraw
    imagem = Image.open(ref).convert('RGB')
    desenho = ImageDraw.Draw(imagem)
    w, h = imagem.size
    cores = ['red', 'cyan', 'yellow', 'lime']
    for i, (nome, c) in enumerate(caixas.items()):
        desenho.rectangle([w * c[0], h * c[1], w * c[2], h * c[3]], outline=cores[i % 4], width=max(3, w // 200))
        desenho.text((w * c[0] + 6, h * c[1] + 6), nome, fill=cores[i % 4])
    imagem.save(destino)


def imprimir(rel: dict) -> None:
    print(f'Vídeo: {rel["video"]}')
    print(f'Referência: {rel["referencia"]} | {rel["quadros"]} quadros a {rel["fps"]}/s')
    for nome, r in rel['regioes'].items():
        print(f'\nRegião "{nome}" (caixa {tuple(round(v, 2) for v in r["caixa"])}): cobertura da peça por segundo (x100)')
        print('  s  ' + ' '.join(f'{s:>3d}' for s in range(len(r['por_segundo']))))
        print('     ' + ' '.join(f'{int(round(v * 100)):>3d}' for v in r['por_segundo']))
        if r['alerta']:
            print('  ALERTA: ' + '; '.join(r['motivos']))
        else:
            print('  ok: a peça continua aparecendo como na referência (não pega coisas NOVAS, como um laço).')
    print('\n' + ('ALERTA: a peça mudou. Veja os segundos acima.' if rel['alerta'] else 'Nenhuma perda de detalhes detectada.'))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('video', type=Path)
    ap.add_argument('--ref', type=Path, help='imagem aprovada (padrão: primeiro quadro do vídeo)')
    ap.add_argument('--regiao', action='append', choices=sorted(REGIOES), help='região da peça (pode repetir; padrão: topo)')
    ap.add_argument('--caixa', action='append', metavar='X0,Y0,X1,Y1', help='caixa própria da peça, frações de 0 a 1 (pode repetir)')
    ap.add_argument('--fps', type=int, default=FPS)
    ap.add_argument('--limite-queda', type=float, default=LIMITE_QUEDA)
    ap.add_argument('--segundos-minimos', type=int, default=SEGUNDOS_MINIMOS)
    ap.add_argument('--limite-final', type=float, default=LIMITE_FINAL)
    ap.add_argument('--saida', type=Path, help='pasta para salvar relatorio.json e referencia_com_caixas.png')
    ap.add_argument('--falhar', action='store_true', help='sai com código 2 se houver alerta (para scripts)')
    args = ap.parse_args(argv)

    caixas = {}
    for nome in args.regiao or ([] if args.caixa else ['topo']):
        caixas[nome] = REGIOES[nome]
    for i, texto in enumerate(args.caixa or [], 1):
        try:
            caixas[f'caixa{i}'] = parse_caixa(texto)
        except ValueError as erro:
            ap.error(str(erro))
    if not args.video.exists():
        ap.error(f'vídeo não encontrado: {args.video}')

    rel = analisar(args.video, args.ref, caixas, args.fps, limite_queda=args.limite_queda,
                   segundos_minimos=args.segundos_minimos, limite_final=args.limite_final)
    imprimir(rel)
    if args.saida:
        args.saida.mkdir(parents=True, exist_ok=True)
        (args.saida / 'relatorio.json').write_text(json.dumps(rel, indent=1, ensure_ascii=False), encoding='utf-8')
        if args.ref:
            salvar_referencia_com_caixas(args.ref, caixas, args.saida / 'referencia_com_caixas.png')
    return 2 if (args.falhar and rel['alerta']) else 0


if __name__ == '__main__':
    sys.exit(main())
