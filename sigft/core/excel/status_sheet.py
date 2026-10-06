r"""
sigft/core/excel/status_sheet.py — leitura/escrita unificada da linha de um
PMIB na planilha `_STATUS_PMIB` (Checkpoint 1.3 do plano de refatoração).

Ver docs/refatoracao/PLANO_REFATORACAO.md, Fase 1 -> CP 1.3, diagnóstico
seção 1.2: "Marcar seção 'COMPLETO' no `_STATUS_PMIB` | 3×:
`upload_conditions.atualizar_status_excel`,
`tech_specs.executar_pipeline_rpa` (inline), `AtualizadorStatusPMIB`".

`StatusPMIB` unifica a MECÂNICA compartilhada pelos 3 escritores de
"COMPLETO" listados acima (e reaproveitada por `pmib_manager_backend`, que
usa só a metade "lock" do checkpoint via `locking.py` — ver lá):

  1. **abrir a planilha** e achar as colunas relevantes via
     `core.excel.headers` (`find_columns`/`rows_from_worksheet`, ambos do
     CP 1.2) — NÃO reimplementa busca de cabeçalho.
  2. **buscar a linha de um PMIB** dentro da planilha já aberta, comparando
     com `core.excel.pmib_codes.normalize_pmib` (canônico do CP 1.2) — NÃO
     reimplementa normalização.
  3. **marcar seções como "COMPLETO"** na linha encontrada.
  4. **salvar com retry** via `core.excel.locking.save_with_retry` (CP 1.3)
     — NÃO reimplementa laço de `PermissionError`. Desde a T1 do roteiro do
     Gestão PMIB v2 (2026-10-05), quem grava é o editor cirúrgico
     (`core/excel/cirurgico.py`), nunca o `wb.save` -- ver "Gravação sem
     perda" abaixo.

Metodologia: a classe expõe tanto o método de conveniência de ponta a ponta
citado explicitamente no plano — `marcar_completo(pmib, secoes)`, usado
"as is" pelos casos mais simples — quanto os PASSOS individuais (`abrir`,
`buscar_linha`, `marcar_linha`, `salvar`, `fechar`), para os 3 call sites
reais que precisam preservar UX/mensagens de erro PRÓPRIAS e distintas em
cada etapa (fallback de coluna fixa em `upload_conditions`, mensagem
dedicada de "cabeçalho não encontrado" em `upload_ficha_duplicada`, "pular
tudo sem erro" em `upload_tech_specs`) — ver os 3 backends migrados para o
uso exato de cada um.

Testabilidade — openpyxl fica NA BORDA: o import de `openpyxl` é PREGUIÇOSO
(só acontece dentro de `abrir()`, e só quando `abrir()` não recebe um
`wb`/`ws` já prontos) — este módulo continua stdlib-only até o momento em
que `abrir()` de fato precisa ler um arquivo `.xlsx` real. Testes passam um
worksheet FALSO (objeto duck-typed em memória, sem depender do pacote
openpyxl instalado — ver `tests/test_status_sheet.py`), exatamente como
`tests/test_headers.py` já faz para `headers.rows_from_worksheet`.

Este módulo é o consumidor de referência de `pmib_codes`/`headers`/
`locking`/`sigft.config` — não reintroduz busca de cabeçalho nem
normalização de PMIB.

Gravação sem perda (2026-10-05, T1 do roteiro do Gestão PMIB v2)
-----------------------------------------------------------------
`salvar()` chamava `wb.save()` do openpyxl, que regrava o arquivo inteiro e
APAGA o que não entende: os comentários em thread (16 dos 47 `_STATUS_PMIB`
tinham em 04/10/2026) e as listas suspensas gravadas como extensão. Cada
"COMPLETO" que o SIG-FT marcava levava junto os comentários da planilha.

Agora a leitura continua com openpyxl (`abrir`), mas a ESCRITA é registrada:
`escrever`/`marcar_linha` mudam a célula na aba aberta (para a leitura seguinte
ver o valor novo) e anotam `(linha, coluna) -> valor`. O `salvar()` aplica só
essas células com o editor cirúrgico (`core/excel/cirurgico.py`), que regrava o
resto do pacote byte a byte. **`wb.save` não é mais chamado por este módulo.**

A cada tentativa o arquivo é RELIDO do disco antes de aplicar as células: se a
pessoa fechou o Excel salvando alguma coisa entre uma tentativa e outra, o que
ela salvou fica -- só as nossas células são reescritas.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, Callable, Iterable, Mapping

from sigft import config
from sigft.core.excel import headers, locking, pmib_codes

# Assinatura de quem grava: `(caminho, aba, escritas, *, nomes, formato_geral)`.
# O padrão é `core.excel.cirurgico.gravar_celulas`; os testes injetam um dublê.
Gravador = Callable[..., None]

# Valor gravado nas células de seção quando uma seção é marcada como
# concluída — literal ÚNICO usado pelos 3 escritores originais
# (`ws.cell(...).value = "COMPLETO"`).
VALOR_COMPLETO = "COMPLETO"

# O contrário, pedido pelo usuário em 2026-08-17 para a ficha duplicada: *"se
# por fim você não conseguir, deixa em branco e daí na hora de completar o
# _STATUS_PMIB você coloca na coluna de Informações Gerais como INCOMPLETO
# para a ficha. Para as colunas que você conseguir preencher tudo, você coloca
# como COMPLETO"*.
#
# Vive aqui, ao lado do irmão, porque é a MESMA decisão: o que se escreve na
# célula de seção do `_STATUS_PMIB`. Deixar um em cada módulo é como nasce a
# planilha com "INCOMPLETO" numa coluna e "Incompleto" na outra.
VALOR_INCOMPLETO = "INCOMPLETO"


class StatusPMIB:
    """Acesso unificado à linha de um PMIB dentro da aba
    `config.ABA_LISTA_MATERIAIS` de um arquivo `_STATUS_PMIB`.

    Uso mínimo (caso simples, 1 PMIB por vez):
        >>> StatusPMIB(caminho).marcar_completo(
        ...     "4500063671.1234", [config.COL_CONDICOES]
        ... )

    Uso composto (lote — abre/acha cabeçalho 1x, marca N PMIBs, salva 1x):
        >>> painel = StatusPMIB(caminho)
        >>> painel.abrir(keywords={...})
        >>> for pmib in pmibs:
        ...     linha = painel.buscar_linha(pmib)
        ...     if linha is not None:
        ...         painel.marcar_linha(linha, [config.COL_CARACT_TECNICAS])
        >>> painel.salvar()
        >>> painel.fechar()
    """

    def __init__(self, caminho_excel, nome_aba: str | None = None, *,
                 gravar: Gravador | None = None) -> None:
        self.caminho_excel = caminho_excel
        self.nome_aba = nome_aba or config.ABA_LISTA_MATERIAIS
        # Quem grava no `salvar()`. `None` = o editor cirúrgico, importado só
        # na hora de gravar (ele precisa do `lxml`; ler não precisa).
        self._gravar = gravar

        # Estado populado por `abrir()`.
        self.wb: Any | None = None
        self.ws: Any | None = None
        self.col_map: dict[str, int] = {}
        self.header_row: int | None = None

        # O que o `salvar()` vai gravar -- ver "Gravação sem perda" no
        # docstring do módulo. Dicionário: a mesma célula escrita duas vezes
        # grava o último valor.
        self._escritas: dict[tuple[int, int], Any] = {}
        self._nomes: dict[str, str] = {}
        self._formato_geral: set[tuple[int, int]] = set()

    @property
    def escritas_pendentes(self) -> dict[tuple[int, int], Any]:
        """Cópia do que ainda não foi gravado: `{(linha, coluna): valor}`."""
        return dict(self._escritas)

    def escrever(self, linha: int, coluna: int, valor: Any, *, formato_geral: bool = False) -> None:
        """Escreve `valor` na célula, EM MEMÓRIA, e a anota para o `salvar()`.

        `formato_geral=True`: a célula guarda NÚMERO e pode ter herdado formato
        de data da coluna vizinha (o DIAS DE ATRASO herdou em 33 arquivos) --
        ao gravar, o estilo dela troca para formato Geral; sem isso, 4 aparece
        como 04/01/1900.
        """
        self.ws.cell(row=linha, column=coluna).value = valor  # type: ignore[union-attr]
        self._escritas[(linha, coluna)] = valor
        if formato_geral:
            self._formato_geral.add((linha, coluna))

    def definir_nome(self, nome: str, referencia: str) -> None:
        """Nome definido GLOBAL a gravar no próximo `salvar()` -- ex.:
        `definir_nome("sigft_calculado_em", '"2026-10-10"')`."""
        self._nomes[nome] = referencia

    def _nome_da_aba(self) -> str:
        """O nome REAL da aba aberta (o openpyxl o expõe em `.title`): quem
        chama pode ter aberto outra aba que não `self.nome_aba`."""
        titulo = getattr(self.ws, "title", None)
        return titulo if isinstance(titulo, str) and titulo else self.nome_aba

    # ------------------------------------------------------------------
    # 1. Carregar (abrir workbook/worksheet + achar colunas via headers)
    # ------------------------------------------------------------------
    def abrir(
        self,
        *,
        wb: Any | None = None,
        ws: Any | None = None,
        keywords: Mapping[str, str | Iterable[str]] | None = None,
        required: Iterable[str] | None = None,
        max_row: int | None = 15,
        max_col: int | None = None,
        **load_kwargs: Any,
    ) -> tuple[dict[str, int], int | None]:
        """Abre a planilha (ou reaproveita `wb`/`ws` já abertos — ESSENCIAL
        para testar sem openpyxl real, e para deixar quem chama controlar
        exatamente como o workbook foi carregado, ex.:
        `openpyxl.load_workbook(caminho, data_only=True)`) e localiza as
        colunas de `keywords` via `core.excel.headers.find_columns`.

        Parâmetros:
          wb/ws: se `ws` for informado, é usado DIRETAMENTE (nenhum import
            de openpyxl acontece) — `wb` só é necessário depois, para
            `salvar()`/`fechar()`. Se `ws` for `None`, abre de verdade:
            usa `wb` se informado, senão importa `openpyxl` (PREGUIÇOSO,
            só aqui) e chama `openpyxl.load_workbook(self.caminho_excel,
            **load_kwargs)`; a aba usada é `wb[self.nome_aba]`.
          keywords: repassado a `headers.find_columns` — default
            `{config.COL_CODIGO_PMIB: config.COL_CODIGO_PMIB}` (busca só a
            coluna-âncora; a maioria dos consumidores passa seu próprio
            dict maior, incluindo as colunas de seção que quer marcar).
          required: repassado a `headers.find_columns` (default `None` =
            todas as chaves de `keywords` são obrigatórias — mesmo default
            de `find_columns`).
          max_row/max_col: repassados a `headers.rows_from_worksheet`
            (mesmo alcance que cada consumidor original já usava: 15
            linhas é o valor mais comum entre os 3 escritores de
            "COMPLETO"; `max_col` fica `None`/sem limite por padrão, exceto
            em `upload_conditions`, que restringe a 49 colunas como o
            original).

        Guarda `self.wb`, `self.ws`, `self.col_map`, `self.header_row` e
        também RETORNA `(col_map, header_row)` (conveniência — muitos
        chamadores só precisam checar `header_row is None` em seguida).
        """
        if ws is None:
            if wb is None:
                import openpyxl  # import preguiçoso -- ver docstring do módulo

                wb = openpyxl.load_workbook(self.caminho_excel, **load_kwargs)
            ws = wb[self.nome_aba]

        self.wb = wb
        self.ws = ws

        keywords_efetivo: Mapping[str, str | Iterable[str]] = (
            keywords if keywords is not None else {config.COL_CODIGO_PMIB: config.COL_CODIGO_PMIB}
        )
        linhas = headers.rows_from_worksheet(ws, max_row=max_row, max_col=max_col)
        self.col_map, self.header_row = headers.find_columns(
            linhas, keywords_efetivo, required=required, max_rows=max_row
        )
        return self.col_map, self.header_row

    # ------------------------------------------------------------------
    # 2. Buscar linha por PMIB
    # ------------------------------------------------------------------
    def buscar_linha(
        self,
        pmib: Any,
        *,
        col_pmib: int | None = None,
        header_row: int | None = None,
    ) -> int | None:
        """Varre `self.ws` (a partir da linha seguinte ao cabeçalho)
        procurando a linha cuja célula na coluna do CÓDIGO PMIB normaliza
        (`pmib_codes.normalize_pmib`) para o MESMO valor que `pmib`
        normalizado. Retorna o número da linha (1-based, convenção
        openpyxl) da PRIMEIRA ocorrência, ou `None` se não encontrar — o
        mesmo critério de "1ª ocorrência ganha" dos 3 laços originais.

        `col_pmib`/`header_row` default para o que `abrir()` já descobriu
        (`self.col_map.get(config.COL_CODIGO_PMIB)` / `self.header_row`);
        um chamador pode sobrescrever os dois — usado por
        `upload_conditions_backend.atualizar_status_excel`, que aplica um
        FALLBACK de coluna fixa (8) e linha de cabeçalho (1) quando a busca
        dinâmica não encontra nada, preservando o comportamento original
        daquele call site específico (`StatusPMIB` não embute esse
        fallback — é uma escolha só daquele consumidor).

        Retorna `None` sem varrer nada se não houver coluna de PMIB
        resolvida (nem via parâmetro, nem via `self.col_map`).
        """
        if col_pmib is None:
            col_pmib = self.col_map.get(config.COL_CODIGO_PMIB)
        if not col_pmib:
            return None

        if header_row is None:
            header_row = self.header_row if self.header_row is not None else 0

        alvo = pmib_codes.normalize_pmib(pmib)
        # `self.ws` so e None antes de `abrir()`; estes metodos exigem a
        # planilha aberta e ja falhariam antes de chegar aqui.
        limite_linha = self.ws.max_row  # type: ignore[union-attr]
        for linha in range(header_row + 1, limite_linha + 1):
            valor_bruto = self.ws.cell(row=linha, column=col_pmib).value  # type: ignore[union-attr]
            if valor_bruto is None:
                continue
            if pmib_codes.normalize_pmib(valor_bruto) == alvo:
                return linha
        return None

    # ------------------------------------------------------------------
    # 3. Marcar seções como "COMPLETO" (em memória — não salva)
    # ------------------------------------------------------------------
    def marcar_linha(
        self,
        linha: int,
        secoes: Mapping[str, object] | Iterable[str],
        *,
        valor: Any = VALOR_COMPLETO,
    ) -> list[str]:
        """Escreve `valor` (default `"COMPLETO"`) nas colunas de `secoes`
        para a `linha` dada, EM MEMÓRIA (não salva — ver `salvar()`).

        `secoes` aceita duas formas, cobrindo os 3 escritores originais:
          - `Mapping[str, bool-like]` (ex.:
            `{"INFO. GERAIS": True, "CONDIÇÕES": False}`): só as chaves com
            valor "truthy" são marcadas — o padrão de
            `AtualizadorStatusPMIB.atualizar_ficha_concluida`
            (`secoes_concluidas`).
          - `Iterable[str]` (ex.: `["CARACT. TÉCNICAS"]`): todas as chaves
            são marcadas — equivalente a um dict onde todo valor é `True`;
            forma mais direta para o caso de 1 seção só
            (`upload_conditions`/`upload_tech_specs`).

        Cada nome de seção é procurado em `self.col_map` primeiro
        EXATAMENTE como veio, depois em maiúsculas (`.upper()`) — cobre
        tanto quem já passa a chave exatamente como o cabeçalho da planilha
        (ex.: `config.COL_CONDICOES` = `"CONDIÇÕES"`) quanto quem monta
        `secoes` com grafia livre e conta com a normalização
        (`AtualizadorStatusPMIB`, que já faz `nome_secao.upper()` para
        montar as PRÓPRIAS `keywords` de `abrir()` — aqui replicamos o
        mesmo `.upper()` do lado da ESCRITA para ficar simétrico).

        Seções cuja coluna não foi encontrada em `self.col_map` são
        silenciosamente IGNORADAS (mesmo comportamento dos 3 originais:
        `if chave_secao in colunas_map` / checagem equivalente antes de
        escrever).

        Retorna a lista de nomes de seção que foram DE FATO marcados
        (subconjunto de `secoes` que tinha valor truthy E coluna
        resolvida) — conveniência para quem quiser logar o que mudou.
        """
        if isinstance(secoes, Mapping):
            itens = list(secoes.items())
        else:
            itens = [(nome, True) for nome in secoes]

        marcadas: list[str] = []
        for nome_secao, ativo in itens:
            if not ativo:
                continue
            coluna = self.col_map.get(nome_secao)
            if coluna is None:
                coluna = self.col_map.get(str(nome_secao).upper())
            if coluna is None:
                continue
            self.escrever(linha, coluna, valor)
            marcadas.append(nome_secao)
        return marcadas

    # ------------------------------------------------------------------
    # 4. Salvar (editor cirúrgico + locking.save_with_retry)
    # ------------------------------------------------------------------
    def salvar(self, **kwargs: Any) -> bool:
        """Grava as células anotadas (e os nomes definidos) com o editor
        cirúrgico, por cima do arquivo, com o retry de
        `locking.save_with_retry(..., **kwargs)` -- mesmo contrato de
        `on_locked`/`max_attempts`/etc. de antes: devolve `True` ao gravar e
        deixa o `PermissionError` subir quando a política desiste.

        Sem nada anotado, devolve `True` sem tocar no arquivo: regravá-lo igual
        só criaria uma versão vazia no Box.
        """
        if not self._escritas and not self._nomes:
            return True

        gravar = self._gravar
        if gravar is None:
            from sigft.core.excel import cirurgico  # precisa do lxml -- só aqui

            gravar = cirurgico.gravar_celulas
        aba = self._nome_da_aba()
        escritas, nomes, geral = dict(self._escritas), dict(self._nomes), set(self._formato_geral)

        # O `save(caminho)` que o `save_with_retry` chama a cada tentativa:
        # relê o arquivo e reaplica as células (ver o docstring do módulo).
        gravacao = SimpleNamespace(
            save=lambda caminho: gravar(caminho, aba, escritas, nomes=nomes, formato_geral=geral))
        resultado = locking.save_with_retry(gravacao, self.caminho_excel, **kwargs)
        self._escritas.clear()
        self._nomes.clear()
        self._formato_geral.clear()
        return resultado

    def fechar(self) -> None:
        """`self.wb.close()`, se houver um `wb` de verdade associado
        (no-op silencioso se `abrir()` só recebeu `ws`, sem `wb` — cenário
        de teste com worksheet falsa)."""
        if self.wb is not None and hasattr(self.wb, "close"):
            self.wb.close()

    # ------------------------------------------------------------------
    # 5. Conveniência ponta a ponta — a assinatura citada no plano
    # ------------------------------------------------------------------
    def marcar_completo(
        self,
        pmib: Any,
        secoes: Mapping[str, object] | Iterable[str],
        *,
        salvar: bool = True,
        fechar: bool = True,
        **save_kwargs: Any,
    ) -> bool:
        """Fluxo completo de conveniência: abre (se `abrir()` ainda não foi
        chamado nesta instância), acha a linha do `pmib`, marca `secoes`
        como `"COMPLETO"`, salva (se `salvar=True`) e fecha (se
        `fechar=True`) — nesta ordem, com `fechar()` garantido mesmo se
        `salvar()` levantar (ex.: `PermissionError` depois de `on_locked`
        abortar) via `finally`.

        Se `self.abrir()` ainda não foi chamado (`self.ws is None`), chama
        `self.abrir()` sem argumentos (busca só `config.COL_CODIGO_PMIB`,
        15 linhas) — para controlar `keywords`/`required`/`max_row` (o
        caso comum, já que a maioria dos consumidores quer buscar TAMBÉM
        as colunas de `secoes`), chame `self.abrir(...)` explicitamente
        ANTES de `marcar_completo(...)`.

        Retorna `True` se o PMIB foi encontrado (e as seções ativas
        marcadas); `False` se o PMIB não foi encontrado na planilha (nada é
        escrito nem salvo nesse caso). Propaga qualquer exceção de
        `abrir()`/`salvar()` (ex.: `PermissionError` final de
        `save_with_retry`) depois de garantir o `fechar()`.
        """
        if self.ws is None:
            self.abrir()

        try:
            linha = self.buscar_linha(pmib)
            if linha is None:
                return False

            self.marcar_linha(linha, secoes)
            if salvar:
                self.salvar(**save_kwargs)
            return True
        finally:
            if fechar:
                self.fechar()
