import os
import logging
from flask import Flask, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from flask_migrate import Migrate
from flask_sslify import SSLify
from flask_socketio import SocketIO

# Set up logging
logging.basicConfig(level=logging.DEBUG)

# Create the Flask app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "dev_secret_key")

# Configure the SQLite database
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", "sqlite:///medconsult.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# Initialize SQLAlchemy
db = SQLAlchemy(app)

# Initialize Flask-Migrate
migrate = Migrate(app, db)

# Set up login manager
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message_category = 'info'

# Enable CSRF protection
csrf = CSRFProtect(app)

# Ensure CSRF protection is applied
csrf.init_app(app)

# Enable SSL for HTTPS
sslify = SSLify(app)

# Initialize SocketIO
socketio = SocketIO(app)

# Debugging CSRF issues
@app.before_request
def debug_csrf():
    if request.method == 'POST':
        print('CSRF Token in Form:', request.form.get('csrf_token'))
        print('CSRF Token in Session:', session.get('_csrf_token'))

# Removed the incorrect CSRF token handling logic
@app.before_request
def set_csrf_token():
    pass  # CSRF tokens are automatically managed by Flask-WTF

@app.context_processor
def inject_csrf_token():
    return dict(csrf_token=session.get('_csrf_token'))

# Import routes after initializing app to avoid circular imports
with app.app_context():
    from routes import *
    from models import *
    
    # Create all database tables
    # Removed db.create_all() to avoid conflicts with Flask-Migrate
    # db.create_all()
    
    # Initialize data (like admin user and specialty fee ranges)
    if 'initialize_data' in locals():
        initialize_data()

if __name__ == '__main__':
    socketio.run(app, debug=True)

# Removed incorrect import of 'yourapp'
# from yourapp import db

# Use the correct import for the current project
from app import db

if __name__ == "__main__":
    db.create_all()
    print("Database tables created successfully.")
