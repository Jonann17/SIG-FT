"""O canal `retry_lock` e a gravação que pergunta — CP C e CP D.

Ver `docs/superpowers/specs/2026-08-28-padronizacao-dialogos-design.md`.

O requisito do usuário: *"sempre que formos salvar em um excel devemos usar o
mesmo método, ou seja, se não deu de salvar aparece a janela instruindo a
fechar e tentar o salvamento de novo para todos módulos"*.

Antes deste trabalho, 7 pontos de gravação em 5 serviços chamavam
`wb.save(path)` direto: com a planilha aberta no Excel, o `PermissionError`
subia sem que nada fosse perguntado, e o lote morria sem dizer o motivo.

O que os testes daqui provam:

* o canal ausente NÃO muda o comportamento de ninguém (é o que torna seguro
  aplicar isto em massa);
* o canal presente é consultado, recebe o caminho e manda retentar;
* nenhum serviço voltou a chamar `wb.save()` cru.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from sigft.core.callbacks import UICallbacks
from sigft.core.excel import locking


class WorkbookTravado:
    """Falha com `PermissionError` nas `falhas` primeiras tentativas."""

    def __init__(self, falhas: int):
        self.falhas = falhas
        self.tentativas = 0
        self.salvo_em = None

    def save(self, caminho):
        self.tentativas += 1
        if self.tentativas <= self.falhas:
            raise PermissionError(13, "arquivo aberto em outro programa", caminho)
        self.salvo_em = caminho


# =============================================================================
# A. UICallbacks.retry_lock — o canal do CP C
# =============================================================================

def test_sem_provedor_o_canal_devolve_false():
    """O default TEM de ser False: é o comportamento de hoje nos 7 pontos que
    falhavam de imediato. Ganhar o canal não pode mudar nada para quem não o
    fornece."""
    callbacks = UICallbacks(log=lambda *a, **k: None)

    assert callbacks.retry_lock("/qualquer/caminho.xlsx") is False


def test_o_canal_nunca_fica_None_depois_de_construido():
    """Os outros 4 canais têm essa garantia; o quinto não podia ser exceção,
    ou o serviço voltaria a precisar de `if callbacks.retry_lock:`."""
    callbacks = UICallbacks(log=lambda *a, **k: None)

    assert callbacks.retry_lock is not None
    assert callable(callbacks.retry_lock)


def test_com_provedor_o_canal_recebe_o_caminho():
    recebidos = []
    callbacks = UICallbacks(
        log=lambda *a, **k: None,
        retry_lock=lambda caminho: recebidos.append(caminho) or True,
    )

    assert callbacks.retry_lock("/fichas/4500063671.0929.xlsx") is True
    assert recebidos == ["/fichas/4500063671.0929.xlsx"]


def test_os_outros_quatro_canais_continuam_funcionando():
    """Guarda contra regressão no protocolo do CP 1.4."""
    callbacks = UICallbacks(log=lambda *a, **k: None)

    assert callbacks.ask("algo?") is False
    assert callbacks.pause("motivo") is None
    assert callbacks.progress(1, 2) is None


# =============================================================================
# B. locking.salvar_perguntando — o helper do CP D
# =============================================================================

def test_sem_canal_o_permission_error_sobe_como_antes():
    """O comportamento histórico dos 7 pontos, preservado."""
    wb = WorkbookTravado(falhas=1)

    with pytest.raises(PermissionError):
        locking.salvar_perguntando(wb, "/x/ficha.xlsx")

    assert wb.tentativas == 1, "não podia ter retentado sem alguém autorizar"


def test_com_canal_dizendo_sim_retenta_e_salva():
    """O usuário fecha o Excel e clica em «Tentar Novamente»."""
    wb = WorkbookTravado(falhas=2)

    ok = locking.salvar_perguntando(wb, "/x/ficha.xlsx", retry_lock=lambda _c: True)

    assert ok is True
    assert wb.tentativas == 3
    assert wb.salvo_em == "/x/ficha.xlsx"


def test_com_canal_dizendo_nao_desiste_na_primeira():
    """«Ignorar e Continuar»."""
    wb = WorkbookTravado(falhas=5)

    with pytest.raises(PermissionError):
        locking.salvar_perguntando(wb, "/x/ficha.xlsx", retry_lock=lambda _c: False)

    assert wb.tentativas == 1


def test_o_canal_recebe_o_caminho_para_a_janela_poder_nomear_o_arquivo():
    """A janela diz «feche o arquivo X» — sem o caminho, ela diria «o
    arquivo», o que não ajuda quem tem vários abertos."""
    recebidos = []
    wb = WorkbookTravado(falhas=1)

    locking.salvar_perguntando(
        wb,
        r"C:\fichas\4500063671.0929.xlsx",
        retry_lock=lambda caminho: recebidos.append(caminho) or True,
    )

    assert recebidos == [r"C:\fichas\4500063671.0929.xlsx"]


def test_salvamento_que_da_certo_de_primeira_nao_pergunta_nada():
    perguntou = []
    wb = WorkbookTravado(falhas=0)

    locking.salvar_perguntando(
        wb, "/x/ok.xlsx", retry_lock=lambda c: perguntou.append(c) or True
    )

    assert perguntou == []
    assert wb.salvo_em == "/x/ok.xlsx"


def test_funciona_com_adaptador_duck_typed():
    """O `translator` salva por xlwings (`wb.save()` sem caminho) e o
    `upload_conditions` por pandas — os dois adaptam com um SimpleNamespace."""
    gravou = []
    adaptador = SimpleNamespace(save=lambda _caminho: gravou.append("salvou"))

    ok = locking.salvar_perguntando(adaptador, "/x/planilha.xlsx")

    assert ok is True
    assert gravou == ["salvou"]


# =============================================================================
# C. O fluxo completo: serviço pergunta -> UI responde
# =============================================================================

def test_fluxo_completo_da_ui_ate_o_disco():
    """Como fica em produção: a tela liga `retry_lock` ao seu diálogo, o
    serviço chama `salvar_perguntando`, e o usuário decide."""
    cliques = iter([True])  # o usuário fecha o Excel e manda tentar de novo
    callbacks = UICallbacks(
        log=lambda *a, **k: None,
        retry_lock=lambda _caminho: next(cliques),
    )
    wb = WorkbookTravado(falhas=1)

    ok = locking.salvar_perguntando(
        wb, "/x/ficha.xlsx", retry_lock=callbacks.retry_lock
    )

    assert ok is True
    assert wb.tentativas == 2


def test_fluxo_completo_com_o_usuario_desistindo():
    callbacks = UICallbacks(log=lambda *a, **k: None, retry_lock=lambda _c: False)
    wb = WorkbookTravado(falhas=99)

    with pytest.raises(PermissionError):
        locking.salvar_perguntando(wb, "/x/ficha.xlsx", retry_lock=callbacks.retry_lock)


# =============================================================================
# D. Guarda: nenhum serviço voltou a salvar cru
# =============================================================================

def test_nenhum_servico_chama_wb_save_direto():
    """O requisito do usuário é «para todos os módulos». Um `wb.save()` novo
    escaparia da janela em silêncio — e só apareceria quando alguém estivesse
    com a planilha aberta, no meio de um lote."""
    import ast
    import pathlib

    dir_servicos = pathlib.Path(__file__).resolve().parent.parent / "sigft" / "services"
    infratores = []

    for arquivo in sorted(dir_servicos.glob("*.py")):
        arvore = ast.parse(arquivo.read_text(encoding="utf-8"))
        for no in ast.walk(arvore):
            if not (isinstance(no, ast.Call) and isinstance(no.func, ast.Attribute)):
                continue
            if no.func.attr != "save":
                continue
            # `wb.save()` sem argumento dentro de um adaptador é o caso do
            # xlwings (translator) — ele JÁ está sob salvar_perguntando.
            if not no.args:
                continue
            infratores.append(f"{arquivo.name}:{no.lineno} -> {ast.unparse(no)[:60]}")

    assert not infratores, (
        "gravação de Excel fora de save_with_retry/salvar_perguntando:\n"
        + "\n".join(infratores)
    )


def test_os_cinco_servicos_do_cp_d_importam_o_locking():
    """Sentinela: se alguém remover o import, o teste acima ainda passaria
    (não há mais `wb.save(path)`), mas a gravação teria sumido junto."""
    import pathlib

    dir_servicos = pathlib.Path(__file__).resolve().parent.parent / "sigft" / "services"
    for nome in ("analyzer", "analyzer_relatorio", "autospec", "pdm", "translator"):
        fonte = (dir_servicos / f"{nome}.py").read_text(encoding="utf-8")
        assert "salvar_perguntando" in fonte, f"{nome} deixou de gravar com retry"
