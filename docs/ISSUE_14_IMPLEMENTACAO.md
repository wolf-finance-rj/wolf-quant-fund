# Issue #14 — sinais de Pairs Trading integrados ao backtest

**Relação:** consome o spread/z-score da [#5](https://github.com/wolf-finance-rj/wolf-quant-fund/issues/5) e emite `TargetSignal` para o motor da [#9](https://github.com/wolf-finance-rj/wolf-quant-fund/issues/9). Protótipo de pesquisa: **não equivale à ativação da estratégia**.

## Arquivos

| Arquivo | Responsabilidade |
|---|---|
| `src/wqf/strategies/pairs/signals.py` | `PairsSignalConfig`, `generate_pairs_signals`, `run_pairs_backtest`, `load_pairs_config` |
| `config/parametros.toml` (`[strategies.pairs]`) | Parâmetros **ilustrativos** (janela, limiares, método, hedge, nocional por perna) |
| `tests/unit/test_pairs_signals.py` | Regras de entrada/saída, lacunas, look-ahead, dimensionamento e validação |
| `tests/integration/test_pairs_backtest.py` | Simulação sintética completa no motor comum, com reconciliação |

## Comportamento

1. **Entrada do z-score:** as barras (`MarketBar`) são as mesmas que vão para o motor. O spread usa o **fechamento** das duas pernas (`calculate_spread` da #5). O z-score usa `compute_rolling_zscore` da #5, que olha só para a janela passada, terminando na própria sessão.
2. **Estados e regras** (z = z-score do spread A vs. B):

   | Estado | Entra quando | Pernas | Sai quando |
   |---|---|---|---|
   | `short_spread` | z ≥ `entry_z` | vende A, compra B | z ≤ `exit_z` (média), z ≥ `stop_z` (stop) |
   | `long_spread` | z ≤ −`entry_z` | compra A, vende B | z ≥ −`exit_z` (média), z ≤ −`stop_z` (stop) |

   - `max_holding_sessions` (opcional) encerra o par depois de N sessões aberto.
   - Depois de um **stop**, o par só volta a entrar quando |z| ficar abaixo de `entry_z` (cooldown), para não reabrir no mesmo desvio.
   - Se a janela tiver desvio-padrão zero, o z-score fica `None` e o par aberto continua aberto, salvo pela saída por tempo.
3. **Sinais:** são emitidos só quando o alvo muda, com dois `TargetSignal` (um por perna) e `available_at = decision_date`. O nome da estratégia é, por padrão, `pairs:A-B`, para que pares que dividem um ativo não sobrescrevam os alvos um do outro (o motor faz o *netting*).
4. **Temporalidade:** a decisão é tomada no fechamento da sessão t e a execução sai na abertura de t+1, pelo motor. Na última sessão não há decisão (`end_of_data`), porque não haveria execução. Ao final dos dados, uma posição ainda aberta fica marcada a mercado.
5. **Lacunas de preço:** o calendário é o conjunto de sessões presente nas barras.
   - Sessão em que uma perna não tem barra: não há decisão (`gap`) e a janela do z-score **recomeça** do zero. A lacuna não é "pulada" nem preenchida.
   - Lacuna com o par **aberto** gera `ValueError`, porque não é possível marcar nem encerrar o par com segurança. O motor da #9 também rejeitaria a falta de preço de um ativo em carteira.
6. **Dimensionamento** (quantidades inteiras, calculadas com o fechamento da sessão de decisão e fixas até a saída):
   - `log_ratio`: qtd_A = ⌊N / P_A⌋ e qtd_B = ⌊N·hedge / P_B⌋
   - `price_ratio`: qtd_B = ⌊N / P_B⌋
   - `hedge_diff`: qtd_B = round(qtd_A·hedge), pois o hedge aqui é razão de ações
   - Se o nocional não comprar ao menos 1 ação de cada perna, o código gera erro.
7. **Custos, caixa e NAV:** são calculados **apenas** por `run_backtest` (#9), com as taxas de `CostRates` (#6). Este módulo não faz nenhuma conta financeira. `run_pairs_backtest` é só um atalho que gera os sinais e chama o motor.
8. **Auditoria:** `PairsSignalReport.decisions` registra, para cada sessão, o z-score, o estado antes e depois, a ação e os alvos.

## Como executar

```bash
uv sync --group dev
uv run ruff check . && uv run ruff format --check .
uv run pytest tests/unit/test_pairs_signals.py tests/integration/test_pairs_backtest.py -q
uv run pytest -q
```

Exemplo mínimo:

```python
from decimal import Decimal as D
from wqf.backtest.costs import load_cost_rates
from wqf.strategies.pairs import load_pairs_config, run_pairs_backtest

config = load_pairs_config("config/parametros.toml", asset_a="PETR3", asset_b="PETR4")
report, result = run_pairs_backtest(
    bars,  # lista de MarketBar com as duas pernas
    config,
    starting_cash=D("100000000"),
    rates=load_cost_rates("config/parametros.toml"),
)
print([(d.session, d.action) for d in report.decisions if d.action != "none"])
print(result.snapshots[-1].nav)
```

## Decisões pendentes (governança / revisão)

- Os limiares (`entry_z = 2`, `exit_z = 0.5`), a janela de 20 sessões e o nocional por perna são **ilustrativos**.
- `hedge_ratio` é fixo e vem da configuração. A estimação (OLS/cointegração) e a seleção de pares ficam fora do escopo.
- Encerramento forçado no fim do backtest, política para lacunas com o par aberto (hoje é erro) e reversão direta de `short_spread` para `long_spread` no mesmo dia (hoje sai e só reentra na sessão seguinte).
- Margem/garantia das pernas vendidas e limites de exposição continuam fora do motor (#9).
