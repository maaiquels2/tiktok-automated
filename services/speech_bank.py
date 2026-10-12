"""Banco de falas: conhecimento por categoria de peca + falas aprovadas.

Duas partes:

1. CATEGORIAS -- o que uma pessoa real fala sobre cada tipo de peca: as
   objecoes tipicas de quem compra, a prova falada que o video mostra, as
   ocasioes de uso e moldes de gancho, reacao, fechamento e chamada. E o
   que da ao gerador local uma voz de categoria (biquini nao fala como
   pijama) e o que entra no pedido para a IA como contexto.

2. FALAS APROVADAS -- roteiros que o estudio marcou como bons ("Guardar no
   banco"). Viram exemplos de estilo para a IA da proxima campanha da mesma
   categoria.

Regras de honestidade que todo molde segue (a auditoria confere de novo):
- Molde que cita um atributo declara ``req``: so aparece quando o briefing
  confirma aquele atributo ("bojo", "forro", "cetim"...).
- Opiniao declarada e livre ("fiquei me sentindo linda"); desempenho nao
  ("modela", "nao esquenta") so com o fato no briefing.
- Nada de urgencia, preco ou estoque: isso so vem da oferta real.
- Sem direcao de camera na fala.

Espacos nos moldes: {dem} essa/esse, {piece} a peca, {art} a/o, {de}
da/do, {prep} nessa/nesse, {pron} ela/ele, {teu} a tua/o teu, {det} o
atributo com artigo, {occ} uma ocasiao, {pain} a dor da objecao.
"""
from __future__ import annotations

import json
import re
import time
import unicodedata
import uuid
from pathlib import Path

STORAGE_KEY = 'app-settings/banco_falas.json'
LOCAL_FILE = 'banco_falas.json'
MAX_SAVED = 400


def _norm(text: str) -> str:
    text = unicodedata.normalize('NFKD', str(text or '').casefold())
    return ''.join(ch for ch in text if not unicodedata.combining(ch))


# --------------------------------------------------------------------------
# Categorias. A ordem importa: a mais especifica primeiro ("short legging"
# antes de "legging", "baby doll" antes de "pijama", "colete de couro"
# antes do courino).
# --------------------------------------------------------------------------
CATEGORIES = [
    {
        'id': 'fantasia', 'label': 'Fantasia', 'piece': 'fantasia', 'gender': 'f',
        'keywords': ['fantasia', 'cosplay'],
        'occasions': ['no carnaval', 'numa festa à fantasia', 'no Halloween', 'numa festa temática'],
        'tone': 'Divertido e animado, de quem já está no clima da festa.',
        'avoid': 'Só citar acessório que vem junto se o briefing listar os itens. Não prometer que serve em todo mundo.',
        'objections': [
            {'needles': ['acompanha', 'vem junto', 'acessório', 'acessorio', 'itens', 'incluso', 'completa'],
             'pain': 'não saber o que vem junto', 'proof': 'Por isso quis te mostrar ela inteira, aqui no corpo.'},
            {'needles': ['transparen', 'fino', 'fina', 'tecido', 'barat'], 'pain': 'o tecido ser fininho',
             'proof': 'Por isso tô aqui na luz, pra você ver o tecido.'},
            {'needles': ['vulgar', 'curt', 'exager'], 'pain': 'ficar curta demais',
             'proof': 'Por isso quis te mostrar ela no corpo, de frente e de lado.'},
        ],
        'hooks': [
            {'t': 'Achei a fantasia que eu queria pra festa e olha isso.'},
            {'t': 'Vesti {dem} {piece} e já entrei no clima da festa.'},
            {'t': 'Gente, olha {dem} {piece} que eu separei pra próxima festa.'},
            {'t': 'Tô apaixonada por {dem} {piece}, sério, quero ir pra festa agora.'},
            {'t': 'Se você ainda não sabe do que ir, olha {dem} que eu achei.'},
            {'t': 'Meu medo com fantasia sempre foi {pain}. Olha {dem} aqui.', 'pain': True},
        ],
        'reactions': [
            {'t': 'E olha como ela fica no corpo, ficou perfeita.'},
            {'t': 'Sério, me senti pronta pra festa na hora.'},
            {'t': 'E os detalhes dela são lindos de perto.'},
        ],
        'closers': ['Já tô me vendo com ela {occ}.', 'Perfeita pra usar {occ}.'],
        'ctas': ['Corre pro carrinho laranja e garante {teu}.', 'Tá no carrinho laranja, vai lá ver de pertinho.'],
        'example': {'det': 'os detalhes', 'pain': 'o tecido ser fininho'},
    },
    {
        'id': 'colete', 'label': 'Colete', 'piece': 'colete', 'gender': 'm',
        'keywords': ['colete'],
        'occasions': ['no dia a dia', 'no trabalho', 'pra sair à noite', 'com jeans'],
        'tone': 'Estiloso e despretensioso, de quem gosta de uma terceira peça no look.',
        'avoid': 'Só dizer couro legítimo se o briefing disser; sintético é outra coisa. Não prometer que "não descasca".',
        'objections': [
            {'needles': ['plástico', 'plastico', 'barat', 'falso', 'brilho'], 'pain': 'parecer plástico',
             'proof': 'Por isso quis te mostrar ele aqui na luz, pra você ver o acabamento.'},
            {'needles': ['larg', 'sobra', 'quadrad'], 'pain': 'ficar largo demais',
             'proof': 'Por isso quis te mostrar ele no corpo, de frente e de lado.'},
        ],
        'hooks': [
            {'t': 'Achei o colete que deixa qualquer look básico mais estiloso.'},
            {'t': 'Vesti {dem} {piece} por cima de uma camiseta e virou outro look.'},
            {'t': 'Gente, olha {dem} {piece} que eu achei pra dar cara nova no look.'},
            {'t': 'Tô apaixonada por {dem} {piece}, sério, combina com tudo que eu tenho.'},
            {'t': 'Colete com {feat}? Eu precisava te mostrar esse aqui hoje.', 'req': 'bolso'},
            {'t': 'Meu medo com colete sempre foi {pain}. Olha {dem} aqui.', 'pain': True},
        ],
        'reactions': [
            {'t': 'E olha como ele fica no corpo, bem estiloso.'},
            {'t': 'Sério, uma peça só e o look muda inteiro.'},
            {'t': 'E os botões dão um charme a mais nele.', 'req': 'botões'},
            {'t': 'E o courino tem um brilho bem discreto.', 'req': 'courino'},
        ],
        'closers': ['Dá pra usar {occ} numa boa.', 'Combina demais {occ}.'],
        'ctas': ['Corre pro carrinho laranja e garante {teu}.', 'Tá no carrinho laranja, escolhe {teu} lá.'],
        'example': {'det': 'os botões', 'pain': 'parecer plástico'},
    },
    {
        'id': 'short_legging', 'label': 'Short legging', 'piece': 'short', 'gender': 'm',
        'keywords': ['short legging', 'shorts legging', 'short de academia', 'short fitness',
                     'bermuda legging', 'short de treino', 'short ciclista'],
        'occasions': ['no treino e depois na rua', 'na academia', 'na caminhada', 'no dia a dia'],
        'tone': 'Animado e prático, de quem treina de verdade.',
        'avoid': 'Não prometer que "não sobe" ou "não marca" sem isso no briefing.',
        'objections': [
            {'needles': ['sobe', 'enrola', 'coxa'], 'pain': 'subir na coxa',
             'proof': 'Por isso tô me mexendo aqui, pra você conferir.'},
            {'needles': ['transparen', 'aparece'], 'pain': 'ficar transparente',
             'proof': 'Por isso tô aqui contra a luz, pra você conferir.'},
            {'needles': ['marca', 'aperta'], 'pain': 'marcar demais',
             'proof': 'Por isso quis te mostrar de frente e de lado.'},
        ],
        'hooks': [
            {'t': 'Achei o short de treino que eu tava procurando faz tempo.'},
            {'t': 'Vesti {dem} {piece} pra treinar e não quis mais tirar.'},
            {'t': 'Meu problema com short de treino sempre foi {pain}.', 'pain': True},
            {'t': 'Short com {feat}? Pra mim isso decide tudo no treino.', 'req': 'cintura alta'},
            {'t': 'Achei um short com {feat} e agora o celular vai comigo.', 'req': 'bolso lateral'},
            {'t': 'Gente, olha {dem} {piece} que eu separei pro treino de amanhã.'},
            {'t': 'Tô apaixonada por {dem} {piece}, sério, não quero treinar com outro.'},
            {'t': 'Se você treina de short igual eu, presta atenção {prep} aqui.'},
        ],
        'reactions': [
            {'t': 'E olha como ele veste, fiquei à vontade pra me mexer.'},
            {'t': 'E a cintura alta deixa o visual bem alinhadinho.', 'req': 'cintura alta'},
            {'t': 'E ainda tem {det}, que faz falta em todo short.', 'req': 'bolso lateral'},
            {'t': 'Sério, fiquei muito confortável com ele.'},
            {'t': 'E olha o caimento dele, fica lindo no corpo.'},
            {'t': 'E é de poliamida, aquele tecido gostoso de treinar.', 'req': 'poliamida'},
        ],
        'closers': ['Dá pra usar {occ} numa boa.', 'Já tô vendo ele {occ}.'],
        'ctas': ['Corre pro carrinho laranja e garante {teu}.', 'Tá no carrinho laranja, escolhe {teu} lá.'],
        'example': {'det': 'a cintura alta', 'pain': 'subir na coxa'},
    },
    {
        'id': 'legging', 'label': 'Calça legging', 'piece': 'legging', 'gender': 'f',
        'keywords': ['legging', 'calça legging', 'calca legging', 'calça de academia'],
        'occasions': ['no treino e depois na rua', 'na academia', 'na caminhada', 'no dia a dia'],
        'tone': 'Confiante e direto, de quem conhece academia.',
        'avoid': 'Compressão, "modela", "segura a barriga" só com o fato no briefing.',
        'objections': [
            {'needles': ['transparen', 'aparece', 'calcinha'], 'pain': 'ficar transparente',
             'proof': 'Por isso tô aqui contra a luz, pra você conferir.'},
            {'needles': ['desce', 'escorrega', 'cai'], 'pain': 'descer no agachamento',
             'proof': 'Por isso tô me mexendo aqui, pra você ver se o cós segura.'},
            {'needles': ['marca', 'aperta', 'barriga'], 'pain': 'marcar a barriga',
             'proof': 'Por isso quis te mostrar de frente e de lado.'},
        ],
        'hooks': [
            {'t': 'Vesti {dem} {piece} pra treinar e não quis mais tirar.'},
            {'t': 'Achei a legging que eu queria usar no treino e na rua.'},
            {'t': 'Meu medo com legging sempre foi {pain}. Olha {dem} aqui.', 'pain': True},
            {'t': 'Legging com {feat}? Agora o celular vai comigo no treino.', 'req': 'bolso lateral'},
            {'t': 'O que me ganhou {prep} {piece} foi {det}, olha só.', 'req': 'cós largo'},
            {'t': 'Agachei com {dem} {piece} de frente pra luz, olha o resultado.', 'req': 'sem transparência'},
            {'t': 'Gente, olha {dem} {piece} que eu tô usando hoje no treino.'},
            {'t': 'Tô apaixonada por {dem} {piece}, sério, virou minha favorita do treino.'},
            {'t': 'Se você vive de legging igual eu, olha {dem} aqui.'},
        ],
        'reactions': [
            {'t': 'E ela veste muito bem, fiquei confiante pra treinar.'},
            {'t': 'E o cós largo abraça a cintura de um jeito gostoso.', 'req': 'cós largo'},
            {'t': 'E o bolso lateral é aquele detalhe que faz falta em toda legging.', 'req': 'bolso lateral'},
            {'t': 'E a cintura alta deixa a silhueta bem bonita.', 'req': 'cintura alta'},
            {'t': 'Sério, fiquei muito confortável com ela.'},
            {'t': 'E olha o caimento dela, fica lindo no corpo.'},
        ],
        'closers': ['Dá pra usar {occ} numa boa.', 'Serve {occ}, sem pensar muito.'],
        'ctas': ['Corre pro carrinho laranja e escolhe {teu}.', 'Tá no carrinho laranja, vai lá ver de pertinho.'],
        'example': {'det': 'o cós largo', 'pain': 'ficar transparente'},
    },
    {
        'id': 'calca_jeans', 'label': 'Calça jeans', 'piece': 'calça', 'gender': 'f',
        'keywords': ['calça jeans', 'calca jeans', 'calça de jeans', 'calca de jeans', 'calça denim',
                     'calca denim', 'mom jeans', 'wide leg jeans', 'skinny jeans'],
        'occasions': ['no dia a dia', 'no trabalho', 'pra sair no fim de semana', 'com tênis ou salto'],
        'tone': 'Prático e confiante, de quem achou o jeans que funciona.',
        'avoid': 'Não prometer que "não laceia", "levanta o bumbum" ou "não desbota" sem isso no briefing.',
        'objections': [
            {'needles': ['cintura', 'sobra', 'abre atrás', 'abre atras'], 'pain': 'sobrar na cintura',
             'proof': 'Por isso quis te mostrar ela no corpo, de frente e de lado.'},
            {'needles': ['aperta', 'apertad', 'marca', 'dura'], 'pain': 'apertar demais',
             'proof': 'Por isso tô me mexendo aqui, pra você ver como ela veste.'},
            {'needles': ['comprid', 'curt', 'barra'], 'pain': 'errar no comprimento',
             'proof': 'Por isso quis te mostrar ela inteira, até a barra.'},
        ],
        'hooks': [
            {'t': 'Achei a calça jeans que eu queria pra usar com tudo.'},
            {'t': 'Vesti {dem} {piece} jeans e já virou minha favorita, sério.'},
            {'t': 'Gente, olha {dem} {piece} jeans que eu achei pro dia a dia.'},
            {'t': 'Tô apaixonada por {dem} {piece} jeans, sério, combina com tudo.'},
            {'t': 'Calça jeans de {feat}? Eu precisava te mostrar essa aqui.', 'req': 'cintura alta'},
            {'t': 'Meu problema com calça jeans sempre foi {pain}. Olha {dem} aqui.', 'pain': True},
        ],
        'reactions': [
            {'t': 'E olha como ela veste no corpo, bem certinha.'},
            {'t': 'Sério, é daquelas que vão com tudo que eu tenho.'},
            {'t': 'E a cintura alta deixa a silhueta lindona.', 'req': 'cintura alta'},
            {'t': 'E ainda tem {det}, do jeitinho que eu gosto.', 'req': 'bolso'},
        ],
        'closers': ['Dá pra usar {occ} numa boa.', 'Já tô pensando nela {occ}.'],
        'ctas': ['Corre pro carrinho laranja e garante {teu}.', 'Tá no carrinho laranja, vai lá ver de pertinho.'],
        'example': {'det': 'a cintura alta', 'pain': 'sobrar na cintura'},
    },
    {
        'id': 'calca_courino', 'label': 'Calça de courino', 'piece': 'calça', 'gender': 'f',
        'keywords': ['courino', 'couro sintético', 'couro sintetico', 'couro ecológico', 'couro ecologico',
                     'calça de couro', 'calca de couro', 'cirrê', 'cirre'],
        'occasions': ['pra sair à noite', 'no trabalho', 'num jantar', 'com uma blusinha básica'],
        'tone': 'Elegante e seguro, de quem monta look com pouca coisa.',
        'avoid': 'É courino (couro sintético): nunca dizer couro legítimo. Não prometer que "não esquenta".',
        'objections': [
            {'needles': ['plástico', 'plastico', 'barat', 'falso', 'brilho'], 'pain': 'parecer plástico',
             'proof': 'Por isso quis te mostrar ela aqui na luz, pra você ver o acabamento.'},
            {'needles': ['aperta', 'caimento', 'desconfort', 'dura'], 'pain': 'ficar dura no corpo',
             'proof': 'Por isso tô me mexendo aqui, pra você ver como ela acompanha.'},
            {'needles': ['marca', 'barriga'], 'pain': 'marcar demais',
             'proof': 'Por isso quis te mostrar de frente e de lado.'},
        ],
        'hooks': [
            {'t': 'Achei a calça de courino que salva qualquer look básico.'},
            {'t': 'Vesti {dem} {piece} com uma blusa simples e virou outro look.'},
            {'t': 'Meu medo com calça de courino sempre foi {pain}. Olha {dem} aqui.', 'pain': True},
            {'t': 'Calça de courino com {feat}: vesti e me apaixonei.', 'req': 'cintura alta'},
            {'t': 'Gente, olha {dem} {piece} de courino que eu achei pra sair à noite.'},
            {'t': 'Tô apaixonada por {dem} {piece}, sério, combina com tudo que eu tenho.'},
            {'t': 'Eu achava que courino não era pra mim. Olha {dem} aqui.'},
        ],
        'reactions': [
            {'t': 'E olha o brilho dela na luz, bem discreto.'},
            {'t': 'Fica arrumada sem eu precisar pensar muito no resto.'},
            {'t': 'E ainda tem {det}, que deixa ela mais arrumadinha.', 'req': 'zíper'},
            {'t': 'E a cintura alta deixa a silhueta lindona.', 'req': 'cintura alta'},
            {'t': 'Sério, ela deixa qualquer look mais arrumado.'},
            {'t': 'E olha como ela fica no corpo, super elegante.'},
        ],
        'closers': ['Dá pra usar {occ} numa boa.', 'Já tô pensando nela {occ}.'],
        'ctas': ['Corre pro carrinho laranja e garante {teu}.', 'Tá no carrinho laranja, vai lá ver de pertinho.'],
        'example': {'det': 'a cintura alta', 'pain': 'parecer plástico'},
    },
    {
        'id': 'maio', 'label': 'Maiô', 'piece': 'maiô', 'gender': 'm',
        'keywords': ['maiô', 'maio', 'body de praia', 'trikini'],
        'occasions': ['na praia', 'na piscina', 'no clube', 'na viagem de verão'],
        'tone': 'Leve e de autoestima, de quem se sente bonita no verão.',
        'avoid': 'Não dizer que "modela", "segura a barriga" ou "esconde" sem isso no briefing.',
        'objections': [
            {'needles': ['barriga', 'marca'], 'pain': 'marcar a barriga',
             'proof': 'Por isso quis te mostrar de frente e de lado.'},
            {'needles': ['cavado', 'cava', 'entra', 'pequeno'], 'pain': 'ficar cavado demais',
             'proof': 'Por isso tô me mexendo aqui, pra você conferir.'},
            {'needles': ['segura', 'sustenta', 'peito', 'seio'], 'pain': 'não segurar direito em cima',
             'proof': 'Por isso quis te mostrar ele no corpo, de frente.'},
            {'needles': ['transparen', 'molhad'], 'pain': 'ficar transparente molhado',
             'proof': 'Por isso tô aqui na luz, pra você conferir o tecido.'},
        ],
        'hooks': [
            {'t': 'Eu nunca fui de maiô, e {dem} {piece} mudou minha cabeça.'},
            {'t': 'Vesti {dem} {piece} e fiquei sem vontade nenhuma de tirar, sério.'},
            {'t': 'Achei o maiô que eu quero levar em toda viagem.'},
            {'t': 'Meu medo com maiô sempre foi {pain}. Olha {dem} aqui.', 'pain': True},
            {'t': 'O que me ganhou {prep} {piece} foi {det}, olha que lindo.', 'req': 'bojo'},
            {'t': 'Maiô com {feat}? Eu precisava mostrar esse pra vocês.', 'req': 'decote nas costas'},
            {'t': 'Gente, olha {dem} {piece} que eu separei pras minhas férias de verão.'},
            {'t': 'Tô apaixonada por {dem} {piece}, sério, quero usar o verão inteiro.'},
        ],
        'reactions': [
            {'t': 'E olha como ele veste, me senti linda logo de cara.'},
            {'t': 'E ainda tem {det}, então não preciso de mais nada por baixo.', 'req': 'bojo'},
            {'t': 'E ele é forrado, que era o que eu mais procurava.', 'req': 'forro'},
            {'t': 'E a amarração deixa do jeitinho que eu gosto.', 'req': 'amarração'},
            {'t': 'Sério, me senti muito bem com ele.'},
            {'t': 'E o decote dele é lindo.', 'req': 'decote'},
            {'t': 'E o decote nas costas é o charme dele.', 'req': 'decote nas costas'},
        ],
        'closers': ['Já tô me imaginando com ele {occ}.', 'Perfeito pra usar {occ}.'],
        'ctas': ['Corre pro carrinho laranja e garante {teu} pro verão.', 'Tá no carrinho laranja, escolhe {teu} lá.'],
        'example': {'det': 'o bojo', 'pain': 'marcar a barriga'},
    },
    {
        'id': 'biquini', 'label': 'Biquíni', 'piece': 'biquíni', 'gender': 'm',
        'keywords': ['biquíni', 'biquini', 'bikini', 'top de praia', 'calcinha de praia'],
        'occasions': ['na praia', 'na piscina', 'na viagem', 'no clube'],
        'tone': 'Solar e confiante, de quem já está com cabeça de férias.',
        'avoid': 'Não prometer que "não sai do lugar" ou "não marca" sem isso no briefing.',
        'objections': [
            {'needles': ['segura', 'sustenta', 'cai', 'peito', 'seio'], 'pain': 'não segurar em cima',
             'proof': 'Por isso quis te mostrar ele no corpo, de frente.'},
            {'needles': ['pequeno', 'cavado', 'fio', 'tamanho'], 'pain': 'ficar pequeno demais',
             'proof': 'Por isso quis te mostrar ele inteiro no corpo.'},
            {'needles': ['transparen', 'molhad'], 'pain': 'ficar transparente molhado',
             'proof': 'Por isso tô aqui na luz, pra você conferir o tecido.'},
        ],
        'hooks': [
            {'t': 'Achei o biquíni que eu quero levar pra todas as viagens.'},
            {'t': 'Vesti {dem} {piece} e me senti linda logo de cara.'},
            {'t': 'Meu medo com biquíni sempre foi {pain}. Olha {dem} aqui.', 'pain': True},
            {'t': 'Biquíni de amarração: dá pra deixar do jeitinho que eu gosto.', 'req': 'amarração'},
            {'t': 'Biquíni com {feat}? Eu precisava te mostrar esse aqui hoje.', 'req': 'bojo'},
            {'t': 'Gente, olha {dem} {piece} que eu separei pras minhas férias de verão.'},
            {'t': 'Tô apaixonada por {dem} {piece}, sério, quero levar em toda viagem.'},
            {'t': 'Se você tá procurando biquíni pro verão, olha {dem} que eu achei.'},
        ],
        'reactions': [
            {'t': 'E olha como ele fica no corpo, valoriza muito.'},
            {'t': 'E o bojo me deixa tranquila pra entrar no mar.', 'req': 'bojo'},
            {'t': 'E ele é forrado, que pra mim é obrigatório.', 'req': 'forro'},
            {'t': 'E essa estampa é a cara do verão.', 'req': 'estampa'},
            {'t': 'Sério, me senti muito bem com ele.'},
            {'t': 'E olha o caimento dele, fica lindo no corpo.'},
        ],
        'closers': ['Já tô me imaginando com ele {occ}.', 'Perfeito pra usar {occ}.'],
        'ctas': ['Corre pro carrinho laranja e garante {teu} pro verão.', 'Tá no carrinho laranja, escolhe {teu} lá.'],
        'example': {'det': 'o bojo', 'pain': 'não segurar em cima'},
    },
    {
        'id': 'saida_praia', 'label': 'Saída de praia', 'piece': 'saída de praia', 'gender': 'f',
        'keywords': ['saída de praia', 'saida de praia', 'kimono de praia', 'quimono de praia',
                     'vestido de praia', 'canga'],
        'occasions': ['na praia', 'no almoço depois da praia', 'na piscina', 'na viagem'],
        'tone': 'Elegante e relaxado, de quem quer sair da praia arrumada.',
        'avoid': 'Transparência pode ser proposital nessa peça: não chamar de defeito nem de vantagem sem o briefing.',
        'objections': [
            {'needles': ['transparen', 'aparece'], 'pain': 'mostrar demais',
             'proof': 'Por isso quis te mostrar ela por cima do biquíni.'},
            {'needles': ['amassa', 'mala', 'viagem'], 'pain': 'não caber na mala',
             'proof': 'Por isso quis te mostrar como ela cai no corpo.'},
        ],
        'hooks': [
            {'t': 'Achei a saída de praia que deixa qualquer biquíni mais chique.'},
            {'t': 'Vesti {dem} {piece} por cima do biquíni e virou look.'},
            {'t': 'Saída de praia de crochê é outro nível, olha essa que eu achei.', 'req': 'crochê'},
            {'t': 'A fenda {prep} {piece} me ganhou na hora.', 'req': 'fenda'},
            {'t': 'Gente, olha {dem} {piece} que eu separei pra praia.'},
            {'t': 'Tô apaixonada por {dem} {piece}, sério, vai comigo pra toda praia.'},
            {'t': 'Se você só usa canga, olha {dem} que eu achei.'},
        ],
        'reactions': [
            {'t': 'Dá pra sair da praia direto pro almoço com ela.'},
            {'t': 'E ela é levinha, dá pra jogar na bolsa e levar.', 'req': 'tecido leve'},
            {'t': 'E a amarração deixa no comprimento que eu quiser.', 'req': 'amarração'},
            {'t': 'E o crochê é tão delicado, parece feito à mão.', 'req': 'crochê'},
            {'t': 'Sério, ela deixa o look de praia muito mais bonito.'},
            {'t': 'E olha como ela cai no corpo, fica lindo.'},
            {'t': 'E a fenda deixa ela ainda mais charmosa.', 'req': 'fenda'},
        ],
        'closers': ['Perfeita pra usar {occ}.', 'Já tô me vendo com ela {occ}.'],
        'ctas': ['Corre pro carrinho laranja e garante {teu}.', 'Tá no carrinho laranja, vai lá ver de pertinho.'],
        'example': {'det': 'o crochê', 'pain': 'mostrar demais'},
    },
    {
        'id': 'baby_doll', 'label': 'Baby doll', 'piece': 'baby doll', 'gender': 'm',
        'keywords': ['baby doll', 'babydoll', 'baby-doll', 'camisola curta'],
        'occasions': ['pra dormir', 'numa noite especial', 'de presente pra alguém especial'],
        'tone': 'Delicado e elegante; nunca sensual explícito.',
        'avoid': 'Nada de linguagem sensual explícita, nudez ou duplo sentido.',
        'objections': [
            {'needles': ['vulgar', 'exagerad', 'sensual', 'curto'], 'pain': 'ficar exagerado',
             'proof': 'Por isso quis te mostrar ele no corpo, pra você ver como é delicado.'},
            {'needles': ['aperta', 'incomoda', 'coça', 'coca'], 'pain': 'incomodar pra dormir',
             'proof': 'Por isso quis te mostrar como ele cai no corpo.'},
            {'needles': ['transparen'], 'pain': 'mostrar demais',
             'proof': 'Por isso quis te mostrar ele aqui na luz.'},
        ],
        'hooks': [
            {'t': 'Achei o baby doll mais delicado que eu já vi.'},
            {'t': 'Vesti {dem} {piece} e me senti linda até pra dormir.'},
            {'t': 'Fiquei apaixonada pelo detalhe de renda {prep} {piece}, olha que lindo.', 'req': 'renda'},
            {'t': 'Baby doll de cetim: elegante sem ser exagerado. Eu amei demais.', 'req': 'cetim'},
            {'t': 'Gente, olha {dem} {piece} que eu achei pra dormir linda.'},
            {'t': 'Tô apaixonada por {dem} {piece}, sério, é delicado demais.'},
            {'t': 'Se você quer dormir se sentindo linda, olha o que eu achei.'},
        ],
        'reactions': [
            {'t': 'E olha que delicado, é daqueles que dá vontade de dar de presente.'},
            {'t': 'E a renda é delicadinha, fica lindo no corpo.', 'req': 'renda'},
            {'t': 'E as alças ajustam, então fica do jeitinho certo.', 'req': 'alça regulável'},
            {'t': 'E o cetim tem um brilho lindo, bem elegante.', 'req': 'cetim'},
            {'t': 'Sério, me senti linda com ele.'},
            {'t': 'E olha o caimento dele, delicado do jeito certo.'},
        ],
        'closers': ['Perfeito {occ}.', 'Já tô pensando nele {occ}.'],
        'ctas': ['Tá no carrinho laranja, vai lá ver de pertinho.', 'Corre pro carrinho laranja e escolhe {teu}.'],
        'example': {'det': 'a renda', 'pain': 'ficar exagerado'},
    },
    {
        'id': 'pijama', 'label': 'Pijama', 'piece': 'pijama', 'gender': 'm',
        'keywords': ['pijama', 'conjunto de dormir', 'camisola', 'short doll'],
        'occasions': ['pra dormir', 'pra ficar em casa no fim de semana', 'numa manhã preguiçosa',
                      'pra receber visita em casa'],
        'tone': 'Aconchegante e gostoso, de quem ama ficar em casa.',
        'avoid': 'Não prometer que "não esquenta" ou que é "fresquinho" sem isso no briefing.',
        'objections': [
            {'needles': ['esquenta', 'calor', 'quente'], 'pain': 'esquentar pra dormir',
             'proof': 'Por isso quis te mostrar o tecido, pra você ver como ele cai.'},
            {'needles': ['aperta', 'incomoda', 'coça', 'coca'], 'pain': 'incomodar pra dormir',
             'proof': 'Por isso quis te mostrar ele no corpo, bem soltinho.'},
            {'needles': ['feio', 'velho', 'sem graça', 'sem graca'], 'pain': 'parecer pijama velho',
             'proof': 'Por isso quis te mostrar os detalhes dele.'},
        ],
        'hooks': [
            {'t': 'Achei o pijama que dá vontade de ir dormir mais cedo.'},
            {'t': 'Vesti {dem} {piece} e não quero mais tirar, nem pra sair.'},
            {'t': 'Pijama de cetim sempre foi meu sonho, olha esse que eu achei.', 'req': 'cetim'},
            {'t': 'Pijama com {feat} é outro nível pra mim, olha esse aqui.', 'req': 'botões'},
            {'t': 'Meu problema com pijama sempre foi {pain}. Olha {dem} aqui.', 'pain': True},
            {'t': 'Gente, olha {dem} {piece} que eu achei pro fim de semana.'},
            {'t': 'Tô apaixonada por {dem} {piece}, sério, não quero mais sair de casa.'},
            {'t': 'Se você ama ficar em casa de pijama igual eu, olha {dem} aqui.'},
        ],
        'reactions': [
            {'t': 'E olha como ele veste, bem soltinho no corpo.'},
            {'t': 'E o tecido é macio de um jeito que dá vontade de ficar o dia todo.', 'req': 'tecido macio'},
            {'t': 'E o cetim tem um brilho lindo, fica elegante até pra dormir.', 'req': 'cetim'},
            {'t': 'E ainda tem {det}, que eu acho um charme.', 'req': 'bolso'},
            {'t': 'Sério, fiquei muito confortável com ele.'},
            {'t': 'E olha como ele fica bonito até pra ficar em casa.'},
        ],
        'closers': ['Perfeito {occ}.', 'Já tô me vendo com ele {occ}.'],
        'ctas': ['Corre pro carrinho laranja e garante {teu}.', 'Tá no carrinho laranja, vai lá ver de pertinho.'],
        'example': {'det': 'o cetim', 'pain': 'esquentar pra dormir'},
    },
    {
        'id': 'regata', 'label': 'Regata', 'piece': 'regata', 'gender': 'f',
        'keywords': ['regata', 'regatinha', 'tank top'],
        'occasions': ['no dia a dia', 'com uma calça de alfaiataria', 'no treino', 'pra sair rapidinho'],
        'tone': 'Prático e esperto, de quem monta look rápido.',
        'avoid': 'Não prometer que "não marca o sutiã" sem bojo ou fato no briefing.',
        'objections': [
            {'needles': ['sutiã', 'sutia', 'alça aparece', 'alca aparece'], 'pain': 'aparecer o sutiã',
             'proof': 'Por isso quis te mostrar ela no corpo, de frente e de lado.'},
            {'needles': ['transparen', 'aparece'], 'pain': 'ficar transparente',
             'proof': 'Por isso tô aqui na luz, pra você conferir.'},
            {'needles': ['marca', 'aperta'], 'pain': 'marcar demais',
             'proof': 'Por isso quis te mostrar de frente e de lado.'},
        ],
        'hooks': [
            {'t': 'Regata básica que não parece básica? Achei, e vou te mostrar.'},
            {'t': 'Vesti {dem} {piece} e ela virou minha peça coringa do dia a dia.'},
            {'t': 'Achei uma regata com {feat} e isso muda tudo pra mim.', 'req': 'bojo'},
            {'t': 'Meu problema com regata sempre foi {pain}. Olha {dem} aqui.', 'pain': True},
            {'t': 'Gente, olha {dem} {piece} que eu achei, virou minha favorita.'},
            {'t': 'Tô apaixonada por {dem} {piece}, sério, é a minha cara.'},
            {'t': 'Se você vive de regata igual eu, olha {dem} aqui.'},
        ],
        'reactions': [
            {'t': 'E olha como ela veste certinho no corpo.'},
            {'t': 'E o tecido canelado deixa ela com cara de peça mais cara.', 'req': 'canelado'},
            {'t': 'E com o bojo eu nem preciso pensar no que usar por baixo.', 'req': 'bojo'},
            {'t': 'Sério, ela combina com quase tudo que eu tenho.'},
            {'t': 'E olha o caimento dela, fica lindo no corpo.'},
        ],
        'closers': ['Dá pra usar {occ} numa boa.', 'Combina demais {occ}.'],
        'ctas': ['Corre pro carrinho laranja e escolhe {teu}.', 'Tá no carrinho laranja, vai lá ver de pertinho.'],
        'example': {'det': 'o bojo', 'pain': 'aparecer o sutiã'},
    },
    {
        'id': 'blusa', 'label': 'Blusa', 'piece': 'blusa', 'gender': 'f',
        'keywords': ['blusa', 'blusinha', 'camiseta', 't-shirt', 'tshirt', 'cropped', 'camisa'],
        'occasions': ['no trabalho', 'pra sair com as amigas', 'no dia a dia', 'com jeans ou saia'],
        'tone': 'Arrumado e fácil, de quem gosta de look pronto.',
        'avoid': 'Não dizer que "não amassa" ou "não desbota" sem isso no briefing.',
        'objections': [
            {'needles': ['transparen', 'aparece'], 'pain': 'ficar transparente',
             'proof': 'Por isso tô aqui na luz, pra você conferir.'},
            {'needles': ['amassa', 'amarrot'], 'pain': 'amassar fácil',
             'proof': 'Por isso quis te mostrar ela no corpo, pra você ver o caimento.'},
            {'needles': ['marca', 'aperta', 'curta'], 'pain': 'marcar demais',
             'proof': 'Por isso quis te mostrar de frente e de lado.'},
        ],
        'hooks': [
            {'t': 'Achei uma blusa que eu já sei que vou usar com tudo.'},
            {'t': 'Vesti {dem} {piece} e o look ficou pronto na hora.'},
            {'t': 'O detalhe de renda {prep} {piece} me ganhou na hora.', 'req': 'renda'},
            {'t': 'Meu problema com blusa sempre foi {pain}. Olha {dem} aqui.', 'pain': True},
            {'t': 'Gente, olha {dem} {piece} que eu achei pra sair com as amigas.'},
            {'t': 'Tô apaixonada por {dem} {piece}, sério, deixa o look pronto rapidinho.'},
            {'t': 'Se você precisa de blusa pro trabalho, olha {dem} que eu achei.'},
        ],
        'reactions': [
            {'t': 'E ela é daquelas que deixam o look arrumado sem esforço.'},
            {'t': 'E o tecido é levinho, perfeito pro calor.', 'req': 'tecido leve'},
            {'t': 'E o decote é lindo, valoriza sem exagero.', 'req': 'decote'},
            {'t': 'E a renda é delicadinha, fica lindo no corpo.', 'req': 'renda'},
            {'t': 'Sério, ela combina com quase tudo.'},
            {'t': 'E olha o caimento dela, fica lindo no corpo.'},
            {'t': 'E a viscose tem um caimento lindo.', 'req': 'viscose'},
        ],
        'closers': ['Dá pra usar {occ} numa boa.', 'Combina demais {occ}.'],
        'ctas': ['Corre pro carrinho laranja e escolhe {teu}.', 'Tá no carrinho laranja, vai lá ver de pertinho.'],
        'example': {'det': 'a renda', 'pain': 'ficar transparente'},
    },
]

# --------------------------------------------------------------------------
# Beleza e acessorios: produto sem corpo a vestir. Os moldes falam do que a
# camera mostra de perto (textura, brilho, acabamento) e nunca de caimento,
# provador ou resultado na pele. Cada categoria declara 'family'; _enrich nao
# aplica a elas os moldes de roupa (look combinado, tamanho "no corpo").
# Atributo (`req`) so aparece quando o briefing o confirma: os rotulos vem de
# _PRODUCT_FEATURES em services/prompts.py.
# --------------------------------------------------------------------------
_BASE_HOOKS = [
    {'t': 'Peguei {dem} {piece} pra te mostrar de pertinho, olha só.'},
    {'t': 'Olha {dem} {piece} que eu achei, vem ver de pertinho.'},
    {'t': 'Gente, olha {dem} {piece} que eu tô mostrando aqui na mesa.'},
    {'t': 'Meu problema com {piece} sempre foi {pain}. Olha {dem} aqui.', 'pain': True},
]
_BASE_REACTIONS = [
    {'t': 'E olha de pertinho, dá pra ver bem os detalhes.'},
    {'t': 'Sinceramente, gostei muito mais do que eu imaginava.'},
]
_BASE_CTAS = ['Corre pro carrinho laranja e escolhe {teu}.', 'Tá no carrinho laranja, vai lá ver de pertinho.']
_QUALITY = {'needles': ['qualidade', 'parece barat', 'frágil', 'fragil'], 'pain': 'parecer barato de perto',
            'proof': 'Por isso quis te mostrar o acabamento de pertinho.'}


def _sem_corpo(cid, label, piece, gender, family, keywords, occasions, tone, avoid, objections, hooks,
               reactions, example, closers=None):
    return {
        'id': cid, 'label': label, 'piece': piece, 'gender': gender, 'family': family, 'keywords': keywords,
        'occasions': occasions, 'tone': tone, 'avoid': avoid,
        'objections': [*objections, _QUALITY],
        'hooks': [*hooks, *_BASE_HOOKS],
        'reactions': [*reactions, *_BASE_REACTIONS],
        'closers': closers or ['Dá pra usar {occ} numa boa.', 'Eu usaria {occ}, sem pensar duas vezes.'],
        'ctas': list(_BASE_CTAS), 'example': example,
    }


_ACESSORIO_AVOID = ('Não dizer o material, o banho, a garantia nem que "não escurece" sem isso no briefing. '
                    'Mostrar de perto, sem prometer durabilidade.')
_BELEZA_AVOID = ('Nunca prometer resultado na pele, hidratação, cheiro, proteção ou duração sem isso no briefing. '
                 'Falar só do que a câmera mostra: textura, cor, embalagem.')
_TAMANHO = {'needles': ['tamanho', 'medida', 'pequeno', 'grande'], 'pain': 'errar o tamanho',
            'proof': 'Por isso tô segurando aqui perto, pra você ter noção do tamanho.'}
_ESCURECE = {'needles': ['escurece', 'oxida', 'enferruja', 'mancha'], 'pain': 'escurecer com o tempo',
             'proof': 'Por isso quis te mostrar o acabamento de pertinho.'}

CATEGORIES.extend([
    _sem_corpo('creme', 'Creme', 'creme', 'm', 'beleza',
               ['creme', 'hidratante', 'loção', 'locao', 'esfoliante'],
               ['de manhã', 'à noite', 'no dia a dia'],
               'Calmo e próximo, de quem mostra um achado da rotina.', _BELEZA_AVOID,
               [{'needles': ['pesado', 'oleoso', 'grudent', 'gordur'], 'pain': 'ficar pesado na pele',
                 'proof': 'Por isso tô aqui mostrando a textura de pertinho.'}],
               [{'t': 'A textura {de} {piece} me ganhou assim que eu abri.', 'req': 'textura leve'},
                {'t': 'O pote {de} {piece} já me conquistou na mesa.', 'req': 'pote de vidro'}],
               [{'t': 'E a textura é leve, olha como ele espalha.', 'req': 'textura leve'},
                {'t': 'E é cremoso, dá pra ver na ponta do dedo.', 'req': 'textura cremosa'},
                {'t': 'E o pote é de vidro, fica lindo na mesa.', 'req': 'pote de vidro'},
                {'t': 'E o cheirinho é suave.', 'req': 'perfume suave'}],
               {'det': 'a textura leve', 'pain': 'ficar pesado na pele'}),
    _sem_corpo('serum', 'Sérum', 'sérum', 'm', 'beleza',
               ['sérum', 'serum', 'tônico', 'tonico'],
               ['de manhã', 'à noite', 'no dia a dia'],
               'Calmo e próximo, de quem mostra um achado da rotina.', _BELEZA_AVOID,
               [{'needles': ['pesado', 'oleoso', 'grudent'], 'pain': 'ficar grudento na pele',
                 'proof': 'Por isso tô aqui mostrando a textura de pertinho.'}],
               [{'t': 'O conta-gotas {de} {piece} me chamou atenção na hora.', 'req': 'conta-gotas'}],
               [{'t': 'E tem conta-gotas, dá pra pegar só um pouquinho.', 'req': 'conta-gotas'},
                {'t': 'E é de vitamina C, igual eu pesquisei.', 'req': 'vitamina c'},
                {'t': 'E a textura é leve, olha na ponta do dedo.', 'req': 'textura leve'}],
               {'det': 'o conta-gotas', 'pain': 'ficar grudento na pele'}),
    _sem_corpo('protetor', 'Protetor solar', 'protetor solar', 'm', 'beleza',
               ['protetor solar', 'protetor facial', 'filtro solar'],
               ['de manhã', 'no dia a dia', 'antes de sair de casa'],
               'Prático e direto, de quem mostra uma rotina simples.', _BELEZA_AVOID,
               [{'needles': ['pesado', 'oleoso', 'branco', 'grudent'], 'pain': 'deixar a pele pesada',
                 'proof': 'Por isso tô aqui mostrando a textura de pertinho.'}],
               [{'t': 'O toque seco {de} {piece} me chamou atenção na hora.', 'req': 'toque seco'}],
               [{'t': 'E o toque é seco, olha aqui na minha mão.', 'req': 'toque seco'},
                {'t': 'E a textura é leve, olha como ele espalha.', 'req': 'textura leve'}],
               {'det': 'o toque seco', 'pain': 'deixar a pele pesada'}),
    _sem_corpo('batom', 'Batom', 'batom', 'm', 'beleza',
               ['batom', 'gloss', 'lip tint', 'tint labial'],
               ['no dia a dia', 'pra sair', 'num jantar'],
               'Animado e próximo, de quem testa a cor na hora.', _BELEZA_AVOID,
               [{'needles': ['cor', 'tom', 'diferente'], 'pain': 'a cor ser diferente da foto',
                 'proof': 'Por isso risquei a cor aqui na mão, pra você ver o tom.'}],
               [{'t': 'O acabamento matte {de} {piece} me ganhou na hora.', 'req': 'acabamento matte'}],
               [{'t': 'E o acabamento é matte, olha a cor aqui na mão.', 'req': 'acabamento matte'},
                {'t': 'E é cremoso, dá pra ver o tom bem de pertinho.', 'req': 'textura cremosa'}],
               {'det': 'o acabamento matte', 'pain': 'a cor ser diferente da foto'}),
    _sem_corpo('esmalte', 'Esmalte', 'esmalte', 'm', 'beleza',
               ['esmalte'],
               ['no dia a dia', 'pra uma festa'],
               'Animado e próximo, de quem mostra a cor nas unhas.', _BELEZA_AVOID,
               [{'needles': ['cor', 'tom', 'diferente'], 'pain': 'a cor ser diferente da foto',
                 'proof': 'Por isso tô mostrando a cor nas minhas unhas, de pertinho.'}],
               [{'t': 'A cor {de} {piece} me ganhou na hora, olha nas unhas.'}],
               [{'t': 'E é cremoso, olha o tom aqui nas unhas.', 'req': 'textura cremosa'}],
               {'det': 'a textura cremosa', 'pain': 'a cor ser diferente da foto'}),
    _sem_corpo('perfume', 'Perfume', 'perfume', 'm', 'beleza',
               ['perfume', 'colônia', 'colonia', 'body splash'],
               ['no dia a dia', 'pra sair', 'num jantar'],
               'Elegante e calmo, de quem mostra um achado.', _BELEZA_AVOID,
               [],
               [{'t': 'O frasco {de} {piece} já me conquistou na mesa.', 'req': 'pote de vidro'}],
               [{'t': 'E o frasco é de vidro, fica lindo na mesa.', 'req': 'pote de vidro'},
                {'t': 'E o cheirinho é suave.', 'req': 'perfume suave'}],
               {'det': 'o frasco de vidro', 'pain': ''}),
    _sem_corpo('brinco', 'Brinco', 'brinco', 'm', 'acessorio',
               ['brinco', 'brincos'],
               ['pra sair com as amigas', 'num jantar', 'no dia a dia'],
               'Delicado e animado, de quem mostra um achado de perto.', _ACESSORIO_AVOID,
               [_TAMANHO, _ESCURECE],
               [{'t': 'A argola {prep} {piece} me ganhou na hora.', 'req': 'argolas'},
                {'t': 'A pedra {prep} {piece} me ganhou na hora.', 'req': 'pedra'}],
               [{'t': 'E o formato dela é lindo, olha de pertinho.', 'req': 'argolas'},
                {'t': 'E a pedra brilha demais de pertinho.', 'req': 'pedra'},
                {'t': 'E o banho de ouro dá um brilho lindo.', 'req': 'banho de ouro'},
                {'t': 'Sério, combina com quase tudo.'}],
               {'det': 'as argolas', 'pain': 'errar o tamanho'}),
    _sem_corpo('colar', 'Colar', 'colar', 'm', 'acessorio',
               ['colar', 'gargantilha'],
               ['pra sair com as amigas', 'num jantar', 'no dia a dia'],
               'Delicado e animado, de quem mostra um achado de perto.', _ACESSORIO_AVOID,
               [_TAMANHO, _ESCURECE],
               [{'t': 'O pingente {prep} {piece} me ganhou na hora.', 'req': 'pingente'}],
               [{'t': 'E o pingente balança lindo, olha só.', 'req': 'pingente'},
                {'t': 'E a corrente é fininha, bem delicada.', 'req': 'corrente fina'},
                {'t': 'Sério, combina com quase tudo.'}],
               {'det': 'o pingente', 'pain': 'errar o tamanho'}),
    _sem_corpo('pulseira', 'Pulseira', 'pulseira', 'f', 'acessorio',
               ['pulseira', 'bracelete'],
               ['pra sair com as amigas', 'num jantar', 'no dia a dia'],
               'Delicado e animado, de quem mostra um achado de perto.', _ACESSORIO_AVOID,
               [_TAMANHO, _ESCURECE],
               [{'t': 'As pérolas {prep} {piece} me ganharam na hora.', 'req': 'pérolas'}],
               [{'t': 'E as pérolas dão um charme, olha de pertinho.', 'req': 'pérolas'},
                {'t': 'E é de elástico, dá pra ajustar fácil.', 'req': 'elástico'},
                {'t': 'Sério, combina com quase tudo.'}],
               {'det': 'as pérolas', 'pain': 'errar o tamanho'}),
    _sem_corpo('anel', 'Anel', 'anel', 'm', 'acessorio',
               ['anel', 'anéis', 'aliança', 'alianca'],
               ['pra sair com as amigas', 'num jantar', 'no dia a dia'],
               'Delicado e animado, de quem mostra um achado de perto.', _ACESSORIO_AVOID,
               [_TAMANHO, _ESCURECE],
               [{'t': 'A pedra {prep} {piece} me ganhou na hora.', 'req': 'pedra'}],
               [{'t': 'E a pedra brilha demais de pertinho.', 'req': 'pedra'},
                {'t': 'E o aro é ajustável, serve em vários dedos.', 'req': 'aro ajustável'},
                {'t': 'Sério, combina com quase tudo.'}],
               {'det': 'a pedra', 'pain': 'errar o tamanho'}),
    _sem_corpo('oculos', 'Óculos', 'óculos', 'm', 'acessorio',
               ['óculos', 'oculos'],
               ['no dia a dia', 'na praia', 'pra dirigir'],
               'Descontraído e animado, de quem mostra o achado no rosto.', _ACESSORIO_AVOID,
               [_TAMANHO],
               [{'t': 'A armação {de} {piece} me ganhou na hora.', 'req': 'acetato'}],
               [{'t': 'E a armação é de acetato, olha de pertinho.', 'req': 'acetato'},
                {'t': 'E a lente tem proteção UV.', 'req': 'proteção uv'},
                {'t': 'Sério, combina com quase tudo.'}],
               {'det': 'a armação de acetato', 'pain': 'errar o tamanho'}),
    _sem_corpo('bolsa', 'Bolsa', 'bolsa', 'f', 'acessorio',
               ['bolsa', 'mochila', 'necessaire', 'carteira'],
               ['no dia a dia', 'no trabalho', 'pra sair'],
               'Prático e animado, de quem mostra o achado por dentro e por fora.', _ACESSORIO_AVOID,
               [{'needles': ['tamanho', 'cabe', 'espaço', 'espaco'], 'pain': 'não saber se cabe tudo',
                 'proof': 'Por isso abri aqui, pra você ver o tamanho por dentro.'}],
               [{'t': 'A alça {prep} {piece} me ganhou na hora.', 'req': 'alça regulável'},
                {'t': 'O zíper {de} {piece} me ganhou na hora.', 'req': 'zíper'}],
               [{'t': 'E a alça é regulável, ajusto do meu jeito.', 'req': 'alça regulável'},
                {'t': 'E tem zíper, olha como fecha.', 'req': 'zíper'},
                {'t': 'E por dentro tem forro, olha aqui.', 'req': 'forro'},
                {'t': 'Sério, combina com quase tudo.'}],
               {'det': 'o zíper', 'pain': 'não saber se cabe tudo'}),
])

# Combinacoes que a modelo veste junto (opiniao de estilo, nao fato da peca).
# Vem dos exemplos de "uma peca, varias combinacoes" do material de vendas,
# reescritos em primeira pessoa.
_COMBOS = {
    'short_legging': ('uma regata soltinha', 'um top de academia'),
    'legging': ('uma camiseta oversized', 'um cropped'),
    'calca_jeans': ('uma camiseta básica', 'uma camisa'),
    'calca_courino': ('uma camiseta básica', 'uma camisa branca'),
    'colete': ('uma camiseta branca', 'uma calça jeans'),
    'maio': ('uma saída de praia', 'um short jeans'),
    'biquini': ('uma saída de praia', 'um short jeans'),
    'saida_praia': ('um biquíni', 'uma rasteirinha'),
    'regata': ('uma calça jeans', 'uma saia midi'),
    'blusa': ('uma calça de alfaiataria', 'uma saia'),
}


def _enrich(cat: dict) -> None:
    """Moldes comuns a todas as categorias: escolha antes da compra, look
    combinado, medidas. Tudo em primeira pessoa e sem fato inventado."""
    fem = cat['gender'] == 'f'
    pron = 'ela' if fem else 'ele'
    cat['hooks'].append({'t': 'Antes de escolher {teu} {piece}, olha {dem} que eu achei.'})
    if cat.get('family'):
        return
    combos = _COMBOS.get(cat['id'])
    if combos:
        cat['hooks'].append({'t': f'Vesti {{dem}} {{piece}} com {combos[0]} e olha como ficou.'})
        cat['closers'].append(f'Fica lindo com {combos[1]}.')
    cat['ctas'].append({'t': 'Confere as medidas no carrinho laranja antes de escolher.',
                        'for_pain': 'errar o tamanho'})
    # Duvida de tamanho e a objecao que mais aparece em roupa comprada online.
    cat['objections'].append({
        'needles': ['tamanho', 'medida', 'numeração', 'numeracao', 'veste pequeno', 'veste grande', 'forma'],
        'pain': 'errar o tamanho',
        'proof': f'Por isso quis te mostrar {pron} no corpo, pra você ter noção do tamanho.',
    })


for _cat in CATEGORIES:
    _enrich(_cat)

_BY_ID = {cat['id']: cat for cat in CATEGORIES}


def category(key: str) -> dict | None:
    return _BY_ID.get(key or '')


def detect(campaign: dict) -> str:
    """Categoria pela descricao do produto (o campo produto manda)."""
    for field in ('product', 'outfit', 'name'):
        text = _norm(campaign.get(field))
        if not text:
            continue
        for cat in CATEGORIES:
            if any(re.search(r'\b' + re.escape(_norm(k)) + r'\b', text) for k in cat['keywords']):
                return cat['id']
    return ''


def objection(cat: dict | None, text: str) -> dict | None:
    """Objecao tipica da categoria que casa com a objecao do briefing."""
    if not cat or not text:
        return None
    low = _norm(text)
    for item in cat.get('objections', []):
        if any(_norm(n) in low for n in item['needles']):
            return item
    return None


# --------------------------------------------------------------------------
# Exemplos para exibir (tela do banco) e para orientar a IA.
# --------------------------------------------------------------------------
def _forms(cat: dict) -> dict:
    fem = cat['gender'] == 'f'
    return {
        'piece': cat['piece'], 'art': 'a' if fem else 'o', 'de': 'da' if fem else 'do',
        'dem': 'essa' if fem else 'esse', 'prep': 'nessa' if fem else 'nesse',
        'pron': 'ela' if fem else 'ele', 'teu': 'a tua' if fem else 'o teu',
    }


class _Slots(dict):
    def __missing__(self, key):
        return '{' + key + '}'


def fill(template: str, slots: dict) -> str:
    text = template.format_map(_Slots(slots))
    return re.sub(r'\s+', ' ', text).strip()


def showcase(cat_id: str, with_article=None) -> list[dict]:
    """Roteiros de exemplo da categoria, com valores ilustrativos.

    ``with_article`` poe o artigo no atributo ("bojo" -> "o bojo"); quem
    chama passa o do gerador, que conhece o genero de cada atributo.
    """
    cat = category(cat_id)
    if not cat:
        return []
    example = cat.get('example', {})
    slots = {**_forms(cat), **example, 'occ': cat['occasions'][0],
             'feat': re.sub(r'^(o|a|os|as)\s+', '', example.get('det', ''))}

    def with_req(item):
        req = item.get('req')
        if not req:
            return slots
        return {**slots, 'feat': req, 'det': with_article(req) if with_article else req}

    out = []
    hooks, reactions = cat['hooks'], cat['reactions']
    for i, hook in enumerate(hooks):
        reaction = reactions[i % len(reactions)]
        closer = cat['closers'][i % len(cat['closers'])]
        cta = cat['ctas'][i % len(cat['ctas'])]
        out.append({
            'hook': fill(hook['t'], with_req(hook)),
            'development': fill(f"{fill(reaction['t'], with_req(reaction))} {closer}", slots),
            'cta': fill(cta['t'] if isinstance(cta, dict) else cta, slots),
            'needs': ', '.join(x for x in (hook.get('req'), reaction.get('req'),
                                           'objeção no briefing' if hook.get('pain') else '') if x),
        })
    return out


# --------------------------------------------------------------------------
# Falas aprovadas pelo estudio (Storage na nuvem, arquivo local no PC).
# --------------------------------------------------------------------------
def _read(data_dir, storage_get=None) -> list[dict]:
    if storage_get is not None:
        try:
            raw = storage_get(STORAGE_KEY)
        except Exception as exc:
            if getattr(exc, 'status', None) == 404:
                return []
            raise
        try:
            data = json.loads(raw.decode('utf-8'))
        except (UnicodeDecodeError, ValueError):
            return []
    else:
        path = Path(data_dir) / LOCAL_FILE
        try:
            data = json.loads(path.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            return []
    items = data.get('items') if isinstance(data, dict) else None
    return [item for item in items or [] if isinstance(item, dict)]


def _write(data_dir, items, storage_put=None) -> None:
    body = json.dumps({'items': items}, ensure_ascii=False, indent=2)
    if storage_put is not None:
        storage_put(STORAGE_KEY, body.encode('utf-8'), 'application/json')
        return
    path = Path(data_dir) / LOCAL_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix('.tmp')
    tmp.write_text(body, encoding='utf-8')
    tmp.replace(path)


def saved(data_dir, storage_get=None, cat_id: str = '') -> list[dict]:
    items = _read(data_dir, storage_get)
    if cat_id:
        items = [item for item in items if item.get('category') == cat_id]
    return sorted(items, key=lambda item: item.get('created_at') or 0, reverse=True)


def add(data_dir, entry: dict, storage_get=None, storage_put=None) -> dict:
    items = _read(data_dir, storage_get)
    clean = {k: str(entry.get(k) or '').strip()[:600] for k in ('hook', 'development', 'cta', 'product', 'color', 'note', 'author')}
    if not (clean['hook'] and clean['development'] and clean['cta']):
        raise ValueError('O roteiro precisa de gancho, desenvolvimento e chamada para entrar no banco.')
    key = ' '.join(_norm(clean[k]) for k in ('hook', 'development', 'cta'))
    if any(' '.join(_norm(i.get(k)) for k in ('hook', 'development', 'cta')) == key for i in items):
        raise ValueError('Esse roteiro já está no banco de falas.')
    record = {**clean, 'id': uuid.uuid4().hex[:12], 'category': str(entry.get('category') or ''),
              'campaign_id': entry.get('campaign_id'), 'created_at': int(time.time())}
    items.append(record)
    _write(data_dir, items[-MAX_SAVED:], storage_put)
    return record


def remove(data_dir, item_id: str, storage_get=None, storage_put=None) -> bool:
    items = _read(data_dir, storage_get)
    kept = [item for item in items if item.get('id') != item_id]
    if len(kept) == len(items):
        return False
    _write(data_dir, kept, storage_put)
    return True


def style_examples(items: list[dict], cat_id: str, limit: int = 4) -> list[dict]:
    """Aprovadas da mesma categoria primeiro; completa com as de outras."""
    same = [i for i in items if i.get('category') == cat_id]
    other = [i for i in items if i.get('category') != cat_id]
    return (same + other)[:limit]
