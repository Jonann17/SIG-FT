---
tags: [normativo, lmr, aberto]
documento: Revision Propuesta CMI AplicacionLMR
data: 2026-08-20
status: aceito-por-itaipu
---

# Revisão da Aplicação LMR — Agosto 2026

Arquivo: `Box/15 - PDM/Revision Propuesta CMI AplicacionLMR.pdf`
"Propuesta Pestana Aplicacion LMR / CMI / Silva" — **20/08/2026 15:12**.

E a devolutiva de Itaipu sobre a proposta do CMI para a aba de Aplicação LMR.
**Documento aberto**: define o que ainda vai mudar no template.

## O caso analisado
`PMIB.1226` — uma **BOMBA**. Itaipu analisou a ficha e o Excel de Aplicação LMR.
Na página 7/11 do esquema hidráulico se visualiza a simbologia da bomba.

## Pedidos de Itaipu

### Na ficha do portal (aba Aplicação LMR)
1. **Falta a quantidade de bombas aplicadas** no equipamento descrito.
2. **Adicionar mais linhas a descrição** — *"Describir cada punto de aplicacion"*.
   Ou seja: **uma linha por ponto de aplicação**, não uma linha agregada.

### No Excel "Aplicação LMR"
> Para este caso analizado **la descripcion es correcta**.

3. **Coluna para o código de Emissor do documento principal.**
4. **Colunas para documentação adicional relacionada** — com interesse declarado em
   *"informaciones dimensionales de diseno y diagramas funcionales"*.
5. **Adicionar no cabeçalho do Excel**: o **WORKSTATEMENT** e a **LISTA DE DOCUMENTOS**.
   - `DOCUMENTO LISTA DE DOCUMENTOS: xxxxxxxxxx`
   - `WORKSTATEMENT: xxxxxxxxxx`

## O que já foi absorvido no template

O template `Templates/APLICACAO LMR - SOBRESSALENTES_template.xlsx` **já tem** as
linhas de `LISTA DE DOCUMENTOS` e `WORKSTATEMENT` no cabeçalho da aba
`DOCS DE REFERENCIA` — mas **em branco**. Ou seja: o campo existe, o preenchimento
sistematico ainda não.

Ver [[Secao - Aplicacao LMR]] para a estrutura completa do template.

## O que isso muda no esforço

O pedido 2 — **uma linha por ponto de aplicação** — e o que mais pesa. Ele
multiplica o volume da aba `APLICACAO - LMR`. Para dimensionar: a aba de exemplo do
RTA no template tem **8.557 linhas** de aplicação para **57 fichas**. Uma média de
150 pontos de aplicação por ficha.

O volume de fichas ainda sem Aplicação LMR é grande o bastante para que a mudança de
critério tenha custo real. Os números do momento ficam em
[[Levantamento - Fichas sem Aplicacao LMR]].
Ver [[Diagnostico - Deficiencias]] e [[Panorama Quantitativo]].

## Status — ACEITO

> [!success] Itaipu aceitou o modelo do CMI
> Confirmado pelo Luan em **31/08/2026**. O critério da Aplicação LMR esta **fechado**.
>
> O que isso muda:
> - **cai o risco de retroatividade** — o que já foi feito de LMR não precisa ser refeito
>   por mudança de critério;
> - a LMR deixa de ser tema de negociação e vira **trabalho de execução**;
> - o gargalo agora e **capacidade e priorização**, não definição.
>
> O que resta e levantar os sistemas e executar. Ver
> [[Levantamento - Fichas sem Aplicacao LMR]].

## Relacionados
[[Secao - Aplicacao LMR]] · [[Diagnostico - Riscos]] · [[RDS-PP e KKS]]
