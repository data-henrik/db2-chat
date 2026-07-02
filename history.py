import json
import sqlite3

DB_PATH = "ochat.db"


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Create the messages table if it does not already exist."""
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS messages (
                id              INTEGER PRIMARY KEY,
                conversation_id TEXT        NOT NULL,
                role            TEXT        NOT NULL,
                content         TEXT        NOT NULL,
                created_at      TIMESTAMP   DEFAULT CURRENT_TIMESTAMP
            )
            """
        )


def save_message(conv_id: str, role: str, content) -> None:
    """Insert one message row. content is JSON-serialised to handle dicts."""
    with _connect() as conn:
        conn.execute(
            "INSERT INTO messages (conversation_id, role, content) VALUES (?, ?, ?)",
            (conv_id, role, json.dumps(content)),
        )


def load_history(conv_id: str) -> list[dict]:
    """Return all messages for a conversation as {"role", "content"} dicts.

    Orphaned tool messages (no preceding assistant+tool_calls) and raw
    <tool_call> assistant messages (model hallucination) are stripped so that
    Ollama always receives a well-formed message sequence.
    """
    with _connect() as conn:
        rows = conn.execute(
            "SELECT role, content FROM messages WHERE conversation_id = ? ORDER BY id",
            (conv_id,),
        ).fetchall()

    messages = []
    for row in rows:
        role = row["role"]
        try:
            content = json.loads(row["content"])
        except (json.JSONDecodeError, TypeError):
            continue  # skip rows with corrupt content

        # If the stored value is a full message dict (has a "role" key), use it
        # directly — this handles assistant messages saved with tool_calls.
        if isinstance(content, dict) and "role" in content:
            msg = content
        else:
            msg = {"role": role, "content": content}

        # Drop raw <tool_call> text that some models emit instead of using the
        # structured tool_calls field — they confuse subsequent model calls.
        if msg.get("role") == "assistant" and isinstance(msg.get("content"), str) \
                and "<tool_call>" in msg["content"]:
            continue

        # Drop tool messages that have no preceding assistant message with
        # tool_calls — Ollama rejects this sequence.
        if msg.get("role") == "tool":
            if not messages or messages[-1].get("role") != "assistant" or \
                    not messages[-1].get("tool_calls"):
                continue

        messages.append(msg)

    return messages


def list_conversations() -> list[dict]:
    """Return one entry per conversation with its last_updated time and a preview."""
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT
                conversation_id,
                MAX(created_at) AS last_updated,
                content         AS last_content
            FROM messages
            GROUP BY conversation_id
            ORDER BY last_updated DESC
            """
        ).fetchall()
    result = []
    for row in rows:
        text = json.loads(row["last_content"])
        if isinstance(text, dict):
            text = str(text)
        preview = text[:60]
        result.append(
            {
                "conversation_id": row["conversation_id"],
                "last_updated": row["last_updated"],
                "preview": preview,
            }
        )
    return result


def delete_conversation(conv_id: str) -> None:
    """Delete all messages belonging to the given conversation."""
    with _connect() as conn:
        conn.execute(
            "DELETE FROM messages WHERE conversation_id = ?",
            (conv_id,),
        )
