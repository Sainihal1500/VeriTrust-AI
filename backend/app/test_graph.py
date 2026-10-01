from workflows.veritrust_graph import build_veritrust_graph


app = build_veritrust_graph()


question = "I bought the product 45 days ago. Can I get a refund?"


result = app.invoke(
    {
        "user_query": question,
        "evidence": [],
        "draft_response": "",
        "policy_check": {},
        "judgment": "",
        "corrected_response": "",
        "final_response": "",
        "decision": ""
    }
)


print("\n==============================")
print("       VERITRUST RESULT")
print("==============================")

print("\nCUSTOMER:")
print(question)

print("\nMAKER:")
print(result.get("draft_response"))

print("\nPOLICY CHECK:")
print(result.get("policy_check"))

print("\nCORRECTED RESPONSE:")
print(result.get("corrected_response"))

print("\nFINAL RESPONSE:")
print(result.get("final_response"))

print("\nJUDGE:")
print(result.get("judgment"))

print("\n==============================")