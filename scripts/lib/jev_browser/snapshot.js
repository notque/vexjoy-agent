// In-page snapshot for the Jev browser harness. Evaluated via CDP
// Runtime.evaluate; returns a JSON-serializable page state.
//
// Contract:
//   window.__jevBrowser.nodes   Map<int, Element>  code-owned node identities
//   window.__jevBrowser.ids     WeakMap<Element,int>
//   window.__jevBrowser.pageKey()  string  document identity (url + doc token)
//   window.__jevBrowser.guard(el)  string  semantic guard for one control
//   window.__jevBrowser.marker()   string  full semantic marker for freshness
//
// The returned object:
//   { url, title, text, scroll, page_key, marker, guards, elements, actions }
// elements: [{index, role, label, value, checked, expanded, operations, node}]
// actions:  [{id, kind, node, index, label, value?, delta?}]
//
// Model output never becomes selectors. Every executable action refers to a
// code-owned integer node id resolved from this registry.
(() => {
  const MAX_ELEMENTS = 250;
  const MAX_TEXT = 6000;

  const reg = (window.__jevBrowser ||= {
    nodes: new Map(),
    ids: new WeakMap(),
    next: 1,
    docToken: Math.random().toString(36).slice(2),
  });

  // Semantic freshness helpers. Freshness compares meaning (url, form values,
  // the selected control and its surroundings), not raw DOM mutation counts,
  // so animations and unrelated widgets do not invalidate a decision.
  const fieldState = (el) => {
    if (!el) return "";
    const tag = el.tagName;
    if (tag === "SELECT") return `s=${el.value}`;
    if (tag === "INPUT") {
      const t = (el.type || "").toLowerCase();
      if (t === "checkbox" || t === "radio") return `c=${el.checked ? 1 : 0}`;
      if (t === "password") return `p=${el.value ? 1 : 0}`;
      return `v=${(el.value || "").slice(0, 200)}`;
    }
    if (tag === "TEXTAREA") return `v=${(el.value || "").slice(0, 200)}`;
    return "";
  };
  reg.pageKey ||= () => `${location.href}#${reg.docToken}`;
  reg.guard ||= (el) => {
    if (!el || !el.isConnected) return "gone";
    const r = el.getBoundingClientRect();
    const ctx = el.closest("form, [role=dialog], dialog, tr, li, fieldset") || el.parentElement;
    const near = (ctx?.innerText || "").replace(/\s+/g, " ").trim().slice(0, 300);
    const dis = el.matches(":disabled") || !!el.closest('[aria-disabled="true"],[inert]');
    return [fieldState(el), dis ? "d" : "e", Math.round(r.x), Math.round(r.y), near].join("|");
  };
  reg.marker ||= () => {
    const forms = [...document.querySelectorAll("input,select,textarea")]
      .filter((e) => e.checkVisibility?.())
      .map((e) => `${e.name || e.id || ""}:${fieldState(e)}`)
      .join(";");
    const text = (document.body?.innerText || "").replace(/\s+/g, " ").trim().slice(0, 4000);
    return `${reg.pageKey()}|${Math.round(scrollY)}|${forms}|${text}`;
  };

  const idFor = (el) => {
    let id = reg.ids.get(el);
    if (id === undefined) {
      id = reg.next++;
      reg.ids.set(el, id);
      reg.nodes.set(id, el);
    }
    return id;
  };

  // Prune disconnected references so ids are never reused for new nodes.
  for (const [id, el] of reg.nodes) if (!el.isConnected) reg.nodes.delete(id);

  const EDITABLE_INPUT = new Set([
    "text", "search", "email", "url", "tel", "password", "number", "date",
    "datetime-local", "month", "week", "time", "",
  ]);

  // Rendered anywhere in the document. Offscreen controls are still offered
  // (marked offscreen); the driver scrolls them into view before input.
  const rendered = (el) => {
    if (!el.isConnected) return false;
    if (!el.checkVisibility?.({ checkOpacity: true, checkVisibilityCSS: true })) return false;
    const r = el.getBoundingClientRect();
    return !!(r.width && r.height);
  };
  const inViewport = (el) => {
    const r = el.getBoundingClientRect();
    return r.bottom > 0 && r.top < innerHeight && r.right > 0 && r.left < innerWidth;
  };

  const disabled = (el) =>
    el.matches(":disabled") || !!el.closest('[aria-disabled="true"],[inert]');

  // Occlusion: a control whose center is covered by something outside it
  // (a modal backdrop, sticky header, toast) cannot be clicked by a user, so
  // Jev must not be offered it. Same test the driver applies before input.
  const covered = (el) => {
    const r = el.getBoundingClientRect();
    const x = Math.min(innerWidth - 1, Math.max(0, r.x + r.width / 2));
    const y = Math.min(innerHeight - 1, Math.max(0, r.y + r.height / 2));
    const hit = document.elementFromPoint(x, y);
    if (!hit) return true;
    return !(el.contains(hit) || hit.contains(el) || (el.tagName === "LABEL" && el.control === hit));
  };

  const clean = (s) => (s || "").replace(/\s+/g, " ").trim().slice(0, 80);

  const labelFor = (el) => {
    const aria = el.getAttribute("aria-label");
    if (aria) return clean(aria);
    const by = el.getAttribute("aria-labelledby");
    if (by) {
      const parts = by.split(/\s+/).map((i) => document.getElementById(i)?.textContent || "");
      const t = clean(parts.join(" "));
      if (t) return t;
    }
    if (el.labels?.length) {
      const t = clean([...el.labels].map((l) => l.textContent).join(" "));
      if (t) return t;
    }
    for (const attr of ["placeholder", "title", "alt", "name"]) {
      const v = el.getAttribute(attr);
      if (v) return clean(v);
    }
    const t = clean(el.textContent);
    if (t) return t;
    const near = el.closest("label, td, li, div")?.textContent;
    return clean(near);
  };

  const roleFor = (el) => {
    const r = el.getAttribute("role");
    if (r) return r;
    const tag = el.tagName;
    if (tag === "A" && el.hasAttribute("href")) return "link";
    if (tag === "BUTTON") return "button";
    if (tag === "SELECT") return "combobox";
    if (tag === "TEXTAREA") return "textbox";
    if (tag === "INPUT") {
      const t = (el.type || "text").toLowerCase();
      if (t === "checkbox") return "checkbox";
      if (t === "radio") return "radio";
      if (t === "submit" || t === "button" || t === "reset" || t === "image") return "button";
      if (t === "search") return "searchbox";
      return "textbox";
    }
    if (/^H[1-6]$/.test(tag)) return "heading";
    if (tag === "SUMMARY") return "button";
    return tag.toLowerCase();
  };

  const isEditable = (el) => {
    if (el.readOnly || el.getAttribute("aria-readonly") === "true") return false;
    if (el.tagName === "TEXTAREA") return true;
    if (el.tagName === "INPUT") return EDITABLE_INPUT.has((el.type || "").toLowerCase());
    if (el.isContentEditable) return true;
    const role = el.getAttribute("role");
    return role === "textbox" || role === "searchbox" || role === "combobox";
  };

  const isClickable = (el) => {
    const tag = el.tagName;
    if (["A", "BUTTON", "SUMMARY", "LABEL"].includes(tag)) return true;
    if (tag === "INPUT") return !isEditable(el) || true; // inputs are clickable (focus)
    if (tag === "SELECT") return false; // use SELECT op instead
    const role = el.getAttribute("role");
    if (role && /^(button|link|tab|menuitem|option|checkbox|radio|switch|treeitem|menuitemcheckbox|menuitemradio)$/.test(role)) return true;
    if (el.hasAttribute("onclick") || el.tabIndex >= 0) return true;
    return false;
  };

  const valueFor = (el) => {
    if (el.tagName === "SELECT") return clean(el.options[el.selectedIndex]?.textContent);
    if (el.tagName === "INPUT" || el.tagName === "TEXTAREA") {
      const t = (el.type || "").toLowerCase();
      if (t === "checkbox" || t === "radio") return "";
      if (t === "password") return el.value ? "(filled)" : "";
      return clean(el.value).slice(0, 80);
    }
    if (el.isContentEditable) return clean(el.textContent).slice(0, 80);
    return "";
  };

  const elements = [];
  const actions = [];
  const guards = {};
  const modal = [...document.querySelectorAll('[role=dialog][aria-modal="true"], dialog[open]')].find(rendered) || null;
  const candidates = document.querySelectorAll(
    "a[href],button,input,select,textarea,summary,[role],[onclick],[tabindex],[contenteditable=''],[contenteditable='true'],h1,h2,h3"
  );

  for (const el of candidates) {
    if (elements.length >= MAX_ELEMENTS) break;
    if (!rendered(el) || disabled(el)) continue;
    const role = roleFor(el);
    const isHeading = role === "heading";
    const onscreen = inViewport(el);
    // Only in-viewport controls can be occlusion-tested; a modal backdrop
    // covers everything behind it, so when a modal is open offscreen
    // controls outside it are dropped too.
    if (!isHeading && onscreen && covered(el)) continue;
    if (!isHeading && !onscreen && modal && !modal.contains(el)) continue;
    const ops = [];
    if (!isHeading) {
      if (el.tagName === "SELECT") ops.push("SELECT");
      else {
        if (isClickable(el)) ops.push("CLICK");
        if (isEditable(el)) ops.push("TYPE_TEXT");
      }
    }
    if (!ops.length && !isHeading) continue;

    const node = idFor(el);
    const index = String(elements.length + 1);
    const entry = { index, node, role, label: labelFor(el), value: valueFor(el), operations: ops };
    if (!onscreen) entry.offscreen = true;
    const t = (el.type || "").toLowerCase();
    if (el.tagName === "A" && el.href) {
      if (!el.href.startsWith(location.origin)) entry.external = true;
      else {
        try {
          const u = new URL(el.href);
          if (u.pathname !== location.pathname) entry.nav = u.pathname;
        } catch {}
      }
    }
    if (t === "checkbox" || t === "radio" || el.getAttribute("role") === "checkbox" || el.getAttribute("role") === "switch") {
      entry.checked = el.checked ?? el.getAttribute("aria-checked") === "true";
    }
    if (el.hasAttribute("aria-expanded")) entry.expanded = el.getAttribute("aria-expanded") === "true";
    if (el.hasAttribute("aria-selected")) entry.selected = el.getAttribute("aria-selected") === "true";
    if (el.tagName === "SELECT") {
      entry.options = [...el.options]
        .filter((o) => !o.disabled)
        .slice(0, 60)
        .map((o, i) => ({ index: `${index}:${i + 1}`, label: clean(o.textContent), value: o.value }));
    }
    elements.push(entry);
    guards[node] = reg.guard(el);

    for (const op of ops) {
      if (op === "SELECT") {
        for (const o of entry.options) actions.push({ id: `e${node}:sel:${o.value}`, kind: "select", node, index: o.index, label: `${entry.label} → ${o.label}`, value: o.value });
      } else if (op === "CLICK") {
        actions.push({ id: `e${node}:click`, kind: "click", node, index, label: entry.label });
      } else if (op === "TYPE_TEXT") {
        actions.push({ id: `e${node}:fill`, kind: "fill", node, index, label: entry.label, role });
      }
    }
  }

  const canScroll = document.documentElement.scrollHeight > innerHeight + 4;
  if (canScroll) {
    actions.push({ id: "scroll_down", kind: "scroll", delta: Math.round(innerHeight * 0.8), label: "Scroll down" });
    actions.push({ id: "scroll_up", kind: "scroll", delta: -Math.round(innerHeight * 0.8), label: "Scroll up" });
  }
  actions.push({ id: "wait", kind: "wait", label: "Wait" });

  const text = (document.body?.innerText || "").replace(/\s+/g, " ").trim().slice(0, MAX_TEXT);

  return {
    url: location.href,
    title: document.title,
    text,
    scroll: { x: Math.round(scrollX), y: Math.round(scrollY) },
    page_key: reg.pageKey(),
    marker: reg.marker(),
    guards,
    elements,
    actions,
  };
})();
