r"""
sigft/core/rpa/respostas.py — o que as telas do PMIB recebem do servidor
(2026-10-14).

O portal é um app OutSystems: cada tela pede seus dados por um endereço
`/PMIB/screenservices/...` e recebe JSON. Quando o robô navega ou clica, o
motor guarda essas respostas (`RPAEngine.capturar_respostas`), e este módulo
diz o que elas significam. É RPA: nada aqui faz requisição -- lê o que o
navegador já recebeu porque o robô agiu como uma pessoa. Regra do Luan
(2026-10-14): a Itaipu proíbe contato com o banco de dados dela, e o SIG-FT
não chama o servidor por fora da tela.

Formas, tiradas do código das próprias telas (docs/PMIB_ENGENHARIA_REVERSA.md):

  - consulta (`ScreenDataSet...`): `{"data": {"List": {"List": [...]}, "Count": N}}`,
    com `"EmptyListItem"` no lugar dos itens quando a lista vem vazia;
  - ação (`Action...`): `{"data": {<saídas>}}`, ou `{"exception": {...}}`
    quando o servidor recusa.

As funções procuram os registros pelo NOME dos campos, em qualquer nível, e
não pela posição: um invólucro a mais numa versão nova do portal não as
derruba. Só biblioteca padrão.
"""
from __future__ import annotations

from sigft import config
from sigft.core.excel import pmib_codes

# Trechos dos endereços (bloco/ação), como estão no código das telas.
# A lista de fichas: uma tabela por status, e uma pesquisa recarrega as sete.
URL_LISTA_DE_FICHAS = "PMIB_DatasheetListTable/ScreenDataSetGetPMIBDataSheetsByCreateBy"
ABAS_DA_LISTA = 7
# O cabeçalho da visualização da ficha: a solicitação de codificação, com o
# código SAP de recebimento ("Código de recepção/estoque" na tela).
URL_CODIFICACAO_DA_FICHA = "PMIB_DataSheetViewHeader/ScreenDataSetGetCodificationRequestsByPMIBDatasheetId"
# O CONFIRMAR da aplicação LMR: grava a aplicação e todas as tags de uma vez.
URL_GRAVAR_APLICACAO_LMR = "Datasheet_ApplicationMRL/ActionApplicationMRL_CreateOrUpdate"


def url_da_ficha(id_ficha) -> str:
    """O endereço da visualização da ficha pelo Id interno -- o mesmo link
    que o próprio portal monta nos avisos de sucesso."""
    base = config.PORTAL_URL.rsplit("/", 1)[0]
    return f"{base}/PMIB_DataSheetView?PMIB_DataSheetId={id_ficha}"


def _registros(no):
    """Todos os dicionários dentro de `no`, em profundidade."""
    if isinstance(no, dict):
        yield no
        for valor in no.values():
            yield from _registros(valor)
    elif isinstance(no, list):
        for valor in no:
            yield from _registros(valor)


def _campo(registro, nome):
    """O valor de `nome` no registro, sem diferença de maiúscula."""
    alvo = nome.lower()
    for chave, valor in registro.items():
        if str(chave).lower() == alvo:
            return valor
    return None


def _vazio(valor) -> bool:
    return valor is None or str(valor).strip() in ("", "0")


def _dados(resposta):
    """O conteúdo útil da resposta, ou `None` se ela é erro ou não é JSON de
    objeto."""
    if not isinstance(resposta, dict) or resposta.get("exception"):
        return None
    return resposta.get("data", resposta)


def _codigo_da_linha(linha) -> str | None:
    numero, sequencial = _campo(linha, "DSNumber"), _campo(linha, "DSNumberSec")
    if _vazio(numero) or sequencial is None:
        return None
    try:
        return f"{int(str(numero).strip())}.{int(str(sequencial).strip()):04d}"
    except ValueError:
        return None


def id_da_ficha(respostas_da_lista, pmib) -> str | None:
    """O Id interno da ficha `pmib`, procurado nas respostas da lista (uma por
    aba). O código PMIB que a tela mostra é `DSNumber` + "." + `DSNumberSec`
    com quatro dígitos. `None` se a ficha não está em nenhuma delas."""
    alvo = pmib_codes.normalize_pmib(pmib)
    for resposta in respostas_da_lista:
        for linha in _registros(_dados(resposta)):
            codigo = _codigo_da_linha(linha)
            if codigo is None or pmib_codes.normalize_pmib(codigo) != alvo:
                continue
            ident = _campo(linha, "Id")
            if not _vazio(ident):
                return str(ident).strip()
    return None


def _cancelada(registro) -> bool:
    status = _campo(registro, "RequestStatus")
    if not isinstance(status, dict):
        return False
    textos = (_campo(status, nome) for nome in ("Label", "DescriptionPt", "DescriptionEs"))
    return any("CANCEL" in str(texto or "").upper() for texto in textos)


def codigo_sap(resposta_da_codificacao) -> str | None:
    """O código SAP de recebimento da ficha, ou `None`.

    É o critério da própria Itaipu (aba "SQL" do export de autorizados): uma
    solicitação de codificação NÃO cancelada com `StockCodeSAP` preenchido. Ter
    esse código é estar autorizado para entrega."""
    for registro in _registros(_dados(resposta_da_codificacao)):
        solicitacao = _campo(registro, "CodificationRequest")
        if not isinstance(solicitacao, dict):
            continue
        codigo = str(_campo(solicitacao, "StockCodeSAP") or "").strip()
        if codigo and not _cancelada(registro):
            return codigo
    return None


def resultado_da_gravacao(resposta, campo_id) -> tuple[bool | None, str]:
    """O que a resposta de uma ação de salvar diz.

      - `(True, id)`: o servidor gravou e devolveu o Id em `campo_id`;
      - `(False, mensagem)`: o servidor recusou -- a mensagem é a dele;
      - `(None, "")`: a resposta não diz nem uma coisa nem outra.
    """
    if isinstance(resposta, dict) and resposta.get("exception"):
        excecao = resposta["exception"]
        if isinstance(excecao, dict):
            mensagem = excecao.get("message") or excecao.get("name") or ""
        else:
            mensagem = excecao
        return False, " ".join(str(mensagem).split())
    dados = _dados(resposta)
    if isinstance(dados, dict):
        ident = _campo(dados, campo_id)
        if not _vazio(ident):
            return True, str(ident).strip()
    return None, ""
