"""O "abrir a pasta de logs" da interface, num lugar só (2026-10-21).

Usado pelo "Abrir pasta de logs" dos Gastos de IA (`views/home.py`) e pelo
"Abrir logs" do Ctrl+K (`main.SIG_FT_App.abrir_pasta_de_logs`).
"""
from __future__ import annotations

from PySide6.QtWidgets import QMessageBox

from sigft.core import plataforma


def abrir(pai=None) -> None:
    """Abre `Documentos\\SIG-FT\\logs\\` no explorador, criando-a se ainda não
    existir (nenhuma tarefa rodou ainda). Falhou: caixa de erro sobre `pai`, que
    pode ser o widget ou uma função que o devolve (chamada só no erro)."""
    from sigft.core.dados_usuario import pasta_logs

    try:
        plataforma.abrir_pasta_criando_se_preciso(str(pasta_logs()))
    except Exception as erro:  # noqa: BLE001 -- vira aviso
        janela = pai() if callable(pai) else pai
        QMessageBox.critical(janela, "Erro", f"Não foi possível abrir a pasta de logs: {erro}")
