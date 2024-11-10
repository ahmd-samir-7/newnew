from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import httpx
import json
import os
from typing import Dict, Any
from dotenv import load_dotenv
import httpx
from groq import Groq
import re

# Load environment variables
load_dotenv()

# Initialize FastAPI app
app = FastAPI(title="GitHub PR Reviewer")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuration
GITHUB_API_URL = "https://api.github.com"
GORK_CLOUD_API_URL = "https://api.gorkcloud.com/v1"
GITHUB_APP_TOKEN = os.getenv("GITHUB_APP_TOKEN")
GORK_CLOUD_API_KEY = os.getenv("GROQ_API_KEY")

# HTTP client for making API requests
http_client = httpx.AsyncClient()

async def fetch_pr_diff(pull_request_url: str) -> str:
    """
    Fetch the pull request diff from GitHub.
    """
    headers = {
        "Accept": "application/vnd.github.v3.diff",
        "Authorization": f"Bearer {GITHUB_APP_TOKEN}",
        "X-GitHub-Api-Version": "2022-11-28"
    }
    
    async with http_client as client:
        response = await client.get(
            pull_request_url,
            headers=headers,
            follow_redirects=True
        )
        
        if response.status_code != 200:
            raise HTTPException(
                status_code=response.status_code,
                detail=f"Failed to fetch PR diff: {response.text}"
            )
            
        return response.text

async def analyze_code_changes(diff_content: str) -> str:
    """
    Analyze code changes using the GORK API.
    """
    headers = {
        "Authorization": f"Bearer {GORK_CLOUD_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": "llama-3.2-11b-text-preview",
        "messages": [
            {
                "role": "system",
                "content": "You are a helpful code reviewer. Analyze the following code changes and provide constructive feedback."
            },
            {
                "role": "user",
                "content": f"Please review this code diff:\n\n{diff_content}"
            }
        ]
    }
    
    async with http_client as client:
        response = await client.post(
            f"{GORK_CLOUD_API_URL}/chat/completions",
            headers=headers,
            json=payload
        )
        
        if response.status_code != 200:
            raise HTTPException(
                status_code=response.status_code,
                detail=f"Failed to analyze code: {response.text}"
            )
            
        return response.json()["choices"][0]["message"]["content"]

async def post_pr_comment(pull_request_url: str, comment: str) -> None:
    """
    Post a general comment on the GitHub pull request.
    """
    # The pull request URL can be used to derive the issue comments URL
    issue_url = pull_request_url.replace("/pulls/", "/issues/") + "/comments"

    headers = {
        "Authorization": f"Bearer {GITHUB_APP_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
        "X-GitHub-Api-Version": "2022-11-28"
    }

    payload = {
        "body": comment
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(
            issue_url,
            headers=headers,
            json=payload
        )

        if response.status_code != 201:
            raise HTTPException(
                status_code=response.status_code,
                detail=f"Failed to post comment: {response.text}"
            )

@app.post("/webhook")  # Changed from /webhook/github to /webhook
async def github_webhook(request: Request):
    """
    Handle GitHub webhook events for pull requests.
    """
    # Add logging to debug webhook payload
    payload = await request.json()
    print(f"Received webhook payload: {json.dumps(payload, indent=2)}")
    print(f"Headers: {dict(request.headers)}")
    
    # Only process pull request events
    if request.headers.get("X-GitHub-Event") != "pull_request":
        print(f"Ignoring non-pull request event: {request.headers.get('X-GitHub-Event')}")
        return {"message": "Event ignored"}
    
    # Only process when PRs are opened or synchronized
    if payload["action"] not in ["opened", "synchronize"]:
        print(f"Ignoring PR action: {payload['action']}")
        return {"message": "Action ignored"}
    
    pull_request = payload["pull_request"]
    pr_url = pull_request["url"]
    
    try:
        # Fetch PR diff
        print(f"Fetching diff for PR: {pr_url}")
        diff_content = await fetch_pr_diff(pr_url)
        
        # Analyze code changes
        print("Analyzing code changes with Olama API")
        feedback = await analyze_code_changes(diff_content)
        
        # Post comment with feedback
        print("Posting feedback as PR comment")
        await post_pr_comment(pr_url, feedback)
        
        return {"message": "PR review completed successfully"}
        
    except Exception as e:
        print(f"Error processing PR review: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error processing PR review: {str(e)}"
        )

@app.get("/")
async def root():
    """
    Root endpoint to verify the server is running.
    """
    return {"message": "GitHub PR Reviewer is running"}

@app.get("/health")
async def health_check():
    """
    Simple health check endpoint.
    """
    return {"status": "healthy"}

async def fetch_pr_diff(pull_request_url: str) -> str:
    """
    Fetch the pull request diff from GitHub.
    """
    headers = {
        "Accept": "application/vnd.github.v3.diff",
        "Authorization": f"Bearer {GITHUB_APP_TOKEN}",
        "X-GitHub-Api-Version": "2022-11-28"
    }

    async with httpx.AsyncClient() as client:
        response = await client.get(
            pull_request_url,
            headers=headers,
            follow_redirects=True
        )

        if response.status_code != 200:
            raise HTTPException(
                status_code=response.status_code,
                detail=f"Failed to fetch PR diff: {response.text}"
            )

        return response.text

async def analyze_code_changes(diff_content: str) -> str:
    """
    Analyze code changes using the Groq API.
    """
    client = Groq()
    completion = client.chat.completions.create(
        model="llama-3.2-11b-text-preview",
        messages=[
            {
                "role": "system",
                "content": "You are a helpful code reviewer. Analyze the following code changes and provide constructive feedback."
            },
            {
                "role": "user",
                "content": f"Please review this code diff:\n\n{diff_content}"
            }
        ],
        temperature=1,
        max_tokens=1024,
        top_p=1,
        stream=True,
        stop=None,
    )

    feedback = ""
    for chunk in completion:
        feedback += chunk.choices[0].delta.content or ""

    return feedback


    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{GORK_CLOUD_API_URL}/chat/completions",
            headers=headers,
            json=payload
        )

        if response.status_code != 200:
            raise HTTPException(
                status_code=response.status_code,
                detail=f"Failed to analyze code: {response.text}"
            )

        return response.json()["choices"][0]["message"]["content"]

import re

async def post_pr_comment(pull_request_url: str, comment: str) -> None:
    """
    Post a general comment on the GitHub pull request.
    """
    # Extract the repository owner, name, and pull request number from the pull_request_url
    match = re.match(r"https://api\.github\.com/repos/(?P<owner>[^/]+)/(?P<repo>[^/]+)/pulls/(?P<pull_number>\d+)", pull_request_url)
    if not match:
        raise ValueError("Invalid pull request URL format")

    # Construct the correct issue comments URL
    owner = match.group("owner")
    repo = match.group("repo")
    pull_number = match.group("pull_number")
    issue_comments_url = f"https://api.github.com/repos/{owner}/{repo}/issues/{pull_number}/comments"

    headers = {
        "Authorization": f"Bearer {GITHUB_APP_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
        "X-GitHub-Api-Version": "2022-11-28"
    }

    payload = {
        "body": comment
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(
            issue_comments_url,
            headers=headers,
            json=payload
        )

        if response.status_code != 201:
            raise HTTPException(
                status_code=response.status_code,
                detail=f"Failed to post comment: {response.text}"
            )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=80)  # Changed port to 80