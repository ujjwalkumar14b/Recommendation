import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, formatPrice } from "../api.js";
import { useAuth } from "../context/AuthContext.jsx";

const icons = ["bi-lamp", "bi-flower1", "bi-cup-hot", "bi-gift", "bi-house-heart"];

function hueFromCode(code) {
  return [...String(code)].reduce((value, char) => value + char.charCodeAt(0), 0) % 360;
}

export default function ProductCard({ product, onAdded, recommendation = false }) {
  if (!product) {
    return null;
  }
  const { isAuthenticated } = useAuth();
  const navigate = useNavigate();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [added, setAdded] = useState(false);
  const hue = hueFromCode(product.stockCode);

  async function addToCart() {
    if (!isAuthenticated) {
      navigate("/login");
      return;
    }
    setBusy(true);
    setError("");
    try {
      const result = await api("/cart/items", {
        method: "POST",
        body: JSON.stringify({
          productName: product.name,
          stockCode: String(product.stockCode),
          quantity: 1,
        }),
      });
      onAdded?.(result);
      setAdded(true);
      window.setTimeout(() => setAdded(false), 1800);
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <article className="product-card h-100">
      <div className="product-art" style={{ "--product-hue": hue }}>
        <span className="product-art-label">PICKPERFECT OBJECTS</span>
        <i className={`bi ${icons[hue % icons.length]} product-art-icon`} aria-hidden="true" />
        {recommendation && product.aiScore !== undefined && (
          <span className="match-pill"><i className="bi bi-stars" /> {product.aiScore}% match</span>
        )}
      </div>
      <div className="product-card-body">
        <div className="d-flex justify-content-between align-items-start gap-2">
          <h2 className="product-name" title={product.name}>{product.name}</h2>
          <span className="product-code">#{product.stockCode}</span>
        </div>
        <div className="product-card-bottom">
          <span className="product-price">{formatPrice(product.price)}</span>
          <button
            type="button"
            className="btn btn-add"
            onClick={addToCart}
            disabled={busy}
            aria-label={`Add ${product.name} to cart`}
          >
            <i className={`bi ${added ? "bi-check2" : "bi-plus-lg"}`} />
          </button>
        </div>
        {error && <p className="inline-error mb-0 mt-2">{error}</p>}
        {recommendation && product.explanation && (
          <details className="explanation-details mt-3">
            <summary><i className="bi bi-stars me-1" />Why this pick?</summary>
            <p className="xai-summary">{product.explanation.summary}</p>
            {product.explanation.reasons.map((reason) => (
              <div className="xai-reason" key={`${reason.label}-${reason.detail}`}>
                <i className="bi bi-check2-circle" />
                <span><strong>{reason.label}:</strong> {reason.detail}</span>
              </div>
            ))}
            {product.explanation.breakdown.length > 0 && (
              <div className="xai-breakdown">
                {product.explanation.breakdown.map((signal) => (
                  <div className="xai-signal" key={signal.key}>
                    <div className="d-flex justify-content-between">
                      <span>{signal.label} <small>({signal.weight}%)</small></span>
                      <span>{signal.score}/100</span>
                    </div>
                    <div className="signal-track">
                      <span style={{ width: `${signal.score}%` }} />
                    </div>
                  </div>
                ))}
              </div>
            )}
          </details>
        )}
        {!isAuthenticated && (
          <Link className="sign-in-hint" to="/login">Sign in to add to your bag</Link>
        )}
      </div>
    </article>
  );
}
