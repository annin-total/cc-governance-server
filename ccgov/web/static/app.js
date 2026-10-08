"use strict";
// 画面の操作だけを受け持つ（タブの切り替え・絞り込み・部署の絞り込み・並べ替え・一覧の折りたたみ・ツールチップ・グラフと表の連動・カレンダーの送りと開閉・削除の確認）。中身はサーバが描画済みで、data-* 属性だけを見る。
// 値を HTML として組み立てない（textContent と属性の切り替えだけを使う）。
(() => {
  document.documentElement.classList.add("js");

  const all = (root, sel) => Array.from(root.querySelectorAll(sel));
  const fmt = (n) => n.toLocaleString("ja-JP");

  // 長い一覧の折りたたみ（data-fold="N"）: 絞り込みで残った行のうち、今の並びの先頭 N 行だけを出し、残りは「さらに表示」で開く。
  // 絞り込み・並べ替えのたびに数え直し、開閉の状態は保つ。残りが無ければボタンを隠す。文言は data-fold-more・data-fold-close
  const FOLDABLE = ":scope > table > tbody > tr, :scope > .m-item";
  const foldButtons = new Map();

  function refold(box) {
    const btn = foldButtons.get(box);
    const n = Number(box.dataset.fold);
    const items = all(box, FOLDABLE);
    const shown = items.filter((e) => !e.hidden);
    const open = btn.getAttribute("aria-expanded") === "true";
    for (const e of items) e.removeAttribute("data-folded");
    if (!open) for (const e of shown.slice(n)) e.setAttribute("data-folded", "");
    btn.hidden = shown.length <= n;
    btn.textContent = open ? box.dataset.foldClose : box.dataset.foldMore.replace("{}", fmt(shown.length - n));
  }

  function refoldIn(root) {
    for (const box of all(root, "[data-fold]")) refold(box);
  }

  function setupFold(box) {
    const btn = Object.assign(document.createElement("button"), { type: "button", className: "fold-more" });
    btn.setAttribute("aria-expanded", "false");
    btn.addEventListener("click", () => {
      btn.setAttribute("aria-expanded", String(btn.getAttribute("aria-expanded") !== "true"));
      refold(box);
    });
    box.after(btn);
    foldButtons.set(box, btn);
    refold(box);
  }

  // 部署の絞り込み（[data-org]）: 値は [部]・[部, 課] の JSON（名簿に無い利用者は空文字）で、行の data-dept・data-sec と比べる。
  // 選んだ部・課は URL の dept=・sec= に持ち、ページの中のリンクにも付けて、タブとページをまたいで保つ。
  // 課を選ぶとその部も選んだ扱いにし、部の中で課を 1 つも選ばなければ部の全課を出す。部の合算の行（data-sec が無い）は部で絞る
  const parseKey = (key, length) => {
    // URL から来る値なので、形の合わないものは null にして捨てる
    try {
      const v = JSON.parse(key);
      return Array.isArray(v) && v.length === length ? v : null;
    } catch (err) {
      return null;
    }
  };
  const deptOf = (sec) => { const v = parseKey(sec, 2); return v && JSON.stringify([v[0]]); };
  const query = new URLSearchParams(location.search);
  const org = {
    depts: new Set(query.getAll("dept").filter((d) => d === "" || parseKey(d, 1))),
    secs: new Set(query.getAll("sec").filter(deptOf)),
  };

  function withOrg(href) {
    const url = new URL(href);
    url.searchParams.delete("dept");
    url.searchParams.delete("sec");
    for (const d of org.depts) url.searchParams.append("dept", d);
    for (const s of org.secs) url.searchParams.append("sec", s);
    return url;
  }
  const redraws = [];

  function orgSel() {
    const depts = new Set(org.depts);
    const secs = new Map();
    for (const s of org.secs) {
      const d = deptOf(s);
      depts.add(d);
      secs.set(d, (secs.get(d) || new Set()).add(s));
    }
    return { depts, secs };
  }

  function orgHit(tr, sel) {
    if (!sel.depts.size || tr.dataset.dept === undefined) return true;
    if (!sel.depts.has(tr.dataset.dept)) return false;
    const mine = sel.secs.get(tr.dataset.dept);
    return tr.dataset.sec === undefined || !mine || mine.has(tr.dataset.sec);
  }

  const axisOf = (chip) => Number(chip.closest("[data-axis]").dataset.axis);

  function filter(panel, state) {
    const q = state.q.toLowerCase();
    const sel = orgSel();
    const rows = all(panel, "tbody tr");
    let shown = 0;
    for (const tr of rows) {
      const tags = (tr.dataset.tags || "").split(" ");
      const chips = state.chips.every((c) => c === "all" || tags.includes(c));
      const hit = chips && orgHit(tr, sel) && (!q || (tr.dataset.q || "").toLowerCase().includes(q));
      tr.hidden = !hit;
      if (hit) shown += 1;
    }
    const counter = panel.querySelector("[data-shown]");
    if (counter) counter.textContent = fmt(shown);
    // 「すべて」の無い区分: 分母は選んだ区分の行の数、グラフ（data-when）も区分に合わせて切り替える
    const total = panel.querySelector("[data-total]");
    if (total) total.textContent = fmt(rows.filter((tr) => (tr.dataset.tags || "").split(" ").includes(state.chips[0])).length);
    for (const el of all(panel, "[data-when]")) el.hidden = el.dataset.when !== state.chips[0];
    const empty = panel.querySelector("[data-empty]");
    if (empty) empty.hidden = shown > 0;
    for (const b of all(panel, "[data-chip]")) b.setAttribute("aria-pressed", String(b.dataset.chip === state.chips[axisOf(b)]));
    refoldIn(panel);
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
    refoldIn(panel);
  }

  function setup(section) {
    const tabs = all(section, "[data-tab]");
    const panels = all(section, "[data-panel]");
    const firstChips = (p) => all(p, "[data-axis]").map((g) => g.querySelector("[data-chip]").dataset.chip);
    const states = new Map(panels.map((p) => [p.dataset.panel, { chips: firstChips(p), q: "" }]));
    const cards = all(document, "[data-open]");

    function open(id, chip, fromCard) {
      const target = states.has(id) ? id : panels[0].dataset.panel;
      for (const t of tabs) t.setAttribute("aria-selected", String(t.dataset.tab === target));
      for (const p of panels) p.hidden = p.dataset.panel !== target;
      for (const c of cards) c.classList.toggle("is-open", Boolean(fromCard) && c.dataset.open === `${target}${chip ? ":" + chip : ""}`);
      const panel = panels.find((p) => p.dataset.panel === target);
      const state = states.get(target);
      if (chip && panel.querySelector(`[data-axis="0"] [data-chip="${CSS.escape(chip)}"]`)) state.chips[0] = chip;
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
          state.chips[axisOf(chip)] = chip.dataset.chip;
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
    redraws.push(() => { for (const p of panels) filter(p, states.get(p.dataset.panel)); });
  }

  // 部署の絞り込みの見た目（押したチップ・押せない課・ボタンの文言）と URL を今の選択にそろえ、表を絞り直す。
  // 選んだ部があれば、その部に入らない課は押せない。ボタンの文言は data-org-* の雛形に、選んだ最初の名前と残りの数を入れる
  const fillIn = (template, ...values) => { let i = 0; return template.replace(/\{\}/g, () => values[i++]); };

  function orgName(widget, key) {
    const chip = all(widget, "[data-dept], [data-sec]").find((b) => (b.dataset.dept ?? b.dataset.sec) === key);
    if (chip) return chip.textContent;
    if (key === "") return widget.dataset.orgUnk;
    const v = parseKey(key, 1) || parseKey(key, 2);
    return v[v.length - 1] ?? "—";
  }

  function syncOrg() {
    const sel = orgSel();
    const keys = [...sel.depts, ...org.secs];
    for (const w of all(document, "[data-org]")) {
      for (const b of all(w, "[data-dept]")) b.setAttribute("aria-pressed", String(sel.depts.has(b.dataset.dept)));
      for (const b of all(w, "[data-sec]")) {
        b.setAttribute("aria-pressed", String(org.secs.has(b.dataset.sec)));
        b.disabled = sel.depts.size > 0 && !sel.depts.has(b.dataset.in);
      }
      const pressed = all(w, "[data-dept], [data-sec]").filter((b) => b.getAttribute("aria-pressed") === "true");
      const first = pressed.length ? pressed[0].textContent : keys.length ? orgName(w, keys[0]) : "";
      w.querySelector("[data-org-toggle]").textContent = !keys.length ? w.dataset.orgAll
        : keys.length === 1 ? fillIn(w.dataset.orgOne, first) : fillIn(w.dataset.orgSome, first, fmt(keys.length - 1));
    }
    history.replaceState(null, "", withOrg(location.href));
    for (const redraw of redraws) redraw();
  }

  function closeOrg(except) {
    for (const w of all(document, "[data-org]")) {
      if (w === except) continue;
      w.querySelector("[data-org-panel]").hidden = true;
      w.querySelector("[data-org-toggle]").setAttribute("aria-expanded", "false");
    }
  }

  document.addEventListener("click", (e) => {
    const w = e.target.closest("[data-org]");
    closeOrg(w);
    if (!w) return;
    const toggle = e.target.closest("[data-org-toggle]");
    const dept = e.target.closest("[data-dept]");
    const sec = e.target.closest("[data-sec]");
    if (toggle) {
      const box = w.querySelector("[data-org-panel]");
      box.hidden = !box.hidden;
      toggle.setAttribute("aria-expanded", String(!box.hidden));
      return;
    }
    if (dept) {
      const key = dept.dataset.dept;
      if (orgSel().depts.has(key)) {
        org.depts.delete(key);
        for (const s of [...org.secs]) if (deptOf(s) === key) org.secs.delete(s);
      } else {
        org.depts.add(key);
      }
    } else if (sec) {
      if (!org.secs.delete(sec.dataset.sec)) org.secs.add(sec.dataset.sec);
    } else if (e.target.closest("[data-org-clear]")) {
      org.depts.clear();
      org.secs.clear();
    } else {
      return;
    }
    syncOrg();
  });

  // ページの中のリンク（ナビ・期間・カレンダー）に、選んだ部署を付けて渡す
  document.addEventListener("click", (e) => {
    const a = e.target.closest("a[href]");
    if (!a || a.origin !== location.origin || a.getAttribute("href").startsWith("#")) return;
    a.href = withOrg(a.href).href;
  });

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

  // 期間の切り替えとカレンダーの日は、開いているタブ（#タブ:区分）を持ち越す
  document.addEventListener("click", (e) => {
    const a = e.target.closest("a[data-period], [data-cal] a");
    if (a && location.hash) a.href = a.href.split("#")[0] + location.hash;
  });

  // カレンダー（details[data-cal]）: サーバが描いた月を 1 つずつ見せる。開閉のたびに選んだ日の月（data-current）に戻す。
  // JS が無ければ描いた月がすべて並び、送りのボタンは隠れたまま
  function setupCal(cal) {
    const months = all(cal, "[data-month]");
    const moves = all(cal, "[data-cal-move]");
    const home = Math.max(0, months.findIndex((m) => m.hasAttribute("data-current")));
    let shown = home;
    const show = () => {
      months.forEach((m, i) => { m.hidden = i !== shown; });
      for (const b of moves) b.disabled = !months[shown + Number(b.dataset.calMove)];
    };
    for (const b of moves) {
      b.hidden = false;
      b.addEventListener("click", () => { shown += Number(b.dataset.calMove); show(); });
    }
    cal.addEventListener("toggle", () => {
      shown = home;
      show();
    });
    show();
  }

  // 開いたカレンダーは、外を押すか Esc で閉じる
  document.addEventListener("click", (e) => {
    for (const cal of all(document, "details[data-cal][open]")) if (!cal.contains(e.target)) cal.open = false;
  });
  document.addEventListener("keydown", (e) => {
    if (e.key !== "Escape") return;
    closeOrg(null);
    for (const cal of all(document, "details[data-cal][open]")) {
      cal.open = false;
      cal.querySelector("summary").focus();
    }
  });

  document.addEventListener("DOMContentLoaded", () => {
    all(document, "[data-fold]").forEach(setupFold);
    all(document, "details[data-cal]").forEach(setupCal);
    all(document, "[data-tabs]").forEach(setup);
    if (document.querySelector("[data-org]")) syncOrg();
    for (const el of all(document, "[data-tip]")) {
      el.removeAttribute("title");
      for (const t of all(el, "title")) t.remove();
    }
    document.body.appendChild(tip);
  });
})();
