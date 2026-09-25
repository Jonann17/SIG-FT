# Tradutor 4.2: tradução local, em lote, sem sair do computador

**Data:** 2026-09-25 · **Pedido:** Rafael ("está muito lento; tradução correta,
mais velocidade, preferência por métodos que não coletem informações; implemente
e lance uma pré-release") · **Módulo:** `services/translator.py` + tela
`views/translator.py` (4.2 Tradutor Técnico PT -> ES).

## 1. O problema, medido no código

O tradutor lê a aba "Ficha Técnica Padrão" (linha 79 em diante, coluna C =
pergunta, M = resposta) e grava a aba "Especificações técnicas copiar", que o
Upload de características (4.3) lê. Por resposta, hoje:

| Custo | Onde | Efeito |
|---|---|---|
| `time.sleep(1.0)` fixo | `processar_arquivo` | 1 s por resposta, sempre |
| 1 chamada ao Google por resposta (+1 s e MyMemory se falhar) | `_traduzir_hibrido` | rede sequencial; no runner do GitHub o Google devolveu **429 nas 76 amostras** |
| Falha das duas vira o **texto em português** na coluna do espanhol | idem | sem aviso nenhum |
| `xw.App(visible=False)` **por arquivo**, com `add_book=True` (padrão) | idem | o `quit()` só roda com `books.count == 0`, e a pasta vazia nunca fecha: **cada ficha deixa um Excel invisível aberto** até o SIG-FT fechar (conferido no fonte do xlwings 0.37) |
| 5 chamadas COM por linha + 5 de formatação por linha | idem | lento, mas secundário |

Uma ficha de 40 respostas custa ~80 s; um lote de 40 fichas passa de 50
minutos. E cada resposta vai para dois serviços públicos gratuitos (Google
Tradutor e MyMemory), fora de qualquer contrato da empresa.

## 2. O que foi testado (GitHub Actions, 2026-09-25)

Experimento descartável no branch de desenvolvimento (`experimentos/traducao_local`),
88 respostas no estilo das fichas (materiais, componentes, elétrica, instruções,
códigos):

| Motor | Tamanho | Qualidade | 88 respostas (Windows, 2 vCPU) |
|---|---|---|---|
| Google (deep_translator) | on-line | não mediu: **429 em todas** | 38 s só de falhas |
| Argos pt->es 1.0 | 73 MB | deixa muito em português ("Porca sextavada", "Graxa", "Mancal") | ~1 s |
| OPUS-MT `itc-itc` base | 65 MB | fraco ("4 pollos", "Rollo rígido") | ~1 s |
| **OPUS-MT `tc-big-itc-itc`** (Helsinki-NLP, CC-BY 4.0) | **218 MB** (int8) | **bom** ("Acero al carbono", "Fundición nodular", "Buje de bronce", "Rodamiento rígido de bolas"); erra vocabulário da casa | **2,2 s** (beam 4) |

Erros do tc-big, todos de vocabulário técnico brasileiro: *mancal* ("falta",
"mangueras"), *porca* ("cerda"), *arruela* ("lavadora"), *chave fim de curso*
("clave"), *conforme desenho* ("como dibujo"), *revenido* ("vuelto"), *Ø* (vira
`⁇`). Trocar o termo por espanhol ANTES do modelo conserta metade; na outra
metade o modelo "retraduz" o espanhol (`cojinete` -> `rodamiento`,
`tuerca` -> `cerda`). Daí os marcadores da seção 4.2.

O caminho do app (só `ctranslate2` + `sentencepiece`, sem `transformers`) bate
com o de referência em 86 de 88 frases (as 2 diferenças são o `Ø`).

## 3. Decisão

**Tradutor local.** O modelo OPUS-MT tc-big, convertido para CTranslate2 int8,
roda na CPU da máquina, **embutido no instalador**. Nada é enviado para fora,
não precisa de chave, rede nem VPN.

Descartados:
- **IA em lote (OpenRouter, retenção zero):** melhor em frases longas, mas manda
  o texto para fora (contra a preferência do pedido) e depende de chave e rede.
  O Upload 4.3 já passa as respostas pela IA e corrige o espanhol dos campos de
  texto. Fica como opção futura, se a qualidade local não bastar.
- **Google em lote (juntar as respostas numa chamada):** continua coletando, e o
  runner mostrou que o serviço gratuito bloqueia por volume.
- **Baixar o modelo no primeiro uso** (asset do Release): o instalador ficaria
  menor, mas entra um download com token, verificação e falha de rede no meio do
  trabalho. Embutir é o que funciona sempre. Custo: o instalador cresce ~200 MB.
  Revisitar se o tamanho da atualização incomodar.

## 4. Componentes

### 4.1 `sigft/core/tradutor_local.py` (o motor)
- `localizar_modelo()`: a pasta do modelo embutido (`_MEIPASS/modelos/tradutor_pt_es`),
  depois `Documentos\SIG-FT\modelos\tradutor_pt_es`, depois `SIGFT_MODELO_TRADUTOR`.
- `TradutorLocal.traduzir(textos) -> list[str]`: lote, `beam_size=4`,
  `replace_unknowns=True` (o `Ø` passa), prefixo `>>spa<<`, `</s>` no fim.
  Carrega uma vez por processo (0,2 s).
- `ModeloAusente`: mensagem que diz onde procurou e como resolver.
- Importa `ctranslate2`/`sentencepiece` só na carga: o resto do app não paga.

### 4.2 `sigft/services/traducao_respostas.py` (regras, sem Excel nem modelo)
Camadas, em ordem, para cada resposta distinta do lote:
1. **Vazio / não se traduz**: número, unidade, código, norma, marca, `N/A`, `-`
   (`220 V`, `IP65`, `6205-2RS`, `NBR 5410`, `WEG W22`). Vai igual.
2. **Glossário, frase inteira**: vai o espanhol do glossário, sem modelo.
3. **Glossário, termo**: cada termo vira um **marcador** (`Xq1`, ...) que o
   modelo copia; depois o marcador vira o termo em espanhol. Marcador perdido ->
   refaz sem marcador e avisa.
4. **Modelo**, em lote, com a caixa tratada: TUDO MAIÚSCULO vai em caixa de
   frase e volta em maiúsculas.
5. **Conferências**: os números da resposta têm de estar na tradução (senão
   fica o original e o log avisa); ponto final que o original não tinha sai.

Glossário em duas camadas: o **da casa** (no código, melhora a cada versão) e
o **do usuário** (`Documentos\SIG-FT\traducao\GLOSSARIO_PT_ES.txt`, formato
`portugues = espanhol`, criado vazio com instruções; **vence** o da casa).

### 4.3 `sigft/services/translator.py` (orquestração)
- `processar_arquivos(caminhos, retry_lock)`: **um** Excel para o lote
  (`add_book=False`, `quit()` + `kill()` no fim), leitura da faixa inteira numa
  chamada, tradução da ficha num lote, escrita da aba numa chamada, formatação
  por faixa. Mesma aba, mesmos cabeçalhos, mesmas cores: o 4.3 não muda.
- `processar_arquivo(caminho)` continua existindo (chama o de cima).
- Linha inicial de `config.LINHA_SPECS_FICHA` (era 79 no código).
- Nome da característica: com dois grupos de parênteses, sai só o ÚLTIMO (a
  ajuda); com um, como antes. Conserta `FAIXA DE TENSAO DE ALIMENTACAO (CA)`
  (PENDENCIAS 2026-09-24).
- Número vindo do Excel sai sem `.0` (`220.0` -> `220`; `0.5` -> `0,5`).
- Aba em inglês ("Standard Technical Sheet"): mensagem própria (o tradutor
  traduz respostas em português).

### 4.4 Tela `views/translator.py`
- Backend criado no primeiro clique (PENDENCIAS 2026-09-24: `__init__` derrubava
  a janela se o backend não carregasse).
- Chama `processar_arquivos` com a lista inteira; botão "Abrir glossário".
- Texto da tela diz que a tradução é local.

### 4.5 Empacotamento
- `requirements.txt`: `ctranslate2`, `sentencepiece`.
- `tools/preparar_tradutor.py`: converte a revisão FIXA do Hugging Face para
  `recursos/tradutor_pt_es/` (+ `origem.json`, README com a licença CC-BY 4.0).
- `release.yml`: prepara o modelo (com cache) ANTES dos testes, para os testes
  com modelo de verdade rodarem no Windows.
- `SIG-FT.spec`: embute `recursos/tradutor_pt_es` como `modelos/tradutor_pt_es`
  e coleta as DLLs do `ctranslate2`.
- `--conferir-pacote`: traduz uma frase **dentro do .exe**; se falhar, o
  release para antes de publicar.

## 5. Erros e avisos (o que o usuário vê)

| Situação | Comportamento |
|---|---|
| Modelo não encontrado | para antes de abrir o Excel, diz onde procurou e o que fazer |
| Aba ausente / ficha em inglês | falha só daquela ficha, com o motivo |
| Número não confere na tradução | fica o original, linha `[CONFERIR]` no log |
| Marcador do glossário perdido | refaz sem marcador, linha `[CONFERIR]` |
| Planilha aberta no Excel | a janela "feche o arquivo" de sempre (`salvar_perguntando`) |
| Parar | termina a ficha atual, fecha o Excel, não deixa processo |

Resumo por ficha: quantas traduzidas pelo modelo, quantas pelo glossário,
quantas iguais; no fim, o tempo total.

## 6. Testes

- Regras (`test_traducao_respostas.py`): não-traduzir, glossário (frase e
  termo), marcadores (perdido -> refaz), caixa, número, ponto final, dedupe.
- Motor (`test_tradutor_local.py`): dublê de `ctranslate2`/`sentencepiece`;
  prefixo, `</s>`, `replace_unknowns`, beam; modelo ausente; e um teste com o
  MODELO DE VERDADE que só roda onde ele existe (o release no Windows).
- Tradutor (`test_translator_lote.py`): Excel dublado (uma instância só, quit
  no fim, escrita em bloco), nome da característica, número, aba em inglês,
  parar, erro por ficha.
- Tela: backend preguiçoso; empacotamento: spec, workflow e conferência.

## 7. Fora do escopo

- Ficha em inglês (resposta EN -> ES e EN -> PT): outro modelo e outro fluxo.
- Tradução PT -> EN dos PDMs (`traducao_pdm`): continua com IA + Google.
- Glossário tirado automaticamente da planilha-mestra (VALORES PT/ES).
