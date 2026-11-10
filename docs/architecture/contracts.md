# Contratos compartilhados — rascunho para aprovação na Sprint 1

**Não são schemas finais.** Cada contrato precisa de especificação de tipos, unidades, fuso horário, nullability, versionamento, testes e decisões sobre disponibilidade temporal.

| Contrato | Mínimo previsto | Envolvidos |
|---|---|---|
| MarketData | ativo, data, preço, volume, disponibilidade, fonte, versão | Dados + Arquitetura |
| StrategySignal | data de decisão, ativo, estratégia, direção, peso desejado | Momentum/Pairs + Backtesting |
| SimulatedTrade | data, ativo, quantidade, preço de execução, custos | Backtesting |
| PositionLedger | posições, caixa, proventos, custos, patrimônio | Backtesting + Analytics |
| BacktestResult | retornos, operações, posições, ID de experimento | Backtesting + Analytics |
| RiskReport | exposição, volatilidade, drawdown, alertas e violações | Risco + Arquitetura |
| ClosingManifest | commit, datasets, hashes, configuração, métricas, aprovações | Arquitetura + Dados + Analytics |

## Contratos implementados (v1.0)

`MarketData`, `StrategySignal` e `SimulatedTrade` estão em `src/wqf/contracts/` (Issue #2),
como `dataclasses` imutáveis da biblioteca padrão. A única dependência nova é `tzdata`
(base oficial de fusos horários, necessária para `zoneinfo` funcionar no Windows). Cada registro é
validado na criação e, se inválido, levanta `ContractValidationError` (subclasse de
`ValueError`) com `contract`, `field` e `reason`. Os campos de texto são normalizados: o
ticker vira maiúsculo e sem espaços, como em `wqf.data`. Os números são convertidos para `float`.

```python
from wqf.contracts import MarketData, StrategySignal, SimulatedTrade
```

### Regras comuns

- **Datas de calendário** (`date`, `decision_date`, `trade_date`) são `datetime.date`. Um
  `datetime` é recusado para não misturar data de pregão com horário.
- **Instantes** (`available_at`) são `datetime` com fuso horário obrigatório.
- **Números** precisam ser finitos. São recusados `NaN`, infinito, texto e `bool`.
- **Serialização:** `to_dict()` gera tipos JSON (datas em ISO-8601). `from_dict()` valida de
  novo e recusa campos obrigatórios ausentes ou campos desconhecidos.
- **Versionamento:** `schema_version` (padrão `"1.0"`). São aceitas versões com o mesmo
  número maior (`1.x`). Uma mudança incompatível exige subir o número maior.

### MarketData

| Campo | Tipo | Unidade / regra |
|---|---|---|
| `ticker` | `str` | código do ativo, maiúsculo |
| `date` | `date` | data do pregão |
| `open`, `high`, `low`, `close` | `float` | BRL por ação, > 0, sem ajuste retroativo; `low <= open, close <= high` |
| `volume` | `float` | quantidade negociada, >= 0 |
| `available_at` | `datetime` (com fuso) | instante em que o dado passa a ser conhecido; não pode ser anterior ao fechamento do pregão (18:00 em `America/Sao_Paulo`) |
| `source` | `str` | identificador da fonte (ex.: `synthetic-equities-v1`) |
| `dividend` | `float` | opcional, BRL por ação na data ex, >= 0 (padrão 0.0) |

### StrategySignal

| Campo | Tipo | Unidade / regra |
|---|---|---|
| `decision_date` | `date` | data da decisão, usando dados disponíveis até ela |
| `ticker` | `str` | código do ativo, maiúsculo |
| `strategy` | `str` | identificador da estratégia (ex.: `momentum_12_1`) |
| `direction` | `SignalDirection` | `long`, `short` ou `flat` |
| `target_weight` | `float` | fração do patrimônio em [-1, 1]; `long` > 0, `short` < 0, `flat` = 0 |

### SimulatedTrade

| Campo | Tipo | Unidade / regra |
|---|---|---|
| `trade_date` | `date` | data do pregão da execução |
| `ticker` | `str` | código do ativo, maiúsculo |
| `quantity` | `float` | ações com sinal (compra > 0, venda < 0); zero é recusado |
| `execution_price` | `float` | BRL por ação, > 0, antes dos custos |
| `costs` | `float` | custos totais em BRL, >= 0 |

**Regra de disponibilidade (anti look-ahead).** A barra de um dia só é considerada
conhecida a partir do fechamento do pregão: `available_at >= market_close(date)`, em que
`market_close` devolve 18:00 do dia no fuso da B3 (`MARKET_TIMEZONE`, `America/Sao_Paulo`).
A comparação é feita entre instantes, então tanto faz o fuso em que `available_at` é
informado. Exemplos:

- `2026-09-30 22:00-03:00` para a barra de `2026-10-01` é recusado: em UTC já é dia 1º, mas
  na B3 ainda é véspera.
- `2026-10-01 09:00-03:00` é recusado: durante o pregão o fechamento ainda não existe.
- `2026-10-01 18:00-03:00` e `2026-10-01 21:00Z` (o mesmo instante) são aceitos.
- Datas anteriores a 2019 seguem o horário de verão da época (UTC-2) pela base de fusos.

18:00 é o fechamento mais tardio do pregão regular da B3, o que torna a regra
conservadora nos dias de pregão mais curto. Feriados e pregões reduzidos não são
verificados aqui; isso cabe a um calendário de pregões.

As escolhas abaixo foram assumidas na v1.0 e ainda dependem de confirmação do responsável
técnico: o limite de peso ±1 por ativo, a permissão de posições vendidas (`short`), a
quantidade fracionária em `SimulatedTrade` e o horário de corte de 18:00
(`MARKET_CLOSE_TIME`) da regra de disponibilidade.

## Decisões pendentes

1. Ajustes corporativos e preços disponíveis por timestamp.
2. Disponibilidade temporal para evitar look-ahead.
3. Regra de execução simulada (preço, atraso, liquidez e custos).
4. Convenção de caixa, garantias e posições vendidas.
5. Política para ausência de histórico confiável e survivorship bias.
6. Persistência e hash dos snapshots.

O comitê deverá registrar as decisões financeiras em `docs/decisions/` antes de consolidar backtests oficiais.
