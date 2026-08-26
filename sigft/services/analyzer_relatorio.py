r"""Relatório do que faltou em cada ficha, para mandar ao FORNECEDOR.

POR QUE EXISTE
------------------------------------------------------------------------
Pedido do usuário (2026-08-26): terminada a análise de um lote, gerar um
`.xlsx` com uma linha por material — o código PMIB numa coluna, e na outra um
resumo do que estava faltando ou errado, com a justificativa de por que a
informação não serve. O arquivo vai para quem preencheu a ficha, como guia da
correção.

QUEM LÊ ISTO NÃO É ENGENHEIRO DO SIG-FT
------------------------------------------------------------------------
É o fornecedor. Daí duas decisões que atravessam o módulo inteiro:

1. **Rótulo, nunca a chave interna.** `peso_liquido` não quer dizer nada para
   quem preencheu; "Peso líquido (kg)" quer. Os rótulos abaixo são os nomes
   que o próprio usuário usou ao listar os campos obrigatórios.
2. **A justificativa da IA é repassada literalmente.** O prompt
   (`montar_validar_ficha`) manda escrevê-la em português e PARA O
   FORNECEDOR — reescrevê-la aqui só afastaria o texto de quem vai lê-lo.

Como `autospec_conferencia`, este módulo **não importa tkinter**: um teste
verifica por AST. A tela só escolhe onde salvar.
"""
import os

from sigft.core.rpa.ficha_layout import CONFIG_MAP

# Rótulos legíveis, na redação do próprio usuário (lista de campos
# obrigatórios de 2026-08-26). Um campo do CONFIG_MAP sem entrada aqui cairia
# no relatório como chave interna -- `test_todo_campo_do_CONFIG_MAP_tem_rotulo`
# existe para isso não acontecer em silêncio quando um campo novo entrar.
ROTULOS = {
    "texto_breve_material": "Texto Breve do Material",
    "unidade": "Un. medida de estoque",
    "tipo_fabricacao": "Tipo de Fabricação",
    "fabricante": "Fabricante",
    "origem": "Origem",
    "tipo": "Tipo",
    "comprimento_embalagem": "Comp. da embalagem unitária",
    "largura_embalagem": "Largura da embalagem unit.",
    "altura_embalagem": "Altura da embalagem unitária",
    "peso_liquido": "Peso líquido (kg)",
    "peso_bruto": "Peso bruto (kg)",
    "sujeito_intemperies": "Sujeito a intempéries?",
    "controle_temp_umidade": ("Necessidade de controle de temperatura e umidade? "
                              "(se sim, informe os valores máximos e mínimos ao lado)"),
    "posicao_armazenamento": "Posição de Armazenamento",
    "protecao": "Proteção",
    "nocivo": "Nocivo",
    "empilhamento": "Empilhamento",
    "embalagem_transporte": "Embalagem para transporte (indicar o TIPO e os cuidados)",
    "transporte": "Posições / Cuidados com içagem",
    "preservacao": "Cuidados durante a preservação",
    "metodo_limpeza": "Métodos de limpeza ou secagem",
    "ferramentas_para_preservacao": "Ferramentas e equipamentos para preservação",
    "tipo_legislacao": "Tipo de legislação e/ou Norma aplicada",
    "tipo_descarte": "Tipo de descarte segundo legislação aplicada",
    "classificacao_periculosidade": "Classificação conforme NBR 10004",
    "logistica_reversa": "Logística reversa",
}

CABECALHO = ("Código PMIB", "O que precisa ser corrigido", "Nota da análise")


class Achado:
    """Um problema numa ficha.

    `tipo`: `"vazio"` (não preenchido), `"invalido"` (a IA reprovou) ou
    `"nao_analisada"` (o aplicativo não conseguiu analisar a ficha inteira).
    `campo` é a chave do `CONFIG_MAP` ou, quando `especificacao=True`, a
    própria pergunta escrita na planilha — especificações técnicas não têm
    chave, o que as identifica é o enunciado.
    """

    def __init__(self, campo, tipo, motivo=None, obrigatorio=False, especificacao=False):
        self.campo = campo
        self.tipo = tipo
        self.motivo = motivo
        self.obrigatorio = obrigatorio
        self.especificacao = especificacao

    def rotulo(self):
        if self.especificacao:
            return str(self.campo)
        return ROTULOS.get(self.campo, self.campo)

    def __repr__(self):  # pragma: no cover - conveniência de depuração
        return f"<Achado {self.campo} {self.tipo}>"


def _frase(achado):
    if achado.tipo == "nao_analisada":
        return achado.motivo or "A ficha não pôde ser analisada."

    marca = " (obrigatório)" if achado.obrigatorio else ""
    if achado.tipo == "vazio":
        return f"{achado.rotulo()}{marca}: em branco, precisa ser preenchido."

    # invalido
    if achado.motivo:
        return f"{achado.rotulo()}{marca}: {achado.motivo}"
    # Modelo mais fraco pode ignorar o "motivo" que o prompt pede. Sem ele o
    # relatório perde a justificativa, mas não pode perder QUAL campo.
    return (f"{achado.rotulo()}{marca}: a informação preenchida não atende ao "
            "que o campo pede.")


def resumo(achados):
    """Todos os achados de UMA ficha, numa célula só."""
    return "\n".join(f"• {_frase(a)}" for a in (achados or []))


class RelatorioAnalise:
    """Acumula as fichas com pendência ao longo do lote.

    Estado deliberadamente burro, como a `Conferencia` do AutoSpec: a tela
    pergunta o que tem, manda salvar, e não decide nada.
    """

    def __init__(self):
        self._fichas = []

    def registrar(self, codigo_pmib, arquivo, nota, achados):
        """Guarda UMA ficha. Ficha sem achado não entra — relatório é lista de
        pendência, e listar quem está certo faz o fornecedor procurar o que
        não existe."""
        achados = list(achados or [])
        if not achados:
            return None
        identificacao = codigo_pmib or os.path.basename(str(arquivo or ""))
        registro = {"pmib": identificacao, "arquivo": arquivo,
                    "nota": nota, "achados": achados}
        self._fichas.append(registro)
        return registro

    @property
    def fichas(self):
        return list(self._fichas)

    def __bool__(self):
        return bool(self._fichas)

    def __len__(self):
        return len(self._fichas)

    def linhas(self):
        """`[(pmib, resumo, nota), ...]` — o conteúdo do `.xlsx`."""
        return [(f["pmib"], resumo(f["achados"]),
                 "" if f["nota"] is None else f"{f['nota']}%")
                for f in self._fichas]

    def salvar_xlsx(self, pasta_destino, nome=None):
        """Grava e devolve o caminho. `None` quando não há pendência.

        O `openpyxl` é importado AQUI dentro, e não no topo: assim o módulo
        continua importável (e testável) sem a dependência pesada, igual ao
        que `sigft/app/file_dialogs.py` faz com o tkinter.
        """
        if not self._fichas:
            return None
        import datetime

        import openpyxl

        nome = nome or ("RELATORIO_ANALISE_" +
                        datetime.datetime.now().strftime("%Y-%m-%d_%H%M%S") + ".xlsx")
        os.makedirs(pasta_destino, exist_ok=True)
        caminho = os.path.join(pasta_destino, nome)
        sufixo = 2
        while os.path.exists(caminho):
            base = nome[:-5] if nome.lower().endswith(".xlsx") else nome
            caminho = os.path.join(pasta_destino, f"{base}_{sufixo}.xlsx")
            sufixo += 1

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Pendencias"
        ws.append(list(CABECALHO))
        for linha in self.linhas():
            ws.append(list(linha))

        # A coluna do resumo tem várias linhas por célula; sem largura e sem
        # quebra de texto o arquivo chega ilegível a quem vai usá-lo.
        try:
            from openpyxl.styles import Alignment, Font

            for celula in ws[1]:
                celula.font = Font(bold=True)
            ws.column_dimensions["A"].width = 22
            ws.column_dimensions["B"].width = 90
            ws.column_dimensions["C"].width = 14
            for linha in ws.iter_rows(min_row=2):
                linha[1].alignment = Alignment(wrap_text=True, vertical="top")
        except Exception:
            pass  # formatação é conforto; o dado já está gravado

        wb.save(caminho)
        return caminho
