from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_apscheduler import APScheduler

db = SQLAlchemy()
login_manager = LoginManager()
scheduler = APScheduler()
login_manager.login_view = 'events.login_page'

def create_app():
    app = Flask(
        __name__,
        static_folder='static',
        template_folder='templates'
    )
    app.config['SECRET_KEY'] = 'your-secret-key'
    app.config['SQLALCHEMY_DATABASE_URI'] = (
        'postgresql://postgres:forprojects@localhost:5432/sos69'
    )
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['APSCHEDULER_API_ENABLED'] = True
    scheduler.init_app(app)
    scheduler.start()

    db.init_app(app)
    login_manager.init_app(app)

    with app.app_context():
        from web_calendar.routes import bp as events_bp
        app.register_blueprint(events_bp)
        db.create_all()
        from web_calendar.models import Event
        from web_calendar.routes import schedule_event_notifications
        from datetime import datetime

        upcoming = Event.query.filter(Event.start_time > datetime.utcnow()).all()
        for ev in upcoming:
            schedule_event_notifications(ev, scheduler)

    return app