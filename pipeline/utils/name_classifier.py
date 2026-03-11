"""Name → language classifier using fastText + rule-based ensemble."""


def classify_name(name: str, confidence_threshold: float = 0.2) -> dict:
    """Classify a single name into a language group.

    Ensemble logic:
    1. Run fastText (fast-langdetect lid.176.bin)
    2. Run rule-based surname classifier
    3. If rule-based returned "Unknown/0.0" (no match) → use fastText
    4. If rule-based confidence >= 0.6 → use rule-based (strong pattern)
    5. Otherwise → use whichever has higher confidence

    Returns dict with: name, nationality, language, confidence
    """
    from pipeline.utils.fasttext_classifier import classify_name_fasttext
    from pipeline.utils.surname_classifier import classify_name_rule

    ft = classify_name_fasttext(name)
    rule = classify_name_rule(name)

    # Rule-based returned its default "no match" → defer to fastText
    if rule["language"] == "Unknown" and rule["confidence"] == 0.0:
        result = ft
    # Rule-based has strong signal → trust it
    elif rule["confidence"] >= 0.6:
        result = rule
    # Both have opinions → pick higher confidence
    elif ft["confidence"] >= rule["confidence"]:
        result = ft
    else:
        result = rule

    # Apply confidence threshold
    if result["confidence"] < confidence_threshold:
        return {
            "name": name,
            "nationality": result["nationality"],
            "language": "Other",
            "confidence": result["confidence"],
        }

    return result


def classify_names_batch(names: list[str], confidence_threshold: float = 0.2) -> list[dict]:
    """Classify a batch of names with deduplication for performance.

    Returns list of dicts with: name, nationality, language, confidence
    """
    # Deduplicate
    unique_names = list(set(names))
    cache = {}

    for uname in unique_names:
        cache[uname] = classify_name(uname, confidence_threshold)

    # Map back to original order
    return [cache[n] for n in names]
