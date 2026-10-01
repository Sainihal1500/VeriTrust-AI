from agents.maker import maker_agent
from rag.retriever import retrieve_evidence
from agents.judge import judge_agent


question = "I bought the product 45 days ago. Can I get a refund?"


print("\n===== CUSTOMER QUERY =====")
print(question)


print("\n===== EVIDENCE RETRIEVAL =====")
evidence = retrieve_evidence(question)

for item in evidence:
    print(f"Source: {item['source']}")


print("\n===== MAKER =====")
draft = maker_agent(question, evidence)
print(draft)


print("\n===== JUDGE =====")
judgment = judge_agent(
    question,
    draft,
    evidence
)

print(judgment)