# Linebot Assistant with LangChain and Vertex AI

> This project originated from a Google Developer Group (Build with AI) workshop by Evan Lin focused on AI integration, specifically introducing Gemini and its implementation with LINE Bot. The initial repository was a basic template provided for quick deployment during the workshop.
> After the workshop, I saw an opportunity to transform this starter project into something more personal and comprehensive. This project serves as both a practical implementation of LLM (Large Language Model) techniques and a learning platform for exploring AI integration in real-world applications.
> The goal is to continuously enhance and customize this bot, incorporating new features and learning opportunities along the way. It's not just about building a LINE bot - it's about understanding and mastering the integration of advanced AI capabilities into practical applications.

## Project Background

This project is a LINE bot that uses Google's Vertex AI Gemini models through LangChain to generate responses to both text and image inputs.

## Technologies Used

- Python 3
- FastAPI
- LINE Messaging API
- Google Vertex AI
- LangChain
- Aiohttp
- PIL (Python Imaging Library)
- Ngrok (for local development)

## Features

- Text message processing using Gemini AI in Traditional Chinese
- Image analysis with scientific detail in Traditional Chinese
- Integration with LINE Messaging API for easy mobile access
- Built with FastAPI for efficient asynchronous processing
- Chat history management

## Setup

1. **Clone the repository to your local machine:**

   ```bash
   git clone https://github.com/hzionn/linebot-gemini-python.git
   cd linebot-gemini-python
   ```

2. **Set up your environment:**
   - Follow the steps in the [Environment Setup](#environment-setup) section to configure your environment variables.

3. **Set up Google Cloud:**
   - Create a Google Cloud project
   - Enable Vertex AI API
   - Set up authentication (service account or application default credentials)

4. **Install the required dependencies:**

   ```bash
   pip install -r requirements.txt
   ```

5. **Start the FastAPI server:**

   ```bash
   uvicorn app:app --reload
   ```

6. **(Local only) Start the ngrok tunnel and set the webhook URL in the LINE Messaging API:**

   ```bash
   ngrok http 8000
   ```

7. **Set up your LINE bot webhook URL to point to your server's endpoint.**

## Environment Setup

### Local Development

1. Copy the example environment file and rename it:

   ```sh
   cp .env.template .env
   ```

2. Open `.env` and fill in your credentials and configuration values.
3. The `.env` file is required for local development only. **Do not commit your `.env` file to version control.**

### Cloud Run Deployment

- For Cloud Run, set environment variables and secrets directly in the Cloud Run service configuration (via the Google Cloud Console or `gcloud` CLI).
- You do **not** need a `.env` file for Cloud Run.

## Deployment Options

### Google Cloud Run

1. Install the Google Cloud SDK and authenticate with your Google Cloud account.
2. Build the Docker image:

   ```bash
   gcloud builds submit --tag gcr.io/$GOOGLE_PROJECT_ID/linebot-gemini
   ```

3. Deploy the Docker image to Cloud Run:

   ```bash
   gcloud run deploy linebot-gemini --image gcr.io/$GOOGLE_PROJECT_ID/linebot-gemini --platform managed --region $GOOGLE_LOCATION --allow-unauthenticated
   ```

4. Set up your LINE bot webhook URL to point to the Cloud Run service URL.
