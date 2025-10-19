"""
Streamlit main application - Task List page
"""

import time

import streamlit as st

from markdoc.task_manager import task_manager
from markdoc.database import SessionLocal, init_db, Task, DocURL
from markdoc.auth import require_authentication, render_logout_button

# Initialize database
init_db()

# Page config
st.set_page_config(
    page_title="MarkDoc - Task List",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Require authentication
require_authentication()

st.title("📚 MarkDoc")
st.markdown("### AI-Powered Document Crawling Engine")

# Auto-refresh control
if "auto_refresh" not in st.session_state:
    st.session_state.auto_refresh = True

# Sidebar
with st.sidebar:
    st.title("📚 MarkDoc")
    st.caption("AI-Powered Document Crawling Engine")

    st.divider()

    # Quick actions
    if st.button("➕ Create New Task", use_container_width=True, type="primary"):
        st.switch_page("pages/1_create_task.py")

    st.divider()

    # Logout button
    render_logout_button()

    st.divider()

    # Navigation
    st.caption("Quick Access")
    st.markdown("🏠 **All Tasks** (Current Page)")
    st.page_link(
        "pages/3_browse_docs.py",
        label="📖 Browse Documents",
        use_container_width=True,
    )

    st.divider()

    # Settings
    st.caption("Page Settings")
    auto_refresh = st.checkbox(
        "Auto Refresh",
        value=st.session_state.auto_refresh,
        help="Automatically refresh page every 3 seconds",
    )
    st.session_state.auto_refresh = auto_refresh

    if st.button("🔄 Manual Refresh", use_container_width=True):
        st.rerun()

# Cleanup finished threads
task_manager.cleanup_finished_threads()

# Load tasks
db = SessionLocal()
try:
    tasks = db.query(Task).order_by(Task.created_at.desc()).all()
finally:
    db.close()

if not tasks:
    st.info("No tasks yet. Create your first crawling task!")
    st.page_link("pages/1_create_task.py", label="➕ Create Task")
else:
    # Display tasks in a table-like format
    for task in tasks:
        with st.container():
            col1, col2, col3, col4 = st.columns([3, 2, 2, 3])

            with col1:
                st.markdown(f"**{task.title}**")
                st.caption(f"Created: {task.created_at.strftime('%Y-%m-%d %H:%M')}")

            with col2:
                # Status badge
                status_map = {
                    "pending": ("🔵", "Pending"),
                    "running": ("🟢", "Running"),
                    "paused": ("🟡", "Paused"),
                    "completed": ("✅", "Completed"),
                    "failed": ("🔴", "Failed"),
                    "cancelled": ("⚫", "Cancelled"),
                }
                status_icon, status_text = status_map.get(
                    task.status, ("⚪", task.status)
                )
                st.markdown(f"{status_icon} **{status_text}**")

            with col3:
                # Statistics - query counts directly to avoid detached instance error
                db = SessionLocal()
                try:
                    doc_count = (
                        db.query(DocURL).filter(DocURL.task_id == task.id).count()
                    )
                finally:
                    db.close()
                st.caption(f"Documents: {doc_count}")

            with col4:
                # Action buttons
                btn_col1, btn_col2, btn_col3, btn_col4, btn_col5 = st.columns(5)

                with btn_col1:
                    if task.status in ["pending", "paused"]:
                        if st.button("▶️", key=f"start_{task.id}", help="Start Task"):
                            task_manager.start_task(task.id)
                            st.rerun()

                with btn_col2:
                    if task.status == "running":
                        if st.button("⏸️", key=f"pause_{task.id}", help="Pause Task"):
                            task_manager.pause_task(task.id)
                            st.rerun()

                with btn_col3:
                    if task.status in ["running", "paused"]:
                        if st.button("⏹️", key=f"cancel_{task.id}", help="Cancel Task"):
                            task_manager.cancel_task(task.id)
                            st.rerun()

                with btn_col4:
                    if st.button("📊", key=f"detail_{task.id}", help="View Details"):
                        # Use session_state to pass task_id
                        st.session_state.selected_task_id = task.id
                        st.switch_page("pages/2_task_detail.py")

                with btn_col5:
                    if task.status != "running":
                        if st.button("🗑️", key=f"delete_{task.id}", help="Delete Task"):
                            if task_manager.delete_task(task.id):
                                st.success(f"Task deleted!")
                                time.sleep(1)
                                st.rerun()
                            else:
                                st.error("Failed to delete task")

            st.divider()

# Auto-refresh logic
if st.session_state.auto_refresh:
    time.sleep(3)
    st.rerun()
