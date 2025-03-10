import json
import requests
import os
import re
import sys
from typing import Dict, Any
from datetime import datetime
from dotenv import load_dotenv
from crewai import Agent, Crew, Task, Process, LLM
from langchain_groq import ChatGroq

load_dotenv()

# API Configuration
API_BASE_URL = "http://127.0.0.1:5000"
GROQ_API_KEY = os.getenv('GROQ_API_KEY')

# Initialize AI Model
llm_2 = ChatGroq(
    temperature=0.3,
    api_key=GROQ_API_KEY
)

llm = LLM(model="groq/llama-3.3-70b-versatile")

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
# - "intent" (Make sure the intent is from the given example only) (e.g., "create_event", "get_events", "update_event", "delete_event", "check_availability")
def classify_user_intent(user_input: str) -> Dict[str, Any]:
    """Use AI to classify intent and extract structured event data."""
    prompt = f"""
    You are a calendar assistant. Identify the user's intent and extract:
    - "intent" (Make sure the intent is from the given example only) (e.g., "casual_chat", "create_event", "get_events", "check_availability", "clarify_user_request")
    - "date_time" (ISO format: YYYY-MM-DDTHH:MM)
    - "duration" (in minutes, default 60 if unspecified)
    - "description" (Short summary of the event)

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
    print('***BYE')
    return fixed_json if fixed_json["intent"] != "unknown" else {"error": "Could not understand the request."}

# 🎯 Calendar API Integration
class CalendarAPI:
    """Handles all calendar API requests."""
    
    @staticmethod
    def create_event(event_details: Dict) -> Dict:
        """Create a calendar event."""
        try:
            response = requests.post(f"{API_BASE_URL}/add", json=event_details)
            return response.json()
        except Exception as e:
            return {"error": f"Failed to create event: {str(e)}"}

    @staticmethod
    def get_events(date: str) -> Dict:
        """Retrieve events for a given date."""
        try:
            response = requests.get(f"{API_BASE_URL}/get-events", params={"date": date})
            return response.json()
        except Exception as e:
            return {"error": f"Failed to fetch events: {str(e)}"}

    @staticmethod
    def check_availability(date_time: str, duration: str) -> Dict:
        """Check available time slots."""
        try:
            response = requests.get(
                f"{API_BASE_URL}/check-availability", 
                params={"datetime": date_time, "duration": duration}
            )
            return response.json()
        except Exception as e:
            return {"error": f"Failed to check availability: {str(e)}"}

# 📌 CrewAI Agent
calendar_agent = Agent(
    role="Calendar Assistant",
    goal="Help users manage their calendar seamlessly",
    backstory="You're an AI-powered calendar manager that schedules, updates, retrieves, and manages events.",
    verbose=True,
    allow_delegation=False,
    llm=llm
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
            expected_output="Friendly response",
            agent=calendar_agent,
            context=[{
        "description": "Casual conversation with the user",
        "expected_output": "A friendly and engaging response",
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
            context=[{'description': f"Create an event: {description} on {date_time} for {duration} minutes", 'expected_output': 'Confirmation of event creation', "action": "create_event", "event_details": parsed_input}]
        )
    elif intent == "get_events":
        return Task(
            description=f"Retrieve events for {date_time}",
            expected_output="List of scheduled events",
            agent=calendar_agent,
            context=[{"description": f"Retrieve events for {date_time}", "expected_output": "List of scheduled events", "action": "get_events", "date": date_time}]
        )
    elif intent == "check_availability":
        return Task(
            description=f"Check availability for {date_time} for {duration} minutes",
            expected_output="Available time slots",
            agent=calendar_agent,
            context=[{'description':f"Check availability for {date_time} for {duration} minutes", 'expected_output': "Available time slots", "action": "check_availability", "date_time": date_time, "duration": duration}]
        )

    return Task(
        description="clarify_user_request",
        expected_output="Request more details from the user",
        agent=calendar_agent,
        context=[{"description":"Clarify user request",
        "expected_output": "Request more details from the user","response": "Could not determine intent."}]
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
        
        print(f"Bot:{result}")  # Blue bot text

if __name__ == "__main__":
    chatbot()
