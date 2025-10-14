import httpx
import os
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
import logging
import base64

app = FastAPI()

load_dotenv()  # Load environment variables from .env file

GITHUB_API_URL = os.getenv("GITHUB_API_URL")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
SECRET_KEY = os.getenv("SECRET_KEY", "default_secret")

logging.basicConfig(level=logging.DEBUG)

@app.get("/")
def read_root():
    return {"message": "Hello, World!"}

@app.post("/api-endpoint")
async def api_endpoint(request: Request):
    try:
        data = await request.json()
        if data.get("secret") != SECRET_KEY:
            return JSONResponse(status_code=403, content={"error": "Forbidden"})
        if data.get("round") == 1 :
            data = await request.json()
            repo_name = data.get("task", "default-repo-name")
            description = "A FastAPI-based application for solving captcha tasks."
            is_public = True

            headers = {
                "Authorization": f"token {GITHUB_TOKEN}",
                "Accept": "application/vnd.github+json"
            }
            payload = {
                "name": repo_name,
                "description": description,
                "private": not is_public
            }

            async with httpx.AsyncClient() as client:
                # Step 1: Create the repository
                response = await client.post(f"{GITHUB_API_URL}/user/repos", headers=headers, json=payload)
                if response.status_code != 201:
                    raise HTTPException(status_code=response.status_code, detail=response.json())
                repo_data = response.json()

                # Step 2: Add an MIT License
                license_content = """MIT License

Copyright (c) 2023

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""
                encoded_license = base64.b64encode(license_content.encode("utf-8")).decode("utf-8")
                await client.put(
                    f"{GITHUB_API_URL}/repos/{repo_data['full_name']}/contents/LICENSE",
                    headers=headers,
                    json={
                        "message": "Add MIT License",
                        "content": encoded_license
                    }
                )

                # Step 3: Add a README.md
                readme_content = f"""# {repo_name}

## Summary
This project is a FastAPI-based application for solving captcha tasks.

## Setup
1. Clone the repository:
```bash
git clone https://github.com/{repo_data['full_name']}.git
```
2. Navigate to the project directory:
```bash
cd {repo_name}
```
3. Install dependencies:
```bash
pip install -r requirements.txt
```
4. Run the application:
```bash
uvicorn main:app --reload
```

## Usage
- Access the root endpoint:
```bash
curl -X GET http://127.0.0.1:8000/
```
- Send a POST request to `/api-endpoint`:
```bash
curl -X POST http://127.0.0.1:8000/api-endpoint \
    -H "Content-Type: application/json" \
    -d '{{"email": "student@example.com", "secret": "abcd", "task": "{repo_name}", "round": 1, "nonce": "ab12-...", "brief": "Create a captcha solver."}}'
```

## License
This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
"""
                encoded_readme = base64.b64encode(readme_content.encode("utf-8")).decode("utf-8")
                await client.put(
                    f"{GITHUB_API_URL}/repos/{repo_data['full_name']}/contents/README.md",
                    headers=headers,
                    json={
                        "message": "Add README.md",
                        "content": encoded_readme
                    }
                )

                # Step 4: Enable GitHub Pages
                pages_payload = {"source": {"branch": "main"}}
                response = await client.post(
                    f"{GITHUB_API_URL}/repos/{repo_data['full_name']}/pages",
                    headers=headers,
                    json=pages_payload
                )
                if response.status_code != 201:
                    raise HTTPException(status_code=response.status_code, detail=response.json())

            return JSONResponse(status_code=200, content={"ok": True, "repo_url": repo_data["html_url"]})
        return JSONResponse(status_code=200, content={"ok": True})
    except Exception as e:
        logging.error(f"Error: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")

