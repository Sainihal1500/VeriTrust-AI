from typing import TypedDict

from langgraph.graph import StateGraph, END

from agents.maker import maker_agent
from agents.judge import judge_agent
from agents.corrector import corrector_agent
from agents.policy_checker import check_policy_contradictions
from rag.retriever import retrieve_evidence


class VeriTrustState(TypedDict):
    user_query: str
    evidence: list
    draft_response: str
    policy_check: dict
    judgment: str
    corrected_response: str
    final_response: str
    decision: str


def retrieve_node(state: VeriTrustState):

    evidence = retrieve_evidence(
        state["user_query"]
    )

    return {
        "evidence": evidence
    }


def maker_node(state: VeriTrustState):

    draft = maker_agent(
        state["user_query"],
        state["evidence"]
    )

    return {
        "draft_response": draft
    }


def policy_check_node(state: VeriTrustState):

    result = check_policy_contradictions(
        state["draft_response"],
        state["evidence"]
    )

    return {
        "policy_check": result
    }


def judge_node(state: VeriTrustState):

    judgment = judge_agent(
        state["user_query"],
        state["draft_response"],
        state["evidence"]
    )

    return {
        "judgment": judgment,
        "final_response": state["draft_response"]
    }


def correction_node(state: VeriTrustState):

    corrected = corrector_agent(
        state["user_query"],
        state["draft_response"],
        state["evidence"],
        str(state["policy_check"])
    )

    return {
        "corrected_response": corrected
    }


def final_judge_node(state: VeriTrustState):

    final_judgment = judge_agent(
        state["user_query"],
        state["corrected_response"],
        state["evidence"]
    )

    return {
        "judgment": final_judgment,
        "final_response": state["corrected_response"]
    }


def route_after_policy_check(state: VeriTrustState):

    decision = state["policy_check"]["decision"]

    if decision == "CORRECT":
        return "correct"

    return "judge"


def route_after_judge(state: VeriTrustState):

    judgment = state["judgment"]

    if '"decision":"CORRECT"' in judgment:
        return "correct"

    if '"decision": "CORRECT"' in judgment:
        return "correct"

    return "approve"


def build_veritrust_graph():

    graph = StateGraph(VeriTrustState)

    graph.add_node("retrieve", retrieve_node)
    graph.add_node("maker", maker_node)
    graph.add_node("policy_check", policy_check_node)
    graph.add_node("judge", judge_node)
    graph.add_node("correct", correction_node)
    graph.add_node("final_judge", final_judge_node)

    graph.set_entry_point("retrieve")

    graph.add_edge("retrieve", "maker")
    graph.add_edge("maker", "policy_check")

    graph.add_conditional_edges(
        "policy_check",
        route_after_policy_check,
        {
            "correct": "correct",
            "judge": "judge"
        }
    )

    graph.add_conditional_edges(
        "judge",
        route_after_judge,
        {
            "correct": "correct",
            "approve": END
        }
    )

    graph.add_edge("correct", "final_judge")
    graph.add_edge("final_judge", END)

    return graph.compile()