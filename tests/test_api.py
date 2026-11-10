from datetime import date, timedelta

from app.models import Branch, JobListing, Student
from app.services import eligibility_reason


def jobs_by_role(client, headers):
    return {j["role"]: j for j in client.get("/api/jobs", headers=headers).json()}


# ------------------------------------------------------------------ auth
def test_student_login_by_usn_and_email(client):
    for ident in ("1RV22CS101", "1rv22cs101", "rahul@college.edu"):
        r = client.post("/api/auth/login", json={"role": "student", "identifier": ident, "password": "student123"})
        assert r.status_code == 200
        assert r.json()["user"] == {"id": 1, "role": "student", "name": "Rahul Kumar"}


def test_bad_credentials_rejected(client):
    for body in ({"role": "student", "identifier": "1RV22CS101", "password": "wrong"},
                 {"role": "student", "identifier": "nobody", "password": "x"},
                 {"role": "officer", "identifier": "placement@college.edu", "password": "student123"}):
        assert client.post("/api/auth/login", json=body).status_code == 401


def test_student_cannot_use_officer_login_and_vice_versa(client):
    r = client.post("/api/auth/login", json={"role": "officer", "identifier": "1RV22CS101", "password": "student123"})
    assert r.status_code == 401


def test_protected_routes_need_a_valid_token(client):
    assert client.get("/api/jobs").status_code == 401
    assert client.get("/api/jobs", headers={"Authorization": "Bearer garbage"}).status_code == 401


def test_roles_are_enforced(client, rahul, officer):
    assert client.get("/api/stats", headers=rahul).status_code == 403
    assert client.post("/api/applications", json={"job_id": 1}, headers=officer).status_code == 403
    assert client.get("/api/students/me", headers=officer).status_code == 403
    assert client.patch("/api/applications/1", json={"status": "SHORTLISTED"}, headers=rahul).status_code == 403


def test_profile_hides_password(client, rahul):
    body = client.get("/api/students/me", headers=rahul).json()
    assert body["usn"] == "1RV22CS101" and body["cgpa"] == 8.2
    assert "password_hash" not in body


# ------------------------------------------------------------------ eligibility
def test_job_list_explains_eligibility(client, rahul):
    jobs = jobs_by_role(client, rahul)
    assert jobs["Software Developer"]["reason"] is None and jobs["Software Developer"]["applied"] is True
    assert jobs["Digital Graduate"]["reason"] == "Requires a CGPA of 8.5 or above"
    assert jobs["Embedded Engineer"]["reason"] == "Open to ECE, MECH only"
    assert jobs["Project Engineer"]["reason"] == "Applications for this drive are closed"
    assert jobs["Systems Engineer"]["branches"] == []          # empty list = all branches


def test_backlog_and_cgpa_boundaries():
    # Rahul-like student: 1 active backlog. A job allowing 0 rejects him on backlogs once CGPA passes.
    job = JobListing(company_id=1, role="Strict", season="2026", min_cgpa=7, max_backlogs=0,
                     drive_date=date.today(), is_open=True)
    s = Student(branch=Branch.CSE, cgpa=8.2, active_backlogs=1, has_accepted_offer=False)
    assert eligibility_reason(s, job) == "Allows at most 0 active backlogs"
    job.max_backlogs = 1
    assert eligibility_reason(s, job) is None                  # boundary: equal is allowed
    s.cgpa = 7.0; job.min_cgpa = 7.0
    assert eligibility_reason(s, job) is None                  # boundary: equal is allowed
    s.cgpa = 6.99
    assert eligibility_reason(s, job).startswith("Requires a CGPA")


def test_rahul_has_an_open_drive_to_apply_to(client, rahul):
    jobs = jobs_by_role(client, rahul)
    open_for_rahul = [r for r, j in jobs.items() if j["reason"] is None and not j["applied"]]
    assert open_for_rahul == ["Programmer Analyst"]


def test_scenario_from_the_doc_rahul_applies_to_abc(client, rahul):
    # ABC: min CGPA 7.0, max 2 backlogs. Rahul: 8.2 and 1 backlog -> allowed.
    jobs = jobs_by_role(client, rahul)
    assert jobs["Software Developer"]["company"] == "ABC Technologies"
    assert jobs["Software Developer"]["min_cgpa"] == 7.0 and jobs["Software Developer"]["max_backlogs"] == 2


# ------------------------------------------------------------------ applying
def test_apply_success_duplicate_and_ineligible(client, login):
    asha = login("1RV22IS045")
    r = client.post("/api/applications", json={"job_id": 4}, headers=asha)       # ISE not allowed for Bosch
    assert r.status_code == 422 and r.json()["detail"] == "Open to ECE, MECH only"
    r = client.post("/api/applications", json={"job_id": 3}, headers=asha)       # TCS: ok
    assert r.status_code == 201 and r.json()["status"] == "APPLIED"
    assert r.json()["job"]["company"] == "TCS"
    r = client.post("/api/applications", json={"job_id": 3}, headers=asha)
    assert r.status_code == 409
    assert client.post("/api/applications", json={"job_id": 999}, headers=asha).status_code == 404
    assert client.post("/api/applications", json={"job_id": 5}, headers=asha).status_code == 422  # closed


def test_my_applications_only_shows_own(client, rahul):
    apps = client.get("/api/applications/me", headers=rahul).json()
    assert {a["job"]["role"] for a in apps} == {"Systems Engineer", "Software Developer"}
    shortlisted = next(a for a in apps if a["status"] == "SHORTLISTED")
    assert shortlisted["interviews"][0]["round_no"] == 1


# ------------------------------------------------------------------ officer workflow
def test_post_drive_validation_and_branches(client, officer, rahul):
    payload = {"company_id": 1, "role": "QA Engineer", "season": "2026", "min_cgpa": 7.5, "max_backlogs": 1,
               "drive_date": str(date.today() + timedelta(days=9)), "branches": ["ECE", "CSE", "CSE"]}
    r = client.post("/api/jobs", json=payload, headers=officer)
    assert r.status_code == 201 and r.json()["branches"] == ["CSE", "ECE"]      # de-duplicated, ordered
    assert client.post("/api/jobs", json={**payload, "min_cgpa": 11}, headers=officer).status_code == 422
    assert client.post("/api/jobs", json={**payload, "company_id": 99}, headers=officer).status_code == 404
    assert client.post("/api/jobs", json={**payload, "branches": ["BIO"]}, headers=officer).status_code == 422
    assert "QA Engineer" in jobs_by_role(client, rahul)


def test_close_and_reopen_drive(client, officer, rahul):
    assert client.patch("/api/jobs/2", json={"is_open": False}, headers=officer).json()["is_open"] is False
    assert jobs_by_role(client, rahul)["Systems Engineer"]["reason"] == "Applications for this drive are closed"
    client.patch("/api/jobs/2", json={"is_open": True}, headers=officer)
    assert jobs_by_role(client, rahul)["Systems Engineer"]["reason"] is None


def test_applicants_list_for_officer(client, officer):
    rows = client.get("/api/jobs/2/applicants", headers=officer).json()
    assert [r["student"]["usn"] for r in rows] == ["1RV22CS101", "1RV22IS045", "1RV22EC072"]
    assert client.get("/api/jobs/999/applicants", headers=officer).status_code == 404
    counts = {j["id"]: j["applicants"] for j in client.get("/api/jobs", headers=officer).json()}
    assert counts[2] == 3


def test_full_journey_apply_shortlist_interview_offer_accept(client, officer, login):
    sneha = login("1RV22CS118")
    app_id = client.post("/api/applications", json={"job_id": 2}, headers=sneha).json()["id"]

    # cannot jump straight to an offer
    assert client.post(f"/api/applications/{app_id}/offer", json={"package_lpa": 9}, headers=officer).status_code == 409
    assert client.post(f"/api/applications/{app_id}/interviews", headers=officer,
                       json={"round_no": 1, "scheduled_at": "2026-12-01T10:00", "venue": "Hall A"}).status_code == 409

    assert client.patch(f"/api/applications/{app_id}", json={"status": "SHORTLISTED"}, headers=officer).status_code == 200
    assert client.patch(f"/api/applications/{app_id}", json={"status": "SHORTLISTED"}, headers=officer).status_code == 409

    iv = {"round_no": 1, "scheduled_at": "2026-12-01T10:00", "venue": "Hall A"}
    r = client.post(f"/api/applications/{app_id}/interviews", json=iv, headers=officer)
    assert r.status_code == 201
    assert client.post(f"/api/applications/{app_id}/interviews", json=iv, headers=officer).status_code == 409  # UNIQUE(app, round)
    assert client.post(f"/api/applications/{app_id}/interviews", headers=officer,
                       json={**iv, "round_no": 0}).status_code == 422
    r = client.patch(f"/api/interviews/{r.json()['id']}", json={"passed": True, "notes": "Great"}, headers=officer)
    assert r.json()["passed"] is True

    assert client.post(f"/api/applications/{app_id}/offer", json={"package_lpa": 0}, headers=officer).status_code == 422
    r = client.post(f"/api/applications/{app_id}/offer", json={"package_lpa": 9.5}, headers=officer)
    assert r.status_code == 201 and r.json()["accepted"] is False
    offer_id = r.json()["id"]
    assert client.post(f"/api/applications/{app_id}/offer", json={"package_lpa": 9.5}, headers=officer).status_code == 409

    # another student cannot accept it
    assert client.post(f"/api/offers/{offer_id}/accept", headers=login("1RV22CS101")).status_code == 404

    r = client.post(f"/api/offers/{offer_id}/accept", headers=sneha)
    assert r.status_code == 200 and r.json()["accepted"] is True
    assert client.post(f"/api/offers/{offer_id}/accept", headers=sneha).status_code == 409

    # the three duplicated facts agree (offer, application status, student flag)
    mine = client.get("/api/applications/me", headers=sneha).json()
    assert next(a for a in mine if a["id"] == app_id)["status"] == "ACCEPTED"
    assert client.get("/api/students/me", headers=sneha).json()["has_accepted_offer"] is True
    # ...and an accepted student can no longer apply anywhere
    r = client.post("/api/applications", json={"job_id": 1}, headers=sneha)
    assert r.status_code in (409, 422)
    assert jobs_by_role(client, sneha)["Digital Graduate"]["reason"] == "You have already accepted an offer"


def test_issued_offer_updates_package_report_before_acceptance(client, officer, login):
    # Package metrics include issued offers, not just accepted offers.
    student = login("1RV22CS118")
    app_id = client.post("/api/applications", json={"job_id": 2}, headers=student).json()["id"]
    client.patch(f"/api/applications/{app_id}", json={"status": "SHORTLISTED"}, headers=officer)
    response = client.post(f"/api/applications/{app_id}/offer", json={"package_lpa": 15}, headers=officer)
    assert response.status_code == 201, response.text
    stats = client.get("/api/stats", headers=officer).json()
    assert stats["highest_package"] == 15
    assert stats["placed"] == 1  # issuing an offer is not the same as accepting it


def test_offer_rechecks_branch_and_academic_eligibility(client, officer, login):
    from app.database import SessionLocal
    from app.models import Branch, Student
    student_headers = login("1RV22CS118")
    app_id = next(a["id"] for a in client.get("/api/applications/me", headers=student_headers).json()
                  if a["job"]["id"] == 3)
    client.patch(f"/api/applications/{app_id}", json={"status": "SHORTLISTED"}, headers=officer)
    with SessionLocal() as db:
        db.query(Student).filter(Student.usn == "1RV22CS118").update({"branch": Branch.MECH})
        db.commit()
    response = client.post(f"/api/applications/{app_id}/offer", json={"package_lpa": 12}, headers=officer)
    assert response.status_code == 422
    assert "restricted to" in response.json()["detail"]


def test_cannot_offer_student_who_already_accepted_elsewhere(client, officer, login):
    meera = login("1RV22EC088")                      # already ACCEPTED at Bosch in seed data
    app_id = client.post("/api/applications", json={"job_id": 2}, headers=meera)
    assert app_id.status_code == 422                 # blocked at apply time already


def test_reject_rules(client, officer):
    assert client.patch("/api/applications/2", json={"status": "REJECTED"}, headers=officer).status_code == 200
    assert client.patch("/api/applications/2", json={"status": "REJECTED"}, headers=officer).status_code == 409
    assert client.patch("/api/applications/6", json={"status": "REJECTED"}, headers=officer).status_code == 409  # accepted
    assert client.patch("/api/applications/2", json={"status": "OFFERED"}, headers=officer).status_code == 422
    assert client.patch("/api/applications/999", json={"status": "REJECTED"}, headers=officer).status_code == 404


def test_companies(client, officer, rahul):
    assert len(client.get("/api/companies", headers=rahul).json()) == 7
    r = client.post("/api/companies", json={"name": "Zoho", "email": "hr@zoho.example"}, headers=officer)
    assert r.status_code == 201
    assert client.post("/api/companies", json={"name": "zoho", "email": "hr@zoho.example"}, headers=officer).status_code == 409
    assert client.post("/api/companies", json={"name": "X", "email": "not-an-email"}, headers=officer).status_code == 422
    assert client.post("/api/companies", json={"name": "Y", "email": "a@b.example"}, headers=rahul).status_code == 403


# ------------------------------------------------------------------ reports
def test_stats(client, officer):
    s = client.get("/api/stats", headers=officer).json()
    assert s["students"] == 10 and s["applications"] == 9 and s["offers"] == 2 and s["placed"] == 1
    assert s["placement_rate"] == 10.0 and s["highest_package"] == 12.0 and s["average_package"] == 9.75
    ece = next(b for b in s["by_branch"] if b["branch"] == "ECE")
    assert ece == {"branch": "ECE", "students": 2, "placed": 1}
    assert [b["branch"] for b in s["by_branch"]] == ["CSE", "ISE", "ECE", "MECH", "CIVIL"]


# ------------------------------------------------------------------ database integrity
def test_database_constraints_are_real(client):
    import sqlalchemy.exc as exc
    from app.database import SessionLocal
    from app.models import Application, InterviewSlot, Offer
    import pytest
    with SessionLocal() as db:                       # duplicate application
        db.add(Application(student_id=1, job_id=2))
        with pytest.raises(exc.IntegrityError):
            db.commit()
    with SessionLocal() as db:                       # dangling foreign key
        db.add(Application(student_id=999, job_id=2))
        with pytest.raises(exc.IntegrityError):
            db.commit()
    with SessionLocal() as db:                       # one offer per application
        db.add(Offer(application_id=5, package_lpa=1, offer_letter_key="x"))
        with pytest.raises(exc.IntegrityError):
            db.commit()
    with SessionLocal() as db:                       # bad CGPA
        db.add(Student(usn="X", full_name="X", email="x@x.x", branch=Branch.CSE, cgpa=11,
                       active_backlogs=0, cleared_backlogs=0, password_hash="x"))
        with pytest.raises(exc.IntegrityError):
            db.commit()
    with SessionLocal() as db:                       # duplicate interview round
        from datetime import datetime
        db.add(InterviewSlot(application_id=1, round_no=1, scheduled_at=datetime.now(), venue="x"))
        with pytest.raises(exc.IntegrityError):
            db.commit()


def test_website_and_health_are_served(client):
    assert client.get("/api/health").json() == {"status": "ok"}
    assert client.get("/").status_code == 200
