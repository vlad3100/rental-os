"""Language-aware rendering of verified facts and viewing slots.

Values are rendered by code, not by the model, so "1.450 €" in German and "€1,450"
in English are both traceable to the stored value "1450".
"""
from __future__ import annotations

from datetime import date, datetime

from .catalog import label
from .domain import Fact, FactKind

_WEEKDAYS = {
    "de": ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"],
    "en": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
}
_MONTHS_EN = ["January", "February", "March", "April", "May", "June", "July", "August", "September",
              "October", "November", "December"]


def _lang(language: str) -> str:
    return "en" if language == "en" else "de"


def money(value: str, language: str) -> str:
    amount = int(float(value))
    if _lang(language) == "en":
        return f"€{amount:,}"
    return f"{amount:,} €".replace(",", ".")


def a_date(value: str, language: str) -> str:
    d = date.fromisoformat(value)
    if _lang(language) == "en":
        return f"{d.day} {_MONTHS_EN[d.month - 1]} {d.year}"
    return f"{d.day:02d}.{d.month:02d}.{d.year}"


def display_value(fact: Fact, language: str) -> str:
    lang = _lang(language)
    value = fact.value or ""
    if fact.kind == FactKind.MONEY:
        return money(value, lang)
    if fact.kind == FactKind.AREA:
        return f"{value} m²"
    if fact.kind == FactKind.DATE:
        return a_date(value, lang)
    if fact.kind == FactKind.BOOL:
        yes = value == "true"
        return ("yes" if yes else "no") if lang == "en" else ("ja" if yes else "nein")
    if fact.kind == FactKind.TEXT and lang == "en" and fact.value_en:
        return fact.value_en
    return value


def slot_display(starts_at: datetime, language: str) -> str:
    lang = _lang(language)
    weekday = _WEEKDAYS[lang][starts_at.weekday()]
    if lang == "en":
        return f"{weekday}, {starts_at.day} {_MONTHS_EN[starts_at.month - 1]} {starts_at.year}, {starts_at:%H:%M}"
    return f"{weekday}, {starts_at:%d.%m.%Y}, {starts_at:%H:%M} Uhr"


_SENTENCES: dict[str, tuple[str, str]] = {
    "cold_rent_eur": ("Die Kaltmiete beträgt {v} im Monat.", "The cold rent is {v} per month."),
    "service_charge_eur": ("Die Nebenkostenvorauszahlung beträgt {v} im Monat.",
                           "The service-charge prepayment is {v} per month."),
    "heating_costs_eur": ("Die Heizkosten betragen {v} im Monat.", "Heating costs are {v} per month."),
    "deposit_eur": ("Die Kaution beträgt {v}.", "The deposit is {v}."),
    "available_from": ("Die Wohnung ist ab dem {v} verfügbar.", "The flat is available from {v}."),
    "living_area_m2": ("Die Wohnfläche beträgt {v}.", "The living area is {v}."),
    "floor": ("Die Wohnung liegt im {v}. Obergeschoss.", "The flat is on floor {v}."),
    "lease_type": ("Der Mietvertrag ist {v}.", "The lease is {v}."),
}
_BOOL_SENTENCES: dict[str, tuple[tuple[str, str], tuple[str, str]]] = {
    "heating_included": (("Die Heizkosten sind in den Nebenkosten enthalten.",
                          "Die Heizkosten sind nicht in den Nebenkosten enthalten."),
                         ("Heating costs are included in the service charge.",
                          "Heating costs are not included in the service charge.")),
    "lift": (("Es gibt einen Aufzug.", "Es gibt keinen Aufzug."), ("There is a lift.", "There is no lift.")),
    "balcony": (("Die Wohnung hat einen Balkon.", "Die Wohnung hat keinen Balkon."),
                ("The flat has a balcony.", "The flat has no balcony.")),
    "fitted_kitchen": (("Eine Einbauküche ist vorhanden.", "Eine Einbauküche ist nicht vorhanden."),
                       ("A fitted kitchen is included.", "There is no fitted kitchen.")),
    "cellar": (("Zur Wohnung gehört ein Kellerabteil.", "Zur Wohnung gehört kein Kellerabteil."),
               ("A cellar storage room is included.", "There is no cellar storage room.")),
}


def fact_sentence(fact: Fact, language: str) -> str:
    lang = _lang(language)
    idx = 1 if lang == "en" else 0
    if fact.kind == FactKind.BOOL and fact.field in _BOOL_SENTENCES:
        variants = _BOOL_SENTENCES[fact.field][idx]
        return variants[0] if fact.value == "true" else variants[1]
    if fact.field == "rooms":
        n = fact.value or ""
        if lang == "en":
            return f"The flat has {n} room." if n == "1" else f"The flat has {n} rooms."
        return f"Die Wohnung hat {n} Zimmer."
    template = _SENTENCES.get(fact.field)
    value = display_value(fact, lang)
    if template:
        return template[idx].format(v=value)
    return f"{label(fact.field, lang)}: {value}."
