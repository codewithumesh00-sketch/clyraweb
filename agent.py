import requests
import os
import json
import time
import re
import hashlib
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()

# -------------------------------
# 🔑 API CONFIGURATION
# -------------------------------
API_KEY = os.getenv("GROQ_API_KEY")
if not API_KEY:
    raise RuntimeError("GROQ_API_KEY is missing in environment")

FREEPIK_API_KEY = os.getenv("FREEPIK_API_KEY", "FPSX0115d227c7c2172201992815a0b65a17")

GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
FREEPIK_URL = "https://api.freepik.com/v1/resources/text2image"

HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

FREEPIK_HEADERS = {
    "x-freepik-api-key": FREEPIK_API_KEY,
    "Content-Type": "application/json"
}

app = FastAPI(title="Clyra AI Builder", version="3.0.0")

# ✅ CORS Setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# -------------------------------
# ✅ KEEP: FREEPIK IMAGE GENERATOR
# -------------------------------
def generate_freepik_image(prompt: str, style: str = "photorealistic", size: str = "1200x600") -> str:
    """Generates a real image using Freepik API with intelligent fallbacks."""
    try:
        os.makedirs("cache", exist_ok=True)
        cache_key = hashlib.md5(f"{prompt}:{style}:{size}".encode()).hexdigest()
        cache_file = f"cache/{cache_key}.json"
        
        if os.path.exists(cache_file):
            try:
                with open(cache_file, "r", encoding="utf-8") as f:
                    cached = json.load(f)
                    if cached.get("url") and cached.get("timestamp", 0) > time.time() - 604800:
                        return cached["url"]
            except:
                pass
        
        payload = {
            "prompt": f"{prompt}, professional, high quality, {style}, commercial use",
            "negative_prompt": "blurry, low quality, distorted, watermark, text, signature, frame, border",
            "style": style,
            "aspect_ratio": "16:9" if "1200x600" in size else ("4:3" if "800x600" in size else "1:1"),
            "model": "flux-1"
        }
        
        response = requests.post(
            FREEPIK_URL,
            headers=FREEPIK_HEADERS,
            json=payload,
            timeout=60
        )
        
        if response.status_code == 200:
            result = response.json()
            image_url = (
                result.get("data", {}).get("url") or 
                result.get("url") or
                result.get("image_url")
            )
            
            if image_url:
                cache_data = {
                    "url": image_url,
                    "prompt": prompt,
                    "style": style,
                    "timestamp": time.time()
                }
                with open(cache_file, "w", encoding="utf-8") as f:
                    json.dump(cache_data, f)
                return image_url
        
        print(f"⚠️ Freepik API error ({response.status_code}): {response.text[:200]}")
        
    except requests.exceptions.Timeout:
        print(f"⚠️ Freepik API timeout for: {prompt[:50]}")
    except requests.exceptions.ConnectionError:
        print(f"⚠️ Freepik connection error")
    except Exception as e:
        print(f"⚠️ Freepik generation error: {type(e).__name__}: {e}")
    
    # Fallback placeholder
    encoded_prompt = re.sub(r'[^a-zA-Z0-9]+', '+', prompt.strip())[:40]
    bg_color = "2563eb" if style == "photorealistic" else "7c3aed"
    return f"https://placehold.co/{size}/{bg_color}/ffffff?text={encoded_prompt}+🪑"


# -------------------------------
# ✅ KEEP: CLEAN RESPONSE UTILS
# -------------------------------
def clean_output(text: str) -> str:
    """Removes markdown code fences and trims whitespace."""
    if not text:
        return ""
    return (
        text.replace("```json", "")
        .replace("```html", "")
        .replace("```jsx", "")
        .replace("```javascript", "")
        .replace("```typescript", "")
        .replace("```", "")
        .strip()
    )


def extract_text(res_json: dict) -> str | None:
    """Safely extracts text from Groq API response."""
    try:
        return res_json["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as e:
        print(f"⚠️ extract_text error: {e}")
        return None


# -------------------------------
# ✅ KEEP: SAFE FALLBACK CONFIG
# -------------------------------
def get_fallback() -> dict:
    """Returns a safe, minimal config when AI generation fails."""
    return {
        "theme": {"primary": "#2563eb", "secondary": "#7c3aed", "background": "#0f172a", "text": "#ffffff", "muted": "#94a3b8"},
        "navigation": {"logoText": "AI Business", "links": ["Home", "About", "Services", "Pricing", "Blog", "Contact"]},
        "hero": {"badge": "AI Website Builder", "heading": "Grow Your Business Faster", "subheading": "Modern AI-powered websites built instantly.", "ctaPrimary": {"text": "Get Started", "href": "/contact"}, "ctaSecondary": {"text": "Explore Services", "href": "/services"}},
        "features": [],
        "about": {"heading": "About Our Company", "content": "We create high-converting digital experiences.", "features": []},
        "services": [],
        "pricing": [],
        "blog": {"heading": "Latest Insights", "posts": []},
        "contact": {"heading": "Contact Us", "subheading": "We'd love to hear from you.", "email": "hello@example.com", "phone": "+1 (555) 010-0000", "address": "Global"},
        "footer": {"company": "AI Business", "description": "Built with Clyra AI", "copyright": "© 2026"}
    }


# -------------------------------
# ✅ KEEP: GROQ API CALL WITH RETRY
# -------------------------------
def call_groq(messages: list[dict]) -> dict | None:
    """Calls Groq API with exponential backoff retry logic."""
    payload = {"model": GROQ_MODEL, "temperature": 0.4, "messages": messages}
    
    for attempt in range(3):
        try:
            response = requests.post(GROQ_URL, headers=HEADERS, json=payload, timeout=120)
            
            if response.status_code == 200:
                return response.json()
            
            print(f"⚠️ Groq error ({response.status_code}, attempt {attempt + 1}): {response.text[:200]}")
            time.sleep(2 ** attempt)
            
        except requests.exceptions.Timeout:
            print(f"⚠️ Groq timeout (attempt {attempt + 1})")
            time.sleep(2 ** attempt)
        except requests.exceptions.ConnectionError:
            print(f"⚠️ Groq connection error (attempt {attempt + 1})")
            time.sleep(2 ** attempt)
        except Exception as e:
            print(f"⚠️ Groq API error: {type(e).__name__}: {e}")
            break
    
    return None


# -------------------------------
# ✅ KEEP: MAIN UI JSON GENERATOR
# -------------------------------
def generate_ui_json(prompt: str, current_content: dict | None = None) -> dict:
    """Generates complete JSON config for website content via Groq AI."""
    try:
        if not prompt:
            return get_fallback()

        edit_block = ""
        if current_content and isinstance(current_content, dict):
            snippet = json.dumps(current_content, ensure_ascii=False)[:5000]
            edit_block = f"\nCurrent config:\n{snippet}\n\nOnly update requested sections. Keep structure identical.\n"

        structured_prompt = f"""
Generate a complete JSON config for a modern business website.
{edit_block}
User request: {prompt}

Return ONLY valid JSON with this exact structure (no markdown, no explanations):

{{
  "theme": {{"primary": "#2563eb", "secondary": "#7c3aed", "background": "#0f172a", "text": "#ffffff", "muted": "#94a3b8"}},
  "navigation": {{"logoText": "...", "links": ["Home", "About", "Services", "Pricing", "Blog", "Contact"]}},
  "hero": {{"badge": "...", "heading": "...", "subheading": "...", "ctaPrimary": {{"text": "...", "href": "/contact"}}, "ctaSecondary": {{"text": "...", "href": "/services"}}}},
  "features": [{{"icon": "⚡", "title": "...", "desc": "..."}}],
  "about": {{"heading": "...", "content": "...", "features": ["...", "..."]}},
  "services": [{{"title": "...", "desc": "...", "price": "..."}}],
  "pricing": [{{"name": "...", "price": "...", "features": ["...", "..."], "highlighted": true}}],
  "blog": {{"heading": "...", "posts": [{{"title": "...", "excerpt": "...", "date": "...", "image": ""}}]}},
  "contact": {{"heading": "...", "subheading": "...", "email": "...", "phone": "...", "address": "..."}},
  "footer": {{"company": "...", "description": "...", "copyright": "..."}}
}}
"""
        messages = [
            {"role": "system", "content": "Return ONLY valid JSON. No markdown, no explanations, no code fences."},
            {"role": "user", "content": structured_prompt}
        ]

        res = call_groq(messages)
        if not res:
            print("⚠️ Groq call failed, using fallback")
            return get_fallback()

        text = extract_text(res)
        if not text:
            return get_fallback()

        cleaned = clean_output(text)
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if match:
            cleaned = match.group(0)

        return json.loads(cleaned)

    except json.JSONDecodeError as e:
        print(f"❌ JSON decode error: {e}")
        return get_fallback()
    except Exception as e:
        print(f"❌ generate_ui_json error: {type(e).__name__}: {e}")
        return get_fallback()


# -------------------------------
# ✅ KEEP: BLOG GENERATOR (SEO Content)
# -------------------------------
def generate_seo_blog(topic: str) -> dict:
    """Generates SEO-optimized HTML blog content."""
    try:
        messages = [
            {"role": "system", "content": "Write SEO optimized HTML blog content. Return clean HTML only."},
            {"role": "user", "content": f"Write a professional, SEO-optimized HTML blog article about: {topic}. Include proper headings, paragraphs, and semantic HTML."}
        ]

        res = call_groq(messages)
        if not res:
            return {"title": topic, "blog": "<p>Content generation temporarily unavailable.</p>"}

        output = extract_text(res)
        return {"title": topic.title(), "blog": clean_output(output) if output else "<p>Empty response</p>"}

    except Exception as e:
        print(f"⚠️ Blog generation error: {e}")
        return {"title": topic, "blog": f"<p>Content generation error: {str(e)}</p>"}


# -------------------------------
# ✅ NEW: TEMPLATE MAP + SELECTOR (40 Live Templates)
# -------------------------------
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

def choose_template_from_prompt(prompt: str) -> str:
    """Maps prompt keywords to one of 40 live templates."""
    text = prompt.lower()
    for key, value in TEMPLATE_NAME_MAP.items():
        if key in text:
            return value
    return "template1"  # Default fallback


# -------------------------------
# ✅ NEW: SIMPLE /generate ENDPOINT
# -------------------------------
class GenerateRequest(BaseModel):
    prompt: str
    currentSchema: dict | None = None


class BlogRequest(BaseModel):
    topic: str


@app.post("/generate", response_model_exclude_none=True)
async def generate(req: GenerateRequest):
    """
    Generate a single-page website schema using one of 40 live templates.
    
    New Architecture:
    - 🎯 Template selection from prompt keywords
    - 🎨 AI-generated content via Groq
    - 🖼️ Real hero image via Freepik
    - ✨ editableData for frontend TSX templates
    """
    prompt = req.prompt.strip()
    
    if not prompt:
        raise HTTPException(status_code=400, detail="Prompt is required")
    
    # Generate AI content
    data = generate_ui_json(prompt, req.currentSchema)
    
    # Generate hero image
    image = generate_freepik_image(prompt)
    
    # Select template from 40 options
    template_id = choose_template_from_prompt(prompt)
    
    # Build simple, template-ready schema
    schema = {
        "category": "business",
        "templateId": template_id,
        "editableData": {
            "hero": {
                "title": prompt.title(),
                "subtitle": "Generated by Clyra AI",
                "image": image
            },
            **data  # Merge all AI-generated content sections
        }
    }

    print(f"✅ Generated template '{template_id}' for: '{prompt[:50]}{'...' if len(prompt) > 50 else ''}'")
    
    return schema


# -------------------------------
# ✅ KEEP: /update ENDPOINT
# -------------------------------
@app.post("/update")
async def update_site(req: GenerateRequest):
    """
    Update an existing website schema with new content.
    Preserves existing structure while refreshing AI content.
    """
    if not req.prompt:
        raise HTTPException(status_code=400, detail="Prompt is required")
    if not req.currentSchema:
        raise HTTPException(status_code=400, detail="currentSchema is required for updates")
    
    updated_data = generate_ui_json(req.prompt, req.currentSchema)
    schema = {**req.currentSchema, **updated_data}
    
    return schema


# -------------------------------
# ✅ KEEP: /generate-blog ENDPOINT
# -------------------------------
@app.post("/generate-blog")
async def generate_blog(req: BlogRequest):
    """Generate SEO-optimized blog content for a given topic."""
    if not req.topic:
        raise HTTPException(status_code=400, detail="Topic is required")
    
    result = generate_seo_blog(req.topic)
    return result


# -------------------------------
# 🏥 HEALTH CHECK
# -------------------------------
@app.get("/health")
def health_check():
    """Production health check endpoint."""
    return {
        "status": "healthy",
        "version": "3.0.0",
        "model": GROQ_MODEL,
        "timestamp": time.time()
    }


# -------------------------------
# 📊 METRICS ENDPOINT
# -------------------------------
@app.get("/metrics")
def get_metrics():
    """Basic metrics endpoint for monitoring."""
    return {
        "uptime": time.time(),
        "endpoints": ["/generate", "/generate-blog", "/update", "/health", "/metrics"]
    }


# -------------------------------
# 🚀 RUN SERVER
# -------------------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=8000,
        workers=1,
        reload=False,
        log_level="info"
    )