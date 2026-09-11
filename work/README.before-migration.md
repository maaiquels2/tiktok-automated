# Fábrica TikTok

Aplicativo local em Flask para organizar campanhas de conteúdo, baseado em um canvas visual.

## Rodar localmente

1. Crie e ative um ambiente virtual Python.
2. Instale as dependências: python -m pip install -r requirements.txt
3. Execute: python app.py
4. Abra: http://127.0.0.1:5050

## O que já funciona

- Canvas visual para o fluxo de criação.
- Tela de criação de briefing em /creator.
- API local com SQLite para criar campanhas e atualizar o status de cada etapa.

## Limites intencionais

O app abre Flow, Grok e TikTok Studio, mas não usa credenciais, não gera conteúdo automaticamente com planos de consumidor e não publica posts sem revisão humana.
