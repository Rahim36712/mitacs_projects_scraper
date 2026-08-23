"""
Simple SQLite persistence for visited URLs and saved projects.
This supports restartability and idempotency for incremental crawls.
"""
import sqlite3
from typing import Optional, Dict
import json


class Database:
    def __init__(self, path: str):
        self.path = path
        self.conn = sqlite3.connect(self.path)
        self._init()

    def _init(self):
        c = self.conn.cursor()
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS projects (
                project_id TEXT PRIMARY KEY,
                url TEXT,
                data TEXT
            )
            """
        )
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS visited_urls (
                url TEXT PRIMARY KEY,
                visited_at TEXT
            )
            """
        )
        self.conn.commit()

    def save_project(self, project: Dict) -> None:
        pid = project.get('project_id') or project.get('url')
        c = self.conn.cursor()
        c.execute('INSERT OR REPLACE INTO projects (project_id, url, data) VALUES (?, ?, ?)',
                  (pid, project.get('url'), json.dumps(project, ensure_ascii=False)))
        self.conn.commit()

    def has_visited(self, url: str) -> bool:
        c = self.conn.cursor()
        c.execute('SELECT 1 FROM visited_urls WHERE url = ?', (url,))
        return c.fetchone() is not None

    def mark_visited(self, url: str, visited_at: str) -> None:
        c = self.conn.cursor()
        c.execute('INSERT OR REPLACE INTO visited_urls (url, visited_at) VALUES (?, ?)', (url, visited_at))
        self.conn.commit()

    def close(self):
        self.conn.close()
