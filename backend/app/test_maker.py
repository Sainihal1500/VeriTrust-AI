from agents.maker import maker_agent


question = "What is VeriTrust AI?"

answer = maker_agent(question)

print("\n===== MAKER AGENT =====")
print(answer)