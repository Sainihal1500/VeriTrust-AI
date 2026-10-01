from agents.judge import judge_agent
from agents.corrector import corrector_agent
from rag.retriever import retrieve_evidence


question = "I bought the product 45 days ago. Can I get a refund?"


# Deliberately incorrect Maker response
bad_draft = """
Yes. You are eligible for a refund because our policy
allows customers to request refunds within 60 days of purchase.
"""


print("\n===== CUSTOMER QUERY =====")
print(question)


print("\n===== HALLUCINATED MAKER RESPONSE =====")
print(bad_draft)


print("\n===== RETRIEVING TRUSTED EVIDENCE =====")
evidence = retrieve_evidence(question)

for item in evidence:
    print(f"Source: {item['source']}")


print("\n===== FIRST JUDGE =====")

judgment = judge_agent(
    question,
    bad_draft,
    evidence
)

print(judgment)


print("\n===== CORRECTOR =====")

corrected_response = corrector_agent(
    question,
    bad_draft,
    evidence,
    judgment
)

print(corrected_response)


print("\n===== SECOND JUDGE =====")

final_judgment = judge_agent(
    question,
    corrected_response,
    evidence
)

print(final_judgment)