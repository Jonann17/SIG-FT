# Upload de Fotos (`sigft/services/upload_fotos.py`)

> Módulo criado em 2026-10-30. Serviço: `sigft/services/upload_fotos.py` · tela:
> `sigft/app_qt/views/upload_fotos.py` (menu **4.5. Upload de Fotos**). O caderno
> da frente, com as decisões e o que o primeiro lote real mostrou, é
> `docs/UPLOAD_DE_FOTOS.md`.

## Propósito
Sobe as fotos dos materiais de um subsistema nas fichas do PMIB (aba "Documentos
e imagens", em edição), trocando as que já estão lá, e marca a coluna
`DOCUMENTOS E IMAGENS` do `_STATUS_PMIB`.

## Entradas e saídas
- **Entradas:**
  - pasta de fotos do subsistema, com arquivos `<4 últimos dígitos do PMIB><letra>`
    (`0071.jpg`, `0071a.jpg`, `0071b.png`…), só JPEG/PNG;
  - `_STATUS_PMIB` do sistema (coluna `CÓDIGO PMIB` liga o final de 4 dígitos à ficha);
  - na tela: o modo (excluir as fotos existentes / perguntar em cada ficha), a
    velocidade do portal (fator ×1/×2/×4 das esperas) e as fichas marcadas.
- **Saídas:**
  - no portal: as fotos da pasta na ficha, descrição `imagens - <4 dígitos>` em PT e ES;
  - no `_STATUS_PMIB`: `COMPLETO` (fotos + documento) ou `INCOMPLETO` com a nota
    de célula "Faltam documentos" (fotos sem documento). Ficha que falhou não é tocada.

## Fluxo
1. `agrupar_fotos(pasta)` → `{quatro: [caminhos]}` na ordem de subida (sem letra
   primeiro) e a lista do que está fora do padrão.
2. `ler_codigos(status)` + `ligar_as_fichas(grupos, codigos)` → fichas, finais sem
   ficha e finais ambíguos (dois contratos com o mesmo final: nunca se adivinha).
3. A tela abre a escolha de fichas (`SelecaoMultiplaDialog`, com "Selecionar
   Todos") e o "Começar?"; só então o navegador, com login manual.
4. Por ficha (`processar_ficha`): `pesquisar_e_abrir` → aba "Documentos e
   imagens" → `fotos_ao_abrir` (espera as LINHAS, não o cabeçalho) → excluir
   (`excluir_todas`, de baixo para cima, conferindo que a linha saiu) ou
   perguntar → `subir_fotos` (envios de até 10 pelo `duplicadas_imagens.subir_juntas`)
   → conferência pela tabela: cada nome presente, nenhum repetido, total certo →
   `tem_documentos`.
5. `marcar_status` grava a coluna pelo editor cirúrgico (preserva comentários em
   thread e listas suspensas); a nota só é posta/removida se for do autor "SIG-FT".

## Regras que não são óbvias
- **Tudo pela tela.** O `pmib-mcp` (Drive do usuário) exclui imagens chamando o
  servidor; o SIG-FT não faz isso (regra do Luan, `core/rpa/respostas.py`).
- **Aviso no plural.** Várias fotos respondem "As imagens foram adicionadas com
  sucesso!": a palavra da seção é `image` (`PALAVRA_DA_SECAO`).
- **Envio que falha não é reenviado às cegas.** `subir_fotos` espera o diálogo
  fechar e a tabela mostrar o que ele gravou; reenvia só o que falta.
- **Esperas por condição, multiplicadas pela velocidade do portal**
  (`Esperas`): no caso bom não custam nada.

## Testes
`tests/test_upload_fotos.py` (serviço, contra um portal dublê com estado),
`tests/test_qt_tela_upload_fotos.py` (tela), `tests/test_cirurgico.py` §G (nota de
célula). Os seletores da tabela de imagens vieram de capturas de tela: só a
execução real no portal os prova.
