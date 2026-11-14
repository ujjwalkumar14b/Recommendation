import { createContext, useContext, useMemo, useState } from "react";
import { api } from "../api.js";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [customer, setCustomer] = useState(() => {
    try {
      return JSON.parse(localStorage.getItem("pickperfect-customer") || "null");
    } catch {
      return null;
    }
  });

  async function authenticate(path, credentials) {
    const result = await api(path, {
      method: "POST",
      body: JSON.stringify(credentials),
    });
    localStorage.setItem("pickperfect-token", result.token);
    localStorage.setItem("pickperfect-customer", JSON.stringify(result.customer));
    setCustomer(result.customer);
    return result.customer;
  }

  function logout() {
    localStorage.removeItem("pickperfect-token");
    localStorage.removeItem("pickperfect-customer");
    setCustomer(null);
  }

  const value = useMemo(
    () => ({
      customer,
      isAuthenticated: Boolean(customer),
      login: (credentials) => authenticate("/auth/login", credentials),
      register: (credentials) => authenticate("/auth/register", credentials),
      logout,
    }),
    [customer]
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  return useContext(AuthContext);
}
