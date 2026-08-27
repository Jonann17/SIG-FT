r"""
sigft/core/relatorio_lote.py — padrão único de log de lote dos serviços do
SIG-FT (Checkpoint 4.4 do plano de refatoração).

Ver docs/refatoracao/PLANO_REFATORACAO.md, Fase 4 -> CP 4.4 (decisão de
produto nº 4), que define 5 exigências para TODO serviço:

  1. **Início de lote**: o que vai fazer, com quantos itens, com quais
     arquivos/config.
  2. **Por item**: identificador (PMIB/arquivo), etapa, resultado (✅/⚠️/❌
     + motivo), duração quando relevante.
  3. **Avisos** sempre com CAUSA e CONSEQUÊNCIA ("campo X rejeitado pelo
     site → preencher manualmente").
  4. **Resumo final obrigatório**: N sucessos, N falhas (listadas), N
     pulados (com motivo), tempo total.
  5. Espelho opcional em arquivo (`logs/sigft_YYYYMMDD.log`), para auditoria.

Este módulo existe para que esse padrão seja UMA implementação, não 12
cópias — o mesmo princípio nº 1 da arquitetura-alvo ("uma implementação por
conceito") que guiou `headers`/`pmib_codes`/`PMIBPortal`/`LLMClient`. Um
serviço não escreve mais as frases de início/resumo à mão: descreve o que
aconteceu com cada item e o texto sai padronizado.

O diagnóstico do plano (seção 1.5) registra o problema que isto resolve:
"**Logs desiguais entre módulos**: `upload_tech_specs` e `pmib_manager`
logam bem; `autospec`, `pdm` e `apagar_lmr` são lacônicos (sem resumo final,
sem contexto do item, sem duração)".

Escreve através do `log(msg, nivel, contexto)` do CP 1.4
(`core/callbacks.py`) — não inventa canal de saída próprio, então tudo
continua aparecendo no console da UI como hoje.

Só stdlib (`time`, `os`, `datetime`, `contextlib`, `dataclasses`).
"""

from __future__ import annotations

import os
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal, Any, Callable

from sigft.core.callbacks import UICallbacks

# Marcadores de resultado por item — os mesmos do texto do checkpoint.
MARCA_SUCESSO = "✅"
MARCA_AVISO = "⚠️"
MARCA_FALHA = "❌"
MARCA_PULADO = "⏭️"


@dataclass
class _Ocorrencia:
    identificador: str
    motivo: str = ""
    duracao_s: float | None = None


def formatar_duracao(segundos: float | None) -> str:
    """Duração legível: `"1,2s"`, `"3min 04s"`, `"1h 02min"`. `None` -> `""`.

    Evita tanto `0.9999999s` quanto `"734.2s"` — um humano lendo o console
    quer saber se levou meio minuto ou meia hora, não o float cru."""
    if segundos is None:
        return ""
    if segundos < 60:
        return f"{segundos:.1f}s".replace(".", ",")
    minutos, resto = divmod(int(segundos), 60)
    if minutos < 60:
        return f"{minutos}min {resto:02d}s"
    horas, minutos = divmod(minutos, 60)
    return f"{horas}h {minutos:02d}min"


class RelatorioLote:
    """Acompanha um lote e emite início, linha por item e resumo final.

    Uso típico (o `with` GARANTE o resumo, inclusive se o lote estourar por
    exceção — é o que impede o "sumiço" de resumo que o diagnóstico aponta):

        with RelatorioLote(callbacks, titulo="Gerando fichas", total=len(itens),
                           contexto={"template": path}) as lote:
            for item in itens:
                with lote.item(item.pmib) as registro:
                    ...                      # trabalho de verdade
                    registro.aviso("campo X rejeitado pelo site",
                                   "preencher manualmente")
                    # sair sem exceção = sucesso; exceção = falha (registrada
                    # e RE-LEVANTADA? não: engolida e contabilizada -- ver
                    # `item()`)

    Também dá para usar sem os gerenciadores de contexto, chamando
    `sucesso()`/`falha()`/`pulado()` direto — útil em funções cujo laço já
    tem uma estrutura de try/except própria que não vale a pena reescrever.
    """

    def __init__(
        self,
        callbacks: UICallbacks,
        *,
        titulo: str,
        total: int | None = None,
        contexto: dict[str, Any] | None = None,
        time_fn: Callable[[], float] = time.time,
    ) -> None:
        """
        Parâmetros:
          callbacks: `UICallbacks` do CP 1.4 — o `log` é obrigatório; se
            houver `progress`, ele é chamado a cada item concluído.
          titulo: o que o lote vai fazer, em linguagem de usuário
            ("Gerando fichas PMIB", "Traduzindo PT->ES").
          total: quantos itens (quando conhecido de antemão). `None` = lote
            de tamanho desconhecido; o resumo usa o total observado.
          contexto: pares chave/valor com os arquivos/config relevantes,
            exibidos na linha de início (exigência nº 1 do checkpoint).
          time_fn: injetável para teste (nenhum teste depende de tempo real).
        """
        self._callbacks = callbacks
        self._titulo = titulo
        self._total = total
        self._contexto = dict(contexto or {})
        self._time_fn = time_fn

        self._sucessos: list[_Ocorrencia] = []
        self._falhas: list[_Ocorrencia] = []
        self._pulados: list[_Ocorrencia] = []
        self._avisos: list[_Ocorrencia] = []
        self._inicio: float | None = None
        self._resumo_emitido = False

    # ------------------------------------------------------------------
    # Ciclo de vida
    # ------------------------------------------------------------------
    def __enter__(self) -> "RelatorioLote":
        self.iniciar()
        return self

    # `Literal[False]` e nao `bool`: um `__exit__` que pode devolver True
    # ENGOLE a excecao do bloco `with`. Este aqui nunca engole -- ele so
    # garante o resumo final e deixa o erro subir. Declarar `bool` deixava
    # essa promessa implicita.
    def __exit__(self, exc_tipo, exc_valor, _tb) -> Literal[False]:
        # O resumo sai SEMPRE — inclusive quando o lote morre no meio por
        # uma exceção não tratada. Um lote que estoura na ficha 87 de 200 é
        # justamente quando o usuário mais precisa do resumo do que já foi
        # feito. A exceção NÃO é engolida (devolve False).
        if exc_valor is not None:
            self._callbacks.log(
                f"{MARCA_FALHA} Lote interrompido por erro inesperado: {exc_valor}",
                nivel="error",
            )
        self.finalizar()
        return False

    def iniciar(self) -> None:
        """Exigência nº 1 — início de lote."""
        self._inicio = self._time_fn()
        quantidade = f"{self._total} item(ns)" if self._total is not None else "itens"
        self._callbacks.log(f"▶️ {self._titulo} — {quantidade}.", nivel="info")
        for chave, valor in self._contexto.items():
            self._callbacks.log(f"   • {chave}: {valor}", nivel="info")

    def finalizar(self) -> None:
        """Exigência nº 4 — resumo final obrigatório. Idempotente: chamar de
        novo (ex.: `finalizar()` explícito dentro de um `with`) não duplica o
        resumo."""
        if self._resumo_emitido:
            return
        self._resumo_emitido = True
        for linha in self.linhas_resumo():
            self._callbacks.log(linha, nivel="info")

    # ------------------------------------------------------------------
    # Registro por item (exigências nº 2 e nº 3)
    # ------------------------------------------------------------------
    @contextmanager
    def item(self, identificador: Any):
        """Envolve o processamento de UM item: mede a duração, e transforma
        "saiu sem exceção" em sucesso e "estourou" em falha — com o motivo.

        A exceção é ENGOLIDA de propósito: o padrão de lote do SIG-FT é
        "um item ruim não derruba o lote" (é o que todos os serviços já
        faziam à mão, com `try/except` por item). Quem precisar propagar
        deve usar `falha()` direto, sem este gerenciador."""
        identificador = str(identificador)
        comeco = self._time_fn()
        registro = _RegistroItem(self, identificador)
        try:
            yield registro
        except Exception as erro:  # noqa: BLE001 - um item ruim não derruba o lote
            self.falha(identificador, f"{type(erro).__name__}: {erro}",
                       duracao_s=self._time_fn() - comeco)
        else:
            if not registro.finalizado:
                self.sucesso(identificador, duracao_s=self._time_fn() - comeco)

    def sucesso(self, identificador: Any, detalhe: str = "", *, duracao_s: float | None = None) -> None:
        ocorrencia = _Ocorrencia(str(identificador), detalhe, duracao_s)
        self._sucessos.append(ocorrencia)
        self._callbacks.log(self._linha_item(MARCA_SUCESSO, ocorrencia), nivel="info")
        self._avisar_progresso()

    def falha(self, identificador: Any, motivo: str, *, duracao_s: float | None = None) -> None:
        ocorrencia = _Ocorrencia(str(identificador), motivo, duracao_s)
        self._falhas.append(ocorrencia)
        self._callbacks.log(self._linha_item(MARCA_FALHA, ocorrencia), nivel="error")
        self._avisar_progresso()

    def pulado(self, identificador: Any, motivo: str) -> None:
        """Item deliberadamente não processado (já COMPLETO, sem PMIB, fora
        do filtro...). O motivo é OBRIGATÓRIO — "pulado" sem motivo é
        exatamente o log pobre que este checkpoint existe para eliminar."""
        ocorrencia = _Ocorrencia(str(identificador), motivo)
        self._pulados.append(ocorrencia)
        self._callbacks.log(self._linha_item(MARCA_PULADO, ocorrencia), nivel="info")
        self._avisar_progresso()

    def aviso(self, identificador: Any, causa: str, consequencia: str) -> None:
        """Exigência nº 3 — aviso SEMPRE com causa e consequência.

        A assinatura obriga os dois: é impossível registrar um aviso solto
        do tipo "erro no campo X" sem dizer o que isso significa para quem
        está lendo."""
        texto = f"{causa} → {consequencia}"
        self._avisos.append(_Ocorrencia(str(identificador), texto))
        self._callbacks.log(
            self._linha_item(MARCA_AVISO, _Ocorrencia(str(identificador), texto)),
            nivel="warn",
        )

    def etapa(self, identificador: Any, descricao: str) -> None:
        """Progresso DENTRO de um item ("etapa atual", exigência nº 2), para
        fluxos longos (RPA). Não conta para o resumo."""
        self._callbacks.log(f"   [{identificador}] {descricao}", nivel="info")

    # ------------------------------------------------------------------
    # Resumo
    # ------------------------------------------------------------------
    def linhas_resumo(self) -> list[str]:
        """As linhas do resumo final, sem emiti-las — útil para teste e para
        quem quiser devolver o resumo como valor além de logá-lo."""
        decorrido = None if self._inicio is None else self._time_fn() - self._inicio
        total_visto = len(self._sucessos) + len(self._falhas) + len(self._pulados)

        linhas = [
            f"── Resumo: {self._titulo} ──",
            f"{MARCA_SUCESSO} {len(self._sucessos)} sucesso(s)"
            f" · {MARCA_FALHA} {len(self._falhas)} falha(s)"
            f" · {MARCA_PULADO} {len(self._pulados)} pulado(s)"
            + (f" · {MARCA_AVISO} {len(self._avisos)} aviso(s)" if self._avisos else ""),
        ]
        if self._total is not None and total_visto != self._total:
            # Discrepância é informação, não ruído: significa que o lote não
            # chegou ao fim (exceção, parada do usuário) — o resumo diz isso
            # em vez de fingir que processou tudo.
            linhas.append(
                f"   (de {self._total} previsto(s); {self._total - total_visto} não processado(s))"
            )
        if decorrido is not None:
            linhas.append(f"   Tempo total: {formatar_duracao(decorrido)}")

        # Falhas e pulados são LISTADOS (exigência nº 4) — um resumo que só
        # diz "3 falhas" obriga o usuário a rolar o console atrás de quais.
        for rotulo, marca, ocorrencias in (
            ("Falhas", MARCA_FALHA, self._falhas),
            ("Pulados", MARCA_PULADO, self._pulados),
        ):
            if ocorrencias:
                linhas.append(f"   {rotulo}:")
                linhas += [
                    f"     {marca} {o.identificador}" + (f" — {o.motivo}" if o.motivo else "")
                    for o in ocorrencias
                ]
        return linhas

    @property
    def sucessos(self) -> list[str]:
        return [o.identificador for o in self._sucessos]

    @property
    def falhas(self) -> list[str]:
        return [o.identificador for o in self._falhas]

    @property
    def pulados(self) -> list[str]:
        return [o.identificador for o in self._pulados]

    # ------------------------------------------------------------------
    def _linha_item(self, marca: str, ocorrencia: _Ocorrencia) -> str:
        partes = [f"{marca} {ocorrencia.identificador}"]
        if ocorrencia.motivo:
            partes.append(f"— {ocorrencia.motivo}")
        if ocorrencia.duracao_s is not None:
            partes.append(f"({formatar_duracao(ocorrencia.duracao_s)})")
        return " ".join(partes)

    def _avisar_progresso(self) -> None:
        if self._total:
            concluidos = len(self._sucessos) + len(self._falhas) + len(self._pulados)
            # `progress` nunca e None aqui: `UICallbacks.__post_init__`
            # normaliza os callbacks ausentes para no-ops seguros (CP 1.4).
            # O mypy so ve a anotacao `Callable | None` do dataclass.
            self._callbacks.progress(concluidos, self._total)  # type: ignore[misc]


@dataclass
class _RegistroItem:
    """Handle devolvido por `RelatorioLote.item()` — deixa o corpo do laço
    registrar etapa/aviso, ou declarar explicitamente pulado/falha (o que
    suprime o sucesso automático da saída sem exceção)."""

    _lote: RelatorioLote
    _identificador: str
    finalizado: bool = field(default=False)

    def etapa(self, descricao: str) -> None:
        self._lote.etapa(self._identificador, descricao)

    def aviso(self, causa: str, consequencia: str) -> None:
        self._lote.aviso(self._identificador, causa, consequencia)

    def pular(self, motivo: str) -> None:
        self._lote.pulado(self._identificador, motivo)
        self.finalizado = True

    def falhar(self, motivo: str) -> None:
        self._lote.falha(self._identificador, motivo)
        self.finalizado = True


# =============================================================================
# Exigência nº 5 — espelho opcional em arquivo, para auditoria.
# =============================================================================

def caminho_log_do_dia(pasta: str = "logs", agora_fn: Callable[[], datetime] = datetime.now) -> str:
    """`logs/sigft_YYYYMMDD.log` — o nome pedido pelo checkpoint."""
    return os.path.join(pasta, f"sigft_{agora_fn().strftime('%Y%m%d')}.log")


def espelhar_em_arquivo(
    callbacks: UICallbacks,
    *,
    caminho: str | None = None,
    agora_fn: Callable[[], datetime] = datetime.now,
) -> UICallbacks:
    """Devolve um `UICallbacks` que faz TUDO o que o original fazia e ainda
    grava cada mensagem, com carimbo de tempo e nível, em `caminho`.

    Opcional por design (exigência nº 5 diz "espelho OPCIONAL"): quem não
    chamar isto continua com o comportamento de hoje, sem arquivo nenhum.

    Falha ao escrever é ENGOLIDA — mesma disciplina de `core/llm/usage.py`
    (CP 3.4) e da captura de prompts: um recurso de auditoria não pode
    derrubar um lote de 200 fichas por causa de disco cheio ou permissão.
    """
    destino = caminho or caminho_log_do_dia(agora_fn=agora_fn)
    log_original = callbacks.log

    def log_espelhado(msg: Any, nivel: str = "info", contexto: Any | None = None) -> None:
        log_original(msg, nivel, contexto)
        try:
            pasta = os.path.dirname(destino)
            if pasta:
                os.makedirs(pasta, exist_ok=True)
            carimbo = agora_fn().strftime("%Y-%m-%d %H:%M:%S")
            with open(destino, "a", encoding="utf-8") as arquivo:
                arquivo.write(f"[{carimbo}] [{nivel.upper()}] {msg}\n")
        except Exception:  # noqa: BLE001 - auditoria nunca derruba produção
            pass

    return UICallbacks(
        log=log_espelhado,
        pause=callbacks.pause,
        ask=callbacks.ask,
        progress=callbacks.progress,
    )
