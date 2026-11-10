// Browser-level smoke test: drives the real pages against a running server (fresh database).
// Usage:  cd tests/e2e && npm install && node e2e.js      (server on :8000, or set BASE_URL)
const { JSDOM } = require("jsdom");
const BASE = process.env.BASE_URL || "http://127.0.0.1:8000";
let pass = 0, fail = 0;
const ok = (c, m) => { c ? pass++ : (fail++, console.log("  FAIL:", m)); if (c) console.log("  ok  :", m); };
const sleep = ms => new Promise(r => setTimeout(r, ms));

async function open() {
  const errors = [];
  const html = (await (await fetch(BASE + "/")).text()).replace(/<script src[^>]*><\/script>/, "").replace(/<link[^>]*>/g, "");
  const js = await (await fetch(BASE + "/js/app.js")).text();
  const dom = new JSDOM(html, { url: BASE + "/", runScripts: "outside-only", pretendToBeVisual: true });
  dom.window.fetch = (u, o) => fetch(new URL(u, BASE), o);
  dom.window.addEventListener("error", e => errors.push(e.message));
  dom.window.eval(js);
  dom.errors = errors;
  return dom;
}
const until = async (fn, what, ms = 4000) => { const t = Date.now(); while (Date.now() - t < ms) { try { if (fn()) return true; } catch (e) {} await sleep(40); } console.log("  TIMEOUT waiting for:", what); return false; };
const txt = d => d.window.document.body.textContent.replace(/\s+/g, " ");
const click = (d, sel, nth = 0) => d.window.document.querySelectorAll(sel)[nth].click();
const route = (d, h) => { d.window.location.hash = h; };
const submit = (d, sel) => d.window.document.querySelector(sel).dispatchEvent(new d.window.Event("submit", { cancelable: true, bubbles: true }));
const setv = (d, sel, v) => { const e = d.window.document.querySelector(sel); e.value = v; };

(async () => {
  /* ============ STUDENT: Rahul ============ */
  console.log("\n[Student journey: Rahul]");
  let d = await open();
  ok(await until(() => d.window.document.querySelector("#lf"), "login form"), "login form renders");
  ok(txt(d).includes("Your placement season, in one place."), "login hero text");
  setv(d, "#pw", "wrong"); submit(d, "#lf");
  ok(await until(() => d.window.document.querySelector("#err").textContent.includes("Incorrect"), "error"), "wrong password shows an error");
  setv(d, "#pw", "student123"); submit(d, "#lf");
  ok(await until(() => txt(d).includes("Hi, Rahul"), "dashboard"), "signs in and shows dashboard greeting");
  ok(await until(() => txt(d).includes("Seminar Hall B"), "interview"), "dashboard lists the upcoming interview");
  const nums = [...d.window.document.querySelectorAll(".stats .card b")].map(b => b.textContent);
  ok(nums.join(",") === "1,2,1,0", `dashboard stats are 1 open, 2 applications, 1 shortlisted, 0 offers (got ${nums})`);

  route(d, "drives");
  ok(await until(() => d.window.document.querySelectorAll(".grid .card").length === 7, "7 drives"), "drives page lists all 7 drives");
  ok(txt(d).includes("Requires a CGPA of 8.5 or above"), "ineligible drive explains CGPA reason");
  ok(txt(d).includes("Open to ECE, MECH only"), "ineligible drive explains branch reason");
  ok(txt(d).includes("Applications for this drive are closed"), "closed drive explained");
  ok(d.window.document.querySelectorAll('[data-act="apply"]').length === 1, "only one Apply button (the one drive he is eligible for)");
  click(d, "#only"); d.window.document.querySelector("#only").dispatchEvent(new d.window.Event("change"));
  ok(await until(() => d.window.document.querySelectorAll(".grid .card").length === 1, "filter"), "'Only drives I can apply to' filters to 1");
  click(d, '[data-act="apply"]');
  ok(await until(() => d.window.document.querySelector("#toast").textContent === "Application sent", "toast"), "Apply shows 'Application sent'");
  ok(await until(() => d.window.document.querySelectorAll('[data-act="apply"]').length === 0, "no apply"), "Apply button disappears after applying");

  route(d, "apps");
  ok(await until(() => d.window.document.querySelectorAll(".app").length === 3, "3 apps"), "My applications shows 3 applications (2 seeded + the one just sent)");
  ok(txt(d).includes("Programmer Analyst") && txt(d).includes("Round 1"), "new application and interview round visible");
  ok(d.window.document.querySelector(".steps") !== null, "progress stepper rendered");

  route(d, "profile");
  ok(await until(() => txt(d).includes("1RV22CS101"), "profile"), "profile shows USN");
  ok(txt(d).includes("8.2") && txt(d).includes("CSE"), "profile shows CGPA and branch");
  ok(d.errors.length === 0, "no JavaScript errors in student session " + d.errors.join("|"));
  click(d, '[data-act="out"]');
  ok(await until(() => d.window.document.querySelector("#lf"), "back to login"), "sign out returns to login");
  d.window.close();

  /* ============ OFFICER ============ */
  console.log("\n[Officer journey]");
  d = await open();
  await until(() => d.window.document.querySelector("#lf"), "login");
  click(d, '.seg button[data-r="officer"]');
  ok(d.window.document.querySelector("#idn").value === "placement@college.edu", "officer tab fills officer email");
  submit(d, "#lf");
  ok(await until(() => txt(d).includes("Post a drive"), "officer home"), "officer lands on Post a drive");
  ok(!txt(d).includes("My applications"), "officer does not see student navigation");

  // post a drive + add company
  setv(d, '#cf [name="name"]', "Zoho"); setv(d, '#cf [name="email"]', "hr@zoho.example"); submit(d, "#cf");
  ok(await until(() => [...d.window.document.querySelectorAll('#pf option')].some(o => o.textContent === "Zoho"), "zoho"), "new company appears in the company list");
  const sel = d.window.document.querySelector('#pf [name="company_id"]');
  sel.value = [...sel.options].find(o => o.textContent === "Zoho").value;
  setv(d, '#pf [name="role"]', "Backend Engineer");
  const dt = new Date(Date.now() + 15 * 864e5).toISOString().slice(0, 10);
  setv(d, '#pf [name="drive_date"]', dt); setv(d, '#pf [name="min_cgpa"]', "7.5"); setv(d, '#pf [name="max_backlogs"]', "1");
  d.window.document.querySelector('#pf [value="CSE"]').checked = true;
  submit(d, "#pf");
  ok(await until(() => d.window.document.querySelector("#toast").textContent === "Drive posted", "posted"), "drive is posted");

  // applicants
  route(d, "applicants");
  ok(await until(() => d.window.document.querySelectorAll("tbody tr").length === 3, "3 rows"), "applicants table loads (Infosys drive, 3 applicants)");
  ok(txt(d).includes("Asha Patil") && txt(d).includes("Ravi Menon") && txt(d).includes("Rahul Kumar"), "all three applicants listed");
  const rows = () => [...d.window.document.querySelectorAll("tbody tr")];
  const ashaRow = () => rows().find(r => r.textContent.includes("Asha Patil"));
  ashaRow().querySelector('[data-v="SHORTLISTED"]').click();
  ok(await until(() => ashaRow().textContent.includes("Shortlisted"), "shortlisted"), "Shortlist moves Asha to Shortlisted");

  ashaRow().querySelector('[data-act="schedule"]').click();
  ok(await until(() => d.window.document.querySelector("#sf"), "dialog"), "Schedule interview dialog opens");
  ok(d.window.document.querySelector('#sf [name="round_no"]').value === "1", "next round number is pre-filled");
  setv(d, '#sf [name="when"]', "2030-01-15T10:30"); setv(d, '#sf [name="venue"]', "Hall C"); submit(d, "#sf");
  ok(await until(() => ashaRow().textContent.includes("Hall C"), "interview"), "interview appears in the table");
  ashaRow().querySelector('[data-act="result"][data-v="true"]').click();
  ok(await until(() => ashaRow().textContent.includes("Passed") && !ashaRow().querySelector('[data-act="result"]'), "result"), "Passed result recorded");

  d.window.document.querySelector(`#pk${ashaRow().querySelector('[data-act="offer"]').dataset.id}`).value = "";
  ashaRow().querySelector('[data-act="offer"]').click();
  ok(await until(() => d.window.document.querySelector("#toast").textContent.includes("package"), "validation"), "issuing an offer without a package shows a message");
  d.window.document.querySelector(`#pk${ashaRow().querySelector('[data-act="offer"]').dataset.id}`).value = "14.5";
  ashaRow().querySelector('[data-act="offer"]').click();
  ok(await until(() => ashaRow().textContent.includes("Offered") && ashaRow().textContent.includes("14.5 LPA"), "offered"), "offer of 14.5 LPA issued");

  rows().find(r => r.textContent.includes("Ravi Menon")).querySelector('[data-v="REJECTED"]').click();
  ok(await until(() => rows().find(r => r.textContent.includes("Ravi Menon")).textContent.includes("Closed"), "rejected"), "Reject closes Ravi's application");

  click(d, '[data-act="toggle"]');
  ok(await until(() => txt(d).includes("Applications closed"), "closed"), "drive can be closed");
  click(d, '[data-act="toggle"]');
  ok(await until(() => txt(d).includes("Applications open"), "reopened"), "drive can be reopened");

  route(d, "reports");
  ok(await until(() => txt(d).includes("Placement reports"), "reports"), "reports page renders");
  ok(txt(d).includes("Highest package offered") && txt(d).includes("14.5 LPA"), "package stats shown");
  ok(d.errors.length === 0, "no JavaScript errors in officer session " + d.errors.join("|"));
  d.window.close();

  /* ============ STUDENT accepts the offer ============ */
  console.log("\n[Student accepts offer: Asha]");
  d = await open();
  await until(() => d.window.document.querySelector("#lf"), "login");
  setv(d, "#idn", "asha@college.edu"); setv(d, "#pw", "student123"); submit(d, "#lf");
  ok(await until(() => txt(d).includes("Hi, Asha"), "dash"), "Asha signs in with her email");
  ok(await until(() => txt(d).includes("Offers waiting for you") && txt(d).includes("14.5 LPA"), "offer"), "dashboard shows the pending 14.5 LPA offer");
  click(d, '[data-act="accept"]');
  ok(await until(() => d.window.document.querySelector("#toast").textContent.includes("Offer accepted"), "accepted"), "offer is accepted");
  route(d, "profile");
  const accepted = () => [...d.window.document.querySelectorAll("dt")].find(x => x.textContent === "Offer accepted")?.nextElementSibling.textContent;
  ok(await until(() => accepted() === "Yes", "profile"), "profile now says Offer accepted: Yes (got " + accepted() + ")");
  route(d, "drives");
  ok(await until(() => txt(d).includes("You have already accepted an offer"), "blocked"), "every drive now explains she has accepted an offer");
  ok(d.window.document.querySelectorAll('[data-act="apply"]').length === 0, "no Apply buttons remain");
  d.window.close();

  console.log(`\n${pass} checks passed, ${fail} failed`);
  process.exit(fail ? 1 : 0);
})().catch(e => { console.error("CRASH", e); process.exit(2); });
