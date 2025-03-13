<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Agentic Assistant</title>
    <link href="https://cdnjs.cloudflare.com/ajax/libs/bootstrap/5.3.0/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">
    <style>
        body {
            background-color: #f8f9fa;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        }
        .chat-container {
            max-width: 800px;
            margin: 2rem auto;
            border-radius: 15px;
            overflow: hidden;
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.1);
        }
        .chat-header {
            background: linear-gradient(135deg, #6a11cb 0%, #2575fc 100%);
            color: white;
            padding: 1.5rem;
            border-top-left-radius: 15px;
            border-top-right-radius: 15px;
        }
        .chat-body {
            height: 400px;
            overflow-y: auto;
            padding: 1rem;
            background-color: white;
        }
        .message {
            margin-bottom: 1rem;
            max-width: 80%;
        }
        .user-message {
            margin-left: auto;
            background-color: #e9f5ff;
            border-radius: 18px 18px 0 18px;
        }
        .bot-message {
            background-color: #f0f2f5;
            border-radius: 18px 18px 18px 0;
        }
        .message-content {
            padding: 0.8rem 1rem;
        }
        .chat-footer {
            background-color: white;
            padding: 1rem;
            border-top: 1px solid #e9ecef;
        }
        .success-message {
            background-color: #dff8e9;
            border-left: 4px solid #28a745;
        }
        .error-message {
            background-color: #ffebee;
            border-left: 4px solid #dc3545;
        }
        .typing-indicator {
            display: none;
            padding: 10px;
            margin-bottom: 10px;
        }
        .typing-indicator span {
            height: 10px;
            width: 10px;
            margin: 0 1px;
            background-color: #6a11cb;
            display: inline-block;
            border-radius: 50%;
            opacity: 0.6;
            animation: typing 1s infinite ease-in-out;
        }
        .typing-indicator span:nth-child(2) {
            animation-delay: 0.2s;
        }
        .typing-indicator span:nth-child(3) {
            animation-delay: 0.4s;
        }
        @keyframes typing {
            0% { transform: translateY(0px); }
            50% { transform: translateY(-5px); }
            100% { transform: translateY(0px); }
        }
        .avatar {
            width: 38px;
            height: 38px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            margin-right: 10px;
        }
        .user-avatar {
            background-color: #e9f5ff;
            color: #2575fc;
        }
        .bot-avatar {
            background: linear-gradient(135deg, #6a11cb 0%, #2575fc 100%);
            color: white;
        }
        .message-wrapper {
            display: flex;
            align-items: flex-start;
            margin-bottom: 1rem;
        }
        .input-area {
            position: relative;
        }
        .emoji-btn {
            position: absolute;
            right: 65px;
            top: 10px;
            color: #6c757d;
            cursor: pointer;
            z-index: 10;
            background: none;
            border: none;
        }
        .event-card {
            background-color: #f8f9fa;
            border-radius: 8px;
            padding: 10px;
            margin-top: 5px;
            border-left: 3px solid #2575fc;
        }
        .event-title {
            font-weight: 600;
            color: #2575fc;
        }
        .event-time {
            font-size: 0.9rem;
            color: #6c757d;
        }
        .slot-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
            gap: 10px;
            margin-top: 10px;
        }
        .time-slot {
            background-color: rgba(37, 117, 252, 0.1);
            border-radius: 8px;
            padding: 8px;
            text-align: center;
            border: 1px solid rgba(37, 117, 252, 0.2);
            transition: all 0.3s ease;
        }
        .time-slot:hover {
            background-color: rgba(37, 117, 252, 0.2);
            transform: translateY(-2px);
        }
        .slot-time {
            font-size: 0.9rem;
            font-weight: 500;
            color: #2575fc;
        }
        .prompt-suggestions {
            background-color: white;
            border-radius: 0 0 15px 15px;
            padding: 1rem;
            border-top: 1px dashed #e9ecef;
            box-shadow: 0 5px 30px rgba(0, 0, 0, 0.1);
        }
        .suggestions-toggle {
            color: #6a11cb;
            font-weight: 500;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            margin-bottom: 10px;
        }
        .suggestions-toggle i {
            margin-left: 5px;
            transition: transform 0.3s ease;
        }
        .suggestions-toggle.collapsed i {
            transform: rotate(180deg);
        }
        .suggestion-item {
            padding: 10px 15px;
            border-radius: 8px;
            background-color: #f8f9fa;
            margin-bottom: 8px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            transition: all 0.3s ease;
        }
        .suggestion-item:hover {
            background-color: #f0f2f5;
        }
        .suggestion-text {
            flex: 1;
            font-size: 0.9rem;
        }
        .try-btn {
            background: linear-gradient(135deg, #6a11cb 0%, #2575fc 100%);
            color: white;
            border: none;
            border-radius: 6px;
            padding: 5px 10px;
            font-size: 0.8rem;
            transition: all 0.3s ease;
        }
        .try-btn:hover {
            opacity: 0.9;
            transform: translateY(-2px);
        }
        @keyframes highlightInput {
            0% { box-shadow: 0 0 0 0 rgba(106, 17, 203, 0.4); }
            70% { box-shadow: 0 0 0 10px rgba(106, 17, 203, 0); }
            100% { box-shadow: 0 0 0 0 rgba(106, 17, 203, 0); }
        }
        .input-highlight {
            animation: highlightInput 1s ease-in-out;
        }
        @keyframes buttonPress {
            0% { transform: scale(1); }
            50% { transform: scale(0.95); }
            100% { transform: scale(1); }
        }
        .button-press {
            animation: buttonPress 0.3s ease-in-out;
        }
        .slot-desc{
            text-transform: capitalize;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="chat-container">
            <div class="chat-header d-flex align-items-center">
                <div class="bot-avatar avatar me-2">
                    <i class="fas fa-robot"></i>
                </div>
                <div>
                    <h5 class="mb-0">Agentic Assistant</h5>
                    <small>Always ready to help</small>
                </div>
                <div class="ms-auto">
                    <button id="clearHistoryBtn" class="btn btn-sm btn-light">
                        <i class="fas fa-trash"></i> Clear History
                    </button>
                </div>
            </div>
            
            <div class="chat-body" id="chatBody">
                <!-- Bot welcome message -->
                <div class="message-wrapper">
                    <div class="bot-avatar avatar">
                        <i class="fas fa-robot"></i>
                    </div>
                    <div class="message bot-message">
                        <div class="message-content">
                            Hello! I'm your Agentic Assistant. I can help you schedule events, book meetings, and more. Try one of the suggested prompts below or type your own request.
                        </div>
                    </div>
                </div>
                
                <div class="typing-indicator" id="typingIndicator">
                    <div class="message-wrapper">
                        <div class="bot-avatar avatar">
                            <i class="fas fa-robot"></i>
                        </div>
                        <div class="message bot-message">
                            <div class="message-content">
                                <span></span>
                                <span></span>
                                <span></span>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
            
            <div class="chat-footer">
                <form id="messageForm">
                    <div class="input-group input-area">
                        <input type="text" id="userInput" class="form-control" placeholder="Type your message..." autocomplete="off">
                        <button type="button" class="emoji-btn">
                            <i class="far fa-smile"></i>
                        </button>
                        <button class="btn" id="sendButton" type="submit" style="background: linear-gradient(135deg, #6a11cb 0%, #2575fc 100%); color: white;">
                            <i class="fas fa-paper-plane"></i>
                        </button>
                    </div>
                </form>
            </div>
            
            <!-- Prompt Suggestions -->
            <div class="prompt-suggestions">
                <div class="suggestions-toggle" id="suggestionsToggle">
                    Example prompts <i class="fas fa-chevron-up"></i>
                </div>
                <div id="suggestionsList">
                    <div class="suggestion-item">
                        <div class="suggestion-text">Create me an meeting for the today at 5pm for the 60 minutes and title it as the board meeting</div>
                        <button class="try-btn">Try it</button>
                    </div>
                    <div class="suggestion-item">
                        <div class="suggestion-text">Create me an meeting for the 20th march at 5pm for the 90 minutes and title it as the hr meeting</div>
                        <button class="try-btn">Try it</button>
                    </div>
                    <div class="suggestion-item">
                        <div class="suggestion-text">Create me an meeting for the 8th march at 11 am for the 120 minutes and title it as the tech meeting</div>
                        <button class="try-btn">Try it</button>
                    </div>
                    <div class="suggestion-item">
                        <div class="suggestion-text">Delete the last booked event</div>
                        <button class="try-btn">Try it</button>
                    </div>
                    <div class="suggestion-item">
                        <div class="suggestion-text">Delete the event of 8th march 11am one</div>
                        <button class="try-btn">Try it</button>
                    </div>
                    <div class="suggestion-item">
                        <div class="suggestion-text">Give me today's schedule</div>
                        <button class="try-btn">Try it</button>
                    </div>
                    <div class="suggestion-item">
                        <div class="suggestion-text">Give me the available slots for today</div>
                        <button class="try-btn">Try it</button>
                    </div>
                    <div class="suggestion-item">
                        <div class="suggestion-text">Give me available slots of 15th march</div>
                        <button class="try-btn">Try it</button>
                    </div>
                    <div class="suggestion-item">
                        <div class="suggestion-text">Give me the schedule</div>
                        <button class="try-btn">Try it</button>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script src="https://cdnjs.cloudflare.com/ajax/libs/jquery/3.6.0/jquery.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/bootstrap/5.3.0/js/bootstrap.bundle.min.js"></script>
    <script>
        $(document).ready(function() {
            const chatBody = document.getElementById('chatBody');
            const messageForm = document.getElementById('messageForm');
            const userInput = document.getElementById('userInput');
            const typingIndicator = document.getElementById('typingIndicator');
            const sendButton = document.getElementById('sendButton');
            const suggestionsToggle = document.getElementById('suggestionsToggle');
            const suggestionsList = document.getElementById('suggestionsList');
            
            // Toggle suggestions
            suggestionsToggle.addEventListener('click', function() {
                this.classList.toggle('collapsed');
                suggestionsList.style.display = suggestionsList.style.display === 'none' ? 'block' : 'none';
            });

            suggestionsToggle.click();
            
            // Handle suggestion button clicks
            document.querySelectorAll('.try-btn').forEach(button => {
                button.addEventListener('click', function() {
                    const suggestionText = this.previousElementSibling.textContent;
                    userInput.value = suggestionText;
                    userInput.classList.add('input-highlight');
                    this.classList.add('button-press');
                    
                    setTimeout(() => {
                        userInput.classList.remove('input-highlight');
                        this.classList.remove('button-press');
                        sendButton.classList.add('button-press');
                        
                        setTimeout(() => {
                            sendButton.classList.remove('button-press');
                            messageForm.dispatchEvent(new Event('submit'));
                        }, 300);
                    }, 500);
                });
            });
            
            // Function to add a message to the chat
            function addMessage(message, isUser = false) {
                const messageWrapper = document.createElement('div');
                messageWrapper.className = 'message-wrapper';
                
                if (isUser) {
                    messageWrapper.innerHTML = `
                        <div class="ms-auto d-flex">
                            <div class="message user-message">
                                <div class="message-content">${message}</div>
                            </div>
                            <div class="user-avatar avatar ms-2">
                                <i class="fas fa-user"></i>
                            </div>
                        </div>
                    `;
                } else {
                    let messageClass = 'bot-message';
                    if (message.includes('success: true')) {
                        messageClass += ' success-message';
                    } else if (message.includes('success: false')) {
                        messageClass += ' error-message';
                    }
                    
                    messageWrapper.innerHTML = `
                        <div class="bot-avatar avatar">
                            <i class="fas fa-robot"></i>
                        </div>
                        <div class="message ${messageClass}">
                            <div class="message-content">${message}</div>
                        </div>
                    `;
                }
                
                // Insert before typing indicator
                chatBody.insertBefore(messageWrapper, typingIndicator);
                
                // Scroll to bottom
                chatBody.scrollTop = chatBody.scrollHeight;
            }
            
            // Function to show typing indicator
            function showTypingIndicator() {
                typingIndicator.style.display = 'block';
                chatBody.scrollTop = chatBody.scrollHeight;
            }
            
            // Function to hide typing indicator
            function hideTypingIndicator() {
                typingIndicator.style.display = 'none';
            }
            
            // Function to format date strings
            function formatDateTime(dateTimeStr) {
                const date = new Date(dateTimeStr);
                return date.toLocaleString('en-US', { 
                    weekday: 'short',
                    month: 'short', 
                    day: 'numeric',
                    hour: '2-digit', 
                    minute: '2-digit',
                    hour12: true
                });
            }
            
            // Function to format time slots
            function formatTimeSlots(slots) {
                let html = '<div class="mt-2 mb-1">Available time slots:</div>';
                html += '<div class="slot-grid">';
                
                slots.forEach(slot => {
                    const startTime = new Date(slot.start);
                    const endTime = new Date(slot.end);
                    const description = slot.description;

                    const formattedStart = `${String(startTime.getUTCHours()).padStart(2, '0')}:${String(startTime.getUTCMinutes()).padStart(2, '0')} UTC`;
                    const formattedEnd = `${String(endTime.getUTCHours()).padStart(2, '0')}:${String(endTime.getUTCMinutes()).padStart(2, '0')} UTC`;

                    console.log(formattedStart, formattedEnd);

                    
                    html += `
                        <div class="time-slot">
                            <div class="slot-time">${formattedStart} - ${formattedEnd}</div>
                            <div class="slot-desc">(${description})</div>
                        </div>
                    `;
                });
                
                html += '</div>';
                return html;
            }
            
            // Function to parse and format event data
            function formatResponse(response) {
                let formattedContent = '';
                
                // Extract the success status
                const isSuccess = response.success;
                
                // Format the message part
                if (typeof response.message === 'string') {
                    formattedContent = response.message;
                }
                
                // Check for available slots
                if (response.slots && Array.isArray(response.slots) && response.slots.length > 0) {
                    formattedContent += formatTimeSlots(response.slots);
                }

                // Check if message contains a nested JSON string (like the example you provided)
                if (typeof response.message === 'string' && response.message.includes("'message':")) {
                    try {
                        // Convert single quotes to double quotes for valid JSON parsing
                        let jsonStr = response.message.replace(/'/g, '"');
                        
                        // If the message itself is a JSON string
                        const parsedResponse = JSON.parse(jsonStr);
                        
                        // Use the parsed message and success values from inside the nested JSON
                        formattedContent = parsedResponse.message || formattedContent;
                        
                        // Check for slots in the parsed response
                        if (parsedResponse.slots && Array.isArray(parsedResponse.slots)) {
                            formattedContent += formatTimeSlots(parsedResponse.slots);
                        }
                        
                        // Override success status with the inner success value if available
                        if (parsedResponse.success !== undefined) {
                            isSuccess = parsedResponse.success;
                        }
                    } catch (e) {
                        console.log("Nested JSON parsing error:", e);
                        // Keep original message if parsing fails
                    }
                }
                
                // Check if message contains event data in string format
                if (typeof response.message === 'string') {
                    try {
                        // Try to parse as JSON if it looks like JSON
                        if (response.message.includes('[{') || response.message.startsWith('{')) {
                            // Convert single quotes to double quotes for valid JSON
                            let jsonStr = response.message.replace(/'/g, '"');
                            let events;
                            
                            if (jsonStr.includes('[{')) {
                                events = JSON.parse(jsonStr);
                            } else {
                                events = [JSON.parse(jsonStr)];
                            }
                            
                            // Format events if parsed successfully
                            if (Array.isArray(events)) {
                                events.forEach(event => {
                                    const startTime = event.start_time ? formatDateTime(event.start_time) : '';
                                    const endTime = event.end_time ? formatDateTime(event.end_time) : '';
                                    const description = event.description || 'Untitled Event';
                                    
                                    formattedContent += `
                                        <div class="event-card">
                                            <div class="event-title">${description}</div>
                                            <div class="event-time">
                                                <i class="far fa-clock"></i> ${startTime} - ${endTime}
                                            </div>
                                        </div>
                                    `;
                                });
                            }
                        }
                    } catch (e) {
                        console.log("Event parsing error:", e);
                        // Keep original message if parsing fails
                    }
                }
                
                // Format success status
                let successStatus = `<span class="text-${isSuccess ? 'success' : 'danger'}">success: ${isSuccess}</span>`;
                
                return `${formattedContent}<br><small class="text-muted">${successStatus}</small>`;
            }
            
            // Function to call the API
            function callApi(userMessage) {
                // Show typing indicator
                showTypingIndicator();
                
                // Make the real AJAX call to your API
                $.ajax({
                    url: 'http://20.197.36.75:5001/api/message',
                    type: 'POST',
                    contentType: 'application/json',
                    data: JSON.stringify({ message: userMessage }),
                    success: function(response) {
                        hideTypingIndicator();
                        addMessage(formatResponse(response));
                    },
                    error: function(error) {
                        hideTypingIndicator();
                        console.error("API Error:", error);
                        addMessage("Sorry, I encountered an error communicating with the server. Please try again later.", false);
                    }
                });
            }
            
            // Handle form submission
            messageForm.addEventListener('submit', function(e) {
                e.preventDefault();
                
                const message = userInput.value.trim();
                
                if (message) {
                    // Add user message to chat
                    addMessage(message, true);
                    
                    // Call API
                    callApi(message);
                    
                    // Clear input
                    userInput.value = '';
                }
            });
            
            // Focus input on page load
            userInput.focus();

            $("#clearHistoryBtn").click(function() {
                // Show a confirmation dialog
                if (confirm("Are you sure you want to clear the chat history?")) {
                    // Show typing indicator while API call is in progress
                    showTypingIndicator();
                    
                    // Call the clear history API
                    $.ajax({
                        url: 'http://20.197.36.75:5001/api/clear-history',
                        type: 'GET',
                        success: function(response) {
                            // Hide typing indicator
                            hideTypingIndicator();
                            
                            // Clear all messages from the UI except the welcome message
                            $("#chatBody").find(".message-wrapper:not(:first-child)").remove();
                            
                            // Add confirmation message
                            addMessage("Chat history has been cleared successfully.", false);
                        },
                        error: function(error) {
                            // Hide typing indicator
                            hideTypingIndicator();
                            
                            // Show error message
                            addMessage("Failed to clear chat history. Please try again later.", false);
                            console.error("Clear history error:", error);
                        }
                    });
                }
            });
        });
    </script>
</body>
</html>