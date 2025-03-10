import json
import requests
import os
import re
import sys
from typing import Dict, Any
from datetime import datetime
from dotenv import load_dotenv
from crewai import Agent, Crew, Task, Process, LLM
from crewai.tools import tool  # Import the Tool class
from langchain_google_genai import ChatGoogleGenerativeAI

load_dotenv()

# API Configuration
API_BASE_URL = "http://127.0.0.1:5000"
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
os.environ["GEMINI_API_KEY"] = GEMINI_API_KEY

# Initialize AI Model
llm_2 = ChatGoogleGenerativeAI(model="gemini-2.0-flash",
                             verbose = True,
                             temperature = 0.6,
                             google_api_key=GEMINI_API_KEY)
llm = LLM(model="gemini/gemini-2.0-flash")

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

# 🔥 AI-Powered Intent Classification
def classify_user_intent(user_input: str) -> Dict[str, Any]:
    """Use AI to classify intent and extract structured event data."""
    prompt = f"""
    You are a calendar assistant. Identify the user's intent and extract:
    - "intent" (Make sure the intent is from the given example only) (e.g., "casual_chat", "create_event", "get_events", "check_availability", "update_event", "delete_event", "clarify_user_request")
    - "date_time" (ISO format: YYYY-MM-DDTHH:MM)
    - "duration" (in minutes, default 60 if unspecified)
    - "description" (Short summary of the event)
    - "old_date_time" (ISO format: YYYY-MM-DDTHH:MM) - Only for update_event intent

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
        "description": parsed_json.get("description", "No description provided")
    }
    
    # Add old_date_time for update events if it exists
    if parsed_json.get("old_date_time"):
        fixed_json["old_date_time"] = parsed_json.get("old_date_time")
    
    print('***BYE')
    return fixed_json if fixed_json["intent"] != "unknown" else {"error": "Could not understand the request."}

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
def delete_event_tool(date_time: str, duration: str, description: str) -> Dict:
    """Delete a calendar event."""
    print('Enter the tool of the delete event')
    try:
        event_data = {
            "start_time": date_time,
            "duration": duration,
            "description": description
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

    # Handle casual chat
    if "casual_chat" in parsed_input:
        response = parsed_input["message"]
        return Task(
            description="Engage in casual chat with the user",
            expected_output="A friendly AI response to the user's casual message",
            agent=calendar_agent,
            context=[{
                "description": "User initiated a casual conversation.",
                "expected_output": response,
                "conversation_type": "casual",
                "response": response  # Keeping the response data
            }]
        )

    intent = parsed_input["intent"]
    date_time = parsed_input.get("date_time")
    duration = parsed_input.get("duration", "60")  # Default: 60 min
    description = parsed_input.get("description", "")

    if intent == "create_event":
        return Task(
            description=f"Create an event: {description} on {date_time} for {duration} minutes",
            expected_output="Confirmation of event creation",
            agent=calendar_agent,
            context=[{
                "description": f"Create a calendar event for {description}",
                "expected_output": "Success message confirming event creation.",
                "intent": "create_event",
                "event_details": parsed_input,
                "required_tool": "create_event_tool"
            }]
        )
    elif intent == "get_events":
        return Task(
            description=f"Retrieve events for {date_time}",
            expected_output="List of scheduled events",
            agent=calendar_agent,
            context=[{
                "description": f"Fetch all scheduled events for {date_time}",
                "expected_output": "A list of events or a message if none exist.",
                "intent": "get_events",
                "date": date_time,
                "required_tool": "get_events_tool"
            }]
        )
    elif intent == "check_availability":
        return Task(
            description=f"Check availability for {date_time} for {duration} minutes",
            expected_output="Available time slots",
            agent=calendar_agent,
            context=[{
                "description": f"Check if there are free slots on {date_time} for {duration} minutes.",
                "expected_output": "A list of available time slots or a message indicating no availability.",
                "intent": "check_availability",
                "date_time": date_time,
                "duration": duration,
                "required_tool": "check_availability_tool"
            }]
        )
    elif intent == "update_event":
        old_date_time = parsed_input.get("old_date_time", date_time)
        return Task(
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
                "required_tool": "update_event_tool"
            }]
        )
    elif intent == "delete_event":
        return Task(
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
                "required_tool": "delete_event_tool"
            }]
        )
    elif intent == "get_available_slots":
        return Task(
            description=f"Find available slots on {date_time} for {duration} minutes",
            expected_output="List of available time slots",
            agent=calendar_agent,
            context=[{
                "description": f"Find all available time slots on {date_time} for a {duration}-minute meeting.",
                "expected_output": "A list of available time slots or a message indicating no availability.",
                "intent": "get_available_slots",
                "date": date_time,
                "duration": duration,
                "required_tool": "get_available_slots_tool"
            }]
        )

    return Task(
        description="Clarify user request",
        expected_output="Request more details from the user",
        agent=calendar_agent,
        context=[{
            "intent": "clarify",
            "message": "I'm not sure what you're asking for. Could you provide more details about what you'd like to do with your calendar?"
        }]
    )

# 💬 WhatsApp-Like Chat UI
def chatbot():
    print("\n💬 Welcome to AI Calendar Assistant! Type 'exit' to quit.\n")

    while True:
        user_input = input("\033[1;32mYou:\033[0m ")  # Green user text
        if user_input.lower() in ["exit", "quit"]:
            print("\033[1;31mBot: Goodbye! Have a great day!\033[0m")
            break

        task = create_calendar_task(user_input)

        crew = Crew(
            agents=[calendar_agent],
            tasks=[task],  # Pass task in a list
            verbose=False,
            process=Process.sequential
        )

        result = crew.kickoff()
        
        print(f"\033[1;34mBot: {result}\033[0m")  # Blue bot text

if __name__ == "__main__":
    chatbot()