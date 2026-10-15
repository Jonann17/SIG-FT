r"""Conferência humana dos documentos DUVIDOSOS.

POR QUE EXISTE
------------------------------------------------------------------------
O filtro anti-intruso (§4.3) tem três destinos desde 2026-08-13:

    certo      cita o fabricante E um identificador -> vira contexto
    duvidoso   cita só uma das duas                 -> ninguém sabe
    descartado nenhuma                              -> fora

O `duvidoso` existe porque nenhuma regra automática resolve o caso. Numa
ficha real do Luan entrou uma **camiseta da Minnie no site do Target**,
porque a URL continha o código do material; e no mesmo lote um datasheet
legítimo de distribuidor foi barrado por não nomear a marca no título. Os
dois casos são indistinguíveis para o código — e **triviais para uma pessoa
que abre o link**.

Decisão do usuário (2026-08-13): em vez de descartar a dúvida, entregá-la.
O processamento roda a fila inteira, e no fim apresenta os links agrupados
por material. O engenheiro abre, marca o que serve, e uma **segunda passada**
usa só o que ele aprovou.

O QUE ESTE MÓDULO É, E O QUE NÃO É
------------------------------------------------------------------------
É a lógica: acumular, agrupar, e reprocessar com a seleção. **Não sabe nada
de tkinter** — devolve estruturas de dados e um generator de linhas de log,
igual ao `process_queue`. Isso é o princípio nº 2 da arquitetura ("UI nunca
contém regra de negócio; serviço nunca importa tkinter") e é o que permite
testar a conferência inteira sem abrir janela.

A tela correspondente vive em `frontend.py`, `class ModuloAutoSpec` — ver
`docs/refatoracao/TRABALHO_PARALELO.md` para o que o CP 7.3 precisa saber.

SALVAR E RETOMAR (2026-08-17)
------------------------------------------------------------------------
Relato do Luan depois de usar: conferir link por link leva tempo, e fechar o
aplicativo no meio **perdia o processamento inteiro** — os links, o
agrupamento e o que já tinha sido conferido. Rodar de novo custa cota de
busca e tempo de IA.

Daí `exportar_txt` / `importar_txt`: a aba vira um `.txt` na pasta do
`_STATUS_PMIB`, e volta de lá — inclusive noutro dia, com o aplicativo
reaberto do zero.

**Por que `.txt` e não JSON.** O arquivo é para ser lido e editado por uma
pessoa: abre no Bloco de Notas, clica no link, marca `[x]` no que serve.
Por isso o parser é deliberadamente tolerante — `[X]`, `[ x ]`, linha em
branco a mais, comentário escrito no meio, tudo passa. Um `JSONDecodeError`
por causa de uma vírgula seria exatamente o tipo de perda que este recurso
veio evitar.
"""
import datetime
import os
import re


class Pendencia:
    """Um material que ficou com documentos duvidosos.

    `ficha` é o caminho do `.xlsx`; `documentos` são os dicts que o
    `_baixar_resultados` guardou (`url`, `title`, `snippet`).
    """

    def __init__(self, ficha, material="", documentos=None, refs_locais=None):
        self.ficha = ficha
        self.material = material or os.path.basename(str(ficha))
        self.documentos = list(documentos or [])
        self.refs_locais = list(refs_locais or [])

    @property
    def nome_curto(self):
        return os.path.basename(str(self.ficha))

    def __repr__(self):  # pragma: no cover - conveniência de depuração
        return f"<Pendencia {self.nome_curto} {len(self.documentos)} doc(s)>"


class Conferencia:
    """Acumula as pendências do lote e devolve a seleção para a 2ª passada.

    Estado deliberadamente burro: a tela pergunta o que mostrar, marca o que
    o usuário escolheu, e devolve. Nenhuma regra de negócio aqui — as regras
    estão em `classificar_resultado`, que é quem decide o que é duvidoso.
    """

    def __init__(self):
        self._pendencias = []

    def registrar(self, ficha, material="", documentos=None, refs_locais=None):
        """Guarda os duvidosos de UMA ficha. Ficha sem duvidoso não entra —
        a lista de conferência só mostra o que precisa de decisão."""
        documentos = [d for d in (documentos or []) if d.get("url")]
        if not documentos:
            return None
        pendencia = Pendencia(ficha, material, documentos, refs_locais)
        self._pendencias.append(pendencia)
        return pendencia

    @property
    def pendencias(self):
        return list(self._pendencias)

    @property
    def total_documentos(self):
        return sum(len(p.documentos) for p in self._pendencias)

    def __bool__(self):
        return bool(self._pendencias)

    def limpar(self):
        self._pendencias = []

    def selecao_por_ficha(self, marcados):
        """`{caminho_da_ficha: [urls aprovadas]}` a partir do que a tela
        marcou.

        `marcados` é `{(indice_da_pendencia, indice_do_documento): bool}` —
        a forma que uma grade de checkbox produz naturalmente. Converter aqui
        deixa a tela sem lógica nenhuma.
        """
        selecao = {}
        for (i_pend, i_doc), marcado in (marcados or {}).items():
            if not marcado:
                continue
            if i_pend >= len(self._pendencias):
                continue
            pendencia = self._pendencias[i_pend]
            if i_doc >= len(pendencia.documentos):
                continue
            selecao.setdefault(pendencia.ficha, []).append(
                pendencia.documentos[i_doc]["url"]
            )
        return selecao

    def pendencia_da_ficha(self, ficha):
        for pendencia in self._pendencias:
            if pendencia.ficha == ficha:
                return pendencia
        return None


# =============================================================================
# Salvar e retomar: o `.txt` que aguenta mão humana
# =============================================================================
# `[  ]`, `[]`, `[x]`, `[X]`, `[ x ]`, `[*]` — tudo que sai de alguém marcando
# depressa no Bloco de Notas. A URL é o primeiro pedaço sem espaço depois do
# colchete.
_MARCA = re.compile(r"^\[\s*([xX*]?)\s*\]\s*(\S+)")
_CAMPO = re.compile(r"^(FICHA|MATERIAL|MANUAL|TITULO|TRECHO)\s*:\s*(.*)$", re.IGNORECASE)

CABECALHO = """\
# =============================================================================
# SIG-FT — Conferencia de documentos duvidosos (AutoSpec AI)
# Gerado em {quando}
# {total} documento(s) em {fichas} ficha(s) aguardando a sua conferencia
#
# COMO USAR
#   1. Abra cada link e veja se o documento e mesmo daquele material.
#   2. Se for, troque [ ] por [x]. Se nao for, deixe como esta.
#   3. Salve o arquivo (mantenha a extensao .txt).
#   4. No SIG-FT, tela "AutoSpec AI", clique em IMPORTAR CONFERENCIA (.txt)
#      e depois em PROCESSAR OS DOCUMENTOS MARCADOS.
#
# Pode parar no meio e continuar depois: o que voce marcar fica salvo aqui.
# NAO APAGUE as linhas FICHA:, MATERIAL: e MANUAL: — sao elas que dizem ao
# programa qual planilha reprocessar e com quais manuais.
# Linhas comecadas por # sao ignoradas.
# =============================================================================\
"""


def _uma_linha(texto):
    """Título e trecho do Google vêm com quebra de linha no meio. Uma linha
    virando duas desalinharia o arquivo inteiro."""
    return " ".join(str(texto or "").split())


def exportar_txt(conferencia, marcados=None):
    """A aba inteira como texto. `marcados` é o mesmo
    `{(i_pendencia, i_documento): bool}` da grade de checkbox — o que já foi
    conferido na tela sai conferido no arquivo."""
    marcados = marcados or {}
    quando = datetime.datetime.now().strftime("%d/%m/%Y as %H:%M")
    partes = [CABECALHO.format(
        quando=quando,
        total=conferencia.total_documentos if conferencia else 0,
        fichas=len(conferencia.pendencias) if conferencia else 0,
    )]

    for i_pend, pendencia in enumerate(conferencia.pendencias if conferencia else []):
        bloco = [f"FICHA: {pendencia.ficha}"]
        if pendencia.material:
            bloco.append(f"MATERIAL: {_uma_linha(pendencia.material)}")
        for ref in pendencia.refs_locais:
            bloco.append(f"MANUAL: {ref}")
        for i_doc, doc in enumerate(pendencia.documentos):
            marca = "x" if marcados.get((i_pend, i_doc)) else " "
            bloco.append(f"  [{marca}] {doc.get('url', '')}")
            if doc.get("title"):
                bloco.append(f"      TITULO: {_uma_linha(doc['title'])}")
            if doc.get("snippet"):
                bloco.append(f"      TRECHO: {_uma_linha(doc['snippet'])}")
        partes.append("\n".join(bloco))

    return "\n\n".join(partes) + "\n"


def importar_txt(texto):
    """Devolve `(Conferencia, marcados)` — pronto para a tela remontar a lista
    e para `selecao_por_ficha` alimentar a 2ª passada.

    Tolerante de propósito: linha que não é `FICHA:`/`MANUAL:`/marcação é
    ignorada em silêncio, e link sem `FICHA:` acima não tem planilha para
    reprocessar, então não entra.
    """
    conferencia = Conferencia()
    marcados = {}
    atual = {"ficha": None, "material": "", "refs": [], "docs": []}

    def _fechar():
        # O `and atual["ficha"]` e o unico lugar que garante "link sem FICHA:
        # acima nao entra" — sem planilha para reprocessar, o link nao tem
        # dono. Nao ha um segundo guard no laco de proposito: dois pontos
        # decidindo a mesma coisa e o comeco de eles discordarem.
        if atual["ficha"] and atual["docs"]:
            i_pend = len(conferencia.pendencias)
            pendencia = conferencia.registrar(
                atual["ficha"], atual["material"],
                [doc for doc, _ in atual["docs"]], atual["refs"],
            )
            if pendencia is not None:
                for i_doc, (_, marcado) in enumerate(atual["docs"]):
                    marcados[(i_pend, i_doc)] = marcado
        atual.update(ficha=None, material="", refs=[], docs=[])

    for linha_bruta in (texto or "").splitlines():
        linha = linha_bruta.strip()
        if not linha or linha.startswith("#"):
            continue

        marca = _MARCA.match(linha)
        if marca:
            doc = {"url": marca.group(2).strip(), "title": "", "snippet": ""}
            atual["docs"].append((doc, bool(marca.group(1).strip())))
            continue

        campo = _CAMPO.match(linha)
        if not campo:
            continue
        nome, valor = campo.group(1).upper(), campo.group(2).strip()
        if nome == "FICHA":
            _fechar()
            atual["ficha"] = valor
        elif nome == "MATERIAL":
            atual["material"] = valor
        elif nome == "MANUAL" and valor:
            atual["refs"].append(valor)
        elif nome in ("TITULO", "TRECHO") and atual["docs"]:
            atual["docs"][-1][0]["title" if nome == "TITULO" else "snippet"] = valor

    _fechar()
    return conferencia, marcados


def pasta_da_conferencia(status_pmib_path, conferencia=None):
    """A pasta do `_STATUS_PMIB` — decisão do usuário: é a que ele já tem
    aberta. Sem status utilizável, a da primeira ficha; em último caso, a
    pasta corrente. Nunca devolve nada que não exista, para não perder o
    arquivo do usuário num caminho inválido."""
    pasta = os.path.dirname(str(status_pmib_path or ""))
    if pasta and os.path.isdir(pasta):
        return pasta
    for pendencia in (conferencia.pendencias if conferencia else []):
        candidata = os.path.dirname(str(pendencia.ficha))
        if candidata and os.path.isdir(candidata):
            return candidata
    return os.getcwd()


def salvar_txt(conferencia, status_pmib_path, marcados=None, pasta=None):
    """Grava e devolve o caminho. `None` quando não há o que salvar.

    O nome leva data e hora, e nunca sobrescreve: perder a conferência de
    ontem ao exportar a de hoje seria o mesmo bug que este recurso veio
    consertar.
    """
    if not conferencia:
        return None
    destino = pasta or pasta_da_conferencia(status_pmib_path, conferencia)
    base = "CONFERENCIA_AUTOSPEC_" + datetime.datetime.now().strftime("%Y-%m-%d_%H%M%S")
    caminho = os.path.join(destino, base + ".txt")
    sufixo = 2
    while os.path.exists(caminho):
        caminho = os.path.join(destino, f"{base}_{sufixo}.txt")
        sufixo += 1
    with open(caminho, "w", encoding="utf-8") as arquivo:
        arquivo.write(exportar_txt(conferencia, marcados))
    return caminho


def carregar_txt(caminho):
    """Lê o arquivo do disco. UTF-8 primeiro; se o Bloco de Notas tiver
    salvado em ANSI (opção que o Windows ainda oferece), cai para cp1252 em
    vez de estourar — o acento é regra na planilha, não exceção."""
    with open(caminho, "rb") as arquivo:
        bruto = arquivo.read()
    for codificacao in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            return importar_txt(bruto.decode(codificacao))
        except UnicodeDecodeError:
            continue
    return importar_txt(bruto.decode("utf-8", errors="replace"))


def fichas_ausentes(conferencia):
    """Planilhas do `.txt` que não estão mais no lugar. O arquivo pode ter
    vindo de outra máquina, ou a ficha pode ter sido movida — descobrir na
    importação é melhor do que descobrir com a 2ª passada falhando uma a
    uma."""
    return [p.ficha for p in (conferencia.pendencias if conferencia else [])
            if not os.path.exists(str(p.ficha))]


def resumo_para_console(conferencia):
    """Linhas para o log do lote. Vazio quando não há o que conferir."""
    if not conferencia:
        return []
    linhas = [
        f"⚠️  {conferencia.total_documentos} documento(s) em "
        f"{len(conferencia.pendencias)} ficha(s) precisam da SUA conferencia.",
        "    Eles citam o fabricante OU o codigo, mas nao os dois — pode ser o",
        "    datasheet certo num distribuidor, pode ser pagina de outro produto.",
        "    Abra a secao 'Conferencia de documentos' abaixo da fila.",
    ]
    for pendencia in conferencia.pendencias:
        linhas.append(f"    · {pendencia.nome_curto}: {len(pendencia.documentos)} link(s)")
    return linhas
