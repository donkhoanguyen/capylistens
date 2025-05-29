from src.fact_checking.fact_checker import FactChecker

# Create an instance of the FactChecker class
checker = FactChecker()

# Example claims to check
claims = [
    "Albert Einstein was a theoretical physicist",
    "Albert Einstein developed the theory of relativity"
]

# Print the fact-checking results
print("\nFact-checking Results:")

# Check the claims
results = checker.check_claims(claims)

# for i, (claim, result) in enumerate(results, 1):
#     print(f"{i}. Claim: {claim}")
#     print(f"   Result: {result}\n")
