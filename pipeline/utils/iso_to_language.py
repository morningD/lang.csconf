"""Mapping from ISO 639-1 language codes to our 17 language groups."""

# Maps fastText lid.176.bin output codes → our language groups.
# Unmapped codes fall through to "Other".
ISO_TO_LANGUAGE = {
    # Chinese
    "zh": "Chinese",

    # English
    "en": "English",

    # Korean
    "ko": "Korean",

    # Japanese
    "ja": "Japanese",

    # German
    "de": "German",

    # French
    "fr": "French",

    # Indian (all Indic languages)
    "hi": "Indian",
    "bn": "Indian",
    "ta": "Indian",
    "te": "Indian",
    "mr": "Indian",
    "gu": "Indian",
    "kn": "Indian",
    "ml": "Indian",
    "pa": "Indian",
    "or": "Indian",
    "ne": "Indian",
    "ur": "Indian",
    "si": "Indian",

    # Spanish
    "es": "Spanish",

    # Italian
    "it": "Italian",

    # Russian (+ Ukrainian, Belarusian)
    "ru": "Russian",
    "uk": "Russian",
    "be": "Russian",

    # Portuguese
    "pt": "Portuguese",

    # Persian (+ Pashto)
    "fa": "Persian",
    "ps": "Persian",

    # Arabic
    "ar": "Arabic",

    # Vietnamese
    "vi": "Vietnamese",

    # Turkish
    "tr": "Turkish",

    # Dutch
    "nl": "Dutch",
}


def iso_to_language_group(iso_code: str) -> str:
    """Map an ISO 639-1 code to one of our 17 language groups.

    Returns "Other" for unmapped codes.
    """
    return ISO_TO_LANGUAGE.get(iso_code, "Other")
