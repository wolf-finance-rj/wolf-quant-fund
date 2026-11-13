# Issue #6 — operações, custos e caixa

## Escopo

- `costs.py`: taxas `Decimal`, custos por transação e aluguel de short ACT/365.
- `accounting.py`: compra/venda, reversão, posições inteiras com sinal, caixa e cobrança única por ID.
- `config/parametros.toml`: taxas de referência do manual, em formato textual decimal.
- `tests/financial/test_accounting.py`: testes de reconciliação sintética.

## Executar dentro do Dev Container

```bash
uv run ruff check .
uv run ruff format --check .
uv run pytest -q
```

## Exemplo mínimo

```python
from decimal import Decimal
from wqf.backtest.accounting import AccountState, Side, Trade, apply_trade
from wqf.backtest.costs import load_cost_rates

rates = load_cost_rates("config/parametros.toml")
state = AccountState(Decimal("1000"))
result = apply_trade(
    state,
    Trade("exec-001", "PETR4", Side.BUY, 10, Decimal("10")),
    rates,
)
assert result.account.cash == Decimal("899.85")
assert result.account.positions["PETR4"] == 10
```

## Premissas explícitas

- Quantidade em ações inteiras; preços positivos em BRL/ação, `Decimal`.
- Compra debita e venda credita caixa. Posição assinada: long positiva; short negativa.
- Custos agregados representam 0,15% do notional, não duplicados. A separação entre corretagem, emolumentos e impacto é pendente de aprovação e está no campo `other_rate`.
- Custos monetários são arredondados para centavos, `ROUND_HALF_UP`.
- Aluguel de short usa quantidade absoluta × preço marcado × taxa anual × dias/365, sem capitalização; chamado explicitamente por ID.
- IDs de execução e cobrança precisam ser únicos ao longo da trajetória contábil.
- Caixa contabiliza recursos da venda a descoberto, **não** representa caixa livre para saque; margem, garantias, financiamento, verificação de poder de compra, liquidez, proventos, data de execução e ledger histórico ficam fora da Issue #6.
- Parametrização corresponde a valores de referência, não aprovação de governança para operação oficial.

## Próximos passos / dependência da Issue #9

- Especificar regras de garantia/margem e tratamento do caixa de short.
- Integrar controle de datas, execução e preços, ledger temporal, proventos e rebalanceamento.
- Modelar limites de exposição, liquidez e bloqueio de caixa.
