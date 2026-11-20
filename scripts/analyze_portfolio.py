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
import yfinance as yf

ROOT = Path(__file__).resolve().parents[1]
PORTFOLIO = ROOT / "site/data/portfolio.json"
OUTPUT = ROOT / "site/data/analysis.json"


def treasury_history():
    url = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=DTB3"
    with urllib.request.urlopen(url, timeout=30) as response:
        rows = list(csv.DictReader(response.read().decode("utf-8").splitlines()))
    values = {pd.Timestamp(row["observation_date"]): float(row["DTB3"]) / 100
              for row in rows if row["DTB3"] not in ("", ".")}
    if not values:
        raise RuntimeError("3-month Treasury history is unavailable")
    return pd.Series(values, dtype=float).sort_index()


def monthly_risk(prices, treasury, weights, price_date):
    completed_month = pd.Timestamp(price_date).to_period("M") - 1
    monthly = prices.groupby(prices.index.to_period("M")).tail(1).copy()
    monthly.index = monthly.index.to_period("M").to_timestamp("M")
    monthly = monthly[monthly.index.to_period("M") <= completed_month].tail(37)
    if len(monthly) != 37 or monthly.isna().any().any():
        return {"status": "unavailable", "reason": "Incomplete 3-year monthly price history", "beta": None, "sharpe": None}
    periods = monthly.index.to_period("M")
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
    risk_free = np.power(1 + previous_rates.to_numpy(), 1 / 12) - 1
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
            "window_start": str(periods[1]), "window_end": str(periods[-1]), "observations": 36}


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
        "symbols": symbols, "source": "Yahoo Finance adjusted closes; FRED DTB3 Treasury bill",
        "risk": risk,
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
