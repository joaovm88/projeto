"""Módulo de domínio puro: sanitização de texto e extração de entidades jurídicas.

Este módulo não possui qualquer dependência de framework, banco de dados ou
infraestrutura (FastAPI, Celery, SQLAlchemy). Ele recebe texto e devolve texto/dados,
o que o torna trivialmente testável com testes unitários simples e reutilizável em
qualquer contexto (worker, script batch, notebook de análise, etc).
"""

from __future__ import annotations

import re
import unicodedata
from collections import Counter

# ---------------------------------------------------------------------------
# Sanitização
# ---------------------------------------------------------------------------

_HTML_TAG_RE = re.compile(r"</?[a-zA-Z!][^<>]{0,200}>?")
_PAGE_NUMBER_RE = re.compile(
    r"^\s*(?:p[aá]gina\s+)?\d{1,4}(?:\s*/\s*\d{1,4}|\s+de\s+\d{1,4})?\s*$",
    re.IGNORECASE | re.MULTILINE,
)
_MULTI_SPACE_RE = re.compile(r"[ \t ]+")
_MULTI_BLANK_LINE_RE = re.compile(r"\n{3,}")
_FORM_FEED_RE = re.compile(r"\x0c")


def normalize_unicode(text: str) -> str:
    """Normaliza para NFC e remove caracteres de controle não imprimíveis."""
    normalized = unicodedata.normalize("NFC", text)
    return "".join(
        ch for ch in normalized if ch in ("\n", "\t") or unicodedata.category(ch)[0] != "C"
    )


def strip_html_tags(text: str) -> str:
    """Remove tags HTML (inclusive tags quebradas/incompletas, comuns em OCR/scraping)."""
    return _HTML_TAG_RE.sub(" ", text)


def strip_page_numbers(text: str) -> str:
    """Remove linhas compostas apenas por numeração de página."""
    return _PAGE_NUMBER_RE.sub("", text)


def strip_repeated_lines(text: str, min_occurrences: int = 3) -> str:
    """Remove linhas que se repetem em múltiplas "páginas" do documento.

    Cabeçalhos e rodapés (ex.: "Diário de Justiça Eletrônico - TJMG") tendem a se
    repetir idênticos em cada página de uma publicação. Uma linha curta que aparece
    ``min_occurrences`` vezes ou mais é tratada como ruído de layout e removida.
    """
    lines = text.split("\n")
    stripped = [line.strip() for line in lines]
    counts = Counter(line for line in stripped if line and len(line) <= 120)
    noisy = {line for line, count in counts.items() if count >= min_occurrences}
    return "\n".join(line for line, s in zip(lines, stripped, strict=True) if s not in noisy)


def collapse_whitespace(text: str) -> str:
    """Colapsa espaços duplicados e linhas em branco excessivas."""
    text = _MULTI_SPACE_RE.sub(" ", text)
    text = _MULTI_BLANK_LINE_RE.sub("\n\n", text)
    return "\n".join(line.strip() for line in text.split("\n")).strip()


def sanitize(raw_text: str) -> str:
    """Pipeline completo de higienização: bruto e ruidoso -> limpo e padronizado."""
    text = _FORM_FEED_RE.sub("\n", raw_text)
    text = normalize_unicode(text)
    text = strip_html_tags(text)
    text = strip_page_numbers(text)
    text = strip_repeated_lines(text)
    text = collapse_whitespace(text)
    return text


# ---------------------------------------------------------------------------
# Extração de entidades (regex compilado, sem ML/LLM)
# ---------------------------------------------------------------------------

_NUMERO_PROCESSO_RE = re.compile(r"\d{7}-\d{2}\.\d{4}\.\d{1}\.\d{2}\.\d{4}")

_TRIBUNAL_RE = re.compile(
    r"\b(TJ[A-Z]{2}|TRF-?\d|TRT-?\d{1,2}|TST|STJ|STF|TSE|STM)\b", re.IGNORECASE
)

_COMARCA_RE = re.compile(
    r"Comarca\s+de\s+([A-ZÀ-Ú][A-Za-zÀ-ÿ\s]{2,60}?)(?=[,.\n]|$)", re.IGNORECASE
)

_DATA_RE = re.compile(r"\b(\d{2})/(\d{2})/(\d{4})\b")

_POLO_ATIVO_RE = re.compile(
    r"\b(?:EXEQUENTE|REQUERENTE|AUTOR(?:A)?|POLO\s+ATIVO)\s*:\s*([^\n,;]{2,120})",
    re.IGNORECASE,
)
_POLO_PASSIVO_RE = re.compile(
    r"\b(?:EXECUTAD[OA]|REQUERID[OA]|R[ÉE]U|POLO\s+PASSIVO)\s*:\s*([^\n,;]{2,120})",
    re.IGNORECASE,
)

_CLASSES_JUDICIAIS = [
    "Execução Fiscal",
    "Ação de Cobrança",
    "Ação de Execução",
    "Ação Ordinária",
    "Ação Civil Pública",
    "Ação de Indenização",
    "Ação Trabalhista",
    "Agravo de Instrumento",
    "Apelação Cível",
    "Cumprimento de Sentença",
    "Embargos à Execução",
    "Execução de Título Extrajudicial",
    "Mandado de Segurança",
    "Recurso Especial",
    "Recurso Extraordinário",
]
_CLASSE_JUDICIAL_RE = re.compile(
    "|".join(re.escape(classe) for classe in _CLASSES_JUDICIAIS), re.IGNORECASE
)

_PALAVRAS_CHAVE_DICIONARIO = [
    "execução fiscal",
    "penhora",
    "intimação",
    "citação",
    "certidão da dívida ativa",
    "embargos",
    "agravo",
    "sentença",
    "despacho",
    "tutela antecipada",
    "audiência",
    "recurso",
    "honorários",
    "prescrição",
    "acórdão",
]


def _first_match(pattern: re.Pattern[str], text: str) -> str | None:
    match = pattern.search(text)
    return match.group(1).strip() if match and match.groups() else (
        match.group(0).strip() if match else None
    )


def extract_numero_processo(text: str) -> str | None:
    return _first_match(_NUMERO_PROCESSO_RE, text)


def extract_tribunal(text: str) -> str | None:
    match = _TRIBUNAL_RE.search(text)
    return match.group(1).upper() if match else None


def extract_comarca(text: str) -> str | None:
    comarca = _first_match(_COMARCA_RE, text)
    return " ".join(comarca.split()) if comarca else None


def extract_classe_judicial(text: str) -> str | None:
    match = _CLASSE_JUDICIAL_RE.search(text)
    if not match:
        return None
    for classe in _CLASSES_JUDICIAIS:
        if classe.lower() == match.group(0).lower():
            return classe
    return match.group(0).title()


def extract_data_publicacao(text: str) -> str | None:
    match = _DATA_RE.search(text)
    if not match:
        return None
    dia, mes, ano = match.groups()
    return f"{ano}-{mes}-{dia}"


def extract_partes(text: str) -> dict[str, str | None]:
    return {
        "polo_ativo": _first_match(_POLO_ATIVO_RE, text),
        "polo_passivo": _first_match(_POLO_PASSIVO_RE, text),
    }


def extract_palavras_chave(text: str) -> list[str]:
    lowered = text.lower()
    found = [termo for termo in _PALAVRAS_CHAVE_DICIONARIO if termo in lowered]
    return found


def extract_metadata(raw_text: str) -> dict:
    """Extrai metadados jurídicos estruturados a partir do texto bruto.

    Propositalmente independente de ``sanitize()``: cabeçalhos e rodapés
    repetidos (ex.: "Diário de Justiça Eletrônico - TJMG") costumam carregar
    o nome do tribunal e seriam perdidos se a extração dependesse do texto já
    com ruído de layout removido. Aqui aplicamos apenas uma normalização leve
    (Unicode + remoção de tags HTML), suficiente para os regex funcionarem de
    forma robusta sem descartar sinal útil.
    """
    text = normalize_unicode(raw_text)
    text = strip_html_tags(text)
    text = collapse_whitespace(text)

    return {
        "numero_processo": extract_numero_processo(text),
        "tribunal": extract_tribunal(text),
        "comarca": extract_comarca(text),
        "classe_judicial": extract_classe_judicial(text),
        "data_publicacao": extract_data_publicacao(text),
        "partes_identificadas": extract_partes(text),
        "palavras_chave": extract_palavras_chave(text),
    }
