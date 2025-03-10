import os
import datetime
import pandas as pd
from flask import Flask, request, render_template, jsonify
import re

app = Flask(__name__)

# Configuration
CSV_CALENDAR_FILE = "calendar.csv"
TIMEZONE = "America/New_York"
WORKING_HOURS = (9, 17)  # Office hours (9 AM - 5 PM) - centralized definition

# Ensure CSV file exists
def initialize_calendar():
    if not os.path.exists(CSV_CALENDAR_FILE):
        df = pd.DataFrame(columns=["start_time", "end_time", "description"])
        df.to_csv(CSV_CALENDAR_FILE, index=False)

# Load calendar from CSV
def load_calendar():
    return pd.read_csv(CSV_CALENDAR_FILE, parse_dates=["start_time", "end_time"], infer_datetime_format=True)

# Save calendar to CSV
def save_calendar(df):
    df.to_csv(CSV_CALENDAR_FILE, index=False)

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

# Check availability
def check_availability(start_time, end_time):
    # First check if the proposed time is within working hours
    within_hours, reason = is_within_working_hours(start_time, end_time)
    if not within_hours:
        return False, reason
    
    df = load_calendar()
    for _, row in df.iterrows():
        if (start_time < row["end_time"]) and (end_time > row["start_time"]):
            return False, "Time slot conflicts with an existing event"
    return True, "Time slot is available"

# Create event
def create_event(start_time, end_time, description):
    is_available, reason = check_availability(start_time, end_time)
    if is_available:
        df = load_calendar()
        new_event = pd.DataFrame([[start_time, end_time, description]], columns=["start_time", "end_time", "description"])
        df = pd.concat([df, new_event], ignore_index=True)
        save_calendar(df)
        return True, "Event created successfully"
    return False, reason

# Delete event
def delete_event(start_time, end_time):
    df = load_calendar()
    
    # Find the matching event
    match_index = df[
        (df["start_time"] == start_time) & 
        (df["end_time"] == end_time) & 
        (df["description"] == description)
    ].index

    if not match_index.empty:
        df = df.drop(match_index).reset_index(drop=True)
        save_calendar(df)
        return True, "Event deleted successfully"
    return False, "Event not found with the specified details"

@app.route('/available-slots', methods=['GET'])
def get_available_slots():
    """
    Finds available time slots for a given date and meeting duration.

    :return: List of available time slots.
    """
    date_str = request.args.get('date')  # Expected format: "YYYY-MM-DD"
    duration_str = request.args.get('duration')  # Expected format: "60 minutes" or similar

    # Extract number from duration string using regex
    duration_match = re.search(r'\d+', duration_str)
    if not duration_match:
        return jsonify({"success": False, "error": "Invalid duration format"})

    duration = int(duration_match.group())

    df = load_calendar()
    date = datetime.datetime.strptime(date_str, "%Y-%m-%d").date()

    slot_duration = datetime.timedelta(minutes=duration)

    # Filter events for the given date
    events = df[(df["start_time"].dt.date == date)]

    # Generate all possible time slots
    start_time = datetime.datetime.combine(date, datetime.time(WORKING_HOURS[0], 0))
    end_time = datetime.datetime.combine(date, datetime.time(WORKING_HOURS[1], 0))

    free_slots = []
    current_time = start_time

    while current_time + slot_duration <= end_time:
        potential_end_time = current_time + slot_duration

        # Check if slot overlaps with any event
        is_conflicting = events.apply(
            lambda row: (current_time < row["end_time"]) and (potential_end_time > row["start_time"]), axis=1
        ).any()

        if not is_conflicting:
            free_slots.append({"start": current_time.isoformat(), "end": potential_end_time.isoformat()})

        current_time += datetime.timedelta(minutes=30)  # Move to the next possible slot in 30-minute increments

    return jsonify({
        "success": True, 
        "available_slots": free_slots,
        "message": f"Found {len(free_slots)} available time slots for the requested date and duration"
    })

@app.route('/add', methods=['POST'])
def add_event():
    data = request.json
    try:
        start_time = datetime.datetime.strptime(data['start_time'], "%Y-%m-%dT%H:%M")
        end_time = start_time + datetime.timedelta(minutes=int(data['duration']))
        
        # Check if the event is within working hours
        within_hours, reason = is_within_working_hours(start_time, end_time)
        if not within_hours:
            return jsonify({"success": False, "error": reason})
        
        success, message = create_event(start_time, end_time, data['description'])
        if success:
            return jsonify({"success": True, "message": message})
        else:
            return jsonify({"success": False, "error": message})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route('/delete', methods=['DELETE'])
def delete_event_route():
    data = request.json
    try:
        start_time = datetime.datetime.strptime(data['start_time'], "%Y-%m-%dT%H:%M")
        end_time = start_time + datetime.timedelta(minutes=int(data['duration']))
        success, message = delete_event(start_time, end_time, data['description'])
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
        df = load_calendar()
        
        # Filter events happening on the given date
        filtered_events = df[
            (df["start_time"].dt.date == date)
        ]

        events_list = filtered_events.to_dict(orient="records")
        return jsonify({
            "success": True, 
            "events": events_list,
            "message": f"Found {len(events_list)} events for {date_str}"
        })
    
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route('/get-events-by-datetime', methods=['GET'])
def get_events_by_datetime():
    datetime_str = request.args.get('datetime')  # Expected format: "YYYY-MM-DDTHH:MM"
    
    try:
        event_datetime = datetime.datetime.strptime(datetime_str, "%Y-%m-%dT%H:%M")
        df = load_calendar()
        
        # Find if there's an event at the exact date-time
        filtered_events = df[
            (df["start_time"] <= event_datetime) & 
            (df["end_time"] > event_datetime)
        ]

        events_list = filtered_events.to_dict(orient="records")
        if events_list:
            message = f"Found {len(events_list)} event(s) at the specified time"
        else:
            message = "No events found at the specified time"
            
        return jsonify({
            "success": True, 
            "events": events_list,
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
            "reason": reason
        })
    
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})
    
@app.route('/update-event', methods=['PUT'])
def update_event():
    data = request.json
    try:
        # Parse old and new times
        old_start_time = datetime.datetime.strptime(data['old_start_time'], "%Y-%m-%dT%H:%M")
        new_start_time = datetime.datetime.strptime(data['new_start_time'], "%Y-%m-%dT%H:%M")
        new_end_time = new_start_time + datetime.timedelta(minutes=int(data['duration']))
        
        # Check if the new time is within working hours
        within_hours, reason = is_within_working_hours(new_start_time, new_end_time)
        if not within_hours:
            return jsonify({"success": False, "error": reason})
        
        # Load existing events
        df = load_calendar()
        
        # Find the event with the old start time
        event_index = df[df["start_time"] == old_start_time].index
        if event_index.empty:
            return jsonify({"success": False, "error": "Event not found"})

        # Store the index before removing (needed for reinsertion)
        event_index_value = event_index[0]
        
        # Store the old event data
        old_event = df.loc[event_index_value].copy()
        
        # Temporarily remove the event from the dataframe
        temp_df = df.drop(event_index).reset_index(drop=True)
        
        # Check if the new time slot is available
        conflict_found = False
        conflict_reason = ""
        
        for _, row in temp_df.iterrows():
            if (new_start_time < row["end_time"]) and (new_end_time > row["start_time"]):
                conflict_found = True
                conflict_reason = f"Time slot conflicts with event: {row['description']}"
                break
        
        if conflict_found:
            return jsonify({"success": False, "error": conflict_reason})

        # Create a new row with updated times
        updated_row = pd.Series({
            "start_time": new_start_time,
            "end_time": new_end_time,
            "description": data.get('description', old_event["description"])
        })
        
        # Add back the updated event
        df.loc[event_index_value] = updated_row
        df.sort_values(by="start_time", inplace=True)  # Keep events in order
        save_calendar(df)

        return jsonify({
            "success": True, 
            "message": "Event updated successfully",
            "details": {
                "old_start": old_start_time.isoformat(),
                "new_start": new_start_time.isoformat(),
                "new_end": new_end_time.isoformat()
            }
        })

    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

if __name__ == '__main__':
    initialize_calendar()
    app.run(debug=True)