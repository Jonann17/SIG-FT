# Configuração (engrenagem) e idioma do SIG-FT (2026-10-22)

Pedido do Jonathan, 2026-10-21/22: juntar numa engrenagem tudo o que hoje é
configurável e espalhado pela Home, e deixar o app em **espanhol, português e
inglês**, perguntado na primeira abertura e trocável na engrenagem.

São duas partes, entregues **juntas, num PR só e numa rc só** (decisão do
Jonathan, 2026-10-22), com um plano único:

- **Parte A: a engrenagem.** Pequena, e é onde o idioma vai morar.
- **Parte B: o idioma.** Grande (cerca de 1.300 textos de interface).

## Decisões (tomadas com o Jonathan)

| Pergunta | Decisão |
|---|---|
| O que muda de idioma | **Só a interface**: botões, títulos, rótulos, dicas, janelas, caixas de aviso e de pergunta, Ctrl+K, resumo do lote, aviso do Windows. **Não** mudam: as mensagens do console (o que serviços e robôs escrevem), o portal PMIB, as planilhas e fichas geradas, o CHANGELOG. |
| Quando a troca vale | **Ao reiniciar.** A engrenagem avisa "O idioma muda na próxima vez que o SIG-FT abrir" e oferece "Reiniciar agora". Cada tela lê seus textos uma vez, ao ser montada. |
| Onde fica a engrenagem | **Só na Home**, no canto superior direito, na linha do título. Também pelo Ctrl+K ("Configuração"). |
| O que vai para a engrenagem | Aparência (tema e letra), Idioma, Seu nome, Avisos (aviso do Windows), Inteligência artificial (Chaves de API, Modelos de IA), Atualizações (versões de teste, procurar atualizações). |
| O que fica na Home | O saudação, Atividades do dia e Gastos de IA. |

A maquete aprovada (capturas offscreen) mostrou a Home limpa com o ⚙ à direita
e a janela com as seis seções.

## Parte A: a engrenagem

### Comportamento

- Botão ⚙ (ícone Lucide `settings`, `variante="fantasma"`) à direita na linha do
  título da Home, com a dica "Configuração". Abre a **janela Configuração**
  (`QDialog` não modal, uma só aberta por vez; abrir de novo traz a mesma para
  a frente).
- Seções, de cima para baixo, títulos à esquerda:
  1. **Aparência**: Escuro / Claro / Sistema; Letra normal / Letra grande. O
     escolhido fica marcado (o `ativo` de hoje). Aplica na hora (`tema.aplicar`,
     `letra.aplicar`).
  2. **Idioma**: Español / Português / English, "O idioma muda na próxima vez
     que o SIG-FT abrir" e "Reiniciar agora" (só habilitado quando a escolha
     difere do idioma em uso).
  3. **Seu nome**: campo com o nome do saudação (`nome.guardar` ao sair do campo
     ou Enter; vazio tira o nome). A Home atualiza o saudação na hora.
  4. **Avisos**: "Avisar no Windows quando uma tarefa terminar ou pedir algo"
     (o `aviso_windows` de hoje).
  5. **Inteligência artificial**: "Chaves de API" e "Modelos de IA" abrem as
     MESMAS janelas que os botões da Home abrem hoje.
  6. **Atualizações**: "Receber versões de teste" (a caixa de hoje) e "Procurar
     atualizações" (a ação de hoje).
- Rodapé: "Fechar". Não há "Salvar": cada mudança vale e é guardada na hora,
  como hoje.
- A Home perde: o seletor de tema e o de letra da linha do título, a caixa
  "Avisar no Windows" da linha do subtítulo, os botões "Modelos de IA", "Chaves
  de API" e "Atualizações" da barra e a caixa "Versões de teste". Ficam
  "Atividades do dia" e "Gastos de IA". O ⚙ ocupa a direita da linha do título.
- Ctrl+K: ganha "Configuração"; as ações de tema, letra, chaves, modelos e
  atualizações continuam no Ctrl+K (fazem o mesmo que antes).

### Como

- `sigft/app_qt/views/configuracao.py` (novo): `JanelaConfiguracao(QDialog)`.
  Reusa as funções que já existem (`tema`, `letra`, `nome`, `aviso_windows`,
  os métodos da Home que abrem Chaves/Modelos/Atualizações). Nenhuma regra nova
  de negócio: a janela só reorganiza o que existe.
- `catalogo.py`: as ações da Home que mudam de lugar continuam definidas lá
  (fonte única); ganha `SECOES_DA_CONFIGURACAO` com a ordem e os textos das
  seções. `ACOES_DA_HOME` passa a ter só as que ficam na barra.
- Cor só em `estilo.py`; sem travessão; o teste de medida da Home é reescrito
  para o layout novo, com o motivo no commit.

### Testes

- Abrir a janela pela Home e pelo Ctrl+K; uma só instância.
- Cada controle faz o mesmo que fazia na Home (tema e letra mudam e ficam
  lembrados; aviso do Windows liga/desliga; versões de teste; os três botões
  chamam as mesmas funções).
- Home sem os itens que saíram; o ⚙ não cobre nada e não alarga a Home, em
  letra normal e Grande, nos dois temas.

## Parte B: o idioma

### Comportamento

- Idiomas: `es` (Español), `pt` (Português), `en` (English). Guardado nas
  preferências (`idioma`).
- **Primeira abertura** (sem `idioma` nas preferências, o que inclui quem
  recebe a atualização): antes de a janela principal ser montada, uma caixa
  pequena pergunta "Idioma / Language" com os três botões, cada um escrito no
  seu idioma. A janela já abre no escolhido (sem reiniciar). Depois vem a
  pergunta do nome, como hoje, já no idioma escolhido. Fechar a caixa sem
  escolher: português, e pergunta de novo na próxima abertura.
- Na engrenagem, trocar e "Reiniciar agora": o app guarda o idioma, abre uma
  nova instância de si mesmo e fecha a atual (com a mesma pergunta de "tarefa
  rodando" que o fechar de hoje faz; se houver tarefa, não reinicia).
- Texto sem tradução cai no português (nunca vazio, nunca a chave).

### Como

- `sigft/app/idioma.py` (novo, sem Qt): `atual()`, `definir(codigo)`,
  `t(texto_pt, **valores)`. A chave é o **próprio texto em português** que está
  no código hoje: a troca no código é `"Selecionar Excel"` → `t("Selecionar Excel")`,
  e o português continua legível no código-fonte. Textos com valores usam
  `{nome}` (`t("Ficha {atual} de {total}", atual=3, total=8)`).
- Catálogos: `sigft/app/idiomas/es.json` e `en.json` (`{"texto pt": "tradução"}`).
  O português não tem catálogo (é a chave).
- Ferramenta `tools/textos_da_interface.py`: varre `sigft/app_qt` e
  `sigft/app/textos_*.py` atrás das chamadas `t("...")`, lista as que faltam em
  cada catálogo e as que sobram. Teste: nenhum `t()` sem entrada em `es` e `en`.
- Teste-guarda (como o de cor crua): texto de interface literal fora de `t()`
  nas telas já convertidas reprova; a lista de telas convertidas cresce a cada
  etapa.
- Traduções: primeira versão feita por mim, com um glossário de termos que
  **não** se traduzem (PDM, PMIB, SAM-GM, STATUS_PMIB, LMR, AutoSpec, Gestão
  PMIB como nome de módulo...) e termos fixos (ficha → ficha técnica / technical
  sheet...). O Jonathan (es) e quem ele indicar revisam antes do Release.
- Os textos dos diálogos (`app/textos_dialogos.py`), as dicas
  (`app/textos_dicas.py`) e o catálogo de módulos (`catalogo.py`) entram cedo:
  são os mais vistos.

### Ordem das tarefas (tudo no mesmo PR)

1. Infraestrutura (`idioma.py`, catálogos, ferramenta, testes) + caixa da
   primeira abertura + seção Idioma da engrenagem ligada + menu lateral, Home,
   engrenagem, Ctrl+K, splash, textos de diálogo e dicas.
2. Telas, de três em três (Cria Fichas, Planilhas PMIB, Analyzer; Upload
   Condições, Tradutor, Upload Specs; Correção de PDM, Upload duplicadas,
   AutoSpec; Aplicação LMR, PMIB Manager, Busca PMIB), com as janelas
   auxiliares de cada uma.
3. Revisão das traduções e fechamento (CHANGELOG, docs, mural).

A tela do AutoSpec é do Rafael (cedida ao Jonathan): a etapa que a converte
troca só literais por `t()`, sem mudar comportamento; os testes de tela dele
que travam textos passam a comparar com `t(...)` no idioma português.

### Riscos

- **Medidas**: textos em espanhol e inglês têm outro comprimento. O ajuste de
  largura da letra Grande (`letra._ajustar_largura`) é estendido para valer
  também na troca de idioma, e um teste varre as 12 telas nos três idiomas
  atrás de texto cortado.
- **Testes que travam texto**: passam a usar `t()` ou a rodar com `pt`.
- **Texto montado com f-string**: precisa virar `t("... {x} ...", x=...)`; a
  ferramenta acusa `t(f"...")`.

## Entrega

Um PR só (engrenagem + idioma completo nas 12 telas) e uma rc só, depois da
revisão final da branch inteira. A ordem das tarefas acima é a ordem do plano;
nenhuma vai à branch oficial antes das outras.
