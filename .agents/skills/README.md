# BookGPT Skills System

This directory contains specialized writing skills for BookGPT. Each skill provides domain-specific guidance, best practices, and workflow instructions for different types of book writing.

## Available Skills

| Skill | Description | Best For |
|-------|-------------|----------|
| `fiction-writer` | Novel and fiction writing with character arcs, plot beats, dialogue focus | Novels, short stories, fictional content |
| `non-fiction-author` | Research citation, factual accuracy, logical structure, reader education | Guides, memoirs, business books, informative content |
| `academic-writer` | Formal tone, peer-review style, reference formatting, methodological rigor | Textbooks, research papers, academic monographs |
| `childrens-book-creator` | Simple language, educational themes, age-appropriate content, illustration prompts | Picture books, early readers, children's literature |
| `screenplay-writer` | Scene headings, action lines, dialogue formatting, visual storytelling | Film scripts, TV shows, stage plays |

## How Skills Work with BookGPT

1. **Skill Selection**: When creating a new project, select the appropriate skill based on your book type
2. **On-Demand Loading**: The agent loads skill instructions when the task matches the skill description
3. **Specialized Guidance**: Each skill provides domain-specific best practices and validation checklists
4. **Tool Integration**: Skills integrate with BookGPT's existing tools (read_file, write_file, edit_file, grep_search)

## Using Skills via Agent Chat

You can request skill-specific guidance via Agent Chat:

- "Use fiction-writer skills to expand chapter 3's opening scene"
- "Apply non-fiction-author best practices to verify factual accuracy"
- "Format this section according to academic-writer standards"
- "Generate illustration prompts using childrens-book-creator guidelines"
- "Ensure proper screenplay formatting for this script section"

## Creating Custom Skills

To create a new skill:
1. Create a directory named `your-skill-name`
2. Add a `SKILL.md` file with frontmatter (name, description) and instructions
3. Ensure the description is specific enough for the agent to load it when needed

See [Agent Skills Specification](https://agentskills.io/specification) for detailed format requirements.