# TalentHub

A campus placement management website. Students check eligibility, apply to drives, follow their
interviews and accept offers. The placement cell posts drives, shortlists applicants, schedules
interviews, issues offers and reads placement statistics.

Built from the Team 10 lab documents: FastAPI + SQLAlchemy + SQLite, with the router → service →
repository → model layering from the TalentHub scenario, and the final 3NF schema from Part D.

## Run it

Requires Python 3.10+.

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python run.py
```

Open **http://127.0.0.1:8000**. The database file `talenthub.db` is created on first start and filled
with demo data. API docs (Swagger) are at **/docs**.

| Role | Sign in with | Password |
| --- | --- | --- |
| Student | `1RV22CS101` (USN) or `rahul@college.edu` | `student123` |
| Placement officer | `placement@college.edu` | `officer123` |

Other demo students: `1RV22IS045` Asha, `1RV22CS118` Sneha (has a pending 12 LPA offer to accept),
`1RV22EC088` Meera (already placed). All use `student123`.

To start with an empty database: delete `talenthub.db` and run `TALENTHUB_SEED=0 python run.py`
(you then need to insert students and an officer yourself).

## What's in it

**Student:** Login, Dashboard, Job Drives (with the reason when you are not eligible), My Applications
(progress tracker, interviews, accept offer), Profile.

**Placement officer:** Login, Post a Drive (and add a company), Applicants and Offers (shortlist, reject,
schedule interviews, record results, issue offers, close or reopen a drive), Reports (students placed,
placement rate, highest and average package, branch-wise table).

### Business rules (all enforced in `app/services.py`)

- Eligibility: drive open, no accepted offer yet, CGPA ≥ minimum, active backlogs ≤ maximum, branch allowed.
  A drive with no allowed branches is open to every branch (the rule recorded in Part B).
- A student can apply to a drive only once. Eligibility is checked at the time of applying.
- Status flow: Applied → Shortlisted → Offered → Accepted, or Rejected from Applied or Shortlisted.
- Interviews and offers only exist for shortlisted students; one slot per round per application; one offer per application.
- Accepting an offer updates the offer, the application status and `students.has_accepted_offer` in
  **one transaction** (3NF Step 8). An accepted student cannot apply again or receive another offer.

### Database

The seven tables of the final schema (Part D) with every key and constraint: composite key
`(job_id, branch)`, `UNIQUE(student_id, job_id)`, `UNIQUE(application_id, round_no)`, unique
`offers.application_id`, unique `usn` and `email`, enums for branch and status, and CHECK constraints
for CGPA, backlogs, round number and package. Foreign keys are switched on for every SQLite
connection (`PRAGMA foreign_keys=ON`), which SQLite does not do by default.

Two additions the documents did not cover, needed for login: table `placement_officers`, and column
`students.password_hash`. Passwords are stored as salted PBKDF2 hashes.

## Project layout

```
app/
  main.py            app setup, error handlers, serves the website
  routers/           HTTP only: auth, students, companies, jobs, applications, stats
  services.py        business rules and transactions
  repositories.py    all database queries
  models.py          SQLAlchemy tables and enums
  schemas.py         request and response shapes (Pydantic)
  deps.py            sign-in and role checks (JWT)
  security.py        password hashing, tokens
  seed.py            demo data
static/              the website (index.html, css/styles.css, js/app.js), plain HTML/CSS/JS
tests/               22 API tests (pytest) and a browser-level test (tests/e2e)
```

## API

All paths are under `/api`. Everything except login needs `Authorization: Bearer <token>`.

| Method and path | Who | Purpose |
| --- | --- | --- |
| `POST /auth/login` | anyone | `{role, identifier, password}` → `{token, user}` |
| `GET /students/me` | student | own profile |
| `GET /jobs` | both | students get `reason` and `applied`; officers get `applicants` |
| `POST /jobs`, `PATCH /jobs/{id}` | officer | post a drive; open or close it |
| `GET /jobs/{id}/applicants` | officer | applicants with interviews and offers |
| `GET /companies`, `POST /companies` | both / officer | list, add |
| `POST /applications`, `GET /applications/me` | student | apply, list own |
| `PATCH /applications/{id}` | officer | `{status: SHORTLISTED or REJECTED}` |
| `POST /applications/{id}/interviews` | officer | `{round_no, scheduled_at, venue}` |
| `PATCH /interviews/{id}` | officer | `{passed, notes}` |
| `POST /applications/{id}/offer` | officer | `{package_lpa}` |
| `POST /offers/{id}/accept` | student | accept own offer |
| `GET /stats` | officer | placement statistics |

Errors come back as `{"detail": "message"}` with 401, 403, 404, 409 (conflict) or 422 (invalid or not eligible).

## Tests

```bash
python -m pytest                       # 22 API tests on a throwaway SQLite database
cd tests/e2e && npm install && node e2e.js   # clicks through the real pages (server running on :8000, fresh DB)
```

## Configuration

Environment variables: `TALENTHUB_DB_URL` (default: SQLite file in the project folder),
`TALENTHUB_SECRET` (JWT signing key), `TALENTHUB_TOKEN_HOURS` (default 8), `TALENTHUB_SEED` (`0` to skip demo data).

Before any real deployment: set a long random `TALENTHUB_SECRET`, serve over HTTPS, and remove the
pre-filled demo credentials from the sign-in screen (`loginView` in `static/js/app.js`).

## Not included

- Offer letter files: `offer_letter_key` is generated as an identifier, but no PDF is produced or stored.
- Creating student accounts or editing CGPA and backlogs from the UI. The documents don't describe a screen for it, so students come from the seed (or add rows to the `students` table).
- A separate company login. The scenario lists a Company role, but the final UI list only has student and placement officer, so the officer acts for companies.
