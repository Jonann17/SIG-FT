---
tags: [processo, ficha, secao]
---

# Seção — Informações Gerais

Primeira seção da ficha. No portal engloba **Informações Gerais** e
**Fabricantes e Fornecedores**.

## Campos (template R3, linhas 4-12)

| Campo | Célula | Valores |
|---|---|---|
| **Texto Breve do Material** | H6 | texto. Segue [[Anexo I - Classificacao de Materiais Sobressalentes\|nome básico + nome modificador]], maiusculas, sem acento, sem C-cedilha nem N-til |
| **Origem** | Q6/T6 | Brasil ou Paraguai / Outros — corresponde a **Procedencia** (Nacional / Importado) do Anexo I item 1.1.8 |
| **Un. medida de estoque** | C8 | unidade SI |
| **Tipo de Fabricacao** | G10/G12 | **Série** ou **Especial**. Anexo I 1.1.4: especificar se o material tem fabricacao específica para a IB |
| **Fabricante** | I10 | nome |
| **Tipo** | T10/T12 | **Reparavel** ou **Não reparavel** |
| **Vida útil** (caso perecivel) | I12 | Anexo I 1.1.3-d: perecibilidade |

## Fabricantes e Fornecedores

Do [[Anexo I - Classificacao de Materiais Sobressalentes]] itens 2.4-2.6:

- **CR — Código de Referência**: o part number do fabricante. Transcricao deve
  **obedecer rigorosamente a forma grafica original**. Até 100 posições.
- **CF — Código de Fornecedor**: identifica o fabricante/fornecedor. **Complemento
  obrigatório** do CR.
- CRs diferentes para o mesmo item significam **equivalencia** entre fabricantes.
- Principio: vincular o CR **ao fabricante**, não ao fornecedor. Vincular a fornecedor
  só em situação excepcional.

> [!tip] Vários fornecedores
> Quando o CMI compra uma solução de um sub-fornecedor, **cada fornecedor e sua
> referência devem constar**. Ver [[Procedimento de Fichas Duplicadas]] item 2.2.

## No caso de ficha duplicada
A Informação Geral da duplicada recebe adicionalmente:
- código de projeto da lista de sobressalentes correspondente (documento, subsistema, sistema)
- código **RDS-PP** do documento da lista
- o **evento de pagamento** associado

E a referência do fabricante ganha o sufixo `D1`, `D2`, ...
Ver [[Fichas Duplicadas]].

## Coluna de controle
No [[Planilha STATUS_PMIB]]: coluna **`INFO. GERAIS`** (COMPLETO / INCOMPLETO / N/A).

## Automação
Módulo **Criar Fichas** do SIG-FT preenche PDM, Contrato, Código Projeto, Descrição
Breve, Origem, Tipo, Unidade e Fabricacao no portal, classificando com IA a partir da
descrição da lista. Ver [[SIG-FT - Modulos]].

## Relacionados
[[Anatomia de uma Ficha Tecnica]] · [[Secao - Caracteristicas Tecnicas]]
