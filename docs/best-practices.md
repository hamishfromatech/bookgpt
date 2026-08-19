# BookGPT: Best Practices & Complete Guide

Welcome to the comprehensive guide for getting the most out of BookGPT. This document covers exact steps, tips, tricks, and best practices to maximize your AI-assisted book writing experience.

---

## 📚 Table of Contents

1. [Getting Started](#getting-started)
2. [Understanding the Writing Pipeline](#understanding-the-writing-pipeline)
3. [Phase 1: Planning & Outline Generation](#phase-1-planning--outline-generation)
4. [Phase 2: Research & Background](#phase-2-research--background)
5. [Phase 3: Chapter Writing](#phase-3-chapter-writing)
6. [Phase 4: Editing & Refinement](#phase-4-editing--refinement)
7. [Agent Chat & Proactive Suggestions](#agent-chat--proactive-suggestions)
8. [Exporting Your Book](#exporting-your-book)
9. [Pro Tips & Tricks](#pro-tips--tricks)
10. [Troubleshooting Common Issues](#troubleshooting-common-issues)

---

## Getting Started

### 1. Initial Setup

Before starting your book project, ensure you have:

- **AI Provider Configured**: Set up OpenAI API key or configure a local LLM (Ollama, LM Studio)
- **Project Details Ready**: Have your book title, genre, and target word count in mind
- **Writing Style Selected**: Choose from Narrative, Descriptive, Conversational, or Formal

### 2. Creating Your First Project

1. Click **"New Project"** on the dashboard
2. Fill in the required details:
   - **Book Title**: Make it compelling and specific
   - **Genre**: Select the closest match (Fiction, Non-Fiction, Fantasy, Mystery, Sci-Fi)
   - **Target Words**: Recommended 30,000-60,000 for standard novels
   - **Writing Style**: Choose based on your target audience

---

## Understanding the Writing Pipeline

BookGPT uses a sophisticated 5-phase agentic pipeline modeled after professional coding agents:

```
Planning → Research → Writing → Editing → Refining (Agent Mode)
```

Each phase builds upon the previous one, ensuring narrative coherence and quality throughout.

---

## Phase 1: Planning & Outline Generation

### What Happens Here

The agent creates a detailed chapter-by-chapter outline including:
- Overall story premise and themes
- Main characters with brief descriptions
- Chapter-by-chapter breakdown
- Key plot points and story beats
- Character arcs and development

### Tips for Success

✅ **Be Specific in Your Genre Selection**: The more specific your genre, the better the agent understands reader expectations.

✅ **Set Realistic Target Lengths**: 
   - Short stories: 5,000-10,000 words
   - Novellas: 20,000-30,000 words
   - Standard novels: 50,000-80,000 words

✅ **Review the Outline Carefully**: Before proceeding to research, ensure the chapter structure aligns with your vision. You can ask the agent to adjust the outline via Agent Chat.

---

## Phase 2: Research & Background

### What Happens Here

The agent gathers background information for:
- World-building details relevant to the story
- Character background research
- Setting descriptions and atmosphere notes
- Technical or historical details needed
- Genre-specific elements to include

### Tips for Success

✅ **Provide Context in Your Description**: When creating your project, include specific world-building elements you want explored (e.g., "Victorian London with magical elements").

✅ **Review Research Notes**: The agent generates `research_notes.md` which contains valuable context for later phases. Review this before writing begins.

---

## Phase 3: Chapter Writing

### What Happens Here

The agent writes chapters sequentially, maintaining:
- Narrative flow and pacing
- Character consistency
- Plot coherence
- Vivid descriptions and natural dialogue

### Tips for Success

✅ **Let the Agent Work Sequentially**: The agent reads previous chapters to maintain continuity. Don't interrupt the writing process prematurely.

✅ **Monitor Progress**: Use the monitoring dashboard to track:
   - Current chapter being written
   - Total words generated
   - Phase progress indicators

✅ **Adaptive Recovery**: If a chapter generation fails, the agent automatically tries fallback strategies with simplified prompts and reduced token limits.

---

## Phase 4: Editing & Refinement

### What Happens Here

The agent performs targeted edits across all chapters:
- Grammar, spelling, punctuation corrections
- Inconsistent character names, locations, or facts
- Awkward phrasing and word choice improvements
- Pacing issue identification
- Dialogue quality enhancement

### Cross-Chapter Consistency Checks

Before editing each chapter, the agent uses `grep_search` to:
- Verify character name consistency across all chapters
- Check location mentions for continuity
- Flag potential plot holes or timeline inconsistencies

### Tips for Success

✅ **Review Editing Notes**: The agent generates `editing_notes.md` summarizing all changes made. Review this document for insights into the editing process.

✅ **Use Agent Suggestions**: During the editing phase, proactive suggestions will appear in the chat drawer recommending consistency checks or specific improvements.

---

## Agent Chat & Proactive Suggestions

### Accessing Agent Chat

Click **"Agent Chat"** on the monitoring dashboard to open the sliding chat drawer. This is your interactive interface with the Supervisor AI.

### Understanding Proactive Suggestions

The agent analyzes your project state and provides context-aware suggestions:

| Suggestion Type | When It Appears | What It Does |
|-----------------|-----------------|--------------|
| **Review and Edit Chapters** | 3+ chapters written, not in editing phase | Recommends starting the editing phase |
| **Check Character Consistency** | Multiple characters introduced | Offers to verify character descriptions across chapters |
| **Review Cross-Chapter Consistency** | During editing with consistency notes | Highlights specific inconsistencies found |
| **Export Your Book** | In refining/completed phase | Reminds you of available export formats |
| **Review Chapter Outline** | Early writing phase (<5 chapters) | Suggests reviewing pacing and plot structure |

### How to Use Agent Chat Effectively

✅ **Be Specific in Your Requests**: Instead of "make it better", say "expand chapter 3's opening scene with more sensory details".

✅ **Reference Specific Chapters**: Use format like "In chapter 5, the protagonist's motivation feels unclear. Can you help clarify this?"

✅ **Use Tool-Specific Commands**:
   - "Check character consistency for 'Sarah' across all chapters"
   - "Read outline.md and suggest plot improvements"
   - "Edit chapter_2.md to improve dialogue quality"

✅ **Review Agent Actions**: The activity feed shows what the agent is doing:
   - Tool calls (read_file, edit_file, grep_search)
   - Reasoning and decisions made
   - Changes applied

---

## Exporting Your Book

### Available Formats

Once your book reaches the "refining" or "completed" phase, you can export in multiple formats:

| Format | Best For | Features |
|--------|----------|----------|
| **PDF** | Printing, sharing, reading on devices | Proper formatting, chapter headings, page breaks |
| **EPUB** | E-readers, Kindle | Responsive layout, navigation |
| **DOCX** | Further editing in Word | Editable format, familiar interface |
| **Plain Text** | Lightweight sharing, processing | No formatting, universal compatibility |

### Export Steps

1. Ensure your book is in "refining" or "completed" phase
2. Click the export button in the project details
3. Select your preferred format
4. Download the generated file

---

## Pro Tips & Tricks

### 1. Optimize Your Writing Style Selection

- **Narrative**: Best for traditional storytelling with clear plot progression
- **Descriptive**: Ideal for world-building heavy fiction or literary fiction
- **Conversational**: Works well for contemporary fiction, romance, or light reading
- **Formal**: Suitable for historical fiction, academic non-fiction, or serious literature

### 2. Manage Chapter Length Expectations

The agent targets approximately 5,000 words per chapter based on your total target length. For a 50,000-word book, expect ~10 chapters. Adjust your target length accordingly.

### 3. Use Running Summaries Effectively

BookGPT maintains a running story summary that includes:
- Brief summary of story progress
- Characters introduced so far
- Locations mentioned

This helps maintain narrative continuity across chapters. Review this in the agent chat if you need to adjust character descriptions or plot directions.

### 4. Leverage Agent Activity Logging

The activity log shows:
- Phase transitions (planning → research → writing → editing)
- Chapter completion status
- Tool calls made by the agent
- Consistency check results

Use this to understand the agent's decision-making process and verify quality at each step.

### 5. Handle Interruptions Gracefully

If the writing process is interrupted:
- The agent saves state to the database automatically
- Use "Resume" button to continue from where it left off
- Running summaries and activity logs are preserved

---

## Troubleshooting Common Issues

### Issue: Chapter Generation Fails or Times Out

**Solution**: The agent uses adaptive retry strategies:
1. First attempt uses standard prompt and token limits
2. If truncated or failed, tries with reduced tokens (down to 2048)
3. Final fallback uses simplified prompts

If all retries fail, check your LLM provider's API status or rate limits.

### Issue: Inconsistent Character Names Across Chapters

**Solution**: 
1. Open Agent Chat
2. Use suggestion: "Check character and location consistency across all chapters"
3. Review the grep_search results for variations in names
4. Request targeted edits using `edit_file` tool

### Issue: Chapter Seems Rushed or Incomplete

**Solution**:
1. Check the running summary to verify story progression
2. Use Agent Chat to request expansion: "Expand chapter 5's climax scene with more detail"
3. The agent can use `write_file` for complete chapter rewrites if needed

### Issue: Export Format Not Available

**Solution**: Ensure your book has reached the "refining" or "completed" phase. Export options are only available after all writing and editing phases are complete.

---

## Final Thoughts

BookGPT is designed to be a collaborative partner in your writing journey. The agentic pipeline ensures quality through systematic planning, research, writing, and editing phases. By understanding how the agent works and using the proactive suggestions effectively, you can create compelling, well-structured books with AI assistance.

Remember:
- **Review at Each Phase**: Don't rush through the pipeline; review outlines, research notes, and edited chapters
- **Use Agent Chat Proactively**: The agent is ready to assist with structural edits, style refinements, or specific content adjustments
- **Iterate and Refine**: Use the refining phase to make targeted improvements based on your vision

Happy writing! 📖✨