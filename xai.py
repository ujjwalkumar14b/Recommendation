SIGNAL_THRESHOLD = 0.15

# Templates matching exact keys from compute_ai_score
TEMPLATES = {
    "ncf": "Strong personalized match based on Neural Collaborative Filtering.",
    "content": "Recommended because it is similar to your selected product.",
    "popular": "Popular choice frequently bought by other customers.",
}

# Order in which signals are prioritized when scoring tie-breaks occur
_ORDER = ["ncf", "content", "popular"]


def explain(ai_score_result):
    """
    Generates a human-readable explanation string based on the output of compute_ai_score.
    """
    if not ai_score_result:
        return "Not enough data is available to explain this recommendation."

    # Handle fallback case
    if ai_score_result.get("fallback_used"):
        return ("Limited personalization data is available for this customer/product, "
                "so this suggestion is based on overall product popularity.")

    weights_used = ai_score_result.get("weights_used", {})
    contributors = []

    # Evaluate registered signals
    for key in _ORDER:
        value = ai_score_result.get(key)
        weight = weights_used.get(key, 0)
        
        # Check signal threshold
        if value is not None and weight > 0 and value >= SIGNAL_THRESHOLD:
            contributors.append((key, value * weight))

    if not contributors:
        return "Recommended based on overall catalog trends and available signals."

    # Sort contributors by weighted impact
    contributors.sort(key=lambda x: x[1], reverse=True)

    # Single primary signal explanation
    if len(contributors) == 1:
        primary_key = contributors[0][0]
        return TEMPLATES.get(primary_key, "Recommended based on your preferences.")

    # Multi-signal hybrid explanation
    top_keys = [key for key, _ in contributors[:3]]
    explanations = [TEMPLATES[k] for k in top_keys if k in TEMPLATES]
    
    return "Multiple recommendation signals support this item: " + " ".join(explanations)