# Franklin Investment Club portfolio site

Created by Robert Bishop, an Accountancy & Finance major at ETSU.

The public site shows the club's positions, sector allocation, and largest holdings. Share counts and cash come from a dated monthly statement. GitHub Actions refreshes closing prices and publishes the static site. The source PDF is kept outside this public repository because its second page contains member ownership information.

## Monthly statement process

1. Save the new Franklin Investment Club PDF statement on your computer. Do **not** add the PDF to this repository.
2. Install the local import dependency once: `python -m pip install -r requirements-import.txt`.
3. Preview the import without changing files:

   ```powershell
   python scripts/import_statement.py "C:\path\to\Franklin Inv Club - MM-YYYY.pdf"
   ```

4. Check the printed statement date, number of positions, stock value, cash, total, additions, removals, and share changes against the PDF. If a new ticker is reported, add its sector to `data/sector-map.json` and preview again. The importer normalizes the statement's `APPL` to `AAPL` and `BRKB` to `BRK-B`.
5. Apply the reviewed import:

   ```powershell
   python scripts/import_statement.py "C:\path\to\Franklin Inv Club - MM-YYYY.pdf" --apply
   git diff -- data/holdings.csv data/portfolio-meta.json site/data/portfolio.json
   ```

6. Commit and push the generated data to `main`. Then check that **Refresh portfolio and publish site** succeeds in [GitHub Actions](https://github.com/BobbyBishopCodes/Franklininvestmentclub.com/actions) and verify the page's holdings date, price date, position count, and total.

The importer reads only the PDF's first page. It fails if a holding does not reconcile to shares × price, the position count disagrees, stock and cost totals disagree, or stock plus cash does not equal the printed portfolio total. It also refuses a statement older than the current one. A repeated import of the same data keeps the existing market price snapshot.

`data/holdings.csv` is the published input. Its columns are `symbol,name,shares,sector,statement_price`. `data/portfolio-meta.json` holds the statement date and cash. The `site/data/portfolio.json` snapshot is generated. Git history preserves prior imports.

## Price and publishing process

The [GitHub repository](https://github.com/BobbyBishopCodes/Franklininvestmentclub.com) is connected as this checkout's `origin`. The workflow runs on changes to data, scripts, site files, or the workflow itself; it also runs on weekdays at 23:00 UTC and through **Run workflow** in Actions. It fetches the latest completed daily close for every ticker, requires one common market date, commits the refreshed snapshot, and deploys `site/` to GitHub Pages. If pricing fails, the action stops instead of publishing mixed dates. `deploy_only` in **Run workflow** republishes the checked-in snapshot without fetching prices.

No market-data API key is required for this version. Prices come from the community `yfinance` package, which can change availability or behavior. GitHub Actions uses its built-in `GITHUB_TOKEN`; do not create or paste a personal access token into this repository. The [live site](https://franklininvestmentclub.com/) is already served by GitHub Pages at the custom domain. The GitHub Pages URL redirects there.

Shares and cash remain dated to the last imported statement, even when prices update. The displayed portfolio value assumes no trades or cash movements after that date. The site labels the holdings date and price date separately.

## Local preview

```powershell
python -m http.server 8000 --directory site
```

Open `http://localhost:8000/`. Opening `site/index.html` directly as a file will usually block its JSON fetch.
