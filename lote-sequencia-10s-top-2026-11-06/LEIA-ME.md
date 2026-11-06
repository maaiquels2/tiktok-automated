# Top tomara que caia: 4 cores, 3 clipes de 10 s cada (vídeo de 30 s)

Para o Flow na versão de 10 s em 720p. Os 3 clipes de cada cor formam UM vídeo de venda: o 1 e o 2 não fecham a venda; só o 3 convida para o link. Cada cor tem uma abertura de suspense e FOMO diferente (regra do estúdio: abre uma lacuna que o próprio vídeo fecha, sem estoque, prazo nem preço inventados).

## 4 passos (para cada cor)
1. **Imagem-base (uma vez por cor).** Cole `0-imagem-base-<cor>.txt` no gerador de imagem e anexe a foto de referência da Micaela. Resultado: ela no espelho, de top da cor, mão livre na cintura. As fotos `0-referencia-top-*.jpg` são só para conferir o top (dobra em cima, franzido na lateral).
2. **Clipe 1.** No Flow, anexe a imagem-base, cole `sequencias/<Cor>/clipe-1/1-prompt-completo.txt` e gere em 10 s.
3. **Clipes 2 e 3.** Igual, com a MESMA imagem-base, colando o prompt de `clipe-2` e depois o de `clipe-3`. (Se o completo pesar, use o `2-prompt-curto.txt` da mesma pasta.)
4. **CapCut.** Junte os 3 na ordem. O texto de tela de cada clipe está em `4-falas.txt`.

## Falas por cor (lacuna aberta no 1, mantida no 2, fechada no 3)

**Amarelo**
1. "Três motivos pra esse top, e o último quase ninguém repara. O primeiro é o tecido duplo, repara na dobra e nas duas camadas, é um detalhe que faz diferença. O segundo é o meu favorito, já te mostro."
2. "O segundo é o franzido na lateral, olha só como ele desce. A modelagem sem alças deixa o ombro livre e combina com jeans, com short, com saia. O terceiro, quase todo mundo passa batido."
3. "O último, que ninguém repara: tamanho único, veste do 34 ao 42. Dá pra usar no dia a dia, no passeio e na festa com a mesma peça. Corre no link aqui embaixo e garante o teu."

**Azul**
1. "Você pode estar perdendo esse top sem nem saber, fica até o fim. O primeiro motivo é o tecido duplo, olha a dobra e as duas camadas, esse detalhe faz diferença. O segundo vem logo em seguida, presta atenção."
2. "O segundo é o franzido na lateral, olha como ele desce. Sem alças, deixa o ombro livre e combina com jeans, com short e com saia. E o terceiro você não pode perder."
3. "O último: é tamanho único e veste do 34 ao 42. Serve pro dia a dia, pro passeio e pra festa, é a mesma peça pra tudo. Toca no link aqui embaixo e escolhe o teu."

**Preto**
1. "Não deixa passar: esse top tem um motivo que ninguém conta. Primeiro, o tecido duplo. Repara na dobra e nas duas camadas, faz muita diferença no detalhe. Já já eu te conto o segundo motivo."
2. "O segundo é o franzido na lateral, olha só como desce. E sem alças o ombro fica livre, e ele combina com jeans, short ou saia. O último é o que quase ninguém conta."
3. "Pronto, o segredo: tamanho único, veste do 34 ao 42. Usa de dia, no passeio, no encontro e na festa, sempre com a mesma peça. Abre o link aqui embaixo e garante o teu."

**Branco**
1. "Fica até o fim: o terceiro motivo eu quase deixei passar. O primeiro é o tecido duplo, olha a dobra e as duas camadas, um detalhe que conta. O segundo motivo vem agora, olha só."
2. "O segundo é o franzido na lateral, repara como ele cai. A modelagem sem alças deixa o ombro livre e combina com jeans, short, saia. Agora vem o terceiro, o que eu quase esqueci."
3. "O terceiro: tamanho único, veste do 34 ao 42. Dá pra usar no dia a dia, num passeio e numa festa, com a mesma peça. Vai no link aqui embaixo e pega o teu."

Cada clipe: 0–3 s gancho, 3–8 s meio, 8–10 s fechamento; 33 a 39 palavras.

## O que mudou depois dos testes no Flow
- O clipe 1 foi recusado (política de conteúdo sexual). Agora o prompt não tem a palavra "bojo" (nem na fala, nem nos fatos), o gesto fica na lateral da cintura e o clima diz "casual, roupa de passeio do dia a dia".
- O clipe 3 desenhou o ícone do TikTok. Agora nenhum prompt cita TikTok, há uma proibição de logotipo de aplicativo e o convite é "link aqui embaixo" (sem "carrinho laranja").
- Só entram fatos do anúncio (sem alças, tecido duplo, tamanho único 34 ao 42, combina com jeans, short e saia) e o franzido que aparece na foto. Não entram "confortável", "fica no lugar" nem "não escorrega". O "bojo" fica só para a legenda.

## Não testado
Nenhum clipe das cores novas foi gerado. Só as fotos do amarelo e do branco foram enviadas como referência separada; azul e preto aparecem só na tela das opções.
