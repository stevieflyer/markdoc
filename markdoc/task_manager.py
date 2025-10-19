"""
Task manager for managing crawler threads.
"""

import threading
from datetime import datetime, timezone

from markdoc.crawler import CrawlerWorker
from markdoc.database import SessionLocal, Task


class TaskManager:
    """Singleton task manager for managing crawler threads"""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._threads: dict[int, tuple[threading.Thread, CrawlerWorker]] = {}
        self._threads_lock = threading.Lock()
        self._initialized = True

    def start_task(self, task_id: int):
        """Start a crawling task"""
        with self._threads_lock:
            # Check if already running
            if task_id in self._threads:
                thread, _ = self._threads[task_id]
                if thread.is_alive():
                    print(f"Task {task_id} is already running")
                    return False

            # Update task status to running
            db = SessionLocal()
            try:
                task = db.query(Task).filter(Task.id == task_id).first()
                if not task:
                    print(f"Task {task_id} not found")
                    return False

                task.status = "running"
                # Set started_at if this is the first time starting (not resuming)
                if not task.started_at:
                    task.started_at = datetime.now(timezone.utc)
                task.updated_at = datetime.now(timezone.utc)
                db.commit()
            finally:
                db.close()

            # Create and start crawler thread
            worker = CrawlerWorker(task_id)
            thread = threading.Thread(target=worker.run, daemon=True)
            thread.start()

            self._threads[task_id] = (thread, worker)
            print(f"Task {task_id} started")
            return True

    def pause_task(self, task_id: int):
        """Pause a running task"""
        db = SessionLocal()
        try:
            task = db.query(Task).filter(Task.id == task_id).first()
            if not task:
                return False

            task.status = "paused"
            task.updated_at = datetime.now(timezone.utc)
            db.commit()
            print(f"Task {task_id} paused")
            return True
        finally:
            db.close()

    def resume_task(self, task_id: int):
        """Resume a paused task"""
        return self.start_task(task_id)

    def cancel_task(self, task_id: int):
        """Cancel a running task"""
        with self._threads_lock:
            # Update task status
            db = SessionLocal()
            try:
                task = db.query(Task).filter(Task.id == task_id).first()
                if not task:
                    return False

                task.status = "cancelled"
                task.completed_at = datetime.now(timezone.utc)
                task.updated_at = datetime.now(timezone.utc)
                db.commit()
            finally:
                db.close()

            # Stop the thread if running
            if task_id in self._threads:
                thread, worker = self._threads[task_id]
                worker.stop()
                # Note: thread will stop on next status check
                del self._threads[task_id]

            print(f"Task {task_id} cancelled")
            return True

    def delete_task(self, task_id: int):
        """Delete a task and all related data"""
        with self._threads_lock:
            # Stop the thread if running
            if task_id in self._threads:
                thread, worker = self._threads[task_id]
                if thread.is_alive():
                    print(f"Cannot delete task {task_id}: task is still running")
                    return False
                worker.stop()
                del self._threads[task_id]

            # Delete from database (cascade will handle related records)
            db = SessionLocal()
            try:
                task = db.query(Task).filter(Task.id == task_id).first()
                if not task:
                    print(f"Task {task_id} not found")
                    return False

                # Check if task is running
                if task.status == "running":
                    print(f"Cannot delete task {task_id}: task is running")
                    return False

                db.delete(task)
                db.commit()
                print(f"Task {task_id} deleted")
                return True
            except Exception as e:
                print(f"Error deleting task {task_id}: {e}")
                db.rollback()
                return False
            finally:
                db.close()

    def get_task_status(self, task_id: int):
        """Get current status of a task"""
        db = SessionLocal()
        try:
            task = db.query(Task).filter(Task.id == task_id).first()
            if task:
                return task.status
            return None
        finally:
            db.close()

    def is_task_running(self, task_id: int):
        """Check if task thread is alive"""
        with self._threads_lock:
            if task_id in self._threads:
                thread, _ = self._threads[task_id]
                return thread.is_alive()
            return False

    def cleanup_finished_threads(self):
        """Remove finished threads from the manager"""
        with self._threads_lock:
            to_remove = []
            for task_id, (thread, _) in self._threads.items():
                if not thread.is_alive():
                    to_remove.append(task_id)

            for task_id in to_remove:
                del self._threads[task_id]


# Global task manager instance
task_manager = TaskManager()
