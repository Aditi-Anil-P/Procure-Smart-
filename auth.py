#auth.py
from flask import Blueprint, request, render_template, redirect, session, flash, url_for
from flask_sqlalchemy import SQLAlchemy
from functools import wraps
import bcrypt
from datetime import datetime
auth_bp = Blueprint('auth', __name__)
db = SQLAlchemy()

# ======  User Model  ================


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    username = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(100), nullable=False)

    def __init__(self, name, username, password):
        self.name = name
        self.username = username
        self.password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

    def check_password(self, password):
        return bcrypt.checkpw(password.encode('utf-8'), self.password.encode('utf-8'))

class Chart(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    filename = db.Column(db.String(200), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship("User", backref="charts")


# =========  Login Required Decorator =============
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash("Please log in to access this page.", "warning")
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function




# auth.py

# ... (rest of the file)

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        username = request.form['username']
        password = request.form['password']

        # --- MODIFIED LOGIC START ---
        if User.query.filter_by(username=username).first():
            # 1. Use flash() for the error message. We use 'danger' for the category.
            flash("The username is already taken. Please choose a different one.", "danger")
            
            # 2. Re-render the template, passing back the user's name and username
            #    so they don't have to re-type everything.
            return render_template('register.html', name=name, username=username) 
        # --- MODIFIED LOGIC END ---

        new_user = User(name=name, username=username, password=password)
        db.session.add(new_user)
        db.session.commit()
        
        # Best practice: use url_for() with the blueprint name
        flash("Registration successful. Please log in.", "success")
        return redirect(url_for('auth.login')) # Use url_for('auth.login') for better routing

    return render_template('register.html')


# auth.py (Corrected login function)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        # Capture 'next' parameter from the URL query string
        next_url = request.args.get('next') 

        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            session['name'] = user.name
            session['username'] = user.username
            session['user_id'] = user.id

            flash(f"Welcome, {user.name}!", "success")
            
            # Use 'next_url' if it exists (i.e., user was redirected here from a feature page)
            if next_url:
                return redirect(next_url) 
            # Otherwise, go to the default dashboard
            return redirect(url_for('dashboard'))
        else:
            flash("Invalid username or password.", "danger")
            return render_template('login.html', username=username)

            
    # GET request
    return render_template('login.html')


@auth_bp.route('/logout')
def logout():
    session.clear()
    flash("Logged out successfully.", "info")
    return redirect(url_for('home'))
