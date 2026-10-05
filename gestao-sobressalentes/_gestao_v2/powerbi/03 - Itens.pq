// =====================================================================
// CONSULTA: Itens   — A TABELA FATO. Uma linha por linha de material de
// todos os _STATUS_PMIB. É a fonte única dos números: o Power BI deixa de
// depender das contagens da mapeadora (que só ficam certas se o SIG-FT
// rodou) e passa a contar item a item.
// Lê _STATUS_PMIB v1 (20 colunas) e v2 (layout de 04/10/2026) — coluna que
// não existe no arquivo vem nula. No v2, SITUAÇÃO DA AUTORIZAÇÃO ocupa o lugar
// do APTO PARA ENTREGA (SIM = AUTORIZADO) e DIAS DE ATRASO vem do SIG-FT.
// =====================================================================
let
    Raiz = if Text.EndsWith(PastaPMIB, "\") then PastaPMIB else PastaPMIB & "\",
    Hoje = DataReferencia,

    // 1. Arquivos vivos (fora de obsoleto, testes, backups e cópias de trabalho)
    Arquivos = Folder.Files(Raiz),
    Filtrados = Table.SelectRows(Arquivos, each
        let
            n = Text.Upper([Name]),
            p = fxNorm([Folder Path])
        in
            Text.EndsWith(n, "_STATUS_PMIB.XLSX")
            and not Text.StartsWith(n, "~$")
            and not List.AnyTrue(List.Transform({"OBSOLETO", "10- TESTES", "TESTES_AUTOSPEC", "\DATASHEETS\", "BACKUP"}, (k) => Text.Contains(p, k)))),

    // 2. Identidade do arquivo: código da lista, área (1º nível) e sistema (resto do caminho)
    ComLista = Table.AddColumn(Filtrados, "Lista", each Text.Start([Name], Text.Length([Name]) - Text.Length("_STATUS_PMIB.xlsx")), type text),
    ComCaminho = Table.AddColumn(ComLista, "Caminho", each Text.AfterDelimiter([Folder Path], Raiz), type text),
    ComArea = Table.AddColumn(ComCaminho, "Area", each Text.BeforeDelimiter([Caminho], "\"), type text),
    ComSistema = Table.AddColumn(ComArea, "Sistema", each
        let Partes = List.Select(Text.Split([Caminho], "\"), each _ <> "")
        in if List.Count(Partes) <= 1 then [Area] else Text.Combine(List.Skip(Partes, 1), " › "), type text),

    // 3. Conteúdo + a revisão da lista de sobressalentes que o arquivo reflete (linha acima do cabeçalho)
    ComDados = Table.AddColumn(ComSistema, "Dados", each fxLerTabela([Content], "Lista de Materiais", "DESCRICAO")),
    ComRevisao = Table.AddColumn(ComDados, "Revisao no Arquivo", each fxRevisaoEmUso([Content]), type text),
    Base = Table.SelectColumns(ComRevisao, {"Lista", "Area", "Sistema", "Caminho", "Revisao no Arquivo", "Dados"}),
    Colunas = {"ITEM", "QTD.", "UNID.", "DESCRICAO", "CODIGO DO MATERIAL", "CODIGO CMI", "MARCA/MODELO",
               "TIPO DE ENTREGA", "FORNECEDOR", "PROCUREMENT", "CODIGO PMIB", "PDM USADO", "STATUS",
               "INFO. GERAIS", "CARACT. TECNICAS", "DOCUMENTOS E IMAGENS", "CONDICOES", "VALORIZACAO", "APLICACAO - LMR",
               "DATA DO EMAIL COMUNICANDO ENTREGA", "SITUACAO DA AUTORIZACAO", "DIAS DE ATRASO",
               "APTO PARA ENTREGA", "EQUIPAMENTO ENTREGUE", "OBSERVACOES"},
    Selecionadas = Table.TransformColumns(Base, {"Dados", each Table.SelectColumns(_, Colunas, MissingField.UseNull)}),
    Expandida = Table.ExpandTableColumn(Selecionadas, "Dados", Colunas),
    ComDescricao = Table.SelectRows(Expandida, each fxNorm([DESCRICAO]) <> ""),

    // 4. Chaves e vocabulário
    ComPMIB = Table.AddColumn(ComDescricao, "PMIB", each fxPMIB([CODIGO PMIB]), type text),
    ComStatus = Table.AddColumn(ComPMIB, "Status", each fxStatus([STATUS]), type text),
    // STATUS DUPLICADO = o mesmo item repetido NA MESMA LISTA (repete o PMIB de outra linha, sem
    // seções preenchidas): não é ficha nova, mas a quantidade conta. A ficha duplicada DE OUTRO
    // SISTEMA é ficha nova (PMIB próprio, PDM.9900.000, PMIB da original em OBSERVACOES).
    ComEFicha = Table.AddColumn(ComStatus, "E Ficha", each [PMIB] <> null and [Status] <> "DUPLICADO", type logical),
    ComDupOutro = Table.AddColumn(ComEFicha, "Duplicada de Outro Sistema", each Text.StartsWith(fxNorm([PDM USADO]), "PDM.9900"), type logical),
    ComPMIBOriginal = Table.AddColumn(ComDupOutro, "PMIB Original", each
        if not [Duplicada de Outro Sistema] then null
        else
            let t = if [OBSERVACOES] = null then "" else Text.From([OBSERVACOES]), p = Text.PositionOf(t, "4500063671")
            in if p < 0 then null else fxPMIB(Text.Select(Text.Middle(t, p, 15), {"0".."9", "."})), type text),
    ComChave = Table.AddColumn(ComPMIBOriginal, "Chave Ficha", each if [E Ficha] then [Lista] & "|" & [PMIB] else null, type text),
    ComEmitida = Table.AddColumn(ComChave, "Emitida", each List.Contains({"EM ANÁLISE IB", "EM CORREÇÃO", "APROVADO"}, [Status]), type logical),
    ComOrdem = Table.AddColumn(ComEmitida, "Ordem Etapa", each
        List.PositionOf({"INICIAR", "FICHA CRIADA", "COM O FORNECEDOR", "EM ELABORAÇÃO", "EM CORREÇÃO", "EM ANÁLISE IB", "APROVADO"}, [Status]) + 1, Int64.Type),
    ComEtapaCliente = Table.AddColumn(ComOrdem, "Etapa Cliente", each
        if [Status] = "APROVADO" then "3. Aprovada"
        else if [Status] = "EM ANÁLISE IB" then "2. Em análise Itaipu"
        else "1. Em preparação (CMI)", type text),
    ComQuem = Table.AddColumn(ComEtapaCliente, "Com Quem", each
        if List.Contains({"INICIAR", "FICHA CRIADA", "EM ELABORAÇÃO", "EM CORREÇÃO"}, [Status]) then "CMI"
        else if [Status] = "COM O FORNECEDOR" then "FORNECEDOR"
        else if [Status] = "EM ANÁLISE IB" then "ITAIPU"
        else if [Status] = "APROVADO" then "CONCLUÍDO"
        else "—", type text),

    // 5. Seções da ficha
    ComSecoes = List.Accumulate(
        {{"INFO. GERAIS", "Info Gerais OK"}, {"CARACT. TECNICAS", "Caract Tecnicas OK"}, {"DOCUMENTOS E IMAGENS", "Documentos OK"},
         {"CONDICOES", "Condicoes OK"}, {"VALORIZACAO", "Valorizacao OK"}, {"APLICACAO - LMR", "LMR OK"}},
        ComQuem,
        (t, par) => Table.AddColumn(t, par{1}, (r) => fxNorm(Record.Field(r, par{0})) = "COMPLETO", type logical)),
    ComFornecedorOK = Table.AddColumn(ComSecoes, "Info Fornecedor OK", each [Info Gerais OK] and [Caract Tecnicas OK] and [Documentos OK] and [Condicoes OK], type logical),

    // 6. Lista de preços: tipo de entrega e valor
    ComPreco = Table.NestedJoin(ComFornecedorOK, {"PMIB"}, PrecosPorPMIB, {"PMIB"}, "Preco", JoinKind.LeftOuter),
    ExpPreco = Table.ExpandTableColumn(ComPreco, "Preco", {"Tipo Preco", "Valor Unitario USD", "Codigo GE Preco", "Lista de Precos"}),
    ComTipo = Table.AddColumn(ExpPreco, "Tipo de Entrega", each
        let DoStatus = fxTipoEntrega([TIPO DE ENTREGA])
        in if DoStatus <> null then DoStatus else if [Tipo Preco] <> null then [Tipo Preco] else "NÃO CLASSIFICADO", type text),
    ComOrigemTipo = Table.AddColumn(ComTipo, "Origem do Tipo", each
        if fxTipoEntrega([TIPO DE ENTREGA]) <> null then "_STATUS_PMIB" else if [Tipo Preco] <> null then "LISTA DE PREÇOS" else "—", type text),
    ComQtd = Table.AddColumn(ComOrigemTipo, "Qtd", each try Number.From([#"QTD."]) otherwise null, type number),
    ComValorLinha = Table.AddColumn(ComQtd, "Valor Linha USD", each
        if [Tipo de Entrega] = "FÍSICA E DOCUMENTAL" and [Qtd] <> null and [Valor Unitario USD] <> null then [Qtd] * [Valor Unitario USD] else null, type number),

    // 7. Trilha logística. SITUAÇÃO DA AUTORIZAÇÃO e DIAS DE ATRASO são CALCULADOS PELO SIG-FT
    //    e gravados no _STATUS_PMIB (decisão de 04/10/2026): aqui só se lê. DIAS DE ATRASO =
    //    dias corridos além do prazo de 15 dias úteis do e-mail; congela quando Itaipu autoriza.
    //    Arquivo antigo (só APTO PARA ENTREGA): SIM = AUTORIZADO; com e-mail e sem nada
    //    calculado aparece como "AGUARDANDO CÁLCULO DO SIG-FT".
    //    Só FÍSICA E DOCUMENTAL precisa de autorização (correções do Luan, 05/10/2026):
    //    DOCUMENTAL (componente explodido) e TÍTULO (agrupamento) -> "N/A"; TIPO vazio ->
    //    "SEM TIPO DE ENTREGA" (não conta até alguém classificar). O tipo aqui é o da COLUNA do
    //    _STATUS_PMIB — o mesmo que o SIG-FT usa —, não o da lista de preços.
    ComDatas = Table.TransformColumns(ComValorLinha, {{"DATA DO EMAIL COMUNICANDO ENTREGA", fxData, type date}}),
    Renomeada = Table.RenameColumns(ComDatas, {{"DATA DO EMAIL COMUNICANDO ENTREGA", "Data Email"}}),
    ComEntregue = Table.AddColumn(Renomeada, "Entregue", each fxNorm([EQUIPAMENTO ENTREGUE]) = "SIM", type logical),
    // a linha DUPLICADO herda o "entregue" da ficha (mesma lista + mesmo PMIB): o valor dela conta junto
    EntreguePorFicha = Table.Group(Table.SelectRows(ComEntregue, each [PMIB] <> null), {"Lista", "PMIB"},
        {{"Ficha Entregue", each List.AnyTrue([Entregue]), type logical}}),
    ComFichaEntregueN = Table.NestedJoin(ComEntregue, {"Lista", "PMIB"}, EntreguePorFicha, {"Lista", "PMIB"}, "FE", JoinKind.LeftOuter),
    ComFichaEntregue = Table.ExpandTableColumn(ComFichaEntregueN, "FE", {"Ficha Entregue"}),
    ComSituacao = Table.AddColumn(ComFichaEntregue, "Situacao Autorizacao", each
        let s = fxNorm([SITUACAO DA AUTORIZACAO]), a = fxNorm([APTO PARA ENTREGA]), tc = fxTipoEntrega([TIPO DE ENTREGA])
        in if s = "AUTORIZADO" or a = "SIM" then "AUTORIZADO"
           else if tc = "DOCUMENTAL" or tc = "TÍTULO" then "N/A"
           else if [Entregue] then "AUTORIZADO"
           else if tc = null then "SEM TIPO DE ENTREGA"
           else if s = "ATRASADO ITAIPU" or s = "AGUARDANDO ITAIPU" then s
           else if [Data Email] <> null and [E Ficha] then "AGUARDANDO CÁLCULO DO SIG-FT"
           else "SEM PEDIDO", type text),
    ComApto = Table.AddColumn(ComSituacao, "Apto", each [Situacao Autorizacao] = "AUTORIZADO", type logical),
    ComAtraso = Table.AddColumn(ComApto, "Dias de Atraso", each try Int64.From([DIAS DE ATRASO]) otherwise null, Int64.Type),
    SemBrutas = Table.RemoveColumns(ComAtraso, {"SITUACAO DA AUTORIZACAO", "DIAS DE ATRASO"}),

    // 8. Trilha documental: compromisso CMI de LMR em até 3 meses do e-mail de intenção
    ComDiasEmail = Table.AddColumn(SemBrutas, "Dias desde Email", each if [Data Email] = null then null else Duration.Days(Hoje - [Data Email]), Int64.Type),
    ComLMR = Table.AddColumn(ComDiasEmail, "Situacao LMR", each
        if [LMR OK] then "LMR CONCLUÍDA"
        else if [Data Email] = null then "SEM PEDIDO"
        else if [Dias desde Email] > 90 then "LMR FORA DO COMPROMISSO"
        else if [Dias desde Email] > 60 then "LMR EM ATENÇÃO"
        else "LMR NO PRAZO", type text),

    // 9. Pendência principal (a primeira coisa que falta) — alimenta a fila de trabalho.
    //    Ficha já emitida só tem três pendências do CMI: cobrar, entregar, ou a LMR que faltou.
    ComPendencia = Table.AddColumn(ComLMR, "Pendencia", each
        if not [E Ficha] then "—"
        else if [Status] = "EM CORREÇÃO" then "Responder comentários de Itaipu"
        else if [Situacao Autorizacao] = "ATRASADO ITAIPU" then "Cobrar autorização de Itaipu"
        else if [Apto] and not [Entregue] and [Tipo de Entrega] = "FÍSICA E DOCUMENTAL" then "Entregar no almoxarifado"
        else if [Emitida] then (if [Status] <> "APROVADO" and not [LMR OK] then "Aplicação LMR" else "—")
        else if [Status] = "COM O FORNECEDOR" or not [Info Fornecedor OK] then "Informações do fornecedor"
        else if not [Valorizacao OK] then "Valorização"
        else if not [LMR OK] then "Aplicação LMR"
        else "Emitir para Itaipu", type text),

    // 10. Limpeza final
    ComReferencia = Table.AddColumn(ComPendencia, "Data Referencia", each Hoje, type date),
    Removidas = Table.RemoveColumns(ComReferencia, {"CODIGO PMIB", "STATUS", "TIPO DE ENTREGA", "APTO PARA ENTREGA", "EQUIPAMENTO ENTREGUE", "Tipo Preco"}),
    Tipada = Table.TransformColumnTypes(Removidas, {
        {"ITEM", type text}, {"QTD.", type text}, {"UNID.", type text}, {"DESCRICAO", type text},
        {"CODIGO DO MATERIAL", type text}, {"CODIGO CMI", type text}, {"MARCA/MODELO", type text},
        {"FORNECEDOR", type text}, {"PROCUREMENT", type text}, {"PDM USADO", type text}, {"Revisao no Arquivo", type text},
        {"INFO. GERAIS", type text}, {"CARACT. TECNICAS", type text}, {"DOCUMENTOS E IMAGENS", type text},
        {"CONDICOES", type text}, {"VALORIZACAO", type text}, {"APLICACAO - LMR", type text}, {"OBSERVACOES", type text}})
in
    Tipada
