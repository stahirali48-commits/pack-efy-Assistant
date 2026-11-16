
from __future__ import annotations

import math
import os
import re
from collections import Counter
from pathlib import Path
from typing import Any

import chromadb


# ==========================================
# PROJECT CONFIGURATION
# ==========================================

BASE_DIR = Path(__file__).resolve().parent.parent

DB_DIR = Path(os.getenv("PACKEFY_DB_DIR", str(BASE_DIR / "chroma_db"))).resolve()

COLLECTION_NAME = "packefy_knowledge"

DEFAULT_CANDIDATE_MULTIPLIER = 4

MIN_CANDIDATES = 12

MAX_CANDIDATES = 50

RRF_CONSTANT = 60


# ==========================================
# CONNECT TO CHROMA DATABASE
# ==========================================

client = chromadb.PersistentClient(
    path=str(DB_DIR)
)

try:

    collection = client.get_collection(
        name=COLLECTION_NAME
    )

except Exception as exc:

    raise RuntimeError(
        f"Could not open Chroma collection: {COLLECTION_NAME}. "
        "First run: python src\\build_index.py"
    ) from exc


# ==========================================
# TEXT TOKENIZATION
# ==========================================

_TOKEN_PATTERN = re.compile(
    r"\d+(?:\.\d+)?|[a-z]+",
    re.IGNORECASE
)


def _tokenize(text: str) -> list[str]:

    return [
        token.lower()
        for token in _TOKEN_PATTERN.findall(text or "")
    ]


# ==========================================
# METADATA HELPER
# ==========================================

def _metadata_value(
    metadata: dict[str, Any],
    key: str,
    default: Any = "unknown"
) -> Any:

    value = metadata.get(key, default)

    return default if value is None else value


# ==========================================
# STANDARD RESULT FORMAT
# ==========================================

def _make_record(
    doc_id: str,
    document: str,
    metadata: dict[str, Any] | None
) -> dict[str, Any]:

    metadata = metadata or {}

    return {

        "id": doc_id,

        "content": document or "",

        "source": _metadata_value(
            metadata, "source_file"
        ),

        "document_id": _metadata_value(
            metadata, "document_id"
        ),

        "version": _metadata_value(
            metadata, "version"
        ),

        "status": _metadata_value(
            metadata, "status"
        ),

        "effective_date": _metadata_value(
            metadata, "effective_date"
        ),

        "chunk_index": _metadata_value(
            metadata, "chunk_index", -1
        ),

        "distance": None,

        "semantic_rank": None,

        "keyword_rank": None,

        "bm25_score": 0.0,

        "rerank_score": 0.0,

        "retrieval_method": ""

    }


# ==========================================
# POLICY FILTERS
# ==========================================

def _policy_filters(
    policy_mode: str
) -> list[dict[str, Any] | None]:

    if policy_mode == "current":

        return [
            {"status": "Current"}
        ]

    if policy_mode == "archived":

        return [
            {"status": "Archived"}
        ]

    if policy_mode == "compare":

        return [

            {"source_file": "current_policy.md"},

            {"source_file": "previous_policy.md"}

        ]

    return [None]


# ==========================================
# LOAD FILTERED DOCUMENTS
# ==========================================

def _get_records(
    where_filter: dict[str, Any] | None = None
) -> list[dict[str, Any]]:

    kwargs = {
        "include": [
            "documents",
            "metadatas"
        ]
    }

    if where_filter is not None:

        kwargs["where"] = where_filter

    result = collection.get(**kwargs)

    ids = result.get("ids") or []

    documents = result.get("documents") or []

    metadatas = result.get("metadatas") or []

    records = []

    for doc_id, document, metadata in zip(
        ids,
        documents,
        metadatas
    ):

        if document is None:
            continue

        records.append(
            _make_record(
                doc_id,
                document,
                metadata
            )
        )

    return records


# ==========================================
# SEMANTIC SEARCH
# ==========================================

def _semantic_search(
    question: str,
    where_filter: dict[str, Any] | None,
    candidate_k: int,
    allowed_count: int
) -> list[dict[str, Any]]:

    if allowed_count <= 0:
        return []

    kwargs = {

        "query_texts": [question],

        "n_results": min(
            candidate_k,
            allowed_count
        ),

        "include": [
            "documents",
            "metadatas",
            "distances"
        ]

    }

    if where_filter is not None:

        kwargs["where"] = where_filter

    result = collection.query(**kwargs)

    ids = (result.get("ids") or [[]])[0] or []

    documents = (
        result.get("documents") or [[]]
    )[0] or []

    metadatas = (
        result.get("metadatas") or [[]]
    )[0] or []

    distances = (
        result.get("distances") or [[]]
    )[0] or []

    ranked = []

    for rank, (doc_id, document, metadata) in enumerate(
        zip(ids, documents, metadatas),
        start=1
    ):

        if document is None:
            continue

        item = _make_record(
            doc_id,
            document,
            metadata
        )

        if rank - 1 < len(distances):

            if distances[rank - 1] is not None:

                item["distance"] = float(
                    distances[rank - 1]
                )

        item["semantic_rank"] = rank

        item["retrieval_method"] = "semantic"

        ranked.append(item)

    return ranked


# ==========================================
# KEYWORD SEARCH - BM25
# ==========================================

def _bm25_search(
    question: str,
    records: list[dict[str, Any]],
    candidate_k: int,
    k1: float = 1.5,
    b: float = 0.75
) -> list[dict[str, Any]]:

    query_terms = list(
        dict.fromkeys(_tokenize(question))
    )

    if not query_terms or not records:
        return []

    tokenized_docs = [

        _tokenize(item["content"])

        for item in records

    ]

    doc_lengths = [

        len(tokens)

        for tokens in tokenized_docs

    ]

    total_docs = len(tokenized_docs)

    average_length = (
        sum(doc_lengths) / total_docs
        if total_docs else 0
    )

    if average_length == 0:
        return []

    term_frequencies = []

    document_frequencies = Counter()

    for tokens in tokenized_docs:

        frequencies = Counter(tokens)

        term_frequencies.append(frequencies)

        document_frequencies.update(
            set(tokens)
        )

    scores = []

    for doc_index, frequencies in enumerate(
        term_frequencies
    ):

        score = 0.0

        doc_length = doc_lengths[doc_index]

        for term in query_terms:

            frequency = frequencies.get(term, 0)

            if not frequency:
                continue

            df = document_frequencies[term]

            idf = math.log(
                1 + (
                    total_docs - df + 0.5
                ) / (
                    df + 0.5
                )
            )

            denominator = frequency + k1 * (

                1 - b + b * (
                    doc_length / average_length
                )

            )

            score += idf * (

                frequency * (k1 + 1)
                / denominator

            )

        if score > 0:

            scores.append(
                (score, doc_index)
            )

    scores.sort(
        key=lambda pair: pair[0],
        reverse=True
    )

    ranked = []

    for rank, (score, doc_index) in enumerate(
        scores[:candidate_k],
        start=1
    ):

        item = dict(records[doc_index])

        item["bm25_score"] = float(score)

        item["keyword_rank"] = rank

        item["retrieval_method"] = "keyword"

        ranked.append(item)

    return ranked


# ==========================================
# HYBRID SEARCH + RE-RANKING
# ==========================================

def _hybrid_search(
    question: str,
    where_filter: dict[str, Any] | None,
    records: list[dict[str, Any]],
    k: int,
    candidate_k: int
) -> list[dict[str, Any]]:

    if not records:
        return []

    candidate_k = min(
        candidate_k,
        len(records)
    )

    # Semantic results

    semantic_results = _semantic_search(

        question,

        where_filter,

        candidate_k,

        len(records)

    )

    # Keyword results

    keyword_results = _bm25_search(

        question,

        records,

        candidate_k

    )

    # Merge both result sets

    merged = {}

    for item in semantic_results:

        merged[item["id"]] = dict(item)

    for item in keyword_results:

        if item["id"] not in merged:

            merged[item["id"]] = dict(item)

        else:

            merged[item["id"]]["bm25_score"] = (
                item["bm25_score"]
            )

    semantic_ranks = {

        item["id"]: item["semantic_rank"]

        for item in semantic_results

    }

    keyword_ranks = {

        item["id"]: item["keyword_rank"]

        for item in keyword_results

    }

    # Reciprocal Rank Fusion

    for doc_id, item in merged.items():

        semantic_rank = semantic_ranks.get(doc_id)

        keyword_rank = keyword_ranks.get(doc_id)

        score = 0.0

        if semantic_rank is not None:

            score += 1 / (
                RRF_CONSTANT + semantic_rank
            )

        if keyword_rank is not None:

            score += 1 / (
                RRF_CONSTANT + keyword_rank
            )

        item["semantic_rank"] = semantic_rank

        item["keyword_rank"] = keyword_rank

        item["rerank_score"] = score

        item["retrieval_method"] = "hybrid_rrf"

    ranked = sorted(

        merged.values(),

        key=lambda item: item["rerank_score"],

        reverse=True

    )

    return ranked[:k]


# ==========================================
# MAIN RETRIEVAL FUNCTION
# ==========================================

def retrieve(
    question: str,
    k: int = 3,
    policy_mode: str = "current",
    search_mode: str = "hybrid",
    candidate_k: int | None = None
) -> list[dict[str, Any]]:

    if not isinstance(question, str) or not question.strip():

        raise ValueError(
            "Question cannot be empty."
        )

    if policy_mode not in (
        "current",
        "archived",
        "compare",
        "all"
    ):

        raise ValueError(
            "Invalid policy mode."
        )

    if search_mode not in (
        "semantic",
        "keyword",
        "hybrid"
    ):

        raise ValueError(
            "Invalid search mode."
        )

    k = max(
        1,
        min(int(k), 10)
    )

    if candidate_k is None:

        candidate_k = max(

            MIN_CANDIDATES,

            k * DEFAULT_CANDIDATE_MULTIPLIER

        )

    candidate_k = max(

        k,

        min(
            int(candidate_k),
            MAX_CANDIDATES
        )

    )

    final_results = []

    for where_filter in _policy_filters(policy_mode):

        records = _get_records(where_filter)

        if not records:
            continue

        if search_mode == "semantic":

            results = _semantic_search(

                question,

                where_filter,

                min(candidate_k, len(records)),

                len(records)

            )[:k]

        elif search_mode == "keyword":

            results = _bm25_search(

                question,

                records,

                min(candidate_k, len(records))

            )[:k]

        else:

            results = _hybrid_search(

                question,

                where_filter,

                records,

                k,

                candidate_k

            )

        final_results.extend(results)

    return final_results


# ==========================================
# DISPLAY RETRIEVAL RESULTS
# ==========================================

def show_results(
    question: str,
    mode: str,
    search_mode: str = "hybrid"
):

    print("\n" + "=" * 65)

    print("QUESTION:", question)

    print("POLICY MODE:", mode)

    print("SEARCH MODE:", search_mode)

    results = retrieve(

        question,

        k=3,

        policy_mode=mode,

        search_mode=search_mode

    )

    if not results:

        print("No relevant evidence found.")

        return

    for number, item in enumerate(
        results,
        start=1
    ):

        print(f"\nRESULT {number}")

        print("Source:", item["source"])

        print("Version:", item["version"])

        print("Status:", item["status"])

        print(
            "Semantic rank:",
            item["semantic_rank"]
        )

        print(
            "Keyword rank:",
            item["keyword_rank"]
        )

        print(
            "BM25 score:",
            round(item["bm25_score"], 4)
        )

        print(
            "Rerank score:",
            round(item["rerank_score"], 6)
        )

        if item["distance"] is not None:

            print(
                "Vector distance:",
                round(item["distance"], 4)
            )

        print(
            "Evidence:",
            item["content"][:350]
        )


# ==========================================
# MAIN TESTING
# ==========================================

if __name__ == "__main__":

    print("\n======================================")

    print("PACK EFY ADVANCED RAG RETRIEVAL")

    print("======================================")

    print(
        "ChromaDB chunks:",
        collection.count()
    )

    demo_question = (
        "What are the current delivery charges "
        "and delivery times?"
    )

    # Test 1: Semantic Search

    show_results(

        demo_question,

        "current",

        "semantic"

    )

    # Test 2: Keyword Search

    show_results(

        demo_question,

        "current",

        "keyword"

    )

    # Test 3: Hybrid Search

    show_results(

        demo_question,

        "current",

        "hybrid"

    )

    # Test 4: Archived Policy

    show_results(

        "What were the old delivery rules before October 2026?",

        "archived",

        "hybrid"

    )

    # Test 5: Policy Comparison

    show_results(

        "Compare previous and current delivery policies.",

        "compare",

        "hybrid"

    )

    print("\n======================================")

    print("HYBRID RETRIEVAL AND RERANKING TEST COMPLETE!")

    print("======================================")
