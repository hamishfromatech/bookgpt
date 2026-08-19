# BookGPT: AI-Powered Book Writing with Agentic Loops & Specialized Skills

An autonomous AI agent that writes complete books using OpenAI (or OpenAI-compatible APIs) with sophisticated tool calling patterns and domain-specific writing skills. Modeled after professional coding agents like Cursor, Windsurf, Aider, and OpenAI Codex.

## Quick Links

- **[Installation Guide](docs/INSTALLATION.md)** - Step-by-step setup for beginners
- [Expert Mode Guide](docs/expert-mode.md) - Advanced configuration
- [Best Practices & Guide](docs/best-practices.md) - Tips, tricks, and agentic experience guide
- [Stripe Setup](docs/STRIPE_SETUP.md) - Billing integration
- [Walkthrough](docs/walkthrough.md) - Full usage guide

## Features

### Core Features
- **🤖 Autonomous Writing**: Complete book generation from title to final draft
- **🛠️ Professional Tools**: File operations modeled after coding agents (read, write, edit, search)
- **🔄 Agentic Loop**: Planning → Research → Writing → Editing → Refining phases
- **🌐 Multiple LLM Support**: OpenAI, Ollama, LM Studio, custom endpoints
- **📚 Structured Output**: Organized chapters with outlines and research notes

### Specialized Skills System
- **🎭 Domain-Specific Workflows**: Select specialized writing skills during project creation:
  - `fiction-writer`: Novel and fiction writing with character arcs, plot beats, dialogue focus
  - `non-fiction-author`: Research citation, factual accuracy, logical structure, reader education
  - `academic-writer`: Formal tone, peer-review style, reference formatting, methodological rigor
  - `childrens-book-creator`: Simple language, educational themes, age-appropriate content, illustration prompts
  - `screenplay-writer`: Scene headings, action lines, dialogue formatting, visual storytelling

### Advanced Features
- **👤 User Authentication**: Secure login system with password management
- **💳 Stripe Billing**: Credit-based system with subscription support
- **📊 Real-time Monitoring**: Live progress dashboard with activity feeds and agent logging
- **📝 Chapter Versioning**: Track and restore previous chapter versions with diff views
- **⏸️ Pause & Resume**: Stop and resume writing sessions anytime (state preserved)
- **💬 Agent Chat**: Interactive chat with proactive suggestions based on project state
- **📥 Multiple Export Formats**: PDF, EPUB, DOCX, and plain text
- **🎨 Character Management**: Create and track characters with consistency checks
- **📖 Plot Tracking**: Manage plot points and story arcs with cross-chapter validation
- **🔒 Rate Limiting & Adaptive Recovery**: API protection with fallback strategies for failed generations
- **📈 Project Analytics**: Track writing progress, token usage, and agent activity logs

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
3. Create a new book project (select genre, target words, writing style, and specialized skill/workflow)
4. Start the writing process
5. Monitor progress in real-time via the monitoring dashboard
6. Use Agent Chat with proactive suggestions to guide the writing process
7. Export your finished book in PDF, EPUB, DOCX, or plain text format

### Help & Documentation

Access the **Help & Docs** page from the sidebar navigation for:
- Comprehensive best practices guide
- Phase-by-phase writing tips
- Agent chat and suggestion usage
- Troubleshooting common issues

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
├── book_agent.py               # Main agentic system with skills integration
├── models/
│   ├── book_model.py           # Book project data model (includes skill field)
│   └── version_model.py        # Chapter versioning
├── tools/
│   ├── file_tools.py           # File operations (read, write, edit, search)
│   ├── writing_tools.py        # Writing-specific tools (evaluation, consistency)
├── .agents/skills/             # Domain-specific writing skills system
│   ├── fiction-writer/SKILL.md
│   ├── non-fiction-author/SKILL.md
│   ├── academic-writer/SKILL.md
│   ├── childrens-book-creator/SKILL.md
│   └── screenplay-writer/SKILL.md
├── utils/
│   ├── llm_client.py           # LLM client
│   ├── task_manager.py         # Background tasks
│   ├── database.py             # Data storage
│   ├── storage.py              # File storage
│   ├── export.py               # Export functions
│   └── validation.py           # Input validation
├── templates/                  # HTML templates (includes docs.html)
├── static/                     # CSS, JS, images
└── docs/                       # Documentation (best-practices.md included)
```

## Development

### Adding New Skills

Skills are located in `.agents/skills/` directory. Each skill is a folder with a `SKILL.md` file containing:
- Frontmatter with `name` and `description`
- Usage instructions and best practices
- Tool integration guidance

Follow the [Agent Skills Specification](https://agentskills.io/specification) for progressive disclosure pattern.

### Adding New Tools

1. Create tool class inheriting from `BaseTool`
2. Implement: `name()`, `description()`, `parameters_schema()`, `execute()`
3. Add to writing tools in `tools/writing_tools.py` or file tools in `tools/file_tools.py`

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

- ✅ Domain-specific writing skills system (fiction, non-fiction, academic, children's, screenplay)
- ✅ Agent activity logging and running story summaries
- ✅ Cross-chapter consistency checks during editing
- ✅ Adaptive retry strategies for chapter generation
- ✅ Proactive suggestions in agent chat
- [ ] Multiple language support & translation
- [ ] Collaborative editing & sharing
- [ ] Voice/audio features (text-to-speech, voice input)
- [ ] Advanced analytics & readability scoring

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
