# VAARChatbot

A document-based chatbot developed for the **PI-5 Integrative Project**, using a **RAG (Retrieval-Augmented Generation)** architecture.

The system retrieves information from documents stored in the project and uses the retrieved passages as context to generate answers grounded in the available sources.

The current version primarily focuses on the education-related framework of Rio Grande do Sul, Brazil:

```text
SAERS → IMERS → PRE → IPM → distribution of municipal ICMS revenue
```

The document collection can be modified or expanded through the `raw/` folder without retraining the language model.

---

# Architecture

The application's main workflow is:

```text
Documents in raw/
        ↓
src/ingestion.py
        ↓
Text extraction and cleaning
        ↓
Chunking
        ↓
Embeddings
        ↓
ChromaDB
        ↓
User question
        ↓
Semantic search
        ↓
Candidate retrieval
        ↓
Reranking and deduplication
        ↓
Context construction
        ↓
LLM via OpenRouter
        ↓
Answer + sources
        ↓
Streamlit
```

The language model is **not retrained on the documents**.

Instead, documents are converted into vector representations and stored in ChromaDB. When a user asks a question, the system searches for the most semantically relevant passages and sends only the retrieved context to the language model.

---

# Current Document Collection

The current version of the project has been optimized primarily for information related to:

- **SAERS** — Rio Grande do Sul School Performance Assessment System (*Sistema de Avaliação do Rendimento Escolar do Rio Grande do Sul*);
- **IMERS** — Rio Grande do Sul Municipal Education Quality Index (*Índice Municipal da Qualidade da Educação do Rio Grande do Sul*);
- **PRE** — Education Share of Municipal Revenue Allocation (*Participação no Rateio da Cota-Parte da Educação*);
- **Municipality size classification**;
- **IPM** — Municipal Participation Index (*Índice de Participação dos Municípios*);
- the relationship between education and the distribution of **municipal ICMS tax revenue**.

The project originally also used documents related to **Fundeb and VAAR**. However, the chatbot can only answer questions on those topics reliably when the relevant documents are present in the `raw/` folder and have been indexed.

---

# Technologies Used

The project uses:

- **Python** — main programming language;
- **Streamlit** — web interface;
- **ChromaDB** — vector database;
- **Sentence Transformers** — embedding generation;
- **LangChain / OpenAI client** — language model integration;
- **OpenRouter** — LLM access;
- **PyPDF** — text extraction from PDF files;
- **python-dotenv** — environment variable management.

Configured language model:

```text
z-ai/glm-5.2:free
```

Embedding model:

```text
sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
```

---

# Current RAG Configuration

The current configuration uses:

```text
CHUNK_SIZE = 900
CHUNK_OVERLAP = 180

TOP_K = 12
CANDIDATE_K = 28
MAX_CONTEXT_CHUNKS = 14

INDEX_BATCH_SIZE = 48
```

## CHUNK_SIZE

Approximately defines the maximum size of text segments created during indexing.

```text
900 characters
```

## CHUNK_OVERLAP

Defines how much content is shared between consecutive chunks.

```text
180 characters
```

The overlap helps prevent context loss when important information falls directly on a chunk boundary.

## CANDIDATE_K

Number of candidates retrieved initially:

```text
28
```

The system retrieves more passages than it will eventually use, allowing a second selection stage.

## TOP_K

Target number of passages after retrieval and reranking:

```text
12
```

## MAX_CONTEXT_CHUNKS

Maximum number of passages included when building the context:

```text
14
```

---

# Retrieval and Reranking

The system does not simply use the first results returned by ChromaDB.

After vector search, the retrieved results go through additional selection stages.

The system considers:

- semantic distance;
- query terms found in each passage;
- source relevance;
- document name;
- deduplication;
- diversity across sources.

Workflow:

```text
Question
   ↓
Expanded search
   ↓
28 candidates
   ↓
Reranking
   ↓
Deduplication
   ↓
Diversification
   ↓
Best passages
   ↓
Context
```

This approach reduces the likelihood of nearly identical chunks dominating the context sent to the language model.

---

# Project Structure

```text
VAARChatbot/
│
├── raw/
│   └── documents used by the RAG system
│
├── src/
│   ├── __init__.py
│   ├── ingestion.py
│   ├── rag.py
│   └── settings.py
│
├── app.py
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

---

# Main Files

## `app.py`

Provides the web interface using **Streamlit**.

Main functions:

- accept user questions;
- maintain conversation history;
- call the RAG system;
- display generated answers;
- display the passages used;
- display retrieved sources;
- present information about the document collection;
- allow the index to be rebuilt when necessary.

---

## `src/ingestion.py`

Handles document preparation and indexing.

Workflow:

```text
File
  ↓
Reading
  ↓
Extraction
  ↓
Cleaning
  ↓
Chunking
  ↓
Embedding
  ↓
ChromaDB
```

The process also stores metadata such as:

```text
source
type
page
chunk
```

CSV files may also include fields such as:

```text
row
uf
entity
codigo_ibge
```

---

## `src/rag.py`

Handles document retrieval and answer generation.

Main workflow:

```text
Question
   ↓
retrieve()
   ↓
Semantic search
   ↓
Query expansion
   ↓
Reranking
   ↓
Deduplication
   ↓
build_context()
   ↓
OpenRouter
   ↓
LLM
   ↓
Answer
```

The model receives:

```text
Question
+
Retrieved passages
```

It then generates an answer using the provided context.

---

## `src/settings.py`

Centralizes the project's configuration, including:

```text
RAW_DIR
CHROMA_DIR
COLLECTION_NAME
EMBEDDING_MODEL
CHUNK_SIZE
CHUNK_OVERLAP
INDEX_BATCH_SIZE
TOP_K
CANDIDATE_K
MAX_CONTEXT_CHUNKS
INDEX_VERSION
```

---

# Supported Document Formats

The current ingestion process primarily supports:

```text
.pdf
.txt
.csv
```

Documents should be placed in:

```text
raw/
```

> Markdown files (`.md`) will only be indexed if `ingestion.py` is configured to accept this extension.

---

# How to Run the Project

## 1. Requirements

To run the project locally, you will need:

- Python 3.11 or later;
- Git;
- an internet connection;
- an OpenRouter API key.

---

# 2. Clone the Repository

Open Command Prompt, PowerShell, or the Visual Studio Code terminal.

Run:

```bash
git clone https://github.com/projects-yuri/VAARChatbot.git
```

Navigate to the project directory:

```bash
cd VAARChatbot
```

---

# 3. Create a Virtual Environment

Run:

```bash
python -m venv .venv
```

## Windows CMD

```cmd
.venv\Scripts\activate
```

## Windows PowerShell

```powershell
.venv\Scripts\Activate.ps1
```

## Linux / macOS

```bash
source .venv/bin/activate
```

When activated successfully, your terminal should display something similar to:

```text
(.venv) C:\Users\username\VAARChatbot>
```

---

# 4. Install Dependencies

Run:

```bash
pip install -r requirements.txt
```

The required libraries are listed in:

```text
requirements.txt
```

---

# 5. Configure OpenRouter

Create a file in the project root named:

```text
.env
```

Example:

```env
OPENROUTER_API_KEY=YOUR_OPENROUTER_API_KEY

OPENROUTER_MODEL=z-ai/glm-5.2:free

OPENROUTER_BASE_URL=https://openrouter.ai/api/v1

EMBEDDING_MODEL=sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2

CHUNK_SIZE=900
CHUNK_OVERLAP=180

TOP_K=12
CANDIDATE_K=28
MAX_CONTEXT_CHUNKS=14

INDEX_BATCH_SIZE=48
```

Replace:

```text
YOUR_OPENROUTER_API_KEY
```

with your actual API key.

> **Never publish your OpenRouter API key on GitHub.**

The file:

```text
.env
```

must remain in `.gitignore`.

---

# 6. Vector Database

The project uses:

```text
ChromaDB
```

The current version allows you to configure the database directory using:

```text
CHROMA_DIR
```

By default, `settings.py` uses a temporary directory compatible with Streamlit Cloud.

This change was introduced to avoid SQLite errors such as:

```text
attempt to write a readonly database
```

and:

```text
no such table: tenants
```

If you need to specify a local directory manually, you can use an environment variable such as:

```env
CHROMA_DIR=data/chroma
```

---

# 7. Add Documents

Place the documents you want to use inside:

```text
raw/
```

Example:

```text
raw/
├── Base_Consolidada_SAERS_IMERS_PRE.pdf
└── outros_documentos.pdf
```

The `raw/` folder is the chatbot's actual knowledge base.

If a document is not in this folder, it will not be included in the standard indexing process.

---

# 8. Build the Index

Before using the chatbot for the first time, run:

```bash
python -m src.ingestion --reset
```

This process:

1. checks the documents;
2. extracts the text;
3. cleans the content;
4. creates the chunks;
5. generates the embeddings;
6. creates or opens ChromaDB;
7. stores the vectors;
8. stores the metadata;
9. records the index state.

---

# 9. Run the Chatbot

After building the index, run:

```bash
streamlit run app.py
```

The application will normally be available at:

```text
http://localhost:8501
```

If your browser does not open automatically, copy the URL and open it manually.

---

# Streamlit Cloud

When deploying to Streamlit Cloud, private configuration values should be added under:

```text
Settings
→ Secrets
```

Example:

```toml
OPENROUTER_API_KEY = "YOUR_API_KEY"

OPENROUTER_MODEL = "z-ai/glm-5.2:free"

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

EMBEDDING_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

CHUNK_SIZE = 900
CHUNK_OVERLAP = 180

TOP_K = 12
CANDIDATE_K = 28
MAX_CONTEXT_CHUNKS = 14

INDEX_BATCH_SIZE = 48
```

Do not place your OpenRouter API key directly in your source code or upload it to GitHub.

---

# How a Question Is Processed

Example:

```text
How does municipality size classification affect PRE?
```

The system roughly follows these steps:

```text
Question
   ↓
Embedding / semantic search
   ↓
Auxiliary queries
   ↓
ChromaDB
   ↓
28 candidates
   ↓
Reranking
   ↓
Deduplication
   ↓
Diversification
   ↓
Context construction
   ↓
OpenRouter
   ↓
GLM
   ↓
Answer
   ↓
Sources
```

---

# Hallucination Mitigation

The chatbot is configured to prioritize answers grounded in the retrieved documents.

The model should:

- answer using the retrieved context;
- avoid inventing laws;
- avoid inventing percentages;
- avoid inventing formulas;
- avoid inventing municipalities or numerical values;
- avoid treating a specific example as a general rule;
- indicate when the documentation does not contain sufficient information.

The core idea is:

```text
ChromaDB finds relevant passages.
Sentence Transformers provide semantic representations.
The LLM explains the findings.
```

---

# Key Concepts Explained

## Chunking

Splits large documents into smaller segments.

```text
Document
↓
Chunk 1
Chunk 2
Chunk 3
```

---

## Tokenization

Splits text into units that can be processed by the language model.

---

## Embedding

Converts a text passage into a numerical representation that captures semantic characteristics.

```text
Text
↓
Vector
```

---

## ChromaDB

Stores vectors and makes it possible to retrieve passages that are semantically similar to the user's question.

---

## Reranking

Reorders retrieved results to prioritize the most useful passages before constructing the context.

---

## RAG

Combines:

```text
Information retrieval
+
Language model
```

Simplified workflow:

```text
Question
↓
Document search
↓
Context
↓
LLM
↓
Answer
```

---

# Updating the Document Collection

If documents in the `raw/` folder are modified, run:

```bash
python -m src.ingestion --reset
```

Then:

```bash
streamlit run app.py
```

---

# Common Issues

## `429`

Example:

```text
429 Too Many Requests
```

This error is usually related to the rate limits of the free model accessed through OpenRouter.

It does not necessarily indicate a problem with the RAG implementation.

---

## `attempt to write a readonly database`

This error is related to the SQLite database used by ChromaDB when the directory lacks the appropriate write permissions.

The current version uses a temporary-directory strategy to reduce this issue on Streamlit Cloud.

---

## `no such table: tenants`

This may occur if an old or incompatible Chroma database exists.

One solution is to rebuild the index:

```bash
python -m src.ingestion --reset
```

---

## Missing Index

If the system reports that the index does not exist or must be rebuilt, run:

```bash
python -m src.ingestion --reset
```

---

# Quick Start

```bash
git clone https://github.com/projects-yuri/VAARChatbot.git

cd VAARChatbot

python -m venv .venv
```

Windows CMD:

```cmd
.venv\Scripts\activate
```

Install the dependencies:

```bash
pip install -r requirements.txt
```

Configure:

```text
.env
```

Then:

```bash
python -m src.ingestion --reset
```

And run:

```bash
streamlit run app.py
```

Open:

```text
http://localhost:8501
```

---

# Architecture Summary

```text
raw/
 ↓
ingestion.py
 ↓
Cleaning
 ↓
Chunking (900 / 180)
 ↓
Sentence Transformers
 ↓
Embeddings
 ↓
ChromaDB
 ↓
28 candidates
 ↓
Reranking
 ↓
TOP_K = 12
 ↓
Context
 ↓
OpenRouter
 ↓
GLM 5.2
 ↓
app.py
 ↓
Streamlit
 ↓
User
```

---

# Project

**PI-5 Integrative Project**

A document-based chatbot powered by RAG, designed to work with educational documentation from Rio Grande do Sul, Brazil.

Repository:

https://github.com/projects-yuri/VAARChatbot
