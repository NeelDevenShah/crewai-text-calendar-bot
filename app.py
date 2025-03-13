import os
import datetime
import re
from flask import Flask, request, render_template, jsonify
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from dateutil import parser
import requests
import pytz

app = Flask(__name__)

# Configuration
SCOPES = ['https://www.googleapis.com/auth/calendar']
TIMEZONE = "Asia/Kolkata"
WORKING_HOURS = (9, 17)  # Office hours (9 AM - 5 PM)

def get_calendar_service():
    """Gets an authorized Google Calendar API service instance."""
    creds = None
    # The file token.json stores the user's access and refresh tokens
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    # If there are no (valid) credentials available, let the user log in
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open('token.json', 'w') as token:
            token.write(creds.to_json())

    return build('calendar', 'v3', credentials=creds)

# Check if time is within working hours
def is_within_working_hours(start_time, end_time):
    # Check if both start and end times are within working hours on their respective days
    start_hour = start_time.hour
    end_hour = end_time.hour
    
    # Check day boundary crossing
    if start_time.date() != end_time.date():
        return False, "Event cannot cross day boundaries"
    
    if start_hour < WORKING_HOURS[0]:
        return False, f"Start time must be after {WORKING_HOURS[0]}:00 AM"
    
    if end_hour > WORKING_HOURS[1]:
        return False, f"End time must be before {WORKING_HOURS[1]}:00 PM"
    
    if start_hour >= WORKING_HOURS[1]:
        return False, f"Start time must be before {WORKING_HOURS[1]}:00 PM"
        
    if end_hour <= WORKING_HOURS[0]:
        return False, f"End time must be after {WORKING_HOURS[0]}:00 AM"
    
    return True, "Within working hours"

# Check availability in Google Calendar
def check_availability(start_time, end_time):
    # First check if the proposed time is within working hours
    within_hours, reason = is_within_working_hours(start_time, end_time)
    if not within_hours:
        return False, reason
    
    service = get_calendar_service()

    # Format times for Google Calendar API
    start_time_str = start_time.isoformat()
    end_time_str = end_time.isoformat()
    
    # Check for conflicts in the calendar
    events_result = service.events().list(
        calendarId='primary',
        timeMin=start_time_str,
        timeMax=end_time_str,
        singleEvents=True,
        orderBy='startTime'
    ).execute()
    
    events = events_result.get('items', [])
    if events:
        return False, "Time slot conflicts with an existing event"
    
    return True, "Time slot is available"

# Delete event from Google Calendar
def delete_event(event_id):
    service = get_calendar_service()
    
    try:
        service.events().delete(calendarId='primary', eventId=event_id).execute()
        return True, "Event deleted successfully"
    except Exception as e:
        return False, f"Error deleting event: {str(e)}"

@app.route('/available-slots', methods=['GET'])
def get_available_slots():
    """
    Finds available time slots for a given date and meeting duration.
    """
    date_str = request.args.get('date')  # Expected format: "YYYY-MM-DD"
    duration_str = request.args.get('duration')  # Expected format: "60 minutes" or similar

    # Extract number from duration string using regex
    duration_match = re.search(r'\d+', duration_str)
    if not duration_match:
        return jsonify({"success": False, "error": "Invalid duration format"})

    duration = int(duration_match.group())
    slot_duration = datetime.timedelta(minutes=duration)
    
    # Parse date and create time bounds
    date = datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
    start_of_day = datetime.datetime.combine(date, datetime.time(WORKING_HOURS[0], 0))
    end_of_day = datetime.datetime.combine(date, datetime.time(WORKING_HOURS[1], 0))
    
    # Convert to timezone aware datetime
    timezone = pytz.timezone(TIMEZONE)
    start_of_day = timezone.localize(start_of_day)
    end_of_day = timezone.localize(end_of_day)
    
    # Format for API
    start_time_str = start_of_day.isoformat()
    end_time_str = end_of_day.isoformat()
    
    service = get_calendar_service()
    
    # Get all events for the day
    events_result = service.events().list(
        calendarId='primary',
        timeMin=start_time_str,
        timeMax=end_time_str,
        singleEvents=True,
        orderBy='startTime'
    ).execute()
    
    events = events_result.get('items', [])
    
    # Find all free slots
    free_slots = []
    current_time = start_of_day
    
    # If no events, the entire day is free
    if not events:
        while current_time + slot_duration <= end_of_day:
            free_slots.append({
                "start": current_time.isoformat(),
                "end": (current_time + slot_duration).isoformat()
            })
            current_time += datetime.timedelta(minutes=30)
    else:
        # Process each event and find gaps
        for event in events:
            event_start = parser.parse(event['start'].get('dateTime', event['start'].get('date')))
            event_end = parser.parse(event['end'].get('dateTime', event['end'].get('date')))
            
            # Add free slots before this event
            while current_time + slot_duration <= event_start:
                free_slots.append({
                    "start": current_time.isoformat(),
                    "end": (current_time + slot_duration).isoformat()
                })
                current_time += datetime.timedelta(minutes=30)
            
            # Move current time to after this event
            current_time = event_end
        
        # Add any remaining slots after the last event
        while current_time + slot_duration <= end_of_day:
            free_slots.append({
                "start": current_time.isoformat(),
                "end": (current_time + slot_duration).isoformat()
            })
            current_time += datetime.timedelta(minutes=30)
    
    return jsonify({
        "success": True, 
        "slots": free_slots,
        "message": f"Found {len(free_slots)} available time slots for the requested date and duration"
    })

@app.route('/delete', methods=['DELETE'])
def delete_event_route():
    data = request.json
    try:
        event_id = data['event_id']
        success, message = delete_event(event_id)
        if success:
            return jsonify({"success": True, "message": message})
        else:
            return jsonify({"success": False, "error": message})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route('/get-events-by-date', methods=['GET'])
def get_events_by_date():
    date_str = request.args.get('date')  # Expected format: "YYYY-MM-DD"
    
    try:
        date = datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
        
        # Create time bounds for the day
        start_of_day = datetime.datetime.combine(date, datetime.time(0, 0))
        end_of_day = datetime.datetime.combine(date, datetime.time(23, 59, 59))
        
        # Convert to timezone aware datetime
        timezone = pytz.timezone(TIMEZONE)
        start_of_day = timezone.localize(start_of_day)
        end_of_day = timezone.localize(end_of_day)
        
        service = get_calendar_service()
        
        # Get all events for the day
        events_result = service.events().list(
            calendarId='primary',
            timeMin=start_of_day.isoformat(),
            timeMax=end_of_day.isoformat(),
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        
        events = events_result.get('items', [])
        
        # Format events for the response
        events_list = []
        for event in events:
            events_list.append({
                "id": event['id'],
                "start_time": event['start'].get('dateTime', event['start'].get('date')),
                "end_time": event['end'].get('dateTime', event['end'].get('date')),
                "description": event.get('summary', 'No description')
            })
        
        return jsonify({
            "success": True, 
            "slots": events_list,
            "message": f"Found {len(events_list)} events for {date_str}"
        })
    
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route('/get-events-by-datetime', methods=['GET'])
def get_events_by_datetime():
    datetime_str = request.args.get('datetime')  # Expected format: "YYYY-MM-DDTHH:MM"
    
    try:
        event_datetime = datetime.datetime.strptime(datetime_str, "%Y-%m-%dT%H:%M")
        
        # Add timezone information
        timezone = pytz.timezone(TIMEZONE)
        event_datetime = timezone.localize(event_datetime)
        
        # Create a small window around the requested time
        start_time = event_datetime - datetime.timedelta(minutes=1)
        end_time = event_datetime + datetime.timedelta(minutes=1)
        
        service = get_calendar_service()
        
        # Get events that may be happening at the requested time
        events_result = service.events().list(
            calendarId='primary',
            timeMin=start_time.isoformat(),
            timeMax=end_time.isoformat(),
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        
        events = events_result.get('items', [])
        
        # Format events for the response
        events_list = []
        for event in events:
            event_start = parser.parse(event['start'].get('dateTime', event['start'].get('date')))
            event_end = parser.parse(event['end'].get('dateTime', event['end'].get('date')))
            
            # Only include events that actually overlap with the requested time
            if event_start <= event_datetime <= event_end:
                events_list.append({
                    "id": event['id'],
                    "start_time": event['start'].get('dateTime', event['start'].get('date')),
                    "end_time": event['end'].get('dateTime', event['end'].get('date')),
                    "description": event.get('summary', 'No description')
                })
        
        if events_list:
            message = f"Found {len(events_list)} event(s) at the specified time"
        else:
            message = "No events found at the specified time"
            
        return jsonify({
            "success": True, 
            "slots": events_list,
            "message": message
        })
    
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route('/check-specific-availability', methods=['GET'])
def check_slot_availability():
    datetime_str = request.args.get('datetime')  # Expected: "YYYY-MM-DDTHH:MM"
    duration = int(request.args.get('duration'))  # Expected: Minutes

    try:
        start_time = datetime.datetime.strptime(datetime_str, "%Y-%m-%dT%H:%M")
        end_time = start_time + datetime.timedelta(minutes=duration)
        
        # Check if the event is within working hours and available
        is_available, reason = check_availability(start_time, end_time)
        
        return jsonify({
            "success": True,
            "available": is_available,
            "message": reason
        })
    
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})
    
@app.route('/update-event', methods=['PUT'])
def update_event():
    data = request.json
    try:
        event_id = data['event_id']
        new_start_time = datetime.datetime.strptime(data['new_start_time'], "%Y-%m-%dT%H:%M")
        new_end_time = new_start_time + datetime.timedelta(minutes=int(data['duration']))
        
        # Check if the new time is within working hours
        within_hours, reason = is_within_working_hours(new_start_time, new_end_time)
        if not within_hours:
            return jsonify({"success": False, "error": reason})
        
        service = get_calendar_service()
        
        # Get the event first
        event = service.events().get(calendarId='primary', eventId=event_id).execute()
        
        # Temporarily delete the event to check for conflicts
        service.events().delete(calendarId='primary', eventId=event_id).execute()
        
        # Check if the new time slot is available
        is_available, reason = check_availability(new_start_time, new_end_time)
        
        if not is_available:
            # Re-insert the original event if the new time isn't available
            service.events().insert(calendarId='primary', body=event).execute()
            return jsonify({"success": False, "error": reason})
        
        # Update the event with new times
        event['start'] = {
            'dateTime': new_start_time.isoformat(),
            'timeZone': TIMEZONE,
        }
        event['end'] = {
            'dateTime': new_end_time.isoformat(),
            'timeZone': TIMEZONE,
        }
        
        if 'description' in data:
            event['description'] = data['description']
            event['summary'] = data['description']
            
        updated_event = service.events().insert(calendarId='primary', body=event).execute()
        
        return jsonify({
            "success": True, 
            "message": "Event updated successfully",
            "event_id": updated_event['id']
        })

    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route('/add', methods=['POST'])
def quick_add_event():
    """Endpoint to quickly add an event using Google Calendar's quickAdd feature"""
    data = request.json
    try:
        text = data['text']  # E.g. "Meeting with John tomorrow at 3pm"
        
        service = get_calendar_service()
        created_event = service.events().quickAdd(
            calendarId='primary',
            text=text
        ).execute()
        
        return jsonify({
            "success": True,
            "message": "Event created successfully",
            "event_id": created_event['id'],
            "event_details": {
                "summary": created_event.get('summary', 'No title'),
                "start": created_event['start'].get('dateTime', created_event['start'].get('date')),
                "end": created_event['end'].get('dateTime', created_event['end'].get('date'))
            }
        })
        
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

if __name__ == '__main__':
    app.run(debug=True)