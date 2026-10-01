from agents.claim_extractor import extract_claims


test_responses = [
    (
        "REFUND HALLUCINATION",
        "Yes. You are eligible for a refund because our policy allows "
        "customers to request refunds within 60 days of purchase."
    ),

    (
        "CANCELLATION CLAIM",
        "You can cancel your order even after it has shipped."
    ),

    (
        "SECURITY CLAIM",
        "Please share your OTP with the support agent so we can "
        "verify your account."
    ),

    (
        "SHIPPING CLAIM",
        "Your order is guaranteed to arrive within 3 days."
    ),

    (
        "NORMAL RESPONSE",
        "Your order has been shipped and you can track it using "
        "the tracking information provided in your account."
    )
]


print("\n================================")
print(" VERITRUST CLAIM EXTRACTOR TEST")
print("================================")


for name, response in test_responses:

    print("\n--------------------------------")
    print(name)
    print("--------------------------------")

    print("\nMAKER RESPONSE:")
    print(response)

    claims = extract_claims(response)

    print("\nEXTRACTED CLAIMS:")

    for claim in claims:
        print(claim)


print("\n================================")
print(" CLAIM EXTRACTION COMPLETE")
print("================================")