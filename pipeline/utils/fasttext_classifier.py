"""FastText-based name classifier using fast-langdetect (lid.176.bin)."""

from pipeline.utils.iso_to_language import iso_to_language_group

_initialized = False


def _ensure_init():
    """Lazy-initialize fast-langdetect with a smoke test."""
    global _initialized
    if _initialized:
        return

    from fast_langdetect import detect

    # Smoke test — detect returns a list of dicts
    result = detect("Pierre Dupont", model="full", k=1)
    if not isinstance(result, list) or not result or "lang" not in result[0]:
        raise RuntimeError("fast-langdetect smoke test failed: unexpected result format")
    _initialized = True


def classify_name_fasttext(name: str) -> dict:
    """Classify a single name using fastText language detection.

    Returns dict with: name, nationality, language, confidence
    """
    _ensure_init()

    from fast_langdetect import detect

    try:
        results = detect(name, model="full", k=1)
        top = results[0]
        iso_code = top["lang"]
        confidence = float(top["score"])
        language = iso_to_language_group(iso_code)

        return {
            "name": name,
            "nationality": iso_code,
            "language": language,
            "confidence": round(confidence, 4),
        }
    except Exception:
        return {
            "name": name,
            "nationality": "Unknown",
            "language": "Other",
            "confidence": 0.0,
        }
