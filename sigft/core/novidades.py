"""Leitura do `CHANGELOG.md` — fonte única do "o que há de novo".

Duas pontas distantes leem o mesmo bloco, e é isso que justifica o módulo:

* a **tela do app** mostra o bloco da versão instalada, para a pessoa saber o
  que mudou depois de atualizar;
* o **workflow de Release** usa o mesmo bloco como corpo do Release no GitHub.

Escrever as duas à mão é garantir que divirjam no primeiro dia corrido — e a
divergência aparece justamente para o usuário, que lê uma coisa no app e outra
no GitHub. Aqui elas saem do mesmo arquivo.

Formato esperado (o "Keep a Changelog" enxuto):

    ## 1.1.0 - 2026-10-01
    - primeira novidade
    - segunda novidade

    ## 1.0.0 - 2026-09-18
    - ...

Fica em `core/` e não em `services/` porque não há regra de negócio nenhuma:
é análise de texto pura, sem rede, sem Tk e sem Excel. Testável direto.
"""
from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass, field

# "## 1.1.0 - 2026-10-01", "## v1.1.0 - 2026-10-01" ou só "## 1.1.0".
#
# ⚠️ Os três traços de `[—–-]` são CLASSE DE CARACTERES, não pontuação de
# frase. Quem for varrer travessão do projeto não pode tocar aqui: o CHANGELOG
# é escrito à mão e o editor de texto de alguém troca `-` por `–` sozinho. Se
# só o hífen valesse, o bloco inteiro deixaria de ser reconhecido e o Release
# sairia SEM notas — em silêncio, com a tag já criada.
# `tests/test_novidades.py::test_os_tres_tracos_separam_versao_e_data` trava
# os três.
_CABECALHO = re.compile(
    r"^##\s+v?(?P<versao>\d+\.\d+(?:\.\d+)?(?:-[0-9A-Za-z.]+)?)"
    r"\s*(?:[—–-]\s*(?P<data>.+?))?\s*$"
)

# Os três marcadores de lista do Markdown. Idem: o editor troca um pelo outro.
_ITEM = re.compile(r"^\s*[-*+]\s+(?P<texto>.+?)\s*$")


@dataclass(frozen=True)
class Bloco:
    """Uma versão do CHANGELOG: o número, a data e as linhas de novidade."""

    versao: str
    data: str = ""
    itens: list[str] = field(default_factory=list)

    def titulo(self) -> str:
        """`v1.0.0 (2026-09-18)`, ou só `v1.0.0` quando não há data."""
        return f"v{self.versao}" + (f" ({self.data})" if self.data else "")

    def markdown(self) -> str:
        """O bloco de volta em Markdown — é o corpo do Release no GitHub."""
        return "\n".join(f"- {i}" for i in self.itens)


def analisar(texto: str | None) -> list[Bloco]:
    """Todos os blocos, na ordem em que aparecem (o mais novo primeiro).

    O que vier ANTES do primeiro `##` é do arquivo, não de uma versão, e é
    descartado — é onde mora o parágrafo de introdução.
    """
    blocos: list[Bloco] = []
    atual: str | None = None
    data = ""
    itens: list[str] = []

    def fechar() -> None:
        if atual is not None:
            blocos.append(Bloco(versao=atual, data=data, itens=list(itens)))

    for linha in (texto or "").splitlines():
        if (m := _CABECALHO.match(linha)):
            fechar()
            atual, data, itens = m.group("versao"), (m.group("data") or "").strip(), []
            continue
        if atual is not None and (mi := _ITEM.match(linha)):
            itens.append(mi.group("texto"))
    fechar()
    return blocos


def bloco_de(texto: str | None, versao: str) -> Bloco | None:
    """O bloco de uma versão. Compara só os números.

    Ignora o `v` da tag e o sufixo de pré-versão, para que `1.1.0-rc.1` ache
    o bloco da `1.1.0`: o bloco é escrito uma vez, quando a versão é planejada,
    e o candidato a lançamento é a mesma coisa em teste. Exigir bloco próprio
    para cada `-rc.N` faria o pré-lançamento abrir sem novidade nenhuma.
    """
    alvo = str(versao or "").lstrip("vV").split("-")[0]
    for b in analisar(texto):
        if b.versao.split("-")[0] == alvo:
            return b
    return None


def caminho_changelog() -> str:
    """Onde está o `CHANGELOG.md`, dentro do executável ou no projeto.

    No `.exe` ele é embutido na raiz do bundle (ver `SIG-FT.spec`), e lá o
    caminho sai do `sys._MEIPASS`. Em desenvolvimento o arquivo mora na raiz
    do repositório, dois níveis acima deste módulo — daí o segundo candidato.
    """
    candidatos = []

    # Dentro do executável: a raiz do bundle (`sys._MEIPASS`).
    if (bundle := getattr(sys, "_MEIPASS", None)):
        candidatos.append(os.path.join(bundle, "CHANGELOG.md"))

    candidatos.append(os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "CHANGELOG.md",
    ))
    return next((c for c in candidatos if os.path.isfile(c)), candidatos[-1])


def ler(versao: str | None = None) -> Bloco | None:
    """Bloco da `versao` (padrão: a instalada); cai para o mais recente.

    A queda para o mais recente cobre o build de desenvolvimento, cuja versão
    ainda não tem entrada no CHANGELOG — melhor mostrar as últimas novidades
    do que uma tela vazia.
    """
    from sigft import __version__

    try:
        with open(caminho_changelog(), encoding="utf-8") as f:
            texto = f.read()
    except OSError:
        return None

    if (b := bloco_de(texto, versao or __version__)) is not None:
        return b
    blocos = analisar(texto)
    return blocos[0] if blocos else None


def para_mostrar_na_abertura(
    versao_atual: str,
    *,
    empacotado: bool,
    texto: str | None = None,
    config_path=None,
) -> Bloco | None:
    """O bloco que a janela de novidades deve mostrar NESTA abertura, ou `None`.

    Mostra uma vez por versão nova: quando a versão do build é diferente da
    última que esta pessoa já viu (`prefs.get_ultima_versao_vista`). A versão
    atual é gravada como vista ANTES de devolver o bloco -- e também quando a
    decisão é não mostrar --, para não repetir. Não mostra:

    * rodando pelo código-fonte (`empacotado=False`; nem grava);
    * na primeira instalação (não há `user_prefs.json`): só grava. Arquivo
      que existe SEM versão gravada é de quem usava uma versão anterior a
      esta janela -- é atualização, e mostra (decisão do Jonathan, 2026-10-19);
    * sem bloco da versão no CHANGELOG (ou sem CHANGELOG): só grava;
    * com a preferência ilegível, ou sem conseguir gravar -- mostrar sem
      gravar seria mostrar em toda abertura.

    Nunca levanta: a abertura do app não pode depender disto. `texto` é o
    conteúdo do CHANGELOG (o teste o passa); `None` lê o do pacote. Sem a
    queda para o bloco mais recente de `ler()`: aqui, bloco errado é pior
    que nenhum.
    """
    if not empacotado:
        return None
    from sigft.core import prefs

    try:
        situacao, vista = prefs.situacao_versao_vista(config_path=config_path)
    except Exception:  # noqa: BLE001 -- preferência ilegível: não mostra
        return None
    if vista == versao_atual:
        return None
    try:
        prefs.set_ultima_versao_vista(versao_atual, config_path=config_path)
    except Exception:  # noqa: BLE001 -- sem gravar, repetiria toda abertura
        return None
    if situacao in ("sem_arquivo", "ilegivel"):
        return None
    if texto is None:
        try:
            with open(caminho_changelog(), encoding="utf-8") as f:
                texto = f.read()
        except OSError:
            return None
    return bloco_de(texto, versao_atual)
