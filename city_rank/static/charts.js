/* Shared Plotly helpers for the city page (city.js) and the compare page (compare.js).
 *
 * Design rules followed by every chart on the site:
 *  - one y-axis per chart (never a dual axis)
 *  - colours come from the CSS tokens in style.css, so light/dark mode match the page
 *  - thin 2px lines, hairline gridlines, hover tooltips on every chart
 *  - every chart has a text/table equivalent on the page
 */
window.CityRankCharts = (function () {
  "use strict";

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

  // Horizontal legend above the plot (used when a chart has 2 series).
  function topLegend(t) {
    return { orientation: "h", x: 0, y: 1.15, font: { color: t.ink2 } };
  }

  const plotConfig = { responsive: true, displaylogo: false, modeBarButtonsToRemove: ["lasso2d", "select2d"] };

  // Show the element's data-empty message instead of a chart when there is no data.
  function hasData(el, xs) {
    if (xs && xs.some((x) => x !== null && x !== undefined)) return true;
    if (window.Plotly) Plotly.purge(el);
    el.innerHTML = '<p class="chart-note">' + (el.dataset.empty || "No data yet.") + "</p>";
    el.style.minHeight = "0";
    return false;
  }

  // Undo hasData's "empty" state before drawing (the compare page reuses elements).
  function resetEmpty(el) {
    if (el.querySelector(".chart-note")) el.innerHTML = "";
    el.style.minHeight = "";
  }

  // Redraw callback whenever the OS or the theme button switches light/dark.
  function onThemeChange(redraw) {
    window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", redraw);
    document.addEventListener("themechange", redraw);   // fired by theme.js
  }

  return { theme, baseLayout, topLegend, plotConfig, hasData, resetEmpty, onThemeChange };
})();
