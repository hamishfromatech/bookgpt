# BookGPT: AI-Powered Book Writing with Agentic Loops

An autonomous AI agent that writes complete books using OpenAI (or OpenAI-compatible APIs) with sophisticated tool calling patterns. Modeled after professional coding agents like Cursor, Windsurf, Aider, and OpenAI Codex.

## Quick Links

- **[Installation Guide](docs/INSTALLATION.md)** - Step-by-step setup for beginners
- [Expert Mode Guide](docs/expert-mode.md) - Advanced configuration
- [Stripe Setup](docs/STRIPE_SETUP.md) - Billing integration
- [Walkthrough](docs/walkthrough.md) - Full usage guide

## Features

### Core Features
- **🤖 Autonomous Writing**: Complete book generation from title to final draft
- **🛠️ Professional Tools**: File operations modeled after coding agents
- **🔄 Agentic Loop**: Planning → Research → Writing → Editing → Refining phases
- **🌐 Multiple LLM Support**: OpenAI, Ollama, LM Studio, custom endpoints
- **📚 Structured Output**: Organized chapters with outlines and research notes

### Advanced Features
- **👤 User Authentication**: Secure login system with password management
- **💳 Stripe Billing**: Credit-based system with subscription support
- **📊 Real-time Monitoring**: Live progress dashboard with activity feeds
- **📝 Chapter Versioning**: Track and restore previous chapter versions
- **⏸️ Pause & Resume**: Stop and resume writing sessions anytime
- **💬 Agent Chat**: Interactive chat to guide the writing process
- **📥 Multiple Export Formats**: PDF, EPUB, DOCX, and plain text
- **🎨 Character Management**: Create and track characters
- **📖 Plot Tracking**: Manage plot points and story arcs
- **🔒 Rate Limiting**: API protection with configurable limits
- **📈 Project Analytics**: Track writing progress and statistics

## Installation

### Quick Start (Recommended)

Use the automated setup script:

**Windows:**
```bash
quickstart.bat
```

**Mac/Linux:**
```bash
./quickstart.sh
```

The script will:
1. Check/install Python
2. Create a virtual environment
3. Install dependencies
4. Guide you through AI provider setup (OpenAI or Ollama)
5. Start the application

### Manual Installation

See the detailed [Installation Guide](docs/INSTALLATION.md) for step-by-step instructions including troubleshooting.

```bash
# Clone and setup
git clone <repository-url>
cd bookgpt
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your settings

# Start the app
python app.py
```

## Usage

### Web Interface

1. Open **http://localhost:6748** in your browser
2. Login with default credentials:
   - **Username:** `user`
   - **Password:** `password`
3. Create a new book project
4. Start the writing process
5. Monitor progress in real-time
6. Export your finished book

### The Writing Process

| Phase | Description |
|-------|-------------|
| **Planning** | Creates detailed chapter-by-chapter outline |
| **Research** | Develops world-building, characters, and context |
| **Writing** | Generates chapters sequentially |
| **Editing** | Reviews and improves the manuscript |
| **Refining** | Interactive chat for manual adjustments |

### Key Features

**Chapter Management**
- View all chapters with status indicators
- Reorder chapters via drag-and-drop
- View version history for each chapter
- Restore previous versions
- Set custom prompts per chapter

**Project Tools**
- **Chat**: Guide the AI with natural language
- **Characters**: Create and manage character profiles
- **Plot Points**: Track story beats and arcs
- **Documents**: Access outlines, research notes, and drafts
- **Export**: Download in PDF, EPUB, DOCX, or TXT

**Billing & Credits** (Optional)
- Stripe integration for paid usage
- Credit-based system for API costs
- Subscription management via Stripe Portal
- Disable billing for unlimited local usage

## API Reference

### Projects
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/projects` | GET | List all projects |
| `/api/projects` | POST | Create new project |
| `/api/projects/{id}` | GET | Get project details |
| `/api/projects/{id}/start` | POST | Start writing |
| `/api/projects/{id}/stop` | POST | Pause writing |
| `/api/projects/{id}/resume` | POST | Resume writing |
| `/api/projects/{id}/progress` | GET | Get progress |
| `/api/projects/{id}/chat` | POST | Chat with agent |
| `/api/projects/{id}/download` | GET | Download book |
| `/api/projects/{id}/export/{format}` | GET | Export (pdf/epub/docx) |

### Chapters
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/projects/{id}/chapters` | GET | List chapters |
| `/api/projects/{id}/chapters/{num}` | GET | Get chapter content |
| `/api/projects/{id}/chapters/{num}` | PUT | Update chapter |
| `/api/projects/{id}/chapters/{num}` | DELETE | Delete chapter |
| `/api/projects/{id}/chapters/{num}/versions` | GET | Get version history |
| `/api/projects/{id}/chapters/{num}/versions/{ver}` | GET | Get specific version |
| `/api/projects/{id}/chapters/{num}/versions/{ver}/restore` | POST | Restore version |

### LLM Configuration
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/llm/config` | GET/POST | Get/update LLM settings |
| `/api/llm/presets` | GET | Get available presets |
| `/api/llm/preset/{name}` | POST | Apply preset |
| `/api/llm/test` | POST | Test connection |

### Billing (Optional)
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/billing/status` | GET | Get billing status |
| `/api/billing/buy` | POST | Purchase credits |
| `/api/billing/portal` | POST | Manage subscription |
| `/api/billing/cancel` | POST | Cancel subscription |

## Configuration

### Environment Variables

```bash
# Flask Configuration
FLASK_SECRET_KEY=your-secret-key
FLASK_DEBUG=true
PORT=6748

# LLM Configuration
OPENAI_API_KEY=sk-...
OPENAI_BASE_URL=https://...     # Optional: custom endpoint
LLM_MODEL=gpt-4o

# Stripe (Optional - set STRIPE_ENABLED=false to disable)
STRIPE_ENABLED=false
STRIPE_PUBLIC_KEY=pk_test_...
STRIPE_SECRET_KEY=sk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...
STRIPE_PRICE_ID=price_...

# Application Domain
DOMAIN=http://localhost:6748
```

### Supported LLM Providers

| Provider | Base URL | Models |
|----------|----------|--------|
| OpenAI | Default | gpt-4o, gpt-4o-mini, gpt-3.5-turbo |
| Ollama | http://localhost:11434/v1 | llama3.2, mistral, codellama |
| LM Studio | http://localhost:1234/v1 | local-model |
| Custom | Any | OpenAI-compatible models |

## Project Structure

```
bookgpt/
├── app.py                      # Flask application
├── book_agent.py               # Main agentic system
├── models/
│   ├── book_model.py           # Book project data model
│   └── version_model.py        # Chapter versioning
├── tools/
│   ├── file_tools.py           # File operations
│   ├── chapter_tools.py        # Chapter management
│   └── research_tools.py       # Research and outlines
├── utils/
│   ├── llm_client.py           # LLM client
│   ├── task_manager.py         # Background tasks
│   ├── database.py             # Data storage
│   ├── storage.py              # File storage
│   ├── export.py               # Export functions
│   └── validation.py           # Input validation
├── templates/                  # HTML templates
├── static/                     # CSS, JS, images
└── docs/                       # Documentation
```

## Development

### Adding New Tools

1. Create tool class inheriting from `BaseTool`
2. Implement: `name()`, `description()`, `parameters_schema()`, `execute()`
3. Add to `ALL_TOOLS` in `utils/agent_factory.py`

### Running Tests

```bash
# Test LLM connection
curl -X POST http://localhost:5000/api/llm/test

# List available tools
curl -X GET http://localhost:5000/api/tools
```

## Troubleshooting

See the [Installation Guide](docs/INSTALLATION.md) for common issues and solutions.

## Roadmap

- [ ] Multiple language support
- [ ] Character consistency tracking
- [ ] Plot coherence validation
- [ ] Collaborative editing
- [ ] Advanced customization options
- [ ] Mobile-responsive interface

## Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open Pull Request

## License

MIT License - see [LICENSE](LICENSE) for details.

## Acknowledgments

- **OpenAI** for function calling patterns
- **Cursor** for file operation tool design
- **Windsurf** for directory listing patterns
- **Aider** for search and replace methodology
- **OpenAI Codex** for agentic loop structure

## Support

- [Installation Guide](docs/INSTALLATION.md) - Getting started
- [Expert Mode Guide](docs/expert-mode.md) - Advanced features
- Open an issue on GitHub
- Join our [Skool Community](https://www.skool.com/open-source-ai-builders-club/about)

---

**Built with ❤️ using modern AI agent patterns.**

*The A-Tech Corporation PTY LTD.*
