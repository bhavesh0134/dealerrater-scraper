#!/usr/bin/env python3
"""Config for the AI-Ark direct-search enrichment pipeline (Spiffy KALI campaign)."""

# Full state names as required by AI-Ark's location enum (ark://reference/locations)
REP_STATES = {
    "garrison": [
        "Alaska", "Arizona", "California", "Colorado", "Hawaii", "Idaho",
        "Minnesota", "Montana", "North Dakota", "New Mexico", "Nevada",
        "Oregon", "South Dakota", "Utah", "Washington", "Wyoming",
    ],
    "justin": [
        "Alabama", "Arkansas", "Florida", "Georgia", "Iowa", "Kansas",
        "Kentucky", "Louisiana", "Missouri", "Mississippi", "Nebraska",
        "Oklahoma", "South Carolina", "Tennessee", "Texas",
    ],
    "mike": [
        "Connecticut", "District of Columbia", "Delaware", "Illinois", "Indiana",
        "Massachusetts", "Maryland", "Maine", "Michigan", "New Hampshire",
        "New Jersey", "New York", "North Carolina", "Ohio", "Pennsylvania",
        "Rhode Island", "Vermont", "Virginia", "Wisconsin",
    ],
}

REP_DISPLAY_NAME = {
    "garrison": "Garrison Ramoso",
    "justin":   "Justin Smith",
    "mike":     "Mike Arena",
}

# DNC — never search or include these brands
DNC_BRANDS = {"hyundai", "genesis"}

# OEM franchise brands to search for (word-boundary matched against company name).
# No DealerRater page-count ceiling here, so include everything sold new in the US
# except DNC brands.
OEM_BRANDS = [
    "Ford", "Toyota", "Chevrolet", "Chrysler", "Mercedes-Benz", "Jeep", "Honda",
    "Nissan", "KIA", "GMC", "Dodge", "Ram", "Cadillac", "Subaru", "Volkswagen",
    "Mazda", "BMW", "Mitsubishi", "Audi", "Lexus", "Acura", "Volvo", "Infiniti",
    "Buick", "Mini", "Land Rover", "Porsche", "Jaguar", "Lincoln", "Fiat",
    "Alfa Romeo", "Maserati", "Ferrari", "Polestar", "Bentley",
    "Lamborghini", "Aston Martin", "Rolls-Royce", "McLaren",
    "Isuzu",
]
# Dropped entirely (see filters.DROP_BRANDS): Smart, Tesla, Scion, Saab,
# Suzuki — discontinued in the US / not sold via a franchise-dealer model,
# and every sampled hit for these was a false positive (unrelated company
# sharing the brand word).

# Brands whose name collides heavily with common English words / other
# business names. No longer used to gate results (that approach wrongly
# dropped legitimate "<City> <Brand>"-pattern dealers) — kept only as a
# reference list; precision is handled via filters.EXCLUDE_NAME_PATTERNS.
HIGH_COLLISION_BRANDS = {
    "ram", "mini", "ford", "honda", "lincoln", "bentley", "mitsubishi",
    "volkswagen", "jaguar", "dodge", "infiniti", "mclaren", "polestar",
    "buick", "fiat", "isuzu", "gmc", "jeep",
}

ICP_TITLE_PHRASES = [
    "service manager",
    "general manager",
    "fixed ops",
    "fixed operations",
    "service director",
    "dealer principal",
    "vice president",
    "owner",
    "president",
    "sales manager",
    "parts manager",
    "internet sales manager",
    "controller",
    "office manager",
]

# Query-time title filter sent to AI-Ark (broader than the strict local recheck
# list above so the API's own search net is wide; local filters.matches_icp_title
# still re-verifies every result against ICP_TITLE_PHRASES).
API_TITLE_QUERY = (
    "service manager,general manager,fixed operations,fixed ops,service director,"
    "dealer principal,vice president,owner,president,sales manager,parts manager,"
    "internet sales manager,controller,office manager"
)

TARGET_CONTACTS_PER_REP = 2000
