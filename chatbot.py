import datetime
import requests
import google.generativeai as genai
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.tools import Tool
from typing import List, Dict, Any, TypedDict, Annotated, Sequence, Literal, Optional
from langchain_core.messages import AIMessage, HumanMessage, BaseMessage, FunctionMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import create_react_agent
from typing import TypedDict, List, Dict, Any
import operator
import json
import os
from dotenv import load_dotenv

# Add this class definition:
class ToolInvocation(TypedDict):
    id: str
    name: str
    arguments: str

load_dotenv()

# API Configuration
API_BASE_URL = "http://127.0.0.1:5000"
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Configure Gemini
genai.configure(api_key=GEMINI_API_KEY)

# Initialize the LangChain compatible Gemini model
llm = ChatGoogleGenerativeAI(
    model="gemini-1.5-flash",
    temperature=0.2,
    google_api_key=GEMINI_API_KEY,
    convert_system_message_to_human=False  # Using this parameter to avoid deprecation warning
)

# Calendar Event API Functions
def get_events_by_date(date: str) -> Dict:
    """Retrieve events by date."""
    try:
        response = requests.get(f"{API_BASE_URL}/get-events", params={"date": date})
        return response.json()
    except Exception as e:
        return {"error": f"Failed to get events: {str(e)}"}

def get_events_by_datetime(date_time: str) -> Dict:
    """Retrieve events by date and time."""
    try:
        parts = date_time.split(" ", 1)
        if len(parts) != 2:
            return {"error": "Please provide both date and time in format 'YYYY-MM-DD HH:MM'"}
        date, time = parts
        response = requests.get(f"{API_BASE_URL}/get-events", params={"date": date, "time": time})
        return response.json()
    except Exception as e:
        return {"error": f"Failed to get events: {str(e)}"}

def create_event(event_details: str) -> Dict:
    """Create a new calendar event."""
    try:
        # Parse the event details from the string
        details = json.loads(event_details)
        title = details.get("title", "")
        date = details.get("date", "")
        time = details.get("time", "")
        
        if not all([title, date, time]):
            return {"error": "Missing required fields: title, date, or time"}
        
        response = requests.post(
            f"{API_BASE_URL}/add-event", 
            json={"title": title, "date": date, "time": time}
        )
        return response.json()
    except json.JSONDecodeError:
        return {"error": "Invalid JSON format for event details"}
    except Exception as e:
        return {"error": f"Failed to create event: {str(e)}"}

def update_event(update_details: str) -> Dict:
    """Update an existing calendar event."""
    try:
        details = json.loads(update_details)
        old_date = details.get("old_date", "")
        old_time = details.get("old_time", "")
        new_title = details.get("new_title", "")
        new_date = details.get("new_date", "")
        new_time = details.get("new_time", "")
        
        if not all([old_date, old_time, new_title, new_date, new_time]):
            return {"error": "Missing required fields for update"}
        
        response = requests.put(
            f"{API_BASE_URL}/update-event", 
            json={
                "old_date": old_date,
                "old_time": old_time,
                "new_title": new_title,
                "new_date": new_date,
                "new_time": new_time
            }
        )
        return response.json()
    except json.JSONDecodeError:
        return {"error": "Invalid JSON format for update details"}
    except Exception as e:
        return {"error": f"Failed to update event: {str(e)}"}

# Define tools for LangGraph
tools = [
    Tool(
        name="get_events_by_date",
        func=get_events_by_date,
        description="Retrieve events by date. Input format: YYYY-MM-DD"
    ),
    Tool(
        name="get_events_by_datetime",
        func=get_events_by_datetime,
        description="Retrieve events by date and time. Input format: 'YYYY-MM-DD HH:MM'"
    ),
    Tool(
        name="create_event",
        func=create_event,
        description="Create a new calendar event. Input format: JSON string with title, date, and time. Example: '{\"title\": \"Meeting\", \"date\": \"2025-03-10\", \"time\": \"14:30\"}'"
    ),
    Tool(
        name="update_event",
        func=update_event,
        description="Update an existing calendar event. Input format: JSON string with old_date, old_time, new_title, new_date, and new_time. Example: '{\"old_date\": \"2025-03-10\", \"old_time\": \"14:30\", \"new_title\": \"Updated Meeting\", \"new_date\": \"2025-03-11\", \"new_time\": \"15:00\"}'"
    ),
]

# Create the system prompt
system_prompt = """You are a helpful calendar assistant that can help users manage their events. 
You can retrieve, create, and update calendar events.

For creating or updating events, make sure to format the data as a proper JSON string.

When retrieving events, make sure to specify the date in YYYY-MM-DD format.
When retrieving events by date and time, provide the date and time as 'YYYY-MM-DD HH:MM'.

Always follow up with the user to see if they need any additional help with their calendar.
"""

# Using create_react_agent from langgraph.prebuilt
agent_executor = create_react_agent(llm, tools)

# Define state type for the graph
class AgentState(TypedDict):
    messages: List[BaseMessage]
    tool_calls: List[ToolInvocation]
    tool_results: List[Dict[str, Any]]

# Define the state graph
def build_graph():
    # Create a new graph
    workflow = StateGraph(AgentState)
    
    # Define the agent node
    workflow.add_node("agent", agent_executor)
    
    # Add an edge from agent back to itself if there are tool calls to make
    workflow.add_conditional_edges(
        "agent",
        lambda state: "tool" if state.get("tool_calls") else "end",
        {
            "tool": "tool_execution",
            "end": END,
        }
    )
    
    # Define the tool execution node
    def execute_tools(state):
        tool_calls = state["tool_calls"]
        results = []
        
        for tool_call in tool_calls:
            tool_name = tool_call["name"]
            tool_args = tool_call["arguments"]
            
            # Find the tool and execute it
            for tool in tools:
                if tool.name == tool_name:
                    try:
                        result = tool.func(tool_args)
                        results.append({
                            "tool_call_id": tool_call["id"],
                            "name": tool_name,
                            "content": result
                        })
                    except Exception as e:
                        results.append({
                            "tool_call_id": tool_call["id"],
                            "name": tool_name,
                            "content": {"error": f"Error executing {tool_name}: {str(e)}"}
                        })
        
        # Clear the tool calls since we've executed them
        return {"tool_calls": [], "tool_results": results}
    
    workflow.add_node("tool_execution", execute_tools)
    
    # Map the results back to the agent
    def map_tool_results(state):
        messages = state["messages"].copy()
        for result in state["tool_results"]:
            messages.append(
                FunctionMessage(
                    content=json.dumps(result["content"]),
                    name=result["name"]
                )
            )
        return {"messages": messages, "tool_results": []}
    
    workflow.add_node("tool_result_mapper", map_tool_results)
    
    # Connect tool execution to the mapper and the mapper to the agent
    workflow.add_edge("tool_execution", "tool_result_mapper")
    workflow.add_edge("tool_result_mapper", "agent")
    
    # Set the entry point
    workflow.set_entry_point("agent")
    
    return workflow.compile()

# Build the graph
graph = build_graph()

def chatbot():
    print("Welcome! How can I assist with your calendar events?")
    messages = []
    
    while True:
        user_input = input("\nYou: ")
        if user_input.lower() in ["exit", "quit"]:
            print("Goodbye!")
            break
        
        # Add user message to state
        messages.append(HumanMessage(content=user_input))
        
        # Initialize the state with the messages
        state = {"messages": messages, "tool_calls": [], "tool_results": []}
        
        # Execute the graph
        result = graph.invoke(state)
        
        # Update messages from result
        messages = result["messages"]
        
        # Print the agent's response (last AIMessage)
        for message in reversed(messages):
            if isinstance(message, AIMessage):
                print(f"Bot: {message.content}")
                break

if __name__ == "__main__":
    chatbot()