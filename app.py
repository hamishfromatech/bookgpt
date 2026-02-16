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
from dotenv import load_dotenv
from datetime import datetime, timezone
from typing import Dict, Any, List
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
stripe.api_key = os.getenv('STRIPE_SECRET_KEY')
STRIPE_PUBLIC_KEY = os.getenv('STRIPE_PUBLIC_KEY')
STRIPE_PRICE_ID = os.getenv('STRIPE_PRICE_ID')
DOMAIN = os.getenv('DOMAIN', 'http://localhost:6748')

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
    if not User.query.filter_by(username='hamish').first():
        admin = User(username='hamish', email='admin@bookgpt.ai', must_change_password=True)
        admin.set_password('password')
        db.session.add(admin)
        db.session.commit()
        logger.info("Master admin account 'hamish' created.")

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
                           stripe_public_key=STRIPE_PUBLIC_KEY,
                           purchase_success=success == 'true',
                           purchase_canceled=canceled == 'true',
                           purchase_type=purchase_type)


# Stripe Routes

@app.route('/buy-credits', methods=['POST'])
@login_required
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
def list_projects():
    """List all book projects."""
    try:
        projects = storage.list_all_projects()
        return jsonify({
            'success': True,
            'projects': projects  # Already dictionaries from storage.list_all_projects()
        })
    except Exception as e:
        logger.error(f"Error listing projects: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/projects', methods=['POST'])
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
        
        # Create project
        project = BookProject(
            id=str(uuid.uuid4()),
            user_id="default",  # For now, use a default user ID
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
def get_project(project_id):
    """Get a specific project."""
    try:
        project = storage.get_project(project_id)
        if not project:
            return jsonify({
                'success': False,
                'error': 'Project not found'
            }), 404
        
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
def start_writing(project_id):
    """Start the writing process for a project asynchronously."""
    try:
        project = storage.get_project(project_id)
        if not project:
            return jsonify({
                'success': False,
                'error': 'Project not found'
            }), 404
        
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
def stop_writing(project_id):
    """Stop the writing process for a project."""
    try:
        project = storage.get_project(project_id)
        if not project:
            return jsonify({
                'success': False,
                'error': 'Project not found'
            }), 404
        
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

@app.route('/api/projects/<project_id>/progress', methods=['GET'])
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
def check_project_task_status(project_id):
    """Check if a project has an active background task."""
    try:
        project = storage.get_project(project_id)
        if not project:
            return jsonify({
                'success': False,
                'error': 'Project not found'
            }), 404
        
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
def get_project_chapters(project_id):
    """Get chapters for a project."""
    try:
        project = storage.get_project(project_id)
        if not project:
            return jsonify({
                'success': False,
                'error': 'Project not found'
            }), 404
        
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
                        chapters.append({
                            'number': chapter_num,
                            'title': f'Chapter {chapter_num}',
                            'words': word_count,
                            'status': 'completed' if word_count > 100 else 'draft',
                            'file_path': chapter_path,
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
def get_project_documents(project_id):
    """Get planning and supporting documents for a project."""
    try:
        project = storage.get_project(project_id)
        if not project:
            return jsonify({
                'success': False,
                'error': 'Project not found'
            }), 404
        
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
                    documents.append({
                        'id': doc['id'],
                        'title': doc['title'],
                        'file_path': absolute_path,
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
def get_project_history(project_id):
    """Get execution history for a project."""
    try:
        project = storage.get_project(project_id)
        if not project:
            return jsonify({
                'success': False,
                'error': 'Project not found'
            }), 404
        
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
def get_project_statistics(project_id):
    """Get statistics for a project."""
    try:
        project = storage.get_project(project_id)
        if not project:
            return jsonify({
                'success': False,
                'error': 'Project not found'
            }), 404
        
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
        
        # Security check - only allow files within projects directory
        if not file_path.startswith('projects/'):
            return jsonify({
                'success': False,
                'error': 'Access denied'
            }), 403
        
        if not os.path.exists(file_path):
            return jsonify({
                'success': False,
                'error': 'File not found'
            }), 404
        
        with open(file_path, 'r', encoding='utf-8') as f:
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
def delete_project(project_id):
    """Delete a project and all its associated data."""
    try:
        project = storage.get_project(project_id)
        if not project:
            return jsonify({
                'success': False,
                'error': 'Project not found'
            }), 404
        
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
def download_book(project_id):
    """Download the final book as a text file."""
    try:
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

@app.route('/api/projects/<project_id>/chat', methods=['POST'])
@login_required
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
        
        # Check credits
        if current_user.credits <= 0 and not current_user.is_subscribed:
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
        
        # Deduct credits (approximate word count of response)
        if response.get('success') and not current_user.is_subscribed:
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
        data = request.json or {}
        api_key = data.get('api_key')
        base_url = data.get('base_url')
        model = data.get('model')
        
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
            error_msg = test_result["error"]
            if "api_key" in error_msg.lower() or "401" in error_msg:
                error_msg = "Authentication failed. Please check your API key."
            elif "connection" in error_msg.lower():
                error_msg = "Connection failed. Please check your base URL."
            
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
            error_msg = f"Connection error. Please check your configuration: {error_msg}"
        elif "timeout" in error_msg:
            error_msg = "Request timeout. Please check your connection and try again."
        elif "OpenAI" in error_msg and "installed" in error_msg:
            error_msg = "OpenAI library not installed. Please install with: pip install openai"
        
        return jsonify({
            'success': False,
            'error': error_msg,
            'debug_info': str(e)  # Include debug info for development
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