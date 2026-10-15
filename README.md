# Fábrica TikTok

App da fábrica TikTok para o perfil da **Micaela**: produção de shorts/UGC para TikTok Shop com interface em **React + Vite** (navegação Início / Produzir / Resultados), API **Flask**. Organiza campanhas com modelo fixa, produto, **várias cores**, prompts de imagem e de vídeo para o **Grok Imagine** (ou Flow), roteiros de 15s em voz de cliente real, **11 formatos de vídeo**, **sequências de 2 ou 3 clipes** com storytelling, legendas inteligentes e publicação **manual** no TikTok Studio (uma cor por vez).

A campanha pode nascer **automática** (fotos do produto + print da descrição → a IA preenche o briefing e já deixa os prompts prontos) ou **manual** (campo por campo).

Repositório: [maaiquels2/tiktok-automated](https://github.com/maaiquels2/tiktok-automated)

## Duas formas de rodar o mesmo app

O código é um só (`app.py` + `frontend/`), mas ele roda de duas formas diferentes, e **as duas continuam existindo ao mesmo tempo**:

| | **Local (Windows)** | **Nuvem** |
|---|---|---|
| Onde fica | No seu PC, ligado | `https://tiktok-automated.vercel.app` (Vercel) |
| Banco de dados | SQLite (`data/fabrica_tiktok.db`) | Postgres (Supabase) |
| Mídia (fotos/vídeos) | Pasta `media/` no disco | Supabase Storage |
| Acesso | `http://127.0.0.1:5050`, ou pelo IP do PC na mesma Wi‑Fi | Qualquer navegador, celular ou computador, de qualquer lugar |
| Login | Nenhum por padrão (é só você no seu PC) | Login com usuário e senha — **até 2 contas**, mesmo estúdio |
| Abrir Grok/Flow/TikTok Studio | Perfil dedicado do Chrome, controlado pelo app (Playwright) | Link direto — abre o app instalado no celular ou uma aba nova no navegador |
| Misturar vídeos (FFmpeg) | ✅ Disponível | ❌ Não disponível (precisa de FFmpeg local) |
| Auto-cut / Critico de Vendas | ✅ Disponível | ❌ Não disponível (avisa um robô que roda no PC) |
| Coleta automática de métricas do Studio (Playwright/CDP) | ✅ Disponível | ❌ Não disponível — preencha o painel de Performance manualmente |

Em resumo: **a nuvem é a forma do dia a dia**, pra você e a Micaela acessarem do celular sem precisar ligar o PC nem instalar nada. **O local continua existindo** pra quando o computador está ligado mesmo assim e você quer usar o mixer de vídeo, o auto-cut ou a coleta automática de métricas — coisas que dependem de programas instalados no Windows (FFmpeg, Chrome com Playwright) e não fazem sentido rodando num servidor.

Escrita de prompts/roteiro/legenda, biblioteca de modelo, análise de foto por IA, publicação em fila por cor e tudo o mais descrito abaixo funciona **igual nos dois modos**.

## O que o projeto entrega

### Nova campanha: automática ou manual
- **Automática** — escolha a moda (praia, academia, casual, dia a dia, íntima, fantasia), suba **1 a 3 fotos do produto** e o **print da descrição** da página do produto. Opcional: a **foto das cores** (print do seletor de cores ou as cores lado a lado), e a IA descreve cada cor com os detalhes. As cores também podem ser digitadas à mão, e o que você escreve vale mais que a leitura da IA.
  - A IA lê tudo, sugere o briefing inteiro (produto, benefício, ângulo, movimentos, detalhes, objeção, oferta e prova social do print), cria a campanha, escreve o roteiro e deixa os prompts do Grok prontos.
  - Oferta e prova social lidas do print aparecem no aviso final para você conferir se ainda valem.
- **Manual** — você preenche o briefing do zero. Os campos já vêm com o padrão da moda escolhida.
- Nas duas formas você já escolhe o **formato do vídeo**, o **tipo de vídeo** (clipe único ou sequência), as **técnicas de câmera** e se a modelo gira um pouco de lado (sem mostrar as costas).

### Formatos de vídeo
Cada formato muda a abertura, as ações do meio, o encerramento e o texto na tela, sobre uma das bases (modelo de frente falando, POV ou só movimento):

| Formato | O que é |
|---|---|
| **Com fala** | Modelo de frente falando com a câmera (padrão) |
| **Celular no espelho** | Ela grava o próprio look no espelho, com o celular na mão — o formato que melhor funcionou nos testes |
| **Só movimento** | Sem fala: puxa, gira e ajusta a peça |
| **Respondendo comentário** | Responde a dúvida de uma cliente e prova na hora |
| **Teste de prova** | Agacha, pula ou gira para provar a peça |
| **Troca de cor** | Termina com a mão na lente para emendar as cores na edição |
| **3 jeitos de usar** | A mesma peça em três looks (experimental) |
| **Abrindo o pacote** | POV tirando a peça da caixa (experimental) |
| **Close ASMR** | Sem fala: closes e o som do tecido |
| **Na mesa, de perto** | Sentada à mesa, mostra o produto e traz perto da lente (experimental) |
| **POV (último caso)** | Só mãos e produto, sem rosto. Nos testes reais o Grok errou mãos e giro da peça: fica por último na lista |

Na etapa de vídeo dá para alternar entre os formatos com a modelo de frente sem refazer a imagem. POV, Espelho e Abrindo o pacote mudam a imagem-base: esses se trocam em **Definir look**.

**Câmera e técnicas (opcional):** *Closes no produto* (o rosto sai do quadro por 1 a 2 s para mostrar o material), *Movimentos ousados*, e até **2 técnicas de retenção** por vídeo — *Começar em movimento*, *Aproximação rápida*, *Mão revelando*, *Loop* e *Esticar o tecido*.

### Tipo de vídeo: clipe único ou sequência em 2 ou 3 clipes
- Escolhido **já na criação da campanha**, no bloco **Tipo de vídeo** logo abaixo da grade de formatos: *Clipe único* (15 s), *Sequência de 2 clipes* (~30 s) ou *Sequência de 3 clipes* (~45 s).
- Dois arcos de storytelling, com **fala nova em cada clipe**:
  - **Motivos** — "Três motivos pra essa peça estar no seu guarda-roupa", um motivo por trecho.
  - **Questionada** — "Sabe o que dizem por aí? Que ela não te valoriza", e a resposta.
- Os motivos só podem ser **fatos verdadeiros da peça**: a sequência exige **pelo menos 3 fatos** (ex.: *capuz, zíper frontal, bolsos laterais*). O texto padrão da moda no campo Detalhes não conta como fato. Sem 3 fatos, a campanha não é criada e o aviso diz o que faltou.
- Todos os clipes partem da **mesma imagem aprovada**. Na etapa de vídeo a sequência já aparece montada no topo, com o prompt de cada clipe (versão completa e Guia do Grok), o texto na tela e o passo a passo de montagem no CapCut.
- As falas de cada clipe podem ser editadas no painel antes de atualizar os prompts.
- **Escrever as falas com IA:** botão próprio no painel (nunca automático, porque gasta tokens). A IA escreve falas novas para cada clipe com os mesmos 3 fatos, e elas passam pela mesma conferência do rascunho: nada fora do briefing, urgência só com oferta real, carrinho só no último clipe, 45 a 57 palavras por clipe e os 3 fatos citados. Reprovadas duas vezes, fica o rascunho, com o motivo na tela. Aprovadas, ficam guardadas por arco, número de clipes e cor: reabrir a etapa de vídeo mostra as mesmas falas sem chamar a IA de novo. Briefing, imagem e status não mudam.
- Em campanhas antigas, o painel tem o campo **"Fatos da peça só para esta sequência"**: ele não mexe no briefing, então a imagem aprovada e os prompts continuam. (Editar o Detalhes do briefing de uma campanha com imagem aprovada apaga a imagem e os prompts.)
- Funciona em Celular no espelho e nos formatos com a modelo de frente (Com fala, Teste de prova, Respondendo comentário, Troca de cor, 3 jeitos). Não funciona em POV, Abrindo o pacote, Só movimento, Close ASMR e Na mesa.
- Sem o botão da IA, as falas são um rascunho montado por regras: revise antes de gerar.

### Mesmas falas em 3 partes (Extend Video)
- Cartão "Mesmas falas em 3 partes (Extend)" na etapa de vídeo, separado da sequência acima: não cria falas novas, reparte as **mesmas falas** do roteiro de 15 s em 3 partes (gancho → prova → fechamento) para usar com o **Extend Video** do Grok, com o checklist de montagem no CapCut.

### Prompt de vídeo: Completo ou Guia do Grok
- Duas versões para o mesmo vídeo, trocadas por um botão na etapa de vídeo:
  - **Completo** — o prompt inteiro com cena, falas, ações cronometradas, expressão e regras de consistência.
  - **Guia do Grok** — versão enxuta no formato do guia oficial do Grok Imagine para imagem-para-vídeo.
- Nos testes, cada versão ganhou em produtos diferentes: vale gerar as duas.
- O prompt respeita o limite de 4.000 caracteres do Grok: acima de ~3.940, o app tira blocos inteiros pelo menos essencial (contexto de nicho, ângulo de venda) e nunca corta identidade, cenário, falas ou as regras de honestidade.
- **Nota do prompt** (1 a 10): checagens rápidas que explicam por que o gerador costuma se perder (muitas ações, atributo que o próprio prompt proíbe, fala longa). É um alerta, não garantia.

### Biblioteca de prompts aprovados
- Os 18 prompts de imagem e de vídeo aprovados nos testes reais de 11 e 12/10/2026 já vêm gravados no banco (Identidade → Biblioteca de prompts).
- Na etapa de vídeo, **Guardar na biblioteca** salva o prompt atual com produto, formato, versão (Completo ou Guia do Grok) e a campanha de origem; dá para filtrar por imagem ou vídeo, copiar e excluir.

### Produção multi-cor
- Informe várias cores no briefing (`Branco, Preto, Azul Marinho…`).
- **Gerar prompts e roteiro** cria automaticamente **um pacote por cor** (imagem, vídeo, falas e legenda).
- A IA **nunca** recebe todas as cores no mesmo prompt de imagem.

### Imagens
- Etapa **Criar imagem** com cartão por cor: prompt + anexar resultado.
- Várias imagens ativas na mesma campanha (slot por cor).
- **Aprovar todas as imagens** só libera quando cada cor tem arquivo.

### Modelo fixa e consistência de identidade
- **Biblioteca da modelo** por nicho (praia, academia, casual, dia a dia, íntima, fantasia): suba as fotos padrão uma vez e reutilize em qualquer campanha.
- Suporta **mais de uma modelo** na biblioteca (não só a Micaela) — escolha qual conjunto de fotos usar por campanha.
- Renomeie o rótulo de cada foto para achar rápido depois, ou exclua a foto de um nicho.
- **Ficha de consistência de personagem**: gera um prompt mestre (com lista de negativos contra troca de rosto, CGI e mãos malformadas) e abre o Grok já pronto para criar a ficha de referência da modelo.

### Análise de foto por IA (opcional)
- Ao criar ou editar o briefing, anexe a **foto de descrição do produto** (aquela print com as características, tamanho, tecido etc.).
- Se a Escrita por IA estiver configurada (ver abaixo), o app manda a foto pra um modelo com visão (`gpt-6-luna` na OpenAI ou `gemini-2.0-flash` — mesma chave da escrita de texto) e preenche sozinho benefício, ângulo, movimentos e detalhes. É a mesma leitura usada na criação automática.
- **A foto manda mais que o modelo padrão do nicho**: o que a IA encontrar na foto substitui o texto genérico do nicho; o texto do nicho só continua valendo pros campos que a foto não esclareceu.
- Sem IA configurada, ou se a análise não encontrar nada de útil, os campos ficam com o padrão do nicho escolhido, como sempre foi.

### Argumento de venda: motor de persuasão
- Três motores, cada um com a sua fórmula, **sempre com fato**:
  - **Necessidade** (dor → agitação → prova) — liga quando o campo **O que mais segura a compra?** está preenchido: o gancho nomeia a dor do cliente e o meio vira a prova que derruba a dúvida.
  - **Desejo** (o padrão) — encanto pela peça e a cliente se imaginando usando, sem afirmar nada além do briefing.
  - **Escassez** (novidade → prova rápida → prazo/estoque) — só existe com **Oferta real** declarada. Cada fala de urgência usa o número exato da oferta; sem prazo não existe "só hoje", sem estoque não existe "últimas peças". Urgência inventada é propaganda enganosa (CDC, art. 37) e derruba vídeo no TikTok Shop.
- **Prova social** ("2 mil vendidos", "nota 4,8") só entra quando declarada no campo próprio.
- O motor também define a direção de cena do vídeo: expressão no gancho, arco emocional e gesto da chamada.
- No briefing, uma prévia mostra como a oferta e a prova social vão virar fatos no roteiro, antes de gerar.

### Roteiros 15s inteligentes
- Falas em **primeira pessoa, na voz de cliente real** (UGC), nunca em tom de catálogo.
- Hook (0–4s), desenvolvimento (4–12s) e CTA (12–15s) **variam por cor**.
- **Fala que ocupa o clipe inteiro:** o alvo é de **45 a 56 palavras** no total. Nos testes reais, com 33 a 46 palavras sobravam 2 a 3 s de silêncio no fim; com ~57 ficava acelerado. Abaixo do alvo o gerador acrescenta uma frase de imaginação de uso (sem afirmar nada novo); acima de 57, encurta pelo fim do desenvolvimento.
- Contador de palavras por trecho no editor, como orientação: comprimento nunca bloqueia o roteiro (fala natural e com gestos vale mais que caber num número).
- O desenvolvimento segue três batidas: prova → objeção quebrada → posse. Se o roteiro estoura o tempo, a posse cai primeiro — a prova nunca é descartada.
- **Banco de falas** por categoria de peça (biquíni não fala como pijama): objeções típicas, prova falada, ocasiões de uso e moldes de gancho e chamada. Molde que cita um atributo só aparece quando o briefing confirma esse atributo.
- **Guardar no banco:** roteiros bons viram exemplos de estilo para a IA nas próximas campanhas da mesma categoria. Dá para excluir do banco depois.
- Botões **Atualizar hook + legenda** e **Atualizar fala inteira** para gerar outra variação sem recomeçar a campanha (também em produto de uma cor só). Salve edições manuais antes de regenerar. A imagem aprovada é preservada; novas falas exigem revisão do roteiro e um novo vídeo.
- Edição manual por campo, com prompt de vídeo recalculado a partir das falas.

### Vídeos
- **Um MP4 por cor**, espelhando o fluxo das imagens.
- Botão único **Abrir Grok/Flow para vídeo** no topo (sem repetir em cada cor).
- Aprovação em lote: 15s e resolução alvo (1080×1920 Flow ou 720×1280 Grok).

### Misturar vídeos (só na versão local)
- Na etapa **Criar vídeo**, bloco **Misturar vídeos**.
- Escolha 2+ MP4s da campanha, ordene, defina segundos por clip (ou deixe vazio para dividir ~15s).
- Salva no slot de uma **cor** ou em **Mix** (requer FFmpeg no PATH / instalado).
- O MP4 gerado precisa ser revisado de novo na aprovação (~15s, 9:16).
- Na nuvem esse bloco não aparece — depende de FFmpeg instalado no computador que roda o servidor.

### Legendas e hashtags para o TikTok
- Legendas alinhadas a produto, benefício, público e cor.
- Até **5 hashtags** por legenda, escolhidas pelo nicho (ex.: fitness, legging, TikTok Shop).
- Botão **Nova legenda** na publicação para refresh rápido.

### Publicação no Studio (fila por cor)
- Abas user-friendly por cor/produto.
- Escolha qual cor subir agora → copie legenda e caminho do MP4 → abra o Studio → registre.
- Passe para a próxima cor; a campanha só fecha como **publicada** quando todas as cores forem registradas.
- Legendas com no máximo **5 hashtags** (nicho + produto + cor).
- **Ver publicação** abre os links do TikTok (`published_url` / slots da checklist) quando a cor ou a campanha já foi registrada.
- O app **não** publica sozinho no TikTok (sem automação de post/tag), em nenhum dos dois modos.

### Performance, Insights e preview 9:16
- No **Studio** (status pronto/publicado): painel **Performance & Insights** por cor — informe views, watch%, likes, saves, pedidos etc. e salve em `checklist.performance`.
- Na versão local, o app pode coletar boa parte desses números sozinho, direto do TikTok Studio (Playwright/Chrome CDP). Na nuvem, esse preenchimento é manual.
- **Gerar insights** roda um crítico local (`services/insights.py`) e grava `checklist.insights` (Hook / Desenvolvimento / CTA + ações). Sem dados inventados do TikTok.
- **Preview 9:16** na aprovação de vídeo: telefone, scrubber e beats Hook (0–4s) · Desenvolvimento (4–12s) · CTA (12–15s) com overlay do roteiro.
- **Teste de gancho:** marque campanhas que mudaram uma coisa só (o gancho) como parte do mesmo teste; o app compara quanto cada uma rendeu por mil visualizações. Sem isso não dá para saber se o vídeo foi bem pelo gancho, pela peça, pela cor ou pelo horário.

### Resultados: auditoria do Studio, playbook e próximos vídeos
- **Auditoria em lote** dos posts do TikTok Studio dos últimos 7, 15 ou 30 dias (ignora vídeos com menos de 100 views por padrão).
- **Playbook de replicação** montado a partir da auditoria: o que repetir no próximo vídeo. Um clique cria uma campanha já preenchida com esse briefing.
- **Análise de link:** coleta as métricas de qualquer vídeo do TikTok pela URL, mesmo sem campanha no app.
- **Fila de produtividade:** o que continuar, o que produzir a seguir pelo playbook e o que melhorar.
- A coleta automática (auditoria e análise de link) usa o Chrome do PC: só na versão local.

### Outras ferramentas da produção
- **Duplicar campanha:** cria uma cópia editável e preserva a original (também a partir de campanha publicada).
- **Vídeo da galeria do celular:** registra um vídeo que ficou na galeria do celular sem precisar subir o arquivo.
- **Auto-cut / Crítico de Vendas** (só local): salva o pedido de corte e entra na fila para o robô do PC processar.
- **Conferir se a peça continua a mesma no vídeo** ([`ferramentas/conferir_produto`](ferramentas/conferir_produto/README.md)): ferramenta local, fora do app, que compara os quadros do vídeo gerado com a imagem aprovada (DINOv2) e avisa quando a peça perde detalhes (bordado que some, estampa que muda). É uma triagem: não pega detalhe novo que aparece, como um laço a mais.

### Renomear campanha
- Controle **Renomear** (lápis) perto do título da campanha.
- PATCH só de `name` — não invalida etapas nem dispara guards de busy/discard de forma agressiva.

### Navegação e campanhas
- Três áreas: **Início** (biblioteca de fotos, atalhos de serviço, lista de campanhas), **Produzir** (stepper das etapas) e **Resultados** (Studio, lote, playbook, histórico, campanha).
- Endereços internos: `#/inicio`, `#/produzir/<id>/<etapa>`, `#/resultados/<aba>` — dá para salvar o link de uma etapa específica.
- Pipeline: modelo → look → imagem → aprovação → roteiro → vídeo → aprovação → Studio → performance.
- Campanhas com **renomear**, editar, copiar e excluir; versão editável a partir de campanha publicada.
- Reuso da referência da mesma modelo entre campanhas.
- Até 8 fotos de produto por campanha; movimentos do produto no prompt de vídeo.
- Exportação TXT/ZIP do pacote (só mídias aprovadas no ZIP) — na versão local.
- Interface ajustada pra celular: menos texto, atalhos de serviço em grade 2×2, fotos da modelo lado a lado, formulários em coluna única.

### Privacidade
- Prompts e rascunhos de texto são **determinísticos e locais** (regras em Python). A API paga de texto só é chamada pela Escrita por IA, pela leitura de fotos e pela criação automática — e só com a chave configurada.
- A chave da OpenAI **nunca** vai para o código nem para o GitHub: fica na variável de ambiente `OPENAI_API_KEY` (na Vercel ou nas variáveis de ambiente do Windows) ou salva pela tela de Identidade.
- Geração de imagem/vídeo é **manual** no Flow ou Grok Imagine (sua assinatura).
- Na versão local, tudo fica no PC: banco, mídia, perfis de navegador. `.gitignore` exclui `data/`, `media/`, `browser_profiles/`, `.venv/`, etc.
- Na nuvem, banco e mídia ficam no Supabase da conta do projeto; o acesso exige login.

## Stack

| Camada | Tecnologia |
|---|---|
| UI | React + Vite (stepper de etapas, navegação por hash, tema claro/escuro, layout mobile) |
| API | Flask (Python) — mesmo `app.py` nos dois modos |
| Banco | SQLite local (`data/fabrica_tiktok.db`) **ou** Postgres via Supabase na nuvem |
| Mídia | Pasta `media/campanha-XXXX/` local **ou** Supabase Storage na nuvem |
| Navegador (só local) | Chrome/Edge + Playwright (Flow/Studio); Grok em processo normal |
| Deploy da nuvem | Vercel (`vercel.json` + `wsgi.py`), build do frontend embutido no build do Vercel |

## Nuvem — usar pelo navegador ou celular

Acesse **`https://tiktok-automated.vercel.app`** em qualquer navegador (celular ou computador). No primeiro acesso, crie a conta principal (usuário + senha); pelo ícone de **Acessos do estúdio** no cabeçalho, o responsável cria a segunda conta e pode redefinir a senha dela depois. As duas contas enxergam **o mesmo estúdio e as mesmas campanhas**.

No celular, os botões de Grok/Flow/TikTok Studio/TikTok abrem como links diretos — o próprio sistema entrega para o aplicativo instalado quando existe associação, ou abre no navegador do celular. Fotos e vídeos anexados sobem direto para o Supabase Storage.

### Variáveis de ambiente da nuvem (configuradas no projeto Vercel)

| Variável | Para quê |
|---|---|
| `FABRICA_CLOUD=1` | Liga o modo nuvem (Postgres + Storage + login obrigatório) |
| `FABRICA_DATABASE_URL` | String de conexão do Postgres (Supabase) |
| `FABRICA_SECRET_KEY` | Chave de sessão do Flask (login) |
| `FABRICA_SUPABASE_URL` | URL do projeto Supabase |
| `FABRICA_SUPABASE_SERVICE_KEY` | Chave de serviço do Supabase (Storage) |
| `FABRICA_SUPABASE_ANON_KEY` | Chave anônima, exigida pelo cabeçalho `Authorization` do Storage |
| `FABRICA_STORAGE_BUCKET` | Nome do bucket de mídia no Supabase Storage |
| `FABRICA_AI_PRICES` | Opcional: preço por modelo para o teto de gasto, em JSON (`{"gpt-6.1-sol": [entrada, saída]}`, US$ por 1 milhão de tokens). O preço cadastrado na tela vale por cima |
| `OPENAI_API_KEY` | Chave da OpenAI para a Escrita por IA, a leitura de fotos e a criação automática. Com ela definida, a IA já vem ligada (desliga quem desmarcar na tela). Secreta: nunca no código |

Colunas novas da tabela de campanhas (como as da sequência, `sequence_clips` e `sequence_arc`) são criadas sozinhas no Postgres quando o servidor sobe. **Tabelas e índices novos ainda são manuais**: rode o SQL no painel do Supabase antes do deploy que precisa deles.

### Fazer um novo deploy

Depois de uma sessão de mudanças, o fluxo é: revisar o que foi commitado localmente (`git log`, `git status`), `git push origin main`, e então redeployar no painel do Vercel (ou deixar o deploy automático do Vercel disparar pelo push, se estiver configurado assim). O build do Vercel roda `cd frontend && npm ci && npm run build` (ver `vercel.json`) antes de subir o `wsgi.py`.

## Abrir no Windows (versão local)

Dois cliques em **`iniciar.vbs`**: sobe o servidor e abre `http://127.0.0.1:5050`. Se a porta estiver ocupada, tenta `5051`–`5059`.

Pelo terminal:

```powershell
cd C:\Users\Admin\Documents\Codex\2026-09-10\Fabrica_TikTok
.\.venv\Scripts\python.exe app.py
```

Fechar a aba do navegador **não** encerra o servidor. No terminal, use Ctrl+C. Com o iniciador, finalize o Python no Gerenciador de Tarefas se precisar.

### Se o servidor travar

Duplo clique em **`reiniciar-fabrica.bat`**: encerra o processo do app naquela pasta e sobe de novo.

### Usar pelo celular (mesma Wi‑Fi, sem ser a versão nuvem)

O iniciador imprime o endereço de LAN (algo como `http://192.168.0.10:5050`). Abra esse endereço no celular conectado à mesma rede. A interface se adapta à tela, e os botões de Grok / Flow / TikTok viram links nativos, abrindo o app instalado em vez do perfil de Chrome do PC.

Isso **não** é a versão nuvem: o servidor continua sendo o seu PC, que precisa estar ligado. Para restringir o acesso a `127.0.0.1`, defina `FABRICA_LAN=0`.

### Quem escreve as falas — três coisas diferentes

É fácil confundir, então vale separar:

| Onde | O que é | Quando age |
|---|---|---|
| **Gerador local** (`services/prompts.py`) | Regras em Python. Monta hook, desenvolvimento, CTA e legenda a partir dos campos do briefing. Não usa internet nem API. | Sempre que a escrita por IA está desligada, falha ou é reprovada. |
| **Escrita por IA** (`services/copywriter.py`) | O app chama a API da OpenAI ou do Gemini com a sua chave, recebe o texto e audita antes de aceitar. Também usada pra analisar a foto de descrição do produto (mesma chave, se o modelo tiver visão). | Sempre que há chave: com `OPENAI_API_KEY` definida (como na nuvem) já vem ligada; sem ela, quando você cola a chave e liga em Identidade → Escrita das falas. Desmarcar na tela desliga. É o app que faz a chamada, sozinho, a cada geração. |
| **Skill `roteiro-ugc-15s`** | Um documento de método. Vive no Claude, **não** dentro do app. | Quando você pede roteiro ao Claude numa conversa. O app não lê esse arquivo. |

As regras da skill foram traduzidas para a instrução que o app manda ao modelo, mas são **duas cópias**: mudar a skill não muda o app, e vice-versa. Se você evoluir a skill e quiser que o app acompanhe, peça a sincronização.

**Como saber qual dos dois escreveu:** a etapa *Roteiro de 15s* mostra um selo no topo — "Escrito por IA · OpenAI" ou "Texto local (sem IA)". Quando a IA é recusada pela auditoria ou pelo provedor, o selo mostra o motivo.

### Teto de gasto da IA
- Em Identidade → Escrita das falas: **teto por dia e por mês, em dólar** (padrão: US$ 2 por dia e US$ 20 por mês; 0 desliga). O painel mostra o gasto de hoje e do mês. O dia e o mês são os de Brasília.
- Atingido o teto, nenhuma chamada à IA sai: o roteiro e as falas da sequência ficam com o texto local, com o motivo no selo, e a leitura de fotos e a criação automática avisam.
- O gasto é calculado pelos tokens que cada chamada grava (por campanha, também mostrado na etapa do roteiro) vezes o **preço de cada modelo** (US$ por 1 milhão de tokens de entrada e de saída). O preço é cadastrado no mesmo painel ou na variável `FABRICA_AI_PRICES`. Modelo sem preço, ou com preço zero, conta pelo **preço de segurança** de US$ 5 na entrada e US$ 20 na saída, alto de propósito, para o teto parar cedo e nunca tarde.

### Escrita das falas por IA (funciona nos dois modos)

O gerador local é correto e nunca inventa atributo, mas monta a frase a partir do rótulo do briefing — por isso sai coisa como *"Repara no tecido sem transparência"*. Quem escreve bem é um modelo de linguagem; quem garante a honestidade é o código.

Por isso os dois trabalham juntos:

1. O app monta o briefing estruturado (fatos confirmados, objeção, oferta, motor, orçamento de palavras).
2. O modelo escreve hook, desenvolvimento, CTA e legenda.
3. O app **audita** o resultado: palavras por trecho, nenhum atributo de desempenho fora do briefing, urgência só com oferta real, no máximo 5 hashtags.
4. Reprovado? Volta para o modelo com os erros apontados, uma vez. Reprovado de novo? Usa o texto local.

Configure no ícone de **Identidade** no cabeçalho: escolha OpenAI ou Gemini, cole a chave e ligue. O botão **Testar conexão** gera um exemplo na hora. Modelo padrão da OpenAI para texto: `gpt-6.1-sol`. Se a variável `OPENAI_API_KEY` existir (na Vercel ou no Windows), ela é usada quando não há chave salva pela tela.

Na versão local, a chave fica em **`data/llm.json`**, só neste computador — fora do Git. Na nuvem, a mesma configuração fica salva no Postgres do projeto (visível pras duas contas do estúdio). Em ambos os casos a API do app nunca devolve a chave inteira — só os últimos quatro caracteres.

### Backup automático (versão local)

A cada inicialização o app copia o banco para `data/backups/fabrica-AAAA-MM-DD.db` e mantém os últimos 10 dias. `data/` fica fora do Git de propósito, então essa cópia é a única proteção contra perder campanhas, playbook e histórico. Na nuvem, o backup é responsabilidade do próprio Supabase (backups do Postgres gerenciado).

### PIN para acesso pela rede (versão local)

Quando você abre a Fábrica local pelo celular (mesma Wi‑Fi), o app pede um **PIN de 4 dígitos**. Ele aparece no cabeçalho (só neste computador), é impresso pelo iniciador e fica guardado em `data/lan_pin.txt`. Sem isso, qualquer pessoa na mesma Wi‑Fi que chegasse à porta 5050 poderia editar ou excluir campanhas. Acesso pelo próprio computador (`127.0.0.1`) nunca pede PIN. Na nuvem, quem protege o acesso é o login (usuário + senha), não o PIN.

### Instalação em outro computador (rodar a versão local em outro PC)

Requer **Python 3.11+**, **Node.js** compatível com Vite 7 (20.19+ ou 22.12+) e **Chrome ou Edge**. Na pasta do projeto:

```powershell
.\instalar.ps1
```

Instala dependências e compila a interface. Rascunhos de texto funcionam offline; Flow/Grok/Studio precisam de internet e login. Veja também [`COMO-INSTALAR-NO-OUTRO-PC.md`](COMO-INSTALAR-NO-OUTRO-PC.md) — hoje, pra um segundo acesso simples sem instalar nada num segundo PC, considere a **versão nuvem** com uma segunda conta em vez de clonar o app localmente.

## Pipeline

**referência → personagem → roteiro → imagem (por cor) → vídeo (por cor) → Studio/publicação**

## Fluxo de uso (resumo)

1. **Nova campanha** — *Automática* (fotos + print → a IA preenche e já gera os prompts) ou *Manual* (briefing + Grok 720p ou Flow 1080p). Escolha o formato do vídeo e o tipo: clipe único ou sequência de 2/3 clipes (com 3 fatos da peça).
2. **Modelo fixa** — anexe a referência (ou reutilize da biblioteca ou de outra campanha).
3. **Definir look** — produto, cores (vírgulas), movimentos, fotos do produto (e, se quiser, a foto de descrição pra IA sugerir os campos) → **Gerar prompts e roteiro**.
4. **Criar imagem** — uma geração/anexo por cor.
5. **Aprovar imagens** — todas as cores.
6. **Roteiro** — revise falas; use refresh se não gostar; guarde as boas no banco de falas.
7. **Criar vídeo** — um MP4 de 15s por cor (Grok/Flow no topo), com o prompt Completo ou o Guia do Grok. Se a campanha é uma sequência, os prompts de cada clipe já estão no topo.
8. **Aprovar vídeos** — lote com checagem de duração/resolução.
9. **Preparar publicação** — fila por cor: legenda (≤5 hashtags) + MP4 + Studio + registrar.
10. **Editar / copiar / excluir** campanhas na fila lateral.

Identidade da modelo é guiada por prompt + revisão humana (sem reconhecimento facial automático).

## Variáveis e privacidade

O app **não lê arquivo `.env`**: as variáveis vêm do ambiente do sistema.

- **Local (Windows):** defina como variável de ambiente do usuário (Configurações → Variáveis de ambiente) ou no terminal antes de subir (`$env:OPENAI_API_KEY='...'`). A chave da IA também pode ser colada na tela de Identidade, que guarda em `data/llm.json`, fora do Git.
- Opcionais: `FABRICA_MICAELA_PROFILE`, `FABRICA_CHROME_USER_DATA`, `FABRICA_LAN=0`.
- **Nuvem:** ver a tabela de variáveis do Vercel, acima.
- Nunca commitar chaves, senhas ou tokens.

`.gitignore` deve cobrir: `data/`, `media/`, `.venv/`, `browser_profiles/`, `.env`, secrets e caches.

## Persistência e arquivos

**Local:**
- Estado: `data/fabrica_tiktok.db` (com backups em `data/backups/`).
- Mídia por campanha:

```text
media/campanha-0001/
  reference-*.jpg
  image-*.png          # uma (ou mais) por cor (slot)
  video-*.mp4          # uma por cor (slot)
  downloads/
```

**Nuvem:** o mesmo formato de dados vive nas tabelas do Postgres (Supabase) e a mídia fica em objetos no Supabase Storage, servidos por link assinado ou por cache de longa duração quando a URL já indica a versão do arquivo.

Em ambos os modos:
- Alterar briefing/referência invalida etapas seguintes conforme regras do app.
- Uploads: imagens até 40 MB / 40 MP; MP4 até 250 MB.
- Controle de versão evita sobrescrita silenciosa entre janelas.

## Perfis de navegador (versão local)

| Perfil | Uso |
|---|---|
| `browser_profiles/flow-maaiquels` | Google Flow e Grok (`maaiquels@gmail.com`) |
| `browser_profiles/tiktok-micaela` | TikTok Studio (conta da Micaela) |

- Confirmação antes de abrir serviços externos.
- Grok abre em Chrome/Edge comum (sem Playwright). Feche o Flow desse perfil antes do Grok e vice-versa.
- O app **não** clica em gerar, **não** escolhe produto no Shop e **não** publica.
- Variáveis opcionais: `FABRICA_MICAELA_PROFILE`, `FABRICA_CHROME_USER_DATA`.
- Na nuvem não existe perfil de navegador: os botões abrem link direto (ver `frontend/src/serviceLinks.jsx`).

## Desenvolvimento

```powershell
# API (local, SQLite)
.\.venv\Scripts\python.exe app.py

# API simulando modo nuvem (Postgres precisa estar acessível)
$env:FABRICA_CLOUD=1; .\.venv\Scripts\python.exe app.py

# UI com hot reload
cd frontend
npm run dev

# Build servido pelo Flask (local) ou pelo Vercel (nuvem)
npm run build

# Testes do backend
.\.venv\Scripts\python.exe -m unittest discover -s tests -v

# Testes da interface (Vitest)
cd frontend
npm test
```

Os dois conjuntos de testes e o build também rodam sozinhos no GitHub a cada push e pull request (`.github/workflows/testes.yml`).

Os números que o gerador, a IA, as sequências e a tela precisam concordar (45 a 56 palavras por clipe de 15 s, teto de 57, limite de 4.000 caracteres do Grok) ficam em `services/limits.py` e `frontend/src/speechBudget.js`; um teste confere que os dois arquivos batem.

### Segurança
- Na nuvem, login obrigatório com limite de tentativas (bloqueio temporário depois de várias senhas erradas).
- Toda gravação (POST/PATCH/DELETE) exige o cabeçalho do próprio app e confere a origem, contra pedidos de outros sites.
- Cabeçalhos de segurança (Content-Security-Policy e afins) em todas as respostas.
- Na versão local, só aceita `localhost` ou rede privada, e a rede pede PIN.
- Arquivos enviados são validados pelo conteúdo (imagem e MP4), não pelo nome.

Rotas úteis: `/` e `/creator` (nova campanha). A documentação completa do projeto — propósito, escopo, arquivo por arquivo, banco de dados, arquitetura da nuvem, as rotas da API e o histórico de mudanças — está em [`DOCUMENTACAO-PROJETO.md`](DOCUMENTACAO-PROJETO.md).

## O que este projeto deliberadamente NÃO faz

- Não chama API paga de imagem/vídeo sozinho (usa Flow/Grok da sua assinatura, manualmente).
- Não automatiza publicação, tag de produto ou login no TikTok, em nenhum dos dois modos.
- Não faz montagem criativa completa de vídeo por IA — o mixer local apenas corta, normaliza e reúne clipes escolhidos pelo operador, e nem está disponível na nuvem.
- Na nuvem, não abre nem controla um Chrome de verdade (sem Playwright/CDP no servidor) — por isso o mixer de vídeo, o auto-cut e a coleta automática de métricas do Studio ficam restritos à versão local.

## Empacotamento futuro

EXE (PyInstaller), Tauri/Electron e montagem automática de vídeo ficam para depois. O iniciador Windows já isola dados locais.

## Referências

- [Vite](https://vite.dev/guide/)
- [Playwright persistent context](https://playwright.dev/python/docs/api/class-browsertype#browser-type-launch-persistent-context)
- [Documentação do Supabase](https://supabase.com/docs)
- [Documentação do Vercel](https://vercel.com/docs)
