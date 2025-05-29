from gpt_extractor import ClaimExtractor

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

    def extract_claims(self, text: str) -> List[str]:
        """Extract claims from the given text using OpenAI."""
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a helpful assistant that extracts claims from text. List each claim on a new line starting with a hyphen."},
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

    def batch_extract_claims(self, texts: List[str]) -> List[List[str]]:
        """Extract claims from multiple texts."""
        all_claims = []
        for text in texts:
            claims = self.extract_claims(text)
            all_claims.append(claims)
        return all_claims

def main():
    # Initialize the claim extractor
    extractor = ClaimExtractor()  # Will use OPENAI_API_KEY from environment
    
    # # Example text to extract claims from
    # sample_text = """
    # The new study shows that regular exercise improves cognitive function. 
    # Participants who exercised 3 times per week showed better memory retention.
    # Additionally, the research found that a balanced diet enhanced the benefits of exercise.
    # """
    
    # # Extract claims from single text
    # claims = extractor.extract_claims(sample_text)
    # print("\nExtracted claims from single text:")
    # for claim in claims:
    #     print(f"- {claim}")
        
    # Example with multiple texts
    multiple_texts = [
        "Mid-Night tonight, I would say. And China charges American rice farmers and over-quoted, it's called, a tariff rate of 65 percent, South Korea charges 50. Actually, they charge different from 50 percent to 513 percent in Japan. Our friend charges a 700 percent, but that's because they don't want a selling rice another thing who can blame.",
    ]
    
    # Extract claims from multiple texts
    batch_claims = extractor.batch_extract_claims(multiple_texts)
    print("\nExtracted claims from multiple texts:")
    for i, text_claims in enumerate(batch_claims):
        print(f"\nText {i+1}:")
        for claim in text_claims:
            print(f"- {claim}")

if __name__ == "__main__":
    main()
