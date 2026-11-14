import mongoose from "mongoose";

const cartItemSchema = new mongoose.Schema(
  {
    productName: { type: String, required: true },
    stockCode: { type: String, required: true },
    price: { type: Number, required: true, min: 0 },
    quantity: { type: Number, required: true, min: 1, max: 99 },
  },
  { _id: false }
);

const cartSchema = new mongoose.Schema(
  {
    customerId: { type: Number, required: true, unique: true },
    items: { type: [cartItemSchema], default: [] },
  },
  { timestamps: true }
);

export default mongoose.model("Cart", cartSchema);
