"""Os TEXTOS da atualização automática -- sem biblioteca gráfica.

Saíram da atualização da interface antiga para que a Qt
(`sigft/app_qt/atualizacao.py`) dissesse as mesmas palavras -- o mesmo caminho
de `textos_dialogos.py`. A interface antiga saiu do SIG-FT em 2026-10-15.

Texto de interface é aparência: palavra por palavra como estava. As frases que
antes eram f-strings soltas dentro das funções viraram funções `msg_*` daqui,
para as duas interfaces não divergirem sem ninguém ver.

Só biblioteca padrão (o `updater` entra só na anotação de tipo).
"""
from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from sigft.services.updater import Atualizacao

TITULO = "Atualização do SIG-FT"

MSG_UAC = (
    "O SIG-FT está instalado para todos os usuários, então o Windows vai pedir "
    "permissão de administrador. Se o pedido for recusado, o SIG-FT fecha sem "
    "atualizar: é só abri-lo de novo."
)

MSG_COMO_FUNCIONA = (
    "Ao atualizar, o SIG-FT fecha, instala a versão nova e abre de novo sozinho. "
    "Suas chaves de API e preferências continuam onde estão."
)

# "Atualizar agora" com um robô rodando: o app fecha sozinho quando o download
# termina, e a tarefa morre ali. Mesmo aviso do "X" da janela principal.
MSG_TAREFA_AO_ATUALIZAR = (
    "Há uma tarefa em andamento (um robô, uma tradução ou uma consulta à IA).\n\n"
    "Para instalar a atualização, o SIG-FT fecha sozinho quando o download "
    "termina. A tarefa é interrompida no ponto em que estiver, e uma planilha "
    "que estava sendo gravada pode ficar pela metade.\n\n"
    "Se puder, espere a tarefa terminar e atualize depois.\n\n"
    "Atualizar mesmo assim?"
)

MSG_DOWNLOAD_CONFERIDO = "Download conferido. Abrindo o instalador..."

TEXTO_ATUALIZAR = "Atualizar agora"
TEXTO_ATUALIZANDO = "Atualizando..."
TEXTO_TENTAR_DE_NOVO = "Tentar de novo"
TEXTO_AGORA_NAO = "Agora não"
TEXTO_O_QUE_MUDOU = "O que mudou:"


def notas_para_exibir(notas: str | None) -> str:
    """O Markdown das notas do Release vira texto de leitura.

    As notas vêm do CHANGELOG (via `latest.json`), escritas para o GitHub:
    `**negrito**`, crase e `- ` de lista. Numa caixa de texto do Tk isso
    aparece cru. Aqui cada item vira um parágrafo com marcador, e o rodapé
    "Como instalar" do corpo do Release (que só existe quando o manifesto
    falta) é cortado no `---`: quem está atualizando pelo app não precisa dele.
    """
    paragrafos = []
    for linha in str(notas or "").splitlines():
        texto = linha.strip()
        if texto == "---":
            break
        if not texto:
            continue
        texto = texto.lstrip("#").strip()
        texto = re.sub(r"^[-*+]\s+", "• ", texto)
        texto = texto.replace("**", "").replace("`", "")
        if texto:
            paragrafos.append(texto)
    return "\n\n".join(paragrafos) or "(Esta versão não trouxe notas.)"


def data_br(iso: str) -> str:
    """`2026-09-25` -> `25/09/2026`. Qualquer outra coisa volta como veio."""
    m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", str(iso or "").strip())
    return f"{m.group(3)}/{m.group(2)}/{m.group(1)}" if m else str(iso or "")


def mb(tamanho_mb: float) -> str:
    return f"{tamanho_mb:.1f}".replace(".", ",")


def erro_curto(erro: BaseException, limite: int = 300) -> str:
    """O começo do erro, para caber na janela do aviso.

    O `FalhaDeRede` traz o diagnóstico de cada rota tentada e passa fácil de
    mil caracteres. Na janela o começo basta; o erro inteiro já foi para o
    `sigft.log` por quem o capturou.
    """
    texto = str(erro).strip()
    return texto if len(texto) <= limite else texto[:limite].rstrip() + " (...)"


def resumo_da_versao(info: Atualizacao, versao_atual: str) -> str:
    """A linha de baixo do título: onde a pessoa está e o que vai receber.

    [2026-10-07] Com o instalador pequeno, o tamanho é o DELE, comparado com o
    do completo: é o ganho que a pessoa precisa ver."""
    partes = [f"Você está na v{versao_atual}."]
    detalhe = f"A v{info.versao}"
    if info.publicado_em:
        detalhe += f" saiu em {data_br(info.publicado_em)}"
    if info.incremental and info.tamanho:
        partes.append(detalhe + ".")
        pequeno = f"A atualização tem {mb(info.tamanho_mb)} MB: só o que mudou"
        if info.tamanho_completo:
            pequeno += f" (o instalador completo tem {mb(info.tamanho_completo_mb)} MB)"
        partes.append(pequeno + ".")
        return " ".join(partes)
    if info.tamanho:
        detalhe += f" e tem {mb(info.tamanho_mb)} MB"
    partes.append(detalhe + ".")
    return " ".join(partes)


# ── as frases montadas (eram f-strings dentro de `atualizacao.py`) ──────────

def titulo_do_aviso(info: Atualizacao) -> str:
    """[2026-10-07] Pelo canal de testes chega pré-lançamento: o título diz."""
    titulo = "Nova versão de teste disponível" if info.prerelease else "Nova versão disponível"
    return f"{titulo}: v{info.versao}"


def msg_sem_verificar(versao_atual: str, motivo: str) -> str:
    return f"Você está na v{versao_atual}.\n\n{motivo}"


def msg_em_dia(versao_atual: str) -> str:
    return f"Você já está na versão mais recente (v{versao_atual})."


def msg_erro_ao_procurar(erro: BaseException) -> str:
    return f"Não foi possível procurar atualizações.\n\n{erro}"


def msg_baixando(info: Atualizacao) -> str:
    return f"Baixando a v{info.versao} ({mb(info.tamanho_mb)} MB)..."


def msg_caiu_no_completo(completo: Atualizacao) -> str:
    return (f"A atualização pequena falhou. Baixando o instalador completo "
            f"({mb(completo.tamanho_mb)} MB)...")


def msg_falhou(erro: BaseException) -> str:
    return (f"Não foi possível atualizar: {erro_curto(erro)}\n\nO SIG-FT "
            f"continua nesta versão. Tente de novo; se o erro se repetir, avise "
            f"quem cuida do SIG-FT. O detalhe completo fica no log "
            f"(Documentos\\SIG-FT\\logs\\sigft.log).")
