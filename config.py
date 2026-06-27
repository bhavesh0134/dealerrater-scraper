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
}

# State strings match the hyphenated DealerRater URL form
GARRISON_STATES = {
    "Alaska", "Arizona", "California", "Colorado", "Hawaii", "Idaho",
    "Minnesota", "Montana", "North-Dakota", "New-Mexico", "Nevada",
    "Oregon", "South-Dakota", "Utah", "Washington", "Wyoming",
}

JUSTIN_STATES = {
    "Alabama", "Arkansas", "Florida", "Georgia", "Iowa", "Kansas",
    "Kentucky", "Louisiana", "Missouri", "Mississippi", "Nebraska",
    "Oklahoma", "South-Carolina", "Tennessee", "Texas",
}

MIKE_STATES = {
    "Connecticut", "DC", "Delaware", "Illinois", "Indiana", "Massachusetts",
    "Maryland", "Maine", "Michigan", "New-Hampshire", "New-Jersey", "New-York",
    "North-Carolina", "Ohio", "Pennsylvania", "Rhode-Island", "Vermont",
    "Virginia", "Wisconsin",
}


def get_rep(state: str) -> str:
    if state in GARRISON_STATES:
        return "Garrison Ramoso"
    if state in JUSTIN_STATES:
        return "Justin Smith"
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
