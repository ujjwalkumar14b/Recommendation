import { useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, formatPrice } from "../api.js";
import { useCart } from "../context/CartContext.jsx";

export default function Checkout() {
  const { cart = { items: [], subtotal: 0 }, refreshCart } = useCart();
  const navigate = useNavigate();
  const checkoutKey = useRef(crypto.randomUUID());
  const [shipping, setShipping] = useState({
    name: "", address: "", city: "", region: "", postalCode: "", phone: "",
  });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [order, setOrder] = useState(null);

  function update(event) {
    setShipping({ ...shipping, [event.target.name]: event.target.value });
  }

  async function submit(event) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const result = await api("/orders", {
        method: "POST",
        body: JSON.stringify({ shipping, checkoutKey: checkoutKey.current }),
      });
      setOrder(result?.order);
      await refreshCart();
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setBusy(false);
    }
  }

  if (order) {
    return (
      <section className="container checkout-page">
        <div className="order-success">
          <div className="success-mark"><i className="bi bi-check-lg" /></div>
          <span className="section-kicker">ORDER CONFIRMED</span>
          <h1>Thank you for your order.</h1>
          <p>Your order <strong>#{order?._id ? order._id.slice(-8).toUpperCase() : "12345678"}</strong> is placed. Your payment is due on delivery.</p>
          <div className="success-total">Order total <strong>{formatPrice(order?.total)}</strong></div>
          <button className="btn btn-dark btn-pill mt-4" onClick={() => navigate("/")}>Back to the collection <i className="bi bi-arrow-right ms-2" /></button>
        </div>
      </section>
    );
  }

  if (!cart?.items?.length) {
    return (
      <section className="container checkout-page">
        <div className="empty-panel"><i className="bi bi-bag" /><h2>Your bag is empty.</h2><p>Add something to your bag before checking out.</p><Link className="btn btn-dark btn-pill" to="/">Browse the collection</Link></div>
      </section>
    );
  }

  return (
    <section className="container checkout-page">
      <div className="breadcrumb-line"><Link to="/cart">Your bag</Link><i className="bi bi-chevron-right" /><span>Checkout</span></div>
      <div className="checkout-heading"><span className="section-kicker">ALMOST YOURS</span><h1>Delivery details</h1><p>Where should we bring your thoughtful finds?</p></div>
      {error && <div className="alert alert-danger">{error}</div>}
      <div className="row g-5">
        <div className="col-lg-7">
          <form className="checkout-form" onSubmit={submit}>
            <div className="row g-3">
              <div className="col-12"><label className="form-label" htmlFor="shipping-name">Full name</label><input id="shipping-name" className="form-control auth-input" name="name" autoComplete="name" value={shipping.name} onChange={update} required /></div>
              <div className="col-12"><label className="form-label" htmlFor="shipping-address">Street address</label><input id="shipping-address" className="form-control auth-input" name="address" autoComplete="street-address" value={shipping.address} onChange={update} required /></div>
              <div className="col-md-6"><label className="form-label" htmlFor="shipping-city">City</label><input id="shipping-city" className="form-control auth-input" name="city" autoComplete="address-level2" value={shipping.city} onChange={update} required /></div>
              <div className="col-md-6"><label className="form-label" htmlFor="shipping-region">State / region</label><input id="shipping-region" className="form-control auth-input" name="region" autoComplete="address-level1" value={shipping.region} onChange={update} required /></div>
              <div className="col-md-6"><label className="form-label" htmlFor="shipping-postal">Postal code</label><input id="shipping-postal" className="form-control auth-input" name="postalCode" autoComplete="postal-code" value={shipping.postalCode} onChange={update} required /></div>
              <div className="col-md-6"><label className="form-label" htmlFor="shipping-phone">Phone</label><input id="shipping-phone" className="form-control auth-input" name="phone" type="tel" autoComplete="tel" value={shipping.phone} onChange={update} required /></div>
            </div>
            <div className="payment-option mt-4"><span className="payment-radio" /><div><strong>Cash on delivery</strong><small>Pay when your order arrives.</small></div><i className="bi bi-cash-coin ms-auto" /></div>
            <button className="btn btn-dark btn-pill w-100 mt-4" disabled={busy}>{busy ? "Placing your order…" : `Place order · ${formatPrice(cart?.subtotal)}`}<i className="bi bi-arrow-right ms-2" /></button>
          </form>
        </div>
        <div className="col-lg-5">
          <aside className="order-summary checkout-summary">
            <span className="section-kicker">IN YOUR BAG</span>
            {cart?.items?.map((item) => (
              <div className="checkout-item" key={item?.stockCode ?? Math.random()}>
                <span className="checkout-item-count">{item?.quantity ?? 1}</span>
                <span>{item?.productName}</span>
                <strong>{formatPrice((item?.price ?? 0) * (item?.quantity ?? 0))}</strong>
              </div>
            ))}
            <div className="summary-total mt-3"><span>Total due on delivery</span><strong>{formatPrice(cart?.subtotal ?? 0)}</strong></div>
          </aside>
        </div>
      </div>
    </section>
  );
}
