# Fábrica TikTok — Documentação do Projeto

**Documento gerado em:** 2026-09-12
**Pasta do projeto:** `C:\Users\Admin\Documents\Codex\2026-09-10\Fabrica TikTok`
**Repositório:** https://github.com/maaiquels2/tiktok-automated
**Como abrir:** duplo clique em `iniciar.vbs` → http://127.0.0.1:5050
**Base auditada:** `main`/`origin/main` no commit `2be3344`, sem alterações anteriores a esta documentação; 65 rotas HTTP; 81 testes executados.

> Este documento explica **o propósito**, **o escopo**, **o que cada arquivo faz** e **tudo o que foi criado e modificado** no projeto. Foi escrito para ser lido sem base prévia em programação — há um glossário no final com os termos técnicos.

---

## 1. Em uma frase

A Fábrica TikTok é um **aplicativo que roda no seu próprio computador** e organiza, do começo ao fim, a produção de vídeos curtos (Shorts/UGC) para TikTok Shop: briefing → prompts → imagem → roteiro de 15s → vídeo → legenda → publicação manual no TikTok Studio → coleta de métricas → playbook do que repetir.

---

## 2. Propósito do projeto

### O problema que ele resolve

Produzir vídeos UGC para TikTok Shop em escala envolve muitos passos repetitivos e fáceis de errar:

- escrever um prompt de imagem diferente **para cada cor** do mesmo produto;
- manter a **mesma modelo** (mesmo rosto, mesmo corpo) em todas as campanhas;
- escrever roteiros de 15 segundos com hook, desenvolvimento e CTA;
- gerar a imagem no Grok/Flow, baixar, anexar no lugar certo;
- gerar o vídeo, conferir duração e resolução;
- escrever legenda com hashtags;
- publicar no TikTok Studio, uma cor por vez, sem perder o controle do que já subiu;
- depois, voltar no Studio para ver o que performou e decidir o que repetir.

Feito à mão, isso vira planilha, pasta bagunçada e retrabalho. A Fábrica transforma esse processo em **um fluxo guiado com estado salvo**: cada campanha sabe em que etapa está, o que já foi aprovado e o que ainda falta.

### A decisão central: *local-first* e "IA na sua assinatura"

O projeto foi deliberadamente construído para rodar **no PC**, e não na nuvem. A razão é prática e econômica:

| Decisão | Por quê |
|---|---|
| Banco de dados local (SQLite, arquivo `data/fabrica_tiktok.db`) | Não depende de servidor, não tem mensalidade, os dados são seus. |
| Mídia em pasta local (`media/campanha-XXXX/`) | Vídeos são pesados; subir tudo para nuvem seria lento e caro. |
| Textos (prompts, roteiros, legendas) gerados por **regras determinísticas em Python**, não por API paga de LLM | Custo zero por campanha, resultado previsível e reproduzível, funciona offline. |
| Imagem e vídeo gerados **manualmente** no Grok Imagine / Google Flow | Você já paga essas assinaturas. Chamar API de geração custaria de novo, por peça. |
| Publicação **manual** no TikTok Studio | Automação de postagem viola termos e arrisca a conta. O app prepara tudo e abre a página; o clique final é humano. |

Em resumo: **o app automatiza a organização e a escrita; a criação visual e a publicação continuam humanas de propósito.**

---

## 3. Escopo

### 3.1 O que está dentro do escopo (o que o app faz)

**Produção multi-cor**
- Você informa várias cores no briefing (`Branco, Preto, Azul Marinho…`).
- O app cria automaticamente **um pacote por cor**: prompt de imagem, prompt de vídeo, falas do roteiro e legenda.
- Regra importante: a IA **nunca** recebe todas as cores no mesmo prompt de imagem (senão ela mistura as cores na mesma peça).

**Modelo fixa e consistência de identidade**
- Uma foto de referência da modelo é anexada e reutilizada entre campanhas.
- Biblioteca de fotos padrão por nicho (`services/model_library.py`).
- **Ficha de consistência de personagem** (`services/character_sheet.py`): um prompt mestre com bloqueio de identidade e lista de negativos ("rosto diferente", "deriva de identidade", "CGI"…) para gerar no Grok uma ficha de referência da modelo.

**Roteiro de 15 segundos**
- Estrutura fixa: **Hook (0–4s) → Desenvolvimento (4–12s) → CTA (12–15s)**.
- As falas variam por cor.
- Botões para regenerar só o hook + legenda, ou a fala inteira, sem recomeçar a campanha.

**Imagens e vídeos**
- Um slot de imagem e um slot de vídeo **por cor**.
- Aprovação em lote: só libera quando todas as cores têm arquivo.
- Conferência de duração (~15s) e resolução alvo (1080×1920 no Flow, 720×1280 no Grok).
- **Misturador de vídeos** (`services/video_mix.py`): junta 2+ MP4s da campanha em um único vídeo ~15s 9:16 usando FFmpeg.
- **Preview 9:16** com scrubber e marcação dos beats do roteiro.

**Legendas e hashtags**
- Legenda alinhada a produto, benefício, público e cor.
- Máximo de **5 hashtags**, escolhidas pelo nicho.

**Publicação (fila por cor)**
- Abas por cor: copiar legenda → copiar caminho do MP4 → abrir o Studio → registrar.
- A campanha só fecha como `published` quando **todas** as cores forem registradas.

**Resultados, métricas e playbook**
- Coleta de métricas do TikTok Studio via Playwright/Chrome CDP (`services/studio_metrics.py`).
- Auditoria em lote de posts de um período.
- **Playbook** (`services/playbook.py`): a partir da auditoria, monta um guia do que repetir (que tipo de hook, que nicho, que formato performou).
- **Fila de hoje (5 posts)** gerada a partir do playbook.
- **Insights locais** (`services/insights.py`): crítica heurística do roteiro (hook fraco? CTA sem verbo? sem urgência?) — sem inventar dados de plataforma.

**Multi-creator**
- Cada PC tem sua própria identidade em `data/studio_identity.json` (nome do estúdio, modelo, @handle, perfil do Chrome).
- `browser_profiles/` e `data/` **nunca** são copiados entre creators.

### 3.2 O que está deliberadamente fora do escopo

- ❌ Não chama API paga de imagem/vídeo. Usa Flow/Grok da sua assinatura, manualmente.
- ❌ Não clica em "gerar", não escolhe produto no Shop, não faz login por você.
- ❌ Não publica sozinho no TikTok, não marca produto, não agenda post.
- ❌ Não usa reconhecimento facial automático — a consistência da modelo é por prompt + revisão humana.
- ❌ Não é um site hospedado (Vercel/serverless). Depende de disco local, SQLite e Chrome no Windows.
- ❌ Não faz montagem criativa completa de vídeo por IA. O mixer atual apenas corta, normaliza e reúne clipes escolhidos pelo operador. O empacotamento em EXE ficou para depois.

---

## 4. Como o sistema é montado (arquitetura)

Pense em três camadas:

```
   [ NAVEGADOR ]  ← a tela que você usa
        │  React + Vite  (frontend/)
        │  fala por HTTP com…
        ▼
   [ SERVIDOR LOCAL ]  ← o cérebro, roda no seu PC
        │  Flask (app.py) + módulos em services/
        │  guarda tudo em…
        ▼
   [ DISCO DO PC ]
        data/fabrica_tiktok.db   (banco SQLite)
        media/campanha-XXXX/     (imagens e vídeos)
        browser_profiles/        (sessões do Chrome)
```

E, ao lado, os serviços externos que **você** opera manualmente:

```
   Grok Imagine / Google Flow  →  gera imagem e vídeo
   TikTok Studio               →  publica e fornece métricas
```

| Camada | Tecnologia | Arquivo principal |
|---|---|---|
| Interface | React + Vite | `frontend/src/App.jsx`, `components.jsx` |
| API / servidor | Flask (Python) | `app.py` (2.417 linhas, 65 rotas HTTP) |
| Banco | SQLite | `data/fabrica_tiktok.db` |
| Mídia | Sistema de arquivos | `media/campanha-XXXX/` |
| Navegador assistido | Chrome/Edge + Playwright (CDP) | `services/browser_assistant.py` |
| Vídeo | FFmpeg | `services/video_mix.py` |

**Por que Flask + SQLite e não algo maior?** Porque o app serve **um usuário em um PC**. Um banco em arquivo e um servidor de processo único são a escolha certa: zero configuração, zero infra, backup é copiar um arquivo.

**Por que React se é um app local?** Porque a tela tem muito estado ao vivo (etapas, slots por cor, uploads, previews). Fazer isso em HTML puro daria muito mais código. O React é compilado uma vez (`npm run build`) e o Flask serve o resultado — não precisa de Node rodando no dia a dia.

---

## 5. Mapa de arquivos — o que cada um faz

### 5.1 Raiz do projeto

| Arquivo | O que é |
|---|---|
| `app.py` | **O servidor.** Cria o app Flask, monta/migra o banco SQLite, define as 65 rotas HTTP, valida uploads, controla transições de status e versionamento das campanhas. |
| `launcher.py` | Iniciador do Windows. Procura uma porta livre entre 5050–5059, reaproveita um servidor já rodando (checa `/api/health` com `version: 6`), sobe o Flask e abre o navegador. Também imprime o endereço de LAN para acessar do celular no mesmo Wi‑Fi. |
| `iniciar.vbs` | Duplo clique para subir tudo sem janela preta de terminal. |
| `reiniciar-fabrica.bat` | Encerra o processo `pythonw.exe` daquele diretório e sobe de novo — atalho para reiniciar completamente o servidor. |
| `instalar.ps1` | Instala dependências Python e Node e compila a interface. |
| `requirements.txt` | Lista de bibliotecas Python. |
| `studio_identity.example.json` | Modelo do arquivo de identidade por PC (o real fica em `data/`, fora do Git). |
| `.gitignore` | Impede que dados, mídia, perfis de navegador, `.venv` e segredos vão parar no GitHub. |
| `README.md` | Visão geral e instruções de uso. |
| `INVENTARIO-FABRICA-E-PLANOS.md` | Resumo do estado atual + planos. |
| `COMO-INSTALAR-NO-OUTRO-PC.md` | Passo a passo para instalar para outra creator. |
| `DOCUMENTACAO-PROJETO.md` | **Este documento.** |

### 5.2 `services/` — a lógica separada do servidor

Cada arquivo aqui resolve **um assunto**, para que `app.py` só precise coordenar.

| Arquivo | Linhas | O que faz |
|---|---:|---|
| `prompts.py` | 1.374 | **O coração da escrita.** Gera, por regras determinísticas, os prompts de imagem e vídeo, as falas do roteiro (hook/desenvolvimento/CTA) e as legendas — um pacote por cor. Inclui normalização para pt-BR (troca "workout" por "treino de academia", "close-up" por "detalhe de perto"), extração de características do produto, sinais de persuasão, direção de gestos e CTAs variados. Nenhuma API paga. |
| `studio_metrics.py` | 1.394 | Raspagem do TikTok Studio com Playwright: página de conteúdo e página de analytics por vídeo. Lê os atributos `data-tt` do DOM (VideoInfoCard, VideoMetricsCard) para extrair views, watch %, likes, saves etc. |
| `browser_assistant.py` | 1.074 | Abertura assistida de navegador. Grok e Flow abrem em **Chrome comum** (sem Playwright, para downloads não travarem a janela); o Studio reutiliza o perfil local configurado. Também cuida de vigiar a pasta de downloads e rotear o arquivo baixado para a campanha certa. **Não clica em gerar, não faz login, não publica.** |
| `playbook.py` | 423 | Transforma um relatório de auditoria em lote num **playbook de replicação**: agrupa por nicho/formato, calcula medianas de views e watch%, e diz o que repetir. |
| `model_library.py` | 256 | Biblioteca de fotos de referência da modelo organizada por nicho (praia, academia, casual, dia-a-dia, íntima, fantasia) e os valores padrão sugeridos de cada nicho no briefing. |
| `insights.py` | 236 | Crítico local do roteiro: procura verbos de CTA, sinais de urgência, tamanho do hook. Gera recomendações **sem inventar dados do TikTok**. |
| `character_sheet.py` | 148 | Prompt mestre em português para gerar no Grok uma ficha de consistência de personagem, com bloqueio de identidade e um `NEGATIVE_PROMPT` extenso contra deriva de rosto, CGI, mãos malformadas etc. |
| `copywriter.py` | 372 | Escrita opcional das falas por modelo de linguagem (OpenAI ou Gemini), com auditoria local: orçamento por trecho, nenhum atributo de desempenho fora do briefing, urgência só com oferta real. Se a resposta falhar ou for reprovada duas vezes, o sistema usa o texto determinístico. A chave fica em `data/llm.json`, fora do Git, e nunca volta pela API. |
| `video_mix.py` | 125 | Concatena/corta MP4s da campanha em um único vídeo ~15s 9:16 via FFmpeg. Localiza o FFmpeg por `FFMPEG_PATH`, pelo PATH ou no caminho padrão do WinGet. |
| `media.py` | 95 | Valida o **conteúdo** dos arquivos (imagem via Pillow, estrutura de caixas do MP4) em vez de confiar na extensão do nome. É uma proteção contra arquivo corrompido ou renomeado. |
| `setup_status.py` | 92 | Checklist de primeira execução: identidade preenchida? fotos por nicho? perfis de navegador usados? |
| `studio_identity.py` | 64 | Identidade por máquina (estúdio, modelo, @handle, dica de perfil do Chrome), lida/gravada em `data/studio_identity.json`. |

### 5.3 `frontend/src/` — a interface

| Arquivo | Linhas | O que faz |
|---|---:|---|
| `components.jsx` | 1.810 | Todos os blocos da tela: `VariantList` (cartões por cor), `PublishQueue` (fila de publicação), `VideoMixer`, `VideoTimelinePreview` (preview 9:16 com beats), `GateCriticoPanel`, `PerformancePanel`, `BriefForm`, `StudioIdentityPanel`, `WriterSettingsPanel`, `SetupChecklist`, `DailyQueueCard`, `ModelLibraryPanel`, `ResultsQuickTools`. |
| `App.jsx` | 667 | A casca do app: navegação por hash (`#/inicio`, `#/produzir/<id>/<etapa>`, `#/resultados/<aba>`), carregamento das campanhas, controle de "sujo/descartar", indicação de quem escreveu o roteiro e o `Panel` que decide o que mostrar em cada etapa. |
| `styles.css` | 4.702 | Sistema visual completo: tokens, temas claro/escuro, componentes, estados, responsividade e acabamento para computador e celular. |
| `api.js` | 109 | Ponte com o servidor: função `api()` (que envia o cabeçalho `X-Local-App`), lista de status, rótulos em português e a definição das 9 etapas do pipeline. |
| `nicheDefaults.js` | 62 | Valores padrão por nicho no formulário de briefing. |
| `serviceLogos.js` | — | Logos do TikTok/TikTok Studio embutidos como base64, para a tela não depender de requisição externa de imagem. |
| `serviceLinks.jsx` | — | Botões de abrir Grok/Flow/TikTok que **mudam de comportamento no celular**: no PC chamam o servidor (perfil de Chrome certo); no celular viram links nativos, para o iOS/Android entregar ao aplicativo instalado quando houver associação. |
| `device.js` | 26 | Detecta iPhone, iPad, Android ou computador, inclusive o caso do iPad que se identifica como Mac. Uma janela pequena ou uma tela de toque, sozinhas, não classificam um computador como celular. |
| `Canvas.jsx` | 53 | Resto do canvas visual original. |
| `main.jsx` | 6 | Ponto de entrada do React. |

### 5.4 Pastas de apoio

| Pasta | Conteúdo |
|---|---|
| `data/` | Banco SQLite, identidade, backups. **Fora do Git. Nunca copiar entre creators.** |
| `media/campanha-XXXX/` | Referências, imagens por cor, vídeos por cor, downloads. Fora do Git. |
| `browser_profiles/` | Sessões do Chrome: `flow-maaiquels`, `grok-maaiquels`, `micaela-cdp`, `tiktok-micaela`, `tiktok-metrics`. Fora do Git. |
| `tests/` | `test_app.py` (577 linhas) e `test_browser_assistant.py` (110 linhas). |
| `reports/` | Relatórios de auditoria — hoje `prompt-audit-2026-09-12/evidence.json`, com o antes/depois dos prompts gerados. |
| `outputs/` | Plano de migração e protótipos HTML do fluxo. |
| `work/` | Cópias do `app.py` e `README.md` de antes da migração. |
| `_patch/` | ~60 scripts Python de patch usados durante o desenvolvimento (ex.: `apply_multi_image.py`, `fix_studio_jsx.py`). Ignorado pelo Git. |

---

## 6. Banco de dados

Seis tabelas em `data/fabrica_tiktok.db`:

| Tabela | Guarda |
|---|---|
| `campaigns` | A campanha: nome, modelo, produto, cores, público, benefício, ângulo, tom, estilo, movimentos, nicho, `status`, `generator` (flow/grok), `version`, `layout`, `checklist`, `published_url`. |
| `campaign_variants` | **Um registro por cor** da campanha, com o pacote de prompts daquela cor. É o que permite a produção multi-cor. |
| `assets` | Arquivos: `reference`, `image` ou `video`, com `slot` (a cor), tamanho, mime, metadados e `approved_at`. |
| `product_assets` | Até 8 fotos do produto por campanha. |
| `prompts` | Prompts da campanha quando não há variação por cor. |
| `steps` | Quais etapas foram concluídas e quais tiveram revisão humana. |

**Detalhe de engenharia:** o esquema é auto-migrável. Na inicialização o `app.py` lê `PRAGMA table_info(campaigns)` e adiciona por `ALTER TABLE` qualquer coluna nova que ainda não exista. Por isso dá para atualizar o app sem perder o banco.

**Status possíveis de uma campanha:**
`briefing` → `image_ready` → `image_approved` → `script_ready` → `video_ready` → `video_approved` → `ready_to_publish` → `published`

**Etapas na tela:**
`model` → `look` → `image` → `image_approval` → `script` → `video` → `video_approval` → `studio` → `performance`

---

## 7. A API (65 rotas HTTP)

Agrupadas por assunto:

**Páginas e estáticos** — `/`, `/creator`, `/gate/`, `/assets/<arquivo>`, `/brand/<arquivo>`, `/favicon.svg`, `/api/health`

**Campanhas** — listar/criar/ler/apagar/editar campanha, `look`, `duplicate`, `copy`, `layout`, `transition`, `package.<fmt>` (exportar TXT/ZIP)

**Geração de texto** — `generate`, `variants/generate`, `prompts` (PATCH), `prompts/refresh`, `variants/<id>/refresh`, `variants/<id>/prompts`

**Arquivos** — `assets` (upload), `assets/<id>/file`, `product-assets/<id>/file`, `reference`, `references`

**Biblioteca da modelo** — `model-library` (GET/POST), `model-library/file`, `model-library/label` (PATCH), `model-library/character-sheet` (GET), `model-library/character-sheet/open` (POST), `reference-from-library`

**Vídeo** — `videos/mix`, `autocut`, `autocut/pending`, `autocut/<job>/dispatched`

**Publicação e resultados** — `publish-slot`, `published-link`, `performance`, `performance/fetch`, `insights`

**Studio** — `studio/open`, `studio/analyze-link`, `studio/link-analyses`, `studio/audit`, `studio/audit/latest`, `studio/playbook` (GET/POST), `studio/playbook/campaign`, `studio/identity` (GET/PATCH)

**Sistema** — `setup-status`, `productivity` (fila de 5 posts do dia), `browser/open-free`, `campaigns/<id>/browser`

**Proteção:** as mutações exigem o cabeçalho `X-Local-App: fabrica-tiktok` e há validação de host (`_host_allowed`) — para que outra página aberta no navegador não consiga mexer no seu banco local.

---

## 8. Fluxo de uso, do início ao fim

1. **Nova campanha** — briefing (produto, cores separadas por vírgula, público, benefício, ângulo, nicho) e escolha do gerador: Flow (1080×1920) ou Grok (720×1280).
2. **Modelo fixa** — anexe a referência ou reutilize da biblioteca/de outra campanha.
3. **Definir look** — produto, cores, movimentos, até 8 fotos do produto → **Gerar prompts e roteiro** (cria um pacote por cor).
4. **Criar imagem** — abra o Grok/Flow, gere e anexe **uma imagem por cor**.
5. **Aprovar imagens** — checagem de identidade e de look; libera só com todas as cores preenchidas.
6. **Roteiro 15s** — revise as falas; use "Atualizar hook + legenda" ou "Atualizar fala inteira" se não gostar.
7. **Criar vídeo** — um MP4 de 15s por cor; opcionalmente use o **Misturar vídeos** (FFmpeg).
8. **Aprovar vídeos** — conferência de duração e resolução, com preview 9:16.
9. **Preparar publicação** — fila por cor: legenda (≤5 hashtags) + caminho do MP4 → abrir Studio → registrar.
10. **Resultados** — coletar métricas, auditar o lote, gerar playbook, criar a próxima campanha a partir dele.

---

## 9. Inteligência aplicada aos prompts

Esta é a parte mais trabalhada do projeto. O gerador não deve apenas preencher um modelo de texto: ele precisa separar instrução visual, direção de cena e fala humana, usar os fatos disponíveis e impedir que a IA invente qualidades do produto.

### 9.1 Briefing estruturado

O briefing reúne nome, modelo, nicho, produto, fotos do produto, cores, público, benefício, objeção, oferta, ângulo, tom, estilo, detalhes e movimentos. Escolher um nicho preenche sugestões editáveis; o operador continua vendo o gerador e pode trocar entre Flow e Grok sem abrir a área avançada.

O sistema reconhece detalhes úteis presentes no texto, entre eles:

- materiais como poliamida, courino, algodão, lã, elastano e poliéster;
- componentes como botões, bolsos, cós, alças, barras e acabamentos;
- linguagem feminina, masculina ou unissex;
- argumentos de economia, qualidade, versatilidade, autoestima e ocasiões de uso;
- objeções reais, como transparência, peça que escorrega, tamanho, aparência barata ou desconforto;
- oferta real, que é a única fonte permitida para urgência comercial.

### 9.2 Prompt de imagem

Cada cor recebe um prompt isolado. O texto instrui o gerador a usar primeiro a modelo fixa e depois as fotos do produto, tratando pessoas de catálogo apenas como referência da peça.

Para a primeira cor, a fotografia da modelo funciona como base da nova imagem. Para as cores seguintes, a imagem aprovada da primeira cor também funciona como referência de cenário. A regra de **edição localizada** pede que somente a região da roupa seja alterada e preserva rosto, corpo, pose, expressão, cabelo, mãos, top, calçados, enquadramento, distância, perspectiva, objetos, sombras, reflexos, iluminação, granulação e qualidade fotográfica.

A seção de integração fotográfica exige dobras, tensão do tecido, oclusão correta pelas mãos e pelo corpo, sombra de contato e bordas naturais. Isso foi criado para evitar o aspecto de pessoa ou roupa colada sobre o cenário. O fundo permanece reconhecível e nítido entre campanhas; o prompt proíbe troca de locação e desfoque artificial.

O prompt de imagem recebe apenas informação útil para uma fotografia estática. Marcas de tempo, roteiro, CTA, legenda, `FYP`, `frame`, `MP4` e direção de vídeo são filtrados antes da montagem. O final reforça que deve ser gerada uma única imagem e que não devem ser descritas falas ou duração.

### 9.3 Roteiro falado de 15 segundos

O roteiro usa três blocos com orçamento de palavras:

| Trecho | Janela | Função |
|---|---:|---|
| Hook | 0–4s | Começar com uma dúvida, objeção, desejo ou situação específica do produto. |
| Desenvolvimento | 4–12s | Explicar uma vantagem observável em linguagem natural. A demonstração visual fica na direção de cena e não é lida pela modelo. |
| CTA | 12–15s | Pedir uma ação compatível com o TikTok Shop, como tocar no produto marcado e escolher tamanho/cor. |

Foram removidas construções artificiais como “Para mulheres de 20 a 40 anos” e frases que mandavam a modelo falar instruções de câmera ou “mostre o produto”. O público orienta a linguagem internamente, sem ser recitado. Termos em inglês são convertidos para português do Brasil quando há equivalente natural.

O motor local combina famílias de hooks, desenvolvimentos e CTAs, elimina duplicatas e usa um índice de variação. Os botões de atualizar hook + legenda, atualizar fala inteira e editar manualmente preservam as outras partes que não foram solicitadas. A interface mostra se o roteiro veio do motor local ou do redator opcional.

Na etapa 5 existe um bloco visível chamado **Escrita por API**. Quando a OpenAI está ativa, o botão principal **Gerar roteiro com ChatGPT** chama explicitamente a API para criar hook, desenvolvimento, CTA e legenda. Em campanhas com várias cores, cada cartão possui o botão **Gerar esta cor com ChatGPT**. As alternativas locais aparecem separadas e identificadas como ações sem uso de API. Se a chave ainda não estiver ativa, a mesma área oferece **Configurar ChatGPT**.

### 9.4 Redator opcional por IA

O projeto funciona sem nenhuma API paga. Quando o operador configura OpenAI ou Gemini em **Redator**, `services/copywriter.py` envia um briefing textual e pede somente `hook`, `development` e `cta`. Uma auditoria local rejeita:

- atributos e promessas ausentes no briefing;
- urgência sem oferta confirmada;
- falas longas demais para 15 segundos;
- títulos, instruções de cena ou metalinguagem dentro da fala;
- resposta incompleta ou formato inválido.

A chamada pede três conceitos diferentes em uma única resposta e escolhe localmente o melhor candidato aprovado. A seleção favorece história em primeira pessoa, quebra da objeção e ocasião real de uso. Ela rejeita pergunta genérica, direção de câmera pronunciada, idade do público recitada, repetição exata do roteiro anterior e CTA que apenas repete a cor. Ao regenerar, o roteiro atual entra no briefing como conteúdo que não deve ser repetido.

Há até duas tentativas. Se o provedor falhar ou a auditoria reprovar a resposta, o motor determinístico local assume automaticamente. A chave fica em `data/llm.json`, não é versionada e não é devolvida ao navegador.

### 9.5 Prompt de vídeo

O vídeo recebe a imagem aprovada da cor como primeiro quadro e referência contínua. O texto separa explicitamente:

- **falas**, que são as únicas frases entre aspas a serem pronunciadas;
- **coreografia**, executada sem ser lida;
- **câmera e enquadramento**;
- **provas visuais** ligadas somente a atributos confirmados;
- **travas de identidade, cenário, produto e continuidade**.

Cada fato confirmado ganha um gesto que possa demonstrá-lo. A coreografia limita uma ação por batida para reduzir movimentos artificiais. O encerramento passou a definir uma ação concreta e natural: mãos relaxadas ou tocando a peça, olhar para o produto marcado e pose estável. Essa mudança resolve a tendência do gerador de encerrar sempre com braços levantados, aceno ou gesto de comemoração.

O vídeo preserva o cenário da imagem aprovada, a posição da câmera, a perspectiva e a iluminação. Movimentos de câmera existem apenas quando ajudam a mostrar o produto e não devem quebrar a continuidade.

### 9.6 Legendas e hashtags

As legendas usam produto, cor, detalhe comprovado e uma ação de loja. A geração corrige contrações do português, evita expressões como “repara em a”, não recita idade e remove hashtags repetidas mesmo quando diferem apenas entre maiúsculas e minúsculas. O limite atual é de cinco hashtags relevantes.

### 9.7 Evidência e prevenção de regressões

`reports/prompt-audit-2026-09-12/evidence.json` guarda um caso de auditoria com briefing e saída exata. Os testes cobrem materiais, unissex, objeção, oferta, fatos negativos, divisão por cor, primeiro cenário versus cores seguintes, ausência de direção de vídeo no prompt de imagem, pontuação, tamanho de hook, orçamento de fala, gesto final, CTA de TikTok Shop e fallback do redator.

---

## 10. O que foi criado e modificado

### 10.1 Fundação e fluxo de produção

- Aplicativo local Flask + React + SQLite, com dados e mídia preservados no computador.
- Canvas de produção transformado em um stepper linear, com pré-requisitos e revisões humanas.
- Upload validado por conteúdo, biblioteca da modelo, fotos do produto e reutilização de referência.
- Exportação de campanha em TXT e pacote ZIP apenas com mídia aprovada.
- Controle de versão para evitar que duas abas sobrescrevam mudanças uma da outra.
- Edição, renomeação, cópia, exclusão e criação de uma versão editável de campanha publicada.
- Correção da rota que criava versão editável e anteriormente terminava em página não encontrada.

### 10.2 Variações, imagem e vídeo

- Uma variação independente por cor, com prompt, imagem, roteiro, vídeo, legenda e publicação próprios.
- Bloqueio de avanço quando falta arquivo ou aprovação de alguma cor.
- Correção específica do caso de uma única cor/um único vídeo que ficava preso em “Aprove todos os vídeos”.
- Migração idempotente que recupera aprovações de vídeo feitas por versões antigas.
- Exibição imediata da imagem recém-anexada na etapa Criar imagem; antes ela só aparecia na aprovação.
- Remoção da duplicação visual do cartão do Grok e das referências na etapa de imagem.
- Mixer local de dois ou mais clipes via FFmpeg e prévia vertical com linha do tempo.

### 10.3 Copy, imagem e direção de vídeo

- Separação total entre prompt de imagem, prompt de vídeo, roteiro falado e legenda.
- Reescrita do motor de copy para produto, material, componentes, ocasião, objeção, oferta e benefício.
- Variações de hook deduplicadas, desenvolvimento sem recitar idade e CTA com vocabulário real da loja.
- Filtro de termos de produção em inglês nas falas e normalização para português do Brasil.
- Auditoria contra promessas inventadas e falsa urgência; “acabamento” e expressões de entusiasmo deixaram de gerar falsos positivos.
- Trava de modelo, edição localizada da roupa, cenário fixo e integração fotográfica realista.
- Direção de gestos ligada às provas do produto, âncora das mãos e final natural.
- Redator opcional OpenAI/Gemini com teste de conexão, mensagem de erro real, adaptação do payload, auditoria e fallback local.
- Identificação visível da origem do roteiro na interface.
- Botão explícito de geração por API na etapa Roteiro de 15s, incluindo geração individual por cor; os botões locais foram renomeados para deixar claro que não consomem API.

### 10.4 Navegador e serviços externos

- Perfis dedicados e persistentes do Chrome para Flow, Grok e TikTok Studio.
- Migração completa dos cinco perfis para `Fabrica TikTok/browser_profiles`; a pasta antiga não existe mais.
- Grok e Flow abertos no Chrome nativo para manter login e downloads estáveis.
- TikTok Studio aberto no perfil local configurado, com mensagens específicas quando o Chrome/perfil não é encontrado.
- Monitoramento das pastas de download e associação do arquivo baixado à campanha.
- Botões separados para TikTok Studio e TikTok.
- Detecção de iPhone, iPad, Android e computador: no computador, o Studio abre pelo servidor e perfil dedicado; no celular, os botões usam links que podem ser entregues aos aplicativos instalados.
- Logos incorporados em base64 e rótulos curtos na interface.
- Cópia para a área de transferência com alternativa compatível com navegadores móveis.

### 10.5 Publicação, resultados e aprendizado

- Fila de publicação por cor com legenda, caminho do vídeo e registro do slot publicado.
- Campo para salvar o link do TikTok mesmo depois da publicação.
- Coleta assistida de views, curtidas, retenção, tráfego, buscas e audiência no TikTok Studio.
- Auditoria em lote e relatório do que performou melhor.
- Insights heurísticos, playbook de replicação e criação de nova campanha a partir do playbook.
- Fila diária de cinco conteúdos e checklist de configuração inicial.
- Gate crítico e prévia 9:16 para revisão antes da publicação.

### 10.6 Interface, celular e operação

- Navegação principal em Início, Produzir e Resultados.
- Rotas por hash que permitem retornar diretamente à campanha e etapa.
- Gerador Flow/Grok visível na etapa Definir look, fora da seção avançada.
- Layout responsivo, tokens de design, temas claro/escuro e estados visuais de sucesso, espera e erro.
- Acesso por celular na mesma rede local, protegido por PIN de quatro dígitos.
- `reiniciar-fabrica.bat` para encerrar apenas o servidor deste projeto e iniciá-lo novamente.
- Renomeação da pasta do projeto para `Fabrica TikTok`, com referências internas e perfis de navegador migrados.
- Backup diário do SQLite antes e depois das migrações, mantendo até dez cópias.

### 10.7 Histórico Git consolidado

A base examinada estava limpa e sincronizada com `main`/`origin/main` no commit `2be3344`; este documento passa a ser a única alteração local. Até esta revisão, existem 21 commits de produto:

| Período | Commits | Entrega principal |
|---|---:|---|
| Base local | `9f13081` a `a45c44d` | Aplicativo, fluxo, uploads, mixer, preview, performance e crítico. |
| Studio e métricas | `8103a20` a `8189ecf` | Coleta por CDP, scraper por `data-tt` e auditoria em lote. |
| Operação multi-creator | `d668354` | Identidade, stepper, fila diária, setup, playbook e instalação em outro PC. |
| Grande revisão | `505da07` e `3762de9` | Prompts, personagem, navegador nativo, celular e relatório técnico. |
| Copy e interface | `aa78bd4` a `8d84442` | Motor por gatilho, backup, temas, PIN, final de vídeo, gestos e enquadramento. |
| Redator opcional | `a64ed95` a `e91611c` | OpenAI/Gemini, fallback, erros claros, identidade e origem do roteiro. |
| Refinamento final | `516ad6a` e `2be3344` | Auditoria sem falso positivo e CTA no vocabulário do TikTok Shop. |

O arquivo `work/` mantém instantâneos anteriores à migração. Os protótipos e planos ficam em `outputs/`; eles servem como histórico e não fazem parte da execução diária.

---

## 11. Como instalar, iniciar e reiniciar

**Uso diário (Windows)**
```
Duplo clique em iniciar.vbs  →  abre http://127.0.0.1:5050
```
Se travar: duplo clique em `reiniciar-fabrica.bat`.

**Pelo terminal**
```powershell
cd "C:\Users\Admin\Documents\Codex\2026-09-10\Fabrica TikTok"
.\.venv\Scripts\python.exe app.py
```

**Reinício completo**

Use `reiniciar-fabrica.bat`. Ele procura processos `pythonw.exe` cuja linha de comando aponta para esta pasta, encerra somente esses processos, espera um segundo e chama `iniciar.vbs` novamente.

**Desenvolvimento**
```powershell
.\.venv\Scripts\python.exe app.py          # API
cd frontend && npm run dev                  # UI com recarregamento automático
cd frontend && npm run build                # compila a UI que o Flask serve
.\.venv\Scripts\python.exe -m unittest discover -s tests -v   # testes
```

**Instalar em outro PC** — ver `COMO-INSTALAR-NO-OUTRO-PC.md`. Requer Python 3.11+, Node 20.19+ ou 22.12+, Chrome/Edge, Git e FFmpeg no PATH.

**Do celular, no mesmo Wi‑Fi** — `http://IP-DO-PC:5050` (o `launcher.py` imprime o endereço). Desligue com `FABRICA_LAN=0` se quiser restringir a 127.0.0.1.

---

## 12. Privacidade, segurança e separação entre creators

- Tudo fica no PC: banco, mídia, perfis de navegador.
- `.gitignore` exclui `data/`, `media/`, `browser_profiles/`, `.venv/`, `.env`, `*.db`, `node_modules/`, `frontend/dist/`, `_patch/`.
- **Nunca copiar entre creators:** `browser_profiles/` (levaria a sessão de Chrome errada) e `data/` (banco, identidade, históricos).
- Cada PC define sua identidade em `data/studio_identity.json` pelo ícone de Identidade no cabeçalho.
- Mutações vindas de outras origens são bloqueadas por validação de host + cabeçalho `X-Local-App`.
- No computador local não há tela de PIN. Pela rede Wi‑Fi, o PIN fica salvo em cookie por até 30 dias.
- As respostas usam `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer` e `X-Frame-Options: DENY`.
- A interface e a API usam `Cache-Control: no-store` nas áreas sensíveis para evitar uma versão antiga depois do reinício.

---

## 13. Validação, limitações conhecidas e próximos passos

**Limitações**
- A raspagem do TikTok Studio depende do DOM deles; se o TikTok mudar a interface, quebra (há retries e mensagem clara, mas exige ajuste no `studio_metrics.py`).
- Depende de Windows, Chrome instalado e FFmpeg no PATH para o mixer.
- A geração de imagem/vídeo continua manual, por escolha de projeto.

**Estado dos testes (12/09/2026, nesta revisão)**

Foram executados **81 testes e todos terminaram como `OK`**. O teste de backup foi corrigido para fechar explicitamente a conexão SQLite no Windows. Ao encerrar a suíte ainda aparecem avisos de tarefas assíncronas dos observadores de download que estavam pendentes; eles não falharam nenhum cenário, mas continuam como oportunidade de limpeza técnica.

A cobertura inclui fluxo completo, migração, backup, autenticação LAN, segurança de origem, upload atômico, troca de referência, edição e duplicação, variações por cor, prompts, redator opcional, aprovações, publicação, exportação e perfis de navegador.

Duas decisões de produto estão registradas nos testes: resolução e duração fora do alvo **avisam, mas não bloqueiam** a aprovação do vídeo; editar apenas a legenda exige preparar a publicação novamente sem invalidar o vídeo aprovado.

**Próximos passos previstos**
- Cancelar/aguardar os observadores de download ao desmontar o assistente de navegador, eliminando os avisos ao final dos testes.
- Empacotamento em EXE (PyInstaller) ou Tauri/Electron.
- Possivelmente limpar `_patch/` e `work/`, que são resíduo do desenvolvimento.
- Unificar os dois caminhos de publicação (`transition` e `publish-slot`).
- Reduzir as oito larguras de breakpoint para três, testando cada faixa com o app aberto.
- Criar testes automatizados de interface para o fluxo completo em computador e iPhone; hoje a maior parte da UI é validada manualmente.
- Manter os seletores do TikTok Studio atualizados quando a plataforma mudar o DOM.

---

## 14. Glossário

| Termo | O que significa aqui |
|---|---|
| **API / rota** | Um "endereço" interno que a tela chama para pedir algo ao servidor, ex.: `/api/campaigns`. |
| **Backend / servidor** | O programa Python (Flask) que roda escondido no seu PC e faz o trabalho pesado. |
| **Frontend** | A parte visual, que roda no navegador. |
| **SQLite** | Banco de dados que é um único arquivo no disco. Backup = copiar o arquivo. |
| **Commit** | Uma "foto" salva do projeto no histórico do Git. Enquanto não há commit, a mudança não está protegida. |
| **Determinístico** | O mesmo briefing sempre gera o mesmo texto. Previsível, sem surpresa e sem custo de IA. |
| **Playwright / CDP** | Ferramenta que controla o Chrome por programa. CDP é o canal que permite conversar com um Chrome já aberto. |
| **Scraping / raspagem** | Ler informação direto da página web, já que não há API oficial disponível. |
| **DOM** | A estrutura interna de uma página web; é nela que o scraper procura os números. |
| **FFmpeg** | Programa de linha de comando que corta, junta e converte vídeo. |
| **Hook / CTA** | Hook = os primeiros segundos que prendem a atenção. CTA = a chamada para ação ("toque no link"). |
| **9:16** | Formato vertical de tela cheia do celular (ex.: 1080×1920). |
| **Slot** | O "lugar reservado" de uma cor dentro da campanha — cada cor tem seu slot de imagem e de vídeo. |
| **UGC** | *User Generated Content* — vídeo com cara de conteúdo de pessoa real, não de anúncio. |

---

*Fim do documento.*
