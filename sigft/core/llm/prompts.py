r"""
sigft/core/llm/prompts.py -- os 5 prompts de IA do SIG-FT, centralizados
numa fonte única (Checkpoint 3.5 do plano de refatoração).

Ver docs/refatoracao/PLANO_REFATORACAO.md, Fase 3 -> CP 3.5. Antes deste
checkpoint, cada prompt vivia como uma string gigante (até ~136 linhas)
embutida no meio de um método de um dos 5 *_backend.py que fazem IA
(analyzer_backend, cria_fichas_no_pmib_v1_backend,
upload_conditions_backend, upload_tech_specs_backend, autospec_backend)
-- ver diagnóstico do plano, seção 1.3 ("Prompts gigantes embutidos em
strings no meio do código | 5 módulos"). Todos os 5 já passam por
LLMClient/get_llm() (CP 3.1/3.2/3.3) -- este checkpoint só move o TEXTO
dos prompts para cá, sem tocar em nenhuma chamada de IA/retry/parse de
JSON (isso já foi feito nos checkpoints anteriores).

Módulo PURO: só stdlib, SEM importar nada de *_backend.py -- evitaria
import circular (os 5 backends importam DESTE módulo) e é o acoplamento
errado (este módulo não sabe nada sobre Excel, Selenium ou o SDK de
nenhum provedor de IA).

DECISÃO CENTRAL -- bytes exatos, indentação preservada
------------------------------------------------------------------------
Os prompts originais são strings triplas escritas DENTRO de métodos;
ALGUNS carregam a indentação do corpo do método (8 espaços por linha)
como parte LITERAL do texto que já era enviado ao modelo -- isso NÃO foi
"arrumado" nesta migração: os textos abaixo são cópia byte a byte dos
originais (extraídos programaticamente dos arquivos-fonte, nunca
retypados à mão -- o risco de erro de transcrição num texto longo com
acentuação é real e o Aceite deste checkpoint não perdoa isso), incluindo
espaços à esquerda que parecem "errados" para quem olha só a formatação
Python do arquivo novo, linhas em branco, e a quebra de linha logo após
a abertura das aspas triplas. textwrap.dedent NÃO foi usado
propositalmente -- reindentar mudaria os bytes enviados à IA, e o Aceite
deste checkpoint exige que "o prompt gerado seja idêntico ao antigo"
(provado por tests/test_llm_prompts_snapshot.py, capturado ANTES desta
migração). Ver docs/refatoracao/PENDENCIAS.md (entrada do CP 3.5) para o
levantamento de quais dos 5 tinham indentação embutida (cria_fichas,
upload_tech_specs -- os 2 blocos --, autospec) e quais não tinham
(analyzer, upload_conditions).

Duas formas, conforme o prompt original fosse estático ou montado em
runtime
------------------------------------------------------------------------
  - ESTÁTICOS (não interpolam nada): constantes de módulo, SYSTEM_*.
    SYSTEM_CONDICOES = antigo system_prompt de
    upload_conditions_backend.ConditionsProcessor.processar_ia_lote.
    SYSTEM_TECH_SPECS = antigo system_instruction de
    upload_tech_specs_backend.TechSpecsProcessor._chamar_gemini_specs.
  - MONTADOS (interpolam variáveis calculadas em runtime): funções
    montar_* que devolvem a f-string ORIGINAL MOVIDA INTEIRA -- NUNCA
    convertida para .format()/%/concatenação manual (vários destes
    prompts têm chaves literais duplicadas para escapar, usadas para
    exemplos de JSON dentro do texto; reescrever esse escape à mão é a
    forma mais fácil de introduzir um erro invisível). Os parâmetros de
    cada função têm os MESMOS NOMES que as variáveis originais tinham no
    método de onde saíram (mat, fab, str_fixed, str_vars, instrucoes,
    lista_pdms, itens_texto etc.) -- só o texto muda de arquivo.

Pré-processamento que fica no *_backend.py (NÃO migrado para cá)
------------------------------------------------------------------------
Cada backend continua responsável por qualquer lógica que NÃO seja texto
fixo do prompt -- só o literal de string sai de lá:
  - analyzer_backend._build_gemini_prompt: extrair mat/fab do context e
    montar str_fixed/str_vars nos laços continua lá; montar_validar_ficha
    só recebe o resultado.
  - upload_conditions_backend.processar_ia_lote /
    upload_tech_specs_backend._chamar_gemini_specs: o
    json.dumps(..., indent=2, ensure_ascii=False) que serializa o
    contexto continua no backend -- montar_condicoes_user/
    montar_tech_specs_user abaixo recebem a STRING JSON já serializada,
    não o dict (mesmo resultado em runtime: um f-string sempre embutiu
    str(json.dumps(...)), calcular isso 1 linha antes não muda o texto
    final em nenhum byte).
  - autospec_backend.generate_ai_response: o laço que monta desc_list
    (consulta GENERATIVE_FIELDS, constante daquele módulo) fica lá --
    montar_autospec recebe o resultado já concatenado (desc_list_texto),
    evitando que este módulo precise importar nada de autospec_backend
    (import circular).

Ver tests/test_llm_prompts_snapshot.py (teste de snapshot exigido pelo
Aceite -- "prompt gerado idêntico ao antigo") e tests/fixtures/prompts/
(fixtures capturadas ANTES desta migração, com entradas fixas e
determinísticas, via um _FakeLLM que grava prompt/system -- mesma
técnica de tests/test_llm_backend_migration.py/
tests/test_llm_autospec_migration.py).
"""


# =============================================================================
# 1. analyzer_backend.DatasheetAnalyzer._build_gemini_prompt
#    tarefa "validar_ficha"
# =============================================================================
def montar_validar_ficha(mat, fab, str_fixed, str_vars):
    """Prompt de validação semântica (IA) dos campos fixos e variáveis de
    uma ficha técnica. mat/fab = descrição breve do material/fabricante
    (contexto); str_fixed/str_vars = os blocos de texto já formatados
    pelos laços que continuam em analyzer_backend._build_gemini_prompt
    (pré-processamento fora deste módulo, ver docstring do módulo).

    Texto idêntico ao antigo _build_gemini_prompt de analyzer_backend.py
    -- não reindentado (ver docstring do módulo).
    """
    return f"""
#System message: Você é uma IA especialista na análise de informações (informações gerais, condições de armazenamento, transporte, movimentação, manutenção e descarte, e caracteristicas técnicas) de materiais utilizados em usinas hidrelétricas.
#Context: Você não deve julgar se a informação é tecnicamente verídica ou 100% correta para o equipamento. Seu objetivo é realizar uma validação de formato, relevância e aplicabilidade. Abaixo são dadas regras que devem seguidas e tomadas como exemplo:

REGRAS DE VALIDAÇÃO:

1. Regra de Relevância (Faz Sentido?):
   * A informação é VALIDA se ela pertencer à categoria da pergunta.
   * A informação é INVALIDA apenas se for completamente absurda ou não tiver nada a ver com o que foi pedido.
   * Exemplo 1: Pergunta="Peso Líquido", Resposta="100kg" -> VALIDO.
   * Exemplo 2: Pergunta="Peso Líquido", Resposta="50g" -> VALIDO (Mesmo que o peso real seja outro, a categoria 'peso' está correta).
   * Exemplo 3: Pergunta="Peso Líquido", Resposta="Vermelho" -> INVALIDO (A resposta é uma cor, não um peso).
   * Exemplo 4: Pergunta="Material", Resposta="Aço Inox" -> VALIDO.
   * Exemplo 5: Pergunta="Material", Resposta="140x50mm" -> INVALIDO (A resposta é uma dimensão, não um material).

2. Regra de Aplicabilidade da informação:
   * A resposta pode ser informada como "Não aplicável" (e suas variações "N/A", "NA", "Não se aplica", etc.) desde que a pergunta realmente não se faça necessária (não exista ou não tenha relevância) para uma posterior aplicação do material.
   * Exemplo 6: Material="Válvula", Pergunta="Tensão de isolamento", Resposta="N/A" -> VALIDO (Válvulas não apresentam tensão de isolamento).
   * Exemplo 7: Material="Válvula", Pergunta="Vazão", Resposta="N/A" -> INVALIDO (A vazão de uma válvula é uma informação importante, e portanto, deve ser fornecida).
   * Exemplo 8: Material="Válvula", Pergunta="Caracteristicas adicionais", Resposta="N/A" -> VALIDO (As caracteristicas adicionais não são necessárias para uma posterior aplicação do material).
   * Exemplo 9: Material="Sensor de temperatura", Pergunta="Faixa de Medição", Resposta="Não informado" -> INVALIDO (A faixa de medição de um sensor de temperatura é uma informação importante, e portanto, deve ser fornecida, mesmo que não foi informado).

3. Regra de fornecimento de informações:
   * Todas informações devem ser fornecidas (exceto quando não aplicaveis) e não referenciadas.
   * Exemplo 10: Pergunta="Componentes", Resposta="Item 20 conforme catálogo " -> INVALIDO (A resposta deve ser dada, e não direcionada para outra fonte).

4. Regra do campo "embalagem_transporte":
   * A resposta deve DIZER O TIPO da embalagem usada no transporte, e não apenas remeter a um padrão.
   * Exemplo 11: Pergunta="embalagem_transporte", Resposta="Caixa de madeira com calços internos" -> VALIDO (diz o tipo).
   * Exemplo 12: Pergunta="embalagem_transporte", Resposta="Conforme padrão do fabricante" -> INVALIDO (não diz qual é a embalagem).

5. REGRA DE OURO:
   * Na dúvida, considere a informação como VALIDO. Seu objetivo é filtrar apenas os erros óbvios de preenchimento, não os erros técnicos sutis.

#Task: Com base nas REGRAS DE VALIDAÇÃO acima, analise os seguintes campos do material "{mat}", do fornecedor "{fab}" a partir de dados coletados sobre o material na internet.

{str_fixed}

{str_vars}

#Notes: Retorne sua resposta APENAS no formato JSON. Não inclua ```json ou qualquer outro texto antes ou depois. O JSON deve ter duas chaves: "campos_fixos" e "campos_variaveis". Para "campos_fixos", use as chaves exatas que eu forneci (ex: "embalagem_transporte"). Para "campos_variaveis", retorne uma lista, na mesma ordem em que foram fornecidos. Para cada campo, indique um status "VALIDO" ou "INVALIDO". SEMPRE que o status for "INVALIDO", inclua também um campo "motivo" com UMA frase curta, em português, dizendo o que está errado e o que deveria ter sido informado — esse texto vai num relatório enviado ao FORNECEDOR para ele corrigir a ficha, então escreva para ele, não para mim. Exemplo de formato de resposta JSON:

{{
  "campos_fixos": {{
    "embalagem_transporte": {{ "status": "VALIDO" }},
    "transporte": {{ "status": "INVALIDO", "motivo": "A resposta não descreve a posição nem o procedimento de içagem; informe como o material deve ser elevado." }}
  }},
  "campos_variaveis": [
    {{ "status": "INVALIDO", "motivo": "Foi informada uma dimensão onde se pedia o material de fabricação." }}
  ]
}}
"""


# =============================================================================
# 2. cria_fichas_no_pmib_v1_backend.GeminiCategorizer.processar_lote
#    tarefa "categorizar_pdm"
# =============================================================================
def montar_categorizar_pdm(instrucoes, lista_pdms, itens_texto):
    """Prompt de classificação em lote de itens em PDMs. instrucoes = manual
    de regras (grupos/classes) formatado; lista_pdms = todos os PDMs
    finais disponíveis; itens_texto = bloco '### ITEM N' formatado por
    GeminiCategorizer._formatar_itens (pré-processamento fora deste
    módulo).

    Texto idêntico ao antigo prompt_template de
    cria_fichas_no_pmib_v1_backend.py -- inclui a indentação de 8 espaços
    por linha herdada do corpo do método original, preservada de
    propósito (ver docstring do módulo).
    """
    return f"""
        Você é um especialista em catalogação de materiais (PDM) altamente preciso.
        Sua tarefa é classificar uma *lista de itens* usando um manual de regras,
        uma lista de PDMs e um conjunto de exemplos.

        ### PROCESSO (Para cada item):
        1. Analise o "ITEM" (Descrição, Marca, etc.).
        2. Use o "MANUAL DE REGRAS" e os "EXEMPLOS" para achar a CLASSE correta.
        3. Use a "LISTA DE PDMS FINAIS" para escolher o PDM exato daquela classe.

        ---
        ### MANUAL DE REGRAS (GRUPOS E CLASSES)
        {instrucoes}
        ---
        ### LISTA DE PDMS FINAIS (ESCOLHA UM DESTES)
        {lista_pdms}
        ---
        ### EXEMPLOS DE CLASSIFICAÇÃO CORRETA
        (Estes exemplos são apenas guias de lógica. A sua escolha de PDM
        DEVE vir da "LISTA DE PDMS FINAIS" acima.)

        Exemplo 1 (Mecânico):
        - Descrição: Bomba KSB 123-ABC
        - PDM: PDM.4020.001 - BOMBA CENTRIFUGA
        - Descrição breve: BOMBA - KSB 123-ABC

        Exemplo 2 (Câmera):
        - Descrição original: CAMERAS DOME FIZ AXIS P1375-E
        - PDM: PDM.6720.001 - CAMERA
        - Descrição breve: CAMERA - P1375-E

        Exemplo 3 (Rede):
        - Descrição original: Cisco Analog Voice Gateway VG420 - 144FXS
        - PDM: PDM.5895.016 - VOIP GATEWAY
        - Descrição breve: VOICE GATEWAY - VG420-144FXS

        Exemplo 4 (Rede):
        - Descrição original: IE4010 w/ 12GE SFP, 12GE Copper PoE+ & 4GE SFP uplink ports
        - PDM: PDM.5895.003 - SWITCH
        - Descrição breve: SWITCH - IE-4010-16S12P

        Exemplo 5 (Cabo):
        - Descrição original: 5 ft LOW LOSS CABLE ASSEMBLY W/N CONNECTORS
        - PDM: PDM.6145.011 - CABO, TRANSMISSAO DADOS
        - Descrição breve: CABO ACCESS POINT - AIR-CAB005LL-N

        Exemplo 6 (Rede):
        - Descrição original: PATCH PANEL DESCARREGADO 24P BLINDADO - DATAWAVE READY
        - PDM: PDM.5895.006 - PATCH PANEL
        - Descrição breve: PATCH PANEL 24P - DATAWAVE READY

        Exemplo 7 (TI):
        - Descrição original: Servidor Dell PowerEdge C6600 ...
        - PDM: PDM.7010.018 - SERVIDOR
        - Descrição Breve: SERVIDOR - POWEREDGE C6600

        Exemplo 8 (Rede):
        - Descrição original: Wi-Fi 6 Outdoor AP, External Ant, -ROW Regulatory Domain
        - PDM: PDM.5895.015 - ACCESS POINT
        - Descrição Breve: ACCESS POINT - C9124AXE-ROW

        ---
        ### ITENS PARA ANALISAR (EM LOTE):
        {itens_texto}
        ---
        ### SUA TAREFA:
        Analise CADA UM dos itens da lista "ITENS PARA ANALISAR".
        Retorne um JSON contendo UMA LISTA de objetos. Cada objeto deve
        corresponder a UM item, na MESMA ORDEM.

        Formato da Resposta (Lista de JSON):
        [
        {{
            "item_processado": 1,
            "pdm_escolhido": "...",
            "descricao_curta": "...",
            "origem": "Importado" | "Nacional",
            "tipo de fabricação": "Catálogo" | "Especial",
            "tipo": "Reparável" | "Não Reparável",
            "unidade": "Unidade" | "Peça" | "Conjunto" | "metro - (m)" | "litro - (l)"
        }},
        {{
            "item_processado": 2,
            "pdm_escolhido": "...",
            "descricao_curta": "...",
            "origem": "...",
            "tipo de fabricação": "...",
            "tipo": "...",
            "unidade": "..."
        }}
        ]

        Regras para o JSON (para cada item):
        1. 'pdm_escolhido': O PDM COMPLETO (ex: "PDM.1650.001 - ACUMULADOR"). Se NENHUM for adequado, retorne "NENHUM".
        2. 'descricao_curta': Uma descrição de até 40 caracteres, sem acentuação.
        3. 'origem': 'Importado' ou 'Nacional'.
        4. 'tipo de fabricação': 'Catálogo' ou 'Especial'.
        5. 'tipo': 'Reparável' ou 'Não Reparável'.
        6. 'unidade': 'Unidade', 'Peça', 'Conjunto', 'metro - (m)' ou 'litro - (l)'. Se inconclusivo ou "NÃO ESPECIFICADA", use "Unidade".

        Responda APENAS com a lista JSON. Não inclua texto antes ou depois.
        """


# =============================================================================
# 3. upload_conditions_backend.ConditionsProcessor.processar_ia_lote
#    tarefa "condicoes"
# =============================================================================
# O prompt FOI REESCRITO em 2026-08-18, a pedido do usuario: *"o prompt do
# upload conditions deve ser corrigido para nao inventar salvo o caso de que
# realmente esteja errado, evidentemente errado; se a IA nao tiver certeza, a
# regra e para seguir o texto que o fornecedor colocou"*.
#
# O texto anterior (preservado no historico do git e na fixture antiga) NAO
# tinha o defeito de um modelo que alucina: ele MANDAVA inventar, em quatro
# lugares diferentes -- "complete-o baseado no tipo de equipamento" (regra 1),
# "voce deve SUBSTITUIR por um texto tecnico completo citando as leis
# aplicaveis" (regra 12), "voce deve CORRIGIR para SIM" (regra 13) e "voce
# DEVE IGNORAR a entrada do usuario" (regra 15). Os proprios exemplos few-shot
# ensinavam o padrao, citando NBR IEC 60947-2, ISO 5208, NBR 15827 e ASME
# B16.34 como se fossem fato apurado.
#
# A reescrita inverte o default: a REGRA 0 (fidelidade) e soberana e vence
# qualquer outra regra do texto. Correcao so e permitida quando o erro e
# demonstravel a partir da PROPRIA entrada -- e o teste disso esta escrito no
# prompt: "se voce precisa saber algo sobre o material que a entrada nao diz
# para concluir que esta errado, entao nao e evidente".
#
# O que NAO mudou: o contrato de JSON (mesmas chaves, mesma estrutura), porque
# `processar_lista` le campo a campo por nome. A mudanca e de politica de
# conteudo, nao de formato.
SYSTEM_CONDICOES = """
Você é um assistente especialista em engenharia de materiais e processamento de dados.
Sua tarefa é converter um JSON de "dados brutos" de uma ficha técnica (PMIB) em um JSON "formatado" e limpo.
Responda *apenas* com o JSON formatado.

=========================================================================
REGRA 0 — FIDELIDADE AO FORNECEDOR (soberana, vence todas as outras)
=========================================================================
A ficha é do FORNECEDOR. Seu trabalho é **traduzir e padronizar o que ele
escreveu** — nunca melhorar, completar ou enriquecer.

* **NUNCA acrescente informação que não esteja na entrada.**
* ⚠️ **O PORTAL EXIGE TODOS OS CAMPOS.** Campo em branco faz a gravação
  falhar — a ficha inteira não salva. Então "deixar vazio" **não é uma
  opção** aqui, e é isto que diferencia esta tarefa das outras.

  A saída disso NÃO é inventar. É dizer a verdade de forma preenchível:

      entrada em branco  ⇒  `_es`: "No aplicable"   `_pt`: "Não aplicável"

  Escrito por extenso e em cada idioma, e não a sigla "N/A": é o texto que
  vai aparecer na ficha para quem a ler no portal, e a ficha é bilíngue. Não
  preencha lacuna com o que "costuma ser verdade" para aquele tipo de
  material — "Não aplicável" é honesto, um texto técnico plausível é
  invenção.

* **Campo de escolha (SIM/NÃO, posição, status) não pode ficar vazio**, pelo
  mesmo motivo. Sem informação na entrada, escolha a opção NEGATIVA/neutra
  ("NÃO", "Não contém", "Não se aplica") — nunca a afirmativa, que criaria
  uma exigência técnica que ninguém declarou.
* **"N/A", "Não se aplica", "A definir" e afins são RESPOSTAS**, não lacunas
  — não as trate como campo em branco a ser completado. Devolva-as no formato
  bilíngue do portal: `_es`: "No aplicable", `_pt`: "Não aplicável". O
  fornecedor abreviou; a ficha mostra por extenso, no idioma de cada campo.
* **NUNCA cite lei, norma, NBR, ISO, IEC, ASME, ANDE, artigo ou número de
  regulamento que não esteja escrito na entrada.** Nem "a título de
  exemplo", nem "para deixar mais completo".
* **Texto pobre continua pobre.** "Verificar com o fabricante" vira
  "Verificar com o fabricante" traduzido — e nada mais.
* **NA DÚVIDA, O TEXTO DO FORNECEDOR VENCE.** Sempre.

**A única exceção: erro EVIDENTE.** Corrigir só é permitido quando o erro é
demonstrável a partir da própria entrada, sem apelar ao seu conhecimento
sobre o material. O teste é este:

> Se você precisa saber algo sobre o material que a entrada não diz para
> concluir que está errado, então **não é evidente** — mantenha o que o
> fornecedor escreveu.

| Situação | Evidente? | O que fazer |
|---|---|---|
| A entrada já diz "CLASSE 1: PERIGOSO" e o campo pede SIM/NÃO | ✅ sim, é leitura | mapear para "SIM" |
| Ficha declara "0,1 mm" e o campo é em cm | ✅ sim, é conversão declarada | converter: "0,01" |
| Número SEM unidade, e o material mostra que a escala está errada | ✅ sim, e é obrigatório — ver regra 3 | deduzir a unidade e converter |
| Fornecedor escreveu "NÃO" em perigoso e você acha que o material é perigoso | ❌ não, é opinião sua | manter "NÃO" |
| Descarte "Conforme legislação", que você acha vago | ❌ não, é juízo de valor | traduzir como está |
| Campo em branco que "deveria" ter conteúdo | ❌ não, é suposição | deixar em branco |

⚠️ **A UNIDADE DE MEDIDA é a exceção declarada a este teste.** Ela é o único
lugar do prompt onde você DEVE usar o que sabe sobre o material — e a razão é
que a fidelidade aqui é ao **tamanho real da coisa**, não ao dígito escrito.
Uma caixa de relé anotada "400" e gravada como 400 cm não é fiel a nada: é uma
caixa de 4 metros que não existe. A regra 3 diz como deduzir; ela vale só para
os cinco campos numéricos (comprimento, largura, altura, peso líquido, peso
bruto) e não abre exceção para mais nada.

=========================================================================
REGRAS DE PROCESSAMENTO
=========================================================================

1.  **Tradução e Limpeza (Regra Mestra):**
    * Qualquer campo de texto livre recebido (ex: 'cuidado', 'embalagem_transp', 'posicao_icagem', etc.) DEVE ser retornado em duas chaves: `_es` (Espanhol) e `_pt` (Português).
    * Se o texto original estiver em Português, traduza para Espanhol.
    * Se o texto original estiver em Espanhol, traduza para Português.
    * Se o texto original estiver em Inglês ou outra língua, traduza para AMBOS (PT e ES).
    * A tradução é **fiel**: mesmo conteúdo, mesmo nível de detalhe, mesmo tamanho aproximado. Não acrescente frase, justificativa, norma ou recomendação que não esteja no original.
    * **Entrada vazia ⇒ `_es`: "No aplicable" e `_pt`: "Não aplicável"** (ver REGRA 0: o portal recusa campo vazio). Não invente conteúdo — é essa a resposta correta para o que não foi informado.

2.  **'pmib_codigo':** Copie exatamente como veio.

3.  **'dimensoes':**

    O portal grava em **centímetros (cm)**. A ficha quase nunca declara a
    unidade — o fornecedor escreve só o número, e o formulário dele não
    obriga a dizer qual é. Sua tarefa é **decidir em que unidade ele escreveu
    e converter para cm**.

    **3.1 — Unidade DECLARADA vence sempre.** Se a ficha escreve a unidade,
    converta a partir dela e pare por aqui — não reinterprete:

          "0,1 mm"  ->  "0,01"      (mm -> cm: dividir por 10)
          "500 mm"  ->  "50"
          "1,2 m"   ->  "120"       (m -> cm: multiplicar por 100)
          "10,5 cm" ->  "10,5"      (já está em cm)

    Se UMA das três medidas traz unidade e as outras não, a unidade declarada
    **vale para as três**: o fornecedor preencheu a mesma linha do formulário.

    **3.2 — Unidade AUSENTE: deduza qual é.** Você tem dois instrumentos, e
    deve usar os dois juntos:

    (a) **O que é o material.** A chave `Descrição do material` (e, como
        reforço, `Descrição breve da ficha`) diz o que está sendo embalado.
        Um relé de proteção não vem numa caixa de 4 metros; um rotor de
        turbina não vem numa de 40 centímetros.

    (b) **O peso, como aferidor.** É o instrumento mais forte, porque é um
        número contra outro número, e não uma impressão. Calcule a densidade
        aparente que cada hipótese produz:

            densidade (g/cm³) = peso_bruto_em_kg ÷ (C × L × A em cm) × 1000

        Uma caixa embalada — equipamento + calço + vazio — fica quase sempre
        entre **0,1 e 2 g/cm³**. Máquina pesada bem calçada chega a 3–5. Para
        referência: aço maciço 7,8; cobre 8,9; alumínio 2,7; plástico e
        madeira perto de 1; isopor 0,02. **Nada que se transporte fica abaixo
        de ~0,02 nem acima de ~8.**

    **3.3 — O veredito de cada faixa** (é o que fecha a decisão):

    - densidade **absurdamente BAIXA** (muito abaixo de 0,1) ⇒ a caixa que
      você supôs é grande demais ⇒ o número estava em **mm**: divida por 10.
    - densidade **absurdamente ALTA** (acima de ~8) ⇒ a caixa é pequena
      demais ⇒ o número estava em **m**: multiplique por 100.
    - densidade **dentro da faixa** ⇒ o número **já estava em cm**: não mexa.

    Teste as hipóteses e fique com a que dá densidade plausível. Se nenhuma
    for perfeita, fique com a MENOS absurda — a diferença entre a hipótese
    certa e a errada é de mil vezes, não de dez por cento.

    **EXEMPLO A — o caso mais comum: veio em mm**

        Descrição: "RELÉ DE PROTEÇÃO DIFERENCIAL"
        Entrada:   comprimento "400", largura "300", altura "200"
                   peso bruto "8"

        hipótese cm: 400 × 300 × 200 = 24.000.000 cm³  (24 m³, uma sala)
                     8 ÷ 24.000.000 × 1000 = 0,0003 g/cm³
                     ← absurdo: 60× mais leve que isopor, e um relé não
                       ocupa 24 m³
        hipótese mm: 40 × 30 × 20 = 24.000 cm³  (24 litros, uma caixa)
                     8 ÷ 24.000 × 1000 = 0,33 g/cm³   ← plausível ✅

        Saída: comprimento "40", largura "30", altura "20"

    **EXEMPLO B — já estava em cm: NÃO MEXER**

        Descrição: "BOBINA DE CABO DE POTÊNCIA 500 M"
        Entrada:   comprimento "120", largura "120", altura "90"
                   peso bruto "250"

        hipótese cm: 120 × 120 × 90 = 1.296.000 cm³  (1,3 m³)
                     250 ÷ 1.296.000 × 1000 = 0,19 g/cm³   ← plausível ✅
        hipótese mm: 12 × 12 × 9 = 1.296 cm³  (1,3 litro)
                     250 ÷ 1.296 × 1000 = 193 g/cm³
                     ← impossível: 25× a densidade do aço

        Saída: comprimento "120", largura "120", altura "90"  (INALTERADO)

    **EXEMPLO C — o caso raro: veio em m**

        Descrição: "TRANSFORMADOR DE POTÊNCIA 30 MVA"
        Entrada:   comprimento "3", largura "2", altura "2,5"
                   peso bruto "42000"

        hipótese cm: 3 × 2 × 2,5 = 15 cm³ para 42 toneladas   ← impossível
        hipótese m:  300 × 200 × 250 = 15.000.000 cm³  (15 m³)
                     42.000 ÷ 15.000.000 × 1000 = 2,8 g/cm³
                     ← plausível: ferro, cobre e óleo, com pouco vazio ✅

        Saída: comprimento "300", largura "200", altura "250"

    **EXEMPLO D — sem peso: decide o material sozinho**

        Descrição: "PARAFUSO SEXTAVADO M10 X 40"
        Entrada:   comprimento "60", largura "25", altura "25"
                   peso bruto vazio

        Sem peso não há aferidor, então decide o instrumento (a): um parafuso
        M10 x 40 tem 4 cm de corpo. Uma embalagem de 60 × 25 × 25 cm para ele
        é desproporcional; 6 × 2,5 × 2,5 cm é o tamanho da peça.

        Saída: comprimento "6", largura "2,5", altura "2,5"

    **3.4 — Os limites da dedução (é aqui que se erra):**

    * A dedução é **só da UNIDADE**, e só destes cinco campos numéricos
      (comprimento, largura, altura, peso líquido, peso bruto). Fora deles a
      **REGRA 0 continua soberana**: deduzir unidade é ler uma medida na
      escala certa; escrever uma norma, um cuidado ou uma lei que o
      fornecedor não citou é inventar um fato. Não são a mesma coisa, e a
      licença de fazer a primeira não é licença de fazer a segunda.
    * **Nunca invente um número que não veio.** Dimensão em branco continua
      em branco — não estime o tamanho da caixa a partir do tipo de material.
      Deduzir a escala de um número existente é permitido; criar o número não.
    * **Aplique o MESMO fator às três medidas.** Comprimento em mm e largura
      em cm na mesma caixa é sinal de que você errou a leitura, não de que o
      fornecedor misturou unidades no mesmo campo.
    * **Na dúvida genuína entre duas hipóteses plausíveis,
      fique com o número como veio.** A dedução existe contra o absurdo, não
      contra o meramente incerto — e "absurdo" aqui é ordem de grandeza, e
      não gosto pessoal.
    * ⚠️ **NÃO ARREDONDE. O campo do portal não tem limite de casas decimais**
      (confirmado pelo usuário e pelo HTML do campo em 2026-08-19:
      `maxlength="30"`, sem máscara) — se a conversão der "0,0000000001", é
      isso que vai. Cortar casas é perder informação que a ficha trouxe.
    * Retorne os valores como strings **contendo apenas o número puro**, sem a unidade (ex: "10,5", "50"). Use vírgula como separador decimal.
    * **Formato do Zero:** valor menor que 1 vai **COM o zero à esquerda** (ex: 0.75 -> "0,75"). ⚠️ A regra anterior mandava OMITIR o zero, e ela foi removida em 2026-08-19: o portal repõe o zero sozinho ao salvar, então o que ele guarda é "0,75" de qualquer jeito — mandar ",75" só criava diferença entre o que se pede e o que se lê de volta.

4.  **'controle_temperatura':**
    * Interprete o texto de entrada (ex: "SIM, manter de 15 a 30 graus") para preencher a estrutura de saída. Interpretar é ler o que está escrito — não é deduzir faixa que o fornecedor não informou.
    * `necessidade`: Deve ser apenas "SIM" ou "NÃO".
    * `climatizacao`: Se houver dados de temperatura, `ativo`=true. `temp_max`/`temp_min` devem ser em **Graus Celsius (°C)**.
    * `umidade`: Se houver dados de umidade, `ativo`=true. `hr_max`/`hr_min` devem ser em **Porcentagem (%)**.
    * Se `necessidade`="NÃO", `climatizacao.ativo` e `umidade.ativo` devem ser `false` e os valores de temp/umidade devem ser strings vazias.
    * Se a entrada exige controle mas **não diz os limites**, `ativo`=false e os valores ficam vazios. Não estime faixa.

5.  **'posicao_armazenamento':** Padronize o texto de entrada para "Vertical", "Horizontal", ou "Indiferente". Se o texto não corresponder a nenhum dos três (ou vier vazio), devolva **"Indiferente"** — é a opção que não impõe exigência nenhuma, e o portal precisa de uma das três.

6.  **'nocivo':**
    * `status`: Interprete o texto de entrada para "Nocivo" ou "Não contém". Baseie-se **apenas no texto recebido**.
    * `cuidado_es` / `cuidado_pt`: Aplique a Regra Mestra de Tradução ao campo 'cuidado' do input.

7.  **'peso':**

    O portal grava em **quilogramas (kg)**. Mesma estrutura da regra 3:
    unidade declarada vence; unidade ausente, deduza.

    **7.1 — Unidade DECLARADA:**

          "210 g"    ->  "0,21"     (g -> kg: dividir por 1000)
          "0,210 kg" ->  "0,21"
          "12,5 kg"  ->  "12,5"
          "1,4 t"    ->  "1400"     (t -> kg: multiplicar por 1000)

    **7.2 — Unidade AUSENTE:** o aferidor é o mesmo da regra 3, invertido —
    agora as dimensões são o lado firme e o peso é o que está sendo julgado.
    Calcule a densidade tratando o número como kg:

    - saiu **absurdamente ALTA** (acima de ~8 g/cm³) ⇒ o número estava em
      **gramas**: divida por 1000.
    - saiu **absurdamente BAIXA** para um equipamento de metal ⇒ considere
      **tonelada**: multiplique por 1000.
    - saiu na faixa ⇒ já estava em kg, não mexa.

    O tipo de material fecha a decisão: um relé não pesa 250 kg, e uma bobina
    de cabo de 500 m não pesa 250 g.

    **EXEMPLO — veio em gramas**

        Descrição: "DISJUNTOR CAIXA MOLDADA 100 A"
        Entrada:   peso líquido "2000"
                   caixa já deduzida: 30 × 20 × 15 cm = 9.000 cm³

        hipótese kg: 2.000 ÷ 9.000 × 1000 = 222 g/cm³
                     ← impossível: 28× a densidade do aço
        hipótese g:  2 ÷ 9.000 × 1000 = 0,22 g/cm³      ← plausível ✅

        Saída: peso líquido "2"

    **7.3 — Coerência entre os dois pesos:** o peso líquido **nunca** é
    maior que o bruto — o bruto inclui a embalagem. Se a sua conversão
    produzir isso, você trocou a unidade de um dos dois: refaça. Se a ficha
    traz só um deles, converta o que existe e deixe o outro vazio; não
    estime o que falta.

    * Vale aqui tudo da regra 3.4: a dedução é só da unidade, número que não
      veio não se inventa, e na dúvida genuína fica como veio.
    * ⚠️ **NÃO ARREDONDE**: o campo não tem limite de casas decimais.
    * Retorne como string, usando vírgula como separador decimal.
    * **Formato do Zero:** valor menor que 1 vai **COM o zero à esquerda** (ex: 0.26 -> "0,26"). ⚠️ A regra anterior mandava OMITIR o zero, e ela foi removida em 2026-08-19: o portal repõe o zero sozinho ao salvar, então o que ele guarda é "0,26" de qualquer jeito — mandar ",26" só criava diferença entre o que se pede e o que se lê de volta.

8.  **'sujeito_intemperie':** Padronize para "SIM" ou "NÃO", conforme o texto recebido.

9.  **'protecao':** Extraia os códigos ("SN", "UV", "EL") do texto de entrada. Retorne uma lista. Se o texto não traz nenhum, retorne lista vazia — este campo é de marcação e aceita nenhuma marca.

10. **'empilhamento':** Extraia o valor numérico (quantidade) do texto. Retorne como string. Sem número no texto, string vazia.

11. **'outros_cuidados':**
    * `status`: Interprete o texto de entrada para "SIM" ou "NÃO".
    * `cuidado_es` / `cuidado_pt`: Aplique a Regra Mestra de Tradução ao campo 'cuidados' do input.

12. **Campos de Texto Único (Transporte, Manutenção, Descarte):**
    * `embalagem_transp` -> `embalagem_transp_es`, `embalagem_transp_pt`
    * `posicao_icagem` -> `posicao_icagem_es`, `posicao_icagem_pt`
    * `cuidad_preserv` -> `cuidad_preserv_es`, `cuidad_preserv_pt`
    * `limpeza_secagem` -> `limpeza_secagem_es`, `limpeza_secagem_pt`
    * `ferramentas` -> `ferramentas_es`, `ferramentas_pt`
    * `legislacao` -> `legislacao_es`, `legislacao_pt`
    * `descarte` -> `descarte_es`, `descarte_pt`
    * ⚠️ **Estes campos são TRADUÇÃO PURA.** Entrada genérica ("Seguir legislação local", "Verificar normas", "Conforme lei", "Sucata") é traduzida **exatamente como está**. É terminantemente proibido substituí-la por texto técnico, citar leis, normas ou números de regulamento, ou descrever a "prática correta" para o tipo de material. Entrada vazia ⇒ `_es`: "No aplicable", `_pt`: "Não aplicável" (o portal recusa vazio).

13. **'perigoso_10004':**
    * Padronize para "SIM" ou "NÃO" a partir **do que a entrada diz**. Ex.: "CLASSE 1: PERIGOSO" -> "SIM"; "CLASSE 2: NÃO PERIGOSO" -> "NÃO". Isto é leitura, não correção.
    * ⚠️ **NÃO reclassifique por conta própria.** Se o fornecedor escreveu "NÃO", devolva "NÃO" — mesmo que o material lhe pareça perigoso pela descrição. Essa avaliação é de quem confere a ficha, não sua.

14. **'logistica_reversa':**
    * `status`: Interprete para "SIM", "NÃO", ou "Não se aplica", conforme o texto recebido.
    * `logistica_reversa_es` / `logistica_reversa_pt`: Aplique a Regra Mestra de Tradução.
    * Não altere o `status` com base no que você concluiu em outro campo.

15. **COERÊNCIA: relate mentalmente, não reescreva.**
    * Entradas contraditórias entre si (ex: `perigoso_10004`="SIM" com `logistica_reversa`="NÃO") **são preservadas como vieram**.
    * A versão anterior destas instruções mandava "IGNORAR a entrada do usuário" e preencher com conhecimento próprio de engenharia. **Isso está revogado**: produziu fichas com normas inventadas, plausíveis e erradas, que ninguém pegava na conferência.
    * Contradição na ficha é problema do fornecedor, e quem decide é a pessoa que revisa. Seu papel é entregar fielmente o que ele escreveu.

---
**EXEMPLOS — o que FIDELIDADE significa na prática:**

**EXEMPLO 1 — texto genérico permanece genérico (regra 12)**

INPUT:
{
  "pmib_codigo": "4500063671.9999",
  "Descrição do material": "DISJUNTOR TRIPOLAR 250A",
  "legislacao": "N/A",
  "perigoso_10004": "CLASSE 1: PERIGOSO",
  "descarte": "Conforme legislação",
  "logistica_reversa": { "status": "SIM", "logistica_reversa": "Verificar com fabricante."}
}

OUTPUT CORRETO:
{
  "pmib_codigo": "4500063671.9999",
  "legislacao_es": "No aplicable",
  "legislacao_pt": "Não aplicável",
  "perigoso_10004": "SIM",
  "descarte_es": "Conforme la legislación",
  "descarte_pt": "Conforme legislação",
  "logistica_reversa": {
    "status": "SIM",
    "logistica_reversa_es": "Verificar con el fabricante.",
    "logistica_reversa_pt": "Verificar com fabricante."
  }
}

Note que "CLASSE 1: PERIGOSO" virou "SIM" (leitura da própria entrada), e que
"Conforme legislação" e "Verificar com fabricante." foram apenas traduzidos,
e o "N/A" do fornecedor saiu por extenso em cada idioma. **Nenhuma lei foi citada, porque nenhuma lei estava na entrada.**

**EXEMPLO 2 — o que NÃO fazer**

Para o mesmo input acima, seria ERRADO devolver:

  "descarte_pt": "O disjuntor deve ser descartado como resíduo eletroeletrônico,
                  conforme a Lei 12.305/2010 no Brasil e a Lei 3956/09 no
                  Paraguai, priorizando a logística reversa..."

Nada disso está na entrada. É invenção — ainda que soe correto e profissional.

**EXEMPLO 3 — contradição preservada (regra 15)**

INPUT:
{
  "pmib_codigo": "4500063671.2222",
  "Descrição do material": "ÓLEO LUBRIFICANTE ISO VG 68",
  "perigoso_10004": "CLASSE 2: NÃO PERIGOSO",
  "descarte": "",
  "logistica_reversa": { "status": "NÃO", "logistica_reversa": ""}
}

OUTPUT CORRETO:
{
  "pmib_codigo": "4500063671.2222",
  "perigoso_10004": "NÃO",
  "descarte_es": "No aplicable",
  "descarte_pt": "Não aplicável",
  "logistica_reversa": {
    "status": "NÃO",
    "logistica_reversa_es": "No aplicable",
    "logistica_reversa_pt": "Não aplicável"
  }
}

Note que os campos em branco viraram "No aplicable"/"Não aplicável", e não
texto técnico: o portal recusa vazio, mas isso não autoriza inventar conteúdo.

Óleo lubrificante provavelmente É perigoso, e o fornecedor provavelmente errou
— mas isso é conhecimento SEU, não da entrada. O campo sai "NÃO", o que estava
em branco sai "Não aplicável", e quem revisa a ficha decide.
--- FIM DOS EXEMPLOS ---
"""


def montar_condicoes_user(dados_api_input_json):
    """Prompt de usuário (user_prompt) da tarefa "condicoes" -- uma única
    linha no original. dados_api_input_json é a string JSON já
    serializada (json.dumps(dados_api_input, indent=2,
    ensure_ascii=False), calculado no backend -- ver docstring do
    módulo).
    """
    return f"Processar: {dados_api_input_json}"


# =============================================================================
# 4. upload_tech_specs_backend.TechSpecsProcessor._chamar_gemini_specs
#    tarefa "tech_specs"
# =============================================================================
# Antigo system_instruction (estático -- não interpola nada). Cópia byte a
# byte, incluindo a indentação de 8 espaços herdada do método original.
SYSTEM_TECH_SPECS = """
        Você é um assistente especialista em normalização de dados técnicos de engenharia.
        Sua tarefa é analisar características técnicas de materiais, comparar com definições de um padrão (PDM) e validar/corrigir as respostas, sem jamais utilizar acentuação nas respostas.

        === REGRAS DE INTEGRIDADE (PROIBIDO DUPLICAR E ALTERAR TIPOS) ===
        1. CHAVES ÚNICAS: O JSON final NÃO PODE, sob nenhuma hipótese, conter características duplicadas. Cada 'CARACTERISTICA_CHAVE' deve aparecer EXATAMENTE UMA VEZ na lista final. Se houver redundância, consolide os dados e mantenha apenas um item.
        2. OBEDIÊNCIA ESTRITA AO TIPO DE DADO: Respeite rigorosamente o 'TIPO_DADO' fornecido na entrada. Se o sistema informou que "VAZAO MAXIMA" é 'NUM', você NUNCA deve alterar para 'CHAR' no JSON. Se a entrada bruta for "max. 80 l/min", como o tipo é 'NUM', você deve extrair APENAS O NÚMERO ("80") e retornar o TIPO intacto como 'NUM'.

        === REGRAS DE FORMATAÇÃO (DECIMAIS E LISTAS) - MUITO IMPORTANTE ===
        1. SEPARADOR DECIMAL: Para valores numéricos (NUM ou INT) com casas decimais, você DEVE utilizar OBRIGATORIAMENTE a VÍRGULA (,) como separador decimal, e NUNCA o ponto (.).
           - Exemplo Correto: "0,86" | "10,26".
           - Exemplo Incorreto: "0.86" | "10.26".
        2. SEPARADOR DE LISTA: Se a resposta pertencer ao tipo LISTA e contiver múltiplos itens selecionados, você DEVE usar PONTO E VÍRGULA (;) para separá-los. NUNCA use vírgula para separar itens, pois a vírgula é exclusiva para decimais.
           - Exemplo Correto: "A; B; E; F".

        === REGRA DE CONVERSÃO DE UNIDADES (SÍMBOLOS) ===
        Para campos do tipo 'NUM' ou 'INT', o sistema fornece as unidades aceitas no campo 'SIMBOLO_UNIDADE' (ex: "AD, m³/h, m³/s").
        - Compare a unidade de medida informada na 'RESPOSTA_CRUA_PT' com as opções válidas.
        - Se a unidade for diferente, você DEVE realizar a conversão matemática correta para uma das unidades válidas (Ex: se a entrada for "171 l/min" e o sistema aceitar "m³/h", você fará o cálculo e retornará "10,26").
        - Coloque APENAS O NÚMERO convertido em 'RESPOSTA_PT_FINAL'.
        - Coloque a UNIDADE VÁLIDA correspondente no campo 'SIMBOLO'.

        === REGRA GLOBAL DE RETENÇÃO E EXCLUSÃO ===
        Sua prioridade MÁXIMA é NÃO perder dados técnicos. Leia o 'TEXTO_AJUDA' fornecido para entender o contexto da característica. Se a 'RESPOSTA_CRUA_PT' contiver qualquer informação que responda ao que é pedido (ex: "classe H", "aço", "NBR"), você DEVE adequar o dado e definir ACAO = "PREENCHER".

        POR OUTRO LADO, se a resposta indicar CLARAMENTE que a característica NÃO SE APLICA, é inexistente ou totalmente vazia, você DEVE definir ACAO = "REMOVER".
        Termos considerados como "Não Aplicável":
        - "NA", "N/A", "N.A", "N.A.", "N/D"
        - "Não aplicável", "Não se aplica", "Sem aplicação"
        - "Inexistente", "Não possui"
        - Traços simples ou duplos: "-", "--", "---"
        - "Idem", "Vide X" (Se não for possível resolver)

        Se a resposta cair na regra de exclusão acima, ignore as regras de tipo abaixo e force a remoção.

        REGRAS DE PROCESSAMENTO POR TIPO:
        1. CHAR (Texto):
           - Verifique se não está em branco. Se estiver vazio, ACAO = "REMOVER".
           - O campo RESPOSTA_ES é obrigatório apenas aqui.
           - SÍMBOLO deve ser sempre "AD".

        2. INT (Intervalo):
           - O campo 'SUBTIPO_INTERVALO' é OBRIGATÓRIO.
           - Analise o contexto (Pergunta e Texto de Ajuda) para escolher EXATAMENTE uma das opções: ["MINIMO / MAXIMO", "DE / PARA", "INICIO / FIM", "LIMITE INFERIOR / LIMITE SUPERIOR", "LIMITE BAIXO / LIMITE ALTO", "MARGEM INFERIOR / MARGEM SUPERIOR", "MAIOR A / MENOR A", "DESDE / ATE"]. Use "MINIMO / MAXIMO" como padrão.
           - RESPOSTA_PT_FINAL deve conter os dois valores separados por barra "/" (ex: "10,5 / 20,8"). E o valor menor deve ser indicado como MINIMO, DE, LIMITE INFERIOR, LIMITE BAIXO, MARGEM INFERIOR, MAIOR A, DESDE e o valor maior como MAXIMO, LIMITE ALTO, LIMITE SUPERIOR, MENOR A, MARGEM SUPERIOR, ATE e outras palavras que indiquem que é quantitativamente maior.

        3. NUM (Numérico Único):
           - Aceita apenas um valor (Lembre-se da regra da vírgula para decimais).
           - Se a resposta tiver múltiplos valores, escolha o mais representativo (pior caso ou nominal). Não adicione textos descritivos (como "max", "min", "ate") na resposta, apenas o valor numérico.

        4. LISTA (Seleção):
           - A resposta DEVE ser baseada nos valores presentes no campo 'VALORES_POSSIVEIS_MASTER'.
           - Lembre-se: múltiplos valores devem ser separados por ponto e vírgula (;).

        SAÍDA ESPERADA (JSON):
        Retorne um JSON puro contendo uma lista de objetos:
        [
            {
                "CARACTERISTICA_CHAVE": "Nome da característica (limpo)",
                "TIPO": "CHAR" | "INT" | "NUM" | "LISTA",
                "VALORES_PT": "...", (Preenchido se tipo LISTA)
                "SUBTIPO_INTERVALO": "MINIMO / MAXIMO" (ou null),
                "RESPOSTA_PT_FINAL": "...",
                "RESPOSTA_ES_FINAL": "...",
                "SIMBOLO": "Unidade (Ex: V, A, mm, m³/h)",
                "ACAO": "PREENCHER" ou "REMOVER"
            }
        ]
        """


def montar_tech_specs_user(contexto_json_serializado):
    """Prompt de usuário (prompt_user) da tarefa "tech_specs".
    contexto_json_serializado é a string JSON já serializada
    (json.dumps(contexto_json, indent=2, ensure_ascii=False), calculado
    no backend -- ver docstring do módulo).

    Texto idêntico ao antigo prompt_user, com uma única mudança textual
    autorizada pelo checkpoint: a expressão que chamava json.dumps(...)
    direto virou uma referência a contexto_json_serializado -- resultado
    em runtime é byte-idêntico (o f-string sempre embutiu
    str(json.dumps(...)), só o LOCAL onde isso é calculado mudou).
    """
    return f"""
        Analise os dados abaixo referentes a um material técnico.
        Execute as regras de normalização e retorne o JSON solicitado.

        DADOS DE ENTRADA:
        {contexto_json_serializado}
{CONTRATO_SAIDA_TECH_SPECS}"""


# -----------------------------------------------------------------------------
# Reforço de contrato de saída — acrescentado em 2026-08-11
# -----------------------------------------------------------------------------
# Motivo: até aqui o formato de saída era descrito UMA vez, no meio do
# `SYSTEM_TECH_SPECS`, e o prompt de usuário terminava nos dados. Isso bastava
# enquanto todo o sistema rodava em Gemini; assim que o primeiro lote rodou em
# outro modelo, a resposta veio embrulhada em `{"items": [...]}` e com quase
# todo campo renomeado (`RESPOSTA_NORMALIZADA_PT` em vez de
# `RESPOSTA_PT_FINAL`), quebrando o RPA.
#
# O que este bloco faz, e por que cada parte existe:
#
#  - fica no FIM do prompt de usuário, que é a posição de maior peso para a
#    maioria dos modelos -- o schema deixa de competir com 60 linhas de regras
#    de negócio pela atenção do modelo;
#  - PROÍBE explicitamente o envelope e as cercas de markdown. "Retorne um
#    JSON puro contendo uma lista" era lido por alguns modelos como permissão
#    para embrulhar; agora o caso está nomeado;
#  - lista os nomes de chave como uma lista literal, e diz que são os únicos
#    aceitos. O bloco de exemplo do system prompt usa `|` e comentários entre
#    parênteses (não é JSON válido), o que convida o modelo a "melhorar" os
#    nomes;
#  - traz um exemplo COMPLETO e VÁLIDO, com um item de cada ação -- exemplo
#    executável vale mais que descrição;
#  - fixa a invariante de contagem (uma característica de entrada -> um item
#    de saída), que é também um ganho de QUALIDADE: era comum o modelo omitir
#    características que não soube tratar, e omissão silenciosa é
#    indistinguível de "não precisava mexer".
CONTRATO_SAIDA_TECH_SPECS = """
        ===============================================================
        FORMATO DA RESPOSTA — ESTA PARTE NAO E NEGOCIAVEL
        ===============================================================
        Responda com um ARRAY JSON no nivel raiz. Comece com [ e termine
        com ]. Nada antes, nada depois.

        PROIBIDO:
          - Envolver o array em um objeto. NAO use {"items": [...]},
            {"resultado": [...]}, {"caracteristicas": [...]} nem nada
            parecido. A resposta COMECA com [.
          - Cercas de markdown (```json ou ```).
          - Qualquer texto explicativo antes ou depois do array.

        REGRAS DE VALOR QUE JA FALHARAM NA PRATICA -- leia antes de
        preencher qualquer campo:

        1. PORCENTAGEM CONTINUA PORCENTAGEM. Se a ficha diz "56%" e o campo
           tem SIMBOLO "%", a resposta e "56", NAO "0,56". Nunca converta
           porcentagem em fracao: o portal ja mostra o simbolo % ao lado.

        2. O SIMBOLO E UMA LISTA FECHADA. Use SOMENTE um dos simbolos que
           vierem em SIMBOLO_UNIDADE daquela caracteristica. Se o valor da
           ficha estiver em outra unidade, CONVERTA o numero para uma das
           unidades permitidas (ex.: campo aceita "AD, kPa" e a ficha diz
           "3 MPa" -> resposta "3000", SIMBOLO "kPa"). Se nao houver
           conversao possivel para nenhuma unidade da lista, devolve o valor
           como esta e usa o primeiro simbolo da lista -- nunca invente um
           simbolo fora dela.

        3. CASAS DECIMAIS. CASAS_DECIMAIS diz quantas casas o campo aceita.
           Nao devolva mais casas que isso.

        4. LISTA: a resposta TEM de ser uma das opcoes de
           VALORES_POSSIVEIS_MASTER (PT) e, no campo ES, a opcao
           correspondente de VALORES_POSSIVEIS_ES -- na MESMA posicao da
           lista. Nao traduza a opcao por conta propria: o portal so aceita o
           texto exato de uma das opcoes, e um texto proximo nao seleciona
           nada.

        5. NA DUVIDA ENTRE PREENCHER E REMOVER, PREENCHA. Uma linha
           preenchida a mais o revisor apaga em 5 segundos; um dado do
           fornecedor que virou REMOVER some sem deixar rastro.

        CHAVES: use EXATAMENTE estes nomes, sem traduzir, sem abreviar e
        sem inventar variantes:
          CARACTERISTICA_CHAVE, TIPO, VALORES_PT, SUBTIPO_INTERVALO,
          RESPOSTA_PT_FINAL, RESPOSTA_ES_FINAL, SIMBOLO, ACAO

        Nomes como RESPOSTA_NORMALIZADA_PT, SIMBOLO_UNIDADE ou TIPO_DADO
        estao ERRADOS na saida: TIPO_DADO e nome de campo da ENTRADA, e
        na saida ele se chama TIPO.

        ACAO aceita exatamente dois valores: "PREENCHER" ou "REMOVER".
          - "PREENCHER" exige CARACTERISTICA_CHAVE, TIPO, RESPOSTA_PT_FINAL,
            RESPOSTA_ES_FINAL e SIMBOLO preenchidos.
          - "REMOVER" exige so CARACTERISTICA_CHAVE e ACAO.

        CONTAGEM: cada caracteristica de CARACTERISTICAS na entrada gera
        UM item na saida, na mesma ordem. Nao omita nenhuma. Se nao souber
        o que fazer com uma, devolva ACAO "REMOVER".

        EXEMPLO COMPLETO DE RESPOSTA VALIDA (copie a forma, nao o conteudo):
        [
          {
            "CARACTERISTICA_CHAVE": "TENSAO NOMINAL",
            "TIPO": "NUM",
            "VALORES_PT": "",
            "SUBTIPO_INTERVALO": null,
            "RESPOSTA_PT_FINAL": "440",
            "RESPOSTA_ES_FINAL": "440",
            "SIMBOLO": "V",
            "ACAO": "PREENCHER"
          },
          {
            "CARACTERISTICA_CHAVE": "NORMAS TECNICAS APLICAVEIS",
            "ACAO": "REMOVER"
          }
        ]
        """


def montar_tech_specs_correcao(mensagem_de_erro, contexto_json_serializado):
    """Prompt da SEGUNDA tentativa, quando a 1ª resposta não passou na
    validação de `tech_specs.normalizar_resposta_specs`.

    Reapresentar o mesmo prompt não adiantaria -- o modelo tende a repetir a
    mesma interpretação. O que muda o resultado é mostrar o ERRO CONCRETO:
    modelos corrigem formato com facilidade quando sabem exatamente o que
    saiu errado, e isso vale para qualquer provedor, o que é justamente o
    ponto (o app não pode depender de um modelo específico acertar de
    primeira).

    O contexto vai junto de novo porque a chamada é sem estado: o provedor
    não guarda a conversa anterior.
    """
    return f"""
        Sua resposta anterior foi RECUSADA pelo sistema que a consome.

        Motivo exato da recusa:
        {mensagem_de_erro}

        Corrija e responda de novo, com os MESMOS dados de entrada abaixo.
        Nao peca desculpas, nao explique: devolva apenas o array JSON.

        DADOS DE ENTRADA:
        {contexto_json_serializado}
{CONTRATO_SAIDA_TECH_SPECS}"""


# =============================================================================
# 5. autospec_backend.AutoSpecCore.generate_ai_response
#    tarefa "autospec"
# =============================================================================
def montar_autospec(txt_brv, fab, desc_comp, context, desc_list_texto):
    """Preâmbulo do prompt de geração de respostas técnicas (RAG).
    txt_brv/fab/desc_comp/context = dados do material e contexto
    recuperado (documentos locais + web); desc_list_texto = a lista de
    campos faltantes já formatada e concatenada pelo laço que continua em
    autospec_backend.generate_ai_response (consulta GENERATIVE_FIELDS,
    constante daquele módulo -- fica lá para este módulo não precisar
    importar de autospec_backend, ver docstring do módulo).

    Texto idêntico ao antigo preâmbulo de prompt em autospec_backend.py;
    a concatenação final com o texto de desc_list é reproduzida aqui
    como o retorno deste f-string somado a desc_list_texto -- mesmo
    resultado byte a byte.
    """
    return f"""
        Você é um Assistente Técnico Industrial.
        DADOS: Nome: {txt_brv} | Descrição: {desc_comp} | Fab: {fab}

        CONTEXTO:
        {context if context else "Nenhuma informação disponível."}

        INSTRUÇÕES:
        1. Priorize "LOCAL DOC".
        2. Verifique se o documento bate com o material.
        3. Campos [INFO TÉCNICA PADRÃO]: Se não houver dados, GERE com base em boas práticas.
        4. Campos [ESTRITO]: Se não houver dados, deixe vazio "".
        5. 'empilhamento': Apenas números inteiros.
        6. Checkboxes: Deduza a melhor opção se não explícito.
        7. Para CADA campo, informe de onde tirou a resposta em "fonte":
           o nome do arquivo em "LOCAL DOC", a URL em "WEB DOC", ou
           "conhecimento tecnico" quando deduziu por boas praticas.

        CAMPOS A PREENCHER (Retorne JSON {{ID: {{"valor": Resposta, "fonte": Origem}}}}):
        """ + desc_list_texto


# =============================================================================
# 8. traducao_pdm.motor_padrao  --  tarefa "traduzir_pdm"  (2026-08-28)
# =============================================================================
def montar_traduzir_pdm(textos, glossario=None):
    """Traduz PT->EN as perguntas de um PDM Modificado, em lote.

    Nasce aqui, e nao junto do servico, pela mesma regra dos outros sete: o
    TEXTO de todo prompt do SIG-FT mora neste arquivo desde o CP 3.5.

    Duas decisoes que estao no texto e valem explicacao:

    - **lote com indice**, e nao uma chamada por frase. Sao frases curtas; o
      lote e o que torna a IA mais barata E mais rapida que o Google Tradutor
      (que cobra 1 segundo de espera por item). O indice existe para a
      resposta poder ser conferida contra a entrada -- `_traduzir_com_ia`
      recusa a resposta se vierem menos traducoes que textos.
    - **o glossario entra como vocabulario OBRIGATORIO.** E o unico jeito de
      "corrigiu uma vez, vale sempre" funcionar de verdade: sem isso o modelo
      alterna entre sinonimos entre uma rodada e outra, e a ficha do fornecedor
      muda de vocabulario sem ninguem ter mudado nada.
    """
    linhas_glossario = ""
    if glossario:
        pares = "\n".join(f'  "{pt}" -> "{en}"' for pt, en in glossario.items())
        linhas_glossario = (
            "\nVOCABULARIO OBRIGATORIO (use EXATAMENTE estas traducoes onde os termos "
            f"aparecerem):\n{pares}\n"
        )

    numeradas = "\n".join(f"{i}. {t}" for i, t in enumerate(textos, start=1))
    return f"""Você é tradutor técnico de português do Brasil para inglês, especializado em documentação de materiais sobressalentes de usinas hidrelétricas.

Traduza as {len(textos)} linhas abaixo. Cada uma é o nome de uma característica técnica que um fornecedor vai preencher numa ficha, geralmente seguida da unidade entre parênteses.

REGRAS:
1. Traduza para o inglês técnico usado em datasheet de fabricante, não para o inglês corrente.
2. PRESERVE a unidade entre parênteses exatamente como está (bar, mm, kg, l/min, V, A, °C não mudam).
3. PRESERVE códigos, normas e designações (ISO 4406, NBR 10004, IP65, DN50) sem traduzir.
4. NÃO acrescente, não explique e não numere: devolva só a tradução de cada linha.
5. Se a linha já estiver em inglês, devolva-a inalterada.
{linhas_glossario}
LINHAS:
{numeradas}

Responda APENAS com JSON, sem ```json e sem texto antes ou depois, no formato:
{{"traducoes": ["tradução da linha 1", "tradução da linha 2", "..."]}}

A lista deve ter exatamente {len(textos)} itens, na mesma ordem das linhas.
"""
