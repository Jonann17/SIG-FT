"""Os diálogos de espera nas telas Qt: o que a interface antiga provava e a
porta Qt tem de manter (portado de `tests/test_app_dialogos_da_tela.py`, que
saiu com a interface antiga em 2026-10-15).

O contrato com a thread do robô (agendar na thread da interface, bloquear o
worker até a decisão, o "X" soltar) está em `tests/test_qt_espera.py` e
`tests/test_qt_dialogos_selecao.py`. Aqui ficam as duas coisas que só a
antiga provava:

1. a mensagem do Excel travado: sem caminho, a histórica do `_STATUS_PMIB`;
   com caminho, o NOME do arquivo (não o caminho inteiro) e o que fazer;
2. a guarda estrutural: toda tela que chama um método de espera
   (`self.pausar_e_esperar`, `self.perguntar_retry_excel`...) herda de quem o
   fornece. O erro real que a originou (CP B, 2026-08): as chamadas foram
   escritas em 3 telas e só UMA herdava o mixin -- as outras teriam estourado
   `AttributeError` na frente do usuário, no meio de um lote, com o navegador
   já aberto. `compileall` não pega (é atributo), `pyflakes` não pega (é
   `self.`), e uma tela que nenhum teste instancia também não.
"""
from __future__ import annotations

import ast
import pathlib
import threading

from PySide6.QtWidgets import QApplication, QWidget

from sigft.app.textos_dialogos import MSG_EXCEL_BLOQUEADO, msg_excel_bloqueado
from sigft.app_qt.widgets import dialogs as qd
from sigft.app_qt.widgets.espera import DialogosDeEspera

RAIZ = pathlib.Path(__file__).resolve().parent.parent
DIR_VIEWS = RAIZ / "sigft" / "app_qt" / "views"


class Tela(DialogosDeEspera, QWidget):
    pass


def _retry_aberto(qtbot):
    def _abertos():
        return [w for w in QApplication.topLevelWidgets()
                if isinstance(w, qd.RetryLockDialog) and w.isVisible()]

    qtbot.waitUntil(lambda: len(_abertos()) == 1, timeout=2000)
    return _abertos()[0]


def _perguntar_em_thread(tela, **kwargs):
    respostas = []
    t = threading.Thread(target=lambda: respostas.append(tela.perguntar_retry_excel(**kwargs)),
                         daemon=True)
    t.start()
    return t, respostas


# =============================================================================
# 1. A mensagem do Excel travado
# =============================================================================

def test_sem_caminho_usa_a_mensagem_historica_do_status_pmib(qt_interface, qtbot):
    tela = Tela()
    qtbot.addWidget(tela)
    t, respostas = _perguntar_em_thread(tela)

    dialogo = _retry_aberto(qtbot)
    assert dialogo.rotulo.text() == MSG_EXCEL_BLOQUEADO

    dialogo.cancelar()
    t.join(3)
    assert respostas == [False]


def test_com_caminho_a_mensagem_NOMEIA_o_arquivo_travado(qt_interface, qtbot):
    """A janela serve pdm/analyzer/autospec/tradutor: dizer «o _STATUS_PMIB»
    seria mentira na maioria dos casos."""
    tela = Tela()
    qtbot.addWidget(tela)
    t, _ = _perguntar_em_thread(tela, caminho=r"C:\fichas\4500063671.0929.xlsx")

    dialogo = _retry_aberto(qtbot)
    texto = dialogo.rotulo.text()
    assert "4500063671.0929.xlsx" in texto
    assert "FECHE O ARQUIVO" in texto

    dialogo.cancelar()
    t.join(3)


def test_mensagem_com_caminho_mostra_so_o_nome_do_arquivo():
    """Caminho inteiro numa janela de 450 px quebraria o texto."""
    msg = msg_excel_bloqueado(r"C:\Users\alguem\Box\muito\fundo\ficha.xlsx")

    assert "ficha.xlsx" in msg
    assert "C:\\Users" not in msg


# =============================================================================
# 2. Guarda: quem CHAMA os métodos de espera precisa TER os métodos
# =============================================================================
METODOS_DO_MIXIN = {
    nome for nome, valor in vars(DialogosDeEspera).items()
    if callable(valor) and not nome.startswith("__")
}
BASES_QUE_FORNECEM = {"DialogosDeEspera", "ModuleFrame"}


def _classes_das_views():
    for arquivo in sorted(DIR_VIEWS.glob("*.py")):
        if arquivo.name == "__init__.py":
            continue
        arvore = ast.parse(arquivo.read_text(encoding="utf-8"))
        for no in ast.walk(arvore):
            if isinstance(no, ast.ClassDef):
                yield arquivo.name, no


def _metodos_do_mixin_referenciados(classe):
    """Toda referência a `self.<metodo do mixin>`, chamada OU não.

    A distinção importa e já falhou uma vez: ligar um canal é
    `retry_lock=self.perguntar_retry_excel` -- uma REFERÊNCIA ao método, sem
    parênteses. Um `ast.Attribute` cobre os dois casos, porque toda chamada
    contém um.
    """
    return {sub.attr for sub in ast.walk(classe)
            if isinstance(sub, ast.Attribute) and isinstance(sub.value, ast.Name)
            and sub.value.id == "self" and sub.attr in METODOS_DO_MIXIN}


def _bases(classe):
    return {ast.unparse(b).split(".")[-1] for b in classe.bases}


def _fornecedoras():
    """As bases que fornecem o mixin, mais as classes das views que herdam de
    uma delas (o `TelaDeUpload` das duas telas de upload, por exemplo)."""
    fornecem = set(BASES_QUE_FORNECEM)
    classes = [c for _, c in _classes_das_views()]
    mudou = True
    while mudou:
        mudou = False
        for classe in classes:
            if classe.name not in fornecem and _bases(classe) & fornecem:
                fornecem.add(classe.name)
                mudou = True
    return fornecem


def test_o_mixin_tem_os_metodos_que_a_guarda_procura():
    assert {"pausar_e_esperar", "perguntar_retry_excel", "_abrir_e_esperar",
            "avisar", "pedir_texto", "perguntar_sim_nao"} <= METODOS_DO_MIXIN


def test_toda_tela_que_chama_o_mixin_realmente_herda_dele():
    fornecem = _fornecedoras()
    faltando = [f"{arquivo}:{classe.name} usa {sorted(_metodos_do_mixin_referenciados(classe))}"
                for arquivo, classe in _classes_das_views()
                if _metodos_do_mixin_referenciados(classe) and not _bases(classe) & fornecem]
    assert not faltando, faltando


def test_a_guarda_acima_esta_de_fato_examinando_telas():
    com_mixin = [c.name for _, c in _classes_das_views() if _metodos_do_mixin_referenciados(c)]
    assert len(com_mixin) >= 5, com_mixin
