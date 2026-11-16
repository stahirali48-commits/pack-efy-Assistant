from pathlib import Path
import uuid
import re
import base64
import streamlit as st

from src.answerer import answer_question


# ==========================================
# CONFIGURATION
# ==========================================

BASE_DIR = Path(__file__).resolve().parent
LOGO_PATH = BASE_DIR / "assets" / "pack-efy-logo-transparent.png"


def render_html(html, unsafe_allow_html=True):
    """Render an HTML snippet safely with st.markdown.

    Markdown treats indented lines and blank lines inside HTML as a
    code block, which prints the raw tags on screen. Stripping the
    indentation and blank lines avoids that.
    """
    cleaned = "\n".join(
        line.strip() for line in html.splitlines() if line.strip()
    )
    st.markdown(cleaned, unsafe_allow_html=unsafe_allow_html)


GREETING_WORDS = {
    "hi", "hello", "hey", "hii", "helo", "hola",
    "salam", "salaam", "aoa", "assalamualaikum",
    "assalamoalaikum", "assalamualaikum",
    "good morning", "good afternoon", "good evening",
    "assalam o alaikum", "assalam-o-alaikum",
    "assalamu alaikum", "as salam o alaikum",
}

THANKS_WORDS = {
    "thanks", "thank you", "thankyou", "thx", "shukriya", "shukria",
}

GREETING_REPLY = "Hello! 👋 How can I help you today?"

THANKS_REPLY = (
    "You're welcome! 😊 Let me know if you need anything else."
)


def get_greeting_reply(text):
    """Return a friendly reply for plain greetings or thanks, else None.

    Only short messages made up entirely of a greeting are matched, so a
    real question such as "hello, what are your delivery charges?" still
    goes to the knowledge base.
    """
    cleaned = re.sub(r"[^a-z0-9\s-]", "", text.lower()).strip()
    cleaned = re.sub(r"\s+", " ", cleaned)

    if cleaned in GREETING_WORDS:
        return GREETING_REPLY

    if cleaned in THANKS_WORDS:
        return THANKS_REPLY

    return None

st.set_page_config(
    page_title="PACK EFY Assistant",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="expanded"
)


# ==========================================
# SESSION STATE
# ==========================================

if "messages" not in st.session_state:
    st.session_state.messages = []

if "pending_question" not in st.session_state:
    st.session_state.pending_question = None

if "chat_history" not in st.session_state:
    first_chat_id = str(uuid.uuid4())

    st.session_state.chat_history = [{
        "id": first_chat_id,
        "title": "New Chat",
        "messages": []
    }]

    st.session_state.active_chat_id = first_chat_id

if "active_chat_id" not in st.session_state:
    st.session_state.active_chat_id = st.session_state.chat_history[0]["id"]


# ==========================================
# READ THE NEW QUESTION (typed or suggested)
# ==========================================
# The question is read here, before anything is drawn, so the user's
# message is stored immediately and shows up right away on screen.

question = st.chat_input("Ask PACK EFY Assistant anything...")

if st.session_state.pending_question:
    question = st.session_state.pending_question
    st.session_state.pending_question = None

if question and question.strip():
    question = question.strip()
    st.session_state.messages.append({
        "role": "user",
        "content": question
    })
else:
    question = None


# ==========================================
# SAVE CURRENT CHAT
# ==========================================

for chat in st.session_state.chat_history:

    if chat["id"] == st.session_state.active_chat_id:

        chat["messages"] = list(st.session_state.messages)

        first_user_message = next(
            (
                message["content"]
                for message in chat["messages"]
                if message["role"] == "user"
            ),
            None
        )

        if first_user_message:
            chat["title"] = (
                first_user_message[:28]
                + ("…" if len(first_user_message) > 28 else "")
            )

        break


# ==========================================
# SIDEBAR
# ==========================================

WEBSITE_URL = ""
SUPPORT_URL = ""
CATALOG_URL = ""

with st.sidebar:

    st.markdown(
        """
        <h2 style="color:#65B32E;">
            📦 PACK EFY
        </h2>
        """,
        unsafe_allow_html=True
    )

    # New Chat
    if st.button(
        "＋ New Chat",
        key="new_chat_button",
        use_container_width=True
    ):

        # Do not pile up empty chats: only create a new one
        # if the current chat already has messages.
        if st.session_state.messages:

            new_chat_id = str(uuid.uuid4())

            st.session_state.chat_history.insert(0, {
                "id": new_chat_id,
                "title": "New Chat",
                "messages": []
            })

            st.session_state.active_chat_id = new_chat_id
            st.session_state.messages = []

        st.session_state.pending_question = None

        st.rerun()

    st.divider()

    # Recent Chats
    st.markdown("### 🕘 Recent Chats")

    for chat in st.session_state.chat_history:

        active = (
            chat["id"] == st.session_state.active_chat_id
        )

        label = (
            "● " if active else "💬 "
        ) + chat["title"]

        if st.button(
            label,
            key=f"recent_chat_{chat['id']}",
            use_container_width=True
        ):

            st.session_state.active_chat_id = chat["id"]
            st.session_state.messages = list(chat["messages"])
            st.session_state.pending_question = None

            st.rerun()

    st.divider()

    # Quick Links
    st.markdown("### 🔗 Quick Links")

    if WEBSITE_URL:
        st.link_button(
            "🌐 Website",
            WEBSITE_URL,
            use_container_width=True
        )
    else:
        st.button(
            "🌐 Website",
            key="website_link",
            disabled=True,
            use_container_width=True
        )

    if SUPPORT_URL:
        st.link_button(
            "🎧 Contact Support",
            SUPPORT_URL,
            use_container_width=True
        )
    else:
        st.button(
            "🎧 Contact Support",
            key="support_link",
            disabled=True,
            use_container_width=True
        )

    if CATALOG_URL:
        st.link_button(
            "📦 Product Catalog",
            CATALOG_URL,
            use_container_width=True
        )
    else:
        st.button(
            "📦 Product Catalog",
            key="catalog_link",
            disabled=True,
            use_container_width=True
        )


# ==========================================
# CUSTOM CSS
# ==========================================

st.markdown("""
<style>

@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', sans-serif;
}

/* Main background */

.stApp {
    background: #FFFFFF !important;
}

.block-container {
    max-width: 1050px;
    padding-top: 4rem;
    padding-bottom: 2rem;
}

/* Sidebar */

section[data-testid="stSidebar"] {
    background: #222222 !important;
}

/* Only force a width while the sidebar is open; a forced min-width on a
   collapsed sidebar pushes the whole page off-center. */
section[data-testid="stSidebar"][aria-expanded="true"] {
    min-width: 260px;
}

section[data-testid="stSidebar"] > div {
    background: #222222 !important;
}

section[data-testid="stSidebar"] * {
    color: #FFFFFF;
}

section[data-testid="stSidebar"] hr {
    border-color: #555555;
}

/* Sidebar buttons */

section[data-testid="stSidebar"] .stButton > button {
    background: #222222 !important;
    color: #FFFFFF !important;
    border: 1px solid #444444 !important;
    border-radius: 10px !important;
    text-align: left !important;
    justify-content: flex-start !important;
    min-height: 0 !important;
    padding: 8px 14px !important;
    font-weight: 500;
}

section[data-testid="stSidebar"] .stButton > button:hover {
    background: #333333 !important;
    border-color: #65B32E !important;
    box-shadow: none !important;
    transform: none !important;
}

section[data-testid="stSidebar"] .stButton > button:disabled {
    opacity: 0.5;
}

/* Main headings */

h1, h2, h3 {
    color: #222222;
}

section[data-testid="stSidebar"] h1,
section[data-testid="stSidebar"] h2,
section[data-testid="stSidebar"] h3 {
    color: #FFFFFF;
}

section[data-testid="stSidebar"] h2 {
    color: #65B32E;
}

/* Brand green */

.brand-green {
    color: #65B32E !important;
}

/* Suggestion buttons (main area) */

.stButton > button {
    text-align: left !important;
    justify-content: flex-start !important;
    background: #FFFFFF !important;
    border: 1px solid #D3D3D3 !important;
    border-radius: 14px !important;
    padding: 14px 18px !important;
    color: #222222 !important;
    min-height: 58px !important;
    font-weight: 600;
    transition: all 0.2s ease;
}

.stButton > button:hover {
    border: 1px solid #65B32E !important;
    background: #F8FBF5 !important;
    box-shadow: 0 4px 14px rgba(101, 179, 46, 0.20);
    transform: translateY(-2px);
}

/* Chat messages */

div[data-testid="stChatMessage"] {
    border: 1px solid #D3D3D3;
    border-radius: 16px;
    padding: 15px;
    margin-bottom: 14px;
    background: #FFFFFF;
}

div[data-testid="stChatMessage"] * {
    color: #222222;
}

/* Chat input background */

div[data-testid="stBottom"] {
    background: transparent !important;
}

div[data-testid="stBottom"] > div {
    background: transparent !important;
    box-shadow: none !important;
}

/* Chat input size */

div[data-testid="stChatInput"] {
    width: 85% !important;
    max-width: 950px !important;
    min-width: 300px !important;
    margin-left: auto !important;
    margin-right: auto !important;
    border-radius: 16px !important;
    background: #FFFFFF !important;
}

/* Chat input focus */

div[data-testid="stChatInput"]:focus-within {
    border: 1px solid #65B32E !important;
    box-shadow: 0 0 0 3px rgba(101, 179, 46, 0.20) !important;
}

/* Send button */

div[data-testid="stChatInput"] button {
    background: #65B32E !important;
    color: #FFFFFF !important;
    border-radius: 50% !important;
    border: none !important;
    min-height: 0 !important;
    padding: 6px !important;
    transform: none !important;
}

/* Hide Streamlit menu and footer */

#MainMenu {
    visibility: hidden;
}

footer {
    visibility: hidden;
}

.stDeployButton {
    display: none;
}

</style>
""", unsafe_allow_html=True)


# ==========================================
# MAIN HEADER WITH LOGO
# ==========================================

if LOGO_PATH.is_file():

    logo_base64 = base64.b64encode(
        LOGO_PATH.read_bytes()
    ).decode()

    render_html(
        f"""
        <div style="text-align:center; margin:0 auto 16px auto; overflow:visible;">
            <img
                src="data:image/png;base64,{logo_base64}"
                style="display:block; margin:0 auto; width:180px; max-width:100%; height:auto;"
            >
        </div>
        """
    )


# ==========================================
# MAIN TITLE
# ==========================================

render_html(
    """
    <div style="
        width:100%;
        text-align:center;
        margin:0 auto 20px auto;
    ">

        <h1 style="
            color:#222222;
            margin:0;
            text-align:center;
        ">
            PACK EFY
            <span style="color:#65B32E;">ASSISTANT</span>
        </h1>

        <p style="
            font-size:15px;
            color:#666666;
            margin:8px 0 0 0;
            text-align:center;
        ">
        </p>

    </div>
    """,
    unsafe_allow_html=True
)


# ==========================================
# WELCOME + SUGGESTED QUESTIONS
# (shown only while the chat is empty)
# ==========================================

# (button label, clean question sent to the assistant)
suggestions = [
    ("📦 What products are available?", "What products are available?"),
    ("🚚 What are Karachi delivery charges?", "What are Karachi delivery charges?"),
    ("📄 Compare old and current policies.", "Compare old and current policies."),
    ("⏰ What are the company's working hours?", "What are the company's working hours?"),
]

if not st.session_state.messages:

    render_html(
        """
        <div style="width:100%; text-align:center; margin:0 auto 20px auto;">

            <p style="
                font-size:22px;
                font-weight:700;
                color:#222222;
                margin:10px 0 8px 0;
            ">
                👋 Welcome!
            </p>

            <p style="
                font-size:18px;
                color:#222222;
                margin:0;
            ">
                Try asking one of these questions:
            </p>

        </div>
        """,
        unsafe_allow_html=True
    )

    col1, col2 = st.columns(2)

    for index, (label, suggestion_question) in enumerate(suggestions):

        target_col = col1 if index % 2 == 0 else col2

        with target_col:

            if st.button(
                label,
                key=f"suggestion_{index}",
                use_container_width=True
            ):

                st.session_state.pending_question = suggestion_question
                st.rerun()


# ==========================================
# DISPLAY CHAT HISTORY
# ==========================================

for message in st.session_state.messages:

    with st.chat_message(
        message["role"],
        avatar="👤" if message["role"] == "user" else "📦"
    ):

        st.markdown(message["content"])


# ==========================================
# GENERATE ANSWER
# ==========================================

if question:

    with st.chat_message("assistant", avatar="📦"):

        with st.spinner(
            "🧠 Searching knowledge base and generating answer..."
        ):

            try:

                greeting_reply = get_greeting_reply(question)

                if greeting_reply:
                    answer = greeting_reply
                else:
                    result = answer_question(
                        question=question,
                        k=3
                    )

                    answer = result["answer"]

                # Remove standalone source/reference lines
                answer = re.sub(
                    r"(?im)^\s*(?:[-*]\s*)?(?:sources?|references?|citations?|retrieved\s+from)\s*:.*$",
                    "",
                    answer
                )

                # Remove extra blank lines
                answer = re.sub(
                    r"\n{3,}",
                    "\n\n",
                    answer
                ).strip()

                if not answer:
                    answer = (
                        "Sorry, I could not find an answer to that "
                        "in the knowledge base."
                    )

            except Exception as error:

                print(
                    "STREAMLIT CHAT ERROR:",
                    repr(error)
                )

                answer = (
                    "Sorry, I could not process your question "
                    "because of a technical issue. "
                    "Please check the API key, internet connection, "
                    "model access, or available API quota, then try again."
                )

    st.session_state.messages.append({
        "role": "assistant",
        "content": answer
    })

    st.rerun()