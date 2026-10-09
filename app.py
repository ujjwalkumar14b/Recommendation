import os
import gc
import xai
import ai_score
import pandas as pd

from datetime import datetime
from flask import Flask, render_template, request
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.feature_extraction.text import TfidfVectorizer

app = Flask(__name__, template_folder='.', static_folder='.', static_url_path='')

# Data Preprocessing 
use_cols = ["Product", "Quantity", "Price", "CustomerID", "StockCode", "Time"]
df = pd.read_csv("data.csv", encoding="latin1", usecols=use_cols)

df["StockCode"] = df["StockCode"].astype('int32')
df["Quantity"] = df["Quantity"].astype('int16')
df["Price"] = df["Price"].astype('float32')
df["CustomerID"] = df["CustomerID"].astype('int32')

train_size = int(len(df) * 0.80)
train_df = df.iloc[:train_size]
user_interaction_counts = train_df.groupby("CustomerID").size().to_dict()


# CustomerID and Product
products = sorted(df["Product"].dropna().astype(str).unique().tolist())
customers = sorted(df["CustomerID"].dropna().astype(int).unique().tolist())
DEFAULT_CUSTOMER_ID = 12347

product_details = (
    df.drop_duplicates(subset=["Product"])[["Product", "Price", "StockCode"]]
    .set_index("Product")
    .to_dict(orient="index")
)

for _product, _details in product_details.items():
    _details["price"] = float(_details.get("Price", 0))
    _details["stockcode"] = _details.get("StockCode", "N/A")

del df
gc.collect()


# Recommendation Models

### Popularity Recommendation
train_df_time = train_df.copy()
train_df_time['Hour'] = pd.to_datetime(train_df_time['Time'], format='%H:%M').dt.hour
popular_products = train_df.groupby("Product")["Quantity"].sum().sort_values(ascending=False).index.tolist()
hourly_popularity = {}

for hour in range(24):
    hour_data = train_df_time[train_df_time['Hour'] == hour]
    if not hour_data.empty:
        popular_in_hour = (
            hour_data.groupby("Product")["Quantity"]
            .sum()
            .sort_values(ascending=False)
            .index.tolist()
        )
        hourly_popularity[hour] = popular_in_hour
    else:
        hourly_popularity[hour] = popular_products

def popular_recommend(target_time=None, top_n=25):
    if target_time is None:
        hour = datetime.now().hour
    elif isinstance(target_time, int):
        hour = target_time
    elif isinstance(target_time, str):
        hour = pd.to_datetime(target_time, format='%H:%M').hour
    elif isinstance(target_time, datetime):
        hour = target_time.hour
    else:
        hour = datetime.now().hour
        
    return hourly_popularity.get(hour, popular_products)[:top_n]


### User Item Matrix 
user_item = train_df.pivot_table(index="CustomerID", columns="Product", values="Quantity", aggfunc="sum", fill_value=0)
user_similarity = cosine_similarity(user_item)
item_similarity = cosine_similarity(user_item.T)
user_similarity_df = pd.DataFrame(user_similarity, index = user_item.index, columns = user_item.index)
item_similarity_df = pd.DataFrame(item_similarity, index = user_item.columns, columns = user_item.columns)

### User Based Collaborative Recommendation
def user_based_recommend(customer_id, top_n = 25):
    if customer_id not in user_item.index:
        return []

    similar_users = (user_similarity_df[customer_id].sort_values(ascending=False).iloc[1:6].index)
    purchased = (user_item.loc[customer_id])
    purchased = (purchased[purchased > 0].index)

    scores = {}
    for user in similar_users:
        items = user_item.loc[user]
        for product in items[items > 0].index:
            if product not in purchased:
                scores[product] = (scores.get(product, 0) + items[product])

    scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return [x[0] for x in scores[:top_n]]


user_similarity_df = user_similarity_df.astype('float32')
user_similarity_df.index = user_similarity_df.index.astype(object)
user_similarity_df.columns = user_similarity_df.columns.astype(object)

### Item Based Collaborative Recommendation
def item_based_recommend(product, top_n = 25):
    if product not in item_similarity_df.index:
        return []

    return (item_similarity_df[product].sort_values(ascending=False).iloc[1:top_n+1].index.tolist())


item_similarity_df = item_similarity_df.astype('float32')
item_similarity_df.index = item_similarity_df.index.astype(object)
item_similarity_df.columns = item_similarity_df.columns.astype(object)


### Content Based Recommendation
product_data = (train_df[['Product']].drop_duplicates().reset_index(drop=True))
tfidf = TfidfVectorizer(stop_words='english')
tfidf_matrix = tfidf.fit_transform(product_data['Product'])
content_similarity = cosine_similarity(tfidf_matrix)

content_similarity_df = pd.DataFrame(
    content_similarity,
    index=product_data['Product'],
    columns=product_data['Product']
)
product_to_tfidf_idx = {product: idx for idx, product in enumerate(product_data['Product'])}

def content_recommend(product, top_n = 25):
    if product not in content_similarity_df.index:
        return []

    return (
        content_similarity_df[product]
        .sort_values(ascending=False)
        .iloc[1:top_n+1]
        .index
        .tolist()
    )


content_similarity_df = content_similarity_df.astype('float32')
content_similarity_df.index = content_similarity_df.index.astype(object)
content_similarity_df.columns = content_similarity_df.columns.astype(object)


### Hybrid Recommendation
user_interaction_counts = train_df.groupby("CustomerID")["Product"].nunique().to_dict()
user_purchased_items = train_df.groupby("CustomerID")["Product"].apply(set).to_dict()

def hybrid_recommend(product=None, customer_id=None, target_time=None, top_n=25, candidate_k=25, low_interaction_threshold=5):
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

# Model Weights Scoring 
def get_popular_score(product):
    if product in popular_products:
        rank = popular_products.index(product)
        return max(0.0, 1.0 - (rank / len(popular_products)))
    return 0.0


def get_user_cf_score(customer_id, product):
    if customer_id is None or product is None:
        return 0.0
    if customer_id not in user_item.index or product not in user_item.columns:
        return 0.0

    ranked_users = user_similarity_df[customer_id].sort_values(ascending=False)
    ranked_users = ranked_users[ranked_users.index != customer_id]
    if ranked_users.empty:
        return 0.0

    contributions = []
    weights = []
    for other_user, similarity in ranked_users.head(5).items():
        similarity = float(similarity)
        if similarity <= 0:
            continue
        other_purchases = user_item.loc[other_user]
        if product not in other_purchases.index:
            continue
        qty = float(other_purchases[product])
        if qty <= 0:
            continue
        contributions.append(similarity * qty)
        weights.append(abs(similarity))

    if not contributions:
        return 0.0

    numerator = sum(contributions)
    denominator = sum(weights) if sum(weights) > 0 else 1.0
    return float(min(1.0, numerator / denominator))


def get_item_cf_score(customer_id, product):
    if customer_id is None or product is None:
        return 0.0
    if customer_id not in user_item.index or product not in item_similarity_df.index:
        return 0.0

    purchased = user_item.loc[customer_id]
    purchased_products = purchased[purchased > 0].index.tolist()
    if not purchased_products:
        return 0.0

    strengths = []
    weights = []
    for purchased_product in purchased_products:
        if purchased_product == product:
            continue
        if purchased_product not in item_similarity_df.index:
            continue
        similarity = float(item_similarity_df.loc[purchased_product, product])
        if similarity <= 0:
            continue
        qty = float(purchased[purchased_product])
        strengths.append(similarity * qty)
        weights.append(abs(similarity) * qty)

    if not strengths:
        return 0.0

    numerator = sum(strengths)
    denominator = sum(weights) if sum(weights) > 0 else 1.0
    return float(min(1.0, numerator / denominator))


def get_content_score(reference_product, product):
    if not reference_product or not product:
        return 0.0
    if reference_product in product_to_tfidf_idx and product in product_to_tfidf_idx:
        idx1 = product_to_tfidf_idx[reference_product]
        idx2 = product_to_tfidf_idx[product]
        return float(cosine_similarity(tfidf_matrix[idx1], tfidf_matrix[idx2])[0][0])
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
                reference_product=reference_product
            )
            product_details[prod]["ai_score"] = score_res["final_ai_score"]
            product_details[prod]["explanation"] = xai.explain(score_res)

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
