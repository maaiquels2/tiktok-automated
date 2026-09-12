# -*- coding: utf-8 -*-
"""Ficha de consistência de personagem — prompt mestre + payload para Grok."""
from __future__ import annotations

NEGATIVE_PROMPT = (
    "pessoa diferente, rosto diferente, morfia facial, deriva de identidade, "
    "estrutura facial alterada, olhos diferentes, nariz diferente, lábios diferentes, "
    "linha do queixo diferente, tom de pele diferente, penteado diferente, "
    "proporções corporais inconsistentes, pessoa duplicada, anatomia distorcida, "
    "rosto assimétrico, pele plástica, pele cerosa, CGI, renderização 3D, cartoon, "
    "anime, ilustração, embelezamento excessivo, maquiagem excessiva, olhos irreais, "
    "rosto borrado, baixo detalhe, dedos extras, dedos ausentes, mãos malformadas, "
    "anatomia ruim."
)

_BASE_PROMPT = """Crie uma FICHA DE CONSISTÊNCIA DE PERSONAGEM profissional e ultrassurrealista em fotografia, usando a imagem de referência enviada como a ÚNICA fonte para a identidade do personagem.

IMPORTANTE — BLOQUEIO DE IDENTIDADE:
A imagem de referência enviada é a referência definitiva de identidade. Reproduza a EXATA MESMA PESSOA em toda a ficha de personagem.

NÃO redesenhe, embelezhe, reinterprete ou substitua o personagem.

Preserve com máxima precisão:
- identidade facial exata
- estrutura e proporções faciais
- olhos, formato dos olhos e cor da íris
- sobrancelhas e formato natural das sobrancelhas
- formato e proporções do nariz
- lábios, formato da boca e plenitude
- bochechas, linha do queixo e queixo
- tom de pele e textura natural da pele
- aparência de idade
- linha do cabelo
- cor exata do cabelo, comprimento, textura e penteado
- proporções corporais e físico
- características faciais distintas

LAYOUT DA FICHA DE PERSONAGEM:

Crie uma imagem de referência-limite limpa e profissional contendo:

1. GRANDE RETRATO FRONTAL / FECHAMENTO DO ROSTO
2. VISTA FRONTAL
3. VISTA 3/4 ESQUERDA
4. VISTA 3/4 DIREITA
5. PERFIL ESQUERDO
6. PERFIL DIREITO
7. VISTA TRASEIRA
8. VISTA FRONTAL DE CORPO INTEIRO
9. VISTA 3/4 DE CORPO INTEIRO
10. VISTA LATERAL DE CORPO INTEIRO
11. VISTA TRASEIRA DE CORPO INTEIRO
12. EXPRESSÃO NEUTRA
13. SORRISO NATURAL
14. SORRISO SUAVE
15. OLHANDO PARA A ESQUERDA
16. OLHANDO PARA A DIREITA
17. FECHAMENTO DOS OLHOS
18. FECHAMENTO DAS SOBRANCELHAS
19. FECHAMENTO DO NARIZ
20. FECHAMENTO DOS LÁBIOS
21. FECHAMENTO DO CABELO
22. FECHAMENTO DE ACESSÓRIOS
23. REFERÊNCIA DE ROUPA / VESTUÁRIO
24. PALETA DE CORES / REFERÊNCIA DE TOM DE PELE

CONSISTÊNCIA:
Cada painel deve mostrar a MESMA pessoa.

Mantenha a identidade facial, proporções, penteado, tom de pele e características físicas consistentes em todos os ângulos, poses e expressões.

Para vistas não claramente visíveis na referência, reconstrua o personagem de forma inteligente, mantendo-se estritamente fiel à referência visível. Não invente características distintas principais.

APRESENTAÇÃO:
Bíblia de personagem de produção cinematográfica premium / ficha de referência de modelagem.
Layout editorial limpo.
Fundo de estúdio neutro.
Iluminação de estúdio realista suave.
Detalhes faciais nítidos.
Poros e textura natural da pele.
Fios de cabelo individuais.
Tecidos e acessórios realistas.
Anatomia humana precisa.
Perspectiva de câmera consistente.
Bordas finas limpas entre painéis.
Rótulos profissionais abaixo de cada vista.
Tipografia elegante mínima.
Estética de referência de moda/modelo de alto padrão.

FOTORREALISMO:
Ultrassurrealista em fotografia.
Aparência humana real.
Textura natural da pele.
Olhos realistas.
Cabelo fisicamente preciso.
Sombras naturais.
Proporções realistas.
Sem aparência de CGI.
Sem pele plástica.
Sem rosto de boneca.
Sem substituição de rosto de beleza artificial.

PROMPT NEGATIVO:
pessoa diferente, rosto diferente, morfia facial, deriva de identidade, estrutura facial alterada, olhos diferentes, nariz diferente, lábios diferentes, linha do queixo diferente, tom de pele diferente, penteado diferente, proporções corporais inconsistentes, pessoa duplicada, anatomia distorcida, rosto assimétrico, pele plástica, pele cerosa, CGI, renderização 3D, cartoon, anime, ilustração, embelezamento excessivo, maquiagem excessiva, olhos irreais, rosto borrado, baixo detalhe, dedos extras, dedos ausentes, mãos malformadas, anatomia ruim.

SAÍDA:
Uma FICHA DE CONSISTÊNCIA DE PERSONAGEM profissional completa e altamente detalhada em uma única imagem, adequada como referência mestre para gerar imagens e vídeos consistentes deste personagem."""


def build_character_sheet_prompt(
    model_name: str,
    niche: str | None = None,
    niche_label: str | None = None,
) -> str:
    name = (model_name or "Micaela").strip() or "Micaela"
    header = (
        f"PERSONAGEM: {name}.\n"
        f"A foto da biblioteca anexada é a ÚNICA fonte de identidade de {name}. "
        f"Trate essa imagem como referência definitiva — não invente outra pessoa.\n"
    )
    niche_line = ""
    label = (niche_label or "").strip()
    niche_id = (niche or "").strip()
    if label or niche_id:
        shown = label or niche_id
        niche_line = (
            f"Nicho / look de referência: {shown}. "
            f"Na seção de roupa/vestuário da ficha, use um outfit coerente com esse nicho, "
            f"sem alterar o rosto, o cabelo ou a identidade de {name}.\n"
        )
    return f"{header}{niche_line}\n{_BASE_PROMPT}".strip() + "\n"


def build_payload(
    model_name: str,
    niche: str | None = None,
    niche_label: str | None = None,
) -> dict:
    name = (model_name or "Micaela").strip() or "Micaela"
    niche_id = (niche or "").strip() or None
    label = (niche_label or "").strip() or None
    return {
        "prompt": build_character_sheet_prompt(name, niche_id, label),
        "negative_prompt": NEGATIVE_PROMPT,
        "model_name": name,
        "niche": niche_id,
        "niche_label": label,
    }
