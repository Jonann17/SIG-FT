# progress.md

## 2026-08-31 — sessão de criação do cofre
- Instalados: `planning-with-files`, `mattpocock-skills` (grill-me / grilling),
  `graphify` CLI (`uv tool install graphifyy` + `graphify install`).
- Rodada de grill: 4 decisões travadas. Ver [[task_plan]].
- Levantamento completo dos documentos-fonte. Ver [[findings]].
- Cofre escrito.
- `_scripts/regenerar_gerado.py` criado — lê o Box, escreve apenas em `_gerado/`.
- Graphify rodado sobre o cofre.

## 2026-09-30 / 10-01 — sessão "Sistema de Gestão v2"
Pedido: melhorar o gerenciamento — colunas novas no `_STATUS_PMIB` (tipo de entrega,
procurement, atraso de Itaipu em 15 d.u.) e um Power BI com visão interna e visão do cliente.
- Inspecionados: estrutura das pastas, 47 `_STATUS_PMIB`, 26 listas de preços, mapeadora
  (4 abas), `.pbix` (descompactado fora do Box), código do SIG-FT.
- Criados: `_scripts/regras_sobressalentes.py` (regras), `_scripts/gerar_prototipo_dashboard.py`
  → `_gerado/prototipo-dashboard.html`, `_gestao_v2/` (template v2, migração, Power BI).
- Migração **simulada** em cópias (47/47, nenhum dado existente alterado). **Não aplicada no Box.**
- Notas atualizadas: [[Lista de Precos]] (PB021), [[Planilha STATUS_PMIB]],
  [[Organizacao das Pastas]], [[Mapeamento das Listas de Sobressalentes]],
  [[Indicadores e Como Ler]], [[findings]]. Plano em [[Plano - Sistema de Gestao v2]].
- 01/10, por ordem do Luan: cópia `15 - PDM/SECOND BRAIN/` do Box sincronizada (25 arquivos,
  backup antes, nada apagado) e pacote enviado ao GitHub — `luanccozer/SIG-FT`, pasta
  `gestao-sobressalentes/`, branch `claude/gestao-sobressalentes-v2`, Pull Request #2.
  Ponto de partida para a próxima conversa: [[README]].

## 2026-10-04 — correção do DUPLICADO e plano de reestruturação
- Luan corrigiu: STATUS `DUPLICADO` = item repetido **na mesma lista**; ficha duplicada de outro
  sistema = `PDM.9900.000` + PMIB da original em OBSERVAÇÕES. Notas corrigidas (Ciclo de Vida,
  Planilha STATUS_PMIB, Glossário, Fichas Duplicadas); valor em US$ passa a contar a quantidade das
  linhas DUPLICADO; dois alertas novos de qualidade.
- Achado: **o openpyxl apaga comentários em thread** (16 arquivos). A migração passou a pular esses
  arquivos e a conferir anotações, comentários, formatação condicional e desenhos antes/depois.
- Decisões do Luan (04/10): sem DATA DA ENTREGA; nenhum cálculo no Excel (SIG-FT calcula e grava
  valores); sem aba de feriados; comentários têm de ser preservados.
- Novo editor `_gestao_v2/xlsx_cirurgico.py` (altera só 3 partes do .xlsx, o resto byte a byte).
  Simulação: 47/47 sem perda, comentários em thread intactos, todos abrem no LibreOffice.
  Power BI passa a ler prazo/situação/atraso gravados pelo SIG-FT.
- Plano de execução: [[Plano - Reestruturacao do STATUS_PMIB]].
- Por ordem do Luan: **arquivo de teste no Box** `10- TESTES/TESTE_V2_Banco_de_Baterias_STATUS_PMIB_migrado.xlsx`
  (cópia migrada; original intocado). Aguardando o Luan abrir no Excel do trabalho para autorizar os 47.
- Divisão de trabalho combinada: alterações nos `_STATUS_PMIB` seguem **neste chat**; correções do SIG-FT
  na **nuvem do GitHub**, pelo roteiro [[Tarefa SIG-FT - Calculo e Gravacao sem Perda]] (fixtures sintéticas
  em `_gestao_v2/fixtures/`, sem texto real).

## 2026-10-04 (noite) — layout v2 definitivo, APLICADO nos 47
- O teste no Excel do trabalho funcionou; o Luan redefiniu o layout: TIPO DE ENTREGA à direita da
  APLICAÇÃO - LMR; SITUAÇÃO DA AUTORIZAÇÃO **no lugar** do APTO PARA ENTREGA; DIAS DE ATRASO (não
  "dias úteis"); FORNECEDOR e PROCUREMENT por último, antes de OBSERVAÇÕES; **sem** DATA DA
  AUTORIZAÇÃO e **sem** coluna de prazo; linha "REVISÃO DA LISTA ... EM USO" em todas as listas.
- `xlsx_cirurgico.py` ganhou `Deslocamento` + `deslocar()`: inserir colunas/linhas como o Excel
  (células, fórmulas — inclusive compartilhadas —, mesclagens, validações x14, formatação
  condicional, filtro, ordenação, painel congelado, nomes definidos, comentários + caixa VML,
  desenhos, calcChain). Recusa o que não sabe deslocar.
- `migrar_status_pmib_v2.py` reescrito; conferência célula a célula na posição nova.
- Simulação 47/47 sem perda; 47/47 abrem no LibreOffice; **aplicado no Box** (backup em
  `%LOCALAPPDATA%\Sobressalentes-v2\backup_20261004-2342`); arquivos do Box idênticos às cópias
  conferidas. Template `Templates/codigo_itaipu_STATUS_PMIB.xlsx` também atualizado (gravado por cima).
- Números: 636 linhas AUTORIZADO (= os 636 SIM), 149 AGUARDANDO, 55 ATRASADO (53 fichas; a mais
  antiga com e-mail de 24/06/2025, 446 dias). Linha de revisão inserida em 42 listas (5 já tinham),
  semeada com a REVISÃO EM USO da mapeadora (DATA DE ALTERAÇÃO "—": não se sabe).
- Regras (`situacao_autorizacao` nova), protótipo, Power BI (`00`, `03`, `04`, `05`, LEIA-ME) e o
  roteiro do SIG-FT ([[Tarefa SIG-FT - Calculo e Gravacao sem Perda]], T0–T5) atualizados.

## 2026-10-05 — ficha DOCUMENTAL não precisa de autorização
- Correção do Luan: componente explodido (TIPO DE ENTREGA = DOCUMENTAL) só tem ficha; a entrega física
  — e a autorização de Itaipu — é a do pai (FÍSICA E DOCUMENTAL). SITUAÇÃO passa a `N/A`, sem dias.
- Regra (`situacao_autorizacao(..., tipo)`), migração (`--recalcular [--apenas-documental]`), Power BI
  (`03`, `05`, LEIA-ME), protótipo e roteiro do SIG-FT (T2) atualizados.
- Box: só #ST00=M00MEU10&MPB020 tinha documentais com situação — 62 células (61 AGUARDANDO + 1 vazia →
  N/A), backup `backup_20261005-0808`, conferência sem outra mudança, abre no LibreOffice.

## 2026-10-05 (manhã) — só FÍSICA conta; mapeadora no v2; roteiro do SIG-FT completo
- Correção do Luan: TÍTULO e TIPO vazio também não contam — só FÍSICA E DOCUMENTAL precisa de autorização
  (DOCUMENTAL/TÍTULO = N/A; vazio = branco). Regra, Power BI, protótipo atualizados; nenhum dado gravado mudou.
- **Defeito da migração corrigido**: DIAS DE ATRASO com formato de data em 33 arquivos (884 células) → formato
  Geral, valor intocado; template também. `_inteiro()` passou a ler número com formato de data.
- **Mapeadora no tratamento v2** (pedido do Luan): 3 colunas inseridas no bloco PMIB (FICHAS DE ENTREGA FÍSICA,
  AGUARDANDO AUTORIZAÇÃO ITAIPU, MAIOR ATRASO ITAIPU (DIAS)); APTO e ATRASO recalculados (ex.: ATRASO de
  #ST00=M00MEU10&MPB020 111 → 3); mensagens nos cabeçalhos e na REVISÃO EM USO. Nenhuma coluna renomeada (o
  `.pbix` atual usa APTO pelo nome). `_gestao_v2/atualizar_mapeadora_v2.py`; backup `backup_mapeadora_20261005-0824`.
- Achado: o Gestão PMIB entra em `testes_autospec/` — o link de #ST00=B01BMU10&EPB020 aponta para a cópia de teste.
- **Roteiro do SIG-FT reescrito** (T0–T5) + **kit de teste** sintético (`fixtures/kit_gestao_pmib/`, 13 casos,
  isca, layout antigo, mapeadora e DocManager sintéticos, `esperado.json`) + `validar_kit_gestao_pmib.py`
  (a referência dá KIT OK). Cópia de referência do `apto_para_entrega_att.py` em `_gestao_v2/referencia_sigft/`.

## 2026-10-05 (tarde) — macro inegociável, mapeadora = cadastro, Power BI v2 montado
- Luan: a T6 (lista de preços 0A) só vale se o **rodapé for feito pela macro** do template — roteiro refeito
  (passo 2 no Excel do trabalho via xlwings); validação final prática; a lista do PDG não é modelo.
- Luan: o "plano R2" era a arquitetura v2 — **mapeadora = cadastro**, contagens no Power BI. Eu tinha feito o
  contrário (acrescentado colunas). Roteiro do SIG-FT e kit corrigidos (o Gestão PMIB grava só REVISÃO EM USO,
  SITUAÇÃO NO PMIB e LINK).
- **Power BI v2 montado** como Projeto do Power BI (`montar_pbip.py` → TMDL + PBIR, relatórios Interno e Itaipu),
  instalado o Power BI Desktop nesta máquina (autorizado) e **testado com os dados reais**: modelo validado pela
  biblioteca oficial (TOM), as 7 tabelas atualizam, medidas batem com a referência em Python, páginas conferidas
  por captura de tela. Entregue no Box: `SOBRESSALENTES - PMIB/Sobressalentes v2 (Power BI)/`.
- **Mapeadora**: retirado o bloco de 18 colunas de contagem (`xlsx_cirurgico.remover_colunas`, nova); sem perda,
  abre no LibreOffice, o Power BI v2 atualiza com ela. O `.pbix` antigo deixou de atualizar.

## 2026-10-05 (tarde/noite) — Power BI v3: executivo
- Luan achou o v2 "feio, poluído"; quer ver a situação geral das fichas, das listas de sobressalentes e das listas
  de preços, com filtro por ET e capítulo, e **sem barra empilhada em porcentagem**. Também perguntou como
  atualizar em outra máquina.
- **Feito**:
  - desenho novo em `_gestao_v2/powerbi/relatorios_v2.py`: tema no estilo do protótipo HTML; filtros ET/Capítulo
    sincronizados; páginas Visão geral, Listas, Listas de preços, Autorização, Fila; Itaipu: Panorama e Pendências;
  - consulta `PastaPMIBEfetiva`, que acha `C:\Users\<usuário>\Box\...\SOBRESSALENTES - PMIB` sozinha;
  - colunas Etapa e Etapa Cliente legíveis e ordenadas;
  - medidas novas para listas de preços.
- **Testado** no Desktop com o parâmetro vazio e os dados reais; páginas conferidas por captura de tela.
- **No Box** (Luan autorizou substituir sem backup): `Sobressalentes v2 (Power BI)/` = versão v3 testada.
  Leitura final com o filtro de ET (propaga entre as páginas) e as duas páginas do Itaipu. Corrigido: cartão com
  "(Em branco)" passou a mostrar 0.
- Falta regenerar `_gestao_v2/powerbi/pbip/` no cofre: ainda é a saída da v2 (bloqueado pelo controle de
  permissões; `python montar_pbip.py` refaz).

## 2026-10-05 (fim da tarde) — painel HTML alinhado ao Power BI; T7 no roteiro do SIG-FT
- Luan perguntou se o HTML pode entrar no SIG-FT e aprovou incluir como **T7**: botão no Gestão PMIB que gera o
  painel e abre no navegador. O Power BI segue como painel oficial.
- O gerador `_scripts/gerar_prototipo_dashboard.py` **quebrava** desde que a mapeadora virou cadastro (lia
  `FICHAS EXISTENTES`). Corrigido:
  - saíram os dois achados de qualidade que dependiam das contagens;
  - ganhou parâmetros `--pasta`, `--mapeadora`, `--saida` e `--hoje`.
- Template alinhado ao Power BI v3:
  - filtros Especificação técnica e Capítulo;
  - indicadores por PMIB distinto;
  - "Material entregue" = itens físicos.
- Conferido com os dados reais, os mesmos números nos dois painéis:
  - sem filtro: 1.352 / 615 / 53 / 122 / 1.084;
  - com Controle Centralizado: 291 / 255 / 32 / 0 / 205.
- Novo `_gestao_v2/validar_painel.py`: compara o painel do SIG-FT com a referência no kit de teste. Testado: diz
  PAINEL OK para a referência e pega dado trocado, script externo e filtro faltando.

## Proximas sessões
1. **SIG-FT** (a partir de 05/10, na nuvem): T0 cabeçalho na linha 5 (módulo PDM); T1 gravar sem
   openpyxl; T2 situação/dias de atraso; T3 revisão em uso → mapeadora; T4 export de autorizados.
2. **Montar o Power BI** a partir de `_gestao_v2/powerbi/`.
3. **Plano de ação — fichas emitidas sem Aplicação LMR** (269 fora do compromisso em 01/10).
4. **Gargalo das Listas de Preços**: campo "revisão da lista de sobressalentes a que se refere".
