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
        
    def extract(self, text):
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

# Create an instance of the ClaimExtractor class
extractor = ClaimExtractor()

# Example text to extract claims from
text = """
Agriculture, you did on eggs, by the way. The egg prices came down to 50%. You got them down to 50%. Once we got involved, they were going through the sky. The egg prices, they were going through the sky. And you did a fantastic job. Now we have lots of eggs in there. Much cheaper down to about 59% now. And they're going down further. We charge 2.8% for so many things that other countries are charging 200%
"""

# Extract claims from the text
# Split the extracted claims into separate sentences
extracted_claims = extractor.extract(text)
extracted_claims = extracted_claims[0].replace('.\n', '. ').split('. ')

# Print the extracted claims
print("\nExtracted Claims:")
for i, claim in enumerate(extracted_claims, 1):
    print(f"{i}. {claim}\n")