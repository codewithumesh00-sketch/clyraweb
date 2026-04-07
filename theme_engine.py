import random

# 🎨 Color palettes
COLOR_THEMES = [
    {
        "primary": "#8B5CF6",
        "secondary": "#06B6D4",
        "background": "#09090B",
        "text": "#FFFFFF"
    },
    {
        "primary": "#F59E0B",
        "secondary": "#EF4444",
        "background": "#FFFFFF",
        "text": "#111111"
    },
    {
        "primary": "#10B981",
        "secondary": "#3B82F6",
        "background": "#0F172A",
        "text": "#E2E8F0"
    },
    {
        "primary": "#EC4899",
        "secondary": "#6366F1",
        "background": "#111827",
        "text": "#F9FAFB"
    }
]


def generate_theme(prompt: str):
    prompt = prompt.lower()

    # 🎯 Smart theme selection
    if "restaurant" in prompt:
        theme = COLOR_THEMES[1]  # warm colors
    elif "tech" in prompt or "saas" in prompt:
        theme = COLOR_THEMES[0]
    elif "portfolio" in prompt:
        theme = COLOR_THEMES[3]
    else:
        theme = random.choice(COLOR_THEMES)

    return {
        "primary_color": theme["primary"],
        "secondary_color": theme["secondary"],
        "bg_color": theme["background"],
        "text_color": theme["text"]
    }