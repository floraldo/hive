# Test Messages for Fleet Command Automation

## Small Test Message
🧪 Simple test message - Hello from Fleet Command!

## Medium Test Message  
🧪 Medium complexity test message with multiple lines:
- Task ID: T001
- Priority: High
- Description: This is a multi-line task description that tests our chunking logic
- Requirements: Should handle special characters like @#$%^&*()
- Unicode test: 🚀🎯💡⚡🔧

## Large Test Message
🧪 Large test message for chunking and retry logic:

**Mission Brief: Authentication System Implementation**

Task ID: T101
Assigned to: Backend Worker
Priority: Critical
Deadline: ASAP

**Requirements:**
1. Implement JWT-based authentication system
2. Create secure login/logout endpoints
3. Add password hashing with bcrypt
4. Implement session management
5. Add middleware for route protection
6. Create user registration with email validation
7. Add forgot password functionality
8. Implement rate limiting for auth endpoints

**Technical Specifications:**
- Use Python Flask framework
- SQLAlchemy ORM for database operations  
- Redis for session storage
- Email service integration (SendGrid or similar)
- Input validation with Marshmallow schemas
- Unit tests with pytest (minimum 80% coverage)
- API documentation with Swagger/OpenAPI
- Docker containerization ready

**Deliverables:**
- Complete authentication API with all endpoints
- Database migration scripts
- Unit and integration tests
- API documentation
- Docker configuration
- Deployment instructions

**Additional Notes:**
This is a critical component for our security infrastructure. Please ensure all best practices are followed:
- OWASP security guidelines
- Proper error handling without information leakage  
- Comprehensive logging for security events
- Input sanitization and validation
- Proper CORS configuration

Report STATUS: success when implementation is complete and all tests pass.

**Code Example Reference:**
```python
# Example authentication decorator
def require_auth(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = request.headers.get('Authorization')
        if not token:
            return jsonify({'error': 'No token provided'}), 401
        try:
            jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
        except jwt.ExpiredSignatureError:
            return jsonify({'error': 'Token expired'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'error': 'Invalid token'}), 401
        return f(*args, **kwargs)
    return decorated_function
```

This message is intentionally large to test our chunking and retry mechanisms. It contains various formatting, code blocks, special characters, and emoji to ensure robust handling of complex message content.