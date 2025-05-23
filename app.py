import streamlit as st
import json
import faiss
import numpy as np
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM, pipeline
from sentence_transformers import SentenceTransformer

# # --------------------- Load Data ---------------------
# @st.cache_resource
# def load_index_and_metadata():
#     index = faiss.read_index("product_faiss.index")
#     with open("product_metadata.json", "r", encoding="utf-8") as f:
#         metadata = json.load(f)
#     return index, metadata
# --------------------- Load Data ---------------------
@st.cache_resource
def load_index_and_metadata():
    index = faiss.read_index("/kaggle/input/data-faiss/product_faiss.index")
    with open("/kaggle/input/data-faiss/product_metadata.json", "r", encoding="utf-8") as f:
        metadata = json.load(f)
    return index, metadata

# --------------------- Load Models ---------------------
@st.cache_resource
def load_models():
    embedder = SentenceTransformer("all-MiniLM-L6-v2")
    model_id = "HuggingFaceH4/zephyr-7b-alpha"
    tokenizer = AutoTokenizer.from_pretrained(model_id)
    model = AutoModelForCausalLM.from_pretrained(
        model_id,
        torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32
    ).to("cuda" if torch.cuda.is_available() else "cpu")
    llm = pipeline("text-generation", model=model, tokenizer=tokenizer, device=0 if torch.cuda.is_available() else -1)
    return embedder, llm

# --------------------- RAG Pipeline ---------------------
def rag_query(user_query, embedder, llm, index, metadata, top_k=5):
    query_embedding = embedder.encode([user_query])
    D, I = index.search(np.array(query_embedding).astype("float32"), top_k)
    top_docs = [metadata[i] for i in I[0]]

    context = "\n".join(
        f"- Brand: {doc['brand']}, Title: {doc['title']}, Tag: {doc['tag']}, Price: {doc['price']}, Discount: {doc['discount']}"
        for doc in top_docs
    )

    prompt = (
        f"You are a helpful assistant that summarizes promotional offers for users.\n"
        f"User query: {user_query}\n"
        f"Relevant offers:\n{context}\n"
        f"Answer:"
    )

    output = llm(prompt, max_new_tokens=200, do_sample=True, temperature=0.7)
    return output[0]["generated_text"].split("Answer:")[-1].strip()

# --------------------- Streamlit UI ---------------------
st.set_page_config(page_title="PromoSensei", page_icon="🎯")
st.title("🎯 PromoSensei - Ask about current promotions")
st.write("Get smart summaries of the latest offers, discounts, and loyalty rewards!")

# Load data & models
index, metadata = load_index_and_metadata()
embedder, llm = load_models()

# Input
user_query = st.text_input("💬 Enter your query:", placeholder="e.g., Any flat 50% off deals today?")

if st.button("🔍 Search"):
    if user_query.strip():
        with st.spinner("Generating response..."):
            try:
                response = rag_query(user_query, embedder, llm, index, metadata)
                st.success("Here's what I found:")
                st.markdown(response)
            except Exception as e:
                st.error(f"Error: {e}")
    else:
        st.warning("Please enter a query.")
