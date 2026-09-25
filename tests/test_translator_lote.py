r"""Tradutor 4.2 (`services/translator.py`): o lote de fichas, com o Excel e o
motor dublados.

O que estes testes seguram, e por quê (spec
`docs/superpowers/specs/2026-09-25-tradutor-local-design.md`):

* **Um Excel por LOTE, fechado no fim.** O código antigo criava um
  `xw.App(visible=False)` por ficha, com a pasta em branco do `add_book`, e o
  `quit()` só rodava com `books.count == 0` -- que nunca acontecia: cada ficha
  deixava um Excel invisível aberto até o SIG-FT fechar.
* **Uma leitura e uma escrita por ficha**, e nenhum `sleep`: era 1 s fixo por
  resposta.
* **O contrato com o Upload 4.3**: mesma aba, mesmos três cabeçalhos, a
  pergunta com o número na frente (o 4.3 tira o número e casa com o Master).
"""
import re
import sys
import types
from datetime import datetime

import pytest

from sigft.core import tradutor_local
from sigft.services import translator


# =============================================================================
# Dublê do Excel (o suficiente do xlwings para o tradutor)
# =============================================================================
def _coluna(letras):
    n = 0
    for c in letras:
        n = n * 26 + (ord(c.upper()) - 64)
    return n


class _Api(types.SimpleNamespace):
    """`range.api.X = ...` -- anota o que foi pedido, sem executar nada."""

    def __init__(self):
        super().__init__(Borders=types.SimpleNamespace(), Font=types.SimpleNamespace())


class _Faixa:
    def __init__(self, aba, r1, c1, r2, c2):
        self.aba, self.r1, self.c1, self.r2, self.c2 = aba, r1, c1, r2, c2
        self.api = _Api()
        aba.faixas.append(self)

    def options(self, **_kw):
        return self

    @property
    def value(self):
        self.aba.leituras += 1
        return [[self.aba.celulas.get((r, c)) for c in range(self.c1, self.c2 + 1)]
                for r in range(self.r1, self.r2 + 1)]

    @value.setter
    def value(self, matriz):
        self.aba.escritas += 1
        self.aba.formato_texto_antes_de_escrever = self.aba.formato_texto
        for i, linha in enumerate(matriz):
            for j, valor in enumerate(linha):
                self.aba.celulas[(self.r1 + i, self.c1 + j)] = valor

    @property
    def number_format(self):
        return None

    @number_format.setter
    def number_format(self, formato):
        if formato == "@":
            self.aba.formato_texto = True

    column_width = None
    row_height = None
    color = None


class _Aba:
    def __init__(self, nome, celulas=None):
        self.name = nome
        self.celulas = dict(celulas or {})
        self.faixas, self.leituras, self.escritas = [], 0, 0
        self.formato_texto = False
        self.formato_texto_antes_de_escrever = None
        self.apagada = False
        self.livro = None

    def range(self, a, b=None):
        if isinstance(a, tuple):
            (r1, c1), (r2, c2) = a, (b or a)
            return _Faixa(self, r1, c1, r2, c2)
        if re.fullmatch(r"[A-Z]+:[A-Z]+", a):
            x, y = a.split(":")
            return _Faixa(self, 1, _coluna(x), 1048576, _coluna(y))
        if re.fullmatch(r"\d+:\d+", a):
            x, y = a.split(":")
            return _Faixa(self, int(x), 1, int(y), 16384)
        partes = [re.fullmatch(r"([A-Z]+)(\d+)", p).groups() for p in a.split(":")]
        (l1, n1), (l2, n2) = partes[0], partes[-1]
        return _Faixa(self, int(n1), _coluna(l1), int(n2), _coluna(l2))

    def delete(self):
        self.apagada = True
        self.livro.abas.remove(self)


class _Abas:
    def __init__(self, livro):
        self.livro = livro

    def __iter__(self):
        return iter(list(self.livro.abas))

    def __getitem__(self, chave):
        if isinstance(chave, int):
            return self.livro.abas[chave]
        return next(a for a in self.livro.abas if a.name == chave)

    def add(self, nome, after=None):
        aba = _Aba(nome)
        aba.livro = self.livro
        self.livro.abas.append(aba)
        return aba


class _Livro:
    def __init__(self, caminho, abas):
        self.caminho = caminho
        self.abas = abas
        for aba in abas:
            aba.livro = self
        self.sheets = _Abas(self)
        self.salvo = False
        self.fechado = False

    def save(self, *_a):
        self.salvo = True

    def close(self):
        self.fechado = True


class _ExcelFalso:
    def __init__(self, fichas):
        self.fichas = fichas            # caminho -> lista de _Aba
        self.abertos = []
        self.quit_chamado = 0
        self.kill_chamado = 0

    @property
    def books(self):
        excel = self

        class _Books:
            def open(self, caminho):
                livro = _Livro(caminho, excel.fichas[str(caminho)])
                excel.abertos.append(livro)
                return livro
        return _Books()

    def quit(self):
        self.quit_chamado += 1

    def kill(self):
        self.kill_chamado += 1


def _ficha(respostas, linha=79, aba="Ficha Técnica Padrão"):
    """`respostas`: lista de (pergunta, resposta) a partir da linha 79."""
    celulas = {}
    for i, (pergunta, resposta) in enumerate(respostas):
        celulas[(linha + i, 3)] = pergunta
        celulas[(linha + i, 13)] = resposta
    return [_Aba(aba, celulas)]


class _MotorFalso:
    """Traduz trocando 'aço' por 'acero' e anota os lotes."""

    def __init__(self):
        self.lotes = []
        self.preparado = 0

    def preparar(self):
        self.preparado += 1

    def __call__(self, textos):
        self.lotes.append(list(textos))
        return [t.replace("Aço", "Acero").replace("aço", "acero").replace("inoxidável", "inoxidable")
                for t in textos]


def _sem_acento(texto):
    import unicodedata
    return "".join(c for c in unicodedata.normalize("NFKD", str(texto))
                   if not unicodedata.combining(c))


@pytest.fixture(autouse=True)
def _unidecode_de_verdade(monkeypatch):
    """O `conftest.py` dubla o `unidecode` com um MagicMock."""
    monkeypatch.setattr(translator, "unidecode", _sem_acento)


def _rodar(fichas, caminhos=None, motor=None, glossario=None, **kw):
    excel = _ExcelFalso(fichas)
    aberturas = []

    def abrir():
        aberturas.append(1)
        return excel

    motor = motor or _MotorFalso()
    tradutor = translator.TechnicalTranslator(
        motor=motor, abrir_excel=abrir, glossario=glossario or {})
    caminhos = caminhos or list(fichas)
    mensagens = list(tradutor.processar_arquivos(caminhos, **kw))
    return excel, aberturas, motor, mensagens


def _aba_copiar(livro):
    return next(a for a in livro.abas if a.name == translator.ABA_DESTINO)


def _linhas(aba):
    ultima = max(r for r, _ in aba.celulas)
    return [[aba.celulas.get((r, c)) for c in (1, 2, 3)] for r in range(1, ultima + 1)]


# =============================================================================
# A. O Excel: um por lote, fechado no fim
# =============================================================================
def test_um_excel_so_para_o_lote_e_ele_fecha_no_fim():
    fichas = {f"f{i}.xlsx": _ficha([("1 - MATERIAL (Informar):", "Aço")]) for i in range(3)}
    excel, aberturas, _, mensagens = _rodar(fichas)
    assert len(aberturas) == 1
    assert excel.quit_chamado == 1
    assert [m for m in mensagens if m == "SUCESSO"] == ["SUCESSO"] * 3
    assert all(livro.fechado and livro.salvo for livro in excel.abertos)


def test_o_excel_real_abre_sem_pasta_em_branco_e_invisivel(monkeypatch):
    """O `add_book=True` padrão do xlwings era o que impedia o `quit()`."""
    chamadas = []
    falso = types.SimpleNamespace(App=lambda **kw: chamadas.append(kw) or types.SimpleNamespace())
    monkeypatch.setitem(sys.modules, "xlwings", falso)
    translator._excel_invisivel()
    assert chamadas == [{"visible": False, "add_book": False}]


def test_excel_fecha_mesmo_quando_a_ficha_da_erro():
    fichas = {"quebrada.xlsx": [_Aba("Outra coisa")], "boa.xlsx": _ficha([("1 - A:", "Aço")])}
    excel, _, _, mensagens = _rodar(fichas, caminhos=["quebrada.xlsx", "boa.xlsx"])
    assert mensagens.count("ERRO") == 1 and mensagens.count("SUCESSO") == 1
    assert excel.quit_chamado == 1
    assert all(livro.fechado for livro in excel.abertos)


def test_nenhum_sleep(monkeypatch):
    def proibido(_s):
        raise AssertionError("o tradutor nao espera mais 1 s por resposta")
    monkeypatch.setattr(translator.time, "sleep", proibido)
    _rodar({"f.xlsx": _ficha([("1 - A:", "Aço"), ("2 - B:", "Aço inoxidável")])})


# =============================================================================
# B. Leitura e escrita em bloco
# =============================================================================
def test_le_a_faixa_numa_chamada_e_escreve_a_aba_numa_chamada():
    excel, _, motor, _ = _rodar({"f.xlsx": _ficha([("1 - A:", "Aço"), ("2 - B:", "Aço inoxidável"),
                                                    ("3 - C:", "220 V")])})
    [livro] = excel.abertos
    assert livro.abas[0].leituras == 1
    assert _aba_copiar(livro).escritas == 1
    assert motor.lotes == [["Aço", "Aço inoxidável"]]          # um lote; o 220 V passa direto


def test_resposta_repetida_em_outra_ficha_nao_volta_ao_motor():
    """"NÃO APLICÁVEL", "Conforme desenho": as fichas de um lote repetem muito.
    A memória vale só para o lote (o glossário não muda no meio dele)."""
    fichas = {"a.xlsx": _ficha([("1 - A:", "Aço inoxidável"), ("2 - B:", "Aço")]),
              "b.xlsx": _ficha([("1 - A:", "Aço inoxidável"), ("2 - B:", "Aço carbono")])}
    excel, _, motor, _ = _rodar(fichas, caminhos=["a.xlsx", "b.xlsx"])
    assert motor.lotes == [["Aço inoxidável", "Aço"], ["Aço carbono"]]
    linhas_b = _linhas(_aba_copiar(excel.abertos[1]))
    assert linhas_b[1][1] == "Acero inoxidable"


def test_a_leitura_comeca_na_linha_do_config():
    from sigft import config
    fichas = {"f.xlsx": _ficha([("1 - A:", "Aço")], linha=config.LINHA_SPECS_FICHA)}
    excel, _, _, _ = _rodar(fichas)
    faixa = excel.abertos[0].abas[0].faixas[0]
    assert (faixa.r1, faixa.c1, faixa.c2) == (config.LINHA_SPECS_FICHA, 3, 13)


def test_a_aba_copiar_segue_o_contrato_do_upload():
    excel, _, _, _ = _rodar({"f.xlsx": _ficha([("1 - MATERIAL (Informar o material):", "Aço inoxidável"),
                                               ("2 - TENSAO (V):", 220.0)])})
    linhas = _linhas(_aba_copiar(excel.abertos[0]))
    assert linhas[0] == ["Pergunta", "Resposta (Espanhol s/ caracteres especiais)",
                         "Resposta (Português s/ caracteres especiais)"]
    assert linhas[1] == ["1 - MATERIAL", "Acero inoxidable", "Aco inoxidavel"]
    assert linhas[2] == ["2 - TENSAO", "220", "220"]


def test_a_aba_copiar_antiga_e_recriada():
    abas = _ficha([("1 - A:", "Aço")]) + [_Aba("Especificações técnicas copiar", {(1, 1): "velha"})]
    excel, _, _, _ = _rodar({"f.xlsx": abas})
    [livro] = excel.abertos
    copias = [a for a in livro.abas if a.name == translator.ABA_DESTINO]
    assert len(copias) == 1 and copias[0].celulas.get((1, 1)) == "Pergunta"


def test_colunas_viram_texto_antes_da_escrita():
    """Sem o formato de texto o Excel converte `1/2` em data ao gravar."""
    excel, _, _, _ = _rodar({"f.xlsx": _ficha([("1 - A:", "1/2")])})
    assert _aba_copiar(excel.abertos[0]).formato_texto_antes_de_escrever is True


def test_para_na_primeira_pergunta_vazia():
    fichas = {"f.xlsx": _ficha([("1 - A:", "Aço"), (None, "lixo"), ("3 - C:", "Aço")])}
    excel, _, _, _ = _rodar(fichas)
    assert len(_linhas(_aba_copiar(excel.abertos[0]))) == 2


# =============================================================================
# C. O que sai de cada célula
# =============================================================================
@pytest.mark.parametrize("valor, texto", [
    (220.0, "220"), (0.5, "0,5"), (1500, "1500"), (None, ""), ("  Aço  ", "Aço"),
    (datetime(2026, 9, 25), "25/09/2026"), (True, "Sim"), (False, "Não"),
])
def test_texto_da_celula(valor, texto):
    assert translator.texto_da_celula(valor) == texto


@pytest.mark.parametrize("pergunta, nome", [
    ("1 - PRESSÃO (Informar em bar):", "1 - PRESSÃO"),
    ("5 - NOME:", "5 - NOME"),
    ("9 - TIPO CONSTRUTIVO (Indicar o tipo (Número de desenho, outros)):", "9 - TIPO CONSTRUTIVO"),
    # PENDENCIAS 2026-09-24: o nome tem parênteses; a ajuda é o ÚLTIMO grupo.
    ("3 - FAIXA DE TENSAO DE ALIMENTACAO (CA) (Informar a faixa):",
     "3 - FAIXA DE TENSAO DE ALIMENTACAO (CA)"),
    ("4 - FAIXA DE TENSAO DE ALIMENTACAO (CC) (Informar a faixa):",
     "4 - FAIXA DE TENSAO DE ALIMENTACAO (CC)"),
    ("7 - NOME (ajuda sem fechar:", "7 - NOME"),
])
def test_nome_da_pergunta(pergunta, nome):
    assert translator.nome_da_pergunta(pergunta) == nome


# =============================================================================
# D. Erros e avisos
# =============================================================================
def test_ficha_em_ingles_explica_o_motivo():
    excel, _, _, mensagens = _rodar({"en.xlsx": [_Aba("Standard Technical Sheet")]})
    assert "ERRO" in mensagens
    assert any("ingles" in _sem_acento(m).lower() for m in mensagens)


def test_aba_com_nome_sem_acento_serve():
    excel, _, _, mensagens = _rodar({"f.xlsx": _ficha([("1 - A:", "Aço")], aba="Ficha Tecnica Padrao")})
    assert "SUCESSO" in mensagens


def test_modelo_ausente_nem_abre_o_excel():
    class _SemModelo(_MotorFalso):
        def preparar(self):
            raise tradutor_local.ModeloAusente("Nao achei o modelo do tradutor local.")

    excel, aberturas, _, mensagens = _rodar({"f.xlsx": _ficha([("1 - A:", "Aço")])}, motor=_SemModelo())
    assert aberturas == []
    assert mensagens[-1] == "ABORTADO"
    assert any("modelo do tradutor" in m for m in mensagens)


def test_aviso_de_conferir_vai_para_o_log_com_a_pergunta():
    def muda_numero(textos):
        return [t.replace("10", "11") for t in textos]

    _, _, _, mensagens = _rodar({"f.xlsx": _ficha([("1 - VIDA UTIL (anos):", "Vida de 10 anos")])},
                                motor=muda_numero)
    assert any("[CONFERIR]" in m and "1 - VIDA UTIL" in m for m in mensagens)


def test_parar_entre_fichas_fecha_o_excel():
    fichas = {f"f{i}.xlsx": _ficha([("1 - A:", "Aço")]) for i in range(3)}
    excel = _ExcelFalso(fichas)
    tradutor = translator.TechnicalTranslator(motor=_MotorFalso(), abrir_excel=lambda: excel, glossario={})
    mensagens = []
    for m in tradutor.processar_arquivos(list(fichas)):
        mensagens.append(m)
        if m == "SUCESSO":
            tradutor.request_stop()
    assert mensagens[-1] == "PARADO"
    assert mensagens.count("SUCESSO") == 1
    assert excel.quit_chamado == 1


def test_resumo_final_tem_contagem_e_tempo():
    _, _, _, mensagens = _rodar({"f.xlsx": _ficha([("1 - A:", "Aço"), ("2 - B:", "220 V")])})
    final = [m for m in mensagens if m.startswith("Tradução concluída")]
    assert final and "1 de 1" in final[0] and " s" in final[0]


def test_o_log_diz_que_nada_sai_do_computador():
    _, _, _, mensagens = _rodar({"f.xlsx": _ficha([("1 - A:", "Aço")])})
    assert any("nada sai deste computador" in m for m in mensagens)


# =============================================================================
# E. Compatibilidade
# =============================================================================
def test_processar_arquivo_de_uma_ficha_continua_existindo():
    excel = _ExcelFalso({"f.xlsx": _ficha([("1 - A:", "Aço")])})
    tradutor = translator.TechnicalTranslator(motor=_MotorFalso(), abrir_excel=lambda: excel, glossario={})
    mensagens = list(tradutor.processar_arquivo("f.xlsx"))
    assert "SUCESSO" in mensagens and excel.quit_chamado == 1


def test_caminho_do_glossario_cria_o_arquivo_do_usuario(tmp_path, monkeypatch):
    """O botão "Abrir glossário" da tela precisa de um arquivo que exista."""
    alvo = tmp_path / "traducao" / "GLOSSARIO_PT_ES.txt"
    monkeypatch.setattr(translator.tr, "caminho_glossario_do_usuario", lambda: alvo)
    caminho = translator.TechnicalTranslator(motor=_MotorFalso()).caminho_do_glossario()
    assert str(caminho) == str(alvo) and alvo.exists()


def test_sem_glossario_injetado_vale_o_da_casa_com_o_do_usuario(tmp_path, monkeypatch):
    alvo = tmp_path / "G.txt"
    alvo.write_text("mancal = rodamiento\n", encoding="utf-8")
    monkeypatch.setattr(translator.tr, "caminho_glossario_do_usuario", lambda: alvo)
    motor = _MotorFalso()
    excel = _ExcelFalso({"f.xlsx": _ficha([("1 - A:", "Mancal e porca")])})
    tradutor = translator.TechnicalTranslator(motor=motor, abrir_excel=lambda: excel)
    list(tradutor.processar_arquivos(["f.xlsx"]))
    enviados = motor.lotes[0]
    assert any("rodamiento" in t.lower() for t in enviados)   # do usuário
    assert any("tuerca" in t.lower() for t in enviados)       # da casa


def test_status_que_a_tela_nao_mostra_estao_listados():
    assert {"SUCESSO", "ERRO", "ERRO_MOVER", "PARADO", "ABORTADO"} <= translator.STATUS


def test_o_glossario_vai_ao_motor():
    """O tradutor passa o glossário adiante: a versão com o termo da casa já
    em espanhol está entre as que o motor recebe."""
    motor = _MotorFalso()
    _rodar({"f.xlsx": _ficha([("1 - A:", "Porca de aço")])}, motor=motor, glossario={"porca": "tuerca"})
    assert "Tuerca de aço" in motor.lotes[0]


# =============================================================================
# F. Caminho longo (o Excel não abre acima de ~218 caracteres)
# =============================================================================
class _QualquerCaminho(dict):
    """A cópia temporária tem outro nome; o dublê devolve a mesma ficha."""

    def __init__(self, abas):
        super().__init__()
        self.abas = abas

    def __getitem__(self, _caminho):
        return self.abas


def _caminho_longo(tmp_path):
    pasta = tmp_path
    while len(str(pasta)) < 250:
        pasta = pasta / ("p" * 40)
    pasta.mkdir(parents=True)
    arquivo = pasta / "4500063671.0001.xlsx"
    arquivo.write_bytes(b"ficha original")
    return arquivo


def test_caminho_longo_usa_copia_temporaria_e_devolve(tmp_path, monkeypatch):
    monkeypatch.setattr(translator.tempfile, "gettempdir", lambda: str(tmp_path))
    arquivo = _caminho_longo(tmp_path)
    excel = _ExcelFalso(_QualquerCaminho(_ficha([("1 - A:", "Aço")])))
    tradutor = translator.TechnicalTranslator(motor=_MotorFalso(), abrir_excel=lambda: excel, glossario={})
    mensagens = list(tradutor.processar_arquivos([str(arquivo)]))
    assert "SUCESSO" in mensagens
    assert excel.abertos[0].caminho != str(arquivo)            # abriu a cópia
    assert arquivo.read_bytes() == b"ficha original"           # a cópia voltou
    assert not list(tmp_path.glob("temp_*"))                   # e foi apagada


def test_caminho_longo_que_falha_nao_deixa_copia_para_tras(tmp_path, monkeypatch):
    monkeypatch.setattr(translator.tempfile, "gettempdir", lambda: str(tmp_path))
    arquivo = _caminho_longo(tmp_path)
    excel = _ExcelFalso(_QualquerCaminho([_Aba("Outra coisa")]))
    tradutor = translator.TechnicalTranslator(motor=_MotorFalso(), abrir_excel=lambda: excel, glossario={})
    mensagens = list(tradutor.processar_arquivos([str(arquivo)]))
    assert "ERRO" in mensagens
    assert not list(tmp_path.glob("temp_*"))
