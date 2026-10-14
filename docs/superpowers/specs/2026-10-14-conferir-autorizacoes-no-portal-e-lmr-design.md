# Conferir autorizações no portal e Aplicação LMR pela resposta do servidor

**Data:** 2026-10-14 · **Pedido:** Luan · **Base:** `docs/PMIB_ENGENHARIA_REVERSA.md` (R1, R6, R8)

> Registro das decisões. O brainstorming chegou à primeira parte do design; o Luan pediu
> então para implementar, commitar e fazer o merge ("Pode implementar... Faça o commit no
> github e o merge"). Por isso este documento foi escrito junto com o código, e não antes
> dele, para aprovação.

## 1. O que o Luan pediu, nas palavras dele

- "O mais importante é criar essas melhorias, de verificar quais foram autorizados."
- "Faça a melhoria do RPA para aplicação LMR, que você disse que ficaria mais rápido."
- "Meu interesse é o RPA, porque a Itaipu proíbe contato com o banco de dados deles, e não
  podemos violar isso de nenhuma forma."
- Depois, numa entrega própria: "verificar o status real de cada ficha, mas em vez de
  verificar para todos, checar apenas daquele sistema". Para ele, CONDIÇÕES só é
  COMPLETO com tudo preenchido, mesmo que o portal aceite menos.

## 2. Decisões

| Decisão | Quem | Por quê |
|---|---|---|
| Só RPA: o robô navega e clica como uma pessoa; lê a resposta que o navegador **já recebeu**. Nada de chamar endpoint por fora da tela, nada de banco. | Luan | Proibição da Itaipu. A leitura da resposta (A) foi escolhida no lugar da leitura do texto da tela (B), que quebra com idioma e layout. |
| "Autorizado" = ter o **código SAP de recebimento** (`StockCodeSAP` numa solicitação de codificação não cancelada). | Luan + dado | Correção do Luan: a aprovação da ficha é outra etapa e não cria o código. O critério é o mesmo da consulta da Itaipu, que vem na aba "SQL" do próprio export de autorizados. |
| Confere **todas** as fichas FÍSICA E DOCUMENTAL sem AUTORIZADO. | Luan | Sem atalho por status: o código nasce na autorização de entrega, que não depende da aprovação. Eram 296 fichas em 14/10. |
| Data da autorização = o **dia da conferência**, pela regra de dias de atraso que já existe. | Luan | "Não precisamos nos importar muito." O portal não mostra a data. Quando a Itaipu liberar os relatórios, troca-se a fonte. |
| Gatilho: **botão próprio** ("CONFERIR NO PORTAL"), no bloco das autorizações do Gestão PMIB. | Luan | — |
| O export da Itaipu continua aceito; as duas fontes gravam pela **mesma** função (`autorizados.aplicar`). | design | Uma implementação por conceito. AUTORIZADO é fato, venha de onde vier. |
| LMR: confirmar pela resposta do servidor; esperar a tag sair do campo; **voltar ao fluxo de 2026-09-28** quando a resposta não vem. | design | Ganho de até 15 s por código sem perder o fluxo calibrado no portal. |

## 3. Como ficou

- **Base (R1).** `RPAEngine.capturar_respostas(trecho_url, acao, quantas, ate, timeout_s)`
  e `captura_respostas_disponivel`. No Playwright, um ouvinte do evento `response`; o tempo
  é contado em tentativas (regra 7 do `PORTAL_COMO_ELE_SE_COMPORTA.md`).
  `core/rpa/respostas.py` interpreta as respostas pelo nome dos campos: Id da ficha na
  lista, código SAP no cabeçalho, resultado de uma gravação.
- **Conferência (R6, parte da autorização).** `services/autorizacao_portal.py`:
  1. lê os `_STATUS_PMIB`;
  2. abre a lista (se ela não responde, para: é login);
  3. pesquisa cada ficha, porque a pesquisa recarrega as sete abas e a da ficha traz o Id;
  4. abre cada ficha pelo link direto e lê a codificação;
  5. grava pelo `autorizados.aplicar`.

  Três fichas seguidas sem resposta param a conferência. Tela: `views/pmib_manager.py`
  (navegador → pausa para o login → conferência → navegador fecha no `finally`).
- **LMR (R8).** `services/lmr.py`:
  - `_confirmar_pela_resposta`: Id da aplicação = gravou; `exception` = recusa, com o
    motivo do servidor; sem resposta = mensagem na tela e volta ao modo antigo.
  - `_esperar_tag_sair_do_campo`: o campo esvaziar substitui a segunda pausa de 0,5 s.

## 4. Como provar

`scripts/check.sh` verde não é prova de portal: os testes usam um portal de mentira escrito
a partir do código das telas. A prova é a etapa **5.4** de `docs/ROTEIRO_DE_TESTE.md`:

- **Conferência:** os PMIBs do último export de autorizados saem com o mesmo código SAP.
- **LMR:** cada código loga "Portal confirmou: aplicação LMR gravada (id ...)". Medir o
  tempo da ficha.

Pendências abertas em `docs/refatoracao/PENDENCIAS.md` (2026-10-14).

## 5. Fora desta entrega

- O **status real das fichas de um sistema** (STATUS e colunas de seção pelo portal), que é
  a próxima entrega, com o mesmo leitor de respostas.
- **R3:** os seletores da LMR com prefixo de posição.
- **R5:** sentinela de versão do portal.
- **Cache do Id** de cada ficha entre conferências: só depois de medir a primeira.
