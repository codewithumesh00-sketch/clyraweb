import io
import zipfile
import requests
import os
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Dict

router = APIRouter()

NETLIFY_TOKEN = os.getenv("NETLIFY_TOKEN")
NETLIFY_SITE_ID = os.getenv("NETLIFY_SITE_ID")

class DeployRequest(BaseModel):
    files: Dict[str, str]
    projectName: str
    platform: str = "netlify"

@router.post("/deploy")
def deploy_site(req: DeployRequest):
    try:
        zip_buffer = io.BytesIO()

        with zipfile.ZipFile(zip_buffer, "w") as zipf:
            for path, content in req.files.items():
                zipf.writestr(path, content)

        zip_buffer.seek(0)

        headers = {
            "Authorization": f"Bearer {NETLIFY_TOKEN}",
            "Content-Type": "application/zip"
        }

        url = f"https://api.netlify.com/api/v1/sites/{NETLIFY_SITE_ID}/deploys"

        response = requests.post(
            url,
            headers=headers,
            data=zip_buffer.read()
        )

        if response.status_code not in [200, 201]:
            return {
                "success": False,
                "error": response.text
            }

        data = response.json()

        return {
            "success": True,
            "url": data.get("ssl_url") or data.get("url")
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }
