# BookGPT: AI-Powered Book Writing with Agentic Loops

An autonomous AI agent that writes complete books using OpenAI (or OpenAI-compatible APIs) with sophisticated tool calling patterns. Modeled after professional coding agents like Cursor, Windsurf, Aider, and OpenAI Codex.

## 🚀 Features

- **🤖 Autonomous Writing**: Complete book generation from title to final draft
- **🛠️ Professional Tools**: File operations modeled after coding agents
- **🔄 Agentic Loop**: Planning → Research → Writing → Editing phases
- **🌐 Multiple LLM Support**: OpenAI, Ollama, LM Studio, Azure, custom endpoints
- **💾 File Management**: Read, write, edit, search files with professional tools
- **📚 Structured Output**: Organized chapters with outlines and research notes

## 🏗️ Architecture

### Core Components

```
BookGPT/
├── book_agent.py          # Main agentic system
├── tools/                 # Professional file & research tools
│   ├── file_tools.py      # File operations (read, write, edit, search)
│   ├── research_tools.py  # Research & outline generation
│   └── __init__.py
├── utils/
│   ├── llm_client.py      # LLM client with OpenAI/custom support
│   └── storage.py         # Project storage
├── models/
│   └── book_model.py      # Book project data model
└── app.py                 # Flask web interface
```

### Tools Inspired by Coding Agents

| Tool | Based On | Function |
|------|----------|----------|
| `ReadFileTool` | Cursor/RooCode | Read files with line numbers and ranges |
| `WriteFileTool` | RooCode | Create/overwrite files with auto-dirs |
| `EditFileTool` | RooCode/Aider | Search & replace with regex support |
| `ListDirectoryTool` | Cursor | List directories, ignore .git/node_modules |
| `SearchFilesTool` | Windsurf | Find files by glob patterns |
| `GrepSearchTool` | RooCode | Search content with context |
| `DeleteFileTool` | Cursor | Safe file deletion |

## 🛠️ Installation

### Prerequisites

- Python 3.8+
- OpenAI API key OR local LLM server

### Setup

```bash
# Clone the repository
git clone <repository-url>
cd bookgpt

# Install dependencies
pip install -r requirements.txt

# Set up environment
export OPENAI_API_KEY="your-api-key"
# OR for local LLM:
export OPENAI_BASE_URL="http://localhost:1234/v1"
export LLM_MODEL="local-model"
```

## 🚀 Quick Start

### 1. Start the Application

```bash
python app.py
```

The web interface will be available at `http://localhost:5000`

### 2. Configure LLM (Optional)

Use the API to configure different LLM providers:

```bash
# OpenAI (default)
curl -X POST http://localhost:5000/api/llm/config \
  -H "Content-Type: application/json" \
  -d '{"model": "gpt-4o"}'

# Ollama (local)
curl -X POST http://localhost:5000/api/llm/preset/ollama \
  -H "Content-Type: application/json" \
  -d '{"model": "llama3.2"}'

# LM Studio (local)
curl -X POST http://localhost:5000/api/llm/preset/lmstudio \
  -H "Content-Type: application/json"
```

### 3. Create a Book Project

```bash
curl -X POST http://localhost:5000/api/projects \
  -H "Content-Type: application/json" \
  -d '{
    "title": "The AI Chronicles",
    "genre": "science_fiction",
    "target_length": 50000,
    "writing_style": "narrative"
  }'
```

### 4. Start Writing

```bash
curl -X POST http://localhost:5000/api/projects/{project_id}/start
```

## 📖 Usage

### Web Interface

1. **Create Project**: Set title, genre, target length
2. **Configure LLM**: Choose OpenAI, Ollama, LM Studio, etc.
3. **Start Writing**: Autonomous generation begins
4. **Monitor Progress**: Track chapters and word count
5. **Download**: Get the final book as text file

### API Usage

```python
import requests

# Create project
response = requests.post('http://localhost:5000/api/projects', json={
    'title': 'My Book',
    'genre': 'fantasy',
    'target_length': 30000,
    'writing_style': 'descriptive'
})
project_id = response.json()['project']['id']

# Start writing
requests.post(f'http://localhost:5000/api/projects/{project_id}/start')

# Check progress
progress = requests.get(f'http://localhost:5000/api/projects/{project_id}/progress')
print(progress.json())

# Download book
response = requests.get(f'http://localhost:5000/api/projects/{project_id}/download')
with open('my_book.txt', 'wb') as f:
    f.write(response.content)
```

### Chat with the Agent

```bash
curl -X POST http://localhost:5000/api/projects/{project_id}/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Can you make the protagonist more mysterious?"}'
```

## 🔧 Configuration

### Environment Variables

```bash
# LLM Configuration
OPENAI_API_KEY=sk-...           # OpenAI API key
OPENAI_BASE_URL=https://...     # Custom endpoint (optional)
LLM_MODEL=gpt-4o                # Model to use

# Flask Configuration
FLASK_SECRET_KEY=your-secret    # Flask secret key
```

### Supported LLM Providers

| Provider | Base URL | Models |
|----------|----------|--------|
| OpenAI | Default | gpt-4o, gpt-4o-mini, gpt-3.5-turbo |
| Ollama | http://localhost:11434/v1 | llama3.2, mistral, codellama |
| LM Studio | http://localhost:1234/v1 | local-model |
| Azure OpenAI | Custom | gpt-4o, gpt-4, gpt-35-turbo |
| Custom | Any | OpenAI-compatible models |

## 🏛️ Agentic Process

### Phase 1: Planning
- AI analyzes book requirements
- Creates detailed chapter-by-chapter outline
- Defines character arcs and plot structure
- **Tool**: `create_outline`

### Phase 2: Research
- Gathers background information
- World-building details and context
- Character research and setting development
- **Tool**: `conduct_research`

### Phase 3: Writing
- Generates chapters sequentially
- Maintains consistency and style
- Uses planning and research as guidance
- **Tools**: `write_file`, `read_file`

### Phase 4: Editing
- Reviews complete manuscript
- Consistency checks and improvements
- Final polish and refinement
- **Tools**: `read_file`, `edit_file`

## 🔍 API Reference

### Projects
- `GET /api/projects` - List all projects
- `POST /api/projects` - Create new project
- `GET /api/projects/{id}` - Get project details
- `POST /api/projects/{id}/start` - Start writing process
- `GET /api/projects/{id}/progress` - Get current progress
- `GET /api/projects/{id}/download` - Download final book
- `POST /api/projects/{id}/chat` - Chat with agent

### LLM Configuration
- `GET /api/llm/config` - Get current configuration
- `POST /api/llm/config` - Update configuration
- `POST /api/llm/test` - Test connection
- `GET /api/llm/presets` - Get available presets
- `POST /api/llm/preset/{name}` - Apply preset

### File Operations
- `GET /api/tools` - List available tools
- `GET /api/projects/{id}/files` - List project files
- `GET /api/projects/{id}/files/{path}` - Read specific file

## 🛠️ Development

### Project Structure

```python
bookgpt/
├── book_agent.py          # Main agentic system
├── tools/                 # Tool implementations
│   ├── file_tools.py      # File operations (Cursor/Windsurf/Aider style)
│   └── research_tools.py  # Research and outline tools
├── utils/
│   ├── llm_client.py      # LLM client with OpenAI/custom support
│   └── storage.py         # Project persistence
├── models/
│   └── book_model.py      # Book project data model
└── app.py                 # Flask web application
```

### Adding New Tools

1. Create tool class inheriting from `BaseTool`
2. Implement required methods: `name()`, `description()`, `parameters_schema()`, `execute()`
3. Add to `get_all_tools()` in `app.py`

```python
class MyTool(BaseTool):
    def name(self) -> str:
        return "my_tool"
    
    def description(self) -> str:
        return "Description of what this tool does"
    
    def parameters_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "param1": {"type": "string", "description": "Parameter description"}
            },
            "required": ["param1"]
        }
    
    def execute(self, param1: str) -> Dict[str, Any]:
        # Tool implementation
        return {"success": True, "result": f"Processed: {param1}"}
```

### Testing

```bash
# Run with debug mode
python app.py

# Test LLM connection
curl -X POST http://localhost:5000/api/llm/test

# Test tool operations
curl -X GET http://localhost:5000/api/tools
```

## 🤝 Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- **OpenAI** for function calling patterns
- **Cursor** for file operation tool design
- **Windsurf** for directory listing patterns
- **Aider** for search and replace functionality
- **OpenAI Codex** for agentic loop structure

## 📊 Performance

- **Planning Phase**: ~30-60 seconds (outline generation)
- **Research Phase**: ~20-40 seconds (background research)
- **Writing Phase**: ~2-5 minutes per chapter (5000 words)
- **Editing Phase**: ~60-90 seconds (review and polish)

*Times vary by model and content complexity*

## 🔮 Roadmap

- [ ] Multiple language support
- [ ] Character consistency tracking
- [ ] Plot coherence validation
- [ ] Export to multiple formats (PDF, EPUB)
- [ ] Collaborative editing
- [ ] Version control for drafts
- [ ] Advanced customization options

## 📞 Support

For support and questions:

1. Check the [API documentation](#api-reference)
2. Review [configuration options](#configuration)
3. Open an issue on GitHub
4. Join our [Skool Community](https://www.skool.com/open-source-ai-builders-club/about)

---

**Built with ❤️ using modern AI agent patterns and professional tool design principles.**
The A-Tech Corporation PTY LTD.


