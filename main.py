from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import httpx
import json
import os
from typing import Dict, Any, List, Tuple
from dotenv import load_dotenv
from groq import Groq
import re
import difflib

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
GITHUB_APP_TOKEN = os.getenv("GITHUB_APP_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# HTTP client for making API requests
http_client = httpx.AsyncClient()

async def fetch_file_content(contents_url: str, repo_url: str, ref: str, path: str) -> str:
    """
    Fetch file content from GitHub using the correct raw content URL.
    
    Args:
        contents_url: The GitHub API contents URL
        repo_url: The repository URL
        ref: The commit SHA or branch name
        path: The file path
    """
    headers = {
        "Authorization": f"Bearer {GITHUB_APP_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
        "X-GitHub-Api-Version": "2022-11-28"
    }
    
    try:
        async with httpx.AsyncClient() as client:
            # Use the contents API endpoint instead of raw URL
            api_url = f"{repo_url}/contents/{path}?ref={ref}"
            print(f"Fetching content from: {api_url}")
            
            response = await client.get(
                api_url,
                headers=headers,
                follow_redirects=True
            )
            
            if response.status_code != 200:
                print(f"Error fetching file content: {response.status_code} - {response.text}")
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"Failed to fetch file content: {response.text}"
                )
            
            content_data = response.json()
            if "content" not in content_data:
                raise HTTPException(
                    status_code=400,
                    detail="No content found in response"
                )
            
            # Decode base64 content
            import base64
            return base64.b64decode(content_data["content"]).decode('utf-8')
            
    except json.JSONDecodeError:
        print("Error decoding JSON response")
        raise HTTPException(
            status_code=500,
            detail="Invalid response format from GitHub API"
        )
    except Exception as e:
        print(f"Unexpected error fetching file: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error fetching file content: {str(e)}"
        )

async def fetch_pr_diff(pull_request_url: str) -> str:
    """Fetch the pull request diff from GitHub."""
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
            print(f"Error fetching PR diff: {response.status_code} - {response.text}")
            raise HTTPException(
                status_code=response.status_code,
                detail=f"Failed to fetch PR diff: {response.text}"
            )

        return response.text

async def format_code_snippet(code_lines: List[str]) -> str:
    """Format code snippet with syntax highlighting and line numbers."""
    snippet = "```go\n"
    for line in code_lines:
        snippet += f"{line}\n"
    snippet += "```"
    return snippet

async def process_file_changes(file_diff: str, file_content: str, filename: str) -> str:
    """Process changes in a specific file and generate a summary."""
    if not file_diff or not file_content:
        print(f"Missing diff or content for file: {filename}")
        return ""

    diff_lines = file_diff.split('\n')
    file_lines = file_content.split('\n')
    
    # Create a unified diff
    unified_diff = '\n'.join(difflib.unified_diff(
        file_lines, file_lines, fromfile=filename, tofile=filename, lineterm=''
    ))
    
    # Format the unified diff as a code snippet
    code_snippet = await format_code_snippet(unified_diff.split('\n'))
    
    # Generate the review comment
    review_comment = f"""
### Changes in {filename}

{code_snippet}

Please review the changes in the file and let me know if you have any concerns or suggestions.
"""
    
    return review_comment

async def post_review_comment(pull_request_url: str, commit_id: str, path: str, body: str) -> None:
    """Post a review comment with formatted code snippet."""
    # Code to post review comment remains the same as before, but the `line` parameter is now removed

@app.post("/webhook")
async def github_webhook(request: Request):
    """Handle GitHub webhook events for pull requests."""
    try:
        print("Received webhook request")
        payload = await request.json()
        print(f"Webhook payload: {json.dumps(payload, indent=2)}")
        
        if request.headers.get("X-GitHub-Event") != "pull_request":
            return {"message": "Event ignored"}
        
        if payload["action"] not in ["opened", "synchronize"]:
            return {"message": "Action ignored"}
        
        pull_request = payload["pull_request"]
        repo_url = pull_request["base"]["repo"]["url"]
        commit_sha = pull_request["head"]["sha"]
        
        # Fetch files changed in the PR
        async with httpx.AsyncClient() as client:
            files_url = f"{pull_request['url']}/files"
            print(f"Fetching files from: {files_url}")
            
            files_response = await client.get(
                files_url,
                headers={
                    "Authorization": f"Bearer {GITHUB_APP_TOKEN}",
                    "Accept": "application/vnd.github.v3+json",
                    "X-GitHub-Api-Version": "2022-11-28"
                }
            )
            
            if files_response.status_code != 200:
                print(f"Error fetching PR files: {files_response.status_code} - {files_response.text}")
                raise HTTPException(
                    status_code=files_response.status_code,
                    detail=f"Failed to fetch PR files: {files_response.text}"
                )
            
            files_changed = files_response.json()
            print(f"Found {len(files_changed)} changed files")
            
            # Generate PR summary
            pr_summary = f"""
### Pull Request Summary

This pull request includes the following changes:

"""
            for file in files_changed:
                if "patch" in file:
                    try:
                        file_content = await fetch_file_content(
                            file.get("contents_url", ""),
                            repo_url,
                            commit_sha,
                            file["filename"]
                        )
                        
                        file_review_comment = await process_file_changes(
                            file["patch"],
                            file_content,
                            file["filename"]
                        )
                        
                        if file_review_comment:
                            pr_summary += file_review_comment
                    except Exception as e:
                        print(f"Error processing file {file['filename']}: {str(e)}")
                else:
                    pr_summary += f"- **{file.get('filename')}**: File was added or deleted\n"
        
        # Post PR summary as a review comment
        await post_review_comment(
            pull_request["url"],
            commit_sha,
            ".",
            pr_summary
        )
        
        return {"message": "PR review completed successfully"}
        
    except Exception as e:
        print(f"Error processing webhook: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
