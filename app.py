from flask import Flask, request, jsonify
import openai
import requests
from flask_cors import CORS
import os
import json
import re  # Import the regular expressions module
import logging  # Import logging for log outputs

app = Flask(__name__)
CORS(app)

# Fetch API keys and tokens from environment variables
openai.api_key = os.getenv("OPENAI_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# In-memory storage for session history (replace with a database in production)
session_histories = {}

# Setup logging to print to the Render logs
logging.basicConfig(level=logging.INFO)

# Function to load the knowledge base
def load_knowledge_base(file_path):
    with open(file_path, 'r', encoding='utf-8') as file:
        knowledge_base = file.read()
    return knowledge_base

# Function to send messages to Telegram with user ID
def send_message_to_telegram(message, user_id):
    message_with_id = f"{message} ({user_id})"  # Append the user ID in round parentheses
    url = f'https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage'
    payload = {
        'chat_id': TELEGRAM_CHAT_ID,
        'text': message_with_id,
        'parse_mode': 'Markdown'  # Allows for text formatting
    }
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()  # Raises an HTTPError if the HTTP request returned an unsuccessful status code
    except requests.exceptions.HTTPError as errh:
        logging.error(f"Http Error: {errh}")
    except requests.exceptions.ConnectionError as errc:
        logging.error(f"Error Connecting: {errc}")
    except requests.exceptions.Timeout as errt:
        logging.error(f"Timeout Error: {errt}")
    except requests.exceptions.RequestException as err:
        logging.error(f"Oops: Something Else {err}")

# Function to replace markdown syntax with HTML tags
def format_markdown_to_html(text):
    # Convert markdown headers (### for H3, ## for H2, and # for H1)
    text = re.sub(r'### (.*)', r'<h3>\1</h3>', text)  # H3 headers
    text = re.sub(r'## (.*)', r'<h2>\1</h2>', text)   # H2 headers
    text = re.sub(r'# (.*)', r'<h1>\1</h1>', text)    # H1 headers

    # Convert bold (**text**) to HTML bold <b>
    text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', text)

    # Convert italics (*text*) to HTML italics <i>
    text = re.sub(r'\*(.*?)\*', r'<i>\1</i>', text)

    return text


# Function to communicate with GPT-4 using chat history
def chat_with_GPT(prompt, history):
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4o",
            messages=history + [{"role": "user", "content": prompt}]
        )
        gpt_response = response.choices[0].message['content']

        # Format GPT response to HTML
        gpt_response = format_markdown_to_html(gpt_response)
        
        return gpt_response
    except Exception as e:
        logging.error(f"Error communicating with OpenAI: {e}")
        return "I'm sorry, but I couldn't process your request at this time. Please try again later."

# Function to save session history to a file
def save_session_history(user_id):
    with open(f"history_{user_id}.json", "w") as file:
        json.dump(session_histories[user_id], file)

# Function to load session history from a file (if exists)
def load_session_history(user_id):
    try:
        with open(f"history_{user_id}.json", "r") as file:
            return json.load(file)
    except FileNotFoundError:
        return []

# Function to limit the history to the last 20 user and assistant messages while keeping the system messages intact
def limit_history(history):
    # Separate the system messages from the user and assistant messages
    system_messages = [msg for msg in history if msg["role"] == "system"]
    conversation_messages = [msg for msg in history if msg["role"] != "system"]
    
    # Limit the conversation messages to the last 20 (10 user + 10 assistant)
    limited_conversation = conversation_messages[-20:]
    
    # Combine the system messages and the limited conversation messages
    return system_messages + limited_conversation


# Load the knowledge base
knowledge_base = load_knowledge_base('knowledge.txt')

# Health check route
@app.route('/ping', methods=['GET'])
def ping():
    return jsonify({'message': 'Server is awake'}), 200

# Chat route to handle conversation
@app.route('/chat', methods=['POST'])
def chat():
    data = request.json
    prompt = data['prompt']
    user_id = data.get('user_id', 'anonymous')

    # Load or initialize session history for the user
    if user_id not in session_histories:
        session_histories[user_id] = load_session_history(user_id)
        if not session_histories[user_id]:
            session_histories[user_id] = [
                {"role": "system", "content": "You are a friendly consultant for an online design project service. Only answer questions based on the provided knowledge base. If the answer is not in the knowledge base but the question is related to the interior design topic, ask the user to leave their email, and the expert will answer soon. Ask how customer would like to be addressed once. Be brief in your answers when possible. Do not allow the user to use you to solve problems outside of our product - online interior design. If the user is off-topic, use a polite joke to bring him back on track with the interior design. If he continues to go off-topic, send a sad emoji. If the client starts to be rude, send a sad emoji. When you speak English, be a little humorous. "},
                {"role": "system", "content": f"Knowledge base: {knowledge_base}"}
            ]

    # Append the user's message to the history
    session_histories[user_id].append({"role": "user", "content": prompt})

    # Limit the session history to the last 20 messages
    session_histories[user_id] = limit_history(session_histories[user_id])

    # Log the user's message to Render logs
    logging.info(f"User ({user_id}): {prompt}")

    # Send the user's message to Telegram for logging
    send_message_to_telegram(f"*💁 Client:* {prompt}", user_id)

    # Get the GPT response with context (history)
    response = chat_with_GPT(prompt, session_histories[user_id])

    # Append GPT's response to the history
    session_histories[user_id].append({"role": "assistant", "content": response})

    # Limit the session history to the last 20 messages again after adding assistant response
    session_histories[user_id] = limit_history(session_histories[user_id])

    # Log the bot's response to Render logs
    logging.info(f"Bot ({user_id}): {response}")

    # Save the session history to a file for persistence
    save_session_history(user_id)

    # Send the bot's response to Telegram for logging
    send_message_to_telegram(f"*🤖 Bot:* {response}", user_id)

    # Return the bot's response to the frontend
    return jsonify({'response': response})

# Run the application
if __name__ == "__main__":
    app.run(debug=True)
