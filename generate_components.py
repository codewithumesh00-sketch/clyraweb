import os
import shutil
import random

# -------------------------------
# 📁 PATH SETUP
# -------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

TEMPLATE_DIR = os.path.join(BASE_DIR, "clyraui-frontend", "templates")
OUTPUT_DIR = os.path.join(BASE_DIR, "clyraui-frontend", "src", "generated")


# -------------------------------
# 🎯 TEMPLATE SELECTION
# -------------------------------
def select_template(prompt: str):
    prompt = prompt.lower()

    real_estate_keywords = [
        "real estate", "property", "realty",
        "homes", "villa", "apartment", "broker"
    ]

    for word in real_estate_keywords:
        if word in prompt:
            return "template1"

    keywords = {
        "template1": ["business", "company", "corporate"],
        "template2": ["portfolio", "developer", "designer"],
        "template3": ["agency", "marketing", "branding"],
        "template4": ["ecommerce", "shop", "store"],
        "template5": ["app", "mobile", "ios", "android"],
        "template6": ["blog", "writer", "content"],
        "template7": ["gym", "fitness", "trainer"]
    }

    for template, words in keywords.items():
        if any(word in prompt for word in words):
            return template

    # 🎲 Smart fallback
    return random.choice([
        "template2",
        "template3",
        "template4",
        "template5",
        "template6",
        "template7"
    ])


# -------------------------------
# 🚀 GENERATE TEMPLATE FILES
# -------------------------------
def generate_template(template_name):
    template_path = os.path.join(TEMPLATE_DIR, template_name)

    if not os.path.exists(template_path):
        raise Exception(f"❌ Template not found: {template_path}")

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # 🧹 Remove old generated files
    for file in os.listdir(OUTPUT_DIR):
        file_path = os.path.join(OUTPUT_DIR, file)
        if os.path.isfile(file_path):
            os.remove(file_path)

    # 🚀 Copy selected template files
    for root, dirs, files in os.walk(template_path):
        for file in files:
            if file.endswith(".tsx") or file.endswith(".ts"):
                src_file = os.path.join(root, file)
                dest_file = os.path.join(OUTPUT_DIR, file)

                shutil.copy(src_file, dest_file)
                print(f"✅ Copied: {file}")

    print(f"\n🔥 Template '{template_name}' generated successfully!")


# -------------------------------
# 🔥 MAIN FUNCTION
# -------------------------------
def run_builder(prompt: str):
    template = select_template(prompt)
    print(f"🎯 Selected Template: {template}")
    generate_template(template)


# -------------------------------
# ▶️ TEST RUN
# -------------------------------
if __name__ == "__main__":
    user_prompt = input("Enter your website idea: ")
    run_builder(user_prompt)