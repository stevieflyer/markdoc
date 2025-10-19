# MarkDoc

📚 AI-Powered Document Crawling Engine

MarkDoc is a powerful documentation crawler built with Streamlit that helps you collect, organize, and browse documentation from any website.

## Features

### 🎯 Core Features

- **Task Management**: Create and manage documentation crawling tasks
- **Smart Crawling**: Automatically discover and crawl documentation pages
- **Content Extraction**: Extract clean markdown content from web pages
- **Pattern Filtering**: Use prefix matching or regular expressions to include/exclude URLs
- **CSS Selectors**: Target specific content areas on pages

### 📖 Document Browsing (NEW!)

The new **Browse Documents** page provides an enhanced experience for viewing your crawled documentation:

- **Project-based View**: Browse documents organized by project (formerly called "Tasks")
- **Rich Document Cards**: See document titles, URLs, and statistics at a glance
- **In-app Preview**: View rendered markdown or source code directly in the app
- **Quick Search**: Find documents by title or URL
- **Smart Filtering**: Filter by availability status
- **Batch Download**: Download all documents from a project as a ZIP archive
- **Individual Downloads**: Download single documents as needed

### 📊 Task Management

- **Real-time Status**: Monitor crawling progress in real-time
- **Flexible Controls**: Start, pause, resume, or cancel tasks
- **Statistics Dashboard**: View document counts, crawl progress, and duration
- **Configuration**: Edit crawling rules and patterns on the fly

## Pages

### 🏠 All Tasks (Home)
- View all crawling tasks
- Quick task controls
- Auto-refresh option

### ➕ Create New Task
- Set up new documentation crawling projects
- Configure URL patterns
- Set content extraction rules

### 📊 Task Details
- Detailed task information
- Document list with status
- Task configuration editor
- Content preview

### 📖 Browse Documents (NEW!)
- **Select a document project** to browse
- **View all documents** in a user-friendly card layout
- **Search and filter** documents easily
- **Preview documents** with rendered markdown view
- **Download individual documents** or the entire project as ZIP
- **See statistics**: Total documents, available count, and total size

## Installation & Setup

### 1. Clone and Install Dependencies

```bash
# Clone the repository
cd /path/to/markdoc

# Install dependencies with uv
uv sync
```

### 2. Configure the Application

Copy the template files and edit them with your settings:

```bash
# Copy config templates
cp config.toml.template config.toml
cp auth_config.yaml.template auth_config.yaml
```

Edit `config.toml`:
- Add your OpenRouter API key
- Add your Jina API key

Edit `auth_config.yaml`:
- Change the cookie secret key
- Update admin credentials (username, password, email)

⚠️ **Important**: These config files contain sensitive information and are excluded from git.

### 3. Streamlit Cloud Deployment (Optional)

If you want to deploy to Streamlit Cloud, see [DEPLOYMENT.md](DEPLOYMENT.md) for detailed instructions.

Quick summary:
- The app automatically detects Streamlit Cloud environment
- Configure secrets through Streamlit Cloud's Web UI
- Use `.streamlit/secrets.toml.template` as reference

## Usage

### Starting the Application

```bash
# Make sure you're in the project directory
cd /path/to/markdoc

# Run with Streamlit
streamlit run markdoc/app.py

# Or use the Makefile
make run
```

### Creating Your First Project

1. Click **"➕ Create New Task"** from the home page
2. Fill in:
   - **Task Title**: A descriptive name (e.g., "Slack API Documentation")
   - **Starting URL**: The base URL to crawl (e.g., `https://docs.slack.dev`)
3. Configure crawling options:
   - Enable/disable content crawling
   - Set CSS selectors (optional)
   - Add URL patterns to include/exclude
4. Click **"Create Task"** to save

### Browsing Documents

1. Click **"📖 Browse Documents"** from any page
2. Select a project from the dropdown
3. Browse the document list:
   - Use the search box to find specific documents
   - Filter by availability status
   - Click **"👁️ View"** to preview a document
   - Click **"📥"** to download individual documents
4. Use **"📦 Download All"** to get the entire project as a ZIP file

The downloaded ZIP file will maintain the directory structure based on the original URLs, with files named using the document titles for better readability.

### Running a Crawl Task

1. Start the task from the home page or task details page
2. Monitor progress in real-time
3. Pause, resume, or cancel as needed
4. Once completed, browse the documents!

## Project Structure

```
markdoc/
├── markdoc/
│   ├── app.py                    # Main application (Task List)
│   ├── config.py                 # Configuration
│   ├── crawler.py                # Web crawling logic
│   ├── task_manager.py           # Task execution management
│   ├── database/
│   │   ├── models.py             # SQLAlchemy models
│   │   └── engine.py             # Database setup
│   ├── pages/
│   │   ├── 1_create_task.py      # Create/Edit Task page
│   │   ├── 2_task_detail.py      # Task Details page
│   │   └── 3_browse_docs.py      # Browse Documents page (NEW!)
│   └── utils/
│       └── jina_utils.py         # Jina AI integration
├── config.toml                   # App configuration
├── markdoc.db                    # SQLite database
└── README.md                     # This file
```

## Database Schema

### Tasks
- Stores crawling task information
- Status tracking (pending, running, paused, completed, failed, cancelled)
- Configuration (URL patterns, CSS selectors, etc.)

### DocURLs
- Discovered documentation URLs
- Link text and metadata
- Status for link detection and content crawling

### DocContent
- Cached markdown content (by URL)
- Crawl timestamps
- Error messages (if any)

## Tips

- **Use descriptive titles**: Help yourself find projects later
- **Configure URL patterns carefully**: Prevent crawling unwanted pages
- **Use CSS selectors**: Extract only the content you need
- **Browse before downloading**: Preview documents to ensure quality
- **Regular expressions**: For complex URL filtering needs
- **Monitor progress**: Check the task details page while crawling

## Technologies

- **Streamlit**: Web interface
- **SQLAlchemy**: Database ORM
- **Jina AI**: Web content extraction
- **SQLite**: Data storage

---

Made with ❤️ for documentation enthusiasts


