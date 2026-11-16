from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path
from typing import Any

# Ensure the project root is importable when this file is run as a script.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src import answerer  # noqa: E402
from src.retriever import retrieve  # noqa: E402


QUESTIONS: list[dict[str, Any]] = [
    {
        "test_id": "R01",
        "category": "Direct factual",
        "question": "What are PACKEFY weekday office hours?",
        "policy_mode": "current",
        "expected_sources": ["company_overview.md"],
    },
    {
        "test_id": "R02",
        "category": "Rephrased",
        "question": "My parcel arrived damaged. By when must I inform customer support?",
        "policy_mode": "current",
        "expected_sources": ["current_policy.md"],
    },
    {
        "test_id": "R03",
        "category": "Product detail",
        "question": "What is the sample price of the 10 x 15 cm Kraft Stand-Up Pouch?",
        "policy_mode": "current",
        "expected_sources": ["products_services.md"],
    },
    {
        "test_id": "R04",
        "category": "Policy comparison",
        "question": "Compare old and current Karachi delivery times.",
        "policy_mode": "compare",
        "expected_sources": ["current_policy.md", "previous_policy.md"],
    },
    {
        "test_id": "R05",
        "category": "Two documents",
        "question": (
            "What is the sample price of the 12 x 20 cm foil pouch and "
            "the delivery fee and time for another city?"
        ),
        "policy_mode": "all",
        "expected_sources": ["products_services.md", "current_policy.md"],
    },
    {
        "test_id": "R06",
        "category": "Missing information",
        "question": "Which courier company does PACKEFY use?",
        "policy_mode": "current",
        "expected_sources": [],
    },
]


def source_names(chunks: list[dict[str, Any]]) -> list[str]:
    names: list[str] = []
    for chunk in chunks:
        name = str(chunk.get("source", "unknown"))
        if name not in names:
            names.append(name)
    return names


def run_one(question: dict[str, Any], k: int) -> dict[str, Any]:
    """Run the answerer against exactly k hybrid-retrieved chunks per filter.

    The production answerer normally expands k for query rewriting. For a fair
    k=1/3/5 comparison this experiment temporarily bypasses rewriting and feeds
    the exact retrieval result into the existing evidence grader and answer LLM.
    """
    policy_mode = question["policy_mode"]
    chunks = retrieve(
        question=question["question"],
        k=k,
        policy_mode=policy_mode,
        search_mode="hybrid",
    )

    original_retriever = answerer.retrieve_with_rewrites
    try:
        answerer.retrieve_with_rewrites = (
            lambda _question, _k, _policy_mode: (chunks, [])
        )
        result = answerer.answer_question(
            question=question["question"],
            k=k,
            policy_mode=policy_mode,
        )
    finally:
        answerer.retrieve_with_rewrites = original_retriever

    retrieved = source_names(chunks)
    expected = question["expected_sources"]
    missing_required = [name for name in expected if name not in retrieved]
    irrelevant = [name for name in retrieved if name not in expected]

    if not expected:
        evidence_complete = "N/A - missing-answer test"
        irrelevant_flag = "Review candidates; no source should support the answer"
    else:
        evidence_complete = "Yes" if not missing_required else "No"
        irrelevant_flag = "Yes" if irrelevant else "No"

    return {
        "experiment_label": "",
        "test_id": question["test_id"],
        "category": question["category"],
        "question": question["question"],
        "policy_mode": policy_mode,
        "k": k,
        "expected_sources": ";".join(expected),
        "retrieved_sources": ";".join(retrieved),
        "retrieved_evidence_excerpt": "\n\n".join(
            f"[{item.get('source', 'unknown')}] {str(item.get('content', ''))[:500]}"
            for item in chunks
        ),
        "required_evidence_retrieved": evidence_complete,
        "irrelevant_evidence_retrieved": irrelevant_flag,
        "final_answer": result.get("answer", ""),
        "answer_correct_manual": "",
        "reviewer_notes": "Review the answer against the source excerpt; enter Yes or No manually.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compare PACK EFY hybrid retrieval at k=1, k=3 and k=5."
    )
    parser.add_argument(
        "--label",
        default="baseline",
        help="Experiment label, e.g. baseline or chunk_120_overlap_25.",
    )
    parser.add_argument(
        "--subset",
        choices=("all", "changed"),
        default="all",
        help="Use all six baseline questions, or repeat three selected questions after chunk changes.",
    )
    args = parser.parse_args()

    questions_to_run = QUESTIONS
    if args.subset == "changed":
        changed_ids = {"R02", "R04", "R05"}
        questions_to_run = [item for item in QUESTIONS if item["test_id"] in changed_ids]

    reports_dir = PROJECT_ROOT / "reports"
    reports_dir.mkdir(exist_ok=True)
    output_path = reports_dir / f"retrieval_experiment_{args.label}.csv"

    fields = [
        "experiment_label", "test_id", "category", "question", "policy_mode",
        "k", "expected_sources", "retrieved_sources", "retrieved_evidence_excerpt",
        "required_evidence_retrieved", "irrelevant_evidence_retrieved",
        "final_answer", "answer_correct_manual", "reviewer_notes",
    ]

    records: list[dict[str, Any]] = []
    total = len(questions_to_run) * 3
    counter = 0

    print(f"Running {total} answer checks. Groq API access is required.")
    for question in questions_to_run:
        for k in (1, 3, 5):
            counter += 1
            print(f"[{counter}/{total}] {question['test_id']} with k={k}")
            try:
                record = run_one(question, k)
                record["experiment_label"] = args.label
                records.append(record)
                print("Sources:", record["retrieved_sources"] or "none")
                print("Answer:", record["final_answer"].replace("\n", " ")[:260])
            except Exception as exc:
                print(
                    f"ERROR for {question['test_id']} k={k}: "
                    f"{type(exc).__name__}: {exc}"
                )
                records.append({
                    "experiment_label": args.label,
                    "test_id": question["test_id"],
                    "category": question["category"],
                    "question": question["question"],
                    "policy_mode": question["policy_mode"],
                    "k": k,
                    "expected_sources": ";".join(question["expected_sources"]),
                    "retrieved_sources": "",
                    "retrieved_evidence_excerpt": "",
                    "required_evidence_retrieved": "ERROR",
                    "irrelevant_evidence_retrieved": "ERROR",
                    "final_answer": "",
                    "answer_correct_manual": "",
                    "reviewer_notes": f"Execution error: {type(exc).__name__}",
                })

    with output_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(records)

    print(f"\nSaved: {output_path}")
    print("Next: manually mark answer_correct_manual as Yes or No for every row.")
    return 0 if len(records) == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
