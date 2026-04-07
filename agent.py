import requests
import os
import json
import time
import re
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("GROQ_API_KEY")
if not API_KEY:
    raise RuntimeError("GROQ_API_KEY is missing in environment")

GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}


# -------------------------------
# CLEAN RESPONSE
# -------------------------------
def clean_output(text):
    if not text:
        return ""
    return (
        text.replace("```json", "")
        .replace("```html", "")
        .replace("```jsx", "")
        .replace("```javascript", "")
        .replace("```", "")
        .strip()
    )


# -------------------------------
# SAFE GROQ TEXT EXTRACTION
# -------------------------------
def extract_text(res_json):
    try:
        return res_json["choices"][0]["message"]["content"]
    except Exception as e:
        print("⚠️ extract_text:", e)
        return None


# -------------------------------
# SAFE FALLBACK CONFIG
# -------------------------------
def get_fallback():
    return {
        "theme": {
            "primary": "#2563eb",
            "secondary": "#7c3aed",
            "background": "#0f172a",
            "text": "#ffffff",
            "muted": "#94a3b8"
        },
        "navigation": {
            "logoText": "AI Business",
            "links": [
                "Home",
                "About",
                "Services",
                "Pricing",
                "Blog",
                "Contact"
            ]
        },
        "hero": {
            "badge": "AI Website Builder",
            "heading": "Grow Your Business Faster",
            "subheading": "Modern AI-powered websites built instantly.",
            "ctaPrimary": {
                "text": "Get Started",
                "href": "/contact"
            },
            "ctaSecondary": {
                "text": "Explore Services",
                "href": "/services"
            }
        },
        "features": [],
        "about": {
            "heading": "About Our Company",
            "content": "We create high-converting digital experiences.",
            "features": []
        },
        "services": [],
        "pricing": [],
        "blog": {
            "heading": "Latest Insights",
            "posts": []
        },
        "contact": {
            "heading": "Contact Us",
            "subheading": "We’d love to hear from you.",
            "email": "hello@example.com",
            "phone": "+1 (555) 010-0000",
            "address": "Global"
        },
        "footer": {
            "company": "AI Business",
            "description": "Built with Clyra AI",
            "copyright": "© 2026"
        }
    }


# -------------------------------
# GROQ API CALL
# -------------------------------
def call_groq(messages):
    payload = {
        "model": GROQ_MODEL,
        "temperature": 0.4,
        "messages": messages
    }

    for _ in range(3):
        try:
            response = requests.post(
                GROQ_URL,
                headers=HEADERS,
                json=payload,
                timeout=120
            )

            if response.status_code == 200:
                return response.json()

            print("⚠️ Groq error:", response.text[:300])
            time.sleep(2)

        except Exception as e:
            print("⚠️ API Error:", e)
            time.sleep(2)

    return None


# -------------------------------
# MAIN UI GENERATOR
# -------------------------------
def generate_ui_json(prompt, current_content=None):
    try:
        if not prompt:
            return get_fallback()

        edit_block = ""
        if current_content and isinstance(current_content, dict):
            snippet = json.dumps(current_content, ensure_ascii=False)[:5000]
            edit_block = f"""
Current config:
{snippet}

Only update requested sections.
"""

        structured_prompt = f"""
Generate a complete JSON config for a modern multi-page business website.

{edit_block}

User request:
{prompt}

Return ONLY valid JSON with this exact structure:

{{
  "theme": {{
    "primary": "#2563eb",
    "secondary": "#7c3aed",
    "background": "#0f172a",
    "text": "#ffffff",
    "muted": "#94a3b8"
  }},
  "navigation": {{
    "logoText": "...",
    "links": ["Home", "About", "Services", "Pricing", "Blog", "Contact"]
  }},
  "hero": {{
    "badge": "...",
    "heading": "...",
    "subheading": "...",
    "ctaPrimary": {{
      "text": "...",
      "href": "/contact"
    }},
    "ctaSecondary": {{
      "text": "...",
      "href": "/services"
    }}
  }},
  "features": [
    {{
      "icon": "⚡",
      "title": "...",
      "desc": "..."
    }}
  ],
  "about": {{
    "heading": "...",
    "content": "...",
    "features": ["...", "..."]
  }},
  "services": [
    {{
      "title": "...",
      "desc": "...",
      "price": "..."
    }}
  ],
  "pricing": [
    {{
      "name": "...",
      "price": "...",
      "features": ["...", "..."],
      "highlighted": true
    }}
  ],
  "blog": {{
    "heading": "...",
    "posts": [
      {{
        "title": "...",
        "excerpt": "...",
        "date": "...",
        "image": ""
      }}
    ]
  }},
  "contact": {{
    "heading": "...",
    "subheading": "...",
    "email": "...",
    "phone": "...",
    "address": "..."
  }},
  "footer": {{
    "company": "...",
    "description": "...",
    "copyright": "..."
  }}
}}
"""

        messages = [
            {
                "role": "system",
                "content": "Return ONLY valid JSON. No markdown."
            },
            {
                "role": "user",
                "content": structured_prompt
            }
        ]

        res = call_groq(messages)
        if not res:
            return get_fallback()

        text = extract_text(res)
        if not text:
            return get_fallback()

        cleaned = clean_output(text)

        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if match:
            cleaned = match.group(0)

        return json.loads(cleaned)

    except Exception as e:
        print("❌ ERROR:", e)
        return get_fallback()


# -------------------------------
# BLOG GENERATOR
# -------------------------------
def generate_seo_blog(topic):
    try:
        messages = [
            {
                "role": "system",
                "content": "Write SEO optimized HTML blog."
            },
            {
                "role": "user",
                "content": f"Write SEO HTML blog on {topic}"
            }
        ]

        res = call_groq(messages)
        if not res:
            return {"title": topic, "blog": "<p>API Error</p>"}

        output = extract_text(res)

        return {
            "title": topic.capitalize(),
            "blog": clean_output(output)
        }

    except Exception as e:
        return {
            "title": topic,
            "blog": f"<p>Error: {str(e)}</p>"
        }