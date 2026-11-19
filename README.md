# PickPerfect
PickPerfect is ecommerce website which allow users to browse all products, register and login, recommend top-25 products based on searched product and its transaction history, and add product to cart and checkout. Recommendation is based on time aware popularity model, collaborative model and content-based model.

## Website Link
Frontend: [https://recommendation-1-91vl.onrender.com](https://recommendation-1-91vl.onrender.com)
Backend: [https://recommendation-backend-uas7.onrender.com](https://recommendation-backend-uas7.onrender.com)
ML Model: [https://pickperfect-xy7l.onrender.com](https://pickperfect-xy7l.onrender.com)


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

## Author
Ujjwal Kumar
GitHub: [https://github.com/ujjwalkumar14b](https://github.com/ujjwalkumar14b)
