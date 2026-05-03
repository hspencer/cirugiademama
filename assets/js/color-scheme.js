/**
 * Color scheme toggle: auto → light → dark → auto
 * Persists in localStorage, applies via [data-color-scheme] on <html>.
 * Initial value applied inline in <head> before paint to avoid FOUC.
 */
(function () {
  "use strict";

  var STATES = ["auto", "light", "dark"];
  var LABELS = { auto: "Auto", light: "Claro", dark: "Oscuro" };
  var STORAGE_KEY = "color-scheme";

  function read() {
    try { return localStorage.getItem(STORAGE_KEY) || "auto"; }
    catch (e) { return "auto"; }
  }
  function write(value) {
    try { localStorage.setItem(STORAGE_KEY, value); } catch (e) {}
  }
  function apply(value) {
    document.documentElement.dataset.colorScheme = value;
  }
  function next(current) {
    return STATES[(STATES.indexOf(current) + 1) % STATES.length];
  }

  function initToggle(button) {
    function refresh() {
      var current = read();
      button.dataset.state = current;
      var label = button.querySelector(".color-scheme-label");
      if (label) label.textContent = LABELS[current];
      button.setAttribute(
        "aria-label",
        "Cambiar tema (actual: " + LABELS[current] + ")"
      );
    }
    button.addEventListener("click", function () {
      var newState = next(read());
      write(newState);
      apply(newState);
      refresh();
    });
    refresh();
  }

  function initNavToggle() {
    var btn = document.querySelector(".nav-toggle");
    var header = document.querySelector(".site-header");
    if (!btn || !header) return;
    btn.addEventListener("click", function () {
      var open = header.dataset.navOpen === "true";
      header.dataset.navOpen = open ? "false" : "true";
      btn.setAttribute("aria-expanded", open ? "false" : "true");
      btn.setAttribute("aria-label", open ? "Abrir menú" : "Cerrar menú");
    });
  }

  function initSubmenus() {
    var hasTouch = "ontouchstart" in window || navigator.maxTouchPoints > 0;
    var triggers = document.querySelectorAll(".site-nav-item.has-submenu > a[aria-haspopup='true']");

    function closeAll(except) {
      triggers.forEach(function (t) {
        if (t === except) return;
        t.setAttribute("aria-expanded", "false");
      });
    }

    triggers.forEach(function (trigger) {
      // Touch / coarse pointer: tap toggles instead of navigating.
      trigger.addEventListener("click", function (e) {
        if (!hasTouch || window.matchMedia("(max-width: 800px)").matches) return;
        var expanded = trigger.getAttribute("aria-expanded") === "true";
        if (!expanded) {
          e.preventDefault();
          closeAll(trigger);
          trigger.setAttribute("aria-expanded", "true");
        }
      });
    });

    document.addEventListener("keydown", function (e) {
      if (e.key !== "Escape") return;
      var anyOpen = document.querySelector(".site-nav-item.has-submenu > a[aria-expanded='true']");
      if (anyOpen) {
        anyOpen.setAttribute("aria-expanded", "false");
        anyOpen.focus();
      }
    });

    document.addEventListener("click", function (e) {
      if (e.target.closest(".site-nav-item.has-submenu")) return;
      closeAll(null);
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    var toggle = document.querySelector(".color-scheme-toggle");
    if (toggle) initToggle(toggle);
    initNavToggle();
    initSubmenus();
  });
})();
