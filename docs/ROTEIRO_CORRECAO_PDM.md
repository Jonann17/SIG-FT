# Roteiro de validação — Correção de PDM (etapa E6)

Este roteiro existe porque **nada do módulo de correção de PDM jamais rodou
contra o portal PMIB real**. As cinco primeiras etapas (E1 a E5) fecharam com
4195 testes verdes, e isso prova a lógica — não prova o portal.

> ⚠️ **`scripts/check.sh` verde não é prova de portal.** Os testes rodam contra
> dublês escritos pelo próprio Claude: eles provam a ideia dele do portal, não
> o portal. Se um seletor estiver errado, tudo passa verde e nada funciona.

E este módulo é **destrutivo por natureza**: trocar o PDM faz o portal apagar
todas as características técnicas. É a única operação do app em que um erro
não deixa a ficha do jeito que estava.

Tempo estimado: **40 a 50 minutos.**

---

## Antes de tudo: leia isto

1. **Use uma ficha de teste descartável.** Não uma das 25 fichas reais. Se não
   tiver uma, crie pelo módulo "Cria Fichas PMIB" e preencha umas cinco
   características à mão — é com elas que o teste vai brincar.
2. **Sessão LOCAL**, com o navegador. A sessão do Claude na web não alcança o
   portal (ver `docs/OLHAR_O_PORTAL.md`).
3. **Abra o app antes.** `python frontend.py` e olhe a janela preta. A tela nova
   nunca foi aberta em lugar nenhum — o ambiente do Claude na web não tem
   `tkinter` nem `customtkinter`, então `--smoke` não rodou lá.

---

## Etapa 0 — O app abre, e a tela existe (2 min)

```bash
python frontend.py --smoke
```

Tem de sair sem erro. Depois:

```bash
python frontend.py
```

| Confira | Esperado |
|---|---|
| Barra lateral | aparece **"5.1. Correção de PDM"**, entre "5. Upload duplicadas" e "7. Aplicação LMR" |
| Clicar nele | abre a tela, sem erro no console |
| Tela inicial | dois botões de arquivo, três de ação em massa, a tabela vazia, dois interruptores e "INICIAR CORREÇÃO" |
| Card na Home | "Correção de PDM" aparece, e clicar nele leva à mesma tela |

**Se der `NameError` ou `TypeError` aqui, pare.** É defeito de montagem da
tela, e as etapas seguintes não vão dizer nada de útil.

---

## Etapa 1 — A planilha e o catálogo (5 min, sem portal)

1. **"Selecionar _STATUS_PMIB"** → escolha a sua planilha de status.
2. A etiqueta ao lado tem de dizer **"N ficha(s)"**, e a tabela tem de encher
   com uma linha por ficha: código, descrição e o PDM que ela usa hoje.

| Se aparecer | O que é |
|---|---|
| "0 ficha(s)" | a aba não é a "Lista de Materiais", ou falta a coluna `CÓDIGO PMIB`. O console diz qual das duas |
| Coluna "PDM atual" vazia | falta a coluna `PDM usado` na planilha. Não impede nada: dá para escolher o PDM novo à mão |

3. **"Planilha de PDMs (opcional)"** → escolha o `PDMs_SAM-GM`. A etiqueta tem
   de dizer **"N PDMs"**.

⚠️ **Sem o catálogo, o botão "Escolher PDM..." não funciona** (ele avisa) — mas
"Só atualizar a revisão" funciona sem ele.

---

## Etapa 2 — As ações em massa (5 min, sem portal)

Ainda sem tocar o portal. Aqui se confere que a tela diz a verdade sobre o que
vai fazer.

1. Selecione **duas ou três** linhas e clique **"Só atualizar a revisão"**.

| Confira | Esperado |
|---|---|
| Coluna "PDM novo" | recebeu **só o código** (`PDM.5920.020`), sem o nome e sem a revisão |
| Coluna "Prévia" | diz *"so a revisao: o portal atribui a vigente"* |
| Console | *"Só atualizar a revisão: N ficha(s)"* |

> 🎯 **A prévia NÃO dá um número aqui, e isso é de propósito.** O catálogo só
> tem a revisão vigente de cada PDM; comparar catálogo com catálogo daria 100%
> sempre, e o que a ficha tem é a revisão *antiga*. Prévia que mente é pior que
> prévia ausente.

2. Clique **"Limpar"** nas mesmas linhas — a coluna "PDM novo" tem de esvaziar.

3. Com o catálogo carregado, selecione **uma** linha e use **"Escolher PDM..."**.
   Busque por um PDM de **código diferente** do atual.

| Confira | Esperado |
|---|---|
| Coluna "PDM novo" | recebeu o texto completo (`PDM.4320.031 - COLUNA FLANGE, ACOPLAMENTO`) |
| Coluna "Prévia" | diz *"N de M caracteristicas casam"* |

4. **Sem nenhuma linha selecionada**, clique "Limpar". Tem de limpar **todas** —
   sem seleção, a ação vale para a planilha inteira.

---

## Etapa 3 — A ficha que JÁ está certa (5 min, portal)

**Este é o teste mais importante da lista**, e o mais fácil de esquecer.

Pegue a sua ficha de teste e confira no portal em que revisão ela está. Se ela
já estiver na revisão **vigente**, deixe-a assim.

1. Na tela: só ela selecionada, **"Só atualizar a revisão"**, "INICIAR CORREÇÃO".
2. Confirme o aviso.

| Confira | Esperado |
|---|---|
| Console | *"PDM ja e o vigente: ... Nao troquei nada"* |
| Console | *"nada a fazer, o PDM ja e o vigente"* |
| **A ficha no portal** | **as características continuam lá, todas** |

🚨 **Se as características sumirem nesta etapa, PARE E ME AVISE.** Quer dizer
que o módulo está trocando o PDM de fichas que já estavam certas — e numa
rodada de 25 fichas isso apagaria as que não precisavam de nada.

---

## Etapa 4 — Atualizar a revisão de verdade (10 min, portal)

Agora uma ficha que está numa revisão **antiga**. Antes de começar:

📸 **Tire um print da tabela de características técnicas dela**, com valores à
vista. É o seu gabarito.

1. Só ela selecionada → **"Só atualizar a revisão"** → **"INICIAR CORREÇÃO"**.
2. Acompanhe o console.

| Momento | O que tem de aparecer |
|---|---|
| Antes de trocar | *"N caracteristica(s) na tela, M com valor"* |
| Antes de trocar | *"retrato em C:\\Users\\...\\Documentos\\SIG-FT\\retratos_pdm\\....json"* |
| Na troca | *"Confirmei a troca de PDM"* |
| Depois | *"PDM trocado e confirmado: ... R2"* |
| Casamento | *"Reposicao: X direta(s), Y com conversao de tipo."* |
| Fim | a lista do que não voltou, e a das que ficaram em branco |

3. **Abra a ficha no portal e compare com o print.**

| Confira | Por quê |
|---|---|
| Os valores voltaram, iguais | é o ponto do módulo inteiro |
| O **espanhol** voltou também | a ficha é bilíngue; metade dela vazia é meia ficha |
| As **unidades** estão certas | unidade errada é o defeito que mais passa batido: o número aparece certo e só a coluna de unidade denuncia |
| Os **intervalos** (mínimo, máximo e o "ENTRE") | são três campos, e o subtipo é o que dá sentido aos outros dois |
| As linhas que sobraram (do PDM novo, sem valor) | **sumiram**, se o interruptor estava ligado |
| O que o console listou como "nao voltou" | está mesmo vazio na ficha, e o valor listado bate com o print |

4. **Abra o arquivo do retrato** (o caminho está no console). É um JSON legível:
   confira que ele tem o que a ficha tinha antes, em português e espanhol.

---

## Etapa 5 — Trocar o PDM por outro (10 min, portal)

Mesma ficha (ou outra de teste). Agora **"Escolher PDM..."** com um PDM de
código diferente.

> ⚠️ Aqui o módulo **não devolve tudo** — medido, 30 a 50%. O que ele garante é
> que nada do reaproveitável se perde e que o resto sai em lista explícita.

| Confira | Esperado |
|---|---|
| Console | a lista *"Nao voltaram para a ficha"*, com o valor de cada uma entre aspas |
| Ficha no portal | as características que os dois PDMs têm em comum estão preenchidas |
| Conversão de tipo | se alguma linha mudou de `NUM` para `CHAR`, o valor tem de estar lá como texto **com a unidade junto** (ex.: `220 V`), e a unidade da linha em `AD` |

---

## Etapa 6 — As recusas (5 min, portal)

São os freios. Cada um existe para impedir que uma ficha fique **pior** do que
estava.

### 6.1 — O interruptor de apagar

Rode uma ficha com **"Apagar as que ficarem em branco" DESLIGADO**.

| Confira | Esperado |
|---|---|
| Console | continua listando as que ficaram em branco |
| Ficha no portal | as linhas em branco **continuam lá** |

### 6.2 — A pausa de conferência

Ligue **"Conferir cada ficha antes de salvar"** e rode uma ficha.

| Confira | Esperado |
|---|---|
| A janela de espera | aparece antes do salvamento, citando o PMIB |
| Enquanto ela está aberta | dá para olhar a ficha no portal, na outra janela |

### 6.3 — O botão "Parar"

Com duas ou três fichas no lote, clique **"Parar"** durante a primeira.

| Confira | Esperado |
|---|---|
| Console | *"Parada pedida pelo usuario. O que ja foi corrigido esta salvo"* |
| Portal | a ficha que estava rodando terminou; as seguintes não foram tocadas |

---

## Etapa 7 — O modo "só repor" (5 min, portal)

É a rede: se algo der errado **depois** da troca, a reposição roda de novo a
partir do arquivo, sem refazer nada no portal.

Hoje ele existe no serviço (`correcao_pdm.repor_do_retrato`) mas **ainda não
tem botão na tela**. Para testar, no Python:

```python
from sigft.services import correcao_pdm as svc

automacao = svc.AutomacaoCorrecaoPDM()
automacao.iniciar()
automacao.abrir_portal("https://apps.itaipu.gov.br/PMIB/PMIB_DatasheetList")
input("faça login e aperte ENTER...")

print(svc.repor_do_retrato(automacao.portal, "4500063671.0242",
                           callback_log=print))
```

| Confira | Esperado |
|---|---|
| Console | *"repondo a partir de ...json (N caracteristica(s) no retrato)"* |
| Portal | **o PDM NÃO mudou** — ele já estava certo |
| Portal | os valores foram reescritos |

> Se isto funcionar bem, vale um botão na tela. Me diga.

---

## Etapa 8 — O que me mandar

Copie e preencha:

| Etapa | Passou? | O que aconteceu |
|---|---|---|
| 0 — app abre, tela existe | | |
| 1 — planilha e catálogo | | |
| 2 — ações em massa | | |
| 3 — **ficha que já está certa** | | |
| 4 — atualizar a revisão | | |
| 5 — trocar o PDM | | |
| 6 — as recusas | | |
| 7 — só repor | | |

Quando algo falhar, o que mais ajuda:

1. **a mensagem exata** do console — copie o texto, não descreva;
2. **o arquivo do retrato** daquela ficha (`Documentos\SIG-FT\retratos_pdm\`);
3. um **print da ficha no portal** no momento do erro;
4. se der para copiar, o **HTML da linha** que não funcionou (botão direito →
   Inspecionar → a linha `<tr>` inteira). É o que resolve seletor errado numa
   rodada em vez de três.

---

## Se der errado no meio de uma ficha

**O original está no retrato.** `Documentos\SIG-FT\retratos_pdm\`, um JSON por
tentativa, o mais novo por último no nome. Ele tem tudo o que a ficha tinha
antes da troca, nos dois idiomas — dá para repor à mão ou pela Etapa 7.

Nenhuma ficha é tocada antes de o retrato estar gravado em disco: se a gravação
falhar, o módulo **não troca o PDM** e diz por quê.
