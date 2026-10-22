"""O mural de atividades em Qt -- o desenho do mural da interface antiga (que
saiu do SIG-FT em 2026-10-15).

A regra (que atividade cai em que faixa, as frases de prazo) mora em
`services/atividades.py` e se prova sem interface; aqui só o desenho, o mesmo
da interface antiga: contador grande na faixa, barra colorida da criticidade à
esquerda de cada cartão, o prazo em destaque à direita, faixas em ordem de
urgência.

As tabelas de rótulo e explicação eram CÓPIA das de lá; o teste
`test_desenho_do_mural_igual_ao_da_home_antiga` trava os valores, e
`tests/test_mural_nomes_do_servico.py` cobra as faixas. As CORES, desde
2026-10-20, são da folha (`estilo.COR_DA_FAIXA`/`COR_DA_CRITICIDADE`, uma por
tema): aqui cada peça só diz a faixa ou a criticidade, por propriedade.

As medidas são as do `pack` de lá: cada CTkLabel tem pelo menos 28 px de altura
(o `height` padrão) com o texto centrado, e os `pady` de vizinhos SOMAM -- por
isso cada peça entra numa caixa com as margens dela, num layout sem espaçamento.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QVBoxLayout, QWidget

from sigft.app import theme
from sigft.app.idioma import marcar, t
from sigft.app_qt import estilo
from sigft.app_qt.widgets import blocos
from sigft.services import atividades as at

# A propriedade `faixa` de cada faixa: o seletor `QLabel[faixa=...]` e
# `#regua_faixa[faixa=...]` da folha, com a cor de cada tema
# (`estilo.COR_DA_FAIXA`). Roxo na travada, vermelho, laranja, verde-água,
# verde e o texto suave nas demais.
COR_FAIXA = {
    at.ATRASADA: "atrasada",
    at.TRAVADA: "travada",
    at.DEVERIA_TER_COMECADO: "deveria_ter_comecado",
    at.EM_ANDAMENTO: "em_andamento",
    at.COMECA_HOJE: "comeca_hoje",
    at.PROXIMOS_DIAS: "proximos_dias",
}

# [2026-10-22] Marcados e traduzidos onde vão à tela (`_faixa`). "ATRASADO" e
# "TRAVADA" também: a guarda não vê palavra única em maiúsculas.
ROTULO_FAIXA = {
    at.ATRASADA: marcar("ATRASADO"),
    at.TRAVADA: marcar("TRAVADA"),
    at.DEVERIA_TER_COMECADO: marcar("DEVERIA TER COMEÇADO"),
    at.EM_ANDAMENTO: marcar("EM ANDAMENTO"),
    at.COMECA_HOJE: marcar("COMEÇA HOJE"),
    at.PROXIMOS_DIAS: marcar("PRÓXIMOS 7 DIAS"),
}

EXPLICACAO_FAIXA = {
    at.ATRASADA: marcar("a previsão de término já passou"),
    at.TRAVADA: marcar("começou e parou; precisa de alguém para destravar"),
    at.DEVERIA_TER_COMECADO: marcar("a data de início passou e ninguém começou"),
    at.EM_ANDAMENTO: marcar("alguém está tocando agora"),
    at.COMECA_HOJE: marcar("entra na fila de hoje"),
    at.PROXIMOS_DIAS: marcar("para se preparar"),
}

# Criticidade 1 a 5 -> a barra lateral (`#barra_criticidade[criticidade=...]`
# na folha). A escala vai do neutro ao vermelho, para que "muito crítico" salte
# sem precisar ler o número; sem criticidade (ou ilegível), a cor da borda.
COR_CRITICIDADE = {nivel: estilo.COR_DA_CRITICIDADE.get(nivel, "texto_suave") for nivel in range(1, 6)}
COR_CRITICIDADE_PADRAO = "borda"
# `wraplength` dos rótulos de lá.
_QUEBRA_ERRO = 740
_QUEBRA_CARTAO = 560


def _nivel_da_criticidade(valor) -> int:
    """1 a 5, ou 0 quando a planilha não traz um desses números."""
    try:
        nivel = int(valor or 0)
    except (TypeError, ValueError):
        return 0
    return nivel if nivel in COR_CRITICIDADE else 0


def _cor_da_criticidade(valor) -> str:
    """A cor da barra (o token `texto_suave`/`borda` nos níveis que seguem o tema)."""
    return COR_CRITICIDADE.get(_nivel_da_criticidade(valor), COR_CRITICIDADE_PADRAO)


def _na_faixa(rotulo, faixa):
    """O rótulo na cor da faixa (`QLabel[faixa=...]` da folha)."""
    rotulo.setProperty("faixa", COR_FAIXA[faixa])
    return rotulo


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
        _caixa(layout, blocos.rotulo_tk(erro, theme.FONTE_CORPO, "erro", quebra=_QUEBRA_ERRO),
               padx=(14, 14), pady=(14, 14))
        return

    total = at.total_do_mural(gavetas)

    cabecalho = QHBoxLayout()
    cabecalho.setSpacing(0)
    cabecalho.addWidget(blocos.rotulo_tk(quando, theme.FONTE_SECAO))
    cabecalho.addSpacing(12)
    cabecalho.addWidget(blocos.rotulo_tk(t("{total} atividade(s) pedindo atenção", total=total),
                                theme.FONTE_CORPO_MIUDO, "legenda"))
    cabecalho.addStretch()
    _caixa(layout, cabecalho, padx=(14, 14), pady=(4, 12))

    if total == 0:
        _caixa(layout, blocos.rotulo_tk(t("Nada pendente para hoje nem para os próximos dias."),
                               theme.FONTE_SUBTITULO, "ok"),
               padx=(14, 14), pady=(24, 24))
        return

    for faixa in at.FAIXAS:
        itens = gavetas.get(faixa) or []
        if not itens:
            continue
        _faixa(layout, faixa, itens)


def _faixa(layout, faixa, itens) -> None:

    # Cabeçalho da faixa: contador GRANDE à esquerda, rótulo e explicação à
    # direita. O número vem primeiro porque é o que se lê de relance.
    barra = QHBoxLayout()
    barra.setSpacing(0)
    barra.addWidget(_na_faixa(blocos.rotulo_tk(str(len(itens)), ("Roboto", 30, "bold"), largura=48,
                                               direita=True), faixa),
                    0, Qt.AlignmentFlag.AlignVCenter)
    barra.addSpacing(10)
    textos = QVBoxLayout()
    textos.setSpacing(0)
    textos.addWidget(_na_faixa(blocos.rotulo_tk(t(ROTULO_FAIXA[faixa]), ("Roboto", 14, "bold")), faixa))
    textos.addWidget(blocos.rotulo_tk(t(EXPLICACAO_FAIXA[faixa]), theme.FONTE_CORPO_MIUDO, "legenda"))
    barra.addLayout(textos)
    barra.addStretch()
    _caixa(layout, barra, padx=(14, 14), pady=(16, 6))

    # Régua fina na cor da faixa, separando o cabeçalho dos cartões.
    regua = QFrame(objectName="regua_faixa")
    regua.setFixedHeight(2)
    regua.setProperty("faixa", COR_FAIXA[faixa])
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
    barra.setProperty("criticidade", str(_nivel_da_criticidade(item.get("criticidade"))))
    grade.addWidget(barra)
    grade.addSpacing(8)

    corpo = QFrame(objectName="corpo_cartao")   # a superfície, de cantos 6 (folha)
    grade.addWidget(corpo, 1)
    coluna = QVBoxLayout(corpo)
    coluna.setContentsMargins(0, 0, 0, 0)
    coluna.setSpacing(0)

    # O GRUPO (nível 1), acima da descrição e em corpo menor: lê-se primeiro
    # a frente, depois a tarefa.
    if item.get("_grupo"):
        _caixa(coluna, blocos.rotulo_tk(str(item["_grupo"]), ("Roboto", 11, "bold"), "legenda",
                               quebra=_QUEBRA_CARTAO),
               padx=(10, 10), pady=(8, 0), horizontal=True).addStretch()

    topo = QHBoxLayout()
    topo.setSpacing(0)
    topo.addWidget(blocos.rotulo_tk(str(item.get("descricao") or t("(sem descrição)")), theme.FONTE_CORPO,
                           quebra=_QUEBRA_CARTAO), 0, Qt.AlignmentFlag.AlignVCenter)
    topo.addStretch()

    # O PRAZO, à direita, em duas alturas: a frase relativa ("venceu há 4 dias",
    # na cor da faixa) responde "corre?"; a data ("término 11/09/26"), "para
    # quando?". As duas frases vêm PRONTAS do serviço.
    prazos = QVBoxLayout()
    prazos.setSpacing(0)
    prazos.addWidget(_na_faixa(blocos.rotulo_tk(at.frase_do_prazo(faixa, item.get("_dias")),
                                                ("Roboto", 12, "bold"), direita=True), faixa),
                     0, Qt.AlignmentFlag.AlignRight)
    if item.get("_termino"):
        prazos.addWidget(blocos.rotulo_tk(str(item["_termino"]), theme.FONTE_CORPO_MIUDO, "legenda",
                                 direita=True), 0, Qt.AlignmentFlag.AlignRight)
    topo.addSpacing(10)
    topo.addLayout(prazos)
    _caixa(coluna, topo, padx=(10, 10), pady=(2 if item.get("_grupo") else 8, 2))

    partes = []
    if item.get("com_quem"):
        partes.append(t("com {pessoa}", pessoa=item["com_quem"]))
    if item.get("status"):
        partes.append(str(item["status"]))
    if item.get("criticidade"):
        partes.append(t("criticidade {nivel}", nivel=item["criticidade"]))
    if partes:
        _caixa(coluna, blocos.rotulo_tk("   ·   ".join(partes), theme.FONTE_CORPO_MIUDO, "legenda"),
               padx=(10, 10), pady=(0, 8), horizontal=True).addStretch()

    _caixa(layout, linha, padx=(14, 14), pady=(3, 3))
