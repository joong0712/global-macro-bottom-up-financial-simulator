"""MySQL 기반 사용자 인증 정보와 분석 기록 저장소."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pymysql
from google.cloud import firestore
from dotenv import load_dotenv


load_dotenv()

PASSWORD_ITERATIONS = 600_000
EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
_INIT_LOCK = threading.Lock()
_INITIALIZED_PATHS: set[str] = set()
_FIRESTORE_CLIENT = None


class UserAlreadyExistsError(ValueError):
    """이미 가입된 이메일일 때 발생한다."""


def _database_path() -> Path:
    configured = os.getenv("APP_DB_PATH")
    if configured:
        return Path(configured).expanduser().resolve()
    return Path(__file__).resolve().parent / "data" / "app.db"


def _mysql_configured() -> bool:
    return all(
        os.getenv(name)
        for name in (
            "MYSQL_HOST",
            "MYSQL_DATABASE",
            "MYSQL_USER",
            "MYSQL_PASSWORD",
        )
    )


def database_backend() -> str:
    configured = os.getenv("USER_STORE_BACKEND", "").strip().lower()
    if configured:
        if configured not in {"firestore", "mysql", "sqlite"}:
            raise ValueError(
                "USER_STORE_BACKEND는 firestore, mysql, sqlite 중 하나여야 합니다."
            )
        return configured
    if os.getenv("APP_DB_PATH"):
        return "sqlite"
    if os.getenv("K_SERVICE"):
        return "firestore"
    if _mysql_configured():
        return "mysql"
    return "sqlite"


def _mysql_enabled() -> bool:
    return database_backend() == "mysql"


def _firestore_enabled() -> bool:
    return database_backend() == "firestore"


def _firestore_client():
    global _FIRESTORE_CLIENT
    if _FIRESTORE_CLIENT is None:
        project = (
            os.getenv("GOOGLE_CLOUD_PROJECT")
            or os.getenv("GCLOUD_PROJECT")
            or None
        )
        database = os.getenv("FIRESTORE_DATABASE", "(default)")
        _FIRESTORE_CLIENT = firestore.Client(
            project=project,
            database=database,
        )
    return _FIRESTORE_CLIENT


def _firestore_user_id(email: str) -> str:
    return hashlib.sha256(normalize_email(email).encode("utf-8")).hexdigest()


def _connection_key() -> str:
    if _firestore_enabled():
        project = os.getenv("GOOGLE_CLOUD_PROJECT", "auto")
        database = os.getenv("FIRESTORE_DATABASE", "(default)")
        return f"firestore://{project}/{database}"
    if _mysql_enabled():
        return (
            f"mysql://{os.getenv('MYSQL_HOST')}:{os.getenv('MYSQL_PORT', '3306')}"
            f"/{os.getenv('MYSQL_DATABASE')}"
        )
    return f"sqlite://{_database_path()}"


@contextmanager
def _connection():
    if _mysql_enabled():
        connection = pymysql.connect(
            host=os.environ["MYSQL_HOST"],
            port=int(os.getenv("MYSQL_PORT", "3306")),
            user=os.environ["MYSQL_USER"],
            password=os.environ["MYSQL_PASSWORD"],
            database=os.environ["MYSQL_DATABASE"],
            charset="utf8mb4",
            cursorclass=pymysql.cursors.DictCursor,
            autocommit=False,
            connect_timeout=10,
            read_timeout=10,
            write_timeout=10,
        )
    else:
        path = _database_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 10000")
    try:
        yield connection
    except Exception:
        connection.rollback()
        raise
    else:
        connection.commit()
    finally:
        connection.close()


def _adapt_query(query: str) -> str:
    return query.replace("?", "%s") if _mysql_enabled() else query


def _execute(connection, query: str, parameters: tuple[Any, ...] = ()):
    cursor = connection.cursor()
    cursor.execute(_adapt_query(query), parameters)
    return cursor


def initialize_database() -> None:
    """사용자·기록 테이블을 필요한 경우 한 번 생성한다."""
    connection_key = _connection_key()
    if connection_key in _INITIALIZED_PATHS:
        return
    with _INIT_LOCK:
        if connection_key in _INITIALIZED_PATHS:
            return
        if _firestore_enabled():
            _firestore_client()
            _INITIALIZED_PATHS.add(connection_key)
            return
        with _connection() as connection:
            if _mysql_enabled():
                _execute(
                    connection,
                    """
                    CREATE TABLE IF NOT EXISTS users (
                        id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
                        email VARCHAR(254) NOT NULL,
                        display_name VARCHAR(30) NOT NULL,
                        password_hash VARCHAR(128) NOT NULL,
                        password_salt VARCHAR(64) NOT NULL,
                        password_iterations INT UNSIGNED NOT NULL,
                        created_at VARCHAR(40) NOT NULL,
                        last_login_at VARCHAR(40) NULL,
                        PRIMARY KEY (id),
                        UNIQUE KEY uq_users_email (email)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                    COLLATE=utf8mb4_unicode_ci
                    """,
                )
                _execute(
                    connection,
                    """
                    CREATE TABLE IF NOT EXISTS user_history (
                        id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
                        user_id BIGINT UNSIGNED NOT NULL,
                        event_type VARCHAR(50) NOT NULL,
                        title VARCHAR(255) NOT NULL,
                        payload_json LONGTEXT NOT NULL,
                        created_at VARCHAR(40) NOT NULL,
                        PRIMARY KEY (id),
                        KEY idx_user_history_user_created (
                            user_id, created_at DESC
                        ),
                        CONSTRAINT fk_user_history_user
                            FOREIGN KEY (user_id) REFERENCES users(id)
                            ON DELETE CASCADE
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                    COLLATE=utf8mb4_unicode_ci
                    """,
                )
            else:
                connection.executescript(
                    """
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    email TEXT NOT NULL COLLATE NOCASE UNIQUE,
                    display_name TEXT NOT NULL,
                    password_hash TEXT NOT NULL,
                    password_salt TEXT NOT NULL,
                    password_iterations INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    last_login_at TEXT
                );

                CREATE TABLE IF NOT EXISTS user_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    event_type TEXT NOT NULL,
                    title TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_user_history_user_created
                ON user_history(user_id, created_at DESC);
                    """
                )
        _INITIALIZED_PATHS.add(connection_key)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def normalize_email(email: str) -> str:
    return email.strip().lower()


def validate_registration(
    email: str,
    display_name: str,
    password: str,
) -> tuple[str, str]:
    normalized_email = normalize_email(email)
    normalized_name = " ".join(display_name.strip().split())
    if not EMAIL_PATTERN.fullmatch(normalized_email):
        raise ValueError("올바른 이메일 주소를 입력해 주세요.")
    if not 2 <= len(normalized_name) <= 30:
        raise ValueError("이름은 2~30자로 입력해 주세요.")
    if len(password) < 8:
        raise ValueError("비밀번호는 8자 이상이어야 합니다.")
    if len(password) > 128:
        raise ValueError("비밀번호는 128자 이하로 입력해 주세요.")
    if not any(character.isalpha() for character in password):
        raise ValueError("비밀번호에 영문자를 하나 이상 포함해 주세요.")
    if not any(character.isdigit() for character in password):
        raise ValueError("비밀번호에 숫자를 하나 이상 포함해 주세요.")
    return normalized_email, normalized_name


def _password_digest(password: str, salt: bytes, iterations: int) -> bytes:
    return hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        iterations,
    )


def create_user(email: str, display_name: str, password: str) -> dict[str, Any]:
    initialize_database()
    normalized_email, normalized_name = validate_registration(
        email,
        display_name,
        password,
    )
    salt = secrets.token_bytes(16)
    digest = _password_digest(password, salt, PASSWORD_ITERATIONS)
    if _firestore_enabled():
        client = _firestore_client()
        document = client.collection("users").document(
            _firestore_user_id(normalized_email)
        )
        transaction = client.transaction()

        @firestore.transactional
        def create_in_transaction(current_transaction):
            if document.get(transaction=current_transaction).exists:
                raise UserAlreadyExistsError("이미 가입된 이메일입니다.")
            current_transaction.set(
                document,
                {
                    "email": normalized_email,
                    "display_name": normalized_name,
                    "password_hash": base64.b64encode(digest).decode("ascii"),
                    "password_salt": base64.b64encode(salt).decode("ascii"),
                    "password_iterations": PASSWORD_ITERATIONS,
                    "created_at": _utc_now(),
                    "last_login_at": None,
                },
            )

        create_in_transaction(transaction)
        return {
            "id": document.id,
            "email": normalized_email,
            "display_name": normalized_name,
        }
    try:
        with _connection() as connection:
            cursor = _execute(
                connection,
                """
                INSERT INTO users (
                    email, display_name, password_hash, password_salt,
                    password_iterations, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    normalized_email,
                    normalized_name,
                    base64.b64encode(digest).decode("ascii"),
                    base64.b64encode(salt).decode("ascii"),
                    PASSWORD_ITERATIONS,
                    _utc_now(),
                ),
            )
            user_id = int(cursor.lastrowid)
    except (sqlite3.IntegrityError, pymysql.err.IntegrityError) as error:
        raise UserAlreadyExistsError("이미 가입된 이메일입니다.") from error
    return {
        "id": user_id,
        "email": normalized_email,
        "display_name": normalized_name,
    }


def authenticate_user(email: str, password: str) -> dict[str, Any] | None:
    initialize_database()
    if not password or len(password) > 128:
        return None
    if _firestore_enabled():
        document = _firestore_client().collection("users").document(
            _firestore_user_id(email)
        )
        snapshot = document.get()
        if not snapshot.exists:
            return None
        row = snapshot.to_dict() or {}
        salt = base64.b64decode(row["password_salt"])
        expected = base64.b64decode(row["password_hash"])
        actual = _password_digest(
            password,
            salt,
            int(row["password_iterations"]),
        )
        if not hmac.compare_digest(actual, expected):
            return None
        document.update({"last_login_at": _utc_now()})
        return {
            "id": document.id,
            "email": str(row["email"]),
            "display_name": str(row["display_name"]),
        }
    with _connection() as connection:
        row = _execute(
            connection,
            "SELECT * FROM users WHERE email = ?",
            (normalize_email(email),),
        ).fetchone()
        if row is None:
            return None
        salt = base64.b64decode(row["password_salt"])
        expected = base64.b64decode(row["password_hash"])
        actual = _password_digest(
            password,
            salt,
            int(row["password_iterations"]),
        )
        if not hmac.compare_digest(actual, expected):
            return None
        _execute(
            connection,
            "UPDATE users SET last_login_at = ? WHERE id = ?",
            (_utc_now(), int(row["id"])),
        )
    return {
        "id": int(row["id"]),
        "email": str(row["email"]),
        "display_name": str(row["display_name"]),
    }


def add_history(
    user_id: int | str,
    event_type: str,
    title: str,
    payload: dict[str, Any] | None = None,
) -> int | str:
    initialize_database()
    if _firestore_enabled():
        clean_payload = json.loads(
            json.dumps(payload or {}, ensure_ascii=False, default=str)
        )
        document = (
            _firestore_client()
            .collection("users")
            .document(str(user_id))
            .collection("history")
            .document()
        )
        document.set(
            {
                "event_type": event_type.strip(),
                "title": title.strip(),
                "payload": clean_payload,
                "created_at": _utc_now(),
            }
        )
        return document.id
    serialized = json.dumps(
        payload or {},
        ensure_ascii=False,
        separators=(",", ":"),
        default=str,
    )
    with _connection() as connection:
        cursor = _execute(
            connection,
            """
            INSERT INTO user_history (
                user_id, event_type, title, payload_json, created_at
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (int(user_id), event_type.strip(), title.strip(), serialized, _utc_now()),
        )
        return int(cursor.lastrowid)


def list_history(
    user_id: int | str,
    *,
    event_type: str | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    initialize_database()
    safe_limit = max(1, min(int(limit), 500))
    if _firestore_enabled():
        query = (
            _firestore_client()
            .collection("users")
            .document(str(user_id))
            .collection("history")
            .order_by("created_at", direction=firestore.Query.DESCENDING)
            .limit(500 if event_type else safe_limit)
        )
        records: list[dict[str, Any]] = []
        for snapshot in query.stream():
            row = snapshot.to_dict() or {}
            if event_type and row.get("event_type") != event_type:
                continue
            records.append(
                {
                    "id": snapshot.id,
                    "event_type": str(row.get("event_type", "")),
                    "title": str(row.get("title", "")),
                    "payload": row.get("payload") or {},
                    "created_at": str(row.get("created_at", "")),
                }
            )
            if len(records) >= safe_limit:
                break
        return records
    query = """
        SELECT id, event_type, title, payload_json, created_at
        FROM user_history
        WHERE user_id = ?
    """
    parameters: list[Any] = [int(user_id)]
    if event_type:
        query += " AND event_type = ?"
        parameters.append(event_type)
    query += " ORDER BY created_at DESC, id DESC LIMIT ?"
    parameters.append(safe_limit)
    with _connection() as connection:
        rows = _execute(connection, query, tuple(parameters)).fetchall()
    return [
        {
            "id": int(row["id"]),
            "event_type": str(row["event_type"]),
            "title": str(row["title"]),
            "payload": json.loads(row["payload_json"]),
            "created_at": str(row["created_at"]),
        }
        for row in rows
    ]


def delete_history(user_id: int | str, history_id: int | str) -> bool:
    initialize_database()
    if _firestore_enabled():
        document = (
            _firestore_client()
            .collection("users")
            .document(str(user_id))
            .collection("history")
            .document(str(history_id))
        )
        if not document.get().exists:
            return False
        document.delete()
        return True
    with _connection() as connection:
        cursor = _execute(
            connection,
            "DELETE FROM user_history WHERE id = ? AND user_id = ?",
            (int(history_id), int(user_id)),
        )
        return cursor.rowcount > 0


def delete_all_history(user_id: int | str) -> int:
    initialize_database()
    if _firestore_enabled():
        collection = (
            _firestore_client()
            .collection("users")
            .document(str(user_id))
            .collection("history")
        )
        deleted_count = 0
        while True:
            documents = list(collection.limit(500).stream())
            if not documents:
                break
            batch = _firestore_client().batch()
            for document in documents:
                batch.delete(document.reference)
            batch.commit()
            deleted_count += len(documents)
        return deleted_count
    with _connection() as connection:
        cursor = _execute(
            connection,
            "DELETE FROM user_history WHERE user_id = ?",
            (int(user_id),),
        )
        return int(cursor.rowcount)
