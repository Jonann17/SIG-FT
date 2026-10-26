# Copiado em parte de luanccozer/DocManager@c9683d2 (docmanager/aconex_backend.py): as constantes, CAMPOS_STRING, MAPA_COLUNAS, ORDEM_COLUNAS, _parse_pagina, classificar_fonte e montar_dataframe (aqui `tabela`). O token, a paginacao e o download viraram o ClienteAconex, sobre o core/rede do SIG-FT. Nao edite aqui sem levar ao DocManager -- PENDENCIAS 2026-10-26.
"""O cliente da API de documentos do Aconex: token OAuth, busca paginada, versões
de um código e download.

As requisições passam pelo `sigft/core/rede.py`, que já resolve a rede da CMI
(PAC do GlobalProtect, certificado do Zscaler). Regras fixadas no desenho
(`docs/superpowers/specs/2026-10-26-aconex-ao-vivo-design.md`, §4.2 e §8):

* 401 numa página: pede token novo e repete uma vez; o segundo 401 é erro;
* 503 (limite de volume ou de frequência): espera 5, 15 e 45 s; depois, erro;
* a paginação acaba no HTTP 400 ou na primeira página vazia (como no DocManager);
* nenhuma mensagem de `ErroAconex` traz o segredo ou o token.
"""
from __future__ import annotations

import base64
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass

import pandas as pd

from sigft.core import rede
from sigft.core.aconex import status_real
from sigft.core.aconex.credenciais import PerfilAconex

PROJECT_ID = "1207975853"
ACONEX_INSTANCE = "https://us1.aconex.com"
AUTH_URL = "https://constructionandengineering.oraclecloud.com/auth/token"

CAMPOS_STRING = (
    "statusid,current,trackingId,title,docno,revision,"
    "versionnumber,reviewstatus,Especialidad_singleSelect,"
    "Subespecialidad_singleSelect,doctype,registered,Dcc_singleSelect,"
    "ControlDelEmisor_singleLineText,Idioma_singleSelect,reviewsource,"
    "Disciplina_singleSelect,"
    "TipoDeDocumentoDcc_singleSelect,ControlCmi_singleLineText"
)
CAMPOS_DAS_VERSOES = "docno,current,filename,revision,versionnumber"

MAPA_COLUNAS = {
    "ControlDelEmisor_singleLineText": "Controle do Emissor",
    "DateModified": "Data de Alteração",
    "DocumentNumber": "No. do Documento",
    "Title": "Título",
    "Revision": "Revisão",
    "TrackingId": "Tracking ID",
    "DocumentStatus": "Status",
    "DocumentType": "Tipo do Documento",
    "ReviewSource": "Fonte",
    "ReviewStatus": "Status da Revisão",
    "VersionNumber": "Versão",
    "Idioma_singleSelect": "Idioma",
    "Subespecialidad_singleSelect": "Subespecialidade",
    "Especialidad_singleSelect": "Especialidade",
    "Dcc_singleSelect": "Subtipo DCC",
    "TipoDeDocumentoDcc_singleSelect": "Tipo do Documento DCC",
    "ControlCmi_singleLineText": "Control CMI",
    "Disciplina_singleSelect": "Disciplina (Modelo)",
}

ORDEM_COLUNAS = [
    "No. do Documento", "Controle do Emissor", "Tracking ID", "Revisão",
    "Data de Alteração", "Status", "Título", "Tipo do Documento",
    "Especialidade", "Subespecialidade", "Tipo do Documento DCC",
    "Subtipo DCC", "Fonte", "Tipo de Tramitação", "Status da Revisão", "Versão",
    "Current", "Idioma", "Control CMI", "Disciplina (Modelo)",
]

PAGE_SIZE = 500          # o register só aceita 25/50/.../500
PAGE_SIZE_VERSOES = 50   # as versões de um código cabem com folga
ESPERAS_503 = (5, 15, 45)
TIMEOUT_DOWNLOAD = 180


class ErroAconex(RuntimeError):
    """Falha ao falar com o Aconex. A mensagem nunca traz o segredo nem o token."""


@dataclass(frozen=True)
class Versao:
    document_id: str
    codigo: str
    revisao: str
    versao: int
    current: bool


def _tag_local(tag: str) -> str:
    return tag.split("}")[-1] if "}" in tag else tag


def _parse_pagina(conteudo: bytes) -> list[dict]:
    root = ET.fromstring(conteudo)
    docs = []
    for d in root.iter():
        if "Document" in d.tag and "Documents" not in d.tag:
            item = {}
            for field_el in d:
                tag = field_el.tag.split("}")[-1] if "}" in field_el.tag else field_el.tag
                if field_el.text is not None:
                    item[tag] = field_el.text
            if item:
                docs.append(item)
    return docs


def _ler_versoes(conteudo: bytes) -> list[Versao]:
    """As versões de uma página, com o `DocumentId` (atributo do `<Document>`)."""
    versoes = []
    for d in ET.fromstring(conteudo).iter():
        if _tag_local(d.tag) != "Document":
            continue
        document_id = d.attrib.get("DocumentId") or d.attrib.get("documentId")
        if not document_id:
            continue
        campos = {_tag_local(c.tag): (c.text or "").strip() for c in d}
        try:
            numero = int(float(campos.get("VersionNumber") or 0))
        except ValueError:
            numero = 0
        versoes.append(Versao(document_id, campos.get("DocumentNumber", ""), campos.get("Revision", ""),
                              numero, campos.get("Current", "").lower() == "true"))
    return versoes


def classificar_fonte(fonte) -> str:
    """Mecanismo de tramitação a partir da Fonte (ReviewSource): 'WF-…' Fluxo,
    número Transmissão, 'SD-…' Docs. Fornecedor, vazio/'Nenhum' ''."""
    s = str(fonte or "").strip()
    if not s or s.upper() == "NENHUM":
        return ""
    up = s.upper()
    if up.startswith("WF"):
        return "Fluxo"
    if up.startswith("SD"):
        return "Docs. Fornecedor"
    if s.replace("-", "").isdigit():
        return "Transmissão"
    return "Outro"


def tabela(registros: list[dict]) -> pd.DataFrame:
    """A tabela do extrato do DocManager (`montar_dataframe`) a partir dos registros da
    busca: colunas canônicas na ordem de `ORDEM_COLUNAS` (as novas vão para o fim),
    datas dd/mm/aaaa e `Current` booleano."""
    if not registros:
        return pd.DataFrame(columns=ORDEM_COLUNAS)
    df = pd.DataFrame(registros).dropna(how="all")
    df = df.rename(columns=MAPA_COLUNAS)
    if "Fonte" in df.columns:
        df["Tipo de Tramitação"] = df["Fonte"].map(classificar_fonte)
    existentes = [c for c in ORDEM_COLUNAS if c in df.columns]
    extras = [c for c in df.columns if c not in existentes]
    df = df[existentes + extras]
    for col in ("Data de Alteração", "registered", "FechaDeInicio_date", "FechaFin_date"):
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce").dt.strftime("%d/%m/%Y").fillna("")
    if "Current" in df.columns:
        df["Current"] = df["Current"].astype(str).str.lower() == "true"
    return df


class ClienteAconex:
    """Fala com o register do projeto em nome de um `PerfilAconex`. O token é pedido
    na primeira chamada e reaproveitado; `abrir` e `esperar` são injetáveis (testes)."""

    def __init__(self, perfil: PerfilAconex, *, abrir=None, esperar=time.sleep, log_cb=lambda _m: None):
        self._perfil = perfil
        self._abrir = abrir or rede.abrir
        self._esperar = esperar
        self._log = log_cb
        self._token: str | None = None

    def conectar(self) -> None:
        """Pede o token agora, se ainda não tem: prova o login antes de qualquer busca."""
        if self._token is None:
            self._token = self._pedir_token()

    @property
    def _register(self) -> str:
        return f"{ACONEX_INSTANCE}/api/projects/{PROJECT_ID}/register"

    def _requisitar(self, url: str, **kw):
        try:
            _sessao, resposta = self._abrir(url, status_ok=None, log_cb=self._log, **kw)
        except rede.FalhaDeRede as erro:
            raise ErroAconex(f"Sem conexão com o Aconex: {rede.resumo_erro(erro)}") from None
        return resposta

    def _pedir_token(self) -> str:
        credencial = base64.b64encode(f"{self._perfil.client_id}:{self._perfil.client_secret}".encode()).decode()
        resposta = self._requisitar(
            AUTH_URL, metodo="POST", timeout=30,
            headers={"Authorization": f"Basic {credencial}",
                     "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8"},
            data={"grant_type": "client_credentials", "user_id": self._perfil.user_id,
                  "user_site": ACONEX_INSTANCE})
        if resposta.status_code != 200:
            raise ErroAconex(f"O Aconex recusou as credenciais do perfil {self._perfil.nome} "
                             f"(HTTP {resposta.status_code}).")
        try:
            token = (resposta.json() or {}).get("access_token")
        except Exception:  # noqa: BLE001 -- resposta sem JSON: tratada abaixo
            token = None
        if not token:
            raise ErroAconex("O Aconex respondeu sem o token de acesso.")
        return token

    def _get(self, url: str, *, params: dict | None = None, timeout: int = 60, xml: bool = True):
        """GET autenticado: renova o token uma vez no 401 e espera no 503."""
        self.conectar()
        renovou = False
        esperas = iter(ESPERAS_503)
        while True:
            cabecalhos = {"Authorization": f"Bearer {self._token}"}
            if xml:
                cabecalhos["Accept"] = "application/xml"
            resposta = self._requisitar(url, metodo="GET", headers=cabecalhos, params=params, timeout=timeout)
            if resposta.status_code == 401:
                if renovou:
                    raise ErroAconex("O Aconex recusou as credenciais (HTTP 401).")
                renovou = True
                self._log("Token do Aconex expirado. Renovando...")
                self._token = self._pedir_token()
                continue
            if resposta.status_code == 503:
                espera = next(esperas, None)
                if espera is None:
                    raise ErroAconex("O Aconex continua acima do limite de uso (HTTP 503). Tente mais tarde.")
                self._log(f"Aconex acima do limite de uso (HTTP 503): esperando {espera} s...")
                self._esperar(espera)
                continue
            return resposta

    def _paginas(self, search_query: str, historico: bool, campos: str, page_size: int, ler) -> list:
        itens, pagina = [], 1
        while True:
            params = {"search_query": search_query, "return_fields": campos, "search_type": "PAGED",
                      "page_size": page_size, "page_number": pagina,
                      "show_document_history": "true" if historico else "false",
                      "sort_field": "docno", "sort_direction": "ASC"}
            resposta = self._get(self._register, params=params)
            if resposta.status_code == 400:      # fim normal da paginação
                return itens
            if resposta.status_code != 200:
                raise ErroAconex(f"A busca no Aconex falhou (HTTP {resposta.status_code}).")
            try:
                lidos = ler(resposta.content)
            except ET.ParseError:
                raise ErroAconex(f"Resposta ilegível do Aconex na página {pagina}.") from None
            if not lidos:
                return itens
            itens.extend(lidos)
            pagina += 1

    def buscar(self, search_query: str, *, historico: bool, campos: str = CAMPOS_STRING,
               page_size: int = PAGE_SIZE) -> list[dict]:
        """Os registros de todas as páginas da busca (campos como o XML os nomeia)."""
        return self._paginas(search_query, historico, campos, page_size, _parse_pagina)

    def versoes_do_codigo(self, codigo: str) -> list[Versao]:
        """Todas as versões do documento de código exato (busca entre aspas, com histórico)."""
        return self._paginas(f'"{codigo}"', True, CAMPOS_DAS_VERSOES, PAGE_SIZE_VERSOES, _ler_versoes)

    def versao_vigente(self, codigo: str) -> Versao | None:
        return next((v for v in self.versoes_do_codigo(codigo) if v.current), None)

    def versao(self, codigo: str, revisao: str) -> Versao | None:
        """A versão de maior número entre as da `revisao` (comparada sem caixa nem espaço)."""
        da_revisao = [v for v in self.versoes_do_codigo(codigo) if status_real.revisoes_iguais(v.revisao, revisao)]
        return max(da_revisao, key=lambda v: v.versao, default=None)

    def baixar(self, document_id: str) -> bytes:
        """O PDF da versão (`/markedup`, o caminho provado no DocManager)."""
        resposta = self._get(f"{self._register}/{document_id}/markedup", timeout=TIMEOUT_DOWNLOAD, xml=False)
        if resposta.status_code != 200 or not resposta.content:
            raise ErroAconex(f"O download do documento {document_id} falhou (HTTP {resposta.status_code}).")
        return resposta.content
