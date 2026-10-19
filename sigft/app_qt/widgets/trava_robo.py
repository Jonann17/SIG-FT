"""Um robô por vez numa seção que junta mais de uma tela (2026-10-19).

A "Aplicação LMR" põe o Upload e a Exclusão em abas da MESMA seção: os dois
robôs trabalham na mesma página do portal e escrevem no mesmo console. Cada
tela já tinha o seu "um robô por vez" (o botão desliga enquanto roda), mas
nada impedia as DUAS de rodarem juntas -- pendência de 2026-10-11. A seção dá
às duas telas a mesma `TravaDeRobo`; tela sozinha (`trava_robo = None`) segue
como sempre.
"""
from __future__ import annotations

import threading


class TravaDeRobo:
    """Quem está rodando agora. `ocupar` e `liberar` podem vir de threads
    diferentes (a interface ocupa, a tarefa libera)."""

    def __init__(self) -> None:
        self._trava = threading.Lock()
        self.dono: str | None = None

    def ocupar(self, dono: str) -> bool:
        if not self._trava.acquire(blocking=False):
            return False
        self.dono = dono
        return True

    def liberar(self) -> None:
        self.dono = None
        if self._trava.locked():
            self._trava.release()


class ComTravaDeRobo:
    """Para a tela (`ModuleFrame`) que roda um robô e pode dividir a seção.
    `NOME_DO_ROBO` é o que a outra tela diz no console."""

    NOME_DO_ROBO = "outro robô"
    trava_robo: TravaDeRobo | None = None

    def robo_ocupado(self) -> bool:
        """Com o robô da OUTRA tela rodando, diz no console e devolve `True`.
        Chamar antes de qualquer pergunta: escolher arquivo para depois ouvir
        "espere" seria pedir o trabalho à toa."""
        trava = self.trava_robo
        if trava is None or trava.dono is None:
            return False
        self.log(f"O robô de {trava.dono} está rodando nesta seção; espere ele terminar "
                 f"(os dois usam a mesma página do portal).")
        return True

    def iniciar_com_trava(self, alvo, *args, botao):
        """`iniciar_tarefa`, segurando a trava da seção do começo ao fim da
        tarefa -- e soltando dê no que der."""
        trava = self.trava_robo
        if trava is not None and not trava.ocupar(self.NOME_DO_ROBO):
            self.robo_ocupado()
            return None

        def com_trava(*a):
            try:
                alvo(*a)
            finally:
                if trava is not None:
                    trava.liberar()

        return self.iniciar_tarefa(com_trava, *args, botao=botao)
