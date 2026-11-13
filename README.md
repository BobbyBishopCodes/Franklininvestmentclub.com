# Franklin Investment Club portfolio site

A static portfolio page hosted on GitHub Pages. The club manually maintains `data/holdings.csv`; GitHub Actions updates closing prices and publishes `site/` on weekdays at 23:00 UTC and on manual dispatch. The source statement for the initial snapshot is dated October 31, 2026.

## Current data

- `data/holdings.csv` contains the 24 public positions from the October 2026 statement. The first page supplied shares, price, and position values. The second page's member ownership data is deliberately excluded.
- `data/portfolio-meta.json` contains the statement date and cash balance. Update cash manually with each new club statement or CSV.
- `site/data/portfolio.json` is generated. The checked-in initial snapshot uses the statement's prices; subsequent Action runs use the latest completed daily closing prices.
- The statement's `APPL` and `BRKB` labels were normalized to `AAPL` and `BRK-B` for quote lookups.

## Updating holdings

Edit or replace `data/holdings.csv` using the existing column headers:

| Column | Meaning |
| --- | --- |
| `symbol` | Market ticker recognized by Yahoo Finance; use `BRK-B` for Berkshire B |
| `name` | Display name |
| `shares` | Current shares held |
| `sector` | Club classification shown in the allocation chart |
| `statement_price` | Price printed in the statement, used for an offline snapshot |

Then update `cash` and `statement_date` in `data/portfolio-meta.json` and push to `main`. The Action will fetch prices, generate the public snapshot, commit it, and deploy the site. The workflow also has a **Run workflow** button. A quote failure stops publication and preserves the prior deployed snapshot. If the provider returns different dates for holdings, the update also stops rather than mixing dates.

To regenerate from statement prices locally:

```powershell
python scripts/refresh_portfolio.py
```

To fetch current closes locally:

```powershell
python -m pip install -r requirements.txt
python scripts/refresh_portfolio.py --refresh
```

Preview the static site with a local web server from the repository root:

```powershell
python -m http.server 8000 --directory site
```

Open `http://localhost:8000/`. Opening `index.html` directly as a file will not load the JSON in most browsers.

## Publishing

1. Create a GitHub repository with `main` as the default branch and push this directory.
2. In repository **Settings → Pages**, set the source to **GitHub Actions**.
3. Run **Refresh portfolio and publish site** or push a change to `data/`, `site/`, or `scripts/`.
4. Once `franklininvestmentclub.com` is purchased, configure its DNS and the custom domain in Pages. Add a `site/CNAME` file containing `franklininvestmentclub.com` at that time.

Market prices are end-of-day snapshots and may lag current trading. Shares and cash remain dated to the latest manually uploaded statement, so the displayed value assumes no subsequent trades or cash movements. Yahoo Finance data is obtained through the community `yfinance` package, so quote availability can change. The page identifies both the holdings date and price date.
