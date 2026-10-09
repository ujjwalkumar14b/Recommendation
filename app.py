import os
import gc
import pandas as pd
import numpy as np
from datetime import datetime
from flask import Flask, render_template, request
from scipy.sparse import csr_matrix
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.feature_extraction.text import TfidfVectorizer

import xai
import ai_score

app = Flask(__name__, template_folder='.', static_folder='.', static_url_path='')

# ---------------------------------------------------------
# 1. Memory-Efficient Data Preprocessing
# ---------------------------------------------------------
use_cols = ["Product", "Quantity", "Price", "CustomerID", "StockCode", "Time"]
df = pd.read_csv("data.csv", encoding="latin1", usecols=use_cols)

# Downcast numerical types immediately
df["StockCode"] = pd.to_numeric(df["StockCode"], errors='coerce', downcast='integer')
df["Quantity"] = pd.to_numeric(df["Quantity"], errors='coerce', downcast='integer')
df["Price"] = pd.to_numeric(df["Price"], errors='coerce', downcast='float')
df["CustomerID"] = pd.to_numeric(df["CustomerID"], errors='coerce', downcast='integer')

df = df.dropna(subset=["CustomerID", "Product"])

train_size = int(len(df) * 0.80)
train_df = df.iloc[:train_size].copy()

# Store minimal structures
products = sorted(train_df["Product"].astype(str).unique().tolist())
customers = sorted(train_df["CustomerID"].astype(int).unique().tolist())
DEFAULT_CUSTOMER_ID = 12347

product_details = (
    df.drop_duplicates(subset=["Product"])[["Product", "Price", "StockCode"]]
    .set_index("Product")
    .to_dict(orient="index")
)
for _product, _details in product_details.items():
    _details["price"] = float(_details.get("Price", 0))
    _details["stockcode"] = str(_details.get("StockCode", "N/A"))

del df
gc.collect()

# ---------------------------------------------------------
# 2. Popularity Lookup Construction
# ---------------------------------------------------------
train_df_time = train_df.copy()
train_df_time['Hour'] = pd.to_datetime(train_df_time['Time'], format='%H:%M', errors='coerce').dt.hour
popular_products = train_df.groupby("Product")["Quantity"].sum().sort_values(ascending=False).index.tolist()

hourly_popularity = {}
for hour in range(24):
    hour_data = train_df_time[train_df_time['Hour'] == hour]
    if not hour_data.empty:
        popular_in_hour = hour_data.groupby("Product")["Quantity"].sum().sort_values(ascending=False).index.tolist()
        hourly_popularity[hour] = popular_in_hour
    else:
        hourly_popularity[hour] = popular_products

del train_df_time
gc.collect()

def popular_recommend(target_time=None, top_n=25):
    if target_time is None:
        hour = datetime.now().hour
    elif isinstance(target_time, int):
        hour = target_time
    elif isinstance(target_time, str):
        try:
            hour = pd.to_datetime(target_time, format='%H:%M').hour
        except Exception:
            hour = datetime.now().hour
    elif isinstance(target_time, datetime):
        hour = target_time.hour
    else:
        hour = datetime.now().hour
    return hourly_popularity.get(hour, popular_products)[:top_n]

# ---------------------------------------------------------
# 3. Sparse User-Item Matrix (Replaces pivot_table & Dense Similarities)
# ---------------------------------------------------------
user_categories = pd.CategoricalDtype(categories=customers, ordered=True)
product_categories = pd.CategoricalDtype(categories=products, ordered=True)

row = train_df["CustomerID"].astype(user_categories).cat.codes
col = train_df["Product"].astype(product_categories).cat.codes

user_item_sparse = csr_matrix(
    (train_df["Quantity"].values, (row, col)),
    shape=(len(customers), len(products)),
    dtype=np.float32
)

user_to_idx = {c: i for i, c in enumerate(customers)}
product_to_idx = {p: i for i, p in enumerate(products)}
idx_to_product = {i: p for i, p in enumerate(products)}

# User Interaction Lookup
user_purchased_items = train_df.groupby("CustomerID")["Product"].apply(set).to_dict()

# ---------------------------------------------------------
# 4. Content-Based TF-IDF (Sparse Vectorizer)
# ---------------------------------------------------------
product_series = pd.Series(products)
tfidf = TfidfVectorizer(stop_words='english', max_features=5000)
tfidf_matrix = tfidf.fit_transform(product_series).astype(np.float32)

del train_df
gc.collect()

# ---------------------------------------------------------
# 5. On-Demand Recommendation Functions
# ---------------------------------------------------------
def user_based_recommend(customer_id, top_n=25):
    if customer_id not in user_to_idx:
        return []
    u_idx = user_to_idx[customer_id]
    user_vec = user_item_sparse[u_idx]
    
    # Compute similarity against all users only for this user
    similarities = cosine_similarity(user_vec, user_item_sparse).flatten()
    top_users = np.argsort(similarities)[::-1][1:6]
    purchased_indices = set(user_vec.indices)
    
    scores = {}
    for other_u in top_users:
        sim = similarities[other_u]
        if sim <= 0:
            continue
        other_items = user_item_sparse[other_u]
        for prod_idx, qty in zip(other_items.indices, other_items.data):
            if prod_idx not in purchased_indices:
                scores[prod_idx] = scores.get(prod_idx, 0.0) + (sim * qty)
                
    sorted_prods = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:top_n]
    return [idx_to_product[idx] for idx, _ in sorted_prods]

def item_based_recommend(product, top_n=25):
    if product not in product_to_idx:
        return []
    p_idx = product_to_idx[product]
    item_vec = user_item_sparse.getcol(p_idx).T
    
    similarities = cosine_similarity(item_vec, user_item_sparse.T).flatten()
    top_items = np.argsort(similarities)[::-1][1:top_n+1]
    return [idx_to_product[idx] for idx in top_items]

def content_recommend(product, top_n=25):
    if product not in product_to_idx:
        return []
    p_idx = product_to_idx[product]
    prod_vec = tfidf_matrix[p_idx]
    
    similarities = cosine_similarity(prod_vec, tfidf_matrix).flatten()
    top_items = np.argsort(similarities)[::-1][1:top_n+1]
    return [idx_to_product[idx] for idx in top_items]

def hybrid_recommend(product=None, customer_id=None, target_time=None, top_n=25, candidate_k=25):
    weights = {"popular": 0.05, "user_cf": 0.05, "item_cf": 0.40, "content": 0.50}
    recs = {
        "popular": popular_recommend(target_time=target_time, top_n=candidate_k) if weights["popular"] > 0 else [],
        "user_cf": user_based_recommend(customer_id, top_n=candidate_k) if weights["user_cf"] > 0 and customer_id else [],
        "item_cf": item_based_recommend(product, top_n=candidate_k) if weights["item_cf"] > 0 and product else [],
        "content": content_recommend(product, top_n=candidate_k) if weights["content"] > 0 and product else [],
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

# ---------------------------------------------------------
# 6. Optimized Model Weights Scoring Functions
# ---------------------------------------------------------
def get_popular_score(product):
    if product in popular_products:
        rank = popular_products.index(product)
        return max(0.0, 1.0 - (rank / len(popular_products)))
    return 0.0

def get_user_cf_score(customer_id, product):
    if customer_id is None or product is None or customer_id not in user_to_idx or product not in product_to_idx:
        return 0.0
    u_idx = user_to_idx[customer_id]
    p_idx = product_to_idx[product]
    
    user_vec = user_item_sparse[u_idx]
    similarities = cosine_similarity(user_vec, user_item_sparse).flatten()
    top_users = np.argsort(similarities)[::-1][1:6]
    
    contributions = []
    weights = []
    for other_u in top_users:
        sim = float(similarities[other_u])
        if sim <= 0:
            continue
        qty = float(user_item_sparse[other_u, p_idx])
        if qty <= 0:
            continue
        contributions.append(sim * qty)
        weights.append(abs(sim))
        
    if not contributions:
        return 0.0
    return float(min(1.0, sum(contributions) / (sum(weights) if sum(weights) > 0 else 1.0)))

def get_item_cf_score(customer_id, product):
    if customer_id is None or product is None or customer_id not in user_to_idx or product not in product_to_idx:
        return 0.0
    u_idx = user_to_idx[customer_id]
    p_idx = product_to_idx[product]
    
    purchased_indices = user_item_sparse[u_idx].indices
    if len(purchased_indices) == 0:
        return 0.0
        
    item_vec = user_item_sparse.getcol(p_idx).T
    similarities = cosine_similarity(item_vec, user_item_sparse.T).flatten()
    
    strengths = []
    weights = []
    for p_other_idx in purchased_indices:
        if p_other_idx == p_idx:
            continue
        sim = float(similarities[p_other_idx])
        if sim <= 0:
            continue
        qty = float(user_item_sparse[u_idx, p_other_idx])
        strengths.append(sim * qty)
        weights.append(abs(sim) * qty)
        
    if not strengths:
        return 0.0
    return float(min(1.0, sum(strengths) / (sum(weights) if sum(weights) > 0 else 1.0)))

def get_content_score(reference_product, product):
    if not reference_product or not product or reference_product not in product_to_idx or product not in product_to_idx:
        return 0.0
    idx1 = product_to_idx[reference_product]
    idx2 = product_to_idx[product]
    return float(cosine_similarity(tfidf_matrix[idx1], tfidf_matrix[idx2])[0][0])

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
                reference_product=reference_product
            )
            product_details[prod]["ai_score"] = score_res["final_ai_score"]
            product_details[prod]["explanation"] = xai.explain(score_res)

# ---------------------------------------------------------
# 7. Flask Routes
# ---------------------------------------------------------
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
        product_details=product_details
    )

@app.route("/recommend", methods=["POST"])
def recommend():
    selected_product = request.form.get("product")
    selected_customer = request.form.get("customer_id", DEFAULT_CUSTOMER_ID)
    customer_id = int(selected_customer) if selected_customer else None

    popular_recommendations = popular_recommend(top_n=25)
    user_cf_recommendations = user_based_recommend(customer_id, top_n=25) if customer_id else []
    item_cf_recommendations = item_based_recommend(selected_product, top_n=25) if selected_product else []
    content_recommendations = content_recommend(selected_product, top_n=25) if selected_product else []
    hybrid_recommendations = hybrid_recommend(product=selected_product, customer_id=customer_id, top_n=25)

    all_recs = set(popular_recommendations + user_cf_recommendations + item_cf_recommendations + content_recommendations + hybrid_recommendations)
    update_product_details_ai(all_recs, customer_id=customer_id, reference_product=selected_product)

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
        product_details=product_details
    )

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
