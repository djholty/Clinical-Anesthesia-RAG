from setuptools import setup, find_packages

setup(
    name="clinical_rag",
    version="1.0.0",
    packages=find_packages(),
    install_requires=[
        "fastapi",
        "uvicorn",
        "streamlit",
        "langchain",
        "langchain_community",
        "langchain_chroma",
        "langchain_huggingface",
        "langchain_groq",
        "chromadb",
        "pypdf",
        "python-dotenv",
        "requests",
    ],
)
