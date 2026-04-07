const express = require("express");
const cors = require("cors");
require("dotenv").config();

const uploadRoute = require("./routes/upload");

const app = express();

app.use(cors());
app.use(express.json({ limit: "10mb" }));

app.use("/upload", uploadRoute);

app.listen(process.env.PORT, () => {
  console.log(`🚀 Server running on port ${process.env.PORT}`);
});