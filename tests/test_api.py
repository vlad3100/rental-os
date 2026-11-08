from conftest import as_user


def test_requires_a_user(client):
    assert client.get("/api/inquiries").status_code == 401


def test_viewer_can_read_but_not_act(client):
    assert client.get("/api/inquiries", headers=as_user("ben")).status_code == 200
    assert client.post("/api/inquiries/INQ-002/process", headers=as_user("ben")).status_code == 403


def test_tenant_isolation(client):
    assert client.get("/api/inquiries/INQ-001", headers=as_user("clara")).status_code == 404
    ids = {i["inquiry_id"] for i in client.get("/api/inquiries", headers=as_user("clara")).json()}
    assert ids == {"INQ-201"}


def test_full_viewing_flow(client):
    anna = as_user("anna")
    out = client.post("/api/inquiries/INQ-001/process", headers=anna).json()
    assert out["workflow_state"] == "reply_human_review" and out["proposed_slot_ids"]
    draft_id = out["draft_id"]
    approved = client.post(f"/api/drafts/{draft_id}/approve", json={}, headers=anna)
    assert approved.status_code == 200 and approved.json()["status"] == "approved"
    assert client.post("/api/inquiries/INQ-001/mark-sent", headers=anna).json()["state"] == "viewing_proposed"
    slot = out["proposed_slot_ids"][0]
    booked = client.post("/api/inquiries/INQ-001/accept-slot", json={"slot_id": slot}, headers=anna)
    assert booked.json()["state"] == "viewing_confirmed"
    assert client.post("/api/inquiries/INQ-001/accept-slot", json={"slot_id": slot}, headers=anna).status_code == 409


def test_slot_not_proposed_cannot_be_booked(client):
    anna = as_user("anna")
    out = client.post("/api/inquiries/INQ-001/process", headers=anna).json()
    client.post(f"/api/drafts/{out['draft_id']}/approve", json={}, headers=anna)
    client.post("/api/inquiries/INQ-001/mark-sent", headers=anna)
    not_offered = client.post("/api/inquiries/INQ-001/accept-slot", json={"slot_id": "S-101-4"}, headers=anna)
    assert not_offered.status_code == 409


def test_human_edit_is_checked_and_override_is_audited(client):
    anna = as_user("anna")
    out = client.post("/api/inquiries/INQ-002/process", headers=anna).json()
    bad = out["response_text"].replace("4.350 €", "3.000 €")
    rejected = client.post(f"/api/drafts/{out['draft_id']}/approve", json={"final_text": bad}, headers=anna)
    assert rejected.status_code == 422
    assert any(f["code"] == "unsupported_number" for f in rejected.json()["findings"])
    ok = client.post(f"/api/drafts/{out['draft_id']}/approve",
                     json={"final_text": bad, "override_reason": "Owner lowered the deposit by phone today."},
                     headers=anna)
    assert ok.status_code == 200 and ok.json()["override_reason"]
    events = client.get("/api/audit", params={"entity_id": "INQ-002"}, headers=anna).json()
    assert any(e["event_type"] == "draft_approved" and e["payload"]["override"] for e in events)


def test_cannot_approve_twice_or_send_unapproved(client):
    anna = as_user("anna")
    out = client.post("/api/inquiries/INQ-003/process", headers=anna).json()
    assert client.post("/api/inquiries/INQ-003/mark-sent", headers=anna).status_code == 409
    client.post(f"/api/drafts/{out['draft_id']}/approve", json={}, headers=anna)
    assert client.post(f"/api/drafts/{out['draft_id']}/approve", json={}, headers=anna).status_code == 409


def test_manual_reply_for_human_case_and_no_reply_after_stop(client):
    anna = as_user("anna")
    client.post("/api/inquiries/INQ-011/process", headers=anna)  # complaint -> needs_human_review
    reply = client.post("/api/inquiries/INQ-011/manual-reply",
                        json={"text": "Guten Tag, entschuldigen Sie die späte Antwort. Viele Grüße"}, headers=anna)
    assert reply.status_code == 200 and reply.json()["author"] == "operator"
    client.post("/api/inquiries/INQ-004/process", headers=anna)  # stop request
    stop_reply = client.post("/api/inquiries/INQ-004/manual-reply", json={"text": "Hallo"}, headers=anna)
    assert stop_reply.status_code == 409


def test_deletion_endpoint_erases(client):
    anna = as_user("anna")
    deleted = client.post("/api/inquiries/INQ-012/delete-data", headers=anna)
    assert deleted.status_code == 200 and deleted.json()["message"] == "[erased]"
    detail = client.get("/api/inquiries/INQ-012", headers=anna).json()
    assert detail["inquiry"]["state"] == "data_deletion_requested"


def test_ingest_requires_existing_unit_of_own_org(client):
    anna = as_user("anna")
    created = client.post("/api/inquiries", json={"unit_id": "U-101", "message": "Ist die Wohnung noch frei?"},
                          headers=anna)
    assert created.status_code == 201 and created.json()["is_synthetic"] is True
    other_org = client.post("/api/inquiries", json={"unit_id": "U-201", "message": "Hallo"}, headers=anna)
    assert other_org.status_code == 404
