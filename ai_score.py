LOW_INTERACTION_THRESHOLD = 5

WEIGHT_PROFILES = {
    "new": {"popular": 0.5, "ncf": 0.0, "content": 0.5},
    "low_interaction": {"popular": 0.2, "ncf": 0.3, "content": 0.5},
    "established": {"popular": 0.2, "ncf": 0.4, "content": 0.4},
}

_popularity_fn = None
_ncf_score_fn = None
_content_score_fn = None
_user_interaction_counts = {}


def configure(
    popular_fn=None,
    ncf_fn=None,
    content_fn=None,
    user_interaction_counts=None,
):

    global _popularity_fn, _ncf_score_fn, _content_score_fn, _user_interaction_counts

    _popularity_fn = popular_fn
    _ncf_score_fn = ncf_fn
    _content_score_fn = content_fn
    _user_interaction_counts = (
        user_interaction_counts if user_interaction_counts is not None else {}
    )


def get_weights(customer_id, low_interaction_threshold=LOW_INTERACTION_THRESHOLD):
    if customer_id is None or customer_id not in _user_interaction_counts:
        return WEIGHT_PROFILES["new"].copy()

    interaction_count = _user_interaction_counts[customer_id]
    if interaction_count < low_interaction_threshold:
        return WEIGHT_PROFILES["low_interaction"].copy()
    return WEIGHT_PROFILES["established"].copy()


def compute_ai_score(product, customer_id=None, reference_product=None):
    weights = get_weights(customer_id)

    components = {
        "popular": _popularity_fn(product) if callable(_popularity_fn) else None,
        "ncf": _ncf_score_fn(customer_id, product) if (customer_id and callable(_ncf_score_fn)) else None,
        "content": _content_score_fn(reference_product, product) if (reference_product and callable(_content_score_fn)) else None,
    }

    available = {k: v for k, v in components.items() if v is not None}
    total_weight = sum(weights[k] for k in available)

    fallback_used = False
    weights_used = {}
    final_score = None

    if total_weight > 0:
        weighted_sum = sum(weights[k] * v for k, v in available.items())
        final_score = (weighted_sum / total_weight) * 100
        weights_used = {k: round(weights[k] / total_weight, 4) for k in available}
    elif callable(_popularity_fn):
        fallback_score = _popularity_fn(product)
        if fallback_score is not None:
            final_score = fallback_score * 100
            fallback_used = True

    result = dict(components)
    result["final_ai_score"] = round(final_score) if final_score is not None else 0
    result["weights_used"] = weights_used
    result["fallback_used"] = fallback_used

    return result