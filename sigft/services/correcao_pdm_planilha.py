r"""A lista de fichas da tela de correção de PDM, e a PRÉVIA (E5, parte 1).

O que a tela mostra e o que ela calcula, fora do Tk. Ler o `_STATUS_PMIB`,
montar as linhas e estimar quanto se recupera são regras de negócio, e regra de
negócio não vive na UI (princípio 2 da arquitetura).

⚠️ A PREVIA E DEFINIDA PELO QUE ELA SE RECUSA A DIZER
------------------------------------------------------------------------
O catálogo guarda só a revisão **vigente** de cada PDM. Numa atualização de
revisão o código é o mesmo dos dois lados, então comparar catálogo com catálogo
daria "100%" sempre -- um número bonito e vazio, porque o que a ficha tem é a
revisão ANTIGA, que o catálogo não tem.

Prévia que mente é pior que prévia ausente: ela é exatamente o que o usuário
olha antes de autorizar uma operação que apaga características. Por isso, na
atualização de revisão, ela diz o que sabe ("o portal vai para a revisão
vigente") e não finge um número.

A leitura da planilha usa `core.excel.headers` -- o cabeçalho das planilhas
reais não está na primeira linha, e achar isso por contagem fixa é como nasce
o "ficha nenhuma encontrada" num arquivo cheio de fichas.

Plano em `docs/refatoracao/CORRECAO_PDM.md` (etapa E5).
"""
from __future__ import annotations

from dataclasses import dataclass

from sigft import config
from sigft.core.excel import headers
from sigft.services.cria_fichas import codigo_do_pdm


# Quantas linhas abaixo do topo o cabeçalho pode estar. As planilhas reais
# trazem título e linhas em branco em cima; 15 e a folga que o `tech_specs` ja
# usava em `encontrar_header`.
MAX_LINHAS_DE_CABECALHO = 15


@dataclass
class FichaParaCorrigir:
    """Uma linha da tela. `pdm_novo` é o que o usuário escolhe; começa vazio."""

    pmib: str
    descricao: str = ""
    pdm_atual: str = ""
    pdm_novo: str = ""


def ler_fichas(aba) -> list[FichaParaCorrigir]:
    """As fichas de um `_STATUS_PMIB` já aberto (aba "Lista de Materiais").

    Recebe a WORKSHEET e não o caminho: mantém este módulo sem openpyxl e
    testável com uma aba falsa, como `core/excel/status_sheet.py` faz.

    Planilha sem a coluna de PMIB devolve lista vazia em vez de levantar: a
    tela mostra "nenhuma ficha" e a pessoa escolhe outro arquivo. Já a falta da
    coluna de PDM não impede nada -- sem o PDM atual dá para escolher o novo à
    mão; sem a lista de fichas não dá para nada.
    """
    linhas = list(headers.rows_from_worksheet(aba))
    colunas, linha_do_cabecalho = headers.find_columns(
        linhas,
        {
            "pmib": config.COL_CODIGO_PMIB,
            "descricao": (config.COL_DESCRICAO, "TEXTO BREVE"),
            "pdm": config.COL_PDM_USADO,
        },
        required=["pmib"],
        max_rows=MAX_LINHAS_DE_CABECALHO,
    )
    if "pmib" not in colunas or linha_do_cabecalho is None:
        return []

    fichas = []
    for linha in linhas[linha_do_cabecalho:]:
        pmib = _celula(linha, colunas.get("pmib"))
        if not pmib:
            continue   # linha em branco no meio, ou o total no fim
        fichas.append(FichaParaCorrigir(
            pmib=pmib,
            descricao=_celula(linha, colunas.get("descricao")),
            pdm_atual=_celula(linha, colunas.get("pdm")),
        ))
    return fichas


def ler_fichas_do_arquivo(caminho, nome_aba=None) -> list[FichaParaCorrigir]:
    """O mesmo, a partir do CAMINHO de um `_STATUS_PMIB`.

    O `import openpyxl` é PREGUIÇOSO e mora só aqui: é o que mantém o resto do
    módulo stdlib-only e testável com uma aba falsa -- a mesma disciplina de
    `core/excel/status_sheet.py`.

    A aba é procurada entre as variantes conhecidas (`config.
    ABA_LISTA_MATERIAIS_VARIANTES`): planilhas reais escrevem o nome de jeitos
    diferentes, e cair fora por causa de um acento seria "nenhuma ficha" num
    arquivo cheio delas.
    """
    import openpyxl  # import preguicoso -- ver a docstring

    wb = openpyxl.load_workbook(caminho, data_only=True, read_only=True)
    try:
        aba = _escolher_aba(wb, nome_aba)
        if aba is None:
            return []
        return ler_fichas(aba)
    finally:
        try:
            wb.close()
        except Exception:  # noqa: BLE001 -- fechar e cortesia
            pass


def _escolher_aba(wb, nome_aba=None):
    nomes = list(getattr(wb, "sheetnames", []) or [])
    candidatos = [nome_aba] if nome_aba else []
    candidatos.append(config.ABA_LISTA_MATERIAIS)
    candidatos.extend(getattr(config, "ABA_LISTA_MATERIAIS_VARIANTES", ()) or ())

    por_normal = {" ".join(str(n).upper().split()): n for n in nomes}
    for candidato in candidatos:
        achado = por_normal.get(" ".join(str(candidato or "").upper().split()))
        if achado:
            return wb[achado]
    # Nenhuma variante casou: a primeira aba e melhor palpite do que desistir.
    return wb[nomes[0]] if nomes else None


def _celula(linha, coluna) -> str:
    if not coluna or coluna > len(linha):
        return ""
    valor = linha[coluna - 1]
    if valor is None:
        return ""
    return " ".join(str(valor).split())


def so_a_revisao(pdm_atual) -> str:
    """O destino da ação em massa **"Só atualizar a revisão"**.

    É só o CÓDIGO do PDM que a ficha já tem: o combo do portal oferece a
    revisão vigente, então o código basta. *"Um clique resolve as 25 fichas."*

    Ficha sem PDM atual devolve `""` -- sem código para copiar, inventar um
    seria escolher um PDM no lugar do usuário.
    """
    return codigo_do_pdm(pdm_atual)


def previa(catalogo, pdm_atual, pdm_novo) -> str:
    """Quanto se espera recuperar, calculado do CATALOGO e sem tocar o portal.

    Três respostas possíveis, e duas delas são recusas honestas:

    - **códigos diferentes**: `"2 de 3 caracteristicas casam"`, pelo nome (no
      Master são 2278 códigos e 2278 nomes, bijeção perfeita);
    - **mesmo código** (atualização de revisão): diz que vai para a revisão
      vigente, **sem número**. Ver o aviso no topo do módulo;
    - **PDM fora do catálogo**: diz que não sabe. Silêncio viraria `"0 de N"`,
      que a pessoa leria como "não recupera nada".
    """
    if catalogo is None or not str(pdm_novo or "").strip():
        return ""

    codigo_atual = codigo_do_pdm(pdm_atual)
    codigo_novo = codigo_do_pdm(pdm_novo)
    if not codigo_novo:
        return ""

    if codigo_atual and codigo_atual == codigo_novo:
        return "so a revisao: o portal atribui a vigente"

    de = catalogo.por_codigo(codigo_atual) if codigo_atual else None
    para = catalogo.por_codigo(codigo_novo)
    if de is None or para is None:
        qual = codigo_novo if para is None else codigo_atual
        return f"sem previa: {qual} nao esta no catalogo"

    antigas = {_chave(c) for c in de.caracteristicas if _chave(c)}
    novas = {_chave(c) for c in para.caracteristicas if _chave(c)}
    if not antigas:
        return "sem previa: o catalogo nao lista as caracteristicas deste PDM"

    return f"{len(antigas & novas)} de {len(antigas)} caracteristicas casam"


def _chave(nome) -> str:
    return " ".join(str(nome or "").upper().split())


def lote(fichas):
    """As `(pmib, pdm_novo)` que vão para o serviço.

    Linha sem PDM novo fica de fora, e isso não é erro: é uma ficha que o
    usuário não quis mexer nesta rodada.
    """
    return [(f.pmib, f.pdm_novo) for f in fichas
            if str(getattr(f, "pdm_novo", "") or "").strip()]
