import hashlib
import re
from typing import Dict, List


# -------------------------------
# 🔥 STABLE IMAGE SEED
# -------------------------------
def _seed_fragment(prompt: str, slot: str) -> str:
    """
    Stable deterministic seed.
    Same prompt always generates same URLs.
    """
    raw = f"{prompt.strip().lower()}|{slot}"
    return hashlib.sha256(raw.encode()).hexdigest()[:20]


# -------------------------------
# 🔥 SMART KEYWORD EXTRACTION
# -------------------------------
def extract_keywords(prompt: str) -> str:
    """
    Extract niche-aware visual keywords.
    Removes generic website builder words.
    """
    words = re.findall(r"[a-zA-Z]+", prompt.lower())

    ignored = {
        "create",
        "make",
        "build",
        "website",
        "landing",
        "page",
        "professional",
        "modern",
        "best",
        "for",
        "with",
        "ai",
        "business",
        "premium",
        "company",
    }

    keywords = [w for w in words if w not in ignored]

    if not keywords:
        return "business"

    return ",".join(keywords[:4])


# -------------------------------
# 🔥 BUILD IMAGE URL
# -------------------------------
def _img(seed: str, w: int, h: int) -> str:
    return f"https://picsum.photos/seed/{seed}/{w}/{h}"


# -------------------------------
# 🔥 UNIVERSAL AI IMAGE ENGINE
# -------------------------------
def generate_images(prompt: str) -> Dict[str, object]:
    """
    Universal deterministic AI image generator.

    Works for:
    ✅ template1
    ✅ template2
    ✅ template3
    ✅ template4
    ✅ template5
    ✅ template6
    ✅ future templates
    """
    keywords = extract_keywords(prompt)

    hero_seed = _seed_fragment(prompt, "hero")
    about_seed = _seed_fragment(prompt, "about")
    gallery_seed = _seed_fragment(prompt, "gallery")
    logo_seed = _seed_fragment(prompt, "logo")

    blog_seeds: List[str] = [
        _seed_fragment(prompt, f"blog{i}") for i in range(1, 4)
    ]

    service_seeds: List[str] = [
        _seed_fragment(prompt, f"service{i}") for i in range(1, 4)
    ]

    return {
        # universal keys
        "hero_image": _img(hero_seed, 1600, 900),
        "about_image": _img(about_seed, 1200, 800),
        "gallery_image": _img(gallery_seed, 1200, 800),
        "logo": _img(logo_seed, 200, 200),

        # legacy compatibility keys
        "image_1": _img(hero_seed, 1200, 700),
        "image_2": _img(about_seed, 900, 700),
        "image_3": _img(gallery_seed, 900, 600),

        # template6 nested arrays
        "blog_images": [
            _img(seed, 800, 500) for seed in blog_seeds
        ],
        "service_images": [
            _img(seed, 600, 400) for seed in service_seeds
        ],

        # metadata
        "keywords": keywords,
    }