"""Preview and import a Franklin Investment Club monthly PDF statement.

Only page one is read. Page two contains member ownership and is never copied
to repository files. Import fails if row values or printed totals disagree.
"""

import argparse
import csv
import io
import json
import re
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from pypdf import PdfReader

from refresh_portfolio import HOLDINGS, META, build, money

ROOT = Path(__file__).resolve().parents[1]
SECTOR_MAP = ROOT / "data" / "sector-map.json"
SYMBOL_ALIASES = {"APPL": "AAPL", "BRKB": "BRK-B"}
AMOUNT = r"\$[\d,]+(?:\.\d{2})?"
ROW = re.compile(
    rf"^\s*(?P<shares>\d[\d,.]*)\s+(?P<name>.+?)\s+\((?P<raw_symbol>[A-Z][A-Z0-9.\-]{{0,14}})\)"
    rf"\s+(?P<average_cost>{AMOUNT})\s+(?P<total_cost>{AMOUNT})"
    rf"\s+(?P<price>{AMOUNT})\s+(?P<value>{AMOUNT})\s+(?P<weight>\d+(?:\.\d+)?%)"
)
DATE = re.compile(r"Statement as of\s+(\d{1,2})/(\d{1,2})/(\d{4})")
POSITION_TOTAL = re.compile(r"Total Stock Value\s+# of Positions\s*=\s*(\d+)\s+(\$[\d,]+\.\d{2})\s+(\$[\d,]+\.\d{2})")
CASH = re.compile(r"Cash & Credit Balance\s+(\$[\d,]+\.\d{2})")
PORTFOLIO_TOTAL = re.compile(r"Total Club Portfolio Value\s+(\$[\d,]+\.\d{2})")


def parse_statement_text(text):
    date_match = DATE.search(text)
    position_total = POSITION_TOTAL.search(text)
    cash_match = CASH.search(text)
    portfolio_total = PORTFOLIO_TOTAL.search(text)
    if not all((date_match, position_total, cash_match, portfolio_total)):
        raise ValueError("Statement heading or totals could not be read; check the PDF layout")
    month, day, year = map(int, date_match.groups())
    as_of = datetime(year, month, day).date().isoformat()
    positions = []
    seen = set()
    for line in text.splitlines():
        if not re.match(r"^\s*\d+\s+.*\([A-Z][A-Z0-9.\-]*\)", line):
            continue
        match = ROW.match(line)
        if not match:
            raise ValueError(f"Could not parse holding row: {line.strip()[:90]}")
        fields = match.groupdict()
        symbol = SYMBOL_ALIASES.get(fields["raw_symbol"], fields["raw_symbol"])
        if symbol in seen:
            raise ValueError(f"Duplicate holding: {symbol}")
        seen.add(symbol)
        shares = money(fields["shares"], f"shares for {symbol}")
        price = money(fields["price"], f"price for {symbol}")
        value = money(fields["value"], f"value for {symbol}")
        cost = money(fields["total_cost"], f"cost for {symbol}")
        if shares <= 0 or price <= 0:
            raise ValueError(f"Nonpositive shares or price for {symbol}")
        if (shares * price).quantize(Decimal("0.01")) != value:
            raise ValueError(f"Shares × price does not equal printed value for {symbol}")
        positions.append({"symbol": symbol, "statement_name": fields["name"].strip(), "shares": shares,
                          "price": price, "value": value, "cost": cost, "printed_weight": Decimal(fields["weight"][:-1])})
    if not positions:
        raise ValueError("No holdings found on statement page one")
    count = int(position_total.group(1))
    invested = money(position_total.group(3), "printed stock total")
    cost_total = money(position_total.group(2), "printed cost total")
    cash = money(cash_match.group(1), "printed cash")
    portfolio = money(portfolio_total.group(1), "printed portfolio total")
    if len(positions) != count:
        raise ValueError(f"Found {len(positions)} holdings; statement prints {count}")
    if sum((item["value"] for item in positions), Decimal(0)) != invested:
        raise ValueError("Holding values do not equal the printed stock total")
    if sum((item["cost"] for item in positions), Decimal(0)) != cost_total:
        raise ValueError("Holding costs do not equal the printed cost total")
    if invested + cash != portfolio:
        raise ValueError("Stock total plus cash does not equal the printed portfolio total")
    for item in positions:
        actual_weight = item["value"] / invested * 100
        if abs(actual_weight - item["printed_weight"]) > Decimal("0.011"):
            raise ValueError(f"Printed weight does not reconcile for {item['symbol']}")
    return {"as_of": as_of, "positions": positions, "invested": invested, "cash": cash, "total": portfolio}


def extract_first_page(path):
    reader = PdfReader(str(path))
    if not reader.pages:
        raise ValueError("The PDF has no pages")
    text = reader.pages[0].extract_text(extraction_mode="layout") or ""
    if not text.strip():
        raise ValueError("Page one has no extractable text; a scanned PDF needs manual review")
    return text


def prepare(statement, sector_map, existing):
    old_by_symbol = {row["symbol"].upper(): row for row in existing}
    rows = []
    for position in statement["positions"]:
        symbol = position["symbol"]
        sector = sector_map.get(symbol)
        if not sector:
            raise ValueError(f"Add a sector for {symbol} to {SECTOR_MAP} before import")
        old = old_by_symbol.get(symbol)
        name = old["name"] if old else position["statement_name"]
        rows.append({"symbol": symbol, "name": name, "shares": str(position["shares"]),
                     "sector": sector, "statement_price": f"{position['price']:.2f}"})
    return rows


def preview(statement, rows, existing):
    old = {row["symbol"]: row for row in existing}
    new = {row["symbol"]: row for row in rows}
    added = sorted(set(new) - set(old))
    removed = sorted(set(old) - set(new))
    changed = sorted(symbol for symbol in set(new) & set(old) if Decimal(new[symbol]["shares"]) != Decimal(old[symbol]["shares"]))
    print(f"Statement: {statement['as_of']} | {len(rows)} positions | stock ${statement['invested']:,.2f} | cash ${statement['cash']:,.2f} | total ${statement['total']:,.2f}")
    print("Added:", ", ".join(added) or "none")
    print("Removed:", ", ".join(removed) or "none")
    print("Share changes:", ", ".join(f"{symbol} {old[symbol]['shares']} → {new[symbol]['shares']}" for symbol in changed) or "none")


def main():
    parser = argparse.ArgumentParser(description="Validate a Franklin monthly statement before updating public holdings")
    parser.add_argument("pdf", type=Path, help="Local monthly statement PDF; it is never copied to this repository")
    parser.add_argument("--apply", action="store_true", help="Write holdings, metadata, and a statement-priced snapshot")
    args = parser.parse_args()
    statement = parse_statement_text(extract_first_page(args.pdf))
    sector_map = json.loads(SECTOR_MAP.read_text(encoding="utf-8"))
    with HOLDINGS.open(newline="", encoding="utf-8-sig") as stream:
        existing = list(csv.DictReader(stream))
    rows = prepare(statement, sector_map, existing)
    preview(statement, rows, existing)
    old_meta = json.loads(META.read_text(encoding="utf-8"))
    if statement["as_of"] < old_meta["statement_date"]:
        raise ValueError("Statement is older than the currently published holdings")
    if not args.apply:
        print("Preview only. Add --apply after reviewing the changes.")
        return
    fields = ["symbol", "name", "shares", "sector", "statement_price"]
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    new_csv = buffer.getvalue()
    source = (old_meta.get("source") if statement["as_of"] == old_meta["statement_date"]
              else f"Franklin Investment Club statement as of {statement['as_of']}")
    new_meta = json.dumps({"statement_date": statement["as_of"], "cash": float(statement["cash"]),
                           "source": source}, indent=2) + "\n"
    if new_csv == HOLDINGS.read_text(encoding="utf-8-sig") and new_meta == META.read_text(encoding="utf-8"):
        print("No holdings or metadata changes; existing price snapshot retained.")
        return
    HOLDINGS.write_text(new_csv, encoding="utf-8")
    META.write_text(new_meta, encoding="utf-8")
    build(refresh=False)
    print("Import applied. Review the diff, then commit and push to GitHub.")


if __name__ == "__main__":
    main()
