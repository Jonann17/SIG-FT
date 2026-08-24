r"""
Captura o portal INTEIRO enquanto VOCÊ faz uma ficha à mão.

    python scripts/capturar_portal.py

Por que este script existe, sem rodeio: mapear o portal pelo log de execução do
robô não estava funcionando. Cada rodada trazia um pedaço da tela, eu pedia
outro, e uma cópia de ficha virou uma semana. O log tem teto de 20 000
caracteres (senão o arquivo fica ilegível para quem o manda), fotografa só a
seção que o robô abriu, e nunca vê a tela que o robô ainda não sabe abrir --
que é justamente a que falta mapear.

Aqui a direção se inverte. **Você navega, o script anota.** Ele não automatiza
nada: abre o navegador, você loga, faz a ficha do zero como faria num dia
normal, e a cada tela pressiona Enter no terminal. Cada Enter grava o HTML
COMPLETO da página -- sem corte, sem escopo, sem seleção minha -- em
`capturas/`.

E grava mais uma coisa, que é o motivo de isto valer mais do que um "salvar
como" do navegador: **o rastro dos seus cliques.** Um listener injetado na
página anota, para cada clique, o elemento exato (id, classe, tipo, o texto do
`<label>` ao lado, o valor). Quando você marca "Horizontal" em Posição de
armazenamento, o rastro registra QUAL `input` recebeu o clique. É o mapa
RÓTULO → CAMPO se escrevendo sozinho, em vez de eu deduzi-lo de um dump
estático -- que é onde eu vinha errando.

O que capturar, para fechar o módulo de ficha duplicada de uma vez:

    1. Informações gerais, com o combo de PDM ABERTO e filtrado
    2. Características técnicas
    3. Condições -> Armazenamento   (marque os radios enquanto captura)
    4. Condições -> Transporte
    5. Condições -> Manutenção
    6. Condições -> Descarte
    7. Fabricantes e fornecedores, depois de digitar a referência
    8. Documentos e imagens

Depois:

    python scripts/capturar_portal.py resumir capturas/003-condicoes.html

lista todo campo de formulário da captura com o rótulo ao lado -- serve para
você conferir que a captura pegou o que precisava antes de me mandar.

⚠️ As capturas contêm dados reais de ficha. `capturas/` está no `.gitignore`.
"""
from __future__ import annotations

import datetime
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sigft import config  # noqa: E402


PASTA = "capturas"

# O espião de cliques. Roda dentro da página, e é o que diferencia esta captura
# de um "salvar como": ele liga a AÇÃO (você clicou em Horizontal) ao CAMPO
# (`RadioButton7-input`), que é o casamento que nenhum dump estático entrega.
#
# `capture: true` para pegar o clique antes de a página cancelar a propagação
# -- os widgets do OutSystems fazem isso, e um listener no bubbling perderia
# justamente os cliques que mais interessam.
ESPIAO = r"""
(() => {
  if (window.__sigftEspiao) return;
  window.__sigftEspiao = [];
  const rotuloDe = (el) => {
    // 1) <label for=id>  2) <label> ancestral  3) o <label> irmão seguinte,
    // que é como o OutSystems desenha radio e checkbox.
    if (el.id) {
      const f = document.querySelector(`label[for="${CSS.escape(el.id)}"]`);
      if (f) return f.innerText.trim();
    }
    const pai = el.closest('label');
    if (pai) return pai.innerText.trim();
    const caixa = el.closest('div');
    if (caixa) {
      const irmao = caixa.querySelector('label');
      if (irmao) return irmao.innerText.trim();
    }
    return '';
  };
  const secaoDe = (el) => {
    const painel = el.closest('[id*="_Content"], [role="tabpanel"], fieldset');
    if (!painel) return '';
    const legenda = painel.querySelector('legend, .osui-tabs__header-item');
    return (legenda ? legenda.innerText : (painel.id || '')).trim().slice(0, 80);
  };
  document.addEventListener('click', (ev) => {
    const el = ev.target;
    window.__sigftEspiao.push({
      quando: new Date().toISOString().slice(11, 19),
      tag: el.tagName,
      id: el.id || '',
      classe: (el.className && el.className.baseVal !== undefined
               ? el.className.baseVal : el.className) || '',
      tipo: el.getAttribute('type') || '',
      valor: (el.value !== undefined ? String(el.value) : '').slice(0, 120),
      marcado: el.checked === undefined ? null : el.checked,
      texto: (el.innerText || '').trim().slice(0, 120),
      rotulo: rotuloDe(el),
      secao: secaoDe(el),
    });
  }, true);
})();
"""


def _agora():
    return datetime.datetime.now().strftime("%Y%m%d_%H%M%S")


def _limpar_nome(texto):
    """Nome de arquivo previsível a partir do que a pessoa digitou."""
    texto = re.sub(r"[^\w\s-]", "", texto, flags=re.UNICODE).strip()
    texto = re.sub(r"[\s_]+", "-", texto).lower()
    return texto or "tela"


def _gravar(caminho, conteudo):
    with open(caminho, "w", encoding="utf-8") as arquivo:
        arquivo.write(conteudo)
    return os.path.getsize(caminho)


def capturar():
    """Abre o navegador e grava uma captura a cada Enter no terminal."""
    from sigft.core.rpa.playwright_engine import PlaywrightEngine

    os.makedirs(PASTA, exist_ok=True)
    sessao = _agora()

    print(__doc__.split("O que capturar")[0].strip())
    print("=" * 74)

    engine = PlaywrightEngine.criar(headless=False)
    pagina = engine.page

    # `add_init_script` reinjeta a cada navegação; `evaluate` cobre a página
    # que JÁ está aberta agora. Sem os dois, uma recarga apaga o espião em
    # silêncio e o rastro chega vazio sem ninguém saber por quê.
    pagina.add_init_script(ESPIAO)
    pagina.goto(config.PORTAL_URL)
    pagina.evaluate(ESPIAO)

    print(f"\nNavegador aberto em {config.PORTAL_URL}")
    print("Faça o login e navegue até a primeira tela que quiser capturar.\n")
    print("A cada tela: escreva um nome curto e tecle Enter (ex.: "
          "'condicoes armazenamento').")
    print("Só Enter usa o nome 'tela'.  Escreva 'fim' para encerrar.\n")

    indice = []
    numero = 0
    while True:
        try:
            resposta = input("captura> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if resposta.lower() in {"fim", "sair", "quit", "exit"}:
            break

        numero += 1
        nome = _limpar_nome(resposta)
        base = os.path.join(PASTA, f"{sessao}-{numero:03d}-{nome}")

        try:
            html = pagina.content()
        except Exception as erro:  # noqa: BLE001
            print(f"   [!] Não consegui ler a página: "
                  f"{type(erro).__name__}: {erro}")
            numero -= 1
            continue

        tamanho = _gravar(f"{base}.html", html)

        # O rastro é ZERADO a cada captura: assim cada arquivo carrega os
        # cliques daquela tela, e não a soma de tudo desde o login.
        try:
            rastro = pagina.evaluate(
                "() => { const r = window.__sigftEspiao || []; "
                "window.__sigftEspiao = []; return r; }")
        except Exception:  # noqa: BLE001
            rastro = []
        if rastro:
            _gravar(f"{base}.cliques.json",
                    json.dumps(rastro, ensure_ascii=False, indent=2))

        # A URL some do HTML salvo, e num SPA ela é a única pista de QUAL
        # ficha estava aberta.
        try:
            url = pagina.url
        except Exception:  # noqa: BLE001
            url = ""
        indice.append({"arquivo": f"{os.path.basename(base)}.html",
                       "nome": resposta or "tela", "url": url,
                       "cliques": len(rastro), "bytes": tamanho})

        print(f"   ✓ {os.path.basename(base)}.html  "
              f"({tamanho // 1024} KB, {len(rastro)} clique(s) anotado(s))")

    if indice:
        _gravar(os.path.join(PASTA, f"{sessao}-indice.json"),
                json.dumps(indice, ensure_ascii=False, indent=2))
        print(f"\n{len(indice)} captura(s) em {PASTA}/ (sessão {sessao}).")
        print("Mande a pasta inteira -- html, cliques e índice.")
    else:
        print("\nNenhuma captura gravada.")

    try:
        engine.fechar()
    except Exception:  # noqa: BLE001
        pass


# ===========================================================================
# `resumir` — conferir a captura sem abrir o HTML
# ===========================================================================

def _texto_visivel(fragmento):
    return " ".join(re.sub(r"<[^>]+>", " ", fragmento).split())


def resumir(caminho):
    """Lista todo campo de formulário da captura, com o rótulo ao lado.

    Serve para você conferir, antes de me mandar, que a tela capturada tem os
    campos que interessam -- em vez de descobrirmos juntos, uma rodada depois,
    que ela pegou a tela errada.
    """
    with open(caminho, encoding="utf-8") as arquivo:
        html = arquivo.read()

    print(f"{caminho}  ({len(html) // 1024} KB)\n")

    rotulos = {}
    for achado in re.finditer(r'<label[^>]*for="([^"]+)"[^>]*>(.*?)</label>',
                              html, re.S):
        rotulos[achado.group(1)] = _texto_visivel(achado.group(2))[:60]

    campos = 0
    for achado in re.finditer(r"<(input|textarea|select)\b[^>]*>", html, re.I):
        etiqueta = achado.group(0)
        campos += 1
        identificador = re.search(r'id="([^"]*)"', etiqueta)
        identificador = identificador.group(1) if identificador else ""
        tipo = re.search(r'type="([^"]*)"', etiqueta)
        tipo = tipo.group(1) if tipo else achado.group(1).lower()
        valor = re.search(r'value="([^"]*)"', etiqueta)
        valor = valor.group(1)[:40] if valor else ""

        # O rótulo do OutSystems quase nunca usa `for`: costuma ser o <label>
        # logo DEPOIS do input. Por isso as duas buscas.
        rotulo = rotulos.get(identificador, "")
        if not rotulo:
            seguinte = re.search(r"<label[^>]*>(.*?)</label>",
                                 html[achado.end():achado.end() + 400], re.S)
            if seguinte:
                rotulo = _texto_visivel(seguinte.group(1))[:60]

        marcas = []
        if "checked" in etiqueta:
            marcas.append("MARCADO")
        if "required" in etiqueta:
            marcas.append("OBRIGATÓRIO")
        if "disabled" in etiqueta:
            marcas.append("desabilitado")

        print(f"  {tipo:10s} {identificador or '(sem id)':46s} "
              f"{rotulo or valor:42s} {' '.join(marcas)}")

    print(f"\n{campos} campo(s) de formulário.")

    cliques = caminho.replace(".html", ".cliques.json")
    if os.path.exists(cliques):
        with open(cliques, encoding="utf-8") as arquivo:
            rastro = json.load(arquivo)
        print(f"\nRastro de cliques ({len(rastro)}):")
        for evento in rastro:
            alvo = evento["id"] or evento["classe"][:40] or evento["tag"]
            rotulo = evento["rotulo"] or evento["texto"]
            print(f"  {evento['quando']}  {alvo:46s} {rotulo[:50]}")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "resumir":
        if len(sys.argv) < 3:
            print("uso: python scripts/capturar_portal.py resumir <arquivo.html>")
            raise SystemExit(2)
        resumir(sys.argv[2])
    else:
        capturar()
