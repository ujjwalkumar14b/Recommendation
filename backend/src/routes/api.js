import { Router } from "express";
import bcrypt from "bcryptjs";
import jwt from "jsonwebtoken";
import { randomUUID } from "node:crypto";
import rateLimit from "express-rate-limit";
import Customer from "../models/Customer.js";
import Cart from "../models/Cart.js";
import Order from "../models/Order.js";
import { optionalAuth, requireAuth } from "../middleware/auth.js";

const router = Router();
const recommenderUrl = process.env.RECOMMENDER_URL || "http://127.0.0.1:5000";
const authLimiter = rateLimit({
  windowMs: 15 * 60 * 1000,
  limit: 30,
  standardHeaders: "draft-7",
  legacyHeaders: false,
  message: { error: "Too many sign-in attempts. Please try again later." },
});

class UpstreamError extends Error {
  constructor(message, status = 502) {
    super(message);
    this.status = status;
  }
}

async function recommenderRequest(path, options = {}) {
  let response;
  try {
    response = await fetch(new URL(path, recommenderUrl), {
      ...options,
      headers: { "content-type": "application/json", ...options.headers },
      signal: AbortSignal.timeout(path === "/api/recommendations" ? 60000 : 15000),
    });
  } catch {
    throw new UpstreamError("The recommendation service is unavailable", 503);
  }

  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new UpstreamError(
      body.error || "The recommendation service could not complete the request",
      response.status >= 400 && response.status < 500 ? response.status : 502
    );
  }
  return body;
}

function asyncRoute(handler) {
  return (req, res, next) => Promise.resolve(handler(req, res, next)).catch(next);
}

function issueToken(customerId) {
  return jwt.sign({ customerId }, process.env.JWT_SECRET, { expiresIn: "7d" });
}

function publicCustomer(customer) {
  return {
    customerId: customer.customerId,
    name: customer.name,
    email: customer.email,
  };
}

function cartResponse(cart) {
  const items = cart?.items || [];
  return {
    items,
    itemCount: items.reduce((sum, item) => sum + item.quantity, 0),
    subtotal: items.reduce((sum, item) => sum + item.price * item.quantity, 0),
  };
}

router.post(
  "/auth/register",
  authLimiter,
  asyncRoute(async (req, res) => {
    const body = req.body || {};
    const { name, email, password } = body;
    const customerId = Number(body.customerId);
    if (
      typeof name !== "string" ||
      name.trim().length < 2 ||
      name.trim().length > 80 ||
      typeof email !== "string" ||
      !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim()) ||
      !Number.isSafeInteger(customerId) ||
      customerId <= 0 ||
      typeof password !== "string" ||
      password.length < 8 ||
      password.length > 128
    ) {
      return res.status(400).json({
        error: "Enter a valid name, email, positive CustomerID, and password of at least 8 characters",
      });
    }

    const normalizedEmail = email.trim().toLowerCase();
    const existing = await Customer.findOne({
      $or: [{ customerId }, { email: normalizedEmail }],
    }).select("customerId email");
    if (existing) {
      return res.status(409).json({
        error:
          existing.customerId === customerId
            ? "That CustomerID is already registered"
            : "That email address is already registered",
      });
    }

    const customer = await Customer.create({
      customerId,
      name: name.trim(),
      email: normalizedEmail,
      passwordHash: await bcrypt.hash(password, 12),
    });
    return res.status(201).json({
      token: issueToken(customer.customerId),
      customer: publicCustomer(customer),
    });
  })
);

router.post(
  "/auth/login",
  authLimiter,
  asyncRoute(async (req, res) => {
    const body = req.body || {};
    const customerId = Number(body.customerId);
    const { password } = body;
    if (!Number.isSafeInteger(customerId) || customerId <= 0 || typeof password !== "string") {
      return res.status(400).json({ error: "Enter your CustomerID and password" });
    }

    const customer = await Customer.findOne({ customerId }).select("+passwordHash");
    if (!customer || !(await bcrypt.compare(password, customer.passwordHash))) {
      return res.status(401).json({ error: "CustomerID or password is incorrect" });
    }
    return res.json({
      token: issueToken(customer.customerId),
      customer: publicCustomer(customer),
    });
  })
);

router.get("/auth/me", requireAuth, (req, res) => {
  res.json({ customer: publicCustomer(req.customer) });
});

router.get(
  "/products",
  asyncRoute(async (req, res) => {
    const page = Math.max(1, Number.parseInt(req.query.page, 10) || 1);
    const perPage = Math.min(60, Math.max(1, Number.parseInt(req.query.perPage, 10) || 24));
    const query = new URLSearchParams({
      page: String(page),
      per_page: String(perPage),
      query: typeof req.query.search === "string" ? req.query.search.trim() : "",
    });
    return res.json(await recommenderRequest(`/api/products?${query}`));
  })
);

router.post(
  "/recommendations",
  optionalAuth,
  asyncRoute(async (req, res) => {
    const product = typeof req.body?.product === "string" ? req.body.product.trim() : "";
    if (!product) {
      return res.status(400).json({ error: "Search for a product to get recommendations" });
    }
    const customerId = req.customer?.customerId ?? null;
    return res.json(
      await recommenderRequest("/api/recommendations", {
        method: "POST",
        body: JSON.stringify({ product, customerId }),
      })
    );
  })
);

router.get("/cart", requireAuth, asyncRoute(async (req, res) => {
  const cart = await Cart.findOne({ customerId: req.customer.customerId }).lean();
  return res.json(cartResponse(cart));
}));

router.post("/cart/items", requireAuth, asyncRoute(async (req, res) => {
  const body = req.body || {};
  const productName = typeof body.productName === "string" ? body.productName.trim() : "";
  const quantity = Number(body.quantity ?? 1);
  if (!productName || !Number.isInteger(quantity) || quantity < 1 || quantity > 99) {
    return res.status(400).json({ error: "Choose a product and a quantity from 1 to 99" });
  }
  const productQuery = new URLSearchParams({ name: productName });
  if (typeof body.stockCode === "string" && body.stockCode.trim()) {
    productQuery.set("stockCode", body.stockCode.trim());
  }
  const product = await recommenderRequest(`/api/products/lookup?${productQuery}`);
  const cart = await Cart.findOneAndUpdate(
    { customerId: req.customer.customerId },
    { $setOnInsert: { customerId: req.customer.customerId } },
    { new: true, upsert: true }
  );
  const existing = cart.items.find((item) => item.stockCode === product.stockCode);
  if (existing) {
    if (existing.quantity + quantity > 99) {
      return res.status(400).json({ error: "A product quantity cannot exceed 99" });
    }
    existing.quantity += quantity;
  } else {
    cart.items.push({
      productName: product.name,
      stockCode: product.stockCode,
      price: product.price,
      quantity,
    });
  }
  await cart.save();
  return res.json(cartResponse(cart));
}));

router.patch("/cart/items/:stockCode", requireAuth, asyncRoute(async (req, res) => {
  const quantity = Number(req.body?.quantity);
  if (!Number.isInteger(quantity) || quantity < 1 || quantity > 99) {
    return res.status(400).json({ error: "Choose a quantity from 1 to 99" });
  }
  const cart = await Cart.findOne({ customerId: req.customer.customerId });
  const item = cart?.items.find((entry) => entry.stockCode === req.params.stockCode);
  if (!item) {
    return res.status(404).json({ error: "That item is not in your cart" });
  }
  item.quantity = quantity;
  await cart.save();
  return res.json(cartResponse(cart));
}));

router.delete("/cart/items/:stockCode", requireAuth, asyncRoute(async (req, res) => {
  const cart = await Cart.findOne({ customerId: req.customer.customerId });
  if (!cart) {
    return res.status(404).json({ error: "Your cart is empty" });
  }
  cart.items = cart.items.filter((item) => item.stockCode !== req.params.stockCode);
  await cart.save();
  return res.json(cartResponse(cart));
}));

router.post("/orders", requireAuth, asyncRoute(async (req, res) => {
  const body = req.body || {};
  const { name, address, city, region, postalCode, phone } = body.shipping || {};
  const shipping = { name, address, city, region, postalCode, phone };
  if (
    Object.values(shipping).some(
      (value) => typeof value !== "string" || !value.trim() || value.trim().length > 160
    )
  ) {
    return res.status(400).json({ error: "Complete every shipping address field" });
  }
  if (!/^[\d+() -]{7,20}$/.test(phone.trim())) {
    return res.status(400).json({ error: "Enter a valid phone number" });
  }

  const customerId = req.customer.customerId;
  const checkoutKey =
    typeof body.checkoutKey === "string" && /^[\w-]{8,80}$/.test(body.checkoutKey)
      ? body.checkoutKey
      : randomUUID();
  const existing = await Order.findOne({ customerId, checkoutKey });
  if (existing) {
    await Cart.updateOne({ customerId }, { $set: { items: [] } });
    return res.status(200).json({ order: existing });
  }

  const cart = await Cart.findOne({ customerId });
  if (!cart?.items.length) {
    return res.status(400).json({ error: "Your cart is empty" });
  }
  const items = cart.items.map((item) => ({
    productName: item.productName,
    stockCode: item.stockCode,
    price: item.price,
    quantity: item.quantity,
  }));
  const total = items.reduce((sum, item) => sum + item.price * item.quantity, 0);

  let order;
  try {
    order = await Order.create({
      customerId,
      checkoutKey,
      items,
      total,
      shipping: Object.fromEntries(
        Object.entries(shipping).map(([key, value]) => [key, value.trim()])
      ),
    });
  } catch (error) {
    if (error.code !== 11000) {
      throw error;
    }
    order = await Order.findOne({ customerId, checkoutKey });
  }
  await Cart.updateOne({ customerId }, { $set: { items: [] } });
  return res.status(201).json({ order });
}));

router.use((error, req, res, next) => {
  if (res.headersSent) {
    return next(error);
  }
  if (error instanceof UpstreamError) {
    return res.status(error.status).json({ error: error.message });
  }
  if (error.name === "ValidationError") {
    return res.status(400).json({ error: error.message });
  }
  if (error.code === 11000) {
    return res.status(409).json({ error: "That account is already registered" });
  }
  console.error("API request failed:", error);
  return res.status(500).json({ error: "Something went wrong. Please try again." });
});

export default router;
