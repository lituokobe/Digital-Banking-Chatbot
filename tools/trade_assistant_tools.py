from datetime import datetime
from sqlite3 import connect
from typing import Literal, Optional
import pandas as pd
from langchain_core.prompts import PromptTemplate
from langchain_core.tools import tool
from langchain_tavily import TavilySearch
from pydantic import BaseModel, Field
from graph.llm import llm
from tools import TAVILY_API_KEY, banking_data_db

# data class for structured output
class stock_name_price(BaseModel):
    """
    Return the stock name and its current price.
    """
    stock_name : Optional[str] = Field(description = "the company name of the stock, not the ticker, not with '.com' or any appendix. English name only.")
    stock_price: Optional[float] = Field(description="the current price of the stock")
# Get current stock price, US stock market only
def get_current_price(stock: str):
    """
    Get the current stock price.
    This is not a tool. This is a function that will be used in the tool of check_earnings and trad_stock.
    Args:
        stock: the stock/security/share name

    Returns:
        the stock name and current stock price in a class of stock_price
    """
    # Check if the stock is listed in US stock market
    search = TavilySearch(max_results=1, api_key=TAVILY_API_KEY)
    query_listed = f"The stock market where {stock} is traded"
    response_listed = search.run(query_listed)

    result_listed = llm.invoke(
        f"This describes the listed market of a stock: {response_listed['results'][0]['content']}."
        "If you think it is not listed in the US stock market, return the string of 'No'."
        "Otherwise, return the string of 'Yes'."
        "Only make judgement based on provided information, don't assume anything."
        "Only return the result in string of 'Yes' or 'No'."
    )

    # Formulate the output class
    # Use the stock name from the search result for standardization
    if result_listed.content == 'No':
        no_listed_result = stock_name_price(stock_name = None, stock_price = None)
        return no_listed_result
    else:
        query_price = f"Check the current share price of {stock} in the US stock market."
        response_price = search.run(query_price)
        if response_price["results"][0]["content"]:
            prompt_template = PromptTemplate.from_template(
                'Here is the latest information of a stock price: {info}, '
                'please extract the company English name as the stock name in string and the the stock price in float.'
                'For the stock name, use the English company name, not the ticker, not with "Inc", ".com", "Corporation" or any appendix. Return English name only.'
                'For example, use "Adobe", never use "Adobe Inc.", "Adobe.com" or "Adobe Corporation".'
                'For the stock price, if there are multiple numbers mentioned, use the one with highest probability as the stoke price. Return one float only.'
            )
            runnable = llm.with_structured_output(stock_name_price)
            chain = prompt_template | runnable
            final_response = chain.invoke({'info':response_price["results"][0]["content"]})
        return final_response

# TODO: Tool with Tavily search to get finance information
@tool
def search_stock(stock: str):
    """
    Search for the current stock price and summarize recent market analysis.
    Args:
        stock: the stock/security/share name

    Returns:
        The summary of the stock price and the relevant analysis of the price and the company.
    """
    query = f"Check the current stock price of {stock} and the most recent analysis articles on the stock price movement or the company performance that affects the stock price."
    search = TavilySearch(max_results=3, api_key=TAVILY_API_KEY)
    response = search.run(query)
    if response["results"]:
        prompt_input = "\n\n".join([d["content"] for d in response["results"]])

    final_response = llm.invoke(
        f"Here is the latest information of {stock} stock price: {prompt_input}, please summarize them in following format: The stock price of {stock} is XXX, and the analysis of the stock is XXXX.")

    return final_response.content

# TODO: Tool to check the balance of the user's trading account
@tool
def check_trading_account_balance(user_id: str):
    """
    Check balance of user's trading account.
    Args:
        user_id: the user's id

    Returns:
        the balance of saving account from this user id
    """
    conn = connect(banking_data_db)
    cursor = conn.cursor()
    cursor.execute("SELECT trading_account FROM user WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    if row is None:
        cursor.close()
        conn.close()
        return "No user found with this ID."
    trading_account = row[0]
    if trading_account is None:
        cursor.close()
        conn.close()
        return "The client has no trading account with the bank."

    query = f"SELECT balance FROM {saving_account} where date = (SELECT MAX(date) FROM {saving_account})"
    cursor.execute(query)
    result = cursor.fetchone()
    cursor.close()
    conn.close()
    return f"Your saving account balance is {result[0]}."

# TODO: Tool to check the earnings and holding details of the user's trading account
@tool
def check_earnings(user_id: str):
    """
    Check earning and the performance (gain or loss of each stock and in total) of user's trading account.
    The result will include a detailed description of the stocks in the user's trading account.
    Args:
        user_id: the user's id

    Returns:
        a summary that describes what and how many stocks (equities, shares) the user is holding and what are their market values. What is the current profit or loss of the user.
    """
    conn = connect(banking_data_db)
    cursor = conn.cursor()
    cursor.execute("SELECT trading_account FROM user WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    if row is None:
        cursor.close()
        conn.close()
        return "No user found with this ID."
    trading_account = row[0]
    if trading_account is None:
        cursor.close()
        conn.close()
        return "The client has no trading account with the bank."

    # Calculate the performance
    df_all = pd.read_sql_query(f"SELECT * FROM {trading_account}", conn).sort_values("date").reset_index(drop=True) # Sort trades by date (safety)
    cursor.close()
    conn.close()

    # Dictionary to track each stock's holdings and P&L
    holdings = {}
    for _, row in df_all.iterrows():
        stock = row["stock"]
        volume = row["volume"]  # + for buy, - for sell
        total_amount = row["total_amount"]  # includes trading fee
        unit_cost = row["total_amount"] / row["volume"]

        if stock not in holdings:
            holdings[stock] = {"shares": 0, "cost_basis": 0.0, "realized_earning": 0.0}

        h = holdings[stock]

        if volume > 0:  # Buy
            h["shares"] += volume
            h["cost_basis"] += total_amount

        else:  # Sell
            shares_to_sell = -volume
            avg_cost = h["cost_basis"] / h["shares"] if h["shares"] > 0 else 0
            # Realized P&L from this sale
            realized = (unit_cost - avg_cost) * shares_to_sell
            h["realized_earning"] += realized
            # Reduce shares and cost basis
            h["shares"] += volume  # volume is negative
            h["cost_basis"] -= avg_cost * shares_to_sell

            # Safety check: reset if no shares remain
            if h["shares"] == 0:
                h["cost_basis"] = 0.0

    # Build result dict (only stocks with remaining shares)
    results = []
    for stock, h in holdings.items():
        if h["shares"] > 0:
            avg_price = h["cost_basis"] / h["shares"]
            # get the current stock price
            current_price = get_current_price(stock).stock_price
            results.append({
                "stock": stock,
                "shares_remaining": h["shares"],
                "holding_price": round(avg_price, 2),
                "realized_earning": round(h["realized_earning"], 2),
                "current_price": current_price,
                "holding_value":h["shares"]*current_price,
                "holding_earning":(current_price*h["shares"]) - h["cost_basis"],
                "unrealized_earning": round((current_price - avg_price) * h["shares"], 2) if current_price is not None else None
            })

    # Create a natural language summary
    parts = []
    total_value = 0
    total_holding_earning = 0
    total_realized_earning = 0

    for item in results:
        stock = item['stock']
        shares = item['shares_remaining']
        holding_price = item['holding_price']
        current_price = item['current_price']
        realized = item['realized_earning']
        holding_earning = item['holding_earning']
        holding_value = item['holding_value']

        total_value += holding_value
        total_holding_earning += holding_earning
        total_realized_earning += realized

        parts.append(
            f"stock {stock} with {shares} shares at ${holding_price:.2f} per share, "
            f"the current price of the stock is ${current_price:.2f}, "
            f"the current holding value is ${holding_value:,.2f}, "
            f"the current holding earning is ${holding_earning:,.2f}, "
            f"and the realized earning is ${realized:,.2f}."
        )

    summary = "The user is holding:\n" + "\n".join(parts) + (
        f"\n\nIn total, the user's total holding value of all stocks is "
        f"${total_value:,.2f}, the total holding earning is ${total_holding_earning:,.2f}, and the total realized earning is ${total_realized_earning:,.2f}."
    )
    return summary

# TODO: Tool to check pending orders
@tool
def check_pending_order(user_id: str):
    """
    Check pending orders of the user.
    Args:
        user_id: user's id

    Returns:
        Information about user's pending orders.
    """
    # Have the user's trading account first.
    conn = connect(banking_data_db)
    cursor = conn.cursor()
    cursor.execute("SELECT trading_account FROM user WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    if row is None:
        cursor.close()
        conn.close()
        return "No user found with this ID."
    trading_account = row[0]
    if trading_account is None:
        cursor.close()
        conn.close()
        return "The user has no trading account with the bank."

    # Have the pending orders
    query = "SELECT * FROM pending_orders WHERE trading_account = ?"
    df_orders = pd.read_sql_query(query, conn, params=(trading_account,)).reset_index(drop=True)
    dict_orders = df_orders.to_dict(orient="records")
    cursor.close()
    conn.close()

    if len(dict_orders) == 0:
        return "The user has no pending orders."
    else:
        buy_order_amount = 0
        order_summary = "Below are the user's pending orders (Daily Limited Orders):\n"
        for item in dict_orders:
            order_summary += (
                f"- {item['action']} order of {abs(item['volume'])} shares of {item['stock']} at ${item['unit_price']:.2f} per share "
                f"with trading fee of ${item['trading_fee']:.2f}, total transfer amount is ${abs(item['total_amount']):.2f}.\n"
            )
            if item['action'] == "buy":
                buy_order_amount += item['total_amount']

        if buy_order_amount > 0:
            order_summary += f"The total pending buy order amount is ${buy_order_amount:.2f}."

        return order_summary

#TODO: Tool to perform a trade
@tool
def trade_stock(user_id: str, stock: str, action: Literal["buy", "sell"], volume: int, price: float):
    """
    Perform a trade (buy or sell stocks/securities/shares) on the user's trading account.
    Only day limit orders are supported.
    To submit the buy order request successfully, the user must have sufficient fund in the trading account.
    The sufficient fund means cash excluding the amount of other pending buy orders.
    Args:
        user_id: the user's id
        stock: the name of the stock/security/share to trade
        action: the type of trade, buy or sell
        volume: the volume of the trade
        price: the bid/asking price of the trade

    Returns:
        The status of the trade, and an update to the database if the trade is successfully submitted.
    """
    current_price = get_current_price(stock)
    if current_price.stock_name is None:
        return f"The stock you want to {action} is not available in the US stock market. We only support tradeing in the US stock market."
    else:
        stock = current_price.stock_name
    # Get user trading account information
    conn = connect(banking_data_db)
    cursor = conn.cursor()
    cursor.execute("SELECT trading_account FROM user WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    if row is None:
        cursor.close()
        conn.close()
        return "No user found with this ID."
    trading_account = row[0]
    if trading_account is None:
        cursor.close()
        conn.close()
        return "The user has no trading account with the bank."

    # Trading information for both buy and sell orders
    # Trading history and trading account balance
    df_all = pd.read_sql_query(f"SELECT * FROM {trading_account}", conn).sort_values("date").reset_index(drop=True)
    # Pending orders
    query = "SELECT * FROM pending_orders WHERE trading_account = ?"
    df_orders = pd.read_sql_query(query, conn, params=(trading_account,)).reset_index(drop=True)
    # Trading amount
    trading_amount = price * volume
    trading_fee = trading_amount * 0.005
    # Current date and time
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Trade logic
    # Buy orders
    if action == "buy":
        # Get available funds for validation of buy orders
        # Get latest cash_end
        current_cash = df_all["cash_end"].iloc[-1]
        # Get the pending buy order amount
        df_buy_orders = df_orders[df_orders["action"] == "buy"]
        dict_buy_orders = df_buy_orders.to_dict(orient="records")
        pending_buy_order_amount = 0
        if len(dict_buy_orders) > 0:
            pending_buy_order_amount = sum(item["total_amount"] for item in dict_buy_orders)

        # Get total amount and available fund for the buy order
        total_amount = trading_amount + trading_fee
        available_funds = current_cash - pending_buy_order_amount

        if price < current_price.stock_price * 0.8:
            cursor.close()
            conn.close()
            return f"Your bid price falls below the permitted threshold of ${current_price.stock_price * 0.8:,.2f}. Kindly revise your buy order to comply with the requirements."
        elif total_amount > current_cash:
            cursor.close()
            conn.close()
            return (
                f"Insufficient funds: Your trading account does not currently hold sufficient funds to place this buy order.\n"
                f"Required amount (including applicable trading fees): ${total_amount:,.2f}.\n"
                f"Available funds for trading: ${available_funds:,.2f}.\n"
                "Please ensure your account is adequately funded before submitting a new order."
            )
        else:
            cursor.execute(
                """
                INSERT INTO pending_orders (date, trading_account, stock, action, unit_price, volume, trading_amount, trading_fee, total_amount)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (now, trading_account, current_price.stock_name, "buy", price, volume, trading_amount, trading_fee,
                 total_amount)
            )
            conn.commit()
            cursor.close()
            conn.close()
            return (
                f"Order Confirmation: Your request to purchase {volume} shares of {current_price.stock_name} at ${price:,.2f} per share has been successfully submitted.\n"
                f"Total amount reserved for settlement: ${total_amount:,.2f}, which includes a trading fee of ${trading_fee:,.2f}."
            )

    # Sell orders
    elif action == "sell":
        # Get available shares for validation of sell orders
        # Track holdings
        df_stock = df_all[df_all["stock"] == stock]
        current_holdings = 0
        if len(df_stock) > 0:
            current_holdings = df_stock["volume"].sum()
        # Get pending volume for sell orders
        df_sell_orders = df_orders[df_orders["action"] == "sell"]
        df_stock_sell_orders = df_sell_orders[df_sell_orders["stock"] == stock]
        pending_sell_order_volume = 0
        if len(df_stock_sell_orders) > 0:
            pending_sell_order_volume = abs(df_stock_sell_orders["volume"].sum())

        # Get total amount and available volume for the sell order
        total_amount = trading_amount - trading_fee
        available_volume = current_holdings - pending_sell_order_volume

        if available_volume < volume:
            cursor.close()
            conn.close()
            return (
                f"You do not currently hold a sufficient quantity of {current_price.stock_name} shares to place this sell order.\n"
                f"Available volume for trading: {int(available_volume)}.\n"
            )
        elif price > current_price.stock_price * 1.2:
            cursor.close()
            conn.close()
            return f"Your asking price exceeds the allowable limit of ${current_price.stock_price * 1.2:,.2f}. Please adjust your sell order to align with the requirements."
        else:
            cursor.execute(
                """
                INSERT INTO pending_orders (date, trading_account, stock, action, unit_price, volume, trading_amount, trading_fee, total_amount)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (now, trading_account, current_price.stock_name, "sell", price, int(volume * (-1)),
                 trading_amount * (-1), trading_fee, total_amount * (-1))
            )
            conn.commit()
            cursor.close()
            conn.close()
            return (
                f"Order Confirmation: Your request to sell {volume} shares of {current_price.stock_name} at ${price:,.2f} per share has been successfully submitted.\n"
                f"Estimated net proceeds from this transaction: ${total_amount:,.2f}, after deducting a trading fee of ${trading_fee:,.2f}."
            )

    return "The specified trade action is invalid. Kindly select either 'buy' or 'sell' to proceed with your transaction."
