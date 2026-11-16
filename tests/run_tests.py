from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.answerer import answer_question, MISSING_ANSWER  # noqa: E402


def split_sources(value: str) -> list[str]:
    return [item.strip() for item in (value or "").split(";") if item.strip()]


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the 20-question PACK EFY RAG test set.")
    parser.add_argument(
        "--output",
        default="reports/test_results_rerun.csv",
        help="Output CSV path relative to the project root.",
    )
    args = parser.parse_args()

    input_path = PROJECT_ROOT / "tests" / "test_set.csv"
    output_path = PROJECT_ROOT / args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with input_path.open("r", encoding="utf-8-sig", newline="") as handle:
        test_cases = list(csv.DictReader(handle))

    if len(test_cases) != 20:
        raise ValueError(f"Expected 20 test questions; found {len(test_cases)}.")

    output_fields = [
        "test_id", "category", "question", "expected_answer", "expected_sources",
        "actual_answer", "actual_sources", "source_match", "answer_correct_manual",
        "policy_mode", "status", "reviewer_notes",
    ]

    results: list[dict[str, Any]] = []
    for index, test in enumerate(test_cases, start=1):
        print(f"[{index}/20] {test['test_id']}: {test['question']}")
        result = answer_question(
            question=test["question"],
            k=3,
            policy_mode=test.get("policy_mode") or None,
        )
        actual_sources = list(dict.fromkeys(
            source.get("filename", "unknown") for source in result.get("sources", [])
        ))
        expected_sources = split_sources(test.get("expected_sources", ""))
        answer = result.get("answer", "")

        if expected_sources:
            source_match = all(source in actual_sources for source in expected_sources)
        else:
            source_match = answer.strip() == MISSING_ANSWER

        results.append({
            "test_id": test["test_id"],
            "category": test["category"],
            "question": test["question"],
            "expected_answer": test["expected_answer"],
            "expected_sources": ";".join(expected_sources),
            "actual_answer": answer,
            "actual_sources": ";".join(actual_sources),
            "source_match": "Yes" if source_match else "No",
            "answer_correct_manual": "",
            "policy_mode": result.get("policy_mode", test.get("policy_mode", "")),
            "status": "REVIEW",
            "reviewer_notes": (
                "Check answer facts, source support, and policy version manually; "
                "then enter Yes/No in answer_correct_manual."
            ),
        })

    with output_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=output_fields)
        writer.writeheader()
        writer.writerows(results)

    print(f"\nSaved {len(results)} rows to: {output_path}")
    print("All rows are marked REVIEW until manual evidence checking is completed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
