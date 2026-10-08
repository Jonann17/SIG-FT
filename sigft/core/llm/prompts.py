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
# Os exemplos do `categorizar_pdm`, por CÓDIGO (2026-10-08).
#
# O título que vai no exemplo sai do catálogo carregado na hora (ver
# `montar_exemplos_categorizar_pdm`): um exemplo com título errado ensina o
# formato de fabricar título, e foi exatamente o defeito que a reescrita de
# 2026-09-22 corrigiu. `pdm_conferido` é o título conferido no Master naquela
# data, e só vale quando não há catálogo (os testes de conteúdo). Os dois
# exemplos sem `pdm_conferido` vêm dos casos reais do usuário e só entram com
# o catálogo -- o título exato deles nunca foi visto no repositório.
EXEMPLOS_CATEGORIZAR_PDM = [
    {
        "rotulo": "Mecânico -- o genérico vence quando nada confirma o específico",
        "codigo": "PDM.4320.007",
        "pdm_conferido": "PDM.4320.007 - BOMBA",
        "descricao_original": "Bomba KSB 123-ABC",
        "descricao_breve": "BOMBA - KSB 123-ABC",
        "por_que": ("a descrição não diz se é centrífuga, hidráulica ou de vácuo.\n"
                    "  Escolher `BOMBA HIDRAULICA` seria afirmar algo que ninguém disse."),
    },
    {
        "rotulo": "Câmera -- a nota da classe vence a semelhança de nome",
        "codigo": "PDM.5836.000",
        "pdm_conferido": "PDM.5836.000 - CAMERA VIDEO",
        "descricao_original": "CAMERAS DOME FIZ AXIS P1375-E",
        "descricao_breve": "CAMERA - P1375-E",
        "por_que": ("é câmera de rede/vídeo. A classe 6720 é de câmeras FOTOGRÁFICAS e\n"
                    "  a 6710 exclui câmeras de vídeo remetendo à 5836."),
    },
    {
        "rotulo": "Rede -- o modificador desempata",
        "codigo": "PDM.5895.016",
        "pdm_conferido": "PDM.5895.016 - VOIP GATEWAY",
        "descricao_original": "Cisco Analog Voice Gateway VG420 - 144FXS",
        "descricao_breve": "VOICE GATEWAY - VG420-144FXS",
        "por_que": ("existe também `PDM.5895.017 - GATEWAY`, mais genérico; aqui a\n"
                    "  descrição CONFIRMA que é de voz."),
    },
    {
        "rotulo": "Rede -- a descrição não nomeia o equipamento",
        "codigo": "PDM.5895.003",
        "pdm_conferido": "PDM.5895.003 - SWITCH",
        "descricao_original": "IE4010 w/ 12GE SFP, 12GE Copper PoE+ & 4GE SFP uplink ports",
        "descricao_breve": "SWITCH - IE-4010-16S12P",
        "por_que": ("nenhuma palavra da descrição diz \"switch\". As portas de uplink e o\n"
                    "  PoE+ dizem. É o caso em que a pré-seleção falha e a lista completa resolve."),
    },
    {
        "rotulo": "Peça descrita pela aplicação -- a Regra A vence a marca",
        "codigo": "PDM.5930.012",
        "pdm_conferido": None,
        "descricao_original": "PLAQUETA EM ALUMINIO PARA VALVULA DUPLOMATIC",
        "descricao_breve": "PLAQUETA - VALVULA DUPLOMATIC",
        "por_que": ("a peça é a plaqueta; \"VALVULA DUPLOMATIC\" diz a que ela serve. A\n"
                    "  Duplomatic faz válvulas, mas não fez esta peça: a marca aqui é da aplicação."),
    },
    {
        "rotulo": "Sinônimo -- a característica confirma",
        "codigo": "PDM.6685.017",
        "pdm_conferido": None,
        "descricao_original": "DISPLAY CRISTAL LIQUIDO 20X2 BACKLIGHT VERDE",
        "descricao_breve": "DISPLAY LCD 20X2",
        "por_que": ("nenhuma palavra do título aparece na descrição, mas um display de\n"
                    "  cristal líquido é um indicador digital, e o PDM tem a característica\n"
                    "  CARACTERISTICAS DO DISPLAY, que confirma."),
    },
    {
        "rotulo": "Cabo",
        "codigo": "PDM.6145.011",
        "pdm_conferido": "PDM.6145.011 - CABO TRANSMISSAO DADOS",
        "descricao_original": "5 ft LOW LOSS CABLE ASSEMBLY W/N CONNECTORS",
        "descricao_breve": "CABO ACCESS POINT - AIR-CAB005LL-N",
        "por_que": "",
    },
    {
        "rotulo": "TI",
        "codigo": "PDM.7010.018",
        "pdm_conferido": "PDM.7010.018 - SERVIDOR",
        "descricao_original": "Servidor Dell PowerEdge C6600",
        "descricao_breve": "SERVIDOR - POWEREDGE C6600",
        "por_que": "",
    },
]


def montar_exemplos_categorizar_pdm(pdm_por_codigo=None):
    """O bloco de exemplos do `categorizar_pdm`.

    `pdm_por_codigo(codigo) -> str | None` devolve o PDM COMPLETO do catálogo
    carregado ("PDM.4320.007 - BOMBA"), ou `None` se o código não está lá --
    e aí o exemplo sai. Sem ele (testes, catálogo dublado), valem os
    `pdm_conferido`, e os exemplos sem título conferido ficam de fora.
    A numeração acompanha os exemplos que entraram, sem buraco."""
    blocos = []
    for exemplo in EXEMPLOS_CATEGORIZAR_PDM:
        if pdm_por_codigo is not None:
            completo = pdm_por_codigo(exemplo["codigo"])
        else:
            completo = exemplo["pdm_conferido"]
        if not completo:
            continue
        linhas = [
            f"Exemplo {len(blocos) + 1} ({exemplo['rotulo']}):",
            f"- Descrição original: {exemplo['descricao_original']}",
            f"- PDM: {completo}",
            f"- Descrição breve: {exemplo['descricao_breve']}",
        ]
        if exemplo["por_que"]:
            linhas.append(f"- Por quê: {exemplo['por_que']}")
        blocos.append("\n".join(linhas))
    return "\n\n".join(blocos)


def montar_categorizar_pdm(instrucoes, lista_pdms, itens_texto, exemplos_texto=None):
    """Prompt de classificação em lote de itens em PDMs.

    - `instrucoes`: o manual de regras (classes FSC com INCLUI / NÃO INCLUI /
      NOTAS), já **podado** às classes que têm PDM -- ver
      `CatalogoPDM.manual_de_regras`;
    - `lista_pdms`: o catálogo inteiro **agrupado por classe FSC** -- ver
      `CatalogoPDM.lista_por_classe`. Ele é a rede: nem toda descrição tem
      palavra que nomeie o equipamento;
    - `itens_texto`: o bloco `### ITEM N` de cada item, **com os candidatos
      pré-filtrados** e as características de cada um -- montado por
      `GeminiCategorizer._formatar_itens`.

    REESCRITO EM 2026-09-22, a pedido do usuário
    ------------------------------------------------------------------------
    O texto anterior (no histórico do git, e na fixture antiga) tinha três
    defeitos medidos contra o catálogo real de 1193 PDMs:

    1. **Dois dos oito exemplos few-shot apontavam para PDMs errados.**
       `PDM.4020.001 - BOMBA CENTRIFUGA` não existe -- nem o código, nem o
       título, sob nenhum código. `PDM.6145.011 - CABO, TRANSMISSAO DADOS`
       tem uma vírgula que o título real não tem, e é essa string que vai
       ser digitada no filtro do portal. Um terceiro, a câmera, apontava a
       classe 6720 ("CÁMARAS FOTOGRÁFICAS") para uma câmera de rede,
       contrariando a nota da própria classe 6710, que remete câmeras de
       vídeo à 5836 -- esse é julgamento de catalogação, não erro de fato.
       Exemplo few-shot é o sinal mais forte de um prompt: ensinar um código
       fabricado é ensinar o formato de fabricar código.

       ⚠️ O exemplo do servidor (`PDM.7010.018 - SERVIDOR`) chegou a ser
       "corrigido" para `PDM.7010.014 - COMPUTADOR` e foi REVERTIDO no mesmo
       dia: ele estava certo. Quem errou foi o leitor do catálogo, que pegava
       o título da PRIMEIRA linha do código em vez do da revisão VIGENTE --
       e na revisão 0 esse PDM se chamava "SERVIDOR CONSOLE". A lição fica
       registrada aqui porque ela é a do módulo inteiro: **título de revisão
       antiga não filtra nada no portal**, e o erro se parece com um acerto.
    2. **O elo entre o manual e a lista nunca era dito.** O processo mandava
       "ache a classe no manual, depois escolha o PDM daquela classe", e a
       lista plana não dizia a classe de ninguém -- apesar de o código
       embuti-la (`PDM.XXXX.YYY`).
    3. **O manual descrevia 41 classes sem nenhum PDM** (165 no manual, 124
       com PDM). Armadilha ativa: a IA raciocinava até a classe e não havia
       o que escolher lá.

    O contrato de JSON **não mudou** -- mesmas 7 chaves, mesmos valores
    permitidos -- porque `app/views/cria_fichas.py` e
    `services/cria_fichas.processar_item_individual` leem campo a campo por
    nome. O que mudou de responsabilidade é o `item_processado`: ele deixou
    de ser decorativo e passou a ser a CHAVE de casamento da resposta com o
    item (antes era a posição na lista, e um item pulado pela IA deslocava
    todas as linhas seguintes em silêncio).

    A indentação de 8 espaços por linha, herdada do método original, foi
    removida: ela era artefato do f-string embutido, não escolha.

    REESCRITO EM 2026-10-08 -- duas passadas
    ------------------------------------------------------------------------
    Spec: docs/superpowers/specs/2026-10-08-escolha-de-pdm-em-duas-passadas-design.md.
    O item traz a "Interpretação" da passada 1; a resposta ganha confiança,
    alternativas, justificativa e as características que confirmam; NENHUM
    fica só para "PDM novo"; a Regra B cede à A quando a marca é da
    aplicação; a lista e os exemplos vêm ANTES do manual, para o prefixo ser
    igual em todos os blocos (cache); e os exemplos saem por código
    (`montar_exemplos_categorizar_pdm`). Os 7 campos de antes continuam
    iguais -- os novos são só acréscimo.
    """
    if exemplos_texto is None:
        exemplos_texto = montar_exemplos_categorizar_pdm()
    return f"""
Você é um especialista em catalogação de materiais (PDM) altamente preciso.
Sua tarefa é classificar uma *lista de itens*, escolhendo para cada um o PDM
correto de um catálogo fechado.

### COMO O CATÁLOGO É ORGANIZADO
Todo PDM tem a forma `PDM.XXXX.YYY`, onde **XXXX é o número da classe FSC** e
YYY é o sequencial dentro dela. Ou seja: o código já diz a classe. Use isso --
o "MANUAL DE REGRAS" abaixo é organizado pelas mesmas classes XXXX, então a
regra de uma classe vale para todos os PDMs cujo código começa com ela.

### DUAS REGRAS DE CATALOGAÇÃO QUE DECIDEM A MAIORIA DOS CASOS DIFÍCEIS

**REGRA A -- o PDM descreve O QUE A PEÇA É, não a que ela serve.**
Todo título de PDM é `NOME BASE` + `MODIFICADOR`, nessa ordem: o nome base diz
o que a peça É, e o modificador apenas qualifica. Quando a descrição traz uma
peça *de* um componente -- a carcaça de um acoplamento, a junta de uma bomba,
o eixo de um redutor, o suporte de um motor --, ela é catalogada pelo que ELA
é, nunca pelo componente que ela serve.

É o erro mais caro que existe aqui, porque a palavra do componente costuma ser
a mais chamativa da descrição. Exemplo real: `COUPLING LANTERN, WITH WIRE MESH
OPENING`, da NETZSCH (fabricante de bombas). A palavra "COUPLING" salta aos
olhos, mas a peça é a **lanterna**: a coluna flangeada que une o acionamento ao
corpo da bomba e aloja o acoplamento no meio, com tela de proteção. Ela não
transmite torque -- ela sustenta e protege o que transmite. O PDM certo é
`PDM.4320.031 - COLUNA FLANGE ACOPLAMENTO` (nome base COLUNA FLANGE,
modificador ACOPLAMENTO), e NÃO um dos PDMs de acoplamento da classe 3010.

As características confirmam quando há dúvida: a peça estrutural pede
QUANTIDADE DE FUROS, DISTANCIA ENTRE FACES, TIPO DE FACE; um acoplamento de
verdade pede TORQUE NOMINAL, ROTACOES MAXIMA, DESALINHAMENTO ANGULAR.

**REGRA B -- o fabricante DA PEÇA sugere a família (a Regra A vence).**
Quando a marca é de quem fabricou a própria peça, ela restringe a classe FSC:
NETZSCH faz bombas, SKF faz rolamento, AXIS faz câmera de rede, Cisco faz
equipamento de rede. Mas a marca muitas vezes nomeia o equipamento que a peça
SERVE, e não quem a fez: em "PLAQUETA EM ALUMINIO PARA VALVULA DUPLOMATIC", a
Duplomatic faz válvulas e a peça é uma plaqueta, não uma válvula. Marca que vem
depois de "PARA" ou "P/" descreve a aplicação; aí vale a Regra A.

### PROCESSO (para cada item)
1. Leia o item (Descrição, Marca/Modelo, Código do Material, Unidade) e a
   "Interpretação", quando houver: é o que uma leitura anterior do mesmo item
   disse que o material É, com sinônimos e a que ele serve. Aplique as regras
   A e B antes de olhar os candidatos.
2. Comece pelos "CANDIDATOS" daquele item. Eles vêm de duas buscas: uma pela
   interpretação e outra pelas palavras da descrição, e trazem a classe e as
   características de cada PDM. As características dizem o que aquele PDM
   descreve -- é o que separa irmãos parecidos (VALVULA ESFERA tem TIPO DE
   PASSAGEM e NUMERO DE VIAS; VALVULA GAVETA tem MATERIAL DA CUNHA).
3. Confira a escolha contra o "MANUAL DE REGRAS" da classe (o INCLUI e o
   NÃO INCLUI de uma classe vencem a semelhança de nome).
4. Se nenhum candidato servir, procure na "LISTA DE PDMS POR CLASSE". Os
   candidatos são uma ajuda, não um limite: quando a descrição não nomeia o
   equipamento (ex.: "IE4010 w/ 12GE SFP uplink ports", que é um switch), a
   pré-seleção não tem como acertar e a lista completa é o caminho.
5. Confirme pelas características: um PDM serve quando as características
   dele fazem sentido para o material. Liste em 'caracteristicas_que_confirmam'
   as que a descrição confirma.
6. Dê sempre o seu melhor palpite, com a confiança honesta. Um palpite com
   confiança BAIXA ajuda quem revisa, porque põe a pessoa na família certa;
   "NENHUM" obriga a procurar à mão entre todos os PDMs do catálogo.
7. Responda "NENHUM" só quando nenhum PDM do catálogo é sequer da família do
   material: é o caso em que um PDM novo precisa ser criado.

### REGRA DE LISTA FECHADA (a mais importante)
O valor de 'pdm_escolhido', e de cada PDM em 'alternativas', DEVE ser,
caractere por caractere, uma string que aparece **literalmente** na "LISTA DE
PDMS POR CLASSE" ou nos "CANDIDATOS" do item -- ou então "NENHUM". Não invente
código, não invente título, não monte um código novo a partir de dois que você
viu, e não conserte o que achar que está escrito errado. Se o PDM que você quer
não está na lista, ele não existe.

---
### LISTA DE PDMS POR CLASSE (ESCOLHA UM DESTES)
{lista_pdms}
---
### EXEMPLOS DE CLASSIFICAÇÃO CORRETA
(Guias de lógica. Todos os PDMs citados aqui existem no catálogo, mas a sua
escolha tem que sair da lista acima, não daqui.)

{exemplos_texto}

---
### MANUAL DE REGRAS (CLASSES FSC QUE TÊM PDM)
{instrucoes}
---
### ITENS PARA ANALISAR (EM LOTE):
{itens_texto}
---
### SUA TAREFA:
Analise CADA UM dos itens da lista "ITENS PARA ANALISAR".
Retorne um JSON contendo UMA LISTA de objetos, um por item, na MESMA ORDEM.

Formato da Resposta (Lista de JSON):
[
{{
    "item_processado": 1,
    "pdm_escolhido": "...",
    "confianca": "ALTA" | "MEDIA" | "BAIXA",
    "alternativas": [{{"pdm": "...", "motivo": "..."}}],
    "justificativa": "...",
    "caracteristicas_que_confirmam": ["..."],
    "descricao_curta": "...",
    "origem": "Importado" | "Nacional",
    "tipo de fabricação": "Catálogo" | "Especial",
    "tipo": "Reparável" | "Não Reparável",
    "unidade": "Unidade" | "Peça" | "Conjunto" | "metro - (m)" | "litro - (l)"
}},
{{
    "item_processado": 2,
    "pdm_escolhido": "...",
    "confianca": "...",
    "alternativas": [],
    "justificativa": "...",
    "caracteristicas_que_confirmam": [],
    "descricao_curta": "...",
    "origem": "...",
    "tipo de fabricação": "...",
    "tipo": "...",
    "unidade": "..."
}}
]

Regras para o JSON (para cada item):
1. 'item_processado': o NÚMERO DO ITEM, exatamente como aparece no cabeçalho
   "### ITEM N" daquele item. Não renumere e não pule: este número é o que
   liga a sua resposta ao material certo. Devolva um objeto para CADA item,
   mesmo os que você classificar como "NENHUM".
2. 'pdm_escolhido': o PDM COMPLETO, copiado literalmente da lista
   (ex: "PDM.1650.001 - ACUMULADOR"), ou "NENHUM".
3. 'confianca': "ALTA" quando a descrição (ou a interpretação) nomeia o
   material e as características do PDM confirmam; "MEDIA" quando a família
   está certa, mas a descrição não decide entre PDMs parecidos; "BAIXA" quando
   é o mais próximo que existe, mas pode haver PDM melhor. Com "NENHUM", use "".
4. 'alternativas': até 2 outros PDMs plausíveis, do mais para o menos provável,
   cada um copiado literalmente da lista e com o motivo em uma frase. Lista
   vazia se não houver outro plausível. Mesmo com "NENHUM", liste aqui os mais
   próximos, se houver.
5. 'justificativa': uma frase dizendo por que este PDM.
6. 'caracteristicas_que_confirmam': nomes de características do PDM escolhido,
   como aparecem nos CANDIDATOS, que a descrição confirma. Lista vazia se
   nenhuma.
7. 'descricao_curta': uma descrição de até 40 caracteres, sem acentuação.
8. 'origem': 'Importado' ou 'Nacional'.
9. 'tipo de fabricação': 'Catálogo' ou 'Especial'.
10. 'tipo': 'Reparável' ou 'Não Reparável'.
11. 'unidade': 'Unidade', 'Peça', 'Conjunto', 'metro - (m)' ou 'litro - (l)'.
    Se inconclusivo ou "NÃO ESPECIFICADA", use "Unidade".

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
        2. LISTA É ESCOLHA ÚNICA: no portal, a característica do tipo LISTA é um campo de seleção que aceita UMA opção só. Em 'VALORES_POSSIVEIS_MASTER' (e em 'VALORES_POSSIVEIS_ES') cada VÍRGULA separa uma opção da seguinte -- é o formato do PDM. A resposta é o texto de UMA dessas opções. NUNCA junte duas opções, nem com vírgula nem com ponto e vírgula.
           - Exemplo: 'VALORES_POSSIVEIS_MASTER' = "Borracha, Nylon, Teflon, etc." são QUATRO opções: "Borracha", "Nylon", "Teflon" e "etc.".
           - Resposta correta: "Nylon". Resposta errada: "Nylon, etc." (junta duas opções e não casa com nenhuma).

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
           - A resposta é EXATAMENTE UMA das opções de 'VALORES_POSSIVEIS_MASTER' (as opções vêm separadas por vírgula).
           - Se a ficha citar mais de uma opção, escolha a que melhor descreve o material. "etc." é uma opção como as outras quando aparece na lista: não a acrescente a outra opção.

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
           As opcoes vem separadas por VIRGULA: "Borracha, Nylon, etc." sao
           TRES opcoes ("Borracha", "Nylon" e "etc."). O campo do portal
           aceita UMA so. Resposta certa: "Nylon". Errada: "Nylon, etc." --
           junta duas opcoes e nao casa com nenhuma.

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


def montar_tech_specs_lista_unica(itens_json_serializados):
    """Prompt da pergunta DIRIGIDA sobre as LISTA (2026-09-28).

    Nasce do relato do usuário: a característica TIPO (LISTA) voltou como
    "Protecao contra descargas atmosfericas, etc." -- duas opções num campo
    do portal que seleciona UMA. `tech_specs.conferir_listas` acha esses casos
    na resposta; este prompt pergunta de novo SÓ sobre eles.

    Duas escolhas de desenho, e o porquê de cada uma:

    - só as características com problema, e não a ficha inteira (que é o que
      `montar_tech_specs_correcao` reenvia). Refazer as 40 respostas para
      corrigir uma poderia mexer nas 39 que estavam certas;
    - a resposta é o NÚMERO da opção, não o texto. Número não tem acento,
      grafia nem tradução para errar -- e é o código que converte o número no
      texto exato do Master, em PT e em ES.

    `itens_json_serializados`: o JSON já serializado, com a resposta recusada,
    o que o fornecedor escreveu e as opções numeradas de cada característica.
    """
    return f"""
        Nas caracteristicas abaixo, a sua resposta NAO e UMA opcao da lista:
        juntou duas opcoes, ou escreveu um texto que nao e nenhuma delas. No
        portal, o campo do tipo LISTA seleciona UMA opcao so.

        Para cada caracteristica, escolha a UNICA opcao que melhor descreve o
        material, lendo RESPOSTA_CRUA_PT e RESPOSTA_CRUA_ES (o que o
        fornecedor escreveu) e TEXTO_AJUDA. Se o fornecedor citou varias,
        escolha a principal. "etc." so quando nenhuma outra opcao servir.

        Responda pelo NUMERO da opcao, como aparece em OPCOES.

        CARACTERISTICAS:
        {itens_json_serializados}

        Responda com um ARRAY JSON no nivel raiz, um objeto por
        caracteristica, com exatamente as chaves CARACTERISTICA_CHAVE e
        NUMERO_DA_OPCAO. Nada antes, nada depois, sem cercas de markdown:
        [
          {{"CARACTERISTICA_CHAVE": "NOME DA CARACTERISTICA", "NUMERO_DA_OPCAO": 2}}
        ]
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

    REESCRITO EM 2026-09-24 (frente do AutoSpec -- zona compartilhada,
    commit isolado). O texto do CP 3.5 era a cópia byte a byte do prompt
    original; este é deliberadamente outro, e a fixture do snapshot foi
    regerada junto. Motivo, com os números: na comparação do usuário com o
    AMP (Gemini lendo o PDF inteiro) nas fichas 0084/0086/0088/0094, o AMP
    achou 78 informações e o AutoSpec 43. Quatro mudanças no texto:

    - pede a PROVA de cada valor (tipo, fonte, página, trecho literal,
      justificativa) -- é o que `autospec_evidencia` confere;
    - DEDUÇÃO permitida em campo técnico de TEXTO (material, norma, uso),
      marcada; NUNCA em número -- o único erro do AMP foi um número deduzido;
    - regras que faltavam: não trocar temperatura de operação por a do
      processo (erro da ficha 0084) nem rotação por frequência da rede
      (ficha 0094); documento que traz outro produto junto (ficha 0088);
      campo com lista de opções responde uma delas;
    - cota de desenho sem unidade segue a unidade do desenho.

    A concatenação com `desc_list_texto` no FIM continua igual.
    """
    return f"""Você é um engenheiro de especificação técnica. Preencha a ficha técnica de um material sobressalente de usina hidrelétrica (Itaipu) a partir dos documentos abaixo. A ficha vai para o cadastro oficial: cada valor precisa vir com a prova de onde saiu.

MATERIAL
- Nome: {txt_brv}
- Descrição: {desc_comp}
- Fabricante (planilha): {fab}

DOCUMENTOS
{context if context else "Nenhuma informação disponível."}

COMO LER
1. Leia os documentos por inteiro: tabelas, notas, desenhos cotados e gráficos contam. Cota de desenho sem unidade segue a unidade do desenho (normalmente mm).
2. Um documento pode cobrir outros modelos, ou até trazer outro produto junto. Use só o que é DESTE material (confira modelo, código, faixa). Se não der para saber qual linha é a dele, deixe o campo vazio.
3. Priorize "LOCAL DOC" (manual anexado pelo usuário) sobre "WEB DOC".
4. Não troque uma grandeza por outra parecida: temperatura de operação (ambiente) x temperatura do processo/fluido x temperatura de armazenamento; pressão de trabalho x pressão máxima ou de teste; corrente nominal x corrente de curto-circuito; rotação do motor x frequência da rede. Responda exatamente a que o campo pede.

COMO RESPONDER
5. Responda na unidade que o campo pede. Se o documento usa outra, converta, use "tipo": "calculo" e ponha o valor original no "trecho".
6. Campo que lista opções (no enunciado ou em "Escolha UMA"): responda exatamente uma delas. Se o documento não disser qual, escolha a mais provável para este tipo de material e use "tipo": "deducao".
7. Campos [ESTRITO] com MEDIDA (dimensão, peso, tensão, corrente, pressão, vazão, rotação, temperatura, potência, grau de proteção IP/NEMA): só o valor escrito no documento. Nunca deduza um número. Sem documento, deixe "".
8. Campos [ESTRITO] de TEXTO (material, norma, aplicação, uso, tipo construtivo, montagem, acoplamento): se o documento não disser, mas o tipo de equipamento tornar a resposta tecnicamente segura, responda com "tipo": "deducao" e explique em "justificativa". Se não for seguro, deixe "".
9. Campos [INFO TÉCNICA PADRÃO]: gere com base em boas práticas de armazenagem e manuseio deste tipo de material, com "tipo": "deducao".
10. 'empilhamento': só um número inteiro.

A PROVA
11. "trecho": copie LITERALMENTE do documento o pedaço de onde o valor saiu (até uns 200 caracteres), sem traduzir nem reescrever. Ele é conferido contra o documento: trecho que não existe invalida o valor.
12. "fonte": o nome do documento exatamente como aparece acima, ou "conhecimento tecnico" na dedução. "pagina": o número da página, quando houver.

Responda com um objeto JSON, uma entrada por ID pedido:
{{"ID": {{"valor": "...", "tipo": "documento" | "calculo" | "deducao", "fonte": "...", "pagina": 1, "trecho": "...", "justificativa": "..."}}}}

CAMPOS A PREENCHER:
""" + desc_list_texto


# =============================================================================
# 5b. autospec.AutoSpecCore.auditar_respostas_do_fornecedor
#     tarefa "autospec" (mesmo modelo do preenchimento)  --  2026-09-28
# =============================================================================
def montar_autospec_auditoria(txt_brv, fab, desc_comp, context, lista_texto):
    """Confere as respostas que o FORNECEDOR escreveu contra o datasheet.

    Pedido do Luan (2026-09-28): o fornecedor responde "nao se aplica" por
    desleixo, e a caracteristica esta no documento; e o valor preenchido pode
    divergir dele. Spec:
    docs/superpowers/specs/2026-09-28-autospec-conferencia-fornecedor-design.md.

    E um prompt SEPARADO do `montar_autospec` de proposito (decisao do
    usuario): o do preenchimento foi calibrado contra o AMP e continua byte a
    byte igual. Tres escolhas do texto:

    - a PROVA (valor, trecho, pagina) so em "diverge": "confere" volta numa
      palavra -- token de saida e o mais caro, e a maioria confere;
    - nada de deducao nem de conhecimento geral: o que sai daqui pode trocar
      o "nao se aplica" do fornecedor na ficha, e so com o documento;
    - unidade, traducao e formato diferentes nao sao divergencia (o app
      confere de novo com `autospec_auditoria.equivalentes`).

    `lista_texto` = as respostas ja formatadas por
    `autospec_auditoria.montar_lista`, concatenadas no FIM, como no
    preenchimento.
    """
    return f"""Você é um engenheiro de especificação técnica. O FORNECEDOR preencheu a ficha técnica de um material sobressalente de usina hidrelétrica (Itaipu). Confira cada resposta dele contra os documentos abaixo. Você não corrige a ficha: diz o que o documento traz para cada característica.

MATERIAL
- Nome: {txt_brv}
- Descrição: {desc_comp}
- Fabricante (planilha): {fab}

DOCUMENTOS
{context if context else "Nenhuma informação disponível."}

COMO CONFERIR
1. Use só o que está ESCRITO no documento e é DESTE material (confira modelo, código, faixa). Nunca deduza nem use conhecimento geral.
2. Compare a mesma grandeza que a pergunta pede: temperatura de operação x do processo x de armazenamento; pressão de trabalho x máxima ou de teste; corrente nominal x de curto-circuito; rotação do motor x frequência da rede.
3. "situacao":
   - "confere": o documento traz o mesmo valor. Unidade equivalente, tradução, arredondamento e formato diferentes NÃO são divergência (24 Vcc = 24 VDC; 0,5 kW = 500 W; Aço inox = Stainless steel).
   - "diverge": o documento traz OUTRO valor. Resposta "Não se aplica" (ou N/A, "não informado", "-") com o valor no documento também é "diverge": a característica se aplica.
   - "nao_consta": o documento não traz esta característica, ou não dá para saber qual linha é a deste material. Na dúvida, "nao_consta".

COMO RESPONDER
4. Em "confere" e "nao_consta", responda só a situação: {{"ID": {{"situacao": "confere"}}}}.
5. Em "diverge", traga a prova:
   - "valor_documento": o valor que o documento dá, na unidade que a pergunta pede (se converter, "tipo": "calculo");
   - "trecho": copie LITERALMENTE do documento o pedaço de onde o valor saiu (até uns 200 caracteres), sem traduzir nem reescrever. Trecho que não existe no documento invalida a divergência;
   - "fonte": o nome do documento exatamente como aparece acima; "pagina": o número da página, quando houver;
   - "justificativa": uma frase curta, só se a diferença não for óbvia.

Responda com um objeto JSON, uma entrada por ID:
{{"ID": {{"situacao": "confere" | "diverge" | "nao_consta", "valor_documento": "...", "tipo": "documento" | "calculo", "fonte": "...", "pagina": 1, "trecho": "...", "justificativa": "..."}}}}

RESPOSTAS DO FORNECEDOR A CONFERIR:
""" + lista_texto


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

    CORRECAO DE 2026-09-03, com os arquivos reais na mao
    ------------------------------------------------------------------------
    A primeira versao deste prompt dizia "cada linha e o nome de uma
    caracteristica tecnica, geralmente seguida da unidade entre parenteses", e
    mandava PRESERVAR o que estivesse entre parenteses. Isso foi escrito com
    exemplos que eu mesmo inventei -- "Pressao de trabalho (bar)".

    A forma real, vista nas fichas que o usuario entregou, e outra:

        9 - TIPO CONSTRUTIVO (Indicar o tipo construtivo do item. Nota:
        Material especifico de compra com (Numero de desenho, referencia,
        nome usual, outros)):

    O parenteses de fora carrega a INSTRUCAO INTEIRA, com parenteses aninhados
    dentro. A regra "preserve o que esta entre parenteses" aplicada a isso
    manda o modelo devolver a instrucao em portugues -- ficha meio traduzida.
    Nenhum teste da suite pegava, porque todos os exemplos eram meus e casavam
    com a suposicao errada. O exemplo trabalhado abaixo vem da ficha em ingles
    da propria Itaipu.
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

Traduza as {len(textos)} linhas abaixo. Cada uma tem a forma:

    NOME DA CARACTERÍSTICA EM MAIÚSCULAS (Instrução de preenchimento para o fornecedor)

O que está entre parênteses NÃO é uma unidade: é uma frase inteira de instrução, e ela também tem de ser traduzida. Dentro dela costuma haver parênteses aninhados — esses sim com unidades, exemplos de valor ou notas.

EXEMPLO (é assim que a Itaipu traduz, siga este estilo):
  PT: NORMAS TECNICAS APLICAVEIS (Indicar quais as normas técnicas aplicáveis ao item.)
  EN: APPLICABLE TECHNICAL STANDARDS (Indicate which technical standards apply to the item.)

REGRAS:
1. MANTENHA o nome da característica em MAIÚSCULAS, e a instrução entre parênteses em caixa normal, começando por verbo no imperativo ("Indicate...").
2. TRADUZA a instrução entre parênteses por inteiro. Deixá-la em português é o pior erro possível aqui: a ficha sai metade em cada idioma e ninguém percebe até o fornecedor reclamar.
3. PRESERVE unidades, números e exemplos de valor exatamente como estão: (V), (A), (mm), (°C), (l/min), 4-20mA, 0-5 V, M12, 1/2" UNF.
4. PRESERVE códigos, normas e designações (ISO 4406, ABNT NBR IEC 60749-1, NBR 10004, IP65, DN50) sem traduzir.
5. Convenções da casa: "Indicar" -> "Indicate"; "do item" -> "of the item"; "ex.:" e "ex:" -> "e.g."; "outros" -> "others"; "Nota:" -> "Note:".
6. Traduza para o inglês técnico de datasheet de fabricante, não para o inglês corrente.
7. NÃO acrescente, não explique e não numere: devolva só a tradução de cada linha.
8. Se a linha já estiver em inglês, devolva-a inalterada.
{linhas_glossario}
LINHAS:
{numeradas}

Responda APENAS com JSON, sem ```json e sem texto antes ou depois, no formato:
{{"traducoes": ["tradução da linha 1", "tradução da linha 2", "..."]}}

A lista deve ter exatamente {len(textos)} itens, na mesma ordem das linhas.
"""


# =============================================================================
# 9. services.cria_fichas.GeminiCategorizer.interpretar_lote
#    tarefa "interpretar_material"  (2026-10-08)
# =============================================================================
def montar_interpretar_material(itens_texto):
    """Passada 1 da escolha de PDM: o que cada material É, nas palavras de um
    catálogo, antes de qualquer busca.

    Existe porque a busca do catálogo é por PALAVRA, e a descrição do
    fornecedor muitas vezes não traz a palavra do PDM: "DISPLAY CRISTAL
    LIQUIDO" é um INDICADOR DIGITAL. Esta passada não recebe o catálogo -- é o
    que a torna barata --, e por isso não escolhe código: o que ela escreve
    vira a consulta da busca (`CatalogoPDM.candidatos_em_duas_frentes`).

    Spec: docs/superpowers/specs/2026-10-08-escolha-de-pdm-em-duas-passadas-design.md §4.1.
    """
    return f"""Você é um especialista em catalogação de materiais sobressalentes de usinas hidrelétricas.
Para cada item abaixo, diga o que o material É, com as palavras que um catálogo de materiais usaria. Você não vai escolher código nenhum: depois, uma busca no catálogo da Itaipu procura exatamente as palavras que você escrever aqui.

Para cada item, devolva:
- "e": o nome genérico do material, como um catálogo o chamaria: o substantivo da peça, seguido do que a qualifica, em maiúsculas, sem marca, sem modelo e sem medida. Ex.: "INDICADOR DIGITAL", "PLAQUETA INDICADORA", "VALVULA ESFERA", "SWITCH REDE".
- "sinonimos": até 4 outros nomes pelos quais o mesmo material é conhecido. Ex.: para um display de cristal líquido, "MOSTRADOR", "DISPLAY LCD", "VISOR DIGITAL".
- "serve": o equipamento a que a peça se destina, quando a descrição diz ("PARA VALVULA DUPLOMATIC" vira "VALVULA DUPLOMATIC"); string vazia quando não diz.

A regra mais importante: "e" é o que a peça É, nunca o equipamento que ela serve. Em "PLAQUETA EM ALUMINIO PARA VALVULA DUPLOMATIC", a peça é uma plaqueta; a válvula vai em "serve".

Quando a descrição não nomeia o material (ex.: "IE4010 w/ 12GE SFP uplink ports"), use o que você sabe sobre o modelo para dizer o que ele é ("SWITCH REDE").

### ITENS
{itens_texto}

### RESPOSTA
Responda APENAS com a lista JSON, um objeto por item, sem texto antes ou depois:
[
  {{"item": 1, "e": "...", "sinonimos": ["...", "..."], "serve": "..."}}
]
O valor de "item" é o número do cabeçalho "### ITEM N" daquele item.
"""
