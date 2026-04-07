def generate_logo(business_name: str, primary_color: str):
    first_letter = business_name[0].upper()

    return f"""
<svg width="120" height="120" xmlns="http://www.w3.org/2000/svg">
  <rect width="120" height="120" rx="20" fill="{primary_color}" />
  <text x="50%" y="55%" font-size="48" text-anchor="middle" fill="white" font-family="Arial" dy=".3em">
    {first_letter}
  </text>
</svg>
"""