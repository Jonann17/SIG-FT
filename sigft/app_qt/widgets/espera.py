"""`pausar_e_esperar` e `perguntar_retry_excel` para as telas Qt.

Mesma API e mesma regra da versão CustomTkinter:
* chamado de um worker: a janela nasce na thread da interface (`na_interface`)
  e o worker espera num `threading.Event`;
* chamado da própria thread da interface: `exec()`, que bloqueia SEM parar o
  laço de eventos -- `Event.wait()` ali congelaria o app.
"""
from __future__ import annotations

import threading

from sigft.app.widgets.dialogs import MSG_EXCEL_BLOQUEADO, TEXTO_CONTINUAR, msg_excel_bloqueado
from sigft.app_qt import interface
from sigft.app_qt.widgets import dialogs


class DialogosDeEspera:
    def _abrir_e_esperar(self, construir_dialogo) -> dict:
        evento = threading.Event()
        resultado: dict = {}
        if interface.na_thread_da_interface():
            dialogo = construir_dialogo(evento, resultado)
            dialogo.exec()
            return resultado

        def abrir() -> None:
            dialogo = construir_dialogo(evento, resultado)
            self._dialogo_aberto = dialogo  # segura a referência enquanto está aberto
            dialogo.show()

        interface.na_interface(abrir)
        evento.wait()
        return resultado

    def pausar_e_esperar(self, mensagem: str, texto_botao: str = TEXTO_CONTINUAR) -> None:
        self._abrir_e_esperar(lambda evento, _res: dialogs.PausaLoginDialog(
            self, mensagem=mensagem, evento_espera=evento, texto_botao=texto_botao))

    def perguntar_retry_excel(self, caminho: object = None) -> bool:
        mensagem = msg_excel_bloqueado(caminho) if caminho is not None else MSG_EXCEL_BLOQUEADO
        resultado = self._abrir_e_esperar(lambda evento, res: dialogs.RetryLockDialog(
            self, mensagem=mensagem, evento_espera=evento, resultado=res))
        return bool(resultado.get("retry", False))
