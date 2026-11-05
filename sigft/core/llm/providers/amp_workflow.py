"""`AmpWorkflowProvider`: o prompt vai ao Workflow AMP do módulo, pelo n8n (2026-11-04).

Cumpre o mesmo contrato dos outros provedores (`generate_raw(...) -> ProviderResult`), e
o transporte é o `core/amp/cliente.ClienteAmp`, o mesmo da Revisão no AMP (uma
implementação só). Contrato com o workflow (formulário): `modo=ia`, `tarefa`, `prompt`,
`system` (quando há) e `json=sim` (quando a tarefa espera JSON); a resposta é
`{"ok": true, "texto": "..."}` (ou `resposta` no lugar de `texto`).

Quem monta é `get_llm`, com `max_retries=0`: cada repetição seria uma execução nova do
agente no AMP. Desenho: `docs/superpowers/specs/2026-11-04-ia-por-modulo-design.md`.

Os ANEXOS (2026-11-05, para o AutoSpec): o PDF e as páginas em imagem vão como arquivos do
formulário (`anexo_1`, `anexo_2`...), com o campo `arquivos` dizendo quantos. O agente do AMP lê
o arquivo anexado, como na revisão das listas, então `aceita_pdf` é verdadeiro. O workflow tem
de passar os arquivos ao agente e responder `arquivos_recebidos`; sem essa confirmação, ou com
menos arquivos do que foram, a resposta não vale (o agente respondeu sem ver os documentos), e
quem chama decide o que fazer: o AutoSpec refaz a ficha com o texto extraído.
"""
from __future__ import annotations

from typing import Any

from sigft.core.llm.client import ProviderResult

SEM_WEBHOOK = ("O módulo está no Workflow AMP, mas o endereço do webhook não foi configurado. "
               "Abra \"Configurar IA\" no módulo (ou Modelos de IA) e preencha o endereço e a chave.")


class AmpWorkflowProvider:
    def __init__(self, url: str, chave: str, *, tarefa: str, cliente: Any | None = None) -> None:
        if not (url or "").strip() and cliente is None:
            raise ValueError(SEM_WEBHOOK + f" (tarefa {tarefa!r}; Workflow AMP)")
        self._tarefa = tarefa
        if cliente is None:
            from sigft.core.amp.cliente import ClienteAmp  # import local: só com o workflow

            cliente = ClienteAmp(url.strip(), (chave or "").strip())
        self._cliente = cliente

    def aceita_pdf(self) -> bool:
        """O agente do AMP lê o PDF anexado (é o que a revisão das listas faz desde 2026-11-03).
        É o `LLMClient.aceita_pdf` que o AutoSpec pergunta antes de anexar o documento."""
        return True

    def generate_raw(self, prompt: str, *, system: str | None = None, json_mode: bool = False,
                     anexos: list[Any] | None = None) -> ProviderResult:
        campos = {"modo": "ia", "tarefa": self._tarefa, "prompt": prompt}
        if system:
            campos["system"] = system
        if json_mode:
            campos["json"] = "sim"
        arquivos = {f"anexo_{numero}": anexo for numero, anexo in enumerate(anexos or [], start=1)}
        if arquivos:
            campos["arquivos"] = str(len(arquivos))
        resposta = self._cliente.enviar(campos, arquivos)
        if not resposta.ok:
            raise RuntimeError(f"Workflow AMP ({self._tarefa}): {resposta.erro or 'falhou'}")
        if arquivos:
            self._conferir_arquivos(resposta.dados.get("arquivos_recebidos"), len(arquivos))
        texto = resposta.dados.get("texto") or resposta.dados.get("resposta")
        if not isinstance(texto, str) or not texto.strip():
            raise RuntimeError(f"Workflow AMP ({self._tarefa}): a resposta veio sem o campo \"texto\".")
        return ProviderResult(texto)

    def _conferir_arquivos(self, recebidos: Any, enviados: int) -> None:
        """O workflow passou ao agente todos os arquivos? Sem confirmação, não dá para saber."""
        try:
            numero = int(recebidos)
        except (TypeError, ValueError):
            raise RuntimeError(
                f"Workflow AMP ({self._tarefa}): o workflow não confirmou que recebeu os arquivos anexados ({enviados}). "
                "Ele passa os arquivos ao agente? Use o workflow deste módulo, de amp/ia_por_modulo/.") from None
        if numero != enviados:
            raise RuntimeError(f"Workflow AMP ({self._tarefa}): o workflow recebeu {numero} de {enviados} "
                               "arquivo(s) anexado(s); o agente não viu todos os documentos.")
