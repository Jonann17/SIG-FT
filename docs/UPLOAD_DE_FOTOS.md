# Caderno do módulo Upload de Fotos (RPA no PMIB)

> Aberto em 2026-10-30. Implementado no mesmo dia, numa sessão na web, a partir
> das capturas de tela da aba "Documentos e imagens" em edição e do `pmib-mcp`
> (o servidor MCP do PMIB, no Drive do usuário). **Ainda não rodou no portal
> real** -- ver "O que falta" abaixo.

## O que o módulo faz

Tela **4.5. Upload de Fotos** (`sigft/app_qt/views/upload_fotos.py`, regra em
`sigft/services/upload_fotos.py`). Para cada ficha do subsistema:

1. abre a ficha em edição e vai à aba "Documentos e imagens";
2. se já há fotos: **exclui todas** (lixeira + confirmar, uma a uma, conferindo
   que a linha saiu) ou **pergunta** -- excluir e subir / adicionar / pular;
3. sobe as fotos da pasta pelo "Adicionar imagens" (o FilePond já validado na
   ficha duplicada, `duplicadas_imagens.subir_arquivos`) e clica em CONFIRMAR;
4. confere que o NOME de cada arquivo apareceu na tabela de imagens;
5. vê se a ficha tem documento associado;
6. passa para a próxima ficha.

No fim, a coluna `DOCUMENTOS E IMAGENS` do `_STATUS_PMIB`:

| Fotos | Documentos na ficha | Grava |
|---|---|---|
| todas subiram | há | `COMPLETO` (e tira a nota "Faltam documentos" que o SIG-FT tenha posto antes) |
| todas subiram | não há | `INCOMPLETO` + nota de célula **"Faltam documentos"** |
| alguma falhou / ficha pulada | -- | não toca; o motivo vai para o console |

## Decisões

- **Pasta:** uma por subsistema; o NOME do arquivo é `<4 últimos dígitos do
  PMIB><letra>` -- `0071.jpg`, `0071a.jpg`, `0071b.png`. Sobe nessa ordem (sem
  letra primeiro). Fora do padrão, sem ficha na planilha ou com o final em duas
  fichas (contratos diferentes): não sobe, e o console lista.
- **Descrição no portal (PT e ES):** `imagens - 0071`, a que as fichas já
  usam (captura de 2026-10-30); a letra fica no nome do arquivo.
- **Nota de célula:** o editor cirúrgico ganhou `escrever_nota`
  (`core/excel/cirurgico.py`). Só mexe em nota de autor "SIG-FT": nota ou
  comentário em thread de uma pessoa na mesma célula fica como está.
- **Tudo pela tela.** O `pmib-mcp` exclui/lista imagens chamando o servidor
  (`ActionPMIBDataSheetImage_Delete`); o SIG-FT não faz isso -- a Itaipu proíbe
  contato com o banco por fora da tela (regra do Luan, `core/rpa/respostas.py`).
- **Home com 13 cards** (escolha do usuário, 2026-10-30): a Home passa a rolar.

## Portal lento (2026-11-03)

O campo **"Velocidade do portal"** (Normal / Lento / Muito lento) multiplica por
1, 2 ou 4 todas as esperas do robô (`upload_fotos.Esperas`): o tempo do motor
(20 s por clique/campo), abrir a ficha, a aba ativa, o diálogo, o FilePond, o
aviso verde (20 s), a tabela de fotos, a exclusão e a conferência. O padrão é
**Lento**: no caso bom não custa nada, porque cada espera termina assim que a
tela responde. Três esperas eram defeito e viraram espera por condição:
a aba ativa (conferida no instante do clique), o diálogo "Adicionar Imagens"
(2 s fixos; o atraso deixava a descrição em branco) e o aviso verde (8 s).

Fica de fora: `PMIBPortal.pesquisar_e_abrir`, compartilhado por todos os
módulos, ainda tem 4 s fixos depois da pesquisa (o motor mais paciente cobre o
lápis que demora a aparecer).

## O que falta (sessão LOCAL, `docs/OLHAR_O_PORTAL.md`)

Os seletores abaixo saíram das capturas, não do DOM. Conferir numa ficha de
teste com foto e documento:

1. `XPATH_TABELA_DE_IMAGENS` -- a tabela que tem o cabeçalho
   "Pré-visualização" (e `XPATH_TABELA_DE_DOCUMENTOS`, "Arquivos anexados").
   Se o portal estiver em espanhol, os cabeçalhos mudam.
2. A lixeira (`fa-trash`) da linha da imagem e o diálogo de confirmação da
   exclusão: o robô tenta `role=dialog` + CONFIRMAR e depois o CONFIRMAR
   genérico do portal. Se não houver diálogo, ele só espera a linha sumir.
3. A coluna "Nome" da tabela mostra o nome do arquivo exatamente como subiu
   (`0071a.JPG`)? É a conferência do upload.
4. Ficha SEM foto: a tabela de imagens some ou fica vazia? (O robô trata as
   duas como "sem fotos".)

A primeira execução real deve ser numa ficha só, no modo "Perguntar".
