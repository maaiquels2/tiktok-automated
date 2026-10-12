# Avaliação da sequência

Marque ✔ ou ✖ depois de ver cada **emenda** (o corte entre dois clipes) e cada vídeo final.

| Critério | O que olhar |
|---|---|
| **I** identidade | mesmo rosto, cabelo e corpo antes e depois do corte |
| **R** roupa | mesma calça (cor, modelagem, bolsos) e mesma blusa |
| **E** cenário | mesmo espelho, ambiente e luz |
| **M** gesto | a mão está onde parou e o gesto continua, sem reiniciar |
| **V** voz | mesmo timbre e energia, sem parecer outra pessoa |
| **F** fala | a fala ocupa os 15 s, sem silêncio no fim, e o clipe seguinte não repete a abertura |
| **N** conteúdo | cada clipe traz um fato novo que o anterior não tinha |
| **C** CTA | só o clipe 3 pede a compra |
| **S** salto | a emenda passa despercebida com corte seco, sem trepidar |
| **U** usável | publicaria o vídeo montado como está (sim / com ajuste / não) |

## Emendas do arco A (Motivos)

| Emenda | Técnica | I | R | E | M | V | F | S | Observação |
|---|---|---|---|---|---|---|---|---|---|
| 1 → 2 | imagem (último quadro) | | | | | | | | |
| 1 → 2 | Extend Video | | | | | | | | |
| 2 → 3 | ______ (vencedora) | | | | | | | | |

## Emendas do arco B (Questionada)

| Emenda | Técnica | I | R | E | M | V | F | S | Observação |
|---|---|---|---|---|---|---|---|---|---|
| 1 → 2 | ______ | | | | | | | | |
| 2 → 3 | ______ | | | | | | | | |

## Vídeo final montado

| Arco | N | C | U | Duração | Observação |
|---|---|---|---|---|---|
| A · Motivos | | | | | |
| B · Questionada | | | | | |

## Como decidir

| Se... | Então |
|---|---|
| A técnica **imagem** ganha (mais ✔ em I, R, E, M) | Ela vira o padrão da funcionalidade; o app passa a gerar o prompt de cada clipe pensado para o último quadro. |
| **Extend Video** ganha | A funcionalidade usa o prompt curto de continuação; o app entrega o clipe 1 completo e os outros curtos. |
| Empate | Oferecer as duas técnicas. |
| Falha em **I, R ou E** nas duas técnicas | O Grok não segura a modelo entre gerações: tentar o mesmo teste com 2 clipes em vez de 3. |
| Falha em **M ou S** (emenda visível) com ✔ em I, R e E | A identidade está boa e o problema é o corte: testar a "frase cortada" no lugar da pergunta aberta, ou cortar mais quadros. |
| Falha em **F** (silêncio ou fala repetida) | As falas ficaram curtas ou longas para os 15 s: ajustar a contagem de palavras do clipe. |
| O arco **A** dá **N ✔** e o **B** dá **N ✖** (ou o contrário) | Esse arco entra na funcionalidade; o outro só vira modelo de roteiro. |
| Os dois arcos ficam bons | Oferecer os dois como formatos de sequência e testar o terceiro arco (vida que muda). |
