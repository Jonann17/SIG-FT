"""Os textos do "Como funciona" de cada tela, num lugar só (2026-10-28).

Ideia trazida do Corella Automation (v1.4.0, *"a interface não está muito
explicativa para novos usuários"*); desenho em
`docs/superpowers/specs/2026-10-28-ajuda-para-quem-comeca-design.md`, parte 1.

Logo abaixo do título de cada tela, sempre no MESMO lugar: uma frase curta,
sempre visível, e o botão "Como funciona", que abre de 3 a 6 itens: o que a tela
espera receber, o que ela muda (o portal? a planilha? só gera arquivo?) e o que
acontece se parar no meio. O widget é `sigft/app_qt/widgets/como_funciona.py`.

Os textos saíram da `docs/base-conhecimento/` de cada módulo e foram conferidos
contra o código: nada aqui promete o que a tela não faz. Mudou o comportamento
de uma tela? Mude o texto dela junto. O do AutoSpec é da frente do Rafael e saiu
do `08b-autospec-contexto-negocio.md`.

Sem Qt. Cada texto vai em `marcar()` (a tradução está em `sigft/app/idiomas/`);
quem mostra chama `traduzido(chave)`.
"""
from __future__ import annotations

from typing import NamedTuple

from sigft.app.idioma import marcar, t

# Um item mais longo que isto vira parágrafo, e o bloco deixa de ser lido de relance.
LIMITE_DO_ITEM = 140
MINIMO_DE_ITENS, MAXIMO_DE_ITENS = 3, 6
# O estado aberto/fechado, lembrado por tela (`prefs`): `como_funciona_aberto.<chave>`.
CHAVE_PREFERENCIA = "como_funciona_aberto"


class Texto(NamedTuple):
    frase: str
    itens: tuple[str, ...]


# A chave é a da tela no `catalogo` (`CriaFichas`); a das abas que têm regra
# própria é `<tela>.<aba>` (ver `ABAS_DAS_SECOES`).
TEXTOS: dict[str, Texto] = {
    "CriaFichas": Texto(
        marcar("Cria as fichas no portal PMIB a partir da lista de materiais do _STATUS_PMIB."),
        (
            marcar("Recebe o _STATUS_PMIB (aba Lista de Materiais), o Código do Projeto e a planilha "
                   "de PDMs da Itaipu."),
            marcar("A IA sugere o PDM de cada item e você revisa: o robô só cria o que foi confirmado "
                   "na revisão."),
            marcar("O robô abre o navegador e pede o login no portal. Num erro, ele para e pergunta o "
                   "que fazer."),
            marcar("Parou no meio? O que já foi criado fica no portal. O _STATUS_PMIB só muda no "
                   "passo 5, Salvar no Excel."),
            marcar("A aba Editar código do projeto troca esse código em massa, nas fichas que você "
                   "escolher."),
        ),
    ),
    "PDM": Texto(
        marcar("Monta as planilhas das fichas PMIB em branco, com as perguntas do PDM de cada material."),
        (
            marcar("Recebe a planilha de PDMs (SAM-GM), o _STATUS_PMIB, o template da ficha e a pasta "
                   "de destino."),
            marcar("Cada material ganha uma planilha com o nome do código PMIB e as características do "
                   "PDM dele."),
            marcar("Grava só na pasta de destino: não mexe no portal nem no _STATUS_PMIB."),
            marcar("Em English, a IA traduz as perguntas; a que não traduzir fica em português, com "
                   "aviso no console."),
            marcar("PDM que não está na planilha, ou sem característica: a ficha dele fica de fora e o "
                   "lote segue."),
        ),
    ),
    "Analyzer": Texto(
        marcar("Dá nota às fichas preenchidas e separa as que passam das que voltam ao fornecedor."),
        (
            marcar("Recebe as fichas (.xlsx), a pasta de saída e, se quiser, o _STATUS_PMIB, que dá a "
                   "descrição de cada material."),
            marcar("Abaixo da nota mínima, ou sem um campo obrigatório, a ficha reprova. Nota e pesos "
                   "ficam no passo 1."),
            marcar("A ficha original não muda: a cópia vai para FT_good, FT_bad (marcada com FORNECER) "
                   "ou FT_nao_concluidas."),
            marcar("FT_nao_concluidas é a ficha que não deu para analisar (IA fora do ar, sem "
                   "características)."),
            marcar("Depois do lote, GERAR RELATÓRIO PARA O FORNECEDOR (.xlsx) lista, por material, o "
                   "que precisa ser corrigido."),
        ),
    ),
    "UploadConditions": Texto(
        marcar("Preenche no portal as condições de armazenamento, transporte, manutenção e descarte."),
        (
            marcar("Recebe o _STATUS_PMIB e as fichas (.xlsx). A IA traduz e padroniza o que o "
                   "fornecedor escreveu, sem inventar."),
            marcar("Primeiro a IA gera um Excel com as condições em português e espanhol; depois o "
                   "robô as grava no portal."),
            marcar("Ficha já COMPLETO na coluna CONDIÇÕES é pulada, a menos que você ligue o Forçar "
                   "processamento."),
            marcar("O robô pede o login e só marca COMPLETO no _STATUS_PMIB quando as quatro seções "
                   "foram salvas."),
            marcar("Parou no meio? As fichas terminadas ficam marcadas; as outras ficam sem COMPLETO "
                   "e podem rodar de novo."),
        ),
    ),
    "Translator": Texto(
        marcar("Traduz as respostas das características das fichas do português para o espanhol."),
        (
            marcar("Recebe as fichas (.xlsx) e grava em cada uma a aba Especificações técnicas "
                   "copiar, que o Upload Specs lê."),
            marcar("A tradução roda neste computador: nenhuma resposta sai daqui. Gravar a aba pede "
                   "o Excel instalado."),
            marcar("Número, unidade, código e norma ficam como estão; o glossário corrige os termos "
                   "que se repetem."),
            marcar("PARAR AGORA para entre uma ficha e a outra: as já traduzidas ficam com a aba nova."),
            marcar("Ficha em inglês não é traduzida: ela falha, com o motivo no console."),
        ),
    ),
    "UploadSpecs": Texto(
        marcar("Preenche no portal as características técnicas das fichas, já traduzidas pelo Tradutor."),
        (
            marcar("Recebe o _STATUS_PMIB, a planilha de PDMs (SAM-GM) e as fichas com a aba "
                   "Especificações técnicas copiar."),
            marcar("A IA ajusta cada resposta ao tipo da característica no PDM e gera um JSON; o robô "
                   "o grava no portal."),
            marcar("Ficha já COMPLETO na coluna CARACT. TÉCNICAS é pulada, a menos que você ligue o "
                   "Forçar processamento."),
            marcar("O robô pede o login, confere o que o portal aceitou e lista no console o que fica "
                   "para fazer à mão."),
            marcar("Só a ficha que o portal confirmou é marcada COMPLETO no _STATUS_PMIB."),
        ),
    ),
    "CorrecaoPDM": Texto(
        marcar("Troca ou atualiza o PDM das fichas no portal sem perder as características."),
        (
            marcar("Recebe o _STATUS_PMIB; a planilha de PDMs (opcional) permite escolher o PDM novo "
                   "e ver a prévia."),
            marcar("Na troca o portal apaga todas as características: o robô as lê antes e repõe as "
                   "que o PDM novo também tem."),
            marcar("Só atualizar a revisão mantém o PDM e leva a ficha à revisão vigente dele."),
            marcar("No fim, o relatório lista o que não voltou. Conferir cada ficha antes de salvar "
                   "pede o seu OK em cada uma."),
        ),
    ),
    "CopiaFichas": Texto(
        marcar("Copia uma ficha que já está no portal para as fichas duplicadas dela."),
        (
            marcar("Recebe o _STATUS_PMIB: duplicada é a linha com PDM.9900.000 no PDM usado e a "
                   "ficha original em OBSERVAÇÕES."),
            marcar("Em Revisar / Editar Fichas você confere cada par e corrige a ficha original antes "
                   "do robô."),
            marcar("O robô pede o login e copia campos, condições, características, PDM, documentos e "
                   "imagens."),
            marcar("Cada coluna do _STATUS_PMIB só recebe COMPLETO se todas as seções dela deram "
                   "certo; o resto fica INCOMPLETO."),
            marcar("O log de auditoria guarda também a estrutura das telas, para investigar uma cópia "
                   "que falhou."),
        ),
    ),
    # Frente do Rafael: o texto saiu do `08b-autospec-contexto-negocio.md`.
    "AutoSpec": Texto(
        marcar("Preenche a ficha técnica vazia com dados de manuais em PDF e de datasheets achados na web."),
        (
            marcar("Recebe o _STATUS_PMIB, a ficha (.xlsx) e os manuais do material. Cada ficha da "
                   "fila é tratada sozinha."),
            marcar("Só preenche célula vazia ou com FORNECER: o que alguém já escreveu fica como está."),
            marcar("O que a automação escreve sai em azul, num arquivo novo _completed.xlsx: a ficha "
                   "original não muda."),
            marcar("Medida (dimensão, peso, tensão) só entra com prova no documento; sem ela, a "
                   "célula fica vazia."),
            marcar("Documento que cita só o fabricante ou só o código vai para a conferência: você "
                   "marca os que valem."),
        ),
    ),
    "LMR.upload": Texto(
        marcar("Cadastra no portal as aplicações (TAGs) das fichas, lidas de uma aba do Excel LMR."),
        (
            marcar("Recebe o Excel LMR; você escolhe a aba e as fichas. Colunas: FICHA PMIB, CÓDIGO "
                   "LMR e TAG LMR."),
            marcar("O robô pede o login e grava cada código LMR com as TAGs dele; só conta o que o "
                   "portal confirmou."),
            marcar("Com o _STATUS_PMIB escolhido, marca COMPLETO ou INCOMPLETO na coluna APLICAÇÃO - "
                   "LMR de cada ficha."),
            marcar("Parou no meio? Ligue Começar de um código específico e informe a posição (0 = 1º "
                   "código LMR da ficha); vale para todas as fichas."),
            marcar("Os códigos que falharam aparecem no console e vão para o erros_lmr.csv, em "
                   "Documentos\\SIG-FT\\logs, para conferir no portal."),
        ),
    ),
    "LMR.exclusao": Texto(
        marcar("Apaga no portal todas as aplicações LMR de uma ficha. Não tem volta."),
        (
            marcar("Recebe o código PMIB de uma ficha. O robô pede o login, abre a ficha e apaga até "
                   "a lista esvaziar."),
            marcar("Não há como desfazer: confira o código antes de INICIAR LIMPEZA."),
            marcar("Com o _STATUS_PMIB escolhido, limpa a coluna APLICAÇÃO - LMR das fichas apagadas "
                   "com sucesso."),
        ),
    ),
    "PMIBManager.gestao": Texto(
        marcar("Atualiza a mapeadora pelo Aconex e pelos _STATUS_PMIB, e calcula a situação de cada lista."),
        (
            marcar("Recebe o histórico do Aconex (DocManager), a pasta raiz dos _STATUS_PMIB e a "
                   "mapeadora de sobressalentes."),
            marcar("Grava nos _STATUS_PMIB a situação da autorização e os dias de atraso; na "
                   "mapeadora, o link, a situação e a revisão."),
            marcar("Arquivo aberto no Excel não grava: o SIG-FT diz qual é e deixa repetir ou seguir "
                   "sem ele."),
            marcar("Aplicar autorizações grava AUTORIZADO pelo export de Itaipu; Conferir no portal "
                   "procura o código SAP de cada ficha."),
            marcar("Gerar painel grava o Painel de Sobressalentes.html na pasta raiz, que abre no "
                   "navegador sem rede."),
        ),
    ),
    "PMIBManager.conferencia": Texto(
        marcar("Aponta as listas com a revisão em uso atrás da última emitida no Aconex e baixa os PDFs."),
        (
            marcar("Recebe a mapeadora e a pasta raiz dos _STATUS_PMIB, as mesmas da Gestão PMIB. A "
                   "mapeadora só é lida."),
            marcar("Rode a Gestão PMIB antes: a tela avisa quando a mapeadora não foi salva hoje."),
            marcar("Baixa o PDF da revisão nova e o da revisão em uso para a pasta de cada lista. "
                   "Nunca sobrescreve arquivo."),
            marcar("Sem conexão com o Aconex, as listas aparecem, mas nada é baixado: o console avisa."),
            marcar("A aba Revisão no AMP parte da última conferência feita aqui."),
        ),
    ),
    "PMIBManager.amp": Texto(
        marcar("Manda ao AMP, uma por vez, as listas marcadas da última conferência e guarda o que mudou "
               "num HTML."),
        (
            marcar("Pede uma conferência feita nesta sessão e o webhook do workflow, no botão Webhook… "
                   "desta aba."),
            marcar("As listas vêm todas marcadas; a que tem falta fica sem caixa. As que voltam com HTML se "
                   "desmarcam sozinhas."),
            marcar("O agente do AMP recebe os dois PDFs e o _STATUS_PMIB como estão e devolve o que mudou e as "
                   "ações no controle."),
            marcar("O HTML vai para a pasta da lista, sem sobrescrever. Nada muda no Excel: você confere e "
                   "aplica."),
            marcar("O console mostra cada passo, e o log de cada rodada fica em Documentos\\SIG-FT\\logs\\amp."),
            marcar("Falhou? Copiar diagnóstico leva o detalhe técnico, sem o texto dos documentos."),
        ),
    ),
    "PMIBManager.docpack": Texto(
        marcar("Cria a pasta, com os templates, de cada lista que ainda não tem _STATUS_PMIB."),
        (
            marcar("Lê a mapeadora: entram as listas sem link e sem _STATUS_PMIB na pasta raiz."),
            marcar("Capítulo, sistema e pasta final se editam com dois cliques; a IA pode sugerir."),
            marcar("Cada pasta ganha o _STATUS_PMIB, a lista com preço (PB021) e LMR, IMAGENS e DATASHEETS."),
            marcar("Nada é sobrescrito, e a mapeadora não muda: rode o Gestão PMIB depois para ligar."),
        ),
    ),
    "SearchPMIB": Texto(
        marcar("Procura um código ou descrição nos _STATUS_PMIB de uma pasta inteira, de uma vez."),
        (
            marcar("Recebe a pasta raiz: ela é varrida com as subpastas, em todo arquivo _STATUS_PMIB."),
            marcar("Direcionada procura só na coluna escolhida e é rápida; Generalista procura na "
                   "linha inteira."),
            marcar("A Generalista ignora acento, espaço e pontuação: ROLAMENTO 6205 acha "
                   "Rolamento-6205."),
            marcar("Só lê: nenhuma planilha muda. Cada achado abre o arquivo ou a pasta dele."),
        ),
    ),
}

# As seções de abas em que cada aba tem regra própria: a tela do menu e as
# chaves das abas, na ordem delas. O bloco da seção mostra o texto da aba aberta.
ABAS_DAS_SECOES: dict[str, tuple[str, ...]] = {
    "LMR": ("LMR.upload", "LMR.exclusao"),
    "PMIBManager": ("PMIBManager.gestao", "PMIBManager.conferencia", "PMIBManager.amp", "PMIBManager.docpack"),
}


def chaves_da_tela(tela: str) -> tuple[str, ...]:
    """As chaves de texto de uma tela do menu: a dela, ou as das abas."""
    return ABAS_DAS_SECOES.get(tela, (tela,))


def traduzido(chave: str) -> Texto:
    """O texto da `chave` no idioma da sessão. Chave desconhecida: `KeyError`."""
    texto = TEXTOS[chave]
    return Texto(t(texto.frase), tuple(t(item) for item in texto.itens))


def chave_da_preferencia(chave: str) -> str:
    return f"{CHAVE_PREFERENCIA}.{chave}"
