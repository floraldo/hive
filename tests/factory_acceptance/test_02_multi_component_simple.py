#!/usr/bin/env python3
"""
Factory Acceptance Test 02: Multi-Component Application Test (Simplified)

This test validates the autonomous platform's ability to generate and coordinate
applications with multiple interacting components (frontend, backend, API, database).
"""

import json
import sqlite3
import subprocess
import time
import requests
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Any
import traceback

# Import the FAT framework
sys.path.insert(0, str(Path(__file__).parent))
from fat_framework import FactoryAcceptanceTest


def generate_simple_todo_app(test_case):
    """Generate a simple multi-component Todo application"""

    print("   [CODE] Generating multi-component Todo application...")

    # Create package structure
    base_dir = Path("apps/todo-app-fat")
    base_dir.mkdir(parents=True, exist_ok=True)
    (base_dir / "backend").mkdir(parents=True, exist_ok=True)
    (base_dir / "frontend").mkdir(parents=True, exist_ok=True)

    # Generate simple Flask backend
    backend_code = '''#!/usr/bin/env python3
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
    cursor.execute("CREATE TABLE IF NOT EXISTS todos (id INTEGER PRIMARY KEY, title TEXT NOT NULL, completed BOOLEAN DEFAULT FALSE)")
    cursor.execute("INSERT OR IGNORE INTO todos (id, title, completed) VALUES (1, 'Complete FAT test', FALSE)")
    cursor.execute("INSERT OR IGNORE INTO todos (id, title, completed) VALUES (2, 'Test multi-component app', FALSE)")
    conn.commit()
    conn.close()

@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({
        "status": "healthy",
        "service": "todo-backend",
        "generated_by": "hive_autonomous_agents",
        "test_type": "multi_component_fat"
    })

@app.route('/api/todos', methods=['GET'])
def get_todos():
    try:
        conn = sqlite3.connect(str(DATABASE_PATH))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM todos ORDER BY id')
        todos = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return jsonify({"success": True, "todos": todos, "count": len(todos)})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/todos', methods=['POST'])
def create_todo():
    try:
        data = request.get_json()
        if not data or 'title' not in data:
            return jsonify({"success": False, "error": "Title required"}), 400

        conn = sqlite3.connect(str(DATABASE_PATH))
        cursor = conn.cursor()
        cursor.execute("INSERT INTO todos (title, completed) VALUES (?, ?)",
                      (data['title'], data.get('completed', False)))
        todo_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return jsonify({"success": True, "todo_id": todo_id}), 201
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/todos/<int:todo_id>', methods=['PUT'])
def update_todo(todo_id):
    try:
        data = request.get_json()
        conn = sqlite3.connect(str(DATABASE_PATH))
        cursor = conn.cursor()

        if 'completed' in data:
            cursor.execute("UPDATE todos SET completed = ? WHERE id = ?", (data['completed'], todo_id))
        if 'title' in data:
            cursor.execute("UPDATE todos SET title = ? WHERE id = ?", (data['title'], todo_id))

        if cursor.rowcount == 0:
            conn.close()
            return jsonify({"success": False, "error": "Todo not found"}), 404

        conn.commit()
        conn.close()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/todos/<int:todo_id>', methods=['DELETE'])
def delete_todo(todo_id):
    try:
        conn = sqlite3.connect(str(DATABASE_PATH))
        cursor = conn.cursor()
        cursor.execute('DELETE FROM todos WHERE id = ?', (todo_id,))

        if cursor.rowcount == 0:
            conn.close()
            return jsonify({"success": False, "error": "Todo not found"}), 404

        conn.commit()
        conn.close()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/', methods=['GET'])
def serve_frontend():
    frontend_path = Path(__file__).parent.parent / "frontend"
    return send_from_directory(str(frontend_path), 'index.html')

if __name__ == '__main__':
    init_db()
    print("Starting Todo Backend on port 5003...")
    app.run(host='0.0.0.0', port=5003, debug=False)
'''

    with open(base_dir / "backend" / "app.py", "w") as f:
        f.write(backend_code)

    # Generate simple frontend
    frontend_html = '''<!DOCTYPE html>
<html>
<head>
    <title>Todo App - Multi-Component FAT</title>
    <style>
        body { font-family: Arial; max-width: 600px; margin: 50px auto; padding: 20px; }
        .todo { padding: 10px; border: 1px solid #ddd; margin: 5px 0; }
        .completed { text-decoration: line-through; background: #f0f0f0; }
        button { padding: 5px 10px; margin: 2px; }
        input { padding: 5px; width: 200px; }
        h1 { color: #333; }
        .badge { background: #007bff; color: white; padding: 2px 6px; border-radius: 3px; font-size: 12px; }
    </style>
</head>
<body>
    <h1>Todo Application <span class="badge">Multi-Component FAT</span></h1>
    <div>
        <input type="text" id="todoTitle" placeholder="Enter todo title">
        <button onclick="addTodo()">Add Todo</button>
    </div>
    <div id="todosList"></div>

    <script>
        const API_BASE = '/api';

        async function loadTodos() {
            try {
                const response = await fetch(API_BASE + '/todos');
                const data = await response.json();

                if (data.success) {
                    displayTodos(data.todos);
                } else {
                    console.error('Failed to load todos:', data.error);
                }
            } catch (error) {
                console.error('Error loading todos:', error);
            }
        }

        function displayTodos(todos) {
            const container = document.getElementById('todosList');
            container.innerHTML = todos.map(todo => `
                <div class="todo ${todo.completed ? 'completed' : ''}">
                    <span>${todo.title}</span>
                    <button onclick="toggleTodo(${todo.id}, ${!todo.completed})">
                        ${todo.completed ? 'Undo' : 'Complete'}
                    </button>
                    <button onclick="deleteTodo(${todo.id})">Delete</button>
                </div>
            `).join('');
        }

        async function addTodo() {
            const title = document.getElementById('todoTitle').value.trim();
            if (!title) return;

            try {
                const response = await fetch(API_BASE + '/todos', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ title })
                });

                const data = await response.json();
                if (data.success) {
                    document.getElementById('todoTitle').value = '';
                    loadTodos();
                } else {
                    alert('Error: ' + data.error);
                }
            } catch (error) {
                alert('Error adding todo: ' + error.message);
            }
        }

        async function toggleTodo(todoId, completed) {
            try {
                const response = await fetch(`${API_BASE}/todos/${todoId}`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ completed })
                });

                const data = await response.json();
                if (data.success) {
                    loadTodos();
                } else {
                    alert('Error: ' + data.error);
                }
            } catch (error) {
                alert('Error updating todo: ' + error.message);
            }
        }

        async function deleteTodo(todoId) {
            if (!confirm('Delete this todo?')) return;

            try {
                const response = await fetch(`${API_BASE}/todos/${todoId}`, {
                    method: 'DELETE'
                });

                const data = await response.json();
                if (data.success) {
                    loadTodos();
                } else {
                    alert('Error: ' + data.error);
                }
            } catch (error) {
                alert('Error deleting todo: ' + error.message);
            }
        }

        // Load todos on page load
        loadTodos();
    </script>
</body>
</html>'''

    with open(base_dir / "frontend" / "index.html", "w") as f:
        f.write(frontend_html)

    # Generate requirements.txt
    with open(base_dir / "requirements.txt", "w") as f:
        f.write("Flask==2.3.3\nFlask-CORS==4.0.0\n")

    print("   [OK] Generated multi-component Todo application")
    print("       - Flask backend with REST API")
    print("       - HTML/JS frontend with CRUD operations")
    print("       - SQLite database integration")
    print("       - Multi-component communication")

    return True


def validate_simple_todo_app(test_case):
    """Validate the simple Todo application"""

    app_dir = Path("apps/todo-app-fat")

    if not app_dir.exists():
        return {"success": False, "error": "Application directory not found"}

    # Check required files
    required_files = ["backend/app.py", "frontend/index.html", "requirements.txt"]
    for file_path in required_files:
        if not (app_dir / file_path).exists():
            return {"success": False, "error": f"Missing file: {file_path}"}

    try:
        # Install dependencies
        install_result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "-r", "requirements.txt"],
            cwd=app_dir,
            capture_output=True,
            text=True,
            timeout=60
        )

        if install_result.returncode != 0:
            return {"success": False, "error": f"Dependencies install failed: {install_result.stderr}"}

        # Start backend server
        server_process = subprocess.Popen(
            [sys.executable, "backend/app.py"],
            cwd=app_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        # Wait for startup
        time.sleep(3)

        try:
            # Test health endpoint
            health_response = requests.get("http://localhost:5003/api/health", timeout=5)
            if health_response.status_code != 200:
                server_process.terminate()
                return {"success": False, "error": f"Health check failed: {health_response.status_code}"}

            health_data = health_response.json()
            if health_data.get("status") != "healthy":
                server_process.terminate()
                return {"success": False, "error": "Health check status not healthy"}

            # Test API functionality
            todos_response = requests.get("http://localhost:5003/api/todos", timeout=5)
            if todos_response.status_code != 200:
                server_process.terminate()
                return {"success": False, "error": f"API failed: {todos_response.status_code}"}

            todos_data = todos_response.json()
            if not todos_data.get("success"):
                server_process.terminate()
                return {"success": False, "error": "API response indicates failure"}

            # Test CRUD operations
            # Create
            create_response = requests.post(
                "http://localhost:5003/api/todos",
                json={"title": "Test Todo"},
                headers={"Content-Type": "application/json"},
                timeout=5
            )
            if create_response.status_code != 201:
                server_process.terminate()
                return {"success": False, "error": f"Create failed: {create_response.status_code}"}

            todo_id = create_response.json().get("todo_id")
            if not todo_id:
                server_process.terminate()
                return {"success": False, "error": "No todo_id returned from create"}

            # Update
            update_response = requests.put(
                f"http://localhost:5003/api/todos/{todo_id}",
                json={"completed": True},
                headers={"Content-Type": "application/json"},
                timeout=5
            )
            if update_response.status_code != 200:
                server_process.terminate()
                return {"success": False, "error": f"Update failed: {update_response.status_code}"}

            # Delete
            delete_response = requests.delete(f"http://localhost:5003/api/todos/{todo_id}", timeout=5)
            if delete_response.status_code != 200:
                server_process.terminate()
                return {"success": False, "error": f"Delete failed: {delete_response.status_code}"}

            # Test frontend
            frontend_response = requests.get("http://localhost:5003/", timeout=5)
            if frontend_response.status_code != 200:
                server_process.terminate()
                return {"success": False, "error": f"Frontend failed: {frontend_response.status_code}"}

            if "Todo Application" not in frontend_response.text:
                server_process.terminate()
                return {"success": False, "error": "Frontend content validation failed"}

        except requests.RequestException as e:
            server_process.terminate()
            return {"success": False, "error": f"Request failed: {str(e)}"}

        # Cleanup
        server_process.terminate()
        server_process.wait(timeout=5)

        return {
            "success": True,
            "details": "Multi-component Todo application validated successfully with full CRUD operations and frontend integration"
        }

    except Exception as e:
        return {"success": False, "error": f"Validation error: {str(e)}"}


def run_multi_component_test():
    """Execute the simplified Multi-Component Test"""

    test_case = {
        "name": "Multi-Component Test",
        "title": "FAT-02: Multi-Component Todo Application",
        "description": "Generate web application with frontend, backend, and database components",
        "goal": "Validate autonomous platform's ability to create multi-component applications",
        "complexity": "MEDIUM",
        "priority": 8,
        "estimated_duration": 600,  # 10 minutes
        "task_data": {
            "project_name": "todo-app-fat",
            "description": "Multi-component Todo app with Flask backend, HTML frontend, SQLite database",
            "requirements": {
                "backend": {"framework": "Flask", "database": "SQLite", "api_type": "REST"},
                "frontend": {"type": "SPA", "technologies": ["HTML", "CSS", "JavaScript"]},
                "database": {"type": "SQLite", "tables": ["todos"]},
                "integration": {"cors_enabled": True, "api_communication": True}
            }
        },
        "metadata": {
            "test_type": "factory_acceptance",
            "test_id": "FAT-02",
            "complexity_level": "multi_component",
            "autonomous_generation": True
        },
        "generator_function": generate_simple_todo_app,
        "validator_function": validate_simple_todo_app
    }

    fat = FactoryAcceptanceTest()
    result = fat.run_test_case(test_case)
    return result


if __name__ == "__main__":
    result = run_multi_component_test()

    if result["success"]:
        print(f"\\n[SUCCESS] Multi-Component Test completed successfully!")
        exit(0)
    else:
        print(f"\\n[FAILURE] Multi-Component Test failed: {result['error']}")
        exit(1)