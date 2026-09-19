"""O que depende do SISTEMA OPERACIONAL, num lugar só — Checkpoint 8.4.

O SIG-FT roda em Windows, e vai continuar rodando: o portal é acessado de
máquinas da empresa, e o tradutor automatiza o Excel de verdade (via COM). Este
módulo **não** existe para tornar o app multiplataforma — existe para que a
dependência do Windows fique **declarada e concentrada**, em vez de espalhada.

A diferença é prática. Antes, `os.startfile` aparecia em 3 lugares, cada um com
o seu `try/except AttributeError` e o seu fallback — e `AttributeError` é uma
forma frágil de detectar o sistema (é o erro que sai porque `os.startfile` só
existe no Windows, não porque alguém decidiu testar isso). Um quarto lugar que
esquecesse o `except` quebraria só na máquina de quem não usa Windows, e só na
hora de clicar no botão.

Concentrar também deixa o custo visível: quem quiser saber "o que prende este
app ao Windows?" lê um arquivo, não faz `grep` no repositório inteiro.

Por que `plataforma.py` e não `platform.py`
-------------------------------------------
`platform` é um módulo da biblioteca padrão. Um arquivo com esse nome dentro do
pacote não quebra o import absoluto (`import platform` continua achando o da
stdlib), mas confunde qualquer leitura — e basta um `from . import platform`
distraído para virar um bug difícil. O plano escreveu "core/platform.py"; o
nome em português evita a colisão e segue a convenção do resto do projeto.
"""
from __future__ import annotations

import os
import subprocess
import sys

# =============================================================================
# Qual sistema
# =============================================================================
EH_WINDOWS = sys.platform.startswith("win")
EH_MAC = sys.platform == "darwin"


def descricao() -> str:
    """Nome legível do sistema, para log e diagnóstico."""
    if EH_WINDOWS:
        return "Windows"
    if EH_MAC:
        return "macOS"
    return sys.platform


# =============================================================================
# Abrir arquivo/pasta no explorador do sistema
# =============================================================================
def abrir_no_sistema(caminho: str | os.PathLike[str]) -> None:
    """Abre `caminho` (arquivo ou pasta) no programa padrão do sistema.

    Substitui as 3 cópias de::

        try: os.startfile(caminho)
        except AttributeError: subprocess.call(['open', caminho])

    Duas melhorias sobre o que havia:

    * decide pelo SISTEMA (`sys.platform`), não pela ausência do atributo.
      `except AttributeError` funcionava, mas capturava pelo sintoma: um
      `AttributeError` vindo de outro lugar seria tratado como "não é
      Windows";
    * Linux entra na conta. As cópias antigas caíam em ``open``, que é
      comando do macOS — no Linux o certo é ``xdg-open``, e o resultado era
      "não acontece nada" sem erro visível.

    Não levanta por caminho inexistente: quem chama decide o que dizer ao
    usuário (as telas mostram "Arquivo não encontrado"). Levanta só se o
    sistema recusar a abertura.
    """
    caminho = str(caminho)

    if EH_WINDOWS:
        # `os.startfile` só existe no Windows -- o `getattr` evita que o
        # analisador estático reclame nas outras plataformas.
        abrir = os.startfile
        abrir(caminho)
        return

    comando = "open" if EH_MAC else "xdg-open"
    subprocess.call([comando, caminho])


def abrir_pasta_criando_se_preciso(pasta: str | os.PathLike[str]) -> None:
    """Abre uma pasta do próprio app, criando-a se ainda não existir.

    O caso é o botão "abrir logs": a pasta só passa a existir depois da
    primeira tarefa de IA, e confrontar o usuário com "pasta não encontrada"
    por algo que é responsabilidade do app criar seria culpá-lo por um estado
    normal.
    """
    os.makedirs(pasta, exist_ok=True)
    abrir_no_sistema(pasta)


# =============================================================================
# Excel de verdade (COM) — o que realmente prende o app ao Windows
# =============================================================================
# `xlwings` automatiza o Excel INSTALADO, pela API COM. Não é uma biblioteca de
# leitura de planilha como o `openpyxl`: ela abre o Excel de verdade.
#
# Isso é usado por UM módulo só, o tradutor (`services/translator.py`), e por um
# motivo que o `openpyxl` não cobre: preservar a formatação e as fórmulas da
# ficha ao criar a aba traduzida.
#
# Requisitos, que são deste caminho e de mais nenhum: Windows **e** Microsoft
# Excel instalado. Nem o Excel Online nem o LibreOffice servem.
def tem_excel_com() -> bool:
    """`True` se dá para automatizar o Excel nesta máquina.

    Verifica as duas condições — sistema e pacote — sem abrir o Excel. Serve
    para a UI avisar ANTES de o usuário selecionar 40 planilhas e clicar em
    processar, em vez de estourar no meio do lote.
    """
    if not EH_WINDOWS:
        return False
    try:
        import xlwings  # noqa: F401  -- só a disponibilidade importa aqui
    except Exception:
        # `Exception` e não `ImportError`: o `xlwings` também estoura na
        # importação quando o Excel não está registrado no COM da máquina.
        return False
    return True


def motivo_sem_excel_com() -> str | None:
    """Explica POR QUE o Excel COM não está disponível, ou `None` se está.

    Mensagem pronta para a UI: "não funciona" sem motivo obriga o usuário a
    adivinhar entre "não tenho Excel" e "o app está quebrado".
    """
    if not EH_WINDOWS:
        return (
            f"O tradutor automatiza o Microsoft Excel instalado, e isso só "
            f"funciona no Windows (este sistema é {descricao()})."
        )
    try:
        import xlwings  # noqa: F401
    except Exception as erro:
        return (
            "Não consegui falar com o Microsoft Excel desta máquina "
            f"({erro}). O tradutor precisa do Excel instalado. O Excel "
            "Online e o LibreOffice não servem."
        )
    return None
