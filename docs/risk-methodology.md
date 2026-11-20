# Portfolio risk estimates

## Displayed Sharpe: one-year weekly reconstruction

The website now uses `estimated_sharpe` from the generated analysis JSON. The
three-year monthly calculation below remains the beta model and a stored
comparison; its Sharpe is no longer displayed.

The displayed estimate uses the latest statement's shares times statement prices,
divided by statement portfolio value including cash, as fixed target weights.
Use 53 Friday endpoints ending on or before the statement date, producing 52
weekly returns. For holiday Fridays, use the preceding available trading close
within three calendar days; missing/nonfinite holding prices make the estimate
unavailable. Prices are adjusted for dividends and splits. Rebalance weekly,
assume cash earns zero, and exclude fees, taxes and transaction costs.

The explicitly assumed effective annual risk-free rate is 4.16%, converted to
weekly return as (1.0416)^(1/52)-1. This is a fixed modeling assumption, not a
claim about historical realized Treasury returns or a live Treasury quote.
Sharpe = sqrt(52) * mean(weekly portfolio return - weekly risk-free return) /
sample standard deviation(weekly excess returns). Square-root scaling assumes
uncorrelated weekly excess returns. Compounded 52-week return and annualized
arithmetic return are separate outputs; CAGR is not substituted into Sharpe.

October 2026 statement reconstruction: October 31, 2025 to October 30, 2026;
52 returns; Sharpe 1.39558, annualized volatility 10.0921%, compounded return
19.2877%, annualized arithmetic return 18.1618%. Provider revisions may cause
small changes. All weights, adjusted endpoint prices and returns are stored in
`estimated_sharpe.weekly_audit`. A synthetic known-return test independently
checks Sharpe and compounded return with Python's standard statistics library.

This is a hypothetical estimate with hindsight in the choice of holdings. The
club's actual YTD share-value return and account-level historical Sharpe are
different measurements. The supplied 1.32 estimate has not been reproduced.

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
