import streamlit as st
import requests
import os

# Use environment variable for backend URL (default to localhost)
# FastAPI backend URL
API_URL = os.getenv("API_URL", "http://127.0.0.1:8000")

st.set_page_config(page_title="Clinical Anesthesia QA System", layout="wide")

# Custom CSS to change the red form border to blue
st.markdown("""
<style>
    /* Change the red form border to blue */
    [data-testid="stForm"] {
        border: 2px solid #1f77b4 !important;
        border-radius: 0.5rem !important;
        padding: 1rem !important;
    }
    
    /* Override any red borders */
    [data-testid="stForm"]:focus-within {
        border-color: #1f77b4 !important;
        box-shadow: none !important;
    }
</style>
""", unsafe_allow_html=True)

st.title("💉 Clinical Anesthesia QA System")
st.write("Interact with your custom RAG model using uploaded PDF guidelines.")

# # --- File upload section (COMMENTED OUT) ---
# st.sidebar.header("📄 Upload a new PDF")
# 
# uploaded_file = st.sidebar.file_uploader("Upload a PDF document", type=["pdf"])
# 
# if uploaded_file:
#     with st.spinner("Uploading and processing PDF..."):
#         files = {"file": (uploaded_file.name, uploaded_file, "application/pdf")}
#         response = requests.post(f"{API_URL}/upload", files=files)
# 
#         if response.status_code == 200:
#             result = response.json()
#             st.sidebar.success(f"✅ {result['status']}")
#             st.sidebar.write(f"**File:** {result['filename']}")
#             st.sidebar.write(f"**Chunks Added:** {result['chunks_added']}")
#         else:
#             st.sidebar.error(f"❌ Upload failed: {response.text}")
# 
# st.divider()

# --- Chat section ---
st.header("💬 Ask a Question")

# Use a form to enable Enter key submission
with st.form(key="question_form", clear_on_submit=False):
    question = st.text_input("Enter your question:", placeholder="e.g., What are the induction agents commonly used in anesthesia?")
    submit_button = st.form_submit_button("Ask", use_container_width=True)

if submit_button:
    if not question.strip():
        st.warning("Please enter a question.")
    else:
        with st.spinner("Retrieving answer..."):
            response = requests.post(f"{API_URL}/ask", json={"question": question})
            if response.status_code == 200:
                answer = response.json()["answer"]
                st.markdown("### Answer")
                st.info(answer)
            else:
                st.error(f"❌ Error: {response.text}")

st.markdown("---")
st.caption("Powered by 🧠 LangChain + Groq + Chroma + HuggingFace")
