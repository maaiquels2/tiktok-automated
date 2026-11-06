"""Regra de gancho (services/hook_types.py): cinco tipos, um por cor, só com o que o briefing sustenta."""
import re
import unittest

from services import copywriter, hook_types
from services.copywriter import audit as copywriter_audit
from services.prompts import generate, generate_variants, hook_type_for
from services.script_budget import count_words

BASE = dict(model_name='Micaela', niche='casual', tone='conversacional', style='natural', generator='grok', movements='',
            offer='', social_proof='', size_proof='')
VESTIDO = dict(BASE, name='Vestido', product='Vestido midi', outfit='vestido midi', color='Preto, Azul, Verde, Rosa, Bege',
               audience='mulheres adultas', benefit='caimento leve', angle='cintura alta', details='cintura alta, bolso, tecido leve',
               objection='')
FORMS = dict(dem='esse', prep='nesse', piece='vestido', art='o', de='do', pron='ele')

# Uma campanha de cada familia para a auditoria estrita de TODAS as cores.
FAMILIAS = {
    'moda': VESTIDO,
    'beleza': dict(BASE, name='Creme', product='Creme hidratante facial', outfit='creme hidratante', color='Branco, Rosa, Azul, Verde',
                   audience='', benefit='', angle='', details='textura leve, pote de vidro', objection=''),
    'acessorio': dict(BASE, name='Brinco', product='Brinco de argola dourada', outfit='brinco', color='Dourado, Prata, Rose, Preto',
                      audience='', benefit='', angle='', details='pérolas, argola', objection=''),
    'casa': dict(BASE, name='Organizador', product='Organizador de gaveta ajustável', outfit='organizador de gaveta',
                 color='Branco, Cinza, Preto, Bege', audience='quem vive com a gaveta bagunçada', benefit='cada talher no seu lugar',
                 angle='antes e depois da gaveta', details='divisórias ajustáveis, plástico resistente',
                 objection='será que cabe na minha gaveta?', video_mode='mesa'),
}


class TypeRotationTests(unittest.TestCase):
    def test_types_rotate_and_skip_what_the_briefing_does_not_support(self):
        self.assertEqual(hook_types.available(False, False), ['curiosidade', 'fomo', 'direto', 'historia'])
        self.assertEqual(hook_types.available(True, False), ['dor', 'curiosidade', 'fomo', 'direto', 'historia'])
        self.assertEqual(hook_types.available(True, True), list(hook_types.ORDER))
        # O que o briefing declarou abre: identidade/prova, depois a dor, depois os tipos sempre disponiveis.
        self.assertEqual([hook_types.type_for_color(i, True, True) for i in range(6)],
                         ['autoridade', 'dor', 'curiosidade', 'fomo', 'direto', 'historia'])
        # A cor 5 repete o tipo da cor 0, mas pega o segundo molde do tipo.
        self.assertEqual(hook_types.slot_in_type(6, True, True), 1)
        self.assertEqual(hook_types.slot_in_type(0, True, True), 0)

    def test_pain_and_proof_come_from_the_briefing(self):
        self.assertEqual(hook_type_for(VESTIDO, 1)[0], 'fomo')
        com_dor = dict(VESTIDO, objection='fica transparente?')
        self.assertEqual(hook_type_for(com_dor, 0)[0], 'dor')
        com_prova = dict(com_dor, social_proof='mais de 2 mil vendidos · nota 4,8')
        self.assertEqual([hook_type_for(com_prova, i)[0] for i in range(6)], list(hook_types.ORDER))
        self.assertEqual(hook_type_for(dict(VESTIDO, audience='mulheres baixinhas'), 0)[0], 'autoridade')

    def test_each_color_of_a_campaign_gets_a_different_hook(self):
        for c in (VESTIDO, dict(VESTIDO, objection='fica transparente?')):
            ganchos = [v['prompts']['hook'] for v in generate_variants(c)]
            self.assertEqual(len(set(ganchos)), len(ganchos), ganchos)

    def test_the_pain_color_speaks_the_briefing_pain(self):
        c = dict(VESTIDO, objection='fica transparente?')
        ganchos = [v['prompts']['hook'] for v in generate_variants(c)]
        self.assertIn('transparente', ganchos[0], ganchos)


class MoldTests(unittest.TestCase):
    def moldes(self, det='o bolso', pain='ficar transparente'):
        return hook_types.typed_hooks(FORMS, det, pain)

    def test_every_mold_fills_and_fits_the_hook_budget(self):
        for tid, texto in self.moldes():
            self.assertNotIn('{', texto, tid)
            self.assertTrue(8 <= count_words(texto) <= 16, (tid, count_words(texto), texto))

    def test_pain_molds_need_a_pain(self):
        self.assertFalse([t for t, _ in self.moldes(pain='') if t.startswith('ht-dor')])
        self.assertTrue([t for t, _ in self.moldes() if t.startswith('ht-dor')])

    def test_no_mold_breaks_the_writing_rules(self):
        for tid, texto in self.moldes():
            low = texto.casefold()
            self.assertEqual(hook_types.problems(texto), [], tid)
            for padrao in copywriter.GENERIC_HOOK_PATTERNS:
                self.assertIsNone(re.search(padrao, low), (tid, padrao))
            for padrao in copywriter.STAGE_DIRECTION_PATTERNS:
                self.assertIsNone(re.search(padrao, low), (tid, padrao))
            for padrao in copywriter.URGENCY_PATTERNS:
                self.assertIsNone(re.search(padrao, low), (tid, padrao))
            self.assertFalse(hook_types.BLOCKED_RE.search(texto), tid)

    def test_every_mold_has_a_first_person_mark_for_the_strict_audit(self):
        for tid, texto in self.moldes():
            self.assertTrue(any(re.search(p, texto.casefold()) for p in copywriter.FIRST_PERSON_PATTERNS), (tid, texto))

    def test_the_verb_agrees_with_a_plural_detail(self):
        textos = [t for _, t in hook_types.typed_hooks(FORMS, 'as argolas', '')]
        self.assertTrue(any('as argolas me chamaram atenção' in t for t in textos))
        self.assertTrue(any('foram o que mais chamaram' in t for t in textos))
        self.assertFalse([t for t in textos if re.search(r'argolas me (?:chamou|fez|ganhou|surpreendeu)', t)])

    def test_the_classifier_agrees_with_the_mold_type(self):
        for tid, texto in self.moldes():
            self.assertEqual(hook_types.classify(texto), hook_types.type_of(tid), (tid, texto))

    def test_ids_carry_the_type_and_old_molds_keep_theirs(self):
        self.assertEqual(hook_types.type_of('ht-historia-2'), 'historia')
        self.assertEqual(hook_types.type_of('nec-medo'), 'dor')
        self.assertEqual(hook_types.type_of('cont-igual'), 'historia')
        self.assertEqual(hook_types.type_of('sp-vendeu'), 'autoridade')
        self.assertEqual(hook_types.type_of('esc-estoque'), '')

    def test_restrict_prefers_new_molds_and_falls_back_to_the_whole_pool(self):
        pool = [('desc-achei', 'a'), ('ht-curiosidade-0', 'b'), ('ht-historia-0', 'c')]
        self.assertEqual([t for t, _ in hook_types.restrict(pool, 'curiosidade')], ['ht-curiosidade-0', 'desc-achei'])
        self.assertEqual(hook_types.restrict(pool, 'autoridade'), pool)


class RuleTests(unittest.TestCase):
    BLOQUEADOS = ('Depois de testar por 2 anos, eu mudei de ideia.', 'Aprendi isso trabalhando com 30 marcas.',
                  'O dia que tudo deu errado com essa blusa.', 'Não cometa o mesmo erro que eu.',
                  'Você sabia disso?', 'Você já percebeu isso?')

    def test_invented_credentials_history_and_empty_questions_are_blocked(self):
        for texto in self.BLOQUEADOS:
            self.assertTrue(hook_types.problems(texto), texto)
        # Suspense e FOMO foram liberados pelo estudio: nao reprovam.
        self.assertEqual(hook_types.problems('Você não vai acreditar no que o bolso me mostrou.'), [])
        self.assertEqual(hook_types.problems('Você já percebeu o bolso nessa calça? Eu só vi de perto.'), [])

    def test_the_audit_blocks_them_in_both_modes(self):
        pack = dict(hook='Depois de testar por 2 anos eu mudei de ideia sobre ela.',
                    development='Eu achei o bolso muito bom e reparei que o tecido é leve de verdade.',
                    cta='Corre pro carrinho laranja e escolhe o teu', caption='Calça #moda')
        for estrito in (True, False):
            problemas = copywriter.audit(pack, dict(VESTIDO, details='bolso, tecido leve'), strict_style=estrito)
            self.assertTrue([p for p in problemas if 'credencial' in p], (estrito, problemas))

    def test_the_ai_prompt_carries_the_rule_and_each_color_its_type(self):
        self.assertIn('TIPO DE GANCHO (regra)', copywriter.SYSTEM_PROMPT)
        self.assertIn('PROIBIDO no hook', copywriter.SYSTEM_PROMPT)
        self.assertNotIn('@HOOK_TYPES@', copywriter.SYSTEM_PROMPT)
        kind, label = copywriter._batch_hook_type(0, dict(VESTIDO, objection='fica transparente?'))
        self.assertEqual((kind, label), ('dor', 'Dor e problema'))
        linha = copywriter._hook_type_line({'batch_hook_type': 'dor'})
        self.assertIn('TIPO DE GANCHO OBRIGATÓRIO: Dor e problema', linha)
        self.assertEqual(copywriter._hook_type_line({}), '')

    def test_a_real_offer_keeps_the_scarcity_hook_in_front(self):
        c = dict(VESTIDO, offer='20% de desconto até domingo')
        hook = generate(c, variant_index=0)['hook']
        self.assertRegex(hook.casefold(), r'20|desconto|domingo')


class AuditEveryColorTests(unittest.TestCase):
    def test_every_color_of_every_family_passes_the_strict_audit(self):
        for familia, c in FAMILIAS.items():
            for indice, variante in enumerate(generate_variants(c, audit=copywriter_audit)):
                pack = variante['prompts']
                self.assertEqual(copywriter_audit(pack, {**c, 'color': variante['color']}), [],
                                 (familia, indice, pack['hook'], pack['development'], pack['cta']))


if __name__ == '__main__':
    unittest.main()
