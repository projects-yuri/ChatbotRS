import os
from pathlib import Path

import streamlit as st


# =========================================================
# SECRETS -> ENV
# =========================================================

try:
    for key in (
        "OPENROUTER_API_KEY",
        "OPENROUTER_MODEL",
        "OPENROUTER_BASE_URL",
        "EMBEDDING_MODEL",
        "TOP_K",
        "CANDIDATE_K",
        "MAX_CONTEXT_CHUNKS",
    ):
        if key in st.secrets:
            os.environ[key] = str(
                st.secrets[key]
            )
except Exception:
    pass


# =========================================================
# PROJECT IMPORTS
# =========================================================

from src.ingestion import index_documents
from src.rag import (
    answer,
)
from src.settings import (
    RAW_DIR,
    EMBEDDING_MODEL,
    TOP_K,
    CANDIDATE_K,
    MAX_CONTEXT_CHUNKS,
)


# =========================================================
# PAGE CONFIGURATION
# =========================================================

st.set_page_config(
    page_title="RS Educational Chatbot",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded",
)


# =========================================================
# STYLING
# =========================================================

st.markdown(
    """
    <style>

    /* Overall background */
    .stApp {
        background:
            linear-gradient(
                135deg,
                #07111f 0%,
                #0c1728 55%,
                #101c30 100%
            );
    }

    /* Content width */
    .block-container {
        max-width: 1180px;
        padding-top: 2rem;
        padding-bottom: 3rem;
    }

    /* Sidebar */
    section[data-testid="stSidebar"] {
        background: #081321;
        border-right: 1px solid rgba(255,255,255,0.08);
    }

    section[data-testid="stSidebar"] > div {
        padding-top: 1.2rem;
    }

    /* Main heading */
    .main-title {
        font-size: 2.3rem;
        font-weight: 800;
        margin-bottom: 0.2rem;
        color: #f7f9fc;
    }

    .main-subtitle {
        font-size: 1rem;
        color: #aeb9ca;
        margin-bottom: 1.5rem;
    }

    /* Cards */
    .info-card {
        background: rgba(255,255,255,0.045);
        border: 1px solid rgba(255,255,255,0.08);
        border-radius: 14px;
        padding: 17px 18px;
        margin-bottom: 10px;
    }

    .info-card-title {
        font-weight: 700;
        font-size: 0.95rem;
        color: #f3f6fb;
        margin-bottom: 5px;
    }

    .info-card-text {
        color: #aeb9ca;
        font-size: 0.88rem;
        line-height: 1.5;
    }

    /* Document */
    .doc-card {
        background: rgba(255,255,255,0.035);
        border: 1px solid rgba(255,255,255,0.07);
        border-radius: 10px;
        padding: 10px 12px;
        margin-bottom: 7px;
    }

    .doc-name {
        color: #f5f7fa;
        font-weight: 600;
        font-size: 0.87rem;
        word-break: break-word;
    }

    .doc-type {
        color: #8895a8;
        font-size: 0.75rem;
        margin-top: 3px;
    }

    /* Online status badge */
    .status-online {
        display: inline-block;
        padding: 5px 10px;
        border-radius: 999px;
        font-size: 0.78rem;
        font-weight: 600;
        background: rgba(48, 209, 88, 0.12);
        color: #74e28f;
        border: 1px solid rgba(48,209,88,0.22);
        margin-bottom: 10px;
    }

    /* Chat */
    [data-testid="stChatMessage"] {
        border-radius: 14px;
        padding: 6px;
    }

    /* Expander */
    [data-testid="stExpander"] {
        border: 1px solid rgba(255,255,255,0.08);
        border-radius: 12px;
        background: rgba(255,255,255,0.025);
    }

    /* Metrics */
    [data-testid="stMetric"] {
        background: rgba(255,255,255,0.035);
        border: 1px solid rgba(255,255,255,0.07);
        padding: 14px;
        border-radius: 12px;
    }

    /* Buttons */
    .stButton > button {
        border-radius: 9px;
        font-weight: 600;
    }

    </style>
    """,
    unsafe_allow_html=True,
)


# =========================================================
# HELPER FUNCTIONS
# =========================================================

def get_available_documents() -> list[Path]:
    """
    Automatically lists documents available
    in the raw/ directory.
    """

    if not RAW_DIR.exists():
        return []

    allowed_extensions = {
        ".pdf",
        ".txt",
        ".csv",
        ".md",
    }

    documents = []

    for path in RAW_DIR.iterdir():
        if (
            path.is_file()
            and path.suffix.lower()
            in allowed_extensions
        ):
            documents.append(path)

    return sorted(
        documents,
        key=lambda item: item.name.lower(),
    )


def document_icon(path: Path) -> str:
    suffix = path.suffix.lower()

    if suffix == ".pdf":
        return "📕"

    if suffix == ".txt":
        return "📄"

    if suffix == ".csv":
        return "📊"

    if suffix == ".md":
        return "📝"

    return "📁"


def document_description(
    filename: str,
) -> str:

    name = filename.lower()

    if "saers" in name:
        return (
            "Educational assessment and academic "
            "performance in Rio Grande do Sul."
        )

    if "imers" in name:
        return (
            "Municipal Education Quality Index "
            "of Rio Grande do Sul."
        )

    if "pre" in name:
        return (
            "Participation in the Allocation of "
            "the Education Revenue Share (PRE)."
        )

    if "icms" in name:
        return (
            "Legislation and regulations related "
            "to education-based ICMS revenue allocation."
        )

    if "fundeb" in name:
        return (
            "Documentation related to "
            "Fundeb."
        )

    if "vaar" in name:
        return (
            "Documentation related to "
            "the VAAR funding supplement."
        )

    return "Document available for consultation."


def source_label(
    item: dict,
) -> str:

    source = item.get(
        "source",
        "Document",
    )

    doc_type = item.get(
        "type",
        "document",
    )

    if doc_type == "csv":
        details: list[str] = []

        entity = item.get("entity")
        row = item.get("row")

        if entity:
            details.append(
                f"municipality: {entity}"
            )

        if row:
            details.append(
                f"row {row}"
            )

        if details:
            return (
                f"{source} — "
                f"{', '.join(details)}"
            )

        return source

    if doc_type == "pdf":
        page = item.get("page")

        if page:
            return (
                f"{source} — page {page}"
            )

    return source


# =========================================================
# DOCUMENTS
# =========================================================

available_documents = (
    get_available_documents()
)


# =========================================================
# INDEXING
# =========================================================

@st.cache_resource(
    show_spinner=False
)
def ensure_index():
    return index_documents(
        reset=False
    )


try:
    with st.spinner(
        "Preparing the document knowledge base..."
    ):
        indexed_chunks = ensure_index()

except Exception as error:
    st.error(
        "Could not initialize "
        "the document knowledge base."
    )

    st.code(
        str(error)
    )

    st.stop()


# =========================================================
# HEADER
# =========================================================

st.markdown(
    """
    <div class="main-title">
        📚 RS Educational Chatbot
    </div>

    <div class="main-subtitle">
        AI-assisted document search covering
        SAERS, IMERS, PRE, and education-based ICMS
        in Rio Grande do Sul, Brazil.
    </div>
    """,
    unsafe_allow_html=True,
)


# =========================================================
# MAIN METRICS
# =========================================================

metric1, metric2, metric3 = st.columns(3)

with metric1:
    st.metric(
        "📚 Documents",
        len(available_documents),
    )

with metric2:
    st.metric(
        "🧩 Indexed chunks",
        indexed_chunks,
    )

with metric3:
    model_name = os.getenv(
        "OPENROUTER_MODEL",
        "Model not specified",
    )

    short_model = (
        model_name.split("/")[-1]
        if "/"
        in model_name
        else model_name
    )

    st.metric(
        "🤖 Model",
        short_model,
    )


# =========================================================
# INFORMATION
# =========================================================

with st.expander(
    "ℹ️ About this chatbot"
):
    st.markdown(
        """
        This chatbot uses **RAG
        (Retrieval-Augmented Generation)**.

        When you ask a question:

        **1.** The system processes your question.

        **2.** It retrieves the most relevant passages
        from the available documents.

        **3.** The retrieved passages are provided
        to the language model as context.

        **4.** The model generates an answer grounded
        in that retrieved context.

        This approach aims to reduce unsupported
        answers and lets you verify information
        against the original documents.
        """
    )


# =========================================================
# SIDEBAR
# =========================================================

with st.sidebar:

    st.markdown(
        """
        <h2 style="
            margin-bottom:4px;
        ">
            📚 Document library
        </h2>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        """
        <span class="status-online">
            ● Knowledge base ready
        </span>
        """,
        unsafe_allow_html=True,
    )

    st.caption(
        "Documents currently available "
        "to the chatbot."
    )

    st.divider()

    # =====================================================
    # AVAILABLE DOCUMENTS
    # =====================================================

    if available_documents:

        for document in available_documents:

            icon = document_icon(
                document
            )

            description = (
                document_description(
                    document.name
                )
            )

            st.markdown(
                f"""
                <div class="doc-card">
                    <div class="doc-name">
                        {icon} {document.name}
                    </div>

                    <div class="doc-type">
                        {description}
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    else:
        st.warning(
            "No documents found "
            "in the raw/ directory."
        )

    st.divider()

    # =====================================================
    # COVERAGE
    # =====================================================

    st.subheader(
        "🎯 Topics covered"
    )

    st.markdown(
        """
        - **SAERS**
        - **IMERS**
        - **PRE**
        - **Education-based ICMS**
        - Educational indicators
        - Municipal population size
        - IPM
        """
    )

    st.divider()

    # =====================================================
    # RAG CONFIGURATION
    # =====================================================

    with st.expander(
        "⚙️ RAG configuration"
    ):

        st.write(
            f"**Embedding:** "
            f"`{EMBEDDING_MODEL}`"
        )

        st.write(
            f"**TOP K:** `{TOP_K}`"
        )

        st.write(
            f"**Candidates:** "
            f"`{CANDIDATE_K}`"
        )

        st.write(
            f"**Maximum context chunks:** "
            f"`{MAX_CONTEXT_CHUNKS}`"
        )

        st.write(
            f"**Indexed chunks:** "
            f"`{indexed_chunks}`"
        )

    st.divider()

    if st.button(
        "🧹 Clear conversation",
        use_container_width=True,
    ):

        st.session_state.messages = []

        st.rerun()

    st.divider()

    st.caption(
        "PI-5 • Educational RAG • "
        "Rio Grande do Sul"
    )


# =========================================================
# SUGGESTED QUESTIONS
# =========================================================

st.markdown(
    "### 💡 Example questions"
)

example1, example2, example3 = (
    st.columns(3)
)

with example1:
    st.info(
        "What is SAERS and what "
        "is its purpose?"
    )

with example2:
    st.info(
        "How does municipal population "
        "size affect PRE?"
    )

with example3:
    st.info(
        "What is the relationship between "
        "IMERS and PRE?"
    )


st.divider()


# =========================================================
# CHAT HISTORY
# =========================================================

if "messages" not in st.session_state:
    st.session_state.messages = []


for message in st.session_state.messages:

    with st.chat_message(
        message["role"]
    ):

        st.markdown(
            message["content"]
        )

        if (
            message["role"]
            == "assistant"
            and message.get("sources")
        ):

            with st.expander(
                f"📄 Sources consulted "
                f"({len(message['sources'])})"
            ):

                for index, item in enumerate(
                    message["sources"],
                    start=1,
                ):

                    st.markdown(
                        f"**{index}. "
                        f"{source_label(item)}**"
                    )

                    st.write(
                        item.get(
                            "text",
                            "",
                        )
                    )


# =========================================================
# INPUT
# =========================================================

question = st.chat_input(
    "Ask about SAERS, IMERS, "
    "PRE, or education-based ICMS..."
)


# =========================================================
# ANSWER
# =========================================================

if question:

    st.session_state.messages.append(
        {
            "role": "user",
            "content": question,
        }
    )

    with st.chat_message(
        "user"
    ):
        st.markdown(
            question
        )

    with st.chat_message(
        "assistant"
    ):

        try:

            with st.spinner(
                "Searching the documents..."
            ):

                response, sources = answer(
                    question
                )

            st.markdown(
                response
            )

            if sources:

                with st.expander(
                    f"📄 Sources consulted "
                    f"({len(sources)})"
                ):

                    for index, item in enumerate(
                        sources,
                        start=1,
                    ):

                        st.markdown(
                            f"**{index}. "
                            f"{source_label(item)}**"
                        )

                        st.write(
                            item.get(
                                "text",
                                "",
                            )
                        )

        except Exception as error:

            response = (
                "Could not generate "
                "the answer."
            )

            sources = []

            st.error(
                response
            )

            st.code(
                str(error)
            )

    st.session_state.messages.append(
        {
            "role": "assistant",
            "content": response,
            "sources": sources,
        }
    )
