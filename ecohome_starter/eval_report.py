from datetime import datetime


# Thresholds for turning average scores into qualitative judgements.
_STRONG_THRESHOLD = 0.8   # at/above this, a metric is a strength
_WEAK_THRESHOLD = 0.6     # below this, a metric is a weakness

# Maps a weak metric to a concrete, actionable improvement suggestion.
_IMPROVEMENT_SUGGESTIONS = {
    "accuracy": "Improve factual accuracy: ensure the agent grounds every figure "
                "in tool data and double-checks that prices, times and savings are "
                "internally consistent.",
    "relevance": "Improve relevance: strengthen the system prompt so the agent "
                 "always addresses the specific device and timeframe in the question "
                 "rather than giving generic advice.",
    "completeness": "Improve completeness: reinforce that every recommendation must "
                    "include a specific time, a cost analysis, a solar consideration, "
                    "and a savings estimate.",
    "usefulness": "Improve usefulness: push the agent to give concrete, time-based, "
                  "actionable steps with numbers instead of vague suggestions.",
    "tool_appropriateness": "Improve tool appropriateness: discourage calling tools "
                            "that aren't needed for the question to avoid wasted calls.",
    "tool_completeness": "Improve tool completeness: strengthen instructions so the "
                         "agent always gathers all the data a question requires before "
                         "answering (e.g. checking both prices and weather for solar+cost "
                         "questions).",
}

# Human-friendly labels for the metrics.
_METRIC_LABELS = {
    "accuracy": "Accuracy",
    "relevance": "Relevance",
    "completeness": "Completeness",
    "usefulness": "Usefulness",
    "tool_appropriateness": "Tool Appropriateness",
    "tool_completeness": "Tool Completeness",
}


def generate_evaluation_report(test_results, response_evals, tool_evals):
    """
    Aggregate per-test evaluations into a structured, system-level report.

    Args:
        test_results (list): the test_results list (each item has test_id, question,
            response, etc.) — used for labelling the per-test breakdown.
        response_evals (list): one evaluate_response() dict per test, same order.
        tool_evals (list): one evaluate_tool_usage() dict per test, same order.

    Returns:
        dict: a structured report with aggregate metrics, an overall score,
        identified strengths and weaknesses, improvement recommendations, and a
        per-test breakdown. Display it with display_evaluation_report().
    """
    n = len(response_evals)

    # --- Aggregate each metric across all tests ----------------------------
    response_metrics = ["accuracy", "relevance", "completeness", "usefulness"]
    tool_metrics = ["tool_appropriateness", "tool_completeness"]

    averages = {}
    for m in response_metrics:
        averages[m] = round(sum(e.get(m, 0) for e in response_evals) / n, 3) if n else 0.0
    for m in tool_metrics:
        averages[m] = round(sum(e.get(m, 0) for e in tool_evals) / n, 3) if n else 0.0

    # Overall score: mean of all six aggregated metrics.
    overall_score = round(sum(averages.values()) / len(averages), 3) if averages else 0.0

    # Separate sub-scores for response quality vs tool usage.
    response_score = round(sum(averages[m] for m in response_metrics) / len(response_metrics), 3)
    tool_score = round(sum(averages[m] for m in tool_metrics) / len(tool_metrics), 3)

    # --- Diagnose strengths and weaknesses ---------------------------------
    strengths = [
        f"{_METRIC_LABELS[m]} is strong (avg {averages[m]:.2f})."
        for m in averages if averages[m] >= _STRONG_THRESHOLD
    ]

    # A metric is weak if EITHER its average is low, OR a large share of
    # individual tests score poorly on it (averages can hide bimodal results).
    def _share_failing(metric, evals):
        if not n:
            return 0.0
        return sum(1 for e in evals if e.get(metric, 0) < _WEAK_THRESHOLD) / n

    weak_metrics = []
    for m in response_metrics:
        share = _share_failing(m, response_evals)
        if averages[m] < _WEAK_THRESHOLD or share >= 0.4:
            weak_metrics.append((m, share))
    for m in tool_metrics:
        share = _share_failing(m, tool_evals)
        if averages[m] < _WEAK_THRESHOLD or share >= 0.4:
            weak_metrics.append((m, share))

    weaknesses = []
    for m, share in weak_metrics:
        if averages[m] < _WEAK_THRESHOLD:
            weaknesses.append(f"{_METRIC_LABELS[m]} needs improvement (avg {averages[m]:.2f}).")
        else:
            weaknesses.append(
                f"{_METRIC_LABELS[m]} is inconsistent: avg looks acceptable "
                f"({averages[m]:.2f}) but {share:.0%} of tests scored below "
                f"{_WEAK_THRESHOLD}."
            )

    # --- Build improvement recommendations from the weaknesses -------------
    recommendations = [_IMPROVEMENT_SUGGESTIONS[m] for m, _ in weak_metrics]
    if not recommendations:
        recommendations.append(
            "Performance is solid across all metrics. Consider adding more diverse "
            "or harder test cases to find edge cases and push the agent further."
        )

    # --- Per-test breakdown for transparency -------------------------------
    per_test = []
    for i in range(n):
        tr = test_results[i] if i < len(test_results) else {}
        per_test.append({
            "test_id": tr.get("test_id", f"test_{i+1}"),
            "question": tr.get("question", ""),
            "response_overall": response_evals[i].get("overall_score", 0),
            "tool_overall": tool_evals[i].get("overall_tool_score", 0),
            "response_feedback": response_evals[i].get("feedback", ""),
            "tool_feedback": tool_evals[i].get("feedback", ""),
        })

    # Count how many tests "passed" a reasonable bar on both axes.
    passed = sum(
        1 for i in range(n)
        if response_evals[i].get("overall_score", 0) >= _WEAK_THRESHOLD
        and tool_evals[i].get("overall_tool_score", 0) >= _WEAK_THRESHOLD
    )

    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "num_tests": n,
        "tests_passed": passed,
        "overall_score": overall_score,
        "response_score": response_score,
        "tool_score": tool_score,
        "metric_averages": averages,
        "strengths": strengths,
        "weaknesses": weaknesses,
        "recommendations": recommendations,
        "per_test": per_test,
    }


def display_evaluation_report(report):
    """
    Pretty-print a report produced by generate_evaluation_report().
    Kept separate from generation so the report data can be saved or reused.
    """
    line = "=" * 64
    print(line)
    print("           ECOHOME ENERGY ADVISOR — EVALUATION REPORT")
    print(line)
    print(f"Generated:     {report['generated_at']}")
    print(f"Tests run:     {report['num_tests']}")
    print(f"Tests passed:  {report['tests_passed']} / {report['num_tests']} "
          f"(both response & tool score >= {_WEAK_THRESHOLD})")
    print()

    # Headline scores
    print("OVERALL SCORE: {:.1%}".format(report["overall_score"]))
    print(f"  Response quality: {report['response_score']:.1%}")
    print(f"  Tool usage:       {report['tool_score']:.1%}")
    print()

    # Metric breakdown with simple bar
    print("METRIC AVERAGES")
    print("-" * 64)
    for m, score in report["metric_averages"].items():
        bar = "█" * int(round(score * 20))
        print(f"  {_METRIC_LABELS[m]:<22} {score:.2f}  {bar}")
    print()

    # Strengths
    print("STRENGTHS")
    print("-" * 64)
    if report["strengths"]:
        for s in report["strengths"]:
            print(f"  + {s}")
    else:
        print("  (No metric reached the 'strong' threshold.)")
    print()

    # Weaknesses
    print("WEAKNESSES")
    print("-" * 64)
    if report["weaknesses"]:
        for w in report["weaknesses"]:
            print(f"  - {w}")
    else:
        print("  None — all metrics at or above the acceptable threshold.")
    print()

    # Recommendations
    print("RECOMMENDATIONS FOR IMPROVEMENT")
    print("-" * 64)
    for i, rec in enumerate(report["recommendations"], 1):
        print(f"  {i}. {rec}")
    print()

    # Per-test breakdown
    print("PER-TEST BREAKDOWN")
    print("-" * 64)
    print(f"  {'Test ID':<26} {'Response':>9} {'Tools':>7}")
    for t in report["per_test"]:
        print(f"  {t['test_id']:<26} {t['response_overall']:>9.2f} {t['tool_overall']:>7.2f}")
    print(line)