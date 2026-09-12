# Instalar a Fábrica TikTok em outro PC (outra creator)

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
