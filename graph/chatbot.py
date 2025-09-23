import uuid
from typing import List, Dict
import gradio as gr
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

# Add memory saver and compile the graph
memory = MemorySaver()
graph = builder.compile(
    checkpointer=memory,
    interrupt_before = [
        "trading_assistant_sensitive_tools",
        "account_assistant_sensitive_tools"
    ]
)

# Preparation before launching: initialize session_id and refresh database
session_id = str(uuid.uuid4())
create_db_update_date(banking_data_excel, banking_data_db)

# Set up config
"""
4 client personas are available in config:
- Luis Zhang (ID: AB123) -  A young working professional with an active lifestyle and diverse personal interests. 
  His investment portfolio is primarily concentrated in technology sector equities.

- Jun-hao Mariano (ID: PB367) A university student balancing academics with a part-time job. 
  His investment approach focuses exclusively on securities issued by well-established, reputable brands.

- Satsuki Ukeja (ID: AB892) A retiree devoted to family life and reliant on pension income.
  Her financial strategy emphasizes stability, with investments exclusively in index funds.

- John Petrov (ID: PB519) A middle-aged blue-collar worker who prefers to keep his finances simple.
  He has no active interest in investment products and maintains a straightforward banking profile.
"""
config = {
    "configurable": {
        "user_id": "AB123",
        # "user_id": "PB367",
        # "user_id": "PB519",
        # "user_id": "AB892",
        "thread_id": session_id,
    }
}

# # TODO: Chatbot in terminal
# _printed = set() #initiate a set, to avoid duplicate printing
#
# #execute flow
# while True:
#     question = input("User: ")
#     if question.lower() in ["quit", "exit"]:
#         print("Thank you for banking with us. Wish you have a good day!")
#         break
#     else:
#         events = graph.stream({"messages": ("user", question)}, config, stream_mode = "values")
#         #print messages
#         for event in events:
#             _print_event(event, _printed)
#
#         current_state = graph.get_state(config)
#         if current_state.next:
#             # Create custom messages for different nodes before interruption
#             approval_messages = {
#                 "trading_assistant_sensitive_tools": (
#                     "To proceed with placing this trade order, please confirm that you have read and agree to the Bank’s and the Stock Exchange’s terms and conditions.\n"
#                     "Enter 'y' to provide your consent and continue with the order submission.\n"
#                     "Note: Providing consent authorizes the request but does not guarantee that the trade will be executed successfully."
#                 ),
#                 "account_assistant_sensitive_tools": (
#                     "To proceed with this fund transfer request, please confirm that you have read and agree to the Bank’s terms and conditions.\n"
#                     "Enter 'y' to provide your consent and continue with the submission.\n"
#                     "Note: Providing consent authorizes the request but does not guarantee that the transfer will be completed successfully."
#                 ),
#             }
#             # Get the next node name
#             next_node = current_state.next[0]
#             # Use custom message if available, fallback to default
#             interruption_message = approval_messages.get(
#                 next_node,
#                 "Do you approve the above operation? Input 'y' to continue, otherwise specify your requests.\n"
#             )
#             user_input = input(interruption_message)
#             if user_input.strip().lower() == "y":
#                 #continue
#                 events = graph.stream(None, config, stream_mode="values")
#                 # print messages
#                 for event in events:
#                     _print_event(event, _printed)
#             else:
#                 result = graph.stream(
#                     {
#                         "messages":[
#                             ToolMessage(
#                                 tool_call_id=event["messages"][-1].tool_calls[0]["id"],
#                                 name="rejection_handler",  # Add tool name explicitly
#                                 content=f"User rejected the tool call, reason is '{user_input}'.",
#                             )
#                         ]
#                     },
#                     config,
#                 )
#                 # print messages
#                 for event in events:
#                     _print_event(event, _printed)

# TODO: Chatbot in GUI by gradio
config["configurable"]["terminated"] = False
def do_graph(user_input, chat_bot):
    """
    function to execute after input is submitted
    """
    if user_input:
        chat_bot.append({'role':'user', 'content': user_input})
    return '', chat_bot

def execute_graph(chat_bot: List[Dict]) -> List[Dict]:
    """
    function to execute the workflow
    """
    # Skip execution if terminated
    if config["configurable"].get("terminated"):
        return chat_bot

    user_input = chat_bot[-1]['content']
    result = '' #AI assistant last message

    if user_input.strip().lower() !='y': #regular user question
        events = graph.stream({"messages": ("user", user_input)}, config, stream_mode = "values")
    else: # user inputs 'y':
        events = graph.stream(None, config, stream_mode="values")

    for event in events:
        messages = event.get("messages")
        if messages:
            if isinstance(messages, list):
                message = messages[-1]
            if message.__class__.__name__ == "AIMessage":
                if message.content:
                    result = message.content #messages that needs to display in web UI
            msg_repr = message.pretty_repr(html = True)
            if len(msg_repr) > 1500:
                msg_repr = msg_repr[:1500] + "... and more."
            print(msg_repr)

    current_state = graph.get_state(config)
    if current_state.next: #interruption happens
        # Create custom messages for different nodes before interruption
        approval_messages = {
            "trading_assistant_sensitive_tools": (
                "To proceed with placing this trade order, please confirm that you have read and agree to the Bank’s and the Stock Exchange’s terms and conditions.\n"
                "Enter 'y' to provide your consent and continue with the order submission.\n"
                "Note: Providing consent authorizes the request but does not guarantee that the trade will be executed successfully."
            ),
            "account_assistant_sensitive_tools": (
                "To proceed with this fund transfer request, please confirm that you have read and agree to the Bank’s terms and conditions.\n"
                "Enter 'y' to provide your consent and continue with the submission.\n"
                "Note: Providing consent authorizes the request but does not guarantee that the transfer will be completed successfully."
            ),
        }
        # Get the next node name
        next_node = current_state.next[0]
        # Use custom message if available, fallback to default
        result = approval_messages.get(
            next_node,
            "Do you approve the above operation? Input 'y' to continue, otherwise specify your requests.\n"
        )

    chat_bot.append({'role':'assistant', 'content': result})

    return chat_bot


# Build a GUI with gradio
css = """
#bgc {background-color: #8FEFA3}.feedback textarea {font-size: 24px !important}

#quit-btn {margin-left: auto; width: auto !important;}
"""
with (gr.Blocks(title='Digital Banking Assistant', css=css) as instance): #set up the page title with css, we have an HTML page
    gr.Label('Digital Banking Assistant', container=False) #header of the page

    chatbot = gr.Chatbot(type='messages', height=350, label = 'AI Assistant') #chatbot widget

    input_textbox = gr.Textbox(label='Please input your question.📝', value='') #input box

    input_textbox.submit(do_graph,
                         [input_textbox, chatbot],
                         [input_textbox, chatbot]
                         ).then(execute_graph, chatbot, chatbot)

    with gr.Row():
        gr.Column(scale=1)  # empty spacer column
        with gr.Column(scale=0):  # button column, won't stretch
            quit_button = gr.Button("End the chat", elem_id="quit-btn")
    def quit_chat(chat_bot):
        config["configurable"]["terminated"] = True
        chat_bot.append({
            'role': 'user',
            'content': 'End the chat'
        })
        chat_bot.append({
            'role': 'assistant',
            'content':"Thank you for using the Digital Banking Assistant. Wish you have a good day!"
        })
        return chat_bot

    quit_button.click(quit_chat, chatbot, chatbot)

if __name__=='__main__':
    #launch the gradio app
    instance.launch(debug=True)