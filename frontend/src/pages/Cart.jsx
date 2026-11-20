import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, formatPrice } from "../api.js";
import { useCart } from "../context/CartContext.jsx";

export default function Cart() {
  const { cart, setCart, error } = useCart();
  const navigate = useNavigate();
  const [actionError, setActionError] = useState("");

  async function updateQuantity(item, quantity) {
    setActionError("");
    try {
      const updated = await api(`/cart/items/${encodeURIComponent(item.stockCode)}`, {
        method: "PATCH",
        body: JSON.stringify({ quantity: Number(quantity) }),
      });
      setCart(updated);
    } catch (requestError) {
      setActionError(requestError.message);
    }
  }

  async function removeItem(item) {
    setActionError("");
    try {
      const updated = await api(`/cart/items/${encodeURIComponent(item.stockCode)}`, {
        method: "DELETE",
      });
      setCart(updated);
    } catch (requestError) {
      setActionError(requestError.message);
    }
  }

  return (
    <section className="container bag-page">
      <div className="page-title-row"><div className="text-center"><h1>Your bag contains {cart.itemCount || 0} products</h1></div></div>
      {error && <div className="alert alert-danger">{error}</div>}
      {actionError && <div className="alert alert-danger">{actionError}</div>}
      {cart?.items?.length ? (
        <div className="row g-5">
          <div className="col-lg-8">
            <div className="bag-items">
              {cart.items.map((item) => (
                <article className="bag-item" key={item?.stockCode ?? Math.random()}>
                  <div className="bag-item-art"><i className="bi bi-box-seam" /></div>
                  <div className="bag-item-details">
                    <span className="product-code">PRODUCT #{item?.stockCode}</span>
                    <h2>{item.productName}</h2>
                    <span className="bag-item-price">{formatPrice(item?.price)}</span>
                  </div>
                  <div className="bag-item-controls">
                    <label className="visually-hidden" htmlFor={`quantity-${item?.stockCode}`}>Quantity</label>
                    <select id={`quantity-${item?.stockCode}`} className="form-select quantity-select" value={item?.quantity ?? 1} onChange={(event) => updateQuantity(item, event.target.value)}>
                      {Array.from({ length: 99 }, (_, index) => index + 1).map((quantity) => <option key={quantity} value={quantity}>{quantity}</option>)}
                    </select>
                    <button className="remove-button" type="button" onClick={() => removeItem(item)}>Remove</button>
                  </div>
                  <strong className="bag-line-total">{formatPrice((item?.price ?? 0) * (item?.quantity ?? 0))}</strong>
                </article>
              ))}
            </div>
          </div>
          <div className="col-lg-4">
            <aside className="order-summary">
              <span className="section-kicker">ORDER SUMMARY</span>
              <div className="summary-row"><span>Subtotal</span><strong>{formatPrice(cart?.subtotal ?? 0)}</strong></div>
              <div className="summary-row"><span>Shipping</span><strong>Calculated at checkout</strong></div>
              <div className="summary-total"><span>Total</span><strong>{formatPrice(cart?.subtotal ?? 0)}</strong></div>
              <p className="summary-note"><i className="bi bi-shield-check me-2" />Payment is collected on delivery.</p>
              <button className="btn btn-dark btn-pill w-100" onClick={() => navigate("/checkout")}>
                Continue to checkout <i className="bi bi-arrow-right ms-2" />
              </button>
            </aside>
          </div>
        </div>
      ) : (
        <div className="empty-panel bag-empty">
          <i className="bi bi-bag" />
          <h2>Your bag is taking a little breather.</h2>
          <p>When you find something you love, it will be waiting here.</p>
          <Link to="/" className="btn btn-dark btn-pill">Explore the collection <i className="bi bi-arrow-right ms-2" /></Link>
        </div>
      )}
    </section>
  );
}
