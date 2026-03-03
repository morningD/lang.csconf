"""Name → nationality/language classifier using name2nat with ethnicolr fallback."""

from pipeline.utils.nationality_to_lang import get_language_group

# Try to import name2nat first, fall back to ethnicolr
_classifier = None
_classifier_type = None


def _init_classifier():
    """Lazy-initialize the name classifier."""
    global _classifier, _classifier_type

    if _classifier is not None:
        return

    # Try name2nat first
    try:
        from name2nat import Name2nat
        nn = Name2nat()
        # Smoke test to verify it actually works
        test_result = nn.classify("Zhang Wei")
        if test_result and len(test_result) > 0:
            _classifier = nn
            _classifier_type = "name2nat"
            print("Using name2nat classifier")
            return
        else:
            print("name2nat loaded but returned empty result, skipping")
    except (ImportError, Exception) as e:
        print(f"name2nat unavailable: {e}")

    # Fall back to ethnicolr
    try:
        import ethnicolr
        _classifier = ethnicolr
        _classifier_type = "ethnicolr"
        print("Using ethnicolr classifier (fallback)")
        return
    except (ImportError, Exception) as e:
        print(f"ethnicolr also unavailable: {e}")

    # Fall back to rule-based classifier
    try:
        from pipeline.utils.surname_classifier import classify_name_rule
        _classifier = classify_name_rule
        _classifier_type = "rules"
        print("Using rule-based surname classifier (fallback)")
        return
    except ImportError:
        pass

    _classifier_type = "none"
    print("WARNING: No name classifier available. All names will be 'Other'.")


def classify_name(name: str, confidence_threshold: float = 0.3) -> dict:
    """Classify a single name into a language group.

    Returns dict with: name, nationality, language, confidence
    """
    _init_classifier()

    if _classifier_type == "name2nat":
        return _classify_name2nat(name, confidence_threshold)
    elif _classifier_type == "ethnicolr":
        return _classify_ethnicolr(name, confidence_threshold)
    elif _classifier_type == "rules":
        return _classifier(name)
    else:
        return {
            "name": name,
            "nationality": "Unknown",
            "language": "Other",
            "confidence": 0.0,
        }


def _classify_name2nat(name: str, threshold: float) -> dict:
    """Classify using name2nat."""
    try:
        result = _classifier.classify(name)

        if result and len(result) > 0:
            # name2nat returns list of (nationality, probability) tuples
            if isinstance(result, list):
                top = result[0]
                if isinstance(top, (list, tuple)) and len(top) >= 2:
                    nationality = str(top[0])
                    confidence = float(top[1])
                elif isinstance(top, dict):
                    nationality = top.get("nationality", "Unknown")
                    confidence = top.get("probability", 0.0)
                else:
                    nationality = str(top)
                    confidence = 0.5
            elif isinstance(result, dict):
                nationality = result.get("nationality", "Unknown")
                confidence = result.get("probability", 0.0)
            else:
                nationality = str(result)
                confidence = 0.5

            if confidence < threshold:
                return {
                    "name": name,
                    "nationality": nationality,
                    "language": "Other",
                    "confidence": confidence,
                }

            language = get_language_group(nationality)
            return {
                "name": name,
                "nationality": nationality,
                "language": language,
                "confidence": confidence,
            }
    except Exception as e:
        pass

    return {
        "name": name,
        "nationality": "Unknown",
        "language": "Other",
        "confidence": 0.0,
    }


def _classify_ethnicolr(name: str, threshold: float) -> dict:
    """Classify using ethnicolr."""
    import pandas as pd

    try:
        # Split name into first and last
        parts = name.strip().split()
        if len(parts) >= 2:
            first_name = parts[0]
            last_name = " ".join(parts[1:])
        else:
            first_name = name
            last_name = name

        df = pd.DataFrame([{"first_name": first_name, "last_name": last_name}])
        result = _classifier.pred_wiki_name(df, "last_name", "first_name")

        if result is not None and len(result) > 0:
            row = result.iloc[0]
            # ethnicolr returns race/ethnicity probabilities
            # Find the highest probability column
            prob_cols = [c for c in result.columns if c.startswith("race_") or c.startswith("api_")]
            if prob_cols:
                best_col = max(prob_cols, key=lambda c: row[c])
                confidence = float(row[best_col])
                ethnicity = best_col.replace("race_", "").replace("api_", "")

                # Map ethnicolr categories to our language groups
                ethnicity_map = {
                    "Asian,GreaterEastAsian,EastAsian": "Chinese",
                    "Asian,GreaterEastAsian,Japanese": "Japanese",
                    "Asian,IndianSubContinent": "Indian",
                    "GreaterAfrican,Muslim": "Arabic",
                    "GreaterEuropean,British": "English",
                    "GreaterEuropean,WestEuropean,French": "French",
                    "GreaterEuropean,WestEuropean,Germanic": "German",
                    "GreaterEuropean,WestEuropean,Italian": "Italian",
                    "GreaterEuropean,WestEuropean,Hispanic": "Spanish",
                    "GreaterEuropean,EastEuropean": "Russian",
                }

                language = ethnicity_map.get(ethnicity, "Other")

                if confidence < threshold:
                    language = "Other"

                return {
                    "name": name,
                    "nationality": ethnicity,
                    "language": language,
                    "confidence": confidence,
                }
    except Exception as e:
        pass

    return {
        "name": name,
        "nationality": "Unknown",
        "language": "Other",
        "confidence": 0.0,
    }


def classify_names_batch(names: list[str], confidence_threshold: float = 0.3) -> list[dict]:
    """Classify a batch of names with deduplication for performance.

    Returns list of dicts with: name, nationality, language, confidence
    """
    _init_classifier()

    # Deduplicate
    unique_names = list(set(names))
    cache = {}

    for name in unique_names:
        cache[name] = classify_name(name, confidence_threshold)

    # Map back to original order
    return [cache[name] for name in names]
