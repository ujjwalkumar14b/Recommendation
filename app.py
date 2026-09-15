from datetime import datetime
import os
import pandas as pd
import torch
import torch.nn as nn

from flask import Flask, render_template, request
from torch.utils.data import DataLoader, Dataset
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.feature_extraction.text import TfidfVectorizer

import ai_score
import xai

app = Flask(__name__, template_folder='.', static_folder='.', static_url_path='')

# ==========================================================
# LOAD DATA AND IN-MEMORY TRAINED MODELS / ARTIFACTS
# ==========================================================
df = pd.read_csv("cleaned_data.csv", encoding="latin1")

df["StockCode"] = df["StockCode"].astype('int32')
df["Quantity"] = df["Quantity"].astype('int32')
df["Price"] = df["Price"].astype('int32')
df["CustomerID"] = df["CustomerID"].astype('int32')

train_size = int(len(df) * 0.80)
train_df = df.iloc[:train_size].copy()

# 1. Popularity Artifacts
popular_products = train_df.groupby("Product")["Quantity"].sum().sort_values(ascending=False).index.tolist()

train_df_time = train_df.copy()
train_df_time['Hour'] = pd.to_datetime(train_df_time['Time'], format='%H:%M').dt.hour

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

# 2. User-Item Pivot Matrix
model_user_item = train_df.pivot_table(
    index="CustomerID", columns="Product", values="Quantity", aggfunc="sum", fill_value=0
)

# 3. Content-Based TF-IDF Artifacts
product_data = train_df[['Product']].drop_duplicates().reset_index(drop=True)
tfidf = TfidfVectorizer(stop_words='english')
tfidf_matrix = tfidf.fit_transform(product_data['Product'])
content_sim = cosine_similarity(tfidf_matrix)

model_content = pd.DataFrame(content_sim, index=product_data['Product'], columns=product_data['Product'])
model_content = model_content.astype('float32')
model_content.index = model_content.index.astype(object)
model_content.columns = model_content.columns.astype(object)

# ==========================================================
# INPUT & PRODUCT DETAILS
# ==========================================================
products = sorted(df["Product"].dropna().astype(str).unique().tolist())
customers = sorted(df["CustomerID"].dropna().astype(int).unique().tolist())
DEFAULT_CUSTOMER_ID = 17850

product_details = {}
for _, row in df.iterrows():
    product = str(row["Product"])
    if product not in product_details:
        product_details[product] = {
            "price": row["Price"],
            "stockcode": row["StockCode"],
        }

# ==========================================================
# RECOMMENDATION FUNCTIONS
# ==========================================================
def popularity_recommend(top_n=25):
    return list(popular_products[:top_n])

def popular_now_recommend(target_time=None, top_n=25):
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

unique_customers = train_df['CustomerID'].unique()
unique_products = df['Product'].unique()

user2idx = {user: i for i, user in enumerate(unique_customers)}
idx2user = {i: user for user, i in user2idx.items()}
product2idx = {prod: i for i, prod in enumerate(unique_products)}
idx2product = {i: prod for prod, i in product2idx.items()}

class RecDataset(Dataset):
    def __init__(self, df, user2idx, product2idx):
        self.users = torch.tensor([user2idx[u] for u in df['CustomerID'] if u in user2idx], dtype=torch.long)
        self.products = torch.tensor([product2idx[p] for p in df['Product'] if p in product2idx], dtype=torch.long)
        self.labels = torch.ones(len(self.users), dtype=torch.float32)

    def __len__(self):
        return len(self.users)

    def __getitem__(self, idx):
        return self.users[idx], self.products[idx], self.labels[idx]

train_filtered = train_df[train_df['CustomerID'].isin(user2idx) & train_df['Product'].isin(product2idx)]
train_dataset = RecDataset(train_filtered, user2idx, product2idx)
train_loader = DataLoader(train_dataset, batch_size=256, shuffle=True)

class NCF(nn.Module):
    def __init__(self, num_users, num_items, embedding_dim=32):
        super(NCF, self).__init__()
        self.user_embedding = nn.Embedding(num_users, embedding_dim)
        self.item_embedding = nn.Embedding(num_items, embedding_dim)
        
        self.fc_layers = nn.Sequential(
            nn.Linear(embedding_dim * 2, 64),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(64, 32),
            nn.ReLU(),
            nn.Linear(32, 1),
            nn.Sigmoid()
        )

    def forward(self, user_indices, item_indices):
        u_emb = self.user_embedding(user_indices)
        i_emb = self.item_embedding(item_indices)
        x = torch.cat([u_emb, i_emb], dim=-1)
        return self.fc_layers(x)

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
ncf_model = NCF(len(user2idx), len(product2idx), embedding_dim=32).to(device)

def ncf_recommend(customer_id, top_n=25):
    if customer_id not in user2idx:
        return []
    
    user_idx = user2idx[customer_id]
    purchased = set(model_user_item.loc[customer_id][model_user_item.loc[customer_id] > 0].index) if customer_id in model_user_item.index else set()
    
    candidate_products = [p for p in unique_products if p not in purchased]
    candidate_indices = [product2idx[p] for p in candidate_products]
    
    u_tensor = torch.tensor([user_idx] * len(candidate_indices), dtype=torch.long).to(device)
    i_tensor = torch.tensor(candidate_indices, dtype=torch.long).to(device)
    
    ncf_model.eval()
    with torch.no_grad():
        scores = ncf_model(u_tensor, i_tensor).squeeze().cpu().numpy()
        
    top_indices = scores.argsort()[::-1][:top_n]
    return [candidate_products[i] for i in top_indices]

def content_recommend(product_name, top_n=25):
    try:
        if product_name not in model_content.index:
            return []

        return (
            model_content[product_name]
            .sort_values(ascending=False)
            .iloc[1:top_n + 1]
            .index
            .tolist()
        )
    except Exception as e:
        print("Content Error:", e)
        return []

def hybrid_recommend(product_name, customer_id=None, target_time=None, top_n=25, candidate_k=25):
    try:
        weights = {'popular': 0.2, 'ncf': 0.4, 'content': 0.4}
        
        recs = {
            'popular': popular_now_recommend(target_time=target_time, top_n=candidate_k),
            'ncf': ncf_recommend(customer_id, top_n=candidate_k) if customer_id else [],
            'content': content_recommend(product_name, top_n=candidate_k)
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

    except Exception as e:
        print("Hybrid Error:", e)
        return []

# ==========================================================
# SCORING FUNCTIONS & AI CONFIGURATION
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
    
    u_tensor = torch.tensor([user_idx], dtype=torch.long).to(device)
    i_tensor = torch.tensor([prod_idx], dtype=torch.long).to(device)
    
    ncf_model.eval()
    with torch.no_grad():
        score = ncf_model(u_tensor, i_tensor).item()
    return score

def get_content_score(reference_product, product):
    if reference_product in model_content.index and product in model_content.columns:
        return float(model_content.loc[reference_product, product])
    return 0.0

ai_score.configure(
    popular_fn=get_popular_score,
    ncf_fn=get_ncf_score,
    content_fn=get_content_score
)

def update_product_details_ai(product_list, customer_id=None, reference_product=None):
    """Calculates AI score and explanation for each item and updates product_details directly."""
    for prod in product_list:
        if prod in product_details:
            score_res = ai_score.compute_ai_score(
                product=prod,
                customer_id=customer_id,
                reference_product=reference_product
            )
            product_details[prod]["ai_score"] = score_res["final_ai_score"]
            product_details[prod]["explanation"] = xai.explain(score_res)

# HOME
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

# RECOMMEND
@app.route("/recommend", methods=["POST"])
def recommend():
    selected_product = request.form.get("product")
    selected_customer = request.form.get("customer_id", DEFAULT_CUSTOMER_ID)
    customer_id = int(selected_customer) if selected_customer else None

    popular_recommendations = popularity_recommend()
    ncf_recommendations = ncf_recommend(customer_id) if customer_id else []
    content_recommendations = content_recommend(selected_product) if selected_product else []
    hybrid_recommendations = hybrid_recommend(selected_product, customer_id=customer_id)

    # Collect all recommended products to update details
    all_recs = set(popular_recommendations + ncf_recommendations + content_recommendations + hybrid_recommendations)
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

# RUN
if __name__ == "__main__":
    criterion = nn.BCELoss()
    optimizer = torch.optim.Adam(ncf_model.parameters(), lr=0.001)

    ncf_model.train()
    epochs = 5
    for epoch in range(epochs):
        total_loss = 0
        for users, items, labels in train_loader:
            users, items, labels = users.to(device), items.to(device), labels.to(device)
            optimizer.zero_grad()
            outputs = ncf_model(users, items).squeeze()
            loss = criterion(outputs, labels)
            loss.backward()
            optimizer.step()
            total_loss += loss.item()
        print(f"Epoch {epoch+1}/{epochs} - Loss: {total_loss/len(train_loader):.4f}")

    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)