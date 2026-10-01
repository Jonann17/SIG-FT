// =====================================================================
// CONSULTA: PrecosArquivos   (uma linha por arquivo de lista de preços)
// Reconhece a lista de preços pelo DCC do código:
//   ...PB021      vigente (revisão do ITAIPU-REF-0013)
//   ...PB020-0x   legado — ainda existe enquanto não for reemitida como PB021
// =====================================================================
let
    Raiz = if Text.EndsWith(PastaPMIB, "\") then PastaPMIB else PastaPMIB & "\",
    Arquivos = Folder.Files(Raiz),
    Filtrados = Table.SelectRows(Arquivos, each
        let
            n = Text.Upper([Name]),
            p = fxNorm([Folder Path])
        in
            (Text.EndsWith(n, ".XLSM") or Text.EndsWith(n, ".XLSX"))
            and (Text.Contains(n, "PB021") or Text.Contains(n, "PB020-0"))
            and not Text.Contains(n, "STATUS_PMIB")
            and not Text.StartsWith(n, "~$")
            and not List.AnyTrue(List.Transform({"COPY", "COPIA", "CÓPIA", "COMENT", "RESPOSTA"}, (k) => Text.Contains(n, k)))
            and not List.AnyTrue(List.Transform({"OBSOLETO", "TESTES", "BACKUP"}, (k) => Text.Contains(p, k)))),
    ComCodigo = Table.AddColumn(Filtrados, "Lista de Precos", each
        let
            SemExt = Text.BeforeDelimiter([Name], ".", {0, RelativePosition.FromEnd}),
            SemRev = if Text.Contains(SemExt, "[") then Text.BeforeDelimiter(SemExt, "[") else SemExt
        in
            Text.Trim(SemRev), type text),
    ComGeracao = Table.AddColumn(ComCodigo, "Geracao", each if Text.Contains(Text.Upper([Name]), "PB021") then "PB021" else "PB020-0x (legado)", type text),
    ComPasta = Table.AddColumn(ComGeracao, "Pasta", each Text.AfterDelimiter([Folder Path], Raiz), type text),
    ComDados = Table.AddColumn(ComPasta, "Dados", each fxLerTabela([Content], "Lista de Materiais", "DESCRICAO")),
    Resultado = Table.SelectColumns(ComDados, {"Lista de Precos", "Geracao", "Pasta", "Date modified", "Dados"})
in
    Resultado


// =====================================================================
// CONSULTA: PrecosPorPMIB   (desabilite o carregamento: só alimenta Itens)
// Uma linha por PMIB. Se o PMIB aparece em mais de um arquivo, vale
// PB021 antes de PB020-0x e, entre iguais, o arquivo mais recente.
// =====================================================================
let
    Base = PrecosArquivos,
    Colunas = {"QTD.", "CODIGO GE", "CODIGO GE (MTA)", "CODIGO CMI", "CODIGO PMIB", "VALOR UNITARIO", "TIPO DE ENTREGA"},
    Selecionadas = Table.TransformColumns(Base, {"Dados", each Table.SelectColumns(_, Colunas, MissingField.UseNull)}),
    Expandida = Table.ExpandTableColumn(Selecionadas, "Dados", Colunas),
    ComPMIB = Table.AddColumn(Expandida, "PMIB", each fxPMIB([CODIGO PMIB]), type text),
    SoComPMIB = Table.SelectRows(ComPMIB, each [PMIB] <> null),
    ComTipo = Table.AddColumn(SoComPMIB, "Tipo Preco", each fxTipoEntrega([TIPO DE ENTREGA]), type text),
    ComValor = Table.AddColumn(ComTipo, "Valor Unitario USD", each try Number.From([VALOR UNITARIO]) otherwise null, type number),
    ComCodigoGE = Table.AddColumn(ComValor, "Codigo GE Preco", each
        List.First(List.Select({[CODIGO GE], [#"CODIGO GE (MTA)"], [CODIGO CMI]}, each _ <> null and fxNorm(_) <> "" and fxNorm(_) <> "-"), null), type text),
    Prioridade = Table.AddColumn(ComCodigoGE, "Prioridade", each if [Geracao] = "PB021" then 2 else 1, Int64.Type),
    Ordenada = Table.Buffer(Table.Sort(Prioridade, {{"Prioridade", Order.Descending}, {"Date modified", Order.Descending}})),
    UmPorPMIB = Table.Distinct(Ordenada, {"PMIB"}),
    Resultado = Table.SelectColumns(UmPorPMIB, {"PMIB", "Tipo Preco", "Valor Unitario USD", "Codigo GE Preco", "Lista de Precos", "Geracao"})
in
    Resultado


// =====================================================================
// CONSULTA: PrecosAconex   (aba "Lista de preços Follow-up" da mapeadora:
//                           o estado de cada lista de preços no Aconex)
// =====================================================================
let
    Arquivo = File.Contents(PastaPMIB & "\Mapeamento Listas de Sobressalentes.xlsx"),
    Tabela = fxLerTabela(Arquivo, "Lista de preços Follow-up", "N DOCUMENTO ITAIPU"),
    SoLinhas = Table.SelectRows(Tabela, each fxNorm([N DOCUMENTO ITAIPU]) <> ""),
    Colunas = Table.SelectColumns(SoLinhas,
        {"N DOCUMENTO ITAIPU", "N DOCUMENTO CMI", "ULTIMA REVISAO EMITIDA", "STATUS DA REVISAO", "DATA DE ATUALIZACAO",
         "LISTA DE SOBRESSALENTES", "ALERTA RDS-PP", "ACAO", "OBSERVACOES"}, MissingField.UseNull),
    Renomeada = Table.RenameColumns(Colunas, {
        {"N DOCUMENTO ITAIPU", "Lista de Precos"}, {"N DOCUMENTO CMI", "Documento CMI"},
        {"ULTIMA REVISAO EMITIDA", "Revisao"}, {"STATUS DA REVISAO", "Status Aconex"},
        {"DATA DE ATUALIZACAO", "Data Aconex"}, {"LISTA DE SOBRESSALENTES", "Lista"},
        {"ALERTA RDS-PP", "Alerta RDS-PP"}, {"ACAO", "Acao"}, {"OBSERVACOES", "Observacoes"}}),
    ComData = Table.TransformColumns(Renomeada, {{"Data Aconex", fxData, type date}}),
    ComGeracao = Table.AddColumn(ComData, "Geracao", each if Text.Contains(Text.Upper(Text.From([Lista de Precos])), "PB021") then "PB021" else "PB020-0x (legado)", type text),
    ComSituacao = Table.AddColumn(ComGeracao, "Situacao Preco", each
        let s = fxNorm([Status Aconex]) in
        if s = "APROVADO" or s = "APROVADO COM COMENTARIOS" then "APROVADA SM.DT"
        else if s = "NAO APROVADO" then "NÃO APROVADA"
        else if s = "VOID" then "CANCELADA"
        else "EMITIDA", type text),
    Tipada = Table.TransformColumnTypes(ComSituacao, {{"Lista de Precos", type text}, {"Lista", type text}, {"Revisao", type text}, {"Status Aconex", type text}})
in
    Tipada
