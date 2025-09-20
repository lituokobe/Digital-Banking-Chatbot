from langchain_core.messages import ToolMessage
from langchain_core.runnables import RunnableLambda
from langgraph.prebuilt import ToolNode

def handle_tool_error(state) -> dict:
    """
    Handle tool error when calling tools.
    Parameters:
        state (dict): dictionary of current state, including error info and list of messages.
    Returns:
        dict: dictionary including error info and list of messages.
    """
    error = state.get("error")
    tool_calls = state["messages"][-1].tool_calls # get the tool calls of last message
    return {
        "messages" : [
            ToolMessage(
                content = f"Error: {repr(error)}\nPlease correct your error.",
                tool_call_id = tc["id"]
            )
            for tc in tool_calls
        ]
    }

def create_tool_node_with_fallback(tools: list) -> dict:
    """
    Create the tool node with fallback. When a tool executes with failure, use the fallback.
    Parameters:
        tools (list)
    Returns:
        dict: tool node with fallback
    """
    return ToolNode(tools).with_fallbacks(
        # Use handle_tool_error as fallback
        [RunnableLambda(handle_tool_error)], exception_key = "error"
    )

def _print_event(event: dict, _printed: set, max_length=1500):
    """
    print even info, especially for dialog state and message info. If the message is too long, it will be cut for readability.

    Parameters :
        event (dict): event dictionary, including dialog state and messages.
        _printed (set): set of the printed, to avoid duplicated prints.
        max_length (int): max length of message, will be cut if exceeding. 1500 by default.
    """
    current_state = event.get("dialog_state")
    if current_state:
        print("Current state: ", current_state[-1])  # print current state
    message = event.get("messages")
    if message:
        if isinstance(message, list):
            message = message[-1]  # if message is a list, get the last one
        if message.id not in _printed:
            msg_repr = message.pretty_repr(html=True)
            if len(msg_repr) > max_length:
                msg_repr = msg_repr[:max_length] + " ... (and more)"  # cut if exceeding the max length
            print(msg_repr)  # print
            _printed.add(message.id)  # add the printed message id to the set of the printed