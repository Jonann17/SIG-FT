"""Achar o navegador do RPA — o que o `SIG-FT Itaipu.bat` fazia e o app não.

O buraco que este módulo fecha
------------------------------
O SIG-FT **não empacota o Chromium**, e isso é decisão, não esquecimento: um
navegador embutido congela na versão do dia do build e fica fora do que a TI
atualiza — é a objeção mais forte numa revisão de segurança corporativa, e ela
é justa (ver `docs/SEGURANCA_TI.md`). Em vez disso o RPA usa o Chrome ou o Edge
que a própria empresa já instala e mantém.

Só que **quem achava esse navegador era o `SIG-FT Itaipu.bat`**: ele sondava os
caminhos e definia `SIGFT_PLAYWRIGHT_EXECUTABLE`. O `playwright_engine.py`
apenas LÊ a variável (`os.environ.get`).

Com o instalador do Inno Setup, o `.bat` deixa de existir na máquina do
usuário. Ninguém define a variável, e o RPA fica sem navegador — **em toda
máquina**. E o sintoma é dos piores: o app abre normalmente, todas as telas
funcionam, e a falha só aparece quando a pessoa aciona um módulo de portal, no
meio do trabalho.

Por isso a sondagem muda de casa: sai do `.bat` e entra aqui, onde há teste.

O que veio do Corella Suite
---------------------------
`apontar_navegador_empacotado()` é a via para um build que LEVE o navegador
(uma pasta `ms-playwright/` ao lado do `.exe`). Hoje o SIG-FT não leva, então
ela não faz nada — mas fica pronta, e é a rede de segurança para a máquina onde
não há Chrome nem Edge.

As três regras dela vieram do dossiê do Corella e cada uma tem um motivo:

* **`setdefault`, nunca atribuição** — quem já definiu
  `PLAYWRIGHT_BROWSERS_PATH` (porque tem navegador próprio, ou porque a TI
  padronizou um caminho) continua mandando;
* **caminho a partir de `sys.executable`**, não de `sys._MEIPASS` nem relativo
  ao diretório de trabalho — a pessoa pode abrir o `.exe` de qualquer lugar;
* **nada aqui pode levantar** — isto roda no bootstrap, e uma exceção impediria
  o app de abrir. A ausência do navegador já tem tratamento visível quando o
  RPA é acionado.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# A variável que o `playwright_engine` lê. Continua sendo a fonte da verdade:
# este módulo a PREENCHE quando ela está vazia, em vez de criar um segundo
# caminho de configuração.
ENV_EXECUTAVEL = "SIGFT_PLAYWRIGHT_EXECUTABLE"

# A pasta de navegadores que o Playwright consulta.
ENV_PASTA_NAVEGADORES = "PLAYWRIGHT_BROWSERS_PATH"

# O processo Node do Playwright ignora `REQUESTS_CA_BUNDLE` e `SSL_CERT_FILE`;
# esta é a única que ele respeita.
ENV_CERT_NODE = "NODE_EXTRA_CA_CERTS"


def candidatos_do_windows(
    *,
    programas: str | None = None,
    programas_x86: str | None = None,
    local: str | None = None,
) -> list[str]:
    """Onde procurar, na ordem — a MESMA do `SIG-FT Itaipu.bat`.

    O Chrome vem antes do Edge porque é o mais exercitado contra o portal
    PMIB; trocar a preferência aqui seria mudança de comportamento disfarçada
    de mudança de lugar.

    Separada de `_candidatos()` de propósito: **a lista é dado, a checagem do
    sistema é política.** Assim o teste que confere esta lista contra o
    `SIG-FT Itaipu.bat` roda em qualquer sistema — inclusive no CI, que é
    Linux. Se ela só existisse dentro do `if os.name == "nt"`, o guard mais
    importante desta frente nunca rodaria onde ele é verificado.
    """
    # As três raízes são parâmetros para o teste poder passar marcadores e
    # comparar ESTA lista com a do `SIG-FT Itaipu.bat` caminho a caminho. Sem
    # isso, as três entradas do Chrome viram a mesma coisa quando a raiz é
    # apagada — e o guard daria verde por acidente, achando que cobriu o que
    # não cobriu. Foi o que aconteceu na primeira versão dele.
    programas = programas if programas is not None else os.environ.get(
        "ProgramFiles", r"C:\Program Files")
    programas_x86 = programas_x86 if programas_x86 is not None else os.environ.get(
        "ProgramFiles(x86)", r"C:\Program Files (x86)")
    local = local if local is not None else os.environ.get("LOCALAPPDATA", "")

    return [
        os.path.join(programas, "Google", "Chrome", "Application", "chrome.exe"),
        os.path.join(programas_x86, "Google", "Chrome", "Application", "chrome.exe"),
        os.path.join(local, "Google", "Chrome", "Application", "chrome.exe"),
        os.path.join(programas_x86, "Microsoft", "Edge", "Application", "msedge.exe"),
        os.path.join(programas, "Microsoft", "Edge", "Application", "msedge.exe"),
    ]


def _candidatos() -> list[str]:
    """A lista, ou vazia fora do Windows.

    Em desenvolvimento no Linux/macOS não há o que sondar, e o RPA do portal
    não roda mesmo.
    """
    return candidatos_do_windows() if os.name == "nt" else []


def encontrar_navegador() -> str | None:
    """O Chrome/Edge a usar, ou `None` quando não há nenhum.

    A escolha explícita da pessoa (`SIGFT_PLAYWRIGHT_EXECUTABLE`) ganha de
    qualquer sondagem — é o que o README documenta para quem tem o navegador
    fora do padrão. Mas só quando o caminho **existe**: um valor apontando para
    arquivo que não está lá é erro de digitação, não escolha, e respeitá-lo
    faria o Playwright estourar com "executable doesn't exist" tendo um Chrome
    instalado ali do lado.

    `None` não é falha: o app abre igual, e só o robô do portal reclama quando
    for acionado. As telas de planilha e de IA não dependem disto.
    """
    if (escolhido := os.environ.get(ENV_EXECUTAVEL, "").strip()):
        if os.path.isfile(escolhido):
            return escolhido

    for candidato in _candidatos():
        if candidato and os.path.isfile(candidato):
            return candidato
    return None


def _pasta_do_programa() -> Path:
    """Onde o `.exe` está (ou a raiz do repositório, rodando do `.py`)."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent.parent.parent


def apontar_navegador_empacotado(
    pasta_do_programa: str | os.PathLike[str] | None = None,
) -> None:
    """Aponta o Playwright para um `ms-playwright/` ao lado do `.exe`, se houver.

    Hoje o SIG-FT não empacota o navegador, então a pasta não existe e esta
    função não faz nada — é o caminho normal. Ela existe para o dia em que um
    build precise levá-lo (máquina sem Chrome nem Edge), e para que esse dia
    não exija descobrir de novo as três regras do docstring do módulo.

    Nunca levanta: roda no bootstrap.
    """
    try:
        if os.environ.get(ENV_PASTA_NAVEGADORES):
            return  # quem já definiu manda
        raiz = Path(pasta_do_programa) if pasta_do_programa else _pasta_do_programa()
        pasta = raiz / "ms-playwright"
        if pasta.is_dir() and any(pasta.glob("chromium-*")):
            os.environ.setdefault(ENV_PASTA_NAVEGADORES, str(pasta))
    except Exception:  # noqa: BLE001 — ver o docstring do módulo
        pass


def propagar_certificado_para_o_node() -> None:
    """`SSL_CERT_FILE` -> `NODE_EXTRA_CA_CERTS`, para o Playwright.

    Era o que o `SIG-FT Itaipu.bat` fazia nas duas últimas linhas, e também se
    perderia com o instalador. O processo Node do Playwright não olha as
    variáveis de certificado do Python; numa rede com Zscaler, sem esta ponte,
    ele falha no download do navegador com erro de certificado.

    Não sobrescreve quem já definiu. Nunca levanta.
    """
    try:
        if os.environ.get(ENV_CERT_NODE):
            return
        if (cert := os.environ.get("SSL_CERT_FILE", "").strip()):
            os.environ[ENV_CERT_NODE] = cert
    except Exception:  # noqa: BLE001
        pass


def preparar_ambiente_do_rpa() -> str | None:
    """Tudo o que o `.bat` fazia, numa chamada. Devolve o navegador achado.

    Chamada na abertura do app. Nunca levanta, e `None` é resultado válido:
    significa "sem navegador nesta máquina", e o app abre do mesmo jeito.
    """
    try:
        apontar_navegador_empacotado()
        propagar_certificado_para_o_node()
        if (achado := encontrar_navegador()):
            os.environ[ENV_EXECUTAVEL] = achado
        return achado
    except Exception:  # noqa: BLE001 — ver o docstring do módulo
        return None
