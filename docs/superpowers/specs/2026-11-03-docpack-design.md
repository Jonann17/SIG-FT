# DocPack (2026-11-03)

Pedido do Jonathan: criar as pastas, com todos os templates, das listas de
sobressalentes que ainda não têm `_STATUS_PMIB`. Descrição do comportamento em
`docs/base-conhecimento/15-docpack.md`.

## Decisões

1. **Onde**: 4ª aba do PMIB Manager (`views/gestao_sobressalentes.py`), embutida, com o
   console e a barra da seção. A Home continua com 12 cartões.
2. **Quais listas**: as da mapeadora sem LINK DA PLANILHA e sem `_STATUS_PMIB` vivo
   pelo código. A regra do título é só "sem PREÇO": `e_lista_de_sobressalentes` pede
   SOBRESSALENTES no título porque escolhe o que ENTRA na mapeadora; aqui a lista já
   está nela, e o título pode vir vazio.
3. **Uma leitura da mapeadora só**: `conferencia_revisoes.ler_mapeadora` ganhou as
   colunas opcionais (CMI, descrição, ET, capítulo, eventos), com padrão vazio. O
   cabeçalho dos eventos tem quebra de linha: a comparação junta os espaços.
4. **Destino**: `<raiz>/<capítulo>/[<sistema>/]<pasta final>`. A pasta final é o
   SUBSISTEMA (vai no A3 do `_STATUS_PMIB` e no SUBSISTEMA da Aplicação LMR). O
   capítulo é uma pasta de primeiro nível da raiz (o vocabulário das pastas, EBOP/MBOP,
   não é o da mapeadora; por isso a pessoa escolhe, ou a IA sugere vendo as pastas).
5. **IA**: tarefa `docpack_pasta` (zona compartilhada, commit isolado), Gemini 3 Flash,
   uma retentativa. Recebe código, título, ET, capítulo e as pastas de dois níveis;
   devolve `{capitulo, sistema, pasta, motivo}`. Só preenche os campos.
6. **Arquivos**: cópia byte a byte (`open(..., "xb")`, nunca sobrescreve) e edição pelo
   `cirurgico`. `_STATUS_PMIB`: A3 no formato do template
   (`ET / CAPÍTULO / SUBSISTEMA | CÓDIGO / CMI | EVENTOS`, o vazio sai), A4 a linha da
   revisão em uso (senão a última emitida) com a data de hoje, lida de volta por
   `status_pmib_arquivos.revisao_do_texto`. Lista com preço: `<código PB021>.xlsm`, Capa
   F37 e E27. Aplicação LMR: `LMR/Aplicação LMR - <pasta>.xlsx`, valores à direita dos
   rótulos da aba DOCS DE REFERENCIA (comparados sem acento; rótulo que falta é aviso).
7. **Prévia e confirmação**: "Pré-visualizar" só escreve o plano; "Criar" escreve o
   plano e pergunta Sim/Não antes de tocar no disco.
8. **Fora do escopo** (futuro, com o workflow do AMP): baixar a última revisão e
   preencher o `_STATUS_PMIB` e a lista com preço pela análise da IA.
