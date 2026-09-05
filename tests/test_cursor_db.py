import sqlite3
from pathlib import Path
from ai_usage_monitor.providers.cursor.db import read_cursor_access_token

def test_read_cursor_access_token_text(tmp_path: Path) -> None:
  db_path = tmp_path / "state.vscdb"
  conn = sqlite3.connect(db_path)
  cursor = conn.cursor()
  cursor.execute("CREATE TABLE ItemTable (key TEXT PRIMARY KEY, value TEXT)")
  cursor.execute("INSERT INTO ItemTable VALUES ('cursorAuth/accessToken', 'sample-token-string')")
  conn.commit()
  conn.close()

  token = read_cursor_access_token(db_path)
  assert token == "sample-token-string"

def test_read_cursor_access_token_utf8_blob(tmp_path: Path) -> None:
  db_path = tmp_path / "state.vscdb"
  conn = sqlite3.connect(db_path)
  cursor = conn.cursor()
  cursor.execute("CREATE TABLE ItemTable (key TEXT PRIMARY KEY, value BLOB)")
  cursor.execute("INSERT INTO ItemTable VALUES ('cursorAuth/accessToken', ?)", ("utf8-blob-token".encode("utf-8"),))
  conn.commit()
  conn.close()

  token = read_cursor_access_token(db_path)
  assert token == "utf8-blob-token"

def test_read_cursor_access_token_utf16le_blob(tmp_path: Path) -> None:
  db_path = tmp_path / "state.vscdb"
  conn = sqlite3.connect(db_path)
  cursor = conn.cursor()
  cursor.execute("CREATE TABLE ItemTable (key TEXT PRIMARY KEY, value BLOB)")
  # UTF-16LE encoding has null bytes at odd indices
  cursor.execute("INSERT INTO ItemTable VALUES ('cursorAuth/accessToken', ?)", ("utf16-blob-token".encode("utf-16le"),))
  conn.commit()
  conn.close()

  token = read_cursor_access_token(db_path)
  assert token == "utf16-blob-token"

def test_read_cursor_access_token_missing_key(tmp_path: Path) -> None:
  db_path = tmp_path / "state.vscdb"
  conn = sqlite3.connect(db_path)
  cursor = conn.cursor()
  cursor.execute("CREATE TABLE ItemTable (key TEXT PRIMARY KEY, value TEXT)")
  conn.commit()
  conn.close()

  token = read_cursor_access_token(db_path)
  assert token is None

def test_read_cursor_access_token_missing_file(tmp_path: Path) -> None:
  missing = tmp_path / "does_not_exist.vscdb"
  token = read_cursor_access_token(missing)
  assert token is None
