from flask import Flask, request, jsonify, session
import openai
import requests
from flask_cors import CORS
import os
from datetime import timedelta

# Initialize Flask application
app = Flask(__name__)

# CORS configuration to allow credentials (cookies) to be sent
CORS(app, supports_credentials=True)

# Configuration
app.secret_key = os.getenv('FLASK_SECRET_KEY')
openai.api_key = os.getenv("OPENAI_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# Configure session settings
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'  # Lax is usually a good balance for cross-origin requests
app.config['SESSION_COOKIE_SECURE'] = True  # Set to False for local testing; True for production with HTTPS
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=30)  # Session timeout
app.config['SESSION_TYPE'] = 'filesystem'  # Store sessions in the filesystem

def load_knowledge_base(file_path):
    with open(file_path, 'r', encoding='utf-8') as file:
        knowledge_base = file.read()
    return knowledge_base

def send_message_to_telegram(message):
    url = f'https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage'
    payload = {
        'chat_id': TELEGRAM_CHAT_ID,
        'text': message,
        'parse_mode': 'Markdown'
    }
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
    except requests.exceptions.HTTPError as errh:
        print(f"Http Error: {errh}")
    except requests.exceptions.ConnectionError as errc:
        print(f"Error Connecting: {errc}")
    except requests.exceptions.Timeout as errt:
        print(f"Timeout Error: {errt}")
    except requests.exceptions.RequestException as err:
        print(f"Oops: Something Else {err}")

def chat_with_GPT(prompt, knowledge_base, history):
    try:
        messages = [
            {"role": "system", "content": "You are a friendly consultant for an online design project service. Only answer questions based on the provided knowledge base. If the answer is not in the knowledge base, ask the user to leave their email for the expert, unless the question is completely out of our product topic. Be a little humorous. Shorten very long answers if possible. Also, do not use headers and paragraphs, use just plain text"},
            {"role": "system", "content": f"Knowledge base: {knowledge_base}"}
        ]

        # Include the conversation history in the message to the model
        messages.extend(history)
        messages.append({"role": "user", "content": prompt})

        response = openai.ChatCompletion.create(
            model="gpt-4o",
            messages=messages
        )
        return response.choices[0].message['content'].strip()
    except Exception as e:
        print(f"Error communicating with OpenAI: {e}")
        return "I'm sorry, but I couldn't process your request at this time. Please try again later."

knowledge_base = load_knowledge_base('knowledge.txt')

@app.route('/ping', methods=['GET'])
def ping():
    return jsonify({'message': 'Server is awake'}), 200

@app.route('/chat', methods=['POST'])
def chat():
    """Main chat endpoint to handle user prompts and generate responses."""
    data = request.json
    prompt = data['prompt']

    # Debugging: Print session details and cookie info
    print(f"Cookies: {request.cookies}")
    print(f"Session before processing: {session.get('history', [])}")

    # Mark the session as permanent to apply the session lifetime
    session.permanent = True

    # Initialize the session history if it doesn't exist
    if 'history' not in session:
        session['history'] = []

    # Append the user prompt to the session history
    session['history'].append({"role": "user", "content": prompt})
    session.modified = True  # Ensure session is marked as modified

    # Log and send user's prompt to Telegram
    print(f"Received prompt: {prompt}")
    send_message_to_telegram(f"*🤔 Client:* {prompt}")

    # Generate a response using OpenAI's API
    response = chat_with_GPT(prompt, knowledge_base, session['history'])

    # Append the bot's response to the session history
    session['history'].append({"role": "assistant", "content": response})
    session.modified = True  # Ensure session is marked as modified

    # Debugging: Print session details
    print(f"Session after processing: {session.get('history', [])}")

    print(f"Response: {response}")
    send_message_to_telegram(f"*🤖 Bot:* {response}")

    return jsonify({'response': response})

if __name__ == "__main__":
    app.run(debug=True)
