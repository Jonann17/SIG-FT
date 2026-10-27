"""Os TEXTOS da atualização automática -- sem biblioteca gráfica.

Saíram da atualização da interface antiga para que a Qt
(`sigft/app_qt/atualizacao.py`) dissesse as mesmas palavras -- o mesmo caminho
de `textos_dialogos.py`. A interface antiga saiu do SIG-FT em 2026-10-15.

Texto de interface é aparência: palavra por palavra como estava. As frases que
antes eram f-strings soltas dentro das funções viraram funções `msg_*` daqui,
para as duas interfaces não divergirem sem ninguém ver.

Só biblioteca padrão (o `updater` entra só na anotação de tipo) e o `idioma`
(2026-10-22): constante em `marcar`, traduzida onde aparece; as frases `msg_*`
já saem no idioma da sessão. As notas do CHANGELOG ficam como vieram.
"""
from __future__ import annotations

import re
from typing import TYPE_CHECKING

from sigft.app.idioma import marcar, t

if TYPE_CHECKING:  # pragma: no cover
    from sigft.services.updater import Atualizacao

TITULO = marcar("Atualização do SIG-FT")

MSG_UAC = marcar(
    "O SIG-FT está instalado para todos os usuários. Esta atualização o passa "
    "para a instalação só sua: o Windows vai pedir a senha de administrador uma "
    "vez, para remover a cópia antiga. Se o pedido for recusado, a versão nova "
    "funciona do mesmo jeito."
)

MSG_COMO_FUNCIONA = marcar(
    "Ao atualizar, o SIG-FT fecha, instala a versão nova e abre de novo sozinho. "
    "Suas chaves de API e preferências continuam onde estão."
)

# "Atualizar agora" com um robô rodando: o app fecha sozinho quando o download
# termina, e a tarefa morre ali. Mesmo aviso do "X" da janela principal.
MSG_TAREFA_AO_ATUALIZAR = marcar(
    "Há uma tarefa em andamento (um robô, uma tradução ou uma consulta à IA).\n\n"
    "Para instalar a atualização, o SIG-FT fecha sozinho quando o download "
    "termina. A tarefa é interrompida no ponto em que estiver, e uma planilha "
    "que estava sendo gravada pode ficar pela metade.\n\n"
    "Se puder, espere a tarefa terminar e atualize depois.\n\n"
    "Atualizar mesmo assim?"
)

MSG_DOWNLOAD_CONFERIDO = marcar("Download conferido. Abrindo o instalador...")

# [2026-10-27] A atualização por arquivos: o próprio SIG-FT aplica e se reabre.
MSG_APLICANDO = marcar("Aplicando a atualização…")
MSG_REABRINDO = marcar("Atualizado. Reabrindo o SIG-FT…")

TEXTO_ATUALIZAR = marcar("Atualizar agora")
TEXTO_ATUALIZANDO = marcar("Atualizando...")
TEXTO_TENTAR_DE_NOVO = marcar("Tentar de novo")
TEXTO_AGORA_NAO = marcar("Agora não")
TEXTO_O_QUE_MUDOU = marcar("O que mudou:")


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
    # As notas vêm do CHANGELOG e ficam como vieram; só o "sem notas" é da interface.
    return "\n\n".join(paragrafos) or t("(Esta versão não trouxe notas.)")


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
    partes = [t("Você está na v{versao}.", versao=versao_atual)]
    if info.publicado_em:
        detalhe = t("A v{versao} saiu em {data}", versao=info.versao, data=data_br(info.publicado_em))
    else:
        detalhe = t("A v{versao}", versao=info.versao)
    if info.incremental and info.tamanho:
        partes.append(detalhe + ".")
        if info.tamanho_completo:
            partes.append(t("A atualização tem {mb} MB: só o que mudou (o instalador completo tem "
                            "{completo} MB).", mb=mb(info.tamanho_mb), completo=mb(info.tamanho_completo_mb)))
        else:
            partes.append(t("A atualização tem {mb} MB: só o que mudou.", mb=mb(info.tamanho_mb)))
        return " ".join(partes)
    if info.tamanho:
        detalhe = t("{detalhe} e tem {mb} MB", detalhe=detalhe, mb=mb(info.tamanho_mb))
    partes.append(detalhe + ".")
    return " ".join(partes)


# ── as frases montadas (eram f-strings dentro de `atualizacao.py`) ──────────

def titulo_do_aviso(info: Atualizacao) -> str:
    """[2026-10-07] Pelo canal de testes chega pré-lançamento: o título diz."""
    if info.prerelease:
        return t("Nova versão de teste disponível: v{versao}", versao=info.versao)
    return t("Nova versão disponível: v{versao}", versao=info.versao)


def msg_sem_verificar(versao_atual: str, motivo: str) -> str:
    return t("Você está na v{versao}.\n\n{motivo}", versao=versao_atual, motivo=motivo)


def msg_em_dia(versao_atual: str) -> str:
    return t("Você já está na versão mais recente (v{versao}).", versao=versao_atual)


def msg_erro_ao_procurar(erro: BaseException) -> str:
    return t("Não foi possível procurar atualizações.\n\n{erro}", erro=erro)


def msg_baixando(info: Atualizacao) -> str:
    return t("Baixando a v{versao} ({mb} MB)...", versao=info.versao, mb=mb(info.tamanho_mb))


def msg_caiu_no_completo(completo: Atualizacao) -> str:
    return t("A atualização pequena falhou. Baixando o instalador completo ({mb} MB)...",
             mb=mb(completo.tamanho_mb))


def msg_falhou(erro: BaseException) -> str:
    return t("Não foi possível atualizar: {erro}\n\nO SIG-FT continua nesta versão. Tente de novo; "
             "se o erro se repetir, avise quem cuida do SIG-FT. O detalhe completo fica no log "
             "(Documentos\\SIG-FT\\logs\\sigft.log).", erro=erro_curto(erro))


def msg_instalador_nao_iniciou(erro: BaseException) -> str:
    """[2026-10-27] O instalador saiu (ou não respondeu) antes de avisar que
    subiu (`updater.InstaladorNaoIniciou`): o SIG-FT ficou aberto."""
    return t("O instalador não chegou a começar, e o SIG-FT continua aberto, nesta versão.\n\n"
             "{erro}\n\nCostuma ser o antivírus, a política da empresa ou o pedido de permissão "
             "do Windows recusado. Tente de novo; se o erro se repetir, avise quem cuida do SIG-FT.",
             erro=erro_curto(erro))
