r"""
Gera planilhas SINTÉTICAS para exercitar o SIG-FT sem ter dados reais em mãos.

    python scripts/gerar_dados_de_teste.py [pasta_destino]

Sem argumento, grava em `dados_de_teste/` na raiz do repositório (ignorada pelo
git). Rodar de novo sobrescreve.

--------------------------------------------------------------------------
O que gera, e o que cada arquivo destrava
--------------------------------------------------------------------------
  <pasta>/
    4500063671.0001_STATUS_PMIB.xlsx   -> Buscar Material, Gestão PMIB, Condições,
    4500063671.0002_STATUS_PMIB.xlsx      Características Técnicas (leitura do status)
    fichas/4500063671.0001.xlsx        -> Analyzer, AutoSpec (a ficha em si)
    fichas/4500063671.0002.xlsx
    LMR_aplicacoes.xlsx                -> Cadastro LMR (aba LMR)

--------------------------------------------------------------------------
O que estes arquivos NÃO provam
--------------------------------------------------------------------------
A estrutura vem de `sigft/config.py` e `sigft/core/rpa/ficha_layout.py`, ou
seja: do que o CÓDIGO espera. Se a ficha real da Itaipu divergir disso em
algum ponto, o gerador vai reproduzir a expectativa do código, não a
realidade — e a divergência continuaria invisível. Estes arquivos servem para
"o módulo roda de ponta a ponta e o fluxo da tela funciona", não para "o
layout está certo". Para isso, só uma ficha real.

Também não substituem o portal: os módulos de RPA continuam precisando do PMIB.

--------------------------------------------------------------------------
Por que openpyxl direto, e não pandas
--------------------------------------------------------------------------
A ficha técnica não é uma tabela: é um formulário com valores em células
espalhadas (`H6:P6` para a descrição, `S6`/`S8` como caixas de seleção…). Quem
descreve esse layout é `ficha_layout.CONFIG_MAP`, e escrever a partir DELE — em
vez de repetir coordenadas aqui — é o que mantém o gerador em dia se o layout
mudar.
"""
from __future__ import annotations

import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sigft import config  # noqa: E402
from sigft.core.rpa import ficha_layout  # noqa: E402

# Materiais plausíveis para um projeto hidrelétrico -- inventados, mas com a
# cara do domínio, para o texto que a IA recebe não ser "aaa bbb ccc".
_MATERIAIS = [
    ("Rolamento de esferas 6208-2RS", "PÇ", "SKF", "Rolamento rígido de esferas, vedado, diâmetro interno 40 mm"),
    ("Válvula solenoide 3/2 vias 24Vcc", "PÇ", "Parker", "Válvula de comando pneumático, corpo em latão, rosca 1/4 BSP"),
    ("Sensor de temperatura PT100 3 fios", "PÇ", "WEG", "Termorresistência com bainha em aço inox 316, cabeçote DIN B"),
    ("Filtro de óleo hidráulico 10 micra", "PÇ", "Hydac", "Elemento filtrante para unidade hidráulica de regulação"),
    ("Contator tripolar 32A bobina 220Vca", "PÇ", "Siemens", "Contator para comando de motor de bomba de drenagem"),
    ("Vedação mecânica eixo 45 mm", "PÇ", "John Crane", "Selo mecânico simples para bomba centrífuga de resfriamento"),
    ("Disjuntor caixa moldada 3x100A", "PÇ", "ABB", "Disjuntor termomagnético para painel de distribuição"),
    ("Correia sincronizadora 8M-1600-30", "PÇ", "Gates", "Correia dentada para acionamento de ventilador"),
]

_PERGUNTAS_SPEC = [
    ("Material do corpo", "Aço inox AISI 316"),
    ("Faixa de temperatura de operação", "-20 °C a +120 °C"),
    ("Pressão máxima de trabalho", "16 bar"),
    ("Tipo de conexão", "Rosca BSP 1/4\""),
    ("Grau de proteção", "IP66"),
    ("Norma aplicável", "ABNT NBR IEC 60529"),
]


def _escrever_celula(ws, referencia, valor):
    """Aceita tanto `"H6"` quanto o range `"H6:P6"` do CONFIG_MAP -- num range
    mesclado, quem guarda o valor é a célula do canto superior esquerdo."""
    ws[referencia.split(":")[0]] = valor


def gerar_ficha(caminho, pmib, material):
    from openpyxl import Workbook

    descricao, unidade, fabricante, detalhe = material
    wb = Workbook()
    ws = wb.active
    ws.title = "FICHA TÉCNICA"

    # Cabeçalho, para o arquivo parecer uma ficha ao ser aberto no Excel.
    ws["B2"] = "FICHA TÉCNICA DE MATERIAL (DADOS SINTÉTICOS -- NÃO É FICHA REAL)"
    ws["B4"] = "Código PMIB:"
    ws["D4"] = pmib

    # Campos do layout, escritos A PARTIR do CONFIG_MAP (ver docstring).
    valores = {
        "texto_breve_material": descricao,
        "unidade": unidade,
        "fabricante": fabricante,
        "comprimento_embalagem": random.choice([10, 20, 35, 50]),
        "largura_embalagem": random.choice([10, 15, 25, 40]),
    }
    for chave, spec in ficha_layout.CONFIG_MAP.items():
        if spec.get("type") == "checkbox":
            # Marca a PRIMEIRA opção de cada par (ex.: Série, BR/PY, Reparável).
            _escrever_celula(ws, spec["cells"][0], "X")
        elif "range" in chave or spec.get("type") == "cell":
            valor = valores.get(chave)
            if valor is not None and "range" in spec:
                _escrever_celula(ws, spec["range"], valor)

    ws["B60"] = "DESCRIÇÃO DETALHADA"
    ws["C62"] = detalhe

    # Bloco de especificações técnicas (pergunta/resposta), na linha que
    # `config.LINHA_SPECS_FICHA` define.
    specs = ficha_layout.VARIAVEIS_SPECS
    linha = specs["start_row"]
    ws.cell(row=linha - 2, column=specs["pergunta_col_idx"], value="ESPECIFICAÇÕES TÉCNICAS")
    for pergunta, resposta in _PERGUNTAS_SPEC:
        ws.cell(row=linha, column=specs["pergunta_col_idx"], value=pergunta)
        ws.cell(row=linha, column=specs["resposta_col_idx"], value=resposta)
        linha += 1

    wb.save(caminho)


def gerar_status_pmib(caminho, pmib, itens):
    """Planilha `_STATUS_PMIB`: aba "Lista de Materiais", cabeçalho na linha
    que `config.LINHA_STATUS_PMIB` define (5) -- é o que
    `core/excel/headers.find_columns` e `StatusPMIB` procuram.

    A linha de cima é a da revisão em uso, como no layout v2 dos arquivos reais
    (04/10/2026): é ela que faz um leitor de cabeçalho FIXO na linha 4 falhar
    aqui também, em vez de só na planilha do usuário."""
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.title = config.ABA_LISTA_MATERIAIS

    ws["A1"] = "CONTROLE DE FICHAS TÉCNICAS -- DADOS SINTÉTICOS"
    ws["A2"] = f"Ficha PMIB: {pmib}"
    ws.cell(row=config.LINHA_STATUS_PMIB - 1, column=1,
            value="REVISÃO DA LISTA DE SOBRESSALENTES ATUAL EM USO: 0A - DATA DE ALTERAÇÃO: 01/10/2026")

    colunas = [
        "ITEM",
        config.COL_CODIGO_PMIB,
        config.COL_DESCRICAO,
        config.COL_PDM_USADO,
        config.COL_INFO_GERAIS,
        config.COL_CONDICOES,
        config.COL_CARACT_TECNICAS,
    ]
    for indice, nome in enumerate(colunas, start=1):
        ws.cell(row=config.LINHA_STATUS_PMIB, column=indice, value=nome)

    linha = config.LINHA_STATUS_PMIB + 1
    for numero, (codigo, material, estados) in enumerate(itens, start=1):
        ws.cell(row=linha, column=1, value=numero)
        ws.cell(row=linha, column=2, value=codigo)
        ws.cell(row=linha, column=3, value=material[0])
        ws.cell(row=linha, column=4, value=f"PDM.{1000 + numero}.001")
        # Deixa um pouco de cada estado: assim os módulos que pulam o que já
        # está COMPLETO têm o que pular E o que processar.
        for offset, estado in enumerate(estados):
            ws.cell(row=linha, column=5 + offset, value=estado)
        linha += 1

    wb.save(caminho)


def gerar_lmr(caminho, registros):
    """Planilha de aplicações LMR: aba LMR com FICHA PMIB / CÓDIGO LMR / TAG LMR
    -- as 3 colunas que `lmr.carregar_dados_excel` exige."""
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.title = "LMR"

    # Cabeçalho NOVO (2026-08-11): é o que a tela e a documentação ensinam
    # agora. O leitor aceita os antigos também, mas o dado de teste tem de
    # mostrar o formato recomendado -- senão ninguém descobre qual é.
    for indice, nome in enumerate(["FICHA PMIB", "CÓDIGO LMR", "TAG LMR"], start=1):
        ws.cell(row=1, column=indice, value=nome)

    for linha, (pmib, codigo, tag) in enumerate(registros, start=2):
        ws.cell(row=linha, column=1, value=pmib)
        ws.cell(row=linha, column=2, value=codigo)
        ws.cell(row=linha, column=3, value=tag)

    wb.save(caminho)


def main() -> int:
    try:
        import openpyxl  # noqa: F401
    except ImportError:
        print("ERRO: `openpyxl` nao esta instalado.")
        print("      Rode antes:  python -m pip install -r requirements.txt")
        print("      (no Windows, o SIG-FT.bat ja faz isso)")
        return 2

    raiz = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    destino = sys.argv[1] if len(sys.argv) > 1 else os.path.join(raiz, "dados_de_teste")
    pasta_fichas = os.path.join(destino, "fichas")
    os.makedirs(pasta_fichas, exist_ok=True)

    random.seed(42)  # mesma saida toda vez -- comparar duas execucoes fica util
    gerados = []

    for numero in (1, 2):
        pmib = f"{config.PREFIXO_CONTRATO}.{numero:04d}"
        # 6 itens por ficha, com estados variados de preenchimento.
        itens = []
        for indice in range(6):
            material = _MATERIAIS[(numero * 3 + indice) % len(_MATERIAIS)]
            codigo = f"{100000 + numero * 100 + indice}"
            if indice < 2:
                estados = ["COMPLETO", "COMPLETO", "COMPLETO"]
            elif indice < 4:
                estados = ["COMPLETO", "", ""]
            else:
                estados = ["", "", ""]
            itens.append((codigo, material, estados))

        caminho_status = os.path.join(destino, f"{pmib}_STATUS_PMIB.xlsx")
        gerar_status_pmib(caminho_status, pmib, itens)
        gerados.append(caminho_status)

        caminho_ficha = os.path.join(pasta_fichas, f"{pmib}.xlsx")
        gerar_ficha(caminho_ficha, pmib, _MATERIAIS[numero % len(_MATERIAIS)])
        gerados.append(caminho_ficha)

    registros = []
    for numero in (1, 2):
        pmib = f"{config.PREFIXO_CONTRATO}.{numero:04d}"
        for indice in range(3):
            codigo = f"{100000 + numero * 100 + indice}"
            # O 1º código de cada ficha tem 2 TAGs -- exercita o agrupamento
            # de TAGs consecutivas que o `lmr` faz.
            for tag in (["A", "B"] if indice == 0 else ["A"]):
                registros.append((pmib, codigo, f"TAG-{numero}{indice}{tag}"))

    caminho_lmr = os.path.join(destino, "LMR_aplicacoes.xlsx")
    gerar_lmr(caminho_lmr, registros)
    gerados.append(caminho_lmr)

    print("Dados de teste gerados em:")
    print(f"  {destino}\n")
    for caminho in gerados:
        print(f"  {os.path.relpath(caminho, destino)}")
    print("\nSao dados SINTETICOS -- servem para exercitar o fluxo das telas,")
    print("nao para conferir se o layout bate com a ficha real da Itaipu.")
    print("Os modulos de RPA continuam precisando do portal PMIB.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
