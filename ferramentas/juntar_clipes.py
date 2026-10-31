"""Junta os clipes de uma sequencia num video so (so no PC, precisa do ffmpeg).

Uso (na pasta Fabrica_TikTok):
    .venv\\Scripts\\python.exe ferramentas\\juntar_clipes.py saida.mp4 clipe1.mp4 clipe2.mp4 [clipe3.mp4]

Confere resolucao e fps, descarta o 1o quadro do clipe seguinte quando ele e copia do ultimo do anterior,
junta sem mexer no tempo e nivela o volume. Detalhes em services/join_clips.py.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from services.join_clips import join_clips  # noqa: E402


def main():
    if len(sys.argv) < 4:
        sys.exit(__doc__)
    try:
        report = join_clips([Path(p) for p in sys.argv[2:]], Path(sys.argv[1]))
    except (ValueError, FileNotFoundError, RuntimeError) as exc:
        sys.exit(f'Erro: {exc}')
    for j in report['junctions']:
        print(f"emenda {j['junction']}: SSIM {j['ssim']:.3f} -> "
              f"{'descartou o 1o quadro repetido' if j['dropped_first_frame'] else 'manteve todos os quadros'}")
    print(f"{report['frames']} quadros, {report['duration_s']} s: {report['destination']}")
    print('Assista a emenda quadro a quadro e ouca a voz antes e depois.')


if __name__ == '__main__':
    main()
