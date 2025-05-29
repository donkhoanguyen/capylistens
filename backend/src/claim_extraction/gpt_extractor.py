import os
from typing import List
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

class ClaimExtractor:
    def __init__(self, api_key: str = None):
        """Initialize the claim extractor with OpenAI API key."""
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OpenAI API key must be provided either directly or via OPENAI_API_KEY environment variable")
        self.client = OpenAI(api_key=self.api_key)

    async def extract_claims(self, text: str) -> List[str]:
        """Extract claims from the given text using OpenAI."""
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": os.getenv("CLAIM_EXTRACTION_PROMPT")},
                    {"role": "user", "content": f"Extract the key claims from this text: {text}"}
                ],
                temperature=0.0,
                max_tokens=1000
            )
            
            # Extract claims from response
            claims_text = response.choices[0].message.content.strip()
            claims = [claim.strip("- ") for claim in claims_text.split("\n") if claim.strip().startswith("-")]
            
            return claims

        except Exception as e:
            print(f"Error extracting claims: {str(e)}")
            return []

    async def batch_extract_claims(self, texts: List[str]) -> List[List[str]]:
        """Extract claims from multiple texts."""
        all_claims = []
        for text in texts:
            claims = await self.extract_claims(text)
            all_claims.append(claims)
        return all_claims