# BookGPT - Installation & Getting Started Guide

This guide will walk you through installing and using BookGPT, even if you've never used Python or command-line tools before.

---

## What is BookGPT?

BookGPT is an AI-powered book writing assistant. It helps you write complete books by:
- Creating detailed outlines
- Developing characters and world-building
- Writing full chapters
- Editing and refining your content

Think of it as having an AI co-author that works with you through the entire book creation process.

---

## Step 1: Download BookGPT

If you're reading this, you've likely already downloaded BookGPT. Make sure you know where the `bookgpt` folder is located on your computer.

---

## Step 2: Run the Quick Start Script

BookGPT includes an automatic setup script that handles everything for you.

### On Windows:

1. Open the `bookgpt` folder
2. Double-click **`quickstart.bat`**
3. Follow the on-screen prompts

### On Mac or Linux:

1. Open the **Terminal** application
2. Navigate to the bookgpt folder:
   ```bash
   cd path/to/bookgpt
   ```
3. Run the setup script:
   ```bash
   ./quickstart.sh
   ```
   > If you get a "permission denied" error, run: `chmod +x quickstart.sh` first

---

## Step 3: Choose Your AI Provider

During setup, you'll be asked to choose an AI provider:

### Option 1: OpenAI (Recommended for most users)
- **What it is:** Uses OpenAI's cloud-based AI models
- **Pros:** High quality output, reliable, no setup required
- **Cons:** Requires an API key (paid usage)
- **What you need:** An OpenAI API key from https://platform.openai.com/api-keys

### Option 2: Ollama (Free, runs locally)
- **What it is:** Runs AI models directly on your computer
- **Pros:** Free, private, no internet required after setup
- **Cons:** Requires downloading Ollama software, uses your computer's resources
- **What you need:** Ollama installed from https://ollama.com/download

**Not sure which to choose?** Start with OpenAI if you have an API key. Use Ollama if you want a free option.

---

## Step 4: Wait for Installation

The script will now:
1. Create a virtual environment (an isolated space for BookGPT)
2. Install required software packages
3. Configure your settings

This may take a few minutes. When it's done, BookGPT will start automatically.

---

## Step 5: Open BookGPT in Your Browser

Once the setup completes, you'll see a message like:

```
BookGPT will be available at: http://localhost:6748
```

Open your web browser (Chrome, Firefox, Safari, or Edge) and go to:
**http://localhost:6748**

### Default Login:
- **Username:** `user`
- **Password:** `password`

> **Important:** Change your password after your first login!

---

## Using BookGPT - Quick Start Guide

### Creating Your First Book Project

1. **Click "New Project"** on the dashboard
2. **Enter your book details:**
   - Title: Your book's title
   - Genre: Fiction, Non-fiction, Fantasy, etc.
   - Target Length: Approximate word count
   - Writing Style: Describe the tone you want

3. **Click "Create Project"**

---

### The 5-Phase Writing Process

BookGPT writes books in organized phases:

#### Phase 1: Planning
The AI creates a detailed chapter-by-chapter outline for your book. Review it and request changes if needed.

#### Phase 2: Research
Develops world-building notes, character profiles, and background information. Great for ensuring consistency.

#### Phase 3: Writing
Writes each chapter based on your outline. You can watch the progress in real-time.

#### Phase 4: Editing
The AI reviews and improves the written content for quality and consistency.

#### Phase 5: Refining
Interactive chat mode where you can request specific changes ("make chapter 3 funnier", "expand the ending")

---

### Downloading Your Book

Once complete, you can export your book in multiple formats:
- **PDF** - For printing or sharing
- **EPUB** - For e-readers (Kindle, Apple Books)
- **DOCX** - For further editing in Word

---

## Troubleshooting

### "Python is not installed"
Run the quickstart script - it will offer to install Python for you, or visit https://www.python.org/downloads/ and install Python 3.8 or newer.

### "Port already in use"
BookGPT uses port 6748. If another program is using it, edit the `.env` file and change `PORT=6748` to another number like `PORT=6749`.

### "OpenAI API key invalid"
Make sure you copied the entire key (starts with `sk-`). You can generate a new one at https://platform.openai.com/api-keys

### Ollama not working
1. Install Ollama from https://ollama.com/download
2. Open a new terminal and run: `ollama pull llama3.1`
3. Restart quickstart

### Can't access localhost:6748
Make sure the quickstart script is still running. If you closed the terminal/command prompt, run quickstart again.

---

## Getting Help

- Check other guides in the `docs/` folder
- Review the README.md for additional information
- Report issues at the project repository

---

## Quick Reference

| Task | How To |
|------|--------|
| Start BookGPT | Run `quickstart.bat` (Windows) or `./quickstart.sh` (Mac/Linux) |
| Stop BookGPT | Press `Ctrl+C` in the terminal |
| Change settings | Edit the `.env` file |
| View project files | Look in the `projects/` folder |
| Reset password | Delete `users.db` and restart |

---

Enjoy writing your book with BookGPT!
