// =====================================================================
// CONSULTA: Feriados
// Calendário usado nos 15 dias úteis de autorização de Itaipu.
// Nacionais do Brasil + pontos facultativos de Carnaval e Corpus Christi.
// DECISÃO EM ABERTO: confirmar com Itaipu se valem também feriados do
// Paraguai e/ou municipais de Foz. Para incluir/tirar, edite a lista.
// =====================================================================
let
    Fonte = #table(
        type table [Data = date, Feriado = text],
        {
            {#date(2024, 1, 1), "Confraternização Universal"},
            {#date(2024, 2, 12), "Carnaval (ponto facultativo)"},
            {#date(2024, 2, 13), "Carnaval (ponto facultativo)"},
            {#date(2024, 3, 29), "Sexta-feira Santa"},
            {#date(2024, 4, 21), "Tiradentes"},
            {#date(2024, 5, 1), "Dia do Trabalho"},
            {#date(2024, 5, 30), "Corpus Christi (ponto facultativo)"},
            {#date(2024, 9, 7), "Independência"},
            {#date(2024, 10, 12), "Nossa Senhora Aparecida"},
            {#date(2024, 11, 2), "Finados"},
            {#date(2024, 11, 15), "Proclamação da República"},
            {#date(2024, 11, 20), "Consciência Negra"},
            {#date(2024, 12, 25), "Natal"},
            {#date(2025, 1, 1), "Confraternização Universal"},
            {#date(2025, 3, 3), "Carnaval (ponto facultativo)"},
            {#date(2025, 3, 4), "Carnaval (ponto facultativo)"},
            {#date(2025, 4, 18), "Sexta-feira Santa"},
            {#date(2025, 4, 21), "Tiradentes"},
            {#date(2025, 5, 1), "Dia do Trabalho"},
            {#date(2025, 6, 19), "Corpus Christi (ponto facultativo)"},
            {#date(2025, 9, 7), "Independência"},
            {#date(2025, 10, 12), "Nossa Senhora Aparecida"},
            {#date(2025, 11, 2), "Finados"},
            {#date(2025, 11, 15), "Proclamação da República"},
            {#date(2025, 11, 20), "Consciência Negra"},
            {#date(2025, 12, 25), "Natal"},
            {#date(2026, 1, 1), "Confraternização Universal"},
            {#date(2026, 2, 16), "Carnaval (ponto facultativo)"},
            {#date(2026, 2, 17), "Carnaval (ponto facultativo)"},
            {#date(2026, 4, 3), "Sexta-feira Santa"},
            {#date(2026, 4, 21), "Tiradentes"},
            {#date(2026, 5, 1), "Dia do Trabalho"},
            {#date(2026, 6, 4), "Corpus Christi (ponto facultativo)"},
            {#date(2026, 9, 7), "Independência"},
            {#date(2026, 10, 12), "Nossa Senhora Aparecida"},
            {#date(2026, 11, 2), "Finados"},
            {#date(2026, 11, 15), "Proclamação da República"},
            {#date(2026, 11, 20), "Consciência Negra"},
            {#date(2026, 12, 25), "Natal"},
            {#date(2027, 1, 1), "Confraternização Universal"},
            {#date(2027, 2, 8), "Carnaval (ponto facultativo)"},
            {#date(2027, 2, 9), "Carnaval (ponto facultativo)"},
            {#date(2027, 3, 26), "Sexta-feira Santa"},
            {#date(2027, 4, 21), "Tiradentes"},
            {#date(2027, 5, 1), "Dia do Trabalho"},
            {#date(2027, 5, 27), "Corpus Christi (ponto facultativo)"},
            {#date(2027, 9, 7), "Independência"},
            {#date(2027, 10, 12), "Nossa Senhora Aparecida"},
            {#date(2027, 11, 2), "Finados"},
            {#date(2027, 11, 15), "Proclamação da República"},
            {#date(2027, 11, 20), "Consciência Negra"},
            {#date(2027, 12, 25), "Natal"},
            {#date(2028, 1, 1), "Confraternização Universal"},
            {#date(2028, 2, 28), "Carnaval (ponto facultativo)"},
            {#date(2028, 2, 29), "Carnaval (ponto facultativo)"},
            {#date(2028, 4, 14), "Sexta-feira Santa"},
            {#date(2028, 4, 21), "Tiradentes"},
            {#date(2028, 5, 1), "Dia do Trabalho"},
            {#date(2028, 6, 15), "Corpus Christi (ponto facultativo)"},
            {#date(2028, 9, 7), "Independência"},
            {#date(2028, 10, 12), "Nossa Senhora Aparecida"},
            {#date(2028, 11, 2), "Finados"},
            {#date(2028, 11, 15), "Proclamação da República"},
            {#date(2028, 11, 20), "Consciência Negra"},
            {#date(2028, 12, 25), "Natal"}
        })
in
    Fonte


// =====================================================================
// CONSULTA: Calendario   (marque como tabela de datas: Ferramentas de tabela >
//                         Marcar como tabela de datas > coluna Data)
// =====================================================================
let
    Inicio = #date(2024, 1, 1),
    Fim = #date(2028, 12, 31),
    Datas = List.Dates(Inicio, Duration.Days(Fim - Inicio) + 1, #duration(1, 0, 0, 0)),
    Tabela = Table.FromList(Datas, Splitter.SplitByNothing(), type table [Data = date]),
    FeriadosLista = List.Buffer(Feriados[Data]),
    ComAno = Table.AddColumn(Tabela, "Ano", each Date.Year([Data]), Int64.Type),
    ComMes = Table.AddColumn(ComAno, "Mes", each Date.Month([Data]), Int64.Type),
    ComMesNome = Table.AddColumn(ComMes, "Mes Ano", each Text.Proper(Date.ToText([Data], "MMM/yy", "pt-BR")), type text),
    ComMesInicio = Table.AddColumn(ComMesNome, "Inicio do Mes", each Date.StartOfMonth([Data]), type date),
    ComSemana = Table.AddColumn(ComMesInicio, "Inicio da Semana", each Date.StartOfWeek([Data], Day.Monday), type date),
    ComUtil = Table.AddColumn(ComSemana, "Dia Util", each Date.DayOfWeek([Data], Day.Monday) < 5 and not List.Contains(FeriadosLista, [Data]), type logical)
in
    ComUtil
