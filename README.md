# 🛡️ VeriTrust AI

### Dual-Agent Maker–Judge Hallucination Guardrail System for Trusted AI Customer Service

> **Don't just let AI answer — verify the answer before you trust it.**

VeriTrust AI is a secure and auditable AI-powered customer-service system designed to make LLM responses more trustworthy.

Instead of allowing an LLM to directly answer customers, VeriTrust AI introduces an independent verification layer that checks generated responses against **trusted company data, policies, authorization rules, and claim-level evidence** before the response reaches the customer.

---

## 🚀 Why VeriTrust AI?

Large Language Models can generate responses that sound correct while containing:

- ❌ Hallucinated information
- ❌ Unsupported claims
- ❌ Incorrect policy interpretations
- ❌ Unauthorized customer-data exposure
- ❌ Unintended business guarantees
- ❌ Inconsistent answers

VeriTrust AI addresses these problems using a **hybrid architecture combining AI agents, deterministic rules, structured databases, RAG, authentication, authorization, and auditing.**

---

# 🧠 Core Idea

### Generation is not verification.

VeriTrust AI separates the process into two major AI roles:

**Maker Agent** → Generates the customer response.

**Judge Agent** → Independently verifies whether that response should be trusted.

If the response is incorrect:

**Corrector Agent** → Fixes the response.

**Final Judge** → Verifies the corrected response again.

This creates a controlled AI workflow instead of blindly trusting the first generated answer.

---

# 🏗️ System Architecture

```text
                         ┌──────────────────┐
                         │     Customer     │
                         └────────┬─────────┘
                                  │
                                  ▼
                         ┌──────────────────┐
                         │     FastAPI      │
                         └────────┬─────────┘
                                  │
                                  ▼
                         ┌──────────────────┐
                         │   Query Router   │
                         └────────┬─────────┘
                                  │
                                  ▼
                         ┌──────────────────┐
                         │  Account Router  │
                         └────────┬─────────┘
                                  │
                                  ▼
                         ┌──────────────────┐
                         │ Authentication & │
                         │  Authorization   │
                         └────────┬─────────┘
                                  │
                     ┌────────────┴────────────┐
                     │                         │
                     ▼                         ▼
              ┌──────────────┐        ┌────────────────┐
              │ Structured   │        │ RAG + ChromaDB │
              │  Database    │        │ Knowledge Base │
              └──────┬───────┘        └───────┬────────┘
                     │                         │
                     └────────────┬────────────┘
                                  │
                                  ▼
                         ┌──────────────────┐
                         │   Maker Agent    │
                         │    Qwen 3.5      │
                         └────────┬─────────┘
                                  │
                                  ▼
                         ┌──────────────────┐
                         │ Claim Extraction │
                         └────────┬─────────┘
                                  │
                                  ▼
                         ┌──────────────────┐
                         │ Claim Verification│
                         └────────┬─────────┘
                                  │
                                  ▼
                         ┌──────────────────┐
                         │  Policy Checker  │
                         └────────┬─────────┘
                                  │
                                  ▼
                         ┌──────────────────┐
                         │   Judge Agent    │
                         └────────┬─────────┘
                                  │
                 ┌────────────────┼────────────────┐
                 │                │                │
                 ▼                ▼                ▼
              APPROVE          CORRECT          BLOCK
                 │                │                │
                 │                ▼                │
                 │        ┌──────────────┐        │
                 │        │   Corrector   │        │
                 │        └──────┬───────┘        │
                 │               │                │
                 │               ▼                │
                 │        ┌──────────────┐        │
                 │        │ Final Judge  │        │
                 │        └──────┬───────┘        │
                 │               │                │
                 └───────────────┼────────────────┘
                                 │
                                 ▼
                         ┌──────────────────┐
                         │  Final Response  │
                         └────────┬─────────┘
                                  │
                                  ▼
                         ┌──────────────────┐
                         │ Audit & Metrics  │
                         └──────────────────┘
