import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api } from "../api.js";
import ProductCard from "../components/ProductCard.jsx";
import { useCart } from "../context/CartContext.jsx";

export default function Recommendations() {
  const [searchParams] = useSearchParams();
  const product = searchParams.get("product") || "";
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const { setCart } = useCart();

  useEffect(() => {
    let active = true;
    setLoading(true);
    setData(null);
    api("/recommendations", { method: "POST", body: JSON.stringify({ product }) })
      .then((result) => { if (active) { setData(result); setError(""); } })
      .catch((requestError) => { if (active) setError(requestError.message); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [product]);

  function onAdded(cart) {
    setCart(cart);
    setNotice("Added to your bag");
    window.setTimeout(() => setNotice(""), 2200);
  }

  return (
    <section className="recommend-page container">
      <div className="breadcrumb-line"><Link to="/">Home</Link><i className="bi bi-chevron-right" /><span>Recommendations</span></div>
      <div className="recommend-intro">
        <span className="section-kicker"><i className="bi bi-stars me-2" />PERSONALIZED DISCOVERY</span>
        <h1>Your next great find.</h1>
        <p>
          Inspired by <strong>{product || "your search"}</strong>. Each suggestion includes a clear
          explanation of the signals that shaped its match.
        </p>
      </div>
      {notice && <div className="toast-note"><i className="bi bi-check-circle me-2" />{notice}</div>}
      {loading && <div className="loading-state"><span className="spinner-border spinner-border-sm me-2" />Finding your best matches…</div>}
      {!loading && error && (
        <div className="empty-panel">
          <i className="bi bi-search" />
          <h2>We couldn't find those picks.</h2>
          <p>{error}</p>
          <Link className="btn btn-dark btn-pill" to="/">Search the catalogue</Link>
        </div>
      )}
      {!loading && data && (
        <>
          <div className="result-bar">
            <div><strong>{data.recommendations.length} recommendations</strong><span>Ranked by the hybrid recommendation model</span></div>
            <span className="model-chip"><i className="bi bi-cpu me-1" /> HYBRID · TOP 25</span>
          </div>
          {data.recommendations.length ? (
            <div className="row g-4">
              {data.recommendations.map((item, index) => (
                <div className="col-6 col-md-4 col-xl-3" key={`${item.stockCode}-${index}`}>
                  <ProductCard product={item} recommendation onAdded={onAdded} />
                </div>
              ))}
            </div>
          ) : (
            <div className="empty-state">There aren't any recommendations for this product yet.</div>
          )}
        </>
      )}
    </section>
  );
}
