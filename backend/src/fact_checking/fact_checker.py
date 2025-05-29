# src/fact_checking/checker.py
from aiolimiter import AsyncLimiter
import os
import httpx
from pydantic import BaseModel
import asyncio

# Create a global rate limiter: 50 requests per 60 seconds
rate_limiter = AsyncLimiter(max_rate=50, time_period=60)

class ChatMessage(BaseModel):
    message: str

class FactChecker:
    def __init__(self, config=None):
        self.config = config
        # Load environment variables early, outside of async methods
        # This helps prevent file I/O during async operations
        self.api_key = os.environ.get('PERPLEXITY_API_KEY')
        if not self.api_key:
            # Only load from .env if not already in environment
            from dotenv import load_dotenv
            load_dotenv()
            self.api_key = os.environ.get('PERPLEXITY_API_KEY')
        
        print("FactChecker initialized.")

    async def check_claims(self, claim):
        url = "https://api.perplexity.ai/chat/completions"
        # Prepare the API request
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": "sonar-pro",
            "messages": [
                {"role": "system", "content": os.getenv("PPLX_PROMPT")},
                {"role": "user", "content": f"Verify this {claim}"},
            ],
            "stepwise_reasoning": True,
        }

        try:
            async with rate_limiter:  # <- this enforces the rate limit
                # Create an async HTTP client and make the request
                async with httpx.AsyncClient() as client:
                    response = await client.post(url, headers=headers, json=data)
                
                # Check if the request was successful
                if response.status_code == 200:
                    result = response.json()
                    reply_text = result["choices"][0]["message"]["content"]
                    print(f"Claim: {claim}\n")
                    print("Response:", reply_text, "\n")
                    return reply_text
                else:
                    error_msg = f"Error: {response.status_code}"
                    print(error_msg)
                    print(response.text)
                    return error_msg

        except Exception as e:
            error_msg = f"An error occurred: {e} here is at calling perplexity api"
            print(error_msg)
            return error_msg