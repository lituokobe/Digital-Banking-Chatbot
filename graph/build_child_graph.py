from langchain_core.messages import ToolMessage
from langgraph.constants import END
from langgraph.graph import StateGraph
from langgraph.prebuilt import tools_condition

from graph.assistant import BankingAssistant, trading_assistant_runnable, trading_assistant_tools, \
    account_assistant_runnable, account_assistant_tools, DB_usage_assistant_runnable, DB_usage_assistant_tools
from graph.base_data_model import CompleteOrEscalate
from graph.entry_node import create_entry_node
from tools.tools_handler import create_tool_node_with_fallback


def build_trading_graph(builder: StateGraph) -> StateGraph:
    """build child graph of trading assistant"""
    builder.add_node(
        "enter_trading_assistant",
        create_entry_node("Trading Assistant", "trading_assistant")
    )
    builder.add_node("trading_assistant", BankingAssistant(trading_assistant_runnable))
    builder.add_edge("enter_trading_assistant", "trading_assistant")

    builder.add_node(
        "trading_assistant_tools",
        create_tool_node_with_fallback(trading_assistant_tools)
    )
    def route_trading(state: dict):
        """
        trading process based on current state route

        :param state: dictionary of current dialog state
        :return: node name of next step
        """
        route = tools_condition(state)  # decide next step
        if route == END:
            return END
        tool_calls = state["messages"][-1].tool_calls  # check tool call of the last message
        did_cancel = any(tc["name"] == CompleteOrEscalate.__name__ for tc in tool_calls)  # check if CompleteOrEscalate is called
        if did_cancel:
            return "leave_skill"  # if user requests to cancel or exit, move to node of leave_skill
        # safe_toolnames = [t.name for t in book_car_rental_safe_tools]  # obtain all safe tool names
        # if all(tc["name"] in safe_toolnames for tc in tool_calls):  # if all tools called are safe tools
        #     return "book_car_rental_safe_tools"  # move to node of safe tools
        # return "book_car_rental_sensitive_tools"  # otherwise move to node of sensitive tools
        return "trading_assistant_tools"

    builder.add_edge("trading_assistant_tools", "trading_assistant")

    builder.add_conditional_edges(
        "trading_assistant",
        route_trading,
        ["trading_assistant_tools", "leave_skill", END]
    )

    # the node for exits of all child assistants
    def pop_dialog_state(state: dict) -> dict:
        """
        pop dislog state and return to main assistant
        this makes the full graph can clearly follow the dialog stream, assign the control to specific child graph based on needs
        :param state: dictionary of current dialog state
        :return: dictionary including new dialog state and messages
        """
        messages = []
        if state["messages"][-1].tool_calls:
            # note: currently we don't process scenario where LLM executes multiple tool calls concurrently
            messages.append(
                ToolMessage(
                    content="Pass the dialog to primary assistant. Please review the previous dialog and assist the user based on requirements.",
                    tool_call_id=state["messages"][-1].tool_calls[0]["id"],
                )
            )
        return {
            "dialog_state": "pop",  # update the dialog state as 'pop'
            "messages": messages,  # return to the message list
        }

    # add leave skill node and connect it back to main assistant
    builder.add_node("leave_skill", pop_dialog_state)
    builder.add_edge("leave_skill", "primary_assistant")

    return builder


def build_account_graph(builder: StateGraph) -> StateGraph:
    """build child graph of trading assistant"""
    builder.add_node(
        "enter_account_assistant",
        create_entry_node("Account Assistant", "account_assistant")
    )
    builder.add_node("account_assistant", BankingAssistant(account_assistant_runnable))
    builder.add_edge("enter_account_assistant", "account_assistant")

    builder.add_node(
        "account_assistant_tools",
        create_tool_node_with_fallback(account_assistant_tools)
    )

    def route_account(state: dict):
        """
        account management process based on current state route

        :param state: dictionary of current dialog state
        :return: node name of next step
        """
        route = tools_condition(state)  # decide next step
        if route == END:
            return END
        tool_calls = state["messages"][-1].tool_calls  # check tool call of the last message
        did_cancel = any(
            tc["name"] == CompleteOrEscalate.__name__ for tc in tool_calls)  # check if CompleteOrEscalate is called
        if did_cancel:
            return "leave_skill"  # if user requests to cancel or exit, move to node of leave_skill
        return "account_assistant_tools"

    builder.add_edge("account_assistant_tools", "account_assistant")

    builder.add_conditional_edges(
        "account_assistant",
        route_account,
        ["account_assistant_tools", "leave_skill", END]
    )

    return builder

def build_DB_usage_graph(builder: StateGraph) -> StateGraph:
    """build child graph of trading assistant"""
    builder.add_node(
        "enter_DB_usage_assistant",
        create_entry_node("DB Usage Assistant", "DB_usage_assistant")
    )
    builder.add_node("DB_usage_assistant", BankingAssistant(DB_usage_assistant_runnable))
    builder.add_edge("enter_DB_usage_assistant", "DB_usage_assistant")

    builder.add_node(
        "DB_usage_assistant_tools",
        create_tool_node_with_fallback(DB_usage_assistant_tools)
    )

    def route_DB_usage(state: dict):
        """
        solve Digital Banking usage problem based on current state route

        :param state: dictionary of current dialog state
        :return: node name of next step
        """
        route = tools_condition(state)  # decide next step
        if route == END:
            return END
        tool_calls = state["messages"][-1].tool_calls  # check tool call of the last message
        did_cancel = any(
            tc["name"] == CompleteOrEscalate.__name__ for tc in tool_calls)  # check if CompleteOrEscalate is called
        if did_cancel:
            return "leave_skill"  # if user requests to cancel or exit, move to node of leave_skill
        return "DB_usage_assistant_tools"

    builder.add_edge("DB_usage_assistant_tools", "DB_usage_assistant")

    builder.add_conditional_edges(
        "DB_usage_assistant",
        route_DB_usage,
        ["DB_usage_assistant_tools", "leave_skill", END]
    )

    return builder