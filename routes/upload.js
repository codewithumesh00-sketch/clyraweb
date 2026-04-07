const express = require("express");
const router = express.Router();
const cloudinary = require("../config/cloudinary");

router.post("/", async (req, res) => {
  try {
    const { image } = req.body;

    const uploadResponse = await cloudinary.uploader.upload(image, {
      folder: "ai-builder",
    });

    res.json({
      url: uploadResponse.secure_url,
    });

  } catch (error) {
    console.error(error);
    res.status(500).json({ error: "Upload failed" });
  }
});

module.exports = router;