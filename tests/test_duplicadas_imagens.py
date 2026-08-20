r"""
Copiar IMAGEM entre fichas (CP 6.4) — a única seção que não se associa.

Documento já existe como objeto no portal, então basta apontar para ele.
Imagem é ARQUIVO: tem de sair da ficha original e entrar na nova.

⚠️ E ISSO DESFAZ UMA PENDÊNCIA QUE EU MESMO REGISTREI. Em 2026-08-19 escrevi
que as imagens ficariam no motor antigo porque "o Playwright não reproduz a
pasta de downloads do Chrome". O HTML que o usuário mandou em 2026-08-20
mostra que o caminho nunca foi a pasta de downloads:

    <img class="custom-img" src="blob:https://apps.itaipu.gov.br/29077935-…">

`blob:` não é endereço HTTP -- é um identificador de objeto válido só dentro
daquela página. Não há nada para baixar de fora; a imagem se lê DE DENTRO do
navegador. Que é mais direto, funciona igual nos dois motores e não depende de
configurar pasta nenhuma. A pendência estava certa sobre o obstáculo e errada
sobre a saída.
"""
import os

import pytest

from sigft.core.rpa import seletores_duplicada as sel
from sigft.core.rpa.portal import PMIBPortal
from sigft.services import duplicadas_imagens as imgs

PNG = b"\x89PNG\r\n\x1a\n" + b"corpo"
JPG = b"\xff\xd8\xff" + b"corpo"
WEBP = b"RIFF\x00\x00\x00\x00WEBP"


@pytest.fixture(autouse=True)
def _sem_espera(monkeypatch):
    monkeypatch.setattr(imgs.time, "sleep", lambda _s: None)


class _EngineDeImagens:
    def __init__(self, slides=(), bytes_por_slide=None, filepond_aceita=True):
        self.slides = list(slides)          # legendas, na ordem
        self.bytes_por_slide = dict(bytes_por_slide or {})
        self.filepond_aceita = filepond_aceita
        self.enviados = []
        self.preenchidos = {}
        self.cliques = []
        self._staged = False

    @staticmethod
    def _indice(seletor):
        import re
        achado = re.search(r"\)\[(\d+)\]", seletor)
        return int(achado.group(1)) if achado else None

    def contar(self, seletor):
        if "filepond--list" in seletor:
            return 1 if (self._staged and self.filepond_aceita) else 0
        if "splide__slide" in seletor and "img" not in seletor and "figcaption" not in seletor:
            return len(self.slides)
        if "figcaption" in seletor or "custom-img" in seletor:
            return 1
        if "Adicionar imagens" in seletor:
            return 1
        if "Input_Description" in seletor:
            return 1
        return 0

    def texto(self, seletor):
        if "figcaption" in seletor:
            i = self._indice(seletor)
            return self.slides[i - 1] if i and i <= len(self.slides) else ""
        return ""

    def bytes_da_imagem(self, seletor):
        i = self._indice(seletor)
        return self.bytes_por_slide.get(i, b"")

    def enviar_arquivo(self, _seletor, caminho):
        self.enviados.append((caminho, open(caminho, "rb").read()))
        self._staged = True

    def fill(self, seletor, texto):
        self.preenchidos[seletor] = texto

    def click(self, seletor):
        self.cliques.append(seletor)


class _PortalDeImagens:
    texto_se_existir = PMIBPortal.texto_se_existir
    valor_se_existir = PMIBPortal.valor_se_existir

    def __init__(self, engine, confirma=True):
        self.engine = engine
        self.confirma = confirma
        self.salvos = []
        self.ancoras = []

    def safe_click(self, seletor):
        self.engine.click(seletor)

    def safe_fill(self, seletor, texto):
        self.engine.fill(seletor, texto)

    def salvar_e_confirmar(self, nome="", callback_log=None, ancora=None, **_k):
        self.salvos.append(nome)
        self.ancoras.append(ancora)
        self.engine._staged = False
        return self.confirma


def _tela(slides=("Botão",), dados=None, **kwargs):
    dados = dados or {i: PNG for i in range(1, len(slides) + 1)}
    engine = _EngineDeImagens(slides, dados)
    return _PortalDeImagens(engine, kwargs.get("confirma", True)), engine


# =============================================================================
# 1. Ler da original -- o blob, e os clones do carrossel
# =============================================================================
def test_le_legenda_e_bytes_de_cada_slide():
    portal, _ = _tela(slides=["Botão", "Lateral"], dados={1: PNG, 2: JPG})

    lidas = imgs.ler_da_original(portal, lambda _m: None)

    assert [l for l, _ in lidas] == ["Botão", "Lateral"]
    assert [d for _, d in lidas] == [PNG, JPG]


def test_o_seletor_dos_slides_EXCLUI_os_clones():
    """`splide` clona slides para o laço infinito. Sem o filtro, a mesma
    imagem seria copiada duas ou três vezes -- e o portal aceitaria todas,
    porque para ele são uploads distintos."""
    assert "not(contains(@class, 'clone'))" in sel.XPATH_IMAGENS_SLIDES


def test_slide_sem_bytes_legiveis_e_pulado_com_aviso():
    """Melhor uma imagem a menos e uma linha no log do que um arquivo vazio
    subindo para o portal."""
    portal, _ = _tela(slides=["Boa", "Quebrada"], dados={1: PNG, 2: b""})
    linhas = []

    lidas = imgs.ler_da_original(portal, linhas.append)

    assert [l for l, _ in lidas] == ["Boa"]
    assert any("Quebrada" in l for l in linhas)


# =============================================================================
# 2. A extensão sai da ASSINATURA, não do nome
# =============================================================================
@pytest.mark.parametrize("dados,esperada", [
    (PNG, ".png"), (JPG, ".jpg"), (WEBP, ""), (b"", ""),
])
def test_a_extensao_vem_dos_primeiros_bytes(dados, esperada):
    """Um `blob:` não tem nome nem extensão, e o `<input>` declara
    `accept="image/jpeg,image/png"`. Extensão errada = MIME errado = portal
    recusa sem dizer por quê."""
    assert imgs.extensao_de(dados) == esperada


def test_formato_que_o_portal_recusaria_nao_e_gravado(tmp_path):
    arquivos = imgs.gravar_temporarias(
        [("ok", PNG), ("webp", WEBP)], str(tmp_path))

    assert [l for l, _ in arquivos] == ["ok"]
    assert len(os.listdir(tmp_path)) == 1


# =============================================================================
# 3. Subir na alvo, com prova
# =============================================================================
def test_imagem_e_enviada_e_a_secao_salva():
    portal, engine = _tela(slides=["Botão"])
    lidas = imgs.ler_da_original(portal, lambda _m: None)

    resultado = imgs.copiar(portal, lidas, "4500063671.0922", lambda _m: None)

    assert resultado.ok is True
    assert len(engine.enviados) == 1
    assert engine.enviados[0][1] == PNG, "subiu os bytes que leu"
    assert portal.salvos == ["Documentos e imagens"]


def test_o_salvamento_da_imagem_vai_ANCORADO():
    portal, _ = _tela(slides=["Botão"])
    lidas = imgs.ler_da_original(portal, lambda _m: None)

    imgs.copiar(portal, lidas, "", lambda _m: None)

    assert portal.ancoras == [sel.XPATH_IMAGENS_CONTAINER]


def test_a_legenda_da_ORIGINAL_vira_a_descricao():
    """Mais fiel do que qualquer texto inventado."""
    portal, engine = _tela(slides=["Vista lateral"])
    lidas = imgs.ler_da_original(portal, lambda _m: None)

    imgs.copiar(portal, lidas, "4500063671.0922", lambda _m: None)

    assert set(engine.preenchidos.values()) == {"Vista lateral"}


def test_sem_legenda_entra_o_codigo_PMIB():
    """*"A descrição da imagem pode ser o código PMIB da ficha."* -- a
    sugestão do usuário vale como RESERVA, não como regra."""
    portal, engine = _tela(slides=[""])
    lidas = imgs.ler_da_original(portal, lambda _m: None)

    imgs.copiar(portal, lidas, "4500063671.0922", lambda _m: None)

    assert set(engine.preenchidos.values()) == {"4500063671.0922"}


def test_filepond_que_NAO_lista_o_arquivo_reprova():
    """A prova de que o arquivo foi aceito é o `<li>` que o FilePond cria.
    Sem ela, "enviei o arquivo" é só "chamei a função" -- o mesmo buraco que
    o "+" da referência e o SALVAR sem toast já custaram neste módulo."""
    portal, engine = _tela(slides=["Botão"])
    engine.filepond_aceita = False
    lidas = imgs.ler_da_original(portal, lambda _m: None)
    linhas = []

    resultado = imgs.copiar(portal, lidas, "", linhas.append)

    assert resultado.ok is False
    assert any("não listou" in l for l in linhas)


def test_salvamento_nao_confirmado_reprova():
    portal, _ = _tela(slides=["Botão"], confirma=False)
    lidas = imgs.ler_da_original(portal, lambda _m: None)

    assert imgs.copiar(portal, lidas, "", lambda _m: None).ok is False


# =============================================================================
# 4. Os temporários somem
# =============================================================================
def test_os_arquivos_temporarios_sao_APAGADOS(monkeypatch):
    """*"Precisamos baixar temporariamente a imagem no disco e depois
    apagá-la."* Vale inclusive quando alguma imagem falha."""
    pastas = []
    original = imgs.tempfile.mkdtemp

    def _espiao(*a, **k):
        pasta = original(*a, **k)
        pastas.append(pasta)
        return pasta

    monkeypatch.setattr(imgs.tempfile, "mkdtemp", _espiao)

    portal, engine = _tela(slides=["Botão"])
    engine.filepond_aceita = False           # a imagem NÃO entra
    lidas = imgs.ler_da_original(portal, lambda _m: None)

    imgs.copiar(portal, lidas, "", lambda _m: None)

    assert pastas and not os.path.exists(pastas[0])


def test_ficha_original_sem_imagem_nao_e_falha():
    portal, _ = _tela(slides=[])

    resultado = imgs.copiar(portal, [], "", lambda _m: None)

    assert resultado.ok is True
    assert "nenhuma" in resultado.detalhe
