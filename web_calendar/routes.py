import os

from flask import (
    render_template, redirect, url_for,
    request, flash, jsonify, Blueprint, current_app
)
from flask_apscheduler import APScheduler
from flask_login import (
    login_user, login_required,
    logout_user, current_user
)
from gigachat import GigaChat
from gigachat.exceptions import GigaChatException
from werkzeug.security import check_password_hash, generate_password_hash
from web_calendar import db, scheduler
from web_calendar.models import User, Event, Notification
from datetime import datetime, timedelta

bp = Blueprint('events', __name__)

def schedule_event_notifications(event: Event, scheduler: APScheduler):
    offsets = [60, 30, 10]
    for mins in offsets:
        run_time = event.start_time - timedelta(minutes=mins)
        if run_time > datetime.utcnow():
            job_id = f"notify_{event.id}_{mins}"
            try:
                scheduler.remove_job(job_id)
            except Exception:
                pass
            scheduler.add_job(
                id=job_id,
                func=create_notification,
                trigger='date',
                run_date=run_time,
                args=[event.id, mins]
            )

def create_notification(event_id: int, offset_minutes: int):
    # Работаем внутри контекста Flask
    app = scheduler.app
    with app.app_context():
        ev = Event.query.get(event_id)
        if not ev:
            return
        message = f"Напоминание: событие '{ev.title}' начнётся через {offset_minutes} минут."
        notif = Notification(
            user_id=ev.user_id,
            event_id=ev.id,
            notify_time=datetime.utcnow(),
            message=message
        )
        db.session.add(notif)
        db.session.commit()

@bp.route('/')
def initial_page():
    return redirect(url_for('events.login_page'))


@bp.route('/login', methods=['GET', 'POST'])
def login_page():
    if current_user.is_authenticated:
        return redirect(url_for('events.calendar_page'))
    if request.method == 'POST':
        email = request.form.get('email')
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
        login         = login_name,
        email         = email,
        password_hash = generate_password_hash(password)
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

@bp.route('/calendar')
@login_required
def calendar_page():
    return render_template('calendar_template.html')


@bp.route('/api/events', methods=['GET'])
@login_required
def get_events():
    year  = request.args.get('year', type=int)
    month = request.args.get('month', type=int)
    q     = Event.query.filter_by(user_id=current_user.id)
    if year and month:
        start = datetime(year, month, 1)
        end   = (start + timedelta(days=32)).replace(day=1)
        q     = q.filter(Event.start_time >= start,
                         Event.start_time < end)
    data = [{
        'id':          e.id,
        'parent_id':   e.parent_id,
        'date':        e.start_time.strftime('%Y-%m-%d'),
        'time':        e.start_time.strftime('%H:%M') + (e.end_time and '-' + e.end_time.strftime('%H:%M') or ''),
        'title':       e.title,
        'description': e.description,
        'frequency':   e.frequency,
        'color':       e.color   # возвращаем цвет пользователю
    } for e in q.order_by(Event.start_time).all()]
    return jsonify(data)

@bp.route('/api/events', methods=['POST'])
@login_required
def create_event():
    data  = request.get_json()
    start = datetime.fromisoformat(data['start'])
    end   = datetime.fromisoformat(data['end']) if data.get('end') else None
    freq  = data.get('frequency', 'none')
    color = data.get('color', '#64b5f6')  # цвет из формы или по умолчанию

    orig = Event(
        user_id     = current_user.id,
        title       = data['title'],
        description = data.get('description'),
        start_time  = start,
        end_time    = end,
        frequency   = freq,
        color       = color
    )
    db.session.add(orig)
    db.session.flush()

    # Генерируем повторения на год вперёд
    if freq in ('daily', 'weekly', 'monthly'):
        _generate_recurrences(orig, start, end, color, freq)

    db.session.commit()

    # планируем уведомления для нового события
    schedule_event_notifications(orig, current_app.apscheduler)

    return jsonify({'status': 'ok', 'id': orig.id}), 201

@bp.route('/api/events/<int:event_id>', methods=['PUT'])
@login_required
def update_event(event_id):
    data      = request.get_json()
    new_start = datetime.fromisoformat(data['start'])
    new_end   = datetime.fromisoformat(data['end']) if data.get('end') else None
    new_color = data.get('color')
    new_freq  = data.get('frequency')
    e = Event.query.filter_by(id=event_id, user_id=current_user.id).first_or_404()

    # 1) Изменение частоты
    if new_freq and new_freq != e.frequency:
        root_id = e.parent_id or e.id
        to_delete = [root_id] + [x.id for x in Event.query.filter_by(parent_id=root_id)]
        Notification.query.filter(Notification.event_id.in_(to_delete)).delete(synchronize_session=False)
        db.session.flush()
        Event.query.filter(
            (Event.id == root_id) |
            (Event.parent_id == root_id)
        ).delete(synchronize_session=False)
        db.session.flush()
        root = Event(
            user_id     = current_user.id,
            title       = e.title,
            description = e.description,
            start_time  = new_start,
            end_time    = new_end,
            frequency   = new_freq,
            color       = new_color or e.color
        )
        db.session.add(root)
        db.session.flush()
        _generate_recurrences(root, new_start, new_end, root.color, new_freq)
        db.session.commit()
        for ev_new in [root] + Event.query.filter_by(parent_id=root.id).all():
            schedule_event_notifications(ev_new, scheduler)
        return jsonify({'status': 'frequency_changed', 'id': root.id}), 200

    # 2) Перемещение серии
    if not e.parent_id and e.frequency in ('daily', 'weekly', 'monthly'):
        to_delete = [e.id] + [x.id for x in Event.query.filter_by(parent_id=e.id)]
        Notification.query.filter(Notification.event_id.in_(to_delete)).delete(synchronize_session=False)
        db.session.flush()
        Event.query.filter(
            (Event.id == e.id) |
            (Event.parent_id == e.id)
        ).delete(synchronize_session=False)
        db.session.flush()
        orig = Event(
            user_id     = current_user.id,
            title       = e.title,
            description = e.description,
            start_time  = new_start,
            end_time    = new_end,
            frequency   = e.frequency,
            color       = new_color or e.color
        )
        db.session.add(orig)
        db.session.flush()
        _generate_recurrences(orig, new_start, new_end, orig.color, e.frequency)
        db.session.commit()
        schedule_event_notifications(orig, scheduler)
        return jsonify({'status': 'updated_series', 'id': orig.id}), 200

    # 3) Изменение одной копии
    if e.parent_id and e.frequency in ('daily', 'weekly', 'monthly'):
        root_id = e.parent_id
        to_delete = [root_id] + [x.id for x in Event.query.filter_by(parent_id=root_id)]
        Notification.query.filter(Notification.event_id.in_(to_delete)).delete(synchronize_session=False)
        db.session.flush()
        Event.query.filter(
            (Event.id == root_id) |
            (Event.parent_id == root_id)
        ).delete(synchronize_session=False)
        db.session.flush()
        orig = Event(
            user_id     = current_user.id,
            title       = e.title,
            description = e.description,
            start_time  = new_start,
            end_time    = new_end,
            frequency   = e.frequency,
            color       = new_color or e.color
        )
        db.session.add(orig)
        db.session.flush()
        _generate_recurrences(orig, new_start, new_end, orig.color, e.frequency)
        db.session.commit()
        schedule_event_notifications(orig, scheduler)
        return jsonify({'status': 'split_series', 'id': orig.id}), 200

    # 4) Одиночное
    e.start_time = new_start
    e.end_time   = new_end
    if new_color:
        e.color = new_color
    if new_freq is not None:
        e.frequency = new_freq
    db.session.commit()
    schedule_event_notifications(e, scheduler)
    return jsonify({'status': 'updated_one', 'id': e.id}), 200

@bp.route('/api/events/<int:event_id>', methods=['DELETE'])
@login_required
def delete_event(event_id):
    e = Event.query.filter_by(id=event_id, user_id=current_user.id).first_or_404()
    if e.parent_id is None and e.frequency in ('daily','weekly','monthly'):
        return jsonify({'status': 'confirm'}), 200
    db.session.delete(e)
    db.session.commit()
    return jsonify({'status': 'deleted_one'}), 200

@bp.route('/api/events/<int:event_id>/delete_single', methods=['DELETE'])
@login_required
def delete_single(event_id):
    e = Event.query.filter_by(id=event_id, user_id=current_user.id).first_or_404()

    if e.parent_id is None and e.frequency in ('daily', 'weekly', 'monthly'):
        children = Event.query.filter_by(parent_id=e.id).all()

        if children:
            new_parent = children[0]
            new_parent.parent_id = None

            # Привязать остальных к новому родителю
            for child in children[1:]:
                child.parent_id = new_parent.id

            # Зафиксировать новые связи ДО удаления родителя
            db.session.commit()

    # Удалить родителя или одиночную копию
    db.session.delete(e)
    db.session.commit()
    return jsonify({'status': 'deleted_one'}), 200



@bp.route('/api/events/<int:event_id>/delete_all', methods=['DELETE'])
@login_required
def delete_all(event_id):
    Event.query.filter(
        (Event.id == event_id) | (Event.parent_id == event_id)
    ).delete(synchronize_session=False)
    db.session.commit()
    return jsonify({'status': 'deleted_all'}), 200

@bp.route('/api/generate_description', methods=['POST'])
@login_required
def generate_description():
    data = request.get_json() or {}
    title = data.get('title', '').strip()
    if not title:
        return jsonify({'error': 'Отсутствует заголовок'}), 400

    api_key = os.getenv('GIGACHAT_API_TOKEN')
    if not api_key:
        current_app.logger.error('GIGACHAT_API_TOKEN is not set')
        return jsonify({'error': 'Internal server error'}), 500

    try:
        # Инициализируем клиент: SSL-валидация отключена для упрощения
        with GigaChat(
            credentials=api_key,
            verify_ssl_certs=False            # отключаем проверку сертификатов
        ) as client:
            # Отправляем запрос и получаем ответ
            response = client.chat(
                f"Сгенерируй краткое, информативное описание события: {title}"
            )
            description = response.choices[0].message.content
    except GigaChatException as e:
        current_app.logger.error(f'GigaChat API error: {e}')
        return jsonify({'error': 'AI service unavailable'}), 502

    return jsonify({'description': description}), 200

def _generate_recurrences(orig, start, end, color, freq):
    """
    Генерация повторений на год вперёд.
    """
    delta = {
        'daily':   timedelta(days=1),
        'weekly':  timedelta(weeks=1)
    }.get(freq)
    cutoff = start + timedelta(days=365)
    current = start

    while True:
        if freq == 'monthly':
            yr, mo = current.year, current.month + 1
            if mo == 13:
                yr, mo = yr + 1, 1
            try:
                current = current.replace(year=yr, month=mo)
            except ValueError:
                try:
                    current = current.replace(year=yr, month=mo, day=1)
                except ValueError:
                    break
            if current > cutoff:
                break
        else:
            current = current + delta
            if current > cutoff:
                break

        copy = Event(
            user_id     = orig.user_id,
            title       = orig.title,
            description = orig.description,
            start_time  = current,
            end_time    = (current + (end - start)) if end else None,
            frequency   = freq,
            color       = color,       # наследуем цвет от оригинала
            parent_id   = orig.id
        )
        db.session.add(copy)

@bp.route('/notifications', methods=['GET'])
@login_required
def get_notifications():
    notifs = Notification.query \
        .filter_by(user_id=current_user.id, sent=False).order_by(Notification.notify_time).all()

    result = []
    for n in notifs:
        result.append({'id': n.id, 'message': n.message})
        n.sent = True
    db.session.commit()
    return jsonify(result)