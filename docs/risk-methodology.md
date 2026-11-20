# Portfolio risk estimates

These figures describe a hypothetical portfolio rebalanced monthly to the latest
statement holdings at current market weights. They do not measure the club's
realized account performance. Today's selection introduces hindsight and survivor
bias. Results are gross of fees, taxes and trading costs.

## Inputs and monthly returns

- Use 37 month-end adjusted closes to obtain 36 monthly returns, ending with the
  month before the portfolio price date. Incomplete current months are excluded.
- Yahoo Finance adjusted closes incorporate corporate action adjustments.
- Stock weight = current position value / total portfolio value. Residual cash
  earns zero. Each month's stock returns are multiplied by these fixed weights.
- Benchmark is the S&P 500 price index (^GSPC). It excludes dividend income,
  whereas adjusted holding prices incorporate dividends; beta is explicitly
  labeled against the price index, not a total-return benchmark.
- Missing, nonpositive, nonfinite or stale monthly inputs yield unavailable
  metrics. Missing holdings are not dropped or reweighted.

## Treasury proxy

Use FRED DGS3MO, quoted on an investment basis. Take the last observation in the
previous month and estimate monthly return as annual yield * calendar days / 365.
This is a yield accrual proxy, not a realized Treasury holding-period return.
The former implementation incorrectly treated the DTB3 discount-basis quote as
an effective annual yield and took its twelfth root.

## Equations

For monthly portfolio return Rp, benchmark Rm and Treasury proxy Rf:

- Excess return E = Rp - Rf.
- Annualized Sharpe = sqrt(12) * arithmetic mean(E) / sample standard deviation(E).
- Beta = sample covariance(Rp, Rm) / sample variance(Rm).

Sample moments use n-1. Square-root annualization assumes uncorrelated monthly
excess returns; it is not an autocorrelation-adjusted statistic or a forecast.
Sharpe uses arithmetic excess return, not CAGR divided by volatility.

## Reproduction and validation

Run `python scripts/analyze_portfolio.py`. The generated `site/data/analysis.json`
stores weights, initial and subsequent adjusted month-end closes, all 36 monthly
portfolio, benchmark, Treasury and excess returns, and intermediate moments.
An independent calculation using Python's statistics.mean and statistics.stdev
agrees with NumPy. Tests cover known return paths, unit beta, partial cash,
Treasury accrual, missing history and independent Sharpe reproduction.

For the November 19, 2026 snapshot (November 2023 through October 2026):

- Monthly mean excess: 0.0208957381 (2.0896%).
- Sample monthly excess volatility: 0.0327850239 (3.2785%).
- Annualized arithmetic excess: 25.0749%.
- Annualized excess volatility: 11.3571%.
- Sharpe: 2.2078666245. Beta: 0.8322343345.

The club's actual Sharpe requires independently sourced account return history,
with deposits and withdrawals accounted for. This estimate cannot establish it.

Sources: https://fred.stlouisfed.org/series/DGS3MO,
https://fred.stlouisfed.org/series/DTB3,
https://web.stanford.edu/~wfsharpe/art/sr/SR.htm.
