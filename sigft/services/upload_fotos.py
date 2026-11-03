r"""
Upload de Fotos (2026-10-30): sobe na ficha as fotos dos materiais de um
subsistema e marca a coluna `DOCUMENTOS E IMAGENS` do `_STATUS_PMIB`.

O caderno do módulo é `docs/UPLOAD_DE_FOTOS.md`. Em resumo:

  - **Pasta:** uma por subsistema. O NOME do arquivo diz a ficha e a ordem:
    os 4 últimos dígitos do código PMIB + letra -- `0071.jpg`, `0071a.jpg`,
    `0071b.jpg`… -- e sobem nessa ordem. O nome vai igual para o portal, que
    o mostra na coluna "Nome" da tabela de imagens.
  - **Ficha:** os 4 dígitos casam com o fim do código no `_STATUS_PMIB`
    escolhido. Dois códigos com o mesmo final (contratos diferentes) é
    ambíguo: vai para o relatório, nunca se adivinha.
  - **Fotos que já estão na ficha:** o modo da tela decide -- *substituir*
    (exclui todas antes de subir) ou *perguntar* (pausa e a pessoa escolhe).
  - **Planilha:** fotos subidas + documento na ficha = `COMPLETO`; fotos
    subidas sem documento = `INCOMPLETO` + nota "Faltam documentos".

⚠️ TUDO PELA TELA. Existe um MCP (`pmib-mcp`, no Drive do usuário) que exclui
e lista imagens chamando o servidor do portal direto
(`…/PMIB_DataSheet_DocumentsAndImages/ActionPMIBDataSheetImage_Delete`). O
SIG-FT NÃO faz isso: a Itaipu proíbe contato com o banco dela por fora da tela
(regra do Luan, 2026-10-14, em `core/rpa/respostas.py`). O MCP serviu de mapa
-- é dele que vem a certeza de que a lixeira da tabela de imagens exclui a
imagem da ficha --, não de atalho.

⚠️ SELETORES DA TABELA AINDA NÃO CONFERIDOS NO DOM REAL. Saíram das capturas de
tela de 2026-10-30 (cabeçalhos "Pré-visualização" e "Arquivos anexados",
lixeira `fa-trash` por linha). O upload em si (`duplicadas_imagens.subir_uma`)
já rodou no portal. A primeira execução real é a prova; ver o caderno.
"""
from __future__ import annotations

import os
import re
import time
from dataclasses import dataclass

from sigft import config
from sigft.core.excel import pmib_codes
from sigft.core.excel.status_sheet import VALOR_COMPLETO, VALOR_INCOMPLETO, StatusPMIB
from sigft.core.rpa import seletores_duplicada as sel
from sigft.core.rpa.factory import criar_engine
from sigft.core.rpa.portal import XPATH_CONFIRMAR, PMIBPortal
from sigft.services import duplicadas_extrator as extrator
from sigft.services import duplicadas_imagens as imagens
from sigft.services.duplicadas_injetor import _log_de

NOME_DO_MODULO = "upload_fotos"
NOTA_FALTAM_DOCUMENTOS = "Faltam documentos"

# O que fazer com as fotos que a ficha já tem.
MODO_SUBSTITUIR = "substituir"
MODO_PERGUNTAR = "perguntar"
# As respostas de `perguntar(pmib, quantas)` no modo PERGUNTAR.
SUBSTITUIR, ADICIONAR, PULAR = "substituir", "adicionar", "pular"

# `0071.jpg`, `0071a.JPG`, `0071b.png`. O portal aceita só JPEG e PNG
# (`accept="image/jpeg,image/png"` no input do FilePond).
_NOME_DA_FOTO = re.compile(r"^(\d{4})([a-z]?)\.(jpe?g|png)$", re.IGNORECASE)

# --- Seletores (das capturas de 2026-10-30; ver o aviso no topo) -----------
# As duas tabelas da aba têm lixeira e coluna "Descrição": o que separa uma da
# outra é o cabeçalho que só ela tem.
XPATH_TABELA_DE_IMAGENS = "//table[.//th[normalize-space()='Pré-visualização']]"
XPATH_TABELA_DE_DOCUMENTOS = "//table[.//th[normalize-space()='Arquivos anexados']]"
_REL_LIXEIRA = "//*[contains(@class, 'fa-trash')]"
XPATH_LINHAS_DE_IMAGEM = XPATH_TABELA_DE_IMAGENS + "//tr[.//*[contains(@class, 'fa-trash')]]"
XPATH_LINHAS_DE_DOCUMENTO = XPATH_TABELA_DE_DOCUMENTOS + "//tr[.//*[contains(@class, 'fa-trash')]]"
XPATH_IMAGEM_DE_NOME = XPATH_TABELA_DE_IMAGENS + "//tr[.//td[normalize-space()={nome}]]"

# Esperas em TENTATIVAS (§0, regra 7 de docs/PORTAL_COMO_ELE_SE_COMPORTA.md).
TENTATIVAS_DA_TABELA = 20
TENTATIVAS_DA_EXCLUSAO = 30
TENTATIVAS_DA_CONFERENCIA = 30
# Depois de um envio que falhou, quanto se espera a tabela mostrar o que ele
# gravou antes de reenviar o resto (3 s).
TENTATIVAS_DA_REVISAO = 6
INTERVALO_S = 0.5
# Teto de exclusões por ficha: uma lixeira que não exclui não pode girar
# para sempre.
MAX_EXCLUSOES = 30
# Tempos-base, em segundos, das esperas que não são em tentativas.
MOTOR_S = 20          # cada clique/campo do motor (`criar_engine`)
CONFIRMACAO_S = 20.0  # o aviso verde depois do CONFIRMAR (o portal usa 8 s)


@dataclass(frozen=True)
class Esperas:
    """Quanto o robô espera em cada passo. `fator` é a "Velocidade do portal"
    da tela (1, 2 ou 4) e multiplica TUDO de uma vez.

    No caso bom não custa nada: cada espera termina assim que a condição
    aparece. O fator só decide quanto se insiste antes de desistir.
    """
    fator: float = 1.0

    def _vezes(self, base):
        return max(1, round(base * self.fator))

    @property
    def tabela(self):
        return self._vezes(TENTATIVAS_DA_TABELA)

    @property
    def exclusao(self):
        return self._vezes(TENTATIVAS_DA_EXCLUSAO)

    @property
    def conferencia(self):
        return self._vezes(TENTATIVAS_DA_CONFERENCIA)

    @property
    def revisao(self):
        return self._vezes(TENTATIVAS_DA_REVISAO)

    @property
    def ficha(self):
        return self._vezes(extrator.TENTATIVAS_DA_FICHA)

    @property
    def aba(self):
        return self._vezes(extrator.TENTATIVAS_DA_ABA_ATIVA)

    @property
    def formulario(self):
        return self._vezes(imagens.TENTATIVAS_DO_FORMULARIO)

    @property
    def motor_s(self):
        return self._vezes(MOTOR_S)

    @property
    def confirmacao_s(self):
        return CONFIRMACAO_S * self.fator

    @property
    def processamento_s(self):
        return imagens.TIMEOUT_PROCESSAMENTO * self.fator


# ===========================================================================
# 1. O lote, sem portal
# ===========================================================================
def agrupar_fotos(pasta):
    """`({"0071": [caminho, …]}, [ignorados])`, cada grupo na ordem de subida.

    A foto sem letra vem antes da `a`: `0071`, `0071a`, `0071b`. Arquivo fora
    do padrão é listado, não adivinhado.
    """
    grupos, ignorados = {}, []
    for nome in sorted(os.listdir(pasta)):
        caminho = os.path.join(pasta, nome)
        if not os.path.isfile(caminho):
            continue
        achado = _NOME_DA_FOTO.match(nome)
        if not achado:
            ignorados.append(nome)
            continue
        grupos.setdefault(achado.group(1), []).append((achado.group(2).lower(), caminho))
    return {quatro: [c for _letra, c in sorted(fotos)] for quatro, fotos in sorted(grupos.items())}, ignorados


def ligar_as_fichas(grupos, codigos):
    """Liga cada grupo de fotos ao código PMIB pelo final de 4 dígitos.

    Devolve `(fichas, sem_ficha, ambiguas)`: `fichas` é `[(pmib, quatro,
    caminhos)]`; `sem_ficha` os finais que não estão na planilha; `ambiguas`
    `{quatro: [pmib, …]}` quando mais de um código termina igual.
    """
    por_final = {}
    for codigo in codigos:
        normal = pmib_codes.normalize_pmib(codigo)
        if normal and "." in normal:
            por_final.setdefault(normal.rsplit(".", 1)[1][-4:], set()).add(normal)
    fichas, sem_ficha, ambiguas = [], [], {}
    for quatro, caminhos in grupos.items():
        candidatos = sorted(por_final.get(quatro, ()))
        if not candidatos:
            sem_ficha.append(quatro)
        elif len(candidatos) > 1:
            ambiguas[quatro] = candidatos
        else:
            fichas.append((candidatos[0], quatro, caminhos))
    return fichas, sem_ficha, ambiguas


def ler_codigos(caminho_status):
    """Os códigos PMIB da coluna "CÓDIGO PMIB" do `_STATUS_PMIB`."""
    painel = StatusPMIB(caminho_status)
    try:
        # Só leitura, sem estilos, só a coluna do código: o `_STATUS_PMIB` de
        # sistema grande levava segundos para abrir inteiro.
        painel.abrir(keywords={config.COL_CODIGO_PMIB: config.COL_CODIGO_PMIB}, max_col=49,
                     read_only=True, data_only=True)
        coluna = painel.col_map.get(config.COL_CODIGO_PMIB)
        if not coluna:
            raise ValueError(f"a coluna '{config.COL_CODIGO_PMIB}' não foi encontrada no _STATUS_PMIB")
        linhas = painel.ws.iter_rows(min_row=(painel.header_row or 0) + 1, min_col=coluna,
                                     max_col=coluna, values_only=True)
        return [linha[0] for linha in linhas if linha[0] not in (None, "")]
    finally:
        painel.fechar()


def descricao_das_fotos(quatro):
    """A descrição que vai em PT e ES -- a que o usuário já usa no portal
    ("imagens - 0071"); a letra de cada foto fica no NOME do arquivo."""
    return f"imagens - {quatro}"


# ===========================================================================
# 2. O que se lê da tela
# ===========================================================================
def _contar(portal, seletor):
    try:
        return portal.engine.contar(seletor) or 0
    except Exception:  # noqa: BLE001 -- tela remontando conta como zero
        return 0


def _esperar(condicao, tentativas):
    for _ in range(tentativas):
        if condicao():
            return True
        time.sleep(INTERVALO_S)
    return condicao()


def fotos_na_ficha(portal):
    """Quantas fotos a ficha aberta tem (linhas da tabela de imagens)."""
    return _contar(portal, XPATH_LINHAS_DE_IMAGEM)


def fotos_ao_abrir(portal, esperas=None):
    """As fotos da ficha recém-aberta, esperando os DADOS e não o cabeçalho.

    O OutSystems desenha a tabela antes de as linhas chegarem: contar no
    primeiro instante dava 0, e o modo "substituir" subia por cima das fotos
    antigas. Espera aparecer alguma linha (ficha sem foto gasta a espera
    inteira, ~10 s) e depois a contagem parar de mudar.
    """
    tentativas = (esperas or Esperas()).tabela
    if not _esperar(lambda: fotos_na_ficha(portal) > 0, tentativas):
        return 0
    anterior = fotos_na_ficha(portal)
    for _ in range(tentativas):
        time.sleep(INTERVALO_S)
        agora = fotos_na_ficha(portal)
        if agora == anterior:
            return agora
        anterior = agora
    return anterior


def tem_documentos(portal):
    """A ficha aberta tem pelo menos um documento associado?"""
    return _contar(portal, XPATH_LINHAS_DE_DOCUMENTO) > 0


def foto_esta_na_tabela(portal, caminho):
    nome = extrator._literal_xpath(os.path.basename(caminho))
    return _contar(portal, XPATH_IMAGEM_DE_NOME.format(nome=nome)) > 0


# ===========================================================================
# 3. O que se faz na tela
# ===========================================================================
def excluir_uma(portal, callback_log=None, esperas=None):
    """Clica na lixeira da ÚLTIMA foto e confirma. `True` só quando a linha
    SAIU da tabela -- clicar não prova nada (§0, regra 6).

    De baixo para cima: a primeira linha é a Principal, e tela desse tipo
    costuma recusar excluí-la enquanto houver outra. Assim ela sai por último.
    """
    _log = _log_de(callback_log)
    antes = fotos_na_ficha(portal)
    if not antes:
        return True
    lixeira = f"({XPATH_LINHAS_DE_IMAGEM})[last()]{_REL_LIXEIRA}"
    try:
        portal.engine.scroll_to(lixeira)
        portal.engine.click_raw(lixeira)
    except Exception as erro:  # noqa: BLE001
        _log(f"      [Erro] Não consegui clicar na lixeira da foto: {type(erro).__name__}.")
        return False

    # A confirmação: a do diálogo primeiro (§3 -- "CONFIRMAR" solto casa outros
    # botões), a genérica do portal se o diálogo não tiver `role`.
    confirmou = False
    for _ in range((esperas or Esperas()).exclusao):
        if fotos_na_ficha(portal) < antes:
            return True
        if not confirmou:
            for botao in (sel.XPATH_DIALOGO_CONFIRMAR, XPATH_CONFIRMAR):
                if _contar(portal, botao):
                    try:
                        portal.engine.click_raw(f"({botao})[1]")
                        confirmou = True
                    except Exception:  # noqa: BLE001 -- tenta de novo na volta
                        pass
                    break
        time.sleep(INTERVALO_S)
    if fotos_na_ficha(portal) < antes:
        return True
    _log("      [Erro] Cliquei na lixeira" + (" e confirmei" if confirmou else "")
         + ", mas a foto continua na tabela.")
    return False


def excluir_todas(portal, callback_log=None, esperas=None):
    """Exclui as fotos da ficha aberta, uma a uma. `True` se a tabela esvaziou."""
    for _ in range(MAX_EXCLUSOES):
        if not fotos_na_ficha(portal):
            return True
        if not excluir_uma(portal, callback_log, esperas):
            return False
    return not fotos_na_ficha(portal)


def subir_fotos(portal, descricao, caminhos, callback_log=None, esperas=None):
    """Sobe em envios de até 10 (o limite do diálogo). Envio que falha é
    refeito foto a foto, e SÓ das que não estão na tabela.

    O diálogo pode gravar parte do envio e mesmo assim não devolver o aviso
    verde: reenviar tudo era foto repetida na ficha. Por isso NÃO se usa aqui a
    autoconferência de `duplicadas_imagens.subir_arquivos`, que tenta de novo
    sem olhar a tabela.
    """
    e = esperas or Esperas()
    tempos = {"timeout_confirmacao": e.confirmacao_s, "timeout_processamento": e.processamento_s,
              "tentativas_do_formulario": e.formulario}
    tamanho = imagens.MAX_ARQUIVOS_POR_ENVIO
    for inicio in range(0, len(caminhos), tamanho):
        lote = caminhos[inicio:inicio + tamanho]
        if imagens.subir_juntas(portal, descricao, lote, callback_log, **tempos):
            continue
        imagens.fechar_formulario(portal, callback_log)
        _esperar(lambda lote=lote: all(foto_esta_na_tabela(portal, c) for c in lote), e.revisao)
        for caminho in [c for c in lote if not foto_esta_na_tabela(portal, c)]:
            if not imagens.subir_juntas(portal, descricao, [caminho], callback_log, **tempos):
                imagens.fechar_formulario(portal, callback_log)


@dataclass
class ResultadoDaFicha:
    pmib: str
    quatro: str
    ok: bool = False
    pulada: bool = False
    tem_documentos: bool = False
    motivo: str = ""


def processar_ficha(portal, pmib, quatro, caminhos, modo=MODO_SUBSTITUIR,
                    perguntar=None, callback_log=None, esperas=None):
    """Uma ficha, de ponta a ponta: abrir, limpar (se for o caso), subir,
    conferir e ver se tem documento."""
    _log = _log_de(callback_log)
    resultado = ResultadoDaFicha(pmib, quatro)
    e = esperas or Esperas()

    if not portal.pesquisar_e_abrir(pmib) or not extrator.esperar_a_ficha_abrir(portal, espera=e.ficha):
        resultado.motivo = "ficha não encontrada ou não abriu em edição"
        return resultado
    if not extrator.abrir_secao(portal, sel.ABA_DOCUMENTOS_EDICAO, callback_log, tentativas=e.aba):
        resultado.motivo = "não abri a aba Documentos e imagens"
        return resultado
    existentes = fotos_ao_abrir(portal, e)
    if not existentes:
        _log("      Nenhuma foto na tabela de imagens: a ficha está sem fotos.")
    else:
        decisao = SUBSTITUIR
        if modo == MODO_PERGUNTAR and perguntar is not None:
            decisao = perguntar(pmib, existentes)
        if decisao == PULAR:
            resultado.pulada = True
            resultado.motivo = f"já tinha {existentes} foto(s); pulada a pedido"
            return resultado
        if decisao == SUBSTITUIR:
            _log(f"      A ficha já tem {existentes} foto(s): excluindo antes de subir.")
            if not excluir_todas(portal, callback_log, e):
                resultado.motivo = "não consegui excluir as fotos que já estavam na ficha"
                return resultado

    descricao = descricao_das_fotos(quatro)
    antes = fotos_na_ficha(portal)
    subir_fotos(portal, descricao, caminhos, callback_log, e)

    # A PROVA é a tabela, não o toast de cada um: o NOME de cada arquivo E o
    # número de linhas -- no modo "adicionar" a foto antiga pode ter o mesmo
    # nome da nova, e só o nome passaria com a nova fora. UMA espera para
    # todas: esperar foto a foto somava 15 s por foto que faltasse.
    _esperar(lambda: all(foto_esta_na_tabela(portal, c) for c in caminhos), e.conferencia)
    faltaram = [os.path.basename(c) for c in caminhos if not foto_esta_na_tabela(portal, c)]
    if faltaram:
        resultado.motivo = f"{len(faltaram)} de {len(caminhos)} foto(s) não apareceram na tabela: {', '.join(faltaram)}"
        return resultado
    esperado = antes + len(caminhos)
    if not _esperar(lambda: fotos_na_ficha(portal) >= esperado, e.conferencia):
        resultado.motivo = (f"a tabela tem {fotos_na_ficha(portal)} foto(s), esperava {esperado}: "
                            f"alguma das novas não entrou")
        return resultado

    resultado.ok = True
    resultado.tem_documentos = tem_documentos(portal)
    return resultado


class UploadFotosAutomation:
    """O robô: um navegador, um login, várias fichas."""

    def __init__(self, esperas=None):
        self.engine = None
        self.portal = None
        self.esperas = esperas or Esperas()

    def iniciar_driver(self):
        self.engine = criar_engine(NOME_DO_MODULO, wait_timeout=self.esperas.motor_s)
        self.portal = PMIBPortal(self.engine)
        return self.engine

    def abrir_portal(self):
        self.engine.goto(config.PORTAL_URL)

    def fechar_driver(self):
        if self.engine:
            self.engine.fechar()

    def solicitar_parada(self):
        if self.portal:
            self.portal.solicitar_parada()

    def processar(self, fichas, modo=MODO_SUBSTITUIR, perguntar=None, callback_log=None):
        """`fichas` vem de `ligar_as_fichas`. Devolve um `ResultadoDaFicha` por
        ficha tentada; para entre uma ficha e outra se pedirem."""
        _log = _log_de(callback_log)
        resultados = []
        for indice, (pmib, quatro, caminhos) in enumerate(fichas, start=1):
            if self.portal.deve_parar():
                _log("Parada solicitada: as fichas seguintes não foram tocadas.")
                break
            _log(f"[{indice}/{len(fichas)}] {pmib}: {len(caminhos)} foto(s)")
            try:
                resultado = processar_ficha(self.portal, pmib, quatro, caminhos, modo,
                                            perguntar, callback_log, self.esperas)
            except Exception as erro:  # noqa: BLE001 -- uma ficha não derruba o lote
                resultado = ResultadoDaFicha(pmib, quatro, motivo=f"{type(erro).__name__}: {erro}")
            if resultado.ok:
                extra = "" if resultado.tem_documentos else " (sem documentos)"
                _log(f"   ✅ {pmib}: {len(caminhos)} foto(s) na ficha{extra}.")
            elif resultado.pulada:
                _log(f"   ⏭️ {pmib}: {resultado.motivo}.")
            else:
                _log(f"   ❌ {pmib}: {resultado.motivo}.")
            # Sem `ir_para_lista` aqui: `pesquisar_e_abrir` da próxima ficha já
            # vai para a lista, e voltar antes era uma carga de página a mais.
            resultados.append(resultado)
        return resultados


# ===========================================================================
# 4. A planilha
# ===========================================================================
def marcar_status(caminho_status, resultados, *, retry_lock=None, callback_log=None):
    """`DOCUMENTOS E IMAGENS` das fichas cujas fotos SUBIRAM: `COMPLETO` com
    documento, `INCOMPLETO` + nota "Faltam documentos" sem.

    Ficha que falhou ou foi pulada não é tocada: o robô não sabe o estado dela.
    Devolve `(quantas, recado)` e nunca levanta -- o trabalho no portal já foi
    feito e é a parte cara.
    """
    _log = _log_de(callback_log)
    feitas = [r for r in resultados if r.ok]
    if not feitas:
        return 0, "Nenhuma ficha com fotos subidas: o _STATUS_PMIB não foi alterado."
    try:
        painel = StatusPMIB(caminho_status)
        painel.abrir(keywords={config.COL_CODIGO_PMIB: config.COL_CODIGO_PMIB,
                               config.COL_DOCS_IMAGENS: config.COL_DOCS_IMAGENS},
                     required=[config.COL_CODIGO_PMIB], max_col=49)
    except Exception as erro:  # noqa: BLE001
        return 0, f"Não consegui abrir o _STATUS_PMIB: {type(erro).__name__}: {erro}"

    coluna = painel.col_map.get(config.COL_DOCS_IMAGENS)
    if not coluna:
        painel.fechar()
        return 0, f"A coluna '{config.COL_DOCS_IMAGENS}' não foi encontrada no _STATUS_PMIB: nada foi marcado."

    marcadas, nao_achadas = 0, []
    for resultado in feitas:
        linha = painel.buscar_linha(resultado.pmib)
        if linha is None:
            nao_achadas.append(resultado.pmib)
            continue
        if resultado.tem_documentos:
            painel.escrever(linha, coluna, VALOR_COMPLETO)
            painel.anotar(linha, coluna, None)  # a nota antiga do SIG-FT deixou de valer
        else:
            painel.escrever(linha, coluna, VALOR_INCOMPLETO)
            painel.anotar(linha, coluna, NOTA_FALTAM_DOCUMENTOS)
        marcadas += 1
        _log(f"   Planilha: {resultado.pmib} -> {config.COL_DOCS_IMAGENS} = "
             + (VALOR_COMPLETO if resultado.tem_documentos else f"{VALOR_INCOMPLETO} ({NOTA_FALTAM_DOCUMENTOS})"))

    try:
        if marcadas:
            painel.salvar(on_locked=lambda _t, _e: bool(retry_lock(caminho_status)) if retry_lock else False)
    except PermissionError:
        return 0, ("O _STATUS_PMIB está aberto no Excel e a marcação NÃO foi salva. As fotos já estão "
                   "no portal: feche a planilha e marque à mão.")
    except Exception as erro:  # noqa: BLE001
        return 0, f"Não consegui salvar o _STATUS_PMIB: {type(erro).__name__}: {erro}"
    finally:
        painel.fechar()

    recado = f"{marcadas} linha(s) marcada(s) no _STATUS_PMIB."
    if nao_achadas:
        recado += f" Não achei na planilha: {', '.join(nao_achadas)}."
    return marcadas, recado
