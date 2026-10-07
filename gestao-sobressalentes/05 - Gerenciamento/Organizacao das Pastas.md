---
tags: [gerenciamento, referencia]
---

# Organização das Pastas

Mapa de `Box/CMI - Consorcio Itaipu/11 - Ger. Engenharia/15 - PDM/`.

> [!danger] Regra
> Esta pasta e conteudo sensivel. **Não alterar nada** sem instrução explicita.
> Os scripts deste cofre a acessam **somente em leitura**.

## Raiz

| Item | O que e |
|---|---|
| `SOBRESSALENTES - PMIB/` | **o coracao** — as listas por ET e sistema |
| `Templates/` | modelos vivos do processo |
| `_python_pdm/` | código Python. **Desatualizado** frente ao GitHub |
| `PDMs From Itaipu/`, `PDMs modificados/` | catalogos de PDM |
| `PDMs SAM-GM 23.09.26.xlsx` | catálogo de PDM mais recente (23/09/2026) |
| `SECOND BRAIN/` | **cópia deste cofre** dentro do Box, para a equipe — o original vive no OneDrive; sincronizar à mão |
| `Apresentação PMIB (PDM) R5.pptx` | o fluxo vigente (a R4 foi para `0 - Obsoleto/`) |
| `AR-EN.DT-001-2026.pdf` | [[Ata AR-EN.DT-001-2026 - As Duas Listas\|ata das duas listas]] |
| `Procedimiento - Fichas PMIB Duplicadas PDM_9900_000.pdf` | [[Procedimento de Fichas Duplicadas]] |
| `Revision Propuesta CMI AplicacionLMR.pdf` | [[Revisao da Aplicacao LMR - Agosto 2026]] |
| `Extrato dos Eventos dos Sobressalentes.xlsx` | eventos de pagamento (80% no recebimento, 20% na aprovação) |
| `PRESENTACION PORTAL PMIB (INTRODUCCION)...mp4` | gravacao de treinamento do portal (2024) |
| `0 - Obsoleto/` | arquivo morto — inclui as apresentações R0–R4, os catálogos `1174`, `1178` e `1193` e `Todos PDMs & Instruções.xlsx` |

> [!success] Divergência do catálogo de PDM resolvida (set/2026)
> Os catálogos `1174` e `1193` foram para `0 - Obsoleto/`. O vigente é
> `PDMs SAM-GM 23.09.26.xlsx`.

## `SOBRESSALENTES - PMIB/`

Agrupamento por ET / área:

```
00 - OBSOLETO
01 - CONTROLE CENTRALIZADO
      RTA - Concluido/       ← a unica marcada como concluida
      SCADA/
      SERVICOS AUXILIARES ESSENCIAIS/
02 - INFRAESTRUTURA COMPLEMENTAR
      SALA SEGURA/
03 - EBOP                    (Electrical Balance of Plant)
      GERADOR DIESEL/  PAINEIS DE MANUTENCAO/  SFC/
      SISTEMA DE VENTILACAO E EXAUSTAO PARA SALA GD/
      TRANSFORMADORES AUXILIARES A OLEO/
04 - MBOP                    (Mechanical Balance of Plant)
      Fire Fight/
05 - UNIDADE GERADORA        ← a maior: 53 listas
      AUXILIARES A UG/  AUXILIARES ESSENCIAIS/  COMPORTA E BYPASS/
      REGULACAO VEL E POT/  SIS DIGITAL DE SUPERVISAO E CONTROLE/
      SISTEMA DE ALIMENTACAO ELETRICA DA UNIDADE/  SISTEMA DE EXCITACAO/
      SISTEMA DE PROTECAO/  TRANSFORMADORES ELEVADORES PRINCIPAIS/
      VALVULAS BY-PASS E CONDUTO FORCADO/
06 - SMF                     (Sistema de Medicao de Faturamento)
07 - VERTEDOURO
08 - GIS
09 - SEM LISTA ASSOCIADO     ← fichas orfas
10 - TESTES
Mapeamento Listas de Sobressalentes.xlsx
Sobressalentes - Dashboard.pbix
sobressalentes_autorizados_AAAAMMDDhhmm.xlsx   ← export de Itaipu: PMIB com código SAP (vira APTO = SIM)
```

> [!warning] Cópias de trabalho no meio das planilhas vivas
> Em 01/10/2026 havia 9 arquivos de trabalho misturados aos vivos — `..._STATUS_PMIB_.xlsx`
> (com `_` a mais), `testes_autospec/`, `Datasheets/ST00B01MSE00EPB020_STATUS_PMIB.xlsx`,
> `... - Copy.xlsm`, `... corrigido.xlsm`. Quem varre a árvore (SIG-FT, Power BI) pode contar
> em dobro. Convenção proposta: na pasta do sistema, **só o arquivo vigente**; o resto numa
> subpasta `_obsoleto/`.

> [!warning] `09 - SEM LISTA ASSOCIADO`
> Contém `Fichas_criadas/` e `Fichas_recebidas/`. São fichas que existem **sem lista de
> sobressalentes correspondente**. Na mapeadora aparece uma linha com `SEM LISTA` em
> todos os campos. E um sintoma de ficha criada antes ou fora do processo formal.
> Ver [[Diagnostico - Deficiencias]].

> [!note] EBOP/MBOP x nomenclatura de ET
> As pastas usam EBOP e MBOP como agrupadores fisicos, mas a mapeadora classifica pela
> ET (`SERVICOS AUXILIARES ELETRICOS`, `SERVICOS AUXILIARES MECANICOS`). **Os dois
> vocabularios convivem** — a pasta não e a fonte de verdade da classificação.

### Dentro de uma pasta de sistema
Padrão observado (ex.: `01 - CONTROLE CENTRALIZADO/RTA - Concluido/`):
- o PDF da lista emitida (`#ITA0=Y01TF001&BPB020[0A].pdf`)
- o `_STATUS_PMIB.xlsx`
- pasta de desenhos de referência (`RTA - docs - codigo/`)
- `Datasheets/` do fornecedor
- correspondencia com Itaipu (correções, seleção de PDMs)

## `Templates/`

| Arquivo | Uso |
|---|---|
| `Ficha Tecnica do PDM-R3.xlsx` | [[Anatomia de uma Ficha Tecnica\|o template da ficha]] |
| `Technical Sheet of PDM-R3.xlsx` | versão em espanhol |
| `codigo_itaipu_STATUS_PMIB.xlsx` | [[Planilha STATUS_PMIB\|template do STATUS_PMIB]] (antes `no_itaipu_STATUS_PMIB.xlsx`) |
| `Aplicação LMR - Sistema.xlsx` | [[Secao - Aplicacao LMR\|template da LMR]] |
| `Lista de Sobressalentes com preço.xlsm` | [[Lista de Precos]] — código `...PB021` |


Os guias de preenchimento (PT/EN) foram para `0 - Obsoleto/`.

## Onde a ET Geral realmente mora

**Não** está em `15 - PDM`. está em:
```
01 - Ger. Integracao/01 - Edital/
  02 ANEXO II - ESPECIFICACAO TECNICA - PORTUGUES/
    ANEXO II - A - ET GERAL/604720T0018P(1)R1.pdf
```
Ver [[ET Geral 6047-20-T0018]].

## Relacionados
[[Mapeamento das Listas de Sobressalentes]] · [[Planilha STATUS_PMIB]]
