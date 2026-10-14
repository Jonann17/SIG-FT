"""O mural de atividades em Qt -- o desenho de `sigft/app/widgets/mural.py`.

A regra (que atividade cai em que faixa, as frases de prazo) mora em
`services/atividades.py` e se prova sem interface; aqui só o desenho, o mesmo
do CustomTkinter: contador grande na faixa, barra colorida da criticidade à
esquerda de cada cartão, o prazo em destaque à direita, faixas em ordem de
urgência.

As tabelas de cor, rótulo e explicação são CÓPIA das de lá (o módulo de lá
importa o customtkinter e não pode ser importado daqui). O teste
`test_desenho_do_mural_igual_ao_customtkinter` falha se um lado mudar sozinho;
`tests/test_mural_nomes_do_servico.py` cobra as faixas nos dois.

As medidas são as do `pack` de lá: cada CTkLabel tem pelo menos 28 px de altura
(o `height` padrão) com o texto centrado, e os `pady` de vizinhos SOMAM -- por
isso cada peça entra numa caixa com as margens dela, num layout sem espaçamento.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QVBoxLayout, QWidget

from sigft.app import theme
from sigft.app_qt import estilo
from sigft.app_qt.widgets import blocos
from sigft.services import atividades as at

# Cor de cada faixa. Vermelho e laranja vêm do tema; as demais seguem a paleta.
COR_FAIXA = {
    at.ATRASADA: theme.COLORS["danger"],
    # Roxo, deliberadamente fora da escala vermelho->laranja->verde do prazo:
    # travada nao e "mais atrasada", e outra natureza de problema.
    at.TRAVADA: "#B07CE8",
    at.DEVERIA_TER_COMECADO: theme.COLORS["warning"],
    at.EM_ANDAMENTO: theme.COLORS["primary_hover"],
    at.COMECA_HOJE: theme.COLORS["accent"],
    at.PROXIMOS_DIAS: theme.COR_TEXTO_APOIO_CLARO,
}

ROTULO_FAIXA = {
    at.ATRASADA: "ATRASADO",
    at.TRAVADA: "TRAVADA",
    at.DEVERIA_TER_COMECADO: "DEVERIA TER COMEÇADO",
    at.EM_ANDAMENTO: "EM ANDAMENTO",
    at.COMECA_HOJE: "COMEÇA HOJE",
    at.PROXIMOS_DIAS: "PRÓXIMOS 7 DIAS",
}

EXPLICACAO_FAIXA = {
    at.ATRASADA: "a previsão de término já passou",
    at.TRAVADA: "começou e parou; precisa de alguém para destravar",
    at.DEVERIA_TER_COMECADO: "a data de início passou e ninguém começou",
    at.EM_ANDAMENTO: "alguém está tocando agora",
    at.COMECA_HOJE: "entra na fila de hoje",
    at.PROXIMOS_DIAS: "para se preparar",
}

# Criticidade 1 a 5 -> cor da barra lateral. A escala vai do neutro ao
# vermelho, para que "muito crítico" salte sem precisar ler o número.
COR_CRITICIDADE = {
    5: "#D32F2F",
    4: "#FF6F3C",
    3: "#FFA726",
    2: "#4DA3A9",
    1: "#5A5A5A",
}
COR_CRITICIDADE_PADRAO = "#3A3A3A"

# CTkLabel sem `text_color`: o texto do tema (gray84).
_COR_TEXTO = estilo.cinza_tk("gray84")
# `wraplength` dos rótulos de lá.
_QUEBRA_ERRO = 740
_QUEBRA_CARTAO = 560


def _cor_da_criticidade(valor) -> str:
    try:
        return COR_CRITICIDADE.get(int(valor or 0), COR_CRITICIDADE_PADRAO)
    except (TypeError, ValueError):
        return COR_CRITICIDADE_PADRAO


def _caixa(layout, item, *, padx=(0, 0), pady=(0, 0), horizontal: bool = False):
    """`pack(padx=, pady=)`: `item` (widget ou layout) numa caixa com essas margens."""
    caixa = QHBoxLayout() if horizontal else QVBoxLayout()
    caixa.setContentsMargins(padx[0], pady[0], padx[1], pady[1])
    caixa.setSpacing(0)
    if isinstance(item, QWidget):
        caixa.addWidget(item)
    elif item is not None:
        caixa.addLayout(item)
    layout.addLayout(caixa)
    return caixa


def montar(parent, gavetas, quando: str, erro: str | None = None) -> None:
    """Desenha o mural dentro de `parent` (que já tem um QVBoxLayout).

    Função solta, não método de janela: se um dia o mural voltar para a Home
    ou for para outro lugar, nada aqui muda.
    """
    layout = parent.layout()
    if erro:
        _caixa(layout, blocos.rotulo_tk(erro, theme.FONTE_CORPO, theme.COLORS["danger"], quebra=_QUEBRA_ERRO),
               padx=(14, 14), pady=(14, 14))
        return

    total = at.total_do_mural(gavetas)

    cabecalho = QHBoxLayout()
    cabecalho.setSpacing(0)
    cabecalho.addWidget(blocos.rotulo_tk(quando, theme.FONTE_SECAO, theme.COLORS["text_light"]))
    cabecalho.addSpacing(12)
    cabecalho.addWidget(blocos.rotulo_tk(f"{total} atividade(s) pedindo atenção",
                                theme.FONTE_CORPO_MIUDO, theme.COR_TEXTO_APOIO))
    cabecalho.addStretch()
    _caixa(layout, cabecalho, padx=(14, 14), pady=(4, 12))

    if total == 0:
        _caixa(layout, blocos.rotulo_tk("Nada pendente para hoje nem para os próximos dias.",
                               theme.FONTE_SUBTITULO, theme.COLORS["accent"]),
               padx=(14, 14), pady=(24, 24))
        return

    for faixa in at.FAIXAS:
        itens = gavetas.get(faixa) or []
        if not itens:
            continue
        _faixa(layout, faixa, itens)


def _faixa(layout, faixa, itens) -> None:
    cor = COR_FAIXA[faixa]

    # Cabeçalho da faixa: contador GRANDE à esquerda, rótulo e explicação à
    # direita. O número vem primeiro porque é o que se lê de relance.
    barra = QHBoxLayout()
    barra.setSpacing(0)
    barra.addWidget(blocos.rotulo_tk(str(len(itens)), ("Roboto", 30, "bold"), cor, largura=48, direita=True),
                    0, Qt.AlignmentFlag.AlignVCenter)
    barra.addSpacing(10)
    textos = QVBoxLayout()
    textos.setSpacing(0)
    textos.addWidget(blocos.rotulo_tk(ROTULO_FAIXA[faixa], ("Roboto", 14, "bold"), cor))
    textos.addWidget(blocos.rotulo_tk(EXPLICACAO_FAIXA[faixa], theme.FONTE_CORPO_MIUDO, theme.COR_TEXTO_APOIO))
    barra.addLayout(textos)
    barra.addStretch()
    _caixa(layout, barra, padx=(14, 14), pady=(16, 6))

    # Régua fina na cor da faixa, separando o cabeçalho dos cartões.
    regua = QFrame(objectName="regua_faixa")
    regua.setFixedHeight(2)
    regua.setStyleSheet(f"#regua_faixa {{ background: {estilo.cinza_tk(cor)}; border: none; }}")
    _caixa(layout, regua, padx=(14, 14), pady=(0, 6))

    for item in itens:
        _cartao(layout, item, faixa)


def _cartao(layout, item, faixa) -> None:
    # Lá: grid com a barra de cor `sticky="ns"` -- ela acompanha a altura do
    # texto. Aqui a linha é horizontal e a barra estica na altura dela.
    linha = QWidget(objectName="linha_cartao")
    grade = QHBoxLayout(linha)
    grade.setContentsMargins(0, 0, 0, 0)
    grade.setSpacing(0)

    # A BARRA DE CRITICIDADE: uma coluna de cor à esquerda. É o elemento mais
    # visual do mural -- dá para varrer a lista só pelas cores e achar o que é
    # grave, sem ler uma palavra.
    barra = QFrame(objectName="barra_criticidade")
    barra.setFixedWidth(6)
    barra.setStyleSheet(f"#barra_criticidade {{ background: {_cor_da_criticidade(item.get('criticidade'))};"
                        " border: none; border-radius: 3px; }")
    grade.addWidget(barra)
    grade.addSpacing(8)

    corpo = QFrame(objectName="corpo_cartao")
    corpo.setStyleSheet(f"#corpo_cartao {{ background: {theme.COR_CARTAO}; border-radius: 6px; }}")
    grade.addWidget(corpo, 1)
    coluna = QVBoxLayout(corpo)
    coluna.setContentsMargins(0, 0, 0, 0)
    coluna.setSpacing(0)

    # O GRUPO (nível 1), acima da descrição e em corpo menor: lê-se primeiro
    # a frente, depois a tarefa.
    if item.get("_grupo"):
        _caixa(coluna, blocos.rotulo_tk(str(item["_grupo"]), ("Roboto", 11, "bold"), theme.COR_TEXTO_APOIO_CLARO,
                               quebra=_QUEBRA_CARTAO),
               padx=(10, 10), pady=(8, 0), horizontal=True).addStretch()

    topo = QHBoxLayout()
    topo.setSpacing(0)
    topo.addWidget(blocos.rotulo_tk(str(item.get("descricao") or "(sem descrição)"), theme.FONTE_CORPO,
                           _COR_TEXTO, quebra=_QUEBRA_CARTAO), 0, Qt.AlignmentFlag.AlignVCenter)
    topo.addStretch()

    # O PRAZO, à direita, em duas alturas: a frase relativa ("venceu há 4 dias",
    # na cor da faixa) responde "corre?"; a data ("término 11/09/26"), "para
    # quando?". As duas frases vêm PRONTAS do serviço.
    prazos = QVBoxLayout()
    prazos.setSpacing(0)
    prazos.addWidget(blocos.rotulo_tk(at.frase_do_prazo(faixa, item.get("_dias")), ("Roboto", 12, "bold"),
                             COR_FAIXA[faixa], direita=True), 0, Qt.AlignmentFlag.AlignRight)
    if item.get("_termino"):
        prazos.addWidget(blocos.rotulo_tk(str(item["_termino"]), theme.FONTE_CORPO_MIUDO, theme.COR_TEXTO_APOIO,
                                 direita=True), 0, Qt.AlignmentFlag.AlignRight)
    topo.addSpacing(10)
    topo.addLayout(prazos)
    _caixa(coluna, topo, padx=(10, 10), pady=(2 if item.get("_grupo") else 8, 2))

    partes = []
    if item.get("com_quem"):
        partes.append(f"com {item['com_quem']}")
    if item.get("status"):
        partes.append(str(item["status"]))
    if item.get("criticidade"):
        partes.append(f"criticidade {item['criticidade']}")
    if partes:
        _caixa(coluna, blocos.rotulo_tk("   ·   ".join(partes), theme.FONTE_CORPO_MIUDO, theme.COR_TEXTO_APOIO_CLARO),
               padx=(10, 10), pady=(0, 8), horizontal=True).addStretch()

    _caixa(layout, linha, padx=(14, 14), pady=(3, 3))
