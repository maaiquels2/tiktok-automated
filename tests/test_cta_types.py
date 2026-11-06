"""CTA tipado e abertura de FOMO dos videos longos (services/cta_types.py + services/story_arcs.py)."""
import re
import unittest
from unittest import mock

from services import copywriter, cta_types, hook_types, story_arcs
from services.prompts import piece_forms
from services.story_arcs import WORD_CEILING, WORD_FLOOR, build_story_arc, closing_type, draft_lines

BASE = dict(model_name='Micaela', audience='', benefit='', angle='', tone='', style='', movements='', generator='grok',
            objection='', offer='', video_mode='espelho', name='Calça', product='Calça jeans', outfit='calça jeans reta',
            color='Azul', niche='dia-a-dia', details='lavagem clara, cintura alta, bolsos na frente')
OBJECAO = dict(objection='será que fica transparente?')
PROVA = dict(social_proof='mais de 2 mil vendidos · nota 4,8', size_proof='1,60 m, tamanho 38')
PUBLICO = dict(audience='mulheres baixinhas')
OFERTA = dict(offer='20% de desconto até domingo')
BRIEFINGS = {
    'nada': {},
    'objecao': OBJECAO,
    'prova': PROVA,
    'publico': PUBLICO,
    'oferta': OFERTA,
    'tudo': {**OBJECAO, **PROVA, **PUBLICO, **OFERTA},
}
ARCS = tuple(story_arcs.ARCS)
SLOTS = range(0, 11)


def campanha(briefing='nada', modo='espelho', **extra):
    return {**BASE, **BRIEFINGS[briefing], 'video_mode': modo, **extra}


def falas_do_fim(r):
    return r['clips'][-1]['lines'][2]


class TypeRuleTests(unittest.TestCase):
    def test_every_type_has_a_label_a_guide_and_a_place_in_the_order(self):
        self.assertEqual(len(cta_types.ORDER), 12)
        for kind in cta_types.ORDER:
            self.assertTrue(cta_types.label(kind), kind)
            self.assertTrue(cta_types.GUIDE.get(kind), kind)

    def test_the_new_closings_fit_the_short_video_cta_budget(self):
        # A IA imita a frase-base: molde com mais de 10 palavras estoura o orçamento e o app troca por um CTA neutro.
        for kind in ('oportunidade', 'exclusividade'):
            for mold in cta_types.MOLDS[kind]:
                self.assertTrue(6 <= len(mold.split()) <= 10, mold)

    def test_types_depend_on_what_the_briefing_supports(self):
        sem = cta_types.available(cta_types.profile(False, '', {}, {}, {}, 'motivos'))
        self.assertEqual(sem, ['oportunidade', 'exclusividade', 'diferencial', 'experiencia', 'custo', 'comparar', 'decisao'])
        # Dúvida e problema: os arcos que abrem numa dúvida ou num problema podem relembrá-lo.
        self.assertIn('problema', cta_types.available(cta_types.profile(False, '', {}, {}, {}, 'problema')))
        self.assertIn('problema', cta_types.available(cta_types.profile(False, '', {}, {}, {}, 'questionada')))
        self.assertNotIn('problema', cta_types.available(cta_types.profile(False, '', {}, {}, {}, 'mito')))
        tudo = cta_types.available(cta_types.profile(True, 'ficar transparente', {'sold': '2 mil'}, {}, {'verb': 'é baixinha'},
                                                     'motivos'))
        self.assertEqual(tudo, list(cta_types.ORDER))

    def test_color_zero_keeps_the_validated_closing_and_the_next_colors_rotate(self):
        has = cta_types.profile(False, '', {}, {}, {}, 'motivos')
        self.assertEqual(cta_types.type_for_slot(0, has), '')
        kinds = [cta_types.type_for_slot(i, has) for i in range(1, 7)]
        self.assertEqual(kinds, ['oportunidade', 'exclusividade', 'diferencial', 'experiencia', 'custo', 'comparar'])
        self.assertEqual([cta_types.slot_in_type(i, has) for i in (1, 7, 8, 14, 15)], [0, 0, 1, 1, 2])

    def test_a_long_pain_does_not_go_into_the_closing(self):
        forms = piece_forms(campanha())
        longa = 'ficar transparente quando eu agacho na academia'
        textos = cta_types.candidates('objecao', 'motivos', forms, 'cintura alta', longa, {}, {}, {})
        self.assertEqual(textos, ['Quebra essa dúvida de vez: confere no carrinho laranja.'])

    def test_the_rule_text_names_the_ten_types_and_the_honesty_limits(self):
        texto = cta_types.rule_text()
        for kind in cta_types.ORDER:
            self.assertIn(cta_types.LABELS[kind], texto)
        self.assertIn('carrinho laranja', texto)
        self.assertIn('Nunca invente preço', texto)


class DraftTests(unittest.TestCase):
    def test_every_arc_clip_count_color_and_briefing_passes_the_rules(self):
        for briefing in BRIEFINGS:
            for modo in ('espelho', ''):
                c = campanha(briefing, modo)
                for arc in ARCS:
                    for clips in (2, 3):
                        for slot in SLOTS:
                            r = build_story_arc(c, c['color'], arc, clips, slot_index=slot, base_image=slot > 0)
                            rotulo = (briefing, modo, arc, clips, slot)
                            for clip in r['clips']:
                                self.assertEqual(clip['problems'], [], (rotulo, clip['index'], clip['lines']))
                                self.assertTrue(WORD_FLOOR <= clip['words'] <= WORD_CEILING, (rotulo, clip['index'], clip['words']))
                                # So o ultimo clipe pede a compra.
                                self.assertEqual('carrinho' in clip['spoken'].casefold(), clip['final'], (rotulo, clip['index']))

    def test_each_color_closes_differently_and_color_zero_is_unchanged(self):
        for briefing in BRIEFINGS:
            c = campanha(briefing)
            forms = piece_forms(c)
            for arc in ARCS:
                for clips in (2, 3):
                    fechos = [falas_do_fim(build_story_arc(c, c['color'], arc, clips, slot_index=i)) for i in SLOTS]
                    rotulo = (briefing, arc, clips)
                    self.assertEqual(len(set(fechos)), len(fechos), (rotulo, fechos))
                    aberturas = [' '.join(re.findall(r'\w+', f.casefold())[:3]) for f in fechos]
                    self.assertEqual(len(set(aberturas)), len(aberturas), (rotulo, aberturas))
                    self.assertEqual(fechos[0], story_arcs._cta_for_slot(c, forms, 0), rotulo)
                    self.assertEqual(fechos[0], falas_do_fim(build_story_arc(c, c['color'], arc, clips)), rotulo)

    def test_color_zero_opening_is_the_one_validated_before(self):
        c = campanha()
        self.assertIn('Três motivos', build_story_arc(c, c['color'], 'motivos', 3)['clips'][0]['lines'][0])
        self.assertIn('vale mesmo a pena', build_story_arc(c, c['color'], 'questionada', 3)['clips'][0]['lines'][0])

    def test_the_closing_only_says_what_the_briefing_supports(self):
        proibidas = {
            'nada': r'vendeu|nota \d|tenho 1|peguei o|baixinha|medo|receio|desconto|domingo|20\s?%',
            'objecao': r'vendeu|nota \d|tenho 1|peguei o|baixinha|desconto|domingo|20\s?%',
            'prova': r'baixinha|medo|receio|desconto|domingo|20\s?%',
            'publico': r'vendeu|nota \d|tenho 1|peguei o|medo|receio|desconto|domingo|20\s?%',
        }
        for briefing, padrao in proibidas.items():
            c = campanha(briefing)
            for arc in ARCS:
                for slot in SLOTS:
                    fecho = falas_do_fim(build_story_arc(c, c['color'], arc, 3, slot_index=slot))
                    self.assertIsNone(re.search(padrao, fecho.casefold()), (briefing, arc, slot, fecho))

    def test_each_declared_signal_shows_up_in_some_color(self):
        esperado = {'objecao': r'receio|medo|dúvida', 'prova': r'vendeu|nota|tenho|peguei', 'publico': r'baixinhas|baixinha',
                    'oferta': r'domingo|20|desconto|oferta'}
        for briefing, padrao in esperado.items():
            c = campanha(briefing)
            fechos = ' | '.join(falas_do_fim(build_story_arc(c, c['color'], 'motivos', 3, slot_index=i)) for i in SLOTS)
            self.assertRegex(fechos.casefold(), padrao, briefing)

    def test_the_offer_type_takes_the_pool_closing_with_the_real_numbers(self):
        c = campanha('oferta')
        self.assertEqual(closing_type(c, 'motivos', 1), 'oferta')
        self.assertEqual(closing_type(c, 'motivos', 0), '')
        r = build_story_arc(c, c['color'], 'motivos', 2, slot_index=1)
        self.assertEqual(r['closing_type'], 'Urgência com oferta')
        self.assertRegex(falas_do_fim(r).casefold(), r'domingo|20|desconto')

    def test_closings_never_use_urgency_or_stage_directions_without_an_offer(self):
        c = campanha('nada')
        for arc in ARCS:
            for slot in SLOTS:
                fecho = falas_do_fim(build_story_arc(c, c['color'], arc, 3, slot_index=slot)).casefold()
                for padrao in copywriter.URGENCY_PATTERNS + copywriter.STAGE_DIRECTION_PATTERNS:
                    self.assertIsNone(re.search(padrao, fecho), (arc, slot, fecho, padrao))
                self.assertIn('carrinho laranja', fecho)


class FomoOpeningTests(unittest.TestCase):
    def test_odd_colors_open_with_suspense_and_never_ask_for_the_purchase(self):
        for briefing in ('nada', 'objecao', 'tudo'):
            c = campanha(briefing)
            for arc in ARCS:
                for clips in (2, 3):
                    for slot in SLOTS:
                        r = build_story_arc(c, c['color'], arc, clips, slot_index=slot)
                        abertura = r['clips'][0]['lines'][0]
                        rotulo = (briefing, arc, clips, slot, abertura)
                        if slot % 2 == 1:
                            self.assertRegex(abertura.casefold(), r'passa batido|ninguém repara|ninguém conta|deixar passar|deixei passar|'
                                                                    r'quase não contei|passei batido', rotulo)
                            self.assertEqual(r['opening_type'], 'Suspense e FOMO', rotulo)
                        else:
                            self.assertEqual(r.get('opening_type', ''), '', rotulo)
                        self.assertIsNone(re.search(r'carrinho|comprar|garante|corre pro', abertura.casefold()), rotulo)
                        self.assertEqual(hook_types.problems(abertura), [], rotulo)

    def test_the_suspense_does_not_become_stock_or_deadline_urgency(self):
        c = campanha('nada')
        for arc in ARCS:
            for slot in (1, 3, 5, 7, 9):
                abertura = build_story_arc(c, c['color'], arc, 3, slot_index=slot)['clips'][0]['lines'][0].casefold()
                for padrao in copywriter.URGENCY_PATTERNS:
                    self.assertIsNone(re.search(padrao, abertura), (arc, slot, abertura))

    def test_the_two_wordings_alternate_between_odd_colors(self):
        c = campanha('nada')
        for arc in ARCS:
            aberturas = {build_story_arc(c, c['color'], arc, 3, slot_index=i)['clips'][0]['lines'][0] for i in (1, 3, 5, 7)}
            self.assertEqual(len(aberturas), 2, (arc, aberturas))


class ResponseAndAiTests(unittest.TestCase):
    def test_the_response_names_the_types_only_for_a_drafted_color_after_the_first(self):
        c = campanha('objecao')
        self.assertNotIn('closing_type', build_story_arc(c, c['color'], 'motivos', 3))
        r = build_story_arc(c, c['color'], 'motivos', 3, slot_index=3)
        self.assertEqual(r['closing_type'], 'Quebrar objeção')
        self.assertEqual(build_story_arc(c, c['color'], 'motivos', 3, slot_index=1)['closing_type'], 'Oportunidade perdida')
        self.assertEqual(build_story_arc(c, c['color'], 'motivos', 3, slot_index=2)['closing_type'], 'Exclusividade')
        self.assertEqual(r['opening_type'], 'Suspense e FOMO')
        editado = [['Gancho editado fora', 'Meio editado fora com lavagem clara, cintura alta e bolsos na frente', 'Fecho editado'],
                   ['Gancho dois editado', 'Meio dois editado fora mostrando a cintura alta e a lavagem clara', 'Fecho dois'],
                   ['Gancho três editado', 'Meio três editado fora com os bolsos na frente e a cintura alta', 'Fecho final tá no carrinho laranja']]
        self.assertNotIn('closing_type', build_story_arc(c, c['color'], 'motivos', 3, lines=editado, slot_index=3))

    def test_the_ai_prompt_carries_the_ten_types_and_the_type_of_the_color(self):
        capturado = {}

        def falso(settings, system, user, validate):
            capturado['system'] = system
            return None, 'simulado'

        c = campanha('objecao')
        with mock.patch.object(copywriter, 'ask_json', falso):
            story_arcs.write_lines_with_ai(c, 'motivos', 3, {}, slot_index=3)
            um = capturado['system']
            story_arcs.write_lines_with_ai(c, 'motivos', 3, {}, slot_index=0)
            zero = capturado['system']
        self.assertIn('TIPO DE FECHAMENTO (regra)', um)
        self.assertIn('fechamento é do tipo "Quebrar objeção"', um)
        self.assertIn('suspense e FOMO', um)
        # A cor 0 recebe a regra, mas nao um tipo nem a abertura de FOMO.
        self.assertIn('TIPO DE FECHAMENTO (regra)', zero)
        self.assertNotIn('fechamento é do tipo', zero)
        self.assertNotIn('abertura do clipe 1 é de suspense', zero)

    def test_draft_lines_returns_three_parts_per_clip(self):
        c = campanha('nada')
        espelho, facts = story_arcs.check_campaign(c)
        for slot in range(0, 6):
            for clips in (2, 3):
                lista = draft_lines(c, 'motivos', clips, facts, slot)
                self.assertEqual([len(trio) for trio in lista], [3] * clips)


if __name__ == '__main__':
    unittest.main()
