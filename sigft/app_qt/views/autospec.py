"""Tela "AutoSpec AI" na interface Qt.

A porta Qt da tela da interface antiga (que saiu do SIG-FT em 2026-10-15,
com tudo o que tinha): preenche as especificações
técnicas da ficha a partir de manuais e datasheets, com IA, e tem a seção de
*Conferência de documentos*, que abre no navegador os documentos que a IA
marcou como duvidosos.

⚠️ Módulo da frente do Rafael (ver `docs/refatoracao/TRABALHO_PARALELO.md`
§3.1). A lógica mora em `sigft/services/autospec.py` (o `AutoSpecCore`) e em
`sigft/services/autospec_conferencia.py` (a conferência e o `.txt`); aqui só
há widget. O bloco da conferência viajou INTEIRO, com os mesmos 6 métodos e 7
atributos da tela antiga (`_build_conferencia`, `_conferencia_mostrar`,
`_conferencia_salvar`, `_conferencia_importar`, `_conferencia_processar`,
`_conferencia_worker`; `conferencia`, `marcados_conf`, `frm_conf`,
`lista_conf`, `btn_conf`, `btn_conf_salvar`, `btn_conf_importar`), e com as
três coisas de fora da classe: `webbrowser`, o import de
`autospec_conferencia as conferencia_txt` no topo (fora do carregamento
preguiçoso, de propósito) e o papel `aviso` da folha (era a cor de aviso
escrita na tela, até 2026-10-20). `_novo_core` continua sendo a
ÚNICA construção do `AutoSpecCore`, usada pelos dois workers.

Os invariantes que `tests/test_autospec_conferencia_tela.py` provava na tela
antiga ele prova aqui, por AST (e `tests/test_qt_tela_autospec.py` os prova
rodando a tela): o fim
do lote MOSTRA a lista nova antes de SALVAR o `.txt` automático; a seção nunca
se esconde (o IMPORTAR existe para quem acabou de abrir o app); processar exige
o `_STATUS_PMIB`; o salvamento automático não abre caixa nenhuma.

O que mudou da tela antiga é só como as threads falam com a interface: lá `messagebox`,
`btn.configure`, `update_queue_ui` e `_conferencia_mostrar` eram chamados de
dentro da thread (proibido no Tk); aqui o worker só loga e usa `self.avisar` e
`interface.na_interface`, e os botões passam por `iniciar_tarefa`. A fila, o
`_STATUS_PMIB` e o interruptor do fornecedor são lidos NO CLIQUE.
"""
from __future__ import annotations

import html
import os
import webbrowser

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QMessageBox, QSizePolicy, QWidget

from sigft.app import backends, ia_por_modulo
from sigft.app.idioma import t
from sigft.app_qt import estilo, file_dialogs, icones, interface
from sigft.app_qt.widgets import blocos, controles
from sigft.app_qt.widgets.arrastar import Arrastavel
from sigft.app_qt.widgets.como_funciona import instalar_como_funciona
from sigft.app_qt.widgets.ia_do_modulo import instalar_configurar_ia
from sigft.app_qt.widgets.module_frame import ModuleFrame
from sigft.services import autospec_conferencia as conferencia_txt

# CTkTextbox(height=120) no lugar do console padrão de 150.
ALTURA_CONSOLE = 120
# O CTkScrollableFrame: conteúdo 6 px dentro do quadro, barra 1 px antes da borda,
# e o que rola some 6 px antes da borda (`blocos.area_rolavel(barra_sempre_visivel=True)`:
# na fila e na conferência, as linhas ficam dentro do retângulo escuro de cantos redondos).
RECUO_ROLAGEM = 6
# Os dois quadros roláveis de dentro (fila e conferência): mais fundos que o
# cartão (o `fundo` do tema, `area_rolavel(fundo="tela")`) e 212 de altura. Lá
# pedem 150 e 190, mas a CTkScrollbar vertical mede 200 e manda na linha do
# grid: 200 + 2 * 6 (medido nas duas).
ALTURA_QUADRO_INTERNO = 212
# Rótulos com `wraplength`: Roboto 11 no Tk tem 14 px por linha (3 linhas =
# 42, medido); o Qt usa 13. A altura mínima é a medida lá (3 linhas).
ALTURA_LINHA_PEQUENA = 14
ALTURA_TEXTO_3_LINHAS = 3 * ALTURA_LINHA_PEQUENA
QUEBRA_TEXTOS = 680
QUEBRA_CONFERENCIA_VAZIA = 650
# CTkCheckBox(text="", width=24, checkbox_width=18, checkbox_height=18): a
# caixa de 18, o vão de 6 e o rótulo vazio de 1 px -- 25 x 24 medidos.
LADO_CAIXA_CONF = 18
TAMANHO_CAIXA_CONF = QSize(25, 24)


def _rotulo(texto: str, *, tamanho: int = 13, negrito: bool = False, papel: str | None = None,
            alinhar: str = "esquerda") -> QLabel:
    """CTkLabel de uma linha, `anchor="w"`, 28 px de altura.

    Texto PURO: estes rótulos mostram dado da pessoa (nome de arquivo, material),
    e no formato automático o QLabel leria um "<b>...</b>" como HTML."""
    r = blocos.rotulo(texto, tamanho=tamanho, negrito=negrito, papel=papel, alinhar=alinhar)
    r.setTextFormat(Qt.TextFormat.PlainText)
    r.setWordWrap(False)
    r.setFixedHeight(blocos.ALTURA_MINIMA_ROTULO)
    return r


def _pintar(rotulo: QLabel, papel: str | None) -> None:
    """O `configure(text_color=...)` do CTkLabel: o papel de texto da folha
    (`legenda`), ou o texto comum com `None`."""
    estilo.definir_papel(rotulo, papel)


def _texto_quebrado(texto: str, *, quebra: int, papel: str | None = None, tamanho: int = 11) -> QLabel:
    """CTkLabel com `wraplength` e `justify="left"`: quebra em `quebra` px, com
    a linha de 14 px do Tk. Texto FIXO da tela (vai como HTML)."""
    r = QLabel()
    r.setTextFormat(Qt.TextFormat.RichText)
    corpo = html.escape(texto, quote=False).replace("\n", "<br>")
    r.setText(f'<div style="line-height: {ALTURA_LINHA_PEQUENA}px;">{corpo}</div>')
    r.setWordWrap(True)
    r.setFixedWidth(quebra)
    # A altura de lá (3 linhas). Com a fonte do Qt, mais estreita, o mesmo texto
    # pode caber em 2: o resto da tela não sobe por isso.
    r.setMinimumHeight(ALTURA_TEXTO_3_LINHAS)
    r.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
    if papel:
        r.setProperty("papel", papel)
    r.setStyleSheet(f"font-size: {tamanho}px; background: transparent;")
    return r


def _cartao(corpo, *, borda: str | None = None, fim: int = 15):
    """O cartão (`blocos.cartao`): peças com padx=15, título com pady 10.

    `borda` = o `border_width=1` da tela antiga, pelo papel: "destaque" (a
    `primaria`) ou "aviso" -- regra `#cartao[borda=...]` da folha. Lá a borda é desenhada
    no canvas e não empurra os filhos; aqui ela come 1 px do conteúdo, que sai
    das margens."""
    layout = blocos.cartao(corpo)
    quadro = layout.parentWidget()
    folga = 0
    if borda:
        quadro.setProperty("borda", borda)
        folga = 1
    layout.setContentsMargins(15 - folga, 10 - folga, 15 - folga, fim - folga)
    layout.setSpacing(0)
    return quadro, layout


def _recuado(layout, widget, esquerda: int, direita: int = 0, *, natural: bool = False) -> None:
    """O `padx` de um filho do `pack`: o widget entre as margens. `natural` =
    sem `fill="x"` (fica com a própria largura, encostado à esquerda)."""
    linha = QHBoxLayout()
    linha.setContentsMargins(esquerda, 0, direita, 0)
    linha.setSpacing(0)
    if natural:
        linha.addWidget(widget, 0, Qt.AlignmentFlag.AlignLeft)
        linha.addStretch()
    else:
        linha.addWidget(widget)
    layout.addLayout(linha)


def _em_caixa(widget, esquerda: int, direita: int) -> QWidget:
    """O widget dentro de um QWidget com margens -- para as listas que se
    refazem (o que entra nelas sai inteiro com `_esvaziar`)."""
    caixa = QWidget()
    linha = QHBoxLayout(caixa)
    linha.setContentsMargins(esquerda, 0, direita, 0)
    linha.setSpacing(0)
    linha.addWidget(widget)
    return caixa


def _esvaziar(layout) -> None:
    """O `for w in frame.winfo_children(): w.destroy()` de lá."""
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        if widget is not None:
            widget.setParent(None)
            widget.deleteLater()


def _sem_largura_minima(widget) -> None:
    """A largura do texto não manda no layout: um nome de arquivo (ou material)
    comprido é cortado no fim, em vez de empurrar o botão ao lado para fora do
    quadro -- ou alargar a lista além da barra de rolagem."""
    widget.setSizePolicy(QSizePolicy.Policy.Ignored, widget.sizePolicy().verticalPolicy())


class _DoisBotoesQueCrescem(QWidget):
    """Dois botões com `pack(side="left", fill="x", expand=True)` e padx (0, 5)
    e (5, 0).

    O Tk dá a cada um o que ele PEDE e reparte a SOBRA igual (lá 418 e 432 para
    pedidos de 171 e 185); o QHBoxLayout com stretch repartiria a largura toda
    (425 e 425), e o segundo botão andaria 7 px.
    """

    VAO = 10

    def __init__(self, esquerdo, direito, *, altura: int) -> None:
        super().__init__()
        self.botoes = (esquerdo, direito)
        for botao in self.botoes:
            botao.setParent(self)
        self.setFixedHeight(altura)

    def sizeHint(self) -> QSize:  # noqa: N802 -- nome do Qt
        esquerdo, direito = self.botoes
        return QSize(esquerdo.sizeHint().width() + self.VAO + direito.sizeHint().width(), self.height())

    def minimumSizeHint(self) -> QSize:  # noqa: N802 -- nome do Qt
        # O pedido do Tk: abaixo disso o texto dos botões seria cortado.
        return self.sizeHint()

    def resizeEvent(self, evento) -> None:  # noqa: N802 -- nome do Qt
        super().resizeEvent(evento)
        self.arrumar()

    def showEvent(self, evento) -> None:  # noqa: N802 -- nome do Qt
        super().showEvent(evento)
        self.arrumar()

    def arrumar(self) -> None:
        esquerdo, direito = self.botoes
        pedido_e, pedido_d = esquerdo.sizeHint().width(), direito.sizeHint().width()
        sobra = max(self.width() - self.VAO - pedido_e - pedido_d, 0)
        largura_e = pedido_e + sobra // 2
        esquerdo.setGeometry(0, 0, largura_e, self.height())
        direito.setGeometry(largura_e + self.VAO, 0, self.width() - largura_e - self.VAO, self.height())


# =============================================================================
# MÓDULO 8: AUTO SPEC AI (INTERFACE GE VERNOVA)
# =============================================================================
class ModuloAutoSpec(ModuleFrame):
    # Arrastar arquivo do Explorer para os botões (2026-10-21, etapa 1b).
    ARRASTAVEIS = (
        Arrastavel("btn_status", "autospec.status_pmib", (".xlsx",)),
        Arrastavel("btn_sheet", "autospec.ficha", (".xlsx",)),
        Arrastavel("btn_refs", "autospec.manuais", (".pdf", ".txt"), varios=True),
        Arrastavel("btn_conf_importar", "autospec.conferencia", (".txt",)),
    )
    def __init__(self, parent=None, controller=None) -> None:
        # Variáveis de Estado
        self.queue: list[dict] = []
        self.temp_sheet = None
        self.temp_refs: list[str] = []
        self.status_pmib_path = None
        self.linhas_fila: list[tuple[QLabel, object]] = []
        self.rotulo_fila_vazia = None
        super().__init__(parent, controller, titulo=t("AutoSpec AI (RAG & Geração)"),
                         altura_console=ALTURA_CONSOLE)

    def _build_ui(self) -> None:
        instalar_como_funciona(self, "AutoSpec")
        instalar_configurar_ia(self, ia_por_modulo.TAREFAS_DA_TELA.get("ModuloAutoSpec", ()))
        # Content: CTkScrollableFrame transparente.
        self.area, corpo = blocos.area_rolavel(self.content_layout, margem=RECUO_ROLAGEM,
                                               barra_sempre_visivel=True)

        # --- SEÇÃO 1: STATUS PMIB ---
        corpo.addSpacing(10)                            # frm_status: pady=10
        self.cartao_status, status = _cartao(corpo)
        self.rotulo_secao1 = _rotulo(t("1. Arquivo de Referência"), tamanho=14, negrito=True,
                                     papel="destaque")
        status.addWidget(self.rotulo_secao1)
        status.addSpacing(10)                           # título (…, 10); a linha: pady=(0, 15)
        linha = QHBoxLayout()
        linha.setContentsMargins(0, 0, 0, 0)
        linha.setSpacing(0)
        self.lbl_status = _rotulo(t("Nenhum _STATUS_PMIB selecionado"), papel="legenda")
        _sem_largura_minima(self.lbl_status)
        linha.addWidget(self.lbl_status, 1)
        self.btn_status = blocos.botao(t("Selecionar _STATUS_PMIB"), variante="cinza", altura=28,
                                       tamanho_fonte=12, largura_minima=estilo.LARGURA_BOTAO_CTK)
        self.btn_status.clicked.connect(self.sel_status)
        linha.addWidget(self.btn_status)
        status.addLayout(linha)

        # --- SEÇÃO 2: MONTADOR DE FILA ---
        corpo.addSpacing(20)                            # frm_status (…, 10) + frm_job (10, …)
        self.cartao_job, job = _cartao(corpo, borda="destaque")
        self.rotulo_secao2 = _rotulo(t("2. Adicionar Tarefa à Fila"), tamanho=14, negrito=True,
                                     papel="destaque")
        job.addWidget(self.rotulo_secao2)

        # A) Ficha Alvo   B) Manuais
        job.addSpacing(15)                              # título (…, 10) + f_sheet (5, …)
        self.lbl_sheet, self.btn_sheet = self._linha_de_arquivo(
            job, t("Ficha: {nome}", nome=t("[Nenhuma]")), t("Selecionar Ficha (.xlsx)"), self.sel_sheet)
        job.addSpacing(10)                              # f_sheet (…, 5) + f_refs (5, …)
        self.lbl_refs, self.btn_refs = self._linha_de_arquivo(
            job, t("Manuais: {n} arquivos", n=0), t("Adic. Manuais (.pdf)"), self.sel_refs)

        # Botão Add
        job.addSpacing(20)                              # f_refs (…, 5) + botão (15, …)
        self.btn_add = blocos.botao(t("Adicionar à Fila"), variante="primario",
                                    altura=28, tamanho_fonte=13, negrito=True)
        # As setas "⬇" das pontas viraram o ícone (Lucide, na cor do tema, 2026-10-20).
        icones.aplicar(self.btn_add, "arrow-down", tamanho=16)
        self.btn_add.clicked.connect(self.add_queue)
        _recuado(job, self.btn_add, 5, 5)               # padx=20 (15 já são do cartão)

        # --- SEÇÃO 3: VISUALIZAÇÃO DA FILA ---
        corpo.addSpacing(20)
        self.cartao_fila, fila = _cartao(corpo)
        self.rotulo_fila = _rotulo(t("Fila de Processamento"), tamanho=14, negrito=True,
                                   papel="destaque")
        fila.addWidget(self.rotulo_fila)
        fila.addSpacing(10)
        # Fundo mais escuro para a lista
        self.queue_frame, self._layout_fila = blocos.area_rolavel(
            fila, fundo="tela", margem=RECUO_ROLAGEM, barra_sempre_visivel=True)
        self.queue_frame.setFixedHeight(ALTURA_QUADRO_INTERNO)
        self.update_queue_ui()

        # --- SEÇÃO 4: EXECUTAR ---
        # Conferencia das respostas do fornecedor (2026-09-28, pedido do
        # Luan). Marcada por padrao; desmarcar e para o lote em que so se
        # quer preencher, e economiza a chamada de IA a mais. O valor vai
        # para um atributo comum pelo sinal (thread da interface), e o
        # clique o entrega aos workers.
        self._conferir_fornecedor = True
        corpo.addSpacing(25)                            # frm_queue (…, 10) + caixa (15, …)
        self.chk_fornecedor = controles.CaixaDeMarcar(
            t("Conferir as respostas do fornecedor contra o datasheet"), tamanho_fonte=13)
        self.chk_fornecedor.setChecked(True)
        self.chk_fornecedor.toggled.connect(self._ao_marcar_conferencia_fornecedor)
        _recuado(corpo, self.chk_fornecedor, 30, natural=True)
        corpo.addSpacing(2)
        self.rotulo_fornecedor = _texto_quebrado(
            t("\"Não se aplica\" que o documento prova vira o valor do documento, em "
              "azul, com a resposta original no comentário da célula. Divergência vai "
              "só para o log: a ficha do fornecedor não é alterada. Usa uma chamada "
              "de IA a mais por ficha que tenha resposta do fornecedor."),
            papel="legenda", quebra=QUEBRA_TEXTOS)
        _recuado(corpo, self.rotulo_fornecedor, 58, natural=True)

        corpo.addSpacing(20)                            # texto (…, 0) + botão (20, …)
        self.btn_run = blocos.botao(t("INICIAR PROCESSAMENTO DA FILA"), variante="acento", altura=50,
                                    tamanho_fonte=15, negrito=True)
        self.btn_run.clicked.connect(self.run_process)
        _recuado(corpo, self.btn_run, 30, 30)

        # --- SEÇÃO 5: CONFERÊNCIA DE DOCUMENTOS ---
        # Bloco AUTOCONTIDO (2026-08-13). Ver `_build_conferencia`.
        corpo.addSpacing(30)                            # botão (…, 20) + frm_conf (10, …)
        self._build_conferencia(corpo)
        corpo.addSpacing(10)                            # frm_conf: pady=10

    def _linha_de_arquivo(self, layout, texto: str, texto_botao: str, acao):
        """Rótulo de legenda à esquerda (fill/expand) e o botão de 180 à direita
        (o cinza escrito à mão lá = a variante "cinza")."""
        linha = QHBoxLayout()
        linha.setContentsMargins(0, 0, 0, 0)
        linha.setSpacing(0)
        rotulo = _rotulo(texto, papel="legenda")
        _sem_largura_minima(rotulo)
        linha.addWidget(rotulo, 1)
        botao = blocos.botao(texto_botao, variante="cinza", altura=28, tamanho_fonte=12,
                             largura_minima=180)
        botao.clicked.connect(acao)
        linha.addWidget(botao)
        layout.addLayout(linha)
        return rotulo, botao

    # =========================================================================
    # CONFERÊNCIA DE DOCUMENTOS DUVIDOSOS  (frente AutoSpecAI — Rafael)
    # =========================================================================
    # Movida da tela antiga EM BLOCO (TRABALHO_PARALELO.md §3.1): os mesmos 6
    # métodos e 7 atributos. Só o desenho de widget mudou de biblioteca; a
    # lógica continua em `sigft/services/autospec_conferencia.py`.
    #
    # POR QUE ESTA TELA EXISTE: o filtro anti-intruso (§4.3) tem três
    # destinos, e o do meio (`duvidoso`) não tem como ser resolvido por
    # código. Numa ficha real entrou uma camiseta da Minnie do site do Target
    # porque a URL continha o código do material; no mesmo lote um datasheet
    # legítimo foi barrado por não citar a marca no título. Indistinguíveis
    # para o programa, triviais para quem abre o link.
    #
    # POR QUE ELA NÃO SE ESCONDE (2026-08-17): conferir 20 links não cabe numa
    # sessão. Salvar/importar `.txt` resolve, mas o botão de IMPORTAR precisa
    # estar visível ANTES de existir conferência nenhuma, que é a situação de
    # quem reabriu o app no dia seguinte. Por isso a seção fica sempre
    # montada, com um estado vazio no lugar da lista.
    # =========================================================================
    def _build_conferencia(self, corpo) -> None:
        """Monta a seção. Fica sempre visível: sem nada a conferir, mostra o
        estado vazio e só o botão de importar funciona."""
        self.conferencia = None
        self.marcados_conf = {}
        self.links_conf = {}
        self.cabecalhos_conf = []
        self.rotulo_conf_vazia = None
        # Uma 2ª passada por vez (ver `_conferencia_processar`).
        self._conf_em_andamento = False

        self.frm_conf, conf = _cartao(corpo, borda="aviso")
        self.rotulo_conf_titulo = _rotulo(t("5. Conferência de documentos"), tamanho=14, negrito=True,
                                          papel="aviso")
        conf.addWidget(self.rotulo_conf_titulo)
        conf.addSpacing(2)                              # título: pady=(10, 2)
        self.rotulo_conf_explicacao = _texto_quebrado(
            t("Estes documentos citam o fabricante OU o código, mas não os dois — "
              "podem ser o datasheet certo num distribuidor, ou a página de outro "
              "produto. Abra o link, confira, e marque os que são deste material.\n"
              "Não precisa terminar agora: salve em .txt e importe depois para "
              "continuar de onde parou."),
            quebra=QUEBRA_TEXTOS)
        _recuado(conf, self.rotulo_conf_explicacao, 0, natural=True)
        conf.addSpacing(8)                              # texto: pady=(0, 8)

        self.lista_conf, self._layout_conf = blocos.area_rolavel(
            conf, fundo="tela", margem=RECUO_ROLAGEM, barra_sempre_visivel=True)
        self.lista_conf.setFixedHeight(ALTURA_QUADRO_INTERNO)
        conf.addSpacing(10)                             # lista: pady=(0, 10)

        self.btn_conf_salvar = blocos.botao(
            t("SALVAR CONFERÊNCIA (.txt)"), variante="primario", altura=32, tamanho_fonte=12,
            largura_minima=estilo.LARGURA_BOTAO_CTK)
        self.btn_conf_salvar.clicked.connect(lambda: self._conferencia_salvar())
        self.btn_conf_importar = blocos.botao(
            t("IMPORTAR CONFERÊNCIA (.txt)"), variante="primario", altura=32, tamanho_fonte=12,
            largura_minima=estilo.LARGURA_BOTAO_CTK)
        self.btn_conf_importar.clicked.connect(self._conferencia_importar)
        self._linha_botoes_conf = _DoisBotoesQueCrescem(self.btn_conf_salvar, self.btn_conf_importar,
                                                        altura=32)
        _recuado(conf, self._linha_botoes_conf, 5, 5)  # padx=20
        conf.addSpacing(8)                              # linha: pady=(0, 8)

        self.btn_conf = blocos.botao(
            t("PROCESSAR OS DOCUMENTOS MARCADOS"), variante="acento", altura=40, tamanho_fonte=13,
            negrito=True)
        self.btn_conf.clicked.connect(self._conferencia_processar)
        _recuado(conf, self.btn_conf, 5, 5)             # padx=20, pady=(0, 15)
        self._conferencia_mostrar(None)

    def _conferencia_mostrar(self, conferencia, marcados=None) -> None:
        """Preenche a lista. `marcados` vem do `.txt` importado — é o que faz
        a conferência retomada nascer com o que já tinha sido conferido."""
        self.conferencia = conferencia
        self.marcados_conf = {}
        self.links_conf = {}
        self.cabecalhos_conf = []
        self.rotulo_conf_vazia = None
        _esvaziar(self._layout_conf)

        estado = bool(conferencia)
        # Com uma 2ª passada rodando, o PROCESSAR fica desligado mesmo que a lista
        # mude (IMPORTAR ou o fim de um lote chegam aqui): quem o devolve é o fim
        # da passada (`_conferencia_terminou`).
        self.btn_conf.setEnabled(estado and not self._conf_em_andamento)
        self.btn_conf_salvar.setEnabled(estado)

        lista = self._layout_conf
        if not conferencia:
            self.rotulo_conf_vazia = _texto_quebrado(
                t("Nenhuma conferência pendente.\n\n"
                  "Se você salvou uma conferência anterior em .txt, use "
                  "IMPORTAR CONFERÊNCIA para continuar de onde parou."),
                papel="legenda", quebra=QUEBRA_CONFERENCIA_VAZIA)
            lista.addSpacing(10)                        # pady=10
            lista.addWidget(_em_caixa(self.rotulo_conf_vazia, 10, 0), 0, Qt.AlignmentFlag.AlignLeft)
            lista.addSpacing(10)
            return

        marcados = marcados or {}
        folga = 0                                       # pady de baixo do vizinho de cima
        for i_pend, pendencia in enumerate(conferencia.pendencias):
            # O emoji é da tela (mono); nome e material são dado da pessoa.
            cabecalho = _rotulo(estilo.mono("📄") + f" {pendencia.nome_curto}  —  {pendencia.material[:60]}",
                                tamanho=12, negrito=True, papel="destaque")
            _sem_largura_minima(cabecalho)
            lista.addSpacing(folga + 8)                 # pady=(8, 2)
            lista.addWidget(_em_caixa(cabecalho, 6, 6))
            self.cabecalhos_conf.append(cabecalho)
            folga = 2

            for i_doc, doc in enumerate(pendencia.documentos):
                caixa = controles.CaixaDeMarcar("", lado=LADO_CAIXA_CONF)
                caixa.setFixedSize(TAMANHO_CAIXA_CONF)
                caixa.setChecked(bool(marcados.get((i_pend, i_doc))))
                self.marcados_conf[(i_pend, i_doc)] = caixa

                url = doc.get("url", "")
                titulo = (doc.get("title") or url)[:70]
                # O link é um botão (lá porque CTkLabel não tem clique nativo); o
                # visual de link é feito à mão. O "&" do título vai dobrado: sozinho,
                # o Qt o leria como mnemônico (some do texto e vira atalho Alt).
                link = blocos.botao(titulo.replace("&", "&&"),
                                    altura=22, tamanho_fonte=11,
                                    variante="fantasma")
                link.setProperty("papel", "link")   # cor de link vem da folha (tokens `info`)
                # O "🔗" virou o ícone, na cor do link (2026-10-20).
                icones.aplicar(link, "external-link", papel_cor="info", tamanho=14)
                # O sublinhado também é da folha (a regra `[papel="link"]`).
                # Por `pintar` (2026-10-21): parte da folha de antes do aumento da letra.
                blocos.pintar(link, "QPushButton { text-align: left;"
                              f" padding: 0 {estilo.FOLGA_TEXTO_BOTAO_CTK}px; }}")
                _sem_largura_minima(link)
                link.clicked.connect(lambda *_, u=url: webbrowser.open(u))
                self.links_conf[(i_pend, i_doc)] = link

                linha = QWidget()
                linha.setFixedHeight(TAMANHO_CAIXA_CONF.height())
                arranjo = QHBoxLayout(linha)
                arranjo.setContentsMargins(6, 0, 6, 0)  # padx=6
                arranjo.setSpacing(0)
                arranjo.addWidget(caixa)
                arranjo.addWidget(link, 1, Qt.AlignmentFlag.AlignVCenter)
                lista.addSpacing(folga + 1)             # pady=1
                lista.addWidget(linha)
                folga = 1
        lista.addSpacing(folga)

    def _marcacoes(self) -> dict:
        return {chave: caixa.isChecked() for chave, caixa in self.marcados_conf.items()}

    def _conferencia_salvar(self, automatico: bool = False, status_pmib_path=None):
        """Grava a aba num `.txt` na pasta do `_STATUS_PMIB`.

        `automatico=True` é a gravação que acontece sozinha quando o lote
        termina: não abre caixa nenhuma (não há quem dê OK). O botão só protege
        quem lembra de clicar nele, e o relato que originou isto foi de alguém
        que precisou fechar o aplicativo no meio da conferência.

        `status_pmib_path`: a do clique que começou o lote (a gravação
        automática); sem ela, a escolhida agora (o botão).
        """
        if not self.conferencia:
            if not automatico:
                QMessageBox.information(self, t("Conferência"), t("Não há conferência para salvar."))
            return None
        try:
            caminho = conferencia_txt.salvar_txt(
                self.conferencia, status_pmib_path or self.status_pmib_path, self._marcacoes()
            )
        except Exception as e:  # noqa: BLE001 -- vira aviso, como lá
            self.log(f"Nao consegui salvar o .txt da conferencia: {e}")
            if not automatico:
                QMessageBox.critical(self, t("Conferência"), t("Não consegui salvar:\n{erro}", erro=e))
            return None
        self.log(f"Conferencia salva em: {caminho}")
        if not automatico:
            QMessageBox.information(self, t("Conferência"), t("Conferência salva em:\n{caminho}", caminho=caminho))
        return caminho

    def _conferencia_importar(self) -> None:
        """Retoma uma conferência salva — inclusive de outra sessão do app."""
        caminho = file_dialogs.ask_open_file(
            "autospec.conferencia", "txt",
            titulo=t("Selecione o .txt da conferência"),
            filetypes=[(t("Texto"), "*.txt"), (t("Todos"), "*.*")],
        )
        if not caminho:
            return
        try:
            conferencia, marcados = conferencia_txt.carregar_txt(caminho)
        except Exception as e:  # noqa: BLE001 -- vira aviso, como lá
            QMessageBox.critical(self, t("Conferência"), t("Não consegui ler o arquivo:\n{erro}", erro=e))
            return
        if not conferencia:
            QMessageBox.warning(
                self, t("Conferência"),
                t("Não encontrei nenhum documento neste arquivo.\n\n"
                  "Ele precisa ter as linhas 'FICHA:' e os links marcados com [ ] ou [x]."),
            )
            return

        self._conferencia_mostrar(conferencia, marcados)
        self.log(f"Conferencia importada de: {caminho}")
        self.log(f" -> {conferencia.total_documentos} documento(s) em "
                 f"{len(conferencia.pendencias)} ficha(s).")
        ausentes = conferencia_txt.fichas_ausentes(conferencia)
        for ficha in ausentes:
            self.log(f" -> AVISO: nao encontrei a ficha {ficha}")
        if ausentes:
            QMessageBox.warning(
                self, t("Conferência"),
                t("{n} ficha(s) não estão mais no caminho gravado no "
                  "arquivo.\nElas vão falhar no processamento — veja o console.", n=len(ausentes)),
            )

    def _conferencia_processar(self) -> None:
        if not self.conferencia:
            return
        if self.backend("autospec_backend") is None:
            return
        # Guard que vale sobretudo para a conferência IMPORTADA: quem reabriu
        # o aplicativo tem a lista de links, mas ainda não escolheu o
        # _STATUS_PMIB — e a 2ª passada lê a planilha de status ficha a ficha.
        if not self.status_pmib_path:
            QMessageBox.critical(
                self, t("Erro"), t("Selecione o arquivo _STATUS_PMIB (seção 1) antes de "
                                   "processar a conferência.")
            )
            return
        selecao = self.conferencia.selecao_por_ficha(self._marcacoes())
        if not selecao:
            QMessageBox.information(
                self, t("Conferência"), t("Marque ao menos um documento antes de processar.")
            )
            return
        # Uma passada por vez: ela regrava o `_completed` de cada ficha, e duas ao
        # mesmo tempo disputariam esses arquivos. O flag segura o PROCESSAR até o
        # fim, mesmo que a lista mude no meio (lá ele religava ali).
        self._conf_em_andamento = True
        self.btn_conf.setEnabled(False)
        self.iniciar_tarefa(self._conferencia_worker, self.conferencia, selecao,
                            self.status_pmib_path, self._conferir_fornecedor)

    def _conferencia_terminou(self) -> None:
        """Fim da 2ª passada, na thread da interface: o PROCESSAR volta se ainda
        houver lista (ela pode ter mudado, ou sumido, durante a passada)."""
        self._conf_em_andamento = False
        try:
            self.btn_conf.setEnabled(bool(self.conferencia))
        except RuntimeError:
            pass  # tela já destruída pelo Qt: nada a devolver

    def _conferencia_worker(self, conferencia, selecao, status_pmib_path, auditar_fornecedor) -> None:
        try:
            core = self._novo_core(auditar_fornecedor)
            core.conferencia = conferencia
            for msg in core.processar_conferidos(selecao, status_pmib_path):
                self.log(msg)
            self.log("Conferência processada!")
            # A lista FICA na tela: o que não foi marcado continua duvidoso, e
            # limpar aqui repetiria a perda que o .txt veio consertar.
            self.log("Os documentos nao marcados continuam na lista. Se for parar "
                     "agora, use SALVAR CONFERENCIA (.txt).")
            self.avisar(t("Sucesso"), t("Documentos conferidos processados."))
        except Exception as e:  # noqa: BLE001 -- mesmo texto da tela antiga
            self.log(f"ERRO na conferência: {e}")
        finally:
            interface.na_interface(self._conferencia_terminou)

    # --- Seletores (Lógica Mantida) -------------------------------------------------
    def sel_status(self) -> None:
        p = file_dialogs.ask_open_file("autospec.status_pmib", "excel", titulo=t("Selecione _STATUS_PMIB"),
                                       filetypes=[("Excel", "*.xlsx")])
        if p:
            self.status_pmib_path = p
            self.lbl_status.setText(os.path.basename(p))
            _pintar(self.lbl_status, None)

    def sel_sheet(self) -> None:
        p = file_dialogs.ask_open_file("autospec.ficha", "excel", titulo=t("Selecione a Ficha Técnica"),
                                       filetypes=[("Excel", "*.xlsx")])
        if p:
            self.temp_sheet = p
            self.lbl_sheet.setText(t("Ficha: {nome}", nome=os.path.basename(p)))
            _pintar(self.lbl_sheet, None)

    def sel_refs(self) -> None:
        ps = file_dialogs.ask_open_files("autospec.manuais", "pdf", titulo=t("Selecione Manuais/PDFs"),
                                         filetypes=[(t("Docs"), "*.pdf *.txt")])
        if ps:
            self.temp_refs = list(ps)
            self.lbl_refs.setText(t("Manuais: {n} arquivos", n=len(ps)))
            _pintar(self.lbl_refs, None)

    def add_queue(self) -> None:
        if not self.temp_sheet:
            QMessageBox.warning(self, t("Aviso"), t("Selecione pelo menos a Ficha Técnica (.xlsx)."))
            return

        self.queue.append({'sheet': self.temp_sheet, 'refs': self.temp_refs})

        # Reset Temp
        self.temp_sheet = None
        self.temp_refs = []
        self.lbl_sheet.setText(t("Ficha: {nome}", nome=t("[Nenhuma]")))
        _pintar(self.lbl_sheet, "legenda")
        self.lbl_refs.setText(t("Manuais: {n} arquivos", n=0))
        _pintar(self.lbl_refs, "legenda")
        self.update_queue_ui()

    def remove_queue(self, idx: int) -> None:
        del self.queue[idx]
        self.update_queue_ui()

    def update_queue_ui(self) -> None:
        _esvaziar(self._layout_fila)
        self.linhas_fila = []
        self.rotulo_fila_vazia = None
        lista = self._layout_fila

        if not self.queue:
            self.rotulo_fila_vazia = _rotulo(t("Fila vazia."), papel="legenda", alinhar="centro")
            lista.addSpacing(10)                        # pady=10, centrado
            lista.addWidget(self.rotulo_fila_vazia, 0, Qt.AlignmentFlag.AlignHCenter)
            lista.addSpacing(10)
            return

        for i, item in enumerate(self.queue):
            fname = os.path.basename(item['sheet'])
            n_refs = len(item['refs'])
            rotulo = _rotulo(t("#{numero}: {nome} (+{n} manuais)", numero=i + 1, nome=fname, n=n_refs),
                            tamanho=12)
            _sem_largura_minima(rotulo)
            botao = blocos.botao("X", variante="perigo", largura=30, altura=25)
            # Sem o padding de 14 da folha do app: num botão de 30 ele cortaria o "X".
            blocos.pintar(botao, "QPushButton { padding: 0; }")
            botao.clicked.connect(lambda *_, x=i: self.remove_queue(x))

            f = QWidget()
            f.setFixedHeight(blocos.ALTURA_MINIMA_ROTULO)
            arranjo = QHBoxLayout(f)
            arranjo.setContentsMargins(5, 0, 5, 0)      # padx=5 dos dois
            arranjo.setSpacing(0)
            arranjo.addWidget(rotulo, 1)
            arranjo.addWidget(botao)
            lista.addSpacing(2 if i == 0 else 4)        # pady=2: os vizinhos somam
            lista.addWidget(f)
            self.linhas_fila.append((rotulo, botao))
        lista.addSpacing(2)

    # --- Execução -------------------------------------------------------------------
    def run_process(self) -> None:
        if self.backend("autospec_backend") is None:
            return
        if not self.status_pmib_path:
            QMessageBox.critical(self, t("Erro"), t("Selecione o arquivo _STATUS_PMIB."))
            return
        if not self.queue:
            QMessageBox.critical(self, t("Erro"), t("Adicione itens à fila."))
            return
        # A fila do lote é a do clique: o que se acrescentar (ou tirar) durante o
        # lote não mexe na lista que a thread está percorrendo.
        self.iniciar_tarefa(self._worker, list(self.queue), self.status_pmib_path,
                            self._conferir_fornecedor, botao=self.btn_run)

    def _ao_marcar_conferencia_fornecedor(self, marcada: bool) -> None:
        self._conferir_fornecedor = bool(marcada)

    def _novo_core(self, auditar_fornecedor: bool):
        """Uma instância do backend com as chaves da tela Home.

        Extraído de `_worker` em 2026-08-13 porque a conferência precisa da
        MESMA construção — duplicar as 4 chaves em dois lugares é como uma
        delas fica para trás quando um provedor novo entra.
        """
        core = backends.exigir("autospec_backend").AutoSpecCore(
            gemini_key=self.controller.get_key("GEMINI"),
            llama_key=self.controller.get_key("LLAMA"),
            google_search_key=self.controller.get_key("GOOGLE_SEARCH"),
            google_cse_id=self.controller.get_key("GOOGLE_CSE")
        )
        # O interruptor da conferencia do fornecedor, para os DOIS workers
        # (lido no clique de cada um).
        core.auditar_fornecedor = auditar_fornecedor
        return core

    def _worker(self, fila, status_pmib_path, auditar_fornecedor) -> None:
        try:
            core = self._novo_core(auditar_fornecedor)
            for msg in core.process_queue(fila, status_pmib_path):
                self.log(msg)

            self.log("Processamento Completo!")
            # Conferência humana: só lista se sobrou dúvida (2026-08-13). O fim do
            # lote -- e o "Sucesso" -- segue na thread da interface.
            conferencia = getattr(core, "conferencia", None)
            interface.na_interface(self._fila_processada, fila, conferencia, status_pmib_path)
        except Exception as e:  # noqa: BLE001 -- mesmo texto da tela antiga
            self.log(f"ERRO FATAL: {e}")

    def _fila_processada(self, fila, conferencia, status_pmib_path=None) -> None:
        """Fim do lote, na thread da interface: tira da fila o que foi
        processado, mostra a conferência e a salva sozinha.

        A ordem importa (invariante de 2026-08-17): `_conferencia_mostrar` zera
        as marcações, então o `.txt` automático sai coerente com a lista nova,
        e não com as marcas do lote anterior.

        Um erro aqui vai para o console como "ERRO FATAL", e o "Sucesso" não
        aparece: a ponte da interface só o escreveria no stderr.
        """
        try:
            processados = {id(item) for item in fila}
            self.queue = [item for item in self.queue if id(item) not in processados]
            self.update_queue_ui()
            self._conferencia_mostrar(conferencia)
            # Salva sozinho (2026-08-17), na pasta do `_STATUS_PMIB` do clique:
            # outro escolhido no meio do lote é para o próximo.
            if conferencia:
                self._conferencia_salvar(automatico=True, status_pmib_path=status_pmib_path)
        except Exception as e:  # noqa: BLE001 -- mesmo texto da tela antiga
            self.log(f"ERRO FATAL: {e}")
            return
        self.avisar(t("Sucesso"), t("Todas as tarefas da fila foram processadas."))
