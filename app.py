from flask import Flask, request, jsonify, session
import openai
import requests
from flask_cors import CORS
from flask_session import Session
import os

app = Flask(__name__)
CORS(app)

# Configure session management
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'mysecretkey')  # Ensure to set a secret key for your session
app.config['SESSION_TYPE'] = 'filesystem'  # This stores sessions in the filesystem; for production, consider other options
Session(app)

openai.api_key = os.getenv("OPENAI_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

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

def chat_with_GPT(prompt, knowledge_base, chat_history):
    try:
        # Combine chat history with the new prompt
        messages = [
            {"role": "system", "content": "You are a friendly consultant for an online design project service. Only answer questions based on the provided knowledge base. If the answer is not in the knowledge base, ask the user to leave their email for the expert, unless the question is completely out of our product topic. Be a little humorous. Shorten very long answers if possible. Also, do not use headers and paragraphs, use just plain text"},
            {"role": "system", "content": f"Knowledge base: {knowledge_base}"}
        ] + chat_history + [{"role": "user", "content": prompt}]
        
        response = openai.ChatCompletion.create(
            model="gpt-4o",  # Use an appropriate model name
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
    data = request.json
    prompt = data['prompt']

    # Initialize chat history in session if not present
    if 'chat_history' not in session:
        session['chat_history'] = []

    # Log and send user's prompt to Telegram
    print(f"Received prompt: {prompt}")
    send_message_to_telegram(f"*🤔 Client:* {prompt}")

    # Get chat history from session
    chat_history = session['chat_history']

    # Generate response using chat_with_GPT
    response = chat_with_GPT(prompt, knowledge_base, chat_history)

    print(f"Response: {response}")
    send_message_to_telegram(f"*🤖 Bot:* {response}")

    # Update chat history
    chat_history.append({"role": "user", "content": prompt})
    chat_history.append({"role": "assistant", "content": response})
    session['chat_history'] = chat_history

    return jsonify({'response': response})

if __name__ == "__main__":
    app.run(debug=True)
