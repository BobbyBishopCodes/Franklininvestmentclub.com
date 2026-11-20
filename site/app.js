const usd = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' });
const whole = new Intl.NumberFormat('en-US', { maximumFractionDigits: 4 });
const percent = new Intl.NumberFormat('en-US', { style: 'percent', minimumFractionDigits: 2, maximumFractionDigits: 2 });
const palette = ['#274d5a', '#4b7777', '#d7a94c', '#769295', '#92785b', '#a9b9a8', '#bb9669', '#617082', '#adb6bd'];

function dateLabel(iso, short = false) {
  const [year, month, day] = iso.split('-').map(Number);
  return new Intl.DateTimeFormat('en-US', { month: short ? 'short' : 'long', day: 'numeric', year: 'numeric', timeZone: 'UTC' }).format(new Date(Date.UTC(year, month - 1, day)));
}

function text(id, value) { document.getElementById(id).textContent = value; }
function signedCurrency(value) { return `${value > 0 ? '+' : ''}${usd.format(value)}`; }
function signedPercent(value) { return `${value > 0 ? '+' : ''}${percent.format(value)}`; }
function gainClass(value) { return value > 0 ? 'gain-positive' : value < 0 ? 'gain-negative' : ''; }

function render(data) {
  const positions = [...data.positions].sort((a, b) => b.market_value - a.market_value);
  const invested = data.invested_value;
  text('price-note', `Holdings and cash: ${dateLabel(data.statement_date)} · Prices: ${dateLabel(data.price_date)}${data.price_basis === 'club statement' ? ' (statement)' : ''}`);
  text('total-value', usd.format(data.total_value));
  text('invested-value', usd.format(invested));
  text('position-count', String(positions.length));
  text('cash-value', usd.format(data.cash));
  text('gain-value', signedCurrency(data.unrealized_gain));
  text('gain-percent', data.total_cost > 0 ? signedPercent(data.unrealized_gain / data.total_cost) : '—');
  if (data.unrealized_gain !== 0) document.getElementById('gain-value').classList.add(gainClass(data.unrealized_gain));
  text('daily-change', data.daily_holdings_change == null ? 'Unavailable' : signedCurrency(data.daily_holdings_change));
  text('daily-change-percent', data.daily_holdings_change_percent == null ? 'Quotes incomplete' : `${signedPercent(data.daily_holdings_change_percent)} · fixed shares`);
  if (data.daily_holdings_change != null && data.daily_holdings_change !== 0) document.getElementById('daily-change').classList.add(gainClass(data.daily_holdings_change));
  text('annual-income', usd.format(data.estimated_annual_income));
  text('income-yield', percent.format(data.estimated_income_yield));
  text('donut-total', new Intl.NumberFormat('en-US', { notation: 'compact', maximumFractionDigits: 2, style: 'currency', currency: 'USD' }).format(invested));
  text('holdings-count-label', `(${positions.length})`);
  text('table-asof', `Prices as of ${dateLabel(data.price_date, true)}`);
  text('year', String(new Date().getFullYear()));

  const sectors = new Map();
  for (const position of positions) sectors.set(position.sector, (sectors.get(position.sector) || 0) + position.market_value);
  const groups = [...sectors].sort((a, b) => b[1] - a[1]);
  let cursor = 0;
  const stops = groups.map((group, i) => { const start = cursor; cursor += group[1] / invested * 100; return `${palette[i % palette.length]} ${start}% ${cursor}%`; });
  document.getElementById('sector-donut').style.background = `conic-gradient(${stops.join(', ')})`;
  document.getElementById('sector-donut').setAttribute('aria-label', groups.map(([name, value]) => `${name} ${percent.format(value / invested)}`).join(', '));
  const sectorList = document.getElementById('sector-list');
  for (const [i, [name, value]] of groups.entries()) {
    const row = document.createElement('div'); row.className = 'sector-row';
    const swatch = document.createElement('span'); swatch.className = 'sector-swatch'; swatch.style.background = palette[i % palette.length];
    const label = document.createElement('span'); label.textContent = name;
    const share = document.createElement('strong'); share.textContent = percent.format(value / invested);
    row.append(swatch, label, share); sectorList.append(row);
  }

  const leaders = positions.slice(0, 5);
  const top = document.getElementById('top-holdings');
  for (const [i, position] of leaders.entries()) {
    const item = document.createElement('div'); item.className = 'top-item';
    const rank = document.createElement('span'); rank.className = 'top-rank'; rank.textContent = String(i + 1).padStart(2, '0');
    const symbol = document.createElement('strong'); symbol.className = 'top-symbol'; symbol.textContent = position.symbol;
    const name = document.createElement('span'); name.className = 'top-name'; name.textContent = position.name;
    const track = document.createElement('div'); track.className = 'top-track';
    const fill = document.createElement('div'); fill.className = 'top-fill'; fill.style.width = `${position.market_value / leaders[0].market_value * 100}%`; track.append(fill);
    const share = document.createElement('span'); share.className = 'top-percent'; share.textContent = percent.format(position.market_value / invested);
    item.append(rank, symbol, name, track, share); top.append(item);
  }

  const body = document.getElementById('holdings-body');
  for (const position of positions) {
    const row = document.createElement('tr');
    const company = document.createElement('td'); const wrapper = document.createElement('div'); wrapper.className = 'company-cell';
    const ticker = document.createElement('button'); ticker.type = 'button'; ticker.className = 'ticker ticker-button'; ticker.textContent = position.symbol;
    ticker.setAttribute('aria-expanded', 'false'); ticker.setAttribute('aria-controls', `details-${position.symbol}`);
    ticker.setAttribute('aria-label', `Show ${position.symbol} position details`);
    const name = document.createElement('span'); name.className = 'company-name'; name.textContent = position.name;
    wrapper.append(ticker, name); company.append(wrapper);
    const sector = document.createElement('td'); sector.className = 'sector-cell'; sector.textContent = position.sector;
    const shares = document.createElement('td'); shares.className = 'num'; shares.textContent = whole.format(position.shares);
    const price = document.createElement('td'); price.className = 'num'; price.textContent = usd.format(position.price);
    const value = document.createElement('td'); value.className = 'num'; value.textContent = usd.format(position.market_value);
    const weight = document.createElement('td'); weight.className = 'num weight-cell'; weight.textContent = percent.format(position.market_value / invested);
    const low = document.createElement('td'); low.className = 'num'; low.textContent = position.week_52_low == null ? '—' : usd.format(position.week_52_low);
    const high = document.createElement('td'); high.className = 'num'; high.textContent = position.week_52_high == null ? '—' : usd.format(position.week_52_high);
    const gain = document.createElement('td'); gain.className = `num gain-cell ${gainClass(position.unrealized_gain)}`;
    gain.textContent = signedCurrency(position.unrealized_gain);
    const gainRate = document.createElement('small'); gainRate.textContent = position.total_cost > 0 ? signedPercent(position.unrealized_gain / position.total_cost) : '—'; gain.append(gainRate);
    row.append(company, sector, shares, price, value, weight, low, high, gain);
    const detailsRow = document.createElement('tr'); detailsRow.id = `details-${position.symbol}`; detailsRow.className = 'position-details'; detailsRow.hidden = true;
    const detailsCell = document.createElement('td'); detailsCell.colSpan = 9;
    const detailsGrid = document.createElement('div'); detailsGrid.className = 'position-details-grid';
    const details = [
      ['Cost basis', usd.format(position.total_cost)],
      ['Average cost / share', usd.format(position.total_cost / position.shares)],
      ['Estimated annual income', usd.format(position.estimated_annual_income)],
      ['Estimated income yield', percent.format(position.estimated_annual_income / position.market_value)],
      ['One-day holdings change', position.daily_change == null ? 'Unavailable' : signedCurrency(position.daily_change)],
    ];
    for (const [label, value] of details) {
      const item = document.createElement('div'); const caption = document.createElement('span'); caption.textContent = label;
      const figure = document.createElement('strong'); figure.textContent = value; item.append(caption, figure); detailsGrid.append(item);
    }
    detailsCell.append(detailsGrid); detailsRow.append(detailsCell);
    ticker.addEventListener('click', () => {
      detailsRow.hidden = !detailsRow.hidden;
      ticker.setAttribute('aria-expanded', String(!detailsRow.hidden));
      ticker.setAttribute('aria-label', `${detailsRow.hidden ? 'Show' : 'Hide'} ${position.symbol} position details`);
    });
    body.append(row, detailsRow);
  }
}

fetch('data/portfolio.json', { cache: 'no-store' }).then(response => {
  if (!response.ok) throw new Error(`Portfolio unavailable (${response.status})`);
  return response.json();
}).then(data => {
  render(data);
  return fetch('data/analysis.json', { cache: 'no-store' }).then(response => {
    if (!response.ok) throw new Error('Historical analysis unavailable');
    return response.json();
  }).then(analysis => {
    const symbols = data.positions.map(position => position.symbol).sort();
    if (analysis.price_date !== data.price_date || analysis.statement_date !== data.statement_date ||
        JSON.stringify(analysis.symbols) !== JSON.stringify(symbols)) throw new Error('Historical analysis does not match portfolio');
    for (const [id, value] of [['portfolio-beta', analysis.risk?.beta], ['portfolio-sharpe', analysis.estimated_sharpe?.sharpe]]) {
      text(id, Number.isFinite(value) ? value.toFixed(2) : 'Unavailable');
    }
  }).catch(error => {
    text('portfolio-beta', 'Unavailable');
    text('portfolio-sharpe', 'Unavailable');
    console.error(error);
  });
}).catch(error => {
  text('price-note', 'Portfolio data could not be loaded. Please try again later.');
  document.getElementById('sector-donut').setAttribute('aria-label', 'Portfolio data unavailable');
  console.error(error);
});
