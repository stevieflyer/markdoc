"""
Browse Documents page - Browse and download documentation from completed projects
"""

import io
import json
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse
from zipfile import ZipFile

import streamlit as st

from markdoc.database import SessionLocal, init_db, Task, DocURL, DocContent
from markdoc.auth import require_authentication, render_logout_button

# Initialize database
init_db()

# Page config
st.set_page_config(
    page_title="MarkDoc - Browse Documents",
    page_icon="📖",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Require authentication
require_authentication()


def sanitize_filename(text: str, max_length: int = 100):
    """Sanitize text to be safe for use as filename."""
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
    """Extract relative path from URL based on base_url, using link_text as filename."""
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
    """Create a zip archive with all markdown files."""
    zip_buffer = io.BytesIO()

    with ZipFile(zip_buffer, "w") as zip_file:
        processed_paths = set()
        successful_count = 0

        db = SessionLocal()
        try:
            for doc_url in doc_urls:
                content = (
                    db.query(DocContent).filter(DocContent.url == doc_url.url).first()
                )

                if not content or not content.markdown_content:
                    continue

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


def load_available_projects():
    """Load all projects (tasks) that have documents."""
    db = SessionLocal()
    try:
        tasks = db.query(Task).order_by(Task.created_at.desc()).all()

        # Filter tasks that have at least one document
        projects = []
        for task in tasks:
            doc_count = db.query(DocURL).filter(DocURL.task_id == task.id).count()
            if doc_count > 0:
                projects.append(
                    {
                        "id": task.id,
                        "title": task.title,
                        "base_url": task.base_url,
                        "status": task.status,
                        "doc_count": doc_count,
                        "created_at": task.created_at,
                    }
                )

        return projects
    finally:
        db.close()


def load_project_documents(project_id: int):
    """Load all documents for a specific project."""
    db = SessionLocal()
    try:
        task = db.query(Task).filter(Task.id == project_id).first()
        if not task:
            return None, []

        doc_urls = db.query(DocURL).filter(DocURL.task_id == project_id).all()

        # Load content for each document
        documents = []
        for doc_url in doc_urls:
            content = db.query(DocContent).filter(DocContent.url == doc_url.url).first()

            doc_info = {
                "id": doc_url.id,
                "url": doc_url.url,
                "title": doc_url.link_text,
                "status": doc_url.content_crawl_status,
                "has_content": bool(content and content.markdown_content),
                "content_size": (
                    len(content.markdown_content)
                    if content and content.markdown_content
                    else 0
                ),
                "error": content.error_message if content else None,
            }

            if content and content.markdown_content:
                doc_info["content"] = content.markdown_content
                doc_info["crawled_at"] = content.crawled_at

            documents.append(doc_info)

        return task, documents
    finally:
        db.close()


@st.dialog("📄 Document Viewer", width="large")
def show_document_modal(doc: dict):
    """Show document content in a modal dialog."""
    st.markdown(f"**Title:** {doc['title']}")
    st.markdown(f"**URL:** {doc['url']}")

    if doc.get("crawled_at"):
        st.caption(f"Crawled at: {doc['crawled_at'].strftime('%Y-%m-%d %H:%M:%S')}")

    st.divider()

    if not doc.get("has_content"):
        st.info("No content available for this document")
        return

    if doc.get("error"):
        st.error(f"Error: {doc['error']}")
        return

    content = doc.get("content", "")
    if not content:
        st.warning("Content is empty")
        return

    # Show tabs for rendered and source view
    tab1, tab2 = st.tabs(["📖 Rendered", "📝 Markdown Source"])

    with tab1:
        st.markdown(content)

    with tab2:
        st.code(content, language="markdown", line_numbers=True)

    st.divider()

    # Download button
    filename = sanitize_filename(
        doc["title"]
        if doc["title"]
        else urlparse(doc["url"]).path.split("/")[-1] or "document"
    )
    st.download_button(
        label="📥 Download Markdown",
        data=content,
        file_name=f"{filename}.md",
        mime="text/markdown",
        use_container_width=True,
        type="primary",
    )


def render_document_card(doc: dict, idx: int):
    """Render a single document as a card."""
    with st.container():
        col1, col2 = st.columns([4, 1])

        with col1:
            # Title
            if doc["has_content"]:
                st.markdown(f"**📄 {doc['title'] or 'Untitled'}**")
            else:
                st.markdown(f"**📄 {doc['title'] or 'Untitled'}** ⚠️")

            # URL
            st.caption(f"🔗 {doc['url']}")

            # Status info
            if doc["has_content"]:
                # Show content stats
                chars = doc["content_size"]
                lines = doc.get("content", "").count("\n") + 1
                st.caption(f"📊 {chars:,} characters · {lines:,} lines")
            else:
                status_text = {
                    "pending": "⏳ Pending",
                    "in_progress": "🔄 In Progress",
                    "done": "✅ Done (no content)",
                    "error": f"❌ Error: {doc.get('error', 'Unknown')}",
                }.get(doc["status"], doc["status"])
                st.caption(status_text)

        with col2:
            if doc["has_content"]:
                if st.button(
                    "👁️ View",
                    key=f"view_{idx}",
                    use_container_width=True,
                    type="primary",
                ):
                    show_document_modal(doc)

                # Download button
                filename = sanitize_filename(
                    doc["title"]
                    if doc["title"]
                    else urlparse(doc["url"]).path.split("/")[-1] or "document"
                )
                st.download_button(
                    label="📥",
                    data=doc.get("content", ""),
                    file_name=f"{filename}.md",
                    mime="text/markdown",
                    use_container_width=True,
                    key=f"download_{idx}",
                    help="Download this document",
                )


def main():
    # Sidebar
    with st.sidebar:
        st.title("📖 MarkDoc")
        st.caption("Document Browser")

        st.divider()

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
            label="📖 Browse Documents (Current)",
            use_container_width=True,
        )

        st.divider()

        # Logout button
        render_logout_button()

        st.divider()

        st.info(
            "💡 **Tip**\n\n"
            "This page allows you to browse and download documents from your completed projects.\n\n"
            "Select a project to view all its documents."
        )

    # Main content
    st.title("📖 Browse Documents")
    st.markdown("View and download documentation from your projects")

    st.divider()

    # Load available projects
    projects = load_available_projects()

    if not projects:
        st.info(
            "📭 No projects with documents found. Create a task and crawl some documentation first!"
        )
        st.page_link("pages/1_create_task.py", label="➕ Create Your First Task")
        return

    # Project selector
    st.subheader("📚 Select a Document Project")

    # Create a nice display for project selection
    project_options = {
        f"{p['title']} ({p['doc_count']} docs)": p["id"] for p in projects
    }

    selected_project_label = st.selectbox(
        "Choose a project:",
        options=list(project_options.keys()),
        index=0,
        key="project_selector",
    )

    selected_project_id = project_options[selected_project_label]

    # Load project details
    task, documents = load_project_documents(selected_project_id)

    if not task:
        st.error("Failed to load project details")
        return

    st.divider()

    # Project information
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("📄 Total Documents", len(documents))

    with col2:
        available_docs = sum(1 for doc in documents if doc["has_content"])
        st.metric("✅ Available", available_docs)

    with col3:
        total_size = sum(doc["content_size"] for doc in documents if doc["has_content"])
        size_kb = total_size / 1024
        st.metric("📊 Total Size", f"{size_kb:.1f} KB")

    with col4:
        # Status badge
        status_map = {
            "pending": "⏳ Pending",
            "running": "🔄 Running",
            "paused": "⏸️ Paused",
            "completed": "✅ Completed",
            "failed": "❌ Failed",
            "cancelled": "⏹️ Cancelled",
        }
        st.metric("Status", status_map.get(task.status, task.status))

    st.markdown(f"**Base URL:** `{task.base_url}`")

    # Download all button
    st.divider()

    available_count = sum(1 for doc in documents if doc["has_content"])

    col1, col2, col3 = st.columns([2, 1, 1])

    with col1:
        st.markdown("### 📦 Download Options")

    with col2:
        if available_count > 0:
            if st.button(
                f"📦 Download All ({available_count} files)",
                use_container_width=True,
                type="primary",
            ):
                with st.spinner("Creating archive..."):
                    db = SessionLocal()
                    try:
                        task_obj = (
                            db.query(Task)
                            .filter(Task.id == selected_project_id)
                            .first()
                        )
                        doc_urls = (
                            db.query(DocURL)
                            .filter(DocURL.task_id == selected_project_id)
                            .all()
                        )

                        zip_data, count = create_markdown_archive(task_obj, doc_urls)

                        st.success(f"✅ Archive created with {count} files!")

                        st.download_button(
                            label="⬇️ Download ZIP",
                            data=zip_data,
                            file_name=f"{sanitize_filename(task.title)}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip",
                            mime="application/zip",
                            use_container_width=True,
                            type="primary",
                        )
                    finally:
                        db.close()
        else:
            st.button(
                "📦 Download All (0 files)",
                disabled=True,
                use_container_width=True,
                help="No documents available for download",
            )

    with col3:
        if st.button("🔄 Refresh", use_container_width=True):
            st.rerun()

    st.divider()

    # Filter and search
    st.subheader("📋 Document List")

    col1, col2 = st.columns([2, 3])

    with col1:
        filter_option = st.selectbox(
            "Filter by:",
            options=["all", "available", "unavailable"],
            format_func=lambda x: {
                "all": "All Documents",
                "available": "✅ Available Only",
                "unavailable": "⚠️ Unavailable Only",
            }[x],
        )

    with col2:
        search_term = st.text_input(
            "🔍 Search documents",
            placeholder="Search by title or URL...",
        )

    # Filter documents
    filtered_docs = documents

    if filter_option == "available":
        filtered_docs = [doc for doc in filtered_docs if doc["has_content"]]
    elif filter_option == "unavailable":
        filtered_docs = [doc for doc in filtered_docs if not doc["has_content"]]

    if search_term:
        search_lower = search_term.lower()
        filtered_docs = [
            doc
            for doc in filtered_docs
            if search_lower in doc["title"].lower()
            or search_lower in doc["url"].lower()
        ]

    st.caption(f"Showing {len(filtered_docs)} of {len(documents)} documents")

    st.divider()

    # Display documents
    if not filtered_docs:
        st.info("No documents match your filter criteria")
    else:
        for idx, doc in enumerate(filtered_docs):
            render_document_card(doc, idx)
            if idx < len(filtered_docs) - 1:
                st.divider()


if __name__ == "__main__":
    main()
