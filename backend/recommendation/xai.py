from __future__ import annotations

__all__ = ["explain"]

SIGNAL_LABELS = {
    "popular": ("Catalog Popularity", "Popular across catalogue."),
    "user_cf": ("User CF", "Based on users with similar tastes."),
    "item_cf": ("Item CF", "Based on items similar to what you interacted with."),
    "content": ("Product Similarity", "Similarity to product."),
}

SIGNAL_ORDER = ["popular", "user_cf", "item_cf", "content"]


def explain(ai_score_result):
    
    if not ai_score_result:
        return {
            "summary": "Not enough data is available to explain this recommendation.",
            "reasons": [],
            "breakdown": [],
        }

    if ai_score_result.get("fallback_used"):
        return {
            "summary": "Limited personalization data is available, so this product is recommended using catalog popularity.",
            "reasons": [
                {
                    "label": "Catalog Popularity",
                    "detail": "Used as the fallback signal because other personalization signals were unavailable.",
                }
            ],
            "breakdown": [],
        }

    weights = ai_score_result.get("weights_used", {})
    breakdown = []
    reasons = []

    for key in SIGNAL_ORDER:
        value = ai_score_result.get(key)
        weight = weights.get(key, 0)

        if value is None or weight <= 0:
            continue

        value = max(0.0, min(1.0, float(value)))
        contribution = value * weight * 100.0
        signal_score = value * 100.0
        label, description = SIGNAL_LABELS[key]

        breakdown.append({
            "key": key,
            "label": label,
            "score": round(signal_score),
            "weight": round(weight * 100),
            "contribution": round(contribution, 1),
        })

        # Only cite a signal as a reason when it actually contributes.
        if value >= 0.15:
            if key == "user_cf":
                detail = f"{description}"
            elif key == "item_cf":
                detail = f"{description}"
            elif key == "content":
                detail = f"{description}"
            else:
                detail = f"{description}"
            reasons.append({"label": label, "detail": detail})

    if not reasons:
        reasons.append({
            "label": "Available recommendation signals",
            "detail": "This item received a lower-strength match across the available signals.",
        })

    # Lead with the strongest actual contributor.
    strongest = max(breakdown, key=lambda x: x["contribution"]) if breakdown else None
    if strongest:
        summary = (
            f"Primarily recommended because of {strongest['label']} "
            f"({strongest['contribution']:.1f} points contributed to the AI score)."
        )
    else:
        summary = "Recommended from the available catalogue signals."

    return {
        "summary": summary,
        "reasons": reasons,
        "breakdown": breakdown,
    }
