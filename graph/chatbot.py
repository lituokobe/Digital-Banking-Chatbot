import uuid
from langgraph.checkpoint.memory import MemorySaver
from langgraph.constants import START, END
from langgraph.graph import StateGraph
from langgraph.prebuilt import tools_condition
from graph.assistant import BankingAssistant, primary_assistant_runnable, primary_assistant_tools
from graph.base_data_model import ToTradingAssistant, ToAccountAssistant, ToDBUsageAssistant
from graph.build_child_graph import build_trading_graph, build_account_graph, build_DB_usage_graph
from tools import banking_data_excel, banking_data_db
from tools.init_db import create_db_update_date
from tools.primary_assistant_tools import fetch_user_information
from graph.state import State
from tools.tools_handler import create_tool_node_with_fallback, _print_event

# Initiate the graph
builder = StateGraph(State)
def get_user_info(state: State):
    """
    Get client's bank account information and update state dictionary
    :param state: current state dict
    :return: new state dict including client info
    """
    return {"user_info":fetch_user_information.invoke({})}

#fetch_user_info is executed first, meaning we can get user's information before doing anything
builder.add_node('fetch_user_info', get_user_info)
#add edges
builder.add_edge(START, 'fetch_user_info')

# add child graphs
builder = build_trading_graph(builder)
builder = build_account_graph(builder)
builder = build_DB_usage_graph(builder)

#add primary assistant
builder.add_node('primary_assistant', BankingAssistant(primary_assistant_runnable))
builder.add_node('primary_assistant_tools', create_tool_node_with_fallback(primary_assistant_tools))

# route for primary assistant
def route_primary_assistant(state: State):
    """
    Based on current state, decide which child assistant node to route to.
    :param state: dictionary of current dialog state
    :return: node name of the next step
    """
    route = tools_condition(state)  # decide next step
    if route == END:
        return END
    tool_calls = state["messages"][-1].tool_calls # get the tool call in the last message
    if tool_calls:
        if tool_calls[0]["name"] == ToTradingAssistant.__name__:
            return "enter_trading_assistant" # go to node of enter_trading_assistant
        elif tool_calls[0]["name"] == ToAccountAssistant.__name__:
            return "enter_account_assistant" # go to node of enter_account_assistant
        elif tool_calls[0]["name"] == ToDBUsageAssistant.__name__:
            return "enter_DB_usage_assistant" # go to node of enter_DB_usage_assistant
        return "primary_assistant_tools"
    raise ValueError("Invalid route") # If cannot find appropriate tool calls, raise an error

#add conditional edges
builder.add_conditional_edges(
    "primary_assistant",
    route_primary_assistant,
    [
        "enter_trading_assistant",
        "enter_account_assistant",
        "enter_DB_usage_assistant",
        "primary_assistant_tools",
        END,
    ]
)

builder.add_edge('primary_assistant_tools', 'primary_assistant')

def route_to_workflow(state: dict) -> str:
    """
    If we are in a state of being assigned, directly route to respective assistant.
    :param state: dictionary of current dialog state
    :return: the node name to go
    """
    dialog_state = state.get("dialog_state")
    if not dialog_state:
        return "primary_assistant"  # of no dialog state, return to main assistant
    return dialog_state[-1]  # otherwise return to the last assistant

builder.add_conditional_edges("fetch_user_info", route_to_workflow)  # route based on user info

memory = MemorySaver()
graph = builder.compile(
    checkpointer=memory,
)

session_id = str(uuid.uuid4())
create_db_update_date(banking_data_excel, banking_data_db)

config = {
    "configurable": {
        # "user_id": "PB367",
        "user_id": "AB123",
        # "user_id": "PB519",
        # "user_id": "AB892",
        #checkpointer is visited by thread_id
        "thread_id": session_id,
    }
}

_printed = set() #initiate a set, to avoid duplicate printing

#execute flow
while True:
    question = input("User: ")
    if question.lower() in ["quit", "exit"]:
        print("Thank you for banking with us. Wish you have a good day!")
        break
    else:
        events = graph.stream({"messages": ("user", question)}, config, stream_mode = "values")
        #print messages
        for event in events:
            _print_event(event, _printed)

        current_state = graph.get_state(config)
        if current_state.next:
            user_input = input(
                "Do you approve above operation? input 'y' to continue, otherwise specify your requests.\n"
            )
            if user_input.strip().lower() == "y":
                #continue
                events = graph.stream(None, config, stream_mode="values")
                # print messages
                for event in events:
                    _print_event(event, _printed)
            else:
                result = graph.stream(
                    {
                        "messages":[
                            ToolMessage(
                                tool_call_id=event["messages"][-1].tool_calls[0]["id"],
                                name="rejection_handler",  # Add tool name explicitly
                                content=f"User rejected the tool call, reason is '{user_input}'.",
                            )
                        ]
                    },
                    config,
                )
                # print messages
                for event in events:
                    _print_event(event, _printed)