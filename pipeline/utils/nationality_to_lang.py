"""Mapping from nationalities/countries to language groups."""

# Maps country codes / nationality labels to language groups.
# Groups: Chinese, English, Korean, Japanese, German, French, Indian,
#         Spanish, Italian, Russian, Portuguese, Persian, Arabic,
#         Vietnamese, Turkish, Dutch, Other

NATIONALITY_TO_LANGUAGE = {
    # Chinese
    "China": "Chinese",
    "Chinese": "Chinese",
    "Taiwan": "Chinese",
    "Taiwanese": "Chinese",
    "Hong Kong": "Chinese",
    "Macau": "Chinese",
    "Singapore Chinese": "Chinese",

    # English
    "United States": "English",
    "American": "English",
    "United Kingdom": "English",
    "British": "English",
    "Canada": "English",
    "Canadian": "English",
    "Australia": "English",
    "Australian": "English",
    "New Zealand": "English",
    "Ireland": "English",
    "South Africa": "English",

    # Korean
    "South Korea": "Korean",
    "Korean": "Korean",
    "North Korea": "Korean",

    # Japanese
    "Japan": "Japanese",
    "Japanese": "Japanese",

    # German
    "Germany": "German",
    "German": "German",
    "Austria": "German",
    "Austrian": "German",
    "Switzerland": "German",
    "Swiss": "German",
    "Liechtenstein": "German",
    "Luxembourg": "German",

    # French
    "France": "French",
    "French": "French",
    "Belgium": "French",
    "Belgian": "French",
    "Monaco": "French",
    "Senegal": "French",
    "Cameroon": "French",
    "Ivory Coast": "French",
    "Tunisia": "French",
    "Morocco French": "French",
    "Algeria French": "French",

    # Indian
    "India": "Indian",
    "Indian": "Indian",
    "Sri Lanka": "Indian",
    "Bangladesh": "Indian",
    "Nepal": "Indian",
    "Pakistan": "Indian",
    "Pakistani": "Indian",

    # Spanish
    "Spain": "Spanish",
    "Spanish": "Spanish",
    "Mexico": "Spanish",
    "Mexican": "Spanish",
    "Colombia": "Spanish",
    "Argentina": "Spanish",
    "Chile": "Spanish",
    "Peru": "Spanish",
    "Venezuela": "Spanish",
    "Ecuador": "Spanish",
    "Cuba": "Spanish",
    "Bolivia": "Spanish",
    "Uruguay": "Spanish",
    "Paraguay": "Spanish",
    "Costa Rica": "Spanish",
    "Guatemala": "Spanish",
    "Honduras": "Spanish",
    "El Salvador": "Spanish",
    "Nicaragua": "Spanish",
    "Panama": "Spanish",

    # Italian
    "Italy": "Italian",
    "Italian": "Italian",

    # Russian
    "Russia": "Russian",
    "Russian": "Russian",
    "Ukraine": "Russian",
    "Ukrainian": "Russian",
    "Belarus": "Russian",
    "Kazakhstan": "Russian",
    "Uzbekistan": "Russian",
    "Georgia": "Russian",

    # Portuguese
    "Portugal": "Portuguese",
    "Portuguese": "Portuguese",
    "Brazil": "Portuguese",
    "Brazilian": "Portuguese",
    "Angola": "Portuguese",
    "Mozambique": "Portuguese",

    # Persian
    "Iran": "Persian",
    "Iranian": "Persian",
    "Afghanistan": "Persian",
    "Tajikistan": "Persian",

    # Arabic
    "Saudi Arabia": "Arabic",
    "Egypt": "Arabic",
    "Egyptian": "Arabic",
    "Iraq": "Arabic",
    "Syria": "Arabic",
    "Jordan": "Arabic",
    "Lebanon": "Arabic",
    "UAE": "Arabic",
    "Qatar": "Arabic",
    "Kuwait": "Arabic",
    "Bahrain": "Arabic",
    "Oman": "Arabic",
    "Yemen": "Arabic",
    "Libya": "Arabic",
    "Sudan": "Arabic",
    "Morocco": "Arabic",
    "Algeria": "Arabic",

    # Vietnamese
    "Vietnam": "Vietnamese",
    "Vietnamese": "Vietnamese",

    # Turkish
    "Turkey": "Turkish",
    "Turkish": "Turkish",
    "Azerbaijan": "Turkish",

    # Dutch
    "Netherlands": "Dutch",
    "Dutch": "Dutch",

    # Nordic → grouped as Other or could be separate
    "Sweden": "Other",
    "Swedish": "Other",
    "Norway": "Other",
    "Norwegian": "Other",
    "Denmark": "Other",
    "Danish": "Other",
    "Finland": "Other",
    "Finnish": "Other",
    "Iceland": "Other",

    # Southeast Asian
    "Thailand": "Other",
    "Thai": "Other",
    "Malaysia": "Other",
    "Indonesian": "Other",
    "Indonesia": "Other",
    "Philippines": "Other",
    "Filipino": "Other",
    "Myanmar": "Other",
    "Cambodia": "Other",
    "Laos": "Other",
    "Singapore": "Other",

    # Eastern European
    "Poland": "Other",
    "Polish": "Other",
    "Czech Republic": "Other",
    "Czech": "Other",
    "Slovakia": "Other",
    "Hungary": "Other",
    "Hungarian": "Other",
    "Romania": "Other",
    "Romanian": "Other",
    "Bulgaria": "Other",
    "Serbia": "Other",
    "Croatia": "Other",
    "Slovenia": "Other",
    "Bosnia": "Other",
    "Albania": "Other",
    "North Macedonia": "Other",
    "Montenegro": "Other",
    "Lithuania": "Other",
    "Latvia": "Other",
    "Estonia": "Other",

    # Greek
    "Greece": "Other",
    "Greek": "Other",
    "Cyprus": "Other",

    # African
    "Nigeria": "Other",
    "Kenya": "Other",
    "Ethiopia": "Other",
    "Ghana": "Other",
    "Tanzania": "Other",
    "Uganda": "Other",
    "Rwanda": "Other",

    # Central Asian
    "Turkmenistan": "Other",
    "Kyrgyzstan": "Other",
    "Mongolia": "Other",

    # Caribbean
    "Jamaica": "Other",
    "Trinidad": "Other",
    "Haiti": "Other",

    # Other
    "Israel": "Other",
    "Israeli": "Other",
}

# All language groups
LANGUAGE_GROUPS = [
    "Chinese", "English", "Korean", "Japanese", "German", "French",
    "Indian", "Spanish", "Italian", "Russian", "Portuguese", "Persian",
    "Arabic", "Vietnamese", "Turkish", "Dutch", "Other"
]

# Language group colors for charts
LANGUAGE_COLORS = {
    "Chinese": "#e74c3c",
    "English": "#3498db",
    "Korean": "#2ecc71",
    "Japanese": "#e67e22",
    "German": "#9b59b6",
    "French": "#1abc9c",
    "Indian": "#f39c12",
    "Spanish": "#e91e63",
    "Italian": "#00bcd4",
    "Russian": "#607d8b",
    "Portuguese": "#8bc34a",
    "Persian": "#795548",
    "Arabic": "#ff9800",
    "Vietnamese": "#26c6da",
    "Turkish": "#ff5722",
    "Dutch": "#ff6f00",
    "Other": "#95a5a6",
}


def get_language_group(nationality: str) -> str:
    """Map a nationality string to a language group."""
    if not nationality:
        return "Other"

    # Try exact match first
    if nationality in NATIONALITY_TO_LANGUAGE:
        return NATIONALITY_TO_LANGUAGE[nationality]

    # Try case-insensitive match
    lower = nationality.lower()
    for key, value in NATIONALITY_TO_LANGUAGE.items():
        if key.lower() == lower:
            return value

    # Try partial match
    for key, value in NATIONALITY_TO_LANGUAGE.items():
        if key.lower() in lower or lower in key.lower():
            return value

    return "Other"
