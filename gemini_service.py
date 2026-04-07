import requests
import os
import time
import json
import hashlib
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("GEMINI_API_KEY")
if not API_KEY:
    raise RuntimeError("GEMINI_API_KEY is missing in environment")

CACHE_FILE = "cache.json"

# Load cache
if os.path.exists(CACHE_FILE):
    with open(CACHE_FILE, "r") as f:
        cache = json.load(f)
else:
    cache = {}


def get_cache_key(prompt):
    return hashlib.md5(prompt.encode()).hexdigest()


def save_cache():
    with open(CACHE_FILE, "w") as f:
        json.dump(cache, f)


def call_gemini(prompt):
    cache_key = get_cache_key(prompt)

    # ✅ RETURN FROM CACHE
    if cache_key in cache:
        print("⚡ Using cached response")
        return cache[cache_key]

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={API_KEY}"

    headers = {
        "Content-Type": "application/json"
    }

    body = {
        "contents": [
            {
                "parts": [
                    {"text": prompt}
                ]
            }
        ]
    }

    retries = 3

    for attempt in range(retries):
        try:
            response = requests.post(url, headers=headers, json=body)

            # ✅ SUCCESS
            if response.status_code == 200:
                data = response.json()
                text = data["candidates"][0]["content"]["parts"][0]["text"]

                # SAVE CACHE
                cache[cache_key] = text
                save_cache()

                return text

            # 🔁 HANDLE 429
            elif response.status_code == 429:
                print("⚠️ Rate limited... retrying")
                time.sleep(5)

            else:
                print("❌ Error:", response.text)
                return "Error generating response"

        except Exception as e:
            print("❌ Exception:", str(e))
            time.sleep(3)

    return "Failed after retries"