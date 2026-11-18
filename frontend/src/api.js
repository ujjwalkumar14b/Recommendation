export async function api(path, options = {}) {
  const token = localStorage.getItem("pickperfect-token");
  const baseUrl = import.meta.env.VITE_BACKEND_URL || "";  
  const formattedPath = path.startsWith("/api") ? path : `/api${path}`;
  const url = `${baseUrl}${formattedPath}`;

  const response = await fetch(url, {
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
