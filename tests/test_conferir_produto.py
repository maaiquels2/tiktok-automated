"""Testes da lógica pura de ferramentas/conferir_produto (sem torch nem ffmpeg).

As séries abaixo são as medidas reais de 12/10/2026 (cobertura do pior 20% dos patches da peça, por segundo, x100).
"""
import contextlib
import importlib.util
import io
import unittest
from pathlib import Path

CAMINHO = Path(__file__).resolve().parent.parent / 'ferramentas' / 'conferir_produto' / 'conferir_produto.py'
spec = importlib.util.spec_from_file_location('conferir_produto', CAMINHO)
cp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cp)


def serie(*pct):
    return [v / 100 for v in pct]


# vídeos BONS de biquíni (peça intacta, com close e giro de lado) e controles de calça jeans aprovados
BOM1_TOPO = serie(95, 91, 90, 91, 83, 80, 86, 89, 82, 86, 88, 85, 87, 82, 80)
BOM1_CALCINHA = serie(94, 88, 85, 85, 70, 68, 89, 92, 83, 89, 91, 88, 84, 83, 79)
BOM2_TOPO = serie(96, 92, 93, 86, 87, 85, 86, 88, 64, 62, 75, 87, 87, 86, 86)
BOM2_CALCINHA = serie(97, 94, 93, 84, 73, 68, 70, 73, 70, 70, 75, 93, 94, 87, 85)
JEANS = [serie(97, 92, 86, 84, 83, 82, 82, 84, 87, 87, 87, 88, 92, 94, 94),
         serie(97, 96, 95, 90, 84, 80, 81, 81, 82, 82, 84, 86, 86, 87, 87),
         serie(94, 88, 88, 89, 93, 90, 90, 91, 92, 91, 91, 91, 91, 91, 92)]
# vídeos em que a peça PERDEU os bordados
ROSA1_TOPO = serie(96, 92, 91, 88, 85, 78, 62, 53, 51, 45, 58, 56, 57, 55, 58)
ROSA2_TOPO = serie(95, 92, 91, 65, 57, 59, 61, 69, 68, 68, 62, 55, 53, 53, 52)
# vídeos em que apareceu algo NOVO (laço): a ferramenta não consegue ver isso (limite documentado)
PRETO_TOPO = serie(95, 91, 91, 79, 85, 85, 81, 73, 66, 76, 70, 72, 89, 87, 85)
MARROM_CALCINHA = serie(93, 90, 90, 81, 82, 63, 72, 86, 91, 91, 82, 83, 90, 84, 86)


class CaixaTests(unittest.TestCase):
    def test_caixa_valida(self):
        self.assertEqual(cp.parse_caixa('0.2, 0.5,0.8,0.92'), (0.2, 0.5, 0.8, 0.92))

    def test_caixa_invalida(self):
        for texto in ('0.2,0.5,0.8', '0.2,0.5,0.8,1.2', '0.8,0.5,0.2,0.9', '0.2,0.9,0.8,0.5', 'a,b,c,d', ''):
            with self.assertRaises(ValueError, msg=texto):
                cp.parse_caixa(texto)

    def test_regioes_prontas_sao_caixas_validas(self):
        for nome, caixa in cp.REGIOES.items():
            self.assertEqual(cp.parse_caixa(','.join(str(v) for v in caixa)), caixa, nome)

    def test_cli_recusa_caixa_ruim_antes_de_carregar_o_modelo(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as erro:
            cp.main([str(CAMINHO), '--caixa', '0.9,0.1,0.2,0.5'])
        self.assertEqual(erro.exception.code, 2)


class PorSegundoTests(unittest.TestCase):
    def test_media_de_cada_segundo_inteiro(self):
        self.assertEqual(cp.por_segundo([1, 1, 1, 1, 0, 0, 0, 0], fps=4), [1.0, 0.0])

    def test_quadros_que_nao_fecham_um_segundo_sao_descartados(self):
        self.assertEqual(len(cp.por_segundo([1] * 10, fps=4)), 2)


class AvaliarTests(unittest.TestCase):
    def test_videos_bons_nao_alertam_apesar_de_close_e_giro(self):
        for nome, s in (('bom1 topo', BOM1_TOPO), ('bom1 calcinha', BOM1_CALCINHA),
                        ('bom2 topo', BOM2_TOPO), ('bom2 calcinha', BOM2_CALCINHA)):
            r = cp.avaliar(s)
            self.assertFalse(r['alerta'], (nome, r['motivos']))

    def test_controles_de_calca_jeans_nao_alertam(self):
        for i, s in enumerate(JEANS):
            self.assertFalse(cp.avaliar(s)['alerta'], i)

    def test_bordado_que_some_alerta_pelos_dois_motivos(self):
        for nome, s, desde in (('rosa com fala', ROSA1_TOPO, 6), ('rosa 3 jeitos', ROSA2_TOPO, 4)):
            r = cp.avaliar(s)
            self.assertTrue(r['alerta'], nome)
            self.assertEqual(len(r['motivos']), 2, (nome, r['motivos']))
            self.assertEqual(r['primeiro_segundo'], desde, nome)

    def test_limite_conhecido_coisa_nova_nao_e_vista(self):
        # O laço no peito (preto) e os laços na calcinha (marrom) NÃO derrubam a cobertura da peça antiga.
        self.assertFalse(cp.avaliar(PRETO_TOPO)['alerta'])
        self.assertFalse(cp.avaliar(MARROM_CALCINHA)['alerta'])

    def test_queda_curta_nao_alerta_mas_queda_que_persiste_alerta(self):
        curta = serie(95, 90, 60, 60, 90, 90, 90, 90)
        self.assertFalse(cp.avaliar(curta)['alerta'])
        longa = serie(95, 90, 60, 60, 60, 60, 90, 90)
        r = cp.avaliar(longa)
        self.assertTrue(r['alerta'])
        self.assertEqual(r['segundos_baixos'], [2, 3, 4, 5])

    def test_final_que_nao_se_recupera_alerta_mesmo_com_poucos_segundos_baixos(self):
        s = serie(95, 92, 90, 88, 85, 80, 75, 70, 68, 68, 68)   # nenhum segundo abaixo de 65, mas termina em 68
        self.assertTrue(cp.avaliar(s)['alerta'])
        self.assertFalse(cp.avaliar(s, limite_final=60)['alerta'])

    def test_limites_podem_ser_ajustados(self):
        self.assertFalse(cp.avaliar(ROSA1_TOPO, limite_queda=40, limite_final=40)['alerta'])
        self.assertTrue(cp.avaliar(BOM2_TOPO, limite_queda=70, segundos_minimos=1)['alerta'])

    def test_serie_vazia_nao_quebra(self):
        r = cp.avaliar([])
        self.assertIn('alerta', r)


if __name__ == '__main__':
    unittest.main()
