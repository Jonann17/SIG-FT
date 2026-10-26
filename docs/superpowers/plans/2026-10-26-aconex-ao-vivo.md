# Aconex ao vivo e Conferência de Revisões: plano de implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** O SIG-FT passa a ler o Aconex ao vivo, com o extrato como reserva, e grava o STATUS REAL pela
batalha de versões do DocManager. Lista nova passa a ser sugerida só com PB020. A tela nova "Conferência
de Revisões" baixa a revisão vigente de toda lista com divergência. Os números do Power BI e do painel
HTML não mudam com isso.

**Architecture:** Um pacote novo, `sigft/core/aconex/`, reúne o que vem do DocManager: a cópia fiel em
`_docmanager/`, a leitura do cofre e o cliente da API. Ele expõe três fachadas: `status_real`,
`credenciais` e `cliente`. No Gestão PMIB, o `read_excel` do passo 1 dá lugar a uma fonte do histórico
(ao vivo ou extrato), e o passo 4 passa a escrever o STATUS REAL. A conferência é um serviço
(`services/conferencia_revisoes.py`) com uma tela Qt fina. Ela só lê a mapeadora e só cria PDF.

**Tech Stack:** Python 3.10+, pandas, openpyxl, requests (sempre por `sigft/core/rede.py`), PySide6,
pytest e pytest-qt. No cofre, o Power BI em Power Query M + DAX, com o `.pbip` gerado por
`montar_pbip.py`.

**Spec:** `docs/superpowers/specs/2026-10-26-aconex-ao-vivo-design.md` (aprovada pelo Luan em 26/10/2026)

## Global Constraints

- Código, comentários e documentação em português. Mensagem de commit sem acento (convenção do repositório).
- Princípios do `CLAUDE.md`: regra de negócio fora da tela; serviço não importa Qt; tela e serviço conversam por callbacks; uma implementação por conceito.
- Texto de tela só com `t()`, traduzido em `sigft/app/idiomas/es.json` e `en.json`. `python tools/textos_da_interface.py --faltando es` (e `en`) tem de sair vazio. Cor só por papel ou variante, ícone só de `icones.NOMES`, nenhum hexadecimal na tela.
- Testes sem rede e sem dado real. O XML do Aconex é sintético. pandas e openpyxl reais só dentro de `pandas_de_verdade(...)` e `openpyxl_de_verdade(...)`.
- O segredo do Aconex e o token nunca vão para log, preferência, mensagem de erro, teste ou repositório.
- Nada grava no `_STATUS_PMIB`. A conferência não grava na mapeadora. No Box, nada é sobrescrito nem apagado.
- Família de aprovação: `Aprovado`, `Aprovado com Comentários` e `Para Assinatura`, comparados sem acento e sem diferença entre maiúsculas e minúsculas. `APROVADO` (valor antigo) também conta.
- Nome do PDF baixado: `<código>[<revisão>].pdf`.
- Constantes copiadas do DocManager: `PROJECT_ID = "1207975853"`, `ACONEX_INSTANCE = "https://us1.aconex.com"`, `AUTH_URL = "https://constructionandengineering.oraclecloud.com/auth/token"`.
- **Portão de cada tarefa:** `bash scripts/check.sh` verde na máquina local. Desde depois de 23/10/2026, o GitHub Actions não roda nos repositórios do Luan por um problema de cobrança da conta. Isso trava o CI e também o Release. Até a cobrança ser resolvida, o check local é o único portão, e não sai versão nova para as máquinas da GE.
- **Ordem obrigatória:** a Tarefa 1 (Power BI) e a Tarefa 3 (painel HTML) vão para produção **antes** da Tarefa 4 (gravar o STATUS REAL).

## Review Focus

1. **Mapeadora ainda com os valores antigos** (`APROVADO`, `EM PROCESSO`, `NÃO APROVADO`): a conferência e os painéis classificam do mesmo jeito que os valores novos. Testes nas Tarefas 3 e 9.
2. **Mapeadora desatualizada:** o Aconex devolve uma revisão mais nova que a `ÚLTIMA REVISÃO EMITIDA`. O PDF recebe o nome da revisão que foi baixada, e a linha avisa. Teste na Tarefa 9.
3. **Cofre do DocManager ausente, cifrado em outra conta do Windows ou com dois perfis:** a parte A usa o extrato, e a B mostra as categorias sem baixar. O segredo não aparece em lugar nenhum. Testes nas Tarefas 6, 10 e 11.
4. **Lista renomeada no Aconex** (código novo, mesmo Tracking ID): o STATUS REAL usa o histórico inteiro do Tracking ID. Teste na Tarefa 4.
5. **401 no meio da paginação ou 503 de limite de uso:** renova o token uma vez; no 503, espera e tenta de novo. Uma falha vira linha de erro e não derruba a rodada. Testes nas Tarefas 7 e 9.

---

### Tarefa 1: Power BI e protótipo do painel contam a família de aprovação (no cofre)

Esta tarefa roda no **cofre** (`C:\Users\LCCoz\OneDrive\Documents\Obsidian\Sobressalentes-Itaipu`), não
no SIG-FT, numa máquina com Power BI Desktop. O ambiente de teste está descrito na memória
`ambiente-maquina-pessoal`. O cofre não é repositório git: o registro vai para
`_planejamento/progress.md`.

**Files:**
- Modify: `_gestao_v2/powerbi/04 - Listas e Eventos.pq` (coluna lógica nova `Lista Aprovada`; comentário da linha 64)
- Modify: `_gestao_v2/powerbi/05 - Medidas.dax:124-129`
- Modify: `_gestao_v2/powerbi/montar_pbip.py:48` (coluna nova na tabela `Listas`)
- Modify: `_scripts/regras_sobressalentes.py` (função nova), `_scripts/gerar_prototipo_dashboard.py:155`, `_scripts/prototipo_template.html:305,438`

**Interfaces:**
- Produces: a coluna `Listas[Lista Aprovada]` (lógica), usada pelas medidas `Listas Aprovadas EN.DT` e `Listas Aprovadas sem Fichas`; no cofre, `regras_sobressalentes.lista_aprovada(status_real) -> bool`.

- [ ] **Passo 1: Medir antes.** Compare o projeto do Box (`SOBRESSALENTES - PMIB\Sobressalentes (Power BI)`) com o do cofre. O Luan salva por lá, então a diferença tem de ser trazida para o cofre antes de continuar. Abra o `.pbip` no Desktop, atualize e anote `[Listas Aprovadas EN.DT]` e `[Listas Aprovadas sem Fichas]` (`%TEMP%\tomlib\dax.py`; se os scripts tiverem sumido, refaça como diz a memória).
- [ ] **Passo 2:** Em `04 - Listas e Eventos.pq`, logo depois da renomeação das colunas, acrescente
  `Table.AddColumn(<passo anterior>, "Lista Aprovada", each List.Contains({"APROVADO", "APROVADO COM COMENTARIOS", "PARA ASSINATURA"}, fxNorm([Status Real])), type logical)`.
  Troque o comentário da linha 64 por: "o Status Real vem da batalha de versões do DocManager (26/10/2026); Lista Aprovada = família de aprovação".
- [ ] **Passo 3:** Em `05 - Medidas.dax`:
  - `Listas Aprovadas EN.DT = CALCULATE ( [Listas], Listas[Lista Aprovada] = TRUE () )`;
  - `Listas Aprovadas sem Fichas = COUNTROWS ( FILTER ( Listas, Listas[Lista Aprovada] && ( ISBLANK ( [Fichas] ) || [Fichas] = 0 ) ) )`;
  - em `montar_pbip.py`, acrescente `Lista Aprovada` (booleana) às colunas de `Listas`.
- [ ] **Passo 4: Provar.** Monte uma pasta de teste com uma cópia da mapeadora e dos `_STATUS_PMIB` do kit (`_gestao_v2/fixtures/kit_gestao_pmib/`). Escreva no STATUS REAL, em seis listas: `APROVADO`, `Aprovado`, `Aprovado com Comentários`, `Para Assinatura`, `Em Processo` e `Não Aprovado`. Gere o projeto (`python montar_pbip.py`), aponte `PastaPMIB` para a pasta de teste, atualize e rode DAX. Esperado: `[Listas Aprovadas EN.DT]` = 4. Depois, aponte de volta para o Box e atualize. Esperado: o mesmo número do Passo 1.
- [ ] **Passo 5:** No cofre, crie `regras_sobressalentes.lista_aprovada(status_real) -> bool`, com a mesma família e a mesma comparação sem acento. O gerador do protótipo põe `"aprov"` em cada lista, e o template troca `l.sr === "APROVADO"` por `l.aprov` (linhas 305 e 438). Regere o protótipo e confira que o número de listas aprovadas é igual ao do Power BI.
- [ ] **Passo 6: Entregar no Box** com `python _gestao_v2/powerbi/entregar_no_box.py`. O Luan autorizou em 26/10/2026: *"se precisar mudar a fórmula DAX lá, mudamos também"*. Nunca feche um Power BI que você não abriu. Registre em `_planejamento/progress.md`.

---

### Tarefa 2: o motor do STATUS REAL, copiado do DocManager

**Files:**
- Create: `sigft/core/aconex/__init__.py` e `sigft/core/aconex/_docmanager/__init__.py`
- Create, como cópia fiel de `luanccozer/DocManager@c9683d2` (`docmanager/core/`), trocando só os imports para o pacote novo: `sigft/core/aconex/_docmanager/{constants,normalize,comissionamento,excecoes,truth_line,status_engine}.py`. Cada arquivo começa com: `# Copiado de luanccozer/DocManager@c9683d2 (docmanager/core/<arquivo>). Nao edite aqui sem levar ao DocManager -- PENDENCIAS 2026-10-26.`
- Create: `sigft/core/aconex/status_real.py`
- Create: `tests/_historico_aconex.py`, cópia de `tests/builders.py` do DocManager, só com `HistoricoBuilder` e `base`
- Test: `tests/test_aconex_status_real.py` e `tests/test_aconex_status_engine_docmanager.py`

**Interfaces:**
- Produces, em `sigft/core/aconex/status_real.py`:
  - `Categoria = Literal["aprovada", "em_processo", "nao_aprovada", "outros"]`
  - `ORDEM_DAS_CATEGORIAS: tuple[Categoria, ...] = ("aprovada", "em_processo", "nao_aprovada", "outros")`
  - `status_real_do_documento(historico: pd.DataFrame) -> str`: o `historico` são todas as linhas de **um** Tracking ID. A função aplica `resolver_linha_da_verdade`; se a linha da verdade disser `nao_emitido`, devolve a constante NÃO EMITIDO do DocManager; senão devolve `calcular_status_real(tl.df_para_calculo, tl.revisao_atual)`. Nada de consolidado.
  - `eh_aprovacao(status: object) -> bool`: usa a lista de veredito de aprovação de `_docmanager/constants.py`, com `remover_acentos(...).upper().strip()` nos dois lados.
  - `categoria(status: object) -> Categoria`: aprovação → `"aprovada"`; `EM PROCESSO` → `"em_processo"`; `NÃO APROVADO` → `"nao_aprovada"`; o resto, vazio e `None` → `"outros"`.
  - `revisoes_iguais(a: object, b: object) -> bool`: compara as duas por `normalizar_revisao`; se uma delas estiver vazia, devolve `False`.

- [ ] **Passo 1:** Copie os seis arquivos e o builder.
- [ ] **Passo 2: Escreva os testes que falham.** Em `tests/test_aconex_status_engine_docmanager.py`, porte do DocManager só os testes com valor esperado escrito (os que comparam com `DataManager` ficam de fora): `test_anulacao_vira_sempre_cancelado`, `test_aprovado_direto`, `test_revisao_vigente_inexistente_nao_emitido`, `test_fantasma_com_salvamento_na_propria_revisao`, `test_fantasma_resgatando_fantasma_vira_nao_emitido`, `test_mudanca_de_familia_reseta_aprovacao`, `test_reprovado_vence_com_atual_fantasma`, `test_reprovado_com_atual_em_processo_vira_em_processo` e `test_reprovacao_em_revisao_numerica_ignorada`. Em `tests/test_aconex_status_real.py`, os casos da §5.3 da spec:

```python
@pytest.fixture(autouse=True)
def _pandas_real():
    with pandas_de_verdade(constants, comissionamento, truth_line, status_engine, status_real, _historico_aconex):
        yield

def _h():
    return HistoricoBuilder("T", "#ITA0=Y01TF001&BPB020", "CMI-1")

def test_0a_aprovada_e_0b_em_processo_da_aprovado():
    h = _h().evento("0", 1, "Aprovado", "01/03/2026").evento("0A", 1, "Aprovado", "01/05/2026") \
            .evento("0B", 1, "Em Processo", "01/09/2026", current=True).build()
    assert status_real_do_documento(h) == "Aprovado"

def test_familia_nova_em_processo_da_em_processo():          # 0C aprovada, 1A em processo
    assert status_real_do_documento(...) == "Em Processo"

def test_0b_nao_aprovada_vigente():                           # == "Não Aprovado"
def test_para_assinatura_vigente():                           # 0 em Para Assinatura == "Para Assinatura"
def test_aprovado_com_comentarios_mantem_o_texto():           # == "Aprovado com Comentários"

@pytest.mark.parametrize("status, esperado", [
    ("Aprovado", True), ("APROVADO", True), ("Aprovado com Comentários", True),
    ("aprovado com comentarios", True), ("Para Assinatura", True),
    ("Em Processo", False), ("Não Aprovado", False), ("Informativo", False), ("", False), (None, False)])
def test_eh_aprovacao(status, esperado): ...

@pytest.mark.parametrize("status, esperado", [
    ("Para Assinatura", "aprovada"), ("APROVADO", "aprovada"), ("EM PROCESSO", "em_processo"),
    ("Não Aprovado", "nao_aprovada"), ("NÃO APROVADO", "nao_aprovada"),
    ("Cancelado", "outros"), ("NÃO EMITIDO", "outros"), (None, "outros")])
def test_categoria(status, esperado): ...

@pytest.mark.parametrize("a, b, esperado", [("0a", "0A ", True), ("0", "0A", False), ("", "", False), (None, "0", False)])
def test_revisoes_iguais(a, b, esperado): ...
```

- [ ] **Passo 3:** Rode `python -m pytest tests/test_aconex_status_real.py tests/test_aconex_status_engine_docmanager.py -v`. Esperado: FAIL, `ModuleNotFoundError: sigft.core.aconex.status_real`.
- [ ] **Passo 4:** Escreva a fachada `status_real.py` com as quatro funções acima.
- [ ] **Passo 5:** Rode de novo os mesmos testes. Esperado: PASS. Depois rode `bash scripts/check.sh`: verde.
- [ ] **Passo 6:** Commit com a mensagem `Motor do STATUS REAL copiado do DocManager (batalha de versoes)`.

---

### Tarefa 3: o painel HTML do SIG-FT conta a família de aprovação

**Files:**
- Modify: `sigft/services/painel.py:494`. O registro de cada lista ganha `"aprov": status_real.eh_aprovacao(m.get("STATUS REAL"))`.
- Modify: `sigft/assets/painel_template.html:302`. Troque `l.sr === "APROVADO"` por `l.aprov`.
- Test: `tests/test_painel.py`

**Interfaces:**
- Consumes: `sigft.core.aconex.status_real.eh_aprovacao` (Tarefa 2).

- [ ] **Passo 1: Escreva os testes que falham.** Use o mesmo padrão dos testes de `montar` que já existem no arquivo, com `openpyxl_de_verdade` e `pandas_de_verdade`:
  - `test_lista_aprovada_pela_familia_de_aprovacao`: `Para Assinatura` dá `aprov is True`, `APROVADO` (valor antigo) dá `True` e `Em Processo` dá `False`;
  - `test_template_nao_compara_status_real_com_texto`: `'l.sr === "APROVADO"' not in texto` e `"l.aprov" in texto`.
- [ ] **Passo 2:** Rode `python -m pytest tests/test_painel.py -v`. Esperado: os dois testes novos falham.
- [ ] **Passo 3:** Faça as duas mudanças.
- [ ] **Passo 4:** Rode `tests/test_painel.py` (PASS) e `bash scripts/check.sh` (verde).
- [ ] **Passo 5:** Commit com a mensagem `Painel conta a familia de aprovacao do STATUS REAL`.

---

### Tarefa 4: o Gestão PMIB grava o STATUS REAL

**Files:**
- Modify: `sigft/services/pmib_manager.py`:
  - na parte D de `_atualizar_mapeamento` (~linhas 915–930), a gravação nova;
  - no comentário T3-g (~linhas 752–760), o STATUS REAL deixa de ser "coluna de pessoas";
  - uma função nova no módulo, `historico_do_documento`.
- Test: `tests/test_pmib_manager_status_real.py`

**Interfaces:**
- Consumes: `status_real.status_real_do_documento` (Tarefa 2).
- Produces: `historico_do_documento(df_api: pd.DataFrame, codigo: str) -> pd.DataFrame | None`, com todas as linhas do Tracking ID do `codigo`, ou `None` se o código não estiver no histórico.

**Comportamento:**
- Para cada linha da mapeadora, a função usa o `novo_codigo` que a parte D já calcula.
- Coluna `STATUS REAL` ausente: um aviso só, `"[AVISO] Coluna 'STATUS REAL' não encontrada na mapeadora: o status real não foi gravado."`, e a rodada segue.
- Código fora do histórico: a célula não muda, e o log registra `" -> STATUS REAL de {codigo}: fora do histórico do Aconex, não mudou."`.
- Valor novo diferente do atual: grava, e o log registra `f" -> STATUS REAL de {codigo}: {antes or '(vazio)'} → {novo}"`. Valor igual: não grava e não registra nada.

- [ ] **Passo 1: Escreva os testes que falham.** Cada teste monta uma mapeadora mínima com o openpyxl real: aba `Acompanhamento Sobressalente`, cabeçalho na linha 2 com `N° DOCUMENTO ITAIPU` e `STATUS REAL`. O `df_api` sai do `HistoricoBuilder`, e o teste roda `list(PMIBManager()._atualizar_mapeamento(caminho, df_api, None, {}))`. Use títulos sem SOBRESSALENTES, para que a parte B não ofereça lista nova.
  - `test_status_real_gravado_pela_batalha`: 0A aprovada e 0B em processo dão a célula `"Aprovado"`;
  - `test_status_real_loga_antes_e_depois`: a célula `"APROVADO"` vira `"Aprovado"`, e o log contém `"APROVADO → Aprovado"`;
  - `test_status_real_igual_nao_loga`;
  - `test_status_real_sem_coluna_avisa_uma_vez`;
  - `test_status_real_codigo_fora_do_historico_nao_muda`: a linha `"SEM LISTA"`;
  - `test_status_real_segue_o_tracking_id_quando_o_codigo_muda`: o histórico tem 0 aprovada com o código antigo e 0A em processo com o código novo (`doc=` do builder, mesmo Tracking ID). Esperado: o código é trocado e o STATUS REAL vira `"Aprovado"`.
- [ ] **Passo 2:** Rode os testes. Esperado: FAIL.
- [ ] **Passo 3:** Implemente `historico_do_documento` e a gravação na parte D. Atualize o comentário T3-g.
- [ ] **Passo 4:** Rode os testes (PASS), `tests/test_pmib_manager_v2.py` e `bash scripts/check.sh` (verde).
- [ ] **Passo 5:** Commit com a mensagem `Gestao PMIB grava o STATUS REAL pela batalha de versoes`.

---

### Tarefa 5: lista nova exige PB020

**Files:**
- Modify: `sigft/services/pmib_manager.py:867-875`. O filtro de `df_novos_cand` passa a usar a função nova.
- Modify: `docs/refatoracao/PENDENCIAS.md`. A linha de 2026-09-03 sobre o filtro do `-01` vira **RESOLVIDO em <data> (regra PB020)**.
- Test: `tests/test_pmib_manager_lista_nova.py`

**Interfaces:**
- Produces: `e_lista_de_sobressalentes(codigo: object, titulo: object) -> bool` em `sigft/services/pmib_manager.py`. A regra é: `"PB020"` aparece em `str(codigo).upper()` **e** `"SOBRESSALENTES"` aparece em `normalizar(titulo)` **e** `"PRECO"` não aparece em `normalizar(titulo)`. O `normalizar` vem de `sigft.services.autorizacao`. O teste do `-01` sai.

- [ ] **Passo 1: Escreva o teste que falha.**

```python
@pytest.mark.parametrize("codigo, titulo, esperado", [
    ("#ITA0=Y01TF001&BPB020", "LISTA DE SOBRESSALENTES - RTA", True),
    ("#ITA0=A01AAM10&EPB020-01", "LISTA DE SOBRESSALENTES - SMF", True),        # o -01 não barra mais
    ("#ST00=X01ABC10&EPB020-01", "LISTA DE PREÇOS DE SOBRESSALENTES", False),
    ("#ST00=X01ABC10&EPB020-02", "LISTA DE PRECOS DE SOBRESSALENTES", False),   # sem acento
    ("#ST00=X01ABC10&MCM001", "PLANILHA DE COMISSIONAMENTO - SOBRESSALENTES", False),
    ("#ST00=X01ABC10&MPB021", "LISTA DE PREÇOS DE SOBRESSALENTES", False),
    (None, None, False)])
def test_e_lista_de_sobressalentes(codigo, titulo, esperado):
    assert e_lista_de_sobressalentes(codigo, titulo) is esperado
```

- [ ] **Passo 2:** Rode o teste. Esperado: FAIL, `ImportError`.
- [ ] **Passo 3:** Implemente a função e troque o filtro em `_atualizar_mapeamento` por ela.
- [ ] **Passo 4:** Rode o teste (PASS) e `bash scripts/check.sh` (verde). Marque a pendência de 2026-09-03 como resolvida.
- [ ] **Passo 5:** Commit com a mensagem `Lista nova so com PB020 no codigo (sem o teste do -01)`.

---

### Tarefa 6: credenciais do Aconex (lê o cofre do DocManager)

**Files:**
- Create: `sigft/core/aconex/credenciais.py`. Copie de `docmanager/services/credenciais.py` só `_dpapi`, `decifrar` e a parte de leitura do `Cofre`, com o mesmo cabeçalho de origem da Tarefa 2.
- Test: `tests/test_aconex_credenciais.py`

**Interfaces:**
- Produces:
  - `@dataclass(frozen=True) class PerfilAconex`: `nome: str`, `client_id: str`, `user_id: str` e `client_secret: str = field(repr=False)`;
  - `caminho_do_cofre() -> Path`: usa `DOCMANAGER_DADOS_DIR`, se definida; senão `Path.home() / "Documents" / "DocManager_Itaipu"`. O arquivo é `/ "credenciais.json"`. Não cria a pasta;
  - `ler_perfis(caminho: Path | None = None) -> list[PerfilAconex]`: só leitura do JSON `{"usuarios": {nome: {"client_id", "user_id", "secret", "cifrado"}}}`. Devolve só os perfis completos, em ordem de nome. Qualquer erro, inclusive a DPAPI recusar o segredo cifrado em outra conta do Windows, vira lista vazia ou perfil de fora. Nunca levanta exceção;
  - `escolher_perfil(perfis: list[PerfilAconex], preferido: str | None) -> PerfilAconex | None`: com um perfil, devolve esse; se `preferido` estiver entre os nomes, devolve esse; senão `None`, e quem chamou pergunta;
  - `PREFERENCIA_PERFIL = "aconex.perfil"`, a chave para `prefs.ler_preferencia` e `prefs.gravar_preferencia`.

- [ ] **Passo 1: Escreva os testes que falham.** Os cofres são escritos com `cifrado: false` (base64):
  - `test_cofre_ausente_devolve_vazio`;
  - `test_le_so_os_perfis_completos`;
  - `test_json_quebrado_devolve_vazio`;
  - `test_perfil_que_a_dpapi_recusa_fica_de_fora` (monkeypatch em `decifrar` para levantar);
  - `test_segredo_nao_aparece_no_repr`;
  - `test_escolher_perfil` (um perfil; dois com preferido; dois sem preferido);
  - `test_caminho_do_cofre_respeita_a_variavel`;
  - só no Windows (`skipif(os.name != "nt")`): `test_decifra_o_que_a_dpapi_cifrou`.
- [ ] **Passo 2:** Rode os testes. Esperado: FAIL.
- [ ] **Passo 3:** Implemente.
- [ ] **Passo 4:** Rode os testes (PASS) e `bash scripts/check.sh` (verde).
- [ ] **Passo 5:** Commit com a mensagem `Leitura do cofre de credenciais do DocManager`.

---

### Tarefa 7: cliente do Aconex

**Files:**
- Modify: `sigft/core/rede.py`. `abrir(...)` ganha `data: dict | None = None`, repassado ao `sessao.request(...)`.
- Create: `sigft/core/aconex/cliente.py`. Copie de `docmanager/aconex_backend.py`: as constantes, `CAMPOS_STRING`, `ORDEM_COLUNAS`, `_parse_pagina` e o comportamento de `montar_dataframe`. As requisições passam pelo `rede.abrir`.
- Test: `tests/test_aconex_cliente.py` e um teste em `tests/test_rede.py`

**Interfaces:**
- Consumes: `PerfilAconex` (Tarefa 6); `status_real.revisoes_iguais` (Tarefa 2).
- Produces:
  - `class ErroAconex(RuntimeError)`;
  - `@dataclass(frozen=True) class Versao`: `document_id: str`, `codigo: str`, `revisao: str`, `versao: int` e `current: bool`;
  - `class ClienteAconex`, com `__init__(self, perfil: PerfilAconex, *, abrir=rede.abrir, esperar=time.sleep, log_cb=lambda _m: None)` e os métodos:
    - `buscar(self, search_query: str, *, historico: bool, campos: str = CAMPOS_STRING, page_size: int = 500) -> list[dict]`;
    - `versoes_do_codigo(self, codigo: str) -> list[Versao]`, com `search_query=f'"{codigo}"'` e `historico=True`;
    - `versao_vigente(self, codigo: str) -> Versao | None`: a `current`, ou `None`;
    - `versao(self, codigo: str, revisao: str) -> Versao | None`: a de maior `versao` entre as que têm `revisoes_iguais`;
    - `baixar(self, document_id: str) -> bytes`: `GET {ACONEX_INSTANCE}/api/projects/{PROJECT_ID}/register/{id}/markedup`, `timeout=180`;
  - `tabela(registros: list[dict]) -> pd.DataFrame`: colunas `ORDEM_COLUNAS` e `Current` booleano.

**Comportamento fixado:**
- Token: `POST AUTH_URL` com `Authorization: Basic base64(client_id:client_secret)` e `Content-Type: application/x-www-form-urlencoded;charset=UTF-8`. O formulário (`data`) é `{"grant_type": "client_credentials", "user_id": ..., "user_site": ACONEX_INSTANCE}`. As requisições seguintes levam `Authorization: Bearer <token>` e `Accept: application/xml`.
- 401 numa página: pede token novo e repete a página uma vez. Um segundo 401 levanta `ErroAconex("O Aconex recusou as credenciais (HTTP 401).")`.
- 503: espera 5, 15 e 45 s (via `esperar`). Depois da terceira espera, levanta `ErroAconex`. `rede.FalhaDeRede` também vira `ErroAconex`, com `rede.resumo_erro`.
- Nenhuma mensagem de `ErroAconex` contém o segredo nem o token.

- [ ] **Passo 1: Escreva os testes que falham.** O `abrir` falso devolve `(None, resposta)`, com `status_code`, `content` e `json()`. O XML é sintético, no molde de `tests/test_aconex_backend.py` do DocManager.
  - `test_token_vai_no_formulario_e_volta_no_bearer`;
  - `test_buscar_pagina_ate_acabar` (duas páginas);
  - `test_401_renova_o_token_uma_vez`;
  - `test_401_duas_vezes_vira_erro_sem_segredo` (`perfil.client_secret not in str(erro)` e o token também não);
  - `test_503_espera_e_tenta_de_novo` (`esperar` recebe `[5, 15]` quando a 3ª tentativa dá certo);
  - `test_versao_vigente_escolhe_a_current`;
  - `test_versao_por_revisao_normalizada` (`"0a"` acha `"0A"`);
  - `test_baixar_usa_markedup_e_devolve_bytes`;
  - `test_tabela_tem_as_colunas_do_extrato` (`list(df.columns) == ORDEM_COLUNAS`);
  - em `tests/test_rede.py`, `test_abrir_repassa_data_do_formulario` (a sessão falsa de `_fabrica_sessao` guarda os kwargs).
- [ ] **Passo 2:** Rode os testes. Esperado: FAIL.
- [ ] **Passo 3:** Implemente.
- [ ] **Passo 4:** Rode os testes (PASS) e `bash scripts/check.sh` (verde).
- [ ] **Passo 5:** Commit com a mensagem `Cliente do Aconex (token, busca paginada, download) sobre core/rede`.

---

### Tarefa 8: diagnóstico do Aconex (prova as buscas)

**Files:**
- Create: `sigft/core/aconex/diagnostico.py`
- Test: `tests/test_aconex_diagnostico.py`

**Interfaces:**
- Consumes: `ClienteAconex` (Tarefa 7); `ler_perfis` e `escolher_perfil` (Tarefa 6).
- Produces:
  - `@dataclass(frozen=True) class Sonda`: `nome: str`, `ok: bool` e `detalhe: str`. O `detalhe` traz só contagens e status HTTP, nunca título nem dado de documento;
  - `sondar(cliente: ClienteAconex, codigo: str) -> list[Sonda]`, que testa, nesta ordem:
    1. token;
    2. busca exata com histórico (quantas versões);
    3. busca pelo Tracking ID dessa lista, uma tentativa por sintaxe documentada no *Documents API Developer Guide* (help.aconex.com/apis/api-guide-documents/, List Documents, `search_query`). Prova: traz versões com mais de um código, quando houver;
    4. busca das listas com PB020 no código e SOBRESSALENTES no título, também uma tentativa por sintaxe documentada. Diz quantas vieram;
  - `main(argv: list[str] | None = None) -> int`: `python -m sigft.core.aconex.diagnostico <código>` imprime uma linha por sonda.

- [ ] **Passo 1: Escreva os testes que falham**, com cliente falso:
  - `test_sonda_ok_e_falha_por_etapa`;
  - `test_detalhe_nao_vaza_titulo` (o título falso `"TITULO_QUE_NAO_PODE_VAZAR"` não aparece em nenhum `detalhe`);
  - `test_token_recusado_para_as_outras_sondas`.
- [ ] **Passo 2:** Rode os testes. Esperado: FAIL.
- [ ] **Passo 3:** Implemente.
- [ ] **Passo 4:** Rode os testes (PASS) e `bash scripts/check.sh` (verde).
- [ ] **Passo 5:** Commit com a mensagem `Diagnostico das buscas do Aconex`.

**Portão G1, com o Luan:** o diagnóstico roda numa máquina com o cofre do DocManager. Pode ser pelo botão
"Testar conexão com o Aconex" da Tarefa 10, que chega na máquina da GE pelo Release, ou pelo comando, numa
sessão local com o cofre. Esta máquina pessoal tem a pasta do DocManager, mas não tem o
`credenciais.json`. O resultado (quais sintaxes funcionam) é anotado na Tarefa 11 antes de ela começar.
As Tarefas 9 e 10 não dependem do G1: usam só a busca exata e o download, que já estão provados.

---

### Tarefa 9: serviço da Conferência de Revisões

**Files:**
- Create: `sigft/services/conferencia_revisoes.py`
- Test: `tests/test_conferencia_revisoes.py`

**Interfaces:**
- Consumes:
  - `status_real.categoria`, `revisoes_iguais` e `ORDEM_DAS_CATEGORIAS` (Tarefa 2);
  - `ClienteAconex.versao_vigente`, `versao` e `baixar`, e `ErroAconex` (Tarefa 7);
  - `pmib_manager.achar_aba`, `NOME_ABA_SOBRESSALENTES` e `COLUNA_CHAVE_SOBRESSALENTES`;
  - `status_pmib_arquivos.listar`.
- Produces:
  - `@dataclass(frozen=True) class ListaNaMapeadora`: `codigo`, `ultima_revisao`, `status_da_revisao`, `status_real` e `revisao_em_uso`, todos `str`, mais `link: str | None` (o destino do hyperlink de `LINK DA PLANILHA`, relativo à pasta da mapeadora);
  - `@dataclass(frozen=True) class Mapeadora`: `caminho: Path`, `salva_em: datetime` (o mtime) e `listas: list[ListaNaMapeadora]`;
  - `ler_mapeadora(caminho: str | Path) -> Mapeadora`: `load_workbook(caminho, data_only=True)`, sem `read_only`, porque o hyperlink precisa disso;
  - `@dataclass(frozen=True) class ItemConferencia`: `lista: ListaNaMapeadora`, `categoria: Categoria`, `pasta: Path | None` e `motivo: str = ""`;
  - `@dataclass class Conferencia`: `itens: list[ItemConferencia]` (só os que têm divergência), `em_dia: int`, `sem_status_pmib: int` e o método `por_categoria(self) -> dict[Categoria, list[ItemConferencia]]`, na ordem de `ORDEM_DAS_CATEGORIAS`;
  - `conferir(mapeadora: Mapeadora, pasta_raiz: Path | None) -> Conferencia`, com as regras na ordem:
    1. sem `link`, conta em `sem_status_pmib`;
    2. `ultima_revisao` vazia vai para `"outros"`, com o motivo "sem revisão emitida no Aconex";
    3. `revisoes_iguais(revisao_em_uso, ultima_revisao)` conta em `em_dia`;
    4. o resto entra com `categoria(status_real)`. Se não houver pasta, vai para `"outros"` com o motivo "_STATUS_PMIB não encontrado";
  - `resolver_pasta(link: str, pasta_mapeadora: Path, codigo: str, pasta_raiz: Path | None) -> Path | None`: o pai de `pasta_mapeadora / link`, se o arquivo existir; senão, a pasta do `_STATUS_PMIB` vivo com esse código em `listar(pasta_raiz)`; senão `None`;
  - `nome_do_pdf(codigo: str, revisao: str) -> str`: `f"{codigo}[{revisao}].pdf"`, trocando só os caracteres reservados do Windows (`<>:"/\|?*`) por `_`. O `#`, o `&` e o `=` ficam;
  - `@dataclass(frozen=True) class Download`: `codigo: str`, `revisao: str | None`, `caminho: Path | None`, `situacao: Literal["baixado", "ja_existia", "falhou"]` e `detalhe: str = ""`;
  - `baixar(conferencia: Conferencia, cliente: ClienteAconex, *, log_cb, progress_cb=None, cancelado_cb=None) -> list[Download]`. Para **todo** item com pasta:
    1. baixa a `versao_vigente(codigo)` com o nome da revisão **devolvida**. Se ela for diferente da `ultima_revisao`, o `detalhe` diz "mapeadora desatualizada: o Aconex está na {rev}";
    2. se o PDF da `revisao_em_uso` não estiver na pasta, baixa também (`versao(codigo, revisao_em_uso)`). Se essa revisão não for encontrada, registra no log e segue;
    3. arquivo existente vira `"ja_existia"`, sem chamar `baixar`;
    4. `ErroAconex` vira `"falhou"`, e o resto continua;
    5. `cancelado_cb()` verdadeiro para o laço.

- [ ] **Passo 1: Escreva os testes que falham.** A mapeadora é real, via `openpyxl_de_verdade`, com hyperlink relativo. O cliente é falso.
  - `test_ler_mapeadora_le_as_colunas_o_link_e_a_data`;
  - `test_sem_link_conta_em_sem_status_pmib`;
  - `test_revisao_igual_conta_em_dia` (`"0a"` com `"0A"`);
  - `test_revisao_em_uso_vazia_e_divergencia`;
  - `test_sem_ultima_revisao_vai_para_outros`;
  - `test_categorias_pelo_status_real`, parametrizado com o vocabulário novo e o antigo: `Para Assinatura` e `APROVADO` → aprovada; `Em Processo` e `EM PROCESSO` → em_processo; `Não Aprovado` e `NÃO APROVADO` → nao_aprovada; `Cancelado`, `NÃO EMITIDO` e `""` → outros;
  - `test_pasta_pelo_link_relativo`;
  - `test_pasta_pelo_codigo_quando_o_link_quebrou`;
  - `test_sem_pasta_vai_para_outros`;
  - `test_por_categoria_na_ordem`;
  - `test_nome_do_pdf` (`("#ITA0=Y01TF001&BPB020", "0A")` → `"#ITA0=Y01TF001&BPB020[0A].pdf"`);
  - `test_baixa_a_vigente_com_o_nome_da_revisao_baixada` (a mapeadora diz `0B`, o Aconex devolve `0C`: o arquivo é `...[0C].pdf` e o detalhe contém `"mapeadora desatualizada"`);
  - `test_nao_baixa_de_novo_o_que_ja_existe`;
  - `test_nunca_sobrescreve` (o conteúdo do arquivo que já existia fica igual);
  - `test_baixa_tambem_a_revisao_em_uso_que_falta`;
  - `test_falha_vira_linha_e_o_resto_continua`;
  - `test_cancelar_para_o_laco`.
- [ ] **Passo 2:** Rode os testes. Esperado: FAIL.
- [ ] **Passo 3:** Implemente.
- [ ] **Passo 4:** Rode os testes (PASS) e `bash scripts/check.sh` (verde).
- [ ] **Passo 5:** Commit com a mensagem `Servico da Conferencia de Revisoes (mapeadora, categorias, downloads)`.

---

### Tarefa 10: tela Conferência de Revisões

**Files:**
- Create: `sigft/app_qt/views/conferencia_revisoes.py`. Use como modelo a estrutura de `sigft/app_qt/views/correcao_pdm.py` (serviço importado direto, tela fina).
- Modify: `sigft/app_qt/main.py`:
  - a fábrica `_conferencia_revisoes`;
  - em `TELAS`, a entrada `"ConferenciaRevisoes": _conferencia_revisoes`.
- Modify: `sigft/app_qt/catalogo.py`:
  - no menu, `("botao", marcar("10. Conferência de Revisões"), "ConferenciaRevisoes")` na seção "Gestão";
  - em `ICONE_DA_TELA`, `"ConferenciaRevisoes": "clipboard-check"`;
  - o cartão em `MODULOS`, com o texto: "Aponta as listas cuja revisão em uso ficou para trás no Aconex, separadas pelo Status Real, e baixa a revisão vigente para a pasta de cada uma."
- Modify: `sigft/app/idiomas/es.json` e `en.json`
- Test: `tests/test_qt_tela_conferencia_revisoes.py`

**Interfaces:**
- Consumes: `ler_mapeadora`, `conferir` e `baixar` (Tarefa 9); `ler_perfis`, `escolher_perfil` e `PREFERENCIA_PERFIL` (Tarefa 6); `ClienteAconex` (Tarefa 7); `sondar` (Tarefa 8).
- Produces: `class ModuloConferenciaRevisoes(ModuleFrame)`.

**Comportamento:**
- **Entradas:** a mapeadora começa na última lembrada (`prefs.get_last_file(CHAVE_MAPEAMENTO)`, a mesma do Gestão PMIB). A pasta raiz começa na última escolhida no Gestão PMIB (chave `"pmib_manager.pasta_raiz"` de `file_dialogs`).
- **Data da mapeadora:** a tela mostra "Mapeadora salva em DD/MM/AAAA HH:MM". Se não for de hoje, mostra também: `t("A mapeadora não foi atualizada hoje. Rode o Gestão PMIB antes para ver as revisões mais recentes.")`.
- **Botão "Conferir revisões":** roda no worker (`iniciar_tarefa`).
  - Mostra os totais por categoria, mais "Em dia" e "Sem _STATUS_PMIB", e uma tabela por categoria, na ordem de `por_categoria()`. Colunas: código, revisão em uso, última revisão emitida, status da revisão, STATUS REAL e PDF.
  - Com perfil, baixa, com progresso e cancelar.
  - Sem perfil, ou com `ErroAconex` no começo, avisa `t("Sem conexão com o Aconex: as listas aparecem, mas nada foi baixado.")`.
- **Perfil:** com dois ou mais e nenhum preferido, a tela pergunta numa janela de escolha e grava a escolha em `PREFERENCIA_PERFIL`.
- **Botão "Testar conexão com o Aconex":** roda `sondar` com o primeiro código da mapeadora e escreve uma linha por sonda no console.

- [ ] **Passo 1: Escreva os testes que falham**, com pytest-qt offscreen e os serviços trocados por monkeypatch:
  - `test_tela_registrada_e_no_menu`;
  - `test_mostra_os_totais_por_categoria`;
  - `test_sem_perfil_nao_baixa_e_avisa`;
  - `test_aviso_de_mapeadora_antiga`;
  - `test_testar_conexao_escreve_as_sondas`.
- [ ] **Passo 2:** Rode os testes. Esperado: FAIL.
- [ ] **Passo 3:** Implemente a tela e as traduções.
- [ ] **Passo 4:** Rode os testes (PASS); `python tools/textos_da_interface.py --faltando es` e `--faltando en` (os dois vazios); `QT_QPA_PLATFORM=offscreen python frontend.py --smoke` (visita a tela nova, sem erro); e `bash scripts/check.sh` (verde).
- [ ] **Passo 5:** Commit com a mensagem `Tela Conferencia de Revisoes`.

---

### Tarefa 11: Gestão PMIB com o histórico ao vivo (depois do G1)

**Antes de começar:** anote aqui o resultado do G1, isto é, as sintaxes de `search_query` que funcionaram
para Tracking ID e para PB020/SOBRESSALENTES. Se alguma das duas não funcionar, avise o Luan **antes** de
seguir, como manda a §4.2 da spec. Nesse caso, `FonteAoVivo.carregar` usa a extração completa
(`cliente.buscar("", historico=True)`), com a mesma interface.

**Files:**
- Create: `sigft/services/historico_aconex.py`
- Modify: `sigft/services/pmib_manager.py`. `executar_fluxo` ganha o parâmetro `fonte`. O passo 1 de `_fluxo` usa a fonte, e os códigos conhecidos (dos `_STATUS_PMIB` e da mapeadora) são lidos antes da carga.
- Modify: `sigft/app_qt/views/pmib_manager.py`. Em `iniciar_gestao`, o Passo 1 passa a ser opcional, e o rótulo mostra "Aconex ao vivo" quando nenhum arquivo foi escolhido. Se o cofre tiver dois ou mais perfis e nenhum preferido, a tela pergunta antes de rodar, com a mesma janela de escolha da Tarefa 10, e grava a escolha em `PREFERENCIA_PERFIL`.
- Test: `tests/test_historico_aconex.py` e `tests/test_pmib_manager_fonte.py`

**Interfaces:**
- Consumes: `ClienteAconex` e `tabela` (Tarefa 7); `ler_perfis` e `escolher_perfil` (Tarefa 6).
- Produces:
  - `class FonteHistorico(Protocol)`: `nome: str` e `def carregar(self, codigos: set[str], log_cb) -> pd.DataFrame`;
  - `class FonteExtrato`, com `__init__(self, caminho: str)` e `nome = f"extrato {basename}"`. O `carregar` é o `read_excel` de hoje, com `Current` booleano, movido de `_fluxo`;
  - `class FonteAoVivo`, com `__init__(self, cliente: ClienteAconex)` e `nome = "Aconex ao vivo"`. O `carregar` faz:
    1. a busca exata com histórico de cada código;
    2. segue o Tracking ID pela sintaxe do G1;
    3. traz as candidatas a lista nova e as listas de preços pela sintaxe do G1;
    4. junta tudo em `tabela(...)`, sem `DocumentId` repetido;
  - `fonte_padrao(caminho_api: str | None) -> FonteHistorico | None`: com `caminho_api`, devolve `FonteExtrato`; sem ele, com perfil, `FonteAoVivo`; sem perfil, `None`;
  - `PMIBManager.executar_fluxo(self, caminho_api, pasta_raiz_status, caminho_gerenciadora, callback_confirm=None, callback_travados=None, hoje=None, fonte: FonteHistorico | None = None)`:
    - `fonte` passada vence. Senão vale `fonte_padrao(caminho_api)`;
    - se não houver fonte, ou se vier `ErroAconex` na carga, o fluxo devolve `"[ERRO] Sem conexão com o Aconex ({motivo}): selecione o Histórico do DocManager (Passo 1) e rode de novo."` e para **antes de gravar qualquer coisa**;
    - na carga, o log registra `f"Fonte do histórico: {fonte.nome}"`.

- [ ] **Passo 1: Escreva os testes que falham.**
  - `test_fonte_extrato_le_como_antes`;
  - `test_fonte_ao_vivo_monta_a_tabela_do_extrato` (colunas = `ORDEM_COLUNAS`);
  - `test_fonte_ao_vivo_segue_o_tracking_id`;
  - `test_fonte_padrao`, com os três casos;
  - `test_fluxo_sem_fonte_para_antes_de_gravar` (o mtime da mapeadora não muda);
  - `test_fluxo_diz_a_fonte_usada`;
  - `test_mesma_mapeadora_com_as_duas_fontes`: o mesmo histórico, como `.xlsx` e como páginas falsas da API, rodado em duas cópias de uma mapeadora mínima. As duas ficam iguais célula a célula.
- [ ] **Passo 2:** Rode os testes. Esperado: FAIL.
- [ ] **Passo 3:** Implemente o serviço, o parâmetro novo e a tela.
- [ ] **Passo 4:** Rode os testes (PASS), `tests/test_pmib_manager_v2.py`, `tests/test_pmib_manager_travados.py` e `bash scripts/check.sh` (verde).
- [ ] **Passo 5:** Commit com a mensagem `Gestao PMIB com o historico do Aconex ao vivo (extrato como reserva)`.

---

### Tarefa 12: fechamento e validação ao vivo (G2)

**Files:**
- Modify: `CHANGELOG.md` (bloco da versão nova)
- Modify: `docs/base-conhecimento/11-pmib-manager-backend.md`: fonte ao vivo, STATUS REAL pela batalha e regra PB020
- Modify: `docs/ROTEIRO_DE_TESTE.md`: etapa nova, "Aconex ao vivo e Conferência de Revisões", com o roteiro do G2 abaixo

- [ ] **Passo 1:** Escreva o CHANGELOG, o documento da base de conhecimento e a etapa do roteiro.
- [ ] **Passo 2:** Rode `bash scripts/check.sh` e `QT_QPA_PLATFORM=offscreen python frontend.py --smoke`. Esperado: verde e sem erro.
- [ ] **Passo 3:** Commit com a mensagem `Changelog, base de conhecimento e roteiro do Aconex ao vivo`, e push para o PR #24. O Release só sai quando o GitHub Actions voltar (Global Constraints).
- [ ] **Passo 4: G2, com o Luan, na máquina da GE, com o Release instalado.** Os critérios são os da §10 da spec:
  1. Testar conexão;
  2. Gestão PMIB ao vivo e com o extrato do dia, em cópias: a mapeadora sai igual;
  3. STATUS REAL igual ao status real do DocManager;
  4. lista nova: PB020 sim, comissionamento não;
  5. Power BI: "Listas Aprovadas" com o mesmo número antes e depois;
  6. conferência no Box real: as categorias conferem, os PDFs vão para as pastas certas e a segunda rodada não baixa nada;
  7. numa máquina sem cofre: o extrato é pedido e nada é baixado.
