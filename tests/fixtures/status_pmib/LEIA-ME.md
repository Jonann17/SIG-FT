# Fixtures do `_STATUS_PMIB`

`status_pmib_v2_sintetico.xlsx` — cópia de
`gestao-sobressalentes/_gestao_v2/fixtures/status_pmib_v2_sintetico.xlsx`
(gerado por `gerar_fixture_sintetica.py` no cofre da gestão dos sobressalentes).

Layout v2 (04/10/2026): linha 4 com a revisão em uso, cabeçalho na linha 5,
TIPO DE ENTREGA / SITUAÇÃO DA AUTORIZAÇÃO / DIAS DE ATRASO / FORNECEDOR /
PROCUREMENT. **Nenhum texto real** ("TEXTO DE TESTE n").

O que ele tem e que o openpyxl apagaria ao salvar — por isso existe:

- 3 comentários em thread (`xl/threadedComments/`, `xl/persons/`) e as 3
  anotações de compatibilidade (`xl/comments1.xml`);
- listas suspensas por nome definido (`lst_status`, `lst_secao`...), no
  formato padrão.

`status_pmib_v1_sintetico.xlsx` — o mesmo arquivo ANTES da migração (layout
antigo, cabeçalho na linha 4, APTO PARA ENTREGA). Tem o que o v2 não tem: **2
listas suspensas gravadas como extensão** (`x14:dataValidation`, apontando para
outra aba) — as que o openpyxl apaga com o aviso "Data Validation extension is
not supported and will be removed". Mesmos 3 comentários em thread.

Usado por `tests/test_cirurgico.py` e `tests/test_status_pmib_gravacao_real.py`.
