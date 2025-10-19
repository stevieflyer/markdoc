"""
Task Detail page - view and manage task details
"""

import io
import json
import time
from pathlib import Path
from zipfile import ZipFile
from urllib.parse import urlparse
from datetime import datetime, timezone

import pandas as pd
import streamlit as st

from markdoc.task_manager import task_manager
from markdoc.database import SessionLocal, init_db, DocContent, DocURL, Task
from markdoc.auth import require_authentication, render_logout_button

# Initialize database
init_db()

# Page config
st.set_page_config(
    page_title="MarkDoc - Task Details",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Require authentication
require_authentication()


# Helper functions
def load_task_data(task_id: int):
    """Load task and related data from database"""
    db = SessionLocal()
    try:
        task = db.query(Task).filter(Task.id == task_id).first()
        if not task:
            return None, None, None

        # Load doc_urls
        doc_urls = db.query(DocURL).filter(DocURL.task_id == task_id).all()

        # Load content for doc_urls (using url-based cache)
        doc_contents = {}
        for doc_url in doc_urls:
            content = db.query(DocContent).filter(DocContent.url == doc_url.url).first()
            if content:
                doc_contents[doc_url.id] = {
                    "markdown_content": content.markdown_content,
                    "error_message": content.error_message,
                    "crawled_at": content.crawled_at,
                }

        return task, doc_urls, doc_contents
    finally:
        db.close()


def get_status_icon(status: str):
    """Get icon for status"""
    icons = {"pending": "🔵", "in_progress": "🟡", "done": "✅", "error": "🔴"}
    return icons.get(status, "⚪")


def get_status_text(status: str):
    """Get English text for status"""
    status_map = {
        "pending": "Pending",
        "in_progress": "In Progress",
        "done": "Done",
        "error": "Error",
    }
    return status_map.get(status, status)


def calculate_statistics(task, doc_urls: list):
    """Calculate task statistics"""
    doc_count = len(doc_urls)

    # Calculate status statistics
    link_detection_done = sum(
        1 for doc in doc_urls if doc.link_detection_status == "done"
    )
    content_crawl_done = sum(
        1 for doc in doc_urls if doc.content_crawl_status == "done"
    )

    return {
        "doc_count": doc_count,
        "link_detection_done": link_detection_done,
        "content_crawl_done": content_crawl_done,
        "link_detection_pending": doc_count - link_detection_done,
        "content_crawl_pending": doc_count - content_crawl_done,
    }


def render_task_config(task, task_id: int, can_edit: bool):
    """Render task configuration section"""
    with st.expander("Task Configuration", expanded=False):
        if "edit_mode" not in st.session_state:
            st.session_state.edit_mode = False

        if can_edit:
            col_info, col_btn = st.columns([4, 1])
            with col_btn:
                if st.session_state.edit_mode:
                    if st.button("Cancel Edit"):
                        st.session_state.edit_mode = False
                        st.rerun()
                else:
                    if st.button("✏️ Edit"):
                        st.session_state.edit_mode = True
                        st.rerun()

        if st.session_state.edit_mode and can_edit:
            render_edit_form(task, task_id)
        else:
            render_view_mode(task, can_edit)


def render_edit_form(task, task_id: int):
    """Render edit form for task configuration"""
    with st.form("edit_config_form"):
        st.markdown("### Edit Configuration")

        # Load config
        config = json.loads(task.config) if task.config else {}

        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**Base URL** (read-only):")
            st.code(task.base_url)
        with col2:
            pattern_type_edit = st.radio(
                "Match Type",
                options=["startswith", "regexp"],
                format_func=lambda x: (
                    "Prefix Match" if x == "startswith" else "Regular Expression"
                ),
                index=(
                    0 if config.get("pattern_type", "startswith") == "startswith" else 1
                ),
                horizontal=True,
            )

        st.divider()

        crawl_content_enabled_edit = st.checkbox(
            "Crawl Content",
            value=config.get("crawl_content_enabled", True),
            help="If enabled, the crawler will extract markdown content from each URL. If disabled, only URL discovery will be performed.",
        )

        css_selectors = config.get("content_css_selectors", [])
        css_selectors_text = st.text_area(
            "Content CSS Selectors (optional, one per line)",
            value="\n".join(css_selectors),
            help="Optional CSS selectors to locate specific content areas.",
            height=100,
        )

        st.divider()

        included = config.get("included_patterns", [])
        excluded = config.get("excluded_patterns", [])

        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**Included Patterns** (one per line)")
            included_text = st.text_area(
                "Included Patterns",
                value="\n".join(included),
                height=150,
                label_visibility="collapsed",
            )
        with col2:
            st.markdown("**Excluded Patterns** (one per line)")
            excluded_text = st.text_area(
                "Excluded Patterns",
                value="\n".join(excluded),
                height=150,
                label_visibility="collapsed",
            )

        submitted = st.form_submit_button("Save Changes", type="primary")
        if submitted:
            save_config_changes(
                task_id,
                pattern_type_edit,
                crawl_content_enabled_edit,
                included_text,
                excluded_text,
                css_selectors_text,
            )


def save_config_changes(
    task_id: int,
    pattern_type: str,
    crawl_content_enabled: bool,
    included_text: str,
    excluded_text: str,
    css_selectors_text: str,
):
    """Save configuration changes to database"""
    included_list = [p.strip() for p in included_text.split("\n") if p.strip()]
    excluded_list = [p.strip() for p in excluded_text.split("\n") if p.strip()]
    css_selectors_list = [
        s.strip() for s in css_selectors_text.split("\n") if s.strip()
    ]

    # Build config JSON
    config = {
        "pattern_type": pattern_type,
        "included_patterns": included_list,
        "excluded_patterns": excluded_list,
        "crawl_content_enabled": crawl_content_enabled,
        "content_css_selectors": css_selectors_list,
    }

    db = SessionLocal()
    try:
        task = db.query(Task).filter(Task.id == task_id).first()
        if task:
            task.config = json.dumps(config)
            task.updated_at = datetime.now(timezone.utc)
            db.commit()
            st.success("Configuration updated successfully!")
            st.session_state.edit_mode = False
            time.sleep(1)
            st.rerun()
    except Exception as e:
        st.error(f"Error updating configuration: {e}")
    finally:
        db.close()


def render_view_mode(task, can_edit: bool):
    """Render view mode for task configuration"""
    # Load config
    config = json.loads(task.config) if task.config else {}

    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("**Base URL:**")
        st.code(task.base_url)
    with col2:
        st.markdown("**Match Type:**")
        pattern_type = config.get("pattern_type", "startswith")
        st.code(
            "Prefix Match" if pattern_type == "startswith" else "Regular Expression"
        )
    with col3:
        st.markdown("**Crawl Content:**")
        st.code("Enabled" if config.get("crawl_content_enabled", True) else "Disabled")

    included = config.get("included_patterns", [])
    excluded = config.get("excluded_patterns", [])
    css_selectors = config.get("content_css_selectors", [])

    if css_selectors:
        st.markdown("**Content CSS Selectors:**")
        for selector in css_selectors:
            st.code(selector)

    if included:
        st.markdown("**Included Patterns:**")
        for pattern in included:
            st.code(pattern)
    if excluded:
        st.markdown("**Excluded Patterns:**")
        for pattern in excluded:
            st.code(pattern)

    if not can_edit:
        st.info(
            "⚠️ Cannot edit while task is running. Please pause or cancel the task first."
        )


def render_statistics(task, stats: dict):
    """Render statistics metrics"""
    col1, col2, col3, col4, col5, col6 = st.columns(6)

    # Map status to English
    status_map = {
        "pending": "Pending",
        "running": "Running",
        "paused": "Paused",
        "completed": "Completed",
        "failed": "Failed",
        "cancelled": "Cancelled",
    }
    status_text = status_map.get(task.status, task.status)

    with col1:
        st.metric("Status", status_text)
    with col2:
        st.metric("Document Count", stats["doc_count"])
    with col3:
        st.metric("Scanned", f"{stats['link_detection_done']}/{stats['doc_count']}")
    with col4:
        st.metric("Crawled", f"{stats['content_crawl_done']}/{stats['doc_count']}")
    with col5:
        duration_str = calculate_duration(task)
        st.metric("Duration", duration_str)
    with col6:
        st.metric("Last Updated", task.updated_at.strftime("%H:%M:%S"))


def calculate_duration(task):
    """Calculate task running duration"""
    if not task.started_at:
        return "N/A"

    started_at = (
        task.started_at.replace(tzinfo=timezone.utc)
        if task.started_at.tzinfo is None
        else task.started_at
    )

    if task.completed_at:
        end_time = (
            task.completed_at.replace(tzinfo=timezone.utc)
            if task.completed_at.tzinfo is None
            else task.completed_at
        )
    else:
        end_time = datetime.now(timezone.utc)

    duration = end_time - started_at
    hours = int(duration.total_seconds() // 3600)
    minutes = int((duration.total_seconds() % 3600) // 60)
    seconds = int(duration.total_seconds() % 60)

    if hours > 0:
        return f"{hours}h {minutes}m"
    elif minutes > 0:
        return f"{minutes}m {seconds}s"
    else:
        return f"{seconds}s"


def render_task_controls(task_id: int, task_status: str):
    """Render task control buttons"""
    st.divider()
    st.subheader("Task Controls")

    col1, col2, col3, col4, col5, col6 = st.columns(6)

    with col1:
        if task_status == "pending" and st.button(
            "▶️ Start", type="primary", width="stretch"
        ):
            task_manager.start_task(task_id)
            st.success("Task started!")
            time.sleep(1)
            st.rerun()

    with col2:
        if task_status == "running" and st.button("⏸️ Pause", width="stretch"):
            task_manager.pause_task(task_id)
            st.success("Task paused!")
            time.sleep(1)
            st.rerun()

    with col3:
        if task_status in ["paused", "cancelled"] and st.button(
            "▶️ Resume", type="primary", width="stretch"
        ):
            task_manager.resume_task(task_id)
            st.success("Task resumed!")
            time.sleep(1)
            st.rerun()

    with col4:
        if task_status in ["running", "paused"] and st.button(
            "⏹️ Cancel", width="stretch"
        ):
            task_manager.cancel_task(task_id)
            st.success("Task cancelled!")
            time.sleep(1)
            st.rerun()

    with col5:
        if task_status in ["completed", "failed", "cancelled"] and st.button(
            "🔄 Restart", width="stretch"
        ):
            restart_task(task_id)

    with col6:
        if task_status != "running" and st.button("🗑️ Delete", width="stretch"):
            handle_delete_button(task_id)


def restart_task(task_id: int):
    """Restart a completed/failed task"""
    db = SessionLocal()
    try:
        task = db.query(Task).filter(Task.id == task_id).first()
        if task:
            task.status = "pending"
            task.started_at = None
            task.updated_at = datetime.now(timezone.utc)
            db.commit()
            task_manager.start_task(task_id)
            st.success("Task restarted!")
            time.sleep(1)
            st.rerun()
    finally:
        db.close()


def handle_delete_button(task_id: int):
    """Handle delete button and confirmation"""
    if "confirm_delete" not in st.session_state:
        st.session_state.confirm_delete = False

    if not st.session_state.confirm_delete:
        st.session_state.confirm_delete = True
        st.rerun()
    else:
        if task_manager.delete_task(task_id):
            st.success("Task deleted!")
            time.sleep(1)
            st.switch_page("app.py")
        else:
            st.error("Failed to delete task")
            st.session_state.confirm_delete = False


def render_delete_confirmation(task_id: int):
    """Render delete confirmation dialog"""
    if st.session_state.get("confirm_delete", False):
        st.warning(
            "⚠️ Are you sure you want to delete this task? This action cannot be undone!"
        )
        col1, col2, col3 = st.columns([1, 1, 3])
        with col1:
            if st.button("Confirm Delete", type="primary"):
                if task_manager.delete_task(task_id):
                    st.success("Task deleted!")
                    time.sleep(1)
                    st.switch_page("app.py")
                else:
                    st.error("Failed to delete task")
                    st.session_state.confirm_delete = False
        with col2:
            if st.button("Cancel"):
                st.session_state.confirm_delete = False
                st.rerun()


def render_doc_urls_tab(doc_urls: list, doc_contents: dict, task_id: int):
    """Render document URLs tab with status and content preview"""
    st.subheader("Document List")

    if not doc_urls:
        st.info("No document URLs discovered yet.")
        return

    # Filter controls
    col1, col2, col3 = st.columns(3)
    with col1:
        link_filter = st.selectbox(
            "Link Scan Status",
            ["all", "pending", "in_progress", "done", "error"],
            format_func=lambda x: {
                "all": "All",
                "pending": "Pending",
                "in_progress": "In Progress",
                "done": "Done",
                "error": "Error",
            }.get(x, x),
            key="link_filter",
        )
    with col2:
        content_filter = st.selectbox(
            "Content Crawl Status",
            ["all", "pending", "in_progress", "done", "error"],
            format_func=lambda x: {
                "all": "All",
                "pending": "Pending",
                "in_progress": "In Progress",
                "done": "Done",
                "error": "Error",
            }.get(x, x),
            key="content_filter",
        )
    with col3:
        search_term = st.text_input(
            "Search URLs", placeholder="Enter URL keywords...", key="url_search"
        )

    # Filter doc_urls
    filtered_docs = doc_urls
    if link_filter != "all":
        filtered_docs = [
            doc for doc in filtered_docs if doc.link_detection_status == link_filter
        ]
    if content_filter != "all":
        filtered_docs = [
            doc for doc in filtered_docs if doc.content_crawl_status == content_filter
        ]
    if search_term:
        filtered_docs = [
            doc for doc in filtered_docs if search_term.lower() in doc.url.lower()
        ]

    st.caption(f"Showing {len(filtered_docs)} / {len(doc_urls)} records")

    # Display as dataframe with status
    df_data = []
    for doc in filtered_docs:
        content_info = doc_contents.get(doc.id, {})
        df_data.append(
            {
                "URL": doc.url,
                "Title": (
                    doc.link_text[:50] + "..."
                    if len(doc.link_text) > 50
                    else doc.link_text
                ),
                "Scan Status": f"{get_status_icon(doc.link_detection_status)} {get_status_text(doc.link_detection_status)}",
                "Crawl Status": f"{get_status_icon(doc.content_crawl_status)} {get_status_text(doc.content_crawl_status)}",
                "Content Size": (
                    f"{len(content_info.get('markdown_content', ''))} chars"
                    if content_info
                    else "N/A"
                ),
            }
        )

    df = pd.DataFrame(df_data)

    # Use container with selection
    event = st.dataframe(
        df,
        height=400,
        width="stretch",
        on_select="rerun",
        selection_mode="single-row",
    )

    # Show content preview for selected row
    if event.selection and event.selection.get("rows"):
        selected_idx = event.selection["rows"][0]
        selected_doc = filtered_docs[selected_idx]
        render_content_preview(selected_doc, doc_contents.get(selected_doc.id))

    # Export buttons
    col1, col2 = st.columns(2)

    with col1:
        csv = df.to_csv(index=False)
        st.download_button(
            label="📥 Download CSV",
            data=csv,
            file_name=f"doc_urls_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv",
            use_container_width=True,
        )

    with col2:
        # Count available markdown files
        available_count = sum(
            1
            for doc in doc_urls
            if doc.content_crawl_status == "done" and doc.id in doc_contents
        )

        if available_count > 0:
            if st.button(
                f"📦 Download All Markdown ({available_count} files)",
                use_container_width=True,
                type="primary",
            ):
                with st.spinner("Creating archive..."):
                    # Get task from database
                    db = SessionLocal()
                    try:
                        task = db.query(Task).filter(Task.id == task_id).first()
                        if task:
                            zip_data, count = create_markdown_archive(task, doc_urls)
                            st.success(f"Archive created with {count} files!")

                            # Provide download
                            st.download_button(
                                label="⬇️ Download ZIP",
                                data=zip_data,
                                file_name=f"{task.title}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip",
                                mime="application/zip",
                                use_container_width=True,
                            )
                    finally:
                        db.close()
        else:
            st.button(
                "📦 Download All Markdown (0 files)",
                use_container_width=True,
                disabled=True,
                help="No markdown files available for download",
            )


@st.dialog("📄 Markdown Preview", width="large")
def show_markdown_modal(doc_url: DocURL, content_info: dict | None):
    """Show markdown content in a modal dialog"""
    # Header with URL
    st.markdown(f"**URL:** {doc_url.url}")
    if content_info and content_info.get("crawled_at"):
        st.caption(
            f"Crawled at: {content_info['crawled_at'].strftime('%Y-%m-%d %H:%M:%S')}"
        )

    st.divider()

    if not content_info:
        st.info("Content not yet crawled")
        return

    if content_info.get("error_message"):
        st.error(f"Error: {content_info['error_message']}")
        return

    markdown_content = content_info.get("markdown_content", "")
    if not markdown_content:
        st.warning("Content is empty")
        return

    # Show preview with tabs
    preview_tab1, preview_tab2 = st.tabs(["Rendered Preview", "Markdown Source"])

    with preview_tab1:
        st.markdown(markdown_content)

    with preview_tab2:
        st.code(markdown_content, language="markdown", line_numbers=True)

    # Download button
    # Use link text or URL path as filename
    from urllib.parse import urlparse

    url_path = urlparse(doc_url.url).path
    filename = (
        doc_url.link_text
        if doc_url.link_text
        else url_path.split("/")[-1] or "document"
    )
    filename = sanitize_filename(filename)

    st.download_button(
        label="📥 Download Markdown",
        data=markdown_content,
        file_name=f"{filename}.md",
        mime="text/markdown",
        use_container_width=True,
    )


def render_content_preview(doc_url: DocURL, content_info: dict | None):
    """Render content info and modal trigger"""
    st.divider()
    st.subheader(f"📄 Document Information")

    # Document information
    col1, col2 = st.columns([3, 1])
    with col1:
        st.markdown(f"**URL:** `{doc_url.url}`")
        st.caption(f"Title: {doc_url.link_text}")
    with col2:
        if content_info and content_info.get("crawled_at"):
            st.caption(
                f"Crawled at: {content_info['crawled_at'].strftime('%Y-%m-%d %H:%M:%S')}"
            )

    # Status info
    if not content_info:
        st.info("Content not yet crawled")
    elif content_info.get("error_message"):
        st.error(f"Error: {content_info['error_message']}")
    else:
        markdown_content = content_info.get("markdown_content", "")
        if not markdown_content:
            st.warning("Content is empty")
        else:
            # Show content statistics
            lines_count = len(markdown_content.split("\n"))
            chars_count = len(markdown_content)
            words_count = len(markdown_content.split())

            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Characters", f"{chars_count:,}")
            with col2:
                st.metric("Lines", f"{lines_count:,}")
            with col3:
                st.metric("Words", f"{words_count:,}")

    # Action buttons
    col1, col2 = st.columns(2)
    with col1:
        if content_info and content_info.get("markdown_content"):
            if st.button(
                "🔍 View Details",
                key=f"modal_btn_{doc_url.id}",
                use_container_width=True,
                type="primary",
            ):
                show_markdown_modal(doc_url, content_info)
    with col2:
        if content_info and content_info.get("markdown_content"):
            # Use link text or URL path as filename
            from urllib.parse import urlparse

            url_path = urlparse(doc_url.url).path
            filename = (
                doc_url.link_text
                if doc_url.link_text
                else url_path.split("/")[-1] or "document"
            )
            filename = sanitize_filename(filename)

            st.download_button(
                label="📥 Download Markdown",
                data=content_info.get("markdown_content", ""),
                file_name=f"{filename}.md",
                mime="text/markdown",
                use_container_width=True,
            )


def sanitize_filename(text: str, max_length: int = 100):
    """
    Sanitize text to be safe for use as filename.
    Remove/replace characters that are not allowed in filenames.
    """
    if not text:
        return "untitled"

    # Replace problematic characters with safe alternatives
    text = text.replace("/", "-")
    text = text.replace("\\", "-")
    text = text.replace(":", "-")
    text = text.replace("*", "-")
    text = text.replace("?", "")
    text = text.replace('"', "'")
    text = text.replace("<", "(")
    text = text.replace(">", ")")
    text = text.replace("|", "-")

    # Remove leading/trailing whitespace and dots
    text = text.strip(". ")

    # Truncate if too long
    if len(text) > max_length:
        text = text[:max_length].strip()

    # If empty after sanitization, use fallback
    if not text:
        return "untitled"

    return text


def extract_relative_path(url: str, base_url: str, link_text: str = ""):
    """
    Extract relative path from URL based on base_url, using link_text as filename.

    Example:
        url: https://docs.slack.dev/app-management/quickstart-app-settings
        base_url: https://docs.slack.dev/
        link_text: "Creating an app from app settings"
        result: app-management/Creating an app from app settings.md
    """
    parsed_url = urlparse(url)
    parsed_base = urlparse(base_url)

    # Extract directory path from URL
    if parsed_url.netloc != parsed_base.netloc:
        # If different domain, use full path
        url_path = parsed_url.path.strip("/")
    else:
        # Get path parts
        url_path = parsed_url.path.strip("/")
        base_path = parsed_base.path.strip("/")

        # Remove base path from url path
        if base_path:
            # Add trailing slash for proper comparison
            base_path_with_slash = base_path + "/"
            url_path_with_slash = url_path + "/"

            if url_path_with_slash.startswith(base_path_with_slash):
                url_path = url_path[len(base_path) :].strip("/")
            elif url_path == base_path:
                url_path = ""

    # Get directory part (all except last segment)
    if url_path:
        path_parts = url_path.split("/")
        if len(path_parts) > 1:
            dir_path = "/".join(path_parts[:-1])
        else:
            dir_path = ""
    else:
        dir_path = ""

    # Use link text as filename if available, otherwise use last URL segment
    if link_text and link_text.strip():
        filename = sanitize_filename(link_text.strip())
    else:
        # Fallback to URL last segment
        if url_path:
            path_parts = url_path.split("/")
            filename = path_parts[-1] if path_parts else "index"
        else:
            filename = "index"

    # Combine directory path and filename
    if dir_path:
        full_path = f"{dir_path}/{filename}.md"
    else:
        full_path = f"{filename}.md"

    return full_path


def create_markdown_archive(task: Task, doc_urls: list[DocURL]):
    """
    Create a zip archive with all markdown files organized by URL path structure.
    File names use link text for better readability.
    Returns the zip file as bytes.
    """
    # Create in-memory zip file
    zip_buffer = io.BytesIO()

    with ZipFile(zip_buffer, "w") as zip_file:
        # Track processed URLs to avoid duplicates
        processed_paths = set()
        successful_count = 0

        db = SessionLocal()
        try:
            for doc_url in doc_urls:
                # Get content from database
                content = (
                    db.query(DocContent).filter(DocContent.url == doc_url.url).first()
                )

                if not content or not content.markdown_content:
                    continue

                # Extract relative path using link text as filename
                relative_path = extract_relative_path(
                    doc_url.url, task.base_url, doc_url.link_text
                )

                # Handle duplicates by adding suffix
                original_path = relative_path
                counter = 1
                while relative_path in processed_paths:
                    path_obj = Path(original_path)
                    relative_path = f"{path_obj.stem}_{counter}{path_obj.suffix}"
                    counter += 1

                processed_paths.add(relative_path)

                # Add to zip
                zip_file.writestr(relative_path, content.markdown_content)
                successful_count += 1
        finally:
            db.close()

    zip_buffer.seek(0)
    return zip_buffer.getvalue(), successful_count


# Main execution
def main():
    # Sidebar
    with st.sidebar:
        st.title("📚 MarkDoc")
        st.caption("AI-Powered Document Crawling Engine")

        st.divider()

        # Show current task info if available
        if "selected_task_id" in st.session_state or st.query_params.get("task_id"):
            task_id_for_sidebar = st.session_state.get(
                "selected_task_id"
            ) or st.query_params.get("task_id")
            if task_id_for_sidebar:
                db = SessionLocal()
                try:
                    task = (
                        db.query(Task)
                        .filter(Task.id == int(task_id_for_sidebar))
                        .first()
                    )
                    if task:
                        st.caption("Current Task")
                        st.success(f"**{task.title}**")
                        status_map = {
                            "pending": ("🔵", "Pending"),
                            "running": ("🟢", "Running"),
                            "paused": ("🟡", "Paused"),
                            "completed": ("✅", "Completed"),
                            "failed": ("🔴", "Failed"),
                            "cancelled": ("⚫", "Cancelled"),
                        }
                        icon, text = status_map.get(task.status, ("⚪", task.status))
                        st.caption(f"Status: {icon} {text}")

                        # Quick actions for task
                        st.divider()
                        st.caption("Task Actions")
                        if task.status == "pending":
                            if st.button(
                                "▶️ Start Task", use_container_width=True, type="primary"
                            ):
                                task_manager.start_task(int(task_id_for_sidebar))
                                st.rerun()
                        elif task.status == "running":
                            if st.button("⏸️ Pause Task", use_container_width=True):
                                task_manager.pause_task(int(task_id_for_sidebar))
                                st.rerun()
                        elif task.status in ["paused", "cancelled"]:
                            if st.button(
                                "▶️ Resume Task",
                                use_container_width=True,
                                type="primary",
                            ):
                                task_manager.resume_task(int(task_id_for_sidebar))
                                st.rerun()

                        st.divider()
                finally:
                    db.close()

        # Navigation
        st.caption("Quick Access")
        st.page_link("app.py", label="🏠 All Tasks", use_container_width=True)
        st.page_link(
            "pages/1_create_task.py",
            label="➕ Create New Task",
            use_container_width=True,
        )
        st.page_link(
            "pages/3_browse_docs.py",
            label="📖 Browse Documents",
            use_container_width=True,
        )

        # Logout button
        render_logout_button()

    # Get task_id
    task_id_str = st.query_params.get("task_id")
    task_id = None

    if task_id_str:
        try:
            task_id = int(task_id_str)
        except ValueError:
            st.error("Invalid task ID.")
            st.page_link("app.py", label="← Back to Task List")
            st.stop()
    elif "selected_task_id" in st.session_state:
        task_id = st.session_state.selected_task_id
        st.query_params["task_id"] = str(task_id)

    if not task_id:
        st.error("No task selected. Please select a task from the task list.")
        st.page_link("app.py", label="← Back to Task List")
        st.stop()

    # Load data
    task, doc_urls, doc_contents = load_task_data(task_id)

    if not task:
        st.error(f"Task not found")
        st.page_link("app.py", label="← Back to Task List")
        st.stop()

    # Header
    st.title(f"📊 {task.title}")

    # Map status to English
    status_map = {
        "pending": "Pending",
        "running": "Running",
        "paused": "Paused",
        "completed": "Completed",
        "failed": "Failed",
        "cancelled": "Cancelled",
    }
    status_text = status_map.get(task.status, task.status)
    st.caption(f"Status: {status_text}")

    if st.button("← Back to Task List"):
        st.switch_page("app.py")

    st.divider()

    # Task configuration
    can_edit = task.status not in ["running"]
    render_task_config(task, task_id, can_edit)

    # Statistics
    stats = calculate_statistics(task, doc_urls)
    render_statistics(task, stats)

    # Task controls
    render_task_controls(task_id, task.status)

    # Delete confirmation
    render_delete_confirmation(task_id)

    # Status info
    status_messages = {
        "running": "🟢 Task is running. The system will continuously discover and crawl new URLs.",
        "paused": "🟡 Task is paused. You can resume or cancel the task.",
        "cancelled": "🔴 Task is cancelled. You can resume from where it stopped, or restart the task completely.",
        "completed": "✅ Task completed successfully!",
        "failed": "❌ Task failed. You can restart the task to retry.",
        "pending": "⏳ Task is pending. Click start to begin crawling.",
    }

    message = status_messages.get(task.status)
    if message:
        if task.status in ["completed"]:
            st.success(message)
        elif task.status in ["failed", "cancelled"]:
            st.error(message) if task.status == "failed" else st.info(message)
        else:
            st.info(message)

    st.divider()

    # Document URLs & Content
    render_doc_urls_tab(doc_urls, doc_contents, task_id)

    # Refresh button
    st.divider()
    if st.button("🔄 Refresh Data"):
        st.rerun()


if __name__ == "__main__":
    main()
