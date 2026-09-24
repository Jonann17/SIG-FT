r"""A camada de IA aprende a mandar o PROPRIO PDF para o modelo (2026-09-24).

Por que: na comparacao do usuario entre o AutoSpec e o AMP (fichas 0084,
0086, 0088, 0094), o AMP -- Gemini flash-lite recebendo o PDF inteiro --
achou 78 informacoes; o AutoSpec, que manda recortes do TEXTO extraido, 43.
Lendo o arquivo, o modelo ve o que o texto perde: o desenho cotado (`ø 36`
sem "mm" ao lado), a tabela com a unidade so no cabecalho, a curva do
ventilador.

O formato de cada provedor:

- **OpenRouter / OpenAI-compativel:** parte `{"type": "file", "file":
  {"filename", "file_data": "data:application/pdf;base64,..."}}` no
  `content` da mensagem; no OpenRouter, mais o plugin `file-parser` com
  `engine: native` -- sem ele, um modelo que nao le PDF cairia no OCR PAGO do
  OpenRouter, sem ninguem ter decidido isso.
- **Gemini direto:** `generate_content([{"mime_type", "data"}, ..., prompt])`.

Quem decide SE manda o PDF e o consumidor (o AutoSpec), perguntando
`aceita_pdf` ao cliente. Aqui so se garante que, pedindo, o anexo sai no
formato certo -- e que, sem pedir, NADA muda na requisicao.
"""
import base64

from sigft.core.llm.client import Anexo, LLMClient, ProviderResult
from sigft.core.llm.providers.gemini import GeminiProvider
from sigft.core.llm.providers.openai_compat import OpenAICompatProvider
from sigft.core.llm.providers.openrouter import OpenRouterProvider

PDF = Anexo(nome="4500063671.0088.pdf", mime="application/pdf", dados=b"%PDF-1.4 fake")
PNG = Anexo(nome="placa.png", mime="image/png", dados=b"\x89PNG fake")


class _Resposta:
    def __init__(self):
        self._payload = {"choices": [{"message": {"content": "{}"}}]}

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


class _Post:
    def __init__(self):
        self.corpos = []

    def __call__(self, url, *, headers, json, timeout):
        self.corpos.append(json)
        return _Resposta()


# =============================================================================
# 1. OpenRouter: o PDF vai como parte `file`, com o plugin nativo
# =============================================================================
def test_openrouter_manda_o_pdf_como_parte_file_em_base64():
    post = _Post()
    OpenRouterProvider("k", "google/gemini-3-flash-preview", http_post=post).generate_raw(
        "preencha a ficha", anexos=[PDF])
    conteudo = post.corpos[0]["messages"][-1]["content"]
    assert conteudo[0] == {"type": "text", "text": "preencha a ficha"}
    parte = conteudo[1]
    assert parte["type"] == "file"
    assert parte["file"]["filename"] == "4500063671.0088.pdf"
    prefixo = "data:application/pdf;base64,"
    assert parte["file"]["file_data"].startswith(prefixo)
    assert base64.b64decode(parte["file"]["file_data"][len(prefixo):]) == PDF.dados


def test_openrouter_pede_leitura_NATIVA_e_nunca_o_ocr_pago_implicito():
    post = _Post()
    OpenRouterProvider("k", "google/gemini-3-flash-preview", http_post=post).generate_raw(
        "x", anexos=[PDF])
    assert post.corpos[0]["plugins"] == [{"id": "file-parser", "pdf": {"engine": "native"}}]


def test_sem_anexo_a_requisicao_sai_exatamente_como_antes():
    """Todas as outras tarefas do app chamam sem anexo. Nada pode mudar
    para elas: nem o formato do `content`, nem chave nova no corpo."""
    post = _Post()
    OpenRouterProvider("k", "google/gemini-3-flash-preview", http_post=post).generate_raw("x")
    corpo = post.corpos[0]
    assert corpo["messages"][-1]["content"] == "x"
    assert "plugins" not in corpo


def test_imagem_vai_como_image_url_e_sem_plugin_de_pdf():
    post = _Post()
    OpenRouterProvider("k", "google/gemini-3-flash-preview", http_post=post).generate_raw(
        "x", anexos=[PNG])
    parte = post.corpos[0]["messages"][-1]["content"][1]
    assert parte["type"] == "image_url"
    assert parte["image_url"]["url"].startswith("data:image/png;base64,")
    assert "plugins" not in post.corpos[0]


# =============================================================================
# 2. Quem le PDF nativamente
# =============================================================================
def test_openrouter_sabe_quais_familias_leem_pdf():
    def aceita(modelo):
        return OpenRouterProvider("k", modelo, http_post=_Post()).aceita_pdf()

    assert aceita("google/gemini-3-flash-preview")
    assert aceita("google/gemini-3.5-flash-lite")
    assert aceita("anthropic/claude-sonnet-4.5")
    assert aceita("openai/gpt-5")
    assert not aceita("deepseek/deepseek-chat")
    assert not aceita("minimax/minimax-m3")
    assert not aceita("x-ai/grok-4.5")


def test_endpoint_da_empresa_nao_recebe_pdf():
    """Endpoint OpenAI-compativel generico: nao ha como saber se le PDF. O
    AutoSpec manda o texto extraido, como sempre fez."""
    assert not OpenAICompatProvider("k", "m", base_url="https://x").aceita_pdf()


def test_gemini_direto_le_pdf():
    assert GeminiProvider("k", "m", genai_module=_Genai([])).aceita_pdf()


# =============================================================================
# 3. Gemini direto: dados em linha, antes do prompt
# =============================================================================
class _Genai:
    def __init__(self, chamadas):
        self.chamadas = chamadas

    def configure(self, **k):
        pass

    def GenerativeModel(self, *a, **k):
        chamadas = self.chamadas

        class _Modelo:
            def generate_content(self, conteudo, **kwargs):
                chamadas.append(conteudo)

                class _R:
                    text = "{}"
                    usage_metadata = None
                return _R()
        return _Modelo()


def test_gemini_manda_o_pdf_em_linha_antes_do_prompt():
    chamadas = []
    GeminiProvider("k", "m", genai_module=_Genai(chamadas)).generate_raw("preencha", anexos=[PDF])
    assert chamadas[0] == [{"mime_type": "application/pdf", "data": PDF.dados}, "preencha"]


def test_gemini_sem_anexo_continua_mandando_so_o_texto():
    chamadas = []
    GeminiProvider("k", "m", genai_module=_Genai(chamadas)).generate_raw("preencha")
    assert chamadas[0] == "preencha"


# =============================================================================
# 4. LLMClient: repassa o anexo, e so quando ha anexo
# =============================================================================
class _ProvedorAntigo:
    """Assinatura de antes: sem `anexos`. Os dubles de teste do app inteiro
    sao assim, e continuam valendo."""

    def __init__(self):
        self.kwargs = []

    def generate_raw(self, prompt, *, system=None, json_mode=False):
        self.kwargs.append({"system": system, "json_mode": json_mode})
        return ProviderResult("{}")


class _ProvedorNovo(_ProvedorAntigo):
    def generate_raw(self, prompt, *, system=None, json_mode=False, anexos=None):
        self.kwargs.append({"anexos": anexos})
        return ProviderResult("{}")

    def aceita_pdf(self):
        return True


def test_o_cliente_repassa_os_anexos_ao_provedor():
    provedor = _ProvedorNovo()
    LLMClient(provedor, provider_name="p", model="m").generate("x", anexos=[PDF])
    assert provedor.kwargs[0]["anexos"] == [PDF]


def test_sem_anexo_o_provedor_de_assinatura_antiga_continua_funcionando():
    provedor = _ProvedorAntigo()
    LLMClient(provedor, provider_name="p", model="m").generate("x")
    assert provedor.kwargs == [{"system": None, "json_mode": False}]


def test_o_cliente_diz_se_o_provedor_aceita_pdf():
    assert LLMClient(_ProvedorNovo(), provider_name="p", model="m").aceita_pdf
    assert not LLMClient(_ProvedorAntigo(), provider_name="p", model="m").aceita_pdf


def test_anexo_nasce_do_arquivo_com_o_tipo_pelo_nome(tmp_path):
    caminho = tmp_path / "Manual.PDF"
    caminho.write_bytes(b"%PDF")
    anexo = Anexo.de_arquivo(str(caminho))
    assert (anexo.nome, anexo.mime, anexo.dados) == ("Manual.PDF", "application/pdf", b"%PDF")
