---
tags: [moc, indice]
atualizado: 2026-08-31
---

# Sobressalentes — Projeto de Modernizacao de Itaipu

Cofre de conhecimento do processo de materiais sobressalentes do **Consórcio de
Modernizacao de Itaipu (CMI)**, contrato **4500063671**.

> [!tip] Continuando de outra conversa?
> Comece por [[README]] — o que foi descoberto em 30/09–01/10/2026 e as próximas tarefas.

> [!info] Como ler este cofre
> Chegando agora: [[Projeto de Modernizacao de Itaipu]] ->
> [[Anatomia de uma Ficha Tecnica]] -> [[Fluxo Macro de Entrega]] ->
> [[Ciclo de Vida de um Item]].
> Já opera o processo e quer a ferramenta: [[SIG-FT - Visao Geral]].
> Quer saber onde doi: [[Diagnostico - Deficiencias]].

## Como este cofre e dividido

> [!important] O nucleo descreve como o sistema funciona, nao como ele esta
> Numero de ficha, percentual, quem esta com o que — isso muda toda semana e vive na
> planilha, nao aqui. O nucleo (`01` a `06`) e permanente: conceitos, processos e cada
> etapa deles.

| Pasta | O que guarda | Muda quando |
|---|---|---|
| `01 - Contexto` | projeto, atores, estrutura de ET e capitulo | raramente |
| `02 - Normativo` | ET, anexos, atas, procedimentos | quando Itaipu publica algo |
| `03 - Processo` | **o coracao** — fluxo, secoes da ficha, cada etapa | quando o processo muda |
| `04 - Codificacao` | RDS-PP, KKS, codigo PMIB, PDM | raramente |
| `05 - Gerenciamento` | os instrumentos: _STATUS_PMIB, mapeadora, indicadores | quando o instrumento muda |
| `06 - SIG-FT` | o que cada modulo faz (o detalhe fica no repositorio) | quando o app muda |
| `07 - Diagnostico` | **documentos de trabalho** — planos e diagnosticos, datados | sao instantaneos |
| `_gerado` | saidas de script, sempre refeitas | a cada execucao |


## O que este processo entrega, em uma frase

Cada material sobressalente comprado para a modernizacao precisa chegar ao
almoxarifado de Itaipu **acompanhado de uma ficha técnica aprovada no portal PMIB** —
e essa ficha e condição para liberar os eventos de pagamento do contrato.

## Mapa

### 01 — Contexto
- [[Projeto de Modernizacao de Itaipu]]
- [[Estrutura ET, Capitulo e Sistema]]
- [[Atores e Areas]]
- [[Glossario]]

### 02 — Normativo
- [[ET Geral 6047-20-T0018]]
- [[Capitulo 18 - Pecas de Reposicao e Sobressalentes]]
- [[Anexo I - Classificacao de Materiais Sobressalentes]]
- [[Anexos II e III - Ficha de Material Reserva e PDM]]
- [[Ata AR-EN.DT-001-2026 - As Duas Listas]]
- [[Procedimento de Fichas Duplicadas]]
- [[Revisao da Aplicacao LMR - Agosto 2026]]

### 03 — Processo
- [[Fluxo Macro de Entrega]]
- [[Entrega Documental e Explosao de Itens]] — por que uma lista de 67 equipamentos vira 164 fichas
- [[Lista de Sobressalentes]]
- [[Lista de Precos]]
- [[Anatomia de uma Ficha Tecnica]]
- [[Secao - Informacoes Gerais]]
- [[Secao - Caracteristicas Tecnicas]]
- [[Secao - Condicoes]]
- [[Secao - Valorizacao]]
- [[Secao - Documentos e Imagens]]
- [[Secao - Aplicacao LMR]]
- [[Fichas Duplicadas]]
- [[MTA, Etiquetas e Entrega no Almoxarifado]]

### 04 — Codificação
- [[RDS-PP e KKS]]
- [[Codigo PMIB]]
- [[Codigo CMI e Codigo Itaipu]]
- [[PDM - Padrao de Descricao de Material]]

### 05 — Gerenciamento
- [[Mapeamento das Listas de Sobressalentes]]
- [[Planilha STATUS_PMIB]]
- [[Ciclo de Vida de um Item]]
- [[Indicadores e Como Ler]]
- [[Organizacao das Pastas]]

### 06 — SIG-FT
- [[SIG-FT - Visao Geral]]
- [[SIG-FT - Arquitetura]]
- [[SIG-FT - Modulos]]
- [[SIG-FT - Camada de IA]]
- [[SIG-FT - Motor de RPA]]
- [[SIG-FT - Refatoracao]]
- [[SIG-FT - Como Rodar]]

### 07 — Diagnostico
- [[Plano - Sistema de Gestao v2]] — **_STATUS_PMIB v2, regra dos 15 d.u. e Power BI interno × Itaipu** (01/10/2026)
- [[Plano - Reestruturacao do STATUS_PMIB]] — **execução da migração**, sem perder histórico nem listas suspensas (04/10/2026)
- [[Diagnostico - Deficiencias]]
- [[Diagnostico - Riscos]]
- [[Diagnostico - Plano de Melhoria]]
- [[Plano - Aba de Listas de Precos]] — hand-off pronto para execução
- [[Plano - Dimensao de Tempo]] — como instrumentar prazo no gerenciamento
- [[Plano - Revisao em Uso automatica]] — tirar a coluna REVISÃO EM USO do preenchimento à mão
- [[Aba de Atividades e Cronograma]] — a aba de acompanhamento e o Gantt gerado dela
- [[Plano de Acao - Aplicacao LMR]] — o passivo e a negociação do novo fluxo
- [[Plano de Acao - ESTRUTURA]] — **esqueleto do plano formal** (reunião Itaipu 31/08)

### Gerado automaticamente
- [[Panorama Quantitativo]] — números da mapeadora. `_scripts/regenerar_gerado.py`
- [[Mapa de Conexoes]] — hubs e ligações do próprio cofre. `_scripts/mapa_de_conexoes.py`
- [[Levantamento - Fichas sem Aplicacao LMR]] — o universo do gargalo. `_scripts/levantamento_lmr.py`
- `_gerado/prototipo-dashboard.html` — protótipo do painel (visão interna e visão Itaipu), item a item. `_scripts/gerar_prototipo_dashboard.py`

### Gestão v2 (`_gestao_v2/`)
- `template/codigo_itaipu_STATUS_PMIB_v2.xlsx` — template novo
- `migrar_status_pmib_v2.py` — migração dos `_STATUS_PMIB` (`--simular` / `--aplicar`)
- `powerbi/` — consultas Power Query, medidas DAX e o [[LEIA-ME]] de montagem

### Planejamento
- [[task_plan]] · [[findings]] · [[progress]]

---

> [!warning] Regra de ouro deste cofre
> Nada aqui escreve no Box. Os scripts de `_scripts/` **leem** as planilhas do Box e
> escrevem apenas dentro de `_gerado/`.
