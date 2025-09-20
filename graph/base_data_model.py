from pydantic import BaseModel, Field

class CompleteOrEscalate(BaseModel):  # define the data model class
    """
    A tool used to mark the current task as completed and/or hand over the control of the conversation to the primary assistant,
    allowing the primary assistant to reroute the conversation based on user needs.
    """
    cancel: bool = True  # cancel the task by default
    reason: str  # reason of cancelling or escalation

    class Config:  # Inner class Config: json_schema_extra: this includes some example data
        json_schema_extra = {
            "example": {
                "cancel": True,
                "reason": "User has changed mind on current task.",
            },
            "example2": {
                "cancel": True,
                "reason": "I have complete the task",
            },
            "example3": {
                "cancel": False,
                "reason": "I need to ask for more information from the user to complete the task.",
            },
        }

class ToTradingAssistant(BaseModel):
    """
    Delegate following task to Trading Assistant who specialized in trading:
    1. check the market price of a stock and analyse it to see if it is worth investing
    2. check the earnings of a trading account
    3. check cash balance of the trading account
    4. check the pending orders
    5. place a buy order for a stock
    6. place a sell order for stock
    """
    user_id: str = Field(description="User's id")
    action: str = Field(description = "The action that the user wants to take, including search_stock, check_earnings, check_pending_order, trade_stock")
    request: str = Field(description = "The request that the user wants to make to the trading assistant")

    class Config:
        json_schema_extra = {
            "Example": {
                "user_id" : "AB123",
                "action": "trade_stock",
                "request": "Can I buy 1000 shares of Alibaba at $400?",
            }
        }

class ToAccountAssistant(BaseModel):
    """
    Delegate following task to Account Assistant who specialized in saving account management:
    1. check the balance of the savings account
    2. check the transaction history of the savings account
    4. check pending transfers
    5. make a transfer to another account
    """
    user_id: str = Field(description="User's id")
    action: str = Field(
        description="The action that the user wants to take, including 'check_balance', 'check_transaction', 'check_pending_transfer', 'transfer_fund'")
    request: str = Field(description="The request that the user wants to make to the Account Assistant")

    class Config:
        json_schema_extra = {
            "Example": {
                "user_id": "AC234",
                "action": "transfer_fund",
                "request": "I want to transfer $80000 to U80934825 at ABC Bank.",
            }
        }

class ToDBUsageAssistant(BaseModel):
    """
        Delegate following task to DB Usage Assistant who specialized in answering Digital Banking usage questions:
        1.banking documents on digital banking
        2.customize the home screen
        3.trading on digital banking
        4.security on digital banking
        5.notifications on digital banking
        6.any other topics related to digital banking (web or app)
        The digital banking include both E-Banking (web version) and Mobile Banking (mobile app version).
        So, if the user ask any questions about these 2 channels of the bank, also delegate the question to DB Usage Assistant.
    """
    request: str = Field(description="The request that the user wants to make to the DB Usage Assistant")

    class Config:
        json_schema_extra = {
            "Example": {
                "request": "Where to download banking documents on the bank's app?",
            }
        }