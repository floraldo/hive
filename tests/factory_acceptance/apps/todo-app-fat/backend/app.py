#!/usr/bin/env python3
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import sqlite3
import json
from datetime import datetime
from pathlib import Path

app = Flask(__name__)
CORS(app)

DATABASE_PATH = Path(__file__).parent.parent / "todos.db"


def init_db():
    """Initialize database"""
    conn = sqlite3.connect(str(DATABASE_PATH))
    cursor = conn.cursor()
    cursor.execute(
        "CREATE TABLE IF NOT EXISTS todos (id INTEGER PRIMARY KEY, title TEXT NOT NULL, completed BOOLEAN DEFAULT FALSE)"
    )
    cursor.execute("INSERT OR IGNORE INTO todos (id, title, completed) VALUES (1, 'Complete FAT test', FALSE)")
    cursor.execute("INSERT OR IGNORE INTO todos (id, title, completed) VALUES (2, 'Test multi-component app', FALSE)")
    conn.commit()
    conn.close()


@app.route("/api/health", methods=["GET"])
def health_check():
    return jsonify(
        {
            "status": "healthy",
            "service": "todo-backend",
            "generated_by": "hive_autonomous_agents",
            "test_type": "multi_component_fat",
        }
    )


@app.route("/api/todos", methods=["GET"])
def get_todos():
    try:
        conn = sqlite3.connect(str(DATABASE_PATH))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM todos ORDER BY id")
        todos = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return jsonify({"success": True, "todos": todos, "count": len(todos)})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/todos", methods=["POST"])
def create_todo():
    try:
        data = request.get_json()
        if not data or "title" not in data:
            return jsonify({"success": False, "error": "Title required"}), 400

        conn = sqlite3.connect(str(DATABASE_PATH))
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO todos (title, completed) VALUES (?, ?)", (data["title"], data.get("completed", False))
        )
        todo_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return jsonify({"success": True, "todo_id": todo_id}), 201
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/todos/<int:todo_id>", methods=["PUT"])
def update_todo(todo_id):
    try:
        data = request.get_json()
        conn = sqlite3.connect(str(DATABASE_PATH))
        cursor = conn.cursor()

        if "completed" in data:
            cursor.execute("UPDATE todos SET completed = ? WHERE id = ?", (data["completed"], todo_id))
        if "title" in data:
            cursor.execute("UPDATE todos SET title = ? WHERE id = ?", (data["title"], todo_id))

        if cursor.rowcount == 0:
            conn.close()
            return jsonify({"success": False, "error": "Todo not found"}), 404

        conn.commit()
        conn.close()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/todos/<int:todo_id>", methods=["DELETE"])
def delete_todo(todo_id):
    try:
        conn = sqlite3.connect(str(DATABASE_PATH))
        cursor = conn.cursor()
        cursor.execute("DELETE FROM todos WHERE id = ?", (todo_id,))

        if cursor.rowcount == 0:
            conn.close()
            return jsonify({"success": False, "error": "Todo not found"}), 404

        conn.commit()
        conn.close()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/", methods=["GET"])
def serve_frontend():
    frontend_path = Path(__file__).parent.parent / "frontend"
    return send_from_directory(str(frontend_path), "index.html")


if __name__ == "__main__":
    init_db()
    print("Starting Todo Backend on port 5003...")
    app.run(host="0.0.0.0", port=5003, debug=False)
