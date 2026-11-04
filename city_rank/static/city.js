/* City page charts (Plotly). Shared helpers live in charts.js (window.CityRankCharts).
 *
 * Charts: rank over time, daily high/low temperature, daily rain, daily snowfall,
 * rush-hour congestion per day (morning vs evening) and by weekday.
 * Every chart has a table equivalent further down the page.
 */
(function () {
  "use strict";

  const C = window.CityRankCharts;
  const data = JSON.parse(document.getElementById("city-data").textContent);

  // ---- Climate ---------------------------------------------------------------------

  // Two series (high, low): legend on top + direct end labels in text colour.
  function temperatureChart(t) {
    const el = document.getElementById("chart-temp");
    const c = data.climate;
    if (!C.hasData(el, c.date)) return;
    const last = c.date.length - 1;
    const layout = C.baseLayout(t, "°C");
    layout.showlegend = true;
    layout.legend = C.topLegend(t);
    layout.margin.r = 44;
    layout.annotations = [
      { x: c.date[last], y: c.temp_max_c[last], text: "High", xanchor: "left", showarrow: false, xshift: 4, font: { color: t.ink2 } },
      { x: c.date[last], y: c.temp_min_c[last], text: "Low", xanchor: "left", showarrow: false, xshift: 4, font: { color: t.ink2 } },
    ];
    Plotly.react(el, [
      { x: c.date, y: c.temp_max_c, name: "Daily high", type: "scatter", mode: "lines",
        line: { color: t.s2, width: 2 }, hovertemplate: "High %{y:.1f} °C<extra></extra>" },
      { x: c.date, y: c.temp_min_c, name: "Daily low", type: "scatter", mode: "lines",
        line: { color: t.s1, width: 2 }, hovertemplate: "Low %{y:.1f} °C<extra></extra>" },
    ], layout, C.plotConfig);
  }

  // Single-series daily bar chart (used for rain and snowfall).
  function dailyBars(t, id, ys, unit, label) {
    const el = document.getElementById(id);
    if (!C.hasData(el, data.climate.date)) return;
    const layout = C.baseLayout(t, unit);
    layout.height = 260;
    layout.bargap = 0.15;
    Plotly.react(el, [
      { x: data.climate.date, y: ys, type: "bar", name: label, marker: { color: t.s1 },
        hovertemplate: label + " %{y:.1f} " + unit + "<extra></extra>" },
    ], layout, C.plotConfig);
  }

  // ---- Rank history: rank 1 at the top (reversed axis) ------------------------------
  function rankChart(t) {
    const el = document.getElementById("chart-rank");
    const h = data.rank_history;
    if (!C.hasData(el, h.date.length >= 2 ? h.date : [])) return;
    const layout = C.baseLayout(t, "Rank");
    layout.height = 260;
    layout.yaxis.range = [data.total_cities + 0.5, 0.5];
    layout.yaxis.dtick = 2;
    Plotly.react(el, [
      { x: h.date, y: h.rank, customdata: h.overall, type: "scatter", mode: "lines+markers",
        line: { color: t.s1, width: 2 }, marker: { color: t.s1, size: 8, line: { color: t.surface, width: 2 } },
        hovertemplate: "Rank #%{y} · score %{customdata:.0f}<extra></extra>" },
    ], layout, C.plotConfig);
  }

  // ---- Traffic ------------------------------------------------------------------------

  // Every sampled day (local date), morning and evening rush as two series.
  // The hover header shows the weekday name, e.g. "Monday, 26 Oct 2026".
  function trafficDailyChart(t) {
    const el = document.getElementById("chart-traffic");
    const tr = data.traffic;
    if (!C.hasData(el, tr.date)) return;
    const layout = C.baseLayout(t, "% slower than free flow");
    layout.height = 280;
    layout.showlegend = true;
    layout.legend = C.topLegend(t);
    layout.yaxis.rangemode = "tozero";
    layout.xaxis.hoverformat = "%A, %d %b %Y";
    layout.xaxis.type = "date";
    const marker = (color) => ({ color: color, size: 8, line: { color: t.surface, width: 2 } });
    Plotly.react(el, [
      { x: tr.date, y: tr.morning_pct, name: "Morning rush (07–10)", type: "scatter", mode: "lines+markers",
        connectgaps: false, line: { color: t.s1, width: 2 }, marker: marker(t.s1),
        hovertemplate: "Morning %{y:.1f}%<extra></extra>" },
      { x: tr.date, y: tr.evening_pct, name: "Evening rush (16–19)", type: "scatter", mode: "lines+markers",
        connectgaps: false, line: { color: t.s2, width: 2 }, marker: marker(t.s2),
        hovertemplate: "Evening %{y:.1f}%<extra></extra>" },
    ], layout, C.plotConfig);
  }

  // Average by weekday (Monday-Friday) over the whole history: grouped bars.
  function trafficWeekdayChart(t) {
    const el = document.getElementById("chart-traffic-weekday");
    const w = data.traffic_weekday;
    if (!C.hasData(el, w.morning_pct.concat(w.evening_pct))) return;
    const layout = C.baseLayout(t, "% slower than free flow");
    layout.height = 280;
    layout.showlegend = true;
    layout.legend = C.topLegend(t);
    layout.barmode = "group";
    layout.bargap = 0.3;
    layout.bargroupgap = 0.08;
    layout.yaxis.rangemode = "tozero";
    Plotly.react(el, [
      { x: w.weekday, y: w.morning_pct, name: "Morning rush", type: "bar", marker: { color: t.s1 },
        hovertemplate: "Morning %{y:.1f}%<extra></extra>" },
      { x: w.weekday, y: w.evening_pct, name: "Evening rush", type: "bar", marker: { color: t.s2 },
        hovertemplate: "Evening %{y:.1f}%<extra></extra>" },
    ], layout, C.plotConfig);
  }

  // ---- Draw everything, and redraw on light/dark switches ------------------------------
  function drawAll() {
    if (typeof Plotly === "undefined") return; // CDN blocked: tables still carry the data
    const t = C.theme();
    temperatureChart(t);
    dailyBars(t, "chart-rain", data.climate.rain_mm, "mm", "Rain");
    dailyBars(t, "chart-snow", data.climate.snowfall_cm, "cm", "Snow");
    rankChart(t);
    trafficDailyChart(t);
    trafficWeekdayChart(t);
  }

  drawAll();
  C.onThemeChange(drawAll);
})();
