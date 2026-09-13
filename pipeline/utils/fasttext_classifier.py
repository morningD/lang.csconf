"""FastText-based name classifier using fast-langdetect (lid.176.bin)."""

from pipeline.utils.iso_to_language import iso_to_language_group

_initialized = False


def _parse_detect(result) -> dict:
    """Normalize fast-langdetect output to {'lang', 'score'}.

    Handles both the legacy dict format and the list-of-dicts format
    returned by newer releases.
    """
    if isinstance(result, list) and result:
        result = result[0]
    if not isinstance(result, dict) or "lang" not in result:
        return {}
    return result


def _ensure_init():
    """Lazy-initialize fast-langdetect with a smoke test."""
    global _initialized
    if _initialized:
        return

    from fast_langdetect import detect

    # Smoke test — detect returns {'lang', 'score'} (dict or single-element list)
    result = _parse_detect(detect("Pierre Dupont"))
    if not result:
        raise RuntimeError("fast-langdetect smoke test failed: unexpected result format")
    _initialized = True


def classify_name_fasttext(name: str) -> dict:
    """Classify a single name using fastText language detection.

    Returns dict with: name, nationality, language, confidence
    """
    _ensure_init()

    from fast_langdetect import detect

    try:
        result = _parse_detect(detect(name))
        if not result:
            raise ValueError("unexpected detect result")
        iso_code = result["lang"]
        confidence = float(result["score"])
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
