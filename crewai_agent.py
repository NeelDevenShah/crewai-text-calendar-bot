import json
import requests
import os
import re
import sys
from typing import Dict, Any, List
from datetime import datetime, date
from dotenv import load_dotenv
from crewai import Agent, Crew, Task, Process, LLM
from crewai.tools import tool  # Import the Tool class
from langchain_google_genai import ChatGoogleGenerativeAI

load_dotenv()

# API Configuration
API_BASE_URL = "http://127.0.0.1:5000"
current_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
os.environ["GEMINI_API_KEY"] = GEMINI_API_KEY

# Initialize AI Model
llm_2 = ChatGoogleGenerativeAI(model="gemini-2.0-flash",
                             verbose = True,
                             temperature = 0.6,
                             google_api_key=GEMINI_API_KEY)
llm = LLM(model="gemini/gemini-2.0-flash")

# Conversation history storage
conversation_history = []

# 🛠 Utility: Extract JSON using Regex
def extract_json(text: str) -> Dict[str, Any]:
    """Extracts and fixes JSON format if needed."""
    json_match = re.search(r"\{.*\}", text, re.DOTALL)  # Find JSON block
    if json_match:
        json_text = json_match.group(0)  # Extract JSON
        try:
            return json.loads(json_text)  # Parse JSON
        except json.JSONDecodeError:
            return {"error": "Invalid JSON format extracted from AI response."}
    return {"error": "No valid JSON found in AI response."}

# Add entry to conversation history
def add_to_history(role: str, content: str, metadata: Dict = None):
    """
    Add an entry to the conversation history.
    
    Args:
        role: 'user' or 'assistant'
        content: The message content
        metadata: Optional additional data (like parsed intents, event details)
    """
    conversation_history.append({
        "role": role,
        "content": content,
        "timestamp": datetime.now().isoformat(),
        "metadata": metadata or {}
    })

# Get formatted conversation history for context
def get_conversation_context(max_entries: int = 5) -> str:
    """
    Returns the recent conversation history formatted for context.
    
    Args:
        max_entries: Maximum number of recent entries to include
    """
    recent_history = conversation_history[-max_entries:] if len(conversation_history) > 0 else []
    if not recent_history:
        return ""
    
    formatted_history = "Previous conversation:\n"
    for entry in recent_history:
        formatted_history += f"{entry['role'].capitalize()}: {entry['content']}\n"
    
    return formatted_history

# 🔥 AI-Powered Intent Classification
def classify_user_intent(user_input: str) -> Dict[str, Any]:
    """Use AI to classify intent and extract structured event data."""
    # Add conversation history for context
    context = get_conversation_context()
    
    prompt = f"""
    You are a calendar assistant. Identify the user's intent and extract:
    - "intent" (Make sure the intent is from the given example only) (e.g., "casual_chat", "create_event", "get_events", "check_availability", "update_event", "delete_event", "clarify_user_request")
    - "date_time" (ISO format: YYYY-MM-DDTHH:MM)
    - "duration" (in minutes, default 60 if unspecified)
    - "description" (Short summary of the event)
    - "old_date_time" (ISO format: YYYY-MM-DDTHH:MM) - Only for update_event intent
    - "reference_context" (any event or information referenced from previous conversation)

    If the user is just chatting (e.g., "Hey, how are you?"), return:
    {{
      "intent": "casual_chat",
      "message": "Friendly response"
    }}

    Return a valid JSON object. Example:
    {{
      "intent": "create_event",
      "date_time": "2025-03-10T14:30",
      "duration": "60",
      "description": "Meeting with John"
    }}

    {context}
    User Query: {user_input}
    """

    response = llm_2.invoke(prompt)
    raw_text = response.content if hasattr(response, "content") else str(response)

    # Extract and validate JSON
    parsed_json = extract_json(raw_text)
    
    print('----------')
    print(parsed_json)
    print(parsed_json['intent'])
    print('----------')
    
    # If casual chat, just return the AI-generated message
    if parsed_json.get("intent") == "casual_chat":
        print('***BYE1')
        return {"casual_chat": True, "message": parsed_json.get("message", "I'm here to help!")}

    # Ensure all required fields exist, fixing missing values
    fixed_json = {
        "intent": parsed_json.get("intent", "unknown"),
        "date_time": parsed_json.get("date_time", datetime.now().isoformat()),  # Default: now
        "duration": str(parsed_json.get("duration", "60")),  # Default: 60 minutes
        "description": parsed_json.get("description", "No description provided"),
        "reference_context": parsed_json.get("reference_context", "")
    }
    
    # Add old_date_time for update events if it exists
    if parsed_json.get("old_date_time"):
        fixed_json["old_date_time"] = parsed_json.get("old_date_time")
    
    print('***BYE')
    return fixed_json if fixed_json["intent"] != "unknown" else {"error": "Could not understand the request."}

# Find referenced event in history
def find_referenced_event() -> Dict:
    """
    Search conversation history for the most recent event details.
    Returns event details if found, empty dict otherwise.
    """
    for entry in reversed(conversation_history):
        metadata = entry.get("metadata", {})
        # Check if this entry contains event details
        if "intent" in metadata and metadata["intent"] in ["create_event", "update_event", "get_events"]:
            if "event_details" in metadata:
                return metadata["event_details"]
    return {}

@tool('create_event_tool')
def create_event_tool(date_time: str, duration: str, description: str) -> Dict:
    """Create a calendar event."""
    print('Enter the tool of the create calendar event')
    try:
        # Extract specific details from event_details
        event_data = {
            "start_time": date_time,
            "duration": duration,
            "description": description
        }
        response = requests.post(f"{API_BASE_URL}/add", json=event_data)
        response_data = response.json()
        if response_data.get("success") == True:
            return {"success": True, "message": response_data.get("message", "Event created successfully")}
        else:
            return {"success": False, "error": response_data.get("error", "Unknown error")}
    except Exception as e:
        return {"success": False, "error": f"Failed to create event: {str(e)}"}

@tool('get_events_tool')
def get_events_tool(date: str) -> Dict:
    """Retrieve events for a given date."""
    print('Enter the tool of the get events')
    try:
        # Format the date to YYYY-MM-DD if it contains a time component
        if "T" in date:
            date = date.split("T")[0]
            
        response = requests.get(f"{API_BASE_URL}/get-events-by-date", params={"date": date})
        response_data = response.json()
        if response_data.get("success") == True:
            return {"success": True, "data": response_data}
        else:
            return {"success": False, "error": response_data.get("error", "Unknown error")}
    except Exception as e:
        return {"success": False, "error": f"Failed to fetch events: {str(e)}"}

@tool('check_availability_tool')
def check_availability_tool(date_time: str, duration: str) -> Dict:
    """Check if a specific time slot is available."""
    print('Enter the tool of the check availability')
    try:
        response = requests.get(
            f"{API_BASE_URL}/check-specific-availability", 
            params={"datetime": date_time, "duration": duration}
        )
        response_data = response.json()
        if response_data.get("success") == True:
            return {"success": True, "available": response_data.get("available"), "reason": response_data.get("reason")}
        else:
            return {"success": False, "error": response_data.get("error", "Unknown error")}
    except Exception as e:
        return {"success": False, "error": f"Failed to check availability: {str(e)}"}

@tool('get_available_slots_tool')
def get_available_slots_tool(date: str, duration: str) -> Dict:
    """Get all available time slots for a given date and duration."""
    print('Enter the tool of the get available slots')
    try:
        # Format the date to YYYY-MM-DD if it contains a time component
        if "T" in date:
            date = date.split("T")[0]
            
        response = requests.get(
            f"{API_BASE_URL}/available-slots", 
            params={"date": date, "duration": duration}
        )
        response_data = response.json()
        if response_data.get("success") == True:
            return {"success": True, "data": response_data}
        else:
            return {"success": False, "error": response_data.get("error", "Unknown error")}
    except Exception as e:
        return {"success": False, "error": f"Failed to get available slots: {str(e)}"}

@tool('update_event_tool')
def update_event_tool(old_date_time: str, new_date_time: str, duration: str, description: str) -> Dict:
    """Update an existing calendar event."""
    print('Enter the tool of the update event')
    try:
        event_data = {
            "old_start_time": old_date_time,
            "new_start_time": new_date_time,
            "duration": duration,
            "description": description
        }
        response = requests.put(f"{API_BASE_URL}/update-event", json=event_data)
        response_data = response.json()
        if response_data.get("success") == True:
            return {"success": True, "message": response_data.get("message", "Event updated successfully")}
        else:
            return {"success": False, "error": response_data.get("error", "Unknown error")}
    except Exception as e:
        return {"success": False, "error": f"Failed to update event: {str(e)}"}

@tool('delete_event_tool')
def delete_event_tool(date_time: str, duration: str) -> Dict:
    """Delete a calendar event."""
    print('Enter the tool of the delete event')
    try:
        event_data = {
            "start_time": date_time,
            "duration": duration
        }
        response = requests.delete(f"{API_BASE_URL}/delete", json=event_data)
        response_data = response.json()
        if response_data.get("success") == True:
            return {"success": True, "message": response_data.get("message", "Event deleted successfully")}
        else:
            return {"success": False, "error": response_data.get("error", "Unknown error")}
    except Exception as e:
        return {"success": False, "error": f"Failed to delete event: {str(e)}"}

# 📌 CrewAI Agent with tools
calendar_agent = Agent(
    role="Calendar Assistant",
    goal="Help users manage their calendar seamlessly",
    backstory="You're an AI-powered calendar manager that schedules, updates, retrieves, and manages events.",
    verbose=True,
    allow_delegation=False,
    llm=llm,
    tools=[create_event_tool, get_events_tool, check_availability_tool, 
           get_available_slots_tool, update_event_tool, delete_event_tool]
)

# 📝 Dynamically Create CrewAI Tasks
def create_calendar_task(user_input):
    """Generate a CrewAI task dynamically based on AI-extracted intent."""
    parsed_input = classify_user_intent(user_input)
    
    # Add to conversation history
    add_to_history("user", user_input)

    # Handle casual chat
    if "casual_chat" in parsed_input:
        response = parsed_input["message"]
        add_to_history("assistant", response, {"intent": "casual_chat"})
        return Task(
            description="Engage in casual chat with the user",
            expected_output="A friendly AI response to the user's casual message",
            agent=calendar_agent,
            context=[{
                "description": "User initiated a casual conversation.",
                "expected_output": response,
                "conversation_type": "casual",
                "response": response,  # Keeping the response data
                "conversation_history": get_conversation_context()
            }]
        )

    intent = parsed_input["intent"]
    date_time = parsed_input.get("date_time")
    duration = parsed_input.get("duration", "60")  # Default: 60 min
    description = parsed_input.get("description", "")
    reference_context = parsed_input.get("reference_context", "")
    
    # Try to resolve references to previous events
    if reference_context and (intent == "update_event" or intent == "delete_event"):
        referenced_event = find_referenced_event()
        if referenced_event:
            # Fill in missing details from the referenced event
            if not date_time or date_time == datetime.now().isoformat():
                date_time = referenced_event.get("date_time", date_time)
            if description == "No description provided":
                description = referenced_event.get("description", description)
            if duration == "60":
                duration = referenced_event.get("duration", duration)

    if intent == "create_event":
        task = Task(
            description=f"Create an event: {description} on {date_time} for {duration} minutes",
            expected_output="Confirmation of event creation",
            agent=calendar_agent,
            context=[{
                "description": f"Create a calendar event for {description}",
                "expected_output": "Success message confirming event creation.",
                "intent": "create_event",
                "event_details": parsed_input,
                "required_tool": "create_event_tool",
                "conversation_history": get_conversation_context()
            }]
        )
    elif intent == "get_events":
        task = Task(
            description=f"Retrieve events for {date_time}",
            expected_output="List of scheduled events",
            agent=calendar_agent,
            context=[{
                "description": f"Fetch all scheduled events for {date_time}",
                "expected_output": "A list of events or a message if none exist.",
                "intent": "get_events",
                "date": date_time,
                "required_tool": "get_events_tool",
                "conversation_history": get_conversation_context()
            }]
        )
    elif intent == "check_availability":
        task = Task(
            description=f"Check availability for {date_time} for {duration} minutes",
            expected_output="Available time slots",
            agent=calendar_agent,
            context=[{
                "description": f"Check if there are free slots on {date_time} for {duration} minutes.",
                "expected_output": "A list of available time slots or a message indicating no availability.",
                "intent": "check_availability",
                "date_time": date_time,
                "duration": duration,
                "required_tool": "check_availability_tool",
                "conversation_history": get_conversation_context()
            }]
        )
    elif intent == "update_event":
        old_date_time = parsed_input.get("old_date_time", date_time)
        task = Task(
            description=f"Update event from {old_date_time} to {date_time} for {duration} minutes",
            expected_output="Confirmation of event update",
            agent=calendar_agent,
            context=[{
                "description": f"Update a calendar event from {old_date_time} to {date_time}",
                "expected_output": "Success message confirming event update.",
                "intent": "update_event",
                "old_date_time": old_date_time,
                "new_date_time": date_time,
                "duration": duration,
                "description": description,
                "required_tool": "update_event_tool",
                "conversation_history": get_conversation_context()
            }]
        )
    elif intent == "delete_event":
        task = Task(
            description=f"Delete event: {description} on {date_time}",
            expected_output="Confirmation of event deletion",
            agent=calendar_agent,
            context=[{
                "description": f"Delete a calendar event for {description} on {date_time}",
                "expected_output": "Success message confirming event deletion.",
                "intent": "delete_event",
                "date_time": date_time,
                "duration": duration,
                "description": description,
                "required_tool": "delete_event_tool",
                "conversation_history": get_conversation_context()
            }]
        )
    elif intent == "get_available_slots":
        task = Task(
            description=f"Find available slots on {date_time} for {duration} minutes",
            expected_output="List of available time slots",
            agent=calendar_agent,
            context=[{
                "description": f"Find all available time slots on {date_time} for a {duration}-minute meeting.",
                "expected_output": "A list of available time slots or a message indicating no availability.",
                "intent": "get_available_slots",
                "date": date_time,
                "duration": duration,
                "required_tool": "get_available_slots_tool",
                "conversation_history": get_conversation_context()
            }]
        )
    else:
        task = Task(
            description="Clarify user request",
            expected_output="Request more details from the user",
            agent=calendar_agent,
            context=[{
                "intent": "clarify",
                "message": "I'm not sure what you're asking for. Could you provide more details about what you'd like to do with your calendar?",
                "conversation_history": get_conversation_context()
            }]
        )
    
    return task

# 💬 WhatsApp-Like Chat UI
def chatbot():
    print("\n💬 Welcome to AI Calendar Assistant! Type 'exit' to quit.\n")

    while True:
        user_input = input("You:")  # Green user text
        if user_input.lower() in ["exit", "quit"]:
            print("Bot: Goodbye! Have a great day!")
            break

        task = create_calendar_task(user_input)

        crew = Crew(
            agents=[calendar_agent],
            tasks=[task],  # Pass task in a list
            verbose=False,
            process=Process.sequential
        )

        result = crew.kickoff()
        
        # Add assistant's response to history
        add_to_history("assistant", result, task.context[0] if task.context else {})
        
        print(f"Bot: {result}")  # Blue bot text

if __name__ == "__main__":
    chatbot()