import os
import re
import numpy as np
from dotenv import load_dotenv
from langchain_core.tools import tool
from langchain_openai import OpenAIEmbeddings

from tools import digital_banking_FAQ, OPENAI_API_KEY

# read FAQ
faq_text = None
with open(digital_banking_FAQ, encoding='utf8') as f:
    faq_text = f.read()
# split FAQ to multiple docs
docs = [{"page_content": txt} for txt in re.split(r"(?=\n###)", faq_text)] # split on ##

# Set up embedding
embeddings_model = OpenAIEmbeddings(api_key = OPENAI_API_KEY)

class VectorStoreRetriever:
    def __init__(self, docs: list, vectors: list):
        self._arr = np.array(vectors)
        self._docs = docs

    # @classmethod decorator is used to define a method that operates on the class itself rather than on instances of the class.
    @classmethod
    def from_docs(cls, docs):
        # generate embedded vectors from docs
        embeddings = embeddings_model.embed_documents([doc["page_content"] for doc in docs])
        vectors = embeddings
        return cls(docs, vectors)

    def query(self, query: str, k: int = 5) -> list[dict]:
        # generated embedded vectors from query
        embed = embeddings_model.embed_query(query)
        # calculate similarity score between query vector and doc vectors
        scores = np.array(embed) @ self._arr.T
        # obtain the k docs with the highest similarity scores
        top_k_idx = np.argpartition(scores, -k)[-k:]
        top_k_idx_sorted = top_k_idx[np.argsort(-scores[top_k_idx])]
        # return k docs with highest similarity scores and the scores
        return [
            {**self._docs[idx], "similarity": scores[idx]} for idx in top_k_idx_sorted
        ]

# Create an instance
retriever = VectorStoreRetriever.from_docs(docs)

# Create a tool function, for searching arline policies
@tool
def lookup_digital_banking_faq(query: str) -> str:
    """check airline policy and check if a given option is allowed.
    Use this function before change flight or any other database change.
    """
    # check the k docs with the highest similarity scores.
    docs = retriever.query(query, k=3)
    # return the docs
    return "\n\n".join([doc["page_content"] for doc in docs])

# # testing
# if __name__ == '__main__':
#     print(lookup_digital_banking_faq.invoke('When should I contact my RM?'))
