r"""
sigft/services/autorizacao_portal.py — confere no portal PMIB quais fichas a
Itaipu já autorizou para entrega (2026-10-14).

Pedido do Luan: saber quais fichas foram autorizadas sem esperar o export
`sobressalentes_autorizados_*.xlsx`. Botão "CONFERIR NO PORTAL" do Gestão PMIB.

O que é "autorizado"
--------------------
Ter o **código SAP de recebimento** ("Código de recepção/estoque" no cabeçalho
da ficha), criado na **autorização de entrega**. A aprovação da ficha é outra
etapa e não cria o código (correção do Luan, 2026-10-14). É o mesmo critério da
consulta que a Itaipu usa para o export -- ela vem na aba "SQL" do próprio
arquivo: solicitação de codificação não cancelada com `StockCodeSAP`
preenchido. Ver `sigft/core/rpa/respostas.codigo_sap`.

Só RPA
------
Regra do Luan (2026-10-14): a Itaipu proíbe contato com o banco de dados dela,
e o SIG-FT não chama o servidor por fora da tela. O robô pesquisa na lista e
abre a ficha como uma pessoa; o que ele lê é a resposta que o navegador
recebeu por causa disso (`RPAEngine.capturar_respostas`).

O fluxo
-------
1. Lê os `_STATUS_PMIB` vivos da Pasta Raiz: fichas FÍSICA E DOCUMENTAL ainda
   sem AUTORIZADO (`fichas_a_conferir`). Só elas precisam de autorização.
2. Abre a lista de fichas. Se ela não responde, para: quase sempre é login.
3. Etapa 1 -- pesquisa cada ficha na lista. Uma pesquisa recarrega as SETE
   abas (uma por status), e a resposta da aba onde a ficha está traz o Id
   interno dela. Nada de percorrer abas.
4. Etapa 2 -- abre cada ficha achada pelo link direto
   (`PMIB_DataSheetView?PMIB_DataSheetId=<Id>`) e lê a solicitação de
   codificação que o cabeçalho recebe.
5. As que têm código SAP viram AUTORIZADO pela MESMA gravação do export
   (`autorizados.aplicar`), com a data da conferência no lugar da data do
   export -- os dias de atraso seguem a regra de sempre.

Fichas seguidas sem resposta (sessão que expirou, navegador fechado) param a
conferência; o que já foi lido continua valendo.

⚠️ `scripts/check.sh` verde não é prova de portal: os testes rodam contra um
portal de mentira escrito a partir do código das telas. A validação é a
primeira execução real, com login.
"""
from __future__ import annotations

import datetime as dt
import os
import time

from sigft import config
from sigft.core.excel import pmib_codes, status_sheet
from sigft.core.rpa import respostas
from sigft.core.rpa.factory import criar_engine
from sigft.core.rpa.seletores_duplicada import XPATH_BUSCA_DA_LISTA
from sigft.services import autorizacao, autorizados, status_pmib_arquivos

# Quanto se espera cada resposta. A espera acaba assim que ela chega; a folga é
# para o portal lento (a primeira página do PMIB já levou 11 s para responder).
TIMEOUT_LISTA_S = 30.0
TIMEOUT_FICHA_S = 30.0
# As pausas do `pesquisar_e_abrir` entre limpar, digitar e o ENTER --
# calibradas no portal real. A espera fixa de 4 s depois do ENTER, essa sim,
# deu lugar à resposta da lista.
PAUSA_DIGITACAO_S = 0.5
# Tantas fichas seguidas sem resposta e a conferência para.
SEGUIDAS_SEM_RESPOSTA_PARA_PARAR = 3
ORIGEM = "conferidos no portal"


def fichas_a_conferir(pasta_raiz):
    """`(pmibs, avisos)`: os PMIBs FÍSICA E DOCUMENTAL sem AUTORIZADO nos
    `_STATUS_PMIB` vivos da pasta, normalizados, e uma linha de log para cada
    arquivo que não pôde ser conferido (e por quê)."""
    pmibs: set[str] = set()
    avisos: list[str] = []
    chaves = {c: c for c in (config.COL_CODIGO_PMIB, config.COL_TIPO_ENTREGA,
                             config.COL_SITUACAO_AUTORIZACAO)}
    for _codigo, caminho in status_pmib_arquivos.listar(pasta_raiz).vivos:
        nome = os.path.basename(caminho)
        if not caminho.lower().endswith(".xlsx"):
            avisos.append(f"[AVISO] {nome}: formato antigo, não conferido.")
            continue
        painel = status_sheet.StatusPMIB(caminho, config.ABA_LISTA_MATERIAIS)
        try:
            col_map, linha_cabecalho = painel.abrir(keywords=chaves, required=[config.COL_CODIGO_PMIB],
                                                    max_row=10, normalize=autorizacao.normalizar)
        except KeyError:
            avisos.append(f"[AVISO] {nome}: não tem a aba '{config.ABA_LISTA_MATERIAIS}', não conferido.")
            continue
        except Exception as erro:  # noqa: BLE001 -- vira aviso; os outros arquivos seguem
            avisos.append(f"[AVISO] {nome}: não consegui ler ({type(erro).__name__}), não conferido.")
            continue
        try:
            faltam = [c for c in (config.COL_TIPO_ENTREGA, config.COL_SITUACAO_AUTORIZACAO) if c not in col_map]
            if linha_cabecalho is None or faltam:
                avisos.append(f"[AVISO] {nome}: sem a coluna {', '.join(faltam) or config.COL_CODIGO_PMIB} "
                              "(layout antigo?), não conferido.")
                continue
            ws = painel.ws
            for r in range(linha_cabecalho + 1, ws.max_row + 1):
                valor = ws.cell(row=r, column=col_map[config.COL_CODIGO_PMIB]).value
                if valor in (None, ""):
                    continue
                tipo = ws.cell(row=r, column=col_map[config.COL_TIPO_ENTREGA]).value
                if autorizacao.tipo_canonico(tipo) != autorizacao.FISICA_E_DOCUMENTAL:
                    continue
                situacao = ws.cell(row=r, column=col_map[config.COL_SITUACAO_AUTORIZACAO]).value
                if autorizacao.normalizar(situacao) == autorizacao.AUTORIZADO:
                    continue
                pmibs.add(pmib_codes.normalize_pmib(valor))
        finally:
            painel.fechar()
    return pmibs, avisos


def _lista(pmibs, limite=20):
    ordem = sorted(pmibs)
    return ", ".join(ordem[:limite]) + ("..." if len(ordem) > limite else "")


class ConferenciaNoPortal:
    """A conferência, sobre um motor de RPA. A tela cria com
    `iniciar_navegador()`; os testes passam um motor de mentira."""

    def __init__(self, engine=None):
        self.engine = engine

    def iniciar_navegador(self):
        self.engine = criar_engine("autorizacao_portal", wait_timeout=20)
        return self.engine

    def abrir_portal(self):
        if self.engine:
            self.engine.goto(config.PORTAL_URL)

    def fechar_navegador(self):
        if self.engine:
            self.engine.fechar()

    # ------------------------------------------------------------------
    def _capturar(self, trecho_url, acao, **opcoes):
        """As respostas da ação, ou `[]` se a ação nem rodou (a tela não
        estava lá: login, navegador fechado). Nunca levanta."""
        try:
            return self.engine.capturar_respostas(trecho_url, acao, **opcoes)
        except Exception:  # noqa: BLE001 -- conta como "sem resposta"
            return []

    def _pesquisar(self, pmib):
        self.engine.clear(XPATH_BUSCA_DA_LISTA)
        time.sleep(PAUSA_DIGITACAO_S)
        self.engine.type_text(XPATH_BUSCA_DA_LISTA, pmib)
        time.sleep(PAUSA_DIGITACAO_S)
        self.engine.press("ENTER")

    def _localizar(self, pmib):
        """Pesquisa `pmib` e devolve as respostas da lista: para na aba que
        traz a ficha, ou depois das sete."""
        return self._capturar(
            respostas.URL_LISTA_DE_FICHAS, lambda: self._pesquisar(pmib),
            quantas=respostas.ABAS_DA_LISTA,
            ate=lambda corpo: respostas.id_da_ficha([corpo], pmib) is not None,
            timeout_s=TIMEOUT_LISTA_S)

    def executar(self, pasta_raiz, *, callback_travados=None, hoje=None):
        """Confere e grava. Generator de linhas de log (o contrato das telas).

        `callback_travados`: o de `autorizados.aplicar` (arquivo aberto no
        Excel). `hoje`: a data da conferência, que vale como data da
        autorização nos dias de atraso."""
        hoje = hoje or dt.date.today()
        yield "Lendo os _STATUS_PMIB da Pasta Raiz..."
        pmibs, avisos = fichas_a_conferir(pasta_raiz)
        yield from avisos
        yield f" -> {len(pmibs)} ficha(s) FÍSICA E DOCUMENTAL ainda sem AUTORIZADO."
        if not pmibs:
            return
        if not getattr(self.engine, "captura_respostas_disponivel", False):
            yield "[ERRO] Este navegador não lê as respostas do portal: a conferência não roda nele."
            return

        yield "Abrindo a lista de fichas do portal..."
        if not self._capturar(respostas.URL_LISTA_DE_FICHAS, lambda: self.engine.goto(config.PORTAL_URL),
                              quantas=respostas.ABAS_DA_LISTA, timeout_s=TIMEOUT_LISTA_S):
            yield ("[ERRO] A lista de fichas do portal não respondeu. Confira se o login foi feito e se a "
                   "lista abre no navegador; depois clique de novo em CONFERIR NO PORTAL.")
            return

        ordem = sorted(pmibs)
        ids: dict[str, str] = {}
        nao_achadas: list[str] = []
        sem_resposta: list[str] = []
        parou = False

        yield f"Etapa 1 de 2: localizando {len(ordem)} ficha(s) no portal..."
        seguidas = 0
        for posicao, pmib in enumerate(ordem, start=1):
            chegaram = self._localizar(pmib)
            if not chegaram:
                sem_resposta.append(pmib)
                seguidas += 1
                if seguidas >= SEGUIDAS_SEM_RESPOSTA_PARA_PARAR:
                    parou = True
                    break
                continue
            seguidas = 0
            ident = respostas.id_da_ficha(chegaram, pmib)
            if not ident:
                # Respostas atrasadas de uma carga anterior da lista podem ter
                # completado a contagem desta pesquisa: pesquisa de novo antes
                # de dar a ficha por não encontrada. O Id nunca sai errado --
                # a linha é casada pelo código --, mas a ausência pode.
                ident = respostas.id_da_ficha(self._localizar(pmib), pmib)
            if ident:
                ids[pmib] = ident
            else:
                nao_achadas.append(pmib)
            if posicao % 25 == 0:
                yield f" -> {posicao}/{len(ordem)} pesquisada(s)..."

        codigos: dict[str, str] = {}
        sem_codigo: list[str] = []
        if not parou and ids:
            yield f"Etapa 2 de 2: lendo o código SAP de recebimento de {len(ids)} ficha(s)..."
            seguidas = 0
            for pmib, ident in ids.items():
                url = respostas.url_da_ficha(ident)
                chegaram = self._capturar(respostas.URL_CODIFICACAO_DA_FICHA,
                                          lambda u=url: self.engine.goto(u), quantas=1,
                                          timeout_s=TIMEOUT_FICHA_S)
                if not chegaram:
                    sem_resposta.append(pmib)
                    seguidas += 1
                    if seguidas >= SEGUIDAS_SEM_RESPOSTA_PARA_PARAR:
                        parou = True
                        break
                    continue
                seguidas = 0
                codigo = respostas.codigo_sap(chegaram[0])
                if codigo:
                    codigos[pmib] = codigo
                    yield f" -> {pmib}: código SAP de recebimento {codigo} -> AUTORIZADO"
                else:
                    sem_codigo.append(pmib)

        if parou:
            yield (f"[AVISO] Parei: {SEGUIDAS_SEM_RESPOSTA_PARA_PARAR} fichas seguidas sem resposta do portal "
                   "(a sessão pode ter expirado ou o navegador foi fechado). O que já foi lido vale; "
                   "clique de novo para conferir o resto.")
        yield (f" -> Conferência: {len(codigos)} autorizada(s) agora, {len(sem_codigo)} ainda sem código SAP, "
               f"{len(nao_achadas)} não encontrada(s) no portal, {len(sem_resposta)} sem resposta.")
        if nao_achadas:
            yield (f"[AVISO] {len(nao_achadas)} ficha(s) não encontrada(s) no portal (confira o código no "
                   f"_STATUS_PMIB): {_lista(nao_achadas)}")
        if sem_resposta:
            yield f"[AVISO] {len(sem_resposta)} ficha(s) sem resposta do portal: {_lista(sem_resposta)}"
        if not codigos:
            yield " -> Nenhuma ficha nova com código SAP: nada a gravar."
            return

        yield f"Gravando AUTORIZADO nos _STATUS_PMIB (data da conferência: {hoje.strftime('%d/%m/%Y')})..."
        yield from autorizados.aplicar(set(codigos), pasta_raiz, data_autorizacao=hoje,
                                       callback_travados=callback_travados, origem=ORIGEM)
