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
                    response = requests.post(f"{API_URL}/ask", json={"question": question}, timeout=30)
                    if response.status_code == 200:
                        answer = response.json()["answer"]
                        st.markdown("### Answer")
                        st.info(answer)
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
                    st.info("Start the server with: `uvicorn app.main:app --reload`")
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
    ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")
    if ADMIN_PASSWORD:
        if "admin_authed" not in st.session_state:
            st.session_state["admin_authed"] = False
        if not st.session_state["admin_authed"]:
            with st.form("admin_login_form"):
                pw = st.text_input("Password", type="password")
                submitted = st.form_submit_button("Login")
            if submitted:
                if pw == ADMIN_PASSWORD:
                    st.session_state["admin_authed"] = True
                    st.success("Authenticated")
                else:
                    st.error("Invalid password")
            if not st.session_state["admin_authed"]:
                st.stop()

    # --- Upload PDFs ---
    st.subheader("Upload PDFs")
    uploaded_pdf = st.file_uploader("Select a PDF to upload", type=["pdf"], accept_multiple_files=False)
    if uploaded_pdf is not None:
        try:
            pdfs_dir = os.path.join("data", "pdfs")
            os.makedirs(pdfs_dir, exist_ok=True)
            dest_path = os.path.join(pdfs_dir, uploaded_pdf.name)
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
            3. Run: `uvicorn app.main:app --reload`
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
                - Make sure the FastAPI server is running: `uvicorn app.main:app --reload`
                - Check server logs for errors
                - Verify the server is accessible at: `http://127.0.0.1:8000`
                - Try refreshing the page and checking the server terminal for error messages
                """)
            except requests.exceptions.ConnectionError:
                st.error("❌ Cannot connect to backend API. Make sure FastAPI server is running.")
                st.info("💡 **How to start the server:**\n```bash\nuvicorn app.main:app --reload\n```")
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
            st.info("Start the server with: `uvicorn app.main:app --reload`")
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
    tab1, tab2, tab3 = st.tabs(["📈 Overview", "📋 Detailed Results", "📊 Historical Trends"])
    
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
        st.info("💡 **How to start the server:**\n```bash\nuvicorn app.main:app --reload\n```")
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
                    ### Correctness Score (Overall Accuracy)
                    **How it's calculated:** An LLM evaluator compares the RAG model's answer to the expected answer, scoring on a 1-4 scale:
                    - **4 (Excellent):** Fully correct and complete
                    - **3 (Good):** Mostly correct with minor omissions
                    - **2 (Fair):** Partially correct but missing key information
                    - **1 (Poor):** Mostly or completely incorrect
                    
                    The average across all questions gives the Overall Accuracy score.
                    """)
                    
                    st.markdown("""
                    ### Citation Quality Score
                    **How it's calculated:** A hybrid approach combining automated metrics (60%) and LLM evaluation (40%):
                    
                    **Automated Metrics:**
                    - Combines precision, recall, and relevance scores from the citation evaluation
                    
                    **LLM Evaluation:**
                    - Assesses relevance, completeness, identifies missing contexts, and flags irrelevant ones
                    - Provides qualitative reasoning for citation quality
                    
                    These are combined into a final 1-4 score (same scale as Correctness).
                    """)
        
        # Metrics row - Expand to include citation scores if available
        if 'average_citation_score' in data:
            col1, col2, col3, col4, col5 = st.columns(5)
        else:
            col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric(
                "Overall Accuracy", 
                f"{data['average_score']:.2f}/4",
                help="Average correctness score across all questions (out of 4)"
            )
        
        with col2:
            if 'average_citation_score' in data:
                st.metric(
                    "Citation Quality", 
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
            if 'average_citation_score' in data:
                st.metric(
                    "Total Questions", 
                    data['total_questions'],
                    help="Number of questions evaluated"
                )
            else:
                excellent_pct = (data['score_distribution']['excellent'] / data['total_questions']) * 100
                st.metric(
                    "Excellent Answers", 
                    f"{excellent_pct:.1f}%",
                    help="Answers scoring 4 (excellent)"
                )
        
        with col4:
            excellent_pct = (data['score_distribution']['excellent'] / data['total_questions']) * 100
            st.metric(
                "Excellent Answers", 
                f"{excellent_pct:.1f}%",
                help="Answers scoring 4 (excellent)"
            )
        
        # col5 only exists when citation scores are available
        if 'average_citation_score' in data:
            with col5:
                cit_excellent_pct = (data.get('citation_score_distribution', {}).get('excellent', 0) / data['total_questions']) * 100
                st.metric(
                    "Excellent Citations", 
                    f"{cit_excellent_pct:.1f}%",
                    help="Citation scores of 4 (excellent)"
                )
        
        # Poor answers metric
        if 'average_citation_score' not in data:
            poor_pct = (data['score_distribution']['poor'] / data['total_questions']) * 100
            st.metric(
                "Poor Answers", 
                f"{poor_pct:.1f}%",
                help="Answers scoring 1 (poor)",
                delta=f"-{poor_pct:.1f}%" if poor_pct > 0 else None,
                delta_color="inverse"
            )
        
        st.divider()
        
        # Score distribution chart - show both correctness and citation if available
        if 'average_citation_score' in data:
            col1, col2, col3 = st.columns(3)
        else:
            col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("Score Distribution")
            dist_data = data['score_distribution']
            fig = go.Figure(data=[go.Pie(
                labels=['Excellent (4)', 'Good (3)', 'Fair (2)', 'Poor (1)'],
                values=[dist_data['excellent'], dist_data['good'], dist_data['fair'], dist_data['poor']],
                marker=dict(colors=['#00CC96', '#636EFA', '#FFA15A', '#EF553B']),
                hole=0.4
            )])
            fig.update_layout(height=400)
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            st.subheader("Correctness Score Histogram")
            scores = [r['score'] for r in data['results']]
            fig = px.histogram(
                x=scores, 
                nbins=20,
                labels={'x': 'Score', 'y': 'Count'},
                color_discrete_sequence=['#636EFA']
            )
            fig.update_layout(height=400, showlegend=False)
            st.plotly_chart(fig, use_container_width=True)
        
        # Citation score chart if available
        if 'average_citation_score' in data:
            with col3:
                st.subheader("Citation Score Distribution")
                if 'citation_score_distribution' in data:
                    cit_dist_data = data['citation_score_distribution']
                    fig = go.Figure(data=[go.Pie(
                        labels=['Excellent (4)', 'Good (3)', 'Fair (2)', 'Poor (1)'],
                        values=[cit_dist_data['excellent'], cit_dist_data['good'], 
                               cit_dist_data['fair'], cit_dist_data['poor']],
                        marker=dict(colors=['#00CC96', '#636EFA', '#FFA15A', '#EF553B']),
                        hole=0.4
                    )])
                    fig.update_layout(height=400)
                    st.plotly_chart(fig, use_container_width=True)
        
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
                        st.plotly_chart(fig, use_container_width=True)
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
                        st.plotly_chart(fig, use_container_width=True)
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
                
                st.markdown("**Correctness Evaluation Reasoning:**")
                st.info(row['reasoning'])
                
                if 'citation_reasoning' in row and pd.notna(row.get('citation_reasoning')):
                    st.markdown("**Citation Evaluation Reasoning:**")
                    st.info(row['citation_reasoning'])
            
    # Tab 3: Historical Trends
    with tab3:
        st.header("Historical Performance Trends")
        
        # Fetch all evaluations
        try:
            all_evals_response = requests.get(f"{API_URL}/monitoring/all", timeout=10)
            if all_evals_response.status_code == 200:
                all_evals = all_evals_response.json()['evaluations']
                
                if len(all_evals) > 1:
                    # Create trend chart
                    df_trends = pd.DataFrame(all_evals)
                    # Parse timestamp format: YYYYMMDD_HHMMSS
                    df_trends['timestamp'] = pd.to_datetime(df_trends['timestamp'], format='%Y%m%d_%H%M%S', errors='coerce')
                    df_trends = df_trends.sort_values('timestamp')
                    
                    fig = px.line(
                        df_trends, 
                        x='timestamp', 
                        y='average_score',
                        markers=True,
                        title='Accuracy Over Time',
                        labels={'average_score': 'Average Score (/4)', 'timestamp': 'Date'}
                    )
                    fig.update_layout(height=400)
                    st.plotly_chart(fig, use_container_width=True)
                    
                    # Show table of all evaluations
                    st.subheader("All Evaluation Runs")
                    st.dataframe(
                        df_trends[['timestamp', 'total_questions', 'average_score']].rename(columns={
                            'timestamp': 'Date',
                            'total_questions': 'Questions',
                            'average_score': 'Avg Score (/4)'
                        }),
                        use_container_width=True
                    )
                else:
                    st.info("Run multiple evaluations over time to see trends. Currently showing only one evaluation.")
                    st.write("To run a new evaluation: `python monitoring/evaluate_rag.py`")
        except Exception as e:
            st.error(f"Error fetching historical data: {e}")
            st.info("Historical data unavailable. Make sure the FastAPI server is running.")

