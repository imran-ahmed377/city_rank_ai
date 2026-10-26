/* Light/dark theme button, shared by every page.
 *
 * By default the site follows the OS setting (prefers-color-scheme). Clicking
 * the button sets <html data-theme="light|dark">, which style.css uses to
 * override the OS choice, and remembers it in localStorage. A small inline
 * script in base.html applies the saved choice before the page paints, so
 * there is no flash of the wrong theme.
 *
 * After a switch this fires a "themechange" event on document so the charts
 * (city.js) can redraw with the new colour tokens.
 */
(function () {
  "use strict";

  const STORAGE_KEY = "city-rank-theme";   // must match the inline script in base.html
  const root = document.documentElement;
  const darkQuery = window.matchMedia("(prefers-color-scheme: dark)");
  const button = document.getElementById("theme-toggle");
  if (!button) return;

  // ---- The theme in effect now: the visitor's choice, else the OS setting ------
  function currentTheme() {
    return root.dataset.theme || (darkQuery.matches ? "dark" : "light");
  }

  // ---- Button text names the theme a click switches *to* ------------------------
  function updateLabel() {
    const next = currentTheme() === "dark" ? "light" : "dark";
    button.querySelector(".theme-label").textContent = next === "dark" ? "Dark" : "Light";
    button.setAttribute("aria-label", "Switch to " + next + " theme");
  }

  // ---- Flip the theme, remember it, and tell the charts ---------------------------
  button.addEventListener("click", function () {
    const next = currentTheme() === "dark" ? "light" : "dark";
    root.dataset.theme = next;
    try { localStorage.setItem(STORAGE_KEY, next); } catch (e) { /* storage blocked */ }
    updateLabel();
    document.dispatchEvent(new Event("themechange"));
  });

  // The OS setting can change while the page is open (e.g. automatic night mode).
  darkQuery.addEventListener("change", updateLabel);

  // The button is hidden in the HTML so it never shows without JavaScript.
  updateLabel();
  button.hidden = false;
})();
