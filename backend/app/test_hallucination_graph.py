from rag.retriever import retrieve_evidence
from agents.corrector import corrector_agent
from agents.judge import judge_agent
from agents.policy_checker import check_policy_contradictions


print("\n================================")
print(" VERITRUST HALLUCINATION TEST")
print("================================")


# 1. Customer question

user_query = "I bought the product 45 days ago. Can I get a refund?"


# 2. Retrieve trusted evidence

evidence = retrieve_evidence(
    user_query,
    n_results=5
)


print("\nCUSTOMER:")
print(user_query)


print("\nTRUSTED EVIDENCE:")

for item in evidence:

    print(
        f"\n[{item['document_id']}] "
        f"{item['source']}"
    )

    print(item["text"][:500])


# 3. DELIBERATE HALLUCINATION
#
# We intentionally give the system an incorrect answer.
# This simulates a Maker Agent hallucination.

draft_response = (
    "Yes. You are eligible for a refund because "
    "our policy allows customers to request refunds "
    "within 60 days of purchase."
)


print("\n================================")
print(" MAKER RESPONSE")
print("================================")

print(draft_response)


# 4. Deterministic policy check

policy_check = check_policy_contradictions(
    draft_response,
    evidence
)


print("\n================================")
print(" POLICY CHECK")
print("================================")

print(policy_check)


# 5. Correct if contradiction detected

if policy_check["decision"] == "CORRECT":

    print("\n🚨 HALLUCINATION DETECTED")

    corrected_response = corrector_agent(
        user_query,
        draft_response,
        evidence,
        str(policy_check)
    )

else:

    corrected_response = draft_response


print("\n================================")
print(" CORRECTOR RESPONSE")
print("================================")

print(corrected_response)


# 6. Final Judge verification

final_judgment = judge_agent(
    user_query,
    corrected_response,
    evidence
)


print("\n================================")
print(" FINAL JUDGE")
print("================================")

print(final_judgment)


print("\n================================")
print(" VERITRUST FINAL RESULT")
print("================================")

print(corrected_response)

print("\n================================")