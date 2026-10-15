"""`pausar_e_esperar`, `perguntar_retry_excel` e `perguntar_arquivos_travados` para as telas Qt.

Mesma API e mesma regra da versão interface antiga:
* chamado de um worker: a janela nasce na thread da interface (`na_interface`)
  e o worker espera num `threading.Event`;
* chamado da própria thread da interface: `exec()`, que bloqueia SEM parar o
  laço de eventos -- `Event.wait()` ali congelaria o app.
"""
from __future__ import annotations

import threading
import traceback

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QInputDialog, QMessageBox

from sigft.app.textos_dialogos import MSG_EXCEL_BLOQUEADO, TEXTO_CONTINUAR, msg_excel_bloqueado
from sigft.app_qt import interface
from sigft.app_qt.widgets import dialogos_selecao, dialogs


class DialogosDeEspera:
    def _abrir_e_esperar(self, construir_dialogo) -> dict:
        evento = threading.Event()
        resultado: dict = {}
        if interface.na_thread_da_interface():
            dialogo = construir_dialogo(evento, resultado)
            dialogo.exec()
            return resultado

        def abrir() -> None:
            try:
                dialogo = construir_dialogo(evento, resultado)
                # Fechado, é apagado: sem isto cada caixa de um lote longo
                # (muitas travas de Excel) ficava viva, escondida, como filha
                # da tela. O worker não toca no diálogo depois do `evento`.
                dialogo.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
                self._dialogo_aberto = dialogo  # segura a referência enquanto está aberto
                dialogo.show()
            except Exception:  # noqa: BLE001 -- o worker não pode ficar preso
                # `interface._rodar` engole a exceção; sem o `set()` o worker
                # esperaria para sempre. Resposta segura: login segue, Excel
                # não repete (`resultado` fica sem "retry").
                traceback.print_exc()
                evento.set()

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

    def perguntar_arquivos_travados(self, falhas, momento) -> bool:
        """Arquivos que não puderam ser gravados (`core.excel.travas.Falha`):
        `True` = Repetir, `False` = Seguir. É o `callback_travados(falhas,
        momento)` do Gestão PMIB e do "Aplicar autorizações"; `momento` escolhe
        os textos (`TEXTOS_TRAVADOS`). "X", Esc ou falha ao abrir = Seguir."""
        itens = [(f.nome, f.diagnostico.motivo, f.diagnostico.o_que_fazer) for f in falhas]
        resultado = self._abrir_e_esperar(lambda evento, res: dialogos_selecao.ArquivosTravadosDialog(
            self, itens=itens, momento=momento, evento_espera=evento, resultado=res))
        return bool(resultado.get("repetir", False))

    # -- perguntas e avisos simples ------------------------------------------
    def _na_interface_e_esperar(self, func):
        """Roda `func()` na thread da interface e devolve o resultado.

        Da própria thread da interface, chama direto (os diálogos estáticos do
        Qt já bloqueiam sem parar o laço de eventos).
        """
        if interface.na_thread_da_interface():
            return func()
        evento = threading.Event()
        caixa: dict = {}

        def rodar() -> None:
            try:
                caixa["valor"] = func()
            except Exception:  # noqa: BLE001 -- o worker não pode ficar preso
                traceback.print_exc()
            finally:
                evento.set()

        interface.na_interface(rodar)
        evento.wait()
        return caixa.get("valor")

    def perguntar_sim_nao(self, titulo: str, mensagem: str, *, padrao_sim: bool = False) -> bool:
        """O `askyesno` do Tk. `padrao_sim` escolhe o botão do Enter: lá era o
        "Sim"; aqui o padrão é o "Não", e a tela pede o "Sim" quando recusar sem
        querer custa mais (ex.: perder o relatório da Correção de PDM)."""
        sim, nao = QMessageBox.StandardButton.Yes, QMessageBox.StandardButton.No

        def perguntar():
            return QMessageBox.question(self, titulo, mensagem, sim | nao, sim if padrao_sim else nao) == sim
        return bool(self._na_interface_e_esperar(perguntar))

    def pedir_texto(self, titulo: str, mensagem: str) -> str | None:
        def pedir():
            texto, ok = QInputDialog.getText(self, titulo, mensagem)
            return texto if ok else None
        return self._na_interface_e_esperar(pedir)

    def avisar(self, titulo: str, mensagem: str, tipo: str = "info", *, esperar: bool = False) -> None:
        """Mostra e segue: o worker não espera a pessoa fechar o aviso.

        `esperar=True`: o worker só segue depois do OK -- o `messagebox`
        chamado de dentro do worker na interface antiga, que bloqueava ali (o
        "Preparo" do robô de Criação de Fichas é uma pausa de propósito).
        """
        funcao = {"info": QMessageBox.information, "aviso": QMessageBox.warning,
                  "erro": QMessageBox.critical}[tipo]
        if esperar:
            self._na_interface_e_esperar(lambda: funcao(self, titulo, mensagem))
            return
        if interface.na_thread_da_interface():
            funcao(self, titulo, mensagem)
        else:
            interface.na_interface(funcao, self, titulo, mensagem)
