# Fábrica TikTok — Documentação do Projeto

**Documento atualizado em:** 2026-09-13
**Pasta do projeto (versão local):** `C:\Users\Admin\Documents\Codex\2026-09-10\Fabrica TikTok`
**Repositório:** https://github.com/maaiquels2/tiktok-automated
**Como abrir (local):** duplo clique em `iniciar.vbs` → http://127.0.0.1:5050
**Como abrir (nuvem):** acessar a URL do deploy na Vercel e entrar com usuário e senha
**Base auditada:** `main` no commit `c158bd2`; 82 rotas HTTP; 90 testes executados, todos `OK`.

> Este documento explica **o propósito**, **o escopo**, **o que cada arquivo faz** e **tudo o que foi criado e modificado** no projeto — incluindo a migração para nuvem (Vercel + Supabase) que foi concluída nesta revisão. Foi escrito para ser lido sem base prévia em programação — há um glossário no final com os termos técnicos.

---

## 1. Em uma frase

A Fábrica TikTok é um aplicativo — hoje disponível **no seu computador ou em um endereço na internet** — que organiza, do começo ao fim, a produção de vídeos curtos (Shorts/UGC) para TikTok Shop: briefing → prompts → imagem → roteiro de 15s → vídeo → legenda → publicação manual no TikTok Studio → coleta de métricas → playbook do que repetir.

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

### A decisão central: "IA na sua assinatura", automação só onde é segura

O projeto foi construído em torno de uma escolha econômica e prática, independente de onde ele roda:

| Decisão | Por quê |
|---|---|
| Textos (prompts, roteiros, legendas) gerados por **regras determinísticas em Python**, não por API paga de LLM | Custo zero por campanha, resultado previsível e reproduzível, funciona offline. |
| Imagem e vídeo gerados **manualmente** no Grok Imagine / Google Flow | Você já paga essas assinaturas. Chamar API de geração custaria de novo, por peça. |
| Publicação **manual** no TikTok Studio | Automação de postagem viola termos e arrisca a conta. O app prepara tudo e abre a página; o clique final é humano. |

Em resumo: **o app automatiza a organização e a escrita; a criação visual e a publicação continuam humanas de propósito.**

### Duas formas de rodar o mesmo `app.py`

Essa filosofia vale integralmente para a **versão local** (a forma original do projeto: banco SQLite em arquivo, mídia em pasta local — ver seção 4.1). Para permitir acesso de qualquer aparelho, com login, e sem depender do PC ligado, o projeto ganhou depois uma **versão em nuvem** (Vercel + Supabase — seção 4.2): mesmo `app.py`, ligado por uma variável de ambiente (`FABRICA_CLOUD=1`), trocando SQLite por Postgres e a pasta `media/` por Supabase Storage. A diferença prática mais importante é que a nuvem **não tem um Chrome de verdade rodando no servidor**, então tudo que dependia de controlar um navegador — misturar vídeos, auto-cut e coleta automática de métricas do Studio — fica só na versão local (detalhes na seção 3.2).

---

## 3. Escopo

### 3.1 O que está dentro do escopo (o que o app faz)

**Produção multi-cor**
- Você informa várias cores no briefing (`Branco, Preto, Azul Marinho…`).
- O app cria automaticamente **um pacote por cor**: prompt de imagem, prompt de vídeo, falas do roteiro e legenda.
- Regra importante: a IA **nunca** recebe todas as cores no mesmo prompt de imagem (senão ela mistura as cores na mesma peça).

**Modelo fixa e consistência de identidade**
- Uma foto de referência da modelo é anexada e reutilizada entre campanhas.
- Biblioteca de fotos padrão por nicho, com suporte a **mais de um modelo** por nicho (`services/model_library.py`).
- **Ficha de consistência de personagem** (`services/character_sheet.py`): um prompt mestre com bloqueio de identidade e lista de negativos ("rosto diferente", "deriva de identidade", "CGI"…) para gerar no Grok uma ficha de referência da modelo.

**Análise de foto por IA (opcional)**
- Ao anexar a foto de descrição do produto, `services/copywriter.py::analyze_product()` pode analisá-la com um modelo de visão (`gpt-4o-mini` ou `gemini-2.0-flash`, usando a mesma chave configurada em Redator) e sugerir benefício, ângulo, movimentos e detalhes.
- Regra de prioridade: **a foto manda mais que o texto padrão do nicho** — se a foto sugere algo diferente do modelo do nicho, a sugestão da foto é o que preenche o briefing; o nicho só é usado como reserva quando não há foto ou a análise falha.

**Roteiro de 15 segundos**
- Estrutura fixa: **Hook (0–4s) → Desenvolvimento (4–12s) → CTA (12–15s)**.
- As falas variam por cor.
- Botões para regenerar só o hook + legenda, ou a fala inteira, sem recomeçar a campanha.

**Imagens e vídeos**
- Um slot de imagem e um slot de vídeo **por cor**.
- Aprovação em lote: só libera quando todas as cores têm arquivo.
- Conferência de duração (~15s) e resolução alvo (1080×1920 no Flow, 720×1280 no Grok).
- **Misturador de vídeos** (`services/video_mix.py`, só na versão local): junta 2+ MP4s da campanha em um único vídeo ~15s 9:16 usando FFmpeg.
- **Preview 9:16** com scrubber e marcação dos beats do roteiro.
- **Vídeo mantido no dispositivo**: em vez de enviar o MP4, é possível selecionar o vídeo direto da galeria do celular — a Fábrica guarda só nome, tamanho e metadados, e a aprovação segue normalmente; o arquivo precisa ser selecionado de novo para assistir depois de recarregar a página.

**Legendas e hashtags**
- Legenda alinhada a produto, benefício, público e cor.
- Máximo de **5 hashtags**, escolhidas pelo nicho.

**Publicação (fila por cor)**
- Abas por cor: copiar legenda → copiar caminho do MP4 → abrir o Studio → registrar.
- A campanha só fecha como `published` quando **todas** as cores forem registradas.

**Resultados, métricas e playbook**
- Coleta de métricas do TikTok Studio via Playwright/Chrome CDP (`services/studio_metrics.py`, só na versão local); na nuvem os números são digitados manualmente.
- Auditoria em lote de posts de um período.
- **Playbook** (`services/playbook.py`): a partir da auditoria, monta um guia do que repetir (que tipo de hook, que nicho, que formato performou).
- **Fila de hoje (5 posts)** gerada a partir do playbook.
- **Insights locais** (`services/insights.py`): crítica heurística do roteiro (hook fraco? CTA sem verbo? sem urgência?) — sem inventar dados de plataforma.

**Multi-creator e login compartilhado**
- Versão local: cada PC tem sua própria identidade em `data/studio_identity.json` (nome do estúdio, modelo, @handle, perfil do Chrome); `browser_profiles/` e `data/` **nunca** são copiados entre creators.
- Versão em nuvem: um sistema de contas (`users`) substitui a separação por PC — a responsável cria a conta principal (owner) e, pelo ícone "Acessos do estúdio" no cabeçalho, cria e reseta a senha de uma segunda conta (editor); as duas veem as mesmas campanhas.

### 3.2 O que está deliberadamente fora do escopo

- ❌ Não chama API paga de imagem/vídeo. Usa Flow/Grok da sua assinatura, manualmente.
- ❌ Não clica em "gerar", não escolhe produto no Shop, não faz login por você.
- ❌ Não publica sozinho no TikTok, não marca produto, não agenda post.
- ❌ Não usa reconhecimento facial automático — a consistência da modelo é por prompt + revisão humana; a análise de foto por IA (seção 3.1) só sugere campos de texto do briefing, nunca decide sozinha.
- ❌ Na **versão em nuvem** não existe Chrome/Playwright de verdade rodando no servidor (a Vercel não permite automação de navegador). Por isso, ficam disponíveis **só na versão local**: misturar vídeos automaticamente, auto-cut/integração com o Critico e a coleta automática de métricas do Studio. Na nuvem essas etapas viram entrada manual.
- ❌ Não faz montagem criativa completa de vídeo por IA. O mixer local apenas corta, normaliza e reúne clipes escolhidos pelo operador.

---

## 4. Como o sistema é montado (arquitetura)

O mesmo `app.py` roda de duas formas.

### 4.1 Versão local

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

### 4.2 Versão em nuvem (Vercel + Supabase)

```
   [ NAVEGADOR / CELULAR ]  ← qualquer aparelho com internet
        │  React + Vite (o mesmo build, servido pelo Flask)
        │  fala por HTTPS com…
        ▼
   [ VERCEL ]  ← hospeda o Flask (wsgi.py → app.py), sem estado próprio
        │  guarda tudo em…
        ▼
   [ SUPABASE ]
        Postgres            (as mesmas tabelas do SQLite, mais `users`)
        Supabase Storage    (imagens, vídeos e referências)
```

Fotos e vídeos maiores não passam pelo servidor da Vercel (que tem limite de tamanho por requisição): o navegador pede um link assinado (`upload-url`), envia o arquivo **direto** ao Supabase Storage, e só então avisa o servidor para validar e gravar no banco (`confirm`) — é o mesmo padrão usado tanto para assets de campanha quanto para a biblioteca de modelos.

Em ambos os casos, e ao lado, os serviços externos que **você** opera manualmente:

```
   Grok Imagine / Google Flow  →  gera imagem e vídeo
   TikTok Studio               →  publica e fornece métricas
```

| Camada | Tecnologia | Arquivo principal |
|---|---|---|
| Interface | React + Vite | `frontend/src/App.jsx`, `components.jsx` |
| API / servidor | Flask (Python) | `app.py` (3.344 linhas, 82 rotas HTTP) — mesmo código nas duas versões, escolhido por `FABRICA_CLOUD` |
| Banco (local) | SQLite | `data/fabrica_tiktok.db` |
| Banco (nuvem) | Postgres (Supabase) | conexão via `FABRICA_DATABASE_URL` |
| Mídia (local) | Sistema de arquivos | `media/campanha-XXXX/` |
| Mídia (nuvem) | Supabase Storage | bucket definido em `FABRICA_STORAGE_BUCKET` |
| Navegador assistido (só local) | Chrome/Edge + Playwright (CDP) | `services/browser_assistant.py` |
| Vídeo (só local) | FFmpeg | `services/video_mix.py` |
| Hospedagem (nuvem) | Vercel | `vercel.json`, `wsgi.py` |

**Por que Flask + SQLite/Postgres e não algo maior?** Porque o app serve um número pequeno de pessoas (uma creator, ou uma creator e uma editora) com poucas escritas simultâneas. Um servidor de processo único e um banco simples são a escolha certa nas duas versões: zero configuração extra, backup simples (copiar um arquivo localmente, ou usar o backup gerenciado do Supabase na nuvem).

**Por que React se parte dele é um app local?** Porque a tela tem muito estado ao vivo (etapas, slots por cor, uploads, previews). Fazer isso em HTML puro daria muito mais código. O React é compilado uma vez (`npm run build`) e o Flask serve o resultado nas duas versões — não precisa de Node rodando no dia a dia, nem na nuvem nem no PC.

---

## 5. Mapa de arquivos — o que cada um faz

### 5.1 Raiz do projeto

| Arquivo | O que é |
|---|---|
| `app.py` | **O servidor.** Cria o app Flask, fala com SQLite ou Postgres conforme `FABRICA_CLOUD`, define as 82 rotas HTTP, valida uploads, controla transições de status e versionamento das campanhas, e (na nuvem) o login das duas contas. |
| `wsgi.py` | Ponto de entrada usado pela Vercel: `from app import create_app; app = create_app()`. Não é usado na versão local. |
| `vercel.json` | Configuração do deploy na Vercel: comando de build (compila o `frontend/` e empacota o Flask) e roteamento. |
| `launcher.py` | Iniciador do Windows (versão local). Procura uma porta livre entre 5050–5059, reaproveita um servidor já rodando (checa `/api/health`), sobe o Flask e abre o navegador. Também imprime o endereço de LAN para acessar do celular no mesmo Wi-Fi. |
| `iniciar.vbs` | Duplo clique para subir tudo sem janela preta de terminal (versão local). |
| `reiniciar-fabrica.bat` | Encerra o processo `pythonw.exe` daquele diretório e sobe de novo (versão local). |
| `instalar.ps1` | Instala dependências Python e Node e compila a interface (versão local). |
| `requirements.txt` | Lista de bibliotecas Python, incluindo `psycopg2-binary` (driver do Postgres, usado só quando `FABRICA_CLOUD=1`). |
| `studio_identity.example.json` | Modelo do arquivo de identidade por PC, usado só na versão local (o real fica em `data/`, fora do Git). |
| `.gitignore` | Impede que dados, mídia, perfis de navegador, `.venv` e segredos vão parar no GitHub. |
| `README.md` | Visão geral e instruções de uso das duas versões. |
| `INVENTARIO-FABRICA-E-PLANOS.md` | Resumo do estado atual + planos. |
| `COMO-INSTALAR-NO-OUTRO-PC.md` | Passo a passo para instalar a versão local para outra creator. |
| `MELHORIAS-SUGERIDAS.md` | Auditorias de UX/UI e de performance, com checklist de status por item. |
| `PROTOTIPO-NUVEM.md` | Registro histórico do protótipo que antecedeu a migração para nuvem — a migração descrita nele já foi concluída (ver seção 10.7). |
| `DOCUMENTACAO-PROJETO.md` | **Este documento.** |

### 5.2 `services/` — a lógica separada do servidor

Cada arquivo aqui resolve **um assunto**, para que `app.py` só precise coordenar.

| Arquivo | Linhas | O que faz |
|---|---:|---|
| `studio_metrics.py` | 1.394 | Raspagem do TikTok Studio com Playwright (só local): página de conteúdo e página de analytics por vídeo. Lê os atributos `data-tt` do DOM (VideoInfoCard, VideoMetricsCard) para extrair views, watch %, likes, saves etc. |
| `prompts.py` | 1.379 | **O coração da escrita.** Gera, por regras determinísticas, os prompts de imagem e vídeo, as falas do roteiro (hook/desenvolvimento/CTA) e as legendas — um pacote por cor. Inclui normalização para pt-BR, extração de características do produto, sinais de persuasão, direção de gestos e CTAs variados. Nenhuma API paga. |
| `browser_assistant.py` | 1.074 | Abertura assistida de navegador (só local — na nuvem, `cloud_mode` desativa esta camada por completo). Grok e Flow abrem em Chrome comum; o Studio reutiliza o perfil local configurado. Também vigia a pasta de downloads e roteia o arquivo baixado para a campanha certa. **Não clica em gerar, não faz login, não publica.** |
| `copywriter.py` | 604 | Escrita opcional das falas por modelo de linguagem (OpenAI ou Gemini), com auditoria local; e `analyze_product()`, a análise de foto por IA (vision) descrita na seção 3.1, que sugere campos do briefing a partir da foto de descrição do produto. Se a resposta falhar ou for reprovada, o sistema usa o texto determinístico. A chave fica em `data/llm.json` (local) ou no banco (nuvem), nunca volta pela API. |
| `playbook.py` | 423 | Transforma um relatório de auditoria em lote num **playbook de replicação**: agrupa por nicho/formato, calcula medianas de views e watch%, e diz o que repetir. |
| `model_library.py` | 363 | Biblioteca de fotos de referência da modelo organizada por nicho, com suporte a **mais de um modelo** por nicho e exclusão de fotos individuais; e os valores padrão sugeridos de cada nicho no briefing. |
| `insights.py` | 236 | Crítico local do roteiro: procura verbos de CTA, sinais de urgência, tamanho do hook. Gera recomendações **sem inventar dados do TikTok**. |
| `character_sheet.py` | 148 | Prompt mestre em português para gerar no Grok uma ficha de consistência de personagem, com bloqueio de identidade e um `NEGATIVE_PROMPT` extenso contra deriva de rosto, CGI, mãos malformadas etc. |
| `video_mix.py` | 125 | Concatena/corta MP4s da campanha em um único vídeo ~15s 9:16 via FFmpeg (só local). Localiza o FFmpeg por `FFMPEG_PATH`, pelo PATH ou no caminho padrão do WinGet. |
| `media.py` | 95 | Valida o **conteúdo** dos arquivos (imagem via Pillow, estrutura de caixas do MP4) em vez de confiar na extensão do nome. É uma proteção contra arquivo corrompido ou renomeado. |
| `setup_status.py` | 92 | Checklist de primeira execução: identidade preenchida? fotos por nicho? perfis de navegador usados? |
| `studio_identity.py` | 79 | Identidade por estúdio (nome, modelo, @handle, dica de perfil do Chrome), lida/gravada em `data/studio_identity.json` (local) ou no banco (nuvem). |

### 5.3 `frontend/src/` — a interface

| Arquivo | Linhas | O que faz |
|---|---:|---|
| `styles.css` | 5.038 | Sistema visual completo: tokens, temas claro/escuro, componentes, estados, responsividade e acabamento para computador e celular. |
| `components.jsx` | 1.925 | Todos os blocos da tela: `VariantList` (cartões por cor), `PublishQueue` (fila de publicação), `VideoMixer`, `VideoTimelinePreview` (preview 9:16 com beats), `GateCriticoPanel`, `PerformancePanel`, `BriefForm`, `StudioIdentityPanel`, `WriterSettingsPanel`, `SetupChecklist`, `DailyQueueCard`, `ModelLibraryPanel`, `ResultsQuickTools`. |
| `App.jsx` | 915 | A casca do app: navegação por hash (`#/inicio`, `#/produzir/<id>/<etapa>`, `#/resultados/<aba>/<id>`), carregamento das campanhas, controle de "sujo/descartar", o `Panel` que decide o que mostrar em cada etapa, e — só relevantes na nuvem — `AuthScreen` (criar acesso principal / entrar) e `UserAccessPanel` (criar e resetar senha da segunda conta). |
| `api.js` | 170 | Ponte com o servidor: função `api()` (que envia o cabeçalho `X-Local-App`), o fluxo de **upload direto ao Supabase Storage** (`requestAssetUploadUrl`/`confirmAssetUpload`, usado na nuvem para não esbarrar no limite de tamanho de requisição da Vercel), lista de status, rótulos em português e a definição das etapas do pipeline. |
| `nicheDefaults.js` | 62 | Valores padrão por nicho no formulário de briefing. |
| `serviceLinks.jsx` | 67 | Botões de abrir Grok/Flow/TikTok que **mudam de comportamento no celular**: no PC chamam o servidor (perfil de Chrome certo, só local); no celular viram links nativos, para o iOS/Android entregar ao aplicativo instalado quando houver associação. |
| `device.js` | 26 | Detecta iPhone, iPad, Android ou computador, inclusive o caso do iPad que se identifica como Mac. Uma janela pequena ou uma tela de toque, sozinhas, não classificam um computador como celular. |
| `Canvas.jsx` | 53 | Resto do canvas visual original. |
| `serviceLogos.js` | 3 | Logos do TikTok/TikTok Studio embutidos como base64, para a tela não depender de requisição externa de imagem. |
| `main.jsx` | 5 | Ponto de entrada do React. |

### 5.4 Pastas de apoio

| Pasta | Conteúdo |
|---|---|
| `data/` | Versão local: banco SQLite, identidade, backups. **Fora do Git. Nunca copiar entre creators.** Na nuvem, o equivalente mora no Postgres/Storage do Supabase, não nesta pasta. |
| `media/campanha-XXXX/` | Versão local: referências, imagens por cor, vídeos por cor, downloads. Fora do Git. Na nuvem, os mesmos arquivos vivem no Supabase Storage. |
| `browser_profiles/` | Sessões do Chrome (só versão local): `flow-maaiquels`, `grok-maaiquels`, `micaela-cdp`, `tiktok-micaela`, `tiktok-metrics`. Fora do Git. Não existe equivalente na nuvem. |
| `tests/` | `test_app.py` (1.217 linhas) e `test_browser_assistant.py` (118 linhas) — 90 testes no total. |
| `reports/` | Relatórios de auditoria — ex.: `prompt-audit-2026-09-12/evidence.json`, com o antes/depois dos prompts gerados. |
| `outputs/` | Plano de migração e protótipos HTML do fluxo (histórico). |
| `work/` | Cópias do `app.py` e `README.md` de antes da migração (histórico). |
| `_patch/` | Scripts Python de patch usados durante o desenvolvimento. Ignorado pelo Git. |

---

## 6. Banco de dados

As mesmas tabelas existem em SQLite (local, arquivo `data/fabrica_tiktok.db`) e em Postgres (nuvem, via Supabase):

| Tabela | Guarda |
|---|---|
| `campaigns` | A campanha: nome, modelo, produto, cores, público, benefício, ângulo, tom, estilo, movimentos, nicho, `status`, `generator` (flow/grok), `version`, `layout`, `checklist`, `published_url`. |
| `campaign_variants` | **Um registro por cor** da campanha, com o pacote de prompts daquela cor. É o que permite a produção multi-cor. |
| `assets` | Arquivos: `reference`, `image` ou `video`, com `slot` (a cor), tamanho, mime, metadados e `approved_at`. Local: caminho em disco. Nuvem: caminho no Supabase Storage. |
| `product_assets` | Até 8 fotos do produto por campanha. |
| `prompts` | Prompts da campanha quando não há variação por cor. |
| `steps` | Quais etapas foram concluídas e quais tiveram revisão humana. |
| `device_videos` | Registro de um vídeo mantido **na galeria do celular** em vez de enviado à Fábrica (nome, tamanho, metadados e aprovação) — existe nas duas versões; ver seção 3.1. |
| `users` | **Só existe na versão em nuvem.** Contas de login: nome de usuário, nome exibido, hash da senha e `role` (`owner`, que pode criar/resetar a segunda conta, ou `editor`). |

**Detalhe de engenharia:** o esquema é auto-migrável nas duas versões. Na inicialização o `app.py` lê a estrutura das tabelas existentes e adiciona qualquer coluna nova que ainda não exista. Por isso dá para atualizar o app sem perder o banco.

**Status possíveis de uma campanha:**
`briefing` → `image_ready` → `image_approved` → `script_ready` → `video_ready` → `video_approved` → `ready_to_publish` → `published`

**Etapas na tela:**
`model` → `look` → `image` → `image_approval` → `script` → `video` → `video_approval` → `studio` → `performance`

---

## 7. A API (82 rotas HTTP)

Agrupadas por assunto:

**Páginas e estáticos** — `/`, `/creator`, `/gate/`, `/assets/<arquivo>`, `/brand/<arquivo>`, `/favicon.svg`, `/api/health`

**Autenticação e contas (nuvem)** — `/api/auth/session`, `/api/auth/setup`, `/api/auth/login`, `/api/auth/logout`, `/api/users` (GET/POST), `/api/users/<id>/reset-password`; e, na versão local, `/api/lan-pin` e `/lan-unlock` (PIN de acesso pela rede local).

**Campanhas** — listar/criar/ler/apagar/editar campanha, `look`, `look/confirm`, `analyze-product`, `analyze-product/confirm` (análise de foto por IA), `duplicate`, `copy`, `layout`, `transition`, `package.<fmt>` (exportar TXT/ZIP)

**Geração de texto** — `generate`, `variants/generate`, `prompts` (PATCH), `prompts/refresh`, `variants/<id>/refresh`, `variants/<id>/prompts`, `writer` (GET/PATCH), `writer/test`

**Arquivos** — `assets` (upload direto por FormData), `assets/upload-url` + `assets/confirm` (upload direto ao Supabase Storage, usado na nuvem), `assets/<id>/file`, `product-assets/<id>/file`, `device-video`, `reference`, `references`

**Biblioteca da modelo** — `model-library` (GET/POST/DELETE), `model-library/models`, `model-library/file`, `model-library/label` (PATCH), `model-library/upload-url` + `model-library/confirm`, `model-library/character-sheet` (GET), `model-library/character-sheet/open` (POST), `reference-from-library`

**Vídeo** — `videos/mix` (só local), `autocut` (só local), `autocut/pending`, `autocut/<job>/dispatched`

**Publicação e resultados** — `publish-slot`, `published-link`, `performance`, `performance/fetch`, `insights`

**Studio** — `studio/open`, `studio/analyze-link`, `studio/link-analyses`, `studio/audit`, `studio/audit/latest`, `studio/playbook` (GET/POST), `studio/playbook/campaign`, `studio/identity` (GET/PATCH)

**Sistema** — `setup-status`, `productivity` (fila de 5 posts do dia), `browser/open-free` (só local), `campaigns/<id>/browser` (só local)

**Proteção:** as mutações exigem o cabeçalho `X-Local-App: fabrica-tiktok` e há validação de host (`_host_allowed`); na nuvem, além disso, a maioria das rotas exige sessão de login válida (`auth_required`).

---

## 8. Fluxo de uso, do início ao fim

1. **Nova campanha** — briefing (produto, cores separadas por vírgula, público, benefício, ângulo, nicho) e escolha do gerador: Flow (1080×1920) ou Grok (720×1280). Ao anexar a foto de descrição do produto, a análise por IA pode sugerir parte do briefing.
2. **Modelo fixa** — anexe a referência ou reutilize da biblioteca/de outra campanha.
3. **Definir look** — produto, cores, movimentos, até 8 fotos do produto → **Gerar prompts e roteiro** (cria um pacote por cor).
4. **Criar imagem** — abra o Grok/Flow, gere e anexe **uma imagem por cor**.
5. **Aprovar imagens** — checagem de identidade e de look; libera só com todas as cores preenchidas.
6. **Roteiro 15s** — revise as falas; use "Atualizar hook + legenda" ou "Atualizar fala inteira" se não gostar.
7. **Criar vídeo** — um MP4 de 15s por cor; opcionalmente use o **Misturar vídeos** (FFmpeg, só local).
8. **Aprovar vídeos** — conferência de duração e resolução, com preview 9:16.
9. **Preparar publicação** — fila por cor: legenda (≤5 hashtags) + caminho do MP4 → abrir Studio → registrar.
10. **Resultados** — coletar métricas (automático só local, manual na nuvem), auditar o lote, gerar playbook, criar a próxima campanha a partir dele.

---

## 9. Inteligência aplicada aos prompts

Esta é a parte mais trabalhada do projeto. O gerador não deve apenas preencher um modelo de texto: ele precisa separar instrução visual, direção de cena e fala humana, usar os fatos disponíveis e impedir que a IA invente qualidades do produto.

### 9.1 Briefing estruturado

O briefing reúne nome, modelo, nicho, produto, fotos do produto, cores, público, benefício, objeção, oferta, ângulo, tom, estilo, detalhes e movimentos. Escolher um nicho preenche sugestões editáveis; a foto de descrição do produto, quando analisada por IA, tem prioridade sobre essas sugestões padrão do nicho. O operador continua vendo o gerador e pode trocar entre Flow e Grok sem abrir a área avançada.

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

Foram removidas construções artificiais como "Para mulheres de 20 a 40 anos" e frases que mandavam a modelo falar instruções de câmera ou "mostre o produto". O público orienta a linguagem internamente, sem ser recitado. Termos em inglês são convertidos para português do Brasil quando há equivalente natural.

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

Há até duas tentativas. Se o provedor falhar ou a auditoria reprovar a resposta, o motor determinístico local assume automaticamente. A chave fica em `data/llm.json` na versão local (não versionada) ou no banco na versão em nuvem, e não é devolvida ao navegador.

### 9.5 Prompt de vídeo

O vídeo recebe a imagem aprovada da cor como primeiro quadro e referência contínua. O texto separa explicitamente:

- **falas**, que são as únicas frases entre aspas a serem pronunciadas;
- **coreografia**, executada sem ser lida;
- **câmera e enquadramento**;
- **provas visuais** ligadas somente a atributos confirmados;
- **travas de identidade, cenário, produto e continuidade**.

Cada fato confirmado ganha um gesto que possa demonstrá-lo. A coreografia limita uma ação por batida para reduzir movimentos artificiais. O encerramento define uma ação concreta e natural: mãos relaxadas ou tocando a peça, olhar para o produto marcado e pose estável — isso evita a tendência do gerador de encerrar sempre com braços levantados, aceno ou gesto de comemoração.

O vídeo preserva o cenário da imagem aprovada, a posição da câmera, a perspectiva e a iluminação. Movimentos de câmera existem apenas quando ajudam a mostrar o produto e não devem quebrar a continuidade.

### 9.6 Legendas e hashtags

As legendas usam produto, cor, detalhe comprovado e uma ação de loja. A geração corrige contrações do português, evita expressões como "repara em a", não recita idade e remove hashtags repetidas mesmo quando diferem apenas entre maiúsculas e minúsculas. O limite atual é de cinco hashtags relevantes.

### 9.7 Evidência e prevenção de regressões

`reports/prompt-audit-2026-09-12/evidence.json` guarda um caso de auditoria com briefing e saída exata. Os testes cobrem materiais, unissex, objeção, oferta, fatos negativos, divisão por cor, primeiro cenário versus cores seguintes, ausência de direção de vídeo no prompt de imagem, pontuação, tamanho de hook, orçamento de fala, gesto final, CTA de TikTok Shop e fallback do redator.

### 9.8 Análise de foto por IA

`analyze_product()`, em `services/copywriter.py`, usa um modelo de visão (mesma chave/config do Redator) para olhar a foto de descrição do produto e sugerir benefício, ângulo, movimentos e detalhes para o briefing. A regra de prioridade é simples: **a foto manda mais que o texto padrão do nicho** — o nicho continua servindo de reserva quando não há foto anexada ou a análise falha, mas nunca sobrescreve o que a IA viu na foto.

---

## 10. O que foi criado e modificado

### 10.1 Fundação e fluxo de produção

- Aplicativo Flask + React, com dados e mídia preservados (localmente em disco, ou na nuvem via Supabase).
- Canvas de produção transformado em um stepper linear, com pré-requisitos e revisões humanas.
- Upload validado por conteúdo, biblioteca da modelo, fotos do produto e reutilização de referência.
- Exportação de campanha em TXT e pacote ZIP apenas com mídia aprovada.
- Controle de versão para evitar que duas abas sobrescrevam mudanças uma da outra.
- Edição, renomeação, cópia, exclusão e criação de uma versão editável de campanha publicada.
- Correção da rota que criava versão editável e anteriormente terminava em página não encontrada.

### 10.2 Variações, imagem e vídeo

- Uma variação independente por cor, com prompt, imagem, roteiro, vídeo, legenda e publicação próprios.
- Bloqueio de avanço quando falta arquivo ou aprovação de alguma cor.
- Correção específica do caso de uma única cor/um único vídeo que ficava preso em "Aprove todos os vídeos".
- Migração idempotente que recupera aprovações de vídeo feitas por versões antigas.
- Exibição imediata da imagem recém-anexada na etapa Criar imagem; antes ela só aparecia na aprovação.
- Remoção da duplicação visual do cartão do Grok e das referências na etapa de imagem.
- Mixer local de dois ou mais clipes via FFmpeg e prévia vertical com linha do tempo.

### 10.3 Copy, imagem e direção de vídeo

- Separação total entre prompt de imagem, prompt de vídeo, roteiro falado e legenda.
- Reescrita do motor de copy para produto, material, componentes, ocasião, objeção, oferta e benefício.
- Variações de hook deduplicadas, desenvolvimento sem recitar idade e CTA com vocabulário real da loja.
- Filtro de termos de produção em inglês nas falas e normalização para português do Brasil.
- Auditoria contra promessas inventadas e falsa urgência; "acabamento" e expressões de entusiasmo deixaram de gerar falsos positivos.
- Trava de modelo, edição localizada da roupa, cenário fixo e integração fotográfica realista.
- Direção de gestos ligada às provas do produto, âncora das mãos e final natural.
- Redator opcional OpenAI/Gemini com teste de conexão, mensagem de erro real, adaptação do payload, auditoria e fallback local.
- Identificação visível da origem do roteiro na interface.
- Botão explícito de geração por API na etapa Roteiro de 15s, incluindo geração individual por cor.

### 10.4 Navegador e serviços externos (versão local)

- Perfis dedicados e persistentes do Chrome para Flow, Grok e TikTok Studio.
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
- Coleta assistida de views, curtidas, retenção, tráfego, buscas e audiência no TikTok Studio (versão local); entrada manual na nuvem.
- Auditoria em lote e relatório do que performou melhor.
- Insights heurísticos, playbook de replicação e criação de nova campanha a partir do playbook.
- Fila diária de cinco conteúdos e checklist de configuração inicial.
- Gate crítico e prévia 9:16 para revisão antes da publicação.

### 10.6 Interface, celular e operação

- Navegação principal em Início, Produzir e Resultados.
- Rotas por hash que permitem retornar diretamente à campanha e etapa.
- Gerador Flow/Grok visível na etapa Definir look, fora da seção avançada.
- Layout responsivo, tokens de design, temas claro/escuro e estados visuais de sucesso, espera e erro.
- Acesso por celular na mesma rede local, protegido por PIN de quatro dígitos (versão local) ou por login (versão em nuvem).
- Backup diário do SQLite antes e depois das migrações, mantendo até dez cópias (versão local); backup gerenciado pelo próprio Supabase na nuvem.

### 10.7 Migração para nuvem (Vercel + Supabase)

O que era um protótipo/plano (registrado em `PROTOTIPO-NUVEM.md`) foi implementado por completo nesta fase:

- Camada de banco adaptada para falar com Postgres/Supabase quando `FABRICA_CLOUD=1`, mantendo SQLite como padrão local — mesmo `app.py`, sem fork de código.
- Correções de compatibilidade SQL entre SQLite e Postgres (ex.: `CURRENT_TIMESTAMP` em colunas `TEXT`, protocolo `with db():`).
- Imagens, vídeos, referências e fotos de produto passaram a ir para o Supabase Storage quando em nuvem, com upload **direto do navegador** (link assinado + confirmação), contornando o limite de tamanho de requisição da Vercel.
- Automação de Chrome/Playwright removida do fluxo online: mixer de vídeo, auto-cut e coleta automática de métricas ficam só na versão local.
- `vercel.json` e `wsgi.py` criados para o deploy; correções sucessivas na detecção do entrypoint Flask pelo build da Vercel.
- Ajustes de autenticação e de bloqueio pelo Cloudflare nas chamadas ao Supabase Storage (troca para a chave de serviço no formato atual).
- Configurações de escrita por IA e de identidade do estúdio passaram a persistir no banco também na nuvem (antes só em arquivo local).
- Sistema de contas (`users`, login por sessão) para acesso compartilhado entre a responsável (owner) e uma segunda pessoa (editor), com criação e redefinição de senha pela própria interface.
- App publicado e funcionando no domínio padrão da Vercel; configurar um domínio próprio e revisar os segredos de produção continua como próximo passo (ver seção 13).

### 10.8 Análise de foto por IA e biblioteca de múltiplos modelos

- `analyze_product()`: análise da foto de descrição do produto por um modelo de visão, sugerindo benefício/ângulo/movimentos/detalhes, com a foto tendo prioridade sobre o texto padrão do nicho.
- Correção de um caso em que a foto de descrição era ignorada ao criar uma campanha nova.
- Biblioteca de fotos padrão passou a suportar mais de um modelo por nicho, com exclusão de fotos individuais.
- Botão para a responsável (owner) redefinir a senha do segundo acesso.

### 10.9 Revisão de UI mobile/desktop e performance (sessão de 2026-09-13)

Auditoria de interface nas telas Início, Produzir, Resultados e conta/identidade, em mobile e desktop, contra o site publicado, seguida de uma revisão de performance:

- **Bug de cascata de CSS:** vários blocos `@media` ficavam fisicamente antes de regras não-condicionais de mesma especificidade em `styles.css`; como o CSS resolve empates pela ordem no arquivo (não pela "estreiteza" do media query), essas regras responsivas eram silenciosamente anuladas em telas estreitas. Corrigido movendo os blocos afetados para o fim do arquivo (cabeçalho, grade de identidade, acordeões de Resultados e outros).
- **Tela em branco ao recarregar em campanha:** um link direto ou uma etapa que sobrou de outra campanha podia deixar `selected` apontando para uma etapa inválida, e a tela quebrava ao tentar ler `stage.title`. Corrigido com leitura defensiva do título e uma rede de segurança (`useEffect`) que devolve a navegação para uma etapa válida em vez de travar.
- Contraste do texto do cabeçalho e quebra de linha dos acordeões de Resultados no celular corrigidos.
- **Cache HTTP:** o bundle JS/CSS com hash no nome (`/assets/...`) ganhou `Cache-Control: public, max-age=31536000, immutable`; as fotos da biblioteca de modelos (link assinado do Supabase) passaram a usar um cache privado alinhado ao tempo de validade do link assinado, em vez de `no-store` incondicional.
- Tudo validado com `npm run build` e os 90 testes de backend antes do commit `c158bd2`.

---

## 11. Como instalar, iniciar e reiniciar

### 11.1 Versão local (Windows)

**Uso diário**
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
$env:FABRICA_CLOUD=1; .\.venv\Scripts\python.exe app.py       # simula o modo nuvem localmente
```

**Instalar em outro PC** — ver `COMO-INSTALAR-NO-OUTRO-PC.md`. Requer Python 3.11+, Node 20.19+ ou 22.12+, Chrome/Edge, Git e FFmpeg no PATH. Uma segunda pessoa também pode, em vez de uma instalação local nova, simplesmente entrar na versão em nuvem com a conta de editor (ver 11.2).

**Do celular, no mesmo Wi-Fi** — `http://IP-DO-PC:5050` (o `launcher.py` imprime o endereço). Desligue com `FABRICA_LAN=0` se quiser restringir a 127.0.0.1.

### 11.2 Versão em nuvem

- Abrir a URL do deploy na Vercel em qualquer navegador (computador ou celular).
- No primeiro acesso, criar a conta principal (owner) em **Crie o acesso principal**.
- Depois, a responsável usa o ícone **Acessos do estúdio** no cabeçalho para criar a conta da segunda pessoa (editor) e, se precisar, redefinir a senha dela.
- Publicar uma atualização: `git push` para o repositório e novo deploy na Vercel (que roda o `buildCommand` de `vercel.json`, compilando o `frontend/` de novo).

---

## 12. Privacidade, segurança e separação entre creators

**Versão local**
- Tudo fica no PC: banco, mídia, perfis de navegador.
- `.gitignore` exclui `data/`, `media/`, `browser_profiles/`, `.venv/`, `.env`, `*.db`, `node_modules/`, `frontend/dist/`, `_patch/`.
- **Nunca copiar entre creators:** `browser_profiles/` (levaria a sessão de Chrome errada) e `data/` (banco, identidade, históricos).
- No computador local não há tela de PIN. Pela rede Wi-Fi, o PIN fica salvo em cookie por até 30 dias.

**Versão em nuvem**
- Dados ficam no Postgres/Storage do Supabase; tráfego é HTTPS pelo domínio da Vercel.
- Acesso por login (usuário/senha, sessão do Flask) em vez de PIN; duas contas por estúdio (owner e editor), sem separação por PC.
- As chaves do Supabase e a chave secreta de sessão (`FABRICA_SECRET_KEY`) ficam nas variáveis de ambiente do projeto na Vercel, fora do repositório.

**Nas duas versões**
- Mutações vindas de outras origens são bloqueadas por validação de host + cabeçalho `X-Local-App`.
- As respostas usam `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer` e `X-Frame-Options: DENY`.
- Rotas de API continuam com `Cache-Control: no-store`; só os arquivos estáticos com hash no nome (bundle JS/CSS) e os arquivos de mídia recebem cache de longa duração (ver seção 10.9).

---

## 13. Validação, limitações conhecidas e próximos passos

**Limitações**
- A raspagem do TikTok Studio depende do DOM deles; se o TikTok mudar a interface, quebra (há retries e mensagem clara, mas exige ajuste no `studio_metrics.py`) — e só existe na versão local.
- A versão local depende de Windows, Chrome instalado e FFmpeg no PATH para o mixer.
- A versão em nuvem não tem Chrome/Playwright no servidor: mixer, auto-cut e coleta automática de métricas ficam indisponíveis lá (ver 3.2).
- A geração de imagem/vídeo continua manual nas duas versões, por escolha de projeto.
- O deploy na Vercel está no ar no domínio padrão (`*.vercel.app`); domínio próprio e uma revisão final dos segredos de produção ainda estão pendentes.

**Estado dos testes (13/09/2026, nesta revisão)**

Foram executados **90 testes e todos terminaram como `OK`** (`python -m unittest tests.test_app`), cobrindo fluxo completo, migração, backup, autenticação (LAN e login em nuvem), segurança de origem, upload atômico e upload direto ao Storage, troca de referência, edição e duplicação, variações por cor, prompts, redator opcional, análise de foto por IA, aprovações, publicação, exportação e perfis de navegador. O build do frontend (`npm run build`) também foi validado.

Duas decisões de produto seguem registradas nos testes: resolução e duração fora do alvo **avisam, mas não bloqueiam** a aprovação do vídeo; editar apenas a legenda exige preparar a publicação novamente sem invalidar o vídeo aprovado.

**Próximos passos previstos**
- Domínio próprio e revisão final dos segredos de produção no Vercel.
- Empacotamento em EXE (PyInstaller) ou Tauri/Electron para a versão local.
- Possivelmente limpar `_patch/` e `work/`, que são resíduo do desenvolvimento.
- Unificar os dois caminhos de publicação (`transition` e `publish-slot`).
- Continuar reduzindo a quantidade de breakpoints de CSS e testando cada faixa com o app aberto (parte disso já foi corrigida na revisão de 2026-09-13 — seção 10.9).
- Criar testes automatizados de interface para o fluxo completo em computador e iPhone; hoje a maior parte da UI é validada manualmente (visualmente e por medição ao vivo no navegador).
- Manter os seletores do TikTok Studio atualizados quando a plataforma mudar o DOM.

---

## 14. Glossário

| Termo | O que significa aqui |
|---|---|
| **API / rota** | Um "endereço" interno que a tela chama para pedir algo ao servidor, ex.: `/api/campaigns`. |
| **Backend / servidor** | O programa Python (Flask) que faz o trabalho pesado, seja no seu PC ou na Vercel. |
| **Frontend** | A parte visual, que roda no navegador. |
| **SQLite** | Banco de dados que é um único arquivo no disco (usado na versão local). Backup = copiar o arquivo. |
| **Postgres / Supabase** | Banco de dados relacional gerenciado na nuvem (usado na versão em nuvem); Supabase é o serviço que hospeda o Postgres e o Storage. |
| **Supabase Storage** | Onde ficam as imagens e vídeos das campanhas quando o app roda na nuvem, no lugar da pasta `media/` local. |
| **Vercel** | Serviço que hospeda a versão em nuvem do app e roda o build a cada novo deploy. |
| **Link assinado (signed URL)** | Um endereço temporário que autoriza enviar ou baixar um arquivo específico do Storage sem expor a chave secreta do Supabase. |
| **Commit** | Uma "foto" salva do projeto no histórico do Git. Enquanto não há commit, a mudança não está protegida. |
| **Determinístico** | O mesmo briefing sempre gera o mesmo texto. Previsível, sem surpresa e sem custo de IA. |
| **Playwright / CDP** | Ferramenta que controla o Chrome por programa (só na versão local). CDP é o canal que permite conversar com um Chrome já aberto. |
| **Scraping / raspagem** | Ler informação direto da página web, já que não há API oficial disponível. |
| **DOM** | A estrutura interna de uma página web; é nela que o scraper procura os números. |
| **FFmpeg** | Programa de linha de comando que corta, junta e converte vídeo (só na versão local). |
| **Hook / CTA** | Hook = os primeiros segundos que prendem a atenção. CTA = a chamada para ação ("toque no link"). |
| **9:16** | Formato vertical de tela cheia do celular (ex.: 1080×1920). |
| **Slot** | O "lugar reservado" de uma cor dentro da campanha — cada cor tem seu slot de imagem e de vídeo. |
| **UGC** | *User Generated Content* — vídeo com cara de conteúdo de pessoa real, não de anúncio. |

---

*Fim do documento.*
