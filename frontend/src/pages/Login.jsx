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
          <input className="mt-3 form-control auth-input" type="number" name="customerId" autoComplete="username" value={customerId} onChange={(event) => setCustomerId(event.target.value)} placeholder="Enter your CustomerID" required />
          <input className="mt-3 form-control auth-input" type="password" name="password" autoComplete="current-password" value={password} onChange={(event) => setPassword(event.target.value)} placeholder="Enter your password" required />
        
          <button className="btn btn-dark btn-pill w-100 mt-4" disabled={busy}>
            {busy ? "Signing in…" : "Sign in"} <i className="bi bi-arrow-right ms-2" />
          </button>
        </form>
        <div className="auth-switch">New to PickPerfect? <Link to="/register">Create an account</Link></div>
      </div>
    </section>
  );
}
