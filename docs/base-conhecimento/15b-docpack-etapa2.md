# DocPack · Etapa 2 — o conteúdo do dossiê

A Etapa 1 (`15-docpack.md`) cria a pasta da lista com os templates vazios. A Etapa 2 preenche a
lista de materiais do `_STATUS_PMIB` a partir do PDF da lista. Ela é feita pelo AMP.

> **2026-11-05:** a lista com preço saiu desta etapa (pedido do Jonathan: o agente não olha para
> ela). Quem a cria e a preenche a partir do `_STATUS_PMIB` é o módulo **Lista de Preços**
> (`16-lista-de-precos.md`).

| Onde | O quê |
|---|---|
| `sigft/services/docpack_etapa2.py` | a varredura, o download, o pedido, a leitura do HTML e a gravação (sem Qt) |
| `sigft/app_qt/views/docpack_etapa2.py` | `ModuloDocPackEtapa2(ModuleFrame)`, que também funciona embutida (`embutida=True`, `progresso_externo=`) |
| `amp/criacao_status_pmib/` | o workflow e o agente **reusados** (do Luan): "Spare Parts Control Sheet Builder" |

## O fluxo

1. **Procurar dossiês vazios.**
   - Os `_STATUS_PMIB` vivos da raiz (`status_pmib_arquivos.listar`) cuja aba "Lista de Materiais" não tem material.
   - Os que já têm material ficam fora, e a contagem vai para o log.
2. **Consultar no AMP.** Nada é escrito nas planilhas nesta etapa. Para cada lista marcada:
   - O PDF da revisão vigente:
     - vem do Aconex (perfil do DocManager, `perfil_do_aconex`), pela rotina da Conferência de Revisões (`conferencia_revisoes._gravar`), que nunca sobrescreve;
     - sem Aconex, usa o `<código>[<rev>].pdf` mais novo da pasta.
   - O `ping` do workflow vem antes. Se falhar, nada é mandado.
   - O workflow recebe:
     - `modo=criar`;
     - a mensagem do LEIA-ME dele;
     - `lista`, que é o PDF;
     - `template`, que é o `_STATUS_PMIB` em branco do próprio dossiê.
   - O HTML que o agente devolve fica na pasta como `<código>[<rev>] criacao AMP.html`, sem sobrescrever (`revisao_amp.gravar_html`).
3. **Gravar nas planilhas.** Mostra o resumo (quantos materiais por lista, e os primeiros) e só grava com o "sim".
   - Antes de escrever, cada planilha é conferida de novo para ver se continua vazia.
   - A gravação é no XML (`core/excel/cirurgico.py`): o resto do pacote sai byte a byte.

## Uma implementação por conceito

- **Workflow da criação.** O `_STATUS_PMIB` de uma lista nova é o que o workflow da Criação do `_STATUS_PMIB` já faz. A Etapa 2 o chama e não tem workflow nem agente próprios.
- **Webhook.** Desde 2026-11-05 fica no **Configurar IA** do DocPack, entrada "Etapa 2: Conteúdo" (só Workflow AMP; a aba mostra só se está configurado), com os nomes `AMP_CRIACAO_STATUS_PMIB_URL` e `AMP_CRIACAO_STATUS_PMIB_CHAVE`.
- **Peças reusadas da Revisão no AMP:**
  - o cliente (`core/amp/cliente.py`);
  - o batimento da espera;
  - a gravação sem sobrescrever;
  - o teste de conexão.

## Regras

- **Leitura do HTML.** A tabela do controle é a que tem ITEM e DESCRIÇÃO no cabeçalho (`ler_tabela`, com `html.parser`). A coluna da página fica de fora porque não tem nome do template.
- **Colunas escritas.** Só as que vêm da lista (`COLUNAS_STATUS`):
  - ITEM, QTD., UNID., DESCRIÇÃO;
  - CÓDIGO DO MATERIAL, CÓDIGO CMI, MARCA/MODELO;
  - TIPO DE ENTREGA.

  As colunas de andamento da equipe e as fórmulas do template não são tocadas.
- **ITEM é rótulo, não quantidade** (2026-11-09). Só o número inteiro vira número; o resto fica
  como está na lista (`3.10`, `3.4`). Antes, `"3.10"` virava 3,1, que é outro item.
- **Listas com duas partes** (2026-11-09, pedido do Luan). Algumas listas trazem à esquerda os
  SOBRESSALENTES CONTRATUAIS (o que a ET pediu) e à direita os SOBRESSALENTES FORNECIDOS (o que se
  entrega). Só o fornecido vira material; o ITEM de cada linha fornecida é o do item contratual
  ao lado dela, e a quantidade é a da direita. A regra é do agente, no AMP
  (`amp/criacao_status_pmib/agente.md`, seção "Listas com duas partes"): o SIG-FT só lê a tabela.
- **Abrir Pasta** (2026-11-09). Cada dossiê da tabela tem o botão da Conferência de Revisões
  (`dialogos_selecao.botao_de_pasta`), que abre a pasta do PDF, do `_STATUS_PMIB` e do HTML do AMP.
- **Preço nunca se inventa.** Uma coluna com cara de preço na tabela do agente é ignorada, com aviso, e o VALOR UNITÁRIO fica vazio.
- **Planilha já preenchida.** Se o `_STATUS_PMIB` já tem material, a gravação é recusada.
- **Não lê a mapeadora.** Desde 2026-11-09 a Etapa 1 não oferece a lista que ainda não saiu no
  Aconex (`15-docpack.md`), mas a Etapa 2 varre os `_STATUS_PMIB` vazios da raiz: um dossiê de
  lista não emitida, criado antes disso ou à mão, entra no Consultar, que baixaria a versão
  corrente dela. Apague esses dossiês antes (PENDENCIAS 2026-11-09).
- **Cabeçalho.** É achado pelo texto, nas 15 primeiras linhas (o do `_STATUS_PMIB` está na linha 5).

## O que não foi provado aqui

O Aconex e o AMP de verdade não foram testados: os testes usam dublês. Também não foi testado o
HTML real do agente nem a abertura dos arquivos gravados no Excel (Windows).

A tela é a aba **Etapa 2: Conteúdo** do módulo DocPack (`views/docpack_secao.py`, item 8.2 do menu), ao lado da Etapa 1.
