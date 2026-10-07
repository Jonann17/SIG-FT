# -*- coding: utf-8 -*-
"""
Restaura a acentuacao do texto das notas do cofre.

O cofre nasceu sem acentos. Este script corrige o TEXTO, preservando o que nao
pode mudar:

  - blocos de codigo e trechos em `crase`
  - alvos de wikilink `[[assim]]` — os arquivos tem nome sem acento, e acentuar
    o alvo quebraria o link (o apelido depois do `|` e acentuado normalmente)
  - frontmatter YAML (tags e status sao identificadores)
  - URLs e alvos de link markdown
  - ancoras de cabecalho referenciadas por `[[nota#cabecalho]]`

Palavras ambiguas ficam de fora por principio: `esta` (verbo ou pronome) e `e`
(verbo ou conjuncao) so mudam em expressoes onde a leitura e inequivoca.

Uso:  python _scripts/acentua.py [--aplicar]
      sem --aplicar, so mostra o que mudaria.
"""
from __future__ import annotations

import collections
import pathlib
import re
import sys

VAULT = pathlib.Path(__file__).resolve().parent.parent

PALAVRAS = {
    # --- nucleo do dominio
    "aplicacao": "aplicação", "aplicacoes": "aplicações", "codigo": "código",
    "codigos": "códigos", "descricao": "descrição", "descricoes": "descrições",
    "secao": "seção", "secoes": "seções", "precos": "preços", "preco": "preço",
    "revisao": "revisão", "revisoes": "revisões", "gestao": "gestão",
    "modulo": "módulo", "modulos": "módulos", "tecnica": "técnica",
    "tecnicas": "técnicas", "tecnico": "técnico", "tecnicos": "técnicos",
    "condicoes": "condições", "condicao": "condição", "referencia": "referência",
    "referencias": "referências", "aprovacao": "aprovação", "emissao": "emissão",
    "caracteristicas": "características", "caracteristica": "característica",
    "criterio": "critério", "criterios": "critérios", "padrao": "padrão",
    "padroes": "padrões", "especificacao": "especificação",
    "especificacoes": "especificações", "codificacao": "codificação",
    "classificacao": "classificação", "identificacao": "identificação",
    "informacao": "informação", "informacoes": "informações",
    "manutencao": "manutenção", "medicao": "medição", "regulacao": "regulação",
    "aeracao": "aeração", "explosao": "explosão", "correcao": "correção",
    "correcoes": "correções", "intencao": "intenção", "autorizacao": "autorização",
    "validacao": "validação", "verificacao": "verificação", "situacao": "situação",
    "atualizacao": "atualização", "atualizacoes": "atualizações",
    "negociacao": "negociação", "elaboracao": "elaboração", "execucao": "execução",
    "producao": "produção", "operacao": "operação", "automacao": "automação",
    "automacoes": "automações", "localizacao": "localização",
    "organizacao": "organização", "apresentacao": "apresentação",
    "documentacao": "documentação", "implementacao": "implementação",
    "integracao": "integração", "migracao": "migração", "formatacao": "formatação",
    "posicao": "posição", "posicoes": "posições", "transicao": "transição",
    "transicoes": "transições", "divisao": "divisão", "supervisao": "supervisão",
    "previsao": "previsão", "dimensao": "dimensão", "conclusao": "conclusão",
    "decisao": "decisão", "decisoes": "decisões", "versao": "versão",
    "versoes": "versões", "sessao": "sessão", "questao": "questão",
    "questoes": "questões", "razao": "razão", "razoes": "razões",
    "funcao": "função", "funcoes": "funções", "acao": "ação", "acoes": "ações",
    "relacao": "relação", "relacoes": "relações", "excecao": "exceção",
    "excecoes": "exceções", "opcao": "opção", "opcoes": "opções",
    "atencao": "atenção", "pressao": "pressão", "impressao": "impressão",
    "permissao": "permissão", "regiao": "região", "adicao": "adição",
    "edicao": "edição", "uniao": "união",
    # --- palavras comuns
    "nao": "não", "sao": "são", "tambem": "também", "alem": "além", "ate": "até",
    "ja": "já", "apos": "após", "tres": "três", "sera": "será", "serao": "serão",
    "estao": "estão", "devera": "deverá", "deverao": "deverão", "podera": "poderá",
    "tera": "terá", "havera": "haverá", "ninguem": "ninguém", "alguem": "alguém",
    "porem": "porém", "contem": "contém", "mantem": "mantém", "voce": "você",
    "voces": "vocês", "numero": "número", "numeros": "números",
    "responsavel": "responsável", "responsaveis": "responsáveis",
    "nivel": "nível", "niveis": "níveis", "util": "útil", "uteis": "úteis",
    "unico": "único", "unica": "única", "unicos": "únicos", "unicas": "únicas",
    "possivel": "possível", "impossivel": "impossível", "visivel": "visível",
    "disponivel": "disponível", "automatizavel": "automatizável",
    "inicio": "início", "indice": "índice", "indices": "índices",
    "minimo": "mínimo", "maximo": "máximo", "proximo": "próximo",
    "proxima": "próxima", "ultimo": "último", "ultima": "última",
    "ultimos": "últimos", "ultimas": "últimas", "proprio": "próprio",
    "propria": "própria", "proprios": "próprios", "proprias": "próprias",
    "necessario": "necessário", "necessaria": "necessária",
    "obrigatorio": "obrigatório", "obrigatoria": "obrigatória",
    "usuario": "usuário", "usuarios": "usuários", "relatorio": "relatório",
    "relatorios": "relatórios", "formulario": "formulário",
    "comentario": "comentário", "comentarios": "comentários",
    "parametro": "parâmetro", "parametros": "parâmetros",
    "analise": "análise", "analises": "análises", "sintese": "síntese",
    "metodo": "método", "metodos": "métodos", "metrica": "métrica",
    "metricas": "métricas", "periodo": "período", "periodica": "periódica",
    "media": "média", "medias": "médias", "calculo": "cálculo",
    "calculos": "cálculos", "titulo": "título", "titulos": "títulos",
    "capitulo": "capítulo", "capitulos": "capítulos", "pagina": "página",
    "paginas": "páginas", "maquina": "máquina", "maquinas": "máquinas",
    "duvida": "dúvida", "duvidas": "dúvidas", "historico": "histórico",
    "memoria": "memória", "estrategia": "estratégia", "logica": "lógica",
    "pratica": "prática", "pratico": "prático", "basico": "básico",
    "publico": "público", "automatico": "automático", "automatica": "automática",
    "especifico": "específico", "especifica": "específica",
    "generico": "genérico", "numerico": "numérico", "ambiguo": "ambíguo",
    "continuo": "contínuo", "continua": "contínua", "multiplo": "múltiplo",
    "importancia": "importância", "distancia": "distância",
    "instancia": "instância", "ausencia": "ausência", "existencia": "existência",
    "evidencia": "evidência", "divergencia": "divergência",
    "dependencia": "dependência", "dependencias": "dependências",
    "pendencia": "pendência", "pendencias": "pendências", "urgencia": "urgência",
    "emergencia": "emergência", "frequencia": "frequência",
    "consequencia": "consequência", "sequencia": "sequência",
    "experiencia": "experiência", "transferencia": "transferência",
    "concluida": "concluída", "concluidas": "concluídas",
    "concluido": "concluído", "concluidos": "concluídos", "saida": "saída",
    "saidas": "saídas", "paineis": "painéis", "orfa": "órfã", "orfas": "órfãs",
    # --- segunda leva
    "solucao": "solução", "solucoes": "soluções", "discussao": "discussão",
    "discussoes": "discussões", "selecao": "seleção", "celula": "célula",
    "celulas": "células", "legivel": "legível", "ilegivel": "ilegível",
    "visao": "visão", "visoes": "visões", "reuniao": "reunião",
    "reunioes": "reuniões", "rotulo": "rótulo", "rotulos": "rótulos",
    "critica": "crítica", "criticas": "críticas", "critico": "crítico",
    "criticos": "críticos", "distincao": "distinção", "sistemico": "sistêmico",
    "sistemica": "sistêmica", "ligacao": "ligação", "ligacoes": "ligações",
    "comeca": "começa", "comecar": "começar", "comecou": "começou",
    "comecam": "começam", "recomendacao": "recomendação",
    "recomendacoes": "recomendações", "destroi": "destrói",
    "reconstroi": "reconstrói", "utilizavel": "utilizável",
    "varias": "várias", "varios": "vários", "so": "só", "le": "lê", "ve": "vê",
    "area": "área", "areas": "áreas", "historia": "história",
    "obvio": "óbvio", "obvia": "óbvia", "serio": "sério", "orgao": "órgão",
    "licao": "lição", "opiniao": "opinião", "formulas": "fórmulas",
    "formula": "fórmula", "alteracao": "alteração", "alteracoes": "alterações",
    "aceitacao": "aceitação", "notificacao": "notificação",
    "consolidacao": "consolidação", "priorizacao": "priorização",
    "valorizacao": "valorização", "padronizacao": "padronização",
    "normalizacao": "normalização", "agregacao": "agregação",
    "geracao": "geração", "criacao": "criação", "remocao": "remoção",
    "insercao": "inserção", "extracao": "extração", "deteccao": "detecção",
    "protecao": "proteção", "direcao": "direção", "instrucao": "instrução",
    "instrucoes": "instruções", "construcao": "construção",
    "distribuicao": "distribuição", "substituicao": "substituição",
    "atribuicao": "atribuição", "definicao": "definição",
    "definicoes": "definições", "repeticao": "repetição",
    "tensao": "tensão", "compreensao": "compreensão", "suspensao": "suspensão",
    "inversao": "inversão", "conversao": "conversão", "colisao": "colisão",
    "colisoes": "colisões", "explosoes": "explosões", "emissoes": "emissões",
    "comissao": "comissão", "transmissao": "transmissão", "missao": "missão",
    "expressao": "expressão", "compressao": "compressão", "sessoes": "sessões",
    "exclusao": "exclusão", "inclusao": "inclusão", "conclusoes": "conclusões",
    "extensao": "extensão", "precisao": "precisão", "previsoes": "previsões",
    "medicoes": "medições", "dimensoes": "dimensões", "expedicao": "expedição",
    "financeira": "financeira", "sugestao": "sugestão", "sugestoes": "sugestões",
    "questionavel": "questionável", "confiavel": "confiável",
    "rastreavel": "rastreável", "aceitavel": "aceitável",
    "defensavel": "defensável", "inevitavel": "inevitável",
    "estavel": "estável", "instavel": "instável", "variavel": "variável",
    "variaveis": "variáveis", "responsabilidade": "responsabilidade",
    "prioridade": "prioridade", "atipico": "atípico", "atipica": "atípica",
    "identico": "idêntico", "identica": "idêntica", "identicos": "idênticos",
    "quimica": "química", "dinamica": "dinâmica", "estatico": "estático",
    "grafico": "gráfico", "graficos": "gráficos", "tabela": "tabela",
    "coluna": "coluna", "ambito": "âmbito", "onus": "ônus",
    "criterioso": "criterioso", "silencio": "silêncio", "consorciadas": "consorciadas",
    "orfaos": "órfãos", "ancora": "âncora", "ancoras": "âncoras",
    "cronograma": "cronograma", "hifen": "hífen",
    # --- cedilha
    "servico": "serviço", "servicos": "serviços", "esforco": "esforço",
    "esforcos": "esforços", "comeco": "começo", "peca": "peça", "pecas": "peças",
    "cabecalho": "cabeçalho", "cabecalhos": "cabeçalhos", "licenca": "licença",
    "seguranca": "segurança", "mudanca": "mudança", "mudancas": "mudanças",
    "diferenca": "diferença", "diferencas": "diferenças", "presenca": "presença",
    "avanco": "avanço", "avancos": "avanços", "balanco": "balanço",
    # --- dominio tecnico
    "agua": "água", "oleo": "óleo", "fisica": "física", "fisico": "físico",
    "mecanica": "mecânica", "mecanico": "mecânico", "eletrica": "elétrica",
    "eletrico": "elétrico", "hidraulica": "hidráulica", "hidraulico": "hidráulico",
    "hidreletrica": "hidrelétrica", "tecnologica": "tecnológica",
    "tecnologico": "tecnológico", "consorcio": "consórcio", "serie": "série",
    "veiculo": "veículo", "ingles": "inglês", "portugues": "português",
    "armazem": "armazém", "valvula": "válvula", "valvulas": "válvulas",
}

# expressoes onde `esta` e `e` sao inequivocamente verbo
FRASES = [
    (r"\besta (em|no|na|nos|nas|com|sem|entre|acima|abaixo|la|ai|aqui)\b", r"está \1"),
    (r"\besta (certo|errado|pronto|pronta|vazio|vazia|feito|feita|sendo|aprovada|aprovado|fechado|fechada|aberto|aberta|correta|incompleta|completa|desatualizada|atualizada)\b", r"está \1"),
    (r"\bnao esta\b", "não está"), (r"\bja esta\b", "já está"),
    (r"\bnao e ", "não é "), (r"\bisso e ", "isso é "),
    (r"\bque e o ", "que é o "), (r"\bque e a ", "que é a "),
    (r"\bque e um ", "que é um "), (r"\bque e uma ", "que é uma "),
    (r"\bnao ha\b", "não há"), (r"\bha (mais de|menos de|meses|anos|dias|semanas)\b", r"há \1"),
]

MARCADOR = "\x00%d\x00"


def preserva(texto: str):
    """Troca por marcadores tudo o que nao pode ser tocado."""
    guardados = []

    def guarda(m):
        guardados.append(m.group(0))
        return MARCADOR % (len(guardados) - 1)

    padroes = [
        r"^---\n.*?\n---\n",        # frontmatter
        r"```.*?```",               # bloco de codigo
        r"`[^`\n]*`",               # trecho em crase
        r"\[\[(?!#)[^\]|]*",         # alvo do wikilink (o '#ancora' fica de fora:
                                    # cabecalho e ancora sao acentuados juntos)
        r"https?://\S+",            # url
        r"\]\([^)]*\)",             # alvo de link markdown
        r"\[![a-z]+\]",             # callout
    ]
    for p in padroes:
        texto = re.sub(p, guarda, texto, flags=re.S)
    return texto, guardados


def restaura(texto: str, guardados) -> str:
    for i, g in enumerate(guardados):
        texto = texto.replace(MARCADOR % i, g)
    return texto


def mesma_caixa(orig: str, novo: str) -> str:
    if orig.isupper():
        return novo.upper()
    if orig[0].isupper():
        return novo[0].upper() + novo[1:]
    return novo


def acentua(texto: str, contador) -> str:
    def troca(m):
        w = m.group(0)
        novo = PALAVRAS.get(w.lower())
        if not novo:
            return w
        contador[w.lower()] += 1
        return mesma_caixa(w, novo)

    texto = re.sub(r"\b[A-Za-z]+\b", troca, texto)
    for pat, rep in FRASES:
        texto, n = re.subn(pat, rep, texto, flags=re.I)
        if n:
            contador["(expressao) " + pat[:28]] += n
    return texto


def main() -> int:
    aplicar = "--aplicar" in sys.argv
    contador = collections.Counter()
    tocados = []

    for q in sorted(VAULT.rglob("*.md")):
        original = q.read_text(encoding="utf-8")
        corpo, guardados = preserva(original)
        corpo = acentua(corpo, contador)
        novo = restaura(corpo, guardados)
        if novo != original:
            tocados.append(q.relative_to(VAULT))
            if aplicar:
                q.write_text(novo, encoding="utf-8")

    print("%s — %d notas %s" % (
        "APLICADO" if aplicar else "SIMULACAO (use --aplicar)",
        len(tocados), "alteradas" if aplicar else "seriam alteradas"))
    print("total de substituicoes: %d\n" % sum(contador.values()))
    print("as 25 mais frequentes:")
    for w, n in contador.most_common(25):
        print("   %-34s %d" % (w, n))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
