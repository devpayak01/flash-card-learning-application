import os
from datetime import datetime, timezone, timedelta
from functools import wraps

from flask import (Flask, render_template, redirect, url_for, flash,
                   request, jsonify, abort)
from flask_login import (LoginManager, login_user, logout_user,
                         login_required, current_user)
from flask_mail import Mail, Message
from flask_wtf import CSRFProtect
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature

from config import Config
from models import db, User, Deck, Card, StudySession

# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------

app = Flask(__name__)
app.config.from_object(Config)

db.init_app(app)
csrf = CSRFProtect(app)
mail = Mail(app)

login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message_category = 'info'

serializer = URLSafeTimedSerializer(app.config['SECRET_KEY'])


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def generate_reset_token(email):
    return serializer.dumps(email, salt='password-reset-salt')


def verify_reset_token(token, expiration=3600):
    try:
        email = serializer.loads(token, salt='password-reset-salt',
                                 max_age=expiration)
    except (SignatureExpired, BadSignature):
        return None
    return email


def send_reset_email(user):
    token = generate_reset_token(user.email)
    reset_url = url_for('reset_password', token=token, _external=True)

    msg = Message('Password Reset Request — FlashMind',
                  recipients=[user.email])
    msg.html = render_template('email/reset_password.html',
                               user=user, reset_url=reset_url)
    msg.body = (f"Hi {user.username},\n\n"
                f"To reset your password, visit: {reset_url}\n\n"
                f"If you did not request this, ignore this email.\n\n"
                f"— FlashMind Team")
    try:
        mail.send(msg)
    except Exception as e:
        # In development, print the reset URL to the console
        print(f"\n*** PASSWORD RESET LINK (dev mode): {reset_url} ***\n")


# ---------------------------------------------------------------------------
# PUBLIC ROUTES
# ---------------------------------------------------------------------------

@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return render_template('index.html')


# ---------------------------------------------------------------------------
# AUTH ROUTES
# ---------------------------------------------------------------------------

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm = request.form.get('confirm_password', '')

        # Validation
        errors = []
        if not username or len(username) < 3:
            errors.append('Username must be at least 3 characters.')
        if not email or '@' not in email:
            errors.append('Please enter a valid email address.')
        if len(password) < 6:
            errors.append('Password must be at least 6 characters.')
        if password != confirm:
            errors.append('Passwords do not match.')
        if User.query.filter_by(username=username).first():
            errors.append('Username already taken.')
        if User.query.filter_by(email=email).first():
            errors.append('Email already registered.')

        if errors:
            for e in errors:
                flash(e, 'danger')
            return render_template('register.html')

        user = User(username=username, email=email)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        login_user(user)
        flash('Welcome to FlashMind! 🎉', 'success')
        return redirect(url_for('dashboard'))

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        remember = request.form.get('remember') == 'on'

        user = User.query.filter(
            (User.username == username) | (User.email == username)
        ).first()

        if user and user.check_password(password):
            login_user(user, remember=remember)
            next_page = request.args.get('next')
            flash('Welcome back! 👋', 'success')
            return redirect(next_page or url_for('dashboard'))

        flash('Invalid username or password.', 'danger')

    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))


@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        user = User.query.filter_by(email=email).first()
        if user:
            send_reset_email(user)
        # Always show success to prevent email enumeration
        flash('If that email is registered, a reset link has been sent.', 'info')
        return redirect(url_for('login'))

    return render_template('forgot_password.html')


@app.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    email = verify_reset_token(token)
    if email is None:
        flash('The reset link is invalid or has expired.', 'danger')
        return redirect(url_for('forgot_password'))

    if request.method == 'POST':
        password = request.form.get('password', '')
        confirm = request.form.get('confirm_password', '')

        if len(password) < 6:
            flash('Password must be at least 6 characters.', 'danger')
            return render_template('reset_password.html', token=token)
        if password != confirm:
            flash('Passwords do not match.', 'danger')
            return render_template('reset_password.html', token=token)

        user = User.query.filter_by(email=email).first()
        if user:
            user.set_password(password)
            db.session.commit()
            flash('Your password has been updated! Please log in.', 'success')
            return redirect(url_for('login'))

    return render_template('reset_password.html', token=token)


# ---------------------------------------------------------------------------
# DASHBOARD
# ---------------------------------------------------------------------------

@app.route('/dashboard')
@login_required
def dashboard():
    decks = current_user.decks.order_by(Deck.created_at.desc()).all()
    total_cards = sum(d.card_count for d in decks)
    sessions = current_user.study_sessions.order_by(
        StudySession.completed_at.desc()).limit(10).all()
    total_sessions = current_user.study_sessions.count()
    total_studied = sum(s.cards_studied for s in
                        current_user.study_sessions.all())

    return render_template('dashboard.html',
                           decks=decks,
                           total_cards=total_cards,
                           sessions=sessions,
                           total_sessions=total_sessions,
                           total_studied=total_studied)


# ---------------------------------------------------------------------------
# DECK ROUTES
# ---------------------------------------------------------------------------

@app.route('/decks')
@login_required
def decks():
    user_decks = current_user.decks.order_by(Deck.created_at.desc()).all()
    return render_template('decks.html', decks=user_decks)


@app.route('/decks/create', methods=['GET', 'POST'])
@login_required
def create_deck():
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        color = request.form.get('color', '#6C63FF')

        if not title:
            flash('Please enter a deck title.', 'danger')
            return render_template('create_deck.html')

        deck = Deck(title=title, description=description,
                    color=color, user_id=current_user.id)
        db.session.add(deck)
        db.session.commit()
        flash(f'Deck "{title}" created!', 'success')
        return redirect(url_for('deck_detail', deck_id=deck.id))

    return render_template('create_deck.html')


@app.route('/decks/<int:deck_id>')
@login_required
def deck_detail(deck_id):
    deck = Deck.query.get_or_404(deck_id)
    if deck.user_id != current_user.id:
        abort(403)
    cards = deck.cards.order_by(Card.created_at.desc()).all()
    return render_template('deck_detail.html', deck=deck, cards=cards)


@app.route('/decks/<int:deck_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_deck(deck_id):
    deck = Deck.query.get_or_404(deck_id)
    if deck.user_id != current_user.id:
        abort(403)

    if request.method == 'POST':
        deck.title = request.form.get('title', '').strip()
        deck.description = request.form.get('description', '').strip()
        deck.color = request.form.get('color', '#6C63FF')

        if not deck.title:
            flash('Deck title cannot be empty.', 'danger')
            return render_template('create_deck.html', deck=deck, editing=True)

        db.session.commit()
        flash('Deck updated!', 'success')
        return redirect(url_for('deck_detail', deck_id=deck.id))

    return render_template('create_deck.html', deck=deck, editing=True)


@app.route('/decks/<int:deck_id>/delete', methods=['POST'])
@login_required
def delete_deck(deck_id):
    deck = Deck.query.get_or_404(deck_id)
    if deck.user_id != current_user.id:
        abort(403)
    db.session.delete(deck)
    db.session.commit()
    flash('Deck deleted.', 'info')
    return redirect(url_for('decks'))


# ---------------------------------------------------------------------------
# CARD ROUTES
# ---------------------------------------------------------------------------

@app.route('/decks/<int:deck_id>/cards/create', methods=['GET', 'POST'])
@login_required
def create_card(deck_id):
    deck = Deck.query.get_or_404(deck_id)
    if deck.user_id != current_user.id:
        abort(403)

    if request.method == 'POST':
        question = request.form.get('question', '').strip()
        answer = request.form.get('answer', '').strip()

        if not question or not answer:
            flash('Both question and answer are required.', 'danger')
            return render_template('create_card.html', deck=deck)

        card = Card(question=question, answer=answer, deck_id=deck.id)
        db.session.add(card)
        db.session.commit()
        flash('Card added!', 'success')

        if request.form.get('add_another'):
            return redirect(url_for('create_card', deck_id=deck.id))
        return redirect(url_for('deck_detail', deck_id=deck.id))

    return render_template('create_card.html', deck=deck)


@app.route('/cards/<int:card_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_card(card_id):
    card = Card.query.get_or_404(card_id)
    if card.deck.user_id != current_user.id:
        abort(403)

    if request.method == 'POST':
        card.question = request.form.get('question', '').strip()
        card.answer = request.form.get('answer', '').strip()

        if not card.question or not card.answer:
            flash('Both question and answer are required.', 'danger')
            return render_template('create_card.html', deck=card.deck,
                                   card=card, editing=True)

        db.session.commit()
        flash('Card updated!', 'success')
        return redirect(url_for('deck_detail', deck_id=card.deck_id))

    return render_template('create_card.html', deck=card.deck,
                           card=card, editing=True)


@app.route('/cards/<int:card_id>/delete', methods=['POST'])
@login_required
def delete_card(card_id):
    card = Card.query.get_or_404(card_id)
    if card.deck.user_id != current_user.id:
        abort(403)
    deck_id = card.deck_id
    db.session.delete(card)
    db.session.commit()
    flash('Card deleted.', 'info')
    return redirect(url_for('deck_detail', deck_id=deck_id))


# ---------------------------------------------------------------------------
# STUDY MODE
# ---------------------------------------------------------------------------

@app.route('/decks/<int:deck_id>/study')
@login_required
def study(deck_id):
    deck = Deck.query.get_or_404(deck_id)
    if deck.user_id != current_user.id:
        abort(403)

    cards = deck.cards.order_by(Card.next_review.asc()).all()
    if not cards:
        flash('This deck has no cards yet. Add some first!', 'warning')
        return redirect(url_for('deck_detail', deck_id=deck.id))

    cards_data = [{
        'id': c.id,
        'question': c.question,
        'answer': c.answer,
        'difficulty': c.difficulty,
        'times_reviewed': c.times_reviewed,
        'accuracy': c.accuracy
    } for c in cards]

    return render_template('study.html', deck=deck, cards_data=cards_data)


@app.route('/api/study/answer', methods=['POST'])
@login_required
def study_answer():
    data = request.get_json()
    card_id = data.get('card_id')
    correct = data.get('correct', False)

    card = Card.query.get_or_404(card_id)
    if card.deck.user_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403

    card.times_reviewed += 1
    if correct:
        card.times_correct += 1
        # Simple spaced repetition: increase interval on correct answers
        days = min(2 ** card.times_correct, 30)
        card.next_review = datetime.now(timezone.utc) + timedelta(days=days)
        card.difficulty = max(0, card.difficulty - 1)
    else:
        # Reset interval on incorrect
        card.next_review = datetime.now(timezone.utc) + timedelta(hours=4)
        card.difficulty = min(3, card.difficulty + 1)

    db.session.commit()

    return jsonify({
        'success': True,
        'accuracy': card.accuracy,
        'times_reviewed': card.times_reviewed
    })


@app.route('/api/study/complete', methods=['POST'])
@login_required
def study_complete():
    data = request.get_json()
    deck_id = data.get('deck_id')
    cards_studied = data.get('cards_studied', 0)
    correct_count = data.get('correct_count', 0)
    duration = data.get('duration', 0)

    session = StudySession(
        user_id=current_user.id,
        deck_id=deck_id,
        cards_studied=cards_studied,
        correct_count=correct_count,
        duration_seconds=duration
    )
    db.session.add(session)
    db.session.commit()

    return jsonify({'success': True, 'session_id': session.id})


# ---------------------------------------------------------------------------
# ERROR HANDLERS
# ---------------------------------------------------------------------------

@app.errorhandler(404)
def not_found(e):
    return render_template('errors/404.html'), 404


@app.errorhandler(403)
def forbidden(e):
    return render_template('errors/403.html'), 403


@app.errorhandler(500)
def server_error(e):
    return render_template('errors/500.html'), 500


# ---------------------------------------------------------------------------
# INIT DB & RUN
# ---------------------------------------------------------------------------

with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(debug=True, port=5000)
