from deploy_router import router as deploy_router
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


# -------------------------------
# ✅ SAVE / LOAD PROJECT
# -------------------------------
@app.post("/save")
async def save_project(data: dict):
    project_id = str(uuid.uuid4())
    os.makedirs("projects", exist_ok=True)
    with open(f"projects/{project_id}.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    return {"success": True, "project_id": project_id}


@app.get("/project/{project_id}")
def load_project(project_id: str):
    path = f"projects/{project_id}.json"
    if not os.path.exists(path):
        return {"success": False, "error": "Project not found"}
    with open(path, "r", encoding="utf-8") as f:
        return {"success": True, "data": json.load(f)}


# -------------------------------
# ✅ ZIP DOWNLOAD ENDPOINT
# -------------------------------
@app.post("/deploy")
async def deploy(data: dict):
    files = data.get("files", {})
    project_name = data.get("projectName", "clyraweb-project")
    template_name = data.get("templateName")

    if not NETLIFY_TOKEN:
        return {"success": False, "error": "NETLIFY_TOKEN missing"}

    if not NETLIFY_SITE_ID:
        return {"success": False, "error": "NETLIFY_SITE_ID missing"}

    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # ✅ Template deploy mode
            if template_name:
                template_src = (
                    Path(__file__).parent.parent
                    / "frontend"
                    / "src"
                    / "templates"
                    / f"{template_name}.tsx"
                )

                if not template_src.exists():
                    return {
                        "success": False,
                        "error": f"Template not found: {template_name} at {template_src}"
                    }

                # ✅ Copy real clean template
                real_template_code = template_src.read_text(encoding="utf-8")

                template_dest = (
                    temp_path
                    / "src"
                    / "templates"
                    / f"{template_name}.tsx"
                )
                template_dest.parent.mkdir(parents=True, exist_ok=True)
                template_dest.write_text(real_template_code, encoding="utf-8")

                print(f"✅ Copied real template: {template_name}")

                # ✅ Create app router files
                app_dir = temp_path / "src" / "app"
                app_dir.mkdir(parents=True, exist_ok=True)

                # ✅ FIXED JSX SYNTAX
                import json
                editable_data = data.get("editableData", {})
                editable_data_json = json.dumps(editable_data)
                (app_dir / "page.tsx").write_text(
                    f'''import TemplatePage from "../templates/{template_name}";

export default function Home() {{
  return <TemplatePage editableData={{{editable_data_json}}} />;
}}
''',
                    encoding="utf-8"
                )

                # ✅ Root layout
                (app_dir / "layout.tsx").write_text(
                    '''export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en">
      <head>
        <script src="https://cdn.tailwindcss.com"></script>
      </head>
      <body>{children}</body>
    </html>
  )
}
''',
                    encoding="utf-8"
                )

            else:
                # ✅ Normal frontend file deploy
                for file_path, content in files.items():
                    full_path = temp_path / file_path
                    full_path.parent.mkdir(parents=True, exist_ok=True)
                    full_path.write_text(content, encoding="utf-8")

            # ✅ package.json
            pkg_json = {
                "name": project_name.lower().replace(" ", "-"),
                "version": "1.0.0",
                "private": True,
                "scripts": {
                    "dev": "next dev",
                    "build": "next build",
                    "start": "next start",
                    "lint": "next lint"
                },
                "dependencies": {
                    "next": "14.2.3",
                    "react": "18.2.0",
                    "react-dom": "18.2.0",
                    "lucide-react": "^0.542.0",
                    "zustand": "^5.0.0"
                },
                "devDependencies": {
                    "@types/node": "^20.0.0",
                    "@types/react": "^18.2.0",
                    "@types/react-dom": "^18.2.0",
                    "typescript": "^5.0.0"
                }
            }
            (temp_path / "package.json").write_text(
                json.dumps(pkg_json, indent=2), encoding="utf-8"
            )

            # ✅ Add next.config.js for static export
            (temp_path / "next.config.js").write_text(
                '''
/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "export",
  images: {
    unoptimized: true,
  },
  trailingSlash: true,
}
module.exports = nextConfig
''',
                encoding="utf-8"
            )

            # ✅ Add fallback store files (prevents import errors)
            store_dir = temp_path / "src" / "store"
            store_dir.mkdir(parents=True, exist_ok=True)

            # ✅ useThemeStore.ts fallback
            theme_data = data.get("theme", {
                "backgroundColor": "#ffffff",
                "textColor": "#000000",
                "primaryColor": "#000000",
                "secondaryColor": "#f5f5f5",
                "accentColor": "#333333",
                "fontFamily": "Inter, sans-serif",
                "borderRadius": 8,
                "sectionSpacing": 80,
            })
            theme_json = json.dumps(theme_data)
            (store_dir / "useThemeStore.ts").write_text(
                f'''
// Auto-generated fallback for deployment
export const useThemeStore = () => {{
  return {{
    theme: {theme_json},
    setTheme: () => {{}},
  }};
}};
''',
                encoding="utf-8"
            )

            # ✅ STEP 2 — REPLACE WITH UNIVERSAL SAFE STORE (ZUSTAND-LIKE)
            (store_dir / "useWebsiteBuilderStore.ts").write_text(
                '''
// ✅ Universal deployment-safe fallback store
const store = {
  pages: [],
  currentPage: "home",
  regions: {},
  updatePage: () => {},
  setCurrentPage: () => {},
  updateRegion: () => {},
};

export const useWebsiteBuilderStore = (selector?: any) => {
  return selector ? selector(store) : store;
};

export const useRegionValue = (key: string) => {
  return (store.regions as any)?.[key] ?? null;
};
''',
                encoding="utf-8"
            )

            # ✅ Add tsconfig.json - FIXED: Separate write_text calls
            (temp_path / "tsconfig.json").write_text(
                '''
{
  "compilerOptions": {
    "target": "ES2017",
    "lib": ["dom", "dom.iterable", "esnext"],
    "allowJs": true,
    "skipLibCheck": true,
    "strict": true,
    "noEmit": true,
    "esModuleInterop": true,
    "module": "esnext",
    "moduleResolution": "bundler",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "jsx": "preserve",
    "incremental": true,
    "plugins": [{"name": "next"}],
    "paths": {
      "@/*": ["./src/*"]
    }
  },
  "include": ["next-env.d.ts", "**/*.ts", "**/*.tsx", ".next/types/**/*.ts"],
  "exclude": ["node_modules"]
}
''',
                encoding="utf-8"
            )

            # ✅ Add next-env.d.ts - FIXED: Now a separate independent call
            (temp_path / "next-env.d.ts").write_text(
                '''/// <reference types="next" />
/// <reference types="next/image-types/global" />

// NOTE: This file should not be edited
''',
                encoding="utf-8"
            )

            # ✅ DEBUG: Print all files being built
            print("🚀 BUILD FILES:")
            for root, dirs, files_list in os.walk(temp_path):
                for file in files_list:
                    rel_path = Path(root).relative_to(temp_path) / file
                    print(f"  📄 {rel_path}")

            # ✅ Install dependencies
            print("📦 Installing dependencies...")
            subprocess.run(
                ["npm.cmd", "install"],
                cwd=temp_path,
                check=True,
                shell=True
            )

            print("🏗️ Building Next.js project...")
            subprocess.run(
                ["npx.cmd", "next", "build"],
                cwd=temp_path,
                check=True,
                shell=True
            )

            # ✅ Zip the OUT folder only (static files for Netlify)
            out_dir = temp_path / "out"
            if not out_dir.exists():
                return {"success": False, "error": "Build failed: 'out' directory not found"}

            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
                for file in out_dir.rglob("*"):
                    if file.is_file():
                        zf.write(file, file.relative_to(out_dir))

            zip_buffer.seek(0)
            print(f"📦 Zipped {out_dir} for Netlify deploy")

            # ✅ Deploy to Netlify
            deploy_url = f"https://api.netlify.com/api/v1/sites/{NETLIFY_SITE_ID}/deploys"
            print(f"📤 Deploying to: {deploy_url}")

            deploy_res = requests.post(
                deploy_url,
                headers={
                    "Authorization": f"Bearer {NETLIFY_TOKEN}",
                    "Content-Type": "application/zip",
                },
                data=zip_buffer.read(),
                timeout=180,  # Extended timeout for large builds
            )

            if deploy_res.status_code not in [200, 201]:
                print(f"❌ Netlify API Error: {deploy_res.status_code} - {deploy_res.text}")
                return {"success": False, "error": f"Netlify API: {deploy_res.text}"}

            deploy_json = deploy_res.json()
            deploy_url_result = (
                deploy_json.get("ssl_url")
                or deploy_json.get("deploy_ssl_url")
                or NETLIFY_SITE_URL
            )

            print(f"✅ Deploy successful: {deploy_url_result}")

            return {
                "success": True,
                "url": deploy_url_result,
                "deploy_id": deploy_json.get("id"),
            }

    except subprocess.CalledProcessError as e:
        print(f"💥 Build error: {e.stderr if hasattr(e, 'stderr') else str(e)}")
        return {"success": False, "error": f"Build failed: {str(e)}"}
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"💥 Deploy exception: {str(e)}")
        return {"success": False, "error": f"{type(e).__name__}: {str(e)}"}


# -------------------------------
# ✅ RUN SERVER
# -------------------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True, log_level="info")