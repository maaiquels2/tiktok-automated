import importlib.util
import unittest
from pathlib import Path

from services import prompts, speech_bank
from services.speech_curated import CURATED
from services.speech_future import FUTURE

LIB_PATH = Path(__file__).resolve().parents[1] / 'ferramentas' / 'curadoria_falas' / 'lib.py'
_spec = importlib.util.spec_from_file_location('curadoria_lib', LIB_PATH)
lib = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(lib)

CATS = {c['id']: c for c in speech_bank.CATEGORIES}


def texto(mold):
    return mold['t'] if isinstance(mold, dict) else mold


class CuratedMoldsTests(unittest.TestCase):
    def test_every_curated_category_exists_and_uses_known_kinds(self):
        for cat_id, bloco in CURATED.items():
            self.assertIn(cat_id, CATS)
            self.assertLessEqual(set(bloco), set(lib.KINDS), cat_id)

    def test_curated_molds_pass_the_same_checks_they_passed_at_curation_time(self):
        for cat_id, bloco in CURATED.items():
            for kind, moldes in bloco.items():
                for mold in moldes:
                    item = mold if isinstance(mold, dict) else {'t': mold}
                    self.assertEqual(lib.check(CATS[cat_id], item, kind), [], (cat_id, kind, item))
                    self.assertEqual(lib.audit_in_context(CATS[cat_id], item, kind), [], (cat_id, kind, item))

    def test_curated_pain_molds_work_with_every_real_objection_of_their_category(self):
        # {pain} chega ao app com a objecao do briefing, nao so com uma de exemplo.
        for cat_id, bloco in CURATED.items():
            for kind, moldes in bloco.items():
                for mold in moldes:
                    item = mold if isinstance(mold, dict) else {'t': mold}
                    self.assertEqual(lib.check_pains(CATS[cat_id], item, kind), [], (cat_id, kind, item))

    def test_curated_molds_are_not_repeated_inside_a_category(self):
        for cat_id, bloco in CURATED.items():
            for kind, moldes in bloco.items():
                textos = [texto(m) for m in moldes]
                self.assertEqual(len(textos), len(set(textos)), (cat_id, kind))

    def test_curated_molds_are_interleaved_and_keep_the_first_original_first(self):
        # A cor 0 recebe o primeiro molde de cada lista: ele tem que ser o mesmo de sempre. Os curados vem intercalados.
        for cat_id, bloco in CURATED.items():
            for kind, moldes in bloco.items():
                vivo = [texto(m) for m in CATS[cat_id][kind]]
                curados = [texto(m) for m in moldes]
                self.assertTrue(set(curados) <= set(vivo), (cat_id, kind))
                originais = [t for t in vivo if t not in set(curados)]
                self.assertEqual(vivo[0], originais[0], (cat_id, kind))
                self.assertEqual(vivo[1], curados[0], (cat_id, kind))
                self.assertEqual(len(vivo), len(originais) + len(curados), (cat_id, kind))

    def test_the_generator_can_reach_curated_hooks_without_a_required_attribute(self):
        # Um molde curado so serve se o gerador o oferece: confere no pool de uma categoria curada.
        for cat_id, bloco in CURATED.items():
            livres = [texto(m) for m in bloco.get('hooks', []) if isinstance(m, dict) and not m.get('req') and not m.get('pain')]
            if not livres:
                continue
            cat = CATS[cat_id]
            campanha = {'product': cat['piece'], 'outfit': cat['piece'], 'color': 'Preto', 'niche': 'casual',
                        'model_name': 'Micaela', 'audience': 'mulheres', 'benefit': '', 'details': '', 'objection': '',
                        'offer': '', 'generator': 'grok', 'video_mode': ''}
            forms = speech_bank._forms(cat)
            linhas = [t for _id, t in prompts._category_lines(campanha, 'hooks', forms)]
            esperado = speech_bank.fill(livres[0], {**forms, 'teu': forms['teu']})
            self.assertIn(esperado, linhas, cat_id)
            return


class FutureLinesAndPainCtaTests(unittest.TestCase):
    ORIGINAIS = {k: tuple(v) for k, v in {**prompts._FUTURE_LINES, **prompts._FUTURE_BY_FAMILY}.items()}

    def test_curated_future_lines_are_clean_and_come_after_the_original_three(self):
        import re
        for grupo, linhas in FUTURE.items():
            vivo = prompts._FUTURE_LINES.get(grupo) or prompts._FUTURE_BY_FAMILY.get(grupo)
            self.assertEqual(tuple(vivo[3:]), tuple(linhas), grupo)
            for texto in linhas:
                cheio = texto.replace('{com}', 'com ela')
                self.assertTrue(7 <= lib.words(cheio) <= 18, (grupo, texto))
                self.assertRegex(cheio, r'[.!]$')
                self.assertEqual(set(re.findall(r'\{(\w+)\}', texto)) - {'com'}, set(), (grupo, texto))
                for padrao in lib.BANNED:
                    self.assertIsNone(re.search(padrao if not padrao.startswith('\b') else lib.norm(padrao), lib.norm(cheio)), (grupo, texto))
                for label in lib.FEATURES:
                    self.assertIsNone(re.search(rf'(?<!\w){re.escape(label.casefold())}(?!\w)', cheio.casefold()), (grupo, texto, label))

    def test_a_campaign_with_seven_colors_no_longer_repeats_the_same_three_use_lines(self):
        forms = {'art': 'a', 'dem': 'essa', 'piece': 'blusa', 'pron': 'ela'}
        campanha = {'product': 'Blusa de viscose', 'niche': 'casual'}
        usadas = {prompts._future_options(campanha, forms, i)[0] for i in range(7)}
        self.assertGreaterEqual(len(usadas), 7)

    def test_a_cta_made_for_a_pain_only_appears_when_the_briefing_has_that_pain(self):
        base = dict(model_name='Micaela', product='Blusa de viscose', outfit='blusa', color='Preto', niche='casual',
                    audience='mulheres', benefit='', details='viscose', movements='', objection='', offer='', generator='grok')
        sem = [prompts.generate(base, variant_index=i)['cta'] for i in range(12)]
        self.assertFalse(any('medidas' in c.casefold() for c in sem), sem)
        com = [prompts.generate({**base, 'objection': 'não sei meu tamanho'}, variant_index=i)['cta'] for i in range(12)]
        self.assertTrue(any('medidas' in c.casefold() or 'tamanho' in c.casefold() for c in com), com)


if __name__ == '__main__':
    unittest.main()
