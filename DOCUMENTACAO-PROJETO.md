# Fábrica TikTok — Documentação do Projeto

**Documento gerado em:** 2026-09-12
**Pasta do projeto:** `C:\Users\Admin\Documents\Codex\2026-09-10\Fabrica TikTok`
**Repositório:** https://github.com/maaiquels2/tiktok-automated
**Como abrir:** duplo clique em `iniciar.vbs` → http://127.0.0.1:5050

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
- ❌ Montagem automática de vídeo e empacotamento em EXE ficaram para depois.

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
| API / servidor | Flask (Python) | `app.py` (2.221 linhas, 60 rotas) |
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
| `app.py` | **O servidor.** Cria o app Flask, monta/migra o banco SQLite, define as 60 rotas da API, valida uploads, controla transições de status e versionamento das campanhas. |
| `launcher.py` | Iniciador do Windows. Procura uma porta livre entre 5050–5059, reaproveita um servidor já rodando (checa `/api/health` com `version: 6`), sobe o Flask e abre o navegador. Também imprime o endereço de LAN para acessar do celular no mesmo Wi‑Fi. |
| `iniciar.vbs` | Duplo clique para subir tudo sem janela preta de terminal. |
| `reiniciar-fabrica.bat` | **(novo)** Mata o processo `pythonw.exe` daquele diretório e sobe de novo — atalho para quando o servidor trava. |
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
| `prompts.py` | 1.061 | **O coração da escrita.** Gera, por regras determinísticas, os prompts de imagem e vídeo, as falas do roteiro (hook/desenvolvimento/CTA) e as legendas — um pacote por cor. Inclui normalização para pt-BR (troca "workout" por "treino de academia", "close-up" por "detalhe de perto"), extração de características do produto, sinais de persuasão e CTAs variados. Nenhuma API paga. |
| `studio_metrics.py` | 1.394 | Raspagem do TikTok Studio com Playwright: página de conteúdo e página de analytics por vídeo. Lê os atributos `data-tt` do DOM (VideoInfoCard, VideoMetricsCard) para extrair views, watch %, likes, saves etc. |
| `browser_assistant.py` | 1.068 | Abertura assistida de navegador. Grok e Flow abrem em **Chrome comum** (sem Playwright, para downloads não travarem a janela); o Studio usa um clone CDP do perfil da creator. Também cuida de vigiar a pasta de downloads e rotear o arquivo baixado para a campanha certa. **Não clica em gerar, não faz login, não publica.** |
| `playbook.py` | 423 | Transforma um relatório de auditoria em lote num **playbook de replicação**: agrupa por nicho/formato, calcula medianas de views e watch%, e diz o que repetir. |
| `model_library.py` | 256 | Biblioteca de fotos de referência da modelo organizada por nicho (praia, academia, casual, dia-a-dia, íntima, fantasia) e os valores padrão sugeridos de cada nicho no briefing. |
| `insights.py` | 236 | Crítico local do roteiro: procura verbos de CTA, sinais de urgência, tamanho do hook. Gera recomendações **sem inventar dados do TikTok**. |
| `character_sheet.py` | 148 | **(novo)** Prompt mestre em português para gerar no Grok uma ficha de consistência de personagem, com bloqueio de identidade e um `NEGATIVE_PROMPT` extenso contra deriva de rosto, CGI, mãos malformadas etc. |
| `video_mix.py` | 125 | Concatena/corta MP4s da campanha em um único vídeo ~15s 9:16 via FFmpeg. Localiza o FFmpeg por `FFMPEG_PATH`, pelo PATH ou no caminho padrão do WinGet. |
| `media.py` | 95 | Valida o **conteúdo** dos arquivos (imagem via Pillow, estrutura de caixas do MP4) em vez de confiar na extensão do nome. É uma proteção contra arquivo corrompido ou renomeado. |
| `setup_status.py` | 92 | Checklist de primeira execução: identidade preenchida? fotos por nicho? perfis de navegador usados? |
| `studio_identity.py` | 64 | Identidade por máquina (estúdio, modelo, @handle, dica de perfil do Chrome), lida/gravada em `data/studio_identity.json`. |

### 5.3 `frontend/src/` — a interface

| Arquivo | Linhas | O que faz |
|---|---:|---|
| `components.jsx` | 1.716 | Todos os blocos da tela: `VariantList` (cartões por cor), `PublishQueue` (fila de publicação), `VideoMixer`, `VideoTimelinePreview` (preview 9:16 com beats), `GateCriticoPanel`, `PerformancePanel`, `BriefForm`, `StudioIdentityPanel`, `SetupChecklist`, `DailyQueueCard`, `ModelLibraryPanel`, `ResultsQuickTools`. |
| `App.jsx` | 620 | A casca do app: navegação por hash (`#/inicio`, `#/produzir/<id>/<etapa>`, `#/resultados/<aba>`), carregamento das campanhas, controle de "sujo/descartar", e o `Panel` que decide o que mostrar em cada etapa. |
| `styles.css` | 838 | Todo o visual. |
| `api.js` | 109 | Ponte com o servidor: função `api()` (que envia o cabeçalho `X-Local-App`), lista de status, rótulos em português e a definição das 9 etapas do pipeline. |
| `nicheDefaults.js` | 62 | Valores padrão por nicho no formulário de briefing. |
| `serviceLogos.js` | — | **(novo)** Logos do TikTok/TikTok Studio embutidos como base64, para a tela não fazer requisição externa de imagem. |
| `serviceLinks.jsx` | 43 | **(novo)** Botões de abrir Grok/Flow/TikTok que **mudam de comportamento no celular**: no PC chamam o servidor (perfil de Chrome certo); no celular viram link nativo `https://`, para o iOS entregar ao app instalado. |
| `device.js` | 26 | **(novo)** Detecta se é iPhone, iPad, Android, ou computador — inclusive o caso do iPad que se identifica como Mac. Comentário no código deixa claro o critério: "uma janela pequena ou tela de toque sozinha não faz de um computador um celular". |
| `Canvas.jsx` | 53 | Resto do canvas visual original. |
| `main.jsx` | 6 | Ponto de entrada do React. |

### 5.4 Pastas de apoio

| Pasta | Conteúdo |
|---|---|
| `data/` | Banco SQLite, identidade, backups. **Fora do Git. Nunca copiar entre creators.** |
| `media/campanha-XXXX/` | Referências, imagens por cor, vídeos por cor, downloads. Fora do Git. |
| `browser_profiles/` | Sessões do Chrome: `flow-maaiquels`, `grok-maaiquels`, `micaela-cdp`, `tiktok-micaela`, `tiktok-metrics`. Fora do Git. |
| `tests/` | `test_app.py` (577 linhas) e `test_browser_assistant.py` (110 linhas). |
| `reports/` | **(novo)** Relatórios de auditoria — hoje `prompt-audit-2026-09-12/evidence.json`, com o antes/depois dos prompts gerados. |
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

## 7. A API (60 rotas)

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

## 9. O que foi criado e modificado

### 9.1 Histórico de commits (8 commits, todos em 11/09/2026)

| # | Commit | O que entrou |
|---|---|---|
| 1 | `9f13081` | **Fábrica TikTok local completa** — a base: Flask + React + SQLite, pipeline de campanha, multi-cor, uploads, exportação. |
| 2 | `03c0aeb` | **Misturador de vídeos** — API com FFmpeg (`services/video_mix.py`) e a UI na etapa Criar vídeo. |
| 3 | `2f42f7e` | **Studio: performance, insights, preview 9:16, crítico local** — nasce `services/insights.py` e o painel de performance. |
| 4 | `a45c44d` | Correção do JSX do `PerformancePanel` e ligação do Preview com o Crítico local. |
| 5 | `8103a20` | **Coleta de performance via Playwright + Chrome CDP** e acesso direto ao analytics. |
| 6 | `3eadbc5` | **Scraper do Studio** lendo `VideoInfoCard` e `VideoMetricsCard` pelos atributos `data-tt` do DOM. |
| 7 | `8189ecf` | **Auditoria em lote do Studio** + insights de tráfego/busca/viewers e correção do estado da UI. |
| 8 | `d668354` | **Identidade multi-creator, stepper "Produzir", fila diária de 5 posts, checklist de setup, abas compartilhadas Grok/Flow, loop do playbook, retries no scraper e guia de instalação em outro PC.** |

### 9.2 Trabalho atual (ainda **não commitado**)

São **23 arquivos modificados** e **9 itens novos** — cerca de **7.473 linhas adicionadas** e **5.330 removidas**. É a maior leva de mudanças desde a base.

#### Arquivos novos (ainda não versionados)

| Arquivo | Para que serve |
|---|---|
| `services/character_sheet.py` | Prompt mestre + negativos para a **ficha de consistência de personagem** no Grok. Resolve o problema de a modelo "mudar de rosto" entre campanhas. |
| `frontend/src/device.js` | Detecção de dispositivo (iPhone / iPad / Android / computador), com tratamento do iPad que se passa por Mac. |
| `frontend/src/serviceLinks.jsx` | Botões de Grok / Flow / TikTok que se comportam diferente no celular (link nativo `https://`, clicado de forma síncrona para o iOS abrir o app) e no PC (chamada ao servidor, que abre o perfil de Chrome correto). |
| `frontend/src/serviceLogos.js` | Logos em base64 embutidos — evita requisição externa de imagem, mantendo o app 100% local. |
| `reiniciar-fabrica.bat` | Encerra o `pythonw.exe` daquele diretório e reinicia via `iniciar.vbs`. |
| `reports/prompt-audit-2026-09-12/evidence.json` | Evidência da auditoria de prompts: briefing de teste e o texto exato gerado, para comparar antes/depois. |
| `frontend/logo-preview.png`, `device-desktop-preview.png`, `device-iphone-preview.png` | Imagens de conferência visual. |

#### Arquivos modificados e o que mudou em cada um

| Arquivo | Δ linhas | Natureza da mudança |
|---|---:|---|
| `services/prompts.py` | +913 | **A maior mudança.** Reescrita profunda do gerador de texto: normalização para pt‑BR, extração de características e materiais do produto, detecção de foco contraditório, sinais de persuasão, tratamento de peça unissex, concordância de artigo/gênero, plano de movimentos, trava de cenário (`_scene_lock`) para o vídeo casar com a imagem aprovada, e variação de CTA e de semente de legenda. |
| `frontend/src/components.jsx` | ~3.195 | Reescrita ampla dos componentes: fila de publicação, mixer, preview com beats, painel de performance, checklist, biblioteca da modelo, ferramentas rápidas de resultados. |
| `services/studio_metrics.py` | ~2.788 | Reestruturação do scraper do Studio com seletores `data-tt` e mais tolerância a mudanças de DOM. |
| `frontend/src/styles.css` | ~1.356 | Revisão geral do visual, incluindo layout responsivo para celular. |
| `frontend/src/App.jsx` | ~1.173 | Nova navegação por hash (`#/inicio`, `#/produzir/...`, `#/resultados/...`), `BrandMark`, `ScriptEditor` e o `Panel` por etapa. |
| `services/browser_assistant.py` | +542 | Grok/Flow migram para **Chrome nativo** em vez de Playwright (downloads paravam de funcionar); vigia de downloads, semeadura das preferências de download do Chrome, roteamento do arquivo baixado, perfil de geração compartilhado, e `open_grok_character_sheet`. |
| `app.py` | +348 | Novas rotas: `model-library/label` (PATCH), `model-library/character-sheet` (GET), `model-library/character-sheet/open` (POST), `browser/open-free` (POST). Novos helpers de segurança/rede: `_host_allowed` e `_lan_urls`. |
| `tests/test_app.py` | ~908 | Testes acompanhando as mudanças de rota e de geração de texto. |
| `README.md` | ~398 | Documentação atualizada. |
| `services/video_mix.py` | ~250 | Ajustes no mixer e na localização do FFmpeg. |
| `services/setup_status.py` | ~184 | Checklist de setup refinado. |
| `services/studio_identity.py` | ~128 | Identidade por PC. |
| `frontend/src/nicheDefaults.js` | ~124 | Padrões por nicho mais ricos. |
| `INVENTARIO-FABRICA-E-PLANOS.md` | ~122 | Inventário atualizado. |
| `launcher.py` | ~115 | Reaproveitamento de servidor já rodando (`version: 6`), varredura de portas 5050–5059, exposição na LAN (`FABRICA_LAN`), log em `data/server.log`, aviso em MessageBox no Windows quando a porta está ocupada. |
| `services/model_library.py` | +88 | Renomear rótulo de foto (`rename_label`) e mais nichos. |
| `COMO-INSTALAR-NO-OUTRO-PC.md` | ~78 | Guia de instalação atualizado. |
| `services/playbook.py` | ~39 | Ajustes no cálculo do playbook. |
| `tests/test_browser_assistant.py` | +20 | Cobertura das mudanças de navegador. |
| `studio_identity.example.json` | ~18 | Campos novos de identidade. |
| `frontend/src/api.js` | +12 | Novas chamadas: `health`, `renameModelLibraryLabel`, `openBrowserFree`, `characterSheet`, `openCharacterSheet`. |
| `.gitignore` | 2 | Mais exclusões. |
| `outputs/PLANO_MIGRACAO_CODEX.md` | 2 | Retoque. |

#### Os quatro temas por trás dessa leva

1. **Qualidade do texto gerado** (`prompts.py` + `reports/`) — o gerador deixou de montar frases genéricas e passou a usar de fato o produto, o material, o público e o benefício do briefing, em português correto. A pasta `reports/` existe para provar isso com evidência lado a lado.
2. **Consistência da modelo** (`character_sheet.py`, biblioteca por nicho, renomear rótulo) — atacar o problema de a IA trocar o rosto da modelo entre gerações.
3. **Confiabilidade do navegador** (`browser_assistant.py`) — Grok e Flow saíram do Playwright e voltaram para o Chrome normal, porque o download do arquivo gerado quebrava a janela automatizada. O Studio continua no clone CDP.
4. **Uso no celular** (`device.js`, `serviceLinks.jsx`, `launcher.py` com LAN, CSS responsivo) — acessar a Fábrica pelo celular no mesmo Wi‑Fi (`http://IP-DO-PC:5050`) e abrir Grok/TikTok nos apps nativos. **Não** é hospedagem na nuvem: o servidor continua sendo o seu PC.

> ⚠️ **Observação:** todo esse trabalho está no diretório mas **ainda não foi commitado**. Enquanto não houver `git commit`, ele não está protegido no histórico nem no GitHub.

---

## 10. Como rodar

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

## 11. Privacidade e separação entre creators

- Tudo fica no PC: banco, mídia, perfis de navegador.
- `.gitignore` exclui `data/`, `media/`, `browser_profiles/`, `.venv/`, `.env`, `*.db`, `node_modules/`, `frontend/dist/`, `_patch/`.
- **Nunca copiar entre creators:** `browser_profiles/` (levaria a sessão de Chrome errada) e `data/` (banco, identidade, históricos).
- Cada PC define sua identidade em `data/studio_identity.json` pelo ícone de Identidade no cabeçalho.
- Mutações vindas de outras origens são bloqueadas por validação de host + cabeçalho `X-Local-App`.

---

## 12. Limitações conhecidas e próximos passos

**Limitações**
- A raspagem do TikTok Studio depende do DOM deles; se o TikTok mudar a interface, quebra (há retries e mensagem clara, mas exige ajuste no `studio_metrics.py`).
- Depende de Windows, Chrome instalado e FFmpeg no PATH para o mixer.
- A geração de imagem/vídeo continua manual, por escolha de projeto.

**Estado dos testes (12/09/2026)**

A suíte tem **51 testes**; **8 falham** hoje. As falhas são de *expectativa desatualizada*: os testes ainda descrevem o comportamento anterior à reescrita do `prompts.py` e às mudanças no `browser_assistant.py`. Em resumo:

| Teste que falha | O que mudou no código |
|---|---|
| `test_script_uses_product_attributes_instead_of_generic_copy`, `test_generated_development_is_speech_and_fits_15_second_budget` | O desenvolvimento do roteiro deixou de citar o público ("mulheres que treinam") e passou a citar o produto e seus fatos confirmados. |
| `test_multiple_color_prompt_variants_are_saved_and_exported` | O pacote por cor passou de 6 para 7 campos. |
| `test_single_script_refresh_preserves_image_and_other_phrases` | O hook agora aparece dentro do prompt de vídeo com pontuação diferente (`?.`), então a comparação literal falha. |
| `test_format_validation_and_wrong_resolution` | A aprovação de vídeo com resolução fora do alvo deixou de retornar erro 409. |
| `test_editing_caption_requires_preparation_again` | Editar a legenda não volta mais o status para `video_approved`. |
| `test_grok_uses_native_browser_without_playwright`, `test_grok_refuses_active_flow_profile` | Grok e Flow passaram a usar o perfil compartilhado `gen-maaiquels` em vez de `flow-maaiquels`. |

As duas últimas linhas da tabela e as duas de comportamento (409 e status da legenda) merecem uma decisão consciente: se a mudança foi intencional, atualiza-se o teste; se não foi, é regressão a corrigir.

**Próximos passos previstos**
- Commitar a leva atual de mudanças.
- Empacotamento em EXE (PyInstaller) ou Tauri/Electron.
- Montagem automática de vídeo.
- Possivelmente limpar `_patch/` e `work/`, que são resíduo do desenvolvimento.
- Alinhar ou remover os 8 testes que falham (ver acima).
- Remover a dependência `@xyflow/react`: ela continua no `package.json` e só é usada para importar um CSS em `main.jsx` — o canvas React Flow não é mais utilizado.

---

## 13. Glossário

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
