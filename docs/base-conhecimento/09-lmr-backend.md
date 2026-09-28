# LMR Backend (`lmr_backend.py`)

> ⚠️ **Onde o código mora hoje** (atualizado em 2026-08-28)
>
> Este documento foi escrito antes da refatoração e descreve o comportamento do
> módulo, que continua valendo. Mas os CAMINHOS mudaram:
>
> | O que o texto abaixo chama de | Está hoje em |
> |---|---|
> | `lmr_backend.py` | `sigft/services/lmr.py` (serviço) · `sigft/app/views/lmr.py` (tela) |
>
> **Desde 2026-09-28** cada código só conta como inserido com a mensagem de sucesso
> do portal, e os botões SALVAR/CONFIRMAR mudaram de seletor: ver a seção no fim.
>
> A lógica de negócio descrita aqui continua válida; o que mudou foi onde ela vive. Camadas novas que este texto não menciona: `sigft/core/excel/` (cabeçalho de planilha, código PMIB, gravação com retry), `sigft/core/llm/` (cliente de IA multi-provedor), `sigft/core/rpa/` (portal e motor), `sigft/core/callbacks.py` (o protocolo UI↔serviço).

## Propósito
Automatiza o preenchimento da aba "Aplicação - LMR" (Lista de Materiais de Reposição) no portal PMIB via Selenium. O módulo lê dados de Excel (aba GERAL com colunas PMIB, Código_PMIB, TAG_PMIB), agrupa TAGs consecutivas por código, navega para a ficha no PMIB, preenche campos de código, quantidade e TAGs, e registra erros em CSV.

## Entradas e Saídas
- **Entradas**: 
  - Arquivo Excel com aba "GERAL" contendo colunas: PMIB (ficha ID), Código_PMIB (código do equipamento), TAG_PMIB (etiqueta/localização)
  - URL portal PMIB: `https://apps.itaipu.gov.br/PMIB/PMIB_DatasheetList`
  - Callbacks: `callback_log` (logging), `callback_ask` (diálogos sim/não), `callback_input` (entrada de texto)
- **Saídas**: 
  - Preenchimento automático de ficha no PMIB (campos Equipment Code, Quantity Installed, Tag)
  - Arquivo `erros_lmr.csv` com registros de falhas (ficha_pmib, index, codigo_pmib, erro)
  - Logs via callback

## Classes e Funções

### `LMRAutomation` (linha 15)
Gerencia automação Selenium para preenchimento LMR.

- `__init__()`: inicializa driver=None, wait=None, url_inicial
- `iniciar_driver()`: instancia Chrome webdriver maximizado, WebDriverWait 20s
- `fechar_driver()`: encerra navegador (quit)
- `abrir_portal(url=None)`: navega para url ou url_inicial
- `carregar_dados_excel(caminho_excel)`: lê aba "GERAL" com usecols ['PMIB', 'Código_PMIB', 'TAG_PMIB'] como strings, limpa espaços, remove NaN, retorna tupla `(sucesso: bool, df_completo, lista_pmibs_unicos, mensagem)` (linha 38-58)
- `_processar_ficha_lmr_interna(df_filtrado, callback_log, callback_input, callback_ask)`: lógica interna de preenchimento para uma ficha, retorna lista de erros dicionários (linha 61-156)
- `processar_lista(lista_pmibs, df_completo, callback_log, callback_ask, callback_input)`: fluxo principal para múltiplas fichas, retorna lista de fichas com erro (linha 159-249)

## Fluxo detalhado

1. **Carregamento de Dados**
   - `carregar_dados_excel()` lê GERAL, limpa whitespace de PMIB, filtra NaN
   - Retorna dataframe completo + lista de PMIBs únicos
   - Se erro (aba não encontrada, arquivo corrompido), retorna mensagem descritiva

2. **Pergunta de Linha Inicial** (linha 74-86)
   - Callback `callback_ask()`: "Deseja começar de uma linha específica?"
   - Se sim, `callback_input()` pede número de linha (0 a len-1)
   - Se entrada inválida ou fora do intervalo, começa do zero
   - Linha escolhida se torna `index` inicial do loop

3. **Loop por PMIB** (linha 168-240)
   - Para cada PMIB na lista:
     - Pesquisa PMIB no campo XPath `//*[@id="b7-InputDatasheetFilter"]` (linha 181)
     - Limpa campo com Ctrl+A + Backspace, digita PMIB, Enter
     - Aguarda 3s recarregar tabela
     - Navega por 24 TABs sequenciais para chegar ao botão "Editar" (linha 197)
     - Clica Editar com Enter
     - Aguarda 3s abrir ficha
     - Clica aba LMR pelo XPath `//*[@id="b10-ApplicationMRL"]/button` (linha 206)

4. **Agrupamento e Preenchimento** (linha 92-156)
   - Filtra DataFrame para PMIB atual
   - Chama `_processar_ficha_lmr_interna()`
   - Começa do `index` (linha 92)
   - Loop while `index < len(df_filtrado)`:
     - Extrai `Código_PMIB` da linha atual
     - Agrupa todas as TAGs consecutivas com mesmo `Código_PMIB` (linha 100-104)
     - XPath campo código: `//*[@id="b10-b19-Input_EquipmentCode"]`
     - XPath campo quantidade: `//*[@id="b10-b19-Input_QuantityInstalled"]`
     - XPath campo TAG: `//*[@id="b10-b19-Input_Tag"]`
     - Para cada TAG do grupo: envia TAG, TAB, ENTER (0.5s pause entre)
     - Clica salvar form: `//*[@id="b10-b19-Form"]/div[2]/button[1]`
     - Clica confirmar footer: `//*[@id="b10-b19-b22-b1-Footer"]/div/button[1]`
     - Aguarda 1s
     - Se sucesso, adiciona código a `processados_ok`, index já foi incrementado no agrupamento
     - Se erro, registra dicionário de erro, pausa para correção manual, **não incrementa index** (repete item) (linha 152-154)

5. **Tratamento de Erro**
   - Callback `callback_ask()`: exibe mensagem "Erro no item {código}. Corrija manualmente no navegador e clique OK"
   - Usuário corrige manualmente no navegador e clica OK
   - Loop tenta o mesmo item novamente

6. **Finalização**
   - Voltar para lista: clica XPath `//*[@id="b9-Content"]` (linha 223)
   - Se erro fatal em ficha inteira, registra e tenta recarregar home
   - Se erros totais, salva `erros_lmr.csv` com pandas DataFrame (linha 244-247)

## Integrações
- **Planilha**: aba GERAL com colunas PMIB, Código_PMIB, TAG_PMIB
- **Portal PMIB**: URL inicial, pesquisa, edição de fichas, navegação TAB (24x), preenchimento de campos
- **Frontend**: callbacks para log, confirmação (ask), entrada (input)
- **Saída**: arquivo `erros_lmr.csv` no diretório de execução

## Pontos de atenção
- Sequência de 24 TABs (linha 197-198) é hardcoded e específica ao layout do portal PMIB — mudanças no HTML quebram navegação
- Agrupamento de TAGs assume que DataFrame está ordenado; dados desordenados podem agrupar TAGs erradas (linha 100-104)
- Quando erro ocorre, `index` **não é incrementado** (linha 154 comentado): repete item — pode causar loop infinito se erro persiste
- Sleep fixo de 0.5-3s entre ações — em conexões lentas podem ser insuficientes (timeouts)
- Callback `callback_ask()` é bloqueante; se usuário não responder, automação congela
- Coluna 'PMIB' de string exige formatação consistente (sem espaços); valores fora do padrão não encontram ficha
- Tratamento de erro genérico (except Exception) engole informação de erro específico, dificultando debug (linha 136)
- CSV de erros é salvo no diretório de execução, não em pasta estruturada — pode não ser encontrado facilmente
- WebDriverWait timeout é 20s global — se operação específica demora mais, levanta TimeoutException não capturada

---

## 2026-09-28 — SALVAR → CONFIRMAR → só segue com a mensagem do portal

Relato do usuário: *"ele não está conseguindo subir as informações"*. Os
botões eram clicados por posição dentro de ids gerados pelo OutSystems
(`//*[@id="b10-b19-Form"]/div[2]/button[1]` e
`//*[@id="b10-b19-b22-b1-Footer"]/div/button[1]`), e o log dizia "inserido ✔️"
no instante do clique, sem conferir nada. Os XPaths de salvar/confirmar da
seção "Fluxo detalhado" acima são os antigos.

O fluxo agora, por código LMR (`LMRAutomation._salvar_e_confirmar_codigo`):

1. espera sair da tela a mensagem de sucesso do código anterior — ela é
   **idêntica** a cada código, e com ela na tela a nova seria dada por velha
   (`PMIBPortal.esperar_confirmacao_anterior_sumir`, até 15 s);
2. clica o SALVAR **do formulário de LMR** (`type="submit"`, ancorado no campo
   do código — e não o primeiro SALVAR da tela, que é o de Informações gerais);
3. espera o diálogo e clica o CONFIRMAR (`type="button"`; primeiro dentro de
   `role="dialog"`, depois o mesmo seletor com que o `apagar_lmr` confirma a
   exclusão nesta aba);
4. só conta como inserido com **"As informações da aplicação LMR foram
   adicionadas com sucesso!"** nova na tela
   (`PALAVRA_DA_SECAO["Aplicação LMR"] = "lmr"`: a mensagem de outra seção não
   confirma a LMR).

Sem a mensagem, o código **não** entra como inserido: vai para
`erros_lmr.csv`, a ficha fica INCOMPLETA no `_STATUS_PMIB`, e a pessoa é
chamada **antes** do próximo código, com o motivo — diálogo que não abriu,
aviso do portal no lugar dele, mensagem que não veio, ou diálogo que ficou
aberto (que travaria a página inteira).

✅ Validado no portal pelo usuário na v1.1.1-rc.4 (2026-09-28). Os botões e a
mensagem vêm do HTML do usuário, e os seletores têm teste com `lxml` sobre ele;
o registro de antes da validação está em `docs/refatoracao/PENDENCIAS.md`,
2026-09-28.
