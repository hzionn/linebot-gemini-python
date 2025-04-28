# Gemini Helper with LangChain and Vertex AI

## Project Background

This project is a LINE bot that uses Google's Vertex AI Gemini models through LangChain to generate responses to both text and image inputs.

## Features

- Text message processing using Gemini AI in Traditional Chinese
- Image analysis with scientific detail in Traditional Chinese
- Integration with LINE Messaging API for easy mobile access
- Built with FastAPI for efficient asynchronous processing
- Chat history management

## Technologies Used

- Python 3
- FastAPI
- LINE Messaging API
- Google Vertex AI (Gemini 2.0 Flash)
- LangChain
- Aiohttp
- PIL (Python Imaging Library)
- Ngrok (for local development)

## Setup

1. Clone the repository to your local machine.
2. Set up Google Cloud:
   - Create a Google Cloud project
   - Enable Vertex AI API
   - Set up authentication (service account or application default credentials)

3. Set the following environment variables:
   - `ChannelSecret`: Your LINE channel secret
   - `ChannelAccessToken`: Your LINE channel access token
   - `GOOGLE_PROJECT_ID`: Your Google Cloud Project ID
   - `GOOGLE_LOCATION`: Google Cloud region (default: us-central1)
   - Optional: `GOOGLE_APPLICATION_CREDENTIALS`: Path to service account key file (if running locally)

4. Install the required dependencies:

   ```bash
   pip install -r requirements.txt
   ```

5. Start the FastAPI server:

   ```bash
   uvicorn main:app --reload
   ```

6. Start the ngrok tunnel (if using local development):

   ```bash
   ngrok http 8000
   ```

7. Set up your LINE bot webhook URL to point to your server's endpoint.

## Deployment Options

### Local Development

Use ngrok or similar tools to expose your local server to the internet for webhook access:

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
