---
tags: [sigft, core]
repo: https://github.com/luanccozer/SIG-FT
---

# SIG-FT — Visão Geral

**Sistema Integrado de Gestão de Fichas Técnicas.**
Aplicativo desktop (Python + CustomTkinter) que automatiza o processo descrito neste
cofre: criação de fichas no portal PMIB, RPA no portal, geração de planilhas para
fornecedores e gestão por planilhas Excel.

> [!important] Onde esta o código de verdade
> **`https://github.com/luanccozer/SIG-FT`**.
> A pasta `Box/15 - PDM/_python_pdm/SIG-FT/` esta **desatualizada** — tem os
> `*_backend.py` monoliticos de antes da refatoracao. Não use como referência.

## O problema que ele resolve

Sem o SIG-FT, cada ficha exige:
1. escolher um PDM entre ~1174 lendo a descrição do material;
2. criar a ficha no portal, clicando;
3. gerar um Excel específico daquele PDM para mandar ao fornecedor;
4. transcrever o que o fornecedor devolveu para 5 abas diferentes do portal;
5. traduzir tudo para espanhol sem acento;
6. cadastrar dezenas a centenas de aplicações LMR, uma a uma;
7. atualizar planilha de status;
8. consolidar tudo numa visão macro.

Na ordem de milhares de fichas, isso não fecha na mão.

## As três camadas de valor

| Camada | O que faz | Módulos |
|---|---|---|
| **Excel** | ler, gerar e atualizar planilhas | PDM, Gestão PMIB, Buscar Material |
| **IA** | classificar, normalizar, traduzir, validar, preencher | Criar Fichas, Analyzer, AutoSpec, Upload Condições, Upload Specs, Tradutor |
| **RPA** | operar o portal PMIB | Criar Fichas, LMR, Apagar LMR, Upload Condições, Upload Specs, Ficha Duplicada |

Vários módulos usam as três.

## Escala do projeto

| | |
|---|---|
| Código no pacote `sigft/` | ~36.000 linhas |
| Módulos de tela | 13 |
| Testes automatizados | 1.327 (+10 skipped) |
| Fases de refatoracao | 8 |
| Motor de RPA | Playwright |

## Constantes que amarram o app ao processo

Em `sigft/config.py`:

| Constante | Valor | Nota |
|---|---|---|
| `PORTAL_URL` | `https://apps.itaipu.gov.br/PMIB/PMIB_DatasheetList` | só acessivel da rede da empresa |
| `PREFIXO_CONTRATO` | `4500063671` | ver [[Codigo PMIB]] |
| `ABA_LISTA_MATERIAIS` | `Lista de Materiais` | + variantes toleradas |

O layout da ficha Excel vive em `sigft/core/rpa/ficha_layout.py` (`CONFIG_MAP`) — e a
**fonte única** do mapeamento célula-a-campo. Ver [[Anatomia de uma Ficha Tecnica]].

## Quem trabalha nele
- **Luan** (`luanccozer`) — dono do repo, refatoracao geral
- **Rafael** (`rafhagmm`) — módulo AutoSpecAI

O contrato de fronteiras entre as duas frentes está em
`docs/refatoracao/TRABALHO_PARALELO.md`.

## Navegue
[[SIG-FT - Arquitetura]] · [[SIG-FT - Modulos]] · [[SIG-FT - Camada de IA]] ·
[[SIG-FT - Motor de RPA]] · [[SIG-FT - Refatoracao]] · [[SIG-FT - Como Rodar]]
