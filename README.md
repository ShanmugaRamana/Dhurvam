# Dhurvam — Agentic Honey-Pot for Scam Detection & Intelligence Extraction

> An AI-powered honeypot system that detects scam messages, engages scammers in believable conversation, and extracts actionable intelligence — built for the GUVI AI Hackathon.

## Architecture

### System Overview

```mermaid
graph TB
    Client["fa:fa-paper-plane Incoming HTTP Request<br/><i>POST /detect</i>"]

    subgraph Server["fa:fa-cogs FastAPI Server (Python 3.11+)"]
        direction TB
        AppFactory["app.py<br/><i>FastAPI App Factory</i>"]
        Middleware["fa:fa-shield Request Logging<br/>Middleware + CORS"]

        subgraph Routes["fa:fa-route API Routes"]
            DetectRoute["detect.py<br/><i>POST /detect</i>"]
            AuthRoute["auth.py<br/><i>Authentication</i>"]
            LogsRoute["logs.py<br/><i>GET /logs</i>"]
        end

        subgraph Core["fa:fa-microchip Core Services"]
            Orchestrator["orchestrator.py<br/><i>Agent Coordinator</i>"]
            APIClients["api_clients.py<br/><i>Multi-Key Failover</i>"]
            Config["config.py"]
            Security["security.py<br/><i>API Key Auth</i>"]
            BGTasks["background_tasks.py<br/><i>Auto-Timeout (45s)</i>"]
            Logger["logger.py"]
            GUVIClient["guvi_client.py<br/><i>Hackathon Submission</i>"]
        end

        subgraph Agents["fa:fa-robot 3-Agent System"]
            Agent1["Agent 1: Conversational<br/><i>Groq — LLaMA 3.3 70B</i>"]
            Agent2["Agent 2: Extraction<br/><i>Mistral AI + Regex</i>"]
            Agent3["Agent 3: End Detection<br/><i>OpenRouter — Gemini 2.0 Flash</i>"]
        end
    end

    subgraph External["fa:fa-cloud External Services"]
        MongoDB[(MongoDB Atlas)]
        GroqAPI["Groq API"]
        MistralAPI["Mistral API"]
        OpenRouterAPI["OpenRouter API"]
        GUVIEndpoint["GUVI Hackathon<br/>Evaluation Endpoint"]
    end

    %% Entry point
    Client --> AppFactory
    AppFactory --> Middleware --> Routes

    %% Internal flow
    DetectRoute --> Orchestrator
    Orchestrator --> Agent1
    Orchestrator --> Agent2
    Orchestrator --> Agent3
    BGTasks -- "Auto-close<br/>inactive sessions" --> MongoDB

    %% Agent to API Clients
    Agent1 --> APIClients
    Agent2 --> APIClients
    Agent3 --> OpenRouterAPI

    %% API Clients to External
    APIClients --> GroqAPI
    APIClients --> MistralAPI
    APIClients --> OpenRouterAPI

    %% Data persistence & submission
    Orchestrator --> MongoDB
    GUVIClient -- "Submit results" --> GUVIEndpoint

    style Server fill:#0f3460,stroke:#16213e,color:#e0e0e0
    style Agents fill:#533483,stroke:#16213e,color:#e0e0e0
    style External fill:#1a1a2e,stroke:#e94560,color:#e0e0e0
    style Core fill:#1a1a2e,stroke:#16213e,color:#e0e0e0
    style Routes fill:#16213e,stroke:#0f3460,color:#e0e0e0
```

### Request Flow — Scam Detection & Engagement

```mermaid
sequenceDiagram
    participant C as Client
    participant API as FastAPI Server
    participant D as Detect Route
    participant O as Orchestrator
    participant A1 as Agent 1 — Conversational
    participant A2 as Agent 2 — Extraction
    participant A3 as Agent 3 — End Detection
    participant DB as MongoDB Atlas
    participant G as GUVI Endpoint

    C->>API: POST /detect (message + sessionId)
    API->>D: Middleware → Route handler

    D->>D: 4-Step Scam Detection<br/>(Brand → Action → Threat → Link)

    alt Message is Human
        D-->>C: {action: "ignore", classification: "Human"}
    else Message is Scammer
        D->>O: start_orchestration() or<br/>continue_orchestration()
        O->>DB: Create / fetch session
        O->>A1: generate_reply(message, history, intel)
        A1-->>O: Honeypot reply
        O->>A2: extract_intelligence(message)
        A2-->>O: Structured intel (bank, UPI, phone, links)
        O->>DB: Merge & persist intelligence
        O->>A3: check_end_condition(count, intel)
        A3-->>O: Continue / Ready to finalize

        alt Ready to finalize
            O->>G: submit_final_result(session)
            Note over O: Session stays ACTIVE<br/>until 45s timeout
        end

        O-->>C: {action: "engage", reply, intelligence}
    end
```

### 3-Agent Orchestration Pipeline

```mermaid
graph LR
    MSG["fa:fa-envelope Incoming<br/>Scammer Message"] --> A1

    subgraph Pipeline["Orchestrator Pipeline (per turn)"]
        direction LR
        A1["fa:fa-theater-masks Agent 1<br/><b>Conversational</b><br/><i>Groq / LLaMA 3.3 70B</i><br/><br/>- Build trust then Probe then Extract<br/>- Tone adaptation<br/>- Multi-key failover"]
        A2["fa:fa-search Agent 2<br/><b>Extraction</b><br/><i>Mistral AI + Regex</i><br/><br/>- Regex first pass<br/>- Mistral contextual validation<br/>- Rule-based boost"]
        A3["fa:fa-clock Agent 3<br/><b>End Detection</b><br/><i>OpenRouter / Gemini 2.0</i><br/><br/>- Intel type count >= 2<br/>- Message count thresholds<br/>- 50-msg safety cap"]
    end

    A1 --> A2 --> A3

    A3 -- "Continue" --> REPLY["fa:fa-comment Send Reply<br/>to Scammer"]
    A3 -- "Finalize" --> SUBMIT["fa:fa-share-square Submit Intel<br/>to GUVI + Keep Engaging"]

    style A1 fill:#e94560,stroke:#1a1a2e,color:#fff
    style A2 fill:#0f3460,stroke:#1a1a2e,color:#fff
    style A3 fill:#533483,stroke:#1a1a2e,color:#fff
```

## Tech Stack

| Component | Technology |
|-----------|-----------|
| **Backend API** | FastAPI (Python 3.11+) |
| **Agent 1 - Conversational** | Groq API (LLaMA 3.3 70B) with multi-key failover |
| **Agent 2 - Extraction** | Mistral AI + Python Regex (hybrid approach) |
| **Agent 3 - End Detection** | OpenRouter (Gemini 2.0 Flash) |
| **Database** | MongoDB Atlas |
| **Frontend** | Node.js, Express, EJS templates |
| **Deployment** | Docker, Render (backend), Vercel (frontend) |

## 3-Agent System

### Agent 1: Conversational Honeypot
- **Provider**: Groq (LLaMA 3.3 70B Versatile)
- **Purpose**: Acts as a believable victim persona to engage scammers
- **Features**:
  - Dynamic strategy per conversation turn (build trust → probe → extract)
  - Aggressive targeted questioning to extract contact info and payment details
  - Tone adaptation (panic for threats, excitement for offers)
  - Repetition avoidance across turns
  - Multi-key failover for resilience

### Agent 2: Intelligence Extraction
- **Provider**: Mistral AI + Python Regex
- **Purpose**: Extract structured intelligence from scammer messages
- **Extracts**:
  - Bank account numbers (11-18 digit, 16-digit cards)
  - UPI IDs (`user@bank` format)
  - Phone numbers (Indian +91 and 10-digit)
  - Phishing links (HTTP/S, shorteners)
  - Email addresses
  - Suspicious keywords (urgency, threats, prizes)
- **Approach**: Fast regex first pass → Mistral contextual validation → Rule-based boost

### Agent 3: End Detection
- **Provider**: OpenRouter (Google Gemini 2.0 Flash)
- **Purpose**: Decides when sufficient intelligence has been gathered
- **Logic**: Based on intel type count + message count thresholds

## Scam Detection

Uses a **4-step decision framework** (in `detect.py`):
1. **Brand Recognition** — Is message from a known legitimate brand?
2. **Action Analysis** — Is the requested action safe or dangerous?
3. **Threat Analysis** — Is there threatening urgency?
4. **Link Analysis** — Is the URL suspicious?

Classifies messages as **Human** (legitimate) or **Scammer** (engage honeypot).

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/detect` | Main scam detection & engagement endpoint |
| `POST` | `/api/honeypot/detect` | Authenticated scam detection |
| `GET` | `/api/honeypot/sessions` | List all sessions |
| `GET` | `/api/honeypot/session/{id}/output` | Get session details |
| `POST` | `/api/honeypot/session/{id}/timeout` | End session on timeout |
| `GET` | `/health` | Health check |

## Project Structure

```
Dhurvam/
├── server/                      # FastAPI Backend
│   ├── app/
│   │   ├── agents/
│   │   │   ├── conversational.py  # Agent 1: Honeypot conversation
│   │   │   ├── extraction.py      # Agent 2: Intelligence extraction
│   │   │   └── end_detection.py   # Agent 3: End condition logic
│   │   ├── api/
│   │   │   └── routes/
│   │   │       ├── detect.py      # Main detection route
│   │   │       ├── auth.py        # Authentication
│   │   │       └── logs.py        # Log access
│   │   ├── core/
│   │   │   ├── orchestrator.py    # Coordinates all 3 agents
│   │   │   ├── api_clients.py     # Multi-key API failover manager
│   │   │   ├── guvi_client.py     # GUVI hackathon submission
│   │   │   ├── database.py        # MongoDB connection
│   │   │   ├── config.py          # Environment config
│   │   │   ├── security.py        # API key auth
│   │   │   ├── background_tasks.py # Auto-timeout checker
│   │   │   └── logger.py          # Logging utility
│   │   └── app.py                 # FastAPI app factory
│   ├── main.py                    # Entry point
│   ├── Dockerfile                 # Docker deployment
│   ├── requirements.txt           # Python dependencies
│   └── .env.example               # Environment template
├── web/                           # Node.js Frontend
│   ├── server.js                  # Express server
│   ├── routes/                    # Proxy routes to backend
│   ├── views/                     # EJS templates
│   └── public/                    # Static assets (CSS, JS)
└── README.md
```

## Setup

### Prerequisites
- Python 3.11+
- Node.js 18+
- MongoDB Atlas account
- API keys: Groq, Mistral, OpenRouter

### Backend
```bash
cd server
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your API keys
python main.py
```

### Frontend
```bash
cd web
npm install
cp .env.example .env
# Edit .env with backend URL
node server.js
```

### Docker
```bash
cd server
docker build -t dhurvam-api .
docker run -p 8000:8000 --env-file .env dhurvam-api
```

## Error Handling

- **Multi-key failover**: Each AI provider (Groq, Mistral, OpenRouter) supports multiple API keys with automatic rotation on failure
- **Timeout detection**: Background task checks for 15-second inactivity
- **Graceful degradation**: If all LLM keys fail, minimal fallback responses maintain engagement
- **Request logging**: Full middleware logging for debugging

## License

MIT License
