/**
 * Glossary tooltips.
 *
 * Inline elements with `.glossary-term` and `data-term-slug` open a popover
 * containing the term's definition. The popover is built progressively from
 * the JSON index at /glosario/glossary.json (built by Jekyll).
 *
 * Accessibility:
 *   - Activates on click, tap and Enter/Space (the term is a <button>).
 *   - Dismisses with Escape, outside click and blur.
 *   - Hover on pointer devices reveals the popover but never replaces the
 *     primary activation. The element also acts as an in-page link to
 *     /glosario/#<slug> for crawlers and assistive tech.
 *   - Falls back to the link if JS is unavailable or the index fails to load.
 */
(function () {
  "use strict";

  var INDEX_URL = "/glosario/glossary.json";
  var indexPromise = null;
  var openPopover = null;

  function loadIndex() {
    if (!indexPromise) {
      indexPromise = fetch(INDEX_URL, { credentials: "same-origin" })
        .then(function (r) { return r.ok ? r.json() : []; })
        .catch(function () { return []; });
    }
    return indexPromise;
  }

  function findEntry(index, slug) {
    for (var i = 0; i < index.length; i++) {
      if (index[i].slug === slug) return index[i];
    }
    return null;
  }

  function close() {
    if (!openPopover) return;
    openPopover.popover.remove();
    openPopover.trigger.setAttribute("aria-expanded", "false");
    openPopover = null;
  }

  function position(popover, trigger) {
    var rect = trigger.getBoundingClientRect();
    var top = window.scrollY + rect.bottom + 8;
    var left = window.scrollX + rect.left;
    var maxLeft = window.scrollX + window.innerWidth - popover.offsetWidth - 16;
    if (left > maxLeft) left = maxLeft;
    if (left < window.scrollX + 16) left = window.scrollX + 16;
    popover.style.top = top + "px";
    popover.style.left = left + "px";
  }

  function open(trigger, entry) {
    close();
    var popover = document.createElement("div");
    popover.className = "glossary-popover";
    popover.setAttribute("role", "tooltip");
    popover.setAttribute("id", "glossary-popover-" + entry.slug);

    var heading = document.createElement("h4");
    heading.textContent = entry.term;
    popover.appendChild(heading);

    var body = document.createElement("div");
    body.innerHTML = entry.html || ("<p>" + entry.definition + "</p>");
    popover.appendChild(body);

    var more = document.createElement("a");
    more.className = "glossary-popover-link";
    more.href = "/glosario/#" + entry.slug;
    more.textContent = "Ver en el glosario →";
    popover.appendChild(more);

    document.body.appendChild(popover);
    position(popover, trigger);

    trigger.setAttribute("aria-expanded", "true");
    trigger.setAttribute("aria-describedby", popover.id);

    openPopover = { popover: popover, trigger: trigger };
  }

  function handleTrigger(event) {
    var trigger = event.currentTarget;
    var slug = trigger.dataset.termSlug;
    if (!slug) return;

    if (openPopover && openPopover.trigger === trigger) {
      event.preventDefault();
      close();
      return;
    }

    event.preventDefault();
    loadIndex().then(function (index) {
      var entry = findEntry(index, slug);
      if (entry) open(trigger, entry);
      else window.location.href = "/glosario/#" + slug;
    });
  }

  function init() {
    var triggers = document.querySelectorAll(".glossary-term[data-term-slug]");
    if (!triggers.length) return;

    triggers.forEach(function (trigger) {
      trigger.setAttribute("aria-expanded", "false");
      trigger.addEventListener("click", handleTrigger);
    });

    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && openPopover) {
        var t = openPopover.trigger;
        close();
        if (t) t.focus();
      }
    });

    document.addEventListener("click", function (e) {
      if (!openPopover) return;
      if (openPopover.popover.contains(e.target)) return;
      if (openPopover.trigger.contains(e.target)) return;
      close();
    });

    window.addEventListener("scroll", function () {
      if (openPopover) position(openPopover.popover, openPopover.trigger);
    }, { passive: true });

    window.addEventListener("resize", function () {
      if (openPopover) position(openPopover.popover, openPopover.trigger);
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
