"""Prova de que as opcoes novas da sequencia (giro por clipe e close de textura) nao mudam nada quando desligadas.

Compara, byte a byte, o que a versao BASE (um commit) e a versao atual geram para os mesmos briefings:
prompt completo, Guia do Grok, Extend Video, falas, texto para copiar e mensagens do pacote do agente de cada
sequencia (services/story_arcs.py), mais o prompt de video e o Guia de clipe unico (services/prompts.py e
prompt_improve.py). Cada versao roda num processo proprio: a base e uma copia de services/ com os arquivos
alterados trocados pelos do commit base (git show), para que a story_arcs da base use a prompts.py da base.

    python ferramentas/comparar_prompts_sequencia.py --base 349302f
    python ferramentas/comparar_prompts_sequencia.py --textura      # o que o close de textura muda (versao atual)
    python ferramentas/comparar_prompts_sequencia.py --tamanhos     # maior prompt e maior mensagem com as opcoes

So leitura: nao grava nada no app nem no banco, nao chama API.
"""
import argparse
import itertools
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

PRODUCTS = {
    # Os mesmos de tests/test_app.py (ARC_PRODUCTS) e o colete de courino do teste real.
    'jeans': dict(product='Calça jeans', outfit='calça jeans', color='Azul claro', niche='dia-a-dia',
                  details='lavagem clara, cintura alta, modelagem reta, bolsos na frente'),
    'legging': dict(product='Legging cintura alta com bolso', outfit='legging', color='Preto', niche='academia',
                    details='tecido grosso, cintura alta, bolso lateral, sem transparência'),
    'vestido': dict(product='Vestido midi de cetim', outfit='vestido', color='Laranja', niche='casual',
                    details='cetim, fenda, alça ajustável'),
    'colete': dict(product='Colete de courino', outfit='colete', color='Preto', niche='casual',
                   details='botões, decote, courino'),
}
BASE = dict(model_name='Micaela', audience='', benefit='', angle='', tone='', style='', movements='',
            objection='', offer='')
ARCS = ('motivos', 'questionada')
CLIPS = (2, 3)
GENERATORS = ('grok', 'flow')
BASE_IMAGE = (False, True)
CAMPAIGN_TURNS = ('', 'leve_lado', 'lado', 'costas')


def video_modes():
    from services.formats import FORMATS
    return ('', 'espelho', *FORMATS, 'pov', 'movimento')


def campaign(name, mode, generator, turns):
    return {**BASE, **PRODUCTS[name], 'video_mode': mode, 'generator': generator, 'body_turns': turns}


def arc_fields(seq):
    """Os textos que vao para o operador, um por chave (para contar e apontar a diferenca)."""
    out = {'text': seq['text'], 'notes': '\n'.join(seq['notes'])}
    for clip in seq['clips']:
        k = clip['index']
        out.update({f'c{k}.prompt': clip['prompt'], f'c{k}.guide': clip['guide'], f'c{k}.extend': clip['extend'],
                    f'c{k}.lines': '\n'.join(clip['lines'])})
    for message in (seq.get('agent') or {}).get('messages', []):
        out[f'agent{message["index"]}'] = message['text']
    out['_all'] = json.dumps(seq, ensure_ascii=False, sort_keys=True)
    return out


def dump(options):
    """Todas as saidas da versao carregada (sys.path ja aponta para ela)."""
    from services.prompt_improve import build_compact_video_prompt
    from services.prompts import generate
    from services.story_arcs import ArcError, build_story_arc
    results = {}
    for name, mode, generator, turns in itertools.product(PRODUCTS, video_modes(), GENERATORS, CAMPAIGN_TURNS):
        c = campaign(name, mode, generator, turns)
        for base_image in BASE_IMAGE:
            pack = generate(c, base_image=base_image)
            key = f'unico|{name}|{mode}|{generator}|{turns}|{base_image}'
            results[key] = {'video': pack['video'],
                            'guia': build_compact_video_prompt(c, pack, c['color']),
                            'falas': '\n'.join(pack.get(k) or '' for k in ('hook', 'development', 'cta'))}
            for arc, clips in itertools.product(ARCS, CLIPS):
                key = f'seq|{name}|{mode}|{generator}|{turns}|{base_image}|{arc}|{clips}'
                opts = dict(options)
                if opts.get('clip_turns') == 'vazio':
                    opts['clip_turns'] = [''] * clips   # "igual a campanha" em todos os clipes
                try:
                    seq = build_story_arc(c, c['color'], arc, clips, base_image=base_image, **opts)
                    results[key] = arc_fields(seq)
                except ArcError as error:
                    results[key] = {'erro': f'{error.status} {error}'}
    return results


def worker(root, out, options):
    sys.path.insert(0, root)
    Path(out).write_text(json.dumps(dump(json.loads(options)), ensure_ascii=False), encoding='utf-8')


def run(root, options, tmp):
    out = Path(tmp) / f'saida-{abs(hash((root, options)))}.json'
    subprocess.run([sys.executable, __file__, '--worker', root, str(out), options], check=True)
    return json.loads(out.read_text(encoding='utf-8'))


def base_tree(ref, tmp):
    """Copia de services/ com os arquivos que mudaram desde ``ref`` trocados pelos de ``ref``."""
    target = Path(tmp) / 'base'
    shutil.copytree(ROOT / 'services', target / 'services', ignore=shutil.ignore_patterns('__pycache__'))
    changed = subprocess.run(['git', '-C', str(ROOT), 'diff', '--name-only', ref, '--', 'services'],
                             capture_output=True, text=True, check=True).stdout.split()
    for path in changed:
        shown = subprocess.run(['git', '-C', str(ROOT), 'show', f'{ref}:{path}'], capture_output=True, check=True)
        (target / path).write_bytes(shown.stdout)
    return str(target), changed


def compare(old, new):
    compared, diffs = 0, []
    for key in sorted(set(old) | set(new)):
        a, b = old.get(key), new.get(key)
        if a is None or b is None:
            diffs.append((key, 'faltou numa das versoes'))
            continue
        for field in sorted(set(a) | set(b)):
            compared += 1
            if a.get(field) != b.get(field):
                diffs.append((key, field))
    return compared, diffs


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--base', help='commit base (ex.: 349302f)')
    parser.add_argument('--textura', action='store_true')
    parser.add_argument('--tamanhos', action='store_true')
    parser.add_argument('--worker', nargs=3, metavar=('ROOT', 'OUT', 'OPTIONS'))
    args = parser.parse_args()
    if args.worker:
        worker(*args.worker)
        return
    with tempfile.TemporaryDirectory() as tmp:
        if args.base:
            root, changed = base_tree(args.base, tmp)
            print(f'base {args.base}; arquivos de services/ trocados pelos da base: {", ".join(changed) or "nenhum"}')
            old = run(root, '{}', tmp)
            new = run(str(ROOT), '{}', tmp)
            compared, diffs = compare(old, new)
            print(f'opcoes desligadas: {len(old)} combinacoes, {compared} comparacoes, {len(diffs)} diferencas')
            # clip_turns todos '' (igual a campanha) e texture=False explicitos tambem nao podem mudar nada.
            explicit = run(str(ROOT), json.dumps({'clip_turns': 'vazio', 'texture': False}), tmp)
            compared2, diffs2 = compare(old, explicit)
            print(f"clip_turns=['']*n e texture=False explicitos: {compared2} comparacoes, {len(diffs2)} diferencas")
            for diff in (diffs + diffs2)[:40]:
                print('  DIFERENCA', *diff)
            if diffs or diffs2:
                sys.exit(1)
        if args.textura:
            off = run(str(ROOT), '{}', tmp)
            on = run(str(ROOT), json.dumps({'texture': True}), tmp)
            changed = {}
            for key in sorted(off):
                if not key.startswith('seq|') or 'erro' in off[key]:
                    continue
                fields = [f for f in off[key] if f not in ('_all', 'notes') and off[key][f] != on[key][f]]
                if fields:
                    product = key.split('|')[1]
                    changed.setdefault(product, set()).add(key)
            total = sum(1 for k in off if k.startswith('seq|') and 'erro' not in off[k])
            print(f'close de textura: {total} sequencias montadas; mudaram (fora as notas):')
            for product in PRODUCTS:
                keys = changed.get(product, set())
                print(f'  {product}: {len(keys)} de {sum(1 for k in off if k.startswith(f"seq|{product}|") and "erro" not in off[k])}')
        if args.tamanhos:
            sizes()


def sizes():
    sys.path.insert(0, str(ROOT))
    from services.story_arcs import CLIP_TURNS, GROK_LIMIT, AGENT_LIMIT, build_story_arc
    worst = {}
    for name, mode, arc, clips in itertools.product(PRODUCTS, ('espelho', ''), ARCS, CLIPS):
        c = campaign(name, mode, 'grok', '')
        options = [('textura', {'texture': True})]
        for turn in CLIP_TURNS:
            if turn:
                for pos in range(clips):
                    options.append((f'giro {turn}', {'clip_turns': [turn if i == pos else '' for i in range(clips)]}))
                    options.append((f'giro {turn} + textura', {'texture': True,
                                    'clip_turns': [turn if i == pos else '' for i in range(clips)]}))
        for label, opts in options:
            seq = build_story_arc(c, c['color'], arc, clips, **opts)
            longest = max(len(clip['prompt']) for clip in seq['clips'])
            agent = max(m['chars'] for m in seq['agent']['messages'])
            over = sum(1 for clip in seq['clips'] if len(clip['prompt']) > GROK_LIMIT)
            item = worst.setdefault(label, dict(prompt=0, agent=0, over=0, runs=0, agent_over=0))
            item['prompt'] = max(item['prompt'], longest)
            item['agent'] = max(item['agent'], agent)
            item['over'] += over
            item['agent_over'] += sum(1 for m in seq['agent']['messages'] if m['chars'] > AGENT_LIMIT)
            item['runs'] += 1
    print(f'limite do prompt {GROK_LIMIT}, do agente {AGENT_LIMIT}')
    for label, item in worst.items():
        print(f'  {label}: maior prompt {item["prompt"]}, clipes acima do limite {item["over"]}; maior mensagem do '
              f'agente {item["agent"]}, acima de {AGENT_LIMIT}: {item["agent_over"]} ({item["runs"]} sequencias)')


if __name__ == '__main__':
    main()
