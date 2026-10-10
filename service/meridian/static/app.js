const VIEWS = {
  overview: {
    kicker: "Reports",
    heading: "Overview",
    lead: "Tokens, cost, and the shape of usage for this identity.",
  },
  platforms: {
    kicker: "Reports",
    heading: "Platforms",
    lead: "Claude and Gemini, for the group and week selected above.",
  },
  groups: {
    kicker: "Reports",
    heading: "Groups",
    lead: "Directory groups this role is allowed to see.",
  },
  weeks: {
    kicker: "Reports",
    heading: "Weeks",
    lead: "ISO weeks across the export window.",
  },
  detail: {
    kicker: "Reports",
    heading: "Breakdown",
    lead: "One line for each week, group, and platform.",
  },
  capabilities: {
    kicker: "Administration",
    heading: "Capabilities",
    lead: "Connector controls for the groups in the group filter. The week filter does not apply here.",
  },
};

const userSelect = document.getElementById("user");
const groupSelect = document.getElementById("group");
const weekSelect = document.getElementById("week");
const banner = document.getElementById("banner");
let directory = { users: [], groups: [] };
let me = null;
const groupNames = {};

function headers() {
  return { "X-User-Id": userSelect.value, "Content-Type": "application/json" };
}

async function get(path) {
  const response = await fetch(path, { headers: headers() });
  const body = await response.json();
  return { ok: response.ok, status: response.status, body };
}

function money(value) {
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(value);
}

function count(value) {
  if (value === null || value === undefined) return "—";
  return new Intl.NumberFormat("en-US").format(value);
}

function labelize(value) {
  return String(value || "").replaceAll("_", " ").replaceAll("-", " ").replace(/\b\w/g, (char) => char.toUpperCase());
}

function initials(name) {
  return name.split(/\s+/).slice(0, 2).map((part) => part.charAt(0).toUpperCase()).join("");
}

function personName(userId) {
  const user = directory.users.find((item) => item.user_id === userId);
  return user ? user.name : userId;
}

function when(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("en-US", { dateStyle: "medium", timeStyle: "short" }).format(date);
}

function applyView(name) {
  document.querySelectorAll(".view").forEach((view) => {
    view.hidden = view.dataset.view !== name;
  });
  document.querySelectorAll(".nav-btn").forEach((button) => {
    const on = button.dataset.view === name;
    button.classList.toggle("active", on);
    if (on) button.setAttribute("aria-current", "page");
    else button.removeAttribute("aria-current");
  });
  const view = VIEWS[name];
  document.getElementById("view-kicker").textContent = view.kicker;
  document.getElementById("view-heading").textContent = view.heading;
  document.getElementById("view-lead").textContent = view.lead;
  document.title = view.heading + " · Meridian usage";
}

function showView(name) {
  if (!VIEWS[name]) name = "overview";
  applyView(name);
  if (location.hash !== "#" + name) history.replaceState(null, "", "#" + name);
}

function showMessage(text, denied) {
  banner.className = denied ? "banner denied" : "banner";
  banner.setAttribute("role", denied ? "alert" : "status");
  banner.replaceChildren();
  const paragraph = document.createElement("p");
  paragraph.className = "banner-text";
  paragraph.textContent = text;
  banner.appendChild(paragraph);
}

function showIdentity() {
  banner.className = "banner";
  banner.setAttribute("role", "status");
  banner.replaceChildren();
  const avatar = document.createElement("div");
  avatar.className = "avatar";
  avatar.textContent = initials(me.name);
  const copy = document.createElement("div");
  const name = document.createElement("div");
  name.className = "identity-name";
  name.append(document.createTextNode(me.name));
  const pill = document.createElement("span");
  pill.className = "pill pill-" + me.role.replaceAll("_", "-");
  pill.textContent = labelize(me.role);
  name.appendChild(pill);
  const meta = document.createElement("div");
  meta.className = "identity-meta";
  const own = (me.groups || []).map((id) => groupNames[id] || id).join(", ");
  const scope = me.visible_groups.length === directory.groups.length
    ? "Sees every group"
    : "Sees own group only";
  meta.textContent = [me.email, own, scope].filter(Boolean).join(" · ");
  copy.append(name, meta);
  banner.append(avatar, copy);
}

const NO_RECORDS = "No record found";

function emptyNote(text) {
  const note = document.createElement("p");
  note.className = "empty-note";
  note.textContent = text;
  return note;
}

function emptyRow(colspan) {
  const tr = document.createElement("tr");
  tr.className = "empty";
  const td = document.createElement("td");
  td.className = "empty";
  td.colSpan = colspan;
  td.textContent = NO_RECORDS;
  tr.appendChild(td);
  return tr;
}

function barRow(title, meta, pct) {
  const row = document.createElement("div");
  const top = document.createElement("div");
  top.className = "bar-top";
  const name = document.createElement("strong");
  name.textContent = title;
  const value = document.createElement("span");
  value.textContent = meta;
  top.append(name, value);
  const track = document.createElement("div");
  track.className = "track";
  const fill = document.createElement("div");
  fill.className = "fill";
  fill.style.width = (pct > 0 ? Math.max(pct, 2) : 0) + "%";
  track.appendChild(fill);
  row.append(top, track);
  return row;
}

function setCount(id, value, noun) {
  const node = document.getElementById(id);
  node.textContent = value ? value + " " + noun : "";
}

function clearTables() {
  document.getElementById("tokens").textContent = "—";
  document.getElementById("cost").textContent = "—";
  document.getElementById("requests").textContent = "—";
  document.getElementById("caps").replaceChildren();
  document.getElementById("platforms").replaceChildren(emptyRow(5));
  document.getElementById("groups").replaceChildren(emptyRow(3));
  document.getElementById("weeks").replaceChildren(emptyRow(3));
  document.getElementById("rows").replaceChildren(emptyRow(5));
  document.getElementById("week-chart").replaceChildren(emptyNote(NO_RECORDS));
  document.getElementById("platform-mix").replaceChildren(emptyNote(NO_RECORDS));
  for (const id of ["platforms-count", "groups-count", "weeks-count", "rows-count"]) {
    document.getElementById(id).textContent = "";
  }
}

function fillSelect(select, options, previous) {
  select.replaceChildren();
  for (const option of options) {
    const node = document.createElement("option");
    node.value = option.value;
    node.textContent = option.label;
    select.appendChild(node);
  }
  if (previous && [...select.options].some((option) => option.value === previous)) {
    select.value = previous;
  }
}

function platformTag(name) {
  const tag = document.createElement("span");
  tag.className = "tag tag-" + name;
  tag.textContent = labelize(name);
  return tag;
}

function tableRows(target, records, cells) {
  const body = document.getElementById(target);
  body.replaceChildren();
  if (!records.length) {
    body.appendChild(emptyRow(cells.length));
    return;
  }
  for (const record of records) {
    const tr = document.createElement("tr");
    for (const cell of cells) {
      const td = document.createElement("td");
      if (cell.num) td.className = "num";
      if (cell.name) td.classList.add("name");
      const rendered = cell.render(record);
      if (rendered instanceof Node) td.appendChild(rendered);
      else td.textContent = rendered;
      tr.appendChild(td);
    }
    body.appendChild(tr);
  }
}

function renderCharts(platforms, weeks) {
  const mix = document.getElementById("platform-mix");
  const chart = document.getElementById("week-chart");
  mix.replaceChildren();
  chart.replaceChildren();
  const tokenTotal = platforms.reduce((sum, row) => sum + row.total_tokens, 0);
  const hasUsage = platforms.some((row) => row.total_tokens || row.cost_usd);
  if (!hasUsage) {
    mix.appendChild(emptyNote(NO_RECORDS));
    chart.appendChild(emptyNote(NO_RECORDS));
    return;
  }
  const peak = weeks.reduce((max, row) => Math.max(max, row.total_tokens), 0) || 1;
  if (!weeks.length) chart.appendChild(emptyNote(NO_RECORDS));
  for (const row of weeks) {
    chart.appendChild(barRow(
      row.week,
      count(row.total_tokens) + " · " + money(row.cost_usd),
      (row.total_tokens / peak) * 100,
    ));
  }
  for (const row of platforms) {
    const share = tokenTotal ? Math.round((row.total_tokens / tokenTotal) * 100) : 0;
    mix.appendChild(barRow(
      labelize(row.platform),
      share + "% · " + money(row.cost_usd),
      share,
    ));
  }
}

async function loadCapabilities() {
  const group = groupSelect.value;
  const path = group ? "/api/capabilities?group=" + encodeURIComponent(group) : "/api/capabilities";
  const result = await get(path);
  const host = document.getElementById("caps");
  const note = document.getElementById("cap-note");
  host.replaceChildren();
  if (!result.ok) {
    note.textContent = result.body.required_scope === "usage:read"
      ? NO_RECORDS
      : (result.body.reason || "Capabilities are not available.");
    return;
  }
  const writable = new Set(me.writable_groups || []);
  note.textContent = writable.size
    ? "Changes are saved immediately and apply to the assistant connector as well as this page. The week filter does not apply here."
    : "You can see these controls. Changing them needs capabilities:write, which your role does not have in this environment.";
  const byGroup = new Map();
  for (const row of result.body) {
    if (!byGroup.has(row.group)) byGroup.set(row.group, []);
    byGroup.get(row.group).push(row);
  }
  const ordered = [...byGroup.keys()].sort((a, b) => (groupNames[a] || a).localeCompare(groupNames[b] || b));
  for (const groupId of ordered) {
    const card = document.createElement("article");
    card.className = "cap-card";
    const head = document.createElement("div");
    head.className = "cap-card-head";
    const title = document.createElement("h3");
    title.textContent = groupNames[groupId] || groupId;
    const access = document.createElement("span");
    const canEdit = writable.has(groupId);
    access.className = "pill " + (canEdit ? "pill-team-lead" : "pill-member");
    access.textContent = canEdit ? "Editable" : "View only";
    head.append(title, access);
    card.appendChild(head);
    for (const row of byGroup.get(groupId)) {
      const line = document.createElement("div");
      line.className = "cap";
      const label = document.createElement("div");
      const name = document.createElement("div");
      name.className = "cap-title";
      name.textContent = labelize(row.capability);
      const meta = document.createElement("div");
      meta.className = "cap-meta";
      meta.textContent = row.updated_at
        ? "Updated " + when(row.updated_at) + " by " + personName(row.updated_by)
        : "Environment default";
      label.append(name, meta);
      const actions = document.createElement("div");
      actions.className = "cap-actions";
      const state = document.createElement("span");
      state.className = "cap-state" + (row.enabled ? " is-on" : "");
      state.textContent = row.enabled ? "On" : "Off";
      const toggle = document.createElement("label");
      toggle.className = "switch";
      const input = document.createElement("input");
      input.type = "checkbox";
      input.checked = row.enabled;
      input.disabled = !canEdit;
      input.setAttribute("aria-label", (groupNames[groupId] || groupId) + " " + labelize(row.capability));
      input.addEventListener("change", async () => {
        const next = input.checked;
        state.textContent = next ? "On" : "Off";
        state.classList.toggle("is-on", next);
        const saved = await fetch("/api/capabilities", {
          method: "PUT",
          headers: headers(),
          body: JSON.stringify({ group: row.group, capability: row.capability, enabled: next }),
        });
        const body = await saved.json();
        if (!saved.ok) {
          input.checked = !next;
          state.textContent = input.checked ? "On" : "Off";
          state.classList.toggle("is-on", input.checked);
          showMessage(body.reason || "The change was refused.", true);
          return;
        }
        await refresh();
      });
      const slider = document.createElement("span");
      slider.className = "slider";
      toggle.append(input, slider);
      actions.append(state, toggle);
      line.append(label, actions);
      card.appendChild(line);
    }
    host.appendChild(card);
  }
}

async function refresh() {
  const meResult = await get("/api/me");
  if (!meResult.ok) {
    me = null;
    showMessage(meResult.body.reason || "This person cannot be loaded.", true);
    clearTables();
    return;
  }
  me = meResult.body;
  const groupOptions = [{ value: "", label: "All visible groups" }];
  for (const id of me.visible_groups) {
    groupOptions.push({ value: id, label: groupNames[id] || id });
  }
  fillSelect(groupSelect, groupOptions, groupSelect.value);
  const group = groupSelect.value;
  const week = weekSelect.value;
  const params = new URLSearchParams();
  if (group) params.set("group", group);
  if (week) params.set("week", week);
  const usage = await get("/api/usage" + (params.toString() ? "?" + params : ""));
  if (!usage.ok) {
    const noRecords = usage.body.required_scope === "usage:read";
    if (noRecords) showIdentity();
    else showMessage(usage.body.reason || "Usage is not available for this person.", true);
    clearTables();
    fillSelect(weekSelect, [{ value: "", label: "All weeks" }], "");
    await loadCapabilities();
    return;
  }
  showIdentity();

  const previousWeek = weekSelect.value;
  const weekOptions = [{ value: "", label: "All weeks" }];
  for (const weekId of usage.body.weeks || []) weekOptions.push({ value: weekId, label: weekId });
  fillSelect(weekSelect, weekOptions, previousWeek);

  const platforms = usage.body.by_platform;
  const tokenTotal = platforms.reduce((sum, row) => sum + row.total_tokens, 0);
  const costTotal = platforms.reduce((sum, row) => sum + row.cost_usd, 0);
  const requestTotal = platforms.reduce((sum, row) => sum + (row.requests || 0), 0);
  document.getElementById("tokens").textContent = count(tokenTotal);
  document.getElementById("cost").textContent = money(costTotal);
  document.getElementById("requests").textContent = count(requestTotal);
  renderCharts(platforms, usage.body.by_week);

  tableRows("platforms", platforms, [
    { name: true, render: (row) => platformTag(row.platform) },
    { num: true, render: (row) => count(row.input_tokens) },
    { num: true, render: (row) => count(row.output_tokens) },
    { num: true, render: (row) => count(row.total_tokens) },
    { num: true, render: (row) => money(row.cost_usd) },
  ]);
  tableRows("groups", usage.body.by_group, [
    { name: true, render: (row) => groupNames[row.group] || row.group },
    { num: true, render: (row) => count(row.total_tokens) },
    { num: true, render: (row) => money(row.cost_usd) },
  ]);
  tableRows("weeks", usage.body.by_week, [
    { name: true, render: (row) => row.week },
    { num: true, render: (row) => count(row.total_tokens) },
    { num: true, render: (row) => money(row.cost_usd) },
  ]);
  tableRows("rows", usage.body.rows, [
    { render: (row) => row.week },
    { name: true, render: (row) => groupNames[row.group] || row.group },
    { render: (row) => platformTag(row.platform) },
    { num: true, render: (row) => count(row.total_tokens) },
    { num: true, render: (row) => money(row.cost_usd) },
  ]);
  setCount("platforms-count", platforms.length, platforms.length === 1 ? "platform" : "platforms");
  setCount("groups-count", usage.body.by_group.length, usage.body.by_group.length === 1 ? "group" : "groups");
  setCount("weeks-count", usage.body.by_week.length, usage.body.by_week.length === 1 ? "week" : "weeks");
  setCount("rows-count", usage.body.rows.length, usage.body.rows.length === 1 ? "row" : "rows");
  await loadCapabilities();
}

async function boot() {
  try {
    const meta = await (await fetch("/api/meta")).json();
    directory = await (await fetch("/api/directory/users")).json();
    for (const group of directory.groups) groupNames[group.group_id] = group.name;
    const foot = document.getElementById("foot");
    const env = document.createElement("div");
    env.className = "env-pill";
    env.textContent = meta.environment;
    const note = document.createElement("p");
    note.textContent = "Server " + meta.server_name + ". Periods are measured from " + meta.as_of + ", the end of the export.";
    foot.replaceChildren(env, note);
    const saved = localStorage.getItem("meridianUserId");
    for (const user of directory.users) {
      const option = document.createElement("option");
      option.value = user.user_id;
      const group = groupNames[user.group_ids[0]] || user.group_ids[0];
      option.textContent = user.name + " · " + labelize(user.role) + " · " + group;
      userSelect.appendChild(option);
    }
    const fallback = directory.users.find((user) => user.role === "team_lead" && user.group_ids[0] === "clinical-operations");
    userSelect.value = saved || (fallback && fallback.user_id) || directory.users[0].user_id;
    userSelect.addEventListener("change", () => {
      localStorage.setItem("meridianUserId", userSelect.value);
      groupSelect.value = "";
      refresh();
    });
    groupSelect.addEventListener("change", refresh);
    weekSelect.addEventListener("change", refresh);
    await refresh();
  } catch (error) {
    showMessage("The usage service did not respond.", true);
  }
}

document.querySelectorAll(".nav-btn").forEach((button) => {
  button.addEventListener("click", () => showView(button.dataset.view));
});
window.addEventListener("hashchange", () => {
  const name = location.hash.slice(1);
  if (VIEWS[name]) applyView(name);
});
showView((location.hash || "#overview").slice(1));
boot();
