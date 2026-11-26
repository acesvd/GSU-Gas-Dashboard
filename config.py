"""
GSU Gas Station Dashboard
Campus Configuration
"""

CAMPUSES = {
    "Buckhead": {
        "lat": 33.847940915477785,
        "lon": -84.36957371100797,
    },
    "Atlanta (Downtown)": {
        "lat": 33.753083408963214,
        "lon": -84.3852816871493,
    },
    "Alpharetta (Perimeter)": {
        "lat": 34.060438194932374,
        "lon": -84.25314994475889,
    },
    "Clarkston (Perimeter)": {
        "lat": 33.792363246884925,
        "lon": -84.23418114516872,
    },
    "Decatur (Perimeter)": {
        "lat": 33.6889511373767,
        "lon": -84.27489105535648,
    },
    "Dunwoody (Perimeter)": {
        "lat": 33.94127405389847,
        "lon": -84.30259285656282,
    },
    "Newton (Perimeter)": {
        "lat": 33.60702541079171,
        "lon": -83.75784080786491,
    },
}

DEFAULT_CAMPUS = "Buckhead"

CAMPUS_SEARCH_PROFILES = {
    "Buckhead": "standard",   
    "Atlanta": "dense",
    "Alpharetta": "sparse",
    "Clarkston": "standard",
    "Decatur": "dense",
    "Dunwoody": "sparse",
    "Newton": "sparse",
}

DEFAULT_SEARCH_PROFILE = "dense"