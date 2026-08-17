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
"""
import os


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
