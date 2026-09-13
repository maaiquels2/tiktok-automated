# Fábrica TikTok — Verificação completa e pontos de melhoria

**Data:** 2026-09-12
**Base analisada:** commit `505da07` (estado atual, já no GitHub)
**O que foi lido:** `services/prompts.py` (1.061 linhas, na íntegra), `app.py` (fluxo de estados, transições, gravação de dados), `frontend/src/App.jsx`, `components.jsx`, `styles.css`, testes e banco de dados real.

Cada item traz **o que é**, **por que importa** e **como corrigir**. A ordem dentro de cada bloco é por impacto.

---

## Status — o que já foi feito

Revisão executada em 12/09/2026. A suíte passou de 51 para 61 testes, todos verdes, e as mudanças de interface foram conferidas com o app rodando.

| Item | Estado |
|---|---|
| A1 "legging" fixa no prompt de imagem | ✅ feito — o substantivo vem do produto |
| A2 pontuação dupla nas falas | ✅ feito |
| A3 `checklist` sobrescrito | ✅ feito — gravações mesclam e a transição preserva métricas, insights e cores publicadas |
| A4 `#ModaFeminina` em qualquer produto | ✅ feito |
| A5 prompt de imagem com dois modos | ✅ feito — 1ª cor cria a base, as demais editam |
| A6 oito testes falhando | ✅ feito — sete alinhados ao comportamento atual, um era bug de teste |
| B1 hooks todos iguais | ✅ feito — famílias por motor |
| B2 cor desperdiçando palavras do hook | ✅ feito |
| B3 desenvolvimento sem estrutura | ✅ feito — prova → objeção → posse |
| B4 CTA único | ✅ feito — quatro famílias, escolhidas pelo motor |
| B5 orçamento de palavras | ✅ feito — por trecho; ao estourar cai a posse, não a prova |
| B6 briefing sem objeção e oferta | ✅ feito — dois campos novos |
| B7 gerador só sabia falar de roupa | ✅ feito — camada de família de produto |
| B8 fala declarada em dois beats | ✅ feito |
| B9 código morto | ✅ feito |
| C1 sem backup automático | ✅ feito — cópia diária, 10 dias de histórico |
| C2 trava `busy` global | ✅ feito — operações longas do Studio não congelam mais o app |
| C3 painel remontado a cada save | ✅ parcial — a posição do scroll é preservada; a remontagem foi mantida de propósito (ver abaixo) |
| C4 rede local sem autenticação | ✅ feito — PIN de 4 dígitos |
| C5 multi-cor pode não estar em uso | ⏳ depende de você — a tabela continua vazia |
| C6 dois caminhos publicam | ✅ mitigado — o risco era perda de dados, resolvido no A3; a unificação em si continua pendente |
| D1 trabalho na coluna mais estreita | ❌ **achado incorreto, retirado** (ver abaixo) |
| D2 sem sistema de design | ✅ feito — 226 tokens por papel |
| D3 oito breakpoints | ✅ parcial — 21 blocos `@media` viraram 10, um por largura; a redução de 8 larguras para 3 continua pendente |
| D4 CSS em duas linhas | ✅ feito — formatado, 4.500 linhas legíveis |
| D5 sem modo escuro / reduced-motion | ✅ feito |
| D6 foco de teclado inconsistente | ✅ feito |
| D7 resíduo do React Flow | ✅ feito — dependência, import e CSS removidos |
| D8 contador de palavras pouco útil | ✅ feito — por trecho, com faixa alvo e cor |

### Correção: o item D1 estava errado

O relatório original dizia que o painel de trabalho ficava espremido em 350 px enquanto o stepper ocupava o centro largo. Isso foi lido do CSS base (`.workspace`), mas a tela de produção usa `.produce-workspace`, que sobrescreve esse grid.

Com o app aberto em 1600 px, a medição real é: fila de campanhas 210 px, painel do stepper 1375 px e **painel de trabalho 1375 px** — ele ocupa a largura inteira, numa segunda linha. A hierarquia já estava correta; não havia o que inverter. O que de fato existia ali era um defeito pequeno de layout — o rótulo `#0021 · Micaela · Grok · 15s` colado no título da campanha na mesma linha —, esse sim corrigido.

Fica o registro do método: o achado nasceu de ler o CSS sem abrir a tela. A verificação visual desmentiu.

### Sobre o C3

A remontagem do painel a cada gravação foi **mantida**. Ela é uma escolha defensiva correta: garante que nenhum campo mostre texto desatualizado depois de um refresh do roteiro. Trocá-la por sincronização manual exigiria acertar seis pontos de estado diferentes (rascunhos de texto, confirmações da etapa, link de publicação, aba de cor ativa), com risco de exibir conteúdo velho — pior do que o problema. O incômodo real, perder a posição da rolagem, foi resolvido guardando e restaurando o scroll.

---

## Resumo executivo

O projeto está sólido na arquitetura e na disciplina de não inventar atributos de produto — isso é raro e vale preservar. Os problemas se concentram em três lugares:

1. **O texto gerado é honesto, mas não é persuasivo.** Os doze hooks são a mesma frase com o verbo trocado. Nenhum usa dor, escassez ou desejo de posse. É o ponto de maior retorno.
2. **Há um bug de produto que afeta toda campanha que não seja de legging** — a palavra "legging" está fixa no prompt de imagem.
3. **Um único campo do banco (`checklist`) guarda quatro coisas diferentes** e é apagado a cada transição, com risco real de perder registro de publicação e métricas.

E um ponto operacional fora das três categorias, mas o mais grave de todos: **não existe backup automático**. Tudo — campanhas, playbook, identidade, histórico — vive em um arquivo só, fora do Git.

---

## 🔴 Bloco A — Corrigir primeiro (bugs)

### A1. A palavra "legging" está fixa no prompt de imagem
**O que é.** Em `services/prompts.py`, dentro de `generate()`, o prompt de imagem diz literalmente:

> "Altere somente a área ocupada pela **legging**, mantendo todo o restante da imagem visualmente idêntico."
> "INTEGRAÇÃO FOTOGRÁFICA: a **legging** nova deve acompanhar exatamente a anatomia e a pose já existentes…"

**Por que importa.** Isso vale para *qualquer* produto. Numa campanha de vestido, maiô, biquíni ou conjunto, você está mandando a IA editar "a legging" de uma foto que não tem legging nenhuma. O modelo ou ignora a instrução (perdendo a trava de edição localizada, que é justamente o que garante a consistência) ou tenta obedecer e erra a peça. É o bug de maior alcance do projeto.

**Como corrigir.** A função `_script_variation` já detecta o substantivo da peça (`piece`: legging, vestido, conjunto, camiseta, blusa, calça, saia, short, top, maiô, biquíni). Extrair essa detecção para uma função própria e usá-la nas duas frases, com "a peça" como padrão quando não reconhecer.

---

### A2. Pontuação dupla nas falas (`movimento?. Olha…`)
**O que é.** Quando o roteiro é regerado ou editado, a fala passa por `_spoken_line()`, que quebra o texto em frases e junta de volta com `". "`. Uma frase que termina em `?` vira `"...em movimento?. Olha o tecido leve"`.

**Por que importa.** Esse texto entra **dentro do prompt de vídeo**, entre aspas, com a instrução "fale palavra por palavra". O gerador de voz lê a pontuação estranha como pausa errada, e o vídeo sai com cadência artificial logo no hook — os 2 segundos mais importantes.

**Como corrigir.** Em `_spoken_line()`, ao juntar as frases, não acrescentar ponto depois de `?` ou `!`. O código já faz essa limpeza em `_script_variation` (`re.sub(r'([!?])\.', r'\1', ...)`), mas ela não é aplicada no caminho de edição. Aplicar a mesma limpeza na saída de `_spoken_line`.

---

### A3. O campo `checklist` é usado para quatro coisas e apagado a cada transição
**O que é.** A coluna `checklist` da tabela `campaigns` guarda, ao mesmo tempo:

- as confirmações de revisão humana da transição;
- `slots` — o registro de qual cor já foi publicada e com qual link;
- `performance` — as métricas que você digita por cor;
- `insights` — a saída do crítico local;
- `video_soft_warnings` — os avisos de duração/resolução.

E a função `state()` executa, em **toda** transição:

```sql
UPDATE campaigns SET status=?, checklist='{}', published_url='', migration_note='' WHERE id=?
```

Três trechos diferentes gravam nesse campo com regras diferentes: `save_performance` **mescla**, `publish_slot` **mescla e restaura** depois do reset, mas o caminho `transition → published` grava só os cinco booleanos, e o aviso de vídeo (`video_soft_warnings`) sobrescreve o objeto inteiro.

**Por que importa.** Publicar pelo caminho genérico apaga o registro de quais cores foram publicadas e as métricas já coletadas. É perda silenciosa: nada dá erro, o dado simplesmente some. E como o playbook é construído a partir de métricas, você perde matéria-prima do aprendizado.

**Como corrigir.** Duas opções, da mais rápida para a mais correta:
1. *Rápida:* fazer todos os caminhos mesclarem em vez de sobrescrever, e `state()` preservar as chaves `slots`, `performance` e `insights`.
2. *Correta:* separar em colunas ou tabelas próprias — `publish_slots`, `performance`, `insights` —, deixando `checklist` só para as confirmações da transição. Isso elimina a classe inteira de bug.

---

### A4. `#ModaFeminina` entra em qualquer produto
**O que é.** Em `_niche_hashtags`, a lista final é sempre `… + ['TikTokShop', 'Achadinhos', 'ModaFeminina', 'ForYou']`.

**Por que importa.** Um produto unissex, masculino, infantil, de casa ou pet recebe `#ModaFeminina`. Hashtag errada entrega o vídeo para o público errado, e o TikTok usa isso como sinal de classificação — prejudica o alcance em vez de ajudar.

**Como corrigir.** Tornar as três tags de fechamento condicionais ao nicho e ao público do briefing, com um conjunto neutro (`#TikTokShop`, `#Achadinhos`) como padrão.

---

### A5. O prompt de imagem mistura dois modos incompatíveis
**O que é.** O mesmo texto diz, na mesma respiração:

> "Use a imagem anexada de {modelo} como referência visual fixa…" *(criar uma foto nova a partir da referência)*
> "EDIÇÃO LOCALIZADA: trate a imagem aprovada da modelo como a fotografia-base final, não como inspiração para uma nova cena." *(editar uma foto que já existe)*

**Por que importa.** Na **primeira cor** de uma campanha ainda não existe imagem aprovada. Você está pedindo ao modelo para editar uma foto-base que não foi entregue. Instruções contraditórias no mesmo prompt baixam a aderência do modelo a *todas* as instruções, inclusive as de identidade.

**Como corrigir.** Gerar duas variantes do prompt: **cor inicial** (criar a partir da referência da modelo, sem o bloco de edição localizada) e **cores seguintes** (edição localizada a partir da imagem aprovada). O app já sabe quais cores têm imagem aprovada — a informação para decidir já existe.

---

### A6. Oito testes falhando — dois já têm resposta
**O que é.** A suíte tem 51 testes e 8 falham.

Sobre as duas dúvidas que ficaram pendentes, a leitura do código **responde uma delas**: em `app.py`, na aprovação de vídeo, há o comentário explícito *"Duration/resolution are advisory only — do not block approval"* e a lógica grava os desvios em `video_soft_warnings`. Ou seja, **foi intencional** — o teste que espera erro 409 está desatualizado e deve ser atualizado.

Restam desatualizados por causa da reescrita: os dois de `prompts.py` (o desenvolvimento não cita mais o público), o de 7 campos por cor, o do hook dentro do prompt de vídeo (ligado ao item A2) e os dois de perfil do Chrome (`gen-maaiquels`). Continua valendo uma conferência sua: **editar a legenda não volta mais o status para "vídeo aprovado"** — não achei comentário dizendo que foi de propósito.

**Como corrigir.** Atualizar os sete testes desatualizados; decidir o caso da legenda.

---

## 🟠 Bloco B — Qualidade do texto gerado (maior retorno sobre venda)

Este bloco é o que mais afeta o resultado dos vídeos. A skill `roteiro-ugc-15s` que acabamos de salvar é exatamente o material para guiar essas mudanças.

### B1. Os doze hooks são a mesma frase com o verbo trocado
**O que é.** As doze opções de hook em `_script_variation` são:

> "Quer ver essa legging no corpo?" · "Como fica essa peça em movimento?" · "Pensando nessa peça?" · "Você usaria essa peça em Azul?" · "Antes de escolher…" · "O que vale observar…?" · "Quer conferir como veste?" · "Dá para notar…" · "Essa versão mostra…" · "Se você procura…" · "Repara no que muda…" · "Vale observar…"

Todas são **convites a observar**. Nenhuma usa dor ("cansei de legging que desce"), escassez ("o preto sempre some primeiro"), prova social ("me perguntaram onde comprei o dia inteiro") ou descoberta ("achei e não esperava esse bolso").

**Por que importa.** O hook decide o vídeo nos primeiros 2 segundos. "Quer ver essa peça no corpo?" é uma pergunta que o espectador responde com o dedo: não. Um hook que nomeia uma dor que ele tem prende; um que pede permissão para mostrar, não.

**Como corrigir.** Substituir a lista por famílias de hook organizadas por motor (necessidade / escassez / desejo), como está na skill. O gerador escolhe a família pelo nicho e rotaciona entre elas nas variações e nas cores — em vez de rotacionar entre doze sinônimos.

---

### B2. A cor aparece em quase todos os hooks
**O que é.** Os doze hooks, sem exceção, carregam a cor: "na versão {cor}", "em {cor}", "na cor {cor}" ou "essa versão {cor}".

**Por que importa.** Um hook de 4 segundos cabe em ~11 palavras faladas. Gastar duas ou três delas dizendo uma cor que o espectador **está vendo na tela** é desperdício puro. A fala deve dizer o que a imagem não consegue.

**Como corrigir.** Tirar a cor do hook por padrão e deixá-la na legenda e no prompt de imagem (onde ela é indispensável). Manter no hook só quando a cor **for** o argumento ("o preto é o que sempre some primeiro").

---

### B3. O desenvolvimento não tem estrutura — tem sinônimos
**O que é.** As doze variações de desenvolvimento são: "Veja X", "Olha X em movimento", "Aqui aparece X", "Vale notar X", "Observe X com a peça no corpo", "Na prática, repare em X", "Para decidir, veja X"… todas seguidas da mesma frase de benefício.

**Por que importa.** Oito segundos é o espaço para **provar** e **quebrar a objeção** que segura a compra. Hoje o desenvolvimento só aponta para o detalhe outra vez. Quem estava na dúvida continua na dúvida.

**Como corrigir.** Adotar a estrutura de três batidas da skill: **prova** (4–6s) → **objeção quebrada** (6–10s) → **posse** (10–12s). Para a batida do meio o gerador precisa do item B6.

---

### B4. Todos os CTAs dizem a mesma coisa
**O que é.** As 12 opções de CTA são variações de "Toque no produto marcado".

**Por que importa.** O CTA muda de acordo com o motor que conduziu o vídeo. Um vídeo de dor fecha melhor com CTA condicional ("se isso te incomoda, ele tá marcado aqui"); um de desejo, com CTA direto; um com oferta real, com escassez verdadeira. Um CTA único trata todos os vídeos como iguais.

**Como corrigir.** Quatro famílias de CTA (direto, condicional, escassez real, posse), escolhidas pelo motor do hook. Escassez só quando o briefing tiver oferta real — ver B6.

---

### B5. O orçamento de palavras é global e corta a coisa errada
**O que é.** O único controle é: se hook + desenvolvimento + CTA passarem de 45 palavras, o código **descarta frases do desenvolvimento**.

**Por que importa.** O desenvolvimento é onde está a prova — é a última coisa que deveria ser cortada. E como não há teto por trecho, um hook de 15 palavras (acontece: "Pensando nessa legging? Veja de perto o bolso lateral antes de escolher a versão Azul Marinho") consome 5 segundos de um beat de 4, empurrando o vídeo inteiro.

**Como corrigir.** Orçamento por trecho, conforme a skill: hook 10–12 palavras, desenvolvimento 20–24, CTA 7–9 (~2,8 palavras por segundo em português falado). Gerar já dentro do limite em vez de cortar depois.

---

### B6. O briefing não pergunta a objeção nem a oferta
**O que é.** Os campos do briefing são: produto, público, benefício, ângulo, tom, estilo, detalhes, movimentos, cores, nicho.

**Por que importa.** Sem saber **qual é a dúvida que segura a compra** ("será que marca?", "será que serve em mim?", "parece barato?"), o gerador não tem como escrever a batida do meio. E sem saber se existe **oferta real**, ele nunca pode usar escassez com honestidade — por isso hoje ele simplesmente não usa.

**Como corrigir.** Dois campos novos no briefing: **Objeção nº 1** (lista curta com opção livre) e **Oferta real** (texto opcional: prazo, desconto, estoque). Ambos alimentam diretamente o desenvolvimento e o CTA. É a mudança de menor esforço com maior efeito sobre a qualidade do roteiro.

---

### B7. O gerador só sabe falar de roupa
**O que é.** O vocabulário é todo de moda: "peça", "no corpo", "caimento", "veste". A detecção de produto (`piece`) só reconhece 11 peças de vestuário; qualquer outra coisa vira "produto".

**Por que importa.** "Quer ver esse produto no corpo?" para um organizador de gaveta é sem sentido. Se o catálogo do TikTok Shop crescer para casa, beleza ou pet, o gerador não acompanha.

**Como corrigir.** Uma camada de **família de produto** (moda, beleza, casa, gadget, pet, infantil) que escolhe o vocabulário, o motor dominante e o que a câmera precisa provar — a tabela existe pronta na skill `roteiro-ugc-15s`.

---

### B8. O prompt de vídeo declara a fala do desenvolvimento em dois lugares
**O que é.** No shot list:

> `4.0–6.0s PROVA 1: … Iniciar a fala do desenvolvimento, distribuída entre 4 e 12s.`
> `6.0–11.0s PROVA 2: … Fala (PT-BR, somente esta frase…): "{development}"`

**Por que importa.** O modelo recebe duas instruções sobre quando a mesma fala começa. Na prática isso produz repetição da frase ou corte no meio.

**Como corrigir.** Declarar a fala uma vez só, no beat onde ela começa, e deixar o outro beat apenas com direção de câmera.

---

### B9. Código morto que confunde a manutenção
- `_focus()` (linha 32) não é chamada em lugar nenhum — foi substituída por `_focus_parts()`.
- `audience_prefix` é sempre string vazia, e ainda existem duas condições que testam se ela tem conteúdo.
- No conjunto `feminine`, `'legging'` aparece duas vezes.

**Como corrigir.** Remover. São três minutos de trabalho e reduzem o risco de alguém "consertar" a função errada depois.

---

## 🟡 Bloco C — Fluxo e operação

### C1. Não existe backup automático (o item mais grave do documento)
**O que é.** A única cópia em `data/backups/` é `before-v1.db`, de 11/09, criada uma vez por uma migração. O banco atual tem 160 KB com todas as campanhas, a identidade, o playbook e o histórico — e `data/` está corretamente fora do Git, o que significa que **o GitHub não protege nada disso**.

**Por que importa.** Um disco com defeito, um `data/` apagado por engano ou uma corrupção do SQLite levam junto todo o histórico de produção. Não há como reconstruir.

**Como corrigir.** Fazer o `launcher.py` copiar o banco para `data/backups/fabrica-AAAA-MM-DD.db` a cada inicialização, mantendo os últimos 10 dias. São ~15 linhas e resolvem o risco inteiro. Bônus: uma cópia semanal para uma pasta do Dropbox/OneDrive (que já existem nesse PC) protege contra perda do disco.

---

### C2. Uma única trava `busy` congela a interface inteira
**O que é.** Todo botão do app é desabilitado por um mesmo estado `busy`.

**Por que importa.** Coletar métricas do Studio demora dezenas de segundos. Durante esse tempo você não consegue editar um roteiro nem abrir outra campanha. Em uma fábrica de 5 posts por dia, isso é tempo parado.

**Como corrigir.** Trocar por travas por área (uma para a campanha atual, outra para operações do Studio), permitindo trabalhar em paralelo.

---

### C3. Cada salvamento remonta o painel inteiro
**O que é.** O painel de etapa é renderizado com `key={c.id}-{c.version}-{selected}`, e `version` é incrementado a cada gravação. Mudar a chave faz o React **destruir e recriar** todo o painel.

**Por que importa.** É uma escolha defensiva que funciona — evita texto desatualizado na tela —, mas cobra caro: a cada salvamento você perde a posição do scroll, blocos que estavam abertos e qualquer texto meio digitado em outro campo. Numa etapa longa como a de publicação, incomoda.

**Como corrigir.** Sincronizar os campos com `useEffect` quando a prop muda — o padrão que o `VariantScriptField` já usa corretamente — e tirar `version` da chave.

---

### C4. O acesso pela rede não tem nenhuma autenticação
**O que é.** Por padrão (`FABRICA_LAN=1`), o servidor escuta em `0.0.0.0` e `_host_allowed` aceita qualquer endereço de rede privada.

**Por que importa.** Em casa, tudo bem. Em um café, coworking ou rede compartilhada, **qualquer pessoa na mesma Wi-Fi** que descubra a porta 5050 abre a Fábrica e pode editar ou excluir campanhas. Não há senha.

**Como corrigir.** Um PIN de quatro dígitos gerado na inicialização e exigido para requisições que não venham de `127.0.0.1`. Ou, mais simples, mudar o padrão para `FABRICA_LAN=0` e ligar só quando for usar o celular.

---

### C5. O caminho multi-cor pode não estar sendo usado
**O que é.** A tabela `campaign_variants` está **vazia**, e as três campanhas do banco estão todas como `published`.

**Por que importa.** A produção multi-cor é uma das funcionalidades centrais e o motivo de boa parte da complexidade do código (slots, aprovação em lote, fila por cor). Se na prática você produz uma cor por campanha, há complexidade sendo mantida sem retorno — ou a funcionalidade não está sendo encontrada na interface.

**Como corrigir.** Antes de qualquer código: vale você me dizer se usa o multi-cor. Se usa e não aparece, é bug de interface. Se não usa, dá para simplificar bastante.

---

### C6. Dois caminhos diferentes publicam uma campanha
**O que é.** `POST /transition` com alvo `published` e `POST /publish-slot` fazem a mesma coisa com regras diferentes de gravação (relacionado ao A3).

**Como corrigir.** Deixar `publish-slot` como caminho único e fazer a transição para `published` apenas refletir o que ele decidiu.

---

## 🔵 Bloco D — Design e interface

### D1. ~~O trabalho acontece na coluna mais estreita~~ — RETIRADO

> Verificado com o app aberto: não procede. O painel de trabalho já ocupa a largura inteira na tela de produção. Ver a correção no topo do documento. O texto abaixo fica como registro do erro.
**O que é.** O layout de produção é `250px (lista) | centro largo (stepper) | 350px (inspector)`. O **inspector** é onde você lê prompts, edita roteiro, anexa mídia e confere aprovação — ou seja, onde 90% do trabalho acontece. O centro, muito mais largo, mostra o stepper das etapas, que é navegação.

**Por que importa.** Prompts de vídeo têm 400+ palavras e você os lê numa coluna de 350 pixels. É a inversão da hierarquia: a navegação ganhou o espaço nobre e o conteúdo ficou espremido.

**Como corrigir.** Inverter as proporções: stepper como uma faixa horizontal fina no topo (ele já é linear, não precisa de área) e o painel de trabalho ocupando o centro largo. É a mudança visual de maior impacto no dia a dia.

---

### D2. Não existe sistema de design
**O que é.** O CSS define **5 variáveis** (`--purple`, `--muted`, `--border`, `--green`, `--purple-soft`), usadas 28 vezes — contra centenas de cores escritas à mão. O roxo da marca `#7047eb` aparece 11 vezes fixo no arquivo **apesar de existir a variável `--purple`**; há ainda `#5733b7`, `#4c348f`, `#f54e93`, `#6038d6`, todos parentes do mesmo roxo.

**Por que importa.** Trocar a cor da marca hoje significa caçar dezenas de valores espalhados, com chance alta de esquecer alguns e deixar a interface remendada. O mesmo vale para espaçamentos e raios de borda.

**Como corrigir.** Um bloco de tokens no topo (cores, espaçamentos, raios, sombras, tipografia) e substituição progressiva dos valores fixos. Não precisa ser tudo de uma vez: começar pelas cores já resolve a maior parte.

---

### D3. Oito breakpoints diferentes
**O que é.** O CSS reage em 1650, 1200, 1100, 950, 850, 720, 650 e 600 pixels.

**Por que importa.** Cada largura nova foi resolvida com um `@media` próprio, e agora regras de faixas vizinhas se contradizem — é por isso que ajustar o layout em uma tela costuma quebrar outra.

**Como corrigir.** Consolidar em três: celular (≤640), tablet (≤1024) e desktop. Ao juntar, várias regras duplicadas simplesmente somem.

---

### D4. O CSS está em duas linhas gigantes
**O que é.** As duas primeiras linhas do `styles.css` concentram a maior parte das regras, minificadas, seguidas de blocos colados depois — resultado dos scripts de patch em `_patch/`.

**Por que importa.** Não dá para achar uma regra, comparar versões ou revisar uma mudança. Qualquer edição nesse arquivo é feita no escuro.

**Como corrigir.** Rodar um formatador uma vez (o `prettier` já vem com o Node) e dividir em seções comentadas. É seguro: o CSS gerado é idêntico.

---

### D5. Sem modo escuro e sem respeito a "reduzir movimento"
**O que é.** Não há `prefers-color-scheme` nem `prefers-reduced-motion` no arquivo.

**Por que importa.** Você trabalha de noite e o app é branco puro (`#f6f5fa`) em tela cheia. E o spinner gira indefinidamente para quem configurou o sistema para reduzir animações.

**Como corrigir.** Com os tokens do D2 no lugar, o modo escuro vira um bloco de ~15 linhas redefinindo as variáveis.

---

### D6. Foco de teclado inconsistente
**O que é.** `:focus-visible` aparece em apenas dois lugares. Campos de formulário têm foco estilizado; botões dependem do contorno padrão do navegador.

**Por que importa.** Navegar por Tab entre os passos fica confuso — e boa parte do trabalho é copiar campo, colar, avançar.

**Como corrigir.** Uma regra única `:focus-visible` para todos os elementos clicáveis.

---

### D7. Resíduo do React Flow
**O que é.** `@xyflow/react` continua no `package.json` e o único uso é `import '@xyflow/react/dist/style.css'` em `main.jsx`. O CSS ainda tem regras `.react-flow__handle`, e `Canvas.jsx` é remanescente do canvas antigo.

**Por que importa.** Peso de download e confusão para quem lê o projeto (inclusive o README descrevia o app errado por causa disso — já corrigido).

**Como corrigir.** Remover a dependência, o import e as regras órfãs.

---

### D8. O contador de palavras não ajuda a decidir
**O que é.** O editor de roteiro mostra o total de palavras e a frase "confirme o tempo com uma leitura".

**Por que importa.** O total não diz **onde** está o excesso. Um roteiro de 44 palavras pode estar perfeito ou ter um hook de 16 palavras que estoura os 4 segundos.

**Como corrigir.** Contador por trecho, com faixa alvo e cor: hook 10–12, desenvolvimento 20–24, CTA 7–9. Verde dentro, âmbar perto, vermelho fora.

---

## O que eu faria primeiro

Se fosse escolher uma ordem pelo retorno sobre o esforço:

| Ordem | Item | Esforço | Retorno |
|---|---|---|---|
| 1 | **C1** backup automático | 15 linhas | Elimina o risco de perder tudo |
| 2 | **A1** "legging" fixa | 10 linhas | Conserta toda campanha que não seja legging |
| 3 | **A2** pontuação dupla | 3 linhas | Melhora a locução de todos os vídeos |
| 4 | **B6** campos de objeção e oferta | pequeno | Destrava B3 e B4 |
| 5 | **B1 + B2 + B5** hooks por motor e orçamento por trecho | médio | O maior ganho de venda |
| 6 | **A3** separar o `checklist` | médio | Para de perder dados de publicação |
| 7 | **D1** inverter as colunas | médio | Ganho diário de conforto |
| 8 | **A6** atualizar os testes | pequeno | Suíte volta a ser um alarme confiável |

Os blocos B1–B5 podem ser implementados usando a skill `roteiro-ugc-15s` como especificação — ela já tem as famílias de hook, a estrutura de três batidas, o banco de objeções e o orçamento de palavras prontos.

---

## O que está bem-feito (e merece ser preservado)

Vale registrar, porque em uma revisão é fácil só listar defeito:

- **A recusa em inventar atributos.** `_product_features`, `_feature_present` e `_focus_is_contradictory` verificam negações ("legging sem bolso") antes de afirmar qualquer coisa. Isso é cuidado de verdade e é o que mantém o conteúdo honesto.
- **A trava de cenário** (`_scene_lock`), que força todas as cores a repetirem a mesma locação — é o que faz um conjunto de vídeos parecer uma coleção e não peças soltas.
- **A validação de mídia pelo conteúdo** (`services/media.py`), lendo as caixas do MP4 em vez de confiar na extensão do arquivo.
- **O controle de versão otimista** (`start()` comparando `version`), que impede duas janelas de sobrescreverem uma à outra em silêncio.
- **A auto-migração do banco**, que permite atualizar o app sem perder dados.
- **A decisão de manter geração e publicação manuais.** É o que mantém o custo em zero e a conta fora de risco.

---

## Auditoria adicional — 2026-09-13 (UI mobile/desktop e performance)

**Data:** 2026-09-13
**Base analisada:** commit `2be3344` até `c158bd2` (site publicado em produção; telas Início, Produzir, Resultados e conta/identidade, em mobile e desktop, revisadas ao vivo no navegador)
**O que foi revisado:** navegação por hash, `styles.css` (cascata completa dos blocos `@media`), `App.jsx`, cabeçalhos de cache em `app.py`.

### Status — o que já foi feito

| Item | Estado |
|---|---|
| E1 cascata de CSS anulando media queries mobile | ✅ feito |
| E2 tela em branco ao recarregar em campanha com etapa inválida | ✅ feito |
| E3 contraste do texto do cabeçalho | ✅ feito |
| E4 acordeões de Resultados quebrando em 3 linhas no celular | ✅ feito |
| E5 bundle JS/CSS sem cache de longo prazo | ✅ feito |
| E6 fotos da biblioteca de modelos sempre `no-store` | ✅ feito |
| E7 suspeita de espaço desperdiçado no desktop (Início) | ❌ **achado incorreto, retirado** (ver abaixo) |

---

### E1. Cascata de CSS anulando media queries mobile
**O que é.** Vários blocos `@media` ficavam fisicamente **antes**, no arquivo, de regras não-condicionais de mesma especificidade. O CSS resolve empates de especificidade pela ordem no arquivo, não pela "estreiteza" do media query — então essas regras responsivas eram silenciosamente anuladas mesmo com a viewport batendo a condição.

**Por que importa.** Pelo menos dez seletores diferentes tinham o comportamento mobile combinado ignorado (grade de identidade virando 2 colunas, atalhos de serviço, cabeçalho do acordeão etc.), sem nenhum erro visível — só "não funciona".

**Como corrigir.** Mover os blocos `@media` afetados para o fim do arquivo, garantindo que vençam o empate de especificidade. Feito para os blocos de 1650px/1200px/950px/650px, 1100px/850px e 720px, com comentário explicando o motivo no próprio CSS.

---

### E2. Tela em branco ao recarregar em campanha com etapa inválida
**O que é.** Um link direto ou uma etapa que sobrou de outra campanha podia deixar o estado `selected` apontando para uma etapa que não existe em `stageInfo`; a tela quebrava tentando ler `stage.title` de `undefined`.

**Por que importa.** Recarregar a página no meio de uma campanha (ou abrir um link salvo) podia travar a tela de produção por completo, sem mensagem de erro.

**Como corrigir.** Leitura defensiva do título (`stage?.title||'Etapa'`) e uma rede de segurança: um `useEffect` que detecta `selected` inválido e devolve a navegação para a próxima etapa válida da campanha, em vez de travar.

---

### E3 e E4. Contraste do cabeçalho e quebra dos acordeões de Resultados
**O que é.** O texto do cabeçalho tinha contraste baixo contra o fundo branco; os cabeçalhos dos acordeões de Resultados quebravam em até três linhas no celular por falta de `flex-wrap`.

**Como corrigir.** Cor de texto mais escura em `.header` e `.workspace-name`; `flex-wrap` e `flex: 1 1 100%` em `.collapse-toggle` dentro do breakpoint de 650px.

---

### E5 e E6. Cache HTTP do bundle e das fotos da biblioteca
**O que é.** O `after_request` global aplicava `Cache-Control: no-store` a **tudo**, inclusive o bundle JS/CSS com hash no nome (que nunca muda de conteúdo sob a mesma URL) e as fotos da biblioteca de modelos servidas por link assinado do Supabase.

**Por que importa.** Isso força o navegador a rebaixar o bundle inteiro a cada visita e a regenerar/rebaixar fotos que não mudaram, direto no orçamento de banda do celular.

**Como corrigir.** `/assets/*` (bundle com hash) ganhou `public, max-age=31536000, immutable`; o redirecionamento assinado das fotos da biblioteca ganhou `private, max-age` um pouco menor que o `expiresIn` do link assinado, em vez de `no-store` incondicional. As demais rotas de API continuam `no-store`, como deve ser.

---

### E7. Suspeita de espaço desperdiçado no desktop (Início) — retirado
**O que é.** Uma primeira leitura de captura de tela (fortemente reduzida) sugeriu que o conteúdo da tela Início não usava toda a largura em telas grandes.

**Por que foi retirado.** Medição direta (`getBoundingClientRect()`) no navegador ao vivo mostrou que o conteúdo já ocupa cerca de 1323–1360px de uma viewport de 1440px, com os cartões de nicho espalhados de ponta a ponta. A captura de tela original tinha sido mal interpretada; nenhuma mudança de CSS foi aplicada para este item.

**Validação:** `npm run build` do frontend e os 90 testes de `tests/test_app.py`, todos `OK`, antes do commit `c158bd2`.
