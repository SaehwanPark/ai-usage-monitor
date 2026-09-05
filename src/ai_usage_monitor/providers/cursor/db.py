"""Read-only access to Cursor desktop state.vscdb SQLite database."""

from __future__ import annotations

from pathlib import Path
import sqlite3
from ai_usage_monitor.windows.paths import get_cursor_db_path


def _decode_sqlite_value(val: bytes | str | None) -> str | None:
  """Decode token value from SQLite TEXT or BLOB column."""
  if val is None:
    return None
  if isinstance(val, str):
    return val.strip() or None

  if isinstance(val, bytes):
    if not val:
      return None
    # Check if looks like ASCII in UTF-16LE (even length, odd bytes are 0, even bytes are ascii)
    if len(val) % 2 == 0 and all(val[i] == 0 for i in range(1, len(val), 2)):
      try:
        decoded = val.decode("utf-16le").strip()
        if decoded:
          return decoded
      except Exception:
        pass

    try:
      decoded = val.decode("utf-8").strip()
      if decoded:
        return decoded
    except Exception:
      pass

    try:
      decoded = val.decode("utf-16le").strip()
      if decoded:
        return decoded
    except Exception:
      pass

  return None


def read_cursor_access_token(db_path: Path | None = None) -> str | None:
  """Read cursorAuth/accessToken from Cursor's state.vscdb in read-only mode."""
  target_path = db_path or get_cursor_db_path()
  if not target_path.is_file():
    return None

  uri = f"file:{target_path.as_posix()}?mode=ro"
  conn: sqlite3.Connection | None = None
  try:
    conn = sqlite3.connect(uri, uri=True, timeout=0.25)
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM ItemTable WHERE key = ? LIMIT 1", ("cursorAuth/accessToken",))
    row = cursor.fetchone()
    if row and row[0] is not None:
      return _decode_sqlite_value(row[0])
  except Exception:
    return None
  finally:
    if conn:
      try:
        conn.close()
      except Exception:
        pass

  return None
