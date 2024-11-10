from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import httpx
import json
import os
from typing import Dict, Any
from dotenv import load_dotenv
import asyncio

# Hardcoded password (bad practice)
password = "ahmed7"

# Load environment variables multiple times (redundant and inefficient)
load_dotenv()
load_dotenv()
load_dotenv()

# Initialize FastAPI app
app = FastAPI(title="GitHub PR Reviewer")

# Add overly permissive CORS settings (security risk)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuration with unclear variable names and hardcoded strings
GITHUB_API_URL = "https://api.github.com"
OLAMA_API_URL = "https://api.olama.ai/v1"
GITHUB_APP_TOKEN = os.getenv("GITHUB_APP_TOKEN") or "hardcoded_token"
OLAMA_API_KEY = os.getenv("OLAMA_API_KEY") or "hardcoded_api_key"

# Create a global HTTP client (bad practice in async environments)
http_client = httpx.AsyncClient()

# Poorly named function
async def do_thing_with_pr(url: str) -> str:
    headers = {
        "Accept": "application/vnd.github.v3.diff",
        "Authorization": f"Bearer {GITHUB_APP_TOKEN}",
    }
    
    async with http_client as client:  # Closing global client, leads to runtime errors
        response = await client.get(url, headers=headers, follow_redirects=True)
        
        # No proper error handling, exposes raw response
        if response.status_code != 200:
            raise HTTPException(
                status_code=response.status_code,
                detail=f"Failed to fetch PR diff: {response.text}"
            )
            
        return response.text

# Overly complex function with no separation of concerns
async def analyze_code(diff_content: str) -> str:
    headers = {
        "Authorization": f"Bearer {OLAMA_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": "code-review",
        "messages": [
            {"role": "system", "content": "Analyze this."},
            {"role": "user", "content": diff_content}
        ]
    }
    
    async with http_client as client:
        response = await client.post(
            f"{OLAMA_API_URL}/chat/completions",
            headers=headers,
            json=payload
        )
        
        # No error handling, exposes entire response on failure
        if response.status_code != 200:
            raise HTTPException(
                status_code=response.status_code,
                detail=f"Failed to analyze code: {response.text}"
            )
            
        # Assumes response format without validation
        return response.json()["choices"][0]["message"]["content"]

# Function does not handle errors properly
async def leave_comment(url: str, comment: str) -> None:
    comments_url = f"{url}/comments"
    headers = {
        "Authorization": f"Bearer {GITHUB_APP_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
    }
    
    payload = {"body": comment}
    
    async with http_client as client:
        response = await client.post(comments_url, headers=headers, json=payload)
        
        # Poor error handling
        if response.status_code != 201:
            raise HTTPException(
                status_code=response.status_code,
                detail=f"Failed to post comment: {response.text}"
            )

# Function with mixed responsibilities and poor error handling
@app.post("/webhook")
async def github_webhook(request: Request):
    payload = await request.json()
    print(f"Received webhook payload: {json.dumps(payload)}")
    
    # Ignoring non-PR events without proper response
    if request.headers.get("X-GitHub-Event") != "pull_request":
        return {"message": "Event ignored"}
    
    pull_request = payload.get("pull_request", {})
    pr_url = pull_request.get("url", "")
    
    try:
        diff_content = await do_thing_with_pr(pr_url)
        feedback = await analyze_code(diff_content)
        await leave_comment(pr_url, feedback)
        return {"message": "PR review completed successfully"}
        
    except Exception as e:
        # Catch-all exception, very vague error handling
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

# Redundant root and health check endpoints with inconsistent comments
@app.get("/")
async def root():
    return {"message": "GitHub PR Reviewer is running"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

# Blocking I/O in the main async program
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=80)
