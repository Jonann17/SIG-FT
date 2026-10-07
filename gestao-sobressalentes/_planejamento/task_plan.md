# task_plan.md — Cofre de Sobressalentes

## Objetivo
Documentar, no nível de detalhe operacional, todo o sistema de gestão de materiais
sobressalentes do Consórcio de Modernizacao de Itaipu (CMI): contexto contratual,
exigencia normativa, processo de ponta a ponta, gerenciamento, deficiencias e o
aplicativo SIG-FT.

## Decisões travadas (rodada de grill, 2026-08-31)
- **Local**: `~/OneDrive/Documents/Obsidian/Sobressalentes-Itaipu`. Fora do Box.
- **Audiencia**: Luan + equipe CMI. Onboarding e handover. Tom institucional;
  dados de gestão entram, julgamento sobre pessoas não entra.
- **Natureza**: hibrido. Notas escritas a mao + pasta `_gerado/` regenerada por
  script a partir das planilhas do Box. **Leitura do Box apenas, nunca escrita.**
- **LMR**: documentada agora em profundidade. O plano de ação das fichas emitidas
  sem LMR fica para sessão dedicada.

## Passos
- [x] Levantar ET Geral 6047-20-T0018 (cap. 18 + Anexos I, II, III)
- [x] Extrair fluxo da Apresentação PMIB R5
- [x] Ler ata AR/EN.DT/001/2026 e procedimento de fichas duplicadas
- [x] Ler proposta de revisão da Aplicação LMR (20/08/2026)
- [x] Mapear estrutura de pastas e templates
- [x] Agregar KPIs da mapeadora
- [x] Clonar e ler o SIG-FT
- [x] Escrever o cofre
- [x] Scripts de regeneracao de `_gerado/` (panorama + mapa de conexoes)
- [ ] **Rodar graphify sobre o cofre** — BLOQUEADO: a passagem semantica sobre
      as 48 notas exige `GEMINI_API_KEY`/`GOOGLE_API_KEY` no ambiente, ou que o
      agente hospedeiro faca a extração. Ver [[progress]].
- [ ] Sessão dedicada: plano de ação das fichas sem Aplicação LMR
- [ ] Sessão dedicada: gargalo de gestão das Listas de Preços

## Fora de escopo (deliberado)
- Escrever qualquer coisa dentro do Box.
- Rodar graphify sobre o Box (a passagem semantica manda documento para um modelo).
- Alterar o repositorio SIG-FT.
