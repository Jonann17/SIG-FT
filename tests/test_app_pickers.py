"""Testes de `sigft/app/widgets/pickers.py` — Checkpoint 7.2 (Fase 7).

Duas coisas importam aqui, e nenhuma delas é aparência:

1. **A memória de caminhos é embutida** (exigência literal do CP 7.2). A tela
   declara `chave`/`categoria` uma vez, ao construir a linha, e nunca mais
   chama `file_dialogs`. Antes, cada `command=` repetia a chamada — e um
   esquecimento fazia AQUELE campo perder a memória em silêncio, sem quebrar
   nada. Sintoma: "esse botão sempre abre na pasta errada".

2. **Cancelar não pode apagar o que já estava escolhido.** As telas antigas
   protegiam isso com um `if f:` antes de mexer no label; um picker que
   esquecesse essa guarda transformaria um Esc distraído em perda de trabalho.

Os diálogos são injetados via `dialog_fn` — o mesmo mecanismo que
`test_file_dialogs.py` usa. Nenhum teste abre seletor de verdade (já foi um
defeito real deste projeto abrir um na tela de quem rodava a suíte).
"""
from __future__ import annotations

import customtkinter as ctk  # dublê — tests/ctk_falso.py
import pytest

from sigft.app import theme
from sigft.app.widgets import pickers


@pytest.fixture()
def raiz():
    return ctk.CTk()


@pytest.fixture()
def config(tmp_path):
    """`user_prefs.json` de teste — nunca toca o real do repositório."""
    return tmp_path / "user_prefs.json"


def _dialogo_que_devolve(valor, registro=None):
    """Dublê de diálogo: devolve `valor` e anota os kwargs recebidos."""

    def _dialogo(**kwargs):
        if registro is not None:
            registro.append(kwargs)
        return valor

    return _dialogo


# =============================================================================
# A. FilePickerRow
# =============================================================================

def test_comeca_vazio_e_cinza(raiz):
    linha = pickers.FilePickerRow(
        raiz, chave="x.y", categoria="excel", texto_botao="Selecionar"
    )

    assert linha.valor is None
    assert linha.label_status.kwargs["text"] == pickers.TEXTO_SEM_ARQUIVO
    assert linha.label_status.kwargs["text_color"] == theme.COR_TEXTO_APOIO


def test_escolher_arquivo_mostra_o_nome_base_em_verde(raiz, tmp_path):
    arquivo = tmp_path / "ficha.xlsx"
    arquivo.write_text("x", encoding="utf-8")

    linha = pickers.FilePickerRow(
        raiz,
        chave="x.y",
        categoria="excel",
        texto_botao="Selecionar",
        dialog_fn=_dialogo_que_devolve(str(arquivo)),
    )
    linha._abrir_dialogo()

    assert linha.valor == str(arquivo)
    # Nome-base, não o caminho inteiro: era o que as telas mostravam.
    assert linha.label_status.kwargs["text"] == "ficha.xlsx"
    assert linha.label_status.kwargs["text_color"] == theme.COLORS["accent"]


def test_cancelar_o_dialogo_preserva_a_escolha_anterior(raiz, tmp_path):
    """Um Esc distraído não pode apagar o trabalho já feito."""
    arquivo = tmp_path / "ficha.xlsx"
    arquivo.write_text("x", encoding="utf-8")

    linha = pickers.FilePickerRow(
        raiz,
        chave="x.y",
        categoria="excel",
        texto_botao="Selecionar",
        dialog_fn=_dialogo_que_devolve(str(arquivo)),
    )
    linha._abrir_dialogo()

    # Agora o usuário abre e cancela (o tkinter devolve "" nesse caso).
    linha._dialog_fn = _dialogo_que_devolve("")
    linha._abrir_dialogo()

    assert linha.valor == str(arquivo)
    assert linha.label_status.kwargs["text"] == "ficha.xlsx"


def test_limpar_volta_ao_estado_cinza(raiz, tmp_path):
    arquivo = tmp_path / "ficha.xlsx"
    arquivo.write_text("x", encoding="utf-8")

    linha = pickers.FilePickerRow(
        raiz,
        chave="x.y",
        categoria="excel",
        texto_botao="Selecionar",
        dialog_fn=_dialogo_que_devolve(str(arquivo)),
    )
    linha._abrir_dialogo()
    linha.limpar()

    assert linha.valor is None
    assert linha.label_status.kwargs["text"] == pickers.TEXTO_SEM_ARQUIVO
    assert linha.label_status.kwargs["text_color"] == theme.COR_TEXTO_APOIO


def test_callback_ao_escolher_recebe_o_caminho(raiz, tmp_path):
    arquivo = tmp_path / "ficha.xlsx"
    arquivo.write_text("x", encoding="utf-8")
    recebidos = []

    linha = pickers.FilePickerRow(
        raiz,
        chave="x.y",
        categoria="excel",
        texto_botao="Selecionar",
        ao_escolher=recebidos.append,
        dialog_fn=_dialogo_que_devolve(str(arquivo)),
    )
    linha._abrir_dialogo()

    assert recebidos == [str(arquivo)]


def test_callback_nao_dispara_quando_o_usuario_cancela(raiz):
    recebidos = []

    linha = pickers.FilePickerRow(
        raiz,
        chave="x.y",
        categoria="excel",
        texto_botao="Selecionar",
        ao_escolher=recebidos.append,
        dialog_fn=_dialogo_que_devolve(""),
    )
    linha._abrir_dialogo()

    assert recebidos == []


# =============================================================================
# B. A memória de caminhos é EMBUTIDA — a exigência do checkpoint
# =============================================================================

def test_a_chave_declarada_chega_ao_file_dialogs(raiz, tmp_path, monkeypatch):
    """A tela declara chave/categoria uma vez; o picker cuida do resto."""
    chamadas = []

    def espiao(chave, categoria, **kwargs):
        chamadas.append((chave, categoria))
        return ""

    monkeypatch.setattr(pickers.file_dialogs, "ask_open_file", espiao)

    linha = pickers.FilePickerRow(
        raiz, chave="pdm.template", categoria="excel", texto_botao="Selecionar"
    )
    linha._abrir_dialogo()

    assert chamadas == [("pdm.template", "excel")]


def test_a_pasta_escolhida_fica_memorizada_para_a_proxima_vez(raiz, tmp_path, monkeypatch):
    """O ganho de verdade do CP 1.5, agora automático.

    Escolher um arquivo em `<tmp>/fichas/` tem de fazer o PRÓXIMO diálogo da
    mesma chave abrir em `<tmp>/fichas/`, sem a tela pedir nada.
    """
    pasta = tmp_path / "fichas"
    pasta.mkdir()
    arquivo = pasta / "ficha.xlsx"
    arquivo.write_text("x", encoding="utf-8")

    config = tmp_path / "user_prefs.json"
    monkeypatch.setattr(pickers.file_dialogs.prefs, "CONFIG_FILE", str(config))

    recebidos = []
    linha = pickers.FilePickerRow(
        raiz,
        chave="autospec.ficha",
        categoria="excel",
        texto_botao="Selecionar",
        dialog_fn=_dialogo_que_devolve(str(arquivo), recebidos),
    )

    linha._abrir_dialogo()  # 1ª vez: sem memória
    linha._abrir_dialogo()  # 2ª vez: deve abrir na pasta da 1ª

    assert recebidos[1]["initialdir"] == str(pasta)


def test_cada_categoria_lembra_a_propria_pasta(raiz, tmp_path, monkeypatch):
    """O caso citado na decisão nº 7: no AutoSpec, o seletor de ficha Excel
    abre na pasta do último Excel e o de manuais na do último PDF — sem
    vai-e-vem entre pastas."""
    pasta_excel = tmp_path / "planilhas"
    pasta_excel.mkdir()
    (pasta_excel / "f.xlsx").write_text("x", encoding="utf-8")

    pasta_pdf = tmp_path / "manuais"
    pasta_pdf.mkdir()
    (pasta_pdf / "m.pdf").write_text("x", encoding="utf-8")

    config = tmp_path / "user_prefs.json"
    monkeypatch.setattr(pickers.file_dialogs.prefs, "CONFIG_FILE", str(config))

    reg_excel, reg_pdf = [], []
    linha_excel = pickers.FilePickerRow(
        raiz,
        chave="autospec.ficha",
        categoria="excel",
        texto_botao="Ficha",
        dialog_fn=_dialogo_que_devolve(str(pasta_excel / "f.xlsx"), reg_excel),
    )
    linha_pdf = pickers.MultiFilePickerRow(
        raiz,
        chave="autospec.manuais",
        categoria="pdf",
        texto_botao="Manuais",
        dialog_fn=_dialogo_que_devolve((str(pasta_pdf / "m.pdf"),), reg_pdf),
    )

    linha_excel._abrir_dialogo()
    linha_pdf._abrir_dialogo()
    linha_excel._abrir_dialogo()
    linha_pdf._abrir_dialogo()

    assert reg_excel[1]["initialdir"] == str(pasta_excel)
    assert reg_pdf[1]["initialdir"] == str(pasta_pdf)


# =============================================================================
# C. MultiFilePickerRow e FolderPickerRow
# =============================================================================

def test_multi_mostra_a_contagem(raiz, tmp_path):
    arquivos = tuple(str(tmp_path / f"f{i}.xlsx") for i in range(3))

    linha = pickers.MultiFilePickerRow(
        raiz,
        chave="x.y",
        categoria="excel",
        texto_botao="Selecionar",
        dialog_fn=_dialogo_que_devolve(arquivos),
    )
    linha._abrir_dialogo()

    assert linha.valor == arquivos
    assert linha.label_status.kwargs["text"] == "3 arquivos selecionados"


def test_multi_cancelado_nao_apaga(raiz, tmp_path):
    arquivos = (str(tmp_path / "f.xlsx"),)
    linha = pickers.MultiFilePickerRow(
        raiz,
        chave="x.y",
        categoria="excel",
        texto_botao="Selecionar",
        dialog_fn=_dialogo_que_devolve(arquivos),
    )
    linha._abrir_dialogo()

    linha._dialog_fn = _dialogo_que_devolve(())
    linha._abrir_dialogo()

    assert linha.valor == arquivos


def test_pasta_mostra_o_nome_da_pasta(raiz, tmp_path):
    pasta = tmp_path / "saida"
    pasta.mkdir()

    linha = pickers.FolderPickerRow(
        raiz,
        chave="analyzer.saida",
        texto_botao="Pasta de saída",
        dialog_fn=_dialogo_que_devolve(str(pasta)),
    )
    linha._abrir_dialogo()

    assert linha.label_status.kwargs["text"] == "saida"


def test_pasta_terminada_em_barra_mostra_o_caminho_inteiro(raiz):
    """`os.path.basename("C:/x/")` é vazio — as telas já tratavam isso."""
    linha = pickers.FolderPickerRow(
        raiz,
        chave="x.y",
        texto_botao="Pasta",
        dialog_fn=_dialogo_que_devolve("C:/dados/"),
    )
    linha._abrir_dialogo()

    assert linha.label_status.kwargs["text"] == "C:/dados/"


def test_pasta_comeca_com_o_texto_de_pasta_vazia(raiz):
    linha = pickers.FolderPickerRow(raiz, chave="x.y", texto_botao="Pasta")
    assert linha.label_status.kwargs["text"] == pickers.TEXTO_SEM_PASTA


# =============================================================================
# D. FileQueueList — as 2 cópias idênticas
# =============================================================================

def _fila(raiz, valor=(), registro=None):
    return pickers.FileQueueList(
        raiz, chave="uc.fichas", dialog_fn=_dialogo_que_devolve(valor, registro)
    )


def test_fila_comeca_vazia_com_contador_zerado(raiz):
    fila = _fila(raiz)

    assert fila.arquivos == []
    assert fila.label_contador.kwargs["text"] == "Planilhas PMIB Selecionadas (0)"


def test_adicionar_preenche_lista_e_contador(raiz):
    fila = _fila(raiz, ("/a/f1.xlsx", "/a/f2.xlsx"))
    fila.adicionar()

    assert fila.arquivos == ["/a/f1.xlsx", "/a/f2.xlsx"]
    # A listbox mostra o nome-base com o prefixo das duas cópias (emoji +
    # dois espaços) -- não o caminho inteiro.
    assert fila.listbox.itens == [" 📊  f1.xlsx", " 📊  f2.xlsx"]
    assert fila.label_contador.kwargs["text"] == "Planilhas PMIB Selecionadas (2)"


def test_adicionar_o_mesmo_arquivo_duas_vezes_nao_duplica(raiz):
    """Duplicar na fila significa processar a mesma ficha duas vezes."""
    fila = _fila(raiz, ("/a/f1.xlsx",))
    fila.adicionar()
    fila.adicionar()

    assert fila.arquivos == ["/a/f1.xlsx"]


def test_adicionar_cancelado_nao_mexe_na_fila(raiz):
    fila = _fila(raiz, ("/a/f1.xlsx",))
    fila.adicionar()

    fila._dialog_fn = _dialogo_que_devolve(())
    fila.adicionar()

    assert fila.arquivos == ["/a/f1.xlsx"]


def test_remover_selecao_multipla_apaga_as_linhas_certas(raiz):
    """De trás para frente: remover pela frente desloca os índices seguintes,
    e a seleção múltipla passaria a apagar a linha errada."""
    fila = _fila(raiz, ("/a/f0.xlsx", "/a/f1.xlsx", "/a/f2.xlsx", "/a/f3.xlsx"))
    fila.adicionar()

    fila.listbox.selecionar(0, 2)
    fila.remover_selecionados()

    assert fila.arquivos == ["/a/f1.xlsx", "/a/f3.xlsx"]
    assert fila.listbox.itens == [" 📊  f1.xlsx", " 📊  f3.xlsx"]
    assert fila.label_contador.kwargs["text"] == "Planilhas PMIB Selecionadas (2)"


def test_remover_sem_selecao_nao_faz_nada(raiz):
    fila = _fila(raiz, ("/a/f1.xlsx",))
    fila.adicionar()

    fila.remover_selecionados()

    assert fila.arquivos == ["/a/f1.xlsx"]


def test_limpar_esvazia_tudo(raiz):
    fila = _fila(raiz, ("/a/f1.xlsx", "/a/f2.xlsx"))
    fila.adicionar()
    fila.limpar()

    assert fila.arquivos == []
    assert fila.listbox.itens == []
    assert fila.label_contador.kwargs["text"] == "Planilhas PMIB Selecionadas (0)"


def test_arquivos_devolve_copia(raiz):
    """Mexer no retorno não pode alterar a fila por baixo."""
    fila = _fila(raiz, ("/a/f1.xlsx",))
    fila.adicionar()

    fila.arquivos.append("/intruso.xlsx")

    assert fila.arquivos == ["/a/f1.xlsx"]


def test_definir_substitui_a_fila_inteira(raiz):
    fila = _fila(raiz, ("/a/f1.xlsx",))
    fila.adicionar()

    fila.definir(["/b/outro.xlsx"])

    assert fila.arquivos == ["/b/outro.xlsx"]
    assert fila.listbox.itens == [" 📊  outro.xlsx"]


def test_rotulo_do_contador_e_configuravel(raiz):
    fila = pickers.FileQueueList(
        raiz, chave="x.y", rotulo="Fichas", dialog_fn=_dialogo_que_devolve(())
    )
    assert fila.label_contador.kwargs["text"] == "Fichas (0)"


def test_os_tres_botoes_tem_os_rotulos_originais(raiz):
    fila = _fila(raiz)

    assert fila.botao_adicionar.kwargs["text"] == "Adicionar Fichas"
    assert fila.botao_remover.kwargs["text"] == "Remover Seleção"
    assert fila.botao_limpar.kwargs["text"] == "Limpar Tudo"
    assert fila.botao_remover.kwargs["fg_color"] == theme.COLORS["danger"]
