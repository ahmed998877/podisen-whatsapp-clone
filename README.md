# Podisen: Clone yourself from whatsapp chat history 🤖

![Podisen - Clone Yourself](banner.png)

Podisen is a WhatsApp chatbot that creates a personalized AI clone of you by learning from your whatsapp chat history. 

With enough quality data, it will deeply understands how you respond, communication style & preferences. You can deploy your clone to a dedicated whatsapp account. Feel free to reach out if you have any questions or suggestions!

## ✨ Key Features
- AI powered Data Organization & Conversation Handling 💫: We don't do just questions and answers. We have multi message conversations. Podisen organize your raw_data with an LLM so multi-message chats stay together and he understands full conversations, not just single messages.
- Automatic Data Cleanup: Cleans up about 90% of your chat data without you having to do it manually.
- Deep Personalization: With good enough data, the model will learns your specific way of communication, making responses that sound just like you.
- End to End Whatsapp deployed Chatbot.


## 🚀 Getting Started

### Prerequisites

- Python 3.10 or higher
- Google Cloud Platform account
- WhatsApp Business API access
- Facebook Developer account
- Docker installed locally

### Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/podisen.git
cd podisen
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set up environment variables:
Create a `.env` file in the root directory with the following variables:
```env
WHATSAPP_TOKEN=your_whatsapp_token
VERIFY_TOKEN=your_verify_token
PROJECT_ID=your_gcp_project_id
LOCATION=your_gcp_location
MODEL_ID=your_model_id
PHONE_NUMBER_ID=your_phone_number_id
```

## 📊 Preparing Your Training Data

The project includes a Jupyter notebook (`0-data-processing/Complete-Data-Processing.ipynb`) to process your WhatsApp chat exports into a training dataset.

1. Export your WhatsApp chats:
   - Open WhatsApp
   - Go to a chat, Click on the top right side 3 dots > More >  Export Chat > Without media
   - Save the exported files in `whatsapp_data/raw_chats/`

2. Run the data processing notebook:
   - Open `0-data-processing/Complete-Data-Processing.ipynb`
   - Set your name in the environment variables
   - Run all cells to process your chats
   - The processed data will be saved in `whatsapp_data/processed/`

3. Additional Manual data cleaning.
   - Search for "<Media Omitted>" and replace it with nothing.
   - If your chat history includes any sensitive information (like personal names or phone numbers), consider anonymizing or removing those entries.
   - Remove any unnecessary metadata or timestamps that may not be relevant for training.
   - Check for and delete any duplicate messages that may have been exported.
   - Ensure that all messages are in a consistent format (e.g., all lowercase or proper casing).
   - Look for any special characters or emojis that may not be processed correctly and decide whether to keep or remove them.
   - Save the cleaned data in a new file to avoid overwriting the original exported chats.

IMPORTANT: Good data means a good output responses. So please pay attention to your dataset. For hight quality personalization I recommend to include at least 10,000 entires across various whatsapp chats.

## 🎯 Fine-Tuning Your Model

### 1. Prepare for Google Cloud Platform

1. Create a new GCP project
2. Enable the Vertex AI API
3. Create a Cloud Storage bucket
4. Upload your processed JSONL file to the bucket

### 2. Fine-Tune the Model

1. Navigate to Vertex AI in Google Cloud Console
2. Select "Tuning" under "Models"
3. Choose a base model (PaLM 2 or Gemini)
4. Configure your fine-tuning job:
   - Select your JSONL file
   - Set hyperparameters
   - Choose training budget
5. Start the fine-tuning process

### 3. Deploy Your Model

1. Deploy the model as an endpoint in Vertex AI
2. Note the model endpoint details for the bot implementation

## 🤖 Building the WhatsApp Bot

### 1. Set Up WhatsApp Business API

1. Register for WhatsApp Business API access
2. Complete the verification process
3. Set up a WhatsApp Business account

### 2. Configure Facebook Developer Platform

1. Go to [Facebook Developers](https://developers.facebook.com)
2. Create a new app or select existing one
3. Add WhatsApp product to your app
4. Configure Webhook:
   - Set Callback URL to your deployed service URL + `/webhook`
   - Set Verify Token (same as in your .env file)
   - Subscribe to messages events

### 3. Get Phone Number ID

1. In Facebook Developer Console, go to WhatsApp > Getting Started
2. Find your Phone Number ID in the API Setup section
3. Add this ID to your .env file

## 🚢 Deployment

### Deploy to Google Cloud Run

1. Build and push the Docker image:
```bash
gcloud builds submit --tag location-docker.pkg.dev/projectId/whatsapp-bot
```

2. Deploy to Cloud Run:
Make sure to use the project ID in text form, not the numeric project ID. Otherwise you'll get an error while deploying. (GCP side)
Run the below command as one line
```bash
gcloud run deploy whatsapp-bot \
  --image location-docker.pkg.dev/projectId/whatsapp-bot \
  --platform managed \
  --region location \
  --allow-unauthenticated \
  --set-env-vars="WHATSAPP_TOKEN=token,VERIFY_TOKEN=Vtoken,PROJECT_ID=projectIDinName,LOCATION=location,MODEL_ID=modelID"
```

## 🔍 Verifying Your Setup

1. After deployment, your webhook URL will be: `https://your-service-url/webhook`
2. In Facebook Developer Console:
   - Go to WhatsApp > Configuration
   - Enter your webhook URL
   - Enter your Verify Token
   - Click "Verify and Save"
3. Test your bot by sending a message to your WhatsApp Business number

## 📝 Notes

- Make sure to use the project ID in text form, not the numeric project ID
- Keep your tokens and API keys secure
- Monitor your Cloud Run logs for any issues
- The bot maintains conversation history for context

## 🤝 Contributing

Contributions are welcome! This is an open-source project, and I'd love to see your ideas and improvements. Here's how you can contribute:

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

Please make sure to update tests as appropriate and adhere to the existing code style.

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 👨‍💻 About the Creator

Hi! I'm **Geethika Isuru**, an AI Engineer & Entrepreneur who's trying to make a better world with AI.

- 💼 [LinkedIn Profile](https://www.linkedin.com/in/geethikaisuru/)
- 📂 [GitHub Profile](https://github.com/geethikaisuru)