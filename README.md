# PACK EFY Assistant — Module 08 Enterprise RAG

A classroom prototype that answers questions about a fictional packaging company using a local Chroma vector database and the Groq chat API. The five Markdown knowledge documents are fictional educational data. Product prices, addresses, and policies must not be treated as real commercial information.

## What the project does

1. Loads five Markdown knowledge files from `knowledge/`.
2. Splits documents into overlapping word chunks (default: 180 words with 35 words of overlap).
3. Stores chunks, source filenames, document IDs, policy versions, status, and effective dates in ChromaDB.
4. Retrieves evidence with semantic search, a local BM25 keyword search, and Reciprocal Rank Fusion (RRF).
5. Uses Groq to rewrite search queries, grade evidence, and generate a grounded response.
6. Uses metadata filters to keep current and archived policy answers separate; comparison questions retrieve both policy files.
7. Displays the answer, source filenames, supporting excerpts, and expandable retrieved chunks in Streamlit.

## Project structure

```text
Module08_RAG_Assignment/
├── app.py
├── requirements.txt
├── .env.example
├── README.md
├── knowledge/
│   ├── company_overview.md
│   ├── current_policy.md
│   ├── operations_faqs.md
│   ├── previous_policy.md
│   └── products_services.md
├── src/
│   ├── __init__.py
│   ├── answerer.py
│   ├── build_index.py
│   └── retriever.py
├── tests/
│   ├── __init__.py
│   ├── test_set.csv
│   └── run_retrieval_experiment.py
└── reports/
    ├── assignment_report.md
    └── test_results.csv
```

## Setup on Windows PowerShell

Run these commands from the project root (the folder containing `app.py`):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Open `.env` and replace `your_groq_api_key_here` with your own Groq API key. Keep the key private and do not upload `.env`.

## Build the knowledge index

```powershell
python -m src.build_index
```

The script checks that the knowledge base contains 1,500–2,500 words, extracts metadata, creates chunks, and rebuilds the Chroma collection. Editing a Markdown file does not automatically update vectors already stored in Chroma; rebuild the index after document changes.

## Run the Streamlit app

```powershell
streamlit run app.py
```

Open the local URL shown in the terminal. Ask a direct question, a question requiring two documents, compare current and old policies, ask for undocumented information, and try the harmless prompt-injection text in `operations_faqs.md`.

## Existing 20-question evaluation

`reports/test_results.csv` contains the recorded 20-question results (20 marked PASS). The test categories are 5 direct factual, 4 rephrased, 3 two-document, 3 policy comparison, 3 missing-information, and 2 prompt-injection questions. The result file notes that automated checks passed and manual evidence review is required; review the cited sources before presenting the results. To rerun the 20 questions with your own API key, use:

```powershell
python tests/run_tests.py
```

The rerun is saved as `reports/test_results_rerun.csv` and is marked REVIEW until manual checking is complete.

## Retrieval experiment: k = 1, 3, 5

The assignment also asks for six questions at `k=1`, `k=3`, and `k=5`, followed by three questions using a different chunk configuration. The runner calls the same hybrid retriever and answer generator with the exact selected `k` for this comparison. It records retrieved sources and answers; the `answer_correct_manual` column must be marked Yes/No after checking the answer against its source excerpt.

First build the default index and run the baseline experiment:

```powershell
python -m src.build_index
python -m tests.run_retrieval_experiment --label baseline
```

Then create a separate index using 120-word chunks and 25-word overlap, without overwriting the default index:

```powershell
$env:PACKEFY_CHUNK_SIZE = "120"
$env:PACKEFY_CHUNK_OVERLAP = "25"
$env:PACKEFY_DB_DIR = "chroma_db_experiment"
python -m src.build_index
python -m tests.run_retrieval_experiment --label chunk_120_overlap_25 --subset changed
```

The two outputs are saved under `reports/`. Compare the retrieved evidence and answers, and manually complete `answer_correct_manual` in each CSV. After testing, restore the normal settings and index:

```powershell
Remove-Item Env:PACKEFY_CHUNK_SIZE
Remove-Item Env:PACKEFY_CHUNK_OVERLAP
Remove-Item Env:PACKEFY_DB_DIR
python -m src.build_index
Remove-Item -Recurse -Force .\chroma_db_experiment
```

Do not describe an experiment as passed until its CSV has been generated and checked.

## Security and limitations

- The app reads the Groq API key from `.env`; the key is never stored in source code.
- Retrieved documents are treated as untrusted evidence. Prompt-injection lines matching the defined patterns are removed before evidence is sent to the answer model.
- The project is a classroom prototype, not a production customer-support service. It uses fictional data, needs an internet connection and a valid Groq API key, and does not include user authentication, company-system integration, production monitoring, or a verified real-world knowledge source.
- If the evidence grader API fails, the code falls back to ranked retrieval candidates. This fallback is logged and should be treated as a limitation when checking answers.

## Demonstration video

**Add the link to your own 3–5 minute screen recording here before LMS submission:** `[ADD DEMO VIDEO LINK]`.

Suggested order: normal factual question → question needing product and policy documents → old/current policy comparison → missing-information question → prompt-injection test → explain one issue investigated (the source/excerpt display gap fixed in this submission, or the evidence-grader fallback limitation). A timed guide is included in `reports/demo_script.md`.

## Submission privacy

Include `.env.example`, not `.env`. Do not include `.venv/`, `chroma_db/`, `chroma_db_experiment/`, Python cache files, or API keys in the LMS ZIP. The index is rebuilt from the supplied knowledge documents.
