# 7000%AUTO

> AI Automation System with 6 Orchestrated Agents powered by MiniMax M2.1

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109+-green.svg)](https://fastapi.tiangolo.com/)
[![Railway](https://img.shields.io/badge/Railway-Deploy-purple.svg)](https://railway.app/)

## 🚀 Overview

7000%AUTO is a fully autonomous AI system that orchestrates 6 specialized agents to ideate, plan, develop, test, deploy, and promote software projects. Built with FastAPI and powered by MiniMax M2.1 model through OpenCode SDK.

### Agent Pipeline

```
┌─────────┐    ┌─────────┐    ┌───────────┐    ┌────────┐    ┌──────────┐    ┌────────────┐
│ Ideator │ -> │ Planner │ -> │ Developer │ -> │ Tester │ -> │ Uploader │ -> │ Evangelist │
└─────────┘    └─────────┘    └───────────┘    └────────┘    └──────────┘    └────────────┘
     │              │               │              │              │                │
   Ideas         Plans           Code          Tests          GitHub            Social
                                                              Deploy            Posts
```

## 🤖 Agents

| Agent | Role | Tools |
|-------|------|-------|
| **Ideator** | Generates innovative project ideas and concepts | Search |
| **Planner** | Creates detailed project plans and task breakdowns | Search, Database |
| **Developer** | Implements production-ready code | Search, Gitea, Database |
| **Tester** | Tests implementations and ensures quality | Search, Gitea, Database |
| **Uploader** | Deploys code to Gitea repositories | Gitea, Database |
| **Evangelist** | Promotes projects on social media | X/Twitter, Search, Database |

## 📋 Prerequisites

- Python 3.11+
- MiniMax API key ([Get one here](https://platform.minimax.chat))
- Gitea Personal Access Token (Create in your Gitea instance settings)
- X/Twitter API keys ([Developer Portal](https://developer.twitter.com/en/portal/dashboard))

## 🛠️ Installation

### Local Development

1. **Clone the repository**
   ```bash
   git clone https://7000pct.gitea.bloupla.net/yourusername/7000auto.git
   cd 7000auto
   ```

2. **Create virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment**
   ```bash
   cp .env.example .env
   # Edit .env with your API keys
   ```

5. **Run the application**
   ```bash
   python main.py
   ```

### Docker

```bash
# Build the image
docker build -t 7000auto .

# Run the container
docker run -d \
  -p 8000:8000 \
  --env-file .env \
  --name 7000auto \
  7000auto
```

### Railway Deployment

1. Connect your GitHub repository to Railway
2. Add environment variables in Railway dashboard
3. Deploy automatically on push

[![Deploy on Railway](https://railway.app/button.svg)](https://railway.app/new)

## 🔧 Configuration

### Environment Variables

| Variable | Description | Required | Default |
|----------|-------------|----------|---------|
| `MINIMAX_API_KEY` | MiniMax API key | ✅ | - |
| `MINIMAX_MODEL` | Model identifier | ❌ | `minimax-m2.1` |
| `GITEA_TOKEN` | Gitea personal access token | ✅ | - |
| `GITEA_USERNAME` | Gitea username for repo creation | ✅ | - |
| `GITEA_URL` | Gitea server URL | ❌ | `https://7000pct.gitea.bloupla.net` |
| `X_API_KEY` | Twitter API key | ✅ | - |
| `X_API_SECRET` | Twitter API secret | ✅ | - |
| `X_ACCESS_TOKEN` | Twitter access token | ✅ | - |
| `X_ACCESS_TOKEN_SECRET` | Twitter access token secret | ✅ | - |
| `DATABASE_URL` | Database connection URL | ❌ | `sqlite+aiosqlite:///./data/7000auto.db` |
| `WORKSPACE_DIR` | Workspace directory | ❌ | `./workspace` |
| `PORT` | Server port | ❌ | `8000` |
| `DEBUG` | Debug mode | ❌ | `false` |

### OpenCode Configuration

The `opencode.json` file configures the OpenCode SDK and MCP servers:

```json
{
  "provider": "minimax",
  "model": "minimax-m2.1",
  "mcpServers": {
    "search": { "enabled": true },
    "gitea": { "enabled": true },
    "x_api": { "enabled": true },
    "database": { "enabled": true }
  }
}
```

## 📡 API Endpoints

### Projects

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/projects` | Create a new project |
| `GET` | `/projects` | List all projects |
| `GET` | `/projects/{id}` | Get project details |
| `POST` | `/projects/{id}/retry` | Retry a failed project |
| `POST` | `/projects/{id}/pause` | Pause a running project |
| `POST` | `/projects/{id}/resume` | Resume a paused project |
| `GET` | `/projects/{id}/logs` | Get project logs |

### System

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/` | Application info |
| `GET` | `/health` | Health check |
| `GET` | `/stats` | System statistics |
| `GET` | `/agents` | List all agents |
| `GET` | `/config` | Current configuration |

### Example Usage

```bash
# Create a new project
curl -X POST http://localhost:8000/projects \
  -H "Content-Type: application/json" \
  -d '{"name": "My Awesome Project", "description": "A CLI tool for productivity"}'

# List projects
curl http://localhost:8000/projects

# Get project status
curl http://localhost:8000/projects/{project_id}

# Check system health
curl http://localhost:8000/health
```

## 🏗️ Project Structure

```
7000auto/
├── main.py              # FastAPI app, orchestrator, and API endpoints
├── config.py            # Environment configuration
├── opencode.json        # OpenCode SDK configuration
├── requirements.txt     # Python dependencies
├── Dockerfile           # Docker configuration
├── .env.example         # Example environment variables
├── .gitignore          # Git ignore rules
├── README.md           # This file
├── data/               # Database and persistent data
├── workspace/          # Generated project workspaces
└── logs/               # Application logs
```

## 🔄 Workflow

1. **Create Project**: Submit a project name and description via API
2. **Ideation**: Ideator agent researches and generates detailed project concepts
3. **Planning**: Planner agent creates implementation plan with tasks and milestones
4. **Development**: Developer agent writes production-ready code
5. **Testing**: Tester agent validates code quality and functionality
6. **Upload**: Uploader agent deploys code to Gitea repository
7. **Evangelism**: Evangelist agent promotes the project on X/Twitter

## 🧪 Development

### Running Tests

```bash
pytest tests/ -v
```

### Code Formatting

```bash
black .
isort .
```

### Type Checking

```bash
mypy main.py config.py
```

## 📊 Monitoring

- **Health Check**: `GET /health` returns system status
- **Statistics**: `GET /stats` returns project counts and agent status
- **Logs**: Structured JSON logging with timestamps

## 🔒 Security

- Non-root Docker user
- Environment-based secrets management
- CORS middleware configured
- No sensitive data in logs
- API docs disabled in production

## 📝 License

MIT License - see [LICENSE](LICENSE) for details.

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## 📧 Support

For issues and questions, please open an issue on our Gitea repository.

---

Built with ❤️ using FastAPI, MiniMax M2.1, and OpenCode SDK
