import re
import json
import requests
from langchain_groq import ChatGroq
from langchain.tools import Tool
from typing import List, Dict, Any, TypedDict
from langchain_core.messages import AIMessage, HumanMessage, BaseMessage, FunctionMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import create_react_agent
import os
from dotenv import load_dotenv
from datetime import datetime

# Add this class definition:
class ToolInvocation(TypedDict):
    id: str
    name: str
    arguments: str

load_dotenv()

# API Configuration
API_BASE_URL = "http://127.0.0.1:5000"
GROQ_API_KEY = os.getenv('GROQ_API_KEY')

# Initialize the LangChain compatible Groq model
llm = ChatGroq(
    model_name="llama3-8b-8192",
    temperature=0.2,
    api_key=GROQ_API_KEY
)

def parse_user_input(user_input: str) -> Dict[str, str]:
    """Extract date, time, duration, and description from user input."""
    # Extract date using regex
    date_match = re.search(
        r"(\d{1,2})(?:st|nd|rd|th)?\s+(january|february|march|april|may|june|july|august|september|october|november|december)\s+(\d{4})",
        user_input,
        re.IGNORECASE
    )
    
    if not date_match:
        return {"error": "Please provide a date in a valid format (e.g., '10th March 2025')."}
    
    day = int(date_match.group(1))
    month = date_match.group(2).lower()
    year = int(date_match.group(3))
    
    month_map = {
        "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
        "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12
    }
    
    month_num = month_map[month]
    
    # Extract time using regex
    time_match = re.search(
        r"(\d{1,2}):?(\d{2})?\s*(am|pm)?",
        user_input,
        re.IGNORECASE
    )
    
    if not time_match:
        return {"error": "Please provide a time in a valid format (e.g., '9 am' or '2:30 pm')."}
    
    hour = int(time_match.group(1))
    minute = int(time_match.group(2)) if time_match.group(2) else 0
    am_pm = time_match.group(3).lower() if time_match.group(3) else None
    
    # Convert to 24-hour format
    if am_pm:
        if am_pm == "pm" and hour < 12:
            hour += 12
        elif am_pm == "am" and hour == 12:
            hour = 0
    
    # Extract duration (default to 60 minutes if not specified)
    duration_match = re.search(r"for\s+(\d+)\s+minutes", user_input, re.IGNORECASE)
    duration = int(duration_match.group(1)) if duration_match else 60
    
    # Extract description
    description_match = re.search(r"(?:title|description|about|regarding|for)\s+[\"'](.+?)[\"']", user_input, re.IGNORECASE)
    if not description_match:
        description_match = re.search(r"(?:title|description|about|regarding|for)\s+(.+?)(?:\s+on\s+|\s+at\s+|$)", user_input, re.IGNORECASE)
    
    if not description_match:
        return {"error": "Please provide a description for the event."}
    
    description = description_match.group(1).strip()
    
    # Format date and time for the API
    date_time_str = f"{year:04d}-{month_num:02d}-{day:02d}T{hour:02d}:{minute:02d}"
    
    return {
        "start_time": date_time_str,
        "duration": str(duration),
        "description": description
    }

def validate_event_details(start_time: str, duration: str, description: str) -> Dict[str, str]:
    """Validate event details."""
    if not start_time:
        return {"error": "Start time is required."}
    if not duration:
        return {"error": "Duration is required."}
    if not description:
        return {"error": "Description is required."}
    return {"success": "Valid input."}

# Calendar Event API Functions
def get_events_by_date(date: str) -> Dict:
    """Retrieve events by date."""
    try:
        response = requests.get(f"{API_BASE_URL}/get-events-by-date", params={"date": date})
        return response.json()
    except Exception as e:
        return {"error": f"Failed to get events: {str(e)}"}

def get_events_by_datetime(datetime_str: str) -> Dict:
    """Retrieve events by date and time."""
    try:
        response = requests.get(f"{API_BASE_URL}/get-events-by-datetime", params={"datetime": datetime_str})
        return response.json()
    except Exception as e:
        return {"error": f"Failed to get events: {str(e)}"}

def create_event(event_details: str) -> Dict:
    """Create a new calendar event."""
    try:
        # Parse the event details from the string
        details = json.loads(event_details)
        start_time = details.get("start_time", "")
        duration = details.get("duration", "")
        description = details.get("description", "")
        
        # Validate input
        validation = validate_event_details(start_time, duration, description)
        if "error" in validation:
            return validation
        
        response = requests.post(
            f"{API_BASE_URL}/add", 
            json={"start_time": start_time, "duration": duration, "description": description}
        )
        return response.json()
    except json.JSONDecodeError:
        return {"error": "Invalid JSON format for event details."}
    except Exception as e:
        return {"error": f"Failed to create event: {str(e)}"}

def update_event(update_details: str) -> Dict:
    """Update an existing calendar event."""
    try:
        details = json.loads(update_details)
        old_start_time = details.get("old_start_time", "")
        new_start_time = details.get("new_start_time", "")
        duration = details.get("duration", "")
        description = details.get("description", "")
        
        if not all([old_start_time, new_start_time, duration, description]):
            return {"error": "Missing required fields for update"}
        
        response = requests.put(
            f"{API_BASE_URL}/update-event", 
            json={
                "old_start_time": old_start_time,
                "new_start_time": new_start_time,
                "duration": duration,
                "description": description
            }
        )
        return response.json()
    except json.JSONDecodeError:
        return {"error": "Invalid JSON format for update details"}
    except Exception as e:
        return {"error": f"Failed to update event: {str(e)}"}

def delete_event(event_details: str) -> Dict:
    """Delete an existing calendar event."""
    try:
        details = json.loads(event_details)
        start_time = details.get("start_time", "")
        duration = details.get("duration", "")
        description = details.get("description", "")
        
        if not all([start_time, duration, description]):
            return {"error": "Missing required fields for deletion"}
        
        response = requests.delete(
            f"{API_BASE_URL}/delete", 
            json={"start_time": start_time, "duration": duration, "description": description}
        )
        return response.json()
    except json.JSONDecodeError:
        return {"error": "Invalid JSON format for event details"}
    except Exception as e:
        return {"error": f"Failed to delete event: {str(e)}"}

def check_availability(availability_details: str) -> Dict:
    """Check available time slots for a given date and time."""
    try:
        details = json.loads(availability_details)
        datetime_str = details.get("datetime", "")
        duration = details.get("duration", "60")  # Default to 60 minutes
        
        if not datetime_str:
            return {"error": "Datetime is required."}
        
        response = requests.get(
            f"{API_BASE_URL}/check-availability", 
            params={"datetime": datetime_str, "duration": duration}
        )
        return response.json()
    except json.JSONDecodeError:
        return {"error": "Invalid JSON format for availability details"}
    except Exception as e:
        return {"error": f"Failed to check availability: {str(e)}"}

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
        description="Retrieve events by date and time. Input format: YYYY-MM-DDTHH:MM"
    ),
    Tool(
        name="create_event",
        func=create_event,
        description="Create a new calendar event. Input format: JSON string with start_time, duration, and description. Example: '{\"start_time\": \"2025-03-10T14:30\", \"duration\": \"60\", \"description\": \"Meeting\"}'"
    ),
    Tool(
        name="update_event",
        func=update_event,
        description="Update an existing calendar event. Input format: JSON string with old_start_time, new_start_time, duration, and description. Example: '{\"old_start_time\": \"2025-03-10T14:30\", \"new_start_time\": \"2025-03-11T15:00\", \"duration\": \"60\", \"description\": \"Updated Meeting\"}'"
    ),
    Tool(
        name="delete_event",
        func=delete_event,
        description="Delete an existing calendar event. Input format: JSON string with start_time, duration, and description. Example: '{\"start_time\": \"2025-03-10T14:30\", \"duration\": \"60\", \"description\": \"Meeting\"}'"
    ),
    Tool(
        name="check_availability",
        func=check_availability,
        description="Check if a time slot is available. Input format: JSON string with datetime and duration. Example: '{\"datetime\": \"2025-03-10T14:30\", \"duration\": \"60\"}'"
    ),
]

# Create the system prompt
system_prompt = """You are a helpful calendar assistant that can help users manage their events. 
You can retrieve, create, update, and delete calendar events.

For creating, updating, or deleting events, make sure to format the data as a proper JSON string.

When retrieving events, make sure to specify the date in YYYY-MM-DD format.
When retrieving events by date and time, provide the date and time as 'YYYY-MM-DDTHH:MM'.

Important Calendar API details:
- Date format: YYYY-MM-DD
- Datetime format: YYYY-MM-DDTHH:MM
- Event creation requires start_time, duration (in minutes), and description
- Check availability requires datetime and duration (in minutes)

Always follow up with the user to see if they need any additional help with their calendar.
"""

# Create the chat prompt with system message
prompt = ChatPromptTemplate.from_messages(
    [
        ("system", system_prompt),
        MessagesPlaceholder(variable_name="messages"),
    ]
)

# Using create_react_agent from langgraph.prebuilt with prompt that includes system message
agent_executor = create_react_agent(llm, tools, prompt=prompt)

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

def process_natural_language_input(user_input: str) -> Dict:
    """Process natural language input to create an event."""
    # Parse user input
    parsed_input = parse_user_input(user_input)
    if "error" in parsed_input:
        return parsed_input
    
    # Validate event details
    validation = validate_event_details(
        parsed_input["start_time"], 
        parsed_input["duration"], 
        parsed_input["description"]
    )
    if "error" in validation:
        return validation
    
    # Create the event
    event_details = json.dumps(parsed_input)
    return create_event(event_details)

def chatbot():
    print("Welcome to your Calendar Assistant! How can I help you manage your events today?")
    
    # Initialize the state with an empty messages list
    state = {
        "messages": [],
        "tool_calls": [],
        "tool_results": []
    }
    
    while True:
        user_input = input("\nYou: ")
        if user_input.lower() in ["exit", "quit"]:
            print("Goodbye!")
            break
        
        # Check if this is a natural language request to create an event
        if re.search(r"(create|add|schedule|book|set up) .+ (on|for) .+", user_input, re.IGNORECASE):
            try:
                result = process_natural_language_input(user_input)
                if "error" in result:
                    print(f"Bot: I'm having trouble understanding your request. {result['error']}")
                else:
                    print(f"Bot: Event created successfully! {result.get('message', '')}")
                continue
            except Exception as e:
                # Fall back to LLM handling if natural language parsing fails
                print(f"Bot: I'll help you with that request.")
        
        # Add the user's message to the state
        state["messages"].append(HumanMessage(content=user_input))
        
        # Create a copy of the state to avoid modifying the original
        current_state = dict(state)
        
        # Run the graph with the current state
        final_state = None
        for output in graph.stream(current_state):
            final_state = output
        
        # Update the state with the final output if it exists
        if final_state:
            state = final_state
        
        # Extract the agent's response
        if state["messages"] and isinstance(state["messages"][-1], AIMessage):
            agent_response = state["messages"][-1]
            print(f"Bot: {agent_response.content}")
        else:
            print("Bot: I'm having trouble understanding. Could you please try rephrasing your request?")

if __name__ == "__main__":
    chatbot()