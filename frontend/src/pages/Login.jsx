import { useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext.jsx";

export default function Login() {
  const { login } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const [customerId, setCustomerId] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(event) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      await login({ customerId, password });
      navigate(location.state?.from?.pathname || "/", { replace: true });
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="container text-center">
      <div className="auth-card">
        <span className="section-kicker">WELCOME BACK</span>
        <h1>Good to see you.</h1>
        {error && <div className="alert alert-danger py-2">{error}</div>}
        <form onSubmit={submit}>
          <label className="form-label" htmlFor="login-customer-id">CustomerID</label>
          <input
            id="login-customer-id"
            className="form-control form-control-lg auth-input"
            type="number"
            min="1"
            step="1"
            autoComplete="username"
            placeholder="Enter your CustomerID"
            value={customerId}
            onChange={(event) => setCustomerId(event.target.value)}
            required
          />
          <label className="form-label mt-3" htmlFor="login-password">Password</label>
          <input
            id="login-password"
            className="form-control form-control-lg auth-input"
            type="password"
            autoComplete="current-password"
            placeholder="At least 8 characters"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            required
          />
          <button className="btn btn-dark btn-pill w-100 mt-4" disabled={busy}>
            {busy ? "Signing in…" : "Sign in"} <i className="bi bi-arrow-right ms-2" />
          </button>
        </form>
        <div className="auth-switch">New to PickPerfect? <Link to="/register">Create an account</Link></div>
      </div>
    </section>
  );
}
