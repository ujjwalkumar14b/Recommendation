DEFAULT_WEIGHTS = {"popular": 0.05, "user_cf": 0.05, "item_cf": 0.40, "content": 0.50}
weights = DEFAULT_WEIGHTS.copy()


def get_weights(customer_id=None):
    if customer_id is None:
        return {"popular": 0.60, "user_cf": 0.0, "item_cf": 0.0, "content": 0.40}
    return DEFAULT_WEIGHTS.copy()


_popularity_fn = None
_user_cf_score_fn = None
_item_cf_score_fn = None
_content_score_fn = None

def configure(popular_fn = None, user_cf_fn = None, item_cf_fn = None, content_fn = None):

    global _popularity_fn, _user_cf_score_fn, _item_cf_score_fn, _content_score_fn

    _popularity_fn = popular_fn
    _user_cf_score_fn = user_cf_fn
    _item_cf_score_fn = item_cf_fn
    _content_score_fn = content_fn
    

def compute_ai_score(product, customer_id=None, reference_product=None):
    weights = get_weights(customer_id)

    components = {
        "popular": _popularity_fn(product) if callable(_popularity_fn) else None,
        "user_cf": _user_cf_score_fn(customer_id, product) if (customer_id and callable(_user_cf_score_fn)) else None,
        "item_cf": _item_cf_score_fn(customer_id, product) if (customer_id and callable(_item_cf_score_fn)) else None,
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