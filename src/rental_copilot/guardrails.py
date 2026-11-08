"""Deterministic guardrails.

They run in code before and after every model call, so no message text and no model
output can talk them out of a decision. They are deliberately simple pattern rules:
easy to read, easy to test, and honest about their limits (see docs/02-build/threat-model.md).

Inbound checks:  stop/deletion requests, prompt-injection cues, sensitive personal data, language.
Outbound checks: every number and fact in a draft must be backed by verified evidence, and the
draft must not request early-stage applicant data, pressure, promise, discuss other applicants,
mention protected characteristics or make legal statements.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from .domain import DraftSlot, Finding, KnowledgeSnippet, Language, Unit

_FLAGS = re.IGNORECASE


def _any(patterns: list[str] | tuple[str, ...], text: str) -> str | None:
    for pattern in patterns:
        match = re.search(pattern, text, _FLAGS)
        if match:
            return match.group(0)
    return None


def sentences(text: str) -> list[str]:
    return [s for s in re.split(r"(?<=[.!?])\s+|\n+", text) if s.strip()]


# ------------------------------------------------------------------ language
_DE_CUES = re.compile(
    r"[äöüß]|\b(ich|sie|die|der|das|und|ist|wohnung|bitte|gibt|wie|wann|mit|nicht|ein|eine|einen|für|hallo|"
    r"guten|noch|wir|auch|frei|danke|grüße|meine|habe)\b", _FLAGS)
_EN_CUES = re.compile(
    r"\b(i|you|your|the|and|is|are|flat|apartment|please|there|how|when|from|with|not|a|an|for|hi|hello|"
    r"thanks|can|could|would|my|we|to|this|it|have|has|be)\b", _FLAGS)


def detect_language(text: str) -> Language:
    de, en = len(_DE_CUES.findall(text)), len(_EN_CUES.findall(text))
    if de == 0 and en == 0:
        return "other"
    return "de" if de >= en else "en"


# ------------------------------------------------------------------ stop and deletion
_DELETION_VERB = (r"lösch\w*", r"\b(delete|erase)\b", r"recht auf (vergessenwerden|löschung)",
                  r"right to (be forgotten|erasure)", r"\bremove (all )?my (personal )?(data|information|details)")
_DELETION_OBJECT = (r"\bdaten\b", r"dsgvo", r"\bangaben\b", r"informationen", r"\banfrage\b", r"\bnachricht",
                    r"\bdata\b", r"information", r"details", r"\brecords?\b", r"\brequest\b", r"\bmessages?\b",
                    r"forgotten", r"erasure")
_OPT_OUT = (
    r"(kontaktieren|kontaktiert|anrufen|schreiben) sie mich (bitte )?(nicht|nie)",
    r"(schreiben|antworten|melden) sie (sich )?(mir|bei mir) (bitte )?(nicht|nie|keine)",
    r"nicht mehr (kontaktieren|schreiben|anrufen|melden)",
    r"keine (weiteren )?(nachrichten|e-?mails?|mails|anrufe|kontaktaufnahmen?)",
    r"(aus|von) (dem|ihrem|ihrer|der) (verteiler|liste|mailingliste)", r"\babmelden\b", r"kein interesse mehr",
    r"lassen sie mich in ruhe",
    r"\b(do not|don't|stop) (contact|e-?mail|messag|call)\w*", r"\bunsubscribe\b", r"\bremove me from\b",
    r"\bno (more|further) (messages|e-?mails|contact|calls)", r"not interested any ?more", r"leave me alone",
)
_CONDITIONAL = r"\b(falls|wenn|sofern|ansonsten|andernfalls|if|unless|otherwise)\b"


@dataclass(frozen=True)
class StopSignal:
    kind: Literal["deletion", "opt_out", "ambiguous_opt_out"]
    evidence: str  # the matched phrase, kept only in memory — never written to the audit log


def detect_stop_or_deletion(text: str) -> StopSignal | None:
    for sentence in sentences(text):
        verb = _any(_DELETION_VERB, sentence)
        if verb and _any(_DELETION_OBJECT, sentence):
            return StopSignal("deletion", verb)
    for sentence in sentences(text):
        phrase = _any(_OPT_OUT, sentence)
        if phrase:
            if re.search(_CONDITIONAL, sentence, _FLAGS):
                return StopSignal("ambiguous_opt_out", phrase)
            return StopSignal("opt_out", phrase)
    return None


# ------------------------------------------------------------------ prompt injection
_INJECTION = (
    r"ignor\w* (alle |all |any |sämtliche )?(bisherigen |vorherigen |previous |prior |above |obigen )?"
    r"(anweisungen|instructions|regeln|rules|vorgaben)",
    r"(system|developer)[ -]?(prompt|nachricht|message|instructions?)", r"\byou are now\b",
    r"\bdu bist (jetzt|ab sofort)\b", r"\bact as\b", r"\bpretend (to be|you are)\b", r"\bjailbreak\b",
    r"</?(system|assistant|instructions?)>", r"\bnew instructions?\b", r"\bneue anweisung",
    r"vergiss (alles|alle)", r"forget (everything|all)",
)


def detect_prompt_injection(text: str) -> bool:
    return _any(_INJECTION, text) is not None


# ------------------------------------------------------------------ sensitive characteristics
SENSITIVE_PATTERNS: dict[str, str] = {
    "family_status": r"\b(kinder\w*|children|kids?|schwanger\w*|pregnan\w*|familie\w*|family|families|"
                     r"alleinerziehend\w*|single (mother|father|parent))\b",
    "origin_or_nationality": r"\b(herkunft|nationalität|staatsangehörigkeit|ausländer\w*|migrationshintergrund|"
                             r"flüchtling\w*|geflüchtet\w*|refugee\w*|nationality|ethnic\w*|foreigner\w*|asyl\w*|"
                             r"deutsche mieter|german tenants?)\b"
                             r"|\b(aus|from) (syrien|syria|der türkei|turkey|afghanistan|der ukraine|ukraine|"
                             r"nigeria|indien|india|polen|poland|rumänien|romania)\b",
    "religion": r"\b(religion\w*|religiös\w*|muslim\w*|christlich\w*|christian\w*|jüdisch\w*|jewish|islam\w*|"
                r"kirche|church|moschee|mosque)\b",
    "health_or_disability": r"\b(krank\w*|behinder\w*|rollstuhl\w*|diagnos\w*|therapie|disab\w*|wheelchair|"
                            r"illness|sick)\b",
    "gender_or_age": r"\b(geschlecht|gender|lebensalter|ihr alter|your age)\b",
}
_IBAN = r"\b[A-Z]{2}\d{2}(?:\s?[A-Z0-9]{4}){3,7}\b"


def detect_sensitive(text: str) -> list[str]:
    found = [name for name, pattern in SENSITIVE_PATTERNS.items() if re.search(pattern, text, _FLAGS)]
    if re.search(_IBAN, text):
        found.append("financial_identifier")
    return found


# ------------------------------------------------------------------ numbers
_DATE_ISO = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})(?:T(\d{2}):(\d{2})(?::\d{2})?)?\b")
_DATE_DE = re.compile(r"\b(\d{1,2})\.(\d{1,2})\.(\d{4})\b")
_TIME = re.compile(r"\b(\d{1,2}):(\d{2})\b")
_NUM = re.compile(r"\d+(?:[.,]\d+)*")


def extract_numbers(text: str) -> set[float]:
    """Numbers as values: '1.450 €' and '€1,450' → 1450; dates and times → their components."""
    found: set[float] = set()

    def take(match: re.Match[str]) -> str:
        found.update(float(int(g)) for g in match.groups() if g is not None)
        return " "

    for rx in (_DATE_ISO, _DATE_DE, _TIME):
        text = rx.sub(take, text)
    for token in _NUM.findall(text):
        if re.fullmatch(r"\d{1,3}(?:[.,]\d{3})+", token):
            found.add(float(token.replace(".", "").replace(",", "")))
        elif "," in token or "." in token:
            try:
                found.add(float(token.replace(",", ".")))
            except ValueError:
                found.update(float(p) for p in re.split(r"[.,]", token) if p)
        else:
            found.add(float(token))
    return found


# ------------------------------------------------------------------ outbound draft checks
_DOC_TERMS = (
    r"schufa", r"bonität", r"\bgehalt(s|snachweis\w*)?\b", r"lohnabrechnung", r"einkommen", r"kontoauszug",
    r"arbeitgeber", r"arbeitsvertrag", r"\bberuf\b", r"personalausweis", r"\bausweis", r"reisepass", r"selbstauskunft",
    r"mietschuldenfreiheit", r"vermieterbescheinigung", r"geburtsdatum", r"familienstand",
    r"credit (check|report|score)", r"pay ?slip", r"salary", r"\bincome\b", r"bank statement", r"employer",
    r"employment contract", r"occupation", r"passport", r"\bid card\b", r"copy of your id", r"date of birth",
    r"marital status",
)
_REQUEST_CUES = (
    r"bitte (senden|schicken|übermitteln|reichen|legen|geben|teilen|lassen)", r"(senden|schicken) sie",
    r"benötige", r"brauche", r"(wir|ich) bitten", r"please (send|provide|share|submit|attach)",
    r"\bwe (need|require)", r"\bi need\b", r"(could|can) you (send|provide|share)", r"\bsend (us|me)\b",
)
_NEGATION = r"\b(keine|keinen|keiner|nicht|kein|no|not|don't|do not|without|noch keine)\b"
_PRESSURE = (
    r"nur noch (heute|kurz|wenige)", r"schnell (entscheiden|zugreifen|sein)", r"sonst (ist|sind) .{0,30}weg",
    r"wer zuerst kommt", r"verpassen sie nicht", r"\bact (now|fast|quickly)\b", r"\bhurry\b", r"limited time",
    r"first come,? first serve", r"don't miss", r"\bdringend\b.{0,20}\bentscheiden\b",
)
_OTHER_APPLICANTS = (
    r"andere(n)? (bewerber|interessenten|mietinteressenten)", r"viele (andere )?(interessenten|bewerber|anfragen)",
    r"other (applicants|candidates|interested parties)", r"many (other )?(applicants|people|inquiries)",
    r"(gute|hohe|schlechte|realistische) chancen", r"\b(good|high|low) chances?\b", r"ihre chancen", r"your chances",
)
_LEGAL = (
    r"mietpreisbremse", r"rechtlich (zulässig|erlaubt|einwandfrei|in ordnung)", r"\bgesetzlich\b", r"\blegally\b",
    r"\b(un)?zulässig\b", r"\blegal\b", r"\billegal\b", r"\bmietspiegel\b",
)
_PROMISE = (
    r"(sie bekommen|sie erhalten) (die|den) (wohnung|zuschlag|vertrag|zusage)", r"\bzusage\b",
    r"you('ll| will) get the (flat|apartment)", r"\bgarantier\w*", r"\bguarantee\w*",
)
_PLACEHOLDER = r"\{[a-z_]+\}|\[(name|datum|date|todo|tbd)\]"


def _numbers_supported_by(unit: Unit, fact_ids: list[str], slots: list[DraftSlot],
                          knowledge: list[KnowledgeSnippet]) -> set[float]:
    allowed: set[float] = set()
    by_id = {f.fact_id: f for f in unit.facts}
    for fact_id in fact_ids:
        fact = by_id.get(fact_id)
        if fact and fact.usable:
            allowed |= extract_numbers(fact.value or "")
            allowed |= extract_numbers(fact.value_en or "")
    for slot in slots:
        dt = slot.starts_at
        allowed |= {float(dt.year), float(dt.month), float(dt.day), float(dt.hour), float(dt.minute)}
    for snippet in knowledge:
        allowed |= extract_numbers(snippet.text)
    return allowed


def check_draft(text: str, *, unit: Unit, fact_ids_used: list[str], slots: list[DraftSlot],
                knowledge: list[KnowledgeSnippet], expected_language: Language) -> list[Finding]:
    """Return findings. Any `block` finding means the draft must not be offered for approval as-is."""
    findings: list[Finding] = []
    by_id = {f.fact_id: f for f in unit.facts}

    for fact_id in fact_ids_used:
        fact = by_id.get(fact_id)
        if fact is None:
            findings.append(Finding(code="unknown_fact_reference", severity="block",
                                    message=f"Draft cites {fact_id}, which is not on this unit's fact sheet."))
        elif not fact.usable:
            findings.append(Finding(code="unverified_fact_used", severity="block",
                                    message=f"Draft uses {fact.field} with status '{fact.status.value}'."))

    supported = _numbers_supported_by(unit, fact_ids_used, slots, knowledge)
    unsupported = sorted(n for n in extract_numbers(text) if n not in supported)
    if unsupported:
        shown = ", ".join(f"{n:g}" for n in unsupported)
        findings.append(Finding(code="unsupported_number", severity="block",
                                message=f"Numbers without verified evidence: {shown}."))

    for sentence in sentences(text):
        if (_any(_DOC_TERMS, sentence) and _any(_REQUEST_CUES, sentence)
                and not re.search(_NEGATION, sentence, _FLAGS)):
            findings.append(Finding(code="early_stage_data_request", severity="block",
                                    message="Draft asks for applicant data that is not needed before a viewing "
                                            "(DSK stage model: name and one contact channel only)."))
            break

    checks = (
        ("pressure_language", _PRESSURE, "Draft uses pressure or false urgency."),
        ("other_applicants_or_chances", _OTHER_APPLICANTS, "Draft talks about other applicants or chances."),
        ("legal_statement", _LEGAL, "Draft makes a legal statement; legal questions go to a human."),
        ("selection_promise", _PROMISE, "Draft promises or implies a selection outcome."),
    )
    for code, patterns, message in checks:
        if _any(patterns, text):
            findings.append(Finding(code=code, severity="block", message=message))

    sensitive = [s for s in detect_sensitive(text) if s != "financial_identifier"]
    if sensitive:
        findings.append(Finding(
            code="sensitive_attribute", severity="block",
            message=f"Draft mentions protected or sensitive characteristics: {', '.join(sensitive)}."))

    if re.search(_PLACEHOLDER, text, _FLAGS):
        findings.append(Finding(code="unfilled_placeholder", severity="warn", message="Draft contains a placeholder."))
    if len(text) > 1500:
        findings.append(Finding(code="too_long", severity="warn", message="Draft is longer than 1,500 characters."))
    if expected_language in ("de", "en") and detect_language(text) != expected_language:
        findings.append(Finding(code="language_mismatch", severity="warn",
                                message=f"Draft language differs from the inquiry language ({expected_language})."))
    return findings


def has_block(findings: list[Finding]) -> bool:
    return any(f.severity == "block" for f in findings)
