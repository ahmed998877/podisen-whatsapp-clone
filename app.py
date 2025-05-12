from flask import Flask, request, jsonify
import os
import requests
import json
from google import genai
from google.genai import types
import time
import logging
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("whatsapp_bot.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# WhatsApp API configuration
WHATSAPP_TOKEN = os.environ.get("WHATSAPP_TOKEN")
if not WHATSAPP_TOKEN:
    raise ValueError("WHATSAPP_TOKEN environment variable is not set")
PHONE_NUMBER_ID = os.environ.get("PHONE_NUMBER_ID")
if not PHONE_NUMBER_ID:
    raise ValueError("PHONE_NUMBER_ID environment variable is not set")

WHATSAPP_URL = os.environ.get("WHATSAPP_URL", "https://graph.facebook.com/v17.0/PHONE_NUMBER_ID/messages")
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN")
if not VERIFY_TOKEN:
    raise ValueError("VERIFY_TOKEN environment variable is not set")

# GCP configuration
PROJECT_ID = os.environ.get("PROJECT_ID")
LOCATION = os.environ.get("LOCATION")
MODEL_ID = os.environ.get("MODEL_ID")

# Get your name
YOUR_NAME = os.environ.get("YOUR_NAME")
if not YOUR_NAME:
    raise ValueError("YOUR_NAME environment variable is not set")

# Message history cache to maintain context
conversation_history = {}
MAX_HISTORY_LENGTH = int(os.environ.get("MAX_HISTORY_LENGTH", "10"))

def initialize_vertexai():
    """Initialize Vertex AI client"""
    try:
        client = genai.Client(
            vertexai=True,
            project=PROJECT_ID,
            location=LOCATION,
        )
        logger.info("Vertex AI initialized successfully")
        return client
    except Exception as e:
        logger.error(f"Failed to initialize Vertex AI: {str(e)}")
        raise

def generate_response(user_id, message_text):
    """Generate a response using the fine-tuned model"""
    try:
        # Get or initialize conversation history
        if user_id not in conversation_history:
            conversation_history[user_id] = []
        
        # Create message history
        contents = []
        
        # Add conversation history
        for entry in conversation_history[user_id]:
            contents.append(
                types.Content(
                    role=entry["role"],
                    parts=[types.Part(text=entry["text"])]
                )
            )
        
        # Add the current message
        contents.append(
            types.Content(
                role="user",
                parts=[types.Part(text=message_text)]
            )
        )
        
        # Get the client
        client = initialize_vertexai()
        
        # Generate response
        model = f"projects/{PROJECT_ID}/locations/{LOCATION}/endpoints/{MODEL_ID}"
        logger.info(f"Using model: {model}")
        
        response = client.models.generate_content(
            model=model,
            contents=contents,
            config=types.GenerateContentConfig(
                temperature=1,
                top_p=0.95,
                max_output_tokens=8192,
                response_modalities=["TEXT"],
                safety_settings=[
                    types.SafetySetting(
                        category="HARM_CATEGORY_HATE_SPEECH",
                        threshold="OFF"
                    ),
                    types.SafetySetting(
                        category="HARM_CATEGORY_DANGEROUS_CONTENT",
                        threshold="OFF"
                    ),
                    types.SafetySetting(
                        category="HARM_CATEGORY_SEXUALLY_EXPLICIT",
                        threshold="OFF"
                    ),
                    types.SafetySetting(
                        category="HARM_CATEGORY_HARASSMENT",
                        threshold="OFF"
                    )],
                    system_instruction = [types.Part.from_text(text=f"""Your name is {YOUR_NAME}. You are a helpful friend. Just keep the conversation going with a casual tone.""")]
                
            )
        )
        
        response_text = response.text
        logger.info(f"Response received: {response_text}")
        
        # Update conversation history
        conversation_history[user_id].append({"role": "user", "text": message_text})
        conversation_history[user_id].append({"role": "model", "text": response_text})
        
        # Limit history length
        if len(conversation_history[user_id]) > MAX_HISTORY_LENGTH * 2:
            conversation_history[user_id] = conversation_history[user_id][-MAX_HISTORY_LENGTH * 2:]
        
        return response_text
    
    except Exception as e:
        logger.error(f"Error generating response: {str(e)}")
        logger.error(f"Error details: {type(e).__name__}")
        if hasattr(e, 'response'):
            logger.error(f"Response status: {e.response.status_code}")
            logger.error(f"Response body: {e.response.text}")
        return "Sorry, I'm having trouble generating a response right now. Please try again later."

def send_whatsapp_message(phone_number, message):
    """Send a message to WhatsApp user"""
    try:
        headers = {
            "Authorization": f"Bearer {WHATSAPP_TOKEN}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": phone_number,
            "type": "text",
            "text": {
                "body": message
            }
        }
        
        response = requests.post(
            WHATSAPP_URL,
            headers=headers,
            data=json.dumps(payload)
        )
        
        if response.status_code == 200:
            logger.info(f"Message sent successfully to {phone_number}")
            return True
        else:
            logger.error(f"Failed to send message: {response.text}")
            return False
            
    except Exception as e:
        logger.error(f"Error sending WhatsApp message: {str(e)}")
        return False

def send_typing_indicator(phone_number, message_id):
    """Send a typing indicator to WhatsApp user"""
    try:
        headers = {
            "Authorization": f"Bearer {WHATSAPP_TOKEN}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "messaging_product": "whatsapp",
            "status": "read",
            "message_id": message_id,
            "typing_indicator": {
                "type": "text"
            }
        }
        
        response = requests.post(
            WHATSAPP_URL,
            headers=headers,
            data=json.dumps(payload)
        )
        
        if response.status_code == 200:
            logger.info(f"Typing indicator sent successfully to {phone_number}")
            return True
        else:
            logger.error(f"Failed to send typing indicator: {response.text}")
            return False
            
    except Exception as e:
        logger.error(f"Error sending typing indicator: {str(e)}")
        return False

@app.route("/webhook", methods=["GET"])
def verify_webhook():
    """Verify the webhook endpoint with WhatsApp"""
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")
    
    if mode and token:
        if mode == "subscribe" and token == VERIFY_TOKEN:
            logger.info("Webhook verified")
            return challenge, 200
        else:
            logger.warning("Webhook verification failed")
            return "Verification failed", 403
    
    return "Invalid request", 400

@app.route("/webhook", methods=["POST"])
def webhook():
    """Handle incoming WhatsApp messages"""
    try:
        data = request.get_json()
        logger.info(f"Received webhook data: {json.dumps(data)}")
        
        if not data:
            logger.warning("Received empty webhook data")
            return "No data received", 400
            
        if "object" not in data or data["object"] != "whatsapp_business_account":
            logger.warning("Invalid webhook object type")
            return "Invalid webhook object", 400
            
        if "entry" not in data or not data["entry"]:
            logger.warning("No entries in webhook data")
            return "No entries found", 400
            
        for entry in data["entry"]:
            if "changes" not in entry or not entry["changes"]:
                continue
                
            for change in entry["changes"]:
                if "value" not in change or "messages" not in change["value"]:
                    continue
                    
                for message in change["value"]["messages"]:
                    if message["type"] != "text":
                        continue
                        
                    sender_id = message["from"]
                    message_text = message["text"]["body"]
                    message_id = message["id"]
                    
                    # Send typing indicator
                    if not send_typing_indicator(sender_id, message_id):
                        logger.error(f"Failed to send typing indicator to {sender_id}")
                    
                    # Generate a response
                    response_text = generate_response(sender_id, message_text)
                    
                    # Send the response back
                    if not send_whatsapp_message(sender_id, response_text):
                        logger.error(f"Failed to send response to {sender_id}")
        
        return "OK", 200
    
    except Exception as e:
        logger.error(f"Error processing webhook: {str(e)}", exc_info=True)
        return "Error processing webhook", 500

@app.route("/", methods=["GET"])
def health_check():
    """Health check endpoint"""
    return "WhatsApp Bot is running!", 200

if __name__ == "__main__":
    # Start the Flask app
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=False)