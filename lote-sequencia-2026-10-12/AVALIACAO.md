# Avaliação da sequência

Marque ✔ ou ✖ depois de ver cada **emenda** (o corte entre dois clipes) e cada vídeo final.

| Critério | O que olhar |
|---|---|
| **Q** partida | `confere_emenda.py` diz OK: o clipe seguinte partiu do último quadro (não da imagem-base) |
| **I** identidade | mesmo rosto, cabelo e corpo antes e depois do corte |
| **R** roupa | mesma calça (cor, modelagem, bolsos) e mesma blusa |
| **E** cenário | mesmo espelho, ambiente e luz |
| **M** gesto | a mão está onde parou e o gesto continua, sem reiniciar |
| **V** voz | mesmo timbre e energia, sem parecer outra pessoa |
| **F** fala | a fala ocupa os 15 s, sem silêncio no fim, e o clipe seguinte não repete a abertura |
| **N** conteúdo | cada clipe traz um fato novo que o anterior não tinha |
| **C** CTA | só o último clipe pede a compra |
| **S** salto | a emenda passa despercebida com corte seco, sem trepidar |
| **U** usável | publicaria o vídeo montado como está (sim / com ajuste / não) |

## Arcos de 2 clipes (uma só emenda): começar por aqui

| Arco | Técnica | Q | I | R | E | M | V | F | S | Observação |
|---|---|---|---|---|---|---|---|---|---|---|
| A-motivos-2clipes | imagem (último quadro) | | | | | | | | | |
| A-motivos-2clipes | Extend Video | | | | | | | | | |
| B-questionada-2clipes | ______ (vencedora) | | | | | | | | | |

## Arcos de 3 clipes (duas emendas)

| Arco | Emenda | Técnica | Q | I | R | E | M | V | F | S | Observação |
|---|---|---|---|---|---|---|---|---|---|---|---|
| A-motivos | 1 → 2 | ______ | | | | | | | | | |
| A-motivos | 2 → 3 | ______ | | | | | | | | | |
| B-questionada | 1 → 2 | ______ | | | | | | | | | |
| B-questionada | 2 → 3 | ______ | | | | | | | | | |

## Vídeo final montado

| Arco | Clipes | N | C | U | Duração | Observação |
|---|---|---|---|---|---|---|
| A-motivos-2clipes | 2 | | | | | |
| B-questionada-2clipes | 2 | | | | | |
| A-motivos | 3 | | | | | |
| B-questionada | 3 | | | | | |

## Como decidir

| Se... | Então |
|---|---|
| **Q ✖** (o clipe 2 partiu da imagem-base) | O teste da emenda não valeu: refaça o clipe 2 com o último quadro do clipe 1 como primeiro quadro. |
| A técnica **imagem** ganha (mais ✔ em I, R, E, M) | Ela vira o padrão da funcionalidade; o app gera o prompt de cada clipe pensado para o último quadro. |
| **Extend Video** ganha | A funcionalidade usa o prompt curto de continuação; o app entrega o clipe 1 completo e os outros curtos. |
| Empate | Oferecer as duas técnicas. |
| Falha em **I, R ou E** nas duas técnicas | O Grok não segura a modelo entre gerações: manter só o arco de 2 clipes. |
| Falha em **M ou S** (emenda visível) com ✔ em I, R e E | A identidade está boa e o problema é o corte: testar a "frase cortada" no lugar da pergunta aberta, ou cortar mais quadros. |
| Falha em **F** (silêncio ou fala repetida) | As falas ficaram curtas ou longas para os 15 s: ajustar a contagem de palavras do clipe. |
| O arco de **2** clipes dá **U ✔** e o de **3** também | Oferecer os dois no app; o de 3 só quando houver pelo menos duas provas distintas. |
| O arco **A** dá **N ✔** e o **B** dá **N ✖** (ou o contrário) | Esse arco entra na funcionalidade; o outro só vira modelo de roteiro. |
| Os dois arcos ficam bons | Oferecer os dois como formatos de sequência e testar o terceiro arco (vida que muda). |
