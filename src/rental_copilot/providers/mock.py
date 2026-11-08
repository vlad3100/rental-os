"""Deterministic mock provider: keyword rules plus templates.

Purpose: run the whole product offline, in tests and in CI, with no API key and no cost.
It is a stand-in for a model, not a model: it was written next to the evaluation cases,
so its eval scores prove the pipeline works, not that a real model is good.
"""
from __future__ import annotations

import re
import time

from ..catalog import FIELDS, K_APPLICATION_PROCESS, K_INVITE, K_NO_SLOTS, K_UNKNOWN, K_VIEWING_PROCESS, label
from ..catalog import asked_fields as catalog_asked_fields
from ..domain import HUMAN_ONLY_INTENTS, Classification, DraftProposal, DraftRequest, Intent
from ..guardrails import detect_language, detect_sensitive
from .base import CallStats

_I = re.IGNORECASE

_HUMAN_CUES: list[tuple[Intent, tuple[str, ...]]] = [
    (Intent.SPAM_OR_SCAM, (r"https?://", r"\bwww\.", r"gewonnen", r"gewinnspiel", r"congratulations", r"\bclaim\b",
                           r"bitcoin", r"crypto", r"click here", r"klicken sie hier", r"promotion", r"western union")),
    (Intent.LEGAL_OR_SENSITIVE, (r"mietpreisbremse", r"rechtlich", r"gesetz", r"zulässig", r"anwalt", r"\blegal",
                                 r"lawyer", r"\blaw\b", r"diskrimin", r"discriminat", r"vermieten sie (auch )?an",
                                 r"do you (also )?rent to")),
    (Intent.COMPLAINT_OR_HOSTILE, (r"unverschämt", r"frechheit", r"unprofessionell", r"niemand antwortet",
                                   r"keine antwort", r"beschwer", r"ridiculous", r"unprofessional",
                                   r"(no one|nobody) (answers|replies|responds)", r"complain")),
    (Intent.NEGOTIATION_OR_SPECIAL_REQUEST, (r"günstiger", r"verhandel", r"spielraum", r"rabatt", r"nachlass",
                                             r"discount", r"lower the rent", r"negotiat", r"cheaper", r"untervermiet",
                                             r"sublet", r"früher einziehen", r"move in earlier")),
    (Intent.INFO_SUBMISSION, (r"\banbei\b", r"im anhang", r"anhängend", r"\battached\b", r"i attach",
                              r"please find", r"hier (sind )?meine unterlagen")),
]
_VIEWING_CUES = (r"besichtig", r"anschauen", r"ansehen", r"\btermin", r"viewing", r"\bview\b", r"\bvisit",
                 r"see the (flat|apartment)", r"look at the (flat|apartment)")
_PROCESS_CUES = (r"bewerb", r"unterlagen", r"ablauf", r"wie läuft", r"selbstauskunft", r"application",
                 r"documents", r"how does .{0,30}work", r"\bprocess\b", r"\bapply\b")

_DEFAULT_FIELDS = {
    Intent.AVAILABILITY_QUESTION: ["available_from"],
    Intent.COST_QUESTION: ["cold_rent_eur", "service_charge_eur", "heating_included", "deposit_eur"],
    Intent.PROPERTY_DETAIL_QUESTION: ["rooms", "living_area_m2"],
    Intent.GENERIC_OR_INCOMPLETE: ["rooms", "living_area_m2", "cold_rent_eur", "available_from"],
}


def _hits(patterns: tuple[str, ...], text: str) -> int:
    return sum(1 for p in patterns if re.search(p, text, _I))


class MockProvider:
    name = "mock"
    prompt_version = "mock-rules-v1"

    # ------------------------------------------------------------------ classification
    def classify(self, message: str, unit_fields: list[str]) -> tuple[Classification, CallStats]:
        start = time.perf_counter()
        language = detect_language(message)
        asked = [f for f in catalog_asked_fields(message) if f in unit_fields]
        groups = {FIELDS[f].group for f in asked}

        human: list[Intent] = []
        for intent, cues in _HUMAN_CUES:
            hits = _hits(cues, message)
            if intent == Intent.SPAM_OR_SCAM:
                if hits >= 2:
                    human.append(intent)
            elif hits:
                human.append(intent)
        sensitive = [s for s in detect_sensitive(message) if s != "financial_identifier"]
        if sensitive and Intent.LEGAL_OR_SENSITIVE not in human:
            human.append(Intent.LEGAL_OR_SENSITIVE)

        content: list[Intent] = []
        if _hits(_VIEWING_CUES, message):
            content.append(Intent.VIEWING_REQUEST)
        if "availability" in groups:
            content.append(Intent.AVAILABILITY_QUESTION)
        if "cost" in groups:
            content.append(Intent.COST_QUESTION)
        if groups & {"detail", "energy"}:
            content.append(Intent.PROPERTY_DETAIL_QUESTION)
        if _hits(_PROCESS_CUES, message):
            content.append(Intent.PROCESS_QUESTION)

        ordered = human + content
        if not ordered:
            primary, secondary = Intent.GENERIC_OR_INCOMPLETE, []
            confidence = 0.7 if len(message) <= 60 else 0.45
            why = "No specific cue matched; short generic message." if len(message) <= 60 else \
                "No specific cue matched in a longer message; unclear intent."
        else:
            primary, secondary = ordered[0], ordered[1:4]
            if primary in HUMAN_ONLY_INTENTS:
                confidence = 0.9
            else:
                confidence = {1: 0.92, 2: 0.85}.get(len(content), 0.78)
            why = f"Rule-based mock: cues for {', '.join(i.value for i in ordered[:4])}."
        if language == "other":
            confidence = min(confidence, 0.5)
        result = Classification(intent=primary, secondary_intents=secondary, language=language, asked_fields=asked,
                                confidence=confidence, rationale=why)
        return result, CallStats(latency_ms=int((time.perf_counter() - start) * 1000))

    # ------------------------------------------------------------------ drafting
    def draft(self, request: DraftRequest) -> tuple[DraftProposal, CallStats]:
        start = time.perf_counter()
        en = request.language == "en"
        facts = {f.field: f for f in request.usable_facts}
        knowledge = {k.knowledge_id: k.text for k in request.knowledge}
        intents = [request.intent, *request.secondary_intents]

        wanted = list(request.asked_fields)
        if not wanted:
            for intent in intents:
                wanted.extend(f for f in _DEFAULT_FIELDS.get(intent, []) if f not in wanted)

        lines: list[str] = []
        used_facts: list[str] = []
        used_knowledge: list[str] = []
        for field in wanted:
            fact = facts.get(field)
            if fact is not None:
                lines.append(fact.sentence)
                used_facts.append(fact.fact_id)

        unknown = [f for f in request.unknown_fields if f in wanted]
        if unknown:
            labels = ", ".join(label(f, request.language) for f in unknown)
            lead = (f"I don't have confirmed information on the following yet: {labels}." if en
                    else f"Zu folgenden Punkten liegen mir noch keine bestätigten Angaben vor: {labels}.")
            lines.append(f"{lead} {knowledge.get(K_UNKNOWN, '')}".strip())
            used_knowledge.append(K_UNKNOWN)

        slot_ids: list[str] = []
        if Intent.VIEWING_REQUEST in intents:
            if request.slots:
                lines.append("These viewing slots are currently available:" if en
                             else "Folgende Besichtigungstermine sind derzeit frei:")
                lines.extend(f"- {s.display}" for s in request.slots)
                lines.append("Please let me know which slot suits you." if en
                             else "Bitte teilen Sie mir mit, welcher Termin Ihnen passt.")
                slot_ids = [s.slot_id for s in request.slots]
            else:
                lines.append(knowledge.get(K_NO_SLOTS, ""))
                used_knowledge.append(K_NO_SLOTS)
            if not request.contact_channel_present:
                lines.append(knowledge.get(K_VIEWING_PROCESS, ""))
                used_knowledge.append(K_VIEWING_PROCESS)
            lines.append(knowledge.get(K_APPLICATION_PROCESS, ""))
            used_knowledge.append(K_APPLICATION_PROCESS)
        elif Intent.PROCESS_QUESTION in intents:
            lines.extend([knowledge.get(K_VIEWING_PROCESS, ""), knowledge.get(K_APPLICATION_PROCESS, "")])
            used_knowledge.extend([K_VIEWING_PROCESS, K_APPLICATION_PROCESS])
        elif request.intent == Intent.GENERIC_OR_INCOMPLETE:
            lines.extend([knowledge.get(K_VIEWING_PROCESS, ""), knowledge.get(K_INVITE, "")])
            used_knowledge.extend([K_VIEWING_PROCESS, K_INVITE])
        else:
            lines.append(knowledge.get(K_INVITE, ""))
            used_knowledge.append(K_INVITE)

        opening = "Hello,\n\nthank you for your message about the flat." if en else \
            "Guten Tag,\n\nvielen Dank für Ihre Nachricht zur Wohnung."
        closing = "Best regards" if en else "Viele Grüße"
        body = "\n".join(line for line in lines if line)
        text = f"{opening}\n\n{body}\n\n{closing}"
        proposal = DraftProposal(
            response_text=text, fact_ids_used=used_facts, unknown_fields=unknown, proposed_slot_ids=slot_ids,
            knowledge_ids_used=list(dict.fromkeys(used_knowledge)),
            rationale=f"Template draft: {len(used_facts)} verified facts, {len(unknown)} unknown, "
                      f"{len(slot_ids)} slots proposed.",
        )
        return proposal, CallStats(latency_ms=int((time.perf_counter() - start) * 1000))
