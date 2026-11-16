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
          <input className="mt-3 form-control auth-input" type="text" name="name" autoComplete="name" value={form.name} onChange={update} placeholder="Enter your name" required />
          <input className="mt-3 form-control auth-input" type="email" name="email" autoComplete="email" value={form.email} onChange={update} placeholder="Enter your email" required />
          <input className="mt-3 form-control auth-input" type="number" name="customerId" autoComplete="username" value={form.customerId} onChange={update} placeholder="Choose a unique number" required />
          <input className="mt-3 form-control auth-input" type="password" name="password" autoComplete="new-password" value={form.password} onChange={update} placeholder="Enter a password" minLength="8" required />
          
          <button className="btn btn-dark btn-pill w-100 mt-4" disabled={busy}>
            {busy ? "Creating account…" : "Create account"} <i className="bi bi-arrow-right ms-2" />
          </button>
        </form>
        <div className="auth-switch">Already have an account? <Link to="/login">Sign in</Link></div>
      </div>
    </section>
  );
}
