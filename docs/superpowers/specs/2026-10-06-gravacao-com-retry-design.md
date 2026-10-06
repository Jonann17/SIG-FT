# Gestão PMIB: quando a gravação falha, dizer qual arquivo, por quê, e deixar repetir

**Data:** 2026-10-06 · **Frente:** refatoração geral (Luan)
**Origem:** *"Antes de fazer o merge, vamos garantir que ao salvar o arquivo com a situação
atualizada caso der algum erro nos podemos contornar esses erros de salvar os excel. Por
exemplo, identificar qual está travado, deu erro e o motivo. E pedir pra fechar e dar retry
nessa parte."*

**Decisões do Luan (2026-10-06):**
- desenho **"lista antes e depois"**: antes de gravar, UMA lista dos arquivos travados com o
  motivo de cada um (Repetir / Seguir sem eles); durante, nada interrompe; no fim da etapa, UMA
  lista do que não gravou, com o motivo, e "Repetir só estes". A mapeadora continua perguntando
  na hora, agora com o motivo. O mesmo vale para "Aplicar autorizações";
- processo: escrever este documento e implementar direto, com testes.

Escopo: o Gestão PMIB (`services/pmib_manager.py`), o "Aplicar autorizações"
(`services/autorizados.py`) e a tela deles (`app/views/pmib_manager.py`). Os outros módulos
continuam com a janela de um arquivo só (`RetryLockDialog`).

---

## 1. O que acontece hoje

| Situação | Hoje |
|---|---|
| `_STATUS_PMIB` aberto no Excel, na etapa 5 | uma `messagebox` POR ARQUIVO, no meio da etapa. Com 5 abertos, 5 interrupções |
| Qualquer outro erro ao gravar um `_STATUS_PMIB` | `[AVISO] falha ao gravar (TipoDoErro: texto)`: sem dizer o que fazer, sem repetir |
| Mapeadora aberta | "Repetir/Cancelar". **Cancelar aborta tudo**: a situação dos `_STATUS_PMIB` nem é recalculada |
| Mapeadora: disco cheio, Box fora do ar | `[ERRO]` e o processo para, sem pergunta |
| Renomear `_STATUS_PMIB` falha | ` -> Erro ao renomear: ...`, sem `[AVISO]`, sem motivo legível |
| Painel HTML travado | aviso genérico "aberto ou bloqueado" |

E um defeito, achado lendo o código para este desenho:

> ⚠️ **O "Repetir" da mapeadora grava por cima do que a pessoa salvou.** A janela diz "salve
> suas alterações, feche a planilha e clique em Repetir". O `wb.save` do openpyxl grava a
> planilha que foi carregada ANTES — quem segue a instrução perde o que acabou de salvar.
> O `_STATUS_PMIB` tem a versão branda do mesmo problema: o editor cirúrgico relê o arquivo,
> mas reaplica as células pelo NÚMERO DA LINHA calculado antes; se a pessoa inseriu uma linha
> antes de fechar, a situação cai na linha errada.

> ⚠️ **E um segundo, achado nos testes com o Windows simulado:** renomear um `_STATUS_PMIB` aberto
> no Excel com `shutil.move` falhava no rename, COPIAVA para o nome novo e não conseguia apagar o
> antigo — sobravam dois controles vivos. Passa a ser `os.rename` (na mesma pasta, renomear nunca
> precisa copiar), recusando um destino que já existe.

## 2. A regra de ouro: Repetir sempre relê

**Toda repetição refaz a etapa daquele arquivo desde a leitura** — abre de novo, recalcula,
grava. Nunca grava o que ficou na memória da tentativa anterior. Isso conserta o defeito acima
e é o que torna seguro pedir "salve, feche e repita".

Por isso a gravação de cada tentativa é UMA só (`max_attempts=1`): quem repete é o fluxo,
refazendo a etapa, e não o laço de `save_with_retry`.

## 3. O diagnóstico: `core/excel/travas.py`

Só stdlib. `diagnosticar(caminho, erro) -> Diagnostico` diz o motivo, o que fazer e se Repetir
adianta. `conferir(caminho)` é a conferência de antes: abre o arquivo para escrita e fecha **sem
escrever nada** (nenhum byte, nenhuma data de modificação; o Box não tem o que versionar) e
devolve `None` (livre) ou o diagnóstico.

| Motivo | Como se reconhece | O que fazer | Repetir adianta |
|---|---|---|---|
| está aberto no Excel (por Fulano) | `PermissionError` e o `~$nome.xlsx` do Excel ao lado | salvar o que for seu e fechar no Excel | sim |
| está como somente leitura | `PermissionError` e sem permissão de escrita | desmarcar "Somente leitura"; conferir permissão/cadeado no Box | sim |
| está em uso por outro programa | `PermissionError` sem os dois sinais acima | Excel de outra pessoa, sincronização do Box, antivírus: esperar e fechar | sim |
| não está mais na pasta | `FileNotFoundError`, pasta acessível | conferir a pasta | não |
| a pasta não está acessível | `FileNotFoundError` com a pasta sumida; erros de rede e de nuvem do Windows | conferir o Box Drive e a rede | sim |
| já existe um arquivo com o nome novo | `FileExistsError` (renomeação) | ver qual é o vivo, mover o outro para OBSOLETO | não |
| o disco está cheio | `ENOSPC`, `ERROR_DISK_FULL` | liberar espaço | sim |
| não é um .xlsx válido | `BadZipFile`, XML ilegível | abrir no Excel e salvar, ou restaurar a versão anterior no Box | não |
| fora do padrão (aba sumiu, célula-mestra de fórmula) | `KeyError`, `NotImplementedError`, `ValueError` do editor | corrigir o arquivo | não |
| erro inesperado (Tipo: texto) | o resto | guardar a linha do log se voltar | sim |

O `~$` sozinho não prova nada: sobra um quando o Excel fecha à força. Por isso ele só dá NOME ao
motivo de um `PermissionError` que de fato aconteceu; um `~$` órfão com o arquivo livre não
acusa travamento.

## 4. O desenho

### 4.1 Lista antes (Gestão PMIB e Aplicar autorizações)

Logo depois de listar os `_STATUS_PMIB` vivos (e antes da renomeação, que também é escrita),
`conferir` cada um, e a mapeadora no Gestão PMIB. Havendo travados, UMA janela:

- cada arquivo com o motivo e o que fazer;
- **Repetir**: confere de novo só os travados; os que ainda estiverem voltam na mesma janela;
- **Seguir sem eles** (ou o "X"): o processo roda. Um `_STATUS_PMIB` pulado é LIDO (contagem,
  revisão em uso, link) e o cálculo roda nele, mas ele não é renomeado nem gravado nesta
  rodada; entra no resumo do fim **só se tinha o que gravar** (pular um arquivo que já estava
  em dia não perdeu nada). Mapeadora pulada: as
  etapas 4, 6, Lista de preços e Atividades não rodam, e as renomeações também ficam para a
  próxima rodada — renomear sem gravar a mapeadora quebraria o link "Abrir Box".

### 4.2 Durante: nada interrompe

Cada falha vira linha NEUTRA no log (` -> nome: não gravado agora (motivo)...`) e entra na
lista do fim. `[AVISO]` só no fim, para o que de fato ficou para trás: uma falha resolvida
pelo Repetir não pode terminar a rodada em "Concluído com avisos".

### 4.3 Lista do fim da etapa

Terminada a etapa 5 (ou a aplicação das autorizações), UMA janela com os que falharam e para os
quais Repetir adianta:

- **Repetir só estes**: refaz cada um desde a leitura (§2); os que falharem de novo voltam;
- **Seguir** (ou o "X"): ficam para a próxima rodada.

Os que Repetir não resolve (sumiu, corrompido, fora do padrão) não entram na janela — vão para
o resumo do fim com o que fazer.

### 4.4 Mapeadora: pergunta na hora

A mapeadora é gravada quatro vezes (metadados, link e situação, Lista de preços, Atividades).
Falhou uma: janela na hora, com o motivo.

- **Repetir**: roda a etapa de novo, relendo a planilha (§2) — o que a pessoa salvou fica;
- **Seguir sem ela**: deixa de abortar. Os `_STATUS_PMIB` continuam sendo gravados (é o
  trabalho de todo dia) e as gravações seguintes da mapeadora são puladas sem perguntar de novo.

Erros que não são de arquivo (aba de sobressalentes não encontrada, coluna faltando) continuam
`[ERRO]` como hoje.

### 4.5 O resumo do fim

```
[AVISO] Não gravados nesta rodada (2):
   - #ST00=...&MPB020_STATUS_PMIB.xlsx: situação e dias de atraso não gravados. Motivo: está aberto no Excel por Luan. Salve o que for seu e feche o arquivo no Excel. Depois, rode de novo.
   - Planilha de mapeamento (mapeadora.xlsx): não gravada: link, situação no PMIB, revisão em uso, metadados, Lista de preços e Atividades ficaram como estavam. Motivo: está em uso por outro programa. (...)
```

(o `(...)` final é o "o que fazer" do motivo, cortado aqui só por largura).

A janela final da tela diz quantos ficaram e manda ao fim do log.

### 4.6 Painel e renomeação

Painel travado: o motivo do diagnóstico no aviso. Renomeação que falha: motivo + o que fazer, e
entra no resumo do fim ("não renomeado para ...").

## 5. Interfaces

- `PMIBManager.executar_fluxo(..., callback_confirm=None, callback_travados=None, hoje=None)` e
  `autorizados.executar(..., callback_travados=None)`. `callback_travados(falhas, momento) ->
  bool`: `True` = Repetir, `False` = Seguir. `momento` é `travas.ANTES`, `travas.DEPOIS` ou
  `travas.NA_HORA`; `falhas` é uma lista de `travas.Falha` (caminho, diagnóstico, rótulo,
  consequência). O `callback_retry_lock` destes dois fluxos sai: ninguém mais o chama.
- Sem callback (testes, chamada sem tela): nada pergunta; segue sem os travados e o resumo diz.
- Tela: `ArquivosTravadosDialog` em `app/widgets/dialogs.py` (lista rolável, dois botões, "X" =
  Seguir, sem `grab_set`, sem `transient`, como os outros diálogos de espera) e
  `perguntar_arquivos_travados` no mixin `DialogosDeEspera`, que a tela do Gestão PMIB passa a
  usar.

## 6. Fora do escopo (vai para `PENDENCIAS.md`)

- **Gravação interrompida no meio.** O editor cirúrgico grava por cima (`r+b`, para o Box
  guardar versão) e o `wb.save` do openpyxl trunca antes de escrever: disco cheio no meio da
  escrita deixa o arquivo pela metade. O Box guarda a versão anterior; o motivo aparece como
  "não é um .xlsx válido", com a instrução de restaurar.
- Os outros módulos continuam com a janela de um arquivo só.

## 7. Como se prova

- `tests/test_travas.py`: cada linha da tabela do §3; o `~$` do Excel lido (com e sem nome
  legível, órfão); `conferir` num arquivo de verdade; os laços de antes e do fim (Repetir até
  liberar, Seguir, sem callback, só os que Repetir resolve vão para a janela).
- Gestão PMIB sobre o kit do cofre (validador do kit diz KIT OK ao fim de cada cenário):
  travado antes → Repetir → gravado; travado antes → Seguir → arquivo intocado byte a byte,
  lido na contagem, no resumo; trava durante a etapa 5 → lista do fim → Repetir só estes →
  gravado; mapeadora travada na hora → Repetir **preserva o que a pessoa salvou antes de
  fechar** (o defeito do §1); mapeadora → Seguir sem ela → `_STATUS_PMIB` gravados, mapeadora
  intocada.
- Aplicar autorizações: os mesmos cenários de antes e do fim.
- Diálogo: os três caminhos de saída soltam o worker ("X" incluído).
- Tela de verdade sob Xvfb com travas simuladas: as duas janelas aparecem com o motivo, e a
  janela final conta os não gravados.

**A validar na máquina do Luan** (não há Excel nem Box no contêiner): abrir um `_STATUS_PMIB`
no Excel e rodar; conferir que a lista de antes o nomeia, que Repetir depois de fechar grava, e
que a conferência não cria versão nova no Box para os arquivos que não mudaram.
