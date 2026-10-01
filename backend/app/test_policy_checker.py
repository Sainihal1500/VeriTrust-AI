from agents.policy_checker import check_policy_contradictions


def run_test(name, draft, evidence):
    print("\n================================")
    print(name)
    print("================================")

    result = check_policy_contradictions(
        draft,
        evidence
    )

    print("MAKER:")
    print(draft)

    print("\nRESULT:")
    print(result)


run_test(
    "TEST 1 — WRONG REFUND PERIOD",
    "You can request a refund within 60 days of purchase.",
    [
        {
            "text": """
            Customers may request a refund within 30 calendar days
            of the original purchase date.
            """
        }
    ]
)


run_test(
    "TEST 2 — CANCELLATION AFTER SHIPPING",
    "You can cancel your order even after it has shipped.",
    [
        {
            "text": """
            Orders may be cancelled before shipment.
            Once an order has shipped, cancellation is normally
            unavailable.
            """
        }
    ]
)


run_test(
    "TEST 3 — UNSAFE OTP REQUEST",
    "Please share your OTP with the support agent so we can verify your account.",
    [
        {
            "text": """
            Customers must never share passwords or one-time
            authentication codes with support agents.
            """
        }
    ]
)


run_test(
    "TEST 4 — GUARANTEED DELIVERY",
    "Your order is guaranteed to arrive within 3 days.",
    [
        {
            "text": """
            Standard shipping generally takes 3-7 business days.
            Delivery times are estimates and may be affected by
            carrier delays.
            """
        }
    ]
)


print("\n================================")
print("ALL POLICY CHECKER TESTS COMPLETE")
print("================================")