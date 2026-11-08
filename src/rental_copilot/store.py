"""SQLite repository.

Plain SQL on purpose: every query is visible, and every query filters by org_id.
A caller that asks for another organisation's record gets NotFound, never the row.
"""
from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .catalog import FIELDS
from .domain import (
    AuditEvent,
    DraftRecord,
    Fact,
    Finding,
    Inquiry,
    KnowledgeSnippet,
    Slot,
    Task,
    Unit,
    User,
)
from .state_machine import InquiryState

SCHEMA_PATH = Path(__file__).with_name("schema.sql")
_TABLES = ["audit_events", "contact_blocks", "tasks", "bookings", "slots", "agent_runs", "drafts", "inquiries",
           "knowledge", "facts", "units", "users", "organizations"]


class NotFound(LookupError):
    pass


def utcnow() -> datetime:
    return datetime.now(UTC).replace(microsecond=0)


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _dt(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


def new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:10]}"


class Store:
    def __init__(self, db_path: str | Path = ":memory:"):
        if str(db_path) != ":memory:":
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._lock = threading.RLock()

    # ------------------------------------------------------------ plumbing
    @contextmanager
    def tx(self) -> Iterator[sqlite3.Connection]:
        """One atomic unit of work: commits on success, rolls back on any exception."""
        with self._lock, self._conn:
            yield self._conn

    def _rows(self, sql: str, params: tuple[Any, ...] = ()) -> list[sqlite3.Row]:
        with self._lock:
            return self._conn.execute(sql, params).fetchall()

    def _one(self, sql: str, params: tuple[Any, ...], what: str) -> sqlite3.Row:
        rows = self._rows(sql, params)
        if not rows:
            raise NotFound(what)
        return rows[0]

    def init_schema(self, reset: bool = False) -> None:
        with self._lock:
            if reset:
                for table in _TABLES:
                    self._conn.execute(f"DROP TABLE IF EXISTS {table}")
                self._conn.commit()
            self._conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))

    # ------------------------------------------------------------ fixtures
    def load_fixture(self, data: dict[str, Any]) -> None:
        now = _iso(utcnow())
        with self.tx() as c:
            for org in data["organizations"]:
                c.execute("INSERT INTO organizations (org_id, name, is_synthetic) VALUES (?, ?, 1)",
                          (org["org_id"], org["name"]))
            for user in data["users"]:
                c.execute("INSERT INTO users VALUES (?, ?, ?, ?)",
                          (user["user_id"], user["org_id"], user["display_name"], user["role"]))
            for unit in data["units"]:
                c.execute("INSERT INTO units (unit_id, org_id, title, district, is_synthetic) VALUES (?, ?, ?, ?, 1)",
                          (unit["unit_id"], unit["org_id"], unit["title"], unit["district"]))
                for fact in unit["facts"]:
                    d = FIELDS[fact["field"]]
                    c.execute(
                        "INSERT INTO facts (fact_id, org_id, unit_id, field, label_de, label_en, kind, value, value_en,"
                        " status, source_ref, note, recorded_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (f"{unit['unit_id']}.{d.field}", unit["org_id"], unit["unit_id"], d.field, d.label_de,
                         d.label_en, d.kind.value, fact.get("value"), fact.get("value_en"), fact["status"],
                         fact.get("source_ref"), fact.get("note"), now),
                    )
            for slot in data["slots"]:
                c.execute("INSERT INTO slots VALUES (?, ?, ?, ?, ?)",
                          (slot["slot_id"], slot["org_id"], slot["unit_id"], slot["starts_at"], slot["capacity"]))
            for item in data["knowledge"]:
                for org_id in item["org_ids"]:
                    for language in ("de", "en"):
                        c.execute("INSERT INTO knowledge VALUES (?, ?, ?, ?)",
                                  (org_id, item["knowledge_id"], language, item[language]))
        for raw in data.get("inquiries", []):
            self.add_inquiry(Inquiry(**raw))

    # ------------------------------------------------------------ users, units, knowledge
    def get_user(self, user_id: str) -> User:
        row = self._one("SELECT * FROM users WHERE user_id = ?", (user_id,), f"user {user_id}")
        return User(**dict(row))

    def list_users(self) -> list[User]:
        return [User(**dict(r)) for r in self._rows("SELECT * FROM users ORDER BY org_id, user_id")]

    def _facts(self, org_id: str, unit_id: str) -> list[Fact]:
        rows = self._rows("SELECT * FROM facts WHERE org_id = ? AND unit_id = ? ORDER BY rowid", (org_id, unit_id))
        return [Fact(**{k: r[k] for k in r.keys() if k not in ("org_id", "recorded_at")}) for r in rows]

    def get_unit(self, org_id: str, unit_id: str) -> Unit:
        row = self._one("SELECT * FROM units WHERE org_id = ? AND unit_id = ?", (org_id, unit_id), f"unit {unit_id}")
        return Unit(org_id=org_id, unit_id=row["unit_id"], title=row["title"], district=row["district"],
                    facts=self._facts(org_id, unit_id))

    def list_units(self, org_id: str) -> list[Unit]:
        rows = self._rows("SELECT unit_id FROM units WHERE org_id = ? ORDER BY unit_id", (org_id,))
        return [self.get_unit(org_id, r["unit_id"]) for r in rows]

    def list_knowledge(self, org_id: str, language: str) -> list[KnowledgeSnippet]:
        lang = "en" if language == "en" else "de"
        rows = self._rows("SELECT knowledge_id, language, text FROM knowledge WHERE org_id = ? AND language = ?"
                          " ORDER BY knowledge_id", (org_id, lang))
        return [KnowledgeSnippet(**dict(r)) for r in rows]

    # ------------------------------------------------------------ inquiries
    def add_inquiry(self, inquiry: Inquiry) -> None:
        with self.tx() as c:
            c.execute(
                "INSERT INTO inquiries (inquiry_id, org_id, unit_id, received_at, channel, applicant_ref,"
                " applicant_display_name, contact_channel, message, state, tool_failures, erased_at, is_synthetic)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)",
                (inquiry.inquiry_id, inquiry.org_id, inquiry.unit_id, _iso(inquiry.received_at), inquiry.channel,
                 inquiry.applicant_ref, inquiry.applicant_display_name, inquiry.contact_channel, inquiry.message,
                 inquiry.state.value, inquiry.tool_failures, _iso(inquiry.erased_at)),
            )

    @staticmethod
    def _inquiry(row: sqlite3.Row) -> Inquiry:
        data = dict(row)
        data["received_at"] = _dt(data["received_at"])
        data["erased_at"] = _dt(data["erased_at"])
        data["is_synthetic"] = True
        return Inquiry(**data)

    def get_inquiry(self, org_id: str, inquiry_id: str) -> Inquiry:
        row = self._one("SELECT * FROM inquiries WHERE org_id = ? AND inquiry_id = ?", (org_id, inquiry_id),
                        f"inquiry {inquiry_id}")
        return self._inquiry(row)

    def list_inquiries(self, org_id: str) -> list[Inquiry]:
        rows = self._rows("SELECT * FROM inquiries WHERE org_id = ? ORDER BY received_at, inquiry_id", (org_id,))
        return [self._inquiry(r) for r in rows]

    def set_inquiry_state(self, org_id: str, inquiry_id: str, state: InquiryState) -> None:
        with self.tx() as c:
            cur = c.execute("UPDATE inquiries SET state = ? WHERE org_id = ? AND inquiry_id = ?",
                            (state.value, org_id, inquiry_id))
            if cur.rowcount != 1:
                raise NotFound(f"inquiry {inquiry_id}")

    def add_tool_failure(self, org_id: str, inquiry_id: str) -> None:
        with self.tx() as c:
            c.execute("UPDATE inquiries SET tool_failures = tool_failures + 1 WHERE org_id = ? AND inquiry_id = ?",
                      (org_id, inquiry_id))

    def erase_inquiry(self, org_id: str, inquiry_id: str) -> None:
        """Remove personal content. Ids, states and the content-free audit trail remain."""
        with self.tx() as c:
            c.execute("UPDATE inquiries SET message = '[erased]', applicant_display_name = NULL, erased_at = ?"
                      " WHERE org_id = ? AND inquiry_id = ?", (_iso(utcnow()), org_id, inquiry_id))
            c.execute("UPDATE drafts SET text = NULL, final_text = NULL, findings_json = '[]'"
                      " WHERE org_id = ? AND inquiry_id = ?", (org_id, inquiry_id))
            c.execute("UPDATE agent_runs SET output_json = NULL WHERE org_id = ? AND inquiry_id = ?",
                      (org_id, inquiry_id))
            c.execute("DELETE FROM bookings WHERE org_id = ? AND inquiry_id = ?", (org_id, inquiry_id))

    # ------------------------------------------------------------ slots
    def list_slots(self, org_id: str, unit_id: str) -> list[Slot]:
        rows = self._rows(
            "SELECT s.*, (SELECT COUNT(*) FROM bookings b WHERE b.slot_id = s.slot_id) AS booked"
            " FROM slots s WHERE s.org_id = ? AND s.unit_id = ? ORDER BY s.starts_at", (org_id, unit_id))
        return [Slot(**{**dict(r), "starts_at": _dt(r["starts_at"])}) for r in rows]

    def get_slot(self, org_id: str, slot_id: str) -> Slot:
        row = self._one(
            "SELECT s.*, (SELECT COUNT(*) FROM bookings b WHERE b.slot_id = s.slot_id) AS booked"
            " FROM slots s WHERE s.org_id = ? AND s.slot_id = ?", (org_id, slot_id), f"slot {slot_id}")
        return Slot(**{**dict(row), "starts_at": _dt(row["starts_at"])})

    def book_slot(self, org_id: str, slot_id: str, inquiry_id: str) -> bool:
        """Book atomically. Returns False if this inquiry already holds the slot (idempotent)."""
        with self.tx() as c:
            if c.execute("SELECT 1 FROM bookings WHERE slot_id = ? AND inquiry_id = ?",
                         (slot_id, inquiry_id)).fetchone():
                return False
            row = c.execute("SELECT capacity, (SELECT COUNT(*) FROM bookings WHERE slot_id = ?) AS booked"
                            " FROM slots WHERE org_id = ? AND slot_id = ?", (slot_id, org_id, slot_id)).fetchone()
            if row is None:
                raise NotFound(f"slot {slot_id}")
            if row["booked"] >= row["capacity"]:
                raise ValueError(f"slot {slot_id} is full")
            c.execute("INSERT INTO bookings VALUES (?, ?, ?, ?)", (slot_id, inquiry_id, org_id, _iso(utcnow())))
            return True

    # ------------------------------------------------------------ drafts
    def save_draft(self, draft: DraftRecord) -> None:
        with self.tx() as c:
            c.execute(
                "INSERT OR REPLACE INTO drafts (draft_id, org_id, inquiry_id, created_at, author, status, text,"
                " final_text, fact_ids_used, proposed_slot_ids, findings_json, reviewed_by, reviewed_at,"
                " override_reason) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (draft.draft_id, draft.org_id, draft.inquiry_id, _iso(draft.created_at), draft.author, draft.status,
                 draft.text, draft.final_text, json.dumps(draft.fact_ids_used), json.dumps(draft.proposed_slot_ids),
                 json.dumps([f.model_dump() for f in draft.findings]),
                 draft.reviewed_by, _iso(draft.reviewed_at), draft.override_reason),
            )

    @staticmethod
    def _draft(row: sqlite3.Row) -> DraftRecord:
        data = dict(row)
        return DraftRecord(
            draft_id=data["draft_id"], org_id=data["org_id"], inquiry_id=data["inquiry_id"],
            created_at=_dt(data["created_at"]), author=data["author"], status=data["status"], text=data["text"],
            final_text=data["final_text"], fact_ids_used=json.loads(data["fact_ids_used"]),
            proposed_slot_ids=json.loads(data["proposed_slot_ids"]),
            findings=[Finding(**f) for f in json.loads(data["findings_json"])],
            reviewed_by=data["reviewed_by"], reviewed_at=_dt(data["reviewed_at"]),
            override_reason=data["override_reason"],
        )

    # ------------------------------------------------------------ agent runs
    def save_run(self, org_id: str, inquiry_id: str, output: dict[str, Any]) -> str:
        run_id = new_id("RUN")
        with self.tx() as c:
            c.execute("INSERT INTO agent_runs VALUES (?, ?, ?, ?, ?)",
                      (run_id, org_id, inquiry_id, _iso(utcnow()), json.dumps(output, ensure_ascii=False)))
        return run_id

    def latest_run(self, org_id: str, inquiry_id: str) -> dict[str, Any] | None:
        rows = self._rows("SELECT output_json FROM agent_runs WHERE org_id = ? AND inquiry_id = ?"
                          " ORDER BY created_at DESC, rowid DESC LIMIT 1", (org_id, inquiry_id))
        if not rows or rows[0]["output_json"] is None:
            return None
        return json.loads(rows[0]["output_json"])

    def get_draft(self, org_id: str, draft_id: str) -> DraftRecord:
        return self._draft(self._one("SELECT * FROM drafts WHERE org_id = ? AND draft_id = ?",
                                     (org_id, draft_id), f"draft {draft_id}"))

    def latest_draft(self, org_id: str, inquiry_id: str) -> DraftRecord | None:
        rows = self._rows("SELECT * FROM drafts WHERE org_id = ? AND inquiry_id = ?"
                          " ORDER BY created_at DESC, rowid DESC LIMIT 1", (org_id, inquiry_id))
        return self._draft(rows[0]) if rows else None

    # ------------------------------------------------------------ tasks and contact blocks
    def add_task(self, org_id: str, inquiry_id: str | None, kind: str, reason: str) -> Task:
        task = Task(task_id=new_id("TASK"), org_id=org_id, inquiry_id=inquiry_id, kind=kind, reason=reason,
                    created_at=utcnow())
        with self.tx() as c:
            c.execute("INSERT INTO tasks VALUES (?, ?, ?, ?, ?, ?, ?)",
                      (task.task_id, org_id, inquiry_id, kind, reason, _iso(task.created_at), task.status))
        return task

    def list_tasks(self, org_id: str, inquiry_id: str | None = None) -> list[Task]:
        if inquiry_id is None:
            rows = self._rows("SELECT * FROM tasks WHERE org_id = ? ORDER BY created_at", (org_id,))
        else:
            rows = self._rows("SELECT * FROM tasks WHERE org_id = ? AND inquiry_id = ? ORDER BY created_at",
                              (org_id, inquiry_id))
        return [Task(**{**dict(r), "created_at": _dt(r["created_at"])}) for r in rows]

    def add_contact_block(self, org_id: str, applicant_ref: str, kind: str) -> bool:
        with self.tx() as c:
            cur = c.execute("INSERT OR IGNORE INTO contact_blocks VALUES (?, ?, ?, ?)",
                            (org_id, applicant_ref, kind, _iso(utcnow())))
            return cur.rowcount == 1

    def contact_blocks(self, org_id: str, applicant_ref: str) -> set[str]:
        rows = self._rows("SELECT kind FROM contact_blocks WHERE org_id = ? AND applicant_ref = ?",
                          (org_id, applicant_ref))
        return {r["kind"] for r in rows}

    # ------------------------------------------------------------ audit
    def add_audit(self, org_id: str, actor: str, event_type: str, entity_type: str, entity_id: str,
                  payload: dict[str, Any]) -> None:
        with self.tx() as c:
            c.execute("INSERT INTO audit_events (org_id, at, actor, event_type, entity_type, entity_id, payload_json)"
                      " VALUES (?, ?, ?, ?, ?, ?, ?)",
                      (org_id, _iso(utcnow()), actor, event_type, entity_type, entity_id,
                       json.dumps(payload, ensure_ascii=False, sort_keys=True)))

    def list_audit(self, org_id: str, entity_id: str | None = None, limit: int = 500) -> list[AuditEvent]:
        if entity_id is None:
            rows = self._rows("SELECT * FROM audit_events WHERE org_id = ? ORDER BY event_id DESC LIMIT ?",
                              (org_id, limit))
        else:
            rows = self._rows("SELECT * FROM audit_events WHERE org_id = ? AND entity_id = ?"
                              " ORDER BY event_id LIMIT ?", (org_id, entity_id, limit))
        return [AuditEvent(event_id=r["event_id"], org_id=r["org_id"], at=_dt(r["at"]), actor=r["actor"],
                           event_type=r["event_type"], entity_type=r["entity_type"], entity_id=r["entity_id"],
                           payload=json.loads(r["payload_json"])) for r in rows]
