# src/claim_extraction/extractor.py

class ClaimExtractor:
    def __init__(self, config=None):
        self.config = config
        
        # Load the model during initialization
        from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
        
        # Load the tokenizer and model
        model_name = "Babelscape/t5-base-summarization-claim-extractor"
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModelForSeq2SeqLM.from_pretrained(model_name)

        print("ClaimExtractor initialized.")

    async def extract(self, text):
        print(f"Extracting claims from text: {text}")
        import torch
        
        # Tokenize input
        inputs = self.tokenizer([text], return_tensors="pt")

        # Generate output (claims)
        with torch.no_grad():
            outputs = self.model.generate(**inputs)

        # Decode and return the extracted claims
        claims = self.tokenizer.batch_decode(outputs, skip_special_tokens=True)
        return claims