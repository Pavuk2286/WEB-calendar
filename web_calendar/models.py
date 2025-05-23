from flask_login import UserMixin
from web_calendar import db, login_manager
from datetime import datetime

class User(db.Model, UserMixin):
    id            = db.Column(db.Integer, primary_key=True)
    email         = db.Column(db.String(128), unique=True, nullable=False)
    login         = db.Column(db.String(128), nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)

    events = db.relationship('Event', backref='user', lazy=True)

class Event(db.Model):
    id            = db.Column(db.Integer, primary_key=True)
    user_id       = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    title         = db.Column(db.String(256), nullable=False)
    description   = db.Column(db.Text)
    start_time    = db.Column(db.DateTime, nullable=False)
    end_time      = db.Column(db.DateTime)
    frequency     = db.Column(db.String(50), default='none')
    color         = db.Column(db.String(20), default='#64b5f6')  # цвет заливки по умолчанию (не синий)
    created_at    = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at    = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )
    parent_id     = db.Column(db.Integer, db.ForeignKey('event.id'), nullable=True)
    children      = db.relationship(
        'Event',
        backref=db.backref('parent', remote_side=[id]),
        lazy='dynamic',
        cascade='all'
    )

class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    event_id = db.Column(db.Integer, db.ForeignKey('event.id'), nullable=False)
    notify_time = db.Column(db.DateTime, nullable=False)
    message = db.Column(db.String(256), nullable=False)
    sent = db.Column(db.Boolean, default=False, nullable=False)

    user = db.relationship('User', backref='notifications')
    event = db.relationship('Event', backref='notifications')

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))
