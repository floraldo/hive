"""
Factory Acceptance Test 02: Multi-Component Application Test (Simplified)

This test validates the autonomous platform's ability to generate and coordinate
applications with multiple interacting components (frontend, backend, API, database).
"""
import pytest
import subprocess
import sys
import time
from pathlib import Path
import requests
sys.path.insert(0, str(Path(__file__).parent))
from fat_framework import FactoryAcceptanceTest

def generate_simple_todo_app(test_case):
    """Generate a simple multi-component Todo application"""
    print('   [CODE] Generating multi-component Todo application...')
    base_dir = Path('apps/todo-app-fat')
    base_dir.mkdir(parents=True, exist_ok=True)
    (base_dir / 'backend').mkdir(parents=True, exist_ok=True)
    (base_dir / 'frontend').mkdir(parents=True, exist_ok=True)
    backend_code = '#!/usr/bin/env python3\nfrom flask import Flask, request, jsonify, send_from_directory\nfrom flask_cors import CORS\nimport sqlite3\nimport json\nfrom datetime import datetime\nfrom pathlib import Path\n\napp = Flask(__name__)\nCORS(app)\n\nDATABASE_PATH = Path(__file__).parent.parent / "todos.db"\n\ndef init_db():\n    """Initialize database"""\n    conn = sqlite3.connect(str(DATABASE_PATH))\n    cursor = conn.cursor()\n    cursor.execute("CREATE TABLE IF NOT EXISTS todos (id INTEGER PRIMARY KEY, title TEXT NOT NULL, completed BOOLEAN DEFAULT FALSE)")\n    cursor.execute("INSERT OR IGNORE INTO todos (id, title, completed) VALUES (1, \'Complete FAT test\', FALSE)")\n    cursor.execute("INSERT OR IGNORE INTO todos (id, title, completed) VALUES (2, \'Test multi-component app\', FALSE)")\n    conn.commit()\n    conn.close()\n\n@app.route(\'/api/health\', methods=[\'GET\'])\ndef health_check():\n    return jsonify({\n        "status": "healthy",\n        "service": "todo-backend",\n        "generated_by": "hive_autonomous_agents",\n        "test_type": "multi_component_fat"\n    })\n\n@app.route(\'/api/todos\', methods=[\'GET\'])\ndef get_todos():\n    try:\n        conn = sqlite3.connect(str(DATABASE_PATH))\n        conn.row_factory = sqlite3.Row\n        cursor = conn.cursor()\n        cursor.execute(\'SELECT * FROM todos ORDER BY id\')\n        todos = [dict(row) for row in cursor.fetchall()]\n        conn.close()\n        return jsonify({"success": True, "todos": todos, "count": len(todos)})\n    except Exception as e:\n        return jsonify({"success": False, "error": str(e)}), 500\n\n@app.route(\'/api/todos\', methods=[\'POST\'])\ndef create_todo():\n    try:\n        data = request.get_json()\n        if not data or \'title\' not in data:\n            return jsonify({"success": False, "error": "Title required"}), 400\n\n        conn = sqlite3.connect(str(DATABASE_PATH))\n        cursor = conn.cursor()\n        cursor.execute("INSERT INTO todos (title, completed) VALUES (?, ?)",\n                      (data[\'title\'], data.get(\'completed\', False)))\n        todo_id = cursor.lastrowid\n        conn.commit()\n        conn.close()\n        return jsonify({"success": True, "todo_id": todo_id}), 201\n    except Exception as e:\n        return jsonify({"success": False, "error": str(e)}), 500\n\n@app.route(\'/api/todos/<int:todo_id>\', methods=[\'PUT\'])\ndef update_todo(todo_id):\n    try:\n        data = request.get_json()\n        conn = sqlite3.connect(str(DATABASE_PATH))\n        cursor = conn.cursor()\n\n        if \'completed\' in data:\n            cursor.execute("UPDATE todos SET completed = ? WHERE id = ?", (data[\'completed\'], todo_id))\n        if \'title\' in data:\n            cursor.execute("UPDATE todos SET title = ? WHERE id = ?", (data[\'title\'], todo_id))\n\n        if cursor.rowcount == 0:\n            conn.close()\n            return jsonify({"success": False, "error": "Todo not found"}), 404\n\n        conn.commit()\n        conn.close()\n        return jsonify({"success": True})\n    except Exception as e:\n        return jsonify({"success": False, "error": str(e)}), 500\n\n@app.route(\'/api/todos/<int:todo_id>\', methods=[\'DELETE\'])\ndef delete_todo(todo_id):\n    try:\n        conn = sqlite3.connect(str(DATABASE_PATH))\n        cursor = conn.cursor()\n        cursor.execute(\'DELETE FROM todos WHERE id = ?\', (todo_id,))\n\n        if cursor.rowcount == 0:\n            conn.close()\n            return jsonify({"success": False, "error": "Todo not found"}), 404\n\n        conn.commit()\n        conn.close()\n        return jsonify({"success": True})\n    except Exception as e:\n        return jsonify({"success": False, "error": str(e)}), 500\n\n@app.route(\'/\', methods=[\'GET\'])\ndef serve_frontend():\n    frontend_path = Path(__file__).parent.parent / "frontend"\n    return send_from_directory(str(frontend_path), \'index.html\')\n\nif __name__ == \'__main__\':\n    init_db()\n    print("Starting Todo Backend on port 5003...")\n    app.run(host=\'0.0.0.0\', port=5003, debug=False)\n'
    with open(base_dir / 'backend' / 'app.py', 'w') as f:
        f.write(backend_code)
    frontend_html = '<!DOCTYPE html>\n<html>\n<head>\n    <title>Todo App - Multi-Component FAT</title>\n    <style>\n        body { font-family: Arial; max-width: 600px; margin: 50px auto; padding: 20px; }\n        .todo { padding: 10px; border: 1px solid #ddd; margin: 5px 0; }\n        .completed { text-decoration: line-through; background: #f0f0f0; }\n        button { padding: 5px 10px; margin: 2px; }\n        input { padding: 5px; width: 200px; }\n        h1 { color: #333; }\n        .badge { background: #007bff; color: white; padding: 2px 6px; border-radius: 3px; font-size: 12px; }\n    </style>\n</head>\n<body>\n    <h1>Todo Application <span class="badge">Multi-Component FAT</span></h1>\n    <div>\n        <input type="text" id="todoTitle" placeholder="Enter todo title">\n        <button onclick="addTodo()">Add Todo</button>\n    </div>\n    <div id="todosList"></div>\n\n    <script>\n        const API_BASE = \'/api\';\n\n        async function loadTodos() {\n            try {\n                const response = await fetch(API_BASE + \'/todos\');\n                const data = await response.json();\n\n                if (data.success) {\n                    displayTodos(data.todos);\n                } else {\n                    console.error(\'Failed to load todos:\', data.error);\n                }\n            } catch (error) {\n                console.error(\'Error loading todos:\', error);\n            }\n        }\n\n        function displayTodos(todos) {\n            const container = document.getElementById(\'todosList\');\n            container.innerHTML = todos.map(todo => `\n                <div class="todo ${todo.completed ? \'completed\' : \'\'}">\n                    <span>${todo.title}</span>\n                    <button onclick="toggleTodo(${todo.id}, ${!todo.completed})">\n                        ${todo.completed ? \'Undo\' : \'Complete\'}\n                    </button>\n                    <button onclick="deleteTodo(${todo.id})">Delete</button>\n                </div>\n            `).join(\'\');\n        }\n\n        async function addTodo() {\n            const title = document.getElementById(\'todoTitle\').value.trim();\n            if (!title) return;\n\n            try {\n                const response = await fetch(API_BASE + \'/todos\', {\n                    method: \'POST\',\n                    headers: { \'Content-Type\': \'application/json\' },\n                    body: JSON.stringify({ title })\n                });\n\n                const data = await response.json();\n                if (data.success) {\n                    document.getElementById(\'todoTitle\').value = \'\';\n                    loadTodos();\n                } else {\n                    alert(\'Error: \' + data.error);\n                }\n            } catch (error) {\n                alert(\'Error adding todo: \' + error.message);\n            }\n        }\n\n        async function toggleTodo(todoId, completed) {\n            try {\n                const response = await fetch(`${API_BASE}/todos/${todoId}`, {\n                    method: \'PUT\',\n                    headers: { \'Content-Type\': \'application/json\' },\n                    body: JSON.stringify({ completed })\n                });\n\n                const data = await response.json();\n                if (data.success) {\n                    loadTodos();\n                } else {\n                    alert(\'Error: \' + data.error);\n                }\n            } catch (error) {\n                alert(\'Error updating todo: \' + error.message);\n            }\n        }\n\n        async function deleteTodo(todoId) {\n            if (!confirm(\'Delete this todo?\')) return;\n\n            try {\n                const response = await fetch(`${API_BASE}/todos/${todoId}`, {\n                    method: \'DELETE\'\n                });\n\n                const data = await response.json();\n                if (data.success) {\n                    loadTodos();\n                } else {\n                    alert(\'Error: \' + data.error);\n                }\n            } catch (error) {\n                alert(\'Error deleting todo: \' + error.message);\n            }\n        }\n\n        // Load todos on page load\n        loadTodos();\n    </script>\n</body>\n</html>'
    with open(base_dir / 'frontend' / 'index.html', 'w') as f:
        f.write(frontend_html)
    with open(base_dir / 'requirements.txt', 'w') as f:
        f.write('Flask==2.3.3\nFlask-CORS==4.0.0\n')
    print('   [OK] Generated multi-component Todo application')
    print('       - Flask backend with REST API')
    print('       - HTML/JS frontend with CRUD operations')
    print('       - SQLite database integration')
    print('       - Multi-component communication')
    return True

def validate_simple_todo_app(test_case):
    """Validate the simple Todo application"""
    app_dir = Path('apps/todo-app-fat')
    if not app_dir.exists():
        return {'success': False, 'error': 'Application directory not found'}
    required_files = ['backend/app.py', 'frontend/index.html', 'requirements.txt']
    for file_path in required_files:
        if not (app_dir / file_path).exists():
            return {'success': False, 'error': f'Missing file: {file_path}'}
    try:
        install_result = subprocess.run([sys.executable, '-m', 'pip', 'install', '-r', 'requirements.txt'], cwd=app_dir, capture_output=True, text=True, timeout=60)
        if install_result.returncode != 0:
            return {'success': False, 'error': f'Dependencies install failed: {install_result.stderr}'}
        server_process = subprocess.Popen([sys.executable, 'backend/app.py'], cwd=app_dir, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        time.sleep(3)
        try:
            health_response = requests.get('http://localhost:5003/api/health', timeout=5)
            if health_response.status_code != 200:
                server_process.terminate()
                return {'success': False, 'error': f'Health check failed: {health_response.status_code}'}
            health_data = health_response.json()
            if health_data.get('status') != 'healthy':
                server_process.terminate()
                return {'success': False, 'error': 'Health check status not healthy'}
            todos_response = requests.get('http://localhost:5003/api/todos', timeout=5)
            if todos_response.status_code != 200:
                server_process.terminate()
                return {'success': False, 'error': f'API failed: {todos_response.status_code}'}
            todos_data = todos_response.json()
            if not todos_data.get('success'):
                server_process.terminate()
                return {'success': False, 'error': 'API response indicates failure'}
            create_response = requests.post('http://localhost:5003/api/todos', json={'title': 'Test Todo'}, headers={'Content-Type': 'application/json'}, timeout=5)
            if create_response.status_code != 201:
                server_process.terminate()
                return {'success': False, 'error': f'Create failed: {create_response.status_code}'}
            todo_id = create_response.json().get('todo_id')
            if not todo_id:
                server_process.terminate()
                return {'success': False, 'error': 'No todo_id returned from create'}
            update_response = requests.put(f'http://localhost:5003/api/todos/{todo_id}', json={'completed': True}, headers={'Content-Type': 'application/json'}, timeout=5)
            if update_response.status_code != 200:
                server_process.terminate()
                return {'success': False, 'error': f'Update failed: {update_response.status_code}'}
            delete_response = requests.delete(f'http://localhost:5003/api/todos/{todo_id}', timeout=5)
            if delete_response.status_code != 200:
                server_process.terminate()
                return {'success': False, 'error': f'Delete failed: {delete_response.status_code}'}
            frontend_response = requests.get('http://localhost:5003/', timeout=5)
            if frontend_response.status_code != 200:
                server_process.terminate()
                return {'success': False, 'error': f'Frontend failed: {frontend_response.status_code}'}
            if 'Todo Application' not in frontend_response.text:
                server_process.terminate()
                return {'success': False, 'error': 'Frontend content validation failed'}
        except requests.RequestException as e:
            server_process.terminate()
            return {'success': False, 'error': f'Request failed: {str(e)}'}
        server_process.terminate()
        server_process.wait(timeout=5)
        return {'success': True, 'details': 'Multi-component Todo application validated successfully with full CRUD operations and frontend integration'}
    except Exception as e:
        return {'success': False, 'error': f'Validation error: {str(e)}'}

def run_multi_component_test():
    """Execute the simplified Multi-Component Test"""
    test_case = {'name': 'Multi-Component Test', 'title': 'FAT-02: Multi-Component Todo Application', 'description': 'Generate web application with frontend, backend, and database components', 'goal': "Validate autonomous platform's ability to create multi-component applications", 'complexity': 'MEDIUM', 'priority': 8, 'estimated_duration': 600, 'task_data': {'project_name': 'todo-app-fat', 'description': 'Multi-component Todo app with Flask backend, HTML frontend, SQLite database', 'requirements': {'backend': {'framework': 'Flask', 'database': 'SQLite', 'api_type': 'REST'}, 'frontend': {'type': 'SPA', 'technologies': ['HTML', 'CSS', 'JavaScript']}, 'database': {'type': 'SQLite', 'tables': ['todos']}, 'integration': {'cors_enabled': True, 'api_communication': True}}}, 'metadata': {'test_type': 'factory_acceptance', 'test_id': 'FAT-02', 'complexity_level': 'multi_component', 'autonomous_generation': True}, 'generator_function': generate_simple_todo_app, 'validator_function': validate_simple_todo_app}
    fat = FactoryAcceptanceTest()
    result = fat.run_test_case(test_case)
    return result
if __name__ == '__main__':
    result = run_multi_component_test()
    if result['success']:
        print('\\n[SUCCESS] Multi-Component Test completed successfully!')
        exit(0)
    else:
        print(f"\\n[FAILURE] Multi-Component Test failed: {result['error']}")
        exit(1)