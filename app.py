from flask import Flask, request, jsonify, render_template, Response, redirect, url_for, flash
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import os
import uuid
import logging
import json
import stripe
import shutil
from dotenv import load_dotenv
from datetime import datetime, timezone
from typing import Dict, Any, List
from functools import wraps
import time
from utils.database import BookDatabase
from utils.task_manager import task_manager, TaskStatus
from models.book_model import BookProject
from utils.agent_factory import get_agent, ALL_TOOLS

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
CORS(app)
app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY', 'dev-secret-key-12345')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Initialize Login Manager
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Stripe Configuration
STRIPE_ENABLED = os.getenv('STRIPE_ENABLED', 'true').lower() == 'true'
STRIPE_SECRET_KEY = os.getenv('STRIPE_SECRET_KEY')
STRIPE_PUBLIC_KEY = os.getenv('STRIPE_PUBLIC_KEY')
STRIPE_PRICE_ID = os.getenv('STRIPE_PRICE_ID')
DOMAIN = os.getenv('DOMAIN', 'http://localhost:6748')

# Only initialize Stripe if enabled and keys are present
if STRIPE_ENABLED and STRIPE_SECRET_KEY:
    stripe.api_key = STRIPE_SECRET_KEY
elif STRIPE_ENABLED:
    logger.warning("Stripe is enabled but STRRIPE_SECRET_KEY is not set. Stripe features will be limited.")
    STRIPE_ENABLED = False

# When Stripe is disabled, users get unlimited usage
UNLIMITED_USAGE = not STRIPE_ENABLED

# =============================================================================
# RATE LIMITING
# =============================================================================

# Simple in-memory rate limiter (use Redis for production)
rate_limit_store = {}

def rate_limit(max_requests: int = 60, window: int = 60, key_prefix: str = 'api'):
    """
    Rate limiting decorator.

    Args:
        max_requests: Maximum number of requests allowed in the window
        window: Time window in seconds
        key_prefix: Prefix for the rate limit key
    """
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            # Get user identifier (IP for anonymous, user_id for authenticated)
            if current_user.is_authenticated:
                user_id = str(current_user.id)
            else:
                user_id = request.remote_addr or 'anonymous'

            # Create rate limit key
            key = f"{key_prefix}:{user_id}:{f.__name__}"

            current_time = time.time()

            # Get or initialize request history
            if key not in rate_limit_store:
                rate_limit_store[key] = []

            # Clean old requests
            rate_limit_store[key] = [
                timestamp for timestamp in rate_limit_store[key]
                if current_time - timestamp < window
            ]

            # Check rate limit
            if len(rate_limit_store[key]) >= max_requests:
                retry_after = int(window - (current_time - rate_limit_store[key][0])) + 1
                return jsonify({
                    'success': False,
                    'error': 'Rate limit exceeded',
                    'retry_after': retry_after
                }), 429

            # Add current request
            rate_limit_store[key].append(current_time)

            return f(*args, **kwargs)
        return wrapped
    return decorator

# Specialized rate limits
def api_rate_limit(f):
    """Standard API rate limit: 60 requests per minute."""
    return rate_limit(max_requests=60, window=60, key_prefix='api')(f)

def chat_rate_limit(f):
    """Chat rate limit: 20 requests per minute (more expensive)."""
    return rate_limit(max_requests=20, window=60, key_prefix='chat')(f)

def write_rate_limit(f):
    """Writing operation rate limit: 10 requests per minute (very expensive)."""
    return rate_limit(max_requests=10, window=60, key_prefix='write')(f)

def export_rate_limit(f):
    """Export rate limit: 10 requests per minute."""
    return rate_limit(max_requests=10, window=60, key_prefix='export')(f)

# ... existing database setup ...

# User Model
class User(UserMixin, db.Model):
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128))
    must_change_password = db.Column(db.Boolean, default=False)
    
    # Stripe fields
    stripe_customer_id = db.Column(db.String(255), nullable=True)
    stripe_subscription_id = db.Column(db.String(255), nullable=True)
    is_subscribed = db.Column(db.Boolean, default=False)
    cancel_at_period_end = db.Column(db.Boolean, default=False)
    subscription_end_date = db.Column(db.DateTime, nullable=True)
    
    # Credits and Usage
    credits = db.Column(db.Integer, default=1000)  # Default 1000 free words
    total_words_written = db.Column(db.Integer, default=0)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, user_id)

# Create database tables and master admin
with app.app_context():
    db.create_all()
    if not User.query.filter_by(username='user').first():
        admin = User(username='user', email='admin@bookgpt.ai', must_change_password=True)
        admin.set_password('password')
        db.session.add(admin)
        db.session.commit()
        logger.info("Master admin account 'user' created.")

# Initialize services
storage = BookDatabase()

# Routes

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        
        if User.query.filter_by(username=username).first():
            flash('Username already exists')
            return redirect(url_for('register'))
        
        user = User(username=username, email=email)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        login_user(user)
        return redirect(url_for('index'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user)
            if user.must_change_password:
                return redirect(url_for('change_password'))
            return redirect(url_for('index'))
        flash('Invalid username or password')
    return render_template('login.html')

@app.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    if request.method == 'POST':
        new_password = request.form.get('password')
        current_user.set_password(new_password)
        current_user.must_change_password = False
        db.session.commit()
        flash('Password updated successfully!')
        return redirect(url_for('index'))
    return render_template('change_password.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/')
@login_required
def index():
    """Serve the main web interface."""
    return render_template('index.html')

@app.route('/settings')
@login_required
def settings():
    """Serve the settings page."""
    return render_template('settings.html')

@app.route('/monitor')
@login_required
def monitor():
    """Serve the monitor page."""
    return render_template('monitor.html')

@app.route('/profile')
@login_required
def profile():
    """Serve the user profile page."""
    # Refresh user from DB to ensure we have latest subscription status
    db.session.refresh(current_user)

    # Check for success/cancel parameters from Stripe
    success = request.args.get('success', 'false')
    canceled = request.args.get('canceled', 'false')
    purchase_type = request.args.get('type', '')

    return render_template('profile.html',
                           stripe_public_key=STRIPE_PUBLIC_KEY if STRIPE_ENABLED else None,
                           stripe_enabled=STRIPE_ENABLED,
                           unlimited_usage=UNLIMITED_USAGE,
                           purchase_success=success == 'true',
                           purchase_canceled=canceled == 'true',
                           purchase_type=purchase_type)


@app.route('/api/billing/status', methods=['GET'])
def get_billing_status():
    """Get billing configuration status."""
    return jsonify({
        'success': True,
        'billing_enabled': STRIPE_ENABLED,
        'unlimited_usage': UNLIMITED_USAGE,
        'stripe_configured': bool(STRIPE_SECRET_KEY and STRIPE_PUBLIC_KEY)
    })


# Stripe Routes

def stripe_required(f):
    """Decorator to check if Stripe is enabled."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not STRIPE_ENABLED:
            return jsonify({
                'success': False,
                'error': 'Billing features are disabled. Set STRIPE_ENABLED=true in .env to enable.'
            }), 403
        return f(*args, **kwargs)
    return decorated_function

@app.route('/buy-credits', methods=['POST'])
@login_required
@stripe_required
def buy_credits():
    try:
        # Example: $10 for 50,000 words
        checkout_session = stripe.checkout.Session.create(
            line_items=[
                {
                    'price_data': {
                        'currency': 'aud',
                        'product_data': {
                            'name': '50,000 Writing Credits',
                            'description': 'Add 50,000 words to your account',
                        },
                        'unit_amount': 1000, # $10.00
                    },
                    'quantity': 1,
                },
            ],
            mode='payment',
            success_url=DOMAIN + '/profile?success=true&type=credits',
            cancel_url=DOMAIN + '/profile?canceled=true',
            customer_email=current_user.email,
            client_reference_id=current_user.id,
            metadata={'type': 'credits', 'amount': 50000}
        )
        return redirect(checkout_session.url, code=303)
    except Exception as e:
        logger.error(f"Credit purchase error: {e}")
        return str(e), 500

@app.route('/create-portal-session', methods=['POST'])
@login_required
@stripe_required
def create_portal_session():
    try:
        if not current_user.stripe_customer_id:
            # Create customer if they don't have one
            customer = stripe.Customer.create(
                email=current_user.email,
                name=current_user.username,
                metadata={'user_id': current_user.id}
            )
            current_user.stripe_customer_id = customer.id
            db.session.commit()

        portal_session = stripe.billing_portal.Session.create(
            customer=current_user.stripe_customer_id,
            return_url=DOMAIN + '/profile',
        )
        return redirect(portal_session.url, code=303)
    except Exception as e:
        logger.error(f"Portal error: {e}")
        flash('Error opening billing portal.')
        return redirect(url_for('profile'))

@app.route('/create-checkout-session', methods=['POST'])
@login_required
@stripe_required
def create_checkout_session():
    try:
        checkout_session = stripe.checkout.Session.create(
            line_items=[
                {
                    'price': STRIPE_PRICE_ID,
                    'quantity': 1,
                },
            ],
            mode='subscription',
            success_url=DOMAIN + '/profile?success=true',
            cancel_url=DOMAIN + '/profile?canceled=true',
            customer_email=current_user.email,
            client_reference_id=current_user.id
        )
        return redirect(checkout_session.url, code=303)
    except Exception as e:
        logger.error(f"Stripe error: {e}")
        return str(e), 500

@app.route('/cancel-subscription', methods=['POST'])
@login_required
@stripe_required
def cancel_subscription():
    try:
        if not current_user.stripe_subscription_id:
            flash('No active subscription found.')
            return redirect(url_for('profile'))

        # Cancel the subscription at the end of the period
        sub = stripe.Subscription.modify(
            current_user.stripe_subscription_id,
            cancel_at_period_end=True
        )
        
        current_user.cancel_at_period_end = True
        current_user.subscription_end_date = datetime.fromtimestamp(sub.current_period_end)
        db.session.commit()
        
        # Redirect with cancel confirmation parameter
        return redirect(url_for('profile', canceled='true', type='subscription_cancel'))

    except Exception as e:
        logger.error(f"Stripe cancellation error: {e}")
        flash('Error cancelling subscription. Please try again.')
        return redirect(url_for('profile'))

@app.route('/webhook', methods=['POST'])
def webhook():
    payload = request.data
    sig_header = request.headers.get('Stripe-Signature')
    endpoint_secret = os.getenv('STRIPE_WEBHOOK_SECRET')

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, endpoint_secret
        )
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return str(e), 400

    try:
        # Handle the event
        logger.info(f"Received webhook event: {event['type']}")
        
        if event['type'] == 'checkout.session.completed':
            session = event['data']['object']
            user_id = session.get('client_reference_id')
            metadata = session.get('metadata', {})
            
            logger.info(f"Processing checkout.session.completed for user_id: {user_id}")
            
            if user_id:
                user = db.session.get(User, user_id)
                if user:
                    # Handle Credit Purchase
                    if metadata.get('type') == 'credits':
                        amount = int(metadata.get('amount', 0))
                        user.credits += amount
                        db.session.commit()
                        logger.info(f"User {user.username} purchased {amount} credits.")
                        return '', 200

                    # Handle Subscription
                    user.stripe_customer_id = session.get('customer')
                    user.stripe_subscription_id = session.get('subscription')
                    user.is_subscribed = True
                    
                    # Safely handle subscription end date
                    if user.stripe_subscription_id:
                        try:
                            sub = stripe.Subscription.retrieve(user.stripe_subscription_id)
                            period_end = sub.get('current_period_end')
                            if period_end:
                                user.subscription_end_date = datetime.fromtimestamp(period_end, tz=timezone.utc).replace(tzinfo=None)
                        except Exception as sub_e:
                            logger.error(f"Error retrieving subscription end date: {sub_e}")
                    
                    user.cancel_at_period_end = False
                    db.session.commit()
                    logger.info(f"User {user.username} (ID: {user_id}) subscribed successfully.")
                else:
                    logger.error(f"User with ID {user_id} not found in database.")
            else:
                logger.error("No client_reference_id found in checkout session.")
        
        elif event['type'] == 'invoice.payment_succeeded':
            session = event['data']['object']
            subscription_id = session.get('subscription')
            if subscription_id:
                user = User.query.filter_by(stripe_subscription_id=subscription_id).first()
                if user:
                    user.is_subscribed = True
                    # Update end date based on the new invoice period
                    sub = stripe.Subscription.retrieve(subscription_id)
                    user.subscription_end_date = datetime.fromtimestamp(sub.current_period_end, tz=timezone.utc).replace(tzinfo=None)
                    db.session.commit()
                    logger.info(f"User {user.username} subscription payment succeeded.")
        
        elif event['type'] == 'customer.subscription.updated':
            subscription = event['data']['object']
            user = User.query.filter_by(stripe_subscription_id=subscription['id']).first()
            if user:
                user.cancel_at_period_end = subscription['cancel_at_period_end']
                user.subscription_end_date = datetime.fromtimestamp(subscription['current_period_end'], tz=timezone.utc).replace(tzinfo=None)
                db.session.commit()

        elif event['type'] == 'customer.subscription.deleted':
            subscription = event['data']['object']
            user = User.query.filter_by(stripe_subscription_id=subscription['id']).first()
            if user:
                user.is_subscribed = False
                user.stripe_subscription_id = None
                db.session.commit()
                logger.info(f"User {user.username} subscription ended.")

        return '', 200
    except Exception as e:
        logger.error(f"Webhook processing error: {e}")
        return str(e), 500

# Project Management

@app.route('/api/projects', methods=['GET'])
@login_required
def list_projects():
    """List all book projects for the current user."""
    try:
        projects = storage.list_user_projects(current_user.id)
        return jsonify({
            'success': True,
            'projects': projects
        })
    except Exception as e:
        logger.error(f"Error listing projects: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/projects', methods=['POST'])
@login_required
def create_project():
    """Create a new book project."""
    try:
        data = request.get_json()

        # Validate required fields
        required_fields = ['title', 'genre', 'target_length', 'writing_style']
        for field in required_fields:
            if field not in data:
                return jsonify({
                    'success': False,
                    'error': f'Missing required field: {field}'
                }), 400

        # Create project with current user
        project = BookProject(
            id=str(uuid.uuid4()),
            user_id=current_user.id,
            title=data['title'],
            genre=data['genre'],
            target_length=data['target_length'],
            writing_style=data['writing_style']
        )
        
        # Store description and characters in metadata
        if data.get('description'):
            project.metadata['description'] = data['description']
        if data.get('characters'):
            project.metadata['characters'] = data['characters']
        
        # Save project
        storage.save_project(project)
        
        return jsonify({
            'success': True,
            'project': project.to_dict()
        })
        
    except Exception as e:
        logger.error(f"Error creating project: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/projects/<project_id>', methods=['GET'])
@login_required
def get_project(project_id):
    """Get a specific project."""
    try:
        project = storage.get_project(project_id)
        if not project:
            return jsonify({
                'success': False,
                'error': 'Project not found'
            }), 404

        # Verify ownership
        if project.user_id != current_user.id:
            return jsonify({
                'success': False,
                'error': 'Access denied'
            }), 403

        # Enrich with agent state if available
        agent = get_agent()
        state = agent.project_states.get(project_id, {})

        project_data = project.to_dict()
        project_data['progress'] = {
            'phase': state.get('current_phase', project.status),
            'percent': state.get('progress_percent', 100.0 if project.status == 'completed' else 0.0),
            'words': state.get('total_words', project.total_words),
            'chapters': state.get('chapter_count', project.chapters_completed),
            'completed': state.get('completed', project.status == 'completed')
        }

        return jsonify({
            'success': True,
            'project': project_data
        })

    except Exception as e:
        logger.error(f"Error getting project: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/projects/<project_id>/start', methods=['POST'])
@login_required
@write_rate_limit
def start_writing(project_id):
    """Start the writing process for a project asynchronously."""
    try:
        project = storage.get_project(project_id)
        if not project:
            return jsonify({
                'success': False,
                'error': 'Project not found'
            }), 404

        # Verify ownership
        if project.user_id != current_user.id:
            return jsonify({
                'success': False,
                'error': 'Access denied'
            }), 403

        # Check if project is already being processed
        existing_tasks = task_manager.get_project_tasks(project_id)
        running_tasks = [task for task in existing_tasks if task.status.value in ['pending', 'running']]
        
        if running_tasks:
            return jsonify({
                'success': False,
                'error': 'Writing process is already running for this project'
            }), 400
        
        # Create async task for writing
        task_id = task_manager.create_task('write_book', project_id)
        
        # Update project status
        project.status = 'writing'
        project.updated_at = datetime.now()
        storage.save_project(project)
        
        return jsonify({
            'success': True,
            'task_id': task_id,
            'message': 'Writing process started in background'
        })
        
    except Exception as e:
        logger.error(f"Error starting writing process: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/projects/<project_id>/stop', methods=['POST'])
@login_required
def stop_writing(project_id):
    """Stop the writing process for a project."""
    try:
        project = storage.get_project(project_id)
        if not project:
            return jsonify({
                'success': False,
                'error': 'Project not found'
            }), 404

        # Verify ownership
        if project.user_id != current_user.id:
            return jsonify({
                'success': False,
                'error': 'Access denied'
            }), 403

        # Get active tasks for this project
        tasks = task_manager.get_project_tasks(project_id)
        running_tasks = [task for task in tasks if task.status.value in ['pending', 'running']]
        
        if not running_tasks:
            return jsonify({
                'success': False,
                'error': 'No active writing process found for this project'
            }), 400
        
        # Cancel all running tasks
        cancelled_count = 0
        for task in running_tasks:
            if task_manager.cancel_task(task.id):
                cancelled_count += 1
        
        if cancelled_count > 0:
            # Update project status
            project.status = 'stopped'
            project.updated_at = datetime.now()
            storage.save_project(project)
            
            return jsonify({
                'success': True,
                'message': f'Successfully stopped {cancelled_count} writing task(s)'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Unable to stop writing process - tasks may have already started'
            }), 400

    except Exception as e:
        logger.error(f"Error stopping writing process: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/projects/<project_id>/resume', methods=['POST'])
@login_required
def resume_writing(project_id):
    """Resume a stopped or failed writing process."""
    try:
        project = storage.get_project(project_id)
        if not project:
            return jsonify({
                'success': False,
                'error': 'Project not found'
            }), 404

        # Verify ownership
        if project.user_id != current_user.id:
            return jsonify({
                'success': False,
                'error': 'Access denied'
            }), 403

        # Check if project can be resumed
        if project.status == 'completed':
            return jsonify({
                'success': False,
                'error': 'Project already completed'
            }), 400

        # Check for existing running tasks
        existing_tasks = task_manager.get_project_tasks(project_id)
        running_tasks = [task for task in existing_tasks if task.status.value in ['pending', 'running']]

        if running_tasks:
            return jsonify({
                'success': False,
                'error': 'Writing process is already running for this project'
            }), 400

        # Create resume task
        task_id = task_manager.create_task('resume_book', project_id)

        return jsonify({
            'success': True,
            'task_id': task_id,
            'message': 'Writing process resuming in background'
        })

    except Exception as e:
        logger.error(f"Error resuming writing process: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/projects/<project_id>/progress', methods=['GET'])
@login_required
def get_progress(project_id):
    """Get the progress of a writing project."""
    try:
        # Get the project first
        project = storage.get_project(project_id)
        if not project:
            return jsonify({
                'success': False,
                'error': 'Project not found'
            }), 404

        # Verify ownership
        if project.user_id != current_user.id:
            return jsonify({
                'success': False,
                'error': 'Access denied'
            }), 403

        # Get the most recent task for this project
        tasks = task_manager.get_project_tasks(project_id)
        
        # If no tasks found, return project-based progress
        if not tasks:
            # Check if project has been written to (has chapters or files)
            project_dir = f"projects/{project_id}"
            has_chapters = os.path.exists(f"{project_dir}/chapters") and os.listdir(f"{project_dir}/chapters")
            has_outline = os.path.exists(f"{project_dir}/outline.txt")
            has_research = os.path.exists(f"{project_dir}/research_notes.txt")
            
            # Calculate progress based on project state
            progress_percentage = 0
            current_phase = 'created'
            
            if has_outline and not has_chapters:
                progress_percentage = 10
                current_phase = 'planning'
            elif has_research:
                progress_percentage = 20
                current_phase = 'research'
            elif has_chapters:
                # Estimate progress based on files and word count
                total_words = project.total_words or 0
                target_length = project.target_length or 1
                progress_percentage = min(100, (total_words / target_length) * 100)
                current_phase = 'writing'
                
                if progress_percentage >= 95:
                    current_phase = 'editing'
                if progress_percentage >= 100:
                    current_phase = 'refining'
                if project.status == 'completed' or project.status == 'refining':
                    current_phase = 'refining'
                    progress_percentage = 100
            
            # If project claims to be writing but has no active tasks, it may have failed
            if project.status in ['writing', 'research', 'editing'] and not has_chapters:
                current_phase = 'failed'
                progress_percentage = 0
                
                # Update project status to failed
                project.status = 'failed'
                project.updated_at = datetime.now()
                storage.save_project(project)
            
            return jsonify({
                'success': True,
                'project_id': project_id,
                'phase': current_phase,
                'progress_percentage': progress_percentage,
                'message': _get_phase_message(current_phase, project),
                'status': project.status,
                'completed': current_phase == 'completed',
                'error': None,
                'recent_activities': _get_recent_activities(project, has_outline, has_chapters),
                'phase_order': _get_phase_order(current_phase),
                'created_at': project.created_at.isoformat(),
                'updated_at': project.updated_at.isoformat(),
                'completed_at': project.completed_at.isoformat() if project.completed_at else None
            })
        
        # Get the most recent task
        latest_task = max(tasks, key=lambda t: t.created_at)
        
        # Convert task to progress format
        progress_data = {
            'success': True,
            'project_id': project_id,
            'task_id': latest_task.id,
            'phase': latest_task.current_phase,
            'progress_percentage': latest_task.progress,
            'message': latest_task.message,
            'status': latest_task.status.value,
            'completed': latest_task.status.value == 'completed',
            'error': latest_task.error,
            'recent_activities': latest_task.activities,
            'phase_order': _get_phase_order(latest_task.current_phase),
            'created_at': latest_task.created_at.isoformat(),
            'started_at': latest_task.started_at.isoformat() if latest_task.started_at else None,
            'completed_at': latest_task.completed_at.isoformat() if latest_task.completed_at else None
        }
        
        return jsonify(progress_data)
        
    except Exception as e:
        logger.error(f"Error getting progress: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

def _get_phase_order(phase: str) -> int:
    """Get the numerical order of a phase for progress calculation."""
    phase_orders = {
        'initializing': 0,
        'planning': 1,
        'research': 2,
        'writing': 3,
        'editing': 4,
        'refining': 5,
        'completed': 6,
        'failed': 7
    }
    return phase_orders.get(phase, 0)

def _get_phase_message(phase: str, project) -> str:
    """Get a descriptive message for a phase."""
    messages = {
        'initializing': 'Initializing writing process...',
        'planning': f'Creating outline for "{project.title}"...',
        'research': 'Gathering research materials...',
        'writing': f'Writing chapters for "{project.title}"...',
        'editing': 'Reviewing and editing content...',
        'refining': 'Agent Mode: Ready for instructions',
        'completed': 'Book writing completed!',
        'failed': 'Writing process failed. Please try again.'
    }
    return messages.get(phase, f'Phase: {phase}')

def _get_recent_activities(project, has_outline: bool, has_chapters: bool) -> list:
    """Generate recent activities based on project state."""
    activities = []
    
    # Project creation
    activities.append({
        'timestamp': project.created_at.isoformat(),
        'message': f'Project "{project.title}" was created'
    })
    
    # Add activities based on what exists
    if has_outline:
        activities.append({
            'timestamp': project.updated_at.isoformat(),
            'message': 'Outline was created'
        })
    
    if has_chapters:
        activities.append({
            'timestamp': project.updated_at.isoformat(),
            'message': 'Chapter writing was started'
        })
    
    # Add current status if different from creation
    if project.status != 'created':
        status_messages = {
            'writing': 'Book writing process started',
            'research': 'Research phase completed',
            'editing': 'Editing phase started',
            'completed': 'Book writing completed',
            'failed': 'Writing process failed',
            'stopped': 'Writing process was stopped'
        }
        
        status_msg = status_messages.get(project.status, f'Status changed to {project.status}')
        activities.append({
            'timestamp': project.updated_at.isoformat(),
            'message': status_msg
        })
    
    # Return most recent activities (last 10)
    return activities[-10:]

@app.route('/api/projects/<project_id>/task-status', methods=['GET'])
@login_required
def check_project_task_status(project_id):
    """Check if a project has an active background task."""
    try:
        project = storage.get_project(project_id)
        if not project:
            return jsonify({
                'success': False,
                'error': 'Project not found'
            }), 404

        # Verify ownership
        if project.user_id != current_user.id:
            return jsonify({
                'success': False,
                'error': 'Access denied'
            }), 403

        # Get tasks for this project
        tasks = task_manager.get_project_tasks(project_id)
        
        # Find active tasks (pending or running)
        active_tasks = [task for task in tasks if task.status.value in ['pending', 'running']]
        
        if active_tasks:
            # Return the most recent active task
            latest_active = max(active_tasks, key=lambda t: t.created_at)
            return jsonify({
                'success': True,
                'hasActiveTask': True,
                'taskData': latest_active.to_dict()
            })
        else:
            return jsonify({
                'success': True,
                'hasActiveTask': False,
                'taskData': None
            })
            
    except Exception as e:
        logger.error(f"Error checking task status: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/projects/<project_id>/chapters', methods=['GET'])
@login_required
def get_project_chapters(project_id):
    """Get chapters for a project."""
    try:
        project = storage.get_project(project_id)
        if not project:
            return jsonify({
                'success': False,
                'error': 'Project not found'
            }), 404

        # Verify ownership
        if project.user_id != current_user.id:
            return jsonify({
                'success': False,
                'error': 'Access denied'
            }), 403

        # Get chapters from project directory
        project_dir = f"projects/{project_id}"
        chapters_dir = f"{project_dir}/chapters"
        chapters = []
        total_words = 0
        
        if os.path.exists(chapters_dir):
            # Get all .md files and sort them naturally
            chapter_files = [f for f in os.listdir(chapters_dir) if f.endswith('.md')]
            chapter_files.sort(key=lambda x: int(x.split('_')[1].split('.')[0]))
            
            for filename in chapter_files:
                chapter_path = os.path.join(chapters_dir, filename)
                try:
                    with open(chapter_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                        word_count = len(content.split())
                        total_words += word_count
                        
                        chapter_num = int(filename.split('_')[1].split('.')[0])
                        # Normalize path separators for cross-platform compatibility
                        normalized_path = chapter_path.replace('\\', '/')
                        chapters.append({
                            'number': chapter_num,
                            'title': f'Chapter {chapter_num}',
                            'words': word_count,
                            'status': 'completed' if word_count > 100 else 'draft',
                            'file_path': normalized_path,
                            'preview': content[:200] + '...' if len(content) > 200 else content
                        })
                except Exception as e:
                    logger.warning(f"Error reading chapter file {filename}: {e}")
                    continue
        
        # Update project word count if different
        if total_words != project.total_words:
            project.total_words = total_words
            project.chapters_completed = len(chapters)
            project.updated_at = datetime.now()
            storage.save_project(project)
            logger.info(f"Updated project {project_id} word count: {total_words} words")
        
        return jsonify({
            'success': True,
            'chapters': chapters,
            'total_chapters': len(chapters),
            'total_words': total_words
        })
        
    except Exception as e:
        logger.error(f"Error getting project chapters: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/projects/<project_id>/documents', methods=['GET'])
@login_required
def get_project_documents(project_id):
    """Get planning and supporting documents for a project."""
    try:
        project = storage.get_project(project_id)
        if not project:
            return jsonify({
                'success': False,
                'error': 'Project not found'
            }), 404

        # Verify ownership
        if project.user_id != current_user.id:
            return jsonify({
                'success': False,
                'error': 'Access denied'
            }), 403

        project_dir = f"projects/{project_id}"
        document_defs = [
            {
                'id': 'outline',
                'title': 'Book Outline',
                'path': 'outline.md',
                'description': 'High-level structure and chapter breakdown generated during planning.'
            },
            {
                'id': 'research',
                'title': 'Research Notes',
                'path': 'research_notes.md',
                'description': 'Background information, world-building, and factual references collected for writing.'
            },
            {
                'id': 'editing',
                'title': 'Editing Notes',
                'path': 'editing_notes.md',
                'description': 'Post-writing editing guidance and revision suggestions.'
            }
        ]
        
        documents = []
        for doc in document_defs:
            absolute_path = os.path.join(project_dir, doc['path'])
            if os.path.exists(absolute_path):
                try:
                    with open(absolute_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    preview = content[:400]
                    if len(content) > 400:
                        preview += '...'
                    # Normalize path separators for cross-platform compatibility
                    normalized_path = absolute_path.replace('\\', '/')
                    documents.append({
                        'id': doc['id'],
                        'title': doc['title'],
                        'file_path': normalized_path,
                        'relative_path': doc['path'],
                        'description': doc['description'],
                        'words': len(content.split()),
                        'characters': len(content),
                        'preview': preview,
                        'updated_at': datetime.fromtimestamp(os.path.getmtime(absolute_path)).isoformat()
                    })
                except Exception as read_error:
                    logger.warning(f"Could not read document {absolute_path}: {read_error}")
                    continue
        
        return jsonify({
            'success': True,
            'documents': documents
        })
    except Exception as e:
        logger.error(f"Error getting project documents: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/projects/<project_id>/history', methods=['GET'])
@login_required
def get_project_history(project_id):
    """Get execution history for a project."""
    try:
        project = storage.get_project(project_id)
        if not project:
            return jsonify({
                'success': False,
                'error': 'Project not found'
            }), 404

        # Verify ownership
        if project.user_id != current_user.id:
            return jsonify({
                'success': False,
                'error': 'Access denied'
            }), 403

        # Get history from execution_history if available
        history = []
        if hasattr(project, 'execution_history') and project.execution_history:
            history = project.execution_history
        else:
            # Create basic history from project timestamps
            history = [
                {
                    'action': 'Project Created',
                    'details': f"Project '{project.title}' was created",
                    'timestamp': project.created_at
                },
                {
                    'action': 'Last Updated',
                    'details': f"Project was last updated",
                    'timestamp': project.updated_at
                }
            ]
        
        return jsonify({
            'success': True,
            'history': history
        })
        
    except Exception as e:
        logger.error(f"Error getting project history: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/projects/<project_id>/statistics', methods=['GET'])
@login_required
def get_project_statistics(project_id):
    """Get statistics for a project."""
    try:
        project = storage.get_project(project_id)
        if not project:
            return jsonify({
                'success': False,
                'error': 'Project not found'
            }), 404

        # Verify ownership
        if project.user_id != current_user.id:
            return jsonify({
                'success': False,
                'error': 'Access denied'
            }), 403

        # Calculate statistics
        chapters_completed = project.chapters_completed or 0
        total_words = project.total_words or 0
        target_length = project.target_length or 1
        
        avg_words_per_chapter = total_words / chapters_completed if chapters_completed > 0 else 0
        completion_rate = (total_words / target_length) * 100 if target_length > 0 else 0
        
        # Estimate completion based on current progress
        days_since_creation = (datetime.now() - datetime.fromisoformat(project.created_at)).days
        estimated_completion = "Unknown"
        if days_since_creation > 0 and completion_rate > 0:
            daily_rate = completion_rate / days_since_creation
            if daily_rate > 0:
                remaining_days = (100 - completion_rate) / daily_rate
                if remaining_days < 1:
                    estimated_completion = "Less than a day"
                elif remaining_days < 7:
                    estimated_completion = f"{int(remaining_days)} days"
                elif remaining_days < 30:
                    estimated_completion = f"{int(remaining_days / 7)} weeks"
                else:
                    estimated_completion = f"{int(remaining_days / 30)} months"
        
        statistics = {
            'avg_words_per_chapter': int(avg_words_per_chapter),
            'total_sessions': 1,  # Would be tracked in real implementation
            'total_writing_time': f"{days_since_creation * 2} minutes",  # Estimate
            'completion_rate': round(completion_rate, 1),
            'estimated_completion': estimated_completion,
            'total_files': chapters_completed + 2  # chapters + outline + research
        }
        
        return jsonify({
            'success': True,
            'statistics': statistics
        })
        
    except Exception as e:
        logger.error(f"Error getting project statistics: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/files/content', methods=['GET'])
def get_file_content():
    """Get content of a file."""
    try:
        file_path = request.args.get('path')
        if not file_path:
            return jsonify({
                'success': False,
                'error': 'File path is required'
            }), 400

        # Normalize path separators (handle both Windows and Unix style)
        file_path = file_path.replace('\\', '/').strip()

        # Security check - only allow files within projects directory
        if not file_path.startswith('projects/'):
            return jsonify({
                'success': False,
                'error': 'Access denied'
            }), 403

        # Convert to OS-native path for file system operations
        native_path = os.path.normpath(file_path)

        if not os.path.exists(native_path):
            return jsonify({
                'success': False,
                'error': f'File not found: {file_path}'
            }), 404

        with open(native_path, 'r', encoding='utf-8') as f:
            content = f.read()

        return jsonify({
            'success': True,
            'content': content
        })
        
    except Exception as e:
        logger.error(f"Error getting file content: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/projects/<project_id>', methods=['DELETE'])
@login_required
def delete_project(project_id):
    """Delete a project and all its associated data."""
    try:
        project = storage.get_project(project_id)
        if not project:
            return jsonify({
                'success': False,
                'error': 'Project not found'
            }), 404

        # Verify ownership
        if project.user_id != current_user.id:
            return jsonify({
                'success': False,
                'error': 'Access denied'
            }), 403

        # Check if project has active tasks
        tasks = task_manager.get_project_tasks(project_id)
        running_tasks = [task for task in tasks if task.status.value in ['pending', 'running']]
        
        # Cancel any pending tasks
        for task in tasks:
            if task.status.value == 'pending':
                task_manager.cancel_task(task.id)
        
        # For running tasks, mark them as cancelled to allow deletion
        for task in running_tasks:
            if task.status.value == 'running':
                task.status = TaskStatus.CANCELLED
                task.completed_at = datetime.now()
                task.message = "Task cancelled due to project deletion"
                logger.info(f"Cancelled running task {task.id} for project deletion")
        
        # Delete project files and directory
        project_dir = f"projects/{project_id}"
        if os.path.exists(project_dir):
            import shutil
            shutil.rmtree(project_dir)
            logger.info(f"Deleted project directory: {project_dir}")
        
        # Delete project from database
        if storage.delete_project(project_id):
            logger.info(f"Deleted project {project_id}: {project.title}")
            
            return jsonify({
                'success': True,
                'message': 'Project deleted successfully'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to delete project from database'
            }), 500
        
    except Exception as e:
        logger.error(f"Error deleting project: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/projects/<project_id>/download', methods=['GET'])
@login_required
def download_book(project_id):
    """Download the final book as a text file."""
    try:
        project = storage.get_project(project_id)
        if not project:
            return jsonify({
                'success': False,
                'error': 'Project not found'
            }), 404

        # Verify ownership
        if project.user_id != current_user.id:
            return jsonify({
                'success': False,
                'error': 'Access denied'
            }), 403

        agent = get_agent()
        book_content = agent.generate_final_book(project_id)

        if not book_content:
            return jsonify({
                'success': False,
                'error': 'Book content not found or not ready'
            }), 404

        # Set appropriate headers for file download
        response = jsonify({
            'success': True,
            'content': book_content
        })
        
        # Add content-disposition header if they want to download as file
        if request.args.get('download') == 'true':
            response.headers['Content-Disposition'] = f'attachment; filename="book_{project_id}.txt"'
        
        return response
        
    except Exception as e:
        logger.error(f"Error downloading book: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/projects/<project_id>/download/pdf', methods=['GET'])
@login_required
def download_pdf(project_id):
    """Download the book as a formatted PDF."""
    try:
        project = storage.get_project(project_id)
        if not project:
            return jsonify({
                'success': False,
                'error': 'Project not found'
            }), 404

        # Verify ownership
        if project.user_id != current_user.id:
            return jsonify({
                'success': False,
                'error': 'Access denied'
            }), 403

        agent = get_agent()
        pdf_bytes = agent.generate_pdf_book(project_id)

        if not pdf_bytes:
            return jsonify({
                'success': False,
                'error': 'PDF generation failed. Make sure reportlab is installed.'
            }), 500

        # Create response with PDF
        from flask import Response
        response = Response(
            pdf_bytes,
            mimetype='application/pdf',
            headers={
                'Content-Disposition': f'attachment; filename="{project.title.replace(" ", "_")}.pdf"'
            }
        )

        return response

    except Exception as e:
        logger.error(f"Error generating PDF: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/projects/<project_id>/chat', methods=['POST'])
@login_required
@chat_rate_limit
def chat_with_agent(project_id):
    """Chat with the Supervisor AI about the book project."""
    try:
        data = request.get_json()
        message = data.get('message')
        stream = data.get('stream', False)
        
        if not message:
            return jsonify({
                'success': False,
                'error': 'Message is required'
            }), 400
        
        # Check credits (skip if billing is disabled)
        if not UNLIMITED_USAGE and current_user.credits <= 0 and not current_user.is_subscribed:
            return jsonify({
                'success': False,
                'error': 'Insufficient credits. Please top up or subscribe to Pro.'
            }), 402

        # Get project context for the Supervisor
        project = storage.get_project(project_id)
        if not project:
            return jsonify({'success': False, 'error': 'Project not found'}), 404
        
        agent = get_agent()
        
        if stream:
            def generate():
                for update in agent.chat_with_agent_stream(project_id, message):
                    yield f"data: {json.dumps(update)}\n\n"
            return Response(generate(), mimetype='text/event-stream')
        
        # Route to agent's chat
        response = agent.chat_with_agent(project_id, message)
        
        # Deduct credits (skip if billing is disabled or user is subscribed)
        if not UNLIMITED_USAGE and response.get('success') and not current_user.is_subscribed:
            word_count = len(response.get('response', '').split())
            current_user.credits = max(0, current_user.credits - word_count)
            current_user.total_words_written += word_count
            db.session.commit()

        return jsonify(response)
        
    except Exception as e:
        logger.error(f"Error in chat: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# LLM Configuration

@app.route('/api/llm/config', methods=['GET'])
def get_llm_config():
    """Get current LLM configuration."""
    try:
        agent = get_agent()
        config = agent.llm.config
        
        return jsonify({
            'success': True,
            'config': {
                'model': config.model,
                'provider': config.provider.value,
                'base_url': config.base_url,
                'temperature': config.temperature,
                'max_tokens': config.max_tokens
            }
        })
        
    except Exception as e:
        logger.error(f"Error getting LLM config: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/llm/config', methods=['POST'])
def update_llm_config():
    """Update LLM configuration."""
    try:
        data = request.get_json()
        
        # Extract configuration parameters
        model = data.get('model')
        api_key = data.get('api_key')
        base_url = data.get('base_url')
        temperature = data.get('temperature', 0.7)
        max_tokens = data.get('max_tokens', 4096)
        
        if not model:
            return jsonify({
                'success': False,
                'error': 'Model is required'
            }), 400
        
        # Create new LLM client with updated configuration
        from utils.llm_client import create_openai_client, create_local_client, LLMClient
        from utils.llm_client import LLMProvider
        
        if base_url:
            # Custom base URL (Ollama, LM Studio, etc.)
            new_client = LLMClient(
                api_key=api_key or "not-needed",
                base_url=base_url,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens
            )
        elif api_key:
            # OpenAI API
            new_client = LLMClient(
                api_key=api_key,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens
            )
        else:
            return jsonify({
                'success': False,
                'error': 'Either api_key or base_url is required'
            }), 400
        
        # Update the global agent with new client
        agent = get_agent()
        agent.llm = new_client
        
        # Save settings to database
        llm_settings = {
            'model': model,
            'api_key': api_key,
            'base_url': base_url,
            'temperature': temperature,
            'max_tokens': max_tokens
        }
        storage.save_settings('llm', llm_settings)
        logger.info("LLM settings saved to database")
        
        return jsonify({
            'success': True,
            'message': 'LLM configuration updated successfully'
        })
        
    except Exception as e:
        logger.error(f"Error updating LLM config: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/writing/config', methods=['POST'])
def update_writing_config():
    """Update writing configuration."""
    try:
        data = request.get_json()
        
        # Extract writing settings
        default_target_length = data.get('defaultTargetLength', 50000)
        default_genre = data.get('defaultGenre', 'fiction')
        expert_mode = data.get('expertMode', False)
        
        # Save writing settings to database
        writing_settings = {
            'default_target_length': int(default_target_length),
            'default_genre': default_genre,
            'expert_mode': expert_mode
        }
        storage.save_settings('writing', writing_settings)
        logger.info("Writing settings saved to database")
        
        return jsonify({
            'success': True,
            'message': 'Writing configuration updated successfully'
        })
        
    except Exception as e:
        logger.error(f"Error updating writing config: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/llm/test', methods=['POST'])
def test_llm_connection():
    """Test LLM connection with enhanced error handling and provider-specific logic."""
    try:
        data = request.get_json(silent=True) or {}
        api_key = data.get('api_key')
        base_url = data.get('base_url')
        model = data.get('model')

        # Get from environment if not provided
        if not api_key:
            api_key = os.getenv('OPENAI_API_KEY')
        if not base_url:
            base_url = os.getenv('OPENAI_BASE_URL')
        if not model:
            model = os.getenv('LLM_MODEL', 'gpt-4-turbo-preview')

        if api_key or base_url:
            # Create a temporary client for testing
            from utils.llm_client import LLMClient, LLMConfig, LLMProvider
            config = LLMConfig(
                provider=LLMProvider.OPENAI,
                model=model or os.getenv("LLM_MODEL", "gpt-4-turbo-preview"),
                api_key=api_key,
                base_url=base_url
            )
            test_client = LLMClient(config)
            test_result = test_client.test_connection()
            current_config = config
        else:
            agent = get_agent()
            test_result = agent.llm.test_connection()
            current_config = agent.llm.config
        
        if test_result["success"]:
            return jsonify({
                'success': True,
                'response': test_result["response"],
                'model': current_config.model,
                'provider': current_config.provider.value,
                'usage': test_result.get("usage", {}),
                'base_url': current_config.base_url or 'default'
            })
        else:
            # Handle specific connection errors
            error_msg = test_result.get("error", "Unknown error")
            if "api_key" in error_msg.lower() or "401" in error_msg:
                error_msg = "Authentication failed. Please check your API key."
            elif "connection" in error_msg.lower():
                error_msg = f"Connection failed. Is the LLM server running at {base_url or 'default endpoint'}?"
            elif "refused" in error_msg.lower():
                error_msg = f"Connection refused. Is the LLM server running at {base_url}?"

            return jsonify({
                'success': False,
                'error': error_msg,
                'model': current_config.model,
                'provider': current_config.provider.value,
                'base_url': current_config.base_url or 'default'
            }), 400
            
    except ImportError as e:
        logger.error(f"OpenAI library not installed: {e}")
        return jsonify({
            'success': False,
            'error': 'OpenAI library not installed. Please install with: pip install openai'
        }), 500

    except Exception as e:
        logger.error(f"Error testing LLM connection: {e}", exc_info=True)

        # Provide more specific error messages
        error_msg = str(e)
        if "Connection" in error_msg or "connection" in error_msg:
            error_msg = f"Connection error. Is your LLM server running at {base_url or 'default endpoint'}?"
        elif "timeout" in error_msg.lower():
            error_msg = "Request timeout. The LLM server took too long to respond."
        elif "refused" in error_msg.lower():
            error_msg = f"Connection refused. Is the LLM server running at {base_url}?"
        elif "401" in error_msg or "Unauthorized" in error_msg:
            error_msg = "Authentication failed. Please check your API key."
        elif "404" in error_msg:
            error_msg = "Model not found. Please check that the model name is correct."
        elif "OpenAI" in error_msg and "installed" in error_msg:
            error_msg = "OpenAI library not installed. Please install with: pip install openai"

        return jsonify({
            'success': False,
            'error': error_msg,
            'debug_info': str(e) if os.getenv('FLASK_DEBUG', 'false').lower() == 'true' else None,
            'model': model,
            'base_url': base_url or 'default'
        }), 500

@app.route('/api/llm/presets', methods=['GET'])
def get_llm_presets():
    """Get available LLM presets."""
    try:
        presets = {
            'openai': {
                'name': 'OpenAI',
                'description': 'OpenAI API (requires API key)',
                'config': {
                    'model': 'gpt-4o',
                    'temperature': 0.7,
                    'max_tokens': 4096
                }
            },
            'openai_fast': {
                'name': 'OpenAI Fast',
                'description': 'OpenAI GPT-4o mini (faster, cheaper)',
                'config': {
                    'model': 'gpt-4o-mini',
                    'temperature': 0.7,
                    'max_tokens': 4096
                }
            },
            'ollama_llama3_2': {
                'name': 'Ollama - Llama 3.2',
                'description': 'Ollama with Llama 3.2 model (local)',
                'config': {
                    'base_url': 'http://localhost:11434/v1',
                    'model': 'llama3.2',
                    'temperature': 0.7,
                    'max_tokens': 4096
                }
            },
            'ollama_llama3_1': {
                'name': 'Ollama - Llama 3.1',
                'description': 'Ollama with Llama 3.1 model (local)', 
                'config': {
                    'base_url': 'http://localhost:11434/v1',
                    'model': 'llama3.1',
                    'temperature': 0.7,
                    'max_tokens': 4096
                }
            },
            'ollama_mistral': {
                'name': 'Ollama - Mistral',
                'description': 'Ollama with Mistral model (local)',
                'config': {
                    'base_url': 'http://localhost:11434/v1',
                    'model': 'mistral',
                    'temperature': 0.7,
                    'max_tokens': 4096
                }
            },
            'llmstuido': {
                'name': 'LM Studio',
                'description': 'LM Studio server (local)',
                'config': {
                    'base_url': 'http://localhost:1234/v1',
                    'model': 'local-model',
                    'temperature': 0.7,
                    'max_tokens': 4096
                }
            },
            'custom_local': {
                'name': 'Custom Local Server',
                'description': 'Custom local LLM server',
                'config': {
                    'api_key': 'not-needed',
                    'temperature': 0.7,
                    'max_tokens': 4096
                }
            }
        }
        
        return jsonify({
            'success': True,
            'presets': presets
        })
        
    except Exception as e:
        logger.error(f"Error getting LLM presets: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/llm/preset/<preset_name>', methods=['POST'])
def apply_llm_preset(preset_name):
    """Apply a specific LLM preset configuration."""
    try:
        presets = {
            'openai': {
                'model': 'gpt-4o',
                'temperature': 0.7,
                'max_tokens': 4096
            },
            'openai_fast': {
                'model': 'gpt-4o-mini',
                'temperature': 0.7,
                'max_tokens': 4096
            },
            'ollama': {
                'base_url': 'http://localhost:11434/v1',
                'model': 'llama3.2',
                'temperature': 0.7,
                'max_tokens': 4096
            },
            'lmstudio': {
                'base_url': 'http://localhost:1234/v1',
                'model': 'local-model',
                'temperature': 0.7,
                'max_tokens': 4096
            }
        }
        
        if preset_name not in presets:
            return jsonify({
                'success': False,
                'error': f'Unknown preset: {preset_name}'
            }), 400
        
        preset_config = presets[preset_name]
        data = request.get_json() or {}
        
        # Override with any provided data
        config = {**preset_config, **data}
        
        # Update agent configuration
        agent = get_agent()
        
        from utils.llm_client import LLMClient
        new_client = LLMClient(**config)
        agent.llm = new_client
        
        return jsonify({
            'success': True,
            'message': f'Applied preset: {preset_name}',
            'config': config
        })
        
    except Exception as e:
        logger.error(f"Error applying preset: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# Tool Operations

@app.route('/api/tools', methods=['GET'])
def list_tools():
    """List all available tools."""
    try:
        tools_info = {}
        for name, tool in ALL_TOOLS.items():
            tools_info[name] = {
                'name': tool.name(),
                'description': tool.description(),
                'parameters': tool.parameters_schema()
            }
        
        return jsonify({
            'success': True,
            'tools': tools_info
        })
        
    except Exception as e:
        logger.error(f"Error listing tools: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/projects/<project_id>/files', methods=['GET'])
def list_project_files(project_id):
    """List files in a project directory."""
    try:
        project = storage.get_project(project_id)
        if not project:
            return jsonify({
                'success': False,
                'error': 'Project not found'
            }), 404
        
        # List project files
        result = ALL_TOOLS['list_directory'].execute(project_id=project_id, path='.')
        
        if result.get('success'):
            return jsonify({
                'success': True,
                'files': result['contents']
            })
        else:
            return jsonify({
                'success': False,
                'error': result.get('error', 'Failed to list files')
            })
        
    except Exception as e:
        logger.error(f"Error listing project files: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/projects/<project_id>/files/<path:file_path>', methods=['GET'])
def read_project_file(project_id, file_path):
    """Read a specific project file."""
    try:
        project = storage.get_project(project_id)
        if not project:
            return jsonify({
                'success': False,
                'error': 'Project not found'
            }), 404
        
        # Read the file
        result = ALL_TOOLS['read_file'].execute(project_id=project_id, path=file_path)
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error reading project file: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# Settings Management

@app.route('/api/settings', methods=['GET'])
def get_settings():
    """Get current application settings."""
    try:
        all_settings = storage.get_all_settings()
        
        # Merge with defaults
        default_settings = {
            'llm': {
                'model': 'gpt-4o',
                'temperature': 0.7,
                'max_tokens': 4096,
                'auto_refresh_interval': 30
            },
            'writing': {
                'default_target_length': 50000,
                'default_genre': '',
                'max_iterations': 20,
                'auto_download': False,
                'enable_research': True,
                'expert_mode': False
            },
            'app': {
                'auto_refresh_interval': 30,
                'notifications_enabled': True,
                'sound_enabled': False,
                'theme': 'light'
            },
            'billing': {
                'enabled': STRIPE_ENABLED,
                'unlimited_usage': UNLIMITED_USAGE
            }
        }

        # Override defaults with saved settings
        for category, settings in all_settings.items():
            if category in default_settings:
                default_settings[category].update(settings)

        return jsonify({
            'success': True,
            'settings': default_settings
        })
        
    except Exception as e:
        logger.error(f"Error getting settings: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/settings', methods=['POST'])
def save_settings():
    """Save application settings."""
    try:
        data = request.get_json()
        
        # Save settings by category
        if 'llm' in data:
            storage.save_settings('llm', data['llm'])
        if 'writing' in data:
            storage.save_settings('writing', data['writing'])
        if 'app' in data:
            storage.save_settings('app', data['app'])
        
        # If it's a partial update, save it under a general category
        if not any(key in data for key in ['llm', 'writing', 'app']):
            storage.save_settings('general', data)
        
        logger.info(f"Settings saved: {data}")

        return jsonify({
            'success': True,
            'message': 'Settings saved successfully'
        })

    except Exception as e:
        logger.error(f"Error saving settings: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# =============================================================================
# EXPORT ENDPOINTS
# =============================================================================

@app.route('/api/projects/<project_id>/export/<format>', methods=['GET'])
@login_required
@export_rate_limit
def export_book(project_id, format):
    """Export book to specified format (txt, json, pdf, epub, docx)."""
    try:
        project = storage.get_project(project_id)
        if not project:
            return jsonify({
                'success': False,
                'error': 'Project not found'
            }), 404

        # Verify ownership
        if project.user_id != current_user.id:
            return jsonify({
                'success': False,
                'error': 'Access denied'
            }), 403

        from utils.export import BookExporter

        exporter = BookExporter(project_id)
        available_formats = exporter.get_available_formats()

        if format.lower() not in available_formats and format.lower() not in ['txt', 'json', 'text']:
            return jsonify({
                'success': False,
                'error': f'Format {format} not available. Available formats: {available_formats}'
            }), 400

        content = exporter.export(
            format=format,
            title=project.title,
            author=current_user.username
        )

        if content is None:
            return jsonify({
                'success': False,
                'error': f'Failed to export as {format}. Check if required libraries are installed.'
            }), 500

        # Determine content type and filename
        content_types = {
            'txt': 'text/plain',
            'text': 'text/plain',
            'json': 'application/json',
            'pdf': 'application/pdf',
            'epub': 'application/epub+zip',
            'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        }

        extensions = {
            'txt': 'txt',
            'text': 'txt',
            'json': 'json',
            'pdf': 'pdf',
            'epub': 'epub',
            'docx': 'docx'
        }

        filename = f"{project.title.replace(' ', '_')}.{extensions.get(format.lower(), 'txt')}"

        response = Response(
            content,
            mimetype=content_types.get(format.lower(), 'application/octet-stream'),
            headers={
                'Content-Disposition': f'attachment; filename="{filename}"'
            }
        )

        return response

    except Exception as e:
        logger.error(f"Error exporting book: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/projects/<project_id>/export', methods=['GET'])
@login_required
def get_export_formats(project_id):
    """Get available export formats for a project."""
    try:
        from utils.export import BookExporter

        exporter = BookExporter(project_id)
        formats = exporter.get_available_formats()

        return jsonify({
            'success': True,
            'formats': formats
        })

    except Exception as e:
        logger.error(f"Error getting export formats: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# =============================================================================
# CHAPTER VERSION HISTORY ENDPOINTS
# =============================================================================

@app.route('/api/projects/<project_id>/chapters/<int:chapter_num>/versions', methods=['GET'])
@login_required
def get_chapter_versions(project_id, chapter_num):
    """Get version history for a chapter."""
    try:
        project = storage.get_project(project_id)
        if not project:
            return jsonify({'success': False, 'error': 'Project not found'}), 404

        if project.user_id != current_user.id:
            return jsonify({'success': False, 'error': 'Access denied'}), 403

        chapter_id = f"chapter_{chapter_num}"
        versions = storage.get_chapter_versions(chapter_id, project_id)

        return jsonify({
            'success': True,
            'chapter_number': chapter_num,
            'versions': versions
        })

    except Exception as e:
        logger.error(f"Error getting chapter versions: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/projects/<project_id>/chapters/<int:chapter_num>/versions/<int:version_num>', methods=['GET'])
@login_required
def get_chapter_version_content(project_id, chapter_num, version_num):
    """Get content of a specific chapter version."""
    try:
        project = storage.get_project(project_id)
        if not project:
            return jsonify({'success': False, 'error': 'Project not found'}), 404

        if project.user_id != current_user.id:
            return jsonify({'success': False, 'error': 'Access denied'}), 403

        versions = storage.get_chapter_versions(f"chapter_{chapter_num}", project_id)

        # Find the specific version
        version_id = None
        for v in versions:
            if v['version_number'] == version_num:
                version_id = v['id']
                break

        if not version_id:
            return jsonify({'success': False, 'error': 'Version not found'}), 404

        content = storage.get_chapter_version_content(version_id)

        return jsonify({
            'success': True,
            'chapter_number': chapter_num,
            'version_number': version_num,
            'content': content
        })

    except Exception as e:
        logger.error(f"Error getting chapter version content: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/projects/<project_id>/chapters/<int:chapter_num>/restore/<int:version_num>', methods=['POST'])
@login_required
def restore_chapter_version(project_id, chapter_num, version_num):
    """Restore a chapter to a specific version."""
    try:
        project = storage.get_project(project_id)
        if not project:
            return jsonify({'success': False, 'error': 'Project not found'}), 404

        if project.user_id != current_user.id:
            return jsonify({'success': False, 'error': 'Access denied'}), 403

        chapter_id = f"chapter_{chapter_num}"

        success = storage.restore_chapter_version(chapter_id, project_id, version_num)

        if success:
            return jsonify({
                'success': True,
                'message': f'Chapter {chapter_num} restored to version {version_num}'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to restore version'
            }), 500

    except Exception as e:
        logger.error(f"Error restoring chapter version: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

# =============================================================================
# MANUAL CHAPTER EDITING ENDPOINTS
# =============================================================================

@app.route('/api/projects/<project_id>/chapters/<int:chapter_num>', methods=['GET'])
@login_required
def get_chapter_content(project_id, chapter_num):
    """Get chapter content for editing."""
    try:
        project = storage.get_project(project_id)
        if not project:
            return jsonify({'success': False, 'error': 'Project not found'}), 404

        if project.user_id != current_user.id:
            return jsonify({'success': False, 'error': 'Access denied'}), 403

        # Read chapter file directly
        chapter_path = f"projects/{project_id}/chapters/chapter_{chapter_num}.md"

        if not os.path.exists(chapter_path):
            return jsonify({'success': False, 'error': 'Chapter not found'}), 404

        with open(chapter_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Save current version before editing
        storage.save_chapter_version(
            chapter_id=f"chapter_{chapter_num}",
            project_id=project_id,
            content=content,
            created_by='user',
            change_summary='Version saved before manual edit'
        )

        return jsonify({
            'success': True,
            'chapter_number': chapter_num,
            'content': content,
            'word_count': len(content.split())
        })

    except Exception as e:
        logger.error(f"Error getting chapter content: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/projects/<project_id>/chapters/<int:chapter_num>', methods=['PUT'])
@login_required
def update_chapter_content(project_id, chapter_num):
    """Update chapter content manually."""
    try:
        project = storage.get_project(project_id)
        if not project:
            return jsonify({'success': False, 'error': 'Project not found'}), 404

        if project.user_id != current_user.id:
            return jsonify({'success': False, 'error': 'Access denied'}), 403

        data = request.get_json()
        content = data.get('content')
        change_summary = data.get('change_summary', 'Manual edit')

        if content is None:
            return jsonify({'success': False, 'error': 'Content is required'}), 400

        # Ensure chapters directory exists
        chapters_dir = f"projects/{project_id}/chapters"
        os.makedirs(chapters_dir, exist_ok=True)

        chapter_path = f"{chapters_dir}/chapter_{chapter_num}.md"

        # Save version history before overwriting
        if os.path.exists(chapter_path):
            with open(chapter_path, 'r', encoding='utf-8') as f:
                old_content = f.read()
            storage.save_chapter_version(
                chapter_id=f"chapter_{chapter_num}",
                project_id=project_id,
                content=old_content,
                created_by='user',
                change_summary='Version before manual edit'
            )

        # Write new content
        with open(chapter_path, 'w', encoding='utf-8') as f:
            f.write(content)

        # Save new version
        storage.save_chapter_version(
            chapter_id=f"chapter_{chapter_num}",
            project_id=project_id,
            content=content,
            created_by='user',
            change_summary=change_summary
        )

        # Update project word count
        total_words = 0
        for filename in os.listdir(chapters_dir):
            if filename.endswith('.md'):
                with open(os.path.join(chapters_dir, filename), 'r', encoding='utf-8') as f:
                    total_words += len(f.read().split())

        project.total_words = total_words
        project.updated_at = datetime.now()
        storage.save_project(project)

        return jsonify({
            'success': True,
            'chapter_number': chapter_num,
            'word_count': len(content.split()),
            'project_total_words': total_words
        })

    except Exception as e:
        logger.error(f"Error updating chapter content: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/projects/<project_id>/chapters/<int:chapter_num>', methods=['DELETE'])
@login_required
def delete_chapter(project_id, chapter_num):
    """Delete a chapter."""
    try:
        project = storage.get_project(project_id)
        if not project:
            return jsonify({'success': False, 'error': 'Project not found'}), 404

        if project.user_id != current_user.id:
            return jsonify({'success': False, 'error': 'Access denied'}), 403

        chapter_path = f"projects/{project_id}/chapters/chapter_{chapter_num}.md"

        if not os.path.exists(chapter_path):
            return jsonify({'success': False, 'error': 'Chapter not found'}), 404

        # Move to trash instead of deleting
        trash_dir = f"projects/{project_id}/trash"
        os.makedirs(trash_dir, exist_ok=True)

        import shutil
        shutil.move(chapter_path, f"{trash_dir}/chapter_{chapter_num}_deleted_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md")

        # Update project
        project.chapters_completed = max(0, project.chapters_completed - 1)
        storage.save_project(project)

        return jsonify({
            'success': True,
            'message': f'Chapter {chapter_num} deleted'
        })

    except Exception as e:
        logger.error(f"Error deleting chapter: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/projects/<project_id>/chapters/reorder', methods=['POST'])
@login_required
def reorder_chapters(project_id):
    """Reorder chapters."""
    try:
        project = storage.get_project(project_id)
        if not project:
            return jsonify({'success': False, 'error': 'Project not found'}), 404

        if project.user_id != current_user.id:
            return jsonify({'success': False, 'error': 'Access denied'}), 403

        data = request.get_json()
        new_order = data.get('order', [])  # List of chapter numbers in new order

        if not new_order:
            return jsonify({'success': False, 'error': 'Order is required'}), 400

        chapters_dir = f"projects/{project_id}/chapters"

        # Create temp directory for reordering
        temp_dir = f"projects/{project_id}/temp_reorder"
        os.makedirs(temp_dir, exist_ok=True)

        # Move all chapters to temp with new names
        for new_num, old_num in enumerate(new_order, 1):
            old_path = f"{chapters_dir}/chapter_{old_num}.md"
            new_path = f"{temp_dir}/chapter_{new_num}.md"

            if os.path.exists(old_path):
                shutil.move(old_path, new_path)

        # Move back from temp
        for filename in os.listdir(temp_dir):
            shutil.move(f"{temp_dir}/{filename}", f"{chapters_dir}/{filename}")

        os.rmdir(temp_dir)

        return jsonify({
            'success': True,
            'message': 'Chapters reordered successfully'
        })

    except Exception as e:
        logger.error(f"Error reordering chapters: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

# =============================================================================
# CHARACTER MANAGEMENT ENDPOINTS
# =============================================================================

@app.route('/api/projects/<project_id>/characters', methods=['GET'])
@login_required
def get_characters(project_id):
    """Get all characters for a project."""
    try:
        project = storage.get_project(project_id)
        if not project:
            return jsonify({'success': False, 'error': 'Project not found'}), 404

        if project.user_id != current_user.id:
            return jsonify({'success': False, 'error': 'Access denied'}), 403

        characters = storage.get_characters(project_id)

        return jsonify({
            'success': True,
            'characters': characters
        })

    except Exception as e:
        logger.error(f"Error getting characters: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/projects/<project_id>/characters', methods=['POST'])
@login_required
def create_character(project_id):
    """Create a new character."""
    try:
        project = storage.get_project(project_id)
        if not project:
            return jsonify({'success': False, 'error': 'Project not found'}), 404

        if project.user_id != current_user.id:
            return jsonify({'success': False, 'error': 'Access denied'}), 403

        data = request.get_json()
        data['project_id'] = project_id

        # Validate required fields
        if not data.get('name'):
            return jsonify({'success': False, 'error': 'Character name is required'}), 400

        character_id = storage.save_character(data)

        return jsonify({
            'success': True,
            'character_id': character_id
        })

    except Exception as e:
        logger.error(f"Error creating character: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/projects/<project_id>/characters/<character_id>', methods=['PUT'])
@login_required
def update_character(project_id, character_id):
    """Update a character."""
    try:
        project = storage.get_project(project_id)
        if not project:
            return jsonify({'success': False, 'error': 'Project not found'}), 404

        if project.user_id != current_user.id:
            return jsonify({'success': False, 'error': 'Access denied'}), 403

        data = request.get_json()
        data['id'] = character_id
        data['project_id'] = project_id

        storage.save_character(data)

        return jsonify({
            'success': True,
            'message': 'Character updated successfully'
        })

    except Exception as e:
        logger.error(f"Error updating character: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/projects/<project_id>/characters/<character_id>', methods=['DELETE'])
@login_required
def delete_character(project_id, character_id):
    """Delete a character."""
    try:
        project = storage.get_project(project_id)
        if not project:
            return jsonify({'success': False, 'error': 'Project not found'}), 404

        if project.user_id != current_user.id:
            return jsonify({'success': False, 'error': 'Access denied'}), 403

        storage.delete_character(character_id)

        return jsonify({
            'success': True,
            'message': 'Character deleted successfully'
        })

    except Exception as e:
        logger.error(f"Error deleting character: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

# =============================================================================
# PLOT MANAGEMENT ENDPOINTS
# =============================================================================

@app.route('/api/projects/<project_id>/plot', methods=['GET'])
@login_required
def get_plot_points(project_id):
    """Get all plot points for a project."""
    try:
        project = storage.get_project(project_id)
        if not project:
            return jsonify({'success': False, 'error': 'Project not found'}), 404

        if project.user_id != current_user.id:
            return jsonify({'success': False, 'error': 'Access denied'}), 403

        plot_points = storage.get_plot_points(project_id)

        return jsonify({
            'success': True,
            'plot_points': plot_points
        })

    except Exception as e:
        logger.error(f"Error getting plot points: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/projects/<project_id>/plot', methods=['POST'])
@login_required
def create_plot_point(project_id):
    """Create a new plot point."""
    try:
        project = storage.get_project(project_id)
        if not project:
            return jsonify({'success': False, 'error': 'Project not found'}), 404

        if project.user_id != current_user.id:
            return jsonify({'success': False, 'error': 'Access denied'}), 403

        data = request.get_json()
        data['project_id'] = project_id

        if not data.get('title'):
            return jsonify({'success': False, 'error': 'Plot point title is required'}), 400

        plot_id = storage.save_plot_point(data)

        return jsonify({
            'success': True,
            'plot_id': plot_id
        })

    except Exception as e:
        logger.error(f"Error creating plot point: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/projects/<project_id>/plot/<plot_id>', methods=['PUT'])
@login_required
def update_plot_point(project_id, plot_id):
    """Update a plot point."""
    try:
        project = storage.get_project(project_id)
        if not project:
            return jsonify({'success': False, 'error': 'Project not found'}), 404

        if project.user_id != current_user.id:
            return jsonify({'success': False, 'error': 'Access denied'}), 403

        data = request.get_json()
        data['id'] = plot_id
        data['project_id'] = project_id

        storage.save_plot_point(data)

        return jsonify({
            'success': True,
            'message': 'Plot point updated successfully'
        })

    except Exception as e:
        logger.error(f"Error updating plot point: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/projects/<project_id>/plot/<plot_id>', methods=['DELETE'])
@login_required
def delete_plot_point(project_id, plot_id):
    """Delete a plot point."""
    try:
        project = storage.get_project(project_id)
        if not project:
            return jsonify({'success': False, 'error': 'Project not found'}), 404

        if project.user_id != current_user.id:
            return jsonify({'success': False, 'error': 'Access denied'}), 403

        storage.delete_plot_point(plot_id)

        return jsonify({
            'success': True,
            'message': 'Plot point deleted successfully'
        })

    except Exception as e:
        logger.error(f"Error deleting plot point: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

# =============================================================================
# TEMPLATE ENDPOINTS
# =============================================================================

@app.route('/api/templates', methods=['GET'])
@login_required
def get_templates():
    """Get all writing templates."""
    try:
        genre = request.args.get('genre')
        templates = storage.get_templates(genre=genre, include_private=True, user_id=current_user.id)

        return jsonify({
            'success': True,
            'templates': templates
        })

    except Exception as e:
        logger.error(f"Error getting templates: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/templates/<template_id>', methods=['GET'])
@login_required
def get_template(template_id):
    """Get a specific template."""
    try:
        template = storage.get_template(template_id)

        if not template:
            return jsonify({'success': False, 'error': 'Template not found'}), 404

        return jsonify({
            'success': True,
            'template': template
        })

    except Exception as e:
        logger.error(f"Error getting template: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/templates', methods=['POST'])
@login_required
def create_template():
    """Create a new writing template."""
    try:
        data = request.get_json()

        if not data.get('name') or not data.get('system_prompt'):
            return jsonify({'success': False, 'error': 'Name and system_prompt are required'}), 400

        data['created_by'] = current_user.id
        template_id = storage.save_template(data)

        return jsonify({
            'success': True,
            'template_id': template_id
        })

    except Exception as e:
        logger.error(f"Error creating template: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/templates/<template_id>', methods=['PUT'])
@login_required
def update_template(template_id):
    """Update a writing template."""
    try:
        template = storage.get_template(template_id)

        if not template:
            return jsonify({'success': False, 'error': 'Template not found'}), 404

        # Only allow creator to update
        if template.get('created_by') and template['created_by'] != current_user.id:
            return jsonify({'success': False, 'error': 'Access denied'}), 403

        data = request.get_json()
        data['id'] = template_id
        template_id = storage.save_template(data)

        return jsonify({
            'success': True,
            'template_id': template_id
        })

    except Exception as e:
        logger.error(f"Error updating template: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/writing-styles', methods=['GET'])
def get_writing_styles():
    """Get available writing style presets."""
    from models.version_model import DEFAULT_WRITING_STYLES

    return jsonify({
        'success': True,
        'styles': DEFAULT_WRITING_STYLES
    })

@app.route('/api/genre-prompts', methods=['GET'])
def get_genre_prompts():
    """Get genre-specific prompts."""
    from models.version_model import GENRE_PROMPTS

    return jsonify({
        'success': True,
        'genres': GENRE_PROMPTS
    })

# =============================================================================
# REAL-TIME PROGRESS (SSE) ENDPOINT
# =============================================================================

@app.route('/api/projects/<project_id>/progress/stream', methods=['GET'])
@login_required
def progress_stream(project_id):
    """Server-Sent Events stream for real-time progress updates."""
    try:
        project = storage.get_project(project_id)
        if not project:
            return jsonify({'success': False, 'error': 'Project not found'}), 404

        if project.user_id != current_user.id:
            return jsonify({'success': False, 'error': 'Access denied'}), 403

        def generate():
            import time
            last_progress = None

            while True:
                # Get current task status
                tasks = task_manager.get_project_tasks(project_id)
                active_tasks = [t for t in tasks if t.status.value in ['pending', 'running']]

                if active_tasks:
                    latest_task = max(active_tasks, key=lambda t: t.created_at)
                    progress_data = {
                        'type': 'progress',
                        'phase': latest_task.current_phase,
                        'progress': latest_task.progress,
                        'message': latest_task.message,
                        'status': latest_task.status.value,
                        'activities': latest_task.activities[-5:] if latest_task.activities else []
                    }
                else:
                    # Check project status
                    project = storage.get_project(project_id)
                    progress_data = {
                        'type': 'progress',
                        'phase': project.status if project else 'unknown',
                        'progress': 100 if project and project.status == 'completed' else 0,
                        'message': 'No active task',
                        'status': 'idle',
                        'activities': []
                    }

                # Only send if changed
                if progress_data != last_progress:
                    yield f"data: {json.dumps(progress_data)}\n\n"
                    last_progress = progress_data

                time.sleep(2)  # Poll every 2 seconds

        return Response(
            generate(),
            mimetype='text/event-stream',
            headers={
                'Cache-Control': 'no-cache',
                'Connection': 'keep-alive',
                'X-Accel-Buffering': 'no'
            }
        )

    except Exception as e:
        logger.error(f"Error in progress stream: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

# =============================================================================
# BACKUP/RESTORE ENDPOINTS
# =============================================================================

@app.route('/api/projects/<project_id>/backup', methods=['GET'])
@login_required
def backup_project(project_id):
    """Export project data as JSON for backup."""
    try:
        project = storage.get_project(project_id)
        if not project:
            return jsonify({'success': False, 'error': 'Project not found'}), 404

        if project.user_id != current_user.id:
            return jsonify({'success': False, 'error': 'Access denied'}), 403

        from utils.export import BookExporter

        # Get project data
        backup_data = {
            'project': project.to_dict(),
            'characters': storage.get_characters(project_id),
            'plot_points': storage.get_plot_points(project_id),
            'exported_at': datetime.now().isoformat(),
            'version': '1.0'
        }

        # Add file contents
        exporter = BookExporter(project_id)
        backup_data['files'] = {}

        # Read all project files
        project_dir = f"projects/{project_id}"
        for root, dirs, files in os.walk(project_dir):
            for file in files:
                file_path = os.path.join(root, file)
                rel_path = os.path.relpath(file_path, project_dir)
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        backup_data['files'][rel_path] = f.read()
                except Exception:
                    pass

        # Add version history
        backup_data['chapter_versions'] = {}
        chapters_dir = f"{project_dir}/chapters"
        if os.path.exists(chapters_dir):
            for filename in os.listdir(chapters_dir):
                if filename.endswith('.md'):
                    chapter_num = filename.split('_')[1].split('.')[0]
                    versions = storage.get_chapter_versions(f"chapter_{chapter_num}", project_id)
                    if versions:
                        backup_data['chapter_versions'][chapter_num] = versions

        return Response(
            json.dumps(backup_data, indent=2),
            mimetype='application/json',
            headers={
                'Content-Disposition': f'attachment; filename="backup_{project.title.replace(" ", "_")}_{project_id}.json"'
            }
        )

    except Exception as e:
        logger.error(f"Error backing up project: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/projects/<project_id>/restore', methods=['POST'])
@login_required
def restore_project(project_id):
    """Restore project from backup."""
    try:
        project = storage.get_project(project_id)
        if not project:
            return jsonify({'success': False, 'error': 'Project not found'}), 404

        if project.user_id != current_user.id:
            return jsonify({'success': False, 'error': 'Access denied'}), 403

        if 'backup_file' not in request.files:
            return jsonify({'success': False, 'error': 'No backup file provided'}), 400

        backup_file = request.files['backup_file']
        backup_data = json.load(backup_file.stream)

        # Restore files
        project_dir = f"projects/{project_id}"
        for rel_path, content in backup_data.get('files', {}).items():
            file_path = os.path.join(project_dir, rel_path)
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)

        # Restore characters
        for char_data in backup_data.get('characters', []):
            char_data['project_id'] = project_id
            storage.save_character(char_data)

        # Restore plot points
        for plot_data in backup_data.get('plot_points', []):
            plot_data['project_id'] = project_id
            storage.save_plot_point(plot_data)

        return jsonify({
            'success': True,
            'message': 'Project restored successfully'
        })

    except Exception as e:
        logger.error(f"Error restoring project: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

# =============================================================================
# ANALYTICS ENDPOINT
# =============================================================================

@app.route('/api/projects/<project_id>/analytics', methods=['GET'])
@login_required
def get_project_analytics(project_id):
    """Get detailed analytics for a project."""
    try:
        project = storage.get_project(project_id)
        if not project:
            return jsonify({'success': False, 'error': 'Project not found'}), 404

        if project.user_id != current_user.id:
            return jsonify({'success': False, 'error': 'Access denied'}), 403

        # Calculate analytics
        chapters = []
        chapters_dir = f"projects/{project_id}/chapters"

        if os.path.exists(chapters_dir):
            for filename in os.listdir(chapters_dir):
                if filename.endswith('.md'):
                    chapter_num = int(filename.split('_')[1].split('.')[0])
                    with open(os.path.join(chapters_dir, filename), 'r', encoding='utf-8') as f:
                        content = f.read()
                        chapters.append({
                            'number': chapter_num,
                            'word_count': len(content.split()),
                            'char_count': len(content)
                        })

        chapters.sort(key=lambda x: x['number'])

        # Calculate statistics
        word_counts = [c['word_count'] for c in chapters]

        analytics = {
            'total_chapters': len(chapters),
            'total_words': sum(word_counts) if word_counts else 0,
            'average_chapter_length': sum(word_counts) / len(word_counts) if word_counts else 0,
            'max_chapter_length': max(word_counts) if word_counts else 0,
            'min_chapter_length': min(word_counts) if word_counts else 0,
            'chapters': chapters,
            'word_count_distribution': word_counts,
            'target_length': project.target_length,
            'completion_percentage': (sum(word_counts) / project.target_length * 100) if project.target_length > 0 else 0,
            'days_since_creation': (datetime.now() - datetime.fromisoformat(project.created_at)).days if project.created_at else 0,
            'estimated_completion': None
        }

        # Estimate completion if we have data
        if analytics['days_since_creation'] > 0 and analytics['completion_percentage'] > 0:
            daily_rate = analytics['completion_percentage'] / analytics['days_since_creation']
            if daily_rate > 0:
                remaining = 100 - analytics['completion_percentage']
                analytics['estimated_completion_days'] = int(remaining / daily_rate) if daily_rate > 0 else None

        # Get character count
        characters = storage.get_characters(project_id)
        analytics['character_count'] = len(characters)

        # Get plot points count
        plot_points = storage.get_plot_points(project_id)
        analytics['plot_point_count'] = len(plot_points)
        analytics['plot_points_by_status'] = {}
        for pp in plot_points:
            status = pp.get('status', 'planned')
            analytics['plot_points_by_status'][status] = analytics['plot_points_by_status'].get(status, 0) + 1

        return jsonify({
            'success': True,
            'analytics': analytics
        })

    except Exception as e:
        logger.error(f"Error getting project analytics: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

# =============================================================================
# COLLABORATION ENDPOINTS
# =============================================================================

# In-memory share storage (use database for production)
project_shares = {}

@app.route('/api/projects/<project_id>/share', methods=['POST'])
@login_required
@api_rate_limit
def share_project(project_id):
    """Share project with another user."""
    try:
        project = storage.get_project(project_id)
        if not project:
            return jsonify({'success': False, 'error': 'Project not found'}), 404

        if project.user_id != current_user.id:
            return jsonify({'success': False, 'error': 'Only the owner can share the project'}), 403

        data = request.get_json()
        share_email = data.get('email')
        permission = data.get('permission', 'view')  # view, edit, admin

        if not share_email:
            return jsonify({'success': False, 'error': 'Email is required'}), 400

        # Find user by email
        share_user = User.query.filter_by(email=share_email).first()
        if not share_user:
            return jsonify({'success': False, 'error': 'User not found'}), 404

        # Create share
        share_id = str(uuid.uuid4())
        if project_id not in project_shares:
            project_shares[project_id] = {}

        project_shares[project_id][share_id] = {
            'id': share_id,
            'project_id': project_id,
            'user_id': share_user.id,
            'user_email': share_user.email,
            'user_username': share_user.username,
            'permission': permission,
            'shared_by': current_user.id,
            'shared_at': datetime.now().isoformat()
        }

        return jsonify({
            'success': True,
            'share': project_shares[project_id][share_id]
        })

    except Exception as e:
        logger.error(f"Error sharing project: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/projects/<project_id>/shares', methods=['GET'])
@login_required
def get_project_shares(project_id):
    """Get all shares for a project."""
    try:
        project = storage.get_project(project_id)
        if not project:
            return jsonify({'success': False, 'error': 'Project not found'}), 404

        if project.user_id != current_user.id:
            return jsonify({'success': False, 'error': 'Access denied'}), 403

        shares = list(project_shares.get(project_id, {}).values())

        return jsonify({
            'success': True,
            'shares': shares
        })

    except Exception as e:
        logger.error(f"Error getting project shares: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/projects/<project_id>/shares/<share_id>', methods=['DELETE'])
@login_required
def revoke_share(project_id, share_id):
    """Revoke a project share."""
    try:
        project = storage.get_project(project_id)
        if not project:
            return jsonify({'success': False, 'error': 'Project not found'}), 404

        if project.user_id != current_user.id:
            return jsonify({'success': False, 'error': 'Only the owner can revoke shares'}), 403

        if project_id in project_shares and share_id in project_shares[project_id]:
            del project_shares[project_id][share_id]
            return jsonify({'success': True, 'message': 'Share revoked'})
        else:
            return jsonify({'success': False, 'error': 'Share not found'}), 404

    except Exception as e:
        logger.error(f"Error revoking share: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

# Comments storage (use database for production)
project_comments = {}

@app.route('/api/projects/<project_id>/comments', methods=['GET'])
@login_required
def get_comments(project_id):
    """Get comments for a project."""
    try:
        project = storage.get_project(project_id)
        if not project:
            return jsonify({'success': False, 'error': 'Project not found'}), 404

        comments = project_comments.get(project_id, [])
        return jsonify({'success': True, 'comments': comments})

    except Exception as e:
        logger.error(f"Error getting comments: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/projects/<project_id>/comments', methods=['POST'])
@login_required
@api_rate_limit
def add_comment(project_id, chapter_num=None):
    """Add a comment to a project or chapter."""
    try:
        project = storage.get_project(project_id)
        if not project:
            return jsonify({'success': False, 'error': 'Project not found'}), 404

        data = request.get_json()
        comment_text = data.get('comment')
        chapter_number = data.get('chapter_number')
        line_number = data.get('line_number')

        if not comment_text:
            return jsonify({'success': False, 'error': 'Comment text is required'}), 400

        comment_id = str(uuid.uuid4())
        comment = {
            'id': comment_id,
            'project_id': project_id,
            'user_id': current_user.id,
            'user_username': current_user.username,
            'comment': comment_text,
            'chapter_number': chapter_number,
            'line_number': line_number,
            'created_at': datetime.now().isoformat(),
            'resolved': False
        }

        if project_id not in project_comments:
            project_comments[project_id] = []
        project_comments[project_id].append(comment)

        return jsonify({'success': True, 'comment': comment})

    except Exception as e:
        logger.error(f"Error adding comment: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/projects/<project_id>/comments/<comment_id>', methods=['DELETE'])
@login_required
def delete_comment(project_id, comment_id):
    """Delete a comment."""
    try:
        if project_id in project_comments:
            project_comments[project_id] = [
                c for c in project_comments[project_id] if c['id'] != comment_id
            ]
        return jsonify({'success': True, 'message': 'Comment deleted'})

    except Exception as e:
        logger.error(f"Error deleting comment: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/projects/<project_id>/comments/<comment_id>/resolve', methods=['POST'])
@login_required
def resolve_comment(project_id, comment_id):
    """Mark a comment as resolved."""
    try:
        if project_id in project_comments:
            for comment in project_comments[project_id]:
                if comment['id'] == comment_id:
                    comment['resolved'] = True
                    comment['resolved_at'] = datetime.now().isoformat()
                    comment['resolved_by'] = current_user.id
                    return jsonify({'success': True, 'comment': comment})

        return jsonify({'success': False, 'error': 'Comment not found'}), 404

    except Exception as e:
        logger.error(f"Error resolving comment: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

# =============================================================================
# CHAPTER CUSTOM PROMPTS & STATUS
# =============================================================================

@app.route('/api/projects/<project_id>/chapters/<int:chapter_num>/prompt', methods=['POST'])
@login_required
def set_chapter_prompt(project_id, chapter_num):
    """Set a custom prompt for a chapter."""
    try:
        project = storage.get_project(project_id)
        if not project:
            return jsonify({'success': False, 'error': 'Project not found'}), 404

        if project.user_id != current_user.id:
            return jsonify({'success': False, 'error': 'Access denied'}), 403

        data = request.get_json()
        custom_prompt = data.get('prompt')

        # Store in project metadata
        if 'chapter_prompts' not in project.metadata:
            project.metadata['chapter_prompts'] = {}
        project.metadata['chapter_prompts'][str(chapter_num)] = custom_prompt
        storage.save_project(project)

        return jsonify({
            'success': True,
            'message': f'Custom prompt set for chapter {chapter_num}'
        })

    except Exception as e:
        logger.error(f"Error setting chapter prompt: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/projects/<project_id>/chapters/<int:chapter_num>/status', methods=['POST'])
@login_required
def set_chapter_status(project_id, chapter_num):
    """Set the status of a chapter (draft, review, published)."""
    try:
        project = storage.get_project(project_id)
        if not project:
            return jsonify({'success': False, 'error': 'Project not found'}), 404

        if project.user_id != current_user.id:
            return jsonify({'success': False, 'error': 'Access denied'}), 403

        data = request.get_json()
        status = data.get('status', 'draft')

        if status not in ['draft', 'review', 'published']:
            return jsonify({'success': False, 'error': 'Invalid status. Must be draft, review, or published'}), 400

        # Store in project metadata
        if 'chapter_status' not in project.metadata:
            project.metadata['chapter_status'] = {}
        project.metadata['chapter_status'][str(chapter_num)] = status
        storage.save_project(project)

        return jsonify({
            'success': True,
            'chapter_number': chapter_num,
            'status': status
        })

    except Exception as e:
        logger.error(f"Error setting chapter status: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/projects/<project_id>/chapters/status', methods=['GET'])
@login_required
def get_chapters_status(project_id):
    """Get the status of all chapters."""
    try:
        project = storage.get_project(project_id)
        if not project:
            return jsonify({'success': False, 'error': 'Project not found'}), 404

        chapter_status = project.metadata.get('chapter_status', {})

        return jsonify({
            'success': True,
            'chapter_status': chapter_status
        })

    except Exception as e:
        logger.error(f"Error getting chapter status: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

# =============================================================================
# CONTENT SAFETY
# =============================================================================

CONTENT_SAFETY_PATTERNS = {
    'violence': ['kill', 'murder', 'death', 'blood', 'gore'],
    'adult': ['explicit', 'sexual', 'nsfw'],
    'hate': ['hate', 'discrimination', 'racist']
}

def check_content_safety(content: str) -> Dict[str, Any]:
    """
    Basic content safety check.
    Returns warnings about potentially sensitive content.
    """
    warnings = []
    content_lower = content.lower()

    for category, keywords in CONTENT_SAFETY_PATTERNS.items():
        matches = [kw for kw in keywords if kw in content_lower]
        if matches:
            warnings.append({
                'category': category,
                'matched_keywords': matches,
                'severity': 'moderate',
                'message': f'Content may contain {category} themes'
            })

    return {
        'has_warnings': len(warnings) > 0,
        'warnings': warnings,
        'word_count': len(content.split()),
        'character_count': len(content)
    }

@app.route('/api/projects/<project_id>/safety-check', methods=['POST'])
@login_required
def check_project_safety(project_id):
    """Check content safety for the entire project."""
    try:
        project = storage.get_project(project_id)
        if not project:
            return jsonify({'success': False, 'error': 'Project not found'}), 404

        if project.user_id != current_user.id:
            return jsonify({'success': False, 'error': 'Access denied'}), 403

        results = {
            'project_id': project_id,
            'chapters': [],
            'overall_warnings': []
        }

        # Check each chapter
        chapters_dir = f"projects/{project_id}/chapters"
        if os.path.exists(chapters_dir):
            for filename in os.listdir(chapters_dir):
                if filename.endswith('.md'):
                    chapter_num = int(filename.split('_')[1].split('.')[0])
                    with open(os.path.join(chapters_dir, filename), 'r', encoding='utf-8') as f:
                        content = f.read()

                    safety_result = check_content_safety(content)
                    results['chapters'].append({
                        'chapter_number': chapter_num,
                        'safety': safety_result
                    })

                    if safety_result['has_warnings']:
                        results['overall_warnings'].extend([
                            {'chapter': chapter_num, **w}
                            for w in safety_result['warnings']
                        ])

        return jsonify({
            'success': True,
            'safety_report': results
        })

    except Exception as e:
        logger.error(f"Error checking content safety: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/content/check', methods=['POST'])
@login_required
def check_content():
    """Check content safety for provided text."""
    try:
        data = request.get_json()
        content = data.get('content', '')

        if not content:
            return jsonify({'success': False, 'error': 'Content is required'}), 400

        result = check_content_safety(content)

        return jsonify({
            'success': True,
            'safety': result
        })

    except Exception as e:
        logger.error(f"Error checking content: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

# =============================================================================
# SCHEDULED WRITING
# =============================================================================

# In-memory scheduled tasks (use database for production)
scheduled_tasks = {}

@app.route('/api/projects/<project_id>/schedule', methods=['POST'])
@login_required
def schedule_writing(project_id):
    """Schedule a writing task for later."""
    try:
        project = storage.get_project(project_id)
        if not project:
            return jsonify({'success': False, 'error': 'Project not found'}), 404

        if project.user_id != current_user.id:
            return jsonify({'success': False, 'error': 'Access denied'}), 403

        data = request.get_json()
        scheduled_time = data.get('scheduled_time')  # ISO format datetime
        task_type = data.get('task_type', 'write_book')  # write_book, resume_book

        if not scheduled_time:
            return jsonify({'success': False, 'error': 'scheduled_time is required'}), 400

        # Parse scheduled time
        try:
            scheduled_dt = datetime.fromisoformat(scheduled_time)
        except ValueError:
            return jsonify({'success': False, 'error': 'Invalid datetime format'}), 400

        # Create scheduled task
        task_id = str(uuid.uuid4())
        scheduled_tasks[task_id] = {
            'id': task_id,
            'project_id': project_id,
            'user_id': current_user.id,
            'task_type': task_type,
            'scheduled_time': scheduled_dt,
            'status': 'scheduled',
            'created_at': datetime.now()
        }

        return jsonify({
            'success': True,
            'scheduled_task': {
                'id': task_id,
                'project_id': project_id,
                'scheduled_time': scheduled_time,
                'task_type': task_type,
                'status': 'scheduled'
            }
        })

    except Exception as e:
        logger.error(f"Error scheduling writing: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/projects/<project_id>/schedule', methods=['GET'])
@login_required
def get_scheduled_tasks(project_id):
    """Get all scheduled tasks for a project."""
    try:
        project = storage.get_project(project_id)
        if not project:
            return jsonify({'success': False, 'error': 'Project not found'}), 404

        tasks = [
            {
                'id': t['id'],
                'project_id': t['project_id'],
                'scheduled_time': t['scheduled_time'].isoformat(),
                'task_type': t['task_type'],
                'status': t['status']
            }
            for t in scheduled_tasks.values()
            if t['project_id'] == project_id
        ]

        return jsonify({
            'success': True,
            'scheduled_tasks': tasks
        })

    except Exception as e:
        logger.error(f"Error getting scheduled tasks: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/schedule/<task_id>', methods=['DELETE'])
@login_required
def cancel_scheduled_task(task_id):
    """Cancel a scheduled task."""
    try:
        if task_id in scheduled_tasks:
            task = scheduled_tasks[task_id]

            # Verify ownership
            if task['user_id'] != current_user.id:
                return jsonify({'success': False, 'error': 'Access denied'}), 403

            del scheduled_tasks[task_id]
            return jsonify({'success': True, 'message': 'Scheduled task cancelled'})

        return jsonify({'success': False, 'error': 'Task not found'}), 404

    except Exception as e:
        logger.error(f"Error cancelling scheduled task: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

# Error handlers

@app.errorhandler(404)
def not_found(error):
    return jsonify({
        'success': False,
        'error': 'Endpoint not found'
    }), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({
        'success': False,
        'error': 'Internal server error'
    }), 500

if __name__ == '__main__':
    # Ensure data directory exists
    os.makedirs('data', exist_ok=True)
    
    logger.info("Starting BookGPT Flask application...")
    logger.info(f"Available tools: {list(ALL_TOOLS.keys())}")
    
    # Run the Flask app
    port = int(os.getenv('PORT', 6748))
    debug = os.getenv('FLASK_DEBUG', 'false').lower() == 'true'
    
    app.run(host='0.0.0.0', port=port, debug=True)