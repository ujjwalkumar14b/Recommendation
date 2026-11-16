import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext.jsx";

export default function Register() {
  const { register } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState({ name: "", email: "", customerId: "", password: "" });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  function update(event) {
    setForm({ ...form, [event.target.name]: event.target.value });
  }

  async function submit(event) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      await register(form);
      navigate("/");
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="container text-center">
      <div className="auth-card">
        <span className="section-kicker">JOIN PICKPERFECT</span>
        <h1>Make it personal.</h1>
        {error && <div className="alert alert-danger py-2">{error}</div>}
        <form onSubmit={submit}>
          <label className="form-label" htmlFor="register-name">Your name</label>
          <input id="register-name" className="form-control auth-input" name="name" autoComplete="name" value={form.name} onChange={update} minLength="2" maxLength="80" required />
          <label className="form-label mt-3" htmlFor="register-email">Email address</label>
          <input id="register-email" className="form-control auth-input" name="email" type="email" autoComplete="email" value={form.email} onChange={update} required />
          <label className="form-label mt-3" htmlFor="register-customer-id">CustomerID</label>
          <input id="register-customer-id" className="form-control auth-input" name="customerId" type="number" min="1" step="1" autoComplete="username" placeholder="Choose a unique number" value={form.customerId} onChange={update} required />
          <label className="form-label mt-3" htmlFor="register-password">Password</label>
          <input id="register-password" className="form-control auth-input" name="password" type="password" minLength="8" maxLength="128" autoComplete="new-password" value={form.password} onChange={update} required />
          <button className="btn btn-dark btn-pill w-100 mt-4" disabled={busy}>
            {busy ? "Creating account…" : "Create account"} <i className="bi bi-arrow-right ms-2" />
          </button>
        </form>
        <div className="auth-switch">Already have an account? <Link to="/login">Sign in</Link></div>
      </div>
    </section>
  );
}
