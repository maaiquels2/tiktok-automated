# Instalar a Fábrica TikTok em outro PC (outra creator)

> **Alternativa mais rápida:** hoje existe uma **versão em nuvem** (Vercel + Supabase) — basta a segunda pessoa abrir a URL do deploy e entrar com uma conta de editor, sem instalar nada no PC dela. Este guia continua valendo para quem quer a instalação local completa (necessária para usar Grok/Flow com perfil de Chrome dedicado, misturar vídeos ou coletar métricas automaticamente do Studio — recursos que só existem na versão local; ver `DOCUMENTACAO-PROJETO.md`, seção 3.2). A conta de editor é criada pela responsável (owner) pelo ícone **Acessos do estúdio** no cabeçalho da versão em nuvem.

## Compartilhar (GitHub)
- Código, `instalar.ps1`, `iniciar.vbs`, `requirements.txt`, este guia

## Nunca copiar da Micaela
- `browser_profiles/` (sessão Chrome errada)
- `data/` (SQLite, playbook, identidade, históricos)
- `media/` das campanhas dela

## Passo a passo

1. Instalar Python 3.11+, Node LTS, Chrome, Git, FFmpeg (PATH).
2. Clonar:
   ```powershell
   git clone https://github.com/maaiquels2/tiktok-automated.git
   cd tiktok-automated
   ```
3. Instalar:
   ```powershell
   powershell -ExecutionPolicy Bypass -File .\instalar.ps1
   ```
4. Subir:
   ```powershell
   .\iniciar.vbs
   ```
   Abre http://127.0.0.1:5050
5. No header, ícone **Identidade**: nome do estúdio, modelo, @handle (sem @), perfil Chrome (nome ou `Profile 7`), lembretes Grok/Flow.
6. Checklist de setup no Início: subir **1 foto por nicho** na biblioteca.
7. **Abrir Grok** ou **Abrir Flow** uma vez → login na conta dela (mesma janela, abas).
8. **Abrir TikTok Studio** / coletar métricas 1× (pode pedir para fechar o Chrome na 1ª clonagem CDP).
9. Rodar lote 7d em Resultados → gerar playbook → usar **Fila de hoje (5 posts)**.

## Atualizar depois
```powershell
git pull
powershell -ExecutionPolicy Bypass -File .\instalar.ps1
.\iniciar.vbs
```

## Versão em nuvem, em vez de instalar aqui

Se a ideia é só dar acesso a uma segunda pessoa (sem precisar de Grok/Flow com perfil de Chrome dedicado, mixer de vídeo ou coleta automática de métricas — que são só locais):

1. Peça a URL do deploy na Vercel para a responsável.
2. Abra a URL e clique em entrar (não em "Crie o acesso principal" — essa conta já existe).
3. A responsável cria o login dela pelo ícone **Acessos do estúdio** no cabeçalho, com usuário e senha.
4. As duas contas veem as mesmas campanhas em tempo real.
