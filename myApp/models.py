from datetime import datetime, timezone
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()


class User(UserMixin, db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    decks = db.relationship('Deck', backref='author', lazy='dynamic', cascade='all, delete-orphan')
    study_sessions = db.relationship('StudySession', backref='user', lazy='dynamic', cascade='all, delete-orphan')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f'<User {self.username}>'


class Deck(db.Model):
    __tablename__ = 'decks'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, default='')
    color = db.Column(db.String(7), default='#6C63FF')
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    cards = db.relationship('Card', backref='deck', lazy='dynamic', cascade='all, delete-orphan')
    study_sessions = db.relationship('StudySession', backref='deck', lazy='dynamic', cascade='all, delete-orphan')

    @property
    def card_count(self):
        return self.cards.count()

    def __repr__(self):
        return f'<Deck {self.title}>'


class Card(db.Model):
    __tablename__ = 'cards'

    id = db.Column(db.Integer, primary_key=True)
    question = db.Column(db.Text, nullable=False)
    answer = db.Column(db.Text, nullable=False)
    deck_id = db.Column(db.Integer, db.ForeignKey('decks.id'), nullable=False)
    difficulty = db.Column(db.Integer, default=0)  # 0=new, 1=easy, 2=medium, 3=hard
    times_reviewed = db.Column(db.Integer, default=0)
    times_correct = db.Column(db.Integer, default=0)
    next_review = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    @property
    def accuracy(self):
        if self.times_reviewed == 0:
            return 0
        return round((self.times_correct / self.times_reviewed) * 100)

    def __repr__(self):
        return f'<Card {self.id} in Deck {self.deck_id}>'


class StudySession(db.Model):
    __tablename__ = 'study_sessions'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    deck_id = db.Column(db.Integer, db.ForeignKey('decks.id'), nullable=False)
    cards_studied = db.Column(db.Integer, default=0)
    correct_count = db.Column(db.Integer, default=0)
    duration_seconds = db.Column(db.Integer, default=0)
    completed_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    @property
    def accuracy(self):
        if self.cards_studied == 0:
            return 0
        return round((self.correct_count / self.cards_studied) * 100)

    def __repr__(self):
        return f'<StudySession {self.id}>'
