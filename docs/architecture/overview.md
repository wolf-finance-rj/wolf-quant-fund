# Arquitetura inicial

Fluxo esperado: providers externos → ingestão e validação → dados padronizados e snapshots → sinais de Momentum/Pairs → backtesting compartilhado → ledger/portfólio → risco → analytics e carta.

As estratégias devem emitir sinais ou posições-alvo, não retornos finais independentes. A contabilidade, custos, caixa e execução simulada ficam concentrados no motor comum.

## Stack inicial

Python 3.12, uv, Pytest, Ruff. Polars/Pandas, DuckDB, Pydantic/Pandera, statsmodels e Plotly/Streamlit serão adicionados por Issues específicas, conforme necessidade demonstrada.

## Gates da primeira sprint

- Ambiente instalável pelos seis integrantes.
- Contratos discutidos e aprovados com casos sintéticos.
- CI executando testes e lint.
- Interfaces e responsáveis documentados.
