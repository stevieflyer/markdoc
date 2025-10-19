"""
Create/Edit Task page
"""

import json
import time
from datetime import datetime, timezone

import streamlit as st

from markdoc.database import SessionLocal, init_db, Task
from markdoc.auth import require_authentication, render_logout_button

# Initialize database
init_db()

# Page config
st.set_page_config(
    page_title="MarkDoc - Create Task",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Require authentication
require_authentication()

# Sidebar
with st.sidebar:
    st.title("📚 MarkDoc")
    st.caption("AI-Powered Document Crawling Engine")

    st.divider()

    # Help info
    st.info(
        "💡 **Task Creation Guide**\n\n1. Fill in task name and starting URL\n2. Configure crawling rules\n3. Set URL filtering patterns\n4. Submit and start crawling"
    )

    st.divider()

    # Navigation
    st.caption("Quick Access")
    st.page_link("app.py", label="🏠 All Tasks", use_container_width=True)
    st.page_link(
        "pages/3_browse_docs.py",
        label="📖 Browse Documents",
        use_container_width=True,
    )

    # Logout button
    render_logout_button()

st.title("➕ Create New Task")

# Form
st.subheader("Basic Information")

title = st.text_input(
    "Task Title *",
    placeholder="e.g.: Slack API Documentation",
    help="Give this crawling task a descriptive name",
)

base_url = st.text_input(
    "Starting URL *",
    placeholder="https://docs.slack.dev",
    help="The starting URL for crawling (e.g.: https://docs.slack.dev)",
)

st.divider()
st.subheader("Crawling Options")

crawl_content_enabled = st.checkbox(
    "Crawl Content",
    value=True,
    help="If enabled, the crawler will extract markdown content from each URL. If disabled, only URL discovery will be performed.",
)

content_css_selectors = st.text_area(
    "Content CSS Selectors (optional, one per line)",
    placeholder="article\nnav\n.content",
    help="Optional CSS selectors to locate specific content areas. If provided, only content matching these selectors will be extracted. If selectors don't match, the crawler will automatically fall back to extracting all content.",
    height=100,
)

st.divider()
st.subheader("URL Pattern Filtering")

pattern_type = st.radio(
    "Match Type",
    options=["startswith", "regexp"],
    format_func=lambda x: "Prefix Match" if x == "startswith" else "Regular Expression",
    horizontal=True,
    help="Choose URL matching method: simple prefix matching or regular expressions",
)

col1, col2 = st.columns(2)

with col1:
    st.markdown("**Included Patterns** (one per line)")
    if pattern_type == "startswith":
        included_help = "Enter URL prefixes to include (one per line).\n\nExamples:\nhttps://docs.slack.dev/api\nhttps://docs.slack.dev/guides\n\nLeave empty to include all links starting with the base URL."
        included_placeholder = (
            "https://docs.slack.dev/api\nhttps://docs.slack.dev/guides"
        )
    else:
        included_help = "Enter regular expression patterns to include (one per line).\n\nExamples:\nhttps://docs\\.slack\\.dev/api/.*\nhttps://docs\\.slack\\.dev/guides/.*\n\nLeave empty to include all links starting with the base URL."
        included_placeholder = (
            "https://docs\\.slack\\.dev/api/.*\nhttps://docs\\.slack\\.dev/guides/.*"
        )

    included_patterns = st.text_area(
        "Included Patterns",
        placeholder=included_placeholder,
        help=included_help,
        height=150,
        label_visibility="collapsed",
    )

with col2:
    st.markdown("**Excluded Patterns** (one per line)")
    if pattern_type == "startswith":
        excluded_help = "Enter URL prefixes to exclude (one per line).\n\nExamples:\nhttps://docs.slack.dev/legacy/\nhttps://docs.slack.dev/changelog/\n\nLeave empty to exclude no URLs."
        excluded_placeholder = (
            "https://docs.slack.dev/legacy/\nhttps://docs.slack.dev/changelog/"
        )
    else:
        excluded_help = "Enter regular expression patterns to exclude (one per line).\n\nExamples:\nhttps://docs\\.slack\\.dev/legacy/.*\nhttps://docs\\.slack\\.dev/changelog/.*\n\nLeave empty to exclude no URLs."
        excluded_placeholder = "https://docs\\.slack\\.dev/legacy/.*\nhttps://docs\\.slack\\.dev/changelog/.*"

    excluded_patterns = st.text_area(
        "Excluded Patterns",
        placeholder=excluded_placeholder,
        help=excluded_help,
        height=150,
        label_visibility="collapsed",
    )

st.divider()

# Validation
is_valid = bool(title and title.strip() and base_url and base_url.strip())

# Submit buttons
col1, col2, col3 = st.columns([1, 1, 3])

with col1:
    preview = st.button("Preview Configuration", use_container_width=True)

with col2:
    submitted = st.button(
        "Create Task",
        type="primary",
        disabled=not is_valid,
        use_container_width=True,
    )

with col3:
    cancelled = st.button("Cancel", use_container_width=True)

if cancelled:
    st.switch_page("app.py")

if preview:
    # Show configuration preview
    included_list = [p.strip() for p in included_patterns.split("\n") if p.strip()]
    excluded_list = [p.strip() for p in excluded_patterns.split("\n") if p.strip()]
    css_selectors_list = [
        s.strip() for s in content_css_selectors.split("\n") if s.strip()
    ]

    st.subheader("Configuration Preview")

    config_preview = {
        "title": title,
        "base_url": base_url,
        "config": {
            "crawl_content_enabled": crawl_content_enabled,
            "pattern_type": pattern_type,
            "included_patterns": (
                included_list
                if included_list
                else ["(empty - will include all links starting with base URL)"]
            ),
            "excluded_patterns": (
                excluded_list if excluded_list else ["(empty - will exclude no links)"]
            ),
            "content_css_selectors": (
                css_selectors_list
                if css_selectors_list
                else ["(empty - will extract all content)"]
            ),
        },
        "status": "pending",
    }

    st.json(config_preview)

    st.info(
        "Please review the configuration above. If it looks correct, click the 'Create Task' button to continue."
    )

if submitted:
    # Parse patterns
    included_list = [p.strip() for p in included_patterns.split("\n") if p.strip()]
    excluded_list = [p.strip() for p in excluded_patterns.split("\n") if p.strip()]
    css_selectors_list = [
        s.strip() for s in content_css_selectors.split("\n") if s.strip()
    ]

    # Build config JSON
    config = {
        "pattern_type": pattern_type,
        "included_patterns": included_list,
        "excluded_patterns": excluded_list,
        "crawl_content_enabled": crawl_content_enabled,
        "content_css_selectors": css_selectors_list,
    }

    # Create task
    db = SessionLocal()
    try:
        task = Task(
            title=title,
            base_url=base_url,
            config=json.dumps(config),
            status="pending",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db.add(task)
        db.commit()
        db.refresh(task)

        st.success(f"Task '{title}' created successfully!")
        st.info("Redirecting to task list...")
        time.sleep(1)
        st.switch_page("app.py")

    except Exception as e:
        st.error(f"Error creating task: {e}")
    finally:
        db.close()
