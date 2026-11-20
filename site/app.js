const usd = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' });
const whole = new Intl.NumberFormat('en-US', { maximumFractionDigits: 4 });
const percent = new Intl.NumberFormat('en-US', { style: 'percent', minimumFractionDigits: 2, maximumFractionDigits: 2 });
const palette = ['#274d5a', '#4b7777', '#d7a94c', '#769295', '#92785b', '#a9b9a8', '#bb9669', '#617082', '#adb6bd'];

function dateLabel(iso, short = false) {
  const [year, month, day] = iso.split('-').map(Number);
  return new Intl.DateTimeFormat('en-US', { month: short ? 'short' : 'long', day: 'numeric', year: 'numeric', timeZone: 'UTC' }).format(new Date(Date.UTC(year, month - 1, day)));
}

function text(id, value) { document.getElementById(id).textContent = value; }

function render(data) {
  const positions = [...data.positions].sort((a, b) => b.market_value - a.market_value);
  const invested = data.invested_value;
  text('price-date-short', dateLabel(data.price_date, true));
  text('price-note', `Holdings and cash: ${dateLabel(data.statement_date)} · Prices: ${dateLabel(data.price_date)}${data.price_basis === 'club statement' ? ' (statement)' : ''}`);
  text('total-value', usd.format(data.total_value));
  text('invested-value', usd.format(invested));
  text('position-count', String(positions.length));
  text('cash-value', usd.format(data.cash));
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
    const ticker = document.createElement('span'); ticker.className = 'ticker'; ticker.textContent = position.symbol;
    const name = document.createElement('span'); name.className = 'company-name'; name.textContent = position.name;
    wrapper.append(ticker, name); company.append(wrapper);
    const sector = document.createElement('td'); sector.className = 'sector-cell'; sector.textContent = position.sector;
    const shares = document.createElement('td'); shares.className = 'num'; shares.textContent = whole.format(position.shares);
    const price = document.createElement('td'); price.className = 'num'; price.textContent = usd.format(position.price);
    const value = document.createElement('td'); value.className = 'num'; value.textContent = usd.format(position.market_value);
    const weight = document.createElement('td'); weight.className = 'num weight-cell'; weight.textContent = percent.format(position.market_value / invested);
    row.append(company, sector, shares, price, value, weight); body.append(row);
  }
}

fetch('data/portfolio.json', { cache: 'no-store' }).then(response => {
  if (!response.ok) throw new Error(`Portfolio unavailable (${response.status})`);
  return response.json();
}).then(render).catch(error => {
  text('price-note', 'Portfolio data could not be loaded. Please try again later.');
  document.getElementById('sector-donut').setAttribute('aria-label', 'Portfolio data unavailable');
  console.error(error);
});
