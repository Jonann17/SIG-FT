# AutoSpec — conferência das respostas do fornecedor: plano de implementação

> **Para quem executa:** execução inline nesta sessão (executing-plans), TDD em cada tarefa.
> Passos com `- [ ]`.

**Objetivo:** a IA confere as respostas do fornecedor na tabela de especificações contra o
datasheet; "não se aplica" com prova vira o valor do documento, divergência vai só para o log.

**Arquitetura:** chamada de IA separada (`auditar_respostas_do_fornecedor`), com a mesma
política de envio de documento do preenchimento (`_preparar_envio`, extraído de
`generate_ai_response`). Peças puras em `services/autospec_auditoria.py`; a decisão que usa a
prova fica no `AutoSpecCore`, reaproveitando `_conferir_pela_prova`.

**Spec:** `docs/superpowers/specs/2026-09-28-autospec-conferencia-fornecedor-design.md`

## Restrições globais

- O prompt, a chamada e a chave de cache do PREENCHIMENTO não mudam (fixture
  `tests/fixtures/prompts/autospec_prompt.txt` intocada).
- Nenhuma resposta com valor do fornecedor chega ao `fill_save`.
- Sem travessão em string de log/tela (`tests/test_texto_da_ui.py`); log sem acento, como o
  resto do módulo.
- `analyze_sheet` continua devolvendo 7 elementos.
- Zonas compartilhadas (`ficha_layout.py`, `prompts.py`) em commit isolado, com a zona na
  mensagem.
- Commit sem acento, em português. Verde (`python -m pytest -q`) antes de cada commit.

## Arquivos

| Arquivo | Papel |
|---|---|
| `sigft/core/rpa/ficha_layout.py` | + `e_nao_se_aplica(valor)` |
| `sigft/core/llm/prompts.py` | + `montar_autospec_auditoria(...)` |
| `sigft/services/autospec_auditoria.py` (novo) | `ItemAuditado`, `ler_resposta`, `equivalentes`, `montar_lista`, `ResultadoAuditoria` (log e resumo) |
| `sigft/services/autospec.py` | coleta em `analyze_sheet`; `_preparar_envio`; `auditar_respostas_do_fornecedor`; decisão; integração em `process_queue` e `processar_conferidos` |
| `sigft/app/views/autospec.py` | caixa "Conferir as respostas do fornecedor contra o datasheet" |
| `tests/test_nao_se_aplica.py`, `tests/test_autospec_auditoria.py`, `tests/test_autospec_auditoria_lote.py`, `tests/test_autospec_auditoria_tela.py` | testes |

## Interfaces

```python
# ficha_layout
def e_nao_se_aplica(valor) -> bool

# prompts
def montar_autospec_auditoria(txt_brv, fab, desc_comp, context, lista_texto) -> str

# autospec_auditoria
SITUACOES = ("confere", "diverge", "nao_consta")
@dataclass class ItemAuditado: situacao: str; valor_documento: str; prova: Evidencia
def ler_resposta(bruto, ids) -> dict[str, ItemAuditado]      # ValueError se não for objeto
def equivalentes(fornecedor, documento, pergunta="") -> bool
def montar_lista(respostas: dict) -> str
@dataclass class ResultadoAuditoria:
    gravar: dict; campos: dict; notas: dict
    na_preenchidos: list  # (desc, fornecedor, valor, onde)
    divergencias: list    # (desc, fornecedor, valor_documento, onde, trecho, justificativa)
    na_mantidos: int; conferem: int; sem_dado: int
    descartados: list     # (desc, motivo)
    falha: str | None; sem_documento: bool
    def linhas_de_log(self) -> list[tuple[str, str]]   # (nivel, texto)
    def resumo(self) -> str

# AutoSpecCore
self.respostas_do_fornecedor: dict   # {campo: {desc, ref, resposta, nao_se_aplica}}
self.auditar_fornecedor = True       # interruptor
def _preparar_envio(self, context, campos, callbacks=None) -> (como_arquivo, anexos, contexto_final, contexto_conferencia)
def auditar_respostas_do_fornecedor(self, txt_brv, fab, desc_comp, respostas, context, callbacks=None) -> ResultadoAuditoria
def _respostas_para_auditar(self) -> dict
def _mesclar_auditoria(self, missing, ai_resp, auditoria) -> (campos, valores)
```

## Tarefas

### Tarefa 1 — `e_nao_se_aplica` (ficha_layout, zona compartilhada)
- [ ] Teste `tests/test_nao_se_aplica.py`: formas exatas (`N/A`, `n.a.`, `NSA`, `-`, traço
      tipográfico por `chr`), frases com e sem complemento (`Não se aplica ao modelo`,
      `NOT APPLICABLE`, `não informado`), e o que NÃO é (`Não`, `Nenhum`, `Não possui`, `0`,
      `Na posição vertical`, `None`, `""`).
- [ ] Rodar, ver falhar; implementar; ver passar; suíte verde.
- [ ] Commit: `ficha_layout: e_nao_se_aplica (zona compartilhada analyzer/autospec)`.

### Tarefa 2 — `montar_autospec_auditoria` (prompts, zona compartilhada)
- [ ] Teste (em `tests/test_autospec_auditoria.py`): interpola material/fabricante/descrição/
      contexto; contexto vazio cai em "Nenhuma informação disponível."; termina na lista; pede
      prova só em `diverge`; proíbe dedução; "unidade/tradução não é divergência"; "N/A com valor
      é diverge"; formato JSON com `situacao`/`valor_documento`/`trecho`.
- [ ] Implementar após `montar_autospec`; fixture do preenchimento intocada.
- [ ] Commit: `prompts: montar_autospec_auditoria (zona compartilhada; montar_autospec intacto)`.

### Tarefa 3 — peças puras (`autospec_auditoria.py`)
- [ ] Testes: `ler_resposta` (envelope, situação por extenso/`nao confere`/string solta, item
      sem prova, não-objeto levanta); `equivalentes` (`24 Vcc`×`24 VDC`, `0,5 kW`×`500 W`,
      `10 bar`×`1 MPa`, `IP54`×`IP65` não, `220 V`×`220/380 V` não, texto igual sem acento sim,
      `Aço inox`×`Stainless steel` não — fica com a IA); `montar_lista`; `linhas_de_log` e
      `resumo`.
- [ ] Implementar; verde; commit `AutoSpec: pecas puras da conferencia do fornecedor`.

### Tarefa 4 — coleta, envio e chamada no `AutoSpecCore`
- [ ] Testes: `analyze_sheet` preenche `respostas_do_fornecedor` (worksheet falsa com linhas
      79+), sem mexer no `missing`; `_preparar_envio` (testes de `test_autospec_documentos.py`
      verdes sem mudança); `auditar_respostas_do_fornecedor`: sem respostas e sem documento não
      chama a IA; cada linha das tabelas da spec §4.4; recusa do PDF cai para o texto; timeout
      vira falha; resposta que não é objeto vira falha; cache serve de volta sem chamar.
- [ ] Implementar; verde; commit `AutoSpec: conferencia das respostas do fornecedor (coleta, chamada e decisao)`.

### Tarefa 5 — lote (`process_queue`, `processar_conferidos`)
- [ ] Testes (`tests/test_autospec_auditoria_lote.py`, fakes como em
      `test_autospec_relatorio_lote.py`): ficha completa com respostas é conferida; com
      gravação chama `fill_save` com a mescla; sem gravação não chama `fill_save` e conta
      sucesso; sem documento conta pulada; interruptor desligado = hoje; falha da conferência
      não derruba o preenchimento; ficha só-conferência com falha conta falha; 2ª passada
      confere; nenhuma resposta com valor chega ao `fill_save`; notas mescladas.
- [ ] Implementar; verde; commit `AutoSpec: o lote confere as respostas do fornecedor`.

### Tarefa 6 — tela
- [ ] Teste por AST (`tests/test_autospec_auditoria_tela.py`): caixa com "fornecedor" no
      texto; `command` grava `self._conferir_fornecedor`; `_novo_core` repassa para
      `auditar_fornecedor`.
- [ ] Implementar; `compileall`, `pyflakes` na tela, abrir o app sob Xvfb se as dependências
      instalarem; commit `AutoSpec: interruptor da conferencia do fornecedor na tela`.

### Tarefa 7 — documentação
- [ ] `08-autospec-backend.md` (quadro 2026-09-28), `08b` §3.1 (a exceção decidida pelo
      usuário), `AUTOSPEC_MELHORIAS.md`, `ROTEIRO_DE_TESTE.md` Etapa 3b, `PENDENCIAS.md`
      (zonas tocadas, listas de N/A a unificar, 2ª passada sem `_modelo_do_item`, aviso do mural
      que saiu), mural do `CLAUDE.md` (aviso Luan → Rafael), `CHANGELOG.md` bloco 1.1.1 (skill
      `sigft-lancar-versao`).
- [ ] `bash scripts/check.sh` + ruff; commit; push.
