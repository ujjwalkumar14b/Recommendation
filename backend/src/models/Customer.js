import mongoose from "mongoose";

const customerSchema = new mongoose.Schema(
  {
    customerId: { type: Number, required: true, unique: true, min: 1 },
    name: { type: String, required: true, trim: true, maxlength: 80 },
    email: { type: String, required: true, unique: true, lowercase: true, trim: true },
    passwordHash: { type: String, required: true, select: false },
  },
  { timestamps: true }
);

export default mongoose.model("Customer", customerSchema);
