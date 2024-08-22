from flask import Flask, request, jsonify
import openai
import requests
from flask_cors import CORS
import os

app = Flask(__name__)
CORS(app)

# Replace with your actual OpenAI API key and Telegram credentials
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
        print(f"OOps: Something Else {err}")

def chat_with_GPT(prompt, knowledge_base):
    response = openai.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a friendly consultant for an online design project service. Only answer questions based on the provided knowledge base. If the answer is not in the knowledge base, ask user to leave his e-mail, and the expert will answer soon. Don't forget to ask how the client would like to be addressed"},
            {"role": "system", "content": f"Knowledge base: {knowledge_base}"},
            {"role": "user", "content": prompt}
        ]
    )
    return response.choices[0].message.content.strip()

knowledge_base = load_knowledge_base('knowledge.txt')

@app.route('/chat', methods=['POST'])
def chat():
    data = request.json
    prompt = data['prompt']

    # Log and send user's prompt to Telegram
    print(f"Received prompt: {prompt}")
    send_message_to_telegram(f"*Client:* {prompt}")

    # Get the response from GPT
    response = chat_with_GPT(prompt, knowledge_base)

    # Log and send bot's response to Telegram
    print(f"Response: {response}")
    send_message_to_telegram(f"*Bot:* {response}")

    return jsonify({'response': response})

if __name__ == "__main__":
    app.run(debug=True)
