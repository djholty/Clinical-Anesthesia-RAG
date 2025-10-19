"""
Test script to debug RAG pipeline issues.
"""
import os
from dotenv import load_dotenv
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain.chains import create_retrieval_chain

# Load environment variables
load_dotenv()

print("=" * 60)
print("   TESTING RAG PIPELINE")
print("=" * 60)

# Check API keys
print("\n1. Checking API Keys...")
hf_token = os.getenv("HF_TOKEN")
groq_key = os.getenv("GROQ_API_KEY")

if not hf_token:
    print("   ❌ HF_TOKEN not found in .env file")
else:
    print(f"   ✓ HF_TOKEN found: {hf_token[:10]}...")

if not groq_key:
    print("   ❌ GROQ_API_KEY not found in .env file")
else:
    print(f"   ✓ GROQ_API_KEY found: {groq_key[:10]}...")

if not hf_token or not groq_key:
    print("\n❌ Missing API keys. Please add them to .env file:")
    print("   HF_TOKEN=your_huggingface_token")
    print("   GROQ_API_KEY=your_groq_api_key")
    exit(1)

os.environ["HF_TOKEN"] = hf_token
os.environ["GROQ_API_KEY"] = groq_key

# Load embeddings
print("\n2. Loading embeddings model...")
try:
    embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
    print("   ✓ Embeddings model loaded")
except Exception as e:
    print(f"   ❌ Error loading embeddings: {e}")
    exit(1)

# Load vector database
print("\n3. Loading vector database...")
DB_DIR = "./data/chroma_db"
try:
    vectordb = Chroma(persist_directory=DB_DIR, embedding_function=embeddings)
    print(f"   ✓ Vector database loaded from {DB_DIR}")
    
    # Check collection size
    collection = vectordb._collection
    count = collection.count()
    print(f"   ✓ Database contains {count} chunks")
    
    if count == 0:
        print("   ⚠️  Warning: Database is empty! Run rebuild_database.py first.")
        exit(1)
        
except Exception as e:
    print(f"   ❌ Error loading database: {e}")
    exit(1)

# Test retrieval
print("\n4. Testing retrieval...")
try:
    retriever = vectordb.as_retriever(search_kwargs={"k": 3})
    test_query = "What is propofol?"
    docs = retriever.invoke(test_query)
    print(f"   ✓ Retrieved {len(docs)} documents for test query")
    if docs:
        print(f"   ✓ First doc preview: {docs[0].page_content[:100]}...")
    else:
        print("   ⚠️  No documents retrieved!")
except Exception as e:
    print(f"   ❌ Error during retrieval: {e}")
    exit(1)

# Test LLM
print("\n5. Testing LLM (Groq)...")
try:
    llm = ChatGroq(model="llama-3.1-8b-instant")
    print("   ✓ LLM initialized")
except Exception as e:
    print(f"   ❌ Error initializing LLM: {e}")
    exit(1)

# Test full RAG chain
print("\n6. Testing full RAG chain...")
try:
    prompt = ChatPromptTemplate.from_template("""
Answer the following question based only on the provided context:
question: {input}
<context>
{context}
</context>
""")
    
    document_chain = create_stuff_documents_chain(llm, prompt)
    retrieval_chain = create_retrieval_chain(retriever, document_chain)
    
    print("   ✓ RAG chain created")
    
    # Test query
    print("\n7. Running test query...")
    test_question = "What is propofol?"
    print(f"   Question: {test_question}")
    
    response = retrieval_chain.invoke({"input": test_question})
    
    print(f"\n   ✅ Answer received:")
    print(f"   {response['answer']}")
    
    print("\n" + "=" * 60)
    print("   ✅ ALL TESTS PASSED!")
    print("=" * 60)
    
except Exception as e:
    print(f"   ❌ Error during RAG query: {e}")
    import traceback
    traceback.print_exc()
    exit(1)

