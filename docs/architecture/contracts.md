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

## Decisões pendentes

1. Ajustes corporativos e preços disponíveis por timestamp.
2. Disponibilidade temporal para evitar look-ahead.
3. Regra de execução simulada (preço, atraso, liquidez e custos).
4. Convenção de caixa, garantias e posições vendidas.
5. Política para ausência de histórico confiável e survivorship bias.
6. Persistência e hash dos snapshots.

O comitê deverá registrar as decisões financeiras em `docs/decisions/` antes de consolidar backtests oficiais.
