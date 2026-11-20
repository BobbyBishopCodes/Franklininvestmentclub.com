# Franklin Investment Club portfolio site

Created by Robert Bishop, an Accountancy & Finance major at ETSU.

The public site shows the club's positions, sector allocation, and largest holdings. Share counts and cash come from a dated club statement or CSV. GitHub Actions refreshes closing prices and publishes the static site. Source files containing member information stay outside this public repository.

## Portfolio updates

Send the new CSV to the site maintainer. The maintainer reconciles it, updates the public holdings and cash balance, and verifies the live deployment. No upload tool or API key is needed from club members. A PDF importer remains available for statements in the October 2026 format.

`data/holdings.csv` is the public input. Its columns are `symbol,name,shares,sector,statement_price`. `data/portfolio-meta.json` holds the holdings date and cash. The `site/data/portfolio.json` snapshot is generated. Git history preserves prior imports.

## Price and publishing process

The [GitHub repository](https://github.com/BobbyBishopCodes/Franklininvestmentclub.com) is connected as this checkout's `origin`. The workflow runs on changes to data, scripts, site files, or the workflow itself; it also runs on weekdays at 23:00 UTC and through **Run workflow** in Actions. It fetches the latest completed daily close for every ticker, requires one common market date, commits the refreshed snapshot, and deploys `site/` to GitHub Pages. If pricing fails, the action stops instead of publishing mixed dates. `deploy_only` in **Run workflow** republishes the checked-in snapshot without fetching prices.

No market-data API key is required for this version. Prices come from the community `yfinance` package, which can change availability or behavior. GitHub Actions uses its built-in `GITHUB_TOKEN`; do not create or paste a personal access token into this repository. The [live site](https://franklininvestmentclub.com/) is already served by GitHub Pages at the custom domain. The GitHub Pages URL redirects there.

Shares and cash remain dated to the last imported statement, even when prices update. The displayed portfolio value assumes no trades or cash movements after that date. The site labels the holdings date and price date separately.

## Local preview

```powershell
python -m http.server 8000 --directory site
```

Open `http://localhost:8000/`. Opening `site/index.html` directly as a file will usually block its JSON fetch.
