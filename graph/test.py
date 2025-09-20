from dotenv import load_dotenv
import os
from langchain_tavily import TavilySearch
from graph.llm import llm
load_dotenv()
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")

def search_stock(stock: str):
    query = f"Check the current stock price of {stock} and the recent 3 analysis articles on the stock price movement."
    search = TavilySearch(max_results=3, api_key=TAVILY_API_KEY)
    response = search.run(query)
    if response["results"]:
        prompt_input = "\n\n".join([d["content"] for d in response["results"]])

    final_response = llm.invoke(f"Here is the latest information of {stock} stock price: {prompt_input}, please summarize it and reply in following format: The stock price of {stock} is XXX, and the marketing analysis of the price is XXXX.")

    return final_response.content

print(search_stock("Apple"))
