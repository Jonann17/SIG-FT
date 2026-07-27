"""Pacote `sigft.core` — núcleo de lógica pura da refatoração do SIG-FT.

Ver docs/refatoracao/PLANO_REFATORACAO.md, seção "Arquitetura-alvo". Tudo
dentro de `core/` é testável sem as dependências pesadas de produção
(pandas, openpyxl, selenium, google-generativeai, ...): os módulos deste
pacote usam SOMENTE a biblioteca padrão, para permanecerem importáveis no
ambiente de teste (ver tests/conftest.py).
"""
