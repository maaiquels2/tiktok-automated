"""Monta o pacote de teste de SEQUENCIA (storytelling) para o CapCut: calça jeans no espelho.

Sem API e sem custo. Dois arcos de 3 clipes de 15 s cada, que se encaixam um no outro:
  A "motivos"     3 motivos para a calça estar no guarda-roupa
  B "questionada" 'calça jeans não te valoriza porque X, Y ou Z' e a resposta

Base: o prompt do espelho que saiu perfeito no controle K2 (mesma modelo, mesmo espelho,
mesmas regras de mão). Entre os clipes só mudam as falas, a coreografia e o começo/fim:
  - bloco de identidade e de cenário: texto IDÊNTICO nos 3 clipes (gerado pelo mesmo código);
  - clipes 1 e 2 NÃO fecham a venda: terminam no meio do gesto, com uma pergunta aberta;
  - só o clipe 3 tem CTA e o gesto de apontar para baixo (carrinho).

Duas técnicas de encadeamento, para o teste comparar:
  imagem  o ÚLTIMO QUADRO do clipe anterior vira o primeiro quadro do próximo (mais controle)
  extend  "Extend Video" do Grok, com um prompt curto do que acontece DEPOIS

Fatos: só entram os que a foto da calça mostra. CONFIRA em FATOS antes de gerar.

Como rodar (na pasta Fabrica_TikTok):
    .venv\\Scripts\\python.exe -I lote-sequencia-2026-10-12\\monta_sequencia.py
"""
import io
import json
import re
import sys
from pathlib import Path

PASTA = Path(__file__).resolve().parent
sys.path.insert(0, str(PASTA.parent))

from services.copywriter import audit  # noqa: E402
from services.prompt_improve import build_compact_video_prompt  # noqa: E402
from services.prompts import _count_words, generate  # noqa: E402

# Fatos confirmados pela foto K2 (cintura alta, lavagem clara, perna reta, dois bolsos na frente).
# Se algum NÃO for verdade na peça real, tire daqui e das falas abaixo, e rode de novo.
FATOS = 'lavagem clara, cintura alta, modelagem reta, bolsos na frente'

CAMPANHA = dict(
    model_name='Micaela', product='Calça jeans', outfit='calça jeans', color='Azul claro', details=FATOS,
    niche='dia-a-dia', generator='grok', video_mode='espelho',
    audience='', benefit='', angle='', tone='', style='', movements='', objection='', offer='',
)

# Cada clipe: 3 falas (0-4 s, 4-12 s, 12-15 s), a coreografia e o que aparece no CapCut.
# Densidade igual à do app (cerca de 50 a 55 palavras por 15 s): abaixo de 46 palavras sobravam 2 a 3 s
# de silêncio no fim do clipe, e silêncio no emenda estraga a sequência.
ARCOS = {
    'A-motivos': dict(
        titulo='3 motivos para a calça jeans estar no guarda-roupa',
        capa='3 motivos pra essa calça estar no seu guarda-roupa',
        clipes=[
            dict(
                papel='Gancho + motivo 1 (cintura alta)',
                falas=('Três motivos pra essa calça jeans estar no teu guarda-roupa, olha só.',
                       'O primeiro eu vi assim que coloquei: a cintura alta. Olha onde ela termina, bem aqui, '
                       'e já imagina com blusinha curta, com camiseta por dentro, com camisa amarrada.',
                       'E o segundo motivo? Esse eu guardei pra você ver logo em seguida.'),
                abertura='dá um passo até o espelho com sorriso confiante e passa a mão no cós da calça',
                meio='passa a mão na cintura mostrando onde a calça termina e, sem parar, gesticula enquanto fala '
                     'dos looks, voltando sempre a mão para a calça',
                fim='termina de frente para o espelho, com a mão livre pousada na cintura, no meio do gesto, sem '
                    'apontar e sem pose de fechamento; a fala segue até o último segundo',
                ultimo_quadro='de frente, celular no peito, mão livre pousada na cintura, falando, sem pose final',
                tela='3 motivos pra ter essa calça',
                amarra='pergunta aberta ("E o segundo motivo?") + gesto parado na cintura',
            ),
            dict(
                papel='Motivos 2 e 3 (lavagem clara, perna reta e bolsos)',
                falas=('É a lavagem clara, repara nesse azul leve, eu já vejo ela com jaqueta preta.',
                       'O terceiro é a modelagem reta, ela desce reta da cintura até o tornozelo. E tem os bolsos '
                       'na frente, olha, dois bolsos, bem no lugar, dá pra apoiar a mão.',
                       'Agora vem a parte que eu mais queria te falar.'),
                abertura='retoma a pose do último quadro e leva a mão ao tecido, tocando a lavagem clara, sem dar '
                         'passo nem recomeçar',
                meio='abre a mão sobre a perna mostrando o azul leve, desce a mão pela lateral da perna até o '
                     'tornozelo marcando a modelagem reta e, por fim, apoia a mão em um dos bolsos da frente',
                fim='termina de frente para o espelho, com a mão livre apoiada no bolso, no meio do gesto, sem '
                    'apontar e sem pose de fechamento; a fala segue até o último segundo',
                ultimo_quadro='de frente, celular no peito, mão livre apoiada no bolso, falando, sem pose final',
                tela='O 2º e o 3º motivo',
                amarra='frase "a parte que eu mais queria te falar" + mão no bolso',
            ),
            dict(
                papel='Projeção de uso + fechamento (CTA)',
                falas=('É que cintura alta, lavagem clara e perna reta juntas resolvem muito look.',
                       'Eu já me imagino com ela no trabalho, no café com as amigas, no fim de semana com tênis '
                       'branco. É daquelas peças que dá vontade de usar a semana inteira.',
                       'Corre pro carrinho laranja e garante a tua.'),
                abertura='retoma a pose do último quadro e começa a gesticular com a mão livre enquanto fala',
                meio='passa a mão pela cintura e depois pela perna, gesticulando como quem conversa com uma amiga',
                fim=None,  # o clipe 3 mantém o fechamento padrão do app (aponta UMA vez para baixo)
                ultimo_quadro='',
                tela='Qual é o seu motivo?',
                amarra='',
            ),
        ],
    ),
    'B-questionada': dict(
        titulo='"Calça jeans não te valoriza?" e a resposta',
        capa='Calça jeans não te valoriza?',
        clipes=[
            dict(
                papel='A pergunta: os 3 motivos de quem duvida',
                falas=('Sabe o que dizem por aí de calça jeans? Que ela não te valoriza.',
                       'Porque é baixa demais, porque a cor pesa, porque a perna é larga. Pode ser que você pense '
                       'assim também. Mas eu vou desmontar um por um, olha comigo.',
                       'Começando pela cintura, presta atenção aqui no que eu vou te mostrar.'),
                abertura='dá um passo até o espelho com sorriso confiante e cruza o olhar com a tela, como quem '
                         'faz uma pergunta',
                meio='ergue a mão livre enumerando com os dedos os motivos (baixa demais, cor que pesa, perna '
                     'larga) e depois volta a mão para a cintura',
                fim='termina de frente para o espelho, com a mão livre apontando para a cintura, no meio do gesto, '
                    'sem pose de fechamento; a fala segue até o último segundo',
                ultimo_quadro='de frente, celular no peito, mão livre apontando a cintura, falando, sem pose final',
                tela='Calça jeans não te valoriza?',
                amarra='"Começando pela cintura..." + mão apontando a cintura',
            ),
            dict(
                papel='A resposta: desmonta cada motivo com um fato',
                falas=('Baixa demais? Olha a cintura alta, ela termina aqui em cima, no lugar certo.',
                       'Segundo, a cor que pesa? É lavagem clara, um azul leve, olha só. Terceiro, perna larga? '
                       'Ela desce reta da cintura ao tornozelo, e tem bolsos na frente.',
                       'Agora me responde com sinceridade: ainda sobrou algum motivo pra duvidar?'),
                abertura='retoma a pose do último quadro e passa a mão sobre a cintura alta, mostrando onde '
                         'ela termina',
                meio='toca a calça mostrando a lavagem clara, desce a mão pela perna até o tornozelo marcando a '
                     'perna reta e apoia a mão em um dos bolsos da frente',
                fim='termina de frente para o espelho, com a palma da mão livre aberta para cima, como quem '
                    'pergunta, no meio do gesto, sem apontar e sem pose de fechamento; a fala segue até o último '
                    'segundo',
                ultimo_quadro='de frente, celular no peito, palma da mão livre aberta para cima (pergunta), falando, '
                              'sem pose final',
                tela='Desmontando cada motivo',
                amarra='pergunta aberta ("ainda sobrou algum motivo?") + palma aberta',
            ),
            dict(
                papel='A resposta final + fechamento (CTA)',
                falas=('Pois é. No fundo, a pergunta nunca foi se calça jeans valoriza ou não.',
                       'Foi qual calça. Eu já me imagino com ela no trabalho, no café com as amigas e no fim de '
                       'semana. Cintura alta, lavagem clara, perna reta: se faltava motivo, é esse.',
                       'Corre pro carrinho laranja e garante a tua.'),
                abertura='retoma a pose do último quadro e baixa a mão sorrindo, como quem dá a resposta',
                meio='passa a mão pela cintura e pela perna enquanto fala dos looks, gesticulando como quem '
                     'conversa com uma amiga',
                fim=None,
                ultimo_quadro='',
                tela='A pergunta é qual calça',
                amarra='',
            ),
        ],
    ),
}

CONTINUIDADE = ('CONTINUIDADE: clipe {n} de {total} da MESMA gravação: mesma modelo, mesmo espelho, mesma roupa e '
                'mesma luz do clipe anterior, não uma cena nova. Abre retomando este quadro: {quadro}. ')


def sub1(padrao, novo, texto, flags=0):
    """Troca exatamente uma ocorrência; se o gerador mudar e o padrão sumir, o script falha em voz alta."""
    resultado, n = re.subn(padrao, novo if callable(novo) else (lambda _m: novo), texto, count=1, flags=flags)
    assert n == 1, f'padrão não encontrado: {padrao[:60]}'
    return resultado


def prompt_completo(n, total, clipe, quadro_anterior):
    falas = clipe['falas']
    pack = generate(CAMPANHA, script=dict(hook=falas[0], development=falas[1], cta=falas[2]))
    texto = pack['video']
    final = n == total
    # PROVA VISUAL do app dá um gesto fixo; aqui a coreografia do clipe já cobre os fatos.
    texto = sub1(r'PROVA VISUAL — [^\n]*\n', '', texto)
    # Ações e encerramento do clipe (o clipe final mantém o gesto de carrinho do app).
    # O gerador ajusta os tempos da shot list ao tamanho da fala (4–10 s, 10–15 s...): captura o início.
    ini = re.search(r'ENCERRAMENTO \((\d+)–15s\)', texto).group(1)
    if final:
        texto = sub1(r'AÇÕES \(escolha 2 a 3[^)]*\): .*?ENCERRAMENTO \(\d+–15s\):',
                     f'AÇÕES (na ordem, emendadas, sem parar nem posar): {clipe["abertura"]}; {clipe["meio"]}. '
                     f'ENCERRAMENTO ({ini}–15s):', texto, re.S)
    else:
        texto = sub1(r'AÇÕES \(escolha 2 a 3[^)]*\): .*? EXPRESSÃO:',
                     f'AÇÕES (na ordem, emendadas, sem parar nem posar): {clipe["abertura"]}; {clipe["meio"]}. '
                     f'ENCERRAMENTO ({ini}–15s): {clipe["fim"]}. EXPRESSÃO:', texto, re.S)
        texto = sub1(r'EXPRESSÃO: encanto → orgulho → convite sorridente\.',
                     'EXPRESSÃO: encanto → curiosidade (sem convite de compra).', texto)
    # Linhas da shot list.
    rotulo = 'HOOK' if n == 1 else 'CONTINUAÇÃO (não é um hook novo: não recomeçar, não reapresentar a peça)'
    # A descrição completa da retomada já está em AÇÕES e em CONTINUIDADE: aqui só a referência curta.
    abre_shot = clipe['abertura'] if n == 1 else 'retoma o gesto do último quadro, sem recomeçar'
    texto = sub1(r'0–(\d+)s HOOK: [^\n]*?Fala \(PT-BR\):',
                 lambda m: f'0–{m.group(1)}s {rotulo}: olhar na tela do celular, {abre_shot}. '
                           'Fala (PT-BR):', texto)
    if not final:
        texto = sub1(r'(\d+)–15s CTA: [^\n]*?Fala \(PT-BR\):',
                     lambda m: f'{m.group(1)}–15s FIM DO TRECHO (a venda NÃO fecha aqui): sem apontar para baixo e '
                               'sem pose de fechamento; segue o gesto e a fala. Fala (PT-BR):', texto)
    # Primeiro quadro: o clipe 1 usa a imagem aprovada; os seguintes, o último quadro do anterior.
    if n > 1:
        texto = sub1(r'ANEXE a IMAGEM APROVADA da cor [^.]*\.',
                     f'ANEXE o ÚLTIMO QUADRO do clipe {n - 1} como primeiro quadro e referência contínua. '
                     + CONTINUIDADE.format(n=n, total=total, quadro=quadro_anterior), texto)
        # A referência de ambiente agora é o quadro anexado, não a foto de referência da modelo.
        texto = sub1(r'o mesmo ambiente mostrado na foto de referência da modelo',
                     'o mesmo ambiente mostrado no último quadro anexado', texto)
    # O Grok corta em 4000 caracteres sem avisar. Cortes de baixa prioridade, um de cada vez, só se passar:
    # nada de identidade, mãos, cenário, falas nem da lista do que não inventar.
    for padrao in (r' Notas adicionais do operador \(não são falas\): [^.]*\. ',
                   r' Estilo visual: natural e realista\.',
                   r' Ângulo de venda \(contexto, não criar atributos\): [^.]*\.',
                   r' Com material confirmado, preservar textura e brilho\.'):
        if len(texto) <= 3940:
            break
        texto = re.sub(padrao, ' ', texto, count=1)
    return texto, pack


def guia_compacto(n, total, clipe, quadro_anterior):
    falas = clipe['falas']
    pack = dict(hook=falas[0], development=falas[1], cta=falas[2])
    texto = build_compact_video_prompt(CAMPANHA, pack, CAMPANHA['color'])
    final = n == total
    acao = f'ela {clipe["abertura"]}, e, sem parar, {clipe["meio"]}'
    if final:
        acao += ('; no final, de frente para o espelho, a mão livre aponta uma vez para baixo com o indicador, '
                 'sorrindo')
    else:
        acao += f'; {clipe["fim"]}'
    texto = sub1(r'(?m)^Ação contínua, sem pausas:.*$',
                 f'Ação contínua, sem pausas: {acao}. Cada gesto começa enquanto o anterior termina: nada de parar, '
                 'posar ou recomeçar entre uma ação e outra.', texto)
    if not final:
        texto = sub1(r'(?m)^Expressão: .*$', 'Expressão: encanto → curiosidade (sem convite de compra).', texto)
    if n > 1:
        texto = sub1(r'(?m)^A imagem anexada é o primeiro quadro: ',
                     CONTINUIDADE.format(n=n, total=total, quadro=quadro_anterior)
                     + 'A imagem anexada é o último quadro do clipe anterior, agora o primeiro quadro: ', texto)
    return texto


def prompt_extend(n, total, clipe):
    falas = ' '.join(falas_do(clipe))
    final = n == total
    fim = ('no final, de frente para o espelho, a mão livre aponta uma vez para baixo com o indicador, sorrindo'
           if final else clipe['fim'])
    return (
        'Continuação do mesmo take, já em movimento: mesma pessoa, mesma roupa, mesmo espelho e mesma luz; segue o '
        'último quadro sem pausa, o celular sempre na mão dela, na altura do peito, sem cobrir o rosto.\n'
        f'Ela {clipe["abertura"]}, e, sem parar, {clipe["meio"]}. Ela emenda a fala no mesmo tom, como quem conta uma '
        f'descoberta para uma amiga: "{falas}"\n'
        f'{fim[0].upper() + fim[1:]}.'
        + ('' if final else ' Termina em movimento, sem parar no último quadro.')
        + '\nFala: espontânea, voz feminina em português do Brasil, lábios sincronizados, só o que está entre aspas; '
          'a fala ocupa os 15 segundos até o fim, sem silêncio; som ambiente baixo, sem música. Sem texto na tela.'
    )


def falas_do(clipe):
    return [f.rstrip() for f in clipe['falas']]


def grava(pasta, nome, texto):
    pasta.mkdir(parents=True, exist_ok=True)
    (pasta / nome).write_text(texto.strip() + '\n', encoding='utf-8')


def main():
    resumo = []
    for arco, dados in ARCOS.items():
        total = len(dados['clipes'])
        linhas_roteiro = [f'# Arco {arco}: {dados["titulo"]}', '',
                          f'Capa (CapCut): "{dados["capa"]}"', '',
                          '| Clipe | Papel | Palavras | Texto na tela (CapCut) | Amarra para o próximo |',
                          '|---|---|---|---|---|']
        falas_md = []
        for i, clipe in enumerate(dados['clipes'], 1):
            quadro_ant = dados['clipes'][i - 2]['ultimo_quadro'] if i > 1 else ''
            pasta = PASTA / 'sequencias' / arco / f'clipe-{i}'
            falas = falas_do(clipe)
            palavras = sum(_count_words(f) for f in falas)
            # Mesma régua de honestidade do app (termos de desempenho, urgência, direção de cena falada).
            problemas = audit(dict(hook=falas[0], development=falas[1], cta=falas[2]), CAMPANHA,
                              require_caption=False, strict_style=False)
            if i < total:  # o CTA do app só vale no último clipe: nos outros não pode haver convite de compra
                assert not re.search(r'carrinho|corre|garante', ' '.join(falas), re.I), (arco, i, 'CTA fora do fim')
            completo, _ = prompt_completo(i, total, clipe, quadro_ant)
            guia = guia_compacto(i, total, clipe, quadro_ant)
            assert len(completo) <= 3940, (arco, i, len(completo))
            grava(pasta, '1-prompt-completo.txt', completo)
            grava(pasta, '2-guia-grok.txt', guia)
            if i > 1:
                grava(pasta, '3-extend-video.txt', prompt_extend(i, total, clipe))
            texto_falas = (f'CLIPE {i}/{total}: {clipe["papel"]}\n\n0–4s : {falas[0]}\n4–12s: {falas[1]}\n'
                           f'12–15s: {falas[2]}\n\nPalavras: {palavras}\nTexto na tela (CapCut, não vai no vídeo): '
                           f'{clipe["tela"]}\nÚltimo quadro esperado: {clipe["ultimo_quadro"] or "(final da venda)"}\n'
                           f'Auditoria do app: {"ok" if not problemas else problemas}')
            grava(pasta, '4-falas.txt', texto_falas)
            linhas_roteiro.append(f'| {i} | {clipe["papel"]} | {palavras} | {clipe["tela"]} | {clipe["amarra"] or "fim da venda (CTA)"} |')
            falas_md.append(f'**Clipe {i}** ({palavras} palavras)\n> {" ".join(falas)}')
            resumo.append(dict(arco=arco, clipe=i, palavras=palavras, chars_completo=len(completo),
                               chars_guia=len(guia), auditoria=problemas))
        grava(PASTA / 'sequencias' / arco, 'ROTEIRO.md', '\n'.join(linhas_roteiro) + '\n\n' + '\n\n'.join(falas_md))
    (PASTA / 'sequencia.json').write_text(json.dumps(resumo, ensure_ascii=False, indent=1), encoding='utf-8')
    for r in resumo:
        print(f"{r['arco']:14} clipe {r['clipe']}  palavras={r['palavras']:3}  completo={r['chars_completo']:4}  "
              f"guia={r['chars_guia']:4}  auditoria={'ok' if not r['auditoria'] else r['auditoria']}")


if __name__ == '__main__':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    main()
