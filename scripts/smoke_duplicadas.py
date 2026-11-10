"""Regressões de duplicadas em Chromium real, com página local sintética.

    python scripts/smoke_duplicadas.py

Não acessa o PMIB nem valida seu DOM atual. Exercita auditoria + escrita nas
quatro sub-abas, persistência ao trocar de aba, mensagens idênticas de duas
imagens e interrupção da fila ao fechar a página. Usa perfil temporário.
SIGFT_PLAYWRIGHT_EXECUTABLE pode apontar para um Chromium já instalado.
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sigft.core.rpa.playwright_engine import PlaywrightEngine  # noqa: E402
from sigft.core.rpa.portal import PMIBPortal  # noqa: E402
from sigft.services import duplicadas_condicoes as cond  # noqa: E402
from sigft.services import duplicadas_robo as robo  # noqa: E402


HTML = """<!doctype html><meta charset="utf-8">
<div id="General"><button onclick="window.salvouErrado=true">SALVAR</button></div>
<div id="demo-Conditions_Header"><button>Condições</button></div>
<div id="demo-Title">
  <div onclick="abrir('Armazenamento')">Condições de armazenamento</div>
  <div>Condições financeiras</div>
  <div onclick="abrir('Transporte')">Transporte</div>
  <div onclick="abrir('Manutenção')">Manutenção</div>
  <div onclick="abrir('Descarte')">Descarte</div>
</div>
<div id="campos"></div>
<button id="imagem" onclick="window.envios++; aviso('A imagem foi adicionada com sucesso!')">Confirmar</button>
<div id="avisos"></div>
<script>
window.salvos = {}; window.envios = 0; window.salvouErrado = false;
const definicoes = {
  'Armazenamento': ['Input_PackingLength', 'RadioButton4-input', 'Checkbox6',
                    'RadioButton8-input', 'RadioButton3-input'],
  'Transporte': ['TextArea_TransportPackagingES', 'TextArea_TransportPackagingPT'],
  'Manutenção': ['TextArea_PreservationCareES', 'TextArea_PreservationCarePT'],
  'Descarte': ['TextArea_TypeLegislationES', 'TextArea_TypeLegislationPT']
};
function aviso(texto) {
  const el = document.createElement('div');
  el.className = 'feedback-message feedback-message-success';
  const mensagem = document.createElement('div');
  mensagem.className = 'feedback-message-text'; mensagem.textContent = texto;
  el.append(mensagem); document.getElementById('avisos').append(el);
  setTimeout(() => el.remove(), 1000);
}
function abrir(nome) {
  document.getElementById('campos').replaceChildren();
  // O clique ativa a aba antes de os campos existirem, como numa SPA.
  setTimeout(() => {
    window.ativa = nome;
    const painel = document.getElementById('campos');
    for (const sufixo of definicoes[nome]) {
      const el = document.createElement('input'); el.id = 'demo-' + sufixo;
      const booleano = sufixo.startsWith('Radio') || sufixo.startsWith('Checkbox');
      el.type = booleano ? 'checkbox' : 'text';
      if (booleano) el.checked = !!(window.salvos[nome] || {})[sufixo];
      else el.value = (window.salvos[nome] || {})[sufixo] || '';
      painel.append(el);
    }
    const salvar = document.createElement('button'); salvar.textContent = 'SALVAR';
    salvar.onclick = () => {
      window.salvos[nome] = Object.fromEntries([...painel.querySelectorAll('input')]
        .map(el => [el.id.slice(5), el.type === 'checkbox' ? el.checked : el.value]));
      aviso('As condições de ' + nome.toLowerCase() + ' foram modificadas com sucesso!');
    };
    painel.append(salvar);
  }, 40);
}
abrir('Armazenamento');
</script>"""


class Auditoria:
    def __init__(self):
        self.fotos = []

    def bloco(self, titulo, _html, **_opcoes):
        self.fotos.append(titulo)


def main():
    with tempfile.TemporaryDirectory(prefix="sigft-smoke-duplicadas-") as perfil:
        engine = PlaywrightEngine.criar(perfil=perfil, headless=True, wait_timeout=2)
        try:
            engine.page.set_content(HTML)
            portal = PMIBPortal(engine)
            auditoria = Auditoria()
            campos = {
                "Armazenamento": {"Input_PackingLength": "40", "RadioButton4-input": True,
                                  "Checkbox6": True, "RadioButton8-input": True,
                                  "RadioButton3-input": True},
                "Transporte": {"TextArea_TransportPackagingES": "Caja",
                               "TextArea_TransportPackagingPT": "Caixa"},
                "Manutenção": {"TextArea_PreservationCareES": "Seco",
                               "TextArea_PreservationCarePT": "Seco"},
                "Descarte": {"TextArea_TypeLegislationES": "Norma",
                             "TextArea_TypeLegislationPT": "Norma"},
            }
            with patch.object(cond, "PAUSA_ABERTURA_SECAO", 0.05), \
                 patch.object(cond, "PAUSA_TROCA_SUBABA", 0.05), \
                 patch.object(cond, "PAUSA_APOS_ESCREVER", 0.01):
                cond.fotografar_edicao(portal, auditoria)
                assert len(auditoria.fotos) == 4
                assert engine.page.evaluate("window.ativa") == "Descarte"
                resultado = cond.escrever(portal, campos, print)
            assert resultado.ok, resultado.detalhe
            assert engine.page.evaluate("window.salvos") == campos
            assert not engine.page.evaluate("window.salvouErrado")
            print("OK: auditoria + quatro sub-abas gravadas e relidas.")

            for _ in range(2):
                assert portal.clicar_e_confirmar("//*[@id='imagem']", "Documentos e imagens")
            assert engine.page.evaluate("window.envios") == 2
            print("OK: duas confirmações consecutivas de imagens com o mesmo texto.")

            engine.page.close()
            fichas = [SimpleNamespace(pmib=str(n), ficha_original="original", descricao="teste")
                      for n in range(3)]
            resultados = robo.processar_lote(fichas, portal=portal, callback_log=print)
            assert len(resultados) == 1 and resultados[0].interrompida
            print("OK: página fechada interrompe a fila sem iniciar as próximas fichas.")
        finally:
            engine.fechar()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
