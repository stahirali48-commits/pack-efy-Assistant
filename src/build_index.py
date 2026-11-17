from pathlib import Path
import os
import re

import chromadb
from chromadb.utils.embedding_functions import DefaultEmbeddingFunction


BASE_DIR = Path(__file__).resolve().parent.parent

KNOWLEDGE_DIR = BASE_DIR / "knowledge"
DB_DIR = Path(os.getenv("PACKEFY_DB_DIR", str(BASE_DIR / "chroma_db"))).resolve()

COLLECTION_NAME = "packefy_knowledge"

CHUNK_SIZE = int(os.getenv("PACKEFY_CHUNK_SIZE", "180"))
CHUNK_OVERLAP = int(os.getenv("PACKEFY_CHUNK_OVERLAP", "35"))


def extract_metadata(text, file_path):

    metadata = {
        "source_file": file_path.name,
        "document_id": "unknown",
        "version": "unknown",
        "status": "unknown",
        "effective_date": "unknown"
    }

    for line in text.splitlines()[:25]:

        if ":" not in line:
            continue

        key, value = line.split(":", 1)

        key = key.strip().lower()
        value = value.strip()

        if key == "document id":
            metadata["document_id"] = value

        elif key in ("document version", "policy version", "version"):
            metadata["version"] = value

        elif key in ("document status", "policy status", "status"):
            metadata["status"] = value

        elif key == "effective date":
            metadata["effective_date"] = value

    return metadata


def split_into_chunks(
    text,
    chunk_size=CHUNK_SIZE,
    overlap=CHUNK_OVERLAP
):

    words = text.split()

    if not words:
        return []

    if overlap >= chunk_size:
        raise ValueError("Overlap must be smaller than chunk size.")

    chunks = []

    step = chunk_size - overlap

    for start in range(0, len(words), step):

        end = start + chunk_size

        chunk = " ".join(words[start:end])

        if chunk.strip():
            chunks.append(chunk)

        if end >= len(words):
            break

    return chunks


def load_documents():

    if not KNOWLEDGE_DIR.exists():
        raise FileNotFoundError(
            f"Knowledge folder not found: {KNOWLEDGE_DIR}"
        )

    files = sorted(KNOWLEDGE_DIR.glob("*.md"))

    if len(files) < 5:
        raise ValueError(
            f"At least 5 Markdown documents required. Found: {len(files)}"
        )

    all_chunks = []

    total_words = 0

    print("\n========== DOCUMENT LOADING ==========")

    for file_path in files:

        text = file_path.read_text(encoding="utf-8-sig")

        if not text.strip():
            raise ValueError(f"Empty document: {file_path.name}")

        word_count = len(text.split())

        total_words += word_count

        chunks = split_into_chunks(text)

        metadata = extract_metadata(
            text,
            file_path
        )

        for index, chunk in enumerate(chunks):

            chunk_id = f"{file_path.stem}_{index:04d}"

            chunk_metadata = {
                **metadata,
                "chunk_index": index
            }

            all_chunks.append({
                "id": chunk_id,
                "text": chunk,
                "metadata": chunk_metadata
            })

        print(
            f"{file_path.name}: "
            f"{word_count} words | "
            f"{len(chunks)} chunks | "
            f"Version: {metadata['version']} | "
            f"Status: {metadata['status']}"
        )

    print("\nTotal documents:", len(files))
    print("Total words:", total_words)
    print("Total chunks:", len(all_chunks))

    if total_words < 1500:
        raise ValueError(
            "Knowledge base must contain at least 1500 words."
        )

    return all_chunks


def build_vector_database(chunks):

    print("\n========== CHROMA DATABASE ==========")

    DB_DIR.mkdir(parents=True, exist_ok=True)

    client = chromadb.PersistentClient(
        path=str(DB_DIR)
    )

    existing_collections = [
        collection.name
        for collection in client.list_collections()
    ]

    if COLLECTION_NAME in existing_collections:

        client.delete_collection(
            name=COLLECTION_NAME
        )

        print("Previous collection removed.")

    embedding_function = DefaultEmbeddingFunction()

    collection = client.create_collection(

        name=COLLECTION_NAME,

        embedding_function=embedding_function,

        metadata={
            "description": "PACKEFY company knowledge base",
            "project": "Bano Qabil Module 08"
        }

    )

    ids = [item["id"] for item in chunks]
    documents = [item["text"] for item in chunks]
    metadatas = [item["metadata"] for item in chunks]

    # Add in batches so a large catalogue does not hit Chroma batch limits
    BATCH = 500
    for start in range(0, len(ids), BATCH):
        collection.add(
            ids=ids[start:start + BATCH],
            documents=documents[start:start + BATCH],
            metadatas=metadatas[start:start + BATCH],
        )

    print("\nEmbeddings generated successfully!")

    print("Collection:", COLLECTION_NAME)

    print("Stored chunks:", collection.count())

    print("Database path:", DB_DIR)

    return collection


def test_retrieval(collection):

    print("\n========== RETRIEVAL TEST ==========")

    results = collection.query(

        query_texts=[
            "What are the current delivery charges and delivery times?"
        ],

        n_results=3,

        include=[
            "documents",
            "metadatas",
            "distances"
        ]

    )

    for index, document in enumerate(
        results["documents"][0]
    ):

        metadata = results["metadatas"][0][index]

        distance = results["distances"][0][index]

        print(f"\nResult {index + 1}")

        print("Source:", metadata["source_file"])

        print("Version:", metadata["version"])

        print("Status:", metadata["status"])

        print("Distance:", round(distance, 4))

        print("Content:", document[:350])


if __name__ == "__main__":

    try:

        chunks = load_documents()

        collection = build_vector_database(chunks)

        test_retrieval(collection)

        print("\n================================")
        print("RAG INDEX BUILD SUCCESSFUL!")
        print("================================")

    except Exception as error:

        print("\nRAG INDEX BUILD FAILED:", str(error))

        raise
