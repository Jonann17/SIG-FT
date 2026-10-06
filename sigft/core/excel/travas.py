r"""
sigft/core/excel/travas.py — por que um arquivo não pôde ser gravado, o que
fazer, e se Repetir adianta.

Ver `docs/superpowers/specs/2026-10-06-gravacao-com-retry-design.md`. Pedido do
Luan (2026-10-06): *"identificar qual está travado, deu erro e o motivo. E
pedir pra fechar e dar retry nessa parte."*

O que mora aqui
---------------
  - `diagnosticar(caminho, erro)`: a exceção vira um `Diagnostico` -- o motivo
    em português, o que fazer, e se Repetir adianta;
  - `conferir(caminho)`: a conferência de ANTES de gravar. Abre o arquivo para
    escrita e fecha sem escrever nada: nenhum byte, nenhuma data de
    modificação, nada para o Box versionar;
  - `conferir_antes` e `repetir_falhas`: os dois laços que perguntam à tela
    (a lista de antes e a lista do fim da etapa), sem saber de tela nenhuma --
    quem responde é o `perguntar(falhas, momento) -> bool` que o fluxo recebe;
  - `resumo`: o bloco "Não gravados nesta rodada" do fim do log.

Por que o `~$` sozinho não prova nada
-------------------------------------
O Excel cria `~$nome.xlsx` ao lado da planilha que abre, com o nome de quem
abriu. Mas sobra um quando o Excel fecha à força. Por isso o `~$` só dá NOME ao
motivo de um `PermissionError` que de fato aconteceu; a prova de travamento é
a tentativa de abrir para escrita (`conferir`).

Repetir sempre relê
-------------------
Estes laços não regravam nada: `repetir_falhas` chama o `refazer(caminho)` do
fluxo, que refaz a etapa daquele arquivo DESDE A LEITURA. Gravar de novo o que
ficou na memória da tentativa anterior apagaria o que a pessoa salvou antes de
fechar o arquivo (§2 do spec).

Só stdlib: a suíte roda sem openpyxl nem lxml de verdade.
"""
from __future__ import annotations

import errno
import ntpath
import os
import re
import zipfile
from dataclasses import dataclass
from typing import Callable, Iterable, Iterator, Mapping

# Os três momentos em que o fluxo pergunta à tela.
ANTES = "antes"      # a lista de antes: travados antes de gravar
DEPOIS = "depois"    # a lista do fim da etapa: não gravados, "Repetir só estes"
NA_HORA = "na_hora"  # um arquivo só, na hora (a mapeadora)

# O título do bloco do fim do log. A tela o procura para dizer, na janela
# final, quantos ficaram para trás.
TITULO_RESUMO = "Não gravados nesta rodada"

# Os motivos (a tabela do §3 do spec).
ABERTO_NO_EXCEL = "aberto_no_excel"
SOMENTE_LEITURA = "somente_leitura"
EM_USO = "em_uso"
SUMIU = "sumiu"
SEM_ACESSO = "sem_acesso"
JA_EXISTE = "ja_existe"
DISCO_CHEIO = "disco_cheio"
CORROMPIDO = "corrompido"
FORA_DO_PADRAO = "fora_do_padrao"
DESCONHECIDO = "desconhecido"

# Códigos do Windows (`OSError.winerror`). Os de rede, e a faixa da API de
# arquivos na nuvem (ERROR_CLOUD_FILE_*, 362 = o provedor não está rodando):
# o Box Drive fora do ar cai aqui.
_WINERROR_SEM_ACESSO = frozenset({21, 53, 59, 64, 67, 121, 1231, 1232}) | frozenset(range(360, 410))
_WINERROR_DISCO_CHEIO = frozenset({39, 112})
_WINERROR_TRAVA = frozenset({5, 32, 33})  # acesso negado, sharing violation, lock violation
_ERRNO_SEM_ACESSO = frozenset(getattr(errno, nome) for nome in (
    "ENETDOWN", "ENETUNREACH", "EHOSTDOWN", "EHOSTUNREACH", "ETIMEDOUT", "ENOTCONN", "ESTALE")
    if hasattr(errno, nome))
_ERRNO_DISCO_CHEIO = frozenset(getattr(errno, nome) for nome in ("ENOSPC", "EDQUOT") if hasattr(errno, nome))
# Exceções de bibliotecas que este módulo não importa (lxml, openpyxl),
# reconhecidas pelo nome da classe.
_NOMES_CORROMPIDO = frozenset({"XMLSyntaxError", "ParseError", "InvalidFileException"})


@dataclass(frozen=True)
class Diagnostico:
    """Por que não gravou. `motivo` completa a frase "o arquivo ...";
    `o_que_fazer` é o remédio, sem o botão (quem mostra diz "e clique em
    Repetir" ou "e rode de novo")."""

    tipo: str
    motivo: str
    o_que_fazer: str
    repetir_adianta: bool


@dataclass(frozen=True)
class Falha:
    """Um arquivo que ficou para trás: onde, por quê, e o que deixou de
    acontecer (`consequencia`). `rotulo` nomeia arquivos que não são
    `_STATUS_PMIB` ("Planilha de mapeamento")."""

    caminho: str
    diagnostico: Diagnostico
    rotulo: str | None = None
    consequencia: str = "não gravado"

    @property
    def nome(self) -> str:
        # `ntpath`: corta `\` e `/` em qualquer sistema (o caminho é do
        # Windows; a suíte roda em Linux).
        arquivo = ntpath.basename(str(self.caminho)) or str(self.caminho)
        return f"{self.rotulo} ({arquivo})" if self.rotulo else arquivo


Perguntar = Callable[[list, str], bool]


# --------------------------------------------------------------------------
# O dono do Excel
# --------------------------------------------------------------------------
def dono_do_excel(caminho) -> str | None:
    """Quem está com a planilha aberta no Excel desta máquina, pelo `~$` ao
    lado dela. `None` = não há `~$`; `""` = há, mas o nome não é legível."""
    caminho = str(caminho)
    dono = os.path.join(os.path.dirname(caminho), "~$" + os.path.basename(caminho))
    if not os.path.isfile(dono):
        return None
    try:
        with open(dono, "rb") as fh:
            dados = fh.read(512)
    except OSError:
        return ""
    return _nome_no_arquivo_de_dono(dados)


def _nome_no_arquivo_de_dono(dados: bytes) -> str:
    """O `~$` do Excel: tamanho (1 byte) + nome ANSI até o byte 54, depois
    tamanho (2 bytes) + nome em UTF-16. Prefere o UTF-16 (acentos); o que não
    for legível vira `""` -- melhor nenhum nome que um nome inventado."""
    if len(dados) >= 56:
        tamanho = int.from_bytes(dados[54:56], "little")
        if 0 < tamanho <= 100 and len(dados) >= 56 + 2 * tamanho:
            try:
                nome = dados[56:56 + 2 * tamanho].decode("utf-16-le")
            except UnicodeDecodeError:
                nome = ""
            if _legivel(nome):
                return nome.strip()
    if dados:
        tamanho = dados[0]
        if 0 < tamanho <= 53 and len(dados) >= 1 + tamanho:
            nome = dados[1:1 + tamanho].decode("cp1252", errors="replace")
            if _legivel(nome):
                return nome.strip()
    return ""


def _legivel(nome: str) -> bool:
    return bool(nome.strip()) and nome.isprintable() and "�" not in nome


# --------------------------------------------------------------------------
# O diagnóstico
# --------------------------------------------------------------------------
def diagnosticar(caminho, erro: BaseException) -> Diagnostico:
    """O motivo de `erro` ao gravar (ou renomear, ou abrir) `caminho`."""
    caminho = str(caminho)
    if isinstance(erro, OSError):
        return _diagnosticar_oserror(caminho, erro)
    if isinstance(erro, zipfile.BadZipFile) or type(erro).__name__ in _NOMES_CORROMPIDO:
        return Diagnostico(
            CORROMPIDO, "não é um .xlsx válido (pode estar corrompido)",
            "Abra no Excel: se ele reparar, salve. Senão, restaure a versão anterior pelo Box.", False)
    if isinstance(erro, (KeyError, NotImplementedError, ValueError)):
        return Diagnostico(FORA_DO_PADRAO, f"está fora do padrão ({_texto(erro)})",
                           "Corrija o arquivo no Excel.", False)
    return _desconhecido(erro)


def _diagnosticar_oserror(caminho: str, erro: OSError) -> Diagnostico:
    winerror = getattr(erro, "winerror", None)
    if isinstance(erro, FileExistsError):
        return Diagnostico(JA_EXISTE, "já existe um arquivo com o nome novo",
                           "Veja qual dos dois é o controle vivo e mova o outro para a pasta OBSOLETO.", False)
    if isinstance(erro, FileNotFoundError):
        if os.path.isdir(os.path.dirname(os.path.abspath(caminho))):
            return Diagnostico(SUMIU, "não está mais na pasta",
                               "Ele foi movido, renomeado ou apagado durante o processo. Confira a pasta.", False)
        return _sem_acesso()
    if erro.errno in _ERRNO_DISCO_CHEIO or winerror in _WINERROR_DISCO_CHEIO:
        return Diagnostico(DISCO_CHEIO, "o disco está cheio", "Libere espaço no disco.", True)
    if erro.errno in _ERRNO_SEM_ACESSO or winerror in _WINERROR_SEM_ACESSO:
        return _sem_acesso()
    if isinstance(erro, PermissionError) or erro.errno in (errno.EACCES, errno.EPERM) \
            or winerror in _WINERROR_TRAVA:
        return _travado(caminho)
    return _desconhecido(erro)


def _travado(caminho: str) -> Diagnostico:
    """Um `PermissionError` de verdade: o atributo, o Excel desta máquina, ou
    outro programa -- nesta ordem. O atributo vem primeiro porque, com ele, o
    `~$` de um Excel aberto em modo leitura mandaria a pessoa fechar o Excel à
    toa."""
    if os.path.exists(caminho) and not os.access(caminho, os.W_OK):
        return Diagnostico(
            SOMENTE_LEITURA, "está marcado como somente leitura",
            "Desmarque 'Somente leitura' nas Propriedades do arquivo, ou confira no Box se você tem "
            "permissão de edição e se não há um cadeado de outra pessoa.", True)
    dono = dono_do_excel(caminho)
    if dono is not None:
        motivo = f"está aberto no Excel por {dono}" if dono else "está aberto no Excel"
        return Diagnostico(ABERTO_NO_EXCEL, motivo, "Salve o que for seu e feche o arquivo no Excel.", True)
    return Diagnostico(
        EM_USO, "está em uso por outro programa",
        "Pode ser o Excel de outra pessoa, a sincronização do Box ou o antivírus. Espere alguns "
        "segundos e feche o que estiver usando o arquivo.", True)


def _sem_acesso() -> Diagnostico:
    return Diagnostico(SEM_ACESSO, "a pasta não está acessível",
                       "Confira se o Box Drive está conectado (ícone ao lado do relógio) e se a rede está no ar.",
                       True)


def _desconhecido(erro: BaseException) -> Diagnostico:
    return Diagnostico(DESCONHECIDO, f"deu um erro inesperado ({type(erro).__name__}: {_texto(erro)})",
                       "Se o erro voltar, guarde esta linha do log para investigar.", True)


def _texto(erro: BaseException) -> str:
    """O texto da exceção sem o `repr` que o `KeyError` põe em volta."""
    if isinstance(erro, KeyError) and erro.args:
        return str(erro.args[0])
    return str(erro) or type(erro).__name__


def fora_do_padrao_na_nova_tentativa(caminho, consequencia: str) -> Falha:
    """A nova tentativa achou o arquivo fora do padrão (aba renomeada,
    cabeçalho sumido -- o aviso já saiu no log): não gravou, e Repetir de novo
    não resolve. Vai para o resumo do fim, não de volta para a janela."""
    return Falha(str(caminho), Diagnostico(
        FORA_DO_PADRAO, "ficou fora do padrão na nova tentativa (veja o aviso logo acima no log)",
        "Corrija o arquivo no Excel.", False), consequencia=consequencia)


# --------------------------------------------------------------------------
# A conferência de antes
# --------------------------------------------------------------------------
def conferir(caminho) -> Diagnostico | None:
    """`None` se dá para gravar agora; senão, o motivo. Abre para escrita e
    fecha sem escrever nada -- o arquivo não muda, nem a data dele."""
    try:
        with open(caminho, "r+b"):
            pass
    except OSError as erro:
        return diagnosticar(caminho, erro)
    return None


# --------------------------------------------------------------------------
# Os dois laços que perguntam
# --------------------------------------------------------------------------
def conferir_antes(alvos: Iterable[tuple[str, str | None]], perguntar: Perguntar | None = None, *,
                   conferir: Callable[[str], Diagnostico | None] = conferir) -> Iterator[str]:
    """A lista de antes. `alvos`: `(caminho, rotulo)`, rótulo `None` para um
    `_STATUS_PMIB`. Generator de linhas de log; DEVOLVE (`return`)
    `{caminho: Falha}` dos que o fluxo deve seguir SEM gravar.

    Havendo travados, pergunta uma vez por todos (`perguntar(falhas, ANTES)`):
    `True` confere de novo só os travados (e pergunta de novo pelos que ainda
    estiverem); `False`, ou sem `perguntar`, segue sem eles.
    """
    alvos = list(alvos)
    rotulos = dict(alvos)
    travados: dict[str, Falha] = {}
    for caminho, rotulo in alvos:
        diagnostico = conferir(caminho)
        if diagnostico is not None:
            travados[caminho] = Falha(caminho, diagnostico, rotulo)
    if not travados:
        yield f" -> Conferi {len(alvos)} arquivo(s) antes de gravar: nenhum travado."
        return {}
    for falha in travados.values():
        yield f" -> Travado antes de gravar: {falha.nome} ({falha.diagnostico.motivo})."
    while travados and perguntar is not None and perguntar(list(travados.values()), ANTES):
        ainda: dict[str, Falha] = {}
        for caminho in travados:
            diagnostico = conferir(caminho)
            if diagnostico is not None:
                ainda[caminho] = Falha(caminho, diagnostico, rotulos.get(caminho))
        yield f" -> Conferi de novo: {len(travados) - len(ainda)} liberado(s), {len(ainda)} ainda travado(s)."
        travados = ainda
    if travados:
        yield (f" -> Seguindo sem {len(travados)} arquivo(s): eles são lidos, mas não gravados nesta "
               "rodada: " + ", ".join(f.nome for f in travados.values()) + ".")
    return travados


def repetir_falhas(falhas: dict[str, Falha], perguntar: Perguntar | None,
                   refazer: Callable[[str], Iterator]) -> Iterator[str]:
    """A lista do fim da etapa. Generator de linhas de log; DEVOLVE
    (`return`) o `falhas` que sobrou (o mesmo dicionário, alterado).

    Só os que Repetir resolve vão para a janela (`perguntar(lista, DEPOIS)`).
    `True` refaz cada um com `refazer(caminho)` -- generator do fluxo que refaz
    a etapa daquele arquivo DESDE A LEITURA e devolve `None` (gravou) ou a
    `Falha` nova --, e pergunta de novo pelos que falharem outra vez.
    """
    while perguntar is not None:
        retentaveis = [f for f in falhas.values() if f.diagnostico.repetir_adianta]
        if not retentaveis or not perguntar(retentaveis, DEPOIS):
            break
        for falha in retentaveis:
            yield f" -> Repetindo {falha.nome}..."
            nova = yield from refazer(falha.caminho)
            if nova is None:
                del falhas[falha.caminho]
                yield f" -> {falha.nome}: gravado na nova tentativa."
            else:
                falhas[falha.caminho] = nova
                yield f" -> {falha.nome}: ainda não gravado ({nova.diagnostico.motivo})."
    return falhas


# --------------------------------------------------------------------------
# O resumo do fim
# --------------------------------------------------------------------------
def quantos_no_resumo(linha: str) -> int | None:
    """O total do cabeçalho do resumo ("[AVISO] Não gravados nesta rodada
    (2):" -> 2), ou `None` se a linha não é ele. A tela usa para dizer, na
    janela final, quantos ficaram para trás."""
    if TITULO_RESUMO not in linha:
        return None
    m = re.search(r"\((\d+)\):", linha)
    return int(m.group(1)) if m else None


def resumo(falhas: Iterable[Falha] | Mapping[str, Falha]) -> list[str]:
    """O bloco do fim do log: UMA linha `[AVISO]` (a tela conta avisos por
    linha) e uma por arquivo, com o que deixou de acontecer, o motivo e o que
    fazer."""
    lista = list(falhas.values()) if isinstance(falhas, Mapping) else list(falhas)
    if not lista:
        return []
    linhas = [f"[AVISO] {TITULO_RESUMO} ({len(lista)}):"]
    for falha in lista:
        d = falha.diagnostico
        linhas.append(f"   - {falha.nome}: {falha.consequencia}. Motivo: {d.motivo}. {d.o_que_fazer} "
                      "Depois, rode de novo.")
    return linhas
