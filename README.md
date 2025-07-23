# Live Interpreter - Open Source Edition

This is an open-source, self-hosted version of the Live Interpreter application. It uses local, GPU-accelerated models for real-time speech-to-text and translation, replacing the previous reliance on Azure Cognitive Services.

## Features

*   **Real-time Transcription:** Converts spoken language into text in real-time.
*   **Real-time Translation:** Translates the transcription into a target language.
*   **Language Detection:** Automatically detects the spoken language.
*   **Web-based UI:** A simple React frontend to display the results.

## Tech Stack

*   **Backend:** FastAPI, WebSockets, PyTorch
*   **Speech-to-Text:** WhisperX
*   **Translation:** Helsinki-NLP models
*   **Frontend:** React
*   **Agent:** Python (for audio capture)

## Getting Started

### Prerequisites

*   A Linux server with a dedicated NVIDIA GPU.
*   NVIDIA drivers, CUDA, and cuDNN installed.
*   Docker and Docker Compose.

### Installation

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/your-username/live-interpreter-opensource.git
    cd live-interpreter-opensource
    ```

2.  **Run the setup script:**
    This script will check your environment, install dependencies like Docker, and download the necessary AI models.
    ```bash
    ./setup_environment.sh
    ```
    *Note: You may need to log out and log back in after the script runs for Docker permissions to apply, then run it again.*

3.  **Build and run with Docker Compose:**
    Once the setup script completes successfully, you can manage the application with the Makefile.
    ```bash
    make up
    ```

### Usage

1.  Open your web browser and navigate to `http://localhost:3000`.
2.  Run the agent to start streaming audio from your system:
    ```bash
    python agent/agent.py
    ```
