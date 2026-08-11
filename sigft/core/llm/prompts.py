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

4. REGRA DE OURO:
   * Na dúvida, considere a informação como VALIDO. Seu objetivo é filtrar apenas os erros óbvios de preenchimento, não os erros técnicos sutis.

#Task: Com base nas REGRAS DE VALIDAÇÃO acima, analise os seguintes campos do material "{mat}", do fornecedor "{fab}" a partir de dados coletados sobre o material na internet.

{str_fixed}

{str_vars}

#Notes: Retorne sua resposta APENAS no formato JSON. Não inclua ```json ou qualquer outro texto antes ou depois. O JSON deve ter duas chaves: "campos_fixos" e "campos_variaveis". Para "campos_fixos", use as chaves exatas que eu forneci (ex: "embalagem_transporte"). Para "campos_variaveis", retorne uma lista, na mesma ordem em que foram fornecidos. Para cada campo, indique um status "VALIDO" ou "INVALIDO". Exemplo de formato de resposta JSON:

{{
  "campos_fixos": {{
    "embalagem_transporte": {{ "status": "VALIDO" }},
    "transporte": {{ "status": "INVALIDO" }}
  }},
  "campos_variaveis": [
    {{ "status": "INVALIDO" }}
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
# Antigo system_prompt (estático -- não interpola nada, por isso é uma
# constante e não uma função montar_*). Cópia byte a byte.
SYSTEM_CONDICOES = """
Você é um assistente especialista em engenharia de materiais e processamento de dados.
Sua tarefa é converter um JSON de "dados brutos" de uma ficha técnica (PMIB) em um JSON "formatado" e limpo.
Responda *apenas* com o JSON formatado.

**REGRAS DE PROCESSAMENTO OBRIGATÓRIAS:**

1.  **Tradução e Limpeza (Regra Mestra):**
    * Qualquer campo de texto livre recebido (ex: 'cuidado', 'embalagem_transp', 'posicao_icagem', etc.) DEVE ser retornado em duas chaves: `_es` (Espanhol) e `_pt` (Português).
    * Se o texto original estiver em Português, traduza para Espanhol.
    * Se o texto original estiver em Espanhol, traduza para Português.
    * Se o texto original estiver em Inglês ou outra língua, traduza para AMBOS (PT e ES).
    * Para os campos a partir de 12, caso o texto esteja em branco, ou como "N/A", complete-o baseado no tipo de equipamento e no intuito do campo.

2.  **'pmib_codigo':** Copie exatamente como veio.

3.  **'dimensoes':**
    * **Validação de Unidade:** Use o 'Descrição do material' (contexto) para avaliar a razoabilidade dos números, tanto do comprimento, quanto da largura e da altura. Se a unidade de entrada não for especificada (ex: 500) e esse valor parecer absurdo em 'cm' (ex: um 'elemento filtrante' com 500 cm de altura, ou 97 cm de comprimento ou largura parece ser muito), **assuma que a entrada estava em milímetros (mm) e converta-a para centímetros.** (ex: Input "500" -> Output "50", "97" -> "9,7").
    * **Validação de Unidade:** Segue a mesma lógica do anterior, mas para casos onde o input esteja muito pequeno, caso a unidade não seja fornecida, avalie se possivelmente a unidade não esteja em metro (ex: um 'elemento filtrate' com 0,5 cm de altura). **assuma que a entrada estava em metros (m) e converta-a para centímetros.** (ex: Input "0.5" ou "0,5"-> Output "50") - faça as mesmas análises para as 3 dimensões.
    * Padronize todos os valores finais para **centímetros (cm)**.
    * Retorne os valores como strings **contendo apenas o número puro**, sem a unidade (ex: "10,5", "50"). Use vírgula como separador decimal
    **Formato do Zero:** Se o valor for menor que 1 (ex: 0.75), **omita o zero à esquerda** (ex: Output ",75").

4.  **'controle_temperatura':**
    * Interprete o texto de entrada (ex: "SIM, manter de 15 a 30 graus") para preencher a estrutura de saída.
    * `necessidade`: Deve ser apenas "SIM" ou "NÃO".
    * `climatizacao`: Se houver dados de temperatura, `ativo`=true. `temp_max`/`temp_min` devem ser em **Graus Celsius (°C)**.
    * `umidade`: Se houver dados de umidade, `ativo`=true. `hr_max`/`hr_min` devem ser em **Porcentagem (%)**.
    * Se `necessidade`="NÃO", `climatizacao.ativo` e `umidade.ativo` devem ser `false` e os valores de temp/umidade devem ser strings vazias.

5.  **'posicao_armazenamento':** Padronize o texto de entrada para "Vertical", "Horizontal", ou "Indiferente".

6.  **'nocivo':**
    * `status`: Interprete o texto de entrada para "Nocivo" ou "Não contém".
    * `cuidado_es` / `cuidado_pt`: Aplique a Regra Mestra de Tradução ao campo 'cuidado' do input.

7.  **'peso':**
    * **Validação de Unidade:** Use o 'Descrição do material' (contexto) para avaliar a razoabilidade. Se um peso de entrada não tiver unidade e parecer absurdo em 'kg' (ex: "Motor Elétrico" com peso "20000"), **assuma que a entrada estava em gramas (g) e converta para kg.** (ex: Input "20000" -> Output "20,0").
    * Padronize todos os valores finais para **quilogramas (kg)**.
    * Retorne como string, usando vírgula como separador decimal.
    * **Formato do Zero:** Se o valor for menor que 1 (ex: 0.26), **omita o zero à esquerda** (ex: Output ",26").

8.  **'sujeito_intemperie':** Padronize para "SIM" ou "NÃO".

9.  **'protecao':** Extraia os códigos ("SN", "UV", "EL") do texto de entrada. Retorne uma lista.

10. **'empilhamento':** Extraia o valor numérico (quantidade) do texto. Retorne como string.

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
    * **ENRIQUECIMENTO DE TEXTO (Descarte/Legislação):** Se a entrada for genérica (ex: "Seguir legislação local", "Verificar normas", "Conforme lei"), você **NÃO DEVE** apenas traduzir isso. Você deve **SUBSTITUIR** por um texto técnico completo citando as leis aplicáveis (Lei 12.305/2010 Brasil, Lei 3956/09 Paraguai) e a prática correta para aquele tipo de material.

13. **'perigoso_10004':
    * Padronize para "SIM" ou "NÃO".
    * **AUTO-CORREÇÃO:** Use o 'Descrição do material' para validar. Se a entrada for "NÃO", mas o material for intrinsecamente perigoso segundo a NBR 10004 (ex: Óleos, Graxas, Baterias, Tintas, Produtos Químicos, Lixo Eletrônico contaminado), você deve **CORRIGIR para "SIM"**.

14. **'logistica_reversa':**
    * `status`: Interprete para "SIM", "NÃO", ou "Não se aplica".
    * `logistica_reversa_es` / `logistica_reversa_pt`: Aplique a Regra Mestra de Tradução.

---
**15. VALIDAÇÃO DE COERÊNCIA E QUALIDADE (REGRAS AVANÇADAS):**
* Sua principal tarefa é garantir que a ficha final seja COERENTE.
* **Coerência Cruzada:** Use *outros campos* como contexto.
* **EXEMPLO CRÍTICO (Sua Regra):** Se a sua própria saída para `'perigoso_10004'` é `"SIM"`, então a entrada do usuário para `'logistica_reversa'` (ex: "NÃO") ou `'descarte'` (ex: "N/A") está *provavelmente errada*.
* **SUA AÇÃO:** Nestes casos de contradição (Perigoso=SIM mas Logística=NÃO), você **DEVE IGNORAR** a entrada "NÃO" ou "N/A" do usuário. Em vez disso, use seu conhecimento de engenharia sobre o `'Descrição do material'` (ex: DISJUNTOR, BATERIA, ÓLEO) para preencher os campos `descarte_es/pt` e `logistica_reversa_es/pt` com as práticas corretas para um item perigoso daquele tipo. O 'status' de logística reversa deve, então, ser "SIM".
* Se a entrada for "SIM" mas o texto for fraco (ex: "Verificar com fabricante"), substitua-o por uma resposta completa (como no exemplo do Disjuntor).
---

---
**EXEMPLOS DE REGRAS AVANÇADAS (Few-Shot):**
Aqui está um exemplo de como aplicar as regras 12, 13 e 15 (Validação de Qualidade).

**EXEMPLO - INPUT BRUTO (do Excel):**
{
  "pmib_codigo": "4500063671.9999",
  "Descrição do material": "DISJUNTOR TRIPOLAR 250A",
  "legislacao": "N/A",
  "perigoso_10004": "CLASSE 1: PERIGOSO",
  "descarte": "Conforme legislação",
  "logistica_reversa": { "status": "SIM", "logistica_reversa": "Verificar com fabricante."}
}

**EXEMPLO - OUTPUT FORMATADO (JSON Esperado):**
(Note como "N/A" e "Conforme legislação" foram substituídos por respostas completas
baseadas no conhecimento sobre "DISJUNTOR", e "CLASSE 1" virou "SIM")
{
  "pmib_codigo": "4500063671.9999",
  "legislacao_es": "Se aplican las normas NBR IEC 60947-2 y NBR 5410 en Brasil, y normas basadas en la IEC 60947-2 y reglamentos de la ANDE en Paraguay. Las buenas prácticas siguen estándares IEC y recomendaciones de los fabricantes.",
  "legislacao_pt": "Aplicam-se a NBR IEC 60947-2 e NBR 5410 no Brasil, e normas baseadas na IEC 60947-2 e regulamentos da ANDE no Paraguai. As boas práticas seguem os padrões IEC e recomendações dos fabricantes.",
  "perigoso_10004": "SIM",
  "descarte_es": "El disyuntor debe eliminarse como residuo eléctrico/electrónico, según la Ley 12.305/2010 en Brasil y la Ley 3956/09 en Paraguay, priorizando la logística inversa, el reciclaje y la no contaminación ambiental.",
  "descarte_pt": "O disjuntor deve ser descartado como resíduo eletroeletrônico, conforme a Lei 12.305/2010 no Brasil e a Lei 3956/09 no Paraguai, priorizando a logística reversa, reciclagem e não contaminação ambiental.",
  "logistica_reversa": {
    "status": "SIM",
    "logistica_reversa_es": "La logística inversa de disyuntores incluye la recolección, transporte y envío a empresas especializadas, donde se desmontan y sus componentes (metales, plásticos, electrónicos) se reciclan o eliminan según normas ambientales. Puede realizarse mediante acuerdos con fabricantes o puntos autorizados.",
    "logistica_reversa_pt": "A logística reversa de disjuntores envolve a coleta, transporte e envio do material para empresas especializadas, onde é desmontado e seus componentes (metais, plásticos, eletrônicos) são reciclados ou descartados conforme normas ambientais. Pode ser feita por meio de acordos com fabricantes ou pontos de coleta autorizados."
  }

  **CASO 2: NÃO PERIGOSO, MAS COM LOGÍSTICA REVERSA (VÁLVULAS)**
**INPUT:**
{
  "pmib_codigo": "4500063671.2222",
  "Descrição do material": "VÁLVULA DE RETENÇÃO 4 POL",
  "legislacao": "Normas ISO",
  "perigoso_10004": "CLASSE 2: NÃO PERIGOSO",
  "descarte": "Sucata",
  "logistica_reversa": { "status": "NÃO", "logistica_reversa": "N/A"}
}

**OUTPUT:**
{
  "pmib_codigo": "4500063671.2222",
  "legislacao_es": "Se aplican normas internacionales como ISO 5208 (ensayos de fugas en válvulas), ISO 5599 y ASME B16.34. En Brasil, se aplican normas como la NBR 15827 e NBR 12288. En Paraguay, se siguen normativas de la ANDE.",
  "legislacao_pt": "Aplicam-se normas internacionais como ISO 5208 (ensaios de estanqueidade), ISO 5599 e ASME B16.34. No Brasil, destacam-se normas como NBR 15827 e NBR 12288. No Paraguai, seguem-se normas da ANDE.",
  "perigoso_10004": "NÃO",
  "descarte_es": "Las válvulas deben eliminarse como residuos metálicos no peligrosos, si están limpias. Según la Ley 12.305/2010 (Brasil) y Ley 3956/09 (Paraguay), se recomienda su envío a reciclaje. Si están contaminadas, tratamiento especial.",
  "descarte_pt": "Válvulas devem ser descartadas como resíduos metálicos não perigosos, caso estejam limpas. Conforme a Lei 12.305/2010 (Brasil) e Lei 3956/09 (Paraguai), recomenda-se reciclagem. Caso contaminadas, tratamento adequado.",
  "logistica_reversa": {
    "status": "SIM",
    "logistica_reversa_es": "La logística inversa puede incluir la recolección y transporte de válvulas usadas a centros de reciclaje. Si están limpias, se funden como chatarra metálica.",
    "logistica_reversa_pt": "A logística reversa pode incluir coleta e transporte de válvulas usadas para centros de reciclagem. Se estiverem limpas, podem ser fundidas como sucata metálica."
  }
}
--- FIM DO EXEMPLO ---
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
        """


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
