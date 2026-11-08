"""Approved field catalogue: which facts a unit can have, how they are labelled, and
which words in an inquiry suggest an applicant is asking about them.

This is configuration data, not model behaviour. A new customer with other fields
would change this file (later: a per-organisation config), not the prompt.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from .domain import FactKind


@dataclass(frozen=True)
class FieldDef:
    field: str
    label_de: str
    label_en: str
    kind: FactKind
    group: str  # cost | availability | detail | energy
    cues: tuple[str, ...]  # regex patterns, matched case-insensitively

    def asked_in(self, text: str) -> bool:
        return any(re.search(p, text, re.IGNORECASE) for p in self.cues)


_ENERGY_CUES = (r"energieausweis", r"energiekennwert", r"energieeffizienz", r"effizienzklasse",
                r"energy certificate", r"energy rating", r"energy class", r"\bepc\b")

FIELDS: dict[str, FieldDef] = {d.field: d for d in [
    FieldDef("cold_rent_eur", "Kaltmiete", "cold rent", FactKind.MONEY, "cost",
             (r"kaltmiete", r"\bmiete\b", r"mietpreis", r"cold rent", r"\bthe rent\b", r"monthly rent",
              r"\brent is\b")),
    FieldDef("service_charge_eur", "Nebenkostenvorauszahlung", "service-charge prepayment", FactKind.MONEY, "cost",
             (r"nebenkosten", r"betriebskosten", r"service charge", r"utilit", r"additional costs")),
    FieldDef("heating_included", "Heizkosten in den Nebenkosten enthalten", "heating included in service charge",
             FactKind.BOOL, "cost", (r"heizkosten", r"heating cost", r"heating included")),
    FieldDef("heating_costs_eur", "Heizkosten (monatlich)", "heating costs (monthly)", FactKind.MONEY, "cost",
             (r"heizkosten", r"heating cost")),
    FieldDef("deposit_eur", "Kaution", "deposit", FactKind.MONEY, "cost", (r"kaution", r"\bdeposit")),
    FieldDef("available_from", "Verfügbar ab", "available from", FactKind.DATE, "availability",
             (r"ab wann", r"verfügbar", r"frei ab", r"bezugsfrei", r"\beinzug", r"\bnoch frei\b", r"\bavailable",
              r"move[ -]?in", r"from when", r"still free")),
    FieldDef("living_area_m2", "Wohnfläche", "living area", FactKind.AREA, "detail",
             (r"wie groß", r"größe", r"quadratmeter", r"m²", r"\bqm\b", r"wohnfläche", r"\bsize\b",
              r"square met", r"\bsqm\b", r"how big", r"how large")),
    FieldDef("rooms", "Zimmer", "rooms", FactKind.COUNT, "detail", (r"zimmer", r"\brooms?\b", r"bedroom")),
    FieldDef("floor", "Stockwerk", "floor", FactKind.COUNT, "detail",
             (r"stockwerk", r"\bstock\b", r"etage", r"obergeschoss", r"which floor", r"what floor")),
    FieldDef("lift", "Aufzug", "lift", FactKind.BOOL, "detail", (r"aufzug", r"fahrstuhl", r"\blift\b", r"elevator")),
    FieldDef("balcony", "Balkon", "balcony", FactKind.BOOL, "detail", (r"balkon", r"terrasse", r"balcon", r"terrace")),
    FieldDef("fitted_kitchen", "Einbauküche", "fitted kitchen", FactKind.BOOL, "detail", (r"küche", r"kitchen")),
    FieldDef("cellar", "Kellerabteil", "cellar storage", FactKind.BOOL, "detail",
             (r"keller", r"cellar", r"basement", r"storage")),
    FieldDef("parking", "Stellplatz", "parking", FactKind.TEXT, "detail",
             (r"stellplatz", r"parkplatz", r"tiefgarage", r"garage", r"parking")),
    FieldDef("pets_policy", "Haustiere", "pets", FactKind.TEXT, "detail",
             (r"haustier", r"\bhund", r"\bkatze", r"\btier", r"\bpets?\b", r"\bdogs?\b", r"\bcats?\b")),
    FieldDef("lease_type", "Mietvertragsart", "lease type", FactKind.TEXT, "detail",
             (r"befristet", r"mindestmietdauer", r"staffelmiete", r"indexmiete", r"fixed[- ]term",
              r"lease term", r"minimum term")),
    FieldDef("heating_type", "Heizungsart", "heating type", FactKind.TEXT, "detail",
             (r"heizungsart", r"art der heizung", r"fernwärme", r"gasheizung", r"heating type", r"type of heating")),
    FieldDef("energy_certificate_type", "Art des Energieausweises", "energy certificate type", FactKind.TEXT,
             "energy", _ENERGY_CUES),
    FieldDef("energy_final_kwh", "Endenergiekennwert", "final energy value", FactKind.TEXT, "energy", _ENERGY_CUES),
    FieldDef("energy_carrier", "Wesentlicher Energieträger", "main energy carrier", FactKind.TEXT, "energy",
             _ENERGY_CUES),
    FieldDef("energy_year", "Baujahr laut Energieausweis", "year of construction (certificate)", FactKind.COUNT,
             "energy", _ENERGY_CUES),
    FieldDef("energy_class", "Energieeffizienzklasse", "energy efficiency class", FactKind.TEXT, "energy",
             _ENERGY_CUES),
    FieldDef("viewing_format", "Besichtigungsablauf", "viewing format", FactKind.TEXT, "process", ()),
]}


def asked_fields(text: str) -> list[str]:
    return [f.field for f in FIELDS.values() if f.asked_in(text)]


def label(field: str, language: str) -> str:
    d = FIELDS.get(field)
    if d is None:
        return field
    return d.label_en if language == "en" else d.label_de


# Approved knowledge snippet ids (texts live in the organisation's fixture / config).
K_VIEWING_PROCESS = "K-VIEWING-PROCESS"
K_APPLICATION_PROCESS = "K-APPLICATION-PROCESS"
K_UNKNOWN = "K-UNKNOWN"
K_NO_SLOTS = "K-NO-SLOTS"
K_INVITE = "K-INVITE"
