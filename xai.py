from __future__ import annotations

SIGNAL_LABELS = {
    "ncf": ("Neural Collaborative Filtering", "Personalized match from the learned customer-product interaction pattern."),
    "content": ("Product Similarity", "Similarity to the product you selected."),
    "popular": ("Catalog Popularity", "Popularity of this product across the catalogue."),
}

SIGNAL_ORDER = ["ncf", "content", "popular"]


def explain(ai_score_result):
    
    if not ai_score_result or ai_score_result.get("fallback_used"):
        return {
            "breakdown": [],
        }

    weights = ai_score_result.get("weights_used", {})
    breakdown = []

    for key in SIGNAL_ORDER:
        value = ai_score_result.get(key)
        weight = weights.get(key, 0)

        if value is None or weight <= 0:
            continue

        value = max(0.0, min(1.0, float(value)))
        contribution = value * weight * 100.0
        signal_score = value * 100.0
        label, _ = SIGNAL_LABELS[key]

        breakdown.append({
            "key": key,
            "label": label,
            "score": round(signal_score),
            "weight": round(weight * 100),
            "contribution": round(contribution, 1),
        })

    return {
        "breakdown": breakdown,
    }