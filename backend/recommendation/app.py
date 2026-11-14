import os
import gc
from pathlib import Path
from datetime import datetime

import numpy as np
import pandas as pd
from scipy.sparse import csr_matrix
from flask import Flask, jsonify, render_template, request
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.feature_extraction.text import TfidfVectorizer

try:
    from . import ai_score, xai
except ImportError:
    import ai_score
    import xai

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = PROJECT_ROOT / "recommendation" / "data.csv"

app = Flask(
    __name__,
    template_folder=str(PROJECT_ROOT / "frontend"),
    static_folder=str(PROJECT_ROOT / "frontend"),
    static_url_path="/static",
)

# 1. Data Preprocessing
use_cols = ["Product", "Quantity", "Price", "CustomerID", "StockCode", "Time"]
df = pd.read_csv(DATA_PATH, encoding="latin1", usecols=use_cols)
df["Product"] = df["Product"].astype(str).str.strip()
df = df.dropna(subset=["Product", "CustomerID"])

df["StockCode"] = pd.to_numeric(df["StockCode"], errors="coerce").fillna(0).astype("int32")
df["Quantity"] = df["Quantity"].astype("int16")
df["Price"] = df["Price"].astype("float32")
df["CustomerID"] = df["CustomerID"].astype("int32")

products = sorted(df["Product"].unique().tolist())
customers = sorted(df["CustomerID"].unique().tolist())
DEFAULT_CUSTOMER_ID = 12347

product_details = (
    df.drop_duplicates(subset=["Product"])[["Product", "Price", "StockCode"]]
    .set_index("Product")
    .to_dict(orient="index")
)
for _product, _details in product_details.items():
    _details["price"] = float(_details.get("Price", 0))
    _details["stockcode"] = _details.get("StockCode", "N/A")

train_size = int(len(df) * 0.80)
train_df = df.iloc[:train_size].copy()

del df
gc.collect()

# 2. Popularity Recommendation
popular_products = (
    train_df.groupby("Product")["Quantity"]
    .sum()
    .sort_values(ascending=False)
    .index.tolist()
)
popular_rank_map = {prod: idx for idx, prod in enumerate(popular_products)}
total_popular = len(popular_products)

train_df["Hour"] = pd.to_datetime(train_df["Time"], format="%H:%M", errors="coerce").dt.hour
hourly_popularity = {}
for hour in range(24):
    hour_data = train_df[train_df["Hour"] == hour]
    if not hour_data.empty:
        hourly_popularity[hour] = (
            hour_data.groupby("Product")["Quantity"]
            .sum()
            .sort_values(ascending=False)
            .index.tolist()
        )
    else:
        hourly_popularity[hour] = popular_products


def popular_recommend(target_time=None, top_n=25):
    if target_time is None:
        hour = datetime.now().hour
    elif isinstance(target_time, int):
        hour = target_time
    elif isinstance(target_time, str):
        hour = pd.to_datetime(target_time, format="%H:%M").hour
    elif isinstance(target_time, datetime):
        hour = target_time.hour
    else:
        hour = datetime.now().hour
    return hourly_popularity.get(hour, popular_products)[:top_n]


# 3. Sparse User-Item Matrix & Float32 Similarity Matrices
train_customers = sorted(train_df["CustomerID"].unique().tolist())
train_products = sorted(train_df["Product"].unique().tolist())

cust_to_idx = {cid: idx for idx, cid in enumerate(train_customers)}
idx_to_cust = {idx: cid for cid, idx in cust_to_idx.items()}

prod_to_idx = {prod: idx for idx, prod in enumerate(train_products)}
idx_to_prod = {idx: prod for prod, idx in prod_to_idx.items()}

grouped_ui = train_df.groupby(["CustomerID", "Product"], as_index=False)["Quantity"].sum()
row_indices = grouped_ui["CustomerID"].map(cust_to_idx).values
col_indices = grouped_ui["Product"].map(prod_to_idx).values
quantities = grouped_ui["Quantity"].astype("float32").values

user_item_sparse = csr_matrix(
    (quantities, (row_indices, col_indices)),
    shape=(len(train_customers), len(train_products)),
    dtype=np.float32,
)

# Compute similarities directly in float32 (no heavy Pandas DataFrames)
user_similarity = cosine_similarity(user_item_sparse, dense_output=True).astype(np.float32)
item_similarity = cosine_similarity(user_item_sparse.T, dense_output=True).astype(np.float32)

user_purchased_items = train_df.groupby("CustomerID")["Product"].apply(set).to_dict()

del grouped_ui, row_indices, col_indices, quantities, train_df
gc.collect()


# 4. Collaborative & Content Recommendation Functions
def user_based_recommend(customer_id, top_n=25):
    if customer_id not in cust_to_idx:
        return []

    u_idx = cust_to_idx[customer_id]
    sims = user_similarity[u_idx]
    # Top 5 most similar users (excluding self)
    top_user_indices = np.argsort(sims)[::-1]
    top_user_indices = [idx for idx in top_user_indices if idx != u_idx][:5]

    purchased_indices = set(user_item_sparse[u_idx].indices)
    scores = {}

    for sim_u_idx in top_user_indices:
        row = user_item_sparse[sim_u_idx]
        for p_idx, qty in zip(row.indices, row.data):
            if qty > 0 and p_idx not in purchased_indices:
                prod_name = idx_to_prod[p_idx]
                scores[prod_name] = scores.get(prod_name, 0.0) + float(qty)

    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return [x[0] for x in ranked[:top_n]]


def item_based_recommend(product, top_n=25):
    if product not in prod_to_idx:
        return []

    p_idx = prod_to_idx[product]
    sims = item_similarity[p_idx]
    top_indices = np.argsort(sims)[::-1]
    return [idx_to_prod[idx] for idx in top_indices if idx != p_idx][:top_n]


# Content-Based Similarity
tfidf = TfidfVectorizer(stop_words="english")
tfidf_matrix = tfidf.fit_transform(train_products)
content_similarity = cosine_similarity(tfidf_matrix, dense_output=True).astype(np.float32)


def content_recommend(product, top_n=25):
    if product not in prod_to_idx:
        return []

    p_idx = prod_to_idx[product]
    sims = content_similarity[p_idx]
    top_indices = np.argsort(sims)[::-1]
    return [idx_to_prod[idx] for idx in top_indices if idx != p_idx][:top_n]


# 5. Hybrid Recommendation
def hybrid_recommend(
    product=None,
    customer_id=None,
    target_time=None,
    top_n=25,
    candidate_k=25,
    low_interaction_threshold=5,
):
    weights = {"popular": 0.05, "user_cf": 0.05, "item_cf": 0.40, "content": 0.50}

    recs = {
        "popular": popular_recommend(target_time=target_time, top_n=candidate_k)
        if weights["popular"] > 0
        else [],
        "user_cf": user_based_recommend(customer_id, top_n=candidate_k)
        if weights["user_cf"] > 0 and customer_id
        else [],
        "item_cf": item_based_recommend(product, top_n=candidate_k)
        if weights["item_cf"] > 0 and product
        else [],
        "content": content_recommend(product, top_n=candidate_k)
        if weights["content"] > 0 and product
        else [],
    }

    candidate_scores = {}
    purchased = user_purchased_items.get(customer_id, set())

    for model_name, item_list in recs.items():
        w = weights[model_name]
        if w == 0:
            continue
        for rank, item in enumerate(item_list):
            if item in purchased:
                continue
            score = w * (1.0 / (rank + 60))
            candidate_scores[item] = candidate_scores.get(item, 0.0) + score

    sorted_candidates = sorted(candidate_scores.items(), key=lambda x: x[1], reverse=True)
    final_recs = [item for item, _ in sorted_candidates[:top_n]]

    if len(final_recs) < top_n:
        for item in popular_recommend(target_time=target_time, top_n=top_n * 2):
            if item not in final_recs and item not in purchased:
                final_recs.append(item)
            if len(final_recs) == top_n:
                break

    return final_recs


# 6. Model Weights Scoring
def get_popular_score(product):
    if product in popular_rank_map and total_popular > 0:
        rank = popular_rank_map[product]
        return max(0.0, 1.0 - (rank / total_popular))
    return 0.0


def get_user_cf_score(customer_id, product):
    if customer_id is None or product is None:
        return 0.0
    if customer_id not in cust_to_idx or product not in prod_to_idx:
        return 0.0

    u_idx = cust_to_idx[customer_id]
    p_idx = prod_to_idx[product]
    sims = user_similarity[u_idx]

    top_user_indices = [idx for idx in np.argsort(sims)[::-1] if idx != u_idx][:5]
    contributions = []
    weights = []

    for other_u_idx in top_user_indices:
        sim = float(sims[other_u_idx])
        if sim <= 0:
            continue
        qty = float(user_item_sparse[other_u_idx, p_idx])
        if qty <= 0:
            continue
        contributions.append(sim * qty)
        weights.append(abs(sim))

    if not contributions:
        return 0.0

    denominator = sum(weights) if sum(weights) > 0 else 1.0
    return float(min(1.0, sum(contributions) / denominator))


def get_item_cf_score(customer_id, product):
    if customer_id is None or product is None:
        return 0.0
    if customer_id not in cust_to_idx or product not in prod_to_idx:
        return 0.0

    u_idx = cust_to_idx[customer_id]
    target_p_idx = prod_to_idx[product]
    user_row = user_item_sparse[u_idx]

    if user_row.nnz == 0:
        return 0.0

    strengths = []
    weights = []
    for p_idx, qty in zip(user_row.indices, user_row.data):
        if p_idx == target_p_idx or qty <= 0:
            continue
        sim = float(item_similarity[p_idx, target_p_idx])
        if sim <= 0:
            continue
        strengths.append(sim * float(qty))
        weights.append(abs(sim) * float(qty))

    if not strengths:
        return 0.0

    denominator = sum(weights) if sum(weights) > 0 else 1.0
    return float(min(1.0, sum(strengths) / denominator))


def get_content_score(reference_product, product):
    if not reference_product or not product:
        return 0.0
    if reference_product in prod_to_idx and product in prod_to_idx:
        idx1 = prod_to_idx[reference_product]
        idx2 = prod_to_idx[product]
        return float(content_similarity[idx1, idx2])
    return 0.0


ai_score.configure(
    popular_fn=get_popular_score,
    user_cf_fn=get_user_cf_score,
    item_cf_fn=get_item_cf_score,
    content_fn=get_content_score,
)


def update_product_details_ai(product_list, customer_id=None, reference_product=None):
    for prod in product_list:
        if prod in product_details:
            score_res = ai_score.compute_ai_score(
                product=prod,
                customer_id=customer_id,
                reference_product=reference_product,
            )
            product_details[prod]["ai_score"] = score_res["final_ai_score"]
            product_details[prod]["explanation"] = xai.explain(score_res)


# 7. Routes
@app.get("/api/health")
def api_health():
    return jsonify({"status": "ok"})


@app.get("/api/products")
def api_products():
    query = request.args.get("query", "").strip().casefold()
    try:
        page = max(1, int(request.args.get("page", "1")))
        per_page = min(100, max(1, int(request.args.get("per_page", "24"))))
    except ValueError:
        return jsonify({"error": "page and per_page must be integers"}), 400

    matching_products = [
        name for name in products if not query or query in name.casefold()
    ]
    if query:
        matching_products.sort(key=lambda name: name.casefold() != query)
    start = (page - 1) * per_page
    items = [
        {
            "name": name,
            "price": product_details[name]["price"],
            "stockCode": str(product_details[name]["stockcode"]),
        }
        for name in matching_products[start : start + per_page]
    ]
    return jsonify(
        {
            "items": items,
            "total": len(matching_products),
            "page": page,
            "perPage": per_page,
        }
    )


@app.get("/api/products/lookup")
def api_product_lookup():
    name = request.args.get("name", "").strip().casefold()
    stock_code = request.args.get("stockCode", "").strip()
    if stock_code:
        product = next(
            (
                item
                for item in products
                if str(product_details[item]["stockcode"]) == stock_code
            ),
            None,
        )
    else:
        product = next((item for item in products if item.casefold() == name), None)
    if product is None:
        return jsonify({"error": "Product not found"}), 404

    details = product_details[product]
    return jsonify(
        {
            "name": product,
            "price": details["price"],
            "stockCode": str(details["stockcode"]),
        }
    )


@app.post("/api/recommendations")
def api_recommendations():
    payload = request.get_json(silent=True) or {}
    selected_product = payload.get("product")
    if not isinstance(selected_product, str) or not selected_product.strip():
        return jsonify({"error": "A product name is required"}), 400

    selected_product = next(
        (
            item
            for item in products
            if item.casefold() == selected_product.strip().casefold()
        ),
        None,
    )
    if selected_product is None:
        return jsonify({"error": "Choose a product from the catalogue"}), 404

    customer_id = payload.get("customerId")
    if customer_id is not None:
        try:
            customer_id = int(customer_id)
        except (TypeError, ValueError):
            return jsonify({"error": "CustomerID must be a positive integer"}), 400
        if customer_id <= 0:
            return jsonify({"error": "CustomerID must be a positive integer"}), 400

    recommendations = hybrid_recommend(
        product=selected_product,
        customer_id=customer_id,
        top_n=25,
    )
    result = []
    for product in recommendations:
        details = product_details.get(product)
        if details is None:
            continue
        score = ai_score.compute_ai_score(
            product=product,
            customer_id=customer_id,
            reference_product=selected_product,
        )
        result.append(
            {
                "name": product,
                "price": details["price"],
                "stockCode": str(details["stockcode"]),
                "aiScore": score["final_ai_score"],
                "explanation": xai.explain(score),
            }
        )

    return jsonify(
        {
            "product": selected_product,
            "recommendations": result,
        }
    )


@app.route("/")
def home():
    return render_template(
        "home.html",
        products=products,
        customers=customers,
        selected_customer=DEFAULT_CUSTOMER_ID,
        selected_product=None,
        popular_recommendations=[],
        user_cf_recommendations=[],
        item_cf_recommendations=[],
        content_recommendations=[],
        hybrid_recommendations=[],
        product_details=product_details,
    )


@app.route("/recommend", methods=["POST"])
def recommend():
    selected_product = request.form.get("product")
    selected_customer = request.form.get("customer_id", DEFAULT_CUSTOMER_ID)
    customer_id = int(selected_customer) if selected_customer else None

    popular_recommendations = popular_recommend(top_n=25)
    user_cf_recommendations = (
        user_based_recommend(customer_id, top_n=25) if customer_id else []
    )
    item_cf_recommendations = (
        item_based_recommend(selected_product, top_n=25) if selected_product else []
    )
    content_recommendations = (
        content_recommend(selected_product, top_n=25) if selected_product else []
    )
    hybrid_recommendations = hybrid_recommend(
        product=selected_product, customer_id=customer_id, top_n=25
    )

    all_recs = set(
        popular_recommendations
        + user_cf_recommendations
        + item_cf_recommendations
        + content_recommendations
        + hybrid_recommendations
    )
    update_product_details_ai(
        all_recs, customer_id=customer_id, reference_product=selected_product
    )

    return render_template(
        "recommend.html",
        products=products,
        customers=customers,
        selected_customer=customer_id,
        selected_product=selected_product,
        popular_recommendations=popular_recommendations,
        user_cf_recommendations=user_cf_recommendations,
        item_cf_recommendations=item_cf_recommendations,
        content_recommendations=content_recommendations,
        hybrid_recommendations=hybrid_recommendations,
        product_details=product_details,
    )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(
        host=os.environ.get("HOST", "0.0.0.0"),
        port=port,
        debug=os.environ.get("FLASK_DEBUG", "0") == "1",
    )
