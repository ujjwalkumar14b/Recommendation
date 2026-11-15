export async function api(path, options = {}) {
  const token = localStorage.getItem("pickperfect-token");
  const response = await fetch(path.startsWith("/api") ? path : `/api${path}`, {
    ...options,
    headers: {
      ...(options.body ? { "content-type": "application/json" } : {}),
      ...(token ? { authorization: `Bearer ${token}` } : {}),
      ...options.headers,
    },
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(body.error || `Request failed (${response.status})`);
  }
  return body;
}

export function formatPrice(value) {
  const numericValue = Number(value);
  const safeValue = Number.isNaN(numericValue) ? 0 : numericValue;

  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 2,
  }).format(safeValue);
}
