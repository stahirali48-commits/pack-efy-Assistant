
import csv
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "tests"))

from run_retrieval_experiment import QUESTIONS, run_one

csv_path = PROJECT_ROOT / "reports" / "retrieval_experiment_chunk_120_overlap_25.csv"

with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
    rows = list(csv.DictReader(f))

targets = [("R05", 1), ("R05", 3)]
question_map = {q["test_id"]: q for q in QUESTIONS}

for test_id, k in targets:
    print(f"\nRetrying {test_id}, k={k}")
    print("Waiting 10 seconds to reduce rate-limit risk...")
    time.sleep(10)

    try:
        result = run_one(question_map[test_id], k)
        result["experiment_label"] = "chunk_120_overlap_25"
        result["reviewer_notes"] = "Retry successful; manual review required."

        for row in rows:
            if row["test_id"] == test_id and int(row["k"]) == k:
                row.update(result)
                break

        print("SUCCESS")
        print("Sources:", result["retrieved_sources"])
        print("Answer:", result["final_answer"])

    except Exception as exc:
        print("RETRY FAILED:", type(exc).__name__, str(exc))
        print("Existing CSV row preserved.")

with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=rows[0].keys())
    writer.writeheader()
    writer.writerows(rows)

print("\nCSV updated. Existing manual evaluations preserved.")
print(csv_path)
