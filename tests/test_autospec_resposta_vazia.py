"""AutoSpec: resposta vazia não é "preenchida por dedução" (2026-11-06).

Rodada da 1.4.0-rc.5 pelo Workflow AMP: o agente devolve `{"valor": "", "tipo": "deducao",
"justificativa": "O documento não traz sinal de saída."}` para o campo que o documento não
responde, e o console dizia "4 campo(s) preenchidos por DEDUCAO TECNICA" listando quatro campos
VAZIOS. A ficha já saía certa (`fill_save` não grava valor vazio); o console é que contava errado.
"""
from __future__ import annotations

from sigft.services import autospec_evidencia as ev
from sigft.services.autospec import AutoSpecCore

PERGUNTA = "3 - SINAL DE SAIDA (Indicar o sinal de saída do item em (mV, V, A, mA) ex.: 4-20mA, 0-5 V, outros)"


def test_resposta_vazia_nao_entra_na_lista_de_deducoes():
    core = AutoSpecCore.__new__(AutoSpecCore)
    core._modelo_do_item = "750-362"
    core.ultimas_evidencias_por_campo = {"var_row_81": ev.Evidencia(
        tipo="deducao", fonte="", justificativa="O documento não traz sinal de saída.")}
    linhas = []

    class _Cb:
        def log(self, msg, nivel="info", contexto=None):
            linhas.append(str(msg))

    aprovados = core._filtrar_por_lastro(
        {"var_row_81": ""}, {"var_row_81": {"desc": PERGUNTA}}, "documento qualquer", _Cb())
    assert not aprovados.get("var_row_81")
    assert not any("DEDUCAO TECNICA" in linha for linha in linhas)
    assert "var_row_81" not in core.notas_por_campo
