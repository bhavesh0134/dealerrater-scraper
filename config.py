#!/usr/bin/env python3
"""
Configuration — OEM/state combos, rep mapping, variant mapping.
Pure constants; no imports from project files.
"""

TIER_1 = [
    ("Chrysler",   "Texas"),
    ("Dodge",      "Texas"),
    ("Jeep",       "Texas"),
    ("Ram",        "Texas"),
    ("Chrysler",   "Florida"),
    ("Jeep",       "Florida"),
    ("Chrysler",   "Georgia"),
    ("Jeep",       "Tennessee"),
    ("Ford",       "Texas"),
    ("Ford",       "Florida"),
    ("Ford",       "Georgia"),
    ("Ford",       "New-York"),
    ("Ford",       "Pennsylvania"),
    ("Ford",       "Ohio"),
    ("Chevrolet",  "Texas"),
    ("Chevrolet",  "California"),
    ("GMC",        "Texas"),
    ("Chevrolet",  "Illinois"),
    ("Chevrolet",  "Ohio"),
]

TIER_2 = [
    ("Toyota",        "Texas"),
    ("Toyota",        "California"),
    ("Toyota",        "Florida"),
    ("Toyota",        "New-York"),
    ("Mercedes-Benz", "California"),
    ("Mercedes-Benz", "Texas"),
    ("Mercedes-Benz", "New-York"),
    ("Mercedes-Benz", "Florida"),
    ("Chrysler",      "South-Carolina"),
    ("Jeep",          "Oklahoma"),
    ("Chrysler",      "Missouri"),
    ("Jeep",          "Alabama"),
]

OEM_VARIANT: dict[str, str] = {
    "Chrysler":     "A",
    "Dodge":        "A",
    "Jeep":         "A",
    "Ram":          "A",
    "Ford":         "B",
    "Chevrolet":    "C",
    "GMC":          "C",
    "Buick":        "C",
    "Cadillac":     "C",
    "Mercedes-Benz": "D",
    "Toyota":       "E",
    "Honda":        "F",
    "Nissan":       "G",
    "KIA":          "H",
    "Subaru":       "I",
    "Volkswagen":   "K",
    "Mazda":        "L",
    "BMW":          "M",
    "Mitsubishi":   "N",
    "Audi":         "O",
    "Lexus":        "P",
    "Acura":        "Q",
    "Volvo":        "R",
    "Infiniti":     "S",
    "Mini":         "T",
    "Land-Rover":   "U",
    "Porsche":      "V",
    "Jaguar":       "W",
    "Independent":  "Z",
}

# State strings match the hyphenated DealerRater URL form
# Revised 2026-08-10 (Revised Sales Territory by Rep_Aug10'26.xlsx) — adds Brandon,
# reshuffles states previously on Justin/Mike. See dealerrater-scraper memory.
GARRISON_STATES = {
    "Alaska", "Arizona", "California", "Colorado", "Hawaii", "Idaho",
    "Minnesota", "Montana", "North-Dakota", "Nebraska", "New-Mexico", "Nevada",
    "Oregon", "South-Dakota", "Utah", "Washington", "Wisconsin", "Wyoming",
}

JUSTIN_STATES = {
    "Alabama", "Arkansas", "Florida", "Georgia",
    "Kentucky", "Louisiana", "Mississippi",
    "North-Carolina", "Oklahoma", "South-Carolina", "Tennessee", "West-Virginia",
}

MIKE_STATES = {
    "Connecticut", "DC", "Delaware", "Massachusetts",
    "Maryland", "Maine", "New-Hampshire", "New-Jersey", "New-York",
    "Pennsylvania", "Rhode-Island", "Vermont", "Virginia",
}

BRANDON_STATES = {
    "Illinois", "Indiana", "Iowa", "Kansas", "Michigan", "Missouri",
    "Ohio", "Texas",
}


def get_rep(state: str) -> str:
    if state in GARRISON_STATES:
        return "Garrison Ramoso"
    if state in JUSTIN_STATES:
        return "Justin Smith"
    if state in BRANDON_STATES:
        return "Brandon"
    return "Mike Arena"


ICP_TITLE_KEYWORDS = [
    "service manager",
    "general manager",
    "fixed ops",
    "service director",
    "dealer principal",
    "fixed operations",
    "vp",
    "vice president",
    "owner",
    "president",
]

# Rate limits (seconds)
RATE_LIMIT_LISTING: float = 2.0
RATE_LIMIT_DETAIL:  float = 1.0

MAX_RETRIES: int = 3
HIGH_VOLUME_THRESHOLD: int = 500
