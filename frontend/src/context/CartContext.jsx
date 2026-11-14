import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { api } from "../api.js";
import { useAuth } from "./AuthContext.jsx";

const emptyCart = { items: [], itemCount: 0, subtotal: 0 };
const CartContext = createContext(null);

export function CartProvider({ children }) {
  const { customer } = useAuth();
  const [cart, setCart] = useState(emptyCart);
  const [error, setError] = useState("");

  const refreshCart = useCallback(async () => {
    if (!customer) {
      setCart(emptyCart);
      setError("");
      return;
    }
    try {
      const result = await api("/cart");
      setCart(result);
      setError("");
    } catch (requestError) {
      setError(requestError.message);
    }
  }, [customer]);

  useEffect(() => {
    refreshCart();
  }, [refreshCart]);

  const value = useMemo(
    () => ({ cart, setCart, refreshCart, error }),
    [cart, refreshCart, error]
  );
  return <CartContext.Provider value={value}>{children}</CartContext.Provider>;
}

export function useCart() {
  return useContext(CartContext);
}
