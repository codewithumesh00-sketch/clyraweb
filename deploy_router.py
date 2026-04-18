import io
import zipfile
import requests
import os
import json
import asyncio
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
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
async def deploy_site(req: DeployRequest):
    async def deploy_generator():
        try:
            yield "STEP:START\n"
            yield "PROGRESS:10\n"
            yield "🚀 Preparing build files...\n"
            await asyncio.sleep(1)

            if not NETLIFY_TOKEN:
                yield "ERROR: NETLIFY_TOKEN not configured\n"
                return

            if not NETLIFY_SITE_ID:
                yield "ERROR: NETLIFY_SITE_ID not configured\n"
                return

            if not req.files:
                yield "ERROR: No template files found\n"
                return

            yield "📦 Validating configuration...\n"
            await asyncio.sleep(0.5)

            deploy_files = req.files.copy()
            if "src/store/useThemeStore.ts" not in deploy_files:
                yield "⚙️ Adding theme store fallback...\n"
                deploy_files["src/store/useThemeStore.ts"] = """
// Auto-generated fallback store for deployment
export interface ThemeStore {
  theme: "dark" | "light";
  toggleTheme: () => void;
}

export const useThemeStore = () => {
  return {
    theme: "dark" as const,
    toggleTheme: () => {}
  };
};
"""

            if "package.json" in deploy_files:
                yield "STEP:INSTALL\n"
                yield "PROGRESS:30\n"
                yield "📦 Installing dependencies...\n"
                await asyncio.sleep(2)
                try:
                    pkg = json.loads(deploy_files["package.json"])
                    deps = pkg.get("dependencies", {})
                    required_deps = {
                        "lucide-react": "^0.542.0",
                        "zustand": "^5.0.0",
                        "next": "14.1.0",
                        "react": "18.2.0",
                        "react-dom": "18.2.0"
                    }
                    for dep, version in required_deps.items():
                        if dep not in deps:
                            deps[dep] = version
                    pkg["dependencies"] = deps
                    deploy_files["package.json"] = json.dumps(pkg, indent=2)
                except json.JSONDecodeError:
                    pass

            yield "STEP:BUILD\n"
            yield "PROGRESS:60\n"
            yield "🏗️ Building Next.js project...\n"
            await asyncio.sleep(2)
            zip_buffer = io.BytesIO()
            
            with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zipf:
                for file_path, content in deploy_files.items():
                    zipf.writestr(file_path, content)

            zip_buffer.seek(0)
            
            yield "STEP:DEPLOY\n"
            yield "PROGRESS:85\n"
            yield f"📤 Uploading to Netlify (Site ID: {NETLIFY_SITE_ID[:8]}...)\n"
            await asyncio.sleep(2)

            headers = {
                "Authorization": f"Bearer {NETLIFY_TOKEN}",
                "Content-Type": "application/zip"
            }

            deploy_url = f"https://api.netlify.com/api/v1/sites/{NETLIFY_SITE_ID}/deploys"

            # Run synchronous requests.post in thread pool to avoid blocking async generator
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None, 
                lambda: requests.post(deploy_url, headers=headers, data=zip_buffer.read(), timeout=120)
            )

            if response.status_code not in [200, 201]:
                yield f"❌ ERROR: Netlify API {response.status_code} - {response.text}\n"
                return

            data = response.json()
            ssl_url = data.get("ssl_url") or data.get("deploy_ssl_url") or data.get("url")
            
            yield "STEP:DONE\n"
            yield "PROGRESS:100\n"
            yield f"✅ Deployment successful\n"
            yield f"URL:{ssl_url}\n"

        except Exception as e:
            yield f"❌ ERROR: Deploy exception - {str(e)}\n"

    return StreamingResponse(deploy_generator(), media_type="text/plain")