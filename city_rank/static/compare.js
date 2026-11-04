/* Compare page: three cities side by side.
 *
 * How it works
 *  - compare.html embeds a summary of every city (built by dashboard.build_compare_context).
 *  - Three <select> pickers choose the cities; the choice is mirrored in the URL
 *    hash (#toronto,calgary,halifax) so a comparison can be shared or bookmarked.
 *  - Every section is a 3-column grid. Each "row" is a full-width label followed by
 *    one cell per city, so values line up like Apple's product comparison pages.
 *  - "Best" marks the strongest of the three cities on a measure (only when at
 *    least two cities have data and they are not all equal).
 *  - Charts are small multiples: one per city, with the SAME axis range across
 *    the three columns so heights can be compared by eye.
 */
(function () {
  "use strict";

  const C = window.CityRankCharts;
  const D = JSON.parse(document.getElementById("compare-data").textContent);
  const COLUMNS = 3;
  const pickers = Array.from(document.querySelectorAll(".city-select"));

  // ---- Small utilities ---------------------------------------------------------------

  // Escape text before putting it into HTML.
  function esc(value) {
    return String(value ?? "").replace(/[&<>"']/g, (ch) => (
      { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[ch]));
  }

  const isNum = (v) => typeof v === "number" && !Number.isNaN(v);
  const fmtScore = (v) => (isNum(v) ? Math.round(v) : "—");
  const fmtRank = (v) => (isNum(v) ? "#" + v : "—");
  const BEST = '<span class="best">Best</span>';

  // Indexes of the best value(s). `higherIsBetter` true/false; null = never mark.
  function bestOf(values, higherIsBetter) {
    if (higherIsBetter === null || higherIsBetter === undefined) return new Set();
    const nums = values.filter(isNum);
    if (nums.length < 2 || nums.every((v) => v === nums[0])) return new Set();
    const target = higherIsBetter ? Math.max(...nums) : Math.min(...nums);
    return new Set(values.map((v, i) => (v === target ? i : -1)).filter((i) => i >= 0));
  }

  // One comparison row: a full-width label, then one cell per selected city.
  function row(label, cells, note) {
    const head = '<div class="cmp-label">' + esc(label) + (note ? ' <span class="cmp-note">' + esc(note) + "</span>" : "") + "</div>";
    return head + cells.map((html) => '<div class="cmp-cell">' + html + "</div>").join("");
  }

  // A row of numbers where the best gets a badge. `cells` is [{value, html}].
  function scoredRow(label, values, htmls, higherIsBetter, note) {
    const best = bestOf(values, higherIsBetter);
    return row(label, htmls.map((h, i) => (best.has(i) ? '<span class="is-best">' + h + "</span>" + BEST : h)), note);
  }

  // ---- Which cities are selected -------------------------------------------------------

  // From the URL hash if valid; filled up with the top-ranked cities.
  function initialPicks() {
    const fromHash = decodeURIComponent(location.hash.slice(1)).split(",").filter((s) => s in D.cities);
    const picks = [...new Set(fromHash)];
    for (const slug of D.order) {
      if (picks.length >= COLUMNS) break;
      if (!picks.includes(slug)) picks.push(slug);
    }
    return picks.slice(0, COLUMNS);
  }

  let picks = initialPicks();
  const cities = () => picks.map((slug) => D.cities[slug]);

  // Fill each <select> with every city in rank order; wire up changes.
  function setupPickers() {
    pickers.forEach((select, column) => {
      select.innerHTML = D.order.map((slug) => {
        const c = D.cities[slug];
        return '<option value="' + esc(slug) + '">' + esc(fmtRank(c.rank) + "  " + c.name + ", " + c.province) + "</option>";
      }).join("");
      select.addEventListener("change", () => {
        const chosen = select.value;
        const other = picks.indexOf(chosen);
        // Picking a city already shown in another column swaps the two columns.
        if (other !== -1 && other !== column) picks[other] = picks[column];
        picks[column] = chosen;
        history.replaceState(null, "", "#" + picks.join(","));
        render();
      });
    });
  }

  // ---- Sections ---------------------------------------------------------------------------

  function renderHeader(list) {
    list.forEach((c, i) => {
      pickers[i].value = c.slug;
      document.getElementById("meta-" + i).innerHTML =
        '<div class="pick-name">' + esc(c.name) + "</div>" +
        '<div class="muted small">' + esc(c.region) + " · " + esc(c.province) + "</div>";
    });
  }

  function renderOverview(list) {
    const ranks = list.map((c) => c.rank);
    const scores = list.map((c) => c.overall);
    const pop = list.map((c) => c.metrics.population || {});
    document.getElementById("cmp-overview").innerHTML =
      scoredRow("Overall rank", ranks, ranks.map((r) => '<span class="cmp-big">' + fmtRank(r) + '</span><span class="muted small"> of ' + D.total_cities + "</span>"), false, "default weights") +
      scoredRow("Overall score", scores, list.map((c) =>
        '<span class="cmp-big">' + fmtScore(c.overall) + '</span><span class="muted small"> / 100</span>' +
        (isNum(c.coverage) && c.coverage < 0.999 ? '<div class="muted small">Some data missing (' + Math.round(c.coverage * 100) + "% of weight)</div>" : "")), true) +
      row("Population", pop.map((p) => esc(p.value || "—") + (p.period ? ' <span class="muted small">(' + esc(p.period) + ")</span>" : ""))) +
      row("Full details", list.map((c) => '<a href="city/' + esc(c.slug) + '.html">' + esc(c.name) + " city page →</a>"));
  }

  function renderCategories(list) {
    document.getElementById("cmp-categories").innerHTML = D.categories.map((cat) => {
      const values = list.map((c) => (c.categories[cat.key] || {}).score);
      const htmls = list.map((c) => {
        const s = c.categories[cat.key] || {};
        return '<div class="bar"><div class="bar-track"><div class="bar-fill" style="width:' + (isNum(s.score) ? s.score.toFixed(1) : 0) + '%"></div></div>' +
          '<span class="bar-value">' + fmtScore(s.score) + "</span></div>" +
          '<div class="muted small">' + (isNum(s.rank) ? fmtRank(s.rank) + " of " + D.total_cities : "no data") + "</div>";
      });
      return scoredRow(cat.label, values, htmls, true);
    }).join("");
  }

  function renderNow(list) {
    const now = list.map((c) => c.now || {});
    document.getElementById("cmp-now").innerHTML =
      row("Temperature", now.map((n) => '<span class="cmp-big">' + esc(n.temp) + " °C</span><div class=\"muted small\">" + esc(n.conditions) + "</div>")) +
      row("Humidity", now.map((n) => esc(n.humidity) + "%")) +
      row("Wind", now.map((n) => esc(n.wind) + " km/h")) +
      scoredRow("Air quality (US AQI)", now.map((n) => Number(n.aqi)), now.map((n) => esc(n.aqi) + ' <span class="muted small">' + esc(n.aqi_label) + "</span>"), false);
  }

  function renderForecast(list) {
    document.getElementById("cmp-forecast").innerHTML = row("Next 7 days", list.map((c) => {
      if (!c.forecast || !c.forecast.length) return '<span class="muted">No forecast</span>';
      return '<ul class="mini-forecast">' + c.forecast.map((f) =>
        "<li><span>" + esc(f.date.slice(0, 3)) + '</span><span class="num">' + esc(f.high) + "° / " + esc(f.low) + '°</span><span class="muted small">' + esc(f.conditions) + "</span></li>").join("") + "</ul>";
    }), "high / low °C");
  }

  // Chart rows: the cells are empty <div>s that drawCharts() fills.
  function chartCells(prefix, emptyText) {
    return picks.map((_, i) => '<div class="mini-chart" id="' + prefix + "-" + i + '" data-empty="' + esc(emptyText) + '"></div>');
  }

  function renderClimate(list) {
    const metric = (key) => list.map((c) => (c.metrics[key] || {}).raw);
    const show = (key, unit) => list.map((c) => esc((c.metrics[key] || {}).value || "—") + ' <span class="muted small">' + unit + "</span>");
    document.getElementById("cmp-climate").innerHTML =
      row("Average high and low, by month", chartCells("cmp-temp", "No climate data."), "°C") +
      row("Rain per month", chartCells("cmp-rain", "No climate data."), "mm") +
      row("Snow per month", chartCells("cmp-snow", "No climate data."), "cm") +
      scoredRow("Extreme cold days (below −20 °C)", metric("cold_days"), show("cold_days", "days"), false) +
      scoredRow("Hot days (above 30 °C)", metric("hot_days"), show("hot_days", "days"), false) +
      scoredRow("Sunshine", metric("sunshine_hours"), show("sunshine_hours", "hours"), true);
  }

  function renderRank() {
    document.getElementById("cmp-rank").innerHTML =
      row("Daily rank (default weights)", chartCells("cmp-rank", "Rank history builds up day by day."));
  }

  function renderTraffic(list) {
    const cong = list.map((c) => c.metrics.congestion_pct || {});
    document.getElementById("cmp-traffic").innerHTML =
      scoredRow("Rush-hour congestion (last 30 days)", cong.map((m) => m.raw),
        cong.map((m) => '<span class="cmp-big">' + esc(m.value || "—") + '</span><span class="muted small">% slower</span>'), false) +
      row("Average by weekday", chartCells("cmp-traffic", "No traffic samples yet."), "morning vs evening rush, %") +
      row("Days of data", list.map((c) => esc(c.traffic_days || 0)));
  }

  function renderMetrics(list) {
    document.getElementById("cmp-metrics").innerHTML = D.groups.map((group) => {
      const rows = group.keys.map((key) => {
        const meta = D.metrics[key];
        const entries = list.map((c) => c.metrics[key] || {});
        const htmls = entries.map((e) =>
          esc(e.value || "—") + ' <span class="muted small">' + esc(meta.unit) + "</span>" +
          (isNum(e.score) ? '<div class="muted small">score ' + Math.round(e.score) + (e.period ? " · " + esc(e.period) : "") + "</div>"
                          : (e.period ? '<div class="muted small">' + esc(e.period) + "</div>" : "")));
        const direction = meta.higher_is_better === null ? "" : (meta.higher_is_better ? "higher is better" : "lower is better");
        return scoredRow(meta.label, entries.map((e) => e.raw), htmls, meta.higher_is_better, direction);
      }).join("");
      return '<h3 class="cmp-group">' + esc(group.label) + "</h3>" + rows;
    }).join("");
  }

  // ---- Charts (small multiples with shared axes) -----------------------------------------

  // [min, max] over all non-null values of several arrays, or null if none.
  function extent(arrays) {
    const nums = arrays.flat().filter(isNum);
    return nums.length ? [Math.min(...nums), Math.max(...nums)] : null;
  }

  function miniLayout(t, yTitle, yRange) {
    const layout = C.baseLayout(t, yTitle);
    layout.height = 220;
    layout.margin = { l: 40, r: 8, t: 30, b: 30 };
    layout.font.size = 11;
    if (yRange) layout.yaxis.range = yRange;
    return layout;
  }

  const miniConfig = Object.assign({}, C.plotConfig, { displayModeBar: false });
  const monthDates = (months) => months.map((m) => m + "-01");   // "2026-03" -> a date Plotly understands

  function drawCharts() {
    if (typeof Plotly === "undefined") return;   // CDN blocked: the numbers are still on the page
    const t = C.theme();
    const list = cities();

    // Shared ranges so the three columns are directly comparable.
    const temp = extent(list.map((c) => c.monthly.temp_max_c.concat(c.monthly.temp_min_c)));
    const rain = extent(list.map((c) => c.monthly.rain_mm));
    const snow = extent(list.map((c) => c.monthly.snowfall_cm));
    const traffic = extent(list.map((c) => c.traffic_weekday.morning_pct.concat(c.traffic_weekday.evening_pct)));

    list.forEach((c, i) => {
      const m = c.monthly;
      const x = monthDates(m.month);

      // Average monthly high (orange) and low (blue).
      let el = document.getElementById("cmp-temp-" + i);
      C.resetEmpty(el);
      if (C.hasData(el, m.month)) {
        const layout = miniLayout(t, "°C", temp && [Math.floor(temp[0]) - 3, Math.ceil(temp[1]) + 3]);
        layout.showlegend = i === 0;               // one legend is enough for the row
        layout.legend = C.topLegend(t);
        layout.xaxis.tickformat = "%b";
        layout.xaxis.hoverformat = "%b %Y";
        Plotly.react(el, [
          { x, y: m.temp_max_c, name: "Avg high", type: "scatter", mode: "lines+markers", line: { color: t.s2, width: 2 },
            marker: { color: t.s2, size: 6 }, hovertemplate: "High %{y:.1f} °C<extra></extra>" },
          { x, y: m.temp_min_c, name: "Avg low", type: "scatter", mode: "lines+markers", line: { color: t.s1, width: 2 },
            marker: { color: t.s1, size: 6 }, hovertemplate: "Low %{y:.1f} °C<extra></extra>" },
        ], layout, miniConfig);
      }

      // Monthly rain and snow totals (separate charts: different units).
      [["cmp-rain-", m.rain_mm, rain, "mm", "Rain"], ["cmp-snow-", m.snowfall_cm, snow, "cm", "Snow"]].forEach(([prefix, ys, range, unit, label]) => {
        el = document.getElementById(prefix + i);
        C.resetEmpty(el);
        if (!C.hasData(el, m.month)) return;
        const layout = miniLayout(t, unit, range && [0, Math.max(1, range[1] * 1.1)]);
        layout.xaxis.tickformat = "%b";
        layout.xaxis.hoverformat = "%b %Y";
        layout.bargap = 0.2;
        Plotly.react(el, [{ x, y: ys, type: "bar", marker: { color: t.s1 },
          hovertemplate: label + " %{y:.0f} " + unit + "<extra></extra>" }], layout, miniConfig);
      });

      // Rank over time: #1 at the top, same 1..N scale for every column.
      el = document.getElementById("cmp-rank-" + i);
      C.resetEmpty(el);
      const h = c.rank_history;
      if (C.hasData(el, h.date.length >= 2 ? h.date : [])) {
        const layout = miniLayout(t, "Rank", [D.total_cities + 0.5, 0.5]);
        layout.yaxis.dtick = 5;
        layout.xaxis.tickformat = "%d %b";        // short labels fit the narrow columns
        layout.xaxis.nticks = 4;
        Plotly.react(el, [{ x: h.date, y: h.rank, customdata: h.overall, type: "scatter", mode: "lines+markers",
          line: { color: t.s1, width: 2 }, marker: { color: t.s1, size: 6 },
          hovertemplate: "Rank #%{y} · score %{customdata:.0f}<extra></extra>" }], layout, miniConfig);
      }

      // Traffic by weekday: morning (blue) vs evening (orange) bars.
      el = document.getElementById("cmp-traffic-" + i);
      C.resetEmpty(el);
      const w = c.traffic_weekday;
      if (C.hasData(el, w.morning_pct.concat(w.evening_pct))) {
        const layout = miniLayout(t, "%", traffic && [0, Math.max(1, traffic[1] * 1.15)]);
        layout.barmode = "group";
        layout.bargap = 0.25;
        layout.showlegend = i === 0;
        layout.legend = C.topLegend(t);
        const days = w.weekday.map((d) => d.slice(0, 3));
        Plotly.react(el, [
          { x: days, y: w.morning_pct, name: "Morning", type: "bar", marker: { color: t.s1 }, hovertemplate: "Morning %{y:.1f}%<extra></extra>" },
          { x: days, y: w.evening_pct, name: "Evening", type: "bar", marker: { color: t.s2 }, hovertemplate: "Evening %{y:.1f}%<extra></extra>" },
        ], layout, miniConfig);
      }
    });
  }

  // ---- Render everything for the current picks ---------------------------------------------
  function render() {
    const list = cities();
    renderHeader(list);
    renderOverview(list);
    renderCategories(list);
    renderNow(list);
    renderForecast(list);
    renderClimate(list);
    renderRank(list);
    renderTraffic(list);
    renderMetrics(list);
    drawCharts();
  }

  setupPickers();
  render();
  C.onThemeChange(drawCharts);
})();
