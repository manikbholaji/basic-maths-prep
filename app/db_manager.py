import os
import sqlite3
import json
import hashlib
from datetime import datetime

# Local SQLite configuration
DB_FILE = os.path.join("data", "local_quiz.db")

# Global MongoDB connection cache
_mongo_client = None
_use_sqlite = False

def get_mongo_db():
    """Returns a MongoDB database instance if MONGODB_URI is available, else None."""
    global _mongo_client, _use_sqlite
    if _use_sqlite:
        return None
    uri = os.environ.get("MONGODB_URI")
    if not uri:
        try:
            import streamlit as st
            if "MONGODB_URI" in st.secrets:
                uri = st.secrets["MONGODB_URI"]
        except Exception:
            pass
    
    if uri:
        try:
            import pymongo
            if _mongo_client is None:
                _mongo_client = pymongo.MongoClient(uri, serverSelectionTimeoutMS=3000)
            # Parse DB name from URI or fallback
            db_name = "basic_maths_prep"
            try:
                from pymongo.uri_parser import parse_uri
                db_name = parse_uri(uri).get("database") or "basic_maths_prep"
            except Exception:
                pass
            return _mongo_client[db_name]
        except Exception as e:
            print(f"MongoDB connection error: {e}")
            return None
    return None

def is_online_mode():
    """Helper to detect if we should run in online MongoDB mode."""
    return get_mongo_db() is not None

def init_db():
    """Initializes the active database (SQLite locally or MongoDB online)."""
    global _use_sqlite
    db = get_mongo_db()
    if db is not None:
        # MongoDB: ensure indexes exist
        try:
            db.command("ping")
            db.users.create_index("username", unique=True)
            db.quizzes.create_index("username")
            print("MongoDB tables/indexes verified.")
            return True
        except Exception as e:
            print(f"Failed to initialize MongoDB indexes: {e}. Falling back to local SQLite.")
            _use_sqlite = True

    # SQLite: create tables
    os.makedirs("data", exist_ok=True)
    conn = None
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        # Create users table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                username TEXT PRIMARY KEY,
                password_hash TEXT NOT NULL,
                name TEXT NOT NULL
            )
        """)
        
        # Create quizzes table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS quizzes (
                quiz_id TEXT PRIMARY KEY,
                username TEXT NOT NULL,
                quiz_type TEXT NOT NULL,
                input_details TEXT NOT NULL,
                questions TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (username) REFERENCES users(username)
            )
        """)
        
        conn.commit()
        print("Local SQLite database verified.")
        
        # Migrate users from users.json if database is empty
        cursor.execute("SELECT COUNT(*) FROM users")
        if cursor.fetchone()[0] == 0:
            json_users_path = os.path.join("data", "users.json")
            if os.path.exists(json_users_path):
                try:
                    with open(json_users_path, "r") as f:
                        users_data = json.load(f)
                    for email, u_data in users_data.items():
                        cursor.execute(
                            "INSERT INTO users (username, password_hash, name) VALUES (?, ?, ?)",
                            (email, u_data.get("password_hash"), u_data.get("name", "Student"))
                        )
                    conn.commit()
                    print("Migrated existing users from users.json to local SQLite DB.")
                except Exception as ex:
                    print(f"Could not migrate users.json: {ex}")
        return True
    except Exception as e:
        print(f"Failed to initialize SQLite: {e}")
        return False
    finally:
        if conn:
            conn.close()

def hash_password(password: str) -> str:
    """Generates standard SHA-256 hash for secure credential storage."""
    return hashlib.sha256(password.encode("utf-8")).hexdigest()

def register_user(username, password, name):
    """Registers a new user. Returns True on success, False if user already exists."""
    username = username.strip().lower()
    name = name.strip()
    password_hash = hash_password(password)
    
    db = get_mongo_db()
    if db is not None:
        try:
            if db.users.find_one({"username": username}) is not None:
                return False
            db.users.insert_one({
                "username": username,
                "password_hash": password_hash,
                "name": name
            })
            return True
        except Exception as e:
            print(f"MongoDB register error: {e}")
            return False
    else:
        conn = None
        try:
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM users WHERE username = ?", (username,))
            if cursor.fetchone() is not None:
                return False
            cursor.execute(
                "INSERT INTO users (username, password_hash, name) VALUES (?, ?, ?)",
                (username, password_hash, name)
            )
            conn.commit()
            return True
        except Exception as e:
            print(f"SQLite register error: {e}")
            return False
        finally:
            if conn:
                conn.close()

def authenticate_user(username, password):
    """Authenticates user. Returns user details dict on success, None on failure."""
    username = username.strip().lower()
    password_hash = hash_password(password)
    
    db = get_mongo_db()
    if db is not None:
        try:
            user = db.users.find_one({"username": username, "password_hash": password_hash})
            if user:
                return {"username": user["username"], "name": user["name"]}
        except Exception as e:
            print(f"MongoDB auth error: {e}")
    else:
        conn = None
        try:
            conn = sqlite3.connect(DB_FILE)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                "SELECT username, name FROM users WHERE username = ? AND password_hash = ?",
                (username, password_hash)
            )
            row = cursor.fetchone()
            if row:
                return {"username": row["username"], "name": row["name"]}
        except sqlite3.Error as e:
            print(f"SQLite auth error: {e}")
        finally:
            if conn:
                conn.close()
    return None

def save_quiz(username, quiz_type, input_details, questions):
    """Saves a generated quiz. Returns the quiz ID."""
    import uuid
    quiz_id = str(uuid.uuid4())
    created_at = datetime.now().isoformat()
    
    # Store questions and input_details as structured object
    db = get_mongo_db()
    if db is not None:
        try:
            db.quizzes.insert_one({
                "quiz_id": quiz_id,
                "username": username,
                "quiz_type": quiz_type,
                "input_details": input_details,
                "questions": questions,
                "created_at": created_at
            })
            return quiz_id
        except Exception as e:
            print(f"MongoDB save_quiz error: {e}")
    else:
        conn = None
        try:
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO quizzes (quiz_id, username, quiz_type, input_details, questions, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (quiz_id, username, quiz_type, json.dumps(input_details), json.dumps(questions), created_at)
            )
            conn.commit()
            return quiz_id
        except sqlite3.Error as e:
            print(f"SQLite save_quiz error: {e}")
        finally:
            if conn:
                conn.close()
    return quiz_id

def get_user_quizzes(username):
    """Retrieves all quizzes for a user, sorted newest first."""
    db = get_mongo_db()
    quizzes = []
    if db is not None:
        try:
            cursor = db.quizzes.find({"username": username}).sort("created_at", -1)
            for doc in cursor:
                quizzes.append({
                    "quiz_id": doc["quiz_id"],
                    "username": doc["username"],
                    "quiz_type": doc["quiz_type"],
                    "input_details": doc["input_details"],
                    "questions": doc["questions"],
                    "created_at": doc["created_at"]
                })
        except Exception as e:
            print(f"MongoDB get_user_quizzes error: {e}")
    else:
        conn = None
        try:
            conn = sqlite3.connect(DB_FILE)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                "SELECT quiz_id, username, quiz_type, input_details, questions, created_at FROM quizzes WHERE username = ? ORDER BY created_at DESC",
                (username,)
            )
            for row in cursor.fetchall():
                quizzes.append({
                    "quiz_id": row["quiz_id"],
                    "username": row["username"],
                    "quiz_type": row["quiz_type"],
                    "input_details": json.loads(row["input_details"]),
                    "questions": json.loads(row["questions"]),
                    "created_at": row["created_at"]
                })
        except sqlite3.Error as e:
            print(f"SQLite get_user_quizzes error: {e}")
        finally:
            if conn:
                conn.close()
    return quizzes

def get_quiz(quiz_id):
    """Retrieves a specific quiz by ID."""
    db = get_mongo_db()
    if db is not None:
        try:
            doc = db.quizzes.find_one({"quiz_id": quiz_id})
            if doc:
                return {
                    "quiz_id": doc["quiz_id"],
                    "username": doc["username"],
                    "quiz_type": doc["quiz_type"],
                    "input_details": doc["input_details"],
                    "questions": doc["questions"],
                    "created_at": doc["created_at"]
                }
        except Exception as e:
            print(f"MongoDB get_quiz error: {e}")
    else:
        conn = None
        try:
            conn = sqlite3.connect(DB_FILE)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                "SELECT quiz_id, username, quiz_type, input_details, questions, created_at FROM quizzes WHERE quiz_id = ?",
                (quiz_id,)
            )
            row = cursor.fetchone()
            if row:
                return {
                    "quiz_id": row["quiz_id"],
                    "username": row["username"],
                    "quiz_type": row["quiz_type"],
                    "input_details": json.loads(row["input_details"]),
                    "questions": json.loads(row["questions"]),
                    "created_at": row["created_at"]
                }
        except sqlite3.Error as e:
            print(f"SQLite get_quiz error: {e}")
        finally:
            if conn:
                conn.close()
    return None
