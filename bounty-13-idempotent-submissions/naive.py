"""Intentionally broken baseline used to prove the concurrency test detects duplicates."""
import sqlite3
import time
import uuid


def submit(path, wallet, bounty, key, content):
    connection = sqlite3.connect(path, timeout=30)
    connection.execute(
        "CREATE TABLE IF NOT EXISTS submissions(id TEXT,wallet TEXT,bounty TEXT,key TEXT,content TEXT)"
    )
    existing = connection.execute(
        "SELECT id FROM submissions WHERE wallet=? AND bounty=?", (wallet, bounty)
    ).fetchone()
    if existing:
        connection.close()
        return existing[0]
    time.sleep(0.01)
    submission_id = str(uuid.uuid4())
    connection.execute(
        "INSERT INTO submissions VALUES(?,?,?,?,?)",
        (submission_id, wallet, bounty, key, content),
    )
    connection.commit()
    connection.close()
    return submission_id
