"""O que os videos mais vendidos do TikTok Shop tem em comum, virado regra do gerador:
gancho que chama o publico, beneficio com verbo certo e prova de tamanho que so existe se o briefing trouxe."""
import unittest

from services import persuasion
from services.prompts import benefit_clause, generate_variants

BASE = dict(model_name='Micaela', niche='casual', audience='mulheres adultas', benefit='alonga as pernas', angle='', tone='',
            style='', movements='', objection='', offer='', generator='grok', video_mode='', color='Azul claro, Azul escuro',
            product='Calça jeans wide leg', outfit='calça jeans wide leg',
            details='100% algodão, cintura alta, bolsos funcionais, barra longa')


def variants(**extra):
    return generate_variants({**BASE, **extra})


class BenefitWithVerbTests(unittest.TestCase):
    def test_a_benefit_that_starts_with_a_verb_does_not_get_tem(self):
        for beneficio in ('alonga as pernas', 'afina a cintura', 'dá uma boa alongada nas pernas'):
            self.assertNotIn('peça tem ' + beneficio.split()[0], benefit_clause({'benefit': beneficio, 'niche': 'casual'}))
        self.assertEqual(benefit_clause({'benefit': 'alonga as pernas', 'niche': 'casual'}), 'A peça alonga as pernas')

    def test_a_noun_benefit_still_gets_tem_even_when_it_starts_like_a_verb(self):
        # "caimento" comeca com "cai", "secagem" com "seca", "temperatura" com "tem".
        for beneficio in ('caimento fluido', 'secagem rápida', 'temperatura ideal'):
            self.assertEqual(benefit_clause({'benefit': beneficio, 'niche': 'casual'}), f'A peça tem {beneficio}')

    def test_the_spoken_line_and_the_video_prompt_read_right(self):
        for v in variants():
            texto = ' '.join([v['prompts']['development'], v['prompts']['video']])
            self.assertNotIn('tem alonga', texto)
        self.assertTrue(any('ela alonga as pernas' in v['prompts']['development'] for v in variants()))


class IdentityHookTests(unittest.TestCase):
    def test_audience_identity_only_for_the_known_markers(self):
        self.assertEqual(persuasion.audience_identity('mulheres baixinhas')['plural'], 'baixinhas')
        self.assertEqual(persuasion.audience_identity('quem é plus size')['verb'], 'é plus size')
        self.assertEqual(persuasion.audience_identity('mulheres adultas'), {})
        self.assertEqual(persuasion.audience_identity('quem gosta de cintura alta'), {})
        self.assertEqual(persuasion.audience_identity(''), {})

    def test_no_niche_default_audience_triggers_an_identity_hook(self):
        from services.model_library import NICHE_DEFAULTS
        for nicho, padrao in NICHE_DEFAULTS.items():
            self.assertEqual(persuasion.audience_identity(padrao.get('audience')), {}, nicho)

    def test_without_an_identity_the_hooks_are_untouched(self):
        for v in variants():
            for frase in ('Amigas ', 'pra quem é', 'Se você é'):
                self.assertNotIn(frase, v['prompts']['hook'])

    def test_with_an_identity_the_first_color_opens_calling_the_audience_and_colors_differ(self):
        ganchos = [v['prompts']['hook'] for v in variants(audience='mulheres baixinhas')]
        self.assertIn('baixinha', ganchos[0])
        self.assertEqual(len(set(ganchos)), len(ganchos))

    def test_the_text_for_the_editor_carries_the_identity_not_the_video_prompt(self):
        rotulos = [v['prompts'][k] for v in variants(audience='mulheres baixinhas') for k in ('screen_text', 'cover_text')]
        self.assertTrue(any('pra quem é baixinha' in r for r in rotulos))
        for v in variants(audience='mulheres baixinhas'):
            self.assertNotIn('pra quem é baixinha', v['prompts']['video'].split('Fala (PT-BR)')[0])


SIZE = '1,47 m, tamanho 34, sobrou um pouco na barra'


class SizeProofTests(unittest.TestCase):
    def test_the_parser_reads_only_what_was_written(self):
        f = persuasion.size_facts(SIZE)
        self.assertEqual((f['height'], f['size'], f['notes']), ('1,47 m', '34', ['sobrou um pouco na barra']))
        self.assertEqual(persuasion.size_facts('150cm')['height'], '1,50 m')
        self.assertEqual(persuasion.size_facts('Peguei o 36')['size'], '36')
        self.assertEqual(persuasion.size_facts(''), {})
        self.assertNotIn('height', persuasion.size_facts('preço 2,50'))

    def test_without_the_field_nothing_about_size_is_spoken(self):
        for v in variants(color='Azul claro, Azul escuro, Preto'):
            falado = ' '.join(v['prompts'][k] for k in ('hook', 'development', 'cta')).casefold()
            for termo in ('1,47', 'tamanho 3', 'tenho 1', 'sobrou', 'ajuste'):
                self.assertNotIn(termo, falado)

    def test_with_the_field_the_declared_data_is_spoken_and_nothing_else(self):
        falas = [' '.join(v['prompts'][k] for k in ('hook', 'development')) for v in variants(size_proof=SIZE)]
        junto = ' '.join(falas)
        self.assertIn('1,47 m', junto)
        self.assertIn('tamanho 34', junto)
        self.assertIn('Sobrou um pouco na barra', junto)
        self.assertEqual(persuasion.size_problems(junto, SIZE), [])
        for inventado in ('não precisei', 'nenhum ajuste', 'fica perfeita'):
            self.assertNotIn(inventado, junto)

    def test_colors_do_not_repeat_the_same_size_sentence(self):
        desenvolvimentos = [v['prompts']['development'] for v in variants(size_proof=SIZE, color='Azul claro, Azul escuro, Preto')]
        self.assertEqual(len(set(desenvolvimentos)), len(desenvolvimentos))

    def test_a_spoken_height_or_size_that_was_not_declared_is_a_problem(self):
        self.assertTrue(persuasion.size_problems('Eu tenho 1,60 m e peguei o tamanho 38', SIZE))
        self.assertTrue(persuasion.size_problems('Eu tenho 1,50 m', ''))
        self.assertEqual(persuasion.size_problems('Eu tenho 1,47 m e peguei o tamanho 34', SIZE), [])

    def test_the_honesty_audit_of_scripts_and_arc_clips_rejects_an_invented_height(self):
        from services.copywriter import audit as honesty_audit
        from services.story_arcs import clip_problems
        fala = dict(hook='Eu tenho 1,60 m e olha essa calça', development='Peguei o tamanho 38 e ficou ótima',
                    cta='Corre pro carrinho laranja')
        base = {**BASE, 'size_proof': SIZE}
        achados = ' '.join(honesty_audit(fala, base, require_caption=False, strict_style=False))
        self.assertIn('altura declarada', achados)
        self.assertIn('numeração declarada', achados)
        trio = [fala['hook'], fala['development'], fala['cta']]
        self.assertTrue(any('altura declarada' in p for p in clip_problems(trio, 1, 1, base)))
        ok = [t for t in clip_problems(['Eu tenho 1,47 m e olha essa calça', 'Peguei o tamanho 34, sobrou um pouco na barra',
                                        'Corre pro carrinho laranja'], 1, 1, base) if 'declarad' in t]
        self.assertEqual(ok, [])

    def test_the_ai_brief_forbids_inventing_size_when_empty_and_quotes_it_when_declared(self):
        vazio = ' '.join(persuasion.size_brief_lines(''))
        self.assertIn('PROIBIDO', vazio)
        declarado = ' '.join(persuasion.size_brief_lines(SIZE))
        self.assertIn('1,47 m', declarado)
        self.assertIn('única fonte', declarado)


class SizeProofApiTests(unittest.TestCase):
    def setUp(self):
        import tempfile
        from pathlib import Path
        from app import create_app
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.client = create_app(dict(TESTING=True, DATA_DIR=root / 'data', MEDIA_DIR=root / 'media',
                                      PROFILE_DIR=root / 'profiles')).test_client()
        self.headers = {'X-Local-App': 'fabrica-tiktok'}
        self.addCleanup(self.temp.cleanup)

    def test_the_field_is_saved_with_the_campaign_and_comes_back(self):
        brief = dict(name='Prova de tamanho', model_name='Micaela', outfit='Calça jeans', color='Azul', product='Calça',
                     audience='Mulheres baixinhas', benefit='Alonga as pernas', angle='Detalhes', tone='Natural',
                     style='Realista', generator='grok', size_proof=SIZE)
        r = self.client.post('/api/campaigns', json=brief, headers=self.headers)
        self.assertEqual(r.status_code, 201, r.json)
        self.assertEqual(self.client.get(f'/api/campaigns/{r.json["id"]}').json['size_proof'], SIZE)

    def test_the_preview_shows_what_was_understood(self):
        r = self.client.post('/api/persuasion/preview', json={'size_proof': SIZE}, headers=self.headers).json
        self.assertEqual(r['size'], ['altura 1,47 m', 'tamanho 34', 'sobrou um pouco na barra'])
        self.assertFalse(r['size_unread'])
        vazio = self.client.post('/api/persuasion/preview', json={'size_proof': ''}, headers=self.headers).json
        self.assertEqual((vazio['size'], vazio['size_unread']), ([], False))


if __name__ == '__main__':
    unittest.main()
