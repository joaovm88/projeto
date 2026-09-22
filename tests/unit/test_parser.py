from app.domain.parser import (
    collapse_whitespace,
    extract_classe_judicial,
    extract_comarca,
    extract_data_publicacao,
    extract_metadata,
    extract_numero_processo,
    extract_palavras_chave,
    extract_partes,
    extract_tribunal,
    normalize_unicode,
    sanitize,
    strip_html_tags,
    strip_page_numbers,
    strip_repeated_lines,
)

RAW_DOCUMENT = """
Diário de Justiça Eletrônico - TJMG
<b>Processo nº 0001234-56.2026.8.13.0707</b>

Comarca de Varginha
Classe Judicial: Execução Fiscal
Data de publicação: 22/09/2026

EXEQUENTE: Fazenda Pública
EXECUTADO: Empresa Comercial Ltda

Vistos etc.   Trata-se de execução  fiscal proposta em face do devedor,
com pedido de penhora   e posterior intimação para pagamento da
certidão da dívida ativa.

Diário de Justiça Eletrônico - TJMG
1
Diário de Justiça Eletrônico - TJMG
2
"""


class TestSanitize:
    def test_removes_html_tags(self) -> None:
        assert strip_html_tags("<b>texto</b> normal <br/>") == " texto  normal  "

    def test_removes_page_numbers(self) -> None:
        text = "Conteúdo real\n1\nMais conteúdo\nPágina 2 de 10\n"
        result = strip_page_numbers(text)
        assert "\n1\n" not in result
        assert "Página 2 de 10" not in result

    def test_removes_repeated_header_lines(self) -> None:
        text = "\n".join(
            ["Cabeçalho Repetido"] * 3 + ["Conteúdo único que não deve ser removido"]
        )
        result = strip_repeated_lines(text, min_occurrences=3)
        assert "Cabeçalho Repetido" not in result
        assert "Conteúdo único que não deve ser removido" in result

    def test_collapse_whitespace(self) -> None:
        assert collapse_whitespace("a   b\n\n\n\nc") == "a b\n\nc"

    def test_normalize_unicode_strips_control_chars(self) -> None:
        result = normalize_unicode("texto\x00com\x07ruído")
        assert "\x00" not in result
        assert "\x07" not in result

    def test_sanitize_end_to_end_produces_clean_text(self) -> None:
        cleaned = sanitize(RAW_DOCUMENT)
        assert "<b>" not in cleaned
        assert "Diário de Justiça Eletrônico - TJMG" not in cleaned
        assert "  " not in cleaned
        assert "Vistos etc." in cleaned


class TestEntityExtraction:
    """A extração de entidades roda sobre o texto bruto (ver docstring de
    ``extract_metadata``), não sobre a saída de ``sanitize()``: cabeçalhos
    repetidos como "Diário de Justiça Eletrônico - TJMG" carregam o nome do
    tribunal e seriam removidos pela limpeza agressiva de exibição.
    """

    def test_extract_numero_processo(self) -> None:
        assert extract_numero_processo(RAW_DOCUMENT) == "0001234-56.2026.8.13.0707"

    def test_extract_tribunal(self) -> None:
        assert extract_tribunal(RAW_DOCUMENT) == "TJMG"

    def test_extract_comarca(self) -> None:
        assert extract_comarca(RAW_DOCUMENT) == "Varginha"

    def test_extract_classe_judicial(self) -> None:
        assert extract_classe_judicial(RAW_DOCUMENT) == "Execução Fiscal"

    def test_extract_data_publicacao(self) -> None:
        assert extract_data_publicacao(RAW_DOCUMENT) == "2026-09-22"

    def test_extract_partes(self) -> None:
        partes = extract_partes(RAW_DOCUMENT)
        assert partes["polo_ativo"] == "Fazenda Pública"
        assert partes["polo_passivo"] == "Empresa Comercial Ltda"

    def test_extract_palavras_chave(self) -> None:
        palavras = extract_palavras_chave(RAW_DOCUMENT)
        assert "execução fiscal" in palavras
        assert "penhora" in palavras
        assert "intimação" in palavras
        assert "certidão da dívida ativa" in palavras

    def test_extract_metadata_returns_all_fields(self) -> None:
        metadata = extract_metadata(RAW_DOCUMENT)
        assert metadata["numero_processo"] == "0001234-56.2026.8.13.0707"
        assert metadata["tribunal"] == "TJMG"
        assert metadata["classe_judicial"] == "Execução Fiscal"

    def test_extract_metadata_on_text_without_entities_returns_none(self) -> None:
        metadata = extract_metadata("Um texto qualquer sem nenhuma entidade jurídica.")
        assert metadata["numero_processo"] is None
        assert metadata["tribunal"] is None
        assert metadata["palavras_chave"] == []
