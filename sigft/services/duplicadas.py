r"""
Ficha duplicada — identificação a partir do `_STATUS_PMIB` (CP 6.2).

Primeira metade do checkpoint: descobrir QUAIS fichas são duplicadas e reunir,
para cada uma, tudo o que a planilha tem a dizer. É a etapa que dá para o
usuário testar hoje, contra a planilha real, **antes de existir uma linha de
RPA** -- e é deliberado que seja assim: se a identificação errar, todo o resto
erra em cima.

As regras vivem em `duplicadas_spec.py` (sem I/O, testadas em isolamento);
aqui é só a leitura da planilha e a montagem do pacote.
"""
from __future__ import annotations

import pandas as pd

from sigft import config
from sigft.core.excel import headers
from sigft.services import duplicadas_spec as spec


class FichaDuplicada:
    """Uma ficha a duplicar, com o que a planilha sabe sobre ela.

    Classe simples em vez de dicionário porque estes campos são lidos em
    quatro lugares diferentes do RPA, e um `dict` deixaria erro de digitação
    de chave virar `None` silencioso -- o tipo de coisa que aqui produz ficha
    plausível e errada.
    """

    def __init__(self, pmib, descricao, pdm_usado, codigo_material,
                 codigo_fornecedor, ficha_original, linha):
        self.pmib = pmib
        self.descricao = descricao
        self.pdm_usado = pdm_usado
        # Referência do FABRICANTE (coluna CÓDIGO DO MATERIAL).
        self.codigo_material = codigo_material
        # Referência do FORNECEDOR (CÓDIGO CMI / CÓDIGO GE). Vazio => pular.
        self.codigo_fornecedor = codigo_fornecedor
        # Código da ficha ORIGINAL, lido de OBSERVAÇÕES.
        self.ficha_original = ficha_original
        self.linha = linha  # linha na planilha, para a mensagem de erro

    @property
    def pronta_para_duplicar(self):
        """Tem o mínimo para o RPA trabalhar?

        Sem a ficha ORIGINAL não há de onde copiar, e sem o CÓDIGO DO MATERIAL
        não há referência de fabricante para escrever. As duas faltas são
        impeditivas e é melhor descobrir na tela de seleção do que no meio do
        lote, com o navegador aberto.
        """
        return bool(self.ficha_original) and bool(self.codigo_material)

    @property
    def motivo_de_impedimento(self):
        faltas = []
        if not self.ficha_original:
            faltas.append("ficha original (coluna OBSERVAÇÕES)")
        if not self.codigo_material:
            faltas.append("referência do fabricante (coluna CÓDIGO DO MATERIAL)")
        return " e ".join(faltas)

    def __repr__(self):  # facilita o log e o teste
        return f"<FichaDuplicada {self.pmib} <- {self.ficha_original}>"


def _texto(valor):
    """Célula do pandas -> texto limpo, com `nan` virando vazio."""
    if valor is None:
        return ""
    texto = str(valor).strip()
    return "" if texto.lower() == "nan" else texto


def _achar_aba(caminho_excel):
    """A aba de materiais, tolerando as variantes de nome já conhecidas.

    Aqui a busca automática é legítima -- ao contrário da planilha de LMR,
    onde o usuário pediu seletor: o `_STATUS_PMIB` é gerado pelo próprio
    sistema, tem estrutura conhecida, e as variantes de nome já estão
    catalogadas em `config.ABA_LISTA_MATERIAIS_VARIANTES` desde o CP 1.1.
    """
    abas = list(pd.ExcelFile(caminho_excel).sheet_names)
    candidatas = [config.ABA_LISTA_MATERIAIS, *config.ABA_LISTA_MATERIAIS_VARIANTES]
    for candidata in candidatas:
        for aba in abas:
            if str(aba).strip().upper() == str(candidata).strip().upper():
                return aba, abas
    return None, abas


def localizar_duplicadas(caminho_excel, callback_log=None):
    """(lista de `FichaDuplicada`, mensagem) — as fichas marcadas com o PDM de
    duplicação no `_STATUS_PMIB`.

    Devolve TODAS as encontradas, inclusive as impedidas (sem ficha original
    ou sem código do material): quem decide o que fazer é a tela de seleção,
    e esconder aqui faria a ficha sumir sem explicação.
    """
    def _log(mensagem):
        if callback_log:
            callback_log(mensagem)

    aba, abas = _achar_aba(caminho_excel)
    if aba is None:
        return [], (
            "Não encontrei a aba de materiais no arquivo. Abas: "
            f"{', '.join(str(a) for a in abas) or '(nenhuma)'}. "
            f"Esperado: {config.ABA_LISTA_MATERIAIS}"
        )

    # O cabeçalho do `_STATUS_PMIB` não está na primeira linha (é `LINHA_STATUS_PMIB`
    # desde o CP 1.1), e a busca dinâmica de `core.excel.headers` cobre a
    # variação -- mesma mecânica que `cria_fichas` e `tech_specs` já usam.
    previa = pd.read_excel(caminho_excel, sheet_name=aba, header=None, nrows=30)
    linha_cabecalho = headers.find_header_row(
        previa.values.tolist(), [config.COL_CODIGO_PMIB]
    )
    if linha_cabecalho is None:
        linha_cabecalho = config.LINHA_STATUS_PMIB - 1

    df = pd.read_excel(caminho_excel, sheet_name=aba, header=linha_cabecalho, dtype=str)
    df.columns = [str(c).strip() for c in df.columns]

    col_pdm = spec.achar_coluna(df.columns, spec.COLUNAS_PDM_USADO)
    if col_pdm is None:
        return [], (
            "A planilha não tem a coluna do PDM usado. Esperado (qualquer grafia): "
            + " / ".join(spec.COLUNAS_PDM_USADO)
            + f". Colunas encontradas: {', '.join(df.columns)}"
        )

    col_material = spec.achar_coluna(df.columns, spec.COLUNAS_REFERENCIA_FABRICANTE)
    col_fornecedor = spec.achar_coluna(df.columns, spec.COLUNAS_REFERENCIA_FORNECEDOR)
    col_original = spec.achar_coluna(df.columns, spec.COLUNAS_FICHA_ORIGINAL)

    # Coluna ausente NÃO é erro fatal: a ficha entra na lista marcada como
    # impedida, e a tela de seleção mostra o porquê. Abortar aqui esconderia
    # de quantas fichas se está falando.
    for nome, coluna, candidatas in (
        ("referência do fabricante", col_material, spec.COLUNAS_REFERENCIA_FABRICANTE),
        ("ficha original", col_original, spec.COLUNAS_FICHA_ORIGINAL),
    ):
        if coluna is None:
            _log(f"   [Aviso] Coluna de {nome} não encontrada ({' / '.join(candidatas)}).")

    encontradas = []
    for indice, linha in df.iterrows():
        if not spec.e_ficha_duplicada(linha.get(col_pdm)):
            continue
        encontradas.append(FichaDuplicada(
            pmib=_texto(linha.get(config.COL_CODIGO_PMIB)),
            descricao=_texto(linha.get(config.COL_DESCRICAO)),
            pdm_usado=_texto(linha.get(col_pdm)),
            codigo_material=_texto(linha.get(col_material)) if col_material else "",
            codigo_fornecedor=_texto(linha.get(col_fornecedor)) if col_fornecedor else "",
            ficha_original=spec.extrair_ficha_original(
                linha.get(col_original) if col_original else None
            ) or "",
            # +2: o pandas conta de 0 e o cabeçalho ocupa uma linha, então
            # este número é o que o usuário vê na barra lateral do Excel.
            linha=int(indice) + linha_cabecalho + 2,
        ))

    prontas = [f for f in encontradas if f.pronta_para_duplicar]
    mensagem = (
        f"Aba '{aba}': {len(encontradas)} ficha(s) marcada(s) como duplicada "
        f"({spec.PDM_DUPLICADA}); {len(prontas)} pronta(s) para o robô."
    )
    return encontradas, mensagem
