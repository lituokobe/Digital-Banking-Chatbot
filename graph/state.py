from typing import TypedDict, Annotated, Literal, Optional, List, Dict, Any
from langchain_core.messages import AnyMessage
from langgraph.graph import add_messages
def update_dialog_stack(left: list[str], right: Optional[str]) -> list[str]:
    """
    Update dialog stack
    :param left: current state dict
    :param right: new state or action to add to the stack. If non, no action;
                  if 'pop', pop up the top (last one) of the stack.
    :return: new state dict with updated dialog stack
    """
    if right is None:
        return left
    elif right == "pop":
        return left[:-1]
    else:
        return left + [right]

#class of state
class State(TypedDict):
    """
    Define the structure of state dict
    :param
    messages: list of messages
    user_info: user information
    dialog_state: agent that is the current dialog
    """
    messages: Annotated[list[AnyMessage], add_messages]
    user_info: List[Dict[str, Any]]
    dialog_state: Annotated[
        list[Literal[
            "primary_assistant",
            "trading_assistant",
            "account_assistant",
            "DB_usage_assistant"
        ]],
        update_dialog_stack
    ]