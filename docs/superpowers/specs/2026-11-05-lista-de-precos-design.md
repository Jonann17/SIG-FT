# Lista de Preços como módulo (2026-11-05)

Pedido do Jonathan (05/11): "Doc pack não precisa trabalhar com listas de preços. O agente do
webhook não olha pra isso. Vamos desenvolver lista de preços em módulo à parte." Com duas
partes: (1) conferir se o sistema tem lista com preço e, se não tiver, colocar o arquivo,
copiando o conteúdo do `_STATUS_PMIB` preenchido; (2) um submódulo que confere a lista com o
`_STATUS_PMIB`, **por pasta específica e não por varredura**, com o link da pasta para a
conferência humana e um botão de atualizar — e, se a lista já tiver preços, **acusar** que
está valorizada e diverge.

## Decisões

1. **Módulo 8.3 "Lista de Preços"**, na Gestão, seção em abas (como DocPack e Conferência de
   Listas): **Criar / preencher** (varredura) e **Conferir** (uma pasta).
2. **DocPack sem lista com preço**: a Etapa 1 não cria o `.xlsm` nem pede o template; a Etapa
   2 só grava o `_STATUS_PMIB`. O `codigo_lista_de_precos` e as células da Capa vieram para
   `services/lista_precos_arquivo.py`.
3. **Detecção**: `<código PB021>` na pasta do `_STATUS_PMIB`, senão qualquer `PB021`/`PB020-0x`
   (legado) que não seja `_STATUS_PMIB` — a mesma regra do painel.
4. **Criar só onde não há** lista; `open(..., "xb")`; o título da Capa vem da DESCRIÇÃO da
   mapeadora lembrada (opcional), senão do nome da pasta.
5. **Casamento dos itens**: CÓDIGO PMIB → código de material → descrição. Comparados: QTD.,
   UNID., DESCRIÇÃO.
6. **Atualizar preserva** VALOR UNITÁRIO (e CÓDIGO GE / TIPO DE ENTREGA, que só a lista tem) dos
   itens que continuam; valorizada pede confirmação com "ATENÇÃO"; removidos e novos vão ao log.
7. **Escrita cirúrgica** (XML); o openpyxl só lê.

## Fora

Preço vindo de algum lugar (nunca se inventa); escrever na mapeadora; conferência em
varredura (pedido explícito: por pasta).
