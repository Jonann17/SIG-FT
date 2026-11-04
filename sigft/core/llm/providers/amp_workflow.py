"""`AmpWorkflowProvider`: o prompt vai ao Workflow AMP do módulo, pelo n8n (2026-11-04).

Cumpre o mesmo contrato dos outros provedores (`generate_raw(...) -> ProviderResult`), e
o transporte é o `core/amp/cliente.ClienteAmp`, o mesmo da Revisão no AMP (uma
implementação só). Contrato com o workflow (formulário): `modo=ia`, `tarefa`, `prompt`,
`system` (quando há) e `json=sim` (quando a tarefa espera JSON); a resposta é
`{"ok": true, "texto": "..."}` (ou `resposta` no lugar de `texto`).

Quem monta é `get_llm`, com `max_retries=0`: cada repetição seria uma execução nova do
agente no AMP. Desenho: `docs/superpowers/specs/2026-11-04-ia-por-modulo-design.md`.
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

    def generate_raw(self, prompt: str, *, system: str | None = None, json_mode: bool = False,
                     anexos: list[Any] | None = None) -> ProviderResult:
        campos = {"modo": "ia", "tarefa": self._tarefa, "prompt": prompt}
        if system:
            campos["system"] = system
        if json_mode:
            campos["json"] = "sim"
        resposta = self._cliente.enviar(campos, {})
        if not resposta.ok:
            raise RuntimeError(f"Workflow AMP ({self._tarefa}): {resposta.erro or 'falhou'}")
        texto = resposta.dados.get("texto") or resposta.dados.get("resposta")
        if not isinstance(texto, str) or not texto.strip():
            raise RuntimeError(f"Workflow AMP ({self._tarefa}): a resposta veio sem o campo \"texto\".")
        return ProviderResult(texto)
