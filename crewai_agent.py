import json
import requests
import os
import re
import sys
from typing import Dict, Any, List
from datetime import datetime, date, timedelta
from dotenv import load_dotenv
from flask import Flask, request, jsonify
from flask_cors import CORS
from crewai import Agent, Crew, Task, Process, LLM
from crewai.tools import tool
import ast
from langchain_google_genai import ChatGoogleGenerativeAI

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# API Configuration
API_BASE_URL = "http://127.0.0.1:5000"
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
os.environ["GEMINI_API_KEY"] = GEMINI_API_KEY

# Initialize AI Model
llm_2 = ChatGoogleGenerativeAI(model="gemini-2.0-flash",
                             verbose=True,
                             temperature=0,
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

# Format date helper function
def format_date_iso(date_str: str) -> str:
    """
    Ensure date is in ISO format YYYY-MM-DDTHH:MM
    If only date is provided, append default time (9:00 AM)
    """
    if not date_str:
        return datetime.now().strftime('%Y-%m-%dT09:00')
    
    # If only date is provided (no time)
    if 'T' not in date_str:
        return f"{date_str}T09:00"
    
    return date_str

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
    current_date = datetime.now()
    
    prompt = f"""
    You are a calendar assistant. Today's date is {current_date.strftime('%Y-%m-%d')}.
    Identify the user's intent and extract:
    - "intent" (Make sure the intent is from the given example only) (e.g., "casual_chat", "create_event", "get_events", "check_availability", "update_event", "delete_event", "clarify_user_request")
    - "date_time" (ISO format: YYYY-MM-DDTHH:MM) - Use today's date {current_date.strftime('%Y-%m-%d')} as default if no date is specified
    - "duration" (in minutes, default 60 if unspecified)
    - "description" (Short summary of the event)
    - "old_date_time" (ISO format: YYYY-MM-DDTHH:MM) - Only for update_event intent
    - "reference_context" (any event or information referenced from previous conversation)

    If the user is just chatting (e.g., "Hey, how are you?"), return:
    {{
      "intent": "casual_chat",
      "message": "Friendly response"
    }}

    For relative dates like "tomorrow" or "next Monday", convert them to actual dates based on today being {current_date.strftime('%Y-%m-%d')}.

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
    
    # If casual chat, just return the AI-generated message
    if parsed_json.get("intent") == "casual_chat":
        return {"casual_chat": True, "message": parsed_json.get("message", "I'm here to help!")}

    # Ensure all required fields exist, fixing missing values
    fixed_json = {
        "intent": parsed_json.get("intent", "unknown"),
        "date_time": parsed_json.get("date_time", datetime.now().isoformat()),  # Default: now
        "duration": str(parsed_json.get("duration", "60")),  # Default: 60 minutes
        "description": parsed_json.get("description", "No description provided"),
        "reference_context": parsed_json.get("reference_context", ""),
        "missing_fields": []
    }
    
    # Add old_date_time for update events if it exists
    if parsed_json.get("old_date_time"):
        fixed_json["old_date_time"] = parsed_json.get("old_date_time")
    
    # Check for required fields for event creation/updates
    if fixed_json["intent"] in ["create_event", "update_event"]:
        # Date time validation with default of current date if missing
        if not parsed_json.get("date_time") or parsed_json.get("date_time") == "":
            fixed_json["missing_fields"].append("date_time")
            
        # Description validation
        if not parsed_json.get("description") or parsed_json.get("description") == "No description provided":
            fixed_json["missing_fields"].append("description")
    
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
    """Retrieve events for a given date. Format the date to YYYY-MM-DD if it contains a time component."""
    try:
        if "T" in date:
            date = date.split("T")[0]
            
        response = requests.get(f"{API_BASE_URL}/get-events-by-date", params={"date": date})
        response_data = response.json()
        if response_data.get("success") == True:
            return {"success": True, "slots": response_data}
        else:
            return {"success": False, "error": response_data.get("error", "Unknown error")}
    except Exception as e:
        return {"success": False, "error": f"Failed to fetch events: {str(e)}"}

@tool('check_availability_tool')
def check_availability_tool(date_time: str, duration: str) -> Dict:
    """Check if a specific time slot is available."""
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
            return {"success": True, "slots": response_data}
        else:
            return {"success": False, "error": response_data.get("error", "Unknown error")}
    except Exception as e:
        return {"success": False, "error": f"Failed to get available slots: {str(e)}"}

@tool('update_event_tool')
def update_event_tool(old_date_time: str, new_date_time: str, duration: str, description: str) -> Dict:
    """Update an existing calendar event."""
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
    backstory="""You're an AI-powered calendar manager that schedules, updates, retrieves, and manages events. And you always return the output in json format only. The format is: 
     {
        "message": "Generalized response message",
        "success": true,
        "slots": [
            {
            "start": "ISO 8601 datetime format",
            "end": "ISO 8601 datetime format"
            }
        ]
        }
    """,
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
    
    # Get current date for context
    current_date = datetime.now()

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
                "expected_output": """Make sure that the output should be in format: {
                    "message": "Generalized response message",
                    "success": true,
                    "slots": [
                        {
                        "start": "ISO 8601 datetime format",
                        "end": "ISO 8601 datetime format"
                        }
                    ]
                    }""",
                "conversation_type": "casual",
                "response": response,  # Keeping the response data
                "conversation_history": get_conversation_context(),
                "current_date": current_date.strftime("%Y-%m-%d")
            }]
        )

    # Handle error in parsing
    if "error" in parsed_input:
        response = "I'm not sure what you're asking for. Could you provide more details about what you'd like to do with your calendar?"
        add_to_history("assistant", response, {"intent": "error"})
        return Task(
            description="Handle parsing error",
            expected_output="Ask user for clarification",
            agent=calendar_agent,
            context=[{
                "description": "Failed to parse user intent.",
                "expected_output": """Make sure that the output should be in format: {
                    "message": "Generalized response message",
                    "success": true,
                    "slots": [
                        {
                        "start": "ISO 8601 datetime format",
                        "end": "ISO 8601 datetime format"
                        }
                    ]
                    }""",
                "response": response,
                "conversation_history": get_conversation_context(),
                "current_date": current_date.strftime("%Y-%m-%d")
            }]
        )

    intent = parsed_input["intent"]
    date_time = parsed_input.get("date_time", "")
    duration = parsed_input.get("duration", "60")  # Default: 60 min
    description = parsed_input.get("description", "")
    reference_context = parsed_input.get("reference_context", "")
    missing_fields = parsed_input.get("missing_fields", [])
    
    # Check for missing required fields for create and update intents
    if (intent == "create_event" or intent == "update_event") and missing_fields:
        missing_info = ", ".join(missing_fields)
        response = f"I need more information to {intent.replace('_', ' ')}. Please provide: {missing_info}."
        add_to_history("assistant", response, {"intent": "request_info", "missing_fields": missing_fields})
        return Task(
            description="Request missing information",
            expected_output="Ask user for required details",
            agent=calendar_agent,
            context=[{
                "description": f"Request missing information for {intent}",
                "expected_output": """Make sure that the output should be in format: {
                    "message": "Generalized response message",
                    "success": true,
                    "slots": [
                        {
                        "start": "ISO 8601 datetime format",
                        "end": "ISO 8601 datetime format"
                        }
                    ]
                    }""",
                "response": response,
                "missing_fields": missing_fields,
                "conversation_history": get_conversation_context(),
                "current_date": current_date.strftime("%Y-%m-%d")
            }]
        )
    
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

    # Ensure date_time is properly formatted with current date as default
    date_time = format_date_iso(date_time)
    
    if intent == "create_event":
        task = Task(
            description=f"Create an event: {description} on {date_time} for {duration} minutes",
            expected_output="Confirmation of event creation",
            agent=calendar_agent,
            context=[{
                "description": f"Create a calendar event for {description}",
                "expected_output": """Make sure that the output should be in format: {
                    "message": "Generalized response message",
                    "success": true,
                    "slots": [
                        {
                        "start": "ISO 8601 datetime format",
                        "end": "ISO 8601 datetime format"
                        }
                    ]
                    }""",
                "intent": "create_event",
                "event_details": {
                    "date_time": date_time,
                    "duration": duration,
                    "description": description
                },
                "required_tool": "create_event_tool",
                "conversation_history": get_conversation_context(),
                "current_date": current_date.strftime("%Y-%m-%d")
            }]
        )
    elif intent == "get_events":
        task = Task(
            description=f"Retrieve events for {date_time}",
            expected_output="List of scheduled events",
            agent=calendar_agent,
            context=[{
                "description": f"Fetch all scheduled events for {date_time}",
                "expected_output": """Make sure that the output should be in format: {
                    "message": "Generalized response message",
                    "success": true,
                    "slots": [
                        {
                        "start": "ISO 8601 datetime format",
                        "end": "ISO 8601 datetime format"
                        }
                    ]
                    }""",
                "intent": "get_events",
                "date": date_time,
                "required_tool": "get_events_tool",
                "conversation_history": get_conversation_context(),
                "current_date": current_date.strftime("%Y-%m-%d")
            }]
        )
    elif intent == "check_availability":
        task = Task(
            description=f"Check availability for {date_time} for {duration} minutes",
            expected_output="Available time slots",
            agent=calendar_agent,
            context=[{
                "description": f"Check if there are free slots on {date_time} for {duration} minutes.",
                "expected_output": """Make sure that the output should be in format: {
                    "message": "Generalized response message",
                    "success": true,
                    "slots": [
                        {
                        "start": "ISO 8601 datetime format",
                        "end": "ISO 8601 datetime format"
                        }
                    ]
                    }""",
                "intent": "check_availability",
                "date_time": date_time,
                "duration": duration,
                "required_tool": "check_availability_tool",
                "conversation_history": get_conversation_context(),
                "current_date": current_date.strftime("%Y-%m-%d")
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
                "expected_output": """Make sure that the output should be in format: {
                    "message": "Generalized response message",
                    "success": true,
                    "slots": [
                        {
                        "start": "ISO 8601 datetime format",
                        "end": "ISO 8601 datetime format"
                        }
                    ]
                    }""",
                "intent": "update_event",
                "old_date_time": old_date_time,
                "new_date_time": date_time,
                "duration": duration,
                "description": description,
                "required_tool": "update_event_tool",
                "conversation_history": get_conversation_context(),
                "current_date": current_date.strftime("%Y-%m-%d")
            }]
        )
    elif intent == "delete_event":
        task = Task(
            description=f"Delete event on {date_time}",
            expected_output="Confirmation of event deletion",
            agent=calendar_agent,
            context=[{
                "description": f"Delete a calendar event for {description} on {date_time}",
                "expected_output": """Make sure that the output should be in format: {
                    "message": "Generalized response message",
                    "success": true,
                    "slots": [
                        {
                        "start": "ISO 8601 datetime format",
                        "end": "ISO 8601 datetime format"
                        }
                    ]
                    }""",
                "intent": "delete_event",
                "date_time": date_time,
                "duration": duration,
                "required_tool": "delete_event_tool",
                "conversation_history": get_conversation_context(),
                "current_date": current_date.strftime("%Y-%m-%d")
            }]
        )
    elif intent == "get_available_slots":
        task = Task(
            description=f"Find available slots on {date_time} for {duration} minutes",
            expected_output="List of available time slots",
            agent=calendar_agent,
            context=[{
                "description": f"Find all available time slots on {date_time} for a {duration}-minute meeting.",
                "expected_output": """Make sure that the output should be in format: {
                    "message": "Generalized response message",
                    "success": true,
                    "slots": [
                        {
                        "start": "ISO 8601 datetime format",
                        "end": "ISO 8601 datetime format"
                        }
                    ]
                    }""",
                "intent": "get_available_slots",
                "date": date_time,
                "duration": duration,
                "required_tool": "get_available_slots_tool",
                "conversation_history": get_conversation_context(),
                "current_date": current_date.strftime("%Y-%m-%d")
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
                "conversation_history": get_conversation_context(),
                "expected_output": """Make sure that the output should be in format: {
                    "message": "Generalized response message",
                    "success": true,
                    "slots": [
                        {
                        "start": "ISO 8601 datetime format",
                        "end": "ISO 8601 datetime format"
                        }
                    ]
                    }""",
                "current_date": current_date.strftime("%Y-%m-%d")
            }]
        )
    
    return task

def clean_json_string(input_string: str) -> str:
    """
    Removes backticks and optional 'json' tags from a JSON-like string
    and returns a properly formatted JSON string.
    
    :param input_string: The raw string containing JSON data.
    :return: A formatted JSON string.
    """
    # Remove triple backticks and "json" if present
    cleaned_string = re.sub(r"^```json|```$", "", input_string.strip(), flags=re.MULTILINE).strip()

    # Load it into a dictionary to validate and reformat
    try:
        json_data = json.loads(cleaned_string)
        return json.dumps(json_data, indent=4)  # Pretty-print JSON
    except json.JSONDecodeError:
        raise ValueError("Invalid JSON format!")

def process_user_message(user_input: str) -> Dict[str, Any]:
    """Process user input and return response"""
    try:
        # Create task based on user input
        print(f'user: {user_input}')
        task = create_calendar_task(user_input)
        
        # Create and execute crew
        crew = Crew(
            agents=[calendar_agent],
            tasks=[task],
            verbose=False,
            process=Process.sequential
        )
        
        result = crew.kickoff()
        
        # Add assistant's response to history
        add_to_history("assistant", result, task.context[0] if task.context else {})
        
        # TODO: Manage the things( for example events, succes) that we are sending to the frontend, that is the object result, for temporary purposes sending the message to the user.
        print(f'agent: {result}')
        print(result.raw)
        print('----------------------')
        print(type(result.raw))
        print('----------------------')
        
        try:
            final_ans = clean_json_string(result.raw)
            return json.loads(final_ans)
        except Exception as e:
            return {
                "success": True,
                "message": result.raw
            }

    except Exception as e:
        error_message = f"Error processing message: {str(e)}"
        return {
            "success": False,
            "message": f"error: {error_message}"
        }

# API Routes
@app.route('/api/message', methods=['POST'])
def handle_message():
    """API endpoint to handle user messages"""
    data = request.json
    if not data or 'message' not in data:
        return jsonify({
            "success": False,
            "message": "Message field is required"
        }), 400
    
    user_message = data['message']
    response = process_user_message(user_message)
    return response
    

@app.route('/api/history', methods=['GET'])
def get_history():
    """API endpoint to get conversation history"""
    return jsonify({
        "success": True,
        "history": conversation_history
    })

@app.route('/api/clear-history', methods=['POST'])
def clear_history():
    """API endpoint to clear conversation history"""
    global conversation_history
    conversation_history = []
    return jsonify({
        "success": True,
        "message": "Conversation history cleared"
    })

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5001, debug=True)