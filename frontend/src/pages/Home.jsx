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

  const pageCount = Math.ceil(result.total / result.perPage);

  return (
    <>
      <section className="hero-wrap">
        <div className="container">
          <div className="hero-panel row g-0 align-items-stretch">
            <div className="col-lg-7 hero-copy">
              <div className="eyebrow"><span className="eyebrow-dot" /> GOOD FINDS, BETTER FIT</div>
              <h1>Find the little things<br />that feel <span>just right.</span></h1>
              <p>
                Discover thoughtful finds, then let our recommendation engine uncover
                something you might love next.
              </p>
              <div className="d-flex flex-wrap gap-3 align-items-center">
                <a className="btn btn-dark btn-pill" href="#collection">
                  Explore the collection <i className="bi bi-arrow-down-right ms-2" />
                </a>
                <span className="hero-proof"><i className="bi bi-stars me-1" /> Recommendations you can understand</span>
              </div>
            </div>
            <div className="col-lg-5 hero-art">
              <div className="hero-orbit orbit-one" />
              <div className="hero-orbit orbit-two" />
              <div className="hero-object hero-object-main"><i className="bi bi-flower1" /></div>
              <div className="hero-object hero-object-small"><i className="bi bi-cup-hot" /></div>
              <div className="hero-sticker"><i className="bi bi-sparkle" /> picked for you</div>
              <div className="hero-caption">Everyday pieces<br />with a little extra.</div>
            </div>
          </div>
          <div className="value-strip row g-0">
            <div className="col-md-4 value-item"><span>01</span><div><strong>Thoughtful discovery</strong><small>Explore a curated catalogue</small></div></div>
            <div className="col-md-4 value-item"><span>02</span><div><strong>Made personal</strong><small>Recommendations from your search</small></div></div>
            <div className="col-md-4 value-item"><span>03</span><div><strong>Clear by design</strong><small>See why a product was suggested</small></div></div>
          </div>
        </div>
      </section>

      <section className="collection-section container" id="collection">
        <div className="section-heading d-flex flex-column flex-md-row align-items-md-end justify-content-between gap-3">
          <div>
            <span className="section-kicker">THE COLLECTION</span>
            <h2>Everyday favourites</h2>
            <p>Distinct finds from the PickPerfect catalogue.</p>
          </div>
          <span className="catalog-count">{result.total.toLocaleString("en-IN")} products</span>
        </div>
        {notice && <div className="toast-note"><i className="bi bi-check-circle me-2" />{notice}</div>}
        {error && <div className="alert alert-danger">{error}</div>}
        {loading ? (
          <div className="loading-state"><span className="spinner-border spinner-border-sm me-2" />Loading the collection…</div>
        ) : (
          <>
            <div className="row g-4">
              {result.items.map((product) => (
                <div className="col-6 col-md-4 col-xl-3" key={product.stockCode}>
                  <ProductCard product={product} onAdded={onAdded} />
                </div>
              ))}
            </div>
            {!result.items.length && <div className="empty-state">No products found in the catalogue.</div>}
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
        <div className="recommendation-callout">
          <div className="callout-star"><i className="bi bi-stars" /></div>
          <div><h3>Looking for something in particular?</h3><p>Search a product above and see your top 25 explainable recommendations.</p></div>
          <Link to="/register" className="btn btn-outline-dark btn-pill ms-md-auto">Join PickPerfect <i className="bi bi-arrow-up-right ms-2" /></Link>
        </div>
      </section>
    </>
  );
}
