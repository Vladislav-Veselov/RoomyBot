from flask import Flask, request, jsonify, session
import openai
import requests
from flask_cors import CORS
import os
import logging

# Initialize the Flask application
app = Flask(__name__)
CORS(app)

# Set the secret key for session management
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'your_default_secret_key')  # Replace with a secure secret key for production

# Set OpenAI and Telegram API keys from environment variables
openai.api_key = os.getenv("OPENAI_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# Set up logging
logging.basicConfig(level=logging.DEBUG)  # Set to DEBUG to capture all messages
logger = logging.getLogger(__name__)

def load_knowledge_base(file_path):
    """Load knowledge base from a file."""
    logger.debug(f"Loading knowledge base from {file_path}")
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            knowledge_base = file.read()
        logger.debug("Knowledge base loaded successfully")
        return knowledge_base
    except Exception as e:
        logger.error(f"Error loading knowledge base: {e}")
        return ""

def send_message_to_telegram(message):
    """Send a message to a predefined Telegram chat using a bot."""
    logger.debug(f"Sending message to Telegram: {message}")
    url = f'https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage'
    payload = {
        'chat_id': TELEGRAM_CHAT_ID,
        'text': message,
        'parse_mode': 'Markdown'
    }
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        logger.debug("Message sent to Telegram successfully")
    except requests.exceptions.HTTPError as errh:
        logger.error(f"Http Error: {errh}")
    except requests.exceptions.ConnectionError as errc:
        logger.error(f"Error Connecting: {errc}")
    except requests.exceptions.Timeout as errt:
        logger.error(f"Timeout Error: {errt}")
    except requests.exceptions.RequestException as err:
        logger.error(f"Oops: Something Else {err}")

def chat_with_GPT(prompt, knowledge_base, history):
    """Communicate with OpenAI's GPT model using the session's conversation history."""
    logger.debug("Calling OpenAI GPT model")
    try:
        messages = [
            {"role": "system", "content": "You are a friendly consultant for an online design project service. Only answer questions based on the provided knowledge base. If the answer is not in the knowledge base, ask the user to leave their email for the expert, unless the question is completely out of our product topic. Be a little humorous. Shorten very long answers if possible. Also, do not use headers and paragraphs, use just plain text"},
            {"role": "system", "content": f"Knowledge base: {knowledge_base}"}
        ]

        # Include the conversation history in the message to the model
        messages.extend(history)
        messages.append({"role": "user", "content": prompt})

        response = openai.ChatCompletion.create(
            model="gpt-4",  # Use an appropriate model name
            messages=messages
        )
        logger.debug("Received response from OpenAI GPT model")
        return response.choices[0].message['content'].strip()
    except Exception as e:
        logger.error(f"Error communicating with OpenAI: {e}")
        return "I'm sorry, but I couldn't process your request at this time. Please try again later."

# Load the knowledge base once at startup
knowledge_base = load_knowledge_base('knowledge.txt')

@app.route('/ping', methods=['GET'])
def ping():
    """Health check endpoint to ensure the server is running."""
    logger.debug("Ping request received")
    return jsonify({'message': 'Server is awake'}), 200

@app.route('/chat', methods=['POST'])
def chat():
    """Main chat endpoint to handle user prompts and generate responses."""
    data = request.json
    prompt = data.get('prompt', '')

    if not prompt:
        logger.warning("No prompt provided in request")
        return jsonify({'response': 'No prompt provided'}), 400

    # Initialize the session history if it doesn't exist
    if 'history' not in session:
        session['history'] = []
        logger.debug("Initialized new session history")

    # Append the user prompt to the session history
    logger.debug(f"User prompt received: {prompt}")
    session['history'].append({"role": "user", "content": prompt})

    # Log and send user's prompt to Telegram
    logger.info(f"User prompt: {prompt}")
    send_message_to_telegram(f"*🤔 Client:* {prompt}")

    # Generate a response using OpenAI's API
    response = chat_with_GPT(prompt, knowledge_base, session['history'])

    # Append the bot's response to the session history
    session['history'].append({"role": "assistant", "content": response})

    logger.info(f"Bot response: {response}")
    send_message_to_telegram(f"*🤖 Bot:* {response}")

    return jsonify({'response': response})

if __name__ == "__main__":
    logger.debug("Starting Flask application")
    app.run(debug=True)
