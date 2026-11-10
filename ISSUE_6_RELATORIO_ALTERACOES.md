# Issue #6 — Relatório de alterações: operações, custos e caixa

**Projeto:** Wolf Quant Fund — Wolf Finance  
**Issue:** [#6 — Implementar cálculos de operações, custos e caixa](https://github.com/wolf-finance-rj/wolf-quant-fund/issues/6)  
**Tipo:** Implementação do módulo de backtesting (contabilidade de operações)  
**Status:** Implementação e checks locais concluídos; revisão de código, CI e aprovação financeira ainda pendentes.

## 1. Objetivo da alteração

Esta entrega introduz funções financeiras isoladas e testáveis para simular operações de compra e venda de ações, atualizar posições e saldo de caixa e calcular os custos operacionais de cada execução. Também contempla o custo de aluguel de ações em posições vendidas (*short*).

A implementação busca atender aos critérios da Issue #6: conferir resultados com cálculos sintéticos manuais, evitar cobranças duplicadas e fornecer testes automatizados reproduzíveis. **Não implementa o motor completo de backtest**, que é escopo da Issue #9.

## 2. Arquivos criados e alterados

| Arquivo | Tipo | Mudança |
|---|---|---|
| `src/wqf/backtest/__init__.py` | Novo | Inicialização do pacote de backtesting. |
| `src/wqf/backtest/costs.py` | Novo | Modelos de taxas e custos, arredondamento monetário, aluguel short e leitura de configuração TOML. |
| `src/wqf/backtest/accounting.py` | Novo | Modelos de operação e estado da conta, aplicação de trades e cobrança de aluguel. |
| `tests/financial/test_accounting.py` | Novo | Testes financeiros com valores esperados explícitos. |
| `config/parametros.toml` | Alterado | Adicionada seção `[backtest.costs]` com taxas de referência configuráveis. |
| `docs/ISSUE_6_IMPLEMENTACAO.md` | Novo | Notas técnicas, exemplo de uso, premissas e dependências. |

> A relação acima descreve os arquivos do pacote de implementação da Issue #6. Ajustes locais adicionais de permissões e lint também foram realizados durante a validação.

## 3. O que foi implementado

### 3.1. Custos operacionais — `costs.py`

- `CostRates`: representa taxas como `Decimal` nas categorias `brokerage_rate`, `exchange_rate`, `impact_rate`, `other_rate` e `annual_borrow_rate`.
- `TradeCosts`: detalha os custos por componente e fornece a propriedade `total`.
- `transaction_costs(notional, rates)`: calcula os custos sobre o valor financeiro da operação (*notional*), evitando somar novamente o custo total às parcelas individuais.
- `brl(value)`: arredonda valores monetários para centavos com `ROUND_HALF_UP`.
- `borrow_cost(short_quantity, price, days, rates)`: calcula o aluguel de posição vendida por juros simples e convenção **ACT/365**.
- `load_cost_rates(path)`: carrega as taxas de um arquivo TOML, mantendo a precisão decimal.

**Parâmetros de referência:**

| Parâmetro | Valor | Representação no código |
|---|---:|---:|
| Custo total por operação | 0,15% | `0.0015` |
| Aluguel anual de posição vendida | 2,00% a.a. | `0.02` |

O manual do fundo informa **0,15% como custo total**, mas não aprova uma divisão específica entre corretagem, emolumentos e impacto. Por isso, a implementação inicial concentra esse custo em `other_rate`, com os outros componentes zerados. **Uma futura divisão não deve ser adicionada por cima dos 0,15%.**

### 3.2. Contabilidade de operações — `accounting.py`

Foram definidos:

- `Side`: enum de direção `BUY` ou `SELL`.
- `Trade`: operação identificada por `trade_id`, ativo, direção, quantidade inteira e preço positivo em BRL/ação.
- `AccountState`: estado com caixa, mapa de posições e IDs já processados.
- `TradeResult`: resultado contendo conta atualizada, notional, custos e variação do caixa.
- `apply_trade(account, trade, rates)`: aplica uma operação à conta sem modificar o estado original.
- `apply_borrow_charge(...)`: debita uma cobrança de aluguel short identificada explicitamente.

**Convenção das posições:** quantidade positiva significa posição comprada (*long*); quantidade negativa, vendida (*short*); quantidade zero remove o ativo do mapa.

**Movimentação do caixa:**

```text
notional = quantidade × preço
custo_operacional = notional × taxa_total (arredondado)

COMPRA: caixa_novo = caixa_anterior - notional - custo_operacional
VENDA:  caixa_novo = caixa_anterior + notional - custo_operacional

posição_nova = posição_anterior + quantidade_assinada
quantidade_assinada = +quantidade para BUY; -quantidade para SELL
```

Os custos de transação são calculados uma única vez sobre a execução inteira, inclusive quando a operação fecha uma posição e abre outra na direção contrária (*reversão*).

**Proteção contra duplicidade:** cada operação usa a chave `trade:<trade_id>`; cada cobrança de aluguel usa `borrow:<charge_id>`. Uma tentativa de reutilizar o mesmo identificador no estado atualizado gera erro em vez de aplicar o débito novamente. Essa proteção vale para a trajetória do `AccountState` em memória; persistência e ledger histórico são assuntos da Issue #9.

### 3.3. Aluguel de posições vendidas

O custo de aluguel segue a fórmula:

```text
aluguel = |quantidade_short| × preço_de_referência × taxa_anual × dias / 365
```

- A cobrança só é positiva se houver posição short no ativo.
- A quantidade usada é o módulo da posição negativa.
- O débito é feito uma vez por `charge_id`.
- Não há agendamento automático de datas: a chamada é explícita.

### 3.4. Configuração financeira — `parametros.toml`

Foi adicionada a configuração de referência:

```toml
[backtest.costs]
brokerage_rate = "0"
exchange_rate = "0"
impact_rate = "0"
other_rate = "0.0015"
annual_borrow_rate = "0.02"
```

Esses valores são **referências do manual**, e não uma aprovação automática para operação oficial. Mudanças nas premissas financeiras devem passar pela governança do fundo.

## 4. Exemplos de conferência manual

Os testes usam operações sintéticas e preços em reais:

| Cenário | Cálculo | Resultado esperado |
|---|---|---|
| Compra de 10 ações a R$ 10, com caixa inicial R$ 1.000 | `1.000 - 100 - 0,15` | Caixa **R$ 899,85**; posição **+10** |
| Venda das 10 ações a R$ 12, após a compra | `899,85 + 120 - 0,18` | Caixa **R$ 1.019,67**; posição zerada |
| Venda short de 10 ações a R$ 10 | `1.000 + 100 - 0,15` | Caixa contábil **R$ 1.099,85**; posição **−10** |
| Cobertura desse short a R$ 9 | `1.099,85 - 90 - 0,14` | Caixa contábil **R$ 1.009,71**; posição zerada |
| Reversão: posição +5, seguida de venda de 8 ações a R$ 10 | A venda de R$ 80 tem custo único de R$ 0,12 | Posição **−3** |
| Aluguel: short de 100 ações a R$ 10, por um dia | `100 × 10 × 0,02 / 365` | **R$ 0,05** após arredondamento |

**Observação:** o caixa de uma venda short inclui os recursos da venda para fins contábeis, mas **não equivale a caixa livre para saque ou novas compras**. Regras de margem, garantia e bloqueio desses recursos ainda não foram implementadas.

## 5. Testes e validação

O arquivo `tests/financial/test_accounting.py` cobre, entre outros casos:

- Compra e venda com reconciliação do saldo de caixa.
- Abertura e cobertura de posições short.
- Reversão de long para short e de short para long.
- Cobrança única de execução e de aluguel por identificador.
- Exclusão da taxa de aluguel para posições long.
- Separação dos componentes de custos sem dupla contagem.
- Validação de preço, quantidade, taxas e dias inválidos.
- Independência entre ativos e leitura de taxas do TOML.
- Arredondamento de custos em operações pequenas.

### Resultado observado no Dev Container

Comandos executados na raiz `/app`:

```bash
uv run ruff check .
uv run ruff format --check .
uv run pytest -q
```

Resultado informado na validação local de **10/11/2026**:

```text
All checks passed!
23 files already formatted
15 passed in 0.25s
```

Os problemas de lint identificados durante a integração foram corrigidos, incluindo organização de imports, simplificação de construções `Decimal`, adequação do tipo da exceção para `Side` inválido e remoção da permissão de execução de arquivos Python que não são scripts executáveis. **O resultado acima é local; a execução do CI da Pull Request ainda deve ser verificada no GitHub.**

## 6. Decisões técnicas e riscos

| Tema | Decisão atual | Limitação / atenção |
|---|---|---|
| Precisão monetária | Uso de `Decimal` e arredondamento para centavos | Políticas de arredondamento precisam ser mantidas consistentes nas demais etapas. |
| Custos de transação | Percentuais parametrizados, com custo total de referência de 0,15% | Rateio entre componentes precisa de aprovação. |
| Aluguel short | Taxa simples ACT/365 sobre posição marcada a preço informado | Calendário, marcação e periodicidade da cobrança ainda não são automáticos. |
| Contabilização | Estado de conta retornado sem mutação do estado anterior | Não há persistência nem ledger completo. |
| Duplicidade | IDs processados armazenados no estado da conta | A unicidade precisa ser preservada pelo futuro motor que gerará as operações. |
| Short e caixa | Receita da venda entra no caixa contábil | Garantias e disponibilidade efetiva não estão modeladas. |

## 7. Fora do escopo e dependências

Estão **fora da Issue #6** e deverão ser tratados em entregas posteriores, especialmente na Issue #9:

- Motor de execução com datas, ordem temporal, preços de execução e rebalanceamento.
- Ledger histórico persistente de operações, eventos de caixa e posições.
- Regras de margem, garantias e disponibilidade do caixa de vendas a descoberto.
- Proventos, desdobramentos e outros eventos corporativos.
- Liquidez, impacto dinâmico de mercado, limites de exposição e controle de poder de compra.
- Integração de dados de mercado e geração de resultados completos de backtest.

## 8. Checklist de entrega

- [x] Funções de operações, custos e atualização de caixa implementadas.
- [x] Testes financeiros sintéticos com expectativas explícitas.
- [x] Verificação local do Ruff e Pytest concluída.
- [ ] Revisar `git diff` e confirmar ausência de arquivos locais (como `.idea/`) e segredos.
- [ ] Revisão independente da implementação e das premissas financeiras.
- [ ] Pull Request referenciando `Closes #6`, com CI verde.
- [ ] Registrar eventuais decisões financeiras pendentes no fluxo de governança.

## 9. Texto sugerido para a Pull Request

**Título:** `feat: implementa operações, custos e caixa do backtest (#6)`

**Resumo:** Implementa a camada inicial de contabilidade do Wolf Quant Fund, com operações long/short, atualização de posições e caixa, custos parametrizados, aluguel de posições vendidas e proteção contra cobranças duplicadas. Adiciona testes sintéticos que verificam os resultados contra cálculos manuais. Os checks locais passaram (Ruff e 15 testes). A execução temporal e o ledger completo seguem fora de escopo e serão integrados na Issue #9.

**Issue relacionada:** `Closes #6`

---

**Referências internas:** `docs/fundo.md`, `docs/architecture/contracts.md`, `docs/architecture/overview.md` e Issue #6.
