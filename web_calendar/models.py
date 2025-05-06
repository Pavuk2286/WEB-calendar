from flask_login import UserMixin
from web_calendar import db, login_manager
from datetime import datetime

class User(db.Model, UserMixin):
    id            = db.Column(db.Integer, primary_key=True)
    email         = db.Column(db.String(128), unique=True, nullable=False)
    login         = db.Column(db.String(128), nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    events        = db.relationship('Event', backref='user', lazy=True)

class Event(db.Model):
    id          = db.Column(db.Integer, primary_key=True)
    user_id     = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    title       = db.Column(db.String(256), nullable=False)
    description = db.Column(db.Text)
    start_time  = db.Column(db.DateTime, nullable=False)
    end_time    = db.Column(db.DateTime)
    frequency   = db.Column(db.String(50), default='none')
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at  = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))