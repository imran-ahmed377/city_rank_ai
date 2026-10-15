/* Rankings page interactivity: re-score cities when the priority sliders move.
 *
 * The overall-score formula here MUST match score_overall() in
 * city_rank/scoring.py: a weighted average of the category scores the city
 * has data for, with weights re-normalised over those categories.
 */
(function () {
  "use strict";

  // ---- Read the page data embedded by the template ---------------------------
  const data = JSON.parse(document.getElementById("rank-data").textContent);
  const categories = data.categories;                      // [{key, label, default_weight}, ...]
  const rowsBySlug = Object.fromEntries(data.rows.map((r) => [r.slug, r]));
  const tbody = document.querySelector("#rank-table tbody");
  const sliders = Array.from(document.querySelectorAll("input[data-category]"));
  const stateLabel = document.getElementById("weights-state");
  const STORAGE_KEY = "city-rank-weights";

  // ---- Weighted average with per-city re-normalisation -----------------------
  function overallScore(scores, weights) {
    let sum = 0;
    let used = 0;
    for (const c of categories) {
      const w = weights[c.key] || 0;
      const s = scores[c.key];
      if (w > 0 && s !== null && s !== undefined) {
        sum += s * w;
        used += w;
      }
    }
    return used > 0 ? sum / used : null;
  }

  function currentWeights() {
    return Object.fromEntries(sliders.map((s) => [s.dataset.category, Number(s.value)]));
  }

  function isDefault(weights) {
    return categories.every((c) => weights[c.key] === c.default_weight);
  }

  // ---- Update the "x% of score" labels next to each slider -------------------
  function updateShareLabels(weights) {
    const total = Object.values(weights).reduce((a, b) => a + b, 0);
    for (const c of categories) {
      const share = total > 0 ? Math.round((weights[c.key] / total) * 100) : 0;
      document.getElementById("o-" + c.key).textContent = share + "%";
    }
  }

  // ---- Re-score, re-sort and re-number the table rows -------------------------
  function render() {
    const weights = currentWeights();
    updateShareLabels(weights);
    stateLabel.textContent = isDefault(weights) ? "Default weights" : "Custom weights";

    // Compute each row's new overall score.
    const rows = Array.from(tbody.querySelectorAll("tr")).map((tr) => ({
      tr,
      score: overallScore(rowsBySlug[tr.dataset.slug].scores, weights),
    }));

    // Best first; cities without any score go last.
    rows.sort((a, b) => (b.score ?? -1) - (a.score ?? -1));

    rows.forEach((row) => {
      // "min" ranking like the Python side: ties share the better rank.
      const rank = row.score === null ? "—" : 1 + rows.filter((o) => o.score !== null && o.score > row.score + 1e-9).length;
      row.tr.querySelector(".rank-cell").textContent = rank;
      row.tr.querySelector(".bar-fill").style.width = (row.score ?? 0).toFixed(1) + "%";
      row.tr.querySelector(".bar-value").textContent = row.score === null ? "—" : Math.round(row.score);
      tbody.appendChild(row.tr); // moving an existing node re-orders it
    });

    // Remember the visitor's weights in this browser (optional convenience).
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify(weights)); } catch (e) { /* storage blocked */ }
  }

  // ---- Restore saved weights, then wire up events ------------------------------
  try {
    const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || "null");
    if (saved) sliders.forEach((s) => { if (s.dataset.category in saved) s.value = saved[s.dataset.category]; });
  } catch (e) { /* ignore unreadable storage */ }

  sliders.forEach((s) => s.addEventListener("input", render));
  document.getElementById("reset-weights").addEventListener("click", () => {
    for (const c of categories) document.getElementById("w-" + c.key).value = c.default_weight;
    render();
  });

  render();
})();
