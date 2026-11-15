import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api.js";
import ProductCard from "../components/ProductCard.jsx";
import { useCart } from "../context/CartContext.jsx";

export default function Home() {
  const [result, setResult] = useState({ items: [], total: 0, page: 1, perPage: 24 });
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const { setCart } = useCart();

  useEffect(() => {
    let active = true;
    setLoading(true);
    api(`/products?page=${page}&perPage=24`)
      .then((data) => {
        if (active) {
          setResult(data);
          setError("");
        }
      })
      .catch((requestError) => { if (active) setError(requestError.message); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [page]);

  function onAdded(cart) {
    setCart(cart);
    setNotice("Added to your bag");
    window.setTimeout(() => setNotice(""), 2200);
  }

  // Safely calculate page count with optional chaining and fallback
  const pageCount = Math.ceil((result?.total ?? 0) / (result?.perPage ?? 24));

  return (
    <>
      <section className="collection-section container" id="collection">
        <div className="section-heading d-flex flex-column flex-md-row align-items-md-end justify-content-between gap-3">
          <div>
            <span className="section-kicker">THE COLLECTION</span>
          </div>
          <span className="catalog-count">{(result?.total ?? 0).toLocaleString("en-IN")} products</span>
        </div>
        {notice && <div className="toast-note"><i className="bi bi-check-circle me-2" />{notice}</div>}
        {error && <div className="alert alert-danger">{error}</div>}
        {loading ? (
          <div className="loading-state"><span className="spinner-border spinner-border-sm me-2" />Loading the collection…</div>
        ) : (
          <>
            <div className="row g-4">
              {result?.items?.map((product, index) => (
                <div className="col-6 col-md-4 col-xl-3" key={product?.stockCode ?? index}>
                  <ProductCard product={product} onAdded={onAdded} />
                </div>
              ))}
            </div>
            {!result?.items?.length && <div className="empty-state">No products found in the catalogue.</div>}
            {pageCount > 1 && (
              <nav className="catalog-pagination" aria-label="Product pages">
                <button className="btn btn-page" disabled={page === 1} onClick={() => setPage(page - 1)}>
                  <i className="bi bi-arrow-left" /> Previous
                </button>
                <span>Page {page} of {pageCount}</span>
                <button className="btn btn-page" disabled={page >= pageCount} onClick={() => setPage(page + 1)}>
                  Next <i className="bi bi-arrow-right" />
                </button>
              </nav>
            )}
          </>
        )}
      </section>
    </>
  );
}
