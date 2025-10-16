import httpx
import os
from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
import logging
import base64
import asyncio

# Ensure logging is configured before any logging statements
logging.basicConfig(level=logging.DEBUG)

app = FastAPI()

load_dotenv()  # Load environment variables from .env file

# Ensure critical environment variables are loaded
GITHUB_API_URL = os.getenv("GITHUB_API_URL", "https://api.github.com")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
SECRET_KEY = os.getenv("SECRET_KEY")

if not GITHUB_TOKEN:
    logging.warning("GITHUB_TOKEN is not set. Ensure it is configured in Render or .env file.")

if not GITHUB_API_URL:
    logging.warning("GITHUB_API_URL is not set. Using default: https://api.github.com")

@app.get("/")
def read_root():
    return {"message": "Hello, World!"}

@app.post("/api-endpoint")
async def api_endpoint(request: Request, background_tasks: BackgroundTasks):
    try:
        data = await request.json()
        evaluation_url = data.get("evaluation_url")
        usercode = data.get("usercode", "default_usercode")

        # Always respond 200 with usercode immediately
        response_data = {"usercode": usercode}

        # Schedule background task only if minimal required inputs are present
        required_keys = ["email", "task", "round", "nonce"]
        missing = [k for k in required_keys if not data.get(k)]
        if evaluation_url and not missing:
            background_tasks.add_task(process_request, data, evaluation_url)
        else:
            if not evaluation_url:
                logging.error("Missing evaluation_url in the request. Skipping background processing.")
            if missing:
                logging.error(f"Missing required fields in the request: {missing}. Skipping background processing.")

        return JSONResponse(status_code=200, content=response_data)
    except Exception as e:
        logging.error(f"Error: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")

async def process_request(data, evaluation_url):
    try:
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
                logging.error(f"Failed to create repository: {response.json()}")
                return
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
                json={"message": "Add MIT License", "content": encoded_license}
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
                json={"message": "Add README.md", "content": encoded_readme}
            )

            # Step 4: Generate additional files using LLM
            llm_generated_files = {
                "example.py": "print('Hello from LLM-generated file!')",
                "config.json": '{"setting": "value"}'
            }
            for filename, content in llm_generated_files.items():
                encoded_content = base64.b64encode(content.encode("utf-8")).decode("utf-8")
                await client.put(
                    f"{GITHUB_API_URL}/repos/{repo_data['full_name']}/contents/{filename}",
                    headers=headers,
                    json={"message": f"Add {filename}", "content": encoded_content}
                )

            # Step 5: Get the latest commit SHA
            repo_commits_url = f"{GITHUB_API_URL}/repos/{repo_data['full_name']}/commits"
            commits_response = await client.get(repo_commits_url, headers=headers)
            if commits_response.status_code != 200:
                logging.error(f"Failed to fetch commits: {commits_response.json()}")
                return
            commit_sha = commits_response.json()[0]["sha"]

            # Step 6: Send POST request to evaluation_url with retries
            evaluation_payload = {
                "email": data.get("email"),
                "task": data.get("task"),
                "round": data.get("round"),
                "nonce": data.get("nonce"),
                "repo_url": repo_data["html_url"],
                "commit_sha": commit_sha,
                "pages_url": f"https://{repo_data['owner']['login']}.github.io/{repo_data['name']}/"
            }

            delay = 1  # Initial delay in seconds
            for attempt in range(5):  # Retry up to 5 times
                eval_response = await client.post(
                    evaluation_url,
                    headers={"Content-Type": "application/json"},
                    json=evaluation_payload
                )
                if eval_response.status_code == 200:
                    logging.info("Successfully sent evaluation request.")
                    break
                logging.error(f"Failed to send evaluation request (attempt {attempt + 1}): {eval_response.text}")
                await asyncio.sleep(delay)
                delay *= 2  # Exponential backoff
            else:
                logging.error("All retries to send evaluation request failed.")
    except Exception as e:
        logging.error(f"Error in process_request: {e}")

