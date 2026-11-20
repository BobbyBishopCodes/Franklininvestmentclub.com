import argparse
import csv
import hashlib
import json
import math
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
HOLDINGS = ROOT / "data" / "holdings.csv"
META = ROOT / "data" / "portfolio-meta.json"
OUTPUT = ROOT / "site" / "data" / "portfolio.json"


def money(value, label):
    try:
        result = Decimal(str(value).replace(",", "").replace("$", ""))
    except InvalidOperation as exc:
        raise ValueError(f"Invalid {label}: {value!r}") from exc
    if not result.is_finite() or result < 0:
        raise ValueError(f"Invalid {label}: {value!r}")
    return result


def load_holdings():
    with HOLDINGS.open(newline="", encoding="utf-8-sig") as stream:
        rows = list(csv.DictReader(stream))
    required = {"symbol", "name", "shares", "sector", "statement_price", "total_cost", "annual_income"}
    if not rows:
        raise ValueError("The holdings CSV is empty")
    if not required.issubset(rows[0]):
        raise ValueError(f"Missing CSV columns: {', '.join(sorted(required - set(rows[0])))}")
    seen = set()
    holdings = []
    for row in rows:
        symbol = row["symbol"].strip().upper()
        if not symbol or symbol in seen:
            raise ValueError(f"Blank or duplicate ticker: {symbol!r}")
        seen.add(symbol)
        shares = money(row["shares"], f"shares for {symbol}")
        if shares == 0:
            raise ValueError(f"Shares must be positive for {symbol}")
        holdings.append({
            "symbol": symbol,
            "name": row["name"].strip(),
            "sector": row["sector"].strip(),
            "shares": shares,
            "statement_price": money(row["statement_price"], f"statement price for {symbol}"),
            "total_cost": money(row["total_cost"], f"total cost for {symbol}"),
            "annual_income": money(row["annual_income"], f"annual income for {symbol}"),
        })
        if not holdings[-1]["name"] or not holdings[-1]["sector"]:
            raise ValueError(f"Name and sector required for {symbol}")
    return holdings


def fetch_quotes(symbols):
    import yfinance as yf

    closes = {}
    ranges = {}
    previous_closes = {}
    dates = set()
    previous_dates = set()
    market_now = datetime.now(ZoneInfo("America/New_York"))
    latest_completed_day = market_now.date() if market_now.hour >= 17 else market_now.date() - timedelta(days=1)
    for symbol in symbols:
        ticker = yf.Ticker(symbol)
        history = ticker.history(period="1y", interval="1d", auto_adjust=False)
        recent = ticker.history(period="7d", interval="1d", auto_adjust=False)
        if history.empty or not {"Close", "High", "Low"}.issubset(history.columns):
            raise RuntimeError(f"No price history for {symbol}")
        if recent.empty or not {"Close", "High", "Low"}.issubset(recent.columns):
            raise RuntimeError(f"No recent close for {symbol}")
        history = history[[index.date() <= latest_completed_day for index in history.index]]
        recent = recent[[index.date() <= latest_completed_day for index in recent.index]]
        valid = recent["Close"].dropna()
        if valid.empty:
            raise RuntimeError(f"No recent close for {symbol}")
        price = float(valid.iloc[-1])
        if not math.isfinite(price) or price <= 0:
            raise RuntimeError(f"Invalid recent close for {symbol}")
        closes[symbol] = Decimal(str(price))
        quote_day = valid.index[-1].date()
        dates.add(quote_day.isoformat())
        if len(valid) > 1:
            previous_closes[symbol] = Decimal(str(float(valid.iloc[-2])))
            previous_dates.add(valid.index[-2].date().isoformat())
        window = pd.concat([history, recent]).sort_index()
        window = window[~window.index.duplicated(keep="last")]
        window = window[[index.date() >= quote_day - timedelta(weeks=52) and index.date() <= quote_day for index in window.index]]
        high = float(window["High"].max())
        low = float(window["Low"].min())
        if not all(map(math.isfinite, (high, low))) or low <= 0 or high < low or not low <= price <= high:
            raise RuntimeError(f"Invalid 52-week range for {symbol}")
        ranges[symbol] = (Decimal(str(low)), Decimal(str(high)))
    if len(dates) != 1:
        raise RuntimeError(f"Quotes have different market dates: {', '.join(sorted(dates))}")
    if len(previous_closes) != len(symbols) or len(previous_dates) != 1:
        previous_closes = {}
    return closes, ranges, previous_closes, dates.pop()


def build(refresh=False, allow_stale=False):
    holdings = load_holdings()
    meta = json.loads(META.read_text(encoding="utf-8"))
    holdings_digest = hashlib.sha256(HOLDINGS.read_bytes() + META.read_bytes()).hexdigest()
    cash = money(meta["cash"], "cash")
    if refresh:
        try:
            closes, ranges, previous_closes, price_date = fetch_quotes([item["symbol"] for item in holdings])
        except RuntimeError:
            if allow_stale and OUTPUT.exists():
                previous = json.loads(OUTPUT.read_text(encoding="utf-8"))
                if previous.get("holdings_digest") == holdings_digest and previous.get("price_date", "") >= meta["statement_date"]:
                    print("::warning::Quote refresh incomplete; deploying the last matching snapshot")
                    return
            raise
        basis = "latest completed daily close"
    else:
        closes = {item["symbol"]: item["statement_price"] for item in holdings}
        ranges = {}
        previous_closes = {}
        price_date = meta["statement_date"]
        basis = "club statement"
    positions = []
    for item in holdings:
        price = closes[item["symbol"]].quantize(Decimal("0.01"))
        value = (item["shares"] * price).quantize(Decimal("0.01"))
        previous_value = (item["shares"] * previous_closes[item["symbol"]]).quantize(Decimal("0.01")) if previous_closes else None
        positions.append({
            "symbol": item["symbol"],
            "name": item["name"],
            "sector": item["sector"],
            "shares": float(item["shares"]),
            "price": float(price),
            "market_value": float(value),
            "total_cost": float(item["total_cost"]),
            "unrealized_gain": float(value - item["total_cost"]),
            "estimated_annual_income": float(item["annual_income"]),
            "daily_change": float(value - previous_value) if previous_value is not None else None,
            "week_52_low": float(ranges[item["symbol"]][0].quantize(Decimal("0.01"))) if refresh else None,
            "week_52_high": float(ranges[item["symbol"]][1].quantize(Decimal("0.01"))) if refresh else None,
        })
    invested = sum(Decimal(str(item["market_value"])) for item in positions)
    total_cost = sum((item["total_cost"] for item in holdings), Decimal(0))
    annual_income = sum((item["annual_income"] for item in holdings), Decimal(0))
    daily_change = sum((Decimal(str(item["daily_change"])) for item in positions), Decimal(0)) if previous_closes else None
    previous_invested = invested - daily_change if daily_change is not None else None
    snapshot = {
        "price_date": price_date,
        "price_basis": basis,
        "statement_date": meta["statement_date"],
        "holdings_digest": holdings_digest,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "cash": float(cash),
        "invested_value": float(invested),
        "total_cost": float(total_cost),
        "unrealized_gain": float(invested - total_cost),
        "total_value": float(invested + cash),
        "estimated_annual_income": float(annual_income),
        "estimated_income_yield": float(annual_income / (invested + cash)) if invested + cash else None,
        "daily_holdings_change": float(daily_change) if daily_change is not None else None,
        "daily_holdings_change_percent": float(daily_change / previous_invested) if previous_invested else None,
        "positions": positions,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(snapshot, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(positions)} positions at {price_date}: ${invested + cash:,.2f}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--refresh", action="store_true", help="Fetch latest daily closing prices")
    parser.add_argument("--allow-stale", action="store_true", help="Retain a matching snapshot if quotes are incomplete")
    args = parser.parse_args()
    build(args.refresh, args.allow_stale)
