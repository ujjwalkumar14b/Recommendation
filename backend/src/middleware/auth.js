import jwt from "jsonwebtoken";
import Customer from "../models/Customer.js";

export async function requireAuth(req, res, next) {
  const token = req.get("authorization")?.replace(/^Bearer\s+/i, "");
  if (!token) {
    return res.status(401).json({ error: "Please sign in to continue" });
  }

  try {
    const payload = jwt.verify(token, process.env.JWT_SECRET);
    const customer = await Customer.findOne({ customerId: payload.customerId }).select(
      "customerId name email"
    );
    if (!customer) {
      return res.status(401).json({ error: "Your session is no longer valid" });
    }
    req.customer = customer;
    return next();
  } catch (error) {
    if (error.name === "TokenExpiredError" || error.name === "JsonWebTokenError") {
      return res.status(401).json({ error: "Please sign in again" });
    }
    return next(error);
  }
}

export async function optionalAuth(req, res, next) {
  const token = req.get("authorization")?.replace(/^Bearer\s+/i, "");
  if (!token) {
    return next();
  }

  try {
    const payload = jwt.verify(token, process.env.JWT_SECRET);
    req.customer = await Customer.findOne({ customerId: payload.customerId }).select(
      "customerId name email"
    );
    if (!req.customer) {
      return res.status(401).json({ error: "Your session is no longer valid" });
    }
    return next();
  } catch (error) {
    if (error.name === "TokenExpiredError" || error.name === "JsonWebTokenError") {
      return res.status(401).json({ error: "Please sign in again" });
    }
    return next(error);
  }
}
