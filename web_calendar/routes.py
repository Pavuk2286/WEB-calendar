from flask import (
    render_template, redirect, url_for,
    request, flash, jsonify, Blueprint
)
from flask_login import (
    login_user, login_required,
    logout_user, current_user
)
from werkzeug.security import check_password_hash, generate_password_hash
from web_calendar import db
from web_calendar.models import User, Event
from datetime import datetime, timedelta

bp = Blueprint('events', __name__)

# ===== Авторизация =====
@bp.route('/')
def initial_page():
    return redirect(url_for('events.login_page'))

@bp.route('/login', methods=['GET', 'POST'])
def login_page():
    if current_user.is_authenticated:
        return redirect(url_for('events.calendar_page'))
    if request.method == 'POST':
        email    = request.form.get('email')
        password = request.form.get('password')
        if not email or not password:
            flash('Поля почты и пароля должны быть заполнены')
            return render_template('login.html')
        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            nxt = request.args.get('next')
            return redirect(nxt or url_for('events.calendar_page'))
        flash('Неверная почта или пароль')
    return render_template('login.html')

@bp.route('/register', methods=['POST'])
def register():
    login_name = request.form.get('login')
    email      = request.form.get('email')
    password   = request.form.get('password')
    password2  = request.form.get('password2')
    if not all([login_name, email, password, password2]):
        flash('Все поля должны быть заполнены')
        return redirect(url_for('events.login_page') + '#register')
    if User.query.filter_by(email=email).first():
        flash('Пользователь с таким email уже существует')
        return redirect(url_for('events.login_page') + '#register')
    if password != password2:
        flash('Пароли не совпадают')
        return redirect(url_for('events.login_page') + '#register')
    new_user = User(
        login=login_name,
        email=email,
        password_hash=generate_password_hash(password)
    )
    db.session.add(new_user)
    db.session.commit()
    login_user(new_user)
    return redirect(url_for('events.calendar_page'))

@bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('events.login_page'))

@bp.errorhandler(401)
def unauthorized(e):
    return redirect(
        url_for('events.login_page') + '?next=' + request.path
    )

# ===== Календарь =====
@bp.route('/calendar')
@login_required
def calendar_page():
    return render_template('calendar_template.html')

# ===== API Событий =====
@bp.route('/api/events', methods=['GET'])
@login_required
def get_events():
    year  = request.args.get('year',  type=int)
    month = request.args.get('month', type=int)
    q     = Event.query.filter_by(user_id=current_user.id)
    if year and month:
        start = datetime(year, month, 1)
        end   = (start + timedelta(days=32)).replace(day=1)
        q     = q.filter(Event.start_time >= start,
                         Event.start_time <  end)
    data = [{
        'id': e.id,
        'date': e.start_time.strftime('%Y-%m-%d'),
        'time': e.start_time.strftime('%H:%M') +
                (e.end_time and '-' + e.end_time.strftime('%H:%M') or ''),
        'title': e.title,
        'description': e.description,
        'frequency': e.frequency
    } for e in q.all()]
    return jsonify(data)

@bp.route('/api/events', methods=['POST'])
@login_required
def create_event():
    data = request.get_json()
    # парсим даты и время первого события
    start = datetime.fromisoformat(data['start'])
    end   = datetime.fromisoformat(data['end']) if data.get('end') else None

    # создаём основное событие
    e = Event(
        user_id     = current_user.id,
        title       = data['title'],
        description = data.get('description'),
        start_time  = start,
        end_time    = end,
        frequency   = data.get('frequency', 'none')
    )
    db.session.add(e)

    # если месячная периодичность — создаём копии до конца года
    if e.frequency == 'monthly':
        day   = start.day
        year  = start.year
        month = start.month
        duration = (end - start) if end else None

        for m in range(month + 1, 13):
            try:
                new_start = start.replace(year=year, month=m, day=day)
            except ValueError:
                continue  # пропускаем месяцы без нужного дня

            new_end = new_start + duration if duration else None
            copy = Event(
                user_id     = current_user.id,
                title       = e.title,
                description = e.description,
                start_time  = new_start,
                end_time    = new_end,
                frequency   = 'none'
            )
            db.session.add(copy)

    db.session.commit()
    return jsonify({'status': 'ok', 'id': e.id}), 201

@bp.route('/api/events/<int:event_id>', methods=['PUT'])
@login_required
def update_event(event_id):
    e = Event.query.filter_by(
        id=event_id, user_id=current_user.id
    ).first_or_404()
    data = request.get_json()
    if 'start' in data:
        e.start_time = datetime.fromisoformat(data['start'])
    if 'end' in data:
        e.end_time   = (datetime.fromisoformat(data['end'])
                        if data['end'] else None)
    if 'frequency' in data:
        e.frequency  = data['frequency']
    if 'title' in data:
        e.title      = data['title']
    if 'description' in data:
        e.description= data['description']
    db.session.commit()
    return jsonify({'status': 'ok'})

@bp.route('/api/events/<int:event_id>', methods=['DELETE'])
@login_required
def delete_event(event_id):
    e = Event.query.filter_by(
        id=event_id, user_id=current_user.id
    ).first_or_404()
    db.session.delete(e)
    db.session.commit()
    return jsonify({'status': 'deleted'})