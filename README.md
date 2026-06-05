# SIT Test Automation Web Runner

This project is an **Automation Test Engine** with a web-based user interface built on FastAPI. It leverages **Playwright** for browser automation and **Google Vertex AI / Gemini** to intelligently plan and execute test steps based on user-provided test cases.

## Features

- **Web UI Management**: Manage different test flows, upload test cases via Excel, and view test histories through a clean web interface.
- **AI-Driven Step Planning**: Uses Google GenAI (Vertex AI) to automatically plan the required browser actions from high-level test case descriptions.
- **Test Execution & Replay**: Execute tests in an AI-assisted mode or replay previously saved, reliable flows.
- **Reporting**: Automatically generates HTML test reports with screenshots and video recordings of the test execution.
- **User & Flow Management**: Separate test cases into different "flows" and manage user credentials (like Odoo login details) for each flow securely.

## Prerequisites

- **Python 3.8+**
- **Playwright** dependencies
- A **Google Cloud Platform (GCP)** project with Vertex AI API enabled and a Service Account JSON key.

## Setup Instructions

1. **Clone the repository** (if you haven't already):
   ```bash
   git clone <repository-url>
   cd Automation-Test-Engine
   ```

2. **Install Python dependencies**:
   It is recommended to use a virtual environment.
   ```bash
   pip install -r requirements.txt
   ```

3. **Install Playwright Browsers**:
   After installing the python packages, you need to install the browser binaries used by Playwright.
   ```bash
   playwright install
   ```

4. **Configuration (.env)**:
   Create a `.env` file in the root of the project with the following structure:
   ```env
   # Odoo credentials (Default fallback for tests)
   ODOO_URL=https://odoo19-dev.porto.co.id/
   ODOO_EMAIL=it@porto.co.id
   ODOO_PASSWORD=your-odoo-password

   # Google AI / Gemini Configuration
   GOOGLE_APPLICATION_CREDENTIALS=prompt-to-viz.json
   GOOGLE_CLOUD_PROJECT=your-gcp-project-id
   GOOGLE_CLOUD_LOCATION=us-central1
   GOOGLE_GENAI_USE_VERTEXAI=TRUE
   ```

5. **Google Cloud Credentials**:
   Place your GCP Service Account JSON key in the root directory and ensure its filename matches the `GOOGLE_APPLICATION_CREDENTIALS` variable in your `.env` (e.g., `prompt-to-viz.json`).

## Running the Application

1. **Start the Web Server**:
   Run the FastAPI server using the following command:
   ```bash
   python web_server.py
   ```
   *Note: This will automatically initialize the required local `data/` directory and default users on the first run.*

2. **Access the Web Interface**:
   Open your browser and navigate to:
   ```
   http://localhost:8000
   ```

3. **Login**:
   Log in using the default credentials (which are created automatically on the first run):
   - **Username**: `admin`
   - **Password**: `admin123`

## Project Structure

- `web_server.py`: The main FastAPI application entry point.
- `core/`: Contains the core automation logic (`step_planner_agent.py`, `test_executor.py`, `flow_manager.py`, `excel_parser.py`).
- `data/`: Local JSON storage for application state, users, flows, and test cases. (Generated automatically).
- `templates/`: HTML templates for the web interface.
- `test-results/`: Output directory where Playwright saves reports, screenshots, and videos.
- `saved_flows/`: Stores the stable, recorded execution steps of tests for replay mode.
