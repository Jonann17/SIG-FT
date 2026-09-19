"""O mural de atividades — o desenho.

[2026-09-03] Pedido do usuário: *"que ela seja visual, e funcione como um
apontamento do que é preciso fazer naquele dia, ou o que deveria estar sendo
feito, e algumas a frente também"*.

A regra (que atividade cai em que faixa) mora em `services/atividades.py` e se
prova sem interface. Aqui só o desenho.

O que torna isto "visual" dentro do CustomTkinter
--------------------------------------------------
Não há gráfico nem timeline — o CustomTkinter não os tem, e o usuário sabe
disso (*"depende da capacidade do front end atual"*). O que dá para fazer, e
foi feito:

* **contador grande na faixa** — o número é lido antes do texto;
* **barra colorida à esquerda de cada cartão**, com a cor da CRITICIDADE: uma
  coluna de cor que se lê de relance, sem ler palavra nenhuma;
* **o prazo em destaque** ("venceu há 4 dias", "começa amanhã") em vez da data
  crua, que exigiria o leitor fazer a conta;
* **faixas em ordem de urgência**, de modo que o que exige ação hoje esteja no
  alto e o "o que vem a seguir" no fim.
"""
from __future__ import annotations

import customtkinter as ctk

from sigft.app import theme
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


def _cor_da_criticidade(valor) -> str:
    try:
        return COR_CRITICIDADE.get(int(valor or 0), COR_CRITICIDADE_PADRAO)
    except (TypeError, ValueError):
        return COR_CRITICIDADE_PADRAO


def montar(parent, gavetas, quando: str, erro: str | None = None):
    """Desenha o mural dentro de `parent`.

    Função solta, não método de janela: se um dia o mural voltar para a Home
    ou for para outro lugar, nada aqui muda.
    """
    if erro:
        ctk.CTkLabel(
            parent, text=erro, font=theme.FONTE_CORPO,
            text_color=theme.COLORS["danger"], justify="left", wraplength=740,
        ).pack(anchor="w", padx=14, pady=14)
        return

    total = at.total_do_mural(gavetas)

    cabecalho = ctk.CTkFrame(parent, fg_color="transparent")
    cabecalho.pack(fill="x", padx=14, pady=(4, 12))
    ctk.CTkLabel(
        cabecalho, text=quando, font=theme.FONTE_SECAO,
        text_color=theme.COLORS["text_light"],
    ).pack(side="left")
    ctk.CTkLabel(
        cabecalho, text=f"{total} atividade(s) pedindo atenção",
        font=theme.FONTE_CORPO_MIUDO, text_color=theme.COR_TEXTO_APOIO,
    ).pack(side="left", padx=(12, 0))

    if total == 0:
        ctk.CTkLabel(
            parent, text="Nada pendente para hoje nem para os próximos dias.",
            font=theme.FONTE_SUBTITULO, text_color=theme.COLORS["accent"],
        ).pack(anchor="w", padx=14, pady=24)
        return

    for faixa in at.FAIXAS:
        itens = gavetas.get(faixa) or []
        if not itens:
            continue
        _faixa(parent, faixa, itens)


def _faixa(parent, faixa, itens):
    cor = COR_FAIXA[faixa]

    # Cabeçalho da faixa: contador GRANDE à esquerda, rótulo e explicação à
    # direita. O número vem primeiro porque é o que se lê de relance.
    barra = ctk.CTkFrame(parent, fg_color="transparent")
    barra.pack(fill="x", padx=14, pady=(16, 6))

    ctk.CTkLabel(
        barra, text=str(len(itens)), font=("Roboto", 30, "bold"), text_color=cor,
        width=48, anchor="e",
    ).pack(side="left")

    textos = ctk.CTkFrame(barra, fg_color="transparent")
    textos.pack(side="left", padx=(10, 0))
    ctk.CTkLabel(
        textos, text=ROTULO_FAIXA[faixa], font=("Roboto", 14, "bold"),
        text_color=cor, anchor="w",
    ).pack(anchor="w")
    ctk.CTkLabel(
        textos, text=EXPLICACAO_FAIXA[faixa], font=theme.FONTE_CORPO_MIUDO,
        text_color=theme.COR_TEXTO_APOIO, anchor="w",
    ).pack(anchor="w")

    # Régua fina na cor da faixa, separando o cabeçalho dos cartões.
    ctk.CTkFrame(parent, height=2, fg_color=cor).pack(fill="x", padx=14, pady=(0, 6))

    for item in itens:
        _cartao(parent, item, faixa)


def _cartao(parent, item, faixa):
    # ⚠️ `height=1` nos dois frames, e o layout por GRID.
    #
    # `CTkFrame` nasce com `height=200`. Com `pack(fill="y")`, essa altura
    # padrão vira o piso do cartão: na primeira montagem cada atividade ocupava
    # ~250 px de tela, quase tudo vazio, e três cartões já enchiam a janela.
    # `height=1` deixa o conteúdo mandar na altura.
    #
    # O grid (em vez de pack) é o que faz a barra de cor acompanhar a altura do
    # texto: `sticky="ns"` estica a barra até a altura da linha, e a linha é
    # medida pelo texto.
    linha = ctk.CTkFrame(parent, fg_color="transparent", height=1)
    linha.pack(fill="x", padx=14, pady=3)
    linha.grid_columnconfigure(1, weight=1)

    # A BARRA DE CRITICIDADE: uma coluna de cor à esquerda. É o elemento mais
    # visual do mural -- dá para varrer a lista só pelas cores e achar o que é
    # grave, sem ler uma palavra.
    ctk.CTkFrame(
        linha, width=6, height=1,
        fg_color=_cor_da_criticidade(item.get("criticidade")),
        corner_radius=3,
    ).grid(row=0, column=0, sticky="ns", padx=(0, 8))

    corpo = ctk.CTkFrame(linha, fg_color=theme.COR_CARTAO, corner_radius=6, height=1)
    corpo.grid(row=0, column=1, sticky="ew")

    # O GRUPO (nível 1), acima da descrição e em corpo menor: lê-se primeiro
    # a frente, depois a tarefa. Vai ACIMA e não na linha de rodapé porque a
    # pergunta que ele responde ("de qual grupo é isto?") vem ANTES de ler a
    # atividade, não depois.
    if item.get("_grupo"):
        ctk.CTkLabel(
            corpo, text=str(item["_grupo"]), font=("Roboto", 11, "bold"),
            text_color=theme.COR_TEXTO_APOIO_CLARO, anchor="w",
            justify="left", wraplength=560,
        ).pack(anchor="w", padx=10, pady=(8, 0))

    topo = ctk.CTkFrame(corpo, fg_color="transparent")
    topo.pack(fill="x", padx=10, pady=(2 if item.get("_grupo") else 8, 2))

    ctk.CTkLabel(
        topo, text=str(item.get("descricao") or "(sem descrição)"),
        font=theme.FONTE_CORPO, justify="left", wraplength=560, anchor="w",
    ).pack(side="left", fill="x", expand=True)

    # O PRAZO, à direita, em duas alturas:
    #
    #   venceu há 4 dias          <- a urgência, na cor da faixa
    #   término 11/09/26          <- para quando é, em corpo miúdo
    #
    # A frase relativa responde "corre?"; a data responde "para quando?".
    # Antes só havia a primeira, e em faixa de início ("era para começar
    # ontem") dava para ler o cartão inteiro sem descobrir o prazo final.
    #
    # As duas frases vêm PRONTAS do serviço (`_dias`, `_termino`), como
    # `_grupo`: a data de hoje e a regra de quando contar os dias moram lá,
    # onde se testam sem abrir janela.
    prazos = ctk.CTkFrame(topo, fg_color="transparent")
    prazos.pack(side="right", padx=(10, 0))

    ctk.CTkLabel(
        prazos, text=at.frase_do_prazo(faixa, item.get("_dias")),
        font=("Roboto", 12, "bold"), text_color=COR_FAIXA[faixa], anchor="e",
    ).pack(anchor="e")

    if item.get("_termino"):
        ctk.CTkLabel(
            prazos, text=str(item["_termino"]), font=theme.FONTE_CORPO_MIUDO,
            text_color=theme.COR_TEXTO_APOIO, anchor="e",
        ).pack(anchor="e")

    partes = []
    if item.get("com_quem"):
        partes.append(f"com {item['com_quem']}")
    if item.get("status"):
        partes.append(str(item["status"]))
    if item.get("criticidade"):
        partes.append(f"criticidade {item['criticidade']}")
    if partes:
        ctk.CTkLabel(
            corpo, text="   ·   ".join(partes), font=theme.FONTE_CORPO_MIUDO,
            text_color=theme.COR_TEXTO_APOIO_CLARO, anchor="w",
        ).pack(anchor="w", padx=10, pady=(0, 8))
