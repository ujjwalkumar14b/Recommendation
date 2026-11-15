# PickPerfect
PickPerfect is MERN-based ecommerce website which allow users to browse all products, register and login, recommend top-25 products based on searched product and its transaction history, and add product to cart and checkout. Recommendation is based on time aware popularity model, collaborative model and content-based model.

## Architecture
- HomePage (Contains all products) 
- Login and Register Page (For authentication)
- Recommendation Page (Recommend top 25 products and its XAI results)
- Cart Page and Checkout Page (User checkout)

## Requirements
- MongoDB, Express.js, React.js, Node.js
- Python 3.12 
- NumPy, Pandas, Matplotlib, Seaborn, Scikit-Learn, Flask
- Bootstrap Framework

## Installation Setup

### 1. Recommendation Backend
```
py -3.12 -m venv .venv  
.\.venv\Scripts\Activate.ps1  
cd backend
pip install -r requirements.txt
python -m recommendation.app
```

### 2. Backend
```
cd backend
npm install
npm run dev
```

### 3. Frontend
```
cd frontend
npm install
npm run dev
```

## API overview
Express (`http://localhost:5001/api`):

- `POST /auth/register`
- `POST /auth/login` 
- `POST /recommendations`
- `POST /cart/items`
- `POST /orders`
- `GET /auth/me`
- `GET /products`
- `GET /cart`
- `PATCH /cart/items/:stockCode`
- `DELETE /cart/items/:stockCode`
