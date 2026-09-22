import gc
from datetime import datetime
import os
import pandas as pd
import torch
import torch.nn as nn

from flask import Flask, render_template, request
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.feature_extraction.text import TfidfVectorizer

import ai_score
import xai

# Disable gradient tracking globally to eliminate memory overhead
torch.set_grad_enabled(False)

app = Flask(__name__, template_folder='.', static_folder='.', static_url_path='')

# ==========================================================
# 1. LIGHTWEIGHT DATA LOADING & PREPROCESSING
# ==========================================================
# Read only required columns from Product.csv as done in the Notebook
target_cols = ["CustomerID", "ProductID", "Product", "Category", "Quantity", "Price", "Time"]

df = pd.read_csv("Product.csv", encoding="latin1", usecols=lambda col: col.strip() in target_cols)
df.columns = df.columns.str.strip()

# Downcast numeric types to preserve memory
df["CustomerID"] = df["CustomerID"].astype('int32')
df["ProductID"] = df["ProductID"].astype('int32')
df["Quantity"] = df["Quantity"].astype('int16')
df["Price"] = df["Price"].astype('float32')

# 80/20 train split matching Notebook Cell [46]
train_size = int(len(df) * 0.80)
train_df = df.iloc[:train_size]

# Overall popular products
popular_products = (
    train_df.groupby("Product")["Quantity"]
    .sum()
    .sort_values(ascending=False)
    .index.tolist()
)

# Hourly popularity map matching Notebook Cell [47]
train_df_time_hours = pd.to_datetime(train_df['Time'], format='%H:%M:%S', errors='coerce').dt.hour
hourly_popularity = {}
for hour in range(24):
    hour_mask = (train_df_time_hours == hour)
    if hour_mask.any():
        popular_in_hour = (
            train_df[hour_mask].groupby("Product")["Quantity"]
            .sum()
            .sort_values(ascending=False)
            .index.tolist()
        )
        hourly_popularity[hour] = popular_in_hour
    else:
        hourly_popularity[hour] = popular_products

# Efficient User Purchase Lookup (Sparse dict set)
purchased_history = train_df.groupby('CustomerID')['Product'].apply(set).to_dict()

# Content-based setup (Category + Product text as in Notebook Cell [50])
product_data = (
    train_df[['Product', 'Category']]
    .drop_duplicates(subset=['Product'])
    .reset_index(drop=True)
)
product_data['content_text'] = product_data['Category'] + " " + product_data['Product']

product_series = product_data['Product'].tolist()
product_to_tfidf_idx = {prod: idx for idx, prod in enumerate(product_series)}

tfidf = TfidfVectorizer(stop_words='english')
tfidf_matrix = tfidf.fit_transform(product_data['content_text'])

# Product Metadata Map for UI rendering
products = sorted(df["Product"].dropna().astype(str).unique().tolist())
customers = list(purchased_history.keys())
DEFAULT_CUSTOMER_ID = customers[0] if customers else 16873

product_details = (
    df.drop_duplicates(subset=["Product"])[["Product", "Price", "ProductID", "Category"]]
    .set_index("Product")
    .to_dict(orient="index")
)

# Align template fields
for _product, _details in product_details.items():
    _details["price"] = float(_details.get("Price", 0))
    _details["stockcode"] = _details.get("ProductID", "N/A")

# Clean up raw pandas DataFrames from RAM
del df, train_df, product_data, train_df_time_hours
gc.collect()

# ==========================================================
# 2. NEURAL COLLABORATIVE FILTERING (WITH CATEGORY EMBEDDINGS)
# ==========================================================
# Create Mappings matching Notebook Cell [49]
unique_customers = list(purchased_history.keys())
unique_products = list(product_to_tfidf_idx.keys())
unique_categories = list(set([details.get("Category", "") for details in product_details.values()]))

user2idx = {user: i for i, user in enumerate(unique_customers)}
product2idx = {prod: i for i, prod in enumerate(unique_products)}
cat2idx = {cat: i for i, cat in enumerate(unique_categories)}

prod2cat_map = {
    prod: cat2idx.get(details.get("Category"), 0) 
    for prod, details in product_details.items()
}

class NCFWithCategory(nn.Module):
    def __init__(self, num_users, num_items, num_categories, embedding_dim=16):
        super(NCFWithCategory, self).__init__()
        self.user_embedding = nn.Embedding(num_users, embedding_dim)
        self.item_embedding = nn.Embedding(num_items, embedding_dim)
        self.cat_embedding = nn.Embedding(num_categories, embedding_dim)
        
        self.fc_layers = nn.Sequential(
            nn.Linear(embedding_dim * 3, 32),
            nn.ReLU(),
            nn.Linear(32, 1),
            nn.Sigmoid()
        )

    def forward(self, user_indices, item_indices, cat_indices):
        u_emb = self.user_embedding(user_indices)
        i_emb = self.item_embedding(item_indices)
        c_emb = self.cat_embedding(cat_indices)
        x = torch.cat([u_emb, i_emb, c_emb], dim=-1)
        return self.fc_layers(x)

device = torch.device("cpu")
ncf_model = NCFWithCategory(
    len(user2idx), 
    len(product2idx), 
    len(cat2idx), 
    embedding_dim=16
).to(device)

if os.path.exists("ncf_model.pt"):
    ncf_model.load_state_dict(torch.load("ncf_model.pt", map_location=device))
ncf_model.eval()

# ==========================================================
# 3. RECOMMENDATION ENGINE LOGIC
# ==========================================================
def popularity_recommend(top_n=25):
    return popular_products[:top_n]

def popular_now_recommend(target_time=None, top_n=25):
    if target_time is None:
        hour = datetime.now().hour
    elif isinstance(target_time, int):
        hour = target_time
    elif isinstance(target_time, str):
        try:
            hour = pd.to_datetime(target_time, format='%H:%M:%S').hour
        except Exception:
            hour = datetime.now().hour
    else:
        hour = datetime.now().hour
        
    return hourly_popularity.get(hour, popular_products)[:top_n]

def ncf_recommend(customer_id, top_n=25):
    if customer_id not in user2idx:
        return []
    
    user_idx = user2idx[customer_id]
    purchased = purchased_history.get(customer_id, set())
    
    candidate_products = [p for p in unique_products if p not in purchased]
    candidate_indices = [product2idx[p] for p in candidate_products]
    candidate_cat_indices = [prod2cat_map.get(p, 0) for p in candidate_products]
    
    u_tensor = torch.tensor([user_idx] * len(candidate_indices), dtype=torch.long)
    i_tensor = torch.tensor(candidate_indices, dtype=torch.long)
    c_tensor = torch.tensor(candidate_cat_indices, dtype=torch.long)

    with torch.no_grad():
        scores = ncf_model(u_tensor, i_tensor, c_tensor).squeeze().numpy()
        
    top_indices = scores.argsort()[::-1][:top_n]
    return [candidate_products[i] for i in top_indices]

def content_recommend(product_name, top_n=25):
    if product_name not in product_to_tfidf_idx:
        return []
    
    idx = product_to_tfidf_idx[product_name]
    target_vec = tfidf_matrix[idx]
    
    sim_scores = cosine_similarity(target_vec, tfidf_matrix).flatten()
    top_indices = sim_scores.argsort()[::-1][1:top_n + 1]
    return [product_series[i] for i in top_indices]

def hybrid_recommend(product_name, customer_id=None, target_time=None, top_n=25, candidate_k=25):
    weights = {'popular': 0.2, 'ncf': 0.4, 'content': 0.4}
    
    recs = {
        'popular': popular_now_recommend(target_time=target_time, top_n=candidate_k),
        'ncf': ncf_recommend(customer_id, top_n=candidate_k) if customer_id else [],
        'content': content_recommend(product_name, top_n=candidate_k) if product_name else []
    }

    combined_scores = {}
    for model_name, product_list in recs.items():
        weight = weights[model_name]
        for rank, prod in enumerate(product_list):
            rank_score = (candidate_k - rank) / candidate_k
            combined_scores[prod] = combined_scores.get(prod, 0.0) + (weight * rank_score)

    if product_name in combined_scores:
        del combined_scores[product_name]

    sorted_products = sorted(combined_scores.items(), key=lambda x: x[1], reverse=True)
    return [prod for prod, score in sorted_products[:top_n]]

# ==========================================================
# 4. SCORING & ROUTES
# ==========================================================
def get_popular_score(product):
    if product in popular_products:
        rank = popular_products.index(product)
        return max(0.0, 1.0 - (rank / len(popular_products)))
    return 0.0

def get_ncf_score(customer_id, product):
    if customer_id not in user2idx or product not in product2idx:
        return None
    user_idx = user2idx[customer_id]
    prod_idx = product2idx[product]
    cat_idx = prod2cat_map.get(product, 0)
    
    u_tensor = torch.tensor([user_idx], dtype=torch.long)
    i_tensor = torch.tensor([prod_idx], dtype=torch.long)
    c_tensor = torch.tensor([cat_idx], dtype=torch.long)
    return ncf_model(u_tensor, i_tensor, c_tensor).item()

def get_content_score(reference_product, product):
    if reference_product in product_to_tfidf_idx and product in product_to_tfidf_idx:
        idx1 = product_to_tfidf_idx[reference_product]
        idx2 = product_to_tfidf_idx[product]
        return float(cosine_similarity(tfidf_matrix[idx1], tfidf_matrix[idx2])[0][0])
    return 0.0

ai_score.configure(
    popular_fn=get_popular_score,
    ncf_fn=get_ncf_score,
    content_fn=get_content_score
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
        "app_home.html",
        products=products,
        customers=customers,
        selected_customer=DEFAULT_CUSTOMER_ID,
        selected_product=None,
        popular_recommendations=[],
        ncf_recommendations=[],
        content_recommendations=[],
        hybrid_recommendations=[],
        product_details=product_details
    )

@app.route("/recommend", methods=["POST"])
def recommend():
    selected_product = request.form.get("product")
    selected_customer = request.form.get("customer_id", DEFAULT_CUSTOMER_ID)
    customer_id = int(selected_customer) if selected_customer else None

    popular_recommendations = popularity_recommend()
    ncf_recommendations = ncf_recommend(customer_id) if customer_id else []
    content_recommendations = content_recommend(selected_product) if selected_product else []
    hybrid_recommendations = hybrid_recommend(selected_product, customer_id=customer_id)

    all_recs = set(popular_recommendations + ncf_recommendations + content_recommendations + hybrid_recommendations)
    
    # Updated line: passing selected_product
    update_product_details_ai(all_recs, customer_id=customer_id, reference_product=selected_product)

    return render_template(
        "app_recommend.html",
        products=products,
        customers=customers,
        selected_customer=customer_id,
        selected_product=selected_product,
        popular_recommendations=popular_recommendations,
        ncf_recommendations=ncf_recommendations,
        content_recommendations=content_recommendations,
        hybrid_recommendations=hybrid_recommendations,
        product_details=product_details
    )

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)