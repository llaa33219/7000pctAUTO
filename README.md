# 7000%AUTO

> Fully Autonomous AI Software Factory — From Idea to Production in One Command

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109+-green.svg)](https://fastapi.tiangolo.com/)
[![OpenCode](https://img.shields.io/badge/OpenCode-AI-purple.svg)](https://opencode.ai/)
[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)

## Overview

**7000%AUTO** is a fully autonomous AI system that creates complete software projects from scratch. It orchestrates 6 specialized AI agents that work together in a pipeline to ideate, plan, develop, test, deploy, and promote software — all without human intervention.

The system discovers trending topics from sources like arXiv, Reddit, and Hacker News, generates innovative project ideas, creates detailed implementation plans, writes production-ready code, runs tests until they pass, deploys to Gitea, and promotes the project on X/Twitter.

## How It Works

### Agent Pipeline

```
┌──────────┐    ┌──────────┐    ┌───────────┐    ┌────────┐    ┌──────────┐    ┌────────────┐
│ Ideator  │───▶│ Planner  │───▶│ Developer │◀──▶│ Tester │───▶│ Uploader │───▶│ Evangelist │
└──────────┘    └──────────┘    └───────────┘    └────────┘    └──────────┘    └────────────┘
     │               │               │               │              │                │
  Searches       Creates         Writes          Runs          Pushes to        Posts to
  for trends     detailed        code            tests         Gitea with       X/Twitter
  & generates    plans           & fixes         & CI/CD       Actions CI
  ideas                          bugs
```

### Agents

| Agent | Role | MCP Tools Used |
|-------|------|----------------|
| **Ideator** 💡 | Searches arXiv, Reddit, HN, Product Hunt for trends and generates unique project ideas | `search_arxiv`, `search_reddit`, `search_hackernews`, `search_producthunt`, `submit_idea` |
| **Planner** 📋 | Creates comprehensive implementation plans with tech stack, file structure, and testing strategy | `submit_plan` |
| **Developer** 👨‍💻 | Implements production-ready code following the plan; fixes bugs reported by Tester | `get_test_result`, `get_ci_result`, `submit_implementation_status` |
| **Tester** 🧪 | Runs linting, type checking, unit tests; validates CI/CD after upload | `submit_test_result`, `get_latest_workflow_status`, `submit_ci_result` |
| **Uploader** 🚀 | Creates Gitea repository, sets up CI/CD workflows, pushes code | `create_repo`, `push_files`, `setup_actions`, `submit_upload_status` |
| **Evangelist** 📣 | Creates and posts promotional content on X/Twitter | `post_tweet` |

### Key Features

- **Infinite Dev-Test Loop**: Developer and Tester iterate until all tests pass — no human intervention needed
- **CI/CD Verification**: After upload, Tester verifies Gitea Actions pass; Developer fixes any CI failures
- **Real-time Dashboard**: Web UI with SSE streaming shows live agent activity and progress
- **MCP-based Communication**: Agents communicate through structured MCP tools, not raw text parsing
- **Provider Agnostic**: Works with any AI provider via OpenCode SDK (Anthropic, OpenAI, MiniMax, etc.)

## Architecture

```
7000auto/
├── main.py                     # FastAPI app entry point, orchestrator lifecycle
├── config.py                   # Environment-based configuration (Pydantic Settings)
├── orchestrator/
│   ├── workflow.py             # WorkflowOrchestrator - runs the agent pipeline
│   ├── opencode_client.py      # OpenCode SDK client wrapper
│   └── state.py                # In-memory project state management
├── mcp_servers/
│   ├── search_mcp.py           # arXiv, Reddit, HN, Product Hunt search
│   ├── gitea_mcp.py            # Gitea repository operations
│   ├── x_mcp.py                # X/Twitter posting
│   ├── database_mcp.py         # Idea/plan submission tools
│   └── devtest_mcp.py          # Developer-Tester communication tools
├── database/
│   ├── models.py               # SQLAlchemy ORM models
│   └── db.py                   # Async database operations
├── web/
│   ├── app.py                  # Dashboard FastAPI app with SSE
│   └── templates/dashboard.html
└── .opencode/agent/            # Agent system prompts
    ├── ideator.md
    ├── planner.md
    ├── developer.md
    ├── tester.md
    ├── uploader.md
    └── evangelist.md
```

## Prerequisites

- **Python 3.11+**
- **Node.js 20+** (for OpenCode CLI)
- **OpenCode CLI** (`npm install -g opencode-ai`)
- **Gitea Instance** with Personal Access Token
- **X/Twitter API** credentials (for Evangelist agent)

## Installation

### 1. Clone and Setup

```bash
git clone <repository-url>
cd 7000auto
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure Environment

Create a `.env` file with your credentials:

```bash
# Required: AI Provider Configuration
OPENCODE_API_KEY=your-api-key
OPENCODE_API_BASE=https://api.anthropic.com/v1  # or your provider's URL
OPENCODE_SDK=@ai-sdk/anthropic                   # or @ai-sdk/openai, etc.
OPENCODE_MODEL=claude-sonnet-4-20250514               # or gpt-4o, etc.
OPENCODE_MAX_TOKENS=8192

# Required: Gitea Configuration
GITEA_TOKEN=your-gitea-personal-access-token
GITEA_USERNAME=your-username
GITEA_URL=https://your-gitea-instance.com

# Required: X/Twitter Configuration
X_API_KEY=your-consumer-key
X_API_SECRET=your-consumer-secret
X_ACCESS_TOKEN=your-access-token
X_ACCESS_TOKEN_SECRET=your-access-token-secret

# Optional
DATABASE_URL=sqlite+aiosqlite:///./data/7000auto.db
AUTO_START=true
DEBUG=false
PORT=8000
```

### 3. Run

```bash
python main.py
```

The system will:
1. Initialize the database
2. Generate `opencode.json` from environment variables
3. Start the OpenCode server
4. Begin the autonomous pipeline (if `AUTO_START=true`)
5. Serve the dashboard at `http://localhost:8000/dashboard`

## Configuration Reference

### Required Environment Variables

| Variable | Description |
|----------|-------------|
| `OPENCODE_API_KEY` | API key for your AI provider |
| `OPENCODE_API_BASE` | Provider's API base URL |
| `OPENCODE_SDK` | AI SDK npm package (e.g., `@ai-sdk/anthropic`) |
| `OPENCODE_MODEL` | Model identifier (e.g., `claude-sonnet-4-20250514`) |
| `OPENCODE_MAX_TOKENS` | Maximum output tokens |
| `GITEA_TOKEN` | Gitea Personal Access Token |
| `GITEA_USERNAME` | Gitea username for repository creation |
| `X_API_KEY` | Twitter/X Consumer Key |
| `X_API_SECRET` | Twitter/X Consumer Secret |
| `X_ACCESS_TOKEN` | Twitter/X Access Token |
| `X_ACCESS_TOKEN_SECRET` | Twitter/X Access Token Secret |

### Optional Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `GITEA_URL` | `https://7000pct.gitea.bloupla.net` | Gitea server URL |
| `DATABASE_URL` | `sqlite+aiosqlite:///./data/7000auto.db` | Database connection URL |
| `AUTO_START` | `true` | Auto-start pipeline on boot |
| `MAX_CONCURRENT_PROJECTS` | `1` | Max concurrent projects |
| `DEBUG` | `false` | Enable debug mode |
| `PORT` | `8000` | Server port |
| `LOG_LEVEL` | `INFO` | Logging level |

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/` | Redirect to dashboard |
| `GET` | `/dashboard` | Real-time monitoring dashboard |
| `GET` | `/health` | Health check with component status |
| `GET` | `/status` | Detailed system status |
| `GET` | `/dashboard/api/stream` | SSE stream for real-time events |
| `GET` | `/dashboard/api/status` | Dashboard status data |
| `GET` | `/dashboard/api/logs` | Recent agent logs |

## Deployment

### Docker

```bash
docker build -t 7000auto .
docker run -d \
  -p 8000:8000 \
  --env-file .env \
  --name 7000auto \
  7000auto
```

### Railway

The project includes `railway.json` for one-click deployment:

1. Connect your repository to Railway
2. Add environment variables in the Railway dashboard
3. Deploy

## MCP Servers

The system uses Model Context Protocol (MCP) servers to provide tools to AI agents:

| Server | Tools |
|--------|-------|
| **search** | `search_arxiv`, `search_reddit`, `search_hackernews`, `search_producthunt` |
| **gitea** | `create_repo`, `push_files`, `create_release`, `setup_actions`, `get_latest_workflow_status`, `get_workflow_run_jobs` |
| **x_api** | `post_tweet`, `search_tweets` |
| **database** | `get_previous_ideas`, `check_idea_exists`, `submit_idea`, `submit_plan` |
| **devtest** | `submit_test_result`, `get_test_result`, `submit_implementation_status`, `get_implementation_status`, `submit_ci_result`, `get_ci_result`, `submit_upload_status` |

## Workflow Details

### Pipeline Flow

1. **Ideation**: Ideator searches multiple sources, checks for duplicate ideas in database, generates a unique project idea
2. **Planning**: Planner creates detailed implementation plan with tech stack, file structure, features, and testing strategy
3. **Development Loop** (infinite until pass):
   - Developer implements/fixes code
   - Tester runs linting, type checking, tests
   - If tests fail → Developer fixes → Tester retests
4. **Upload & CI Loop** (max 5 iterations):
   - Uploader pushes to Gitea with CI workflow
   - Tester checks Gitea Actions status
   - If CI fails → Developer fixes → Uploader re-pushes
5. **Promotion**: Evangelist creates and posts tweet with Gitea link

### Agent Communication

Agents don't parse each other's raw output. Instead, they communicate through structured MCP tools:

```
Developer                          Tester
    │                                 │
    │  submit_implementation_status   │
    │────────────────────────────────▶│
    │                                 │
    │         get_test_result         │
    │◀────────────────────────────────│
    │                                 │
    │       submit_test_result        │
    │◀────────────────────────────────│
```

## License

This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

**Built with [FastAPI](https://fastapi.tiangolo.com/), [OpenCode SDK](https://opencode.ai/), and [MCP](https://modelcontextprotocol.io/)**
