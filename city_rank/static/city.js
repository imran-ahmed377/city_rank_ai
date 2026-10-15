/* City page charts (Plotly).
 *
 * Design rules followed here:
 *  - one y-axis per chart (rain and snow get separate charts, never a dual axis)
 *  - colours come from the CSS tokens in style.css, so light/dark mode match the page
 *  - thin 2px lines, hairline gridlines, hover tooltips on every chart
 *  - every chart has a text/table equivalent on the page (metrics table, monthly table)
 */
(function () {
  "use strict";

  const data = JSON.parse(document.getElementById("city-data").textContent);

  // ---- Theme: read colour tokens from CSS custom properties ----------------------
  function theme() {
    const css = getComputedStyle(document.documentElement);
    const v = (name) => css.getPropertyValue(name).trim();
    return {
      surface: v("--surface"), ink: v("--ink"), ink2: v("--ink-2"), muted: v("--muted"),
      grid: v("--grid"), axis: v("--axis"), s1: v("--series-1"), s2: v("--series-2"),
    };
  }

  // ---- Shared layout: transparent background, hairline grid, x-unified hover --------
  function baseLayout(t, yTitle) {
    return {
      height: 320,
      margin: { l: 56, r: 16, t: 28, b: 40 },
      paper_bgcolor: "rgba(0,0,0,0)",
      plot_bgcolor: "rgba(0,0,0,0)",
      font: { family: "system-ui, -apple-system, Segoe UI, sans-serif", color: t.ink2, size: 12 },
      hovermode: "x unified",
      hoverlabel: { bgcolor: t.surface, bordercolor: t.axis, font: { color: t.ink } },
      showlegend: false,
      xaxis: { showgrid: false, linecolor: t.axis, tickcolor: t.axis, tickfont: { color: t.muted } },
      yaxis: {
        title: { text: yTitle, font: { color: t.ink2 } },
        gridcolor: t.grid, zerolinecolor: t.axis, tickfont: { color: t.muted },
      },
    };
  }

  const plotConfig = { responsive: true, displaylogo: false, modeBarButtonsToRemove: ["lasso2d", "select2d"] };

  // Show the element's "empty" message instead of a chart when there is no data.
  function hasData(el, xs) {
    if (xs && xs.length > 0) return true;
    el.innerHTML = '<p class="chart-note">' + el.dataset.empty + "</p>";
    el.style.minHeight = "0";
    return false;
  }

  // ---- Individual charts ----------------------------------------------------------

  // Two series (high, low): legend on top + direct end labels in text colour.
  function temperatureChart(t) {
    const el = document.getElementById("chart-temp");
    const c = data.climate;
    if (!hasData(el, c.date)) return;
    const last = c.date.length - 1;
    const layout = baseLayout(t, "°C");
    layout.showlegend = true;
    layout.legend = { orientation: "h", x: 0, y: 1.12, font: { color: t.ink2 } };
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
    ], layout, plotConfig);
  }

  // Single-series daily bar chart (used for rain and snowfall).
  function dailyBars(t, id, ys, unit, label) {
    const el = document.getElementById(id);
    if (!hasData(el, data.climate.date)) return;
    const layout = baseLayout(t, unit);
    layout.height = 260;
    layout.bargap = 0.15;
    Plotly.react(el, [
      { x: data.climate.date, y: ys, type: "bar", name: label, marker: { color: t.s1 },
        hovertemplate: label + " %{y:.1f} " + unit + "<extra></extra>" },
    ], layout, plotConfig);
  }

  // Rank history: rank 1 at the top (reversed axis).
  function rankChart(t) {
    const el = document.getElementById("chart-rank");
    const h = data.rank_history;
    if (!hasData(el, h.date.length >= 2 ? h.date : [])) return;
    const layout = baseLayout(t, "Rank");
    layout.height = 260;
    layout.yaxis.range = [data.total_cities + 0.5, 0.5];
    layout.yaxis.dtick = 2;
    Plotly.react(el, [
      { x: h.date, y: h.rank, customdata: h.overall, type: "scatter", mode: "lines+markers",
        line: { color: t.s1, width: 2 }, marker: { color: t.s1, size: 8, line: { color: t.surface, width: 2 } },
        hovertemplate: "Rank #%{y} · score %{customdata:.0f}<extra></extra>" },
    ], layout, plotConfig);
  }

  // Daily mean rush-hour congestion.
  function trafficChart(t) {
    const el = document.getElementById("chart-traffic");
    const tr = data.traffic;
    if (!hasData(el, tr.date)) return;
    const layout = baseLayout(t, "% slower than free flow");
    layout.height = 260;
    layout.yaxis.rangemode = "tozero";
    Plotly.react(el, [
      { x: tr.date, y: tr.congestion_pct, type: "scatter", mode: "lines+markers",
        line: { color: t.s1, width: 2 }, marker: { color: t.s1, size: 8, line: { color: t.surface, width: 2 } },
        hovertemplate: "%{y:.1f}% slower<extra></extra>" },
    ], layout, plotConfig);
  }

  // ---- Draw everything (and redraw when the OS switches light/dark) ----------------
  function drawAll() {
    if (typeof Plotly === "undefined") return; // CDN blocked: tables still carry the data
    const t = theme();
    temperatureChart(t);
    dailyBars(t, "chart-rain", data.climate.rain_mm, "mm", "Rain");
    dailyBars(t, "chart-snow", data.climate.snowfall_cm, "cm", "Snow");
    rankChart(t);
    trafficChart(t);
  }

  drawAll();
  window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", drawAll);
})();
