"use strict";
// 画面の操作だけを受け持つ（タブの切り替え・絞り込み・並べ替え・ツールチップ・グラフと表の連動・削除の確認）。中身はサーバが描画済みで、data-* 属性だけを見る。
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
    // 「すべて」の無い区分: 分母は選んだ区分の行の数、グラフ（data-when）も区分に合わせて切り替える
    const total = panel.querySelector("[data-total]");
    if (total) total.textContent = fmt(rows.filter((tr) => (tr.dataset.tags || "").split(" ").includes(state.chip)).length);
    for (const el of all(panel, "[data-when]")) el.hidden = el.dataset.when !== state.chip;
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
    const firstChip = (p) => { const c = p.querySelector("[data-chip]"); return c ? c.dataset.chip : "all"; };
    const states = new Map(panels.map((p) => [p.dataset.panel, { chip: firstChip(p), q: "" }]));
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

  // ツールチップ: カードの小さなグラフの点と丸めた値（data-tip）。文言は「見出し  値」で、2 つの空白の前を薄く、後ろを濃く出す。
  // JS が無ければ同じ文言の title が出る。ツールチップを出すときは title を外し、二重に出さない
  const TIP_OFFSET = 14;
  const TIP_MARGIN = 4;
  const tip = Object.assign(document.createElement("div"), { className: "tip", hidden: true });
  tip.setAttribute("role", "tooltip");

  function placeTip(e) {
    const r = tip.getBoundingClientRect();
    const above = e.clientY - r.height - TIP_OFFSET;
    tip.style.left = `${Math.min(e.clientX + TIP_OFFSET, window.innerWidth - r.width - TIP_MARGIN)}px`;
    tip.style.top = `${above < TIP_MARGIN ? e.clientY + TIP_OFFSET : above}px`;
  }

  function guide(target) {
    for (const line of all(document, ".spark-guide.is-on")) line.classList.remove("is-on");
    const line = target && target.closest("svg") && target.closest("svg").querySelector(".spark-guide");
    if (!line || target.dataset.gx === undefined) return;
    line.setAttribute("x1", target.dataset.gx);
    line.setAttribute("x2", target.dataset.gx);
    line.classList.add("is-on");
  }

  function showTip(target, e) {
    const [head, ...rest] = target.dataset.tip.split("  ");
    const parts = rest.length ? [["span", head], ["b", rest.join("  ")]] : [["b", head]];
    tip.replaceChildren(...parts.map(([tag, text]) => Object.assign(document.createElement(tag), { textContent: text })));
    tip.hidden = false;
    guide(target);
    placeTip(e);
  }

  // 下段のグラフと表の連動: 同じ data-link の棒（svg の g）と行を強調する。
  // グラフから当てた行が表の枠の中で見えていなければ、枠の中だけを最小限動かす（ページは動かさない）
  const LINKED = "svg g[data-link], tbody tr[data-link]";

  function unlink(panel) {
    panel.classList.remove("is-linking");
    for (const el of all(panel, ".is-hot")) el.classList.remove("is-hot");
  }

  function reveal(row) {
    const box = row.closest(".tscroll");
    const head = box.querySelector("thead").getBoundingClientRect().height;
    const b = box.getBoundingClientRect();
    const r = row.getBoundingClientRect();
    const top = Math.max(b.top + head, 0);
    const bottom = Math.min(b.bottom, window.innerHeight);
    if (bottom - top < r.height) return;
    if (r.top < top) box.scrollTop -= top - r.top;
    else if (r.bottom > bottom) box.scrollTop += r.bottom - bottom;
  }

  function link(el, panel) {
    unlink(panel);
    panel.classList.add("is-linking");
    const same = all(panel, LINKED).filter((x) => x.dataset.link === el.dataset.link);
    for (const x of same) x.classList.add("is-hot");
    const row = same.find((x) => x.tagName === "TR");
    if (el.tagName !== "TR" && row && !row.hidden) reveal(row);
  }

  document.addEventListener("pointerover", (e) => {
    const target = e.target.closest("[data-tip]");
    if (target) showTip(target, e);
    const linked = e.target.closest(LINKED);
    const panel = linked && linked.closest("[data-panel]");
    if (panel) link(linked, panel);
  });
  document.addEventListener("pointermove", (e) => { if (!tip.hidden) placeTip(e); });
  document.addEventListener("pointerout", (e) => {
    const target = e.target.closest("[data-tip]");
    if (target && !target.contains(e.relatedTarget)) {
      tip.hidden = true;
      guide(null);
    }
    const linked = e.target.closest(LINKED);
    const panel = linked && linked.closest("[data-panel]");
    if (panel && !linked.contains(e.relatedTarget)) unlink(panel);
  });

  // 取り消せない操作（削除）は、送る前にブラウザの確認を出す。文言は data-confirm の属性値をそのまま使う
  document.addEventListener("submit", (e) => {
    const form = e.target.closest("form[data-confirm]");
    if (form && !window.confirm(form.dataset.confirm)) e.preventDefault();
  });

  // 期間の切り替えは、開いているタブ（#タブ:区分）を持ち越す
  document.addEventListener("click", (e) => {
    const a = e.target.closest("a[data-period]");
    if (a && location.hash) a.href = a.href.split("#")[0] + location.hash;
  });

  document.addEventListener("DOMContentLoaded", () => {
    all(document, "[data-tabs]").forEach(setup);
    for (const el of all(document, "[data-tip]")) {
      el.removeAttribute("title");
      for (const t of all(el, "title")) t.remove();
    }
    document.body.appendChild(tip);
  });
})();
