// =====================================================================
// CONSULTA: Listas   — DIMENSÃO. Uma linha por Lista de Sobressalentes.
// A mapeadora continua sendo o CADASTRO das listas (responsável, ET,
// revisão, eventos...). Os NÚMEROS saem de Itens. Lista que tem
// _STATUS_PMIB mas não está na mapeadora entra mesmo assim (com aviso).
// =====================================================================
let
    Arquivo = File.Contents(PastaPMIB & "\Mapeamento Listas de Sobressalentes.xlsx"),
    Tabela = fxLerTabela(Arquivo, "Acompanhamento Sobressalente", "N DOCUMENTO ITAIPU"),
    SoLinhas = Table.SelectRows(Tabela, each fxNorm([N DOCUMENTO ITAIPU]) <> ""),
    Colunas = Table.SelectColumns(SoLinhas, {
        "N DOCUMENTO ITAIPU", "N DOCUMENTO CMI", "ULTIMA REVISAO EMITIDA", "STATUS DA REVISAO", "STATUS REAL",
        "REVISAO EM USO", "DESCRICAO", "ESPECIFICACAO TECNICA", "CAPITULO", "RESPONSAVEL", "PROCUREMENT",
        "ELABORADOR DO DOCUMENTO", "ORIGEM FORNECEDOR", "ENTREGA", "OBSERVACAO",
        "EVENTOS DE PAGAMENTOS RELACIONADOS", "SITUACAO NO PMIB"}, MissingField.UseNull),
    Renomeada = Table.RenameColumns(Colunas, {
        {"N DOCUMENTO ITAIPU", "Lista"}, {"N DOCUMENTO CMI", "Documento CMI"},
        {"ULTIMA REVISAO EMITIDA", "Ultima Revisao"}, {"STATUS DA REVISAO", "Status da Revisao"},
        {"STATUS REAL", "Status Real"}, {"REVISAO EM USO", "Revisao em Uso"}, {"DESCRICAO", "Descricao"},
        {"ESPECIFICACAO TECNICA", "Especificacao Tecnica"}, {"CAPITULO", "Capitulo"},
        {"RESPONSAVEL", "Responsavel"}, {"PROCUREMENT", "Procurement (lista)"},
        {"ELABORADOR DO DOCUMENTO", "Elaborador"}, {"ORIGEM FORNECEDOR", "Origem Fornecedor"},
        {"ENTREGA", "Entrega (texto)"}, {"OBSERVACAO", "Observacao"},
        {"EVENTOS DE PAGAMENTOS RELACIONADOS", "Eventos"}, {"SITUACAO NO PMIB", "Situacao PMIB (mapeadora)"}}),
    TextoTudo = Table.TransformColumns(Renomeada, List.Transform(Table.ColumnNames(Renomeada), (c) => {c, each if _ = null then null else Text.Trim(Text.From(_)), type text})),
    ComOrigem = Table.AddColumn(TextoTudo, "Origem Cadastro", each "MAPEADORA", type text),

    // listas que existem só como _STATUS_PMIB
    DeItens = Table.Distinct(Table.SelectColumns(Itens, {"Lista", "Sistema"}), {"Lista"}),
    Faltantes = Table.SelectRows(DeItens, each not List.Contains(ComOrigem[Lista], [Lista])),
    FaltantesFmt = Table.AddColumn(Table.RenameColumns(Faltantes, {{"Sistema", "Descricao"}}), "Origem Cadastro", each "SÓ _STATUS_PMIB (falta na mapeadora)", type text),
    Unidas = Table.Combine({ComOrigem, FaltantesFmt}),

    // nome curto para gráficos: pasta do _STATUS_PMIB; sem ela, a descrição sem o prefixo padrão
    Pastas = Table.Distinct(Table.SelectColumns(Itens, {"Lista", "Area", "Sistema"}), {"Lista"}),
    ComPasta = Table.NestedJoin(Unidas, {"Lista"}, Pastas, {"Lista"}, "P", JoinKind.LeftOuter),
    ExpPasta = Table.ExpandTableColumn(ComPasta, "P", {"Area", "Sistema"}),
    ComNome = Table.AddColumn(ExpPasta, "Nome", each
        if [Sistema] <> null then [Sistema]
        else
            let
                d = if [Descricao] = null then [Lista] else [Descricao],
                Prefixos = {"ATUALIZAÇÃO TECNOLÓGICA - PAT_OBJ1 - ", "ATUALIZAÇÃO TECNOLÓGICA – PAT_OBJ1 - ",
                            "ENG. ELÉTRICA - ", "ENG. MECÂNICA  - ", "ENG. MECÂNICA - ", "ENG. ELETRÔNICA - ", "ENG. CIVIL - ",
                            " - LISTA DE SOBRESSALENTES", " - LISTA DESOBRESSALENTES"},
                Limpo = List.Accumulate(Prefixos, d, (s, p) => Text.Replace(s, p, ""))
            in
                Text.Trim(Limpo), type text),
    ComAreaFinal = Table.AddColumn(ComNome, "Area Final", each if [Area] <> null then [Area] else "SEM _STATUS_PMIB", type text),
    ComFlags = Table.AddColumn(ComAreaFinal, "Tem Responsavel", each [Responsavel] <> null and fxNorm([Responsavel]) <> "" and fxNorm([Responsavel]) <> "-", type logical),

    // revisão em uso: a do próprio _STATUS_PMIB (linha acima do cabeçalho) manda; a da
    // mapeadora fica como referência até o SIG-FT passar a copiá-la do arquivo
    Revisoes = Table.Distinct(Table.SelectRows(Table.SelectColumns(Itens, {"Lista", "Revisao no Arquivo"}),
                                               each [Revisao no Arquivo] <> null), {"Lista"}),
    ComRevArq = Table.ExpandTableColumn(Table.NestedJoin(ComFlags, {"Lista"}, Revisoes, {"Lista"}, "R", JoinKind.LeftOuter),
                                        "R", {"Revisao no Arquivo"}),
    ComRevMap = Table.RenameColumns(ComRevArq, {{"Revisao em Uso", "Revisao em Uso (mapeadora)"}}),
    ComRevisao = Table.AddColumn(ComRevMap, "Revisao em Uso", each
        if [Revisao no Arquivo] <> null then [Revisao no Arquivo] else [#"Revisao em Uso (mapeadora)"], type text),
    ComDefasagem = Table.AddColumn(ComRevisao, "Revisao Desatualizada", each
        [Revisao em Uso] <> null and [Ultima Revisao] <> null and fxNorm([Ultima Revisao]) <> "SEM LISTA"
        and fxNorm([Revisao em Uso]) <> fxNorm([Ultima Revisao]), type logical),
    Final = Table.RemoveColumns(Table.RenameColumns(ComDefasagem, {{"Area", "Area (pasta)"}}), {"Sistema"})
in
    Final


// =====================================================================
// CONSULTA: Atividades   — aba "Atividades" da mapeadora (plano de ação)
// =====================================================================
let
    Arquivo = File.Contents(PastaPMIB & "\Mapeamento Listas de Sobressalentes.xlsx"),
    Tabela = fxLerTabela(Arquivo, "Atividades", "NV"),
    ComLista = Table.AddColumn(Tabela, "Lista", each if [NV] = 1 then [CODIGO ITAIPU] else null),
    ComFrente = Table.AddColumn(ComLista, "Frente", each if [NV] = 1 then [DESCRICAO] else null),
    Preenchida = Table.FillDown(ComFrente, {"Lista", "Frente"}),
    SoAtividades = Table.SelectRows(Preenchida, each [NV] <> 1 and fxNorm([DESCRICAO]) <> ""),   // NV vazio conta como atividade
    Selecionada = Table.SelectColumns(SoAtividades, {"Lista", "Frente", "DESCRICAO", "DATA PREVISTA DE INICIO", "DATA DE INICIO",
        "PREVISAO DE TERMINO", "DATA DE TERMINO", "STATUS", "ALTERACAO DO STATUS", "COM QUEM ESTA", "DETALHE", "CRITICIDADE", "CONCLUIDA"}, MissingField.UseNull),
    Renomeada = Table.RenameColumns(Selecionada, {
        {"DESCRICAO", "Atividade"}, {"DATA PREVISTA DE INICIO", "Inicio Previsto"}, {"DATA DE INICIO", "Inicio Real"},
        {"PREVISAO DE TERMINO", "Termino Previsto"}, {"DATA DE TERMINO", "Termino Real"}, {"STATUS", "Status Atividade"},
        {"ALTERACAO DO STATUS", "Alteracao do Status"}, {"COM QUEM ESTA", "Com Quem Esta"}, {"DETALHE", "Detalhe"},
        {"CRITICIDADE", "Criticidade"}, {"CONCLUIDA", "Concluida"}}),
    Datas = Table.TransformColumns(Renomeada, {
        {"Inicio Previsto", fxData, type date}, {"Inicio Real", fxData, type date}, {"Termino Previsto", fxData, type date},
        {"Termino Real", fxData, type date}, {"Alteracao do Status", fxData, type date}}),
    ComConcluida = Table.TransformColumns(Datas, {{"Concluida", each _ = true or fxNorm(_) = "TRUE" or fxNorm(_) = "VERDADEIRO", type logical}}),
    ComSituacao = Table.AddColumn(ComConcluida, "Situacao", each
        if [Concluida] or fxNorm([Status Atividade]) = "CONCLUIDA" then "CONCLUÍDA"
        else if fxNorm([Status Atividade]) = "TRAVADA" then "TRAVADA"
        else if [Termino Previsto] <> null and [Termino Previsto] < DataReferencia then "ATRASADA"
        else if [Inicio Real] = null then "NÃO INICIADA"
        else "EM DIA", type text),
    Tipada = Table.TransformColumnTypes(ComSituacao, {{"Lista", type text}, {"Frente", type text}, {"Atividade", type text},
        {"Status Atividade", type text}, {"Com Quem Esta", type text}, {"Detalhe", type text}, {"Criticidade", Int64.Type}})
in
    Tipada


// =====================================================================
// CONSULTA: Eventos   — "Extrato dos Eventos dos Sobressalentes.xlsx"
// (fica na pasta 15 - PDM, um nível acima de PastaPMIB)
// Tipo ENTREGA = parcela paga no recebimento; APROVAÇÃO = na aprovação.
// =====================================================================
let
    PastaPDM = Text.BeforeDelimiter(PastaPMIB, "\", {0, RelativePosition.FromEnd}),
    Arquivo = File.Contents(PastaPDM & "\Extrato dos Eventos dos Sobressalentes.xlsx"),
    Tabela = fxLerTabela(Arquivo, "Sheet2", "ITEM"),
    ComGrupo = Table.AddColumn(Tabela, "Grupo", each if [VALOR] = null and [ITEM] <> null then [ITEM] else null),
    Preenchida = Table.FillDown(ComGrupo, {"Grupo"}),
    SoEventos = Table.SelectRows(Preenchida, each [VALOR] <> null),
    ComEvento = Table.AddColumn(SoEventos, "Evento", each Text.Upper(Text.Remove(Text.From([ITEM]), {" "})), type text),
    ComPercentual = Table.AddColumn(ComEvento, "Percentual", each try Number.From(Text.BeforeDelimiter(Text.From([VALOR]), "%")) / 100 otherwise null, Percentage.Type),
    ComTipo = Table.AddColumn(ComPercentual, "Tipo Evento", each if Text.Contains(fxNorm([DESCRICAO]), "APROVACAO") then "APROVAÇÃO" else "ENTREGA", type text),
    Final = Table.SelectColumns(Table.RenameColumns(ComTipo, {{"DESCRICAO", "Descricao Evento"}, {"MES DE REFERENCIA", "Mes de Referencia"}}),
        {"Evento", "Grupo", "Tipo Evento", "Percentual", "Descricao Evento", "Mes de Referencia"}, MissingField.UseNull)
in
    Final


// =====================================================================
// CONSULTA: ListaEvento   — ponte Lista x Evento ("2835, 2835a, 2836")
// Relacionamento Listas 1—* ListaEvento com filtro cruzado AMBAS as direções.
// =====================================================================
let
    Base = Table.SelectRows(Table.SelectColumns(Listas, {"Lista", "Eventos"}), each [Eventos] <> null),
    Separada = Table.AddColumn(Base, "Evento", each
        List.Select(List.Transform(Text.SplitAny([Eventos], ",/;"), each Text.Upper(Text.Remove(Text.Trim(_), {" "}))), each _ <> "")),
    Expandida = Table.ExpandListColumn(Separada, "Evento"),
    Final = Table.Distinct(Table.SelectColumns(Expandida, {"Lista", "Evento"}))
in
    Final
