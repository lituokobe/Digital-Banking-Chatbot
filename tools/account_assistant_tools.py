from datetime import datetime
import pandas as pd
from langchain_core.tools import tool
from sqlite3 import connect
from tools import banking_data_db

# TODO: Tool to check the balance of the user's saving account
@tool
def check_saving_account_balance(user_id: str):
    """
    Check balance of user's saving account.
    Args:
        user_id: the user's id

    Returns:
        the balance of saving account from this user id
    """
    conn = connect(banking_data_db)
    cursor = conn.cursor()
    cursor.execute("SELECT saving_account FROM user WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    if row is None:
        conn.close()
        cursor.close()
        return "No user found with this ID."
    saving_account = row[0]
    if saving_account is None:
        conn.close()
        cursor.close()
        return "The user has no saving account with the bank."

    query = f"SELECT balance FROM {saving_account} where date = (SELECT MAX(date) FROM {saving_account})"
    cursor.execute(query)
    result = cursor.fetchone()
    cursor.close()
    conn.close()
    return f"Your saving account balance is {result[0]}."

# TODO: Tool to check the transaction history of the user's saving account
@tool
def check_account_history(user_id: str, start_date: str, end_date: str):
    """
    Check transaction history of user's saving account.
    Args:
        user_id: the user's id
        start_date: the start date of the transaction history
        end_date: the end date of the transaction history

    Returns:
        a summary transaction history from this user id
    """
    conn = connect(banking_data_db)
    cursor = conn.cursor()
    cursor.execute("SELECT saving_account FROM user WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    if row is None:
        cursor.close()
        conn.close()
        return "No user found with this ID."
    saving_account = row[0]
    if saving_account is None:
        cursor.close()
        conn.close()
        return "The user has no saving account with the bank."

    # Extract the data in the queried period.
    query = f"""SELECT * FROM {saving_account} WHERE date >= ? AND date < date(?, '+1 day') ORDER BY date"""
    df_all = pd.read_sql_query(query, conn, params=(start_date, end_date)).sort_values("date").reset_index(drop=True)  # Sort trades by date (safety)
    cursor.close()
    conn.close()

    if df_all.empty:
        return "No transactions found within the specified date range."

    df_all["date"] = pd.to_datetime(df_all["date"])

    # Time span in months
    start = pd.to_datetime(start_date)
    end = pd.to_datetime(end_date)
    months_span = max((end.year - start.year) * 12 + end.month - start.month, 1)

    # Income analysis
    df_income = df_all[df_all["transaction_category"] == "Income"]
    total_income = df_income["transaction_amount"].sum()
    highest_income = df_income.loc[df_income["transaction_amount"].idxmax()]
    lowest_income = df_income.loc[df_income["transaction_amount"].idxmin()]
    avg_income = total_income / months_span

    # Expense analysis
    df_expense = df_all[df_all["transaction_category"] == "Expense"]
    total_expense = -df_expense["transaction_amount"].sum()
    highest_expense = df_expense.loc[df_expense["transaction_amount"].idxmin()]
    lowest_expense = df_expense.loc[df_expense["transaction_amount"].idxmax()]
    avg_expense = total_expense / months_span

    # Transfer analysis
    df_transfer = df_all[df_all["transaction_category"] == "Transfer"]
    total_transfer = -df_transfer["transaction_amount"].sum()
    highest_transfer = df_transfer.loc[df_transfer["transaction_amount"].idxmin()]
    lowest_transfer = df_transfer.loc[df_transfer["transaction_amount"].idxmax()]
    avg_transfer = total_transfer / months_span

    # Build summary
    summary = f"**Transaction Summary from {start_date} to {end_date}**\n\n"

    summary += f"**Income Overview**\n"
    summary += f"- Total Income: ${total_income:,.2f}\n"
    summary += f"- Highest Income: ${highest_income['transaction_amount']:,.2f} on {highest_income['date'].date()} ({highest_income['description']})\n"
    if lowest_income is not None:
        summary += f"- Lowest Income (excluding interest): ${lowest_income['transaction_amount']:,.2f} on {lowest_income['date'].date()} ({lowest_income['description']})\n"
    else:
        summary += f"- No non-interest income found to determine lowest income.\n"
    if months_span > 1:
        summary += f"- Average Monthly Income: ${avg_income:,.2f}\n"

    summary += f"\n**Expense Overview**\n"
    summary += f"- Total Expense: ${total_expense:,.2f}\n"
    summary += f"- highest Expense: ${-highest_expense['transaction_amount']:,.2f} on {highest_expense['date'].date()} ({highest_expense['description']})\n"
    summary += f"- lowest Expense: ${-lowest_expense['transaction_amount']:,.2f} on {lowest_expense['date'].date()} ({lowest_expense['description']})\n"
    if months_span > 1:
        summary += f"- Average Monthly Expense: ${avg_expense:,.2f}\n"

    summary += f"\n**Transfer Overview**\n"
    summary += f"- Total Transfer: ${total_transfer:,.2f}\n"
    summary += f"- highest Transfer: ${-highest_transfer['transaction_amount']:,.2f} on {highest_transfer['date'].date()} ({highest_transfer['description']})\n"
    summary += f"- lowest Transfer: ${-lowest_transfer['transaction_amount']:,.2f} on {lowest_transfer['date'].date()} ({lowest_transfer['description']})\n"
    if months_span > 1:
        summary += f"- Average Monthly Transfer: ${avg_transfer:,.2f}\n"


    return {
        "summary": summary,
        "income_transactions": df_income.to_dict(orient="records"),
        "expense_transactions": df_expense.to_dict(orient="records"),
        "transfer_transactions": df_transfer.to_dict(orient="records")
    }

# TODO: Tool to check pending transfer
@tool
def check_pending_transfer(user_id: str):
    """
    Check pending transfers of the user.
    Args:
        user_id: user's id

    Returns:
        Information about user's pending transfers.
    """
    # Have the user's saving account first.
    conn = connect(banking_data_db)
    cursor = conn.cursor()
    cursor.execute("SELECT saving_account FROM user WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    if row is None:
        conn.close()
        cursor.close()
        return "No user found with this ID."
    saving_account = row[0]
    if saving_account is None:
        conn.close()
        cursor.close()
        return "The user has no saving account with the bank."

    # Have the pending transfers
    query = "SELECT * FROM pending_transfers WHERE sender_account = ?"
    df_transfers = pd.read_sql_query(query, conn, params=(saving_account,)).sort_values(
        "transfer_date").reset_index(drop=True)
    dict_transfers = df_transfers.to_dict(orient="records")
    cursor.close()
    conn.close()

    if len(dict_transfers) == 0:
        return "The user has no pending transfers."
    else:
        transfer_summary = "Below are the user's pending transfers:\n"
        total_pending_transfer = 0
        for item in dict_transfers:
            transfer_dt = datetime.strptime(item['transfer_date'][:10], "%Y-%m-%d")
            transfer_summary += (
                f"- ${item['transfer_amount']:.2f} to {item['recipient_account']} "
                f"at {item['recipient_bank']} on {transfer_dt.strftime('%A, %B %d, %Y')}.\n"
            )
            total_pending_transfer += item['transfer_amount']

        transfer_summary += f"Total pending transfer amount is ${total_pending_transfer:.2f}."

        return transfer_summary

# TODO: Tool to make a transfer
@tool
def transfer_fund(user_id: str, amount: float, recipient_account: str, recipient_bank: str, transfer_date: str):
    """
    Make a transfer from user's saving account to another account.
    To submit the transfer request successfully at the same day, the user must have sufficient fund in the saving account.
    And the transfer amount should be no more than $3000 per transaction.
    Args:
        user_id: user's id
        amount: the amount of money user would like to transfer, in dollar
        recipient_account: the amount number of the recipient
        recipient_bank: the bank of the recipient's account
        transfer_date: the date in which the user would like to perform this transfer

    Returns:
        The status of the transfer, and an update to the database if the transfer is successfully submitted.
    """
    # Gey the user's saving account first.
    conn = connect(banking_data_db)
    cursor = conn.cursor()
    cursor.execute("SELECT saving_account FROM user WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    if row is None:
        conn.close()
        cursor.close()
        return "No user found with this ID."
    saving_account = row[0]
    if saving_account is None:
        conn.close()
        cursor.close()
        return "The user has no saving account with the bank."

    # Check if the transfer date is valid.
    try:
        transfer_dt = datetime.strptime(transfer_date, "%Y-%m-%d").date()
    except ValueError:
        cursor.close()
        conn.close()
        return "The transfer date format is invalid. Please use 'YYYY-MM-DD'."
    today = datetime.today().date()
    if transfer_dt < today:
        cursor.close()
        conn.close()
        return "Transfers can only be scheduled for today or a future date. Kindly update the transfer date to proceed."

    # Check if the transfer amount is valid
    if amount > 3000:
        cursor.close()
        conn.close()
        return "The maximum allowable amount per transaction with the chatbot is $3,000. Please contact your relationship manager to adjust the limit or select other channel to submit the transfer."
    if amount < 0:
        cursor.close()
        conn.close()
        return "Please input an appropriate transfer amount."

    # Check if the remaining balance (excluding today's pending transfers) is sufficient (only for today's transfer)
    query = f"SELECT balance FROM {saving_account} where date = (SELECT MAX(date) FROM {saving_account})"
    cursor.execute(query)
    current_balance = cursor.fetchone()[0]

    # Have the pending transfers
    query = "SELECT * FROM pending_transfers WHERE sender_account = ?"
    df_transfers = pd.read_sql_query(query, conn, params=(saving_account,)).sort_values("transfer_date").reset_index(
        drop=True)
    dict_transfers = df_transfers.to_dict(orient="records")

    # Have today's sum of pending transfers
    if len(dict_transfers) > 0:
        today = datetime.today().date()
        today_pending_transfer = sum(item["transfer_amount"]
                                     for item in dict_transfers
                                     if datetime.strptime(item['transfer_date'][:10], "%Y-%m-%d").date() == today)
    else:
        today_pending_transfer = 0
    available_funds = current_balance - today_pending_transfer
    if transfer_dt == today and amount > available_funds:
        cursor.close()
        conn.close()
        return (
            f"Insufficient funds: your saving account does not currently hold enough balance to complete this transfer.\n"
            f"Available transferable amount today: ${available_funds:,.2f}.\n"
            "Please ensure adequate funds are available before proceeding."
        )
    # The transfer is OK to proceed
    else:
        cursor.execute(
            """
            INSERT INTO pending_transfers (date, sender_account, transfer_amount, recipient_account, recipient_bank, transfer_date)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (today.strftime("%Y-%m-%d %H:%M:%S"), saving_account, amount, recipient_account, recipient_bank, transfer_dt.strftime("%Y-%m-%d %H:%M:%S"))
        )
        conn.commit()
        cursor.close()
        conn.close()

        formatted_date = datetime.strptime(transfer_date, "%Y-%m-%d").strftime("%A, %B %d, %Y")
        confirmation_message = f"Your transfer of ${amount:,.2f} to account {recipient_account} at {recipient_bank} has been successfully scheduled for {formatted_date}."
        if transfer_dt > today:
            confirmation_message += " Kindly ensure that sufficient funds are available in your account on the scheduled transfer date."

        return confirmation_message