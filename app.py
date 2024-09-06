from flask import Flask, request, jsonify
import openai
import requests
from flask_cors import CORS
import os
from sqlalchemy import create_engine, Column, Integer, String, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

app = Flask(__name__)
CORS(app)

# Set up SQLite database
DATABASE_URL = "sqlite:///chatbot.db"
engine = create_engine(DATABASE_URL)
Base = declarative_base()

# Define a session for database interactions
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Database Model for storing chat history
class ChatHistory(Base):
    __tablename__ = "chat_histories"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, index=True)
    role = Column(String)  # 'user' or 'assistant'
    content = Column(Text)

# Create the database table
Base.metadata.create_all(bind=engine)

# Fetch API keys and tokens from environment variables
openai.api_key = os.getenv("OPENAI_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# Function to load the knowledge base
def load_knowledge_base(file_path):
    with open(file_path, 'r', encoding='utf-8') as file:
        knowledge_base = file.read()
    return knowledge_base

# Function to send messages to Telegram
def send_message_to_telegram(message):
    url = f'https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage'
    payload = {
        'chat_id': TELEGRAM_CHAT_ID,
        'text': message,
        'parse_mode': 'Markdown'  # Allows for text formatting
    }
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()  # Raises an HTTPError if the HTTP request returned an unsuccessful status code
    except requests.exceptions.HTTPError as errh:
        print(f"Http Error: {errh}")
    except requests.exceptions.ConnectionError as errc:
        print(f"Error Connecting: {errc}")
    except requests.exceptions.Timeout as errt:
        print(f"Timeout Error: {errt}")
    except requests.exceptions.RequestException as err:
        print(f"Oops: Something Else {err}")

# Function to communicate with GPT-4 using chat history
def chat_with_GPT(prompt, history):
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4",  # Use an appropriate model name
            messages=history + [{"role": "user", "content": prompt}]
        )
        return response.choices[0].message['content'].strip()
    except Exception as e:
        print(f"Error communicating with OpenAI: {e}")
        return "I'm sorry, but I couldn't process your request at this time. Please try again later."

# Function to load chat history from the database
def load_session_history(user_id):
    db = SessionLocal()
    history = db.query(ChatHistory).filter_by(user_id=user_id).all()
    db.close()
    
    # Format history into a list of dictionaries for GPT input
    formatted_history = [{"role": entry.role, "content": entry.content} for entry in history]
    
    if not formatted_history:
        formatted_history = [
            {"role": "system", "content": "You are a friendly consultant for an online design project service."},
            {"role": "system", "content": f"Knowledge base: {knowledge_base}"}
        ]
    return formatted_history

# Function to save chat history to the database
def save_message_to_db(user_id, role, content):
    db = SessionLocal()
    chat_message = ChatHistory(user_id=user_id, role=role, content=content)
    db.add(chat_message)
    db.commit()
    db.close()

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
    history = load_session_history(user_id)

    # Append the user's message to the history in the database
    save_message_to_db(user_id, "user", prompt)

    # Send the user's message to Telegram for logging
    send_message_to_telegram(f"*Client:* {prompt}")

    # Get the GPT response with context (history)
    response = chat_with_GPT(prompt, history)

    # Save GPT's response to the database
    save_message_to_db(user_id, "assistant", response)

    # Send the bot's response to Telegram for logging
    send_message_to_telegram(f"*Bot:* {response}")

    # Return the bot's response to the frontend
    return jsonify({'response': response})

# Run the application
if __name__ == "__main__":
    app.run(debug=True)
