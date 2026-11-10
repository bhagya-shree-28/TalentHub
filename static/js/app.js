"use strict";
/* TalentHub frontend. Talks to the FastAPI backend under /api (same origin). */

const BRANCHES = ["CSE", "ISE", "ECE", "MECH", "CIVIL"];
const $ = (s, r = document) => r.querySelector(s);
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const pill = (s, label) => `<span class="pill ${s}">${label || s[0] + s.slice(1).toLowerCase()}</span>`;
const toDate = d => new Date(/^\d{4}-\d{2}-\d{2}$/.test(d) ? d + "T00:00" : d);
const fmtD = d => toDate(d).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" });
const fmtT = d => toDate(d).toLocaleString("en-IN", { day: "numeric", month: "short", hour: "numeric", minute: "2-digit" });
const lpa = n => `${Number(n).toFixed(2).replace(/\.?0+$/, "")} LPA`;
const plural = (n, w) => `${n} ${w}${n === 1 ? "" : "s"}`;

/* ---------------------------------------------------------------- session + API */
const KEY = "talenthub.session";
let session = null, loginNote = "";
try { session = JSON.parse(localStorage.getItem(KEY)); } catch (e) { /* ignore */ }

function signOut(note = "") {
  session = null; loginNote = note;
  try { localStorage.removeItem(KEY); } catch (e) { /* ignore */ }
  location.hash = "";
  route();
}

async function api(method, path, body) {
  let res;
  try {
    res = await fetch("/api" + path, {
      method,
      headers: { "Content-Type": "application/json", ...(session ? { Authorization: "Bearer " + session.token } : {}) },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch (e) {
    throw new Error("Can't reach the server. Check that it is running and try again.");
  }
  let data = null;
  try { data = await res.json(); } catch (e) { /* no body */ }
  if (res.status === 401 && session && path !== "/auth/login") {
    signOut((data && data.detail) || "Your session has expired. Please sign in again.");
    throw new Error("Signed out");
  }
  if (!res.ok) throw new Error((data && typeof data.detail === "string" && data.detail) || "Something went wrong. Please try again.");
  return data;
}

let toastTimer;
function toast(text, bad) {
  const t = $("#toast");
  t.textContent = text; t.className = "show" + (bad ? " bad" : "");
  clearTimeout(toastTimer); toastTimer = setTimeout(() => { t.className = ""; }, 3000);
}
async function guard(fn) {
  try { await fn(); } catch (e) { if (e.message !== "Signed out") toast(e.message, true); }
}

/* ---------------------------------------------------------------- views */
const ROUTES = {
  student: [["dash", "Dashboard"], ["drives", "Job drives"], ["apps", "My applications"], ["profile", "Profile"]],
  officer: [["post", "Post a drive"], ["applicants", "Applicants and offers"], ["reports", "Reports"]],
};
const V = {};
let onlyOk = false, curJob = 0;

/* ---- student ---- */
V.dash = async () => {
  const [me, apps, jobs] = await Promise.all([api("GET", "/students/me"), api("GET", "/applications/me"), api("GET", "/jobs")]);
  const count = s => apps.filter(a => a.status === s).length;
  const open = jobs.filter(j => !j.reason && !j.applied).length;
  const slots = apps.filter(a => a.status === "SHORTLISTED")
    .flatMap(a => a.interviews.filter(i => i.passed == null).map(i => ({ ...i, job: a.job })))
    .sort((x, y) => toDate(x.scheduled_at) - toDate(y.scheduled_at));
  const offers = apps.filter(a => a.offer && !a.offer.accepted && a.status === "OFFERED");
  $("#main").innerHTML = `<h1>Hi, ${esc(me.full_name.split(" ")[0])}</h1>
  <div class="stats">
    <div class="card"><b>${open}</b><span>Drives you can apply to</span></div>
    <div class="card"><b>${apps.length}</b><span>Applications</span></div>
    <div class="card"><b>${count("SHORTLISTED")}</b><span>Shortlisted</span></div>
    <div class="card"><b>${count("OFFERED") + count("ACCEPTED")}</b><span>Offers</span></div>
  </div>
  <div class="two">
    <section class="card"><h3>Upcoming interviews</h3>${slots.length ? slots.map(s => `<div class="li"><b>${esc(s.job.role)}</b>, ${esc(s.job.company)}<p class="sl">Round ${s.round_no}: ${fmtT(s.scheduled_at)}, ${esc(s.venue)}</p></div>`).join("") : '<p class="muted">No interviews scheduled yet.</p>'}</section>
    <section class="card"><h3>Offers waiting for you</h3>${offers.length ? offers.map(a => `<div class="li row"><div><b>${esc(a.job.company)}</b><p class="sl">${lpa(a.offer.package_lpa)}, ${esc(a.job.role)}</p></div><button class="btn sm" data-act="accept" data-id="${a.offer.id}">Accept</button></div>`).join("") : '<p class="muted">No pending offers.</p>'}</section>
  </div>`;
};

const driveCard = j => `<article class="card">
  <div class="row"><div><h3>${esc(j.role)}</h3><p class="muted">${esc(j.company)}</p></div>${j.applied ? pill("APPLIED") : ""}</div>
  <dl class="kv">
    <div><dt>Drive date</dt><dd>${fmtD(j.drive_date)}</dd></div><div><dt>Minimum CGPA</dt><dd>${j.min_cgpa}</dd></div>
    <div><dt>Max active backlogs</dt><dd>${j.max_backlogs}</dd></div><div><dt>Branches</dt><dd>${j.branches.length ? j.branches.join(", ") : "All branches"}</dd></div>
  </dl>
  ${j.applied ? "" : j.reason ? `<p class="why">${esc(j.reason)}</p>` : `<button class="btn" data-act="apply" data-id="${j.id}">Apply</button>`}
</article>`;

V.drives = async () => {
  const jobs = await api("GET", "/jobs");
  const draw = () => {
    const list = jobs.filter(j => !onlyOk || (!j.reason && !j.applied));
    $("#main").innerHTML = `<div class="top"><h1>Job drives</h1><label class="chk"><input type="checkbox" id="only" ${onlyOk ? "checked" : ""}>Only drives I can apply to</label></div>
    ${list.length ? `<div class="grid">${list.map(driveCard).join("")}</div>` : '<div class="empty">No drives match. Untick the filter to see every drive.</div>'}`;
    $("#only").onchange = e => { onlyOk = e.target.checked; draw(); };
  };
  draw();
};

const STEPS = ["APPLIED", "SHORTLISTED", "OFFERED", "ACCEPTED"];
const stepper = status => {
  if (status === "REJECTED") return "";
  const at = STEPS.indexOf(status);
  return `<ol class="steps" aria-label="Progress">${STEPS.map((s, i) => `<li class="${i < at ? "done" : i === at ? "now" : ""}">${s[0] + s.slice(1).toLowerCase()}</li>`).join("")}</ol>`;
};

V.apps = async () => {
  const apps = await api("GET", "/applications/me");
  $("#main").innerHTML = `<h1>My applications</h1>${apps.length ? apps.map(a => `<article class="card app">
    <div class="row"><div><h3>${esc(a.job.role)}</h3><p class="muted">${esc(a.job.company)}, applied ${fmtD(a.applied_at)}</p></div>${pill(a.status)}</div>
    ${stepper(a.status)}
    ${a.interviews.map(i => `<p class="sl">Round ${i.round_no}: ${fmtT(i.scheduled_at)}, ${esc(i.venue)}${i.passed === true ? " (passed)" : i.passed === false ? " (not cleared)" : ""}</p>`).join("")}
    ${a.offer ? `<div class="offer"><b>${lpa(a.offer.package_lpa)} offer</b>${a.offer.accepted ? '<span class="ok">Accepted</span>' : `<button class="btn sm" data-act="accept" data-id="${a.offer.id}">Accept offer</button>`}</div>` : ""}
  </article>`).join("") : '<div class="empty">You haven’t applied anywhere yet. Open Job drives to see where you’re eligible.</div>'}`;
};

V.profile = async () => {
  const s = await api("GET", "/students/me");
  const fields = [["Full name", s.full_name], ["USN", s.usn], ["Email", s.email], ["Branch", s.branch], ["CGPA", s.cgpa],
    ["Active backlogs", s.active_backlogs], ["Cleared backlogs", s.cleared_backlogs], ["Offer accepted", s.has_accepted_offer ? "Yes" : "No"]];
  $("#main").innerHTML = `<h1>Profile</h1><section class="card"><dl class="kv" style="grid-template-columns:repeat(auto-fit,minmax(200px,1fr))">${fields.map(([k, v]) => `<div><dt>${k}</dt><dd>${esc(v)}</dd></div>`).join("")}</dl>
  <p class="muted sm">The placement cell maintains your CGPA and backlog count. Contact them if something looks wrong.</p></section>`;
};

/* ---- placement officer ---- */
V.post = async () => {
  const companies = await api("GET", "/companies");
  const today = new Date().toISOString().slice(0, 10);
  $("#main").innerHTML = `<h1>Post a drive</h1><div class="split">
  <form id="pf" class="card form">
    <label>Company<select name="company_id">${companies.map(c => `<option value="${c.id}">${esc(c.name)}</option>`).join("")}</select></label>
    <label>Role<input name="role" maxlength="120" required></label>
    <label>Season<input name="season" value="${new Date().getFullYear()}" maxlength="20" required></label>
    <label>Drive date<input type="date" name="drive_date" min="${today}" required></label>
    <label>Minimum CGPA<input type="number" name="min_cgpa" step="0.01" min="0" max="10" value="6.0" required></label>
    <label>Maximum active backlogs<input type="number" name="max_backlogs" min="0" max="50" value="0" required></label>
    <fieldset><legend>Allowed branches</legend>${BRANCHES.map(b => `<label class="chk"><input type="checkbox" name="br" value="${b}">${b}</label>`).join("")}
      <p class="muted sm">Leave all unticked to open the drive to every branch.</p></fieldset>
    <button class="btn">Post drive</button>
  </form>
  <form id="cf" class="card"><h3>Company not listed?</h3><p class="muted sm" style="margin-bottom:1rem">Add it here, then pick it in the drive form.</p>
    <label>Company name<input name="name" maxlength="120" required></label>
    <label>Contact email<input type="email" name="email" maxlength="160" required></label>
    <button class="btn alt">Add company</button></form></div>`;
  $("#pf").onsubmit = e => {
    e.preventDefault();
    const f = new FormData(e.target), form = e.target;
    guard(async () => {
      await api("POST", "/jobs", { company_id: +f.get("company_id"), role: f.get("role"), season: f.get("season"), drive_date: f.get("drive_date"),
        min_cgpa: +f.get("min_cgpa"), max_backlogs: +f.get("max_backlogs"), is_open: true, branches: f.getAll("br") });
      toast("Drive posted");
      form.reset();
    });
  };
  $("#cf").onsubmit = e => {
    e.preventDefault();
    const f = new FormData(e.target);
    guard(async () => { await api("POST", "/companies", { name: f.get("name"), email: f.get("email") }); toast("Company added"); await route(); });
  };
};

const ivCell = a => a.interviews.length ? a.interviews.map(i => `<div class="iv"><span>Round ${i.round_no}: ${fmtT(i.scheduled_at)}, ${esc(i.venue)}</span>
  ${i.passed === true ? pill("ACCEPTED", "Passed") : i.passed === false ? pill("REJECTED", "Not cleared")
    : a.status === "SHORTLISTED" ? `<span class="acts"><button class="btn alt sm" data-act="result" data-id="${i.id}" data-v="true">Passed</button><button class="btn alt sm bad" data-act="result" data-id="${i.id}" data-v="false">Not cleared</button></span>` : ""}</div>`).join("")
  : '<span class="muted">None yet</span>';

const actions = a => {
  const reject = `<button class="btn alt sm bad" data-act="status" data-id="${a.id}" data-v="REJECTED">Reject</button>`;
  const next = Math.max(0, ...a.interviews.map(i => i.round_no)) + 1;
  switch (a.status) {
    case "APPLIED": return `<button class="btn sm" data-act="status" data-id="${a.id}" data-v="SHORTLISTED">Shortlist</button>${reject}`;
    case "SHORTLISTED": return `<button class="btn alt sm" data-act="schedule" data-id="${a.id}" data-next="${next}">Schedule interview</button>
      <input id="pk${a.id}" type="number" step="0.1" min="0" placeholder="LPA" aria-label="Package in LPA"><button class="btn sm" data-act="offer" data-id="${a.id}">Issue offer</button>${reject}`;
    case "OFFERED": return `<span class="muted">Waiting for ${a.offer ? lpa(a.offer.package_lpa) : "the"} response</span>`;
    case "ACCEPTED": return `<span class="ok">Accepted${a.offer ? ", " + lpa(a.offer.package_lpa) : ""}</span>`;
    default: return '<span class="muted">Closed</span>';
  }
};

V.applicants = async () => {
  const jobs = await api("GET", "/jobs");
  if (!jobs.length) { $("#main").innerHTML = '<h1>Applicants and offers</h1><div class="empty">No drives yet. Post a drive to start receiving applications.</div>'; return; }
  if (!jobs.some(j => j.id === curJob)) curJob = (jobs.find(j => j.applicants > 0) || jobs[0]).id;
  const job = jobs.find(j => j.id === curJob);
  const rows = await api("GET", `/jobs/${curJob}/applicants`);
  const n = s => rows.filter(r => r.status === s).length;
  $("#main").innerHTML = `<h1>Applicants and offers</h1>
  <div class="top" style="margin-bottom:1rem"><label class="chk">Drive <select id="jsel" style="margin:0 0 0 .5rem;width:auto;max-width:70vw">${jobs.map(j => `<option value="${j.id}" ${j.id === curJob ? "selected" : ""}>${esc(j.company)}, ${esc(j.role)}</option>`).join("")}</select></label>
    <div class="acts">${pill(job.is_open ? "OPEN" : "CLOSED", job.is_open ? "Applications open" : "Applications closed")}
    <button class="btn alt sm" data-act="toggle" data-id="${job.id}" data-v="${!job.is_open}">${job.is_open ? "Close applications" : "Reopen applications"}</button></div></div>
  <p class="muted" style="margin-bottom:1rem">${plural(rows.length, "applicant")}, ${n("SHORTLISTED")} shortlisted, ${n("OFFERED") + n("ACCEPTED")} with offers. Minimum CGPA ${job.min_cgpa}, up to ${plural(job.max_backlogs, "active backlog")}, ${job.branches.length ? job.branches.join(", ") : "all branches"}.</p>
  ${rows.length ? `<div class="scroll"><table><thead><tr><th>Student</th><th>Branch</th><th>CGPA</th><th>Status</th><th>Interviews</th><th>Action</th></tr></thead><tbody>
    ${rows.map(a => `<tr><td><b>${esc(a.student.full_name)}</b><div class="muted sm">${esc(a.student.usn)}</div></td><td>${a.student.branch}</td><td>${a.student.cgpa}</td><td>${pill(a.status)}</td><td>${ivCell(a)}</td><td><div class="acts">${actions(a)}</div></td></tr>`).join("")}
  </tbody></table></div>` : '<div class="empty">Nobody has applied to this drive yet.</div>'}`;
  $("#jsel").onchange = e => { curJob = +e.target.value; route(); };
};

V.reports = async () => {
  const s = await api("GET", "/stats");
  const money = v => v == null ? "None yet" : lpa(v);
  $("#main").innerHTML = `<h1>Placement reports</h1>
  <div class="stats">
    <div class="card"><b>${s.placed}</b><span>Students placed</span></div>
    <div class="card"><b>${s.placement_rate}%</b><span>of ${s.students} students placed</span></div>
    <div class="card"><b>${s.offers}</b><span>Offers issued</span></div>
    <div class="card"><b>${s.applications}</b><span>Applications</span></div>
  </div>
  <div class="stats" style="grid-template-columns:repeat(auto-fit,minmax(220px,1fr))">
    <div class="card"><b style="font-size:1.3rem">${money(s.highest_package)}</b><span>Highest package offered</span></div>
    <div class="card"><b style="font-size:1.3rem">${money(s.average_package)}</b><span>Average package offered</span></div>
  </div>
  <div class="scroll"><table><thead><tr><th>Branch</th><th>Students</th><th>Placed</th><th>Placement rate</th></tr></thead><tbody>
  ${s.by_branch.map(b => { const r = b.students ? Math.round(100 * b.placed / b.students) : 0; return `<tr><td><b>${b.branch}</b></td><td>${b.students}</td><td>${b.placed}</td><td><div class="acts"><div class="bar" role="img" aria-label="${r}% placed"><i style="width:${r}%"></i></div>${r}%</div></td></tr>`; }).join("")}
  </tbody></table></div>`;
};

/* ---------------------------------------------------------------- shell, login, routing */
function shell(r) {
  const u = session.user;
  $("#app").innerHTML = `<header><div class="brand"><i></i>TalentHub</div>
    <nav aria-label="Main">${ROUTES[u.role].map(([k, t]) => `<a href="#${k}" class="${k === r ? "on" : ""}" ${k === r ? 'aria-current="page"' : ""}>${t}</a>`).join("")}</nav>
    <div class="who"><span>${esc(u.name)}</span><button class="link" data-act="out">Sign out</button></div></header>
    <main id="main"><p class="muted">Loading…</p></main>`;
}

function loginView() {
  let role = "student";
  const demo = { student: ["1RV22CS101", "student123"], officer: ["placement@college.edu", "officer123"] };
  $("#app").innerHTML = `<div class="login"><aside><div class="brand light"><i></i>TalentHub</div><h1>Your placement season, in one place.</h1>
    <ol class="path"><li>Check where you’re eligible</li><li>Apply to drives</li><li>Get shortlisted and interview</li><li>Accept your offer</li></ol></aside>
    <form id="lf"><h2>Sign in</h2>
    <div class="seg" role="group" aria-label="Sign in as"><button type="button" class="on" data-r="student">Student</button><button type="button" data-r="officer">Placement officer</button></div>
    ${loginNote ? `<p class="note" role="status">${esc(loginNote)}</p>` : ""}
    <label id="idl">USN or email<input id="idn" autocomplete="username" required></label>
    <label>Password<input id="pw" type="password" autocomplete="current-password" required></label>
    <p id="err" class="err" role="alert"></p><button class="btn" style="width:100%">Sign in</button>
    <p class="muted sm" style="margin-top:1rem">Demo accounts are filled in for you. Student: 1RV22CS101 / student123. Officer: placement@college.edu / officer123.</p></form></div>`;
  const fill = () => { $("#idn").value = demo[role][0]; $("#pw").value = demo[role][1]; $("#idl").firstChild.textContent = role === "student" ? "USN or email" : "Email"; };
  fill();
  document.querySelectorAll(".seg button").forEach(b => b.onclick = () => {
    role = b.dataset.r;
    document.querySelectorAll(".seg button").forEach(x => x.classList.toggle("on", x === b));
    fill();
  });
  $("#lf").onsubmit = async e => {
    e.preventDefault(); $("#err").textContent = "";
    const btn = e.target.querySelector(".btn"); btn.disabled = true;
    try {
      session = await api("POST", "/auth/login", { role, identifier: $("#idn").value, password: $("#pw").value });
      try { localStorage.setItem(KEY, JSON.stringify(session)); } catch (x) { /* ignore */ }
      loginNote = ""; location.hash = ""; route();
    } catch (err) { $("#err").textContent = err.message; btn.disabled = false; }
  };
}

async function route() {
  if (!session) return loginView();
  const list = ROUTES[session.user.role];
  const r = (list.find(x => x[0] === location.hash.slice(1)) || list[0])[0];
  shell(r);
  try { await V[r](); } catch (e) { if (e.message !== "Signed out") $("#main").innerHTML = `<div class="empty">${esc(e.message)}</div>`; }
}

function openSchedule(appId, nextRound) {
  const dlg = $("#dlg");
  dlg.innerHTML = `<form id="sf"><h3>Schedule interview</h3>
    <label>Round<input type="number" name="round_no" min="1" max="20" value="${nextRound}" required></label>
    <label>Date and time<input type="datetime-local" name="when" required></label>
    <label>Venue<input name="venue" maxlength="160" placeholder="Room, hall or meeting link" required></label>
    <p id="derr" class="err" role="alert"></p>
    <div class="acts end"><button type="button" class="btn alt" data-act="closedlg">Cancel</button><button class="btn">Schedule</button></div></form>`;
  dlg.showModal ? dlg.showModal() : dlg.setAttribute("open", "");
  $("#sf").onsubmit = async e => {
    e.preventDefault();
    const f = new FormData(e.target);
    try {
      await api("POST", `/applications/${appId}/interviews`, { round_no: +f.get("round_no"), scheduled_at: f.get("when"), venue: f.get("venue") });
      closeDialog(); toast("Interview scheduled"); await route();
    } catch (err) { $("#derr").textContent = err.message; }
  };
}
function closeDialog() { const d = $("#dlg"); d.close ? d.close() : d.removeAttribute("open"); }

document.addEventListener("click", e => {
  const b = e.target.closest("[data-act]");
  if (!b) return;
  const act = b.dataset.act, id = +b.dataset.id;
  if (act === "out") return signOut();
  if (act === "closedlg") return closeDialog();
  if (act === "schedule") return openSchedule(id, +b.dataset.next);
  guard(async () => {
    if (act === "apply") { await api("POST", "/applications", { job_id: id }); toast("Application sent"); }
    if (act === "accept") { await api("POST", `/offers/${id}/accept`); toast("Offer accepted. Congratulations!"); }
    if (act === "status") { await api("PATCH", `/applications/${id}`, { status: b.dataset.v }); toast(b.dataset.v === "SHORTLISTED" ? "Student shortlisted" : "Application rejected"); }
    if (act === "result") { await api("PATCH", `/interviews/${id}`, { passed: b.dataset.v === "true" }); toast("Result recorded"); }
    if (act === "toggle") { await api("PATCH", `/jobs/${id}`, { is_open: b.dataset.v === "true" }); toast(b.dataset.v === "true" ? "Applications reopened" : "Applications closed"); }
    if (act === "offer") {
      const v = parseFloat($("#pk" + id).value);
      if (!(v > 0)) throw new Error("Enter the package in LPA");
      await api("POST", `/applications/${id}/offer`, { package_lpa: v }); toast("Offer issued");
    }
    await route();
  });
});
window.addEventListener("hashchange", route);
route();
