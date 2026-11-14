import "dotenv/config";
import cors from "cors";
import express from "express";
import helmet from "helmet";
import mongoose from "mongoose";
import apiRouter from "./routes/api.js";

const requiredEnvironment = ["MONGODB_URI", "JWT_SECRET"];
const missingEnvironment = requiredEnvironment.filter((key) => !process.env[key]);
if (missingEnvironment.length) {
  throw new Error(`Missing required environment variables: ${missingEnvironment.join(", ")}`);
}
if (process.env.JWT_SECRET.length < 32) {
  throw new Error("JWT_SECRET must be at least 32 characters long");
}

const app = express();
app.disable("x-powered-by");
app.use(helmet());
app.use(cors({ origin: process.env.CLIENT_ORIGIN || "http://localhost:5173" }));
app.use(express.json({ limit: "1mb" }));
app.get("/api/health", (req, res) => res.json({ status: "ok" }));
app.use("/api", apiRouter);
app.use((req, res) => res.status(404).json({ error: "API route not found" }));
app.use((error, req, res, next) => {
  if (res.headersSent) {
    return next(error);
  }
  if (error.type === "entity.parse.failed") {
    return res.status(400).json({ error: "Request body must be valid JSON" });
  }
  if (error.type === "entity.too.large") {
    return res.status(413).json({ error: "Request body is too large" });
  }
  console.error("Request failed:", error);
  return res.status(500).json({ error: "Something went wrong. Please try again." });
});

const port = Number(process.env.PORT) || 5001;
await mongoose.connect(process.env.MONGODB_URI);
app.listen(port, () => {
  console.log(`PickPerfect API listening on http://localhost:${port}`);
});
