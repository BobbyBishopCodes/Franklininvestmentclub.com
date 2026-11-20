const analysisUsd = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' });
const analysisPercent = new Intl.NumberFormat('en-US', { style: 'percent', minimumFractionDigits: 2, maximumFractionDigits: 2 });
const svgNamespace = 'http://www.w3.org/2000/svg';
const clusterColors = ['#325c66', '#9a744f', '#7f9b87', '#ad854a', '#687aa0'];

function svgElement(tag, attributes = {}) {
  const element = document.createElementNS(svgNamespace, tag);
  for (const [key, value] of Object.entries(attributes)) element.setAttribute(key, String(value));
  return element;
}

function renderClusters(data) {
  const container = document.getElementById('cluster-list');
  const groups = new Map();
  data.symbols.forEach((symbol, index) => {
    const group = data.correlation.groups[index];
    if (!groups.has(group)) groups.set(group, []);
    groups.get(group).push(symbol);
  });
  for (const [group, symbols] of [...groups].sort((a, b) => a[0] - b[0])) {
    const item = document.createElement('div'); item.className = 'cluster-item';
    item.style.borderLeft = `4px solid ${clusterColors[(group - 1) % clusterColors.length]}`;
    const title = document.createElement('strong'); title.textContent = `Cluster ${group}`;
    const tickers = document.createElement('span'); tickers.textContent = symbols.join(' · ');
    item.append(title, tickers); container.append(item);
  }
}

function renderHeatmap(data) {
  const { symbols } = data;
  const { matrix, leaf_order: order } = data.correlation;
  const cell = 23, inset = 79, size = inset + symbols.length * cell + 12;
  const svg = svgElement('svg', { viewBox: `0 0 ${size} ${size}`, width: size, height: size, role: 'img', 'aria-label': 'Return correlation matrix for current holdings' });
  order.forEach((index, row) => {
    const y = inset + row * cell;
    const label = svgElement('text', { x: inset - 8, y: y + 16, 'text-anchor': 'end', 'font-size': 10, fill: '#46534e' });
    label.textContent = symbols[index]; svg.append(label);
    const top = svgElement('text', { x: inset + row * cell + 13, y: inset - 10, 'text-anchor': 'start', 'font-size': 10, fill: '#46534e', transform: `rotate(-55 ${inset + row * cell + 13} ${inset - 10})` });
    top.textContent = symbols[index]; svg.append(top);
    order.forEach((column, col) => {
      const value = matrix[index][column];
      const strength = Math.min(1, Math.abs(value));
      const color = value >= 0 ? `rgba(50, 92, 102, ${0.12 + strength * 0.88})` : `rgba(169, 75, 69, ${0.12 + strength * 0.88})`;
      const rect = svgElement('rect', { x: inset + col * cell, y, width: cell - 1, height: cell - 1, fill: color });
      const title = svgElement('title'); title.textContent = `${symbols[index]} / ${symbols[column]}: ${value.toFixed(2)}`;
      rect.append(title); svg.append(rect);
    });
  });
  document.getElementById('correlation-heatmap').append(svg);
}

function renderPca(data) {
  const points = data.correlation.pca;
  const xs = points.map(point => point[0]), ys = points.map(point => point[1]);
  const minX = Math.min(...xs), maxX = Math.max(...xs), minY = Math.min(...ys), maxY = Math.max(...ys);
  const width = 850, height = 430, margin = 42;
  const x = value => margin + (value - minX) / (maxX - minX || 1) * (width - margin * 2);
  const y = value => height - margin - (value - minY) / (maxY - minY || 1) * (height - margin * 2);
  const svg = svgElement('svg', { viewBox: `0 0 ${width} ${height}`, role: 'img', 'aria-label': 'Two principal components of current holdings return correlations' });
  svg.append(svgElement('line', { x1: margin, x2: width - margin, y1: height - margin, y2: height - margin, stroke: '#9ea8a1' }));
  svg.append(svgElement('line', { x1: margin, x2: margin, y1: margin, y2: height - margin, stroke: '#9ea8a1' }));
  const horizontal = svgElement('text', { x: width - margin, y: height - 9, 'text-anchor': 'end', 'font-size': 11, fill: '#65706b' });
  horizontal.textContent = 'PC 1'; svg.append(horizontal);
  const vertical = svgElement('text', { x: 10, y: margin, 'font-size': 11, fill: '#65706b' });
  vertical.textContent = 'PC 2'; svg.append(vertical);
  data.symbols.forEach((symbol, index) => {
    const color = clusterColors[(data.correlation.groups[index] - 1) % clusterColors.length];
    const dot = svgElement('circle', { cx: x(points[index][0]), cy: y(points[index][1]), r: 5, fill: color });
    const title = svgElement('title'); title.textContent = `${symbol} · cluster ${data.correlation.groups[index]}`; dot.append(title); svg.append(dot);
    const label = svgElement('text', { x: x(points[index][0]) + 7, y: y(points[index][1]) - 6, 'font-size': 10, fill: '#34413c' });
    label.textContent = symbol; svg.append(label);
  });
  document.getElementById('pca-chart').append(svg);
}

function projectSimplex(values) {
  const sorted = [...values].sort((a, b) => b - a);
  let sum = 0, threshold = 0;
  for (let i = 0; i < sorted.length; i++) {
    sum += sorted[i];
    const candidate = (sum - 1) / (i + 1);
    if (sorted[i] > candidate) threshold = candidate;
  }
  return values.map(value => Math.max(0, value - threshold));
}

function scenarioWeights(portfolio, analysis, selected, target, confidence) {
  const symbols = analysis.symbols;
  const positions = new Map(portfolio.positions.map(position => [position.symbol, position]));
  const weights = symbols.map(symbol => positions.get(symbol).market_value / portfolio.invested_value);
  const covariance = analysis.scenario.annual_covariance;
  const delta = analysis.scenario.risk_aversion, tau = analysis.scenario.tau;
  const index = symbols.indexOf(selected);
  const prior = covariance.map(row => delta * row.reduce((sum, value, j) => sum + value * weights[j], 0));
  const current = positions.get(selected);
  const yieldEstimate = current.estimated_annual_income / current.market_value;
  const targetExcess = target / current.price - 1 + yieldEstimate - analysis.scenario.risk_free_rate;
  const confidenceRatio = confidence / 100;
  const viewScale = confidenceRatio === 0 ? 0 : confidenceRatio / (tau * covariance[index][index]);
  const posterior = prior.map((value, j) => value + tau * covariance[j][index] * viewScale * (targetExcess - prior[index]));
  const rowBound = Math.max(...covariance.map(row => row.reduce((sum, value) => sum + Math.abs(value), 0)));
  const step = 1 / (delta * rowBound);
  let suggested = [...weights];
  for (let iteration = 0; iteration < 2000; iteration++) {
    const gradient = covariance.map((row, j) => posterior[j] - delta * row.reduce((sum, value, k) => sum + value * suggested[k], 0));
    const next = projectSimplex(suggested.map((value, j) => value + step * gradient[j]));
    const difference = Math.max(...next.map((value, j) => Math.abs(value - suggested[j])));
    suggested = next;
    if (difference < 1e-10) break;
  }
  return { currentWeight: weights[index], suggestedWeight: suggested[index],
           currentValue: current.market_value, suggestedValue: suggested[index] * portfolio.invested_value,
           targetReturn: target / current.price - 1 + yieldEstimate, posteriorReturn: posterior[index] + analysis.scenario.risk_free_rate };
}

function addResult(container, label, value) {
  const item = document.createElement('div'); const caption = document.createElement('span'); caption.textContent = label;
  const figure = document.createElement('strong'); figure.textContent = value;
  item.append(caption, figure); container.append(item);
}

function setupScenario(portfolio, analysis) {
  const select = document.getElementById('scenario-symbol');
  const target = document.getElementById('scenario-target');
  const slider = document.getElementById('scenario-confidence');
  const output = document.getElementById('scenario-confidence-label');
  const positions = new Map(portfolio.positions.map(position => [position.symbol, position]));
  for (const symbol of analysis.symbols) {
    const option = document.createElement('option'); option.value = symbol; option.textContent = `${symbol} · ${positions.get(symbol).name}`; select.append(option);
  }
  const updateTarget = () => { target.value = String(positions.get(select.value).price); };
  select.addEventListener('change', updateTarget); updateTarget();
  slider.addEventListener('input', () => { output.value = `${slider.value}%`; });
  document.getElementById('scenario-form').addEventListener('submit', event => {
    event.preventDefault();
    const price = Number(target.value), confidence = Number(slider.value);
    if (!Number.isFinite(price) || price <= 0) return;
    const result = scenarioWeights(portfolio, analysis, select.value, price, confidence);
    const container = document.getElementById('scenario-result'); container.replaceChildren();
    addResult(container, 'Current weight', analysisPercent.format(result.currentWeight));
    addResult(container, 'Suggested weight', analysisPercent.format(result.suggestedWeight));
    const change = Math.abs(result.suggestedValue - result.currentValue) < 0.005 ? 0 : result.suggestedValue - result.currentValue;
    addResult(container, 'Illustrative change', `${change > 0 ? '+' : ''}${analysisUsd.format(change)}`);
    addResult(container, 'Target annual return incl. income', analysisPercent.format(result.targetReturn));
    addResult(container, 'Posterior annual return', analysisPercent.format(result.posteriorReturn));
    addResult(container, 'Suggested position value', analysisUsd.format(result.suggestedValue));
    const note = document.createElement('p'); note.textContent = 'Weights are long-only, sum to 100% of invested assets, and keep current cash fixed. They depend strongly on the target and confidence entered.';
    container.append(note); container.hidden = false;
    document.getElementById('scenario-status').textContent = `Scenario calculated for ${select.value}.`;
  });
}

Promise.all([
  fetch('data/portfolio.json', { cache: 'no-store' }).then(response => response.json()),
  fetch('data/analysis.json', { cache: 'no-store' }).then(response => response.json()),
]).then(([portfolio, analysis]) => {
  const symbols = portfolio.positions.map(position => position.symbol).sort();
  if (portfolio.price_date !== analysis.price_date || portfolio.statement_date !== analysis.statement_date ||
      JSON.stringify(symbols) !== JSON.stringify(analysis.symbols)) throw new Error('Analysis does not match current holdings');
  const risk = analysis.risk;
  document.getElementById('portfolio-beta').textContent = risk.beta == null ? 'Unavailable' : risk.beta.toFixed(2);
  document.getElementById('portfolio-sharpe').textContent = risk.sharpe == null ? 'Unavailable' : risk.sharpe.toFixed(2);
  document.getElementById('analysis-status').textContent = risk.status === 'available' ? '' : `Risk figures unavailable: ${risk.reason}.`;
  document.getElementById('analysis-period').textContent = `${analysis.correlation.observations} shared daily returns · ${analysis.correlation.start_date} to ${analysis.correlation.end_date}. Current holdings and weights are used for risk estimates.`;
  renderClusters(analysis); renderHeatmap(analysis); renderPca(analysis);
  document.getElementById('analysis-content').hidden = false;
  setupScenario(portfolio, analysis);
}).catch(error => {
  document.getElementById('analysis-status').textContent = 'Historical analysis is unavailable for the current holdings.';
  document.getElementById('scenario-status').textContent = 'Scenario inputs are unavailable until historical analysis refreshes.';
  document.getElementById('scenario-form').hidden = true;
  console.error(error);
});
