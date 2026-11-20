"""Build historical risk, correlation, clustering, and scenario inputs.

These are current-weight illustrations, not the club's historical account returns.
"""

import csv
import json
import math
import urllib.request
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import scipy.cluster.hierarchy as hierarchy
from scipy.spatial.distance import squareform
from refresh_portfolio import load_holdings
import yfinance as yf

ROOT = Path(__file__).resolve().parents[1]
PORTFOLIO = ROOT / "site/data/portfolio.json"
OUTPUT = ROOT / "site/data/analysis.json"


def weekly_estimate(prices, weights, as_of, annual_risk_free=0.0416):
    """52 completed Friday weeks, statement weights, zero-return residual cash."""
    end = pd.Timestamp(as_of)
    end -= pd.Timedelta(days=(end.weekday() - 4) % 7)
    endpoints = pd.date_range(end=end, periods=53, freq='W-FRI')
    symbols = sorted(weights)
    sampled = []
    for endpoint in endpoints:
        available = prices.loc[prices.index <= endpoint, symbols]
        if available.empty or (endpoint - available.index[-1]).days > 3:
            return {'status': 'unavailable', 'sharpe': None, 'reason': 'Missing weekly close'}
        sampled.append(available.iloc[-1])
    closes = pd.DataFrame(sampled, index=endpoints)
    if not np.isfinite(closes.to_numpy()).all() or (closes <= 0).any().any():
        return {'status': 'unavailable', 'sharpe': None, 'reason': 'Invalid weekly prices'}
    if any(not math.isfinite(w) or w < 0 for w in weights.values()) or sum(weights.values()) > 1 + 1e-9:
        raise ValueError('Invalid weekly portfolio weights')
    returns = closes.pct_change(fill_method=None).iloc[1:].to_numpy() @ np.array([weights[s] for s in symbols])
    weekly_rf = (1 + annual_risk_free) ** (1 / 52) - 1
    excess = returns - weekly_rf
    sd = float(np.std(excess, ddof=1))
    if sd <= 1e-12:
        return {'status': 'unavailable', 'sharpe': None, 'reason': 'Zero weekly volatility'}
    return {'status': 'available', 'reason': None,
            'sharpe': float(math.sqrt(52) * np.mean(excess) / sd),
            'compounded_annual_return': float(np.prod(1 + returns) - 1),
            'annualized_arithmetic_return': float(np.mean(returns) * 52),
            'annualized_volatility': float(sd * math.sqrt(52)),
            'annual_risk_free_assumption': annual_risk_free, 'weekly_risk_free': weekly_rf,
            'method': 'Statement weights rebalanced weekly; adjusted closes; cash earns zero; gross of costs',
            'window_start': endpoints[0].date().isoformat(), 'window_end': endpoints[-1].date().isoformat(),
            'observations': 52, 'weights': weights, 'cash_weight': 1 - sum(weights.values()),
            'initial_adjusted_closes': {s: float(closes.iloc[0][s]) for s in symbols},
            'weekly_audit': [{'week_end': endpoints[i + 1].date().isoformat(),
                              'portfolio_return': float(returns[i]), 'excess_return': float(excess[i]),
                              'adjusted_closes': {s: float(closes.iloc[i + 1][s]) for s in symbols}} for i in range(52)]}


def treasury_history():
    url = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=DGS3MO"
    with urllib.request.urlopen(url, timeout=30) as response:
        rows = list(csv.DictReader(response.read().decode("utf-8").splitlines()))
    values = {pd.Timestamp(row["observation_date"]): float(row["DGS3MO"]) / 100
              for row in rows if row["DGS3MO"] not in ("", ".")}
    if not values:
        raise RuntimeError("3-month Treasury history is unavailable")
    return pd.Series(values, dtype=float).sort_index()


def monthly_risk(prices, treasury, weights, price_date):
    completed_month = pd.Timestamp(price_date).to_period("M") - 1
    if any(not math.isfinite(w) or w < 0 for w in weights.values()) or sum(weights.values()) > 1 + 1e-9:
        raise ValueError("Weights must be finite, nonnegative and sum to at most one")
    monthly = prices.groupby(prices.index.to_period("M")).tail(1).copy()
    monthly.index = monthly.index.to_period("M").to_timestamp("M")
    monthly = monthly[monthly.index.to_period("M") <= completed_month].tail(37)
    if len(monthly) != 37 or monthly.isna().any().any():
        return {"status": "unavailable", "reason": "Incomplete 3-year monthly price history", "beta": None, "sharpe": None}
    periods = monthly.index.to_period("M")
    if periods[-1] != completed_month or not np.isfinite(monthly.to_numpy()).all() or (monthly <= 0).any().any():
        return {"status": "unavailable", "reason": "Stale or invalid monthly prices", "beta": None, "sharpe": None}
    if list(periods) != list(pd.period_range(periods[0], periods[-1], freq="M")):
        return {"status": "unavailable", "reason": "Gap in monthly price history", "beta": None, "sharpe": None}
    rates = treasury.resample("ME").last()
    previous_rates = rates.reindex(monthly.index[:-1])
    if previous_rates.isna().any():
        return {"status": "unavailable", "reason": "Incomplete Treasury history", "beta": None, "sharpe": None}
    changes = monthly.pct_change(fill_method=None).iloc[1:]
    symbols = list(weights)
    portfolio_returns = changes[symbols].to_numpy() @ np.array([weights[s] for s in symbols])
    benchmark_returns = changes["^GSPC"].to_numpy()
    # Investment-basis yield proxy, known at the prior month end. This is
    # simple ACT/365 accrual, not a realized Treasury total-return series.
    days = np.array([(end - start).days for start, end in zip(monthly.index[:-1], monthly.index[1:])])
    risk_free = previous_rates.to_numpy() * days / 365
    cash_weight = 1 - sum(weights.values())
    # Statement cash is modeled as non-interest-bearing.
    excess = portfolio_returns - risk_free
    benchmark_variance = np.var(benchmark_returns, ddof=1)
    excess_sd = np.std(excess, ddof=1)
    if benchmark_variance <= 0 or excess_sd <= 0:
        return {"status": "unavailable", "reason": "Zero return variance", "beta": None, "sharpe": None}
    beta = np.cov(portfolio_returns, benchmark_returns, ddof=1)[0, 1] / benchmark_variance
    sharpe = math.sqrt(12) * np.mean(excess) / excess_sd
    if not all(map(math.isfinite, (beta, sharpe))):
        return {"status": "unavailable", "reason": "Invalid risk result", "beta": None, "sharpe": None}
    return {"status": "available", "reason": None, "beta": float(beta), "sharpe": float(sharpe),
            "window_start": str(periods[1]), "window_end": str(periods[-1]), "observations": 36,
            "method": "Current weights rebalanced monthly; adjusted total returns; cash earns zero; gross of fees",
            "risk_free_method": "Prior month-end DGS3MO investment yield times calendar days / 365 (proxy)",
            "annualization": "sqrt(12); assumes monthly excess returns are uncorrelated",
            "cash_weight": cash_weight, "weights": weights,
            "mean_monthly_excess": float(np.mean(excess)), "sample_monthly_excess_sd": float(excess_sd),
            "annualized_arithmetic_excess": float(12 * np.mean(excess)),
            "annualized_excess_volatility": float(math.sqrt(12) * excess_sd),
            "monthly_audit": [{"month": str(periods[i + 1]),
                               "adjusted_closes": {s: float(monthly.iloc[i + 1][s]) for s in monthly.columns},
                               "portfolio_return": float(portfolio_returns[i]),
                               "benchmark_return": float(benchmark_returns[i]), "risk_free_return": float(risk_free[i]),
                               "excess_return": float(excess[i])} for i in range(36)],
            "initial_adjusted_closes": {s: float(monthly.iloc[0][s]) for s in monthly.columns}}


def build():
    portfolio = json.loads(PORTFOLIO.read_text(encoding="utf-8"))
    symbols = sorted(position["symbol"] for position in portfolio["positions"])
    if len(symbols) < 3 or len(symbols) != len(set(symbols)):
        raise ValueError("Analysis requires at least three distinct holdings")
    price_date = portfolio["price_date"]
    raw = yf.download(symbols + ["^GSPC"], period="5y", interval="1d", auto_adjust=True,
                      progress=False, threads=False)["Close"]
    if raw.empty or not set(symbols + ["^GSPC"]).issubset(raw.columns):
        raise RuntimeError("Historical prices are missing one or more holdings")
    prices = raw[symbols + ["^GSPC"]].copy()
    prices.index = prices.index.tz_localize(None) if prices.index.tz is not None else prices.index
    prices = prices[prices.index.date <= date.fromisoformat(price_date)]
    if prices.empty or (date.fromisoformat(price_date) - prices.index[-1].date()).days > 7:
        raise RuntimeError("Historical prices are too old for the portfolio price date")
    treasury = treasury_history()
    weights = {position["symbol"]: position["market_value"] / portfolio["total_value"]
               for position in portfolio["positions"]}
    risk = monthly_risk(prices, treasury, weights, price_date)
    holdings = load_holdings()
    statement_values = {h['symbol']: float(h['shares'] * h['statement_price']) for h in holdings}
    statement_total = sum(statement_values.values()) + portfolio['cash']
    estimate = weekly_estimate(prices, {s: v / statement_total for s, v in statement_values.items()}, portfolio['statement_date'])

    start = pd.Timestamp(price_date) - pd.Timedelta(days=3 * 365 + 2)
    daily = prices.loc[prices.index >= start, symbols].pct_change(fill_method=None).dropna()
    if len(daily) < 120:
        raise RuntimeError("Fewer than 120 shared daily returns")
    correlation = daily.corr().to_numpy()
    if not np.isfinite(correlation).all():
        raise RuntimeError("Invalid holdings correlation matrix")
    distance = np.sqrt(np.maximum(0, (1 - correlation) / 2))
    np.fill_diagonal(distance, 0)
    linkage = hierarchy.linkage(squareform(distance, checks=False), method="average")
    cluster_count = min(5, len(symbols))
    groups = hierarchy.fcluster(linkage, t=cluster_count, criterion="maxclust")
    centered = correlation - correlation.mean(axis=0)
    u, singular, _ = np.linalg.svd(centered, full_matrices=False)
    coordinates = (u[:, :2] * singular[:2]).tolist()
    covariance = np.cov(daily.to_numpy(), rowvar=False, ddof=1) * 252
    covariance = 0.9 * covariance + 0.1 * np.diag(np.diag(covariance))
    covariance += np.eye(len(symbols)) * 1e-8
    if not np.isfinite(covariance).all() or np.min(np.linalg.eigvalsh(covariance)) <= 0:
        raise RuntimeError("Invalid scenario covariance matrix")
    latest_treasury = treasury[treasury.index.date <= date.fromisoformat(price_date)].iloc[-1]
    document = {
        "price_date": price_date, "statement_date": portfolio["statement_date"],
        "symbols": symbols, "source": "Yahoo Finance adjusted closes; FRED DGS3MO investment-basis Treasury yield",
        "risk": risk, "estimated_sharpe": estimate,
        "correlation": {"start_date": daily.index[0].date().isoformat(),
                        "end_date": daily.index[-1].date().isoformat(), "observations": len(daily),
                        "matrix": correlation.tolist(), "leaf_order": hierarchy.leaves_list(linkage).tolist(),
                        "groups": groups.tolist(), "pca": coordinates},
        "scenario": {"risk_free_rate": float(latest_treasury), "risk_aversion": 2.5,
                     "tau": 0.025, "annual_covariance": covariance.tolist()},
    }
    OUTPUT.write_text(json.dumps(document, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(f"Wrote analysis for {len(symbols)} holdings through {price_date}; risk {risk['status']}")


if __name__ == "__main__":
    build()
