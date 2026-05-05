#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Converter Missa (PDF Versão Celular) -> TXT Holyrics
=====================================================

Lê o folheto da Missa "A Missa - Versão Celular" (Arquidiocese do Rio
de Janeiro) e gera dois arquivos TXT prontos para serem colados no
software Holyrics:

   - Parte 1: do início até a Homilia
   - Parte 2: da Homilia em diante (até a Antífona Mariana)

Uso:
    python converter_missa_holyrics.py <arquivo.pdf> [--saida pasta]

Requer: pdfplumber  (pip install pdfplumber)
"""

from __future__ import annotations
import argparse
import re
import sys
from pathlib import Path

try:
    import pdfplumber
except ImportError:
    print("ERRO: pdfplumber não está instalado. Rode: pip install pdfplumber",
          file=sys.stderr)
    sys.exit(2)


# =====================================================================
# CONFIG
# =====================================================================

COR = "#B81414"  # vermelho usado pelo Holyrics nos exemplos

# Linhas máx. por slide e largura nominal (TVs 65" do projeto)
LINHAS_POR_SLIDE = 7
CHARS_POR_LINHA = 25
ALVO_CHARS_SLIDE = LINHAS_POR_SLIDE * CHARS_POR_LINHA  # ~175

CABECALHOS_BLOCO = {
    "Ritos Iniciais": "RITOS INICIAIS",
    "Liturgia da Palavra": "LITURGIA DA PALAVRA",
    "Liturgia Eucarística": "LITURGIA EUCARÍSTICA",
    "Ritos Finais": "RITOS FINAIS",
}

# Nomes possíveis das seções numeradas. O número associado VARIA entre
# Missas (ex.: em Pentecostes há "Sequência" entre 2ª Leitura e Aclamação,
# o que desloca toda a numeração de Homilia em diante). Por isso aceitamos
# QUALQUER número, validando apenas o NOME conhecido.
NOMES_SECOES = [
    "Canto de Entrada",
    "Saudação",
    "Ato Penitencial",
    "Hino de Louvor",
    "Coleta",
    "Primeira Leitura",
    "Salmo Responsorial",
    "Segunda Leitura",
    "Sequência",                       # Pentecostes / Corpus Christi / Páscoa
    "Aclamação ao Evangelho",
    "Evangelho",
    "Homilia",
    "Profissão de Fé",
    "Oração dos Fiéis", "Oração dos fiéis",
    "Renovação das Promessas Batismais",  # Pentecostes / Vigília Pascal
    "Canto das Ofertas",
    "Convite à Oração",
    "Sobre as Oferendas",
    "Oração Eucarística",
    "Rito da Comunhão",
    "Canto de Comunhão",
    "Depois da Comunhão",
    "Vivência",
    "Bênção Final e Despedida",
    "Bênção Final",
]

# Mantemos SECOES_NOMES como dict por compatibilidade interna (alguns
# pontos antigos do código referenciam pelo número típico do Domingo comum).
SECOES_NOMES = {
    1:  ["Canto de Entrada"],
    2:  ["Saudação"],
    3:  ["Ato Penitencial"],
    4:  ["Hino de Louvor"],
    5:  ["Coleta"],
    6:  ["Primeira Leitura"],
    7:  ["Salmo Responsorial"],
    8:  ["Segunda Leitura"],
    9:  ["Aclamação ao Evangelho"],
    10: ["Evangelho"],
    11: ["Homilia"],
    12: ["Profissão de Fé"],
    13: ["Oração dos Fiéis", "Oração dos fiéis"],
    14: ["Canto das Ofertas"],
    15: ["Convite à Oração"],
    16: ["Sobre as Oferendas"],
    17: ["Oração Eucarística"],
    18: ["Rito da Comunhão"],
    19: ["Canto de Comunhão"],
    20: ["Depois da Comunhão"],
    21: ["Vivência"],
    22: ["Bênção Final e Despedida"],
}


def _eh_nome_secao(num: int, candidato: str) -> bool:
    """Verifica se 'candidato' começa com o nome de uma seção conhecida.
    O parâmetro 'num' é mantido para compatibilidade — não é usado para
    restringir, pois a numeração varia entre tipos de Missa."""
    cand = candidato.strip().rstrip(".").lower()
    for nome in NOMES_SECOES:
        if cand.startswith(nome.lower()):
            return True
    return False


def _nome_da_secao(p: str) -> str | None:
    """Se p for cabeçalho 'N. Nome conhecido', retorna o nome (em minúsculas).
    Caso contrário, None."""
    m = re.match(r"^\s*\d{1,2}\.\s*(.+?)\s*$", p)
    if not m:
        return None
    cand = m.group(1).strip().rstrip(".").lower()
    for nome in NOMES_SECOES:
        if cand.startswith(nome.lower()):
            return nome.lower()
    return None


# =====================================================================
# ETAPA 1 — EXTRAÇÃO DO PDF
# =====================================================================

def extrair_texto_pdf(pdf_path: Path) -> str:
    """Extrai texto puro de todas as páginas, exceto a capa (pág 1)."""
    with pdfplumber.open(pdf_path) as pdf:
        partes = []
        for i, page in enumerate(pdf.pages):
            if i == 0:
                continue  # capa
            t = page.extract_text() or ""
            partes.append(t)
        return "\n".join(partes)


# =====================================================================
# ETAPA 2 — LIMPEZA DE ARTEFATOS LINHA-A-LINHA
# =====================================================================

def _dedupe_chars(s: str) -> str:
    """Linhas do cabeçalho saem com cada char duplicado por causa da fonte
    (ex.: 'AAnnoo AA -- nnoo 3333 -- 1100 ddee mmaaiioo ddee 22002266').
    Detecta e remove a duplicação."""
    nucleo = re.sub(r"[\s–\-]", "", s)
    if len(nucleo) < 6:
        return s
    pares = [nucleo[i:i+2] for i in range(0, len(nucleo) - 1, 2)]
    iguais = sum(1 for p in pares if len(p) == 2 and p[0] == p[1])
    if iguais / max(1, len(pares)) >= 0.8:
        out = []
        i = 0
        while i < len(s):
            ch = s[i]
            if i + 1 < len(s) and s[i + 1] == ch and ch != " ":
                out.append(ch); i += 2
            else:
                out.append(ch); i += 1
        return "".join(out)
    return s


def limpar_linhas(texto: str) -> list[str]:
    """Quebra em linhas e aplica todas as limpezas linha-a-linha."""
    linhas_in = texto.split("\n")
    linhas: list[str] = []

    # Cortar tudo a partir do início de "LEITURAS DA SEMANA" / anúncios
    # laterais / data isolada após a Antífona Mariana.
    # Atenção: "Antífona Mariana" pode estar quebrado em "Ant\nífona Mariana"
    # nas linhas brutas — verificamos as duas formas.
    # Importante: SÓ cortamos por estes marcadores DEPOIS da Antífona Mariana,
    # porque "60o Dia Mundial..." pode aparecer também como SUBTÍTULO no
    # cabeçalho da Missa (ex.: Solenidade da Ascensão = "60º Dia Mundial das
    # Comunicações Sociais"). Antes da Antífona Mariana esses marcadores
    # podem ser conteúdo legítimo.
    fim = None
    idx_antifona_mariana = None
    for i, l in enumerate(linhas_in):
        s = l.strip()
        if s.lower() == "antífona mariana":
            idx_antifona_mariana = i
        elif (s == "Ant" and i + 1 < len(linhas_in)
              and linhas_in[i + 1].strip().lower().startswith("ífona mariana")):
            idx_antifona_mariana = i

        if idx_antifona_mariana is None:
            continue  # antes da Antífona Mariana, não corta

        if (s.upper() == "LEITURAS DA SEMANA"
                or s.upper().startswith("ORAÇÃO PELO DIA")
                or s.upper().startswith("ORAÇÃO DO DIZIMISTA")
                or "EE AAÍÍ" in s
                or re.match(r"^\d{1,2}[º°o]?\s+Dia\s+Mundial", s, re.IGNORECASE)):
            fim = i
            break
        if (i > idx_antifona_mariana + 1
                and re.fullmatch(r"\d{1,2}\s+de\s+\w+\s+de\s+\d{4}\s*", s)):
            fim = i
            break
    if fim is not None:
        linhas_in = linhas_in[:fim]

    # Filtro de "créditos de música": uma quebra de 2 linhas começando com
    # "Entrada:" e terminando com "Antífona Mariana" / "Liturgia das Horas"
    # ou similar. Detecta o INÍCIO e remove até o FIM.
    indices_credito_remover = set()
    i = 0
    while i < len(linhas_in):
        l = linhas_in[i]
        if re.match(r"^\s*Entrada:\s+", l):
            indices_credito_remover.add(i)
            # Se a 1ª linha JÁ parece um crédito completo (contém Comunhão:/
            # Final:/Ofertas: e termina com '.'), o crédito é apenas essa.
            ja_completo = (
                re.search(r"(Comunh[ãa]o:|Final:|Ofertas:)", l)
                and l.rstrip().endswith(".")
            )
            if ja_completo:
                i += 1
                continue
            # Senão: continuação em até 2 linhas, parando ao encontrar uma
            # que termine com '.' (fim do crédito).
            j = i + 1
            while j < len(linhas_in) and j - i <= 2:
                indices_credito_remover.add(j)
                if linhas_in[j].rstrip().endswith("."):
                    break
                j += 1
            i = j + 1
            continue
        i += 1

    # Limpezas linha a linha
    for idx, raw in enumerate(linhas_in):
        if idx in indices_credito_remover:
            continue
        l = raw.rstrip()
        # Dedupe de chars duplicados
        l = _dedupe_chars(l)
        # Remove "+" / "=" / "—" isolados (símbolo de cruz no folheto)
        if l.strip() in {"=", "+", "—", "–"}:
            continue
        # Versículo bíblico sobrescrito sozinho — pode ser "15" ou "15 16" ou "5 6 7"
        if re.fullmatch(r"\s*(?:\d{1,3}\s+)*\d{1,3}\s*", l):
            continue
        # Posturas
        if l.strip() in {"(De pé)", "(Sentados)", "(Sentado)", "(De Pé)",
                         "(Em pé)"}:
            continue
        # Cantos selecionados / aprovação eclesiástica / footer editora
        if any(s in l for s in ["EDITORA NOSSA SENHORA DA PAZ",
                                "PORTAL DA ARQUIDIOCESE",
                                "Cantos selecionados pela Comissão",
                                "COM APROVAÇÃO ECLESIÁSTICA",
                                "Publicação da Comissão",
                                "Rua Joana Angélica",
                                "Rua Benjamin Constant",
                                "www.arqrio.org.br",
                                "Vicariato para A comunicação social",
                                "Folheto Oficial",
                                "Versão Celular"]):
            continue
        linhas.append(l)

    # Junta hifenização: "celebra-\ndos" -> "celebrados". ENCADEADO:
    # se a linha juntada ainda termina com "-" e a próxima começa com letra
    # (lowercase OU palavra inteira em maiúscula tipo "CORPO"), continua.
    junta: list[str] = []
    i = 0
    while i < len(linhas):
        atual = linhas[i].rstrip()
        while (atual.endswith("-")
                and i + 1 < len(linhas)
                and linhas[i + 1]
                and linhas[i + 1][0].isalpha()):
            prox_strip = linhas[i + 1].lstrip()
            primeira_palavra = prox_strip.split()[0] if prox_strip.split() else ""
            primeira_palavra_clean = re.sub(r"[^A-Za-zÀ-ÿ]", "", primeira_palavra)
            if (primeira_palavra_clean and
                (primeira_palavra_clean[0].islower()
                 or (primeira_palavra_clean.isupper() and len(primeira_palavra_clean) >= 2))):
                atual = atual[:-1] + prox_strip
                i += 1
            else:
                break
        junta.append(atual)
        i += 1
    linhas = junta

    # Letra capitulada inicial: linha = uma maiúscula isolada + próxima começando com lower
    # Caso especial: "P\n-vos" (drop cap P sobreposto a "unir-vos") → o
    # P pertence ao INÍCIO de um parágrafo P., e o "-vos" deve emendar com
    # a palavra anterior preservando o hífen.
    junta = []
    i = 0
    while i < len(linhas):
        atual = linhas[i].rstrip()
        if (re.fullmatch(r"[A-ZÀ-Ý]", atual)
                and i + 1 < len(linhas)
                and linhas[i + 1]):
            prox = linhas[i + 1]
            if prox[0].islower():
                junta.append(atual + prox)
                i += 2
                continue
            # Drop cap "P" entre "...palavra-" e "-resto"
            if (prox.startswith("-") and len(prox) > 1
                    and prox[1].isalpha()
                    and atual in ("P", "T", "L")):
                # Junta a anterior preservando hífen (ou descartando o
                # extra) e PREFIXA atualizando a linha de início do parágrafo.
                if junta and junta[-1].rstrip().endswith("-"):
                    # "unir-" + "-vos a..." → "unir-vos a..."
                    junta[-1] = junta[-1].rstrip() + prox.lstrip("-")
                else:
                    junta.append(prox.lstrip("-"))
                # Reinjeta "X. " no INÍCIO do parágrafo: volta na pilha
                # até a primeira linha após "T./P./L. Algo" ou linha em
                # branco e prefixa.
                marc = atual + ". "
                idx_inicio = len(junta) - 1
                k = idx_inicio
                while k > 0:
                    prev = junta[k - 1].strip()
                    if (not prev
                            or re.match(r"^[PTL]\.\s+", prev)
                            or prev in CABECALHOS_BLOCO.values()
                            or prev.startswith(CABECALHO_TAG)):
                        break
                    k -= 1
                if not junta[k].lstrip().startswith(("P.", "T.", "L.")):
                    junta[k] = marc + junta[k].lstrip()
                i += 2
                continue
        junta.append(linhas[i])
        i += 1
    linhas = junta

    # "Ant\nífona ..." -> "Antífona ..."
    junta = []
    i = 0
    while i < len(linhas):
        atual = linhas[i].rstrip()
        if (atual == "Ant"
                and i + 1 < len(linhas)
                and linhas[i + 1].lstrip().lower().startswith("ífona")):
            junta.append("Antífona" + linhas[i + 1].lstrip()[len("ífona"):])
            i += 2
            continue
        junta.append(linhas[i])
        i += 1
    linhas = junta

    # Remove "(Sentados)" / "(De pé)" embutidos no FIM de linhas (ex.: "(At ...) (Sentados)")
    posturas_re = re.compile(r"\s*\((?:De pé|De Pé|Em pé|Sentados?|Sentado)\)\s*")
    linhas = [posturas_re.sub("", l).rstrip() for l in linhas]

    # Hifenização in-line (algum hífen ficou seguido de espaço por causa do PDF):
    # "Espí- rito" -> "Espírito"
    # Cuidado: NÃO desfazer hifens reais ("todo-poderoso").
    # Heurística: hífen seguido de espaço entre duas partes minúsculas que formam
    # palavra plausível (sem espaço duplicado em meio).
    def desfazer_hifen_espaco(s: str) -> str:
        return re.sub(r"(\w+)-\s+(\w+)",
                      lambda m: m.group(1) + m.group(2)
                      if (m.group(2)[0].islower())
                      else m.group(0),
                      s)
    linhas = [desfazer_hifen_espaco(l) for l in linhas]

    return [l for l in linhas if l is not None]


# =====================================================================
# ETAPA 3 — IDENTIFICAR SEÇÕES NUMERADAS (ANTES DE REORDENAR DROP CAPS)
# =====================================================================
#
# Padrão típico no PDF (versão celular):
#     ...texto da estrofe anterior...
#     2.
#     Saudação
#     Em nome do Pai...
#     P.
#     T. Amém.
#
# Queremos: "2. Saudação" como cabeçalho próprio. Removemos as duas
# linhas "2." + "Saudação" e inserimos como uma nova linha-cabeçalho.

CABECALHO_TAG = "\x00SECAO\x00"  # marcador interno


def detectar_secoes(linhas: list[str]) -> list[str]:
    """Detecta padrão 'N.\\nNome da seção N' e o substitui por
    '\\x00SECAO\\x00N. Nome da seção'. Retorna lista de linhas modificada."""
    out: list[str] = []
    i = 0
    while i < len(linhas):
        l = linhas[i].rstrip()
        m = re.fullmatch(r"\s*(\d{1,2})\.\s*", l)
        if m and i + 1 < len(linhas):
            num = int(m.group(1))
            nome_linha = linhas[i + 1].strip()
            if _eh_nome_secao(num, nome_linha):
                # Junta numero + nome em uma linha-cabeçalho
                out.append(f"{CABECALHO_TAG}{num}. {nome_linha}")
                i += 2
                continue
        out.append(linhas[i])
        i += 1
    return out


# =====================================================================
# ETAPA 4 — REORDENAR DROP CAPS (P./T./L. e numeração de estrofe)
# =====================================================================

def reordenar_drop_caps(linhas: list[str]) -> list[str]:
    """Move 'P.', 'T.', 'L.' e numeração de estrofes que ficaram em linha
    própria DEPOIS do texto para ANTES do parágrafo a que pertencem.

    Estratégia: cada drop cap aparece DEPOIS da primeira linha do parágrafo
    que lhe pertence. Movemos prefixando à linha imediatamente anterior."""
    out: list[str] = []
    i = 0
    while i < len(linhas):
        l = linhas[i]
        # Pular linhas-cabeçalho de seção
        if l.startswith(CABECALHO_TAG):
            out.append(l)
            i += 1
            continue

        s = l.strip()
        # Drop cap "P.", "T.", "L."
        m_dc = re.fullmatch(r"([PTL])\s*\.", s)
        if m_dc and out:
            marc = m_dc.group(1) + "."
            anterior = out[-1]
            if (anterior.strip()
                    and not anterior.startswith(CABECALHO_TAG)
                    and not _linha_eh_titulo(anterior)):
                out[-1] = f"{marc} {anterior.lstrip()}"
                i += 1
                continue
            # Caso especial: anterior é "(referência)" — pula até linha de texto
            j = len(out) - 1
            while j >= 0 and (not out[j].strip() or out[j].startswith(CABECALHO_TAG)
                              or _linha_eh_titulo(out[j])):
                j -= 1
            if j >= 0:
                out[j] = f"{marc} {out[j].lstrip()}"
                i += 1
                continue

        # Numeração de estrofe "N." em linha própria
        m_ne = re.fullmatch(r"(\d{1,2})\s*\.", s)
        if m_ne and out:
            num = m_ne.group(1)
            anterior = out[-1]
            if (anterior.strip()
                    and not anterior.startswith(CABECALHO_TAG)
                    and not _linha_eh_titulo(anterior)):
                out[-1] = f"{num}. {anterior.lstrip()}"
                i += 1
                continue

        out.append(l)
        i += 1
    return out


def _linha_eh_titulo(l: str) -> bool:
    s = l.strip()
    if not s:
        return True
    if s in CABECALHOS_BLOCO:
        return True
    if s.lower().startswith("antífona"):
        return True
    if re.match(r"^\(.+\)$", s):
        return True
    if s.startswith("Leitura "):
        return True
    if s.startswith("Prefácio"):
        return True
    return False


# =====================================================================
# ETAPA 5 — JUNTAR LINHAS EM PARÁGRAFOS LÓGICOS
# =====================================================================

def juntar_paragrafos(linhas: list[str]) -> list[str]:
    """Recebe a lista já reordenada (com cabeçalhos marcados) e devolve
    uma lista de parágrafos lógicos, com strings vazias entre blocos."""
    paragrafos: list[str] = []
    buf = ""
    for l in linhas:
        s = l.strip()
        if not s:
            if buf:
                paragrafos.append(buf.strip()); buf = ""
            paragrafos.append("")  # marca de quebra
            continue
        if l.startswith(CABECALHO_TAG):
            if buf:
                paragrafos.append(buf.strip()); buf = ""
            paragrafos.append(l)  # mantém com marker
            continue
        if _inicia_novo_paragrafo(s):
            if buf:
                paragrafos.append(buf.strip()); buf = ""
            buf = s
            continue
        if _eh_linha_titulo_propria(s):
            if buf:
                paragrafos.append(buf.strip()); buf = ""
            paragrafos.append(s)  # cabeçalho como linha própria
            continue
        if buf:
            buf = buf + " " + s
        else:
            buf = s
    if buf:
        paragrafos.append(buf.strip())

    # Compactar quebras múltiplas em uma só
    out: list[str] = []
    prev_blank = False
    for p in paragrafos:
        if p == "":
            if not prev_blank and out:
                out.append("")
                prev_blank = True
        else:
            out.append(p)
            prev_blank = False

    # Pós-limpeza: hifenização inline com espaço ("per- doe" -> "perdoe").
    # NÃO alterar hifens reais ("todo-poderoso") onde NÃO há espaço.
    re_hifen_esp = re.compile(r"(\w{2,})-\s+(\w+)")

    def _undo(s: str) -> str:
        anterior = None
        atual = s
        while anterior != atual:
            anterior = atual
            atual = re_hifen_esp.sub(
                lambda m: (m.group(1) + m.group(2))
                if m.group(2)[0].islower()
                else m.group(0),
                atual)
        return atual

    out = [_undo(p) if p else p for p in out]
    return out


def _inicia_novo_paragrafo(s: str) -> bool:
    """True se a linha s deve INICIAR um novo parágrafo lógico."""
    if re.match(r"^[PTL]\.\s+\S", s):
        return True
    if re.match(r"^\d{1,2}\.\s+\S", s):
        return True
    if re.match(r"^REFRÃO:", s, re.IGNORECASE):
        return True
    return False


def _eh_linha_titulo_propria(s: str) -> bool:
    """True se a linha é cabeçalho/título que fica em linha própria
    (não junta com texto antes nem depois)."""
    if s in CABECALHOS_BLOCO:
        return True
    if s.lower().startswith("antífona "):
        return True
    if re.match(r"^Leitura\s+d[ao]s?", s):
        return True
    if re.match(r"^Prefácio\s+", s):
        return True
    if re.fullmatch(r"\(.+\)", s):  # referência bíblica isolada
        return True
    if s.lower().startswith("momento de silêncio"):
        return True
    if s.lower().startswith("(momento de silêncio"):
        return True
    return False


# =====================================================================
# ETAPA 6 — DETECTAR E EXTRAIR CABEÇALHO DA MISSA + INTRO
# =====================================================================
#
# Roda em LINHAS (antes da junção de parágrafos) para evitar que tudo
# seja colado em um parágrafo gigante.

CABECALHO_MISSA_INICIO_TAG = "\x00CAB_MISSA\x00"  # marca uma linha como "início do bloco do cabeçalho da Missa" — esse bloco será montado no final


def detectar_cabecalho_missa(linhas: list[str]) -> tuple[list[str], list[str]]:
    """Encontra nas primeiras linhas:
       - "Ano A – no NN – DD de mes de YYYY"
       - "Nº Domingo da..." (descartável)
       - "Ano Jubilar Arquidiocesano [– Subtítulo]"
    Remove essas linhas e devolve um BLOCO de cabeçalho pronto para Holyrics
    (com SEJAM BEM-VINDOS) + a lista de linhas restantes (a primeira já é a
    intro com letra capitulada aplicada na primeira letra).

    Retorna (bloco_cabecalho_pronto, linhas_restantes_com_intro_marcada).
    """
    re_cab_full = re.compile(
        r"^Ano\s+([ABC])\s*[–\-]\s*n[º°o]\s*(\d+)\s*[–\-]\s*"
        r"(\d{1,2})\s+de\s+(\w+)\s+de\s+(\d{4})\s*$",
        re.IGNORECASE)
    re_jub = re.compile(r"^Ano\s+Jubilar\b", re.IGNORECASE)
    re_ritos = re.compile(r"^Ritos\s+Iniciais\s*$", re.IGNORECASE)

    idx_cab = None
    cab_match = None

    # Procura o cabeçalho de data nas primeiras linhas
    for i, l in enumerate(linhas[:30]):
        s = l.strip()
        if not s:
            continue
        m = re_cab_full.match(s)
        if m:
            idx_cab = i; cab_match = m; break

    if cab_match is None:
        return [], list(linhas)

    # Após o cabeçalho de data: consome subtítulos curtos descartáveis
    # ("X Domingo da Páscoa", "Domingo de Pentecostes", "Solenidade de X",
    # "Festa de X", "Dia das Mães", etc.) e captura "Ano Jubilar..." se
    # aparecer. Para no início da intro (parágrafo longo).
    indices_remover = {idx_cab}
    cab_jubilar = None
    j = idx_cab + 1
    while j < len(linhas):
        s = linhas[j].strip()
        if not s:
            j += 1; continue
        if re_ritos.match(s):
            break  # chegou em "Ritos Iniciais" — para
        if re_jub.match(s):
            cab_jubilar = s
            indices_remover.add(j)
            j += 1; continue
        # Subtítulo descartável: linha curta (poucas palavras) sem ponto
        # final e sem letras minúsculas no meio típicas de prosa.
        n_palavras = len(s.split())
        termina_pontuacao = s.endswith((".", ",", "!", "?", ":", ";"))
        if n_palavras <= 8 and not termina_pontuacao:
            indices_remover.add(j)
            j += 1; continue
        break  # parágrafo de intro

    ano_litur = cab_match.group(1).upper()
    numero = cab_match.group(2)
    dia = cab_match.group(3).zfill(2)
    mes = cab_match.group(4).lower()
    ano = cab_match.group(5)

    # Constrói as linhas do "slide 1" do cabeçalho. Ficam JUNTAS no mesmo
    # slide via '\n' interno.
    linhas_cab1 = [f"Ano {ano_litur} – nº {numero}",
                   f"{dia} de {mes} de {ano}"]
    if cab_jubilar:
        linhas_cab1.append(cab_jubilar)
    cab_slide1 = "\n".join(linhas_cab1)

    cab_slide2 = "SEJAM BEM-VINDOS!\nREZEMOS PELAS SEGUINTES INTENÇÕES"

    bloco_cabecalho = [cab_slide1, "", cab_slide2, ""]

    restantes = [l for k, l in enumerate(linhas) if k not in indices_remover]

    # Aplica letra capitulada à PRIMEIRA letra do PRIMEIRO parágrafo de intro.
    # Para isso, encontra a primeira linha não-vazia e prefixa <color>X</color>.
    for k, l in enumerate(restantes):
        if l.strip() and l.strip()[0].isalpha():
            primeira = l.lstrip()
            ch = primeira[0]
            modificada = (f"<color: {COR}>{ch}</color>" + primeira[1:])
            restantes[k] = modificada
            break

    return bloco_cabecalho, restantes


# =====================================================================
# ETAPA 7 — APLICAR FORMATAÇÃO HOLYRICS
# =====================================================================

def aplicar_formatacao(paragrafos: list[str]) -> list[str]:
    """Aplica tags <color> e <i> nos elementos litúrgicos."""
    out: list[str] = []
    for p in paragrafos:
        if p == "":
            out.append("")
            continue

        # Cabeçalho de bloco litúrgico
        if p in CABECALHOS_BLOCO:
            out.append(CABECALHOS_BLOCO[p])
            continue

        # Cabeçalho de seção numerada (CABECALHO_TAG)
        if p.startswith(CABECALHO_TAG):
            out.append(p[len(CABECALHO_TAG):])  # ex: "1. Canto de Entrada"
            continue

        # P. / T. / L. iniciais
        m = re.match(r"^([PTL])\.\s+(.*)", p, re.DOTALL)
        if m:
            letra = m.group(1)
            resto = m.group(2)
            if letra == "L":
                out.append(f"<color: {COR}>{letra}.</color><i> {resto}")
            else:
                out.append(f"<color: {COR}>{letra}.</color> {resto}")
            continue

        # REFRÃO:
        m = re.match(r"^REFRÃO:\s*(.*)", p, re.IGNORECASE | re.DOTALL)
        if m:
            out.append(f"<color: {COR}>REFRÃO:</color> {m.group(1)}")
            continue

        # Numeração de estrofe "N. ..."
        m = re.match(r"^(\d{1,2})\.\s+(.+)", p, re.DOTALL)
        if m:
            num = m.group(1)
            resto = m.group(2)
            out.append(f"<color: {COR}>{num}.</color> {resto}")
            continue

        out.append(p)
    return out


# =====================================================================
# ETAPA 7.5 — REPETIR REFRÃO/RESPOSTA APÓS CADA ESTROFE
# =====================================================================
#
# Em cantos (Entrada, Salmo, Aclamação, Ofertas, Comunhão), o REFRÃO é
# repetido entre/após cada estrofe quando se canta — mas o folheto só
# mostra uma vez. Replicamos aqui automaticamente.
# Na Oração dos Fiéis, a resposta T. é repetida após cada intenção.

# Identificação por NOME (independente do número, que varia entre Missas)
NOMES_SECAO_REFRAO = {
    "canto de entrada", "salmo responsorial", "aclamação ao evangelho",
    "canto das ofertas", "canto de comunhão",
}
NOMES_SECAO_ORACAO_FIEIS = {"oração dos fiéis"}


_RE_REFRAO_FMT = re.compile(
    r"^<color:\s*[^>]+>\s*REFR[ÃA]O:\s*</color>", re.IGNORECASE)
_RE_RESPOSTA_T_FMT = re.compile(
    r"^<color:\s*[^>]+>\s*T\.\s*</color>", re.IGNORECASE)
_RE_ESTROFE_FMT = re.compile(
    r"^<color:\s*[^>]+>\s*(?:\d{1,2}|L)\.\s*</color>", re.IGNORECASE)


def _eh_refrao_fmt(p: str) -> bool:
    return bool(_RE_REFRAO_FMT.match(p.strip()))


def _eh_resposta_t_fmt(p: str) -> bool:
    return bool(_RE_RESPOSTA_T_FMT.match(p.strip()))


def _eh_estrofe_fmt(p: str) -> bool:
    return bool(_RE_ESTROFE_FMT.match(p.strip()))


def _eh_cabecalho_secao_qualquer(p: str) -> bool:
    """True se p é um cabeçalho 'N. Nome de seção conhecida'."""
    return _nome_da_secao(p) is not None


def _eh_cabecalho_de_corte(p: str) -> bool:
    """Cabeçalhos que terminam uma seção: bloco litúrgico ou outra seção."""
    if p in {"RITOS INICIAIS", "LITURGIA DA PALAVRA",
             "LITURGIA EUCARÍSTICA", "RITOS FINAIS", "AVISOS"}:
        return True
    if _eh_cabecalho_secao_qualquer(p):
        return True
    return False


def replicar_refraos(paragrafos: list[str]) -> list[str]:
    """Replica o REFRÃO/T. dentro de cada seção apropriada (canto/salmo/
    aclamação/ofertas/comunhão e Oração dos Fiéis)."""
    out: list[str] = []
    i = 0
    n = len(paragrafos)
    while i < n:
        p = paragrafos[i]
        nome = _nome_da_secao(p)
        is_canto = nome in NOMES_SECAO_REFRAO
        is_oracao = nome in NOMES_SECAO_ORACAO_FIEIS
        if is_canto or is_oracao:
            j = i + 1
            while j < n:
                if _eh_cabecalho_de_corte(paragrafos[j]):
                    if _nome_da_secao(paragrafos[j]) == nome:
                        j += 1; continue
                    break
                j += 1
            bloco = paragrafos[i:j]
            if is_oracao:
                bloco = _replicar_resposta_oracao(bloco)
            else:
                bloco = _replicar_refrao_canto(bloco)
            out.extend(bloco)
            i = j
            continue
        out.append(p)
        i += 1
    return out


def _replicar_refrao_canto(secao: list[str]) -> list[str]:
    """Em uma seção de canto/salmo: REFRÃO repetido após cada estrofe.

    - Se o original começa com REFRÃO antes da 1ª estrofe:
        REFRÃO, e1, REFRÃO, e2, REFRÃO, ..., en, REFRÃO
    - Se o original começa com a 1ª estrofe (sem refrão antes):
        e1, REFRÃO, e2, REFRÃO, ..., en, REFRÃO
    Mantém os demais elementos (cabeçalhos e textos avulsos) na ordem.
    """
    # Coleta estrofes e o primeiro REFRÃO
    refrao = None
    primeira_pos_canto = None  # "R" se REFRÃO veio primeiro, "E" se estrofe
    estrofes_pos = []   # índices das estrofes em `secao`
    refrao_pos = []     # índices dos REFRÃOs em `secao`
    extras_finais_pos = []  # índices APÓS o último elemento canto
    ultimo_canto_idx = -1
    for k, p in enumerate(secao):
        if not p.strip():
            continue
        if _eh_refrao_fmt(p):
            if refrao is None:
                refrao = p
            refrao_pos.append(k)
            ultimo_canto_idx = k
            if primeira_pos_canto is None:
                primeira_pos_canto = "R"
        elif _eh_estrofe_fmt(p):
            estrofes_pos.append(k)
            ultimo_canto_idx = k
            if primeira_pos_canto is None:
                primeira_pos_canto = "E"
    if refrao is None or not estrofes_pos:
        return secao

    # Reconstrói: cabeçalho e tudo ANTES do primeiro elemento canto
    primeiro_canto_idx = min(
        (refrao_pos + estrofes_pos)
    )
    saida: list[str] = list(secao[:primeiro_canto_idx])
    # Bloco de estrofes/refrão
    estrofes = [secao[k] for k in estrofes_pos]
    if primeira_pos_canto == "R":
        saida.append(refrao)
        for est in estrofes:
            saida.append(est)
            saida.append(refrao)
    else:
        for est in estrofes:
            saida.append(est)
            saida.append(refrao)
    # Tudo depois do último elemento canto (ex: "Momento de silêncio...")
    saida.extend(secao[ultimo_canto_idx + 1:])
    return saida


def _replicar_resposta_oracao(secao: list[str]) -> list[str]:
    """Oração dos Fiéis: replica o "T. ..." (resposta da assembleia) APÓS
    cada intenção numerada e após o "(Outras intenções)" placeholder.

    Estrutura típica:
        13. Oração dos Fiéis
        P. intro
        T. resposta
        1. intenção
        2. intenção
        3. ...
        (Outras intenções)
        P. conclusão
        T. Amém.
    """
    # Identifica a primeira resposta T. (a "resposta repetível")
    resposta_t = None
    for p in secao:
        if _eh_resposta_t_fmt(p):
            resposta_t = p
            break
    if resposta_t is None:
        return secao

    # Reconstrói: percorre os elementos. Após cada estrofe e após
    # "(Outras intenções)", insere a resposta T. (a menos que já esteja).
    saida: list[str] = []
    i = 0
    n = len(secao)
    while i < n:
        p = secao[i]
        saida.append(p)
        # Se é estrofe numerada → insere T. após (se já não vier T. no próximo
        # parágrafo não-vazio)
        if _eh_estrofe_fmt(p) or re.fullmatch(r"\(.+\)", p.strip()):
            # Olha o próximo não-vazio
            j = i + 1
            while j < n and not secao[j].strip():
                j += 1
            if j < n and _eh_resposta_t_fmt(secao[j]):
                # já tem resposta T. logo após — segue
                pass
            else:
                # Não pode inserir T. se o próximo é P. (final) ou bloco
                saida.append(resposta_t)
        i += 1
    return saida


# =====================================================================
# ETAPA 8 — DIVIDIR PARTE 1 / PARTE 2 (na Homilia)
# =====================================================================

def dividir_partes(paragrafos: list[str]) -> tuple[list[str], list[str]]:
    """Localiza o cabeçalho da Homilia (qualquer numeração — em Pentecostes
    é '12. Homilia' por causa da Sequência) e divide:
    - Parte 1: do início até (e incluindo) o cabeçalho da Homilia
    - Parte 2: começa com cabeçalho 'N. Homilia' (repetido)
    """
    idx = None
    for i, p in enumerate(paragrafos):
        s = p.strip()
        if re.match(r"^\d{1,2}\.\s*Homil[íi]a\s*$", s, re.IGNORECASE):
            idx = i
            break
    if idx is None:
        return paragrafos, []
    parte1 = list(paragrafos[:idx + 1])
    parte2 = list(paragrafos[idx:])
    while parte1 and parte1[-1] == "":
        parte1.pop()
    while parte2 and parte2[-1] == "":
        parte2.pop()
    return parte1, parte2


# =====================================================================
# ETAPA 9 — QUEBRAR EM SLIDES
# =====================================================================

def _eh_cabecalho_estrutural(p: str) -> bool:
    if p in {"RITOS INICIAIS", "LITURGIA DA PALAVRA",
             "LITURGIA EUCARÍSTICA", "RITOS FINAIS", "AVISOS"}:
        return True
    # Cabeçalho 'N. Nome de seção conhecida' — aceita qualquer N de 1 a 99
    if _nome_da_secao(p) is not None:
        return True
    if p.lower().startswith("antífona "):
        return True
    if re.fullmatch(r"\(.+\)", p):
        return True
    if p.startswith("Leitura "):
        return True
    if p.startswith("Prefácio"):
        return True
    return False



def quebrar_em_slides(paragrafos: list[str]) -> list[str]:
    """Recebe paragrafos formatados e devolve uma lista pronta para escrita
    com linhas em branco entre slides."""
    saida: list[str] = []
    i = 0
    while i < len(paragrafos):
        p = paragrafos[i]
        if p == "":
            i += 1
            continue

        if _eh_cabecalho_estrutural(p):
            cabecalhos = [p]
            j = i + 1
            conteudo = None
            while j < len(paragrafos):
                if paragrafos[j] == "":
                    j += 1; continue
                if _eh_cabecalho_estrutural(paragrafos[j]):
                    cabecalhos.append(paragrafos[j]); j += 1; continue
                conteudo = paragrafos[j]; j += 1
                break

            if saida and saida[-1] != "":
                saida.append("")

            if conteudo is None:
                saida.extend(cabecalhos)
            else:
                pedacos = _quebrar_paragrafo_longo(conteudo, ALVO_CHARS_SLIDE)
                primeiro = pedacos[0] if pedacos else ""
                saida.extend(cabecalhos)
                if primeiro:
                    saida.append(primeiro)
                for pt in pedacos[1:]:
                    saida.append("")
                    saida.append(pt)
            i = j
            continue

        if _comprimento_visual(p) <= ALVO_CHARS_SLIDE * 1.1:
            if saida and saida[-1] != "":
                saida.append("")
            saida.append(p)
            i += 1
            continue

        partes = _quebrar_paragrafo_longo(p, ALVO_CHARS_SLIDE)
        for pt in partes:
            if saida and saida[-1] != "":
                saida.append("")
            saida.append(pt)
        i += 1

    return saida


def _comprimento_visual(p: str) -> int:
    sem_tags = re.sub(r"<[^>]+>", "", p)
    if "\n" in sem_tags:
        return max(len(l) for l in sem_tags.split("\n"))
    return len(sem_tags)


def _quebrar_paragrafo_longo(p: str, alvo: int) -> list[str]:
    if _comprimento_visual(p) <= alvo * 1.1:
        return [p]
    tag_match = re.match(r"^(<color:[^>]+>[^<]+</color>(?:<i>)?\s*)", p)
    prefixo = ""
    corpo = p
    if tag_match:
        prefixo = tag_match.group(1)
        corpo = p[len(prefixo):]
    pedacos = _split_e_agrupar(corpo, r"(?<=[.!?])\s+", alvo)
    pedacos = _refinar_pedacos(pedacos, r"(?<=[:;])\s+", alvo)
    pedacos = _refinar_pedacos(pedacos, r"(?<=[,])\s+", alvo)
    if pedacos:
        pedacos[0] = prefixo + pedacos[0]
    return pedacos


def _split_e_agrupar(corpo: str, split_re: str, alvo: int) -> list[str]:
    fragmentos = re.split(split_re, corpo)
    pedacos: list[str] = []
    buf = ""
    for s in fragmentos:
        candidato = (buf + " " + s).strip() if buf else s
        if _comprimento_visual(candidato) <= alvo * 1.1 or not buf:
            buf = candidato
        else:
            pedacos.append(buf)
            buf = s
    if buf:
        pedacos.append(buf)
    return pedacos


def _refinar_pedacos(pedacos: list[str], split_re: str, alvo: int) -> list[str]:
    out: list[str] = []
    for p in pedacos:
        if _comprimento_visual(p) <= alvo * 1.1:
            out.append(p); continue
        out.extend(_split_e_agrupar(p, split_re, alvo))
    return out


def montar_txt(linhas_finais: list[str]) -> str:
    saida: list[str] = ["<styled>"]
    prev_blank = False
    for l in linhas_finais:
        if l == "":
            if not prev_blank and saida and saida[-1] != "<styled>":
                saida.append("")
                prev_blank = True
            continue
        saida.append(l)
        prev_blank = False
    return "\n".join(saida).rstrip() + "\n"


def converter(pdf_path: Path, pasta_saida: Path) -> tuple[Path, Path]:
    pasta_saida.mkdir(parents=True, exist_ok=True)
    base = pdf_path.stem.replace("_CELULAR", "").replace(" - CELULAR", "")

    bruto = extrair_texto_pdf(pdf_path)
    linhas = limpar_linhas(bruto)
    bloco_cabecalho, linhas = detectar_cabecalho_missa(linhas)
    linhas = detectar_secoes(linhas)
    linhas = reordenar_drop_caps(linhas)
    paragrafos = juntar_paragrafos(linhas)
    formatados = aplicar_formatacao(paragrafos)
    formatados = replicar_refraos(formatados)
    completo = list(bloco_cabecalho) + formatados
    parte1, parte2 = dividir_partes(completo)
    slides1 = quebrar_em_slides(parte1)
    slides2 = quebrar_em_slides(parte2)

    txt1 = montar_txt(slides1)
    txt2 = montar_txt(slides2)

    p1 = pasta_saida / f"{base} - Parte 1.txt"
    p2 = pasta_saida / f"{base} - Parte 2.txt"
    p1.write_text(txt1, encoding="utf-8")
    p2.write_text(txt2, encoding="utf-8")
    return p1, p2


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Converter folheto da Missa para TXTs do Holyrics.")
    parser.add_argument("pdf", type=Path,
                        help="Caminho do PDF (versao celular).")
    parser.add_argument("--saida", type=Path, default=None,
                        help="Pasta de saida (padrao: a mesma do PDF).")
    args = parser.parse_args(argv)
    pdf = args.pdf
    if not pdf.is_file():
        print(f"ERRO: arquivo nao encontrado: {pdf}", file=sys.stderr)
        return 2
    saida = args.saida or pdf.parent
    p1, p2 = converter(pdf, saida)
    print("OK")
    print(f"  {p1}")
    print(f"  {p2}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
