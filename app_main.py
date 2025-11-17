"""
Main Streamlit App with Navigation
"""
import streamlit as st
import requests
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import os
import time
import json

# FastAPI backend URL
API_URL = os.getenv("API_URL", "http://127.0.0.1:8000")

st.set_page_config(page_title="Clinical Anesthesia QA System", layout="wide", page_icon="💉")

# Custom CSS
st.markdown("""
<style>
    /* Change text input focus border from red to blue */
    input:focus {
        border-color: #1f77b4 !important;
        outline: none !important;
        box-shadow: 0 0 0 1px #1f77b4 !important;
    }
    
    /* Change form border color */
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

# Sidebar navigation
st.sidebar.title("Navigation")
page = st.sidebar.radio("Go to", ["💬 Ask Questions", "🔐 Admin"])

# Theme info
with st.sidebar.expander("🎨 Theme", expanded=False):
    st.caption("Switch between light and dark themes using the ⋮ menu → Settings → Theme")

# Page 1: Ask Questions (Original Frontend)
if page == "💬 Ask Questions":
    st.title("💉 Clinical Anesthesia QA System")
    st.write("Interact with your custom RAG model using uploaded PDF guidelines.")
    
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
                try:
                    # Debug: Show API URL being called
                    if st.session_state.get("debug_mode", False):
                        st.caption(f"🔍 Calling API: {API_URL}/ask")
                    
                    response = requests.post(f"{API_URL}/ask", json={"question": question}, timeout=30)
                    
                    # Debug: Show response status
                    if st.session_state.get("debug_mode", False):
                        st.caption(f"🔍 Response status: {response.status_code}")
                    
                    if response.status_code == 200:
                        result = response.json()
                        answer = result.get("answer", "No answer provided")
                        contexts = result.get("contexts", [])
                        
                        st.markdown("### Answer")
                        st.info(answer)
                        
                        # Show contexts if available
                        if contexts:
                            st.markdown("---")
                            st.markdown(f"### 📚 Sources ({len(contexts)} sources)")
                            
                            for idx, ctx in enumerate(contexts, 1):
                                source = ctx.get("source", "Unknown")
                                content = ctx.get("content", "")
                                
                                # Extract just the filename from full path if present
                                if "/" in source:
                                    source_filename = source.split("/")[-1]
                                else:
                                    source_filename = source
                                
                                # Use expander for each source to keep it organized and compact
                                with st.expander(f"📄 Source {idx}: {source_filename}", expanded=False):
                                    # Display full content in a readable, scrollable format
                                    if content:
                                        # Calculate appropriate height based on content length
                                        content_lines = len(content.split('\n'))
                                        # Show more lines for longer content, but cap at reasonable max
                                        content_height = min(400, max(150, content_lines * 15))
                                        
                                        st.text_area(
                                            "**Content Excerpt:**",
                                            value=content.strip(),
                                            height=content_height,
                                            disabled=True,
                                            key=f"source_{idx}_content",
                                            help="Full text excerpt from this source document. Scroll to read complete content."
                                        )
                                        st.caption(f"📏 {len(content)} characters | {content_lines} lines")
                                    else:
                                        st.warning("No content available for this source")
                    elif response.status_code == 401:
                        # API key error
                        error_detail = response.json().get("detail", "Unknown API key error")
                        st.error("🔑 **API Key Error**")
                        st.warning(error_detail)
                        with st.expander("💡 How to Fix"):
                            st.markdown("""
                            1. Check your `.env` file has `GROQ_API_KEY=your_key_here`
                            2. Verify your Groq API key is valid at: https://console.groq.com/
                            3. Make sure you haven't exceeded your API quota
                            4. Restart the FastAPI server after updating your `.env` file
                            """)
                    elif response.status_code == 504:
                        # Timeout error
                        error_detail = response.json().get("detail", "Request timed out")
                        st.error("⏱️ **Request Timeout**")
                        st.warning(error_detail)
                        with st.expander("💡 Troubleshooting"):
                            st.markdown("""
                            **The Groq API took too long to respond. Try:**
                            1. Wait a moment and try again (API might be temporarily slow)
                            2. Simplify your question or break it into smaller parts
                            3. Check Groq status page for service issues
                            4. Try using a simpler/shorter question first to test if API is responsive
                            """)
                    elif response.status_code == 503:
                        # Service unavailable / over capacity
                        error_detail = response.json().get("detail", "Service unavailable")
                        st.error("🔴 **API Over Capacity**")
                        st.warning(error_detail)
                        with st.expander("💡 What to do"):
                            st.markdown("""
                            **The Groq API is currently overloaded. Try:**
                            1. Wait and try again later (the system will automatically back off exponentially)
                            2. Check service status: https://groqstatus.com
                            3. Consider running evaluations during off-peak hours
                            4. The system will automatically retry with exponential backoff
                            """)
                    elif response.status_code == 429:
                        # Rate limit / quota exceeded
                        error_detail = response.json().get("detail", "Rate limit exceeded")
                        st.error("⏱️ **Rate Limit / Quota Exceeded**")
                        st.warning(error_detail)
                        with st.expander("💡 How to Fix"):
                            st.markdown("""
                            1. You may have reached your Groq API usage limit
                            2. Check your usage at: https://console.groq.com/
                            3. Wait a bit and try again (limits reset periodically)
                            4. Consider upgrading your Groq plan if you need more quota
                            5. Check if evaluations are running in the background (they use API calls too)
                            """)
                    else:
                        error_text = response.text
                        try:
                            error_json = response.json()
                            error_detail = error_json.get("detail", error_text)
                        except:
                            error_detail = error_text[:500]
                        st.error(f"❌ Error {response.status_code}: {error_detail}")
                except requests.exceptions.Timeout:
                    st.error("❌ Request timed out after 30 seconds.")
                    st.info("The Groq API may be slow or unresponsive. Try again in a moment.")
                except requests.exceptions.ConnectionError:
                    st.error("❌ Cannot connect to backend API. Make sure FastAPI server is running.")
                    st.info("Start the server with: `./start_server.sh` (or see README for full command)")
                except Exception as e:
                    st.error(f"❌ Unexpected error: {str(e)}")
                    with st.expander("Debug Details"):
                        st.code(f"Error type: {type(e).__name__}\nError: {str(e)}")
    
    st.markdown("---")
    st.caption("Powered by 🧠 LangChain + Groq + Chroma + HuggingFace")

# Page 2: Admin (Monitoring + Upload)
elif page == "🔐 Admin":
    st.title("🔐 Admin")
    st.write("Monitoring and PDF upload portal")

    # --- Password protection ---
    import hashlib
    import hmac
    import time
    
    ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")
    if ADMIN_PASSWORD:
        if "admin_authed" not in st.session_state:
            st.session_state["admin_authed"] = False
            st.session_state["login_attempts"] = 0
            st.session_state["last_login_attempt"] = 0
        
        # Session timeout (1 hour)
        SESSION_TIMEOUT = 3600
        if st.session_state.get("admin_authed") and st.session_state.get("last_activity"):
            if time.time() - st.session_state["last_activity"] > SESSION_TIMEOUT:
                st.session_state["admin_authed"] = False
                st.session_state["login_attempts"] = 0
                st.error("Session expired. Please login again.")
        
        if not st.session_state["admin_authed"]:
            # Rate limiting: max 5 attempts per 15 minutes
            RATE_LIMIT_WINDOW = 900  # 15 minutes
            MAX_ATTEMPTS = 5
            current_time = time.time()
            
            # Reset attempts if window expired
            if current_time - st.session_state["last_login_attempt"] > RATE_LIMIT_WINDOW:
                st.session_state["login_attempts"] = 0
            
            if st.session_state["login_attempts"] >= MAX_ATTEMPTS:
                time_remaining = RATE_LIMIT_WINDOW - (current_time - st.session_state["last_login_attempt"])
                if time_remaining > 0:
                    minutes = int(time_remaining / 60)
                    st.error(f"Too many login attempts. Please wait {minutes} minute(s) before trying again.")
                    st.stop()
                else:
                    st.session_state["login_attempts"] = 0
            
            with st.form("admin_login_form"):
                pw = st.text_input("Password", type="password")
                submitted = st.form_submit_button("Login")
            
            if submitted:
                st.session_state["last_login_attempt"] = time.time()
                st.session_state["login_attempts"] = st.session_state.get("login_attempts", 0) + 1
                
                # Use constant-time comparison to prevent timing attacks
                # Hash both passwords and compare hashes using hmac.compare_digest
                input_hash = hashlib.sha256(pw.encode()).hexdigest()
                stored_hash = hashlib.sha256(ADMIN_PASSWORD.encode()).hexdigest()
                
                if hmac.compare_digest(input_hash, stored_hash):
                    st.session_state["admin_authed"] = True
                    st.session_state["login_attempts"] = 0
                    st.session_state["last_activity"] = time.time()
                    st.success("Authenticated")
                    st.rerun()  # Refresh to show admin content
                else:
                    st.error("Invalid password")
            
            if not st.session_state["admin_authed"]:
                st.stop()
        else:
            # Update last activity time
            st.session_state["last_activity"] = time.time()

    # --- Upload PDFs ---
    st.subheader("Upload PDFs")
    uploaded_pdf = st.file_uploader("Select a PDF to upload", type=["pdf"], accept_multiple_files=False)
    if uploaded_pdf is not None:
        try:
            # Import security utils
            from app.security_utils import sanitize_filename
            
            # Sanitize filename to prevent path traversal
            safe_filename = None
            try:
                safe_filename = sanitize_filename(uploaded_pdf.name)
            except ValueError as e:
                st.error(f"Invalid filename: {str(e)}")
            
            # Only proceed with upload if filename validation passed
            if safe_filename:
                pdfs_dir = os.path.join("data", "pdfs")
                os.makedirs(pdfs_dir, exist_ok=True)
                dest_path = os.path.join(pdfs_dir, safe_filename)
                with open(dest_path, "wb") as f:
                    f.write(uploaded_pdf.getbuffer())
                st.success(f"Saved to {dest_path}")
                st.info("If conversion is enabled or a watcher is running, a corresponding .md will be generated in data/ingested_documents.")
        except Exception as e:
            st.error(f"Upload failed: {e}")

    st.markdown("---")
    st.header("📊 RAG Model Monitoring Dashboard")
    st.write("Track and analyze RAG model performance over time")
    
    # First, check if server is reachable
    server_reachable = False
    with st.expander("🔍 Server Connection Status", expanded=True):
        try:
            health_check = requests.get(f"{API_URL}/health", timeout=3)
            if health_check.status_code == 200:
                health_data = health_check.json()
                st.success(f"✅ Server is reachable at {API_URL}")
                st.json(health_data)
                server_reachable = True
            else:
                st.warning(f"⚠️ Server responded with status {health_check.status_code}")
                st.code(health_check.text)
        except requests.exceptions.ConnectionError:
            st.error(f"❌ **Cannot connect to server at {API_URL}**")
            st.info("""
            **The FastAPI server is not running or not accessible.**
            
            **To start the server:**
            1. Open a new terminal window
            2. Navigate to the project directory
            3. Run: `./start_server.sh` (or `uvicorn app.main:app --reload --reload-exclude '.venv/*'`)
            4. You should see: `INFO: Uvicorn running on http://127.0.0.1:8000`
            5. Refresh this page
            """)
        except requests.exceptions.Timeout:
            st.error(f"⏱️ **Request timed out when connecting to {API_URL}**")
            st.info("The server might be overloaded or not responding. Check the server terminal for errors.")
        except Exception as e:
            st.error(f"❌ **Error checking server status: {str(e)}**")
            st.code(f"Error type: {type(e).__name__}\nError: {str(e)}")
    
    if not server_reachable:
        st.warning("⚠️ **Monitoring features require the FastAPI server to be running.**")
        st.stop()
    
    # Check if evaluation is running for auto-refresh and fetch status
    evaluation_running = False
    status_data = {}
    try:
        status_check = requests.get(f"{API_URL}/monitoring/evaluation_status", timeout=5)
        if status_check.status_code == 200:
            status_data = status_check.json()
            evaluation_running = status_data.get("is_running", False)
            # Debug: show status in sidebar (comment out after debugging)
            with st.sidebar.expander("🔍 Debug Status", expanded=False):
                st.json(status_data)
                st.write(f"evaluation_running: {evaluation_running}")
    except requests.exceptions.ConnectionError:
        # API not available, can't check status
        st.sidebar.error("Cannot connect to API")
        pass
    except requests.exceptions.Timeout:
        # Timeout checking status, skip auto-refresh
        st.sidebar.warning("API timeout")
        pass
    except Exception as e:
        # Show exception for debugging
        st.sidebar.error(f"Status check error: {str(e)}")
        pass
    
    # Prominent progress display at the top when evaluation is running
    if evaluation_running:
        # Always show progress when evaluation is detected as running
        total = status_data.get("total_questions", 0) if status_data else 0
        current = status_data.get("current_question", 0) if status_data else 0
        progress_percent = status_data.get("progress_percent", 0.0) if status_data else 0.0
        message = status_data.get("message", "Processing...") if status_data else "Evaluation running..."
        
        # Large, prominent progress banner
        st.markdown("---")
        st.markdown(f"### 🔄 Evaluation Running - Progress: {progress_percent:.1f}%")
        
        if total > 0:
            progress = current / total if total > 0 else 0.0
            # Large progress bar
            st.progress(progress, text=f"Processing question {current} of {total} ({progress_percent:.1f}% complete)")
            
            # Progress metrics in columns
            prog_col1, prog_col2, prog_col3 = st.columns(3)
            with prog_col1:
                st.metric("Completed", f"{current}", f"of {total}")
            with prog_col2:
                remaining = total - current
                st.metric("Remaining", f"{remaining}")
            with prog_col3:
                st.metric("Status", "🔄 Running")
            
            st.info(f"📝 {message}")
        else:
            # Show progress even when total is 0 (initializing)
            st.progress(0.0, text="Initializing evaluation...")
            st.info(f"⏳ {message}")
        
        st.markdown("---")
        
        # Auto-refresh every 2 seconds while running
        time.sleep(2)
        st.rerun()
    
    # Evaluation Control Section
    st.header("🚀 Run Evaluation")
    
    # Info box about running evaluations through the web interface
    st.info("💡 **Tip:** Use the button below to run evaluations through this web interface. Progress will be displayed here in real-time. If you run evaluations directly from the command line, progress will only show in the console.")
    
    col1, col2, col3 = st.columns([2, 2, 1])
    
    with col1:
        if st.button("▶️ Run New Evaluation", type="primary", use_container_width=True):
            try:
                # Increased timeout to 30 seconds to allow for server initialization
                response = requests.post(f"{API_URL}/monitoring/trigger_evaluation", timeout=30)
                if response.status_code == 200:
                    result = response.json()
                    if result["status"] == "started":
                        st.success("✅ Evaluation started! It will run in the background.")
                        st.info("ℹ️ Page will auto-refresh every 2 seconds to show real-time progress.")
                        # Give API a moment to set status, then check it
                        time.sleep(0.5)
                        # Verify status was set before rerunning
                        try:
                            verify_response = requests.get(f"{API_URL}/monitoring/evaluation_status", timeout=5)
                            if verify_response.status_code == 200:
                                verify_data = verify_response.json()
                                if verify_data.get("is_running", False):
                                    st.success(f"✅ Status confirmed: {verify_data.get('message', 'Running')}")
                        except:
                            pass  # Continue even if verification fails
                        # Trigger immediate refresh to start auto-refresh loop
                        st.rerun()
                    else:
                        st.warning(result.get("message", "Could not start evaluation"))
                else:
                    st.error(f"Error {response.status_code}: {response.text}")
            except requests.exceptions.Timeout:
                st.error("⚠️ Request timed out after 30 seconds.")
                st.info("💡 **Troubleshooting:**")
                st.markdown("""
                - Make sure the FastAPI server is running: `./start_server.sh`
                - Check server logs for errors
                - Verify the server is accessible at: `http://127.0.0.1:8000`
                - Try refreshing the page and checking the server terminal for error messages
                """)
            except requests.exceptions.ConnectionError:
                st.error("❌ Cannot connect to backend API. Make sure FastAPI server is running.")
                st.info("💡 **How to start the server:**\n```bash\n./start_server.sh\n```")
            except Exception as e:
                st.error(f"Failed to trigger evaluation: {e}")
                with st.expander("Debug Details"):
                    st.code(f"Error type: {type(e).__name__}\nError: {str(e)}")
    
    with col2:
        # Check evaluation status and show progress
        try:
            status_response = requests.get(f"{API_URL}/monitoring/evaluation_status", timeout=5)
            if status_response.status_code == 200:
                status_data = status_response.json()
                # Use .get() to safely access keys with defaults
                if status_data.get("is_running", False):
                    total = status_data.get("total_questions", 1)
                    current = status_data.get("current_question", 0)
                    progress_percent = status_data.get("progress_percent", 0.0)
                    message = status_data.get("message", "Processing...")
                    
                    if total > 0 and current >= 0:
                        progress = current / total if total > 0 else 0.0
                        
                        # Show status with progress percentage
                        st.warning(f"⏳ Evaluation in progress")
                        
                        # Enhanced progress bar with visual indicators
                        st.progress(progress, text=f"{progress_percent:.1f}% Complete")
                        
                        # Progress details
                        st.metric(
                            "Progress", 
                            f"{current} / {total} questions",
                            delta=f"{int(progress_percent)}%"
                        )
                        
                        # Show message
                        st.caption(f"📝 {message}")
                        
                        # Estimate time remaining if we have progress data
                        if current > 0 and progress < 1.0 and progress > 0:
                            elapsed_per_question = time.time()  # This would need to be tracked on backend
                            remaining_questions = total - current
                            # Note: Actual time estimation would require timing data from backend
                            
                    else:
                        st.warning("⏳ Evaluation starting...")
                        st.caption(status_data.get("message", "Initializing..."))
                        
                elif status_data.get("status") == "completed":
                    st.success("✅ Last evaluation completed")
                    st.caption(status_data.get("message", ""))
                    # Show final progress
                    total = status_data.get("total_questions", 0)
                    if total > 0:
                        st.progress(1.0, text="100% Complete")
                        st.caption(f"✅ Completed all {total} questions")
                elif status_data.get("status") == "error":
                    st.error("❌ Last evaluation had errors")
                    st.caption(status_data.get("message", ""))
                else:
                    st.info("💤 No evaluation running")
        except requests.exceptions.ConnectionError:
            st.error("❌ Cannot connect to backend API. Make sure FastAPI server is running.")
            st.info("Start the server with: `./start_server.sh`")
        except requests.exceptions.Timeout:
            st.warning("⚠️ Request timed out. API may be busy.")
        except Exception as e:
            st.warning(f"⚠️ Could not fetch evaluation status: {str(e)}")
            with st.expander("Debug Details"):
                st.code(f"Error type: {type(e).__name__}\nError: {str(e)}")
    
    with col3:
        if st.button("🔄 Refresh Status", use_container_width=True):
            st.rerun()
    
    # Enhanced progress display section (appears when evaluation is running)
    try:
        status_response = requests.get(f"{API_URL}/monitoring/evaluation_status", timeout=5)
        if status_response.status_code == 200:
            status_data = status_response.json()
            if status_data.get("is_running", False):
                total = status_data.get("total_questions", 0)
                current = status_data.get("current_question", 0)
                progress_percent = status_data.get("progress_percent", 0.0)
                message = status_data.get("message", "Processing...")
                
                # Always show progress section when running
                st.divider()
                st.subheader("📊 Evaluation Progress")
                
                if total > 0:
                    progress = current / total if total > 0 else 0.0
                    
                    # Progress bar with percentage
                    st.progress(progress, text=f"{progress_percent:.1f}% Complete ({current}/{total} questions)")
                    
                    # Metrics row
                    prog_col1, prog_col2, prog_col3 = st.columns(3)
                    with prog_col1:
                        st.metric("Questions Processed", f"{current}", f"of {total}")
                    with prog_col2:
                        st.metric("Progress", f"{progress_percent:.1f}%", f"{total - current} remaining")
                    with prog_col3:
                        status_icon = "🔄" if progress < 100 else "✅"
                        st.metric("Status", status_icon, status_data.get("status", "running").title())
                    
                    # Current activity message
                    if message:
                        st.info(f"📝 {message}")
                    
                    # Estimated completion (rough estimate - would need timing data for accuracy)
                    if current > 0 and progress < 1.0:
                        # Simple visual indicator
                        remaining = total - current
                        st.caption(f"⏱️ Approximately {remaining} questions remaining")
                else:
                    # Show initializing state
                    st.warning("⏳ Evaluation starting...")
                    st.caption("Initializing evaluation process...")
                    st.progress(0.0, text="Starting...")
    except Exception:
        pass  # Silently fail - status already shown in col2
    
    st.divider()
    
    # Tabs for different views
    tab1, tab2, tab3, tab4 = st.tabs(["📈 Overview", "📋 Detailed Results", "📊 Historical Trends", "✍️ Manual Assessment"])
    
    # Fetch all available evaluations for selection
    all_evaluations = []
    try:
        all_evals_response = requests.get(f"{API_URL}/monitoring/all", timeout=10)
        if all_evals_response.status_code == 200:
            all_evaluations = all_evals_response.json().get('evaluations', [])
            # Sort by timestamp (most recent first)
            all_evaluations.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
    except Exception:
        pass  # Silently fail, will use latest only
    
    # Fetch latest evaluation data with timeout handling
    data = None
    latest_timestamp = None
    try:
        response = requests.get(f"{API_URL}/monitoring/latest", timeout=10)
        if response.status_code == 200:
            data = response.json()
            latest_timestamp = data.get('timestamp', 'Unknown')
            
            if data and "error" in data:
                st.error(data["error"])
                st.info("Run an evaluation first: `python monitoring/evaluate_rag.py`")
                data = None
        elif response.status_code == 404:
            # No evaluation results yet
            data = None
        else:
            # Other status codes
            data = None
    except requests.exceptions.Timeout:
        # Timeout - don't show error, just proceed without data
        data = None
    except requests.exceptions.ConnectionError:
        # Connection error - show helpful message
        st.error("❌ Cannot connect to backend API. Make sure FastAPI server is running.")
        st.info("💡 **How to start the server:**\n```bash\n./start_server.sh\n```")
        data = None
    except Exception as e:
        # Other errors - log but don't stop execution
        data = None
    
    if not data:
        # Show helpful message when no data is available
        st.info("📝 **No evaluation results found yet.** Run your first evaluation using the button above to see results here.")
        st.stop()
    
    # Tab 1: Overview
    with tab1:
        st.header("Latest Evaluation Results")
        
        # Metrics Explanation Section
        with st.expander("📖 How Evaluation Metrics Are Calculated", expanded=False):
                    st.markdown("""
                    ### Correctness Score (Accuracy)
                    **How it's calculated:** An LLM evaluator compares the RAG model's answer to the expected answer, scoring on a 1-4 scale:
                    - **4 (Excellent):** Fully correct and complete
                    - **3 (Good):** Mostly correct with minor omissions
                    - **2 (Fair):** Partially correct but missing key information
                    - **1 (Poor):** Mostly or completely incorrect
                    
                    The average across all questions gives the Accuracy score.
                    """)
                    
                    st.markdown("""
                    ### Citation Score
                    **How it's calculated:** A hybrid approach combining automated metrics (60%) and LLM evaluation (40%):
                    
                    **Automated Metrics:**
                    - Combines precision, recall, and relevance scores from the citation evaluation
                    
                    **LLM Evaluation:**
                    - Assesses relevance, completeness, identifies missing contexts, and flags irrelevant ones
                    - Provides qualitative reasoning for citation quality
                    
                    These are combined into a final 1-4 score (same scale as Correctness).
                    """)
        
        # Metrics row - Show Accuracy, Citation Score, and Good+Excellent percentages
        if 'average_citation_score' in data:
            col1, col2, col3, col4 = st.columns(4)
        else:
            col1, col2, col3 = st.columns(3)
        
        st.subheader("🤖 Automated Evaluation")
        
        with col1:
            st.metric(
                "Accuracy", 
                f"{data['average_score']:.2f}/4",
                help="Average correctness score from automated evaluation (out of 4)"
            )
        
        with col2:
            if 'average_citation_score' in data:
                st.metric(
                    "Citation Score", 
                    f"{data['average_citation_score']:.2f}/4",
                    help="Average citation relevance score (out of 4)"
                )
            else:
                st.metric(
                    "Total Questions", 
                    data['total_questions'],
                    help="Number of questions evaluated"
                )
        
        with col3:
            # Accuracy: Good+Excellent %
            good_excellent_count = data['score_distribution']['excellent'] + data['score_distribution']['good']
            accuracy_good_excellent_pct = (good_excellent_count / data['total_questions']) * 100
            st.metric(
                "Accuracy: Good+Excellent", 
                f"{accuracy_good_excellent_pct:.1f}%",
                help="Percentage of answers scoring 3 (Good) or 4 (Excellent)"
            )
        
        # col4 only exists when citation scores are available
        if 'average_citation_score' in data:
            with col4:
                # Citation Score: Good+Excellent %
                cit_dist = data.get('citation_score_distribution', {})
                cit_good_excellent_count = cit_dist.get('excellent', 0) + cit_dist.get('good', 0)
                cit_good_excellent_pct = (cit_good_excellent_count / data['total_questions']) * 100
                st.metric(
                    "Citation Score: Good+Excellent", 
                    f"{cit_good_excellent_pct:.1f}%",
                    help="Percentage of citations scoring 3 (Good) or 4 (Excellent)"
                )
        
        # Manual Assessment Metrics Section
        # Fetch latest manual assessment
        manual_data_overview = None
        try:
            manual_response = requests.get(f"{API_URL}/monitoring/manual_assessment/latest", timeout=10)
            if manual_response.status_code == 200:
                manual_data_overview = manual_response.json()
                if 'error' in manual_data_overview:
                    manual_data_overview = None
        except Exception:
            manual_data_overview = None
        
        if manual_data_overview:
            # Display manual assessment metrics in same format as automated
            if 'average_citation_score' in manual_data_overview:
                manual_col1, manual_col2, manual_col3, manual_col4 = st.columns(4)
            else:
                manual_col1, manual_col2, manual_col3 = st.columns(3)
            
            with manual_col1:
                st.metric(
                    "Accuracy", 
                    f"{manual_data_overview['average_score']:.2f}/4",
                    help="Average correctness score from manual assessment (out of 4)"
                )
            
            with manual_col2:
                if 'average_citation_score' in manual_data_overview:
                    st.metric(
                        "Citation Score", 
                        f"{manual_data_overview['average_citation_score']:.2f}/4",
                        help="Average citation relevance score from manual assessment (out of 4)"
                    )
                else:
                    st.metric(
                        "Total Questions", 
                        manual_data_overview['total_questions'],
                        help="Number of questions in manual assessment"
                    )
            
            with manual_col3:
                # Accuracy: Good+Excellent %
                manual_good_excellent_count = manual_data_overview['score_distribution']['excellent'] + manual_data_overview['score_distribution']['good']
                manual_accuracy_good_excellent_pct = (manual_good_excellent_count / manual_data_overview['total_questions']) * 100
                st.metric(
                    "Accuracy: Good+Excellent", 
                    f"{manual_accuracy_good_excellent_pct:.1f}%",
                    help="Percentage of answers scoring 3 (Good) or 4 (Excellent) in manual assessment"
                )
            
            # col4 only exists when citation scores are available
            if 'average_citation_score' in manual_data_overview:
                with manual_col4:
                    # Citation Score: Good+Excellent %
                    manual_cit_dist = manual_data_overview.get('citation_score_distribution', {})
                    manual_cit_good_excellent_count = manual_cit_dist.get('excellent', 0) + manual_cit_dist.get('good', 0)
                    manual_cit_good_excellent_pct = (manual_cit_good_excellent_count / manual_data_overview['total_questions']) * 100
                    st.metric(
                        "Citation Score: Good+Excellent", 
                        f"{manual_cit_good_excellent_pct:.1f}%",
                        help="Percentage of citations scoring 3 (Good) or 4 (Excellent) in manual assessment"
                    )
            
            st.subheader("📋 Manual Assessment")
        else:
            st.subheader("📋 Manual Assessment")
            st.info("No manual assessment available yet. Create one in the Manual Assessment tab.")
        
        st.divider()
        
        # Fetch latest manual assessment for bar graphs
        manual_data_for_charts = None
        try:
            manual_response = requests.get(f"{API_URL}/monitoring/manual_assessment/latest", timeout=10)
            if manual_response.status_code == 200:
                manual_data_for_charts = manual_response.json()
                if 'error' in manual_data_for_charts:
                    manual_data_for_charts = None
        except Exception:
            manual_data_for_charts = None
        
        # Score distribution chart - show bar graphs for correctness and citation if available
        if 'average_citation_score' in data:
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("Accuracy Score Distribution")
                scores = [r['score'] for r in data['results']]
                # Count occurrences of each score (1, 2, 3, 4) for automated
                score_counts = pd.Series(scores).value_counts().sort_index()
                score_counts = score_counts.reindex([1, 2, 3, 4], fill_value=0)
                
                # Get manual assessment scores if available
                manual_scores = []
                if manual_data_for_charts and 'results' in manual_data_for_charts:
                    manual_scores = [r.get('score', 0) for r in manual_data_for_charts['results'] if 'score' in r and pd.notna(r.get('score'))]
                
                manual_score_counts = pd.Series(manual_scores).value_counts().sort_index() if manual_scores else pd.Series([], dtype=int)
                manual_score_counts = manual_score_counts.reindex([1, 2, 3, 4], fill_value=0)
                
                # Calculate totals for percentage calculation
                total_automated = len(scores) if scores else 1  # Avoid division by zero
                total_manual = len(manual_scores) if manual_scores else 1  # Avoid division by zero
                
                # Convert counts to percentages
                score_percentages = (score_counts.values / total_automated) * 100 if total_automated > 0 else [0, 0, 0, 0]
                manual_score_percentages = (manual_score_counts.values / total_manual) * 100 if total_manual > 0 else [0, 0, 0, 0]
                
                # Create grouped bar chart
                fig = go.Figure()
                fig.add_trace(go.Bar(
                    x=[1, 2, 3, 4],
                    y=score_percentages,
                    name='Automated Assessment',
                    marker_color='#636EFA'
                ))
                fig.add_trace(go.Bar(
                    x=[1, 2, 3, 4],
                    y=manual_score_percentages,
                    name='Manual Assessment',
                    marker_color='#00CC96'
                ))
                fig.update_xaxes(dtick=1, tickmode='linear', title='Score')
                fig.update_yaxes(title='Percentage (%)', range=[0, 100], tickformat='.0f', ticksuffix='%')
                fig.update_layout(
                    height=400,
                    barmode='group',
                    showlegend=True,
                    legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01)
                )
                st.plotly_chart(fig, use_container_width=True, key="accuracy_dist_chart_with_citation")
        
            with col2:
                st.subheader("Citation Score Distribution")
                cit_scores = [r.get('citation_score', 0) for r in data['results'] if 'citation_score' in r and pd.notna(r.get('citation_score'))]
                if cit_scores:
                    # Count occurrences of each score (1, 2, 3, 4) for automated
                    cit_score_counts = pd.Series(cit_scores).value_counts().sort_index()
                    cit_score_counts = cit_score_counts.reindex([1, 2, 3, 4], fill_value=0)
                    
                    # Get manual assessment citation scores if available
                    manual_cit_scores = []
                    if manual_data_for_charts and 'results' in manual_data_for_charts:
                        manual_cit_scores = [r.get('citation_score', 0) for r in manual_data_for_charts['results'] if 'citation_score' in r and pd.notna(r.get('citation_score'))]
                    
                    manual_cit_score_counts = pd.Series(manual_cit_scores).value_counts().sort_index() if manual_cit_scores else pd.Series([], dtype=int)
                    manual_cit_score_counts = manual_cit_score_counts.reindex([1, 2, 3, 4], fill_value=0)
                    
                    # Calculate totals for percentage calculation
                    total_automated_cit = len(cit_scores) if cit_scores else 1  # Avoid division by zero
                    total_manual_cit = len(manual_cit_scores) if manual_cit_scores else 1  # Avoid division by zero
                    
                    # Convert counts to percentages
                    cit_score_percentages = (cit_score_counts.values / total_automated_cit) * 100 if total_automated_cit > 0 else [0, 0, 0, 0]
                    manual_cit_score_percentages = (manual_cit_score_counts.values / total_manual_cit) * 100 if total_manual_cit > 0 else [0, 0, 0, 0]
                    
                    # Create grouped bar chart
                    fig = go.Figure()
                    fig.add_trace(go.Bar(
                        x=[1, 2, 3, 4],
                        y=cit_score_percentages,
                        name='Automated Assessment',
                        marker_color='#636EFA'
                    ))
                    fig.add_trace(go.Bar(
                        x=[1, 2, 3, 4],
                        y=manual_cit_score_percentages,
                        name='Manual Assessment',
                        marker_color='#00CC96'
                    ))
                    fig.update_xaxes(dtick=1, tickmode='linear', title='Score')
                    fig.update_yaxes(title='Percentage (%)', range=[0, 100], tickformat='.0f', ticksuffix='%')
                    fig.update_layout(
                        height=400,
                        barmode='group',
                        showlegend=True,
                        legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01)
                    )
                    st.plotly_chart(fig, use_container_width=True, key="citation_dist_chart")
                else:
                    st.info("No citation scores available")
        else:
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("Accuracy Score Distribution")
                scores = [r['score'] for r in data['results']]
                # Count occurrences of each score (1, 2, 3, 4) for automated
                score_counts = pd.Series(scores).value_counts().sort_index()
                score_counts = score_counts.reindex([1, 2, 3, 4], fill_value=0)
                
                # Get manual assessment scores if available
                manual_scores = []
                if manual_data_for_charts and 'results' in manual_data_for_charts:
                    manual_scores = [r.get('score', 0) for r in manual_data_for_charts['results'] if 'score' in r and pd.notna(r.get('score'))]
                
                manual_score_counts = pd.Series(manual_scores).value_counts().sort_index() if manual_scores else pd.Series([], dtype=int)
                manual_score_counts = manual_score_counts.reindex([1, 2, 3, 4], fill_value=0)
                
                # Calculate totals for percentage calculation
                total_automated = len(scores) if scores else 1  # Avoid division by zero
                total_manual = len(manual_scores) if manual_scores else 1  # Avoid division by zero
                
                # Convert counts to percentages
                score_percentages = (score_counts.values / total_automated) * 100 if total_automated > 0 else [0, 0, 0, 0]
                manual_score_percentages = (manual_score_counts.values / total_manual) * 100 if total_manual > 0 else [0, 0, 0, 0]
                
                # Create grouped bar chart
                fig = go.Figure()
                fig.add_trace(go.Bar(
                    x=[1, 2, 3, 4],
                    y=score_percentages,
                    name='Automated Assessment',
                    marker_color='#636EFA'
                ))
                fig.add_trace(go.Bar(
                    x=[1, 2, 3, 4],
                    y=manual_score_percentages,
                    name='Manual Assessment',
                    marker_color='#00CC96'
                ))
                fig.update_xaxes(dtick=1, tickmode='linear', title='Score')
                fig.update_yaxes(title='Percentage (%)', range=[0, 100], tickformat='.0f', ticksuffix='%')
                fig.update_layout(
                    height=400,
                    barmode='group',
                    showlegend=True,
                    legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01)
                )
                st.plotly_chart(fig, use_container_width=True, key="accuracy_dist_chart_no_citation")
        
        # Citation sub-metrics visualization removed - keeping only citation_score and correctness
        if False:  # 'average_citation_score' in data:
            # Extract citation metrics from results
            df_results = pd.DataFrame(data['results'])
            citation_metrics_data = []
            
            for _, row in df_results.iterrows():
                if 'citation_metrics' in row:
                    metrics = row['citation_metrics']
                    # Handle JSON string if needed
                    if isinstance(metrics, str):
                        try:
                            metrics = json.loads(metrics)
                        except:
                            continue
                    
                    if isinstance(metrics, dict):
                        citation_metrics_data.append({
                            'faithfulness': metrics.get('faithfulness'),
                            'grounding': metrics.get('grounding'),
                            'precision': metrics.get('precision'),
                            'recall': metrics.get('recall'),
                            'relevance': metrics.get('relevance'),
                            'consistency': metrics.get('consistency'),
                            'citation_score': row.get('citation_score', 0),
                            'question_idx': row.get('index', 0)
                        })
            
            if citation_metrics_data:
                df_metrics = pd.DataFrame(citation_metrics_data)
                st.divider()
                st.subheader("📊 Citation Sub-Metrics Analysis")
                
                # Faithfulness vs Grounding scatter plot
                col1, col2 = st.columns(2)
                
                with col1:
                    st.markdown("**Faithfulness vs Grounding**")
                    # Filter out None values
                    scatter_data = df_metrics[
                        df_metrics['faithfulness'].notna() & 
                        df_metrics['grounding'].notna()
                    ]
                    if not scatter_data.empty:
                        fig = px.scatter(
                            scatter_data,
                            x='grounding',
                            y='faithfulness',
                            size='citation_score',
                            color='citation_score',
                            hover_data=['question_idx'],
                            labels={
                                'grounding': 'Grounding Score (0-1)',
                                'faithfulness': 'Faithfulness Score (0-1)',
                                'citation_score': 'Citation Score (1-4)'
                            },
                            color_continuous_scale='Viridis',
                            title="Answer Grounding vs Claim Faithfulness"
                        )
                        fig.update_traces(marker=dict(line=dict(width=0.5, color='white')))
                        fig.update_layout(height=400, showlegend=False)
                        st.plotly_chart(fig, use_container_width=True, key="faithfulness_grounding_scatter")
                    else:
                        st.info("Insufficient data for scatter plot")
                
                with col2:
                    st.markdown("**Precision vs Recall** (if ground truth available)")
                    # Filter out None values
                    pr_data = df_metrics[
                        df_metrics['precision'].notna() & 
                        df_metrics['recall'].notna()
                    ]
                    if not pr_data.empty:
                        fig = px.scatter(
                            pr_data,
                            x='recall',
                            y='precision',
                            size='citation_score',
                            color='citation_score',
                            hover_data=['question_idx'],
                            labels={
                                'recall': 'Recall@k (0-1)',
                                'precision': 'Precision@k (0-1)',
                                'citation_score': 'Citation Score (1-4)'
                            },
                            color_continuous_scale='Viridis',
                            title="Retrieval Precision vs Recall"
                        )
                        fig.update_traces(marker=dict(line=dict(width=0.5, color='white')))
                        fig.update_layout(height=400, showlegend=False)
                        fig.add_shape(
                            type="line",
                            line=dict(dash="dash", color="gray", width=1),
                            x0=0, x1=1, y0=0, y1=1
                        )
                        st.plotly_chart(fig, use_container_width=True, key="precision_recall_scatter")
                    else:
                        st.info("Precision/Recall require ground truth sources")
                
                # Citation metrics summary statistics
                st.markdown("**Citation Sub-Metrics Summary**")
                metrics_cols = ['faithfulness', 'grounding', 'precision', 'recall', 'relevance', 'consistency']
                available_metrics = [col for col in metrics_cols if col in df_metrics.columns and df_metrics[col].notna().any()]
                
                if available_metrics:
                    summary_stats = df_metrics[available_metrics].describe().T[['mean', 'std', 'min', 'max']]
                    summary_stats.columns = ['Mean', 'Std Dev', 'Min', 'Max']
                    summary_stats = summary_stats.round(3)
                    st.dataframe(summary_stats, use_container_width=True)
                
        # Top and bottom performers
        st.divider()
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("🏆 Top 5 Best Answers")
            df = pd.DataFrame(data['results'])
            top_5 = df.nlargest(5, 'score')[['question', 'score']]
            for idx, row in top_5.iterrows():
                st.success(f"**Score: {row['score']}/4**")
                st.write(f"Q: {row['question'][:100]}...")
                st.write("")
        
        with col2:
            st.subheader("⚠️ Bottom 5 Answers (Need Improvement)")
            bottom_5 = df.nsmallest(5, 'score')[['question', 'score']]
            for idx, row in bottom_5.iterrows():
                st.error(f"**Score: {row['score']}/4**")
                st.write(f"Q: {row['question'][:100]}...")
                st.write("")
            
    # Tab 2: Detailed Results
    with tab2:
        st.header("Detailed Question-by-Question Results")
        
        # Evaluation selector - allow users to choose which evaluation run to view
        if len(all_evaluations) > 1:
            eval_options_dict = {}
            eval_options_list = []
            for eval_info in all_evaluations:
                timestamp = eval_info.get('timestamp', 'Unknown')
                avg_score = eval_info.get('average_score', 0.0)
                total_q = eval_info.get('total_questions', 0)
                # Format timestamp if possible
                try:
                    from datetime import datetime
                    dt = datetime.strptime(timestamp, '%Y%m%d_%H%M%S')
                    formatted_date = dt.strftime('%Y-%m-%d %H:%M:%S')
                    label = f"{formatted_date} - Score: {avg_score:.2f}/4 ({total_q} questions)"
                except:
                    label = f"{timestamp} - Score: {avg_score:.2f}/4 ({total_q} questions)"
                eval_options_dict[timestamp] = label
                eval_options_list.append(timestamp)
            
            # Find index of latest
            selected_idx = 0
            for i, ts in enumerate(eval_options_list):
                if ts == latest_timestamp:
                    selected_idx = i
                    break
            
            selected_timestamp = st.selectbox(
                "📅 Select Evaluation Run:",
                options=eval_options_list,
                format_func=lambda ts: eval_options_dict.get(ts, ts),
                index=selected_idx,
                help="Choose which evaluation run to view detailed results for"
            )
            selected_label = eval_options_dict.get(selected_timestamp, selected_timestamp)
            
            # Fetch the selected evaluation if it's not the latest
            if selected_timestamp != latest_timestamp:
                try:
                    eval_response = requests.get(f"{API_URL}/monitoring/{selected_timestamp}", timeout=10)
                    if eval_response.status_code == 200:
                        data = eval_response.json()
                        st.info(f"📊 Showing results for evaluation from {selected_label.split(' - ')[0]}")
                    else:
                        st.warning(f"Could not load evaluation {selected_timestamp}, showing latest instead.")
                except Exception as e:
                    st.warning(f"Error loading selected evaluation: {e}. Showing latest instead.")
        else:
            # Only one evaluation available, show it
            if all_evaluations:
                eval_info = all_evaluations[0]
                timestamp = eval_info.get('timestamp', 'Unknown')
                try:
                    from datetime import datetime
                    dt = datetime.strptime(timestamp, '%Y%m%d_%H%M%S')
                    formatted_date = dt.strftime('%Y-%m-%d %H:%M:%S')
                    st.caption(f"📅 Evaluation from: {formatted_date}")
                except:
                    st.caption(f"📅 Evaluation timestamp: {timestamp}")
        
        # Quick reference for metrics (if citation sub-metrics are available)
        if any('citation_metrics' in str(r) for r in data.get('results', [])):
            with st.expander("💡 Quick Reference: What Each Metric Means", expanded=False):
                st.markdown("""
                        | Metric | Range | What It Measures |
                        |--------|-------|------------------|
                        | **Correctness Score** | 1-4 | How accurate is the answer compared to the expected answer? |
                        | **Citation Score** | 1-4 | Overall quality of sources retrieved and cited |
                        | **Precision@k** | 0.0-1.0 | % of retrieved sources that match expected sources |
                        | **Recall@k** | 0.0-1.0 | % of expected sources that were successfully found |
                        | **Grounding** | 0.0-1.0 | % of answer citations that match retrieved sources |
                        | **Faithfulness** | 0.0-1.0 | % of answer claims that can be verified in contexts |
                        | **Relevance** | 0.0-1.0 | How semantically similar contexts are to the question |
                        | **Consistency** | 0.0-1.0 | % of citations that match actual retrieval results |
                        """)
                st.caption("💡 Tip: Higher scores are better for all metrics. Scores above 0.7 are generally good.")
        
        # Filters
        col1, col2, col3 = st.columns(3)
        with col1:
            score_filter = st.selectbox(
                "Filter by score range",
                ["All", "Excellent (4)", "Good (3)", "Fair (2)", "Poor (1)"]
            )
        
        with col2:
            search_query = st.text_input("Search questions", "")
        
        with col3:
            sort_by = st.selectbox("Sort by", ["Question Number", "Score (High to Low)", "Score (Low to High)"])
        
        # Apply filters
        df = pd.DataFrame(data['results'])
        
        if score_filter != "All":
            if "Excellent" in score_filter:
                df = df[df['score'] == 4]
            elif "Good" in score_filter:
                df = df[df['score'] == 3]
            elif "Fair" in score_filter:
                df = df[df['score'] == 2]
            elif "Poor" in score_filter:
                df = df[df['score'] == 1]
        
        if search_query:
            df = df[df['question'].str.contains(search_query, case=False, na=False)]
        
        if sort_by == "Score (High to Low)":
            df = df.sort_values('score', ascending=False)
        elif sort_by == "Score (Low to High)":
            df = df.sort_values('score', ascending=True)
        else:
            df = df.sort_values('index')
        
        st.write(f"Showing {len(df)} of {data['total_questions']} questions")
        
        # Display results
        for idx, row in df.iterrows():
            score_color = "🟢" if row['score'] == 4 else "🟡" if row['score'] == 3 else "🟠" if row['score'] == 2 else "🔴"
            
            # Build expander title with scores
            expander_title = f"{score_color} Q{row['index'] + 1}: {row['question'][:80]}... - Correctness: {row['score']}/4"
            if 'citation_score' in row and pd.notna(row.get('citation_score')):
                cit_score = int(row['citation_score']) if pd.notna(row['citation_score']) else 0
                cit_color = "🟢" if cit_score == 4 else "🟡" if cit_score == 3 else "🟠" if cit_score == 2 else "🔴"
                expander_title += f" | Citation: {cit_score}/4 {cit_color}"
            
            with st.expander(expander_title):
                st.markdown(f"**Question:** {row['question']}")
                
                # Show scores side-by-side
                score_col1, score_col2 = st.columns(2)
                with score_col1:
                    st.metric("Correctness Score", f"{int(row['score'])}/4", 
                            help="LLM-evaluated accuracy compared to expected answer")
                with score_col2:
                    if 'citation_score' in row and pd.notna(row.get('citation_score')):
                        st.metric("Citation Score", f"{int(row['citation_score'])}/4",
                                help="Hybrid score (60% automated metrics + 40% LLM evaluation) for citation quality")
                
                st.divider()
                
                col1, col2 = st.columns(2)
                
                with col1:
                    st.markdown("**Expected Answer:**")
                    st.text_area("Expected", row['expected_answer'], height=200, disabled=True, key=f"exp_{idx}")
                
                with col2:
                    st.markdown("**RAG Answer:**")
                    st.text_area("RAG", row['rag_answer'], height=200, disabled=True, key=f"rag_{idx}")
                
                # Show ground truth sources if available
                if 'ground_truth_sources' in row and pd.notna(row.get('ground_truth_sources')) and str(row['ground_truth_sources']).strip():
                    st.markdown("**Expected Sources (Ground Truth):**")
                    st.info(str(row['ground_truth_sources']))
                
                # Show retrieved chunks from vector database
                contexts = row.get('contexts', [])
                if contexts:
                    # Handle contexts if they're JSON strings
                    if isinstance(contexts, str):
                        try:
                            import json
                            contexts = json.loads(contexts)
                        except:
                            contexts = []
                    
                    if contexts and len(contexts) > 0:
                        st.markdown("**Retrieved Chunks from Vector Database:**")
                        st.caption(f"Retrieved {len(contexts)} chunks (default: 4 chunks, ~2000 characters each)")
                        
                        for chunk_idx, context in enumerate(contexts, 1):
                            source = context.get('source', 'Unknown source')
                            page = context.get('page', 'N/A')
                            content = context.get('content', '')
                            char_count = len(content) if content else 0
                            
                            chunk_title = f"Chunk {chunk_idx}: {source}"
                            if page and page != 'N/A' and pd.notna(page):
                                chunk_title += f" (Page {page})"
                            chunk_title += f" ({char_count} chars)"
                            
                            # Use container instead of expander to avoid nesting
                            with st.container():
                                st.markdown(f"**{chunk_title}**")
                                st.markdown(f"**Source:** {source}")
                                if page and page != 'N/A' and pd.notna(page):
                                    st.markdown(f"**Page:** {page}")
                                st.markdown(f"**Character Count:** {char_count}")
                                st.markdown("**Content:**")
                                st.text_area("Content", content, height=200, disabled=True, key=f"chunk_{idx}_{chunk_idx}", label_visibility="hidden")
                                st.divider()
                
                st.markdown("**Correctness Evaluation Reasoning:**")
                st.info(row['reasoning'])
                
                if 'citation_reasoning' in row and pd.notna(row.get('citation_reasoning')):
                    st.markdown("**Citation Evaluation Reasoning:**")
                    st.info(row['citation_reasoning'])
            
    # Tab 3: Historical Trends
    with tab3:
        st.header("Historical Performance Trends")
        
        # Fetch all evaluations and manual assessments
        try:
            all_evals_response = requests.get(f"{API_URL}/monitoring/all", timeout=10)
            all_evals = []
            if all_evals_response.status_code == 200:
                all_evals = all_evals_response.json()['evaluations']
                
            # Fetch manual assessments
            manual_assessments = []
            try:
                manual_response = requests.get(f"{API_URL}/monitoring/manual_assessments", timeout=10)
                if manual_response.status_code == 200:
                    response_data = manual_response.json()
                    manual_assessments = response_data.get('assessments', [])
                elif manual_response.status_code == 404:
                    # No manual assessments found - this is expected if none exist
                    manual_assessments = []
                else:
                    st.warning(f"Error fetching manual assessments: Status {manual_response.status_code}")
            except requests.exceptions.RequestException as e:
                st.warning(f"Could not fetch manual assessments: {str(e)}")
            except Exception as e:
                st.warning(f"Unexpected error fetching manual assessments: {str(e)}")
            
            # Combine evaluations and manual assessments
            all_data = []
            for eval_data in all_evals:
                # Validate required fields for automated evaluations
                if 'timestamp' in eval_data and 'average_score' in eval_data:
                    eval_data['assessment_type'] = 'automated'
                    all_data.append(eval_data)
            
            for manual_data in manual_assessments:
                # Validate required fields for manual assessments
                if 'timestamp' in manual_data and 'average_score' in manual_data:
                    # Ensure timestamp is a string in YYYYMMDD_HHMMSS format
                    if isinstance(manual_data['timestamp'], str):
                        manual_data['assessment_type'] = 'manual'
                        all_data.append(manual_data)
                    else:
                        # Try to convert timestamp if it's not a string
                        try:
                            manual_data['timestamp'] = str(manual_data['timestamp'])
                            manual_data['assessment_type'] = 'manual'
                            all_data.append(manual_data)
                        except Exception:
                            # Skip invalid manual assessment data
                            continue
                else:
                    # Log missing fields but don't show error to user
                    continue
            
            if len(all_data) > 0:
                # Create trend chart
                df_trends = pd.DataFrame(all_data)
                # Parse timestamp format: YYYYMMDD_HHMMSS
                df_trends['timestamp'] = pd.to_datetime(df_trends['timestamp'], format='%Y%m%d_%H%M%S', errors='coerce')
                # Drop rows where timestamp parsing failed
                df_trends = df_trends.dropna(subset=['timestamp'])
                df_trends = df_trends.sort_values('timestamp')
                    
                # Separate automated and manual assessments
                df_automated = df_trends[df_trends['assessment_type'] == 'automated']
                df_manual = df_trends[df_trends['assessment_type'] == 'manual']
                
                # Create figure with both types
                fig = go.Figure()
                
                # Add automated evaluations line
                if not df_automated.empty:
                    fig.add_trace(go.Scatter(
                        x=df_automated['timestamp'],
                        y=df_automated['average_score'],
                        mode='lines+markers',
                        name='Automated Evaluation',
                        marker=dict(color='#636EFA', size=8, symbol='circle'),
                        hovertemplate='<b>Automated Evaluation</b><br>Date: %{x}<br>Score: %{y:.2f}/4<extra></extra>'
                    ))
                
                # Add manual assessments with different color and marker
                if not df_manual.empty:
                    fig.add_trace(go.Scatter(
                        x=df_manual['timestamp'],
                        y=df_manual['average_score'],
                        mode='markers',
                        name='Manual Assessment',
                        marker=dict(color='#00CC96', size=10, symbol='square'),
                        hovertemplate='<b>Manual Assessment</b><br>Date: %{x}<br>Score: %{y:.2f}/4<extra></extra>'
                    ))
                
                # Only show chart if we have at least one data point
                if not df_automated.empty or not df_manual.empty:
                    fig.update_layout(
                        height=400,
                        title='Accuracy Over Time',
                        xaxis_title='Date',
                        yaxis_title='Average Score (/4)',
                        hovermode='closest',
                        legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01)
                    )
                    st.plotly_chart(fig, use_container_width=True, key="historical_trends_chart")
                
                # Show table of all evaluations and assessments
                st.subheader("All Evaluation Runs")
                display_df = df_trends[['timestamp', 'total_questions', 'average_score', 'assessment_type']].copy()
                display_df['assessment_type'] = display_df['assessment_type'].map({'automated': 'Automated', 'manual': 'Manual'})
                st.dataframe(
                    display_df.rename(columns={
                        'timestamp': 'Date',
                        'total_questions': 'Questions',
                        'average_score': 'Avg Score (/4)',
                        'assessment_type': 'Type'
                    }),
                    use_container_width=True
                )
            elif len(all_data) == 1:
                st.info("Run multiple evaluations or manual assessments over time to see trends.")
            else:
                st.info("Run multiple evaluations over time to see trends. Currently showing only one evaluation.")
                st.write("To run a new evaluation: `python monitoring/evaluate_rag.py`")
        except Exception as e:
            st.error(f"Error fetching historical data: {e}")
            st.info("Historical data unavailable. Make sure the FastAPI server is running.")
    
    # Tab 4: Manual Assessment
    with tab4:
        st.header("Manual Assessment")
        st.markdown("Generate a random sample of 20 questions from the latest evaluation and manually assess accuracy and citation scores.")
        
        # Initialize session state for manual assessment
        if 'manual_assessment_questions' not in st.session_state:
            st.session_state.manual_assessment_questions = None
        if 'manual_scores' not in st.session_state:
            st.session_state.manual_scores = {}
        
        # Step 1: Generate random sample
        col1, col2 = st.columns([3, 1])
        with col1:
            st.subheader("Step 1: Generate Random Sample")
            if st.button("Generate Random Sample of 20 Questions", type="primary"):
                try:
                    response = requests.post(f"{API_URL}/monitoring/manual_assessment/start", timeout=10)
                    if response.status_code == 200:
                        data = response.json()
                        if 'error' in data:
                            st.error(data['error'])
                        else:
                            st.session_state.manual_assessment_questions = data.get('questions', [])
                            st.session_state.manual_scores = {}
                            st.success(f"✅ Generated {len(st.session_state.manual_assessment_questions)} random questions!")
                            st.rerun()
                    else:
                        st.error(f"Error generating sample: {response.status_code}")
                except Exception as e:
                    st.error(f"Error connecting to API: {str(e)}")
        
        # Step 2: Display questions and scoring form
        if st.session_state.manual_assessment_questions:
            st.divider()
            st.subheader("Step 2: Assess Questions")
            st.markdown("Rate each question on a scale of 1-4 for both Accuracy and Citation Score.")
            
            # Display questions with scoring inputs
            for idx, question_data in enumerate(st.session_state.manual_assessment_questions):
                with st.expander(f"Question {idx + 1}: {question_data.get('question', '')[:80]}...", expanded=False):
                    st.markdown(f"**Question:** {question_data.get('question', '')}")
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        st.markdown("**RAG Answer:**")
                        st.text_area("RAG Answer", question_data.get('rag_answer', ''), height=150, disabled=True, key=f"manual_rag_{idx}", label_visibility="hidden")
                    
                    with col2:
                        st.markdown("**Expected Answer:**")
                        expected = question_data.get('expected_answer', 'N/A')
                        st.text_area("Expected Answer", expected, height=150, disabled=True, key=f"manual_exp_{idx}", label_visibility="hidden")
                    
                    # Show ground truth sources if available
                    if 'ground_truth_sources' in question_data and pd.notna(question_data.get('ground_truth_sources')) and str(question_data.get('ground_truth_sources', '')).strip():
                        st.markdown("**Expected Sources (Ground Truth):**")
                        st.info(str(question_data.get('ground_truth_sources', '')))
                    
                    # Show retrieved chunks from vector database
                    contexts = question_data.get('contexts', [])
                    if contexts:
                        # Handle contexts if they're JSON strings
                        if isinstance(contexts, str):
                            try:
                                import json
                                contexts = json.loads(contexts)
                            except:
                                contexts = []
                        
                        if contexts and len(contexts) > 0:
                            st.markdown("**Retrieved Chunks from Vector Database:**")
                            st.caption(f"Retrieved {len(contexts)} chunks (default: 4 chunks, ~2000 characters each)")
                            
                            for chunk_idx, context in enumerate(contexts, 1):
                                source = context.get('source', 'Unknown source')
                                page = context.get('page', 'N/A')
                                content = context.get('content', '')
                                char_count = len(content) if content else 0
                                
                                chunk_title = f"Chunk {chunk_idx}: {source}"
                                if page and page != 'N/A' and pd.notna(page):
                                    chunk_title += f" (Page {page})"
                                chunk_title += f" ({char_count} chars)"
                                
                                # Use container instead of expander to avoid nesting
                                with st.container():
                                    st.markdown(f"**{chunk_title}**")
                                    st.markdown(f"**Source:** {source}")
                                    if page and page != 'N/A' and pd.notna(page):
                                        st.markdown(f"**Page:** {page}")
                                    st.markdown(f"**Character Count:** {char_count}")
                                    st.markdown("**Content:**")
                                    st.text_area("Chunk Content", content, height=200, disabled=True, key=f"manual_chunk_{idx}_{chunk_idx}", label_visibility="hidden")
                                    st.divider()
                    
                    # Scoring inputs
                    score_col1, score_col2 = st.columns(2)
                    with score_col1:
                        accuracy_score = st.selectbox(
                            "Accuracy Score (1-4)",
                            options=[1, 2, 3, 4],
                            index=2,  # Default to 3
                            key=f"manual_acc_{idx}",
                            help="1=Poor, 2=Fair, 3=Good, 4=Excellent"
                        )
                    
                    with score_col2:
                        citation_score = st.selectbox(
                            "Citation Score (1-4)",
                            options=[1, 2, 3, 4],
                            index=2,  # Default to 3
                            key=f"manual_cit_{idx}",
                            help="1=Poor, 2=Fair, 3=Good, 4=Excellent"
                        )
                    
                    # Store scores
                    st.session_state.manual_scores[idx] = {
                        'question': question_data.get('question', ''),
                        'rag_answer': question_data.get('rag_answer', ''),
                        'expected_answer': question_data.get('expected_answer', ''),
                        'manual_accuracy_score': accuracy_score,
                        'manual_citation_score': citation_score
                    }
            
            st.divider()
            st.subheader("Step 3: Submit Assessment")
            
            # Check if all questions are scored
            all_scored = len(st.session_state.manual_scores) == len(st.session_state.manual_assessment_questions)
            
            if st.button("Submit Manual Assessment", type="primary", disabled=not all_scored):
                if not all_scored:
                    st.warning("Please score all questions before submitting.")
                else:
                    try:
                        # Prepare submission data
                        questions = list(st.session_state.manual_scores.values())
                        response = requests.post(
                            f"{API_URL}/monitoring/manual_assessment/submit",
                            json={"questions": questions},
                            timeout=30
                        )
                        if response.status_code == 200:
                            data = response.json()
                            if data.get('success'):
                                st.success(f"✅ Manual assessment saved successfully! Timestamp: {data.get('timestamp', '')}")
                                # Clear session state
                                st.session_state.manual_assessment_questions = None
                                st.session_state.manual_scores = {}
                                st.rerun()
                            else:
                                st.error(f"Error: {data.get('error', 'Unknown error')}")
                        else:
                            st.error(f"Error submitting assessment: {response.status_code}")
                    except Exception as e:
                        st.error(f"Error connecting to API: {str(e)}")
            
            if not all_scored:
                st.info(f"📝 Please score all {len(st.session_state.manual_assessment_questions)} questions before submitting.")

