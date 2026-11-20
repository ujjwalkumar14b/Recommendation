import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../api.js";
import { useAuth } from "../context/AuthContext.jsx";
import { useCart } from "../context/CartContext.jsx";

export default function Navbar() {
  const { customer, logout } = useAuth();
  const { cart } = useCart();
  const navigate = useNavigate();
  const [query, setQuery] = useState("");
  const [suggestions, setSuggestions] = useState([]);
  const [searchError, setSearchError] = useState("");

  useEffect(() => {
    const value = query.trim();
    if (value.length < 2) {
      setSuggestions([]);
      setSearchError("");
      return undefined;
    }
    const timer = window.setTimeout(async () => {
      try {
        const result = await api(`/products?search=${encodeURIComponent(value)}&perPage=8`);
        setSuggestions(result.items);
        setSearchError("");
      } catch (error) {
        setSearchError(error.message);
      }
    }, 250);
    return () => window.clearTimeout(timer);
  }, [query]);

  function search(event) {
    event.preventDefault();
    const product = suggestions.find((item) => item.name.toLowerCase() === query.trim().toLowerCase())
      || (suggestions.length === 1 ? suggestions[0] : null);
    if (product) {
      setQuery(product.name);
      setSuggestions([]);
      setSearchError("");
      navigate(`/recommendations?product=${encodeURIComponent(product.name)}`);
      return;
    }
    setSearchError(
      suggestions.length
        ? "Choose a product from the suggestions so we can find its closest matches."
        : "Search for a product from the catalogue first."
    );
  }

  function chooseSuggestion(product) {
    setQuery(product.name);
    setSuggestions([]);
    setSearchError("");
    navigate(`/recommendations?product=${encodeURIComponent(product.name)}`);
  }

  return (
    <nav className="navbar navbar-expand-lg navbar-light navbar-glass sticky-top">
      <div className="container py-2">
        <Link className="navbar-brand brand-logo" to="/">PickPerfect</Link>
        <button
          className="navbar-toggler border-0 shadow-none"
          type="button"
          data-bs-toggle="collapse"
          data-bs-target="#storeNavigation"
          aria-controls="storeNavigation"
          aria-expanded="false"
          aria-label="Toggle navigation"
        >
          <i className="bi bi-list fs-2" />
        </button>
        <div className="collapse navbar-collapse" id="storeNavigation">
          <form className="nav-search position-relative mx-lg-auto my-3 my-lg-0" onSubmit={search}>
            <i className="bi bi-search search-symbol" />
            <input
              aria-label="Search a product for recommendations"
              className="form-control search-input"
              placeholder="Search a product for recommendations..."
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              onFocus={() => setSearchError("")}
            />
            <button type="submit" className="btn btn-search" aria-label="Get recommendations">
              <i className="bi bi-arrow-up-right" />
            </button>
            {(suggestions.length > 0 || searchError) && (
              <div className="search-popover">
                {suggestions.map((product) => (
                  <button
                    className="suggestion-row"
                    key={product.stockCode}
                    type="button"
                    onClick={() => chooseSuggestion(product)}
                  >
                    <span className="suggestion-icon"><i className="bi bi-box-seam" /></span>
                    <span className="text-truncate">{product.name}</span>
                    <i className="bi bi-arrow-up-right ms-auto" />
                  </button>
                ))}
                {searchError && <p className="search-message">{searchError}</p>}
              </div>
            )}
          </form>
          <div className="nav-actions d-flex align-items-center gap-2 ms-lg-3">
            {customer ? (
              <>
                <Link className="btn btn-link nav-login" to="/cart">Cart ({cart.itemCount || 0})</Link>
                <Link className="btn btn-link nav-login">{customer.name.split(" ")[0]}</Link>
                <button className="btn btn-link nav-login" type="button" onClick={() => { logout(); navigate("/"); }}>Sign out</button>
              </>
            ) : (
              <>
                <Link className="btn btn-link nav-login" to="/cart">Cart</Link>
                <Link className="btn btn-link nav-login" to="/login">Log in</Link>
                <Link className="btn btn-link nav-login" to="/register">Register</Link>
              </>
            )}
          </div>
        </div>
      </div>
    </nav>
  );
}
