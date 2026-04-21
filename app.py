print("🚀 BACKEND STARTING...")
import zipfile
import tempfile
import subprocess
import shutil
import requests
import os
import hashlib
import json
import uuid
import io
import time
from pathlib import Path
from typing import Optional, Literal

from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket
from pydantic import BaseModel, Field
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from agent import generate_ui_json, generate_seo_blog

# ✅ Firestore — optional, only used on Cloud Run
USE_FIRESTORE = False
db = None
try:
    from google.cloud import firestore
    db = firestore.Client()
    USE_FIRESTORE = True
    print("✅ Firestore initialized")
except Exception as e:
    db = None
    USE_FIRESTORE = False
    print("⚠️  Firestore unavailable — using local JSON fallback:", e)


# ✅ FIX 3: FORCE ENV PATH LOAD - Explicit .env path
env_path = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=env_path)

app = FastAPI(title="clyraweb AI Backend 🚀")
active_connections: list[WebSocket] = []

# ✅ ENV VARS
NETLIFY_TOKEN = os.getenv("NETLIFY_TOKEN")
NETLIFY_SITE_ID = os.getenv("NETLIFY_SITE_ID")
NETLIFY_SITE_URL = os.getenv("NETLIFY_SITE_URL")

# ✅ FIX 4: DEBUG TOKEN LOAD - Verify env vars are loading
print("🔐 NETLIFY TOKEN:", NETLIFY_TOKEN[:10] + "..." if NETLIFY_TOKEN else "❌ MISSING")
print("🔐 NETLIFY SITE:", NETLIFY_SITE_ID if NETLIFY_SITE_ID else "❌ MISSING")

# -------------------------------
# ✅ TYPE DEFINITIONS
# -------------------------------
CategoryType = Literal["blog", "ecommerce", "saas", "portfolio", "business"]
StyleModeType = Literal[
    "luxury", "glass", "dark", "furniture", "bold", "corporate",
    "natural", "education", "food", "health", "entertainment", "realestate", "minimal"
]

# -------------------------------
# ✅ STYLE MODE DETECTOR (THE BRAIN 🧠)
# -------------------------------
def detect_style_mode(prompt: str) -> StyleModeType:
    """Analyzes prompt keywords and returns style DNA for visual mutation."""
    text = prompt.lower()

    style_keywords: dict[StyleModeType, list[str]] = {
        "furniture": ["furniture", "wood", "chair", "table", "craft", "artisan", "handmade", "organic"],
        "luxury": ["luxury", "premium", "elegant", "sophisticated", "exclusive", "high-end", "upscale"],
        "glass": ["glass", "saas", "dashboard", "modern", "tech", "software", "app", "platform", "digital"],
        "dark": ["dark", "neon", "night", "cyber", "futuristic", "glow", "matrix", "hacker"],
        "bold": ["bold", "creative", "agency", "vibrant", "colorful", "energetic", "playful", "fun"],
        "corporate": ["corporate", "professional", "business", "finance", "bank", "law", "consulting"],
        "natural": ["eco", "green", "natural", "wellness", "organic", "sustainable", "earth", "plant"],
        "education": ["education", "school", "academy", "course", "learn", "training", "university"],
        "food": ["food", "restaurant", "cafe", "bistro", "dining", "chef", "cuisine", "menu"],
        "health": ["health", "medical", "clinic", "doctor", "hospital", "wellness", "fitness", "gym"],
        "entertainment": ["music", "entertainment", "event", "concert", "festival", "party", "nightlife"],
        "realestate": ["real estate", "property", "homes", "realtor", "housing", "apartment", "building"],
    }

    for mode, keywords in style_keywords.items():
        if any(k in text for k in keywords):
            return mode

    return "minimal"


# -------------------------------
# ✅ STYLE MODE → THEME MAPPING
# -------------------------------
def get_style_theme(style_mode: StyleModeType) -> dict:
    """Returns theme config based on style mode for automatic theming."""

    style_themes: dict[StyleModeType, dict] = {
        "luxury": {"primary": "#D4AF37", "secondary": "#1a1a1a", "background": "#0a0a0a", "text": "#ffffff", "muted": "#b8b8b8", "accent": "#C0A080", "font": "serif"},
        "glass": {"primary": "#6366f1", "secondary": "#8b5cf6", "background": "linear-gradient(135deg, #667eea 0%, #764ba2 100%)", "text": "#ffffff", "muted": "#e2e8f0", "accent": "#a78bfa", "font": "sans", "glass": True, "blur": "20px"},
        "dark": {"primary": "#00f5d4", "secondary": "#9d4edd", "background": "#0a0a0f", "text": "#ffffff", "muted": "#94a3b8", "accent": "#00f5d4", "font": "mono", "glow": True},
        "furniture": {"primary": "#8B7355", "secondary": "#D4C4B0", "background": "#FDFCF8", "text": "#2c2c2c", "muted": "#6b6b6b", "accent": "#A0826D", "font": "serif", "texture": "wood"},
        "bold": {"primary": "#ff6b6b", "secondary": "#4ecdc4", "background": "#ffffff", "text": "#1a1a1a", "muted": "#666666", "accent": "#ffe66d", "font": "sans", "bold": True},
        "corporate": {"primary": "#1e40af", "secondary": "#64748b", "background": "#ffffff", "text": "#0f172a", "muted": "#64748b", "accent": "#3b82f6", "font": "sans"},
        "natural": {"primary": "#22c55e", "secondary": "#84cc16", "background": "#f0fdf4", "text": "#166534", "muted": "#65a30d", "accent": "#4ade80", "font": "sans"},
        "education": {"primary": "#3b82f6", "secondary": "#8b5cf6", "background": "#ffffff", "text": "#1e293b", "muted": "#64748b", "accent": "#60a5fa", "font": "sans"},
        "food": {"primary": "#f97316", "secondary": "#ef4444", "background": "#fffbeb", "text": "#78350f", "muted": "#92400e", "accent": "#fb923c", "font": "sans"},
        "health": {"primary": "#06b6d4", "secondary": "#14b8a6", "background": "#f0fdff", "text": "#164e63", "muted": "#0e7490", "accent": "#22d3ee", "font": "sans"},
        "entertainment": {"primary": "#ec4899", "secondary": "#8b5cf6", "background": "#0f0720", "text": "#ffffff", "muted": "#c4b5fd", "accent": "#f472b6", "font": "sans"},
        "realestate": {"primary": "#059669", "secondary": "#64748b", "background": "#ffffff", "text": "#0f172a", "muted": "#64748b", "accent": "#10b981", "font": "sans"},
        "minimal": {"primary": "#3b82f6", "secondary": "#64748b", "background": "#ffffff", "text": "#0f172a", "muted": "#64748b", "accent": "#93c5fd", "font": "sans"},
    }

    return style_themes.get(style_mode, style_themes["minimal"])


# -------------------------------
# ✅ REQUEST MODELS
# -------------------------------
class GenerateRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=2000)
    template: Optional[str] = None
    content: Optional[dict] = None


class BlogRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=2000)


# -------------------------------
# ✅ CORS CONFIG
# -------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# -------------------------------
# ✅ HEALTH CHECK
# -------------------------------
@app.get("/")
def home():
    return {"status": "OK 🚀", "message": "Backend running", "version": "2.1.0"}


# -------------------------------
# ✅ WEBSOCKET LIVE PREVIEW
# -------------------------------
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    active_connections.append(websocket)
    try:
        while True:
            await websocket.receive_text()
    except Exception:
        if websocket in active_connections:
            active_connections.remove(websocket)


# ============================================================
# ✅ CATEGORY DETECTION (FOR METADATA)
# ============================================================
def detect_category(text: str) -> CategoryType:
    """Detect content category from prompt keywords."""
    lower = text.lower()

    if any(k in lower for k in ["blog", "article", "news", "seo", "journal", "stories"]):
        return "blog"
    if any(k in lower for k in ["shop", "store", "ecommerce", "product", "furniture", "chair", "table", "fashion"]):
        return "ecommerce"
    if any(k in lower for k in ["saas", "software", "crm", "dashboard", "platform", "app"]):
        return "saas"
    if any(k in lower for k in ["portfolio", "developer", "designer", "resume", "cv"]):
        return "portfolio"

    return "business"


# ============================================================
# ✅ 40-TEMPLATE SMART MAPPER
# ============================================================
TEMPLATE_NAME_MAP = {
    "modern business": "template1",
    "ecommerce store": "template2",
    "portfolio pro": "template3",
    "restaurant hub": "template4",
    "fitness coach": "template5",
    "saas landing": "template6",
    "agency flow": "template7",
    "furniture showcase": "template8",
    "real estate prime": "template9",
    "medical clinic": "template10",
    "education academy": "template11",
    "travel explorer": "template12",
    "beauty salon": "template13",
    "law firm": "template14",
    "construction build": "template15",
    "car rental": "template16",
    "pet care": "template17",
    "photography studio": "template18",
    "event planner": "template19",
    "crypto startup": "template20",
    "ai product": "template21",
    "blog magazine": "template22",
    "podcast studio": "template23",
    "fashion brand": "template24",
    "jewelry luxury": "template25",
    "interior design": "template26",
    "bakery shop": "template27",
    "gaming zone": "template28",
    "ngo charity": "template29",
    "resume portfolio": "template30",
    "wedding planner": "template31",
    "hotel booking": "template32",
    "mobile app": "template33",
    "electronics shop": "template34",
    "dental care": "template35",
    "yoga meditation": "template36",
    "freelancer personal": "template37",
    "news portal": "template38",
    "course seller": "template39",
    "startup pitch": "template40",
}

from difflib import get_close_matches


def choose_template_from_prompt(prompt: str) -> str:
    """
    Ultra-smart intent-based template selector.
    Understands business meaning, keywords, typos, and natural prompts.
    """

    normalized = (
        prompt.lower()
        .replace(" ", "")
        .replace("-", "")
        .replace("_", "")
        .replace('"', "")
        .strip()
    )

    # ---------------------------------------------------
    # ✅ 1) DIRECT TEMPLATE NAME MATCH
    # ---------------------------------------------------
    normalized_map = {
        name.lower().replace(" ", "").replace("-", "").replace("_", ""): template_id
        for name, template_id in TEMPLATE_NAME_MAP.items()
    }

    if normalized in normalized_map:
        return normalized_map[normalized]

    for key, template_id in normalized_map.items():
        if normalized in key or key.startswith(normalized):
            return template_id

    close = get_close_matches(normalized, normalized_map.keys(), n=1, cutoff=0.5)
    if close:
        return normalized_map[close[0]]

    # ---------------------------------------------------
    # ✅ 2) AI-LEVEL INTENT ROUTING
    # ---------------------------------------------------
    text = prompt.lower()

    intent_rules = [
        (["fashion", "clothing", "apparel", "dress", "tshirt", "shoe"], "template24"),
        (["ecommerce", "store", "shop", "product", "cart"], "template2"),
        (["portfolio", "resume", "developer", "designer", "personal"], "template3"),
        (["restaurant", "cafe", "food", "menu", "chef", "bakery"], "template4"),
        (["fitness", "gym", "coach", "health trainer"], "template5"),
        (["saas", "software", "crm", "dashboard", "platform", "startup"], "template6"),
        (["agency", "marketing", "creative studio"], "template7"),
        (["furniture", "chair", "table", "wood"], "template8"),
        (["real estate", "property", "apartment", "builder"], "template9"),
        (["clinic", "hospital", "doctor", "medical"], "template10"),
        (["academy", "education", "course", "school"], "template11"),
        (["travel", "tour", "trip"], "template12"),
        (["beauty", "salon", "spa"], "template13"),
        (["law", "legal", "advocate"], "template14"),
        (["construction", "builder", "architecture"], "template15"),
        (["car rental", "cars", "vehicles"], "template16"),
        (["pets", "pet care", "dog", "cat"], "template17"),
        (["photography", "photo studio"], "template18"),
        (["events", "wedding", "planner"], "template19"),
        (["crypto", "blockchain", "web3"], "template20"),
        (["ai", "artificial intelligence", "automation"], "template21"),
        (["blog", "articles", "news"], "template22"),
        (["podcast", "audio", "music"], "template23"),
        (["jewelry", "luxury", "gold", "diamond"], "template25"),
        (["interior", "home decor"], "template26"),
        (["gaming", "esports"], "template28"),
        (["ngo", "charity", "donation"], "template29"),
        (["hotel", "booking", "resort"], "template32"),
        (["mobile app", "app showcase"], "template33"),
        (["electronics", "gadgets"], "template34"),
        (["dental", "dentist"], "template35"),
        (["yoga", "meditation", "wellness"], "template36"),
        (["freelancer", "personal brand"], "template37"),
        (["news portal", "media"], "template38"),
        (["course seller", "online learning"], "template39"),
        (["startup pitch", "investor", "pitch deck"], "template40"),
    ]

    for keywords, template_id in intent_rules:
        if any(keyword in text for keyword in keywords):
            return template_id

    # ---------------------------------------------------
    # ✅ 3) SMART COMBINATION RULES
    # ---------------------------------------------------
    if "ecommerce" in text and "fashion" in text:
        return "template24"

    if "portfolio" in text and ("developer" in text or "java" in text):
        return "template3"

    if "luxury" in text and ("jewelry" in text or "gold" in text):
        return "template25"

    if "startup" in text and ("saas" in text or "software" in text):
        return "template6"

    return "template1"

# ============================================================
# ✅ UNIVERSAL EDITABLE DATA BUILDER
# ============================================================
def build_base_editable_data(prompt: str, images: list[str], category: CategoryType) -> dict:
    """Build shared editable data structure for all categories."""
    brand_name = prompt.title().split()[0] if prompt.title().split() else "Brand"

    return {
        "navbar": {
            "brand": brand_name,
            "links": [
                {"label": "Home", "page": "home"},
                {"label": "Collections", "page": "collections"} if category == "ecommerce"
                else {"label": "Articles", "page": "articles"} if category == "blog"
                else {"label": "Features", "page": "features"},
                {"label": "Account", "page": "account"},
            ],
        },
        "hero": {
            "title": f"Welcome to {prompt.title()}",
            "subtitle": f"Premium experience crafted for {prompt}",
            "ctaText": "Get Started" if category != "blog" else "Read Articles",
            "image": images[0] if images else None,
        },
        "footer": {
            "brand": brand_name,
            "text": f"Premium digital experience for {prompt}",
            "copyright": f"© 2026 {prompt.title()}",
        },
    }


# ============================================================
# ✅ BLOG CONTENT BUILDER
# ============================================================
def build_blog_editable_data(prompt: str, images: list[str]) -> dict:
    """Build editable data specifically for blog category."""
    base = build_base_editable_data(prompt, images, "blog")

    base["navbar"]["links"] = [
        {"label": "Home", "page": "home"},
        {"label": "Articles", "page": "articles"},
        {"label": "About", "page": "about"},
    ]

    base["hero"] = {
        "title": f"Welcome to {prompt.title()}",
        "subtitle": f"Stories, travel guides, and local updates from {prompt}",
        "ctaText": "Read Articles",
        "image": images[0] if images else None,
    }

    base["posts"] = [
        {
            "id": 1,
            "title": f"Best places to visit in {prompt.title()}",
            "excerpt": "Discover hidden gems, food, and travel spots.",
            "image": images[0] if images else None,
        },
        {
            "id": 2,
            "title": f"Top cafes in {prompt.title()}",
            "excerpt": "A local guide for coffee lovers.",
            "image": images[1] if len(images) > 1 else None,
        },
    ]

    base["footer"] = {
        "brand": f"{prompt.title()} Blog",
        "text": f"Your trusted local stories from {prompt}",
        "copyright": f"© 2026 {prompt.title()} Blog",
    }

    return base


# ============================================================
# ✅ ECOMMERCE CONTENT BUILDER
# ============================================================
def build_ecommerce_editable_data(prompt: str, images: list[str]) -> dict:
    """Build editable data specifically for ecommerce category."""
    base = build_base_editable_data(prompt, images, "ecommerce")

    base["products"] = [
        {
            "id": "product-1",
            "title": f"{prompt.title()} Premium Product",
            "description": f"Best quality {prompt}",
            "price": 299,
            "category": "general",
            "slug": "premium-product",
            "image": images[0] if images else None,
        },
        {
            "id": "product-2",
            "title": f"{prompt.title()} Exclusive Edition",
            "description": f"Limited edition {prompt}",
            "price": 499,
            "category": "luxury",
            "slug": "exclusive-edition",
            "image": images[1] if len(images) > 1 else None,
        },
    ]

    return base


# ============================================================
# ✅ SAAS CONTENT BUILDER
# ============================================================
def build_saas_editable_data(prompt: str, images: list[str]) -> dict:
    """Build editable data specifically for SaaS category."""
    base = build_base_editable_data(prompt, images, "saas")

    base["features"] = [
        {
            "id": "feature-1",
            "title": "Smart Dashboard",
            "description": f"Powerful tools for {prompt}",
            "icon": "dashboard",
        },
        {
            "id": "feature-2",
            "title": "Analytics Suite",
            "description": "Real-time insights and reporting",
            "icon": "analytics",
        },
    ]

    return base


# ============================================================
# ✅ MAIN GENERATE ENDPOINT — CLEAN & STABLE
# ============================================================
@app.post("/generate")
async def generate(req: GenerateRequest):
    prompt = req.prompt.strip()
    if not prompt:
        return {"success": False, "error": "Prompt required"}

    try:
        print(f"⚡ Generating: {prompt}")

        # ✅ AI content generation with safe fallback
        try:
            data = generate_ui_json(prompt, current_content=req.content)
            if not isinstance(data, dict):
                print(f"⚠️ Invalid AI response type: {type(data)}")
                data = {}
        except Exception as ai_error:
            print(f"⚠️ UI JSON generation failed: {type(ai_error).__name__}: {ai_error}")
            data = {}

        # ✅ Stable fallback images (no broken external calls)
        images = [
            f"https://picsum.photos/seed/{prompt}-1/1600/900",
            f"https://picsum.photos/seed/{prompt}-2/1600/900",
            f"https://picsum.photos/seed/{prompt}-3/1600/900",
        ]

        # ✅ Empty theme fallback (style handled by detect_style_mode)
        theme = {}

        # ✅ Style detection
        style_mode = detect_style_mode(prompt)
        print(f"🎨 Detected style mode: {style_mode}")
        style_theme = get_style_theme(style_mode)

        # ✅ Category detection (for metadata only)
        category = detect_category(prompt)
        
        # ✅ Smart template selection from 40 options
        template_id = choose_template_from_prompt(prompt)
        print(f"📦 Category: {category} | Template: {template_id}")

        # ✅ Build editable data by category
        if category == "blog":
            editable_data = build_blog_editable_data(prompt, images)
        elif category == "ecommerce":
            editable_data = build_ecommerce_editable_data(prompt, images)
        elif category == "saas":
            editable_data = build_saas_editable_data(prompt, images)
        else:
            editable_data = build_base_editable_data(prompt, images, category)

        # ✅ Merge AI data safely
        final_editable_data = {
            **editable_data,
            **(data if isinstance(data, dict) else {}),
        }

        # ✅ Final schema with editableData support
        website_schema = {
            "category": category,
            "templateId": template_id,
            "prompt": prompt,
            "styleMode": style_mode,
            "editableData": final_editable_data,
            "metadata": {
                "generatedAt": str(uuid.uuid4()),
                "source": "fastapi-template-engine",
                "theme": {
                    **(theme if isinstance(theme, dict) else {}),
                    **style_theme,
                },
            },
        }

        return {"success": True, "website": website_schema}

    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"success": False, "error": f"{type(e).__name__}: {str(e)}"}


# -------------------------------
# ✅ BLOG GENERATION ENDPOINT
# -------------------------------
@app.post("/generate-blog")
async def generate_blog(req: BlogRequest):
    try:
        result = generate_seo_blog(req.prompt)
        return {"success": True, "title": result["title"], "blog": result["blog"]}
    except Exception as e:
        return {"success": False, "error": str(e)}


# -------------------------------
# ✅ STYLE MODE PREVIEW ENDPOINT
# -------------------------------
@app.get("/style/{mode}")
async def preview_style(mode: str):
    """Preview theme config for a style mode (for frontend dev)."""
    valid_modes: list[StyleModeType] = [
        "luxury", "glass", "dark", "furniture", "bold", "corporate",
        "natural", "education", "food", "health", "entertainment", "realestate", "minimal"
    ]
    if mode not in valid_modes:
        return {"success": False, "error": f"Unknown style mode. Valid: {valid_modes}"}

    theme = get_style_theme(mode)  # type: ignore
    return {
        "success": True,
        "styleMode": mode,
        "theme": theme,
        "example_classes": [
            f"bg-{mode}-primary", f"text-{mode}-accent",
            f"border-{mode}-secondary", f"font-{theme.get('font', 'sans')}"
        ],
    }


# ── Project storage: Firestore on Cloud Run, JSON files locally ──
PROJECTS_DIR = Path(__file__).parent / "projects"
PROJECTS_DIR.mkdir(parents=True, exist_ok=True)


@app.post("/save")
async def save_project(data: dict):
    project_id = str(uuid.uuid4())
    if USE_FIRESTORE and db:
        db.collection("projects").document(project_id).set(data)
    else:
        (PROJECTS_DIR / f"{project_id}.json").write_text(
            json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
        )
    return {"success": True, "project_id": project_id}


@app.get("/project/{project_id}")
def load_project(project_id: str):
    if USE_FIRESTORE and db:
        doc = db.collection("projects").document(project_id).get()
        if not doc.exists:
            return {"success": False, "error": "Project not found"}
        return {"success": True, "data": doc.to_dict()}
    else:
        project_file = PROJECTS_DIR / f"{project_id}.json"
        if not project_file.exists():
            return {"success": False, "error": "Project not found"}
        return {"success": True, "data": json.loads(project_file.read_text(encoding="utf-8"))}


# -------------------------------
# ✅ ZIP DOWNLOAD ENDPOINT
# -------------------------------
# -------------------------------
# ✅ STREAMING DEPLOY ENDPOINT (Cloud Run compatible)
# No filesystem template reads, no npm/Node.js dependency
# Accepts rendered HTML from frontend → ZIPs → deploys to Netlify
# -------------------------------
@app.post("/deploy")
async def deploy(data: dict):
    import asyncio
    import io as _io

    files        = data.get("files", {})          # {"index.html": "...", ...}
    project_name = data.get("projectName", "clyraweb-project")
    editable_data = data.get("editableData", {})
    theme         = data.get("theme", {})

    async def generate():
        yield "STEP:START\n"
        yield "PROGRESS:10\n"
        yield "🚀 Preparing deployment...\n"

        if not NETLIFY_TOKEN:
            yield "ERROR:NETLIFY_TOKEN missing in environment\n"
            return
        if not NETLIFY_SITE_ID:
            yield "ERROR:NETLIFY_SITE_ID missing in environment\n"
            return

        try:
            # ── Build static HTML ─────────────────────────────────────
            yield "STEP:BUILD\n"
            yield "PROGRESS:35\n"
            yield "🏗️ Generating static HTML...\n"

            # Use index.html from files dict if provided by frontend
            if files and "index.html" in files:
                index_html = files["index.html"]
                yield "✅ Using frontend-provided HTML\n"
            else:
                # Generate a minimal HTML shell from editable_data
                title       = editable_data.get("hero", {}).get("title", project_name)
                subtitle    = editable_data.get("hero", {}).get("subtitle", "")
                bg_color    = theme.get("backgroundColor", "#0f172a")
                text_color  = theme.get("textColor", "#ffffff")
                primary     = theme.get("primaryColor", "#6366f1")

                nav_links   = editable_data.get("navbar", {}).get("links", [])
                nav_html    = "".join(
                    f'<a href="#" style="color:{primary};margin:0 12px;text-decoration:none;">'
                    f'{link.get("label","") if isinstance(link, dict) else link}</a>'
                    for link in nav_links
                )

                footer_text = editable_data.get("footer", {}).get("copyright", f"© 2026 {project_name}")

                index_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title}</title>
  <style>
    *{{box-sizing:border-box;margin:0;padding:0}}
    body{{font-family:Inter,sans-serif;background:{bg_color};color:{text_color};min-height:100vh}}
    nav{{display:flex;justify-content:space-between;align-items:center;padding:20px 40px;
         background:rgba(255,255,255,0.05);backdrop-filter:blur(10px);border-bottom:1px solid rgba(255,255,255,0.1)}}
    .brand{{font-size:1.4rem;font-weight:700;color:{primary}}}
    .hero{{display:flex;flex-direction:column;align-items:center;justify-content:center;
           padding:120px 40px;text-align:center;min-height:70vh}}
    h1{{font-size:clamp(2rem,5vw,4rem);font-weight:800;margin-bottom:24px;
        background:linear-gradient(135deg,{primary},{text_color});
        -webkit-background-clip:text;-webkit-text-fill-color:transparent}}
    p{{font-size:1.2rem;opacity:0.7;max-width:600px;line-height:1.6}}
    .cta{{margin-top:40px;padding:16px 40px;background:{primary};color:#fff;
          border:none;border-radius:8px;font-size:1rem;font-weight:600;cursor:pointer;
          text-decoration:none;display:inline-block}}
    footer{{text-align:center;padding:40px;opacity:0.5;font-size:0.85rem;
            border-top:1px solid rgba(255,255,255,0.1)}}
  </style>
</head>
<body>
  <nav>
    <span class="brand">{project_name}</span>
    <div>{nav_html}</div>
  </nav>
  <section class="hero">
    <h1>{title}</h1>
    <p>{subtitle}</p>
    <a href="#" class="cta">Get Started</a>
  </section>
  <footer>{footer_text}</footer>
</body>
</html>"""
                yield "✅ HTML generated from template data\n"

            # ── Package as ZIP ────────────────────────────────────────
            yield "PROGRESS:60\n"
            yield "📦 Packaging for Netlify...\n"

            zip_buffer = _io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
                zf.writestr("index.html", index_html)
                # Write any extra files (CSS, JS) the frontend may have sent
                for fname, fcontent in files.items():
                    if fname != "index.html":
                        zf.writestr(fname, fcontent)
            zip_buffer.seek(0)
            yield "✅ ZIP packaged\n"

            # ── Deploy to Netlify ─────────────────────────────────────
            yield "STEP:DEPLOY\n"
            yield "PROGRESS:80\n"
            yield "📤 Uploading to Netlify...\n"

            deploy_api_url = f"https://api.netlify.com/api/v1/sites/{NETLIFY_SITE_ID}/deploys"
            deploy_res = await asyncio.to_thread(
                requests.post,
                deploy_api_url,
                headers={
                    "Authorization": f"Bearer {NETLIFY_TOKEN}",
                    "Content-Type": "application/zip",
                },
                data=zip_buffer.read(),
                timeout=180,
            )

            if deploy_res.status_code not in [200, 201]:
                yield f"ERROR:Netlify API {deploy_res.status_code}: {deploy_res.text[:300]}\n"
                return

            deploy_json = deploy_res.json()
            live_url = (
                deploy_json.get("ssl_url")
                or deploy_json.get("deploy_ssl_url")
                or NETLIFY_SITE_URL
            )

            yield "STEP:DONE\n"
            yield "PROGRESS:100\n"
            yield "✅ Deploy successful!\n"
            yield f"URL:{live_url}\n"

        except Exception as e:
            import traceback
            traceback.print_exc()
            yield f"ERROR:{type(e).__name__}: {str(e)}\n"

    return StreamingResponse(generate(), media_type="text/plain")

# -------------------------------
# ✅ RUN SERVER
# -------------------------------
if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8080))
    uvicorn.run("app:app", host="0.0.0.0", port=port, reload=False, log_level="info")
