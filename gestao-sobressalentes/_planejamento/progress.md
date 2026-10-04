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
- Simulação de 04/10: 31 migrados sem perda, 16 pulados intactos.
- Plano de execução: [[Plano - Reestruturacao do STATUS_PMIB]]. Aguardando aprovação.

## Proximas sessões
1. **Aplicar a migração v2** (depois das decisões da seção 8 do plano) e montar o Power BI.
2. **SIG-FT**: 15 d.u. no `pmib_manager.py`; carimbar DATA DA AUTORIZAÇÃO no script de aptos;
   follow-up de preços em PB021.
3. **Plano de ação — fichas emitidas sem Aplicação LMR** (269 fora do compromisso em 01/10).
4. **Gargalo das Listas de Preços**: campo "revisão da lista de sobressalentes a que se refere".
