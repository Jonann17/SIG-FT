r"""
Upload de Fotos (2026-10-30) -- `sigft/services/upload_fotos.py`.

O portal aqui é um dublê com estado: a tabela de imagens é uma lista de nomes,
a lixeira abre o diálogo e o CONFIRMAR tira a primeira linha. Ele prova a
ORDEM e as CONFERÊNCIAS do robô (excluir antes de subir, só dar ok com o nome
na tabela), não os seletores -- esses só a primeira execução real prova.
"""
import os

import pytest

from sigft.services import upload_fotos as uf

from _openpyxl_de_verdade import openpyxl_de_verdade


@pytest.fixture(autouse=True)
def _sem_espera(monkeypatch):
    monkeypatch.setattr(uf.time, "sleep", lambda _s: None)


# ===========================================================================
# 1. O lote
# ===========================================================================
def test_agrupar_fotos_na_ordem_de_subida_e_lista_o_que_nao_segue_o_padrao(tmp_path):
    for nome in ("0071b.JPG", "0071.jpg", "0071a.png", "0072.jpeg", "leia-me.txt", "0071c.gif", "71.jpg"):
        (tmp_path / nome).write_bytes(b"x")

    grupos, ignorados = uf.agrupar_fotos(str(tmp_path))

    assert {q: [os.path.basename(p) for p in c] for q, c in grupos.items()} == {
        "0071": ["0071.jpg", "0071a.png", "0071b.JPG"],
        "0072": ["0072.jpeg"],
    }
    assert sorted(ignorados) == ["0071c.gif", "71.jpg", "leia-me.txt"]


def test_ligar_as_fichas_pelo_final_e_nunca_adivinhar_ambiguo():
    grupos = {"0071": ["a"], "0072": ["b"], "0099": ["c"]}
    codigos = ["4500063671.0071", "'4500063671.72", "4500063671.0072", "4500099999.0072"]

    fichas, sem_ficha, ambiguas = uf.ligar_as_fichas(grupos, codigos)

    assert fichas == [("4500063671.0071", "0071", ["a"])]
    assert sem_ficha == ["0099"]
    assert ambiguas == {"0072": ["4500063671.0072", "4500099999.0072"]}


# ===========================================================================
# 2. O robô, contra o dublê
# ===========================================================================
class _Engine:
    def __init__(self, fotos=(), documentos=0):
        self.fotos = list(fotos)
        self.documentos = documentos
        self.dialogo = False
        self.ordem = []

    def contar(self, seletor):
        if seletor.startswith(uf.XPATH_TABELA_DE_IMAGENS + "//tr[.//td[normalize-space()="):
            return sum(1 for nome in self.fotos if f"'{nome}'" in seletor)
        if seletor == uf.XPATH_LINHAS_DE_IMAGEM:
            return len(self.fotos)
        if seletor == uf.XPATH_TABELA_DE_IMAGENS:
            return 1
        if seletor == uf.XPATH_LINHAS_DE_DOCUMENTO:
            return self.documentos
        if "CONFIRMAR" in seletor:
            return 1 if self.dialogo else 0
        return 0

    def scroll_to(self, _seletor):
        pass

    def click_raw(self, seletor):
        if "fa-trash" in seletor:
            self.dialogo = True
        elif "CONFIRMAR" in seletor and self.dialogo:
            self.ordem.append(("excluiu", self.fotos.pop(0)))
            self.dialogo = False


class _Portal:
    def __init__(self, engine):
        self.engine = engine

    def pesquisar_e_abrir(self, _pmib):
        return True


@pytest.fixture
def portal(monkeypatch):
    def _criar(fotos=(), documentos=0, sobe=True):
        engine = _Engine(fotos, documentos)

        def _subir(_portal, descricao, caminhos, _log=None, **_tempos):
            engine.envios.append(list(caminhos))
            for caminho in caminhos:
                engine.ordem.append(("subiu", caminho, descricao))
                if sobe:
                    engine.fotos.append(caminho.rsplit("/", 1)[-1])
            return sobe

        engine.envios = []
        monkeypatch.setattr(uf.extrator, "esperar_a_ficha_abrir", lambda *_a, **_k: True)
        monkeypatch.setattr(uf.extrator, "abrir_secao", lambda *_a, **_k: True)
        monkeypatch.setattr(uf.imagens, "subir_juntas", _subir)
        monkeypatch.setattr(uf.imagens, "fechar_formulario", lambda *_a, **_k: True)
        return _Portal(engine)
    return _criar


NOVAS = ["/fotos/0071.JPG", "/fotos/0071a.JPG"]


def test_substituir_exclui_as_antigas_antes_de_subir_as_novas(portal):
    p = portal(fotos=["0071e.JPG", "0071c.JPG"], documentos=2)

    resultado = uf.processar_ficha(p, "4500063671.0071", "0071", NOVAS, uf.MODO_SUBSTITUIR)

    assert resultado.ok and resultado.tem_documentos
    assert p.engine.fotos == ["0071.JPG", "0071a.JPG"]
    assert [passo[0] for passo in p.engine.ordem] == ["excluiu", "excluiu", "subiu", "subiu"]
    assert p.engine.ordem[2][2] == "imagens - 0071"


def test_ficha_sem_foto_so_sobe_e_sem_documento_diz_isso(portal):
    p = portal(fotos=[], documentos=0)

    resultado = uf.processar_ficha(p, "4500063671.0071", "0071", NOVAS, uf.MODO_SUBSTITUIR)

    assert resultado.ok and not resultado.tem_documentos
    assert [passo[0] for passo in p.engine.ordem] == ["subiu", "subiu"]


def test_perguntar_e_pular_nao_toca_na_ficha(portal):
    p = portal(fotos=["0071.JPG"])
    perguntas = []

    def perguntar(pmib, quantas):
        perguntas.append((pmib, quantas))
        return uf.PULAR

    resultado = uf.processar_ficha(p, "4500063671.0071", "0071", NOVAS, uf.MODO_PERGUNTAR, perguntar)

    assert resultado.pulada and not resultado.ok
    assert perguntas == [("4500063671.0071", 1)]
    assert p.engine.ordem == []


def test_perguntar_e_adicionar_sobe_sem_excluir(portal):
    p = portal(fotos=["0071z.JPG"])

    resultado = uf.processar_ficha(p, "4500063671.0071", "0071", NOVAS, uf.MODO_PERGUNTAR,
                                   lambda *_a: uf.ADICIONAR)

    assert resultado.ok
    assert p.engine.fotos == ["0071z.JPG", "0071.JPG", "0071a.JPG"]


def test_foto_que_nao_aparece_na_tabela_nao_e_ok(portal):
    p = portal(fotos=[], sobe=False)

    resultado = uf.processar_ficha(p, "4500063671.0071", "0071", NOVAS)

    assert not resultado.ok
    assert "0071.JPG" in resultado.motivo and "0071a.JPG" in resultado.motivo


def test_linhas_que_chegam_depois_do_cabecalho_ainda_sao_excluidas(portal):
    # O OutSystems desenha a tabela antes dos dados: as primeiras leituras dão 0
    # linhas. Contar cedo demais fazia o modo "substituir" subir por cima.
    p = portal(fotos=["0071e.JPG", "0071c.JPG"])
    reais, leituras = p.engine.contar, {"n": 0}

    def contar_com_atraso(seletor):
        if seletor == uf.XPATH_LINHAS_DE_IMAGEM and leituras["n"] < 4:
            leituras["n"] += 1
            return 0
        return reais(seletor)
    p.engine.contar = contar_com_atraso

    resultado = uf.processar_ficha(p, "4500063671.0071", "0071", NOVAS, uf.MODO_SUBSTITUIR)

    assert resultado.ok
    assert p.engine.fotos == ["0071.JPG", "0071a.JPG"]


def test_adicionar_com_nome_repetido_que_nao_sobe_nao_e_ok(portal):
    # A foto antiga já se chama 0071.JPG: achar o nome na tabela não prova que a
    # nova entrou. A conferência conta as linhas também.
    p = portal(fotos=["0071.JPG", "0071a.JPG"], sobe=False)

    resultado = uf.processar_ficha(p, "4500063671.0071", "0071", NOVAS, uf.MODO_PERGUNTAR,
                                   lambda *_a: uf.ADICIONAR)

    assert not resultado.ok


def test_exclui_de_baixo_para_cima_e_a_principal_fica_por_ultimo(portal):
    # Precaução: a primeira linha é a Principal, e tela desse tipo costuma
    # recusar excluí-la enquanto houver outra.
    p = portal(fotos=["0071e.JPG (principal)", "0071c.JPG", "0071d.JPG"])

    def click(seletor):
        if "fa-trash" in seletor:
            p.engine.dialogo = "[last()]" in seletor or len(p.engine.fotos) == 1
        elif "CONFIRMAR" in seletor and p.engine.dialogo:
            p.engine.ordem.append(("excluiu", p.engine.fotos.pop()))
            p.engine.dialogo = False
    p.engine.click_raw = click

    resultado = uf.processar_ficha(p, "4500063671.0071", "0071", NOVAS, uf.MODO_SUBSTITUIR)

    assert resultado.ok
    assert [passo[1] for passo in p.engine.ordem[:3]] == ["0071d.JPG", "0071c.JPG", "0071e.JPG (principal)"]


def test_lixeira_que_nao_exclui_para_a_ficha_sem_subir(portal):
    p = portal(fotos=["0071.JPG"])
    p.engine.click_raw = lambda _s: None  # o clique "pega", mas nada sai da tabela

    resultado = uf.processar_ficha(p, "4500063671.0071", "0071", NOVAS)

    assert not resultado.ok
    assert "excluir" in resultado.motivo
    assert p.engine.ordem == []


# ===========================================================================
# 3. A planilha, com arquivo de verdade
# ===========================================================================
def _status(tmp_path):
    caminho = tmp_path / "_STATUS_PMIB.xlsx"
    with openpyxl_de_verdade():
        from openpyxl import Workbook

        wb = Workbook()
        aba = wb.active
        aba.title = "Lista de Materiais"
        aba.append(["ITEM", "CÓDIGO PMIB", "DOCUMENTOS E IMAGENS"])
        aba.append([1, "4500063671.0071", ""])
        aba.append([2, "4500063671.0072", ""])
        wb.save(caminho)
    return caminho


def test_marcar_status_completo_e_incompleto_com_nota(tmp_path):
    pytest.importorskip("lxml")
    caminho = _status(tmp_path)
    resultados = [
        uf.ResultadoDaFicha("4500063671.0071", "0071", ok=True, tem_documentos=True),
        uf.ResultadoDaFicha("4500063671.0072", "0072", ok=True, tem_documentos=False),
        uf.ResultadoDaFicha("4500063671.0099", "0099", ok=False, motivo="falhou"),
    ]

    with openpyxl_de_verdade():
        quantas, recado = uf.marcar_status(str(caminho), resultados)
        from openpyxl import load_workbook

        aba = load_workbook(caminho)["Lista de Materiais"]

    assert quantas == 2, recado
    assert aba["C2"].value == "COMPLETO" and aba["C2"].comment is None
    assert aba["C3"].value == "INCOMPLETO"
    assert aba["C3"].comment.text == "Faltam documentos"


def test_ler_codigos_da_coluna_codigo_pmib(tmp_path):
    caminho = _status(tmp_path)

    with openpyxl_de_verdade():
        codigos = uf.ler_codigos(str(caminho))

    assert codigos == ["4500063671.0071", "4500063671.0072"]


# ===========================================================================
# 4. Até 10 fotos por envio, e sem foto repetida quando um envio falha
# ===========================================================================
def test_doze_fotos_sobem_em_dois_envios_de_10_e_2(portal):
    p = portal(fotos=[])
    doze = [f"/fotos/0071{letra}.JPG" for letra in ["", *"abcdefghijk"]]

    resultado = uf.processar_ficha(p, "4500063671.0071", "0071", doze)

    assert resultado.ok
    assert [len(envio) for envio in p.engine.envios] == [10, 2]


def test_envio_que_falha_so_reenvia_as_que_nao_entraram(portal, monkeypatch):
    # O diálogo pode ter gravado parte do envio antes de falhar. Reenviar tudo
    # era foto repetida na ficha (como as duas 0052.JPG da captura de 2026-11-03).
    p = portal(fotos=[])
    envios = p.engine.envios

    def _subir_falhando_na_primeira(_portal, descricao, caminhos, _log=None, **_tempos):
        envios.append(list(caminhos))
        if len(envios) == 1:                        # o envio grava só a 1ª e falha
            p.engine.fotos.append(caminhos[0].rsplit("/", 1)[-1])
            return False
        p.engine.fotos.extend(c.rsplit("/", 1)[-1] for c in caminhos)
        return True
    monkeypatch.setattr(uf.imagens, "subir_juntas", _subir_falhando_na_primeira)

    resultado = uf.processar_ficha(p, "4500063671.0071", "0071",
                                   ["/fotos/0071.JPG", "/fotos/0071a.JPG", "/fotos/0071b.JPG"])

    assert resultado.ok
    assert sorted(p.engine.fotos) == ["0071.JPG", "0071a.JPG", "0071b.JPG"]  # nenhuma duas vezes
    assert envios[1:] == [["/fotos/0071a.JPG"], ["/fotos/0071b.JPG"]]


def test_o_lote_nao_volta_para_a_lista_entre_fichas(monkeypatch):
    # `pesquisar_e_abrir` já vai para a lista; voltar antes era uma carga de
    # página a mais por ficha.
    class _PortalDoLote:
        voltas = 0

        def deve_parar(self):
            return False

        def ir_para_lista(self):
            self.voltas += 1

    monkeypatch.setattr(uf, "processar_ficha",
                        lambda _p, pmib, quatro, *_a, **_k: uf.ResultadoDaFicha(pmib, quatro, ok=True))
    robo = uf.UploadFotosAutomation()
    robo.portal = _PortalDoLote()

    robo.processar([("4500063671.0071", "0071", ["a"]), ("4500063671.0072", "0072", ["b"])])

    assert robo.portal.voltas == 0


# ===========================================================================
# 5. Portal lento (2026-11-03): esperar pela CONDIÇÃO, e mais quando ele está lento
# ===========================================================================
def test_aba_que_o_portal_marca_como_ativa_com_atraso_ainda_abre(monkeypatch):
    # Conferir o `aria-selected` no mesmo instante do clique dava "o portal não
    # marcou a aba como ativa" assim que o portal demorava um pouco.
    monkeypatch.setattr(uf.extrator.time, "sleep", lambda _s: None)
    leituras = {"n": 0}

    class _Engine:
        def contar(self, seletor):
            if "aria-selected" in seletor:
                leituras["n"] += 1
                return 1 if leituras["n"] >= 4 else 0
            return 1

        def atributo(self, *_a):
            return ""

    class _P:
        engine = _Engine()

        def safe_click(self, _s):
            pass

    assert uf.extrator.abrir_secao(_P(), "Documentos e imagens") is True


def test_dialogo_que_demora_a_abrir_ainda_recebe_a_descricao(monkeypatch):
    # Com 2 s fixos de espera, o diálogo lento ainda não tinha os campos e as
    # descrições ficavam em branco em silêncio.
    imgs = uf.imagens
    monkeypatch.setattr(imgs.time, "sleep", lambda _s: None)

    class _Engine:
        def __init__(self):
            self.leituras, self.enviados = 0, []

        def contar(self, seletor):
            if "Input_Description" in seletor:
                self.leituras += 1
                return 1 if self.leituras > 6 else 0
            if "filepond--list" in seletor:
                return 1 if self.enviados else 0
            return 1 if "Adicionar imagens" in seletor else 0

        def enviar_arquivo(self, _seletor, caminho):
            self.enviados.append(caminho)

    class _P:
        def __init__(self):
            self.engine, self.preenchidos, self.confirmacoes = _Engine(), [], []

        def safe_click(self, _s):
            pass

        def safe_fill(self, _seletor, texto):
            self.preenchidos.append(texto)

        def clicar_e_confirmar(self, _botao, _nome, _log=None, **kwargs):
            self.confirmacoes.append(kwargs)
            return True

    p = _P()
    assert imgs.subir_juntas(p, "imagens - 0071", ["a.jpg"], timeout_confirmacao=40) is True
    assert p.preenchidos == ["imagens - 0071", "imagens - 0071"]
    assert p.confirmacoes == [{"timeout_s": 40}]


def test_portal_lento_multiplica_as_esperas_e_o_tempo_do_motor(monkeypatch):
    criados = []
    monkeypatch.setattr(uf, "criar_engine", lambda _nome, wait_timeout: criados.append(wait_timeout))
    monkeypatch.setattr(uf, "PMIBPortal", lambda engine: engine)

    uf.UploadFotosAutomation(esperas=uf.Esperas(fator=2)).iniciar_driver()

    assert criados == [2 * uf.Esperas().motor_s]
    assert uf.Esperas(fator=2).tabela == 2 * uf.Esperas().tabela


def test_portal_lento_espera_as_fotos_que_demoram_a_aparecer(portal):
    # As linhas só chegam depois de 30 olhadas: no ritmo normal (20) a ficha
    # pareceria vazia e as fotos novas subiriam por cima das antigas.
    p = portal(fotos=["0071e.JPG"])
    reais, leituras = p.engine.contar, {"n": 0}

    def contar_lento(seletor):
        if seletor == uf.XPATH_LINHAS_DE_IMAGEM and leituras["n"] < 30:
            leituras["n"] += 1
            return 0
        return reais(seletor)
    p.engine.contar = contar_lento

    resultado = uf.processar_ficha(p, "4500063671.0071", "0071", NOVAS, uf.MODO_SUBSTITUIR,
                                   esperas=uf.Esperas(fator=2))

    assert resultado.ok
    assert p.engine.fotos == ["0071.JPG", "0071a.JPG"]



# ===========================================================================
# 6. O log do lote de 35 fichas (2026-11-03)
# ===========================================================================
def test_envio_que_salva_devagar_nao_e_reenviado(portal, monkeypatch):
    # O portal gravou o envio, mas o aviso veio tarde e a tabela demorou mais
    # que 3 s: o robô reenviava tudo e a ficha ficava com foto repetida.
    p = portal(fotos=[])
    leituras = {"n": 0}

    def _subir_lento(_portal, _descricao, caminhos, _log=None, **_tempos):
        p.engine.envios.append(list(caminhos))
        if len(p.engine.envios) == 1:
            p.engine.pendentes = [c.rsplit("/", 1)[-1] for c in caminhos]
            return False                           # "Não vi nenhuma mensagem de confirmação"
        p.engine.fotos.extend(c.rsplit("/", 1)[-1] for c in caminhos)
        return True
    monkeypatch.setattr(uf.imagens, "subir_juntas", _subir_lento)
    reais = p.engine.contar

    def contar(seletor):
        pendentes = getattr(p.engine, "pendentes", None)
        if pendentes and "normalize-space()=" in seletor:
            leituras["n"] += 1
            if leituras["n"] > 20:                 # ~10 s depois, a tabela mostra
                p.engine.fotos.extend(pendentes)
                p.engine.pendentes = None
        return reais(seletor)
    p.engine.contar = contar

    resultado = uf.processar_ficha(p, "4500063671.0071", "0071", NOVAS)

    assert resultado.ok, resultado.motivo
    assert len(p.engine.envios) == 1                # nada reenviado
    assert sorted(p.engine.fotos) == ["0071.JPG", "0071a.JPG"]


def test_foto_repetida_na_ficha_nao_e_ok(portal, monkeypatch):
    p = portal(fotos=[])

    def _subir_duas_vezes(_portal, _descricao, caminhos, _log=None, **_tempos):
        p.engine.fotos.extend(2 * [c.rsplit("/", 1)[-1] for c in caminhos])
        return True
    monkeypatch.setattr(uf.imagens, "subir_juntas", _subir_duas_vezes)

    resultado = uf.processar_ficha(p, "4500063671.0071", "0071", NOVAS)

    assert not resultado.ok
    assert "repetida" in resultado.motivo


def test_envio_maior_ganha_mais_tempo_de_processamento(portal, monkeypatch):
    # "O FilePond ainda estava processando depois de 60s" com 6 a 8 fotos.
    p = portal(fotos=[])
    tempos = []

    def _subir(_portal, _descricao, caminhos, _log=None, **kwargs):
        tempos.append((len(caminhos), kwargs["timeout_processamento"]))
        p.engine.fotos.extend(c.rsplit("/", 1)[-1] for c in caminhos)
        return True
    monkeypatch.setattr(uf.imagens, "subir_juntas", _subir)

    uf.subir_fotos(p, "x", [f"/f/0071{l}.JPG" for l in ["", *"abcdefghij"]])

    (n1, t1), (n2, t2) = tempos
    assert (n1, n2) == (10, 1) and t1 > t2



# ===========================================================================
# 7. Revisão de código de 2026-11-04
# ===========================================================================
def test_ler_codigos_de_planilha_sem_a_marca_de_dimensao(tmp_path):
    # Em só-leitura, o openpyxl tira o tamanho da aba do <dimension>; sem ele,
    # max_row é None e o cabeçalho "não existia".
    import re
    import zipfile
    caminho = _status(tmp_path)
    sem = tmp_path / "sem_dimension.xlsx"
    with zipfile.ZipFile(caminho) as zin, zipfile.ZipFile(sem, "w") as zout:
        for info in zin.infolist():
            dados = zin.read(info.filename)
            if info.filename.startswith("xl/worksheets/sheet"):
                dados = re.sub(rb"<dimension[^>]*/>", b"", dados)
            zout.writestr(info, dados)

    with openpyxl_de_verdade():
        codigos = uf.ler_codigos(str(sem))

    assert codigos == ["4500063671.0071", "4500063671.0072"]


def test_nota_que_nao_entrou_e_dita_no_console(tmp_path, monkeypatch):
    # Célula com comentário de outra pessoa: a nota não entra, e o console não
    # pode dizer que entrou.
    pytest.importorskip("lxml")
    from sigft.core.excel import cirurgico
    caminho = _status(tmp_path)
    reais = cirurgico.gravar_celulas
    monkeypatch.setattr(cirurgico, "gravar_celulas", lambda *a, **k: (reais(*a, **k), ["C3"])[1])
    linhas = []

    with openpyxl_de_verdade():
        uf.marcar_status(str(caminho), [uf.ResultadoDaFicha("4500063671.0072", "0072", ok=True)],
                         callback_log=linhas.append)

    assert any("C3" in linha and "nota" in linha.lower() for linha in linhas)


def test_linhas_que_chegam_em_blocos_sao_contadas_inteiras(portal):
    # Portal lento: 2 linhas, uma pausa, depois as 5. Duas leituras iguais
    # seguidas paravam a contagem em 2.
    p = portal(fotos=["a.JPG", "b.JPG", "c.JPG", "d.JPG", "e.JPG"])
    leituras = {"n": 0}
    reais = p.engine.contar

    def contar(seletor):
        if seletor == uf.XPATH_LINHAS_DE_IMAGEM:
            leituras["n"] += 1
            return 2 if leituras["n"] <= 3 else reais(seletor)
        return reais(seletor)
    p.engine.contar = contar

    assert uf.fotos_ao_abrir(p) == 5
