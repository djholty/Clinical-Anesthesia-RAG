"""
Main Streamlit App with Navigation
"""
import streamlit as st
import requests
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import os

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
page = st.sidebar.radio("Go to", ["💬 Ask Questions", "📊 Monitoring Dashboard"])

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
                response = requests.post(f"{API_URL}/ask", json={"question": question})
                if response.status_code == 200:
                    answer = response.json()["answer"]
                    st.markdown("### Answer")
                    st.info(answer)
                else:
                    st.error(f"❌ Error: {response.text}")
    
    st.markdown("---")
    st.caption("Powered by 🧠 LangChain + Groq + Chroma + HuggingFace")

# Page 2: Monitoring Dashboard
elif page == "📊 Monitoring Dashboard":
    st.title("📊 RAG Model Monitoring Dashboard")
    st.write("Track and analyze RAG model performance over time")
    
    # Tabs for different views
    tab1, tab2, tab3 = st.tabs(["📈 Overview", "📋 Detailed Results", "📊 Historical Trends"])
    
    # Fetch latest evaluation data
    try:
        response = requests.get(f"{API_URL}/monitoring/latest")
        if response.status_code == 200:
            data = response.json()
            
            if "error" in data:
                st.error(data["error"])
                st.info("Run an evaluation first: `python david_work_files/evaluate_rag.py`")
                st.stop()
            
            # Tab 1: Overview
            with tab1:
                st.header("Latest Evaluation Results")
                
                # Metrics row
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    st.metric(
                        "Overall Accuracy", 
                        f"{data['average_score']:.1f}%",
                        help="Average score across all questions"
                    )
                
                with col2:
                    st.metric(
                        "Total Questions", 
                        data['total_questions'],
                        help="Number of questions evaluated"
                    )
                
                with col3:
                    excellent_pct = (data['score_distribution']['excellent'] / data['total_questions']) * 100
                    st.metric(
                        "Excellent Answers", 
                        f"{excellent_pct:.1f}%",
                        help="Answers scoring 90-100"
                    )
                
                with col4:
                    poor_pct = (data['score_distribution']['poor'] / data['total_questions']) * 100
                    st.metric(
                        "Poor Answers", 
                        f"{poor_pct:.1f}%",
                        help="Answers scoring below 50",
                        delta=f"-{poor_pct:.1f}%" if poor_pct > 0 else None,
                        delta_color="inverse"
                    )
                
                st.divider()
                
                # Score distribution chart
                col1, col2 = st.columns(2)
                
                with col1:
                    st.subheader("Score Distribution")
                    dist_data = data['score_distribution']
                    fig = go.Figure(data=[go.Pie(
                        labels=['Excellent (90-100)', 'Good (70-89)', 'Fair (50-69)', 'Poor (0-49)'],
                        values=[dist_data['excellent'], dist_data['good'], dist_data['fair'], dist_data['poor']],
                        marker=dict(colors=['#00CC96', '#636EFA', '#FFA15A', '#EF553B']),
                        hole=0.4
                    )])
                    fig.update_layout(height=400)
                    st.plotly_chart(fig, use_container_width=True)
                
                with col2:
                    st.subheader("Score Histogram")
                    scores = [r['score'] for r in data['results']]
                    fig = px.histogram(
                        x=scores, 
                        nbins=20,
                        labels={'x': 'Score', 'y': 'Count'},
                        color_discrete_sequence=['#636EFA']
                    )
                    fig.update_layout(height=400, showlegend=False)
                    st.plotly_chart(fig, use_container_width=True)
                
                # Top and bottom performers
                st.divider()
                col1, col2 = st.columns(2)
                
                with col1:
                    st.subheader("🏆 Top 5 Best Answers")
                    df = pd.DataFrame(data['results'])
                    top_5 = df.nlargest(5, 'score')[['question', 'score']]
                    for idx, row in top_5.iterrows():
                        st.success(f"**Score: {row['score']}/100**")
                        st.write(f"Q: {row['question'][:100]}...")
                        st.write("")
                
                with col2:
                    st.subheader("⚠️ Bottom 5 Answers (Need Improvement)")
                    bottom_5 = df.nsmallest(5, 'score')[['question', 'score']]
                    for idx, row in bottom_5.iterrows():
                        st.error(f"**Score: {row['score']}/100**")
                        st.write(f"Q: {row['question'][:100]}...")
                        st.write("")
            
            # Tab 2: Detailed Results
            with tab2:
                st.header("Detailed Question-by-Question Results")
                
                # Filters
                col1, col2, col3 = st.columns(3)
                with col1:
                    score_filter = st.selectbox(
                        "Filter by score range",
                        ["All", "Excellent (90-100)", "Good (70-89)", "Fair (50-69)", "Poor (0-49)"]
                    )
                
                with col2:
                    search_query = st.text_input("Search questions", "")
                
                with col3:
                    sort_by = st.selectbox("Sort by", ["Question Number", "Score (High to Low)", "Score (Low to High)"])
                
                # Apply filters
                df = pd.DataFrame(data['results'])
                
                if score_filter != "All":
                    if "Excellent" in score_filter:
                        df = df[df['score'] >= 90]
                    elif "Good" in score_filter:
                        df = df[(df['score'] >= 70) & (df['score'] < 90)]
                    elif "Fair" in score_filter:
                        df = df[(df['score'] >= 50) & (df['score'] < 70)]
                    elif "Poor" in score_filter:
                        df = df[df['score'] < 50]
                
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
                    score_color = "🟢" if row['score'] >= 90 else "🟡" if row['score'] >= 70 else "🟠" if row['score'] >= 50 else "🔴"
                    
                    with st.expander(f"{score_color} Q{row['index'] + 1}: {row['question'][:80]}... - Score: {row['score']}/100"):
                        st.markdown(f"**Question:** {row['question']}")
                        
                        st.divider()
                        
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            st.markdown("**Expected Answer:**")
                            st.text_area("Expected", row['expected_answer'], height=200, disabled=True, key=f"exp_{idx}")
                        
                        with col2:
                            st.markdown("**RAG Answer:**")
                            st.text_area("RAG", row['rag_answer'], height=200, disabled=True, key=f"rag_{idx}")
                        
                        st.markdown("**Evaluation Reasoning:**")
                        st.info(row['reasoning'])
            
            # Tab 3: Historical Trends
            with tab3:
                st.header("Historical Performance Trends")
                
                # Fetch all evaluations
                try:
                    all_evals_response = requests.get(f"{API_URL}/monitoring/all")
                    if all_evals_response.status_code == 200:
                        all_evals = all_evals_response.json()['evaluations']
                        
                        if len(all_evals) > 1:
                            # Create trend chart
                            df_trends = pd.DataFrame(all_evals)
                            df_trends['timestamp'] = pd.to_datetime(df_trends['timestamp'], errors='coerce')
                            df_trends = df_trends.sort_values('timestamp')
                            
                            fig = px.line(
                                df_trends, 
                                x='timestamp', 
                                y='average_score',
                                markers=True,
                                title='Accuracy Over Time',
                                labels={'average_score': 'Average Score (%)', 'timestamp': 'Date'}
                            )
                            fig.update_layout(height=400)
                            st.plotly_chart(fig, use_container_width=True)
                            
                            # Show table of all evaluations
                            st.subheader("All Evaluation Runs")
                            st.dataframe(
                                df_trends[['timestamp', 'total_questions', 'average_score']].rename(columns={
                                    'timestamp': 'Date',
                                    'total_questions': 'Questions',
                                    'average_score': 'Avg Score (%)'
                                }),
                                use_container_width=True
                            )
                        else:
                            st.info("Run multiple evaluations over time to see trends. Currently showing only one evaluation.")
                            st.write("To run a new evaluation: `python david_work_files/evaluate_rag.py`")
                except Exception as e:
                    st.error(f"Error fetching historical data: {e}")
        
        else:
            st.error(f"Failed to fetch evaluation data: {response.status_code}")
    
    except requests.exceptions.ConnectionError:
        st.error("❌ Cannot connect to backend API")
        st.info("Make sure the FastAPI backend is running: `uvicorn app.main:app`")
    except Exception as e:
        st.error(f"Error: {e}")
        import traceback
        st.code(traceback.format_exc())

