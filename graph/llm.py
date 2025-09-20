from langchain_openai import ChatOpenAI
from tools import OPENAI_BASE_URL, OPENAI_API_KEY

# llm = ChatOpenAI(
#     model='gpt-4.1-nano',
#     base_url= OPENAI_BASE_URL,
#     api_key = OPENAI_API_KEY,
#     temperature=0,
# )

llm = ChatOpenAI(
    model='gpt-4.1',
    base_url= OPENAI_BASE_URL,
    api_key = OPENAI_API_KEY,
    temperature=0,
)