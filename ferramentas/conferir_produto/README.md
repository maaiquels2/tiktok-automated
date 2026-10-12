# Conferir se a peça continua a mesma no vídeo

Ferramenta **local** (não faz parte do app nem roda na Vercel) que compara os quadros de um vídeo gerado com a imagem
aprovada e avisa quando a **peça perdeu detalhes** ao longo do vídeo (o bordado some, a estampa muda, a peça vira outra).

Usa o DINOv2 (Meta, Apache 2.0, modelo `facebook/dinov2-small`, ~90 MB, baixado na primeira execução).

## Como funciona
1. Extrai 4 quadros por segundo com o `ffmpeg`.
2. Pega, na imagem aprovada (ou no primeiro quadro), os pedaços ("patches") dentro de uma **caixa** que cobre a peça.
3. Para cada quadro, vê o quanto cada pedaço da peça ainda **tem um par parecido em algum lugar do quadro**. Pose, zoom e
   posição não pesam. Por segundo, usa o **pior 20%** dos pedaços.
4. Alerta se a cobertura ficou abaixo de **65** por **4 s ou mais**, ou se a média dos **últimos 3 s** ficou abaixo de **70**.

## O que ela pega e o que não pega
| Pega | **Não** pega |
|---|---|
| Bordado, pérola ou estampa que some | Coisa **nova** que aparece (um laço, um nó, uma tira) |
| A peça virar outra no meio do vídeo | Pequenas mudanças de forma sem perda de detalhe |

Giros de lado, close-ups e a mão na frente derrubam a cobertura por 1 a 3 s **mesmo com a peça intacta**; por isso a regra
usa persistência e o estado final, não um segundo isolado. Em "3 jeitos de usar" a peça é coberta de propósito (saia por
cima, camisa), então o alerta da região da calcinha pode ser esperado.

## Calibração (12/10/2026)
Só 9 vídeos, então é uma **triagem**, não um veredito:

| Vídeo | Resultado |
|---|---|
| 2 vídeos bons de biquíni bordado (com close e giro de lado) | sem alerta |
| 3 vídeos de calça jeans aprovados (controle) | sem alerta (cobertura mínima 80) |
| Biquíni rosa, "Com fala": bordado some a partir de ~6 s | **alerta** |
| Biquíni rosa, "3 jeitos": bordado some a partir de ~4 s | **alerta** |
| Biquíni preto, teste de prova: laço novo no peito | sem alerta (limite conhecido) |
| Biquíni marrom: laços novos na calcinha | sem alerta (limite conhecido) |

Uma medida de "algo novo ao redor da peça" também foi testada e **não separa** os vídeos bons dos ruins (os bons
também caem em close e giro), então não foi incluída. Para laço acrescentado, o caminho seria um modelo de visão
comparando quadros escolhidos com a imagem aprovada.

## Instalação (uma vez, num ambiente separado)
Não instale isto no `.venv` do projeto nem coloque no `requirements.txt` da raiz: a Vercel instala esse arquivo e o
PyTorch é pesado demais para a função.

```powershell
python -m venv ferramentas\conferir_produto\.venv-conferir
ferramentas\conferir_produto\.venv-conferir\Scripts\python.exe -m pip install torch --index-url https://download.pytorch.org/whl/cpu
ferramentas\conferir_produto\.venv-conferir\Scripts\python.exe -m pip install -r ferramentas\conferir_produto\requisitos-conferir.txt
winget install Gyan.FFmpeg      # se ainda não tiver o ffmpeg
```

## Uso
```powershell
$py = "ferramentas\conferir_produto\.venv-conferir\Scripts\python.exe"
# biquíni: topo e calcinha, com a imagem aprovada como referência
& $py ferramentas\conferir_produto\conferir_produto.py media\video.mp4 --ref media\imagem_aprovada.jpg --regiao topo --regiao calcinha --saida media\conferencia
# peça em outro enquadramento: caixa própria (frações da imagem: x0,y0,x1,y1) e confira o desenho em referencia_com_caixas.png
& $py ferramentas\conferir_produto\conferir_produto.py media\video.mp4 --ref media\imagem.jpg --caixa 0.2,0.5,0.8,0.92 --saida media\conferencia
```
Regiões prontas (`--regiao`): `topo`, `calcinha`, `tronco`, `pernas`, ajustadas ao plano americano dos vídeos do app.
`--falhar` faz o comando sair com código 2 quando houver alerta (útil em scripts).
