import os
import re
import json
import time
import glob
import argparse
from collections import defaultdict
from datetime import datetime
from typing import List, Dict, Tuple, Any
from google import genai
from google.genai import types
from tqdm import tqdm
import logging
import random
from dotenv import load_dotenv

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("whatsapp_processing.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class WhatsAppProcessor:
    def __init__(self, your_name: str, api_key: str = None):
        """
        Initialize the WhatsApp chat processor
        
        Args:
            your_name (str): Your name in the chats (to identify which messages are yours)
            api_key (str, optional): Gemini API key. Defaults to environment variable.
        """
        self.your_name = your_name
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
        self.client = genai.Client(api_key=self.api_key)
        self.model = "gemini-2.0-flash"
        
        # Rate limit tracking
        self.request_timestamps = []
        self.max_rpm = 14  # Setting slightly below actual limit for safety
        self.requests_today = 0
        self.max_rpd = 1400  # Setting slightly below actual limit for safety
        
        # Make sure directories exist
        os.makedirs("whatsapp_data/processed", exist_ok=True)
        
    def _respect_rate_limit(self):
        """Respect the Gemini API rate limits"""
        # Check and enforce daily limit
        current_date = datetime.now().date()
        # Reset daily counter if it's a new day
        if hasattr(self, 'last_request_date') and self.last_request_date != current_date:
            self.requests_today = 0
        self.last_request_date = current_date
        
        if self.requests_today >= self.max_rpd:
            logger.warning(f"Daily request limit reached ({self.max_rpd}). Waiting until tomorrow.")
            # Calculate seconds until midnight
            now = datetime.now()
            tomorrow = datetime(now.year, now.month, now.day) + timedelta(days=1)
            seconds_to_wait = (tomorrow - now).total_seconds() + 10  # Add 10 seconds buffer
            time.sleep(seconds_to_wait)
            self.requests_today = 0
            return
        
        # Check and enforce per-minute limit
        current_time = time.time()
        # Remove timestamps older than 1 minute
        self.request_timestamps = [ts for ts in self.request_timestamps if current_time - ts < 60]
        
        if len(self.request_timestamps) >= self.max_rpm:
            # Wait until we're under the rate limit
            sleep_time = 60 - (current_time - self.request_timestamps[0]) + 1  # Add 1 second buffer
            logger.info(f"Rate limit approaching. Waiting {sleep_time:.2f} seconds")
            time.sleep(sleep_time)
        
        # Add current timestamp and increment counters
        self.request_timestamps.append(time.time())
        self.requests_today += 1

    def parse_raw_chat(self, file_path: str) -> List[Dict]:
        """
        Parse a raw WhatsApp chat export file
        
        Args:
            file_path (str): Path to the chat export file
            
        Returns:
            List[Dict]: List of message dictionaries with timestamp, sender, and text
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except UnicodeDecodeError:
            # Try another common encoding
            with open(file_path, 'r', encoding='latin-1') as f:
                content = f.read()
                
        # WhatsApp date format: DD/MM/YYYY, HH:MM - Sender: Message
        # or: DD/MM/YYYY, HH:MM am/pm - Sender: Message
        pattern = r'(\d{1,2}/\d{1,2}/\d{2,4},\s\d{1,2}:\d{2}(?:\s?[ap]m)?)\s-\s([^:]+):\s(.*)'
        
        # Split by new message (starting with date)
        messages = []
        current_message = None
        
        for line in content.split('\n'):
            match = re.match(pattern, line)
            if match:
                if current_message:
                    messages.append(current_message)
                
                timestamp_str, sender, text = match.groups()
                # Clean up sender name
                sender = sender.strip()
                
                try:
                    # Try to parse timestamp in various formats
                    formats = [
                        '%d/%m/%Y, %I:%M %p',  # 12-hour with AM/PM
                        '%d/%m/%Y, %H:%M',     # 24-hour
                        '%m/%d/%Y, %I:%M %p',  # US format 12-hour
                        '%m/%d/%Y, %H:%M',     # US format 24-hour
                    ]
                    
                    timestamp = None
                    for fmt in formats:
                        try:
                            timestamp = datetime.strptime(timestamp_str, fmt)
                            break
                        except ValueError:
                            continue
                    
                    if timestamp is None:
                        # Fallback if no format worked
                        timestamp = datetime.now()
                        logger.warning(f"Could not parse timestamp: {timestamp_str}, using current time")
                    
                except Exception as e:
                    logger.error(f"Error parsing timestamp: {timestamp_str}, {str(e)}")
                    timestamp = datetime.now()
                
                current_message = {
                    'timestamp': timestamp,
                    'sender': sender,
                    'text': text
                }
            elif current_message:
                # Continuation of previous message
                current_message['text'] += f"\n{line}"
        
        # Add the last message
        if current_message:
            messages.append(current_message)
            
        return messages

    def group_messages_by_conversation(self, messages: List[Dict], max_time_diff: int = 3600) -> List[List[Dict]]:
        """
        Group messages into conversations based on time gaps
        
        Args:
            messages (List[Dict]): List of message dictionaries
            max_time_diff (int): Maximum time difference in seconds between messages in the same conversation
            
        Returns:
            List[List[Dict]]: List of conversations, each containing a list of message dictionaries
        """
        if not messages:
            return []
            
        conversations = []
        current_conversation = [messages[0]]
        
        for i in range(1, len(messages)):
            time_diff = (messages[i]['timestamp'] - messages[i-1]['timestamp']).total_seconds()
            
            # If time difference is greater than threshold, start a new conversation
            if time_diff > max_time_diff:
                if len(current_conversation) > 1:  # Only keep conversations with at least 2 messages
                    conversations.append(current_conversation)
                current_conversation = []
                
            current_conversation.append(messages[i])
        
        # Add the last conversation if it has at least 2 messages
        if len(current_conversation) > 1:
            conversations.append(current_conversation)
            
        return conversations

    def format_conversation_for_llm(self, conversation: List[Dict]) -> str:
        """
        Format a conversation for input to the LLM
        
        Args:
            conversation (List[Dict]): List of message dictionaries in a conversation
            
        Returns:
            str: Formatted conversation string
        """
        formatted = "Convert this WhatsApp conversation into a training example for an LLM fine-tuning dataset. "
        formatted += f"Messages from '{self.your_name}' should be assigned the 'model' role, and messages from others should be the 'user' role.\n\n"
        formatted += "Format the output as a valid JSON object following this structure:\n"
        formatted += '{\n  "contents": [\n    {"role": "user/model", "parts": [{"text": "message content"}]},\n    ...\n  ]\n}\n\n'
        formatted += "Combine sequential messages from the same speaker with a line break between them. Preserve all emojis, slang, and casual language. Output only valid JSON, no explanations.\n\n"
        formatted += "CONVERSATION START:\n"
        
        for msg in conversation:
            timestamp_str = msg['timestamp'].strftime('%I:%M %p')
            formatted += f"{timestamp_str} - {msg['sender']}: {msg['text']}\n"
        
        formatted += "CONVERSATION END\n"
        return formatted

    def process_conversation_with_llm(self, conversation_text: str) -> Dict:
        """
        Process a conversation with Gemini to convert it to the training format
        
        Args:
            conversation_text (str): Formatted conversation text
            
        Returns:
            Dict: Processed conversation in the training format
        """
        self._respect_rate_limit()
        
        try:
            contents = [
                types.Content(
                    role="user",
                    parts=[types.Part.from_text(text=conversation_text)],
                )
            ]
            
            generate_content_config = types.GenerateContentConfig(
                response_mime_type="application/json",
            )
            
            response = self.client.models.generate_content(
                model=self.model,
                contents=contents,
                config=generate_content_config,
            )
            
            # Parse the response as JSON
            try:
                result = json.loads(response.text)
                return result
            except json.JSONDecodeError:
                # If parsing fails, try to extract JSON from the response
                logger.warning("Failed to parse LLM response as JSON, attempting to extract JSON")
                json_pattern = r'```json\s*(.*?)\s*```'
                json_match = re.search(json_pattern, response.text, re.DOTALL)
                
                if json_match:
                    try:
                        result = json.loads(json_match.group(1))
                        return result
                    except json.JSONDecodeError:
                        logger.error("Failed to extract valid JSON from code block")
                
                # Another attempt with just finding the first { and last }
                try:
                    start_idx = response.text.find('{')
                    end_idx = response.text.rfind('}') + 1
                    if start_idx != -1 and end_idx > start_idx:
                        json_str = response.text[start_idx:end_idx]
                        result = json.loads(json_str)
                        return result
                except Exception:
                    pass
                    
                logger.error(f"Failed to parse LLM response as JSON: {response.text}")
                return None
            
        except Exception as e:
            logger.error(f"Error calling Gemini API: {str(e)}")
            time.sleep(5)  # Back off on errors
            return None

    def validate_training_example(self, example: Dict) -> bool:
        """
        Validate that a training example has the correct structure
        
        Args:
            example (Dict): Training example dictionary
            
        Returns:
            bool: Whether the example is valid
        """
        try:
            if not example or 'contents' not in example:
                return False
                
            contents = example['contents']
            if not isinstance(contents, list) or len(contents) < 1:  # Allow single messages
                return False
                
            # Check message structure
            for content in contents:
                if 'role' not in content or 'parts' not in content:
                    return False
                if not content['parts'] or not isinstance(content['parts'], list):
                    return False
                if 'text' not in content['parts'][0]:
                    return False
                    
                # Validate role is either 'user' or 'model'
                if content['role'] not in ['user', 'model']:
                    return False
                    
            return True
        except Exception:
            return False

    def process_all_chats(self, output_path: str = "whatsapp_data/processed/train_data.jsonl"):
        """
        Process all WhatsApp chat exports in the raw_chats folder
        
        Args:
            output_path (str): Path to save the processed JSONL file
        """
        chat_files = glob.glob("whatsapp_data/raw_chats/*.txt")
        if not chat_files:
            logger.error("No chat files found in whatsapp_data/raw_chats/")
            return
            
        logger.info(f"Found {len(chat_files)} chat files to process")
        all_training_examples = []
        
        for file_path in tqdm(chat_files, desc="Processing chat files"):
            try:
                logger.info(f"Processing {file_path}")
                
                # Parse the raw chat
                messages = self.parse_raw_chat(file_path)
                logger.info(f"Found {len(messages)} messages in {file_path}")
                
                # Group messages into conversations
                conversations = self.group_messages_by_conversation(messages)
                logger.info(f"Grouped into {len(conversations)} conversations")
                
                # Process each conversation
                for conv_idx, conversation in enumerate(conversations):
                    # Process all conversations, including single messages
                    logger.info(f"Processing conversation {conv_idx+1}/{len(conversations)} with {len(conversation)} messages")
                    
                    # Format the conversation for the LLM
                    conversation_text = self.format_conversation_for_llm(conversation)
                    
                    # Process with Gemini
                    training_example = self.process_conversation_with_llm(conversation_text)
                    
                    # Validate and add to results
                    if training_example and self.validate_training_example(training_example):
                        all_training_examples.append(training_example)
                    else:
                        logger.warning(f"Invalid training example for conversation {conv_idx}")
            
            except Exception as e:
                logger.error(f"Error processing file {file_path}: {str(e)}")
        
        # Save the results
        with open(output_path, 'w', encoding='utf-8') as f:
            for example in all_training_examples:
                f.write(json.dumps(example) + '\n')
                
        logger.info(f"Saved {len(all_training_examples)} training examples to {output_path}")

def main():
    # Load environment variables from .env file
    load_dotenv()
    
    # Get values from environment variables
    your_name = os.getenv('YOUR_NAME')
    api_key = os.getenv('GEMINI_API_KEY')
    
    if not your_name:
        raise ValueError("YOUR_NAME environment variable is not set")
    if not api_key:
        raise ValueError("GEMINI_API_KEY environment variable is not set")
    
    # Set fixed output path
    output_path = "whatsapp_data/processed/train_data.jsonl"
    
    processor = WhatsAppProcessor(your_name=your_name, api_key=api_key)
    processor.process_all_chats(output_path=output_path)

if __name__ == "__main__":
    main()