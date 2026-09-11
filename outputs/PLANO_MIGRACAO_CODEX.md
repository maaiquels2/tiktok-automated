# Fábrica TikTok — Plano de migração para Codex

## Objetivo

Construir um aplicativo local para organizar a criação de conteúdos de TikTok com uma modelo visual fixa.

O fluxo precisa:

1. Definir produto, roupa, cor, público, benefício e estilo.
2. Reutilizar uma mesma imagem de referência da modelo; somente roupa e cor mudam.
3. Gerar prompts de imagem e vídeo.
4. Criar hook, desenvolvimento e CTA.
5. Criar vídeo vertical de 15 segundos: 1080p no Google Flow ou 720p no Grok Imagine.
6. Aprovar imagem e vídeo antes de seguir.
7. Preparar a publicação no TikTok Studio da Micaela: MP4, legenda e seleção manual de produto.

## O que já foi criado

### Protótipos visuais

- outputs/fabrica-tiktok.html
  - Formulário de produto e look.
  - Gerador local de prompts, frases e legenda.
  - Botões para abrir Google Flow, Grok e TikTok Studio.

- outputs/fluxo-tiktok-visual.html
  - Canvas visual inspirado em React Flow.
  - Blocos arrastáveis: modelo fixa, look, imagem, aprovação, frases, vídeo e Studio.
  - Alternância visual Flow 1080p e Grok 720p.

### Base executável local

- app.py
  - Aplicação Flask local.
  - Rota /: canvas visual.
  - Rota /creator: tela de briefing.
  - API local: GET e POST /api/campaigns; PATCH /api/campaigns/id.
  - Banco SQLite em data/fabrica_tiktok.db.

- requirements.txt: Flask.
- .venv: ambiente Python local criado.
- A aplicação foi testada em http://127.0.0.1:5050.

## Estado atual

O Flask e a API local funcionam. O canvas ainda é um protótipo: arrasta blocos, mas ainda não carrega campanhas do SQLite nem atualiza a API ao avançar uma etapa.

Playwright ainda não foi instalado nem integrado.

## Arquitetura recomendada

Usuário → interface React com React Flow → API Flask → SQLite, arquivos locais, gerador de prompts e assistente Playwright.

| Componente | Responsabilidade |
|---|---|
| React Flow | Canvas, nós, conexões, estados e ações da campanha |
| Flask | API local, regras do fluxo, persistência e organização de arquivos |
| SQLite | Campanhas, etapas, prompts e metadados |
| Python | Prompts, roteiros, nomes de arquivos e tarefas locais |
| Playwright | Abre serviços e prepara páginas usando perfis dedicados |
| Codex | Desenvolve e mantém o projeto; não roda embutido no aplicativo |

## Perfis de navegador

Não automatizar o perfil principal do Chrome. Criar perfis de automação separados e fazer login manualmente uma vez:

| Diretório local | Conta | Serviços |
|---|---|---|
| browser_profiles/flow-maaiquels | maaiquels@gmail.com | Google Flow e Grok Imagine |
| browser_profiles/tiktok-micaela | Conta da Micaela | TikTok Studio |

Essas pastas contêm cookies e sessões. Nunca enviar para o GitHub.

Adicionar ao .gitignore:

    .venv/
    data/
    media/
    browser_profiles/
    playwright/.auth/
    *.db

## Regras de automação

### Permitido no modo assistido

- Abrir Flow, Grok Imagine e TikTok Studio no perfil correto.
- Navegar à página certa.
- Copiar ou preencher um prompt.
- Indicar arquivo para anexar.
- Organizar download e renomear arquivos localmente.
- Abrir o Studio com vídeo e legenda prontos.

### Deve exigir clique e revisão humana

- Clique que consome créditos de geração.
- Aprovação de imagem e vídeo.
- Seleção de produto no TikTok Shop.
- Publicação final.

Não automatizar Grok Imagine no plano consumidor: a política da xAI proíbe acesso automatizado/não humano. O app apenas abre e prepara a página.

## Próximas etapas

### Fase 1 — Interface real

1. Criar frontend React com Vite.
2. Instalar React Flow, pacote @xyflow/react.
3. Converter o canvas para componentes React.
4. Tela com fila de campanhas à esquerda, canvas no centro e propriedades da etapa à direita.
5. Carregar campanhas reais pela API Flask.

### Fase 2 — Campanhas e mídia

1. Ampliar a tabela campaigns.
2. Criar tabelas assets, steps e prompts.
3. Criar botões e endpoints de upload para imagem da modelo, imagem aprovada e vídeo MP4.
4. Criar botão de download de pacote TXT e ZIP da campanha.
5. Estrutura de arquivos por campanha:

    media/
      campanha-0001/
        referencia-modelo.jpg
        imagem-aprovada.png
        video-aprovado.mp4
        pacote-tiktok.txt

### Fase 3 — Fluxo

1. Formulário: campanha, modelo, roupa, cor, produto, público, benefício, ângulo, tom e detalhes.
2. Gerar prompt de imagem, prompt de vídeo, hook, desenvolvimento, CTA e legenda.
3. Estados:

    briefing
    → image_ready
    → image_approved
    → script_ready
    → video_ready
    → video_approved
    → ready_to_publish
    → published

4. Cada nó muda de cor e estado no canvas.

### Fase 4 — Playwright assistido

1. Instalar Playwright no ambiente virtual.
2. Criar services/browser_assistant.py.
3. Implementar:
   - open_flow_for_image(campaign_id)
   - open_flow_for_video(campaign_id)
   - open_grok_for_image(campaign_id)
   - open_grok_for_video(campaign_id)
   - open_tiktok_studio(campaign_id)
4. Cada função abre perfil dedicado, abre apenas a URL necessária e pede confirmação antes de qualquer ação externa.
5. Não salvar senhas no código.

### Fase 5 — TikTok Studio

1. Após aprovação do MP4, oferecer Preparar publicação.
2. Abrir Studio no perfil da Micaela.
3. Mostrar vídeo, legenda copiável e checklist de produto.
4. A Micaela sobe o MP4, escolhe produto, cola a legenda, revisa e publica.

## Empacotar para Windows

1. Quando a versão estiver estável, usar PyInstaller para gerar EXE.
2. O iniciador abre Flask local e a interface no navegador.
3. Opcionalmente migrar depois para Tauri/Electron para um aplicativo sem aba de navegador.

## Comandos atuais

    cd C:\Users\Admin\Documents\Codex\2026-09-10\criei-meu-proprio-app-para-gerar
    .\.venv\Scripts\python.exe app.py

Abrir: http://127.0.0.1:5050

## Critério da primeira versão utilizável

- Criar e visualizar campanhas no canvas.
- Anexar imagem fixa da modelo e imagem aprovada.
- Gerar e copiar prompts, roteiro e legenda.
- Anexar e baixar vídeo MP4.
- Abrir Flow, Grok e TikTok Studio no perfil certo por botões.
- Persistir tudo localmente.
- Exigir revisão humana antes de gerar, aprovar ou publicar.

