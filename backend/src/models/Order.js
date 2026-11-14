import mongoose from "mongoose";

const orderItemSchema = new mongoose.Schema(
  {
    productName: { type: String, required: true },
    stockCode: { type: String, required: true },
    price: { type: Number, required: true, min: 0 },
    quantity: { type: Number, required: true, min: 1 },
  },
  { _id: false }
);

const orderSchema = new mongoose.Schema(
  {
    customerId: { type: Number, required: true, index: true },
    checkoutKey: { type: String, required: true },
    items: { type: [orderItemSchema], required: true },
    total: { type: Number, required: true, min: 0 },
    shipping: {
      name: { type: String, required: true },
      address: { type: String, required: true },
      city: { type: String, required: true },
      region: { type: String, required: true },
      postalCode: { type: String, required: true },
      phone: { type: String, required: true },
    },
    paymentMethod: { type: String, enum: ["Cash on delivery"], default: "Cash on delivery" },
    status: { type: String, enum: ["Placed", "Shipped", "Delivered"], default: "Placed" },
  },
  { timestamps: true }
);

orderSchema.index({ customerId: 1, checkoutKey: 1 }, { unique: true });

export default mongoose.model("Order", orderSchema);
