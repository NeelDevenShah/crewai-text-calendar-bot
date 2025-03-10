import os
import datetime
import pandas as pd
from flask import Flask, request, render_template, jsonify
import re

app = Flask(__name__)

# Configuration
CSV_CALENDAR_FILE = "calendar.csv"
TIMEZONE = "America/New_York"

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

# Check availability
def check_availability(start_time, end_time):
    df = load_calendar()
    for _, row in df.iterrows():
        if (start_time < row["end_time"]) and (end_time > row["start_time"]):
            return False  # Time slot is taken
    return True

# Create event
def create_event(start_time, end_time, description):
    if check_availability(start_time, end_time):
        df = load_calendar()
        new_event = pd.DataFrame([[start_time, end_time, description]], columns=["start_time", "end_time", "description"])
        df = pd.concat([df, new_event], ignore_index=True)
        save_calendar(df)
        return True
    return False

# Delete event
def delete_event(start_time, end_time, description):
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
        return True
    return False

def load_calendar(csv_path="calendar.csv"):
    """
    Loads calendar events from a CSV file.
    Expected CSV columns: ["start_time", "end_time"]
    Both should be in ISO format: "YYYY-MM-DDTHH:MM"
    """
    df = pd.read_csv(csv_path)
    df["start_time"] = pd.to_datetime(df["start_time"])
    df["end_time"] = pd.to_datetime(df["end_time"])
    return df

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

    working_hours = (9, 17)  # Office hours (9 AM - 5 PM)
    slot_duration = datetime.timedelta(minutes=duration)

    # Filter events for the given date
    events = df[(df["start_time"].dt.date == date)]

    # Generate all possible time slots
    start_time = datetime.datetime.combine(date, datetime.time(working_hours[0], 0))
    end_time = datetime.datetime.combine(date, datetime.time(working_hours[1], 0))

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

        current_time += slot_duration  # Move to the next possible slot

    return jsonify({"success": True, "available_slots": free_slots})

@app.route('/add', methods=['POST'])
def add_event():
    data = request.json
    try:
        start_time = datetime.datetime.strptime(data['start_time'], "%Y-%m-%dT%H:%M")
        end_time = start_time + datetime.timedelta(minutes=int(data['duration']))
        if create_event(start_time, end_time, data['description']):
            return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})
    return jsonify({"success": False})

@app.route('/delete', methods=['DELETE'])
def delete_event_route():
    data = request.json
    try:
        start_time = datetime.datetime.strptime(data['start_time'], "%Y-%m-%dT%H:%M")
        end_time = start_time + datetime.timedelta(minutes=int(data['duration']))
        if delete_event(start_time, end_time, data['description']):
            return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})
    return jsonify({"success": False})

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
        return jsonify({"success": True, "events": events_list})
    
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
        return jsonify({"success": True, "events": events_list})
    
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route('/check-specific-availability', methods=['GET'])
def check_slot_availability():
    datetime_str = request.args.get('datetime')  # Expected: "YYYY-MM-DDTHH:MM"
    duration = int(request.args.get('duration'))  # Expected: Minutes

    try:
        start_time = datetime.datetime.strptime(datetime_str, "%Y-%m-%dT%H:%M")
        end_time = start_time + datetime.timedelta(minutes=duration)
        
        is_available = check_availability(start_time, end_time)
        return jsonify({"success": True, "available": is_available})
    
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
        
        # Load existing events
        df = load_calendar()
        
        # Find the event with the old start time
        event_index = df[df["start_time"] == old_start_time].index
        if event_index.empty:
            return jsonify({"success": False, "error": "Event not found"})

        event_index = event_index[0]  # Extract first matching event
        
        # Temporarily remove the event from the list (to avoid self-collision)
        df.drop(event_index, inplace=True)
        
        # Check if the new time slot is available
        for _, row in df.iterrows():
            if (new_start_time < row["end_time"]) and (new_end_time > row["start_time"]):
                return jsonify({"success": False, "error": "Time slot is already taken"})

        # Update event details
        df.loc[event_index] = [new_start_time, new_end_time, data['description']]
        df.sort_values(by="start_time", inplace=True)  # Keep events in order
        save_calendar(df)

        return jsonify({"success": True, "message": "Event updated successfully"})

    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

if __name__ == '__main__':
    initialize_calendar()
    app.run(debug=True)