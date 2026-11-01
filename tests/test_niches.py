"""Consistencia dos nichos entre o backend e o frontend, e dos textos padrao de cada nicho.

Os textos padrao entram no briefing quando a pessoa escolhe o nicho (applyNiche
copia todos) e dali vao para os prompts. Um texto padrao que pede CTA visual ou
afirma desempenho que o briefing nao confirmou vira instrucao para o gerador.
"""
import json
import re
import unicodedata
import unittest
from pathlib import Path

from services import model_library, piece, playbook, prompts

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'frontend' / 'src'
IDS = [k for k, _ in model_library.NICHES]
FIELDS = ('outfit', 'audience', 'benefit', 'angle', 'tone', 'style', 'details', 'movements')


def fold(text):
    text = unicodedata.normalize('NFKD', str(text or '').casefold())
    return ''.join(ch for ch in text if not unicodedata.combining(ch))


def js_defaults():
    src = (SRC / 'nicheDefaults.js').read_text(encoding='utf-8')
    return json.loads(src[src.index('{'):src.rindex('}') + 1])


def js_object_keys(source, start_marker):
    """Chaves de um objeto JS de uma linha como {praia:'Praia','dia-a-dia':'Dia a dia'}."""
    i = source.index(start_marker)
    body = source[source.index('{', i):source.index('}', i) + 1]
    return [a or b for a, b in re.findall(r"(?:'([^']+)'|([\w]+))\s*:", body)]


def js_niche_list(source, marker):
    """ids e rotulos de uma lista JS [{id:'praia',label:'Moda praia'}, ...]."""
    i = source.index(marker)
    body = source[source.index('[', i):source.index('];', i)]
    return re.findall(r"id:'([^']+)',\s*label:'([^']+)'", body)


# Pede elemento grafico na tela (o carrinho so e falado; os builders proibem UI desenhada).
VISUAL_CTA = re.compile(r'\bcta visual\b|\bcarrinho\b|\bsetas?\b|\bstickers?\b|\btexto na tela\b|'
                        r'\bna tela\b|\bicones?\b|\bemojis?\b|\bbotao de compra\b|\blegenda na tela\b')
# Desempenho que so vale com o briefing confirmando (ATRIBUTOS NAO CONFIRMADOS do prompt de video).
# "premium" sozinho fica de fora: "realista premium" (estilo da intima) e estetica, nao fato do tecido.
CLAIMS = re.compile(r'\bcompress\w*|\belasticidade\b|\bstretch\b|\bsecage\w*|\bseca rapid\w*|\bdry ?fit\b|'
                    r'\bsuporte\b|\btecido premium\b|\brespiravel\b|\bnao fica transparente\b|'
                    r'\bsem transparencia\b|\bmodelador\w*|\blevanta (?:o )?bumbum\b|\bprotecao uv\b|\bnao marca\b')

# Problemas que existem HOJE nos textos padrao e que ficam como estao: trocar o texto muda
# byte a byte os prompts gerados (academia.details entra como "Notas adicionais do operador"
# no prompt de video e como DETALHES ESTATICOS no de imagem; praia.movements muda 28 prompts
# de video no formato "So movimento"; academia.audience entra no briefing da IA). A correcao
# e decisao do produto. Quem corrigir um texto tira a linha daqui (o teste falha se a linha
# sobrar), e qualquer problema novo falha direto.
KNOWN = {
    ('praia', 'movements', 'cta visual'),      # "pose final com CTA visual"
    ('academia', 'audience', 'compressao'),    # "buscando compressão e estilo"
    ('academia', 'details', 'stretch'),        # "Mostrar tecido stretch, cos e suporte."
    ('academia', 'details', 'suporte'),
}


class NicheIdsAgreeTests(unittest.TestCase):
    def test_every_list_of_niches_has_the_same_ids(self):
        components = (SRC / 'components.jsx').read_text(encoding='utf-8')
        api = (SRC / 'api.js').read_text(encoding='utf-8')
        modals = (SRC / 'modals.jsx').read_text(encoding='utf-8')
        listas = {
            'model_library.NICHE_DEFAULTS': list(model_library.NICHE_DEFAULTS),
            'model_library.NICHE_IDS': sorted(model_library.NICHE_IDS, key=IDS.index),
            'piece.NICHES': list(piece.NICHES),
            'prompts.VIDEO_NICHE': list(prompts.VIDEO_NICHE),
            'nicheDefaults.js': list(js_defaults()),
            'components.jsx NICHES': [i for i, _ in js_niche_list(components, 'export const NICHES')],
            'components.jsx applyNiche': js_object_keys(components, 'const label=({'),
            'api.js NICHES': [i for i, _ in js_niche_list(api, 'export const NICHES')],
            'modals.jsx NICHE_SHORT': js_object_keys(modals, 'const NICHE_SHORT='),
        }
        for nome, ids in listas.items():
            self.assertEqual(ids, IDS, nome)

    def test_labels_match_between_backend_and_frontend(self):
        components = (SRC / 'components.jsx').read_text(encoding='utf-8')
        api = (SRC / 'api.js').read_text(encoding='utf-8')
        for nome, src in (('components.jsx', components), ('api.js', api)):
            self.assertEqual(dict(js_niche_list(src, 'export const NICHES')), model_library.NICHE_LABELS, nome)

    def test_playbook_and_validation_only_use_existing_niches(self):
        self.assertLessEqual(set(playbook.NICHE_MAP.values()), set(IDS))
        app_src = (ROOT / 'app.py').read_text(encoding='utf-8')
        mensagem = re.search(r"Nicho invalido\. Use ([^']+)'", app_src).group(1)
        for niche in IDS:
            self.assertIn(niche, mensagem)

    def test_python_and_js_defaults_are_identical(self):
        js = js_defaults()
        for niche in IDS:
            self.assertEqual(js[niche], model_library.NICHE_DEFAULTS[niche], niche)

    def test_every_niche_fills_every_field(self):
        for niche in IDS:
            d = model_library.NICHE_DEFAULTS[niche]
            self.assertEqual(set(d), set(FIELDS), niche)
            for field in FIELDS:
                self.assertTrue(str(d[field]).strip(), (niche, field))


class NicheDefaultTextTests(unittest.TestCase):
    def offenders(self):
        found = set()
        for niche in IDS:
            for field, value in model_library.NICHE_DEFAULTS[niche].items():
                low = fold(value)
                for pattern in (VISUAL_CTA, CLAIMS):
                    for m in pattern.finditer(low):
                        found.add((niche, field, m.group(0)))
        return found

    def test_defaults_ask_no_visual_cta_and_claim_no_unconfirmed_performance(self):
        novos = self.offenders() - KNOWN
        self.assertFalse(novos, 'Texto padrão de nicho pedindo CTA visual ou afirmando desempenho: '
                                f'{sorted(novos)}. O carrinho só é falado; desempenho só com o briefing confirmando.')

    def test_known_exceptions_still_exist(self):
        # Quando alguem corrigir o texto, esta lista tem que encolher junto.
        sobrando = KNOWN - self.offenders()
        self.assertFalse(sobrando, f'Exceção corrigida no texto, tire de KNOWN: {sorted(sobrando)}')

    def test_spoken_cta_in_defaults_is_not_a_visual_cta(self):
        # "CTA final" (dia a dia, intima, fantasia) e o CTA falado no fim: nao conta como pedido de UI.
        for niche in ('dia-a-dia', 'intima', 'fantasia'):
            self.assertFalse(VISUAL_CTA.search(fold(model_library.NICHE_DEFAULTS[niche]['movements'])), niche)

    def test_the_patterns_catch_what_they_promise(self):
        for texto in ('pose final com CTA visual', 'seta apontando o carrinho', 'sticker de oferta',
                      'texto na tela com o preço'):
            self.assertTrue(VISUAL_CTA.search(fold(texto)), texto)
        for texto in ('buscando compressão', 'boa elasticidade', 'secagem rápida', 'dá suporte',
                      'tecido premium', 'tecido stretch'):
            self.assertTrue(CLAIMS.search(fold(texto)), texto)
        for texto in ('realista premium', 'CTA final animado', 'close no tecido', 'ajustar o cós'):
            self.assertFalse(VISUAL_CTA.search(fold(texto)) or CLAIMS.search(fold(texto)), texto)

    def test_the_known_claims_are_still_blocked_in_the_generated_video(self):
        # Enquanto os textos nao mudam, a trava do prompt de video continua proibindo as afirmacoes.
        c = dict(model_name='Micaela', product='Legging cintura alta', color='Preto', niche='academia',
                 generator='grok', **model_library.NICHE_DEFAULTS['academia'])
        video = prompts.generate(c)['video']
        trava = video.split('ATRIBUTOS NÃO CONFIRMADOS', 1)[1].split('.', 1)[0]
        for termo in ('compressão', 'elasticidade', 'suporte', 'secagem', 'tecido premium'):
            self.assertIn(termo, trava)


if __name__ == '__main__':
    unittest.main()
