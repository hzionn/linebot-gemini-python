# Linebot Assistant with LangChain and Vertex AI

## Project Background

This project originated from a Google Developer Group (Build with AI) workshop by Evan Lin focused on AI integration, specifically introducing Gemini and its implementation with LINE Bot. The initial repository was a basic template provided for quick deployment during the workshop.

After the workshop, the project was expanded into a more personal and comprehensive assistant, serving as both a practical implementation of LLM (Large Language Model) techniques and a learning platform for exploring AI integration in real-world applications. The goal is to continuously enhance and customize this bot, incorporating new features and learning opportunities along the way.

## Overview

This project is a LINE bot that leverages Google Vertex AI Gemini models (via LangChain) to provide advanced conversational and image analysis capabilities. It is designed for personal use, learning, and experimentation with LLMs and AI integration on messaging platforms.

## Features

- **Conversational AI:** Responds to user text messages using Gemini (Vertex AI) via LangChain.
- **Image Understanding:** Analyzes images sent by users and provides structured, scientific responses.
- **Per-User Chat History:** Maintains a recent message history for each user to enable context-aware conversations.
- **Automatic History Management:** User histories are capped to a fixed number of messages and are automatically cleaned up for inactive users.
- **Prompt System:** Uses customizable system prompts for both text and vision models, loaded from the `prompts/` directory.
- **Agent Tools:** Supports tools such as current time lookup, Google Search and more to be added.
- **Cloud Native:** Designed for deployment on Google Cloud Run, but can also run locally for development.

## Quick Start

1. **Clone the repository:**

   ```bash
   git clone https://github.com/hzionn/linebot-gemini-python.git
   cd linebot-gemini-python
   ```

2. **Set up your environment:**
   - Copy `.env.template` to `.env` and fill in your credentials (for local development).
   - For Cloud Run, set environment variables in the service configuration.

3. **Install dependencies:**

   ```bash
   pip install -r requirements.txt
   ```

4. **Prompts and History:**

   ```bash
   make
   ```

5. **Start the server locally:**

   ```bash
   uvicorn app:app --reload
   ```

6. **(Optional) Use ngrok for local webhook testing:**

   ```bash
   ngrok http 8000
   ```

7. **Set your LINE bot webhook URL** to your server endpoint.

## Deployment

- **Google Cloud Run:**
  - Build and deploy using the provided Dockerfile.
  - Set environment variables and secrets in Cloud Run.
  - No database setup required; user histories are stored as files.

## Important Notes

- **Persistence:** User chat histories are stored as files in the `history/` directory (or a mounted volume in production). No external database is required.
- **Chat History Limits:** Each user's history is capped (can be changed in `.env`). Inactive users' histories are periodically saved and removed from memory.
- **Prompt Customization:** System prompts for both text and vision models can be customized by editing files in the `prompts/` directory.
- **Tools:** The bot can access current time, set reminders (not implemented yet), and perform Google searches via agent tools.
- **No Database:** All persistence is file-based. If you need to scale horizontally, use a shared volume for the `history/` directory.
- **No User Profile/Character Selection Yet:** The bot currently does not support user-selectable LLM profiles or characters.

## Architecture

See [docs/architecture.md](docs/architecture.md) for architecture details.

## Limitations & Future Directions

- No support for user-selectable LLM profiles/characters (planned).
- No database integration; all persistence is file-based.
- No admin interface or analytics.
- All configuration is via environment variables or prompt files.

## License

MIT License. See [LICENSE](LICENSE) for details.
