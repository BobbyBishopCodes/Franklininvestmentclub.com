import argparse
import csv
import json
import math
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from zoneinfo import ZoneInfo

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
    required = {"symbol", "name", "shares", "sector", "statement_price"}
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
        })
        if not holdings[-1]["name"] or not holdings[-1]["sector"]:
            raise ValueError(f"Name and sector required for {symbol}")
    return holdings


def fetch_closes(symbols):
    import yfinance as yf

    closes = {}
    dates = set()
    market_now = datetime.now(ZoneInfo("America/New_York"))
    latest_completed_day = market_now.date() if market_now.hour >= 17 else market_now.date() - timedelta(days=1)
    for symbol in symbols:
        history = yf.Ticker(symbol).history(period="7d", interval="1d", auto_adjust=False)
        if history.empty or "Close" not in history:
            raise RuntimeError(f"No recent close for {symbol}")
        valid = history["Close"].dropna()
        valid = valid[[index.date() <= latest_completed_day for index in valid.index]]
        if valid.empty:
            raise RuntimeError(f"No recent close for {symbol}")
        price = float(valid.iloc[-1])
        if not math.isfinite(price) or price <= 0:
            raise RuntimeError(f"Invalid recent close for {symbol}")
        closes[symbol] = Decimal(str(price))
        dates.add(valid.index[-1].date().isoformat())
    if len(dates) != 1:
        raise RuntimeError(f"Quotes have different market dates: {', '.join(sorted(dates))}")
    return closes, dates.pop()


def build(refresh=False):
    holdings = load_holdings()
    meta = json.loads(META.read_text(encoding="utf-8"))
    cash = money(meta["cash"], "cash")
    if refresh:
        closes, price_date = fetch_closes([item["symbol"] for item in holdings])
        basis = "latest completed daily close"
    else:
        closes = {item["symbol"]: item["statement_price"] for item in holdings}
        price_date = meta["statement_date"]
        basis = "club statement"
    positions = []
    for item in holdings:
        price = closes[item["symbol"]].quantize(Decimal("0.01"))
        value = (item["shares"] * price).quantize(Decimal("0.01"))
        positions.append({
            "symbol": item["symbol"],
            "name": item["name"],
            "sector": item["sector"],
            "shares": float(item["shares"]),
            "price": float(price),
            "market_value": float(value),
        })
    invested = sum(Decimal(str(item["market_value"])) for item in positions)
    snapshot = {
        "price_date": price_date,
        "price_basis": basis,
        "statement_date": meta["statement_date"],
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "cash": float(cash),
        "invested_value": float(invested),
        "total_value": float(invested + cash),
        "positions": positions,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(snapshot, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(positions)} positions at {price_date}: ${invested + cash:,.2f}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--refresh", action="store_true", help="Fetch latest daily closing prices")
    build(parser.parse_args().refresh)
