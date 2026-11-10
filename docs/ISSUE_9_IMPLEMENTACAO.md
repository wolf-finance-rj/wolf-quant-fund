# Issue #9 — motor de backtesting e ledger de patrimônio

**Relação:** [Issue #9](https://github.com/wolf-finance-rj/wolf-quant-fund/issues/9) depende da [Issue #6](https://github.com/wolf-finance-rj/wolf-quant-fund/issues/6).

## Objetivo

Criar um simulador **determinístico e auditável**, que consome **posições-alvo** de estratégias e dados diários de ativos, converte mudanças de alvo em uma **única execução líquida por ativo/sessão** e registra posições, caixa e NAV (*Net Asset Value*) em cada dia de negociação.

Este pacote **complementa**, sem sobrescrever, os arquivos `accounting.py` e `costs.py` da #6. A PR da #9 deve partir de uma branch que já contenha a #6. Se a #6 não foi integrada à `main`, integre-a primeiro ou crie a branch da #9 a partir da branch local da #6.

## Arquivos novos

| Arquivo | Responsabilidade |
|---|---|
| `src/wqf/backtest/engine.py` | `MarketBar`, `TargetSignal`, calendário de sessões, execução dos alvos, custos e accruals |
| `src/wqf/backtest/ledger.py` | `LedgerEvent`, `DailySnapshot`, `BacktestResult`, cálculo de NAV e `reconcile` |
| `tests/financial/test_ledger.py` | Reconciliação financeira, preços faltantes, imutabilidade e detecção de adulteração |
| `tests/integration/test_backtest_engine.py` | Cenários sintéticos end-to-end, estratégias diferentes e casos de borda |

## Contratos e convenções **provisórias**

1. **Calendário:** sessões = datas distintas presentes nas barras (`MarketBar`). Não há consulta a calendário externo. O motor ordena datas e ativos de maneira determinística; datas faltantes de ativos mantidos em carteira causam erro explícito.
2. **Disponibilidade e look-ahead:** `TargetSignal` declara `available_at <= decision_date`, com decisão no **fechamento** da sessão de origem. A execução ocorre na **abertura da sessão seguinte disponível**, nunca no fechamento usado para gerar o sinal. Não é possível provar a origem dos dados dentro do sinal; a etapa de dados/estratégia deve validar timestamps e evitar ajustes corporativos conhecidos apenas no futuro.
3. **Preços:** `open_price` = preço de execução em BRL por ação, `close_price` = preço de marcação a mercado em BRL por ação; ambos são `Decimal`, positivos e finitos. A execução usa unidades inteiras. Não há slippage adicional além dos componentes parametrizados da #6.
4. **Sinais:** `TargetSignal` especifica **quantidade-alvo inteira por estratégia e ativo**, não peso percentual. O último alvo de cada estratégia/ativo permanece ativo até ser substituído (inclusive por zero). O motor soma os alvos de estratégias distintas no mesmo ativo e executa a diferença entre a posição atual e o alvo líquido. Uma alteração de alvo que não muda a posição líquida não gera operação nem taxa.
5. **Custos:** a contabilidade usa `apply_trade`/`apply_borrow_charge` da #6. Cada execução/intervalo tem ID distinto. **Custos já debitados do caixa não são subtraídos novamente do NAV.** A alíquota de referência do manual é 0,15% da operação e 2% a.a. no aluguel short, mas as taxas são recebidas via `CostRates`.
6. **Aluguel de short:** entre o fechamento da sessão anterior e a sessão atual, incide sobre a posição short anterior, avaliada ao **fechamento anterior**, com dias corridos ACT/365 e arredondamento por intervalo. Inclui finais de semana sem sessões. Isso é uma convenção técnica de simulação, não uma regra de faturamento oficial de corretora.
7. **CDI/caixa:** `cash_interval_rates`, quando fornecido, é um mapa obrigatório para **todas** as sessões após a primeira, com a taxa **efetiva de cada intervalo**. A remuneração aplica a taxa ao saldo **positivo no fechamento anterior**, mesmo se o custo de aluguel é debitado na abertura da sessão seguinte. Se `None`, o rendimento é zero para testes *offline*; **não equivale à política oficial de caixa a 100% do CDI**. Taxas reais devem vir do pipeline de dados com convenção aprovada.
8. **Saldo negativo/short:** caixa negativo é contabilizado sem financiamento; caixa de venda a descoberto é registrado, mas pode estar bloqueado como garantia na realidade. **O motor não valida margem, garantia, liquidez, poder de compra nem limites de alavancagem.** Portanto, não usar esta versão para certificar aderência à política operacional do fundo.
9. **Rebalanceamento:** por padrão, só executa quando recebe sinais. A opção `monthly_first_session_only=True` restringe a execução à primeira sessão disponível de cada mês, mas **não gera automaticamente sinais mensais**. Para executar no início do mês, a decisão deve ser fornecida na última sessão anterior. Decisão tática sobre regras e exceções precisa de aprovação da governança.
10. **Imutabilidade e auditoria:** os estados da #6 são imutáveis; snapshots e registros mantêm cópias somente-leitura. Cada execução registra data da decisão, alvos por estratégia, alvo líquido, preço, quantidade assinada, custo e variação de caixa. O ledger reconcilia caixa, quantidades, custos por sessão e NAV.

As regras 2, 3, 6, 7, 8 e 9 precisam ser avaliadas formalmente pelo comitê antes de serem tratadas como contratos definitivos de execução.

## Como executar no Dev Container

Após aplicar os arquivos novos **sobre uma cópia que já contenha a Issue #6**:

```bash
uv run ruff format .
uv run ruff check .
uv run ruff format --check .
uv run pytest tests/financial tests/integration -q
uv run pytest -q
```

Se o Ruff apontar `EXE002`, verifique as permissões de execução dos arquivos Python (`chmod 644 ...`) e como o volume Docker/Windows preserva os bits de permissão.

## Exemplo reproduzível (BRL)

```python
from datetime import date
from decimal import Decimal as D
from wqf.backtest.costs import CostRates
from wqf.backtest.engine import MarketBar, TargetSignal, run_backtest

D1 = date(2026, 11, 2)
D2 = date(2026, 11, 3)
D3 = date(2026, 11, 4)
rates = CostRates(other_rate=D("0.0015"), annual_borrow_rate=D("0.02"))

result = run_backtest(
    bars=[
        MarketBar(D1, "PETR4", D("10"), D("100")),
        MarketBar(D2, "PETR4", D("10"), D("11")),
        MarketBar(D3, "PETR4", D("12"), D("13")),
    ],
    signals=[
        TargetSignal(D1, D1, "momentum", "PETR4", 10),
        TargetSignal(D2, D2, "momentum", "PETR4", 0),
    ],
    starting_cash=D("1000"),
    rates=rates,
)

assert [day.nav for day in result.snapshots] == [D("1000.00"), D("1009.85"), D("1019.67")]
```

A compra ocorre na abertura de D2 (10 ações × R$10 = R$100, custo R$0,15); patrimônio no fechamento D2 = 899,85 + 10 × 11 = R$1.009,85. A venda ocorre na abertura de D3 (10 × 12 = R$120, custo R$0,18); saldo/NAV final R$1.019,67.

## Modelo de auditoria

- **Journal**: `result.events` com `kind = trade | borrow | cash_interest`, `event_id` e `cash_delta`.
- **Snapshot**: `result.snapshots` por sessão com `cash`, `positions`, `closing_prices`, `net_market_value`, `nav`, `transaction_costs`, `borrow_costs`, `cash_interest`, IDs dos eventos.
- **Invariant financeiro**: `NAV_t = cash_t + Σ (quantidade_assinada_t × preço_fechamento_t)`; posição vendida entra com sinal negativo.
- **Reconciliação**: `reconcile(result, starting_cash)` recalcula caixa a partir do journal, atualiza posições, confere custos por sessão e recalcula NAV.

## Testes / status

Validação isolada com **dados sintéticos**, Python 3.13 no ambiente de preparação:

- 18 novos testes da #9 passando.
- 32 testes passando quando combinados com a cópia de referência da #6.

**Pendente:** rodar em Python **3.12**, `ruff` e CI real do repositório no Dev Container do time. Não considerar a Issue aprovada antes da PR, CI verde e revisão independente.

## Fora de escopo / próximos incrementos

- Ingestão de preços, eventos corporativos e snapshots reais (#8).
- Estratégias Momentum/Pairs e geração de sinais (outras Issues).
- Execução automática com pesos percentuais; conversão dos pesos em quantidades por preço/capital requer política específica.
- Margens, garantias, empréstimo e financiamento, liquidez/impacto de mercado, stops, proventos e reconciliação com corretoras.
- Persistência do ledger em arquivos/banco, manifests de execução e CLI (#10).
- Documentos financeiros, cartas de performance e aprovação de fechamento (outras Issues).

## Texto sugerido para a Pull Request

**Título:** `feat(backtest): adiciona motor por datas e ledger de patrimônio (#9)`

**Resumo:** Introduz motor determinístico de datas que recebe alvos de estratégias, executa ordens líquidas na abertura seguinte, reutiliza a contabilidade da #6 e produz snapshots diários auditáveis de posições, caixa, custos e NAV. Inclui reconciliação e testes financeiros/integrados sintéticos.

**Checklist:**
- [ ] Issue #6 incluída na base da branch
- [ ] Formatação, Ruff e Pytest aprovados no Dev Container
- [ ] Regras de execução e limitações revisadas com equipe de Backtesting/Risco
- [ ] CI aprovado e revisão independente solicitada

`Closes #9`
