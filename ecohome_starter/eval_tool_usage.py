def _extract_tools_used(messages):
    """
    Pull the list of tool names that were actually called from the agent's
    message history. A tool-result message carries a tool_call_id and the
    name of the tool that produced it (same pattern the notebook uses above).
    """
    tools_used = []
    for msg in messages:
        # Messages may be LangChain objects (model_dump) or plain dicts.
        try:
            obj = msg.model_dump()
        except AttributeError:
            obj = msg if isinstance(msg, dict) else {}
        if obj.get("tool_call_id"):
            name = obj.get("name") or getattr(msg, "name", None)
            if name:
                tools_used.append(name)
    return tools_used


def evaluate_tool_usage(messages, expected_tools):
    """
    Evaluate whether the agent used the right tools for the task.

    Rule-based and deterministic: we compare the tools the agent actually
    called against the expected tools using set operations.

    Two metrics (each 0.0 - 1.0):
      - tool_appropriateness: of the tools the agent DID call, how many were
        expected? (penalises calling irrelevant/unnecessary tools)
      - tool_completeness: of the expected tools, how many did the agent call?
        (penalises missing necessary tools)

    Args:
        messages (list): the agent response message history (response["messages"]).
        expected_tools (list): tool names a correct answer should use.

    Returns:
        dict with the two metric scores, the tools used/expected, and feedback.
    """
    tools_used = _extract_tools_used(messages)
    used_set = set(tools_used)
    expected_set = set(expected_tools)

    # Tool completeness: did we cover everything that was needed?
    if expected_set:
        matched = used_set & expected_set
        tool_completeness = len(matched) / len(expected_set)
        missing = expected_set - used_set
    else:
        tool_completeness = 1.0
        missing = set()

    # Tool appropriateness: were the tools we DID call relevant?
    if used_set:
        relevant = used_set & expected_set
        tool_appropriateness = len(relevant) / len(used_set)
        extra = used_set - expected_set
    else:
        # No tools called at all. If some were expected, that's a failure.
        tool_appropriateness = 1.0 if not expected_set else 0.0
        extra = set()

    # Build human-readable feedback.
    feedback_parts = []
    if not tools_used:
        feedback_parts.append(
            "No tools were called. The agent answered from general knowledge "
            "instead of gathering data." if expected_set
            else "No tools were expected or called."
        )
    else:
        feedback_parts.append(
            f"Agent called {len(tools_used)} tool(s): {sorted(used_set)}."
        )
    if missing:
        feedback_parts.append(
            f"Missing expected tool(s): {sorted(missing)}. "
            "These were needed to fully answer the question."
        )
    else:
        feedback_parts.append("All expected tools were used.")
    if extra:
        feedback_parts.append(
            f"Called unexpected tool(s): {sorted(extra)}. "
            "Not necessarily wrong, but not required for this question."
        )

    overall = round((tool_appropriateness + tool_completeness) / 2, 2)

    return {
        "tool_appropriateness": round(tool_appropriateness, 2),
        "tool_completeness": round(tool_completeness, 2),
        "overall_tool_score": overall,
        "tools_used": sorted(used_set),
        "tools_expected": sorted(expected_set),
        "tools_missing": sorted(missing),
        "tools_extra": sorted(extra),
        "feedback": " ".join(feedback_parts),
    }
