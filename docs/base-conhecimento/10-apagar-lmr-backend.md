# Apagar LMR Backend (`apagar_lmr_backend.py`)

> ⚠️ **Onde o código mora hoje** (atualizado em 2026-08-28)
>
> Este documento foi escrito antes da refatoração e descreve o comportamento do
> módulo, que continua valendo. Mas os CAMINHOS mudaram:
>
> | O que o texto abaixo chama de | Está hoje em |
> |---|---|
> | `apagar_lmr_backend.py` | `sigft/services/apagar_lmr.py` (serviço) · `sigft/app_qt/views/apagar_lmr.py` (tela) |
>
> A lógica de negócio descrita aqui continua válida; o que mudou foi onde ela vive. Camadas novas que este texto não menciona: `sigft/core/excel/` (cabeçalho de planilha, código PMIB, gravação com retry), `sigft/core/llm/` (cliente de IA multi-provedor), `sigft/core/rpa/` (portal e motor), `sigft/core/callbacks.py` (o protocolo UI↔serviço).

## Propósito
Automatiza a exclusão de todas as aplicações (LMR) associadas a uma ficha técnica no portal PMIB. O módulo busca a ficha pelo código, abre a aba "Aplicação - LMR", entra em loop deletando cada linha até TimeoutException indicar que nenhuma linha permanece, e confirma cada exclusão via popup.

## Entradas e Saídas
- **Entradas**: 
  - Código PMIB (ID da ficha técnica a limpar)
  - URL portal PMIB: `https://apps.itaipu.gov.br/PMIB/PMIB_DatasheetList`
  - Callback: `callback_log` (logging de progresso)
- **Saídas**: 
  - Ficha PMIB com aba LMR vazia (todas as linhas deletadas)
  - Logs de sucesso/erro via callback

## Classes e Funções

### `ApagarLMRAutomation` (linha 13)
Gerencia automação Selenium para exclusão de LMRs.

- `__init__()`: inicializa driver=None, wait=None, url_inicial
- `iniciar_driver()`: instancia Chrome webdriver maximizado, WebDriverWait 20s
- `fechar_driver()`: encerra navegador (quit)
- `abrir_portal()`: navega para url_inicial
- `safe_click(locator)`: helper de clique seguro com scroll e retry (linha 35-43)
  - Espera elemento estar presente
  - Scroll para visibilidade (center block)
  - Aguarda ser clicável
  - Executa clique via JavaScript
  - Ignora silenciosamente exceções
- `_pesquisar_e_abrir(pmib)`: pesquisa PMIB e clica botão editar (lápis) para abrir ficha, retorna tupla `(sucesso: bool, mensagem)` (linha 45-80)
  - Garante estar na URL inicial
  - Busca campo pesquisa com XPath `//input[contains(@placeholder, 'Código')]`
  - Limpa campo, digita PMIB, Enter
  - Aguarda 3s tabela recarregar
  - Clica ícone lápis via XPath dinâmico: `//span[text()='{pmib}']/ancestor::tr//i[contains(@class, 'fa-pencil')]/parent::a`
  - Aguarda 4s edição abrir
  - Retorna True se sucesso, False + mensagem se não encontra
- `executar_limpeza(pmib_codigo, callback_log)`: abre ficha e loop de exclusão (linha 83-153)

## Fluxo detalhado

1. **Abertura de Ficha** (linha 87-93)
   - Chama `_pesquisar_e_abrir(pmib_codigo)`
   - Se falha, loga mensagem e retorna
   - Se sucesso, prossegue

2. **Acesso à Aba LMR** (linha 95-103)
   - Clica botão LMR via XPath `//*[@id="b10-ApplicationMRL"]/button` (linha 99)
   - Aguarda 2s abrir aba
   - Se erro (pode já estar aberta), ignora (except genérico) (linha 103)

3. **Loop de Exclusão** (linha 106-147)
   - Inicializa contador `count = 0`
   - Loop infinito while True (linha 109):
     - Aguarda 1s tabela estabilizar
     - Tenta localizar primeira lixeira (ícone fa-trash na linha 2 da tbody)
     - XPath: `//*[@id="b10-b19-$b17"]/table/tbody/tr[2]//i[contains(@class, "fa-trash")]/parent::a`
     - Scroll para visibilidade (center)
     - Clica lixeira (JS click)
     - Tenta localizar botão CONFIRMAR via XPath genérico: `//button[@type="button" and text()="CONFIRMAR"]`
     - Clica confirmar (JS click)
     - Incrementa contador
     - Loga "Item N apagado"
     - Aguarda 1.5s para refresh tabela
     - **Se TimeoutException**: não achou mais lixeiras → break, sucesso (linha 137-140)
     - **Se StaleElementReferenceException**: tabela atualizou → continue (linha 141-143)
     - **Se outro erro**: para (linha 144-147)

4. **Retorno à Lista** (linha 149-153)
   - Tenta navegar para url_inicial (bom para fluxo contínuo)
   - Ignora silenciosamente exceção (opcional)

## Integrações
- **Portal PMIB**: lista de fichas, edição, aba LMR, exclusão via lixeira
- **Frontend**: callback_log para progresso
- **Saída**: tabela LMR vazia na ficha

## Pontos de atenção
- XPath da tabela `//*[@id="b10-b19-$b17"]/table/tbody/tr[2]` assume estrutura HTML específica — mudança no layout quebra localização (linha 117)
- tr[2] é hardcoded para primeira linha de dados; se header tiver múltiplas linhas ou estrutura mudar, alvo errado (linha 117)
- Safe_click ignora exceções silenciosamente (except genérico) — pode mascarar problemas reais (linha 42)
- TimeoutException é esperado e indica sucesso (fim do loop) — lógica contra-intuitiva (linha 137)
- StaleElementReferenceException é recuperável via continue — pode causar loop infinito se elemento não se estabilizar (linha 141-143)
- Sleep fixo 0.5-1.5s entre ações — em conexões lentas podem ser insuficientes
- WebDriverWait timeout global 20s — se operação específica demora mais, levanta TimeoutException inesperada
- Callback_ask não é usado aqui (apenas callback_log) — confirmação é automática via popup
- Se popup de confirmação tiver texto diferente de "CONFIRMAR", XPath falha silenciosamente (linha 129)
- Função não valida quantas linhas foram deletadas vs. quantas deveriam estar; sucesso é determinado apenas por TimeoutException
