# Tradutor Técnico PT -> ES (tela 4.2)

> **Onde o código mora** (reescrito em 2026-09-25)
>
> | Parte | Arquivo |
> |---|---|
> | Tela | `sigft/app_qt/views/translator.py` (`ModuloTranslator`) |
> | Lote de fichas, Excel | `sigft/services/translator.py` (`TechnicalTranslator`) · shim `translator_backend.py` |
> | Regras da tradução | `sigft/services/traducao_respostas.py` |
> | Motor (modelo local) | `sigft/core/tradutor_local.py` |
> | Preparo do modelo | `tools/preparar_tradutor.py` → `recursos/tradutor_pt_es/` (fora do Git) |
> | Por que assim | `docs/superpowers/specs/2026-09-25-tradutor-local-design.md` |

## Propósito

Traduz as respostas das características técnicas de cada ficha (aba "Ficha
Técnica Padrão", linha `config.LINHA_SPECS_FICHA` = 79 em diante, coluna C =
pergunta, M = resposta) do português para o espanhol, e grava a aba
**"Especificações técnicas copiar"**, que o Upload de características (4.3)
lê. O contrato com o 4.3 não mudou: mesma aba, mesmos três cabeçalhos
(`Pergunta` | `Resposta (Espanhol s/ caracteres especiais)` |
`Resposta (Português s/ caracteres especiais)`), pergunta com o número na
frente.

## Como era, e por que mudou

Até a 1.1.0: uma chamada ao Google Tradutor por resposta (MyMemory quando o
Google falhava), com `time.sleep(1.0)` fixo, e um `xw.App()` por ficha. ~80 s
por ficha de 40 respostas; cada resposta saía para dois serviços públicos; se
os dois falhassem, o **português ia para a coluna do espanhol** sem aviso; e o
`xw.App()` com `add_book=True` (padrão) deixava **um Excel invisível aberto
por ficha** até o SIG-FT fechar (o `quit()` só rodava com `books.count == 0`).

## Como é agora

### O motor (`core/tradutor_local.py`)
- OPUS-MT `tc-big-itc-itc` (Helsinki-NLP, CC-BY 4.0), convertido para
  CTranslate2 int8 (~218 MB), **embutido no instalador** em
  `modelos/tradutor_pt_es`. Roda na CPU; nada sai do computador.
- Só `ctranslate2` + `sentencepiece` em execução, importados na primeira
  tradução. Carga ~0,5 s, uma vez por sessão (`obter()`).
- Prefixo `>>spa<<` (o modelo é multilíngue), beam 4, teto de decodificação
  proporcional à entrada, SEM `replace_unknowns` (ele trazia o próprio
  `>>spa<<` no lugar do `Ø`).
- Onde procura: `SIGFT_MODELO_TRADUTOR`, o pacote (`_MEIPASS`), `recursos/`
  do repositório, `Documentos\SIG-FT\modelos\`. Sem modelo: `ModeloAusente`
  dizendo onde procurou e o que fazer.

### As regras (`services/traducao_respostas.py`)
Por resposta distinta do lote:
1. vazia ou "não se traduz" (número, unidade, código, norma, `N/A`) → igual;
2. glossário, frase inteira → espanhol do glossário, sem modelo;
3. símbolo fora do vocabulário (`Ø`, `±`, `²`) → marcador `XQn`, volta igual;
4. termo do glossário dentro da frase → **três versões** numa ida ao modelo:
   direta, com o termo já em espanhol, com o termo num marcador. Vence a mais
   natural que mantém o termo (medido: o marcador garante o termo, mas às vezes
   estraga a frase em volta, "compuerta como vástago");
5. conferências: `⁇`, prefixo vazado ou marcador perdido invalidam a versão;
   número que muda devolve o original; ponto final segue o original; TUDO
   MAIÚSCULO vai em caixa de frase e volta em maiúsculas.

Glossário em duas camadas: `GLOSSARIO_DA_CASA` (no código, só o que o modelo
errou: mancal, porca, arruela, gaxeta, escova de carvão, chave fim de curso,
conforme desenho, revenido...) e o do usuário
(`Documentos\SIG-FT\traducao\GLOSSARIO_PT_ES.txt`, formato `portugues =
espanhol`, **vence** o da casa, acento e caixa não importam). O botão "Abrir
glossário" da tela abre esse arquivo.

### O lote (`services/translator.py`)
- `processar_arquivos(caminhos, retry_lock)`: prepara o motor e o glossário
  **antes** de abrir o Excel (modelo ausente → `ABORTADO` sem tocar planilha);
  **um** Excel invisível para o lote (`add_book=False`, `quit()` + `kill()` no
  fim, mesmo com erro); por ficha, uma leitura da faixa C..M e uma escrita da
  aba (colunas em formato texto antes, para `1/2` não virar data).
- Memória do lote: resposta repetida em outra ficha não volta ao modelo.
- `processar_arquivo(caminho)` continua existindo (chama o de cima).
- Nome da característica: com dois grupos de parênteses sai só o último
  (`FAIXA DE TENSAO DE ALIMENTACAO (CA) (ajuda)` → `... (CA)`); com um, como
  antes.
- Célula → texto: `220.0` → `220`, `0.5` → `0,5`, data → `dd/mm/aaaa`.
- Aba "Standard Technical Sheet" (ficha em inglês): falha só daquela ficha,
  com o motivo.
- Saída sem acento (`unidecode`), exigência do portal, como antes.
- Palavras de status que a tela não mostra: `STATUS` =
  {`SUCESSO`, `ERRO`, `ERRO_MOVER`, `PARADO`, `ABORTADO`}.

### A tela (`views/translator.py`)
- Backend criado no **primeiro clique** (antes, no `__init__`, derrubava a
  janela principal se o backend não carregasse).
- O lote inteiro vai ao serviço; `ABORTADO` vira caixa de erro.

## Medido (GitHub Actions, 2026-09-25)
88 respostas no estilo das fichas: 84 certas, 4 aceitáveis (concordância de
gênero, "Previa consulta"), 0 para conferir. ~2 a 10 s para as 88 num runner
Windows de 2 núcleos. O Google, no mesmo runner, devolveu 429 em todas.

## Pontos de atenção
- Instalador ~200 MB maior (o modelo). Se o tamanho da atualização incomodar,
  a alternativa é baixar o modelo no primeiro uso a partir do Release.
- Ficha em inglês não é traduzida (EN → ES/PT pede outro modelo).
- Qualidade: frases longas e raras podem sair com gramática imperfeita. O
  Upload 4.3 ainda passa as respostas pela IA, que corrige o espanhol dos
  campos de texto; e o glossário do usuário conserta o que se repetir.
- Excel COM (Windows + Excel instalado) continua sendo requisito da escrita.
