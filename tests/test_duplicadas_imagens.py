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

    def clicar_e_confirmar(self, seletor_botao, nome="", callback_log=None, **_k):
        """Quem grava a imagem é o "Confirmar" DENTRO do diálogo -- o SALVAR da
        seção fica inacessível enquanto ele está aberto (log de 2026-08-20)."""
        self.engine.cliques.append(seletor_botao)
        self.salvos.append(nome)
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


# ⚠️ Havia aqui um `test_o_salvamento_da_imagem_vai_ANCORADO`, que provava
# que a imagem era salva pelo SALVAR da seção, ancorado no container. Ele
# morreu com a descoberta de 2026-08-20: a seção NÃO é quem grava a imagem, e
# tentar o SALVAR dela custava 20 s de timeout porque o diálogo aberto o
# cobre. O teste do botão certo está no fim deste arquivo
# (`test_a_imagem_e_confirmada_pelo_botao_do_DIALOGO`).


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


# =============================================================================
# O botão é "Confirmar", dentro do diálogo — não o SALVAR da seção
# =============================================================================
# Log de 2026-08-20, 15h04:
#
#     [Erro] Não consegui clicar no SALVAR de 'Documentos e imagens'
#            (subindo da seção): TempoEsgotado. Algo pode estar cobrindo o
#            botão -- salve à mão.
#
# Não era "algo cobrindo": o botão da seção está mesmo inacessível enquanto o
# diálogo de imagem está aberto, e o botão certo é OUTRO. O usuário mandou os
# dois pedaços que faltavam:
#
#     <button class="btn btn-primary text-uppercase">Confirmar</button>
#     <div class="feedback-message-text">A imagem foi adicionada com sucesso!</div>
#
# Ou seja: confirma-se DENTRO do diálogo, e o portal responde com um toast
# próprio. A seção não precisa de SALVAR nenhum.

def test_a_imagem_e_confirmada_pelo_botao_do_DIALOGO(monkeypatch):
    monkeypatch.setattr(imgs.time, "sleep", lambda _s: None)
    portal, engine = _tela(slides=["Botão"])
    lidas = imgs.ler_da_original(portal, lambda _m: None)

    imgs.copiar(portal, lidas, "", lambda _m: None)

    assert any("Confirmar" in c for c in engine.cliques), (
        "o SALVAR da seção fica inacessível com o diálogo aberto -- quem "
        "confirma a imagem é o botão de dentro dele"
    )


def test_a_palavra_da_secao_de_imagens_esta_mapeada():
    """"A imagem foi adicionada com sucesso!" -- a redação veio do usuário.
    Sem a palavra, um toast remanescente de outra seção confirmaria esta."""
    from sigft.core.rpa import portal as portal_mod

    assert portal_mod.mensagem_confirma_secao(
        "A imagem foi adicionada com sucesso!", sel.ABA_DOCUMENTOS_EDICAO) is True
    assert portal_mod.mensagem_confirma_secao(
        "A característica técnica foi salva com sucesso!",
        sel.ABA_DOCUMENTOS_EDICAO) is False


# ===========================================================================
# Esperar o UPLOAD terminar antes de confirmar
# ===========================================================================
# Log do usuário, 2026-08-21: a imagem entrava, o "Confirmar" vinha 2 s depois
# e o portal não devolvia toast nenhum. Diagnóstico dele: *"quando carregamos
# uma imagem, pode ser que demore a fazer o upload, e talvez seja esse o erro,
# tentar clicar antes de esperar dar o upload"*.

class _EngineComEstado:
    """Motor de mentira que expõe `data-filepond-item-state`, como o FilePond
    real: o `<li>` nasce ao ACEITAR o arquivo, e o estado muda quando o
    processamento TERMINA."""

    def __init__(self, ciclos_processando=0):
        self.restam = ciclos_processando
        self.consultas = 0

    def contar(self, seletor):
        self.consultas += 1
        if "not(contains" in seletor:          # "ainda processando?"
            if self.restam > 0:
                self.restam -= 1
                return 1
            return 0
        if "@data-filepond-item-state" in seletor:   # "há item com estado?"
            return 1
        return 0


class _PortalComEstado:
    def __init__(self, engine):
        self.engine = engine


def test_espera_ate_o_filepond_terminar(monkeypatch):
    monkeypatch.setattr(imgs.time, "sleep", lambda _s: None)
    portal = _PortalComEstado(_EngineComEstado(ciclos_processando=5))

    assert imgs.esperar_processamento(portal, lambda _m: None) is True


def test_nao_confirma_se_o_upload_nunca_termina(monkeypatch):
    """Clicar em Confirmar no meio do processamento é o que fazia o portal não
    responder nada -- melhor recusar e dizer, do que clicar e não saber."""
    monkeypatch.setattr(imgs.time, "sleep", lambda _s: None)
    relogio = {"t": 0.0}
    monkeypatch.setattr(imgs.time, "monotonic", lambda: relogio.__setitem__("t", relogio["t"] + 10) or relogio["t"])
    portal = _PortalComEstado(_EngineComEstado(ciclos_processando=10_000))
    logs = []

    assert imgs.esperar_processamento(portal, logs.append, timeout=30) is False
    assert "NÃO cliquei em Confirmar" in "\n".join(logs)


def test_tela_sem_o_atributo_de_estado_nao_trava(monkeypatch):
    """Versão de FilePond que não expõe o estado: não há o que observar.
    Devolver `True` e deixar a checagem do `<li>` decidir é melhor do que
    fingir que esperou -- ou do que travar até o timeout."""
    monkeypatch.setattr(imgs.time, "sleep", lambda _s: None)

    class _SemEstado:
        def contar(self, _seletor):
            return 0

    assert imgs.esperar_processamento(_PortalComEstado(_SemEstado())) is True


def test_subir_uma_NAO_confirma_com_o_upload_em_andamento(monkeypatch, tmp_path):
    """CONTRAPROVA DA LIGAÇÃO, e não só da função: a espera tem de estar DENTRO
    de `subir_uma`, antes do "Confirmar".

    Sem este teste, remover a chamada não quebrava nada -- foi o que a
    sabotagem mostrou em 2026-08-21. `esperar_processamento` sozinha, testada e
    nunca chamada, é a mesma coisa que não existir.
    """
    monkeypatch.setattr(imgs.time, "sleep", lambda _s: None)
    # noqa B008: o `iter(...)` no default e o TRUQUE, nao um descuido -- e o
    # que faz cada chamada de `monotonic()` devolver o proximo valor da
    # sequencia, simulando o relogio andando. Avaliar uma vez so e o ponto.
    monkeypatch.setattr(imgs.time, "monotonic",
                        lambda c=iter(range(0, 10_000, 10)): next(c))  # noqa: B008
    portal, engine = _tela()

    contar_original = engine.contar

    def contar(seletor):
        if "not(contains" in seletor:
            return 1            # o FilePond NUNCA termina
        if "@data-filepond-item-state" in seletor:
            return 1
        return contar_original(seletor)

    engine.contar = contar
    arquivo = tmp_path / "imagem.png"
    arquivo.write_bytes(PNG)
    logs = []

    entrou = imgs.subir_uma(portal, "legenda", str(arquivo), logs.append)

    assert entrou is False
    assert portal.salvos == []      # nada de "Confirmar"
    assert "NÃO cliquei em Confirmar" in "\n".join(logs)


# =============================================================================
# Autoconferência (2026-10-20): formulário preso se fecha e a imagem é tentada
# de novo -- a cadeia do log de 2026-10-19 (FilePond sumiu → "Não achei
# 'Adicionar imagens'" → as duas fichas seguintes sem lista).
# =============================================================================
class _EngineComFormulario(_EngineDeImagens):
    def __init__(self, *args, falhas_de_upload=0, esc_fecha=True, **kwargs):
        super().__init__(*args, **kwargs)
        self.aberto = False
        self.falhas_de_upload = falhas_de_upload
        self.esc_fecha = esc_fecha
        self.teclas = []

    def contar(self, seletor):
        if seletor == sel.XPATH_IMAGENS_CONTAINER:
            return int(self.aberto)
        if "Adicionar imagens" in seletor:
            return 0 if self.aberto else 1   # o formulário cobre o link
        return super().contar(seletor)

    def click(self, seletor):
        super().click(seletor)
        if "Adicionar imagens" in seletor:
            self.aberto = True

    def enviar_arquivo(self, seletor, caminho):
        if self.falhas_de_upload:
            self.falhas_de_upload -= 1
            raise TimeoutError("Timeout 20000ms exceeded")
        super().enviar_arquivo(seletor, caminho)

    def press(self, teclas):
        self.teclas.append(teclas)
        if teclas == "ESCAPE" and self.esc_fecha:
            self.aberto = False


class _PortalComFormulario(_PortalDeImagens):
    def clicar_e_confirmar(self, seletor_botao, nome="", callback_log=None, **_k):
        self.engine.aberto = False
        return super().clicar_e_confirmar(seletor_botao, nome, callback_log)


def _tela_com_formulario(slides=("Botão",), **kwargs):
    engine = _EngineComFormulario(slides, {i: PNG for i in range(1, len(slides) + 1)},
                                  **kwargs)
    return _PortalComFormulario(engine), engine


def test_upload_que_falha_FECHA_o_formulario_e_tenta_de_novo():
    portal, engine = _tela_com_formulario(falhas_de_upload=1)
    lidas = imgs.ler_da_original(portal, lambda _m: None)
    linhas = []

    resultado = imgs.copiar(portal, lidas, "", linhas.append)

    assert resultado.ok is True
    assert "ESCAPE" in engine.teclas
    assert "[Autoconferência] Imagens" in "\n".join(linhas)
    assert len(engine.enviados) == 1


def test_a_imagem_SEGUINTE_nao_herda_o_formulario_preso():
    """Sem fechar, a 2ª imagem dava "Não achei 'Adicionar imagens'"."""
    portal, engine = _tela_com_formulario(slides=("A", "B"), falhas_de_upload=2)
    lidas = imgs.ler_da_original(portal, lambda _m: None)
    linhas = []

    resultado = imgs.copiar(portal, lidas, "", linhas.append)

    assert "Não achei 'Adicionar imagens'" not in "\n".join(linhas)
    assert resultado.detalhe == "1 de 2 não subiram"
    assert engine.aberto is False, "a ficha seguinte recebe a tela livre"


def test_formulario_que_nao_fecha_vira_erro_no_log():
    portal, _ = _tela_com_formulario(falhas_de_upload=5, esc_fecha=False)
    lidas = imgs.ler_da_original(portal, lambda _m: None)
    linhas = []

    imgs.copiar(portal, lidas, "", linhas.append)

    assert "Feche à mão" in "\n".join(linhas)


# =============================================================================
# Várias imagens num só diálogo (Upload de Fotos, 2026-11-03): o "Adicionar
# Imagens" aceita até 10 arquivos ("Máximo 10 arquivos").
# =============================================================================
class _EngineDeVarias(_EngineDeImagens):
    def __init__(self, aceita=None):
        super().__init__()
        self.aceita = aceita        # quantos o FilePond lista; None = todos
        self.na_lista = 0

    def contar(self, seletor):
        if "filepond--list" in seletor:
            return self.na_lista
        return super().contar(seletor)

    def enviar_arquivo(self, _seletor, caminhos):
        self.enviados.append(caminhos)
        quantos = len(caminhos) if isinstance(caminhos, list) else 1
        self.na_lista = quantos if self.aceita is None else self.aceita


def test_subir_juntas_manda_todos_num_so_envio_e_confirma_uma_vez():
    engine = _EngineDeVarias()
    portal = _PortalDeImagens(engine)

    entrou = imgs.subir_juntas(portal, "imagens - 0071", ["a.jpg", "b.jpg", "c.jpg"])

    assert entrou is True
    assert engine.enviados == [["a.jpg", "b.jpg", "c.jpg"]]
    assert portal.salvos == ["Documentos e imagens"]
    assert engine.preenchidos  # a descrição foi preenchida


def test_subir_juntas_com_arquivo_que_o_filepond_nao_listou_nao_confirma():
    engine = _EngineDeVarias(aceita=2)
    portal = _PortalDeImagens(engine)
    linhas = []

    entrou = imgs.subir_juntas(portal, "imagens - 0071", ["a.jpg", "b.jpg", "c.jpg"], linhas.append)

    assert entrou is False
    assert portal.salvos == []      # não clicou em Confirmar com arquivo faltando
    assert "2 de 3" in "\n".join(linhas)


def test_subir_uma_continua_mandando_um_caminho_so():
    engine = _EngineDeVarias()
    portal = _PortalDeImagens(engine)

    assert imgs.subir_uma(portal, "x", "a.jpg") is True
    assert engine.enviados == ["a.jpg"]
