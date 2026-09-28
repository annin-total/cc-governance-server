"use strict";
// 画面の操作だけを受け持つ（タブの切り替え・絞り込み・並べ替え）。中身はサーバが描画済みで、data-* 属性だけを見る。
// 値を HTML として組み立てない（textContent と属性の切り替えだけを使う）。
(() => {
  document.documentElement.classList.add("js");

  const all = (root, sel) => Array.from(root.querySelectorAll(sel));
  const fmt = (n) => n.toLocaleString("ja-JP");

  function filter(panel, state) {
    const q = state.q.toLowerCase();
    const rows = all(panel, "tbody tr");
    let shown = 0;
    for (const tr of rows) {
      const tags = (tr.dataset.tags || "").split(" ");
      const hit = (state.chip === "all" || tags.includes(state.chip)) && (!q || (tr.dataset.q || "").toLowerCase().includes(q));
      tr.hidden = !hit;
      if (hit) shown += 1;
    }
    const counter = panel.querySelector("[data-shown]");
    if (counter) counter.textContent = fmt(shown);
    const empty = panel.querySelector("[data-empty]");
    if (empty) empty.hidden = shown > 0;
    for (const b of all(panel, "[data-chip]")) b.setAttribute("aria-pressed", String(b.dataset.chip === state.chip));
  }

  function compare(a, b) {
    const x = a === "" ? -Infinity : Number(a);
    const y = b === "" ? -Infinity : Number(b);
    if (!Number.isNaN(x) && !Number.isNaN(y)) return x - y;
    return a.localeCompare(b, "ja");
  }

  function sort(panel, button) {
    const th = button.closest("th");
    const index = Number(button.dataset.sort);
    const dir = th.getAttribute("aria-sort") === "descending" ? 1 : -1;
    for (const other of all(panel, "thead th")) other.removeAttribute("aria-sort");
    th.setAttribute("aria-sort", dir > 0 ? "ascending" : "descending");
    const tbody = panel.querySelector("tbody");
    const value = (tr) => tr.children[index].dataset.v || "";
    all(tbody, "tr").sort((a, b) => compare(value(a), value(b)) * dir).forEach((tr) => tbody.appendChild(tr));
  }

  function setup(section) {
    const tabs = all(section, "[data-tab]");
    const panels = all(section, "[data-panel]");
    const states = new Map(panels.map((p) => [p.dataset.panel, { chip: "all", q: "" }]));
    const cards = all(document, "[data-open]");

    function open(id, chip, fromCard) {
      const target = states.has(id) ? id : panels[0].dataset.panel;
      for (const t of tabs) t.setAttribute("aria-selected", String(t.dataset.tab === target));
      for (const p of panels) p.hidden = p.dataset.panel !== target;
      for (const c of cards) c.classList.toggle("is-open", Boolean(fromCard) && c.dataset.open === `${target}${chip ? ":" + chip : ""}`);
      const panel = panels.find((p) => p.dataset.panel === target);
      const state = states.get(target);
      if (chip && panel.querySelector(`[data-chip="${CSS.escape(chip)}"]`)) state.chip = chip;
      filter(panel, state);
    }

    function go(hash, fromCard) {
      history.replaceState(null, "", hash);
      const [id, chip] = hash.slice(1).split(":");
      open(id, chip, fromCard);
    }

    for (const p of panels) {
      const bar = p.querySelector("[data-filter]");
      if (bar) bar.hidden = false;
      const state = states.get(p.dataset.panel);
      const input = p.querySelector("[data-search]");
      if (input) input.addEventListener("input", () => { state.q = input.value.trim(); filter(p, state); });
      p.addEventListener("click", (e) => {
        const chip = e.target.closest("[data-chip]");
        const sorter = e.target.closest("[data-sort]");
        if (chip) {
          state.chip = chip.dataset.chip;
          for (const c of cards) c.classList.remove("is-open");
          filter(p, state);
        }
        if (sorter) sort(p, sorter);
      });
    }
    for (const t of tabs) t.addEventListener("click", (e) => { e.preventDefault(); go(`#${t.dataset.tab}`, false); });
    for (const c of cards) {
      c.addEventListener("click", (e) => {
        e.preventDefault();
        go(`#${c.dataset.open}`, true);
        section.scrollIntoView({ block: "start" });
      });
    }
    const [id, chip] = location.hash.slice(1).split(":");
    open(id, chip, Boolean(chip));
  }

  document.addEventListener("DOMContentLoaded", () => all(document, "[data-tabs]").forEach(setup));
})();
