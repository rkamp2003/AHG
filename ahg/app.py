from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import sqlite3
import json
from datetime import datetime
from openai  import OpenAI# ChatGPT API
import os
import openai
import requests
from werkzeug.datastructures import MultiDict


app = Flask(__name__)
app.secret_key = os.urandom(24) 

### DATABASE ###

def get_db_connection():
    conn = sqlite3.connect('ahg/database.db')
    conn.row_factory = sqlite3.Row
    return conn

### HOMEPAGE ###

@app.route('/')
def index():
    return render_template('index.html')


### TEACHER ###

@app.route('/login_teacher', methods=['POST'])
def login_teacher():
    email = request.form.get('email')
    password = request.form.get('password')

    if not email or not password:
        return "Fehler: Bitte füllen Sie alle Felder aus.", 400

    conn = get_db_connection()
    teacher = conn.execute('SELECT * FROM Teachers WHERE email = ? AND password = ?', (email, password)).fetchone()
    conn.close()

    if teacher:
        # Speichere nur die primitive ID (Integer) in der Session
        session['teacher_id'] = int(teacher['id'])
        return redirect(url_for('teacher_dashboard'))
    else:
        return "Login data invalid. Please try again."


    
@app.route('/teacher_dashboard')
def teacher_dashboard():
    if 'teacher_id' not in session:
        return redirect('/')

    teacher_id = session['teacher_id']

    conn = get_db_connection()
    teacher = conn.execute('SELECT * FROM Teachers WHERE id = ?', (teacher_id,)).fetchone()
    
    # Hole Klassen mit allen relevanten Feldern, einschließlich grade_level
    classes = conn.execute(
        'SELECT id, class_name, subject, grade_level FROM Classes WHERE teacher_id = ?',
        (teacher_id,)
    ).fetchall()
    conn.close()

    return render_template('teacher_dashboard.html', teacher=teacher, classes=classes)


    

@app.route('/register_teacher', methods=['POST'])
def register_teacher():
    name = request.form['name']
    email = request.form['email']
    password = request.form['password']
    
    conn = get_db_connection()
    conn.execute('INSERT INTO Teachers (name, email, password) VALUES (?, ?, ?)', (name, email, password))
    conn.commit()
    conn.close()
    
    return redirect('/')


@app.route('/create_class', methods=['POST'])
def create_class():
    teacher_id = request.form['teacher_id']
    class_name = request.form['class_name']
    subject = request.form['subject']
    grade_level = request.form.get('grade_level', type=int)

    conn = get_db_connection()
    conn.execute(
        'INSERT INTO Classes (class_name, subject, grade_level, teacher_id) VALUES (?, ?, ?, ?)',
        (class_name, subject, grade_level, teacher_id)
    )
    conn.commit()
    conn.close()

    return redirect(url_for('teacher_dashboard', teacher_id=teacher_id))


@app.route('/class_details_teacher/<int:class_id>/<int:teacher_id>')
def class_details_teacher(class_id, teacher_id):
    import json
    from datetime import datetime
    conn = get_db_connection()

    # Klasseninformationen abrufen
    class_info = conn.execute(
        '''
        SELECT Classes.id, Classes.class_name, Classes.subject, Teachers.name AS teacher_name
        FROM Classes
        JOIN Teachers ON Classes.teacher_id = Teachers.id
        WHERE Classes.id = ? AND teacher_id = ?
        ''', (class_id, teacher_id)
    ).fetchone()

    # Schüler und deren Skill Levels abrufen
    students = conn.execute(
        '''
        SELECT Participants.id, Participants.name, ClassMembers.class_skill_level
        FROM Participants
        JOIN ClassMembers ON Participants.id = ClassMembers.student_id
        WHERE ClassMembers.class_id = ?
        ''', (class_id,)
    ).fetchall()

    # Hausaufgaben abrufen
    # Abrufen der Homework-Listen für die spezifische Klasse
    homework_list = conn.execute(
        '''
        SELECT Homework.id, Homework.title, Homework.date_created, Homework.status,
            CASE 
                WHEN EXISTS (
                    SELECT 1 FROM HomeworkResults
                    WHERE HomeworkResults.homework_id = Homework.id
                )
                OR EXISTS (
                    SELECT 1 FROM HomeworkOpenQuestionsResults
                    WHERE HomeworkOpenQuestionsResults.homework_id = Homework.id
                )
                THEN 'Done'
                ELSE 'Open'
            END AS done_status
        FROM Homework
        WHERE Homework.class_id = ? AND Homework.is_team_challenge = 0
        ''', (class_id,)
    ).fetchall()

    homework_list_graphs = conn.execute(
    '''
    SELECT Homework.id, Homework.title, Homework.date_created, Homework.status,
        CASE 
            WHEN EXISTS (
                SELECT 1 FROM HomeworkResults
                WHERE HomeworkResults.homework_id = Homework.id
            )
            OR EXISTS (
                SELECT 1 FROM HomeworkOpenQuestionsResults
                WHERE HomeworkOpenQuestionsResults.homework_id = Homework.id
            )
            THEN 'Done'
            ELSE 'Open'
        END AS done_status
    FROM Homework
    WHERE Homework.class_id = ?
    ''', (class_id,)
).fetchall()

    # Team Challenges für diese Klasse abrufen
    team_challenges = conn.execute(
        '''
        SELECT Homework.id, Homework.title, Homework.date_created,
            TeamChallenges.start_time, TeamChallenges.end_time, TeamChallenges.goal_score, TeamChallenges.current_score, Homework.status
        FROM Homework
        JOIN TeamChallenges ON Homework.id = TeamChallenges.homework_id
        WHERE Homework.class_id = ? AND Homework.is_team_challenge = 1 AND Homework.status IN ("draft", "published")
        ''',
        (class_id,)
    ).fetchall()

    # Durchschnittswerte für Graphen berechnen (MC + Open Questions, jeweils in % und Skill)
    dates = []
    titles = []
    avg_percent_corrects = []
    avg_skill_levels = []

    # Hole alle veröffentlichten Hausaufgaben (MC + Open)
    published_homework = [hw for hw in homework_list_graphs if hw['status'] == 'published']

    for hw in published_homework:
        # Datum und Titel erfassen
        date_created = hw['date_created']
        if isinstance(date_created, str):
            try:
                date_created = datetime.strptime(date_created, '%Y-%m-%d')
            except ValueError:
                date_created = datetime.strptime(date_created, '%Y-%m-%d %H:%M:%S')
        dates.append(date_created.strftime('%Y-%m-%d'))
        titles.append(hw['title'])

        # Durchschnitt Prozent (MC)
        avg_mc = conn.execute(
            '''
            SELECT AVG(percent_correct) AS avg_percent
            FROM HomeworkResults
            WHERE homework_id = ?
            ''', (hw['id'],)
        ).fetchone()['avg_percent']

        # Durchschnitt Prozent (Open)
        avg_open = conn.execute(
            '''
            SELECT AVG(percent_correct) AS avg_percent
            FROM HomeworkOpenQuestionsResults
            WHERE homework_id = ?
            ''', (hw['id'],)
        ).fetchone()['avg_percent']

        # Kombiniere beide (nur die, die existieren)
        percent_values = [v for v in [avg_mc, avg_open] if v is not None]
        avg_percent = round(sum(percent_values) / len(percent_values), 2) if percent_values else 0
        avg_percent_corrects.append(avg_percent)

        # Durchschnitt Skill Level (MC)
        avg_skill_mc = conn.execute(
            '''
            SELECT AVG(new_class_skill_level) AS avg_skill
            FROM HomeworkResults
            WHERE homework_id = ?
            ''', (hw['id'],)
        ).fetchone()['avg_skill']

        # Durchschnitt Skill Level (Open)
        avg_skill_open = conn.execute(
            '''
            SELECT AVG(new_class_skill_level) AS avg_skill
            FROM HomeworkOpenQuestionsResults
            WHERE homework_id = ?
            ''', (hw['id'],)
        ).fetchone()['avg_skill']

        skill_values = [v for v in [avg_skill_mc, avg_skill_open] if v is not None]
        avg_skill = round(sum(skill_values) / len(skill_values), 2) if skill_values else 0
        avg_skill_levels.append(avg_skill)

    # Nur veröffentlichte Aufgaben zählen!
    published_homework = [hw for hw in homework_list if hw['status'] == 'published']
    published_team_challenges = [tc for tc in team_challenges if tc['status'] == 'published']
    total_tasks = len(published_homework) + len(published_team_challenges)

    # Dicts für alle Schüler
    total_homework_per_student = {}
    completed_homework_per_student = {}

    for s in students:
        student_id = s['id']
        # Erledigte MC-Aufgaben
        mc_done = conn.execute(
            '''
            SELECT COUNT(*) FROM HomeworkResults
            JOIN Homework ON HomeworkResults.homework_id = Homework.id
            WHERE Homework.class_id = ? AND HomeworkResults.student_id = ?
            ''', (class_id, student_id)
        ).fetchone()[0]
        # Erledigte Open Questions
        open_done = conn.execute(
            '''
            SELECT COUNT(*) FROM HomeworkOpenQuestionsResults
            JOIN Homework ON HomeworkOpenQuestionsResults.homework_id = Homework.id
            WHERE Homework.class_id = ? AND HomeworkOpenQuestionsResults.student_id = ?
            ''', (class_id, student_id)
        ).fetchone()[0]
        # Erledigte Team Challenges (MC + Open)
        team_mc_done = conn.execute(
            '''
            SELECT COUNT(*) FROM HomeworkResults
            JOIN Homework ON HomeworkResults.homework_id = Homework.id
            WHERE Homework.class_id = ? AND Homework.is_team_challenge = 1 AND HomeworkResults.student_id = ?
            ''', (class_id, student_id)
        ).fetchone()[0]
        team_open_done = conn.execute(
            '''
            SELECT COUNT(*) FROM HomeworkOpenQuestionsResults
            JOIN Homework ON HomeworkOpenQuestionsResults.homework_id = Homework.id
            WHERE Homework.class_id = ? AND Homework.is_team_challenge = 1 AND HomeworkOpenQuestionsResults.student_id = ?
            ''', (class_id, student_id)
        ).fetchone()[0]

        completed = mc_done + open_done + team_mc_done + team_open_done
        total_homework_per_student[student_id] = total_tasks
        completed_homework_per_student[student_id] = completed

        print 

    conn.close()

    return render_template(
        'class_details_teacher.html',
        class_info=class_info,
        students=students,
        teacher_id=teacher_id,
        homework_list=homework_list,
        team_challenges=team_challenges,
        dates=dates,
        titles=titles,
        avg_percent_corrects=avg_percent_corrects,  # <- das ist die richtige Liste!
        avg_skill_levels=avg_skill_levels,
        total_homework_per_student=total_homework_per_student,
        completed_homework_per_student=completed_homework_per_student
        )



@app.route('/delete_class', methods=['POST'])
def delete_class():
    if 'teacher_id' not in session:
        return redirect('/')

    # Debugging: Zeige die gesendeten Formular-Daten an
    print("Formulardaten:", request.form)

    class_id = request.form.get('class_id')

    if not class_id:
        return "Fehler: Ungültige Anfrage. class_id fehlt.", 400

    conn = get_db_connection()

    teacher_id = session['teacher_id']

    # Überprüfen, ob der Lehrer die Klasse unterrichtet
    class_info = conn.execute(
        'SELECT * FROM Classes WHERE id = ? AND teacher_id = ?',
        (class_id, teacher_id)
    ).fetchone()

    if not class_info:
        conn.close()
        return "Fehler: Die Klasse existiert nicht oder Sie haben keine Berechtigung, sie zu löschen.", 403

    # Lösche die Klasse und alle zugehörigen Einträge
    conn.execute('DELETE FROM ClassMembers WHERE class_id = ?', (class_id,))
    conn.execute('DELETE FROM Classes WHERE id = ?', (class_id,))
    conn.commit()
    conn.close()

    print(f"Kurs {class_id} wurde von Lehrer {teacher_id} gelöscht.")

    # Weiterleitung zurück zum Lehrer-Dashboard
    return redirect(url_for('teacher_dashboard'))


@app.route('/student_details/<int:student_id>/<int:class_id>/<int:teacher_id>')
def student_details(student_id, class_id, teacher_id):
    import json
    from datetime import datetime
    conn = get_db_connection()

    # Schüler- und Klasseninformationen abrufen
    student_info = conn.execute(
        '''
        SELECT Participants.id, Participants.name, Participants.email, Participants.skill_level,
               ClassMembers.class_skill_level
        FROM Participants
        JOIN ClassMembers ON Participants.id = ClassMembers.student_id
        WHERE Participants.id = ? AND ClassMembers.class_id = ?
        ''',
        (student_id, class_id)
    ).fetchone()

    if not student_info:
        conn.close()
        return "Fehler: Schüler existiert nicht oder ist nicht in dieser Klasse.", 404

    # MC
    mc_results = conn.execute(
        '''
        SELECT date_submitted, percent_correct, new_class_skill_level, Homework.title
        FROM HomeworkResults
        JOIN Homework ON HomeworkResults.homework_id = Homework.id
        WHERE HomeworkResults.student_id = ? AND Homework.class_id = ?
        ''', (student_id, class_id)
    ).fetchall()

    # Open
    open_results = conn.execute(
        '''
        SELECT date_submitted, percent_correct, new_class_skill_level, Homework.title
        FROM HomeworkOpenQuestionsResults
        JOIN Homework ON HomeworkOpenQuestionsResults.homework_id = Homework.id
        WHERE HomeworkOpenQuestionsResults.student_id = ? AND Homework.class_id = ?
        ''', (student_id, class_id)
    ).fetchall()

    # Kombiniere und sortiere nach Datum:
    all_results = list(mc_results) + list(open_results)
    all_results.sort(key=lambda r: r['date_submitted'])
    all_results.sort(key=get_sort_key)

    dates = []
    percent_corrects = []
    skill_levels = []
    titles = []

    for r in all_results:
        # Stelle sicher, dass nur das Datum (YYYY-MM-DD) verwendet wird
        date_val = r['date_submitted']
        if isinstance(date_val, str):
            date_val = date_val[:10]  # Nur die ersten 10 Zeichen (YYYY-MM-DD)
        elif isinstance(date_val, datetime):
            date_val = date_val.strftime('%Y-%m-%d')
        dates.append(date_val)
        percent = r['percent_correct']
        percent_corrects.append(round(percent, 2) if percent is not None else None)
        skill_levels.append(r['new_class_skill_level'])
        titles.append(r['title'])

    conn.close()

    return render_template(
        'student_details.html',
        student_info=student_info,
        class_id=class_id,
        teacher_id=teacher_id,
        dates=dates,
        titles=titles,
        percent_corrects=percent_corrects,
        skill_dates=dates,
        skill_levels=skill_levels
    )


### STUDENT ###


@app.route('/login_student', methods=['POST'])
def login_student():
    email = request.form.get('email')
    password = request.form.get('password')

    if not email or not password:
        return "Fehler: Bitte füllen Sie alle Felder aus.", 400

    conn = get_db_connection()
    student = conn.execute('SELECT * FROM Participants WHERE email = ? AND password = ?', (email, password)).fetchone()
    conn.close()

    if student:
        # Speichere nur die primitive ID (Integer) in der Session
        session['student_id'] = int(student['id'])
        return redirect(url_for('student_dashboard'))
    else:
        return "Anmeldedaten ungültig. Bitte versuchen Sie es erneut."


    

@app.route('/register_student', methods=['POST'])
def register_student():
    name = request.form['name']
    email = request.form['email']
    password = request.form['password']
    
    conn = get_db_connection()
    conn.execute(
        'INSERT INTO Participants (name, email, password) VALUES (?, ?, ?)',
        (name, email, password)
    )
    conn.commit()
    conn.close()
    
    return redirect('/')



@app.route('/student_dashboard')
def student_dashboard():
    if 'student_id' not in session:
        return redirect('/')

    student_id = session['student_id']
    conn = get_db_connection()

    # Schülerinformationen abrufen
    student = conn.execute('SELECT * FROM Participants WHERE id = ?', (student_id,)).fetchone()

    # Beigetretene Klassen abrufen
    joined_classes = conn.execute(
        '''
        SELECT Classes.*, Teachers.name AS teacher_name, ClassMembers.class_skill_level
        FROM Classes
        JOIN ClassMembers ON Classes.id = ClassMembers.class_id
        JOIN Teachers ON Classes.teacher_id = Teachers.id
        WHERE ClassMembers.student_id = ?
        ''',
        (student_id,)
    ).fetchall()

    # Nach dem Laden von student_id
    favorite_badges = conn.execute(
        '''
        SELECT Badges.* FROM UserFavoriteBadges
        JOIN Badges ON UserFavoriteBadges.badge_id = Badges.id
        WHERE UserFavoriteBadges.user_id = ?
        ORDER BY UserFavoriteBadges.position
        ''', (student_id,)
    ).fetchall()

    # Graphen vorbereiten (MC + Open Questions kombiniert für Skill-Level-Graph)
    dates = []
    titles = []
    skill_levels = []
    class_names = []

    # Hole alle Skill-Änderungen aus MC und Open Questions
    mc_skill_history = conn.execute(
        '''
        SELECT HomeworkResults.date_submitted, Homework.title, HomeworkResults.new_skill_level, Classes.class_name
        FROM HomeworkResults
        JOIN Homework ON HomeworkResults.homework_id = Homework.id
        JOIN Classes ON Homework.class_id = Classes.id
        WHERE HomeworkResults.student_id = ?
        ''',
        (student_id,)
    ).fetchall()

    open_skill_history = conn.execute(
        '''
        SELECT HomeworkOpenQuestionsResults.date_submitted, Homework.title, HomeworkOpenQuestionsResults.new_skill_level, Classes.class_name
        FROM HomeworkOpenQuestionsResults
        JOIN Homework ON HomeworkOpenQuestionsResults.homework_id = Homework.id
        JOIN Classes ON Homework.class_id = Classes.id
        WHERE HomeworkOpenQuestionsResults.student_id = ?
        ''',
        (student_id,)
    ).fetchall()

    # Kombiniere und sortiere nach Datum
    all_skill_history = list(mc_skill_history) + list(open_skill_history)
    all_skill_history.sort(key=lambda entry: entry['date_submitted'])
    all_results.sort(key=get_sort_key)

    for entry in all_skill_history:
        # Nur Datum (YYYY-MM-DD)
        date_val = entry['date_submitted']
        if isinstance(date_val, str):
            date_val = date_val[:10]
        elif isinstance(date_val, datetime):
            date_val = date_val.strftime('%Y-%m-%d')
        dates.append(date_val)
        titles.append(entry['title'])
        skill_levels.append(entry['new_skill_level'])
        class_names.append(entry['class_name'])

    all_classes = conn.execute('SELECT id, class_name FROM Classes').fetchall()
    all_classes_dict = [{'id': int(class_['id']), 'class_name': class_['class_name']} for class_ in all_classes]


    all_badges = conn.execute('SELECT * FROM Badges').fetchall()
    user_badge_ids = set([
        row['badge_id'] for row in conn.execute('SELECT badge_id FROM UserBadges WHERE user_id = ?', (student_id,))
    ])

    level = student['level']

    # Homework: MC + Open Questions
    hw_count = conn.execute('''
        SELECT
            (SELECT COUNT(*) FROM HomeworkResults WHERE student_id = ?)
        + (SELECT COUNT(*) FROM HomeworkOpenQuestionsResults WHERE student_id = ?)
    ''', (student_id, student_id)).fetchone()[0]

    # Retry: MC + Open Questions
    retry_count = conn.execute('''
        SELECT
            (SELECT COUNT(*) FROM HomeworkRetryResults WHERE student_id = ?)
        + (SELECT COUNT(*) FROM HomeworkRetryOpenResults WHERE student_id = ?)
    ''', (student_id, student_id)).fetchone()[0]

    # Team: MC + Open Questions, nur rechtzeitig abgegebene Team-Challenges
    team_success_count = conn.execute('''
        SELECT COUNT(*) FROM TeamChallenges
        WHERE TeamChallenges.success = 'success'
        AND (
            EXISTS (
                SELECT 1 FROM HomeworkResults
                WHERE HomeworkResults.homework_id = TeamChallenges.homework_id
                AND HomeworkResults.student_id = ?
                AND (
                        TeamChallenges.completed_at IS NULL
                        OR HomeworkResults.date_submitted <= TeamChallenges.completed_at
                    )
            )
            OR EXISTS (
                SELECT 1 FROM HomeworkOpenQuestionsResults
                WHERE HomeworkOpenQuestionsResults.homework_id = TeamChallenges.homework_id
                AND HomeworkOpenQuestionsResults.student_id = ?
                AND (
                        TeamChallenges.completed_at IS NULL
                        OR HomeworkOpenQuestionsResults.date_submitted <= TeamChallenges.completed_at
                    )
            )
        )
    ''', (student_id, student_id)).fetchone()[0]

    # Gruppiere Badges nach Kategorie
    from collections import defaultdict
    badges_by_cat = defaultdict(list)
    for badge in all_badges:
        badges_by_cat[badge['category']].append(badge)

    badge_progress = []
    for cat, badges in badges_by_cat.items():
        # Sortiere nach Threshold
        badges = sorted(badges, key=lambda b: b['threshold'])
        # Bestimme aktuellen Wert
        if cat == 'level':
            current = level
        elif cat == 'homework':
            current = hw_count
        elif cat == 'retry':
            current = retry_count
        elif cat == 'team':
            current = team_success_count
        else:
            current = 0
        # Finde den nächsten noch nicht erreichten Badge
        next_badge = None
        for badge in badges:
            achieved = badge['id'] in user_badge_ids
            badge_progress.append({
                "id": badge['id'],
                "name": badge['name'],
                "description": badge['description'],
                "category": badge['category'],
                "threshold": badge['threshold'],
                "current": current,
                "achieved": achieved,
                "is_next": False,
                "icon_url": badge['icon_url'] if 'icon_url' in badge.keys() else ''
            })
        # Markiere nur den nächsten noch nicht erreichten Badge für Fortschritt
        for badge in badges:
            if badge['id'] not in user_badge_ids:
                for b in badge_progress:
                    if b['id'] == badge['id']:
                        b['is_next'] = True
                break

    level_up = session.pop('level_up', None)
    new_badges = session.pop('new_badges', None)

    conn.close()

    thresholds = []
    needed = 25
    total = 0
    for _ in range(1, 30):
        total += needed
        thresholds.append(total)
        needed *= 2

    check_and_award_badges(student_id)

    return render_template(
        'student_dashboard.html',
        student=student,
        joined_classes=joined_classes,
        dates=dates,
        skill_levels=skill_levels,
        titles=titles,
        class_names=class_names,
        all_classes=all_classes_dict,
        favorite_badges=favorite_badges,
        badge_progress=badge_progress,
        new_badges=new_badges,
        thresholds=thresholds,
        level_up=level_up
    )



@app.route('/join_class', methods=['POST'])
def join_class():
    student_id = request.form['student_id']
    class_id = request.form['class_id']

    conn = get_db_connection()
    existing_member = conn.execute(
        'SELECT * FROM ClassMembers WHERE class_id = ? AND student_id = ?',
        (class_id, student_id)
    ).fetchone()

    if existing_member:
        conn.close()
        return "Sie sind bereits Mitglied dieser Klasse."
    
    # Gesamtskill-Level des Schülers abrufen
    skill_level = conn.execute(
        'SELECT skill_level FROM Participants WHERE id = ?',
        (student_id,)
    ).fetchone()['skill_level']

    # Schüler der Klasse hinzufügen und das Klassenskill-Level setzen
    conn.execute(
        '''
        INSERT INTO ClassMembers (class_id, student_id, class_skill_level)
        VALUES (?, ?, ?)
        ''',
        (class_id, student_id, skill_level)
    )

    conn.commit()
    conn.close()

    return redirect(url_for('class_details_student', class_id=class_id, student_id=student_id))


@app.route('/class_details_student/<int:class_id>/<int:student_id>')
def class_details_student(class_id, student_id):
    from datetime import datetime
    conn = get_db_connection()

    # Klasseninformationen abrufen
    class_info = conn.execute(
        '''
        SELECT Classes.id, Classes.class_name, Classes.subject, Teachers.name AS teacher_name
        FROM Classes
        JOIN Teachers ON Classes.teacher_id = Teachers.id
        WHERE Classes.id = ?
        ''', (class_id,)
    ).fetchone()

    # Schülerinformationen abrufen
    student = conn.execute(
        '''
        SELECT Participants.name, Participants.email, ClassMembers.class_skill_level
        FROM Participants
        JOIN ClassMembers ON Participants.id = ClassMembers.student_id
        WHERE Participants.id = ? AND ClassMembers.class_id = ?
        ''', (student_id, class_id)
    ).fetchone()

    # Alle Hausaufgaben abrufen
    homework_list = conn.execute(
        '''
        SELECT Homework.id, Homework.title, Homework.date_created,
            CASE 
                WHEN EXISTS (
                    SELECT 1 FROM HomeworkResults
                    WHERE HomeworkResults.homework_id = Homework.id
                    AND HomeworkResults.student_id = ?
                )
                OR EXISTS (
                    SELECT 1 FROM HomeworkOpenQuestionsResults
                    WHERE HomeworkOpenQuestionsResults.homework_id = Homework.id
                    AND HomeworkOpenQuestionsResults.student_id = ?
                )
                THEN 'Done'
                ELSE 'Open'
            END AS status
        FROM Homework
        WHERE Homework.class_id = ? AND Homework.is_team_challenge = 0 AND Homework.status = 'published'
        ''',
        (student_id, student_id, class_id)
    ).fetchall()

    team_challenges = conn.execute(
        '''
        SELECT Homework.id, Homework.title, Homework.date_created,
            TeamChallenges.goal_score, TeamChallenges.current_score,
            CASE 
                WHEN EXISTS (
                    SELECT 1 FROM HomeworkResults
                    WHERE HomeworkResults.homework_id = Homework.id
                    AND HomeworkResults.student_id = ?
                )
                OR EXISTS (
                    SELECT 1 FROM HomeworkOpenQuestionsResults
                    WHERE HomeworkOpenQuestionsResults.homework_id = Homework.id
                    AND HomeworkOpenQuestionsResults.student_id = ?
                )
                THEN 'Done'
                ELSE 'Open'
            END AS status
        FROM Homework
        JOIN TeamChallenges ON Homework.id = TeamChallenges.homework_id
        WHERE Homework.class_id = ? AND Homework.is_team_challenge = 1 AND Homework.status = 'published'
        ''',
        (student_id, student_id, class_id)
    ).fetchall()

    students_list = conn.execute(
        '''
        SELECT Participants.id, Participants.name, ClassMembers.class_skill_level
        FROM Participants
        JOIN ClassMembers ON Participants.id = ClassMembers.student_id
        WHERE ClassMembers.class_id = ?
        ''', (class_id,)
    ).fetchall()

    # Für alle Teilnehmer die Favoriten-Badges laden
    student_fav_badges = {}
    for s in students_list:
        favs = conn.execute(
            '''
            SELECT Badges.icon_url, Badges.name FROM UserFavoriteBadges
            JOIN Badges ON UserFavoriteBadges.badge_id = Badges.id
            WHERE UserFavoriteBadges.user_id = ?
            ORDER BY UserFavoriteBadges.position
            ''', (s['id'],)
        ).fetchall()
        student_fav_badges[s['id']] = favs

    # Progress calculation
    total_homework = len(homework_list) + len(team_challenges)
    completed_homework = sum(1 for hw in homework_list if hw['status'] == 'Done') + sum(1 for tc in team_challenges if tc['status'] == 'Done')

    # Daten für Graphen vorbereiten – MC + Open Questions kombiniert
    mc_results = conn.execute(
        '''
        SELECT date_submitted, percent_correct, new_class_skill_level, Homework.title
        FROM HomeworkResults
        JOIN Homework ON HomeworkResults.homework_id = Homework.id
        WHERE HomeworkResults.student_id = ? AND Homework.class_id = ?
        ''', (student_id, class_id)
    ).fetchall()

    open_results = conn.execute(
        '''
        SELECT date_submitted, percent_correct, new_class_skill_level, Homework.title
        FROM HomeworkOpenQuestionsResults
        JOIN Homework ON HomeworkOpenQuestionsResults.homework_id = Homework.id
        WHERE HomeworkOpenQuestionsResults.student_id = ? AND Homework.class_id = ?
        ''', (student_id, class_id)
    ).fetchall()

    all_results = list(mc_results) + list(open_results)
    all_results.sort(key=lambda r: r['date_submitted'])

    all_results.sort(key=get_sort_key)

    dates = []
    percent_corrects = []
    skill_levels = []
    titles = []

    for r in all_results:
        date_val = r['date_submitted']
        if isinstance(date_val, str):
            date_val = date_val[:10]
        elif isinstance(date_val, datetime):
            date_val = date_val.strftime('%Y-%m-%d')
        dates.append(date_val)
        percent = r['percent_correct']
        percent_corrects.append(round(percent, 2) if percent is not None else None)
        skill_levels.append(r['new_class_skill_level'])
        titles.append(r['title'])

    conn.close()

    return render_template(
        'class_details_student.html',
        class_info=class_info,
        student=student,
        student_id=student_id,
        homework_list=homework_list,
        team_challenges=team_challenges,
        students=students_list,
        student_fav_badges=student_fav_badges,
        total_homework=total_homework,
        completed_homework=completed_homework,
        dates=dates,
        percent_corrects=percent_corrects,
        skill_levels=skill_levels,
        titles=titles
    )

def get_sort_key(r):
    val = r['date_submitted']
    if isinstance(val, str):
        return val  # ISO-Format: lexikographisch sortierbar
    elif isinstance(val, datetime):
        return val.isoformat()
    return ""



@app.route('/leave_class', methods=['POST'])
def leave_class():
    if 'student_id' not in session:
        return redirect('/')

    student_id = session['student_id']
    class_id = request.form.get('class_id')

    if not class_id:
        return "Fehler: Ungültige Anfrage. class_id fehlt.", 400

    conn = get_db_connection()

    existing_member = conn.execute(
        'SELECT * FROM ClassMembers WHERE class_id = ? AND student_id = ?',
        (class_id, student_id)
    ).fetchone()

    if not existing_member:
        conn.close()
        return "Fehler: Sie sind kein Mitglied dieser Klasse.", 400

    conn.execute('DELETE FROM ClassMembers WHERE class_id = ? AND student_id = ?', (class_id, student_id))
    conn.commit()
    conn.close()

    return redirect(url_for('student_dashboard'))


### Aufgabenerstellung ###


@app.route('/create_homework', methods=['POST'])
def create_homework():
    import json
    from datetime import datetime

    api_key = os.getenv("CHATGPT_API_KEY")

    class_id = request.form['class_id']
    description = request.form['description']
    title = request.form['title']
    teacher_id = request.form['teacher_id']
    is_team_challenge = int(request.form.get('is_team_challenge', 0))
    start_time = request.form.get('start_time')
    end_time = request.form.get('end_time')
    goal_score = request.form.get('goal_score')

    # Hole Klasseninformationen aus der Datenbank
    conn = get_db_connection()
    class_info = conn.execute(
        'SELECT subject, grade_level FROM Classes WHERE id = ?',
        (class_id,)
    ).fetchone()

    # Generiere Hausaufgaben mit ChatGPT
    prompt = f"""
    Create homework for the subject {class_info['subject']} in the grade {class_info['grade_level']}:
    For reference, students have a skill_level between 1 and 10, with 10 being the best/most difficult.

    Homework description: {description}

    Based on Bloom's Taxonomy, the questions should be divided into the task types Remembering, Understanding, Applying, Analysing, Evaluating, Creating.
    1st level of difficulty (skill_level 1) 3 * Remembering, 3 * Understanding, 3 * Applying, 1 * Analysing
    2nd level of difficulty (skill_level 4) 2 * Remembering, 3 * Understanding, 3 * Applying, 2 * Analysing
    3rd level of difficulty (skill_level 8) 2 * Remembering, 2 * Understanding, 3 * Applying, 3 * Analysing
    The homework should only contain multiple-choice questions. 
    Each question should have four possible answers and the correct answer should be returned as an index (0-based).

    Create a total of 30 questions: 10 questions per difficulty level.
    Please answer only with JSON content in the following format:
    [
        {{"skill_level": 1, "questions": [
            {{"question": "...", "options": ["...", "...", "...", "..."], "answer": 0, "explanation": "...", "taxonomy": "..."}},
            {{"question": "...", "options": ["...", "...", "...", "..."], "answer": 1, "explanation": "...", "taxonomy": "..."}}
        ]}},
        {{"skill_level": 4, "questions": [
            {{"question": "...", "options": ["...", "...", "...", "..."], "answer": 2, "explanation": "...", "taxonomy": "..."}}
        ]}},
        {{"skill_level": 8, "questions": [
            {{"question": "...", "options": ["...", "...", "...", "..."], "answer": 3, "explanation": "...", "taxonomy": "..."}}
        ]}}
    ]
    """

    print("=== Prompt an ChatGPT ===")
    print(prompt)
    print("========================")

    # OpenAI API-Endpunkt und Header
    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }

    # Anfrage-Daten
    data = {
        "model": "gpt-4o",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7
    }

    try:
        # HTTP POST-Anfrage an die OpenAI API
        response = requests.post(url, headers=headers, json=data)

        # Antwort prüfen
        if response.status_code == 200:
            result = response.json()
            generated_content = result["choices"][0]["message"]["content"]

            # JSON aus der Antwort extrahieren
            try:
                json_start = generated_content.index('[')  # Suche den Beginn der JSON-Liste
                json_end = generated_content.rindex(']')  # Suche das Ende der JSON-Liste
                json_content = generated_content[json_start:json_end + 1]
                question_data = json.loads(json_content)  # JSON-Daten parsen
            except (ValueError, json.JSONDecodeError) as e:
                return f"Fehler beim Parsen der JSON-Antwort: {str(e)}", 500
        else:
            print(f"Fehler: {response.status_code} - {response.text}")
            return None
    

        cursor = conn.execute(
            'INSERT INTO Homework (class_id, description, title, date_created, is_team_challenge) VALUES (?, ?, ?, ?, ?)',
            (class_id, description, title, datetime.now().date(), is_team_challenge)
        )
        homework_id = cursor.lastrowid

        if is_team_challenge:
            conn.execute(
                'INSERT INTO TeamChallenges (homework_id, start_time, end_time, goal_score) VALUES (?, ?, ?, ?)',
                (homework_id, start_time, end_time, goal_score)
            )

        # Speichern der Fragen
        for question_set in question_data:
            skill_level = question_set["skill_level"]
            for question in question_set["questions"]:
                # Speichere die Optionen als einfache Liste im JSON-Format
                options = json.dumps(question["options"])
                conn.execute(
                    '''INSERT INTO HomeworkQuestions
                       (homework_id, skill_level, question, correct_answer, explanation, question_type, options, taxonomy)
                       VALUES (?, ?, ?, ?, ?, 'multiple_choice', ?, ?)''',
                    (homework_id, skill_level, question["question"], question["answer"], question["explanation"], options, question["taxonomy"])
                )

        conn.commit()
        conn.close()

    except Exception as e:
        return f"Ein Fehler ist aufgetreten: {str(e)}", 500

    return redirect(url_for('edit_homework', homework_id=homework_id, class_id=class_id, teacher_id=teacher_id))


@app.route('/create_learning_content', methods=['POST'])
def create_learning_content():
    data = request.get_json()
    content_type = data.get('type')

    if content_type == 'mc':
        title = data.get('title')
        description = data.get('desc')
        class_id = data.get('class_id')
        teacher_id = data.get('teacher_id')
        is_team_challenge = int(data.get('is_team_challenge', 0))
        start_time = data.get('start_time')
        end_time = data.get('end_time')
        goal_score = data.get('goal_score')

        # Simuliere ein POST-Formular für create_homework
        form_data = MultiDict([
            ('class_id', class_id),
            ('description', description),
            ('title', title),
            ('teacher_id', teacher_id),
            ('is_team_challenge', is_team_challenge),
            ('start_time', start_time),
            ('end_time', end_time),
            ('goal_score', goal_score)
        ])
        old_form = request.form
        request.form = form_data
        try:
            result = create_homework()
        finally:
            request.form = old_form

        # Wenn create_homework ein Redirect ist, extrahiere die Ziel-URL
        if hasattr(result, 'location'):
            return jsonify({"redirect_url": result.location})
        return jsonify({"message": "Multiple Choice content created."})

    elif content_type == 'open':
        title = data.get('title')
        description = data.get('desc')
        class_id = data.get('class_id')
        teacher_id = data.get('teacher_id')
        is_team_challenge = int(data.get('is_team_challenge', 0))
        start_time = data.get('start_time')
        end_time = data.get('end_time')
        goal_score = data.get('goal_score')

        conn = get_db_connection()
        class_info = conn.execute(
            'SELECT subject, grade_level FROM Classes WHERE id = ?',
            (class_id,)
        ).fetchone()

        # Prompt für Open Questions nach Bloom
        prompt = f"""
    Create open-ended homework for the subject {class_info['subject']} in the grade {class_info['grade_level']}:
    For reference, students have a skill_level between 1 and 10, with 10 being the best/most difficult.

    Homework description: {description}

    Based on Bloom's Taxonomy, the questions should be divided into the task types Remembering, Understanding, Applying, Analysing, Evaluating, Creating.
    For each of the following skill levels, generate 6 open-ended questions (one for each taxonomy type):
    - skill_level 1 (easy): Remembering, Understanding, Applying, Analysing, Evaluating, Creating
    - skill_level 4 (medium): Remembering, Understanding, Applying, Analysing, Evaluating, Creating
    - skill_level 8 (hard): Remembering, Understanding, Applying, Analysing, Evaluating, Creating

    For each question, also generate a sample solution (model answer) that would be considered a very good answer for a student.
    Please answer only with JSON content in the following format:
    [
        {{"skill_level": 1, "questions": [
            {{"question": "...", "sample_solution": "...", "taxonomy": "Remembering"}},
            ... (total 6 questions, one per taxonomy)
        ]}},
        {{"skill_level": 4, "questions": [
            ... (6 questions)
        ]}},
        {{"skill_level": 8, "questions": [
            ... (6 questions)
        ]}}
    ]
    """
        print("=== Prompt an ChatGPT ===")
        print(prompt)
        print("========================")
        # OpenAI API-Aufruf (wie bei MC)
        api_key = os.getenv("CHATGPT_API_KEY")
        url = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }
        data_api = {
            "model": "gpt-4o",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.7
        }

        try:
            response = requests.post(url, headers=headers, json=data_api)
            if response.status_code == 200:
                result = response.json()
                generated_content = result["choices"][0]["message"]["content"]
                try:
                    json_start = generated_content.index('[')
                    json_end = generated_content.rindex(']')
                    json_content = generated_content[json_start:json_end + 1]
                    open_questions = json.loads(json_content)
                except (ValueError, json.JSONDecodeError) as e:
                    conn.close()
                    return {"message": f"Fehler beim Parsen der JSON-Antwort: {str(e)}"}, 500
            else:
                conn.close()
                return {"message": f"Fehler: {response.status_code} - {response.text}"}, 500

            # Speichere die Aufgabe in Homework (jetzt mit is_team_challenge)
            cursor = conn.execute(
                'INSERT INTO Homework (class_id, description, title, date_created, status, is_team_challenge) VALUES (?, ?, ?, ?, ?, ?)',
                (class_id, description, title, datetime.now().date(), 'draft', is_team_challenge)
            )
            homework_id = cursor.lastrowid

            # Team Challenge ggf. speichern
            if is_team_challenge:
                conn.execute(
                    'INSERT INTO TeamChallenges (homework_id, start_time, end_time, goal_score) VALUES (?, ?, ?, ?)',
                    (homework_id, start_time, end_time, goal_score)
                )

            # Speichere die Open Questions
            for question_set in open_questions:
                skill_level = question_set.get("skill_level")
                for q in question_set.get("questions", []):
                    conn.execute(
                        '''INSERT INTO HomeworkOpenQuestions
                        (homework_id, skill_level, question, sample_solution, taxonomy)
                        VALUES (?, ?, ?, ?, ?)''',
                        (homework_id, skill_level, q["question"], q["sample_solution"], q["taxonomy"])
                    )

            conn.commit()
            conn.close()
            # Gib die Edit-URL zurück (wie bei MC)
            edit_url = url_for('edit_homework', homework_id=homework_id, class_id=class_id, teacher_id=teacher_id)
            return jsonify({"redirect_url": edit_url})

        except Exception as e:
            conn.close()
            return {"message": f"Ein Fehler ist aufgetreten: {str(e)}"}, 500
            
    elif content_type == 'essay':
        return {"message": "Essay task created."}
    else:
        return {"message": "Unknown content type."}, 400

@app.route('/homework/<int:homework_id>/<int:student_id>')
def view_homework_student(homework_id, student_id):
    import json
    conn = get_db_connection()

    # Abrufen der Klasseninformationen
    class_info = conn.execute(
        'SELECT Classes.id, Classes.class_name, Classes.subject, Teachers.name AS teacher_name '
        'FROM Classes '
        'JOIN Teachers ON Classes.teacher_id = Teachers.id '
        'JOIN Homework ON Classes.id = Homework.class_id '
        'WHERE Homework.id = ?', (homework_id,)
    ).fetchone()

    if not class_info:
        conn.close()
        return "Fehler: Diese Klasse existiert nicht.", 404

    # Überprüfen, ob die Hausaufgabe bereits eingereicht wurde
    homework_status = conn.execute(
        '''
        SELECT 
            CASE 
                WHEN mc.date_submitted IS NOT NULL OR openq.date_submitted IS NOT NULL THEN 'Done'
                ELSE 'Open'
            END AS status,
            mc.selected_answers,
            openq.feedback_json
        FROM Homework
        LEFT JOIN HomeworkResults mc ON Homework.id = mc.homework_id AND mc.student_id = ?
        LEFT JOIN HomeworkOpenQuestionsResults openq ON Homework.id = openq.homework_id AND openq.student_id = ?
        WHERE Homework.id = ?
        ''', (student_id, student_id, homework_id)
    ).fetchone()

    selected_answers = {}
    mc_feedback_summary = ""
    mc_feedback_recommendation = ""
    mc_correct_count = 0
    mc_incorrect_count = 0

    if homework_status and homework_status['status'] == "Done":
        result = conn.execute(
            'SELECT mc_feedback_summary, mc_feedback_recommendation, correct_count, incorrect_count FROM HomeworkResults WHERE homework_id = ? AND student_id = ? ORDER BY date_submitted DESC LIMIT 1',
            (homework_id, student_id)
        ).fetchone()
        if result:
            mc_feedback_summary = result['mc_feedback_summary'] or ""
            mc_feedback_recommendation = result['mc_feedback_recommendation'] or ""
            mc_correct_count = result['correct_count'] or 0
            mc_incorrect_count = result['incorrect_count'] or 0

        if homework_status and homework_status['selected_answers']:
            try:
                selected_answers = json.loads(homework_status['selected_answers'])
            except Exception:
                selected_answers = {}

    # Hausaufgabe abrufen
    homework = conn.execute(
        'SELECT id, title, description, date_created, class_id FROM Homework WHERE id = ?',
        (homework_id,)
    ).fetchone()

    # Hole die class_id der aktuellen Hausaufgabe
    class_id = homework['class_id']

    # Hole den Skill-Level für diese Klasse
    student = conn.execute(
        'SELECT class_skill_level FROM ClassMembers WHERE student_id = ? AND class_id = ?',
        (student_id, class_id)
    ).fetchone()
    student_skill_level = student['class_skill_level'] if student else 0

    # Nach dem Abrufen von student_skill_level
    class_skill_level = student_skill_level if student_skill_level else None

    print(f"Student Skill Level: {student_skill_level}")

    # Wenn Hausaufgabe schon bearbeitet wurde, nimm das gespeicherte Skill-Level
    answered_skill_level = None
    if homework_status and homework_status['status'] == "Done":
        # Versuche zuerst, das Skill-Level aus OpenQuestionsResults zu holen
        result = conn.execute(
            'SELECT answered_skill_level FROM HomeworkOpenQuestionsResults WHERE homework_id = ? AND student_id = ? ORDER BY date_submitted DESC LIMIT 1',
            (homework_id, student_id)
        ).fetchone()
        # Falls dort nichts steht, nimm das aus HomeworkResults (MC)
        if not result or result['answered_skill_level'] is None:
            result = conn.execute(
                'SELECT answered_skill_level FROM HomeworkResults WHERE homework_id = ? AND student_id = ? ORDER BY date_submitted DESC LIMIT 1',
                (homework_id, student_id)
            ).fetchone()
        if result and result['answered_skill_level'] is not None:
            answered_skill_level = result['answered_skill_level']

    if answered_skill_level is not None:
        student_skill_level = answered_skill_level

    print(f"Answered Skill Level: {answered_skill_level}")

    if student_skill_level <= 3:
        skill_level = 1
    elif student_skill_level <= 7:
        skill_level = 4
    else:
        skill_level = 8

    print(f"Skill Level: {skill_level}")

    # Open Questions für das Skill Level laden
    open_questions = conn.execute(
        'SELECT id, question, sample_solution, taxonomy, skill_level FROM HomeworkOpenQuestions WHERE homework_id = ? AND skill_level = ?',
        (homework_id, skill_level)
    ).fetchall()

    if not homework:
        conn.close()
        return "Fehler: Diese Hausaufgabe existiert nicht.", 404

    goal_score = None
    current_score = None
    team_challenge = conn.execute(
        'SELECT goal_score, current_score FROM TeamChallenges WHERE homework_id = ?', (homework_id,)
    ).fetchone()
    if team_challenge:
        goal_score = team_challenge['goal_score']
        current_score = team_challenge['current_score']

    # Fragen basierend auf Skill-Level abrufen
    question_data = conn.execute(
        'SELECT question, correct_answer, explanation, options, taxonomy, skill_level FROM HomeworkQuestions WHERE homework_id = ? AND skill_level = ?',
        (homework_id, skill_level)
    ).fetchall()

    questions = []
    correct_answers = {}
    explanations = {}

    for idx, row in enumerate(question_data):
        question = dict(row)
        question['options'] = [{'index': i, 'option': opt} for i, opt in enumerate(json.loads(question['options']))]
        questions.append({'index': idx, **question})
        correct_answers[idx] = question['correct_answer']
        explanations[idx] = question['explanation']

    # Retry-Homeworks abrufen
    retry_tasks = conn.execute(
        '''SELECT id, generated_questions, date_created, retry_count, 
                  json_extract(generated_questions, '$[0].question') as title
           FROM HomeworkRetries
           WHERE homework_id = ? AND student_id = ?
           ORDER BY date_created DESC''',
        (homework_id, student_id)
    ).fetchall()

    retry_list = []
    for retry in retry_tasks:
        retry_list.append({
            'id': retry['id'],
            'title': f"Retry {retry['retry_count']} - {retry['date_created'][:16].replace('T', ' ')}",
            'date_created': retry['date_created'][:16].replace('T', ' '),
        })

    # Lade Open-Question-Feedback, falls vorhanden
    oq_result = conn.execute(
        'SELECT feedback_json, correct_count, wrong_count, summary, recommendation FROM HomeworkOpenQuestionsResults WHERE homework_id = ? AND student_id = ?',
        (homework_id, student_id)
    ).fetchone()
    openq_feedback = None
    if oq_result:
        openq_feedback = {
            "feedback": json.loads(oq_result["feedback_json"]),
            "correct_count": oq_result["correct_count"],
            "wrong_count": oq_result["wrong_count"],
            "summary": oq_result["summary"],
            "recommendation": oq_result["recommendation"]
        }
    else:
        openq_feedback = None
    openq_answers = {}
    openq_answers_rows = conn.execute(
        'SELECT open_question_id, answer FROM HomeworkOpenAnswers WHERE homework_id = ? AND student_id = ?',
        (homework_id, student_id)
    ).fetchall()
    for row in openq_answers_rows:
        openq_answers[str(row['open_question_id'])] = row['answer']
    conn.close()

    print("DEBUG: homework_id", homework_id, "skill_level", skill_level, "len(question_data)", len(question_data))

    return render_template(
        'view_homework_student.html',
        homework=homework,
        questions=questions,
        class_info=class_info,
        student_id=student_id,
        correct_answers=correct_answers,
        explanations=explanations,
        homework_status=homework_status['status'],
        selected_answers=selected_answers,
        class_skill_level=class_skill_level,
        open_questions=open_questions,
        retry_tasks=retry_list,
        goal_score=goal_score,
        current_score=current_score,
        openq_answers=openq_answers,
        openq_feedback=openq_feedback,
        mc_correct_count=mc_correct_count,
        mc_incorrect_count=mc_incorrect_count,
        mc_feedback_summary=mc_feedback_summary,
        mc_feedback_recommendation=mc_feedback_recommendation
    )

@app.route('/retry_homework_view/<int:retry_id>/<int:student_id>')
def retry_homework_view(retry_id, student_id):
    conn = get_db_connection()
    retry = conn.execute('SELECT * FROM HomeworkRetries WHERE id = ?', (retry_id,)).fetchone()
    if not retry:
        conn.close()
        return "Retry homework not found", 404

    retry_type = retry['retry_type'] if 'retry_type' in retry.keys() else 'mc'

    if retry_type == 'open':
        # Open-Question-Retry
        question_data = conn.execute(
            'SELECT * FROM HomeworkRetryOpenQuestions WHERE retry_id = ?', (retry_id,)
        ).fetchall()
        questions = [dict(row) for row in question_data]

        # Lade bereits gespeicherte Antworten
        answers_rows = conn.execute(
            'SELECT open_question_id, answer FROM HomeworkRetryOpenAnswers WHERE retry_id = ? AND student_id = ?',
            (retry_id, student_id)
        ).fetchall()
        openq_answers = {str(row['open_question_id']): row['answer'] for row in answers_rows}

        # Lade Feedback, falls vorhanden
        oq_result = conn.execute(
            'SELECT feedback_json, correct_count, wrong_count, summary, recommendation FROM HomeworkRetryOpenResults WHERE retry_id = ? AND student_id = ?',
            (retry_id, student_id)
        ).fetchone()
        openq_feedback = None
        if oq_result:
            openq_feedback = {
                "feedback": json.loads(oq_result["feedback_json"]),
                "correct_count": oq_result["correct_count"],
                "wrong_count": oq_result["wrong_count"],
                "summary": oq_result["summary"],
                "recommendation": oq_result["recommendation"]
            }

        conn.close()
        return render_template(
            'view_retry_open_homework.html',
            retry=retry,
            questions=questions,
            student_id=student_id,
            openq_answers=openq_answers,
            openq_feedback=openq_feedback
        )
    elif retry_type == 'mc':
        question_data = conn.execute(
            'SELECT * FROM HomeworkRetryQuestions WHERE retry_id = ?', (retry_id,)
        ).fetchall()
        questions = []
        for idx, row in enumerate(question_data):
            question = dict(row)
            question['options'] = [{'index': i, 'option': opt} for i, opt in enumerate(json.loads(question['options']))]
            questions.append({'index': idx, **question})

        result = conn.execute(
            'SELECT selected_answers, mc_feedback_summary, mc_feedback_recommendation, correct_count, incorrect_count FROM HomeworkRetryResults WHERE retry_id = ? AND student_id = ?',
            (retry_id, student_id)
        ).fetchone()
        selected_answers = json.loads(result['selected_answers']) if result and result['selected_answers'] else {}

        mc_feedback_summary = result['mc_feedback_summary'] if result else ""
        mc_feedback_recommendation = result['mc_feedback_recommendation'] if result else ""
        mc_correct_count = result['correct_count'] if result else 0
        mc_incorrect_count = result['incorrect_count'] if result else 0

        conn.close()
        return render_template(
            'view_retry_homework.html',
            retry=retry,
            questions=questions,
            student_id=student_id,
            selected_answers=selected_answers,
            mc_feedback_summary=mc_feedback_summary,
            mc_feedback_recommendation=mc_feedback_recommendation,
            mc_correct_count=mc_correct_count,
            mc_incorrect_count=mc_incorrect_count
        )
    else:
        conn.close()
        return "Unsupported retry type", 400


@app.route('/view_homework_teacher/<int:homework_id>/<int:class_id>/<int:teacher_id>')
def view_homework_teacher(homework_id, class_id, teacher_id):
    import json
    conn = get_db_connection()

    # Hausaufgabendetails
    homework = conn.execute(
        'SELECT id, title, description, date_created FROM Homework WHERE id = ?',
        (homework_id,)
    ).fetchone()
    if not homework:
        conn.close()
        return "Error: Homework not found", 404

    # Fragen laden
    question_data = conn.execute(
        'SELECT id, question, correct_answer, explanation, options, taxonomy, skill_level FROM HomeworkQuestions WHERE homework_id = ?',
        (homework_id,)
    ).fetchall()

    questions = []
    correct_answers = {}
    explanations = {}

    # Gruppiere Fragen nach Skill-Level für Index-Berechnung
    questions_by_skill = {1: [], 4: [], 8: []}
    for row in question_data:
        questions_by_skill[row['skill_level']].append(row)

    # Baue Fragenliste für das Template
    for idx, row in enumerate(question_data):
        question = dict(row)
        question['options'] = [{'index': i, 'option': opt} for i, opt in enumerate(json.loads(question['options']))]
        question['id'] = row['id']
        questions.append({'index': idx, **question})
        correct_answers[idx] = int(question['correct_answer'])
        explanations[idx] = question['explanation']

    open_questions = conn.execute(
        'SELECT id, question, sample_solution, taxonomy, skill_level FROM HomeworkOpenQuestions WHERE homework_id = ?',
        (homework_id,)
    ).fetchall()

    # --- NEU: Ergebnisse aus beiden Tabellen (MC + Open) kombinieren ---
    mc_results = conn.execute(
        'SELECT student_id, answered_skill_level FROM HomeworkResults WHERE homework_id = ?', (homework_id,)
    ).fetchall()
    openq_results = conn.execute(
        'SELECT student_id, answered_skill_level FROM HomeworkOpenQuestionsResults WHERE homework_id = ?', (homework_id,)
    ).fetchall()

    all_results = { (r['student_id'], r['answered_skill_level']) for r in mc_results }
    all_results.update({ (r['student_id'], r['answered_skill_level']) for r in openq_results })

    done_skill_1 = len([r for r in all_results if r[1] is not None and r[1] <= 3])
    done_skill_4 = len([r for r in all_results if r[1] is not None and 4 <= r[1] <= 7])
    done_skill_8 = len([r for r in all_results if r[1] is not None and r[1] >= 8])
    num_done = len(all_results)

    # Alle Schüler der Klasse für Gesamtzahl pro Gruppe
    students = conn.execute(
        'SELECT id, class_skill_level FROM ClassMembers WHERE class_id = ?', (class_id,)
    ).fetchall()
    students_skill_1 = [s for s in students if s['class_skill_level'] is not None and s['class_skill_level'] <= 3]
    students_skill_4 = [s for s in students if s['class_skill_level'] is not None and 4 <= s['class_skill_level'] <= 7]
    students_skill_8 = [s for s in students if s['class_skill_level'] is not None and s['class_skill_level'] >= 8]

    total_skill_1 = len(students_skill_1)
    total_skill_4 = len(students_skill_4)
    total_skill_8 = len(students_skill_8)

    # Gruppiere Fragen nach Skill-Level für Index-Berechnung
    questions_by_skill = {1: [], 4: [], 8: []}
    for row in question_data:
        questions_by_skill[row['skill_level']].append(row)
    for k in questions_by_skill:
        questions_by_skill[k].sort(key=lambda q: q['id'])

    question_stats = []
    for row in question_data:
        q_id = row['id']
        skill_level = row['skill_level']
        group_questions = questions_by_skill[skill_level]
        group_idx = group_questions.index(row)

        # Zähle alle Ergebnisse, bei denen answered_skill_level zur Gruppe passt und selected_answers[group_idx] existiert
        answered = 0
        correct = 0
        results = conn.execute(
            'SELECT selected_answers FROM HomeworkResults WHERE homework_id = ? AND answered_skill_level >= ? AND answered_skill_level <= ?',
            (
                homework_id,
                skill_level if skill_level == 8 else (1 if skill_level == 1 else 4),
                skill_level if skill_level == 8 else (3 if skill_level == 1 else 7)
            )
        ).fetchall()
        for res in results:
            try:
                answers = json.loads(res['selected_answers'])
                if str(group_idx) in answers:
                    answered += 1
                    correct_answer = conn.execute(
                        'SELECT correct_answer FROM HomeworkQuestions WHERE id = ?', (q_id,)
                    ).fetchone()[0]
                    if str(answers[str(group_idx)]) == str(correct_answer):
                        correct += 1
            except Exception:
                pass

        wrong = answered - correct
        percent_correct = int((correct / answered) * 100) if answered > 0 else 0
        percent_wrong = 100 - percent_correct if answered > 0 else 0
        question_stats.append({
            "question_id": q_id,
            "answered": answered,
            "correct": correct,
            "wrong": wrong,
            "percent_correct": percent_correct,
            "percent_wrong": percent_wrong
        })

    openq_stats_rows = conn.execute(
        'SELECT id, question, skill_level FROM HomeworkOpenQuestions WHERE homework_id = ?', (homework_id,)
    ).fetchall()

    # Gruppiere nach Skill-Level und sortiere
    openq_by_skill = {1: [], 4: [], 8: []}
    for row in openq_stats_rows:
        openq_by_skill[row['skill_level']].append(row)
    for k in openq_by_skill:
        openq_by_skill[k].sort(key=lambda q: q['id'])

    # Lade alle Results für diese Hausaufgabe
    results = conn.execute(
        'SELECT feedback_json FROM HomeworkOpenQuestionsResults WHERE homework_id = ?',
        (homework_id,)
    ).fetchall()

    for row in openq_stats_rows:
        oq_id = str(row['id'])
        answered = 0
        correct = 0
        for res in results:
            feedback = json.loads(res['feedback_json'])
            if oq_id in feedback:
                answered += 1
                if feedback[oq_id].get("is_correct") is True:
                    correct += 1

        wrong = answered - correct
        percent_correct = int((correct / answered) * 100) if answered > 0 else 0
        percent_wrong = 100 - percent_correct if answered > 0 else 0
        question_stats.append({
            "question_id": int(oq_id),
            "answered": answered,
            "correct": correct,
            "wrong": wrong,
            "percent_correct": percent_correct,
            "percent_wrong": percent_wrong
        })

    conn.close()

    return render_template(
        'view_homework_teacher.html',
        homework=homework,
        questions=questions,
        class_info={'id': class_id},
        teacher_id=teacher_id,
        correct_answers=correct_answers,
        explanations=explanations,
        question_stats=question_stats,
        open_questions=open_questions,
        num_done=num_done,
        total_students=total_skill_1 + total_skill_4 + total_skill_8,
        done_skill_1=done_skill_1,
        done_skill_4=done_skill_4,
        done_skill_8=done_skill_8,
        total_skill_1=total_skill_1,
        total_skill_4=total_skill_4,
        total_skill_8=total_skill_8,
    )

    return render_template(
        'view_homework_teacher.html',
        homework=homework,
        questions=questions,
        class_info={'id': class_id},
        teacher_id=teacher_id,
        correct_answers=correct_answers,
        explanations=explanations,
        question_stats=question_stats,
        open_questions=open_questions,
        num_done=num_done,
        total_students=total_skill_1 + total_skill_4 + total_skill_8,
        done_skill_1=done_skill_1,
        done_skill_4=done_skill_4,
        done_skill_8=done_skill_8,
        total_skill_1=total_skill_1,
        total_skill_4=total_skill_4,
        total_skill_8=total_skill_8,
    )


@app.route('/delete_homework', methods=['POST'])
def delete_homework():
    homework_id = request.form.get('homework_id')
    class_id = request.form.get('class_id')
    teacher_id = request.form.get('teacher_id')
    
    if not homework_id or not class_id or not teacher_id:
        # Fehlerbehandlung, falls ein erwartetes Feld fehlt
        return "Fehlende Parameter. Operation konnte nicht abgeschlossen werden.", 400

    conn = get_db_connection()
    conn.execute('DELETE FROM Homework WHERE id = ?', (homework_id,))
    conn.commit()
    conn.close()

    return redirect(url_for('class_details_teacher', class_id=class_id, teacher_id=teacher_id))


@app.route('/submit_homework', methods=['POST'])
def submit_homework():
    from datetime import datetime
    import json
    conn = get_db_connection()

    # JSON-Daten aus der Anfrage holen
    data = request.get_json()
    homework_id = data.get('homework_id')
    student_id = data.get('student_id')
    correct_count = int(data.get('correct_count'))
    incorrect_count = int(data.get('incorrect_count'))
    selected_answers = data.get('selected_answers', {})

    # Datum der Abgabe erfassen
    date_submitted = datetime.now()

    try:
        # 1. Anpassung des Class Skill Levels
        class_skill_level = conn.execute(
            '''
            SELECT class_skill_level FROM ClassMembers
            WHERE student_id = ? AND class_id = (
                SELECT class_id FROM Homework WHERE id = ?
            )
            ''',
            (student_id, homework_id)
        ).fetchone()['class_skill_level']

        old_class_skill_level = class_skill_level

        if old_class_skill_level <= 3:
            q_skill_level = 1
        elif old_class_skill_level <= 7:
            q_skill_level = 4
        else:
            q_skill_level = 8

        # Neue Bewertung basierend auf der Leistung
        if correct_count > 7:
            class_skill_level = min(10, class_skill_level + 1)
        elif correct_count < 4:
            class_skill_level = max(1, class_skill_level - 1)

        # Aktualisieren des Class Skill Levels
        conn.execute(
            '''
            UPDATE ClassMembers
            SET class_skill_level = ?
            WHERE student_id = ? AND class_id = (
                SELECT class_id FROM Homework WHERE id = ?
            )
            ''',
            (class_skill_level, student_id, homework_id)
        )

        # 2. Berechnung des Gesamt-Skill-Levels
        avg_class_skill = conn.execute(
            '''
            SELECT ROUND(AVG(class_skill_level), 0) as avg_skill
            FROM ClassMembers
            WHERE student_id = ?
            ''',
            (student_id,)
        ).fetchone()['avg_skill']

        # Gesamt-Skill-Level aktualisieren
        conn.execute(
            '''
            UPDATE Participants
            SET skill_level = ?
            WHERE id = ?
            ''',
            (avg_class_skill, student_id)
        )

        # 3. MC-Feedback generieren (KI)
        # Hole alle Fragen und richtige Antworten
        questions = conn.execute(
            'SELECT question, options, correct_answer, explanation, taxonomy FROM HomeworkQuestions WHERE homework_id = ? AND skill_level = ?',
            (homework_id, q_skill_level)
        ).fetchall()

        print(f"DEBUG: homework_id {homework_id}, old_class_skill_level {old_class_skill_level}, len(questions) {len(questions)}")

        questions_for_gpt = []
        for idx, q in enumerate(questions):
            options = json.loads(q['options'])
            questions_for_gpt.append({
                "question": q['question'],
                "options": options,
                "correct_answer": q['correct_answer'],
                "student_answer": selected_answers.get(str(idx)),
                "explanation": q['explanation'],
                "taxonomy": q['taxonomy']
            })

        # Prompt für KI
        class_info = conn.execute(
            'SELECT subject, grade_level FROM Classes WHERE id = (SELECT class_id FROM Homework WHERE id = ?)', (homework_id,)
        ).fetchone()
        subject = class_info['subject'] if class_info else ''
        grade_level = class_info['grade_level'] if class_info else ''

        prompt = f"""
You are an educational assistant. Please analyze the following multiple-choice homework results for a student.

- Give a short, motivating summary of the student's performance.
- Based on the number and type of mistakes, recommend a learning path: Should the student retry with more multiple-choice questions, switch to open questions, or review the material first?
- Give concrete, actionable advice for improvement.
- Formulate your answer as if you were the student's sidekick. Talk directly to them.
- A answere is correct if correct_answer and student_answer are the same, for example "correct_answer": 0,"student_answer": 0,

Homework info:
- Subject: {subject}
- Grade: {grade_level}

Questions and answers:
{json.dumps(questions_for_gpt, ensure_ascii=False, indent=2)}

Please answer in JSON:
{{
  "summary": "...",
  "recommendation": "..."
}}
"""

        print("=== Prompt an ChatGPT ===")
        print(prompt)
        print("========================")

        # KI-Call
        api_key = os.getenv("CHATGPT_API_KEY")
        url = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }
        data_api = {
            "model": "gpt-4o",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.7
        }

        try:
            response = requests.post(url, headers=headers, json=data_api)
            if response.status_code == 200:
                result = response.json()
                generated_content = result["choices"][0]["message"]["content"]
                try:
                    json_start = generated_content.index('{')
                    json_end = generated_content.rindex('}')
                    json_content = generated_content[json_start:json_end + 1]
                    gpt_json = json.loads(json_content)
                    mc_feedback_summary = gpt_json.get("summary", "")
                    mc_feedback_recommendation = gpt_json.get("recommendation", "")
                except Exception as e:
                    mc_feedback_summary = "No summary available."
                    mc_feedback_recommendation = ""
            else:
                mc_feedback_summary = "No summary available."
                mc_feedback_recommendation = ""
        except Exception as e:
            mc_feedback_summary = "No summary available."
            mc_feedback_recommendation = ""

        # Nach dem Zählen von correct_count und incorrect_count:
        total = correct_count + incorrect_count
        percent_correct = (correct_count / total) * 100 if total > 0 else 0


        # Ergebnis speichern mit neuem Skill-Level, selected_answers und Feedback
        conn.execute(
            '''
            INSERT INTO HomeworkResults (homework_id, student_id, correct_count, 
                                         incorrect_count, date_submitted, 
                                         new_class_skill_level, new_skill_level, selected_answers,
                                         mc_feedback_summary, mc_feedback_recommendation, answered_skill_level, percent_correct)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''',
            (homework_id, student_id, correct_count, incorrect_count, date_submitted,
             class_skill_level, avg_class_skill, json.dumps(selected_answers),
             mc_feedback_summary, mc_feedback_recommendation, old_class_skill_level, percent_correct)
        )

         # Team-Punkte gutschreiben, falls TeamChallenge
        team_challenge = conn.execute(
            'SELECT id FROM TeamChallenges WHERE homework_id = ?', (homework_id,)
        ).fetchone()

        conn.commit()
        conn.close()

        add_points_and_check_level(student_id, correct_count * 2, allow_bonus=True)
        if team_challenge:
            add_points_to_team(homework_id, student_id, correct_count * 2, allow_bonus=True)
        check_and_award_badges(student_id)
        # Erfolgsmeldung mit neuem Skill Level
        return jsonify({
            "message": "Results successfully saved",
            "correct_count": correct_count,
            "class_skill_level": class_skill_level,
            "overall_skill_level": avg_class_skill
        }), 200

    except Exception as e:
        return jsonify({"message": f"Ein Fehler ist aufgetreten: {str(e)}"}), 500

@app.route('/check_open_questions', methods=['POST'])
def check_open_questions():
    import openai
    import json
    from datetime import datetime

    data = request.get_json()
    homework_id = data['homework_id']
    student_id = data['student_id']
    answers = data['answers']

    conn = get_db_connection()

    for oq_id, answer in answers.items():
        conn.execute(
            '''
            INSERT INTO HomeworkOpenAnswers (homework_id, student_id, open_question_id, answer, date_submitted)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(homework_id, student_id, open_question_id)
            DO UPDATE SET answer=excluded.answer, date_submitted=excluded.date_submitted
            ''',
            (homework_id, student_id, oq_id, answer, datetime.now().isoformat())
        )

    homework = conn.execute('SELECT * FROM Homework WHERE id = ?', (homework_id,)).fetchone()
    class_info = conn.execute(
        'SELECT subject, grade_level FROM Classes WHERE id = ?',
        (homework['class_id'],)
    ).fetchone()
    subject = class_info['subject']
    grade_level = class_info['grade_level']
    open_questions = conn.execute(
        'SELECT id, question, sample_solution, taxonomy FROM HomeworkOpenQuestions WHERE id IN (%s)' %
        ','.join('?'*len(answers)),
        tuple(answers.keys())
    ).fetchall()

    questions_for_gpt = []
    for oq in open_questions:
        questions_for_gpt.append({
            "id": oq['id'],
            "question": oq['question'],
            "sample_solution": oq['sample_solution'],
            "taxonomy": oq['taxonomy'],
            "student_answer": answers[str(oq['id'])]
        })

    prompt = f"""
        You are an educational assistant. Please grade the following open questions for a student.
        For each question, compare the student's answer with the sample solution. 
        If the answer is correct, reply with "Correct!" and set "is_correct": true.
        If not, explain what is missing or incorrect, and set "is_correct": false.
        After all questions, give a short overall feedback as "summary" and a concrete learning path recommendation as "recommendation".
        Students can Retry by working more open questions or multiple choice questions.
        Formulate the Answers as if you where the students sideckick. Talk directly to Him.

        Homework info:
        - Subject: {subject}
        - Grade: {grade_level}
        - Description: {homework['description']}

        Questions and answers:
        {json.dumps(questions_for_gpt, ensure_ascii=False, indent=2)}

        Please answer in JSON:
        {{
        "feedback": {{
            "<question_id>": {{"result": "...", "is_correct": true/false}},
            ...
        }},
        "summary": "...",
        "recommendation": "..."
        }}
        """
    print("=== Prompt an ChatGPT ===")
    print(prompt)
    print("========================")

    api_key = os.getenv("CHATGPT_API_KEY")
    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    data_api = {
        "model": "gpt-4o",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7
    }

    try:
        response = requests.post(url, headers=headers, json=data_api)
        if response.status_code == 200:
            result = response.json()
            generated_content = result["choices"][0]["message"]["content"]
            try:
                # Versuche, das JSON explizit aus dem Text zu extrahieren
                json_start = generated_content.index('{')
                json_end = generated_content.rindex('}')
                json_content = generated_content[json_start:json_end + 1]
                gpt_json = json.loads(json_content)
            except (ValueError, json.JSONDecodeError) as e:
                print("Fehler beim Parsen der JSON-Antwort:", e)
                gpt_json = {"feedback": {}, "summary": "Sorry, automatic grading failed.", "recommendation": ""}
        else:
            print(f"OpenAI error: {response.status_code} - {response.text}")
            gpt_json = {"feedback": {}, "summary": "Sorry, automatic grading failed.", "recommendation": ""}
    except Exception as e:
        print("OpenAI request failed:", e)
        gpt_json = {"feedback": {}, "summary": "Sorry, automatic grading failed.", "recommendation": ""}

    # Zähle richtige und falsche Antworten
    correct_count = 0
    wrong_count = 0
    for feedback in gpt_json.get("feedback", {}).values():
        if feedback.get("is_correct") is True:
            correct_count += 1
        else:
            wrong_count += 1

    # Skill-Level-Logik
    class_skill_level = conn.execute(
        'SELECT class_skill_level FROM ClassMembers WHERE student_id = ? AND class_id = (SELECT class_id FROM Homework WHERE id = ?)',
        (student_id, homework_id)
    ).fetchone()
    class_skill_level = class_skill_level['class_skill_level'] if class_skill_level else 5
    old_class_skill_level = class_skill_level

    # Nach dem Zählen von correct_count und wrong_count:
    total = correct_count + wrong_count
    percent_correct = (correct_count / total) * 100 if total > 0 else 0

    # Neue Skill-Berechnung
    if correct_count <= 2:
        new_class_skill_level = max(1, class_skill_level - 1)
    elif correct_count <= 4:
        new_class_skill_level = class_skill_level
    else:
        new_class_skill_level = min(10, class_skill_level + 1)

    # Update in DB
    conn.execute(
        'UPDATE ClassMembers SET class_skill_level = ? WHERE student_id = ? AND class_id = (SELECT class_id FROM Homework WHERE id = ?)',
        (new_class_skill_level, student_id, homework_id)
    )

    print("Saved OpenQuestionsResults for", homework_id, student_id)

    avg_class_skill = conn.execute(
        '''
        SELECT ROUND(AVG(class_skill_level), 0) as avg_skill
        FROM ClassMembers
        WHERE student_id = ?
        ''',
        (student_id,)
    ).fetchone()['avg_skill']

    conn.execute(
        '''
        UPDATE Participants
        SET skill_level = ?
        WHERE id = ?
        ''',
        (avg_class_skill, student_id)
    )

        # Speichere das Ergebnis in der Datenbank (Upsert)
    try:
        conn.execute(
            '''
            INSERT INTO HomeworkOpenQuestionsResults (homework_id, student_id, feedback_json, correct_count, wrong_count, summary, recommendation, date_submitted, answered_skill_level, percent_correct, new_class_skill_level, new_skill_level)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(homework_id, student_id)
            DO UPDATE SET feedback_json=excluded.feedback_json, correct_count=excluded.correct_count, wrong_count=excluded.wrong_count, summary=excluded.summary, recommendation=excluded.recommendation, date_submitted=excluded.date_submitted, answered_skill_level=excluded.answered_skill_level, percent_correct=excluded.percent_correct, new_class_skill_level=excluded.new_class_skill_level, new_skill_level=excluded.new_skill_level
            ''',
            (
                homework_id,
                student_id,
                json.dumps(gpt_json.get("feedback", {})),
                correct_count,
                wrong_count,
                gpt_json.get("summary", ""),
                gpt_json.get("recommendation", ""),
                datetime.now().isoformat(),
                old_class_skill_level,
                percent_correct,
                new_class_skill_level,
                avg_class_skill
            )
        )
        print("Insert/Update HomeworkOpenQuestionsResults OK")
    except Exception as e:
        print("Insert/Update HomeworkOpenQuestionsResults FAILED:", e)

    # Team-Punkte gutschreiben, falls TeamChallenge
    team_challenge = conn.execute(
        'SELECT id FROM TeamChallenges WHERE homework_id = ?', (homework_id,)
    ).fetchone()

    conn.commit()
    conn.close()

    add_points_and_check_level(student_id, correct_count * 4, allow_bonus=True)
    if team_challenge:
        add_points_to_team(homework_id, student_id, correct_count * 4, allow_bonus=True)
    check_and_award_badges(student_id)
    gpt_json["correct_count"] = correct_count
    gpt_json["wrong_count"] = wrong_count
    gpt_json["class_skill_level"] = new_class_skill_level
    gpt_json["overall_skill_level"] = avg_class_skill
    return jsonify(gpt_json)

@app.route('/submit_retry_task', methods=['POST'])
def submit_retry_task():
    from datetime import datetime
    conn = get_db_connection()
    data = request.get_json()
    retry_id = data.get('retry_id')
    student_id = data.get('student_id')
    correct_count = int(data.get('correct_count'))
    incorrect_count = int(data.get('incorrect_count'))
    selected_answers = data.get('selected_answers', {})

    # Prüfe, ob schon ein Ergebnis existiert
    existing = conn.execute(
        'SELECT id FROM HomeworkRetryResults WHERE retry_id = ? AND student_id = ?',
        (retry_id, student_id)
    ).fetchone()

    if existing:
        conn.close()
        return {"message": "Already submitted"}, 200

    # Hole die Fragen für diesen Retry
    questions = conn.execute(
        'SELECT question, options, correct_answer, explanation FROM HomeworkRetryQuestions WHERE retry_id = ?',
        (retry_id,)
    ).fetchall()

    questions_for_gpt = []
    for idx, q in enumerate(questions):
        options = json.loads(q['options'])
        questions_for_gpt.append({
            "question": q['question'],
            "options": options,
            "correct_answer": q['correct_answer'],
            "student_answer": selected_answers.get(str(idx)),
            "explanation": q['explanation']
        })

    # Hole Kontextinfos
    retry = conn.execute('SELECT homework_id FROM HomeworkRetries WHERE id = ?', (retry_id,)).fetchone()
    homework_id = retry['homework_id']
    class_info = conn.execute(
        'SELECT subject, grade_level FROM Classes WHERE id = (SELECT class_id FROM Homework WHERE id = ?)', (homework_id,)
    ).fetchone()
    subject = class_info['subject'] if class_info else ''
    grade_level = class_info['grade_level'] if class_info else ''

    # Prompt für KI
    prompt = f"""
You are an educational assistant. Please analyze the following multiple-choice retry homework results for a student.

- Give a short, motivating summary of the student's performance.
- Based on the number and type of mistakes, recommend a learning path: Should the student retry with more multiple-choice questions, switch to open questions, or review the material first?
- Give concrete, actionable advice for improvement.
- Formulate your answer as if you were the student's sidekick. Talk directly to them.
- A answere is correct if correct_answer and student_answer are the same, for example "correct_answer": 0,"student_answer": 0,

Homework info:
- Subject: {subject}
- Grade: {grade_level}

Questions and answers:
{json.dumps(questions_for_gpt, ensure_ascii=False, indent=2)}

Please answer in JSON:
{{
  "summary": "...",
  "recommendation": "..."
}}
"""
    print("=== Prompt an ChatGPT ===")
    print(prompt)
    print("========================")
    # KI-Call
    api_key = os.getenv("CHATGPT_API_KEY")
    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    data_api = {
        "model": "gpt-4o",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7
    }

    try:
        response = requests.post(url, headers=headers, json=data_api)
        if response.status_code == 200:
            result = response.json()
            generated_content = result["choices"][0]["message"]["content"]
            try:
                json_start = generated_content.index('{')
                json_end = generated_content.rindex('}')
                json_content = generated_content[json_start:json_end + 1]
                gpt_json = json.loads(json_content)
                mc_feedback_summary = gpt_json.get("summary", "")
                mc_feedback_recommendation = gpt_json.get("recommendation", "")
            except Exception as e:
                mc_feedback_summary = "No summary available."
                mc_feedback_recommendation = ""
        else:
            mc_feedback_summary = "No summary available."
            mc_feedback_recommendation = ""
    except Exception as e:
        mc_feedback_summary = "No summary available."
        mc_feedback_recommendation = ""

    date_submitted = datetime.now().isoformat()
    conn.execute(
        '''INSERT INTO HomeworkRetryResults
           (retry_id, student_id, selected_answers, correct_count, incorrect_count, date_submitted, mc_feedback_summary, mc_feedback_recommendation)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
        (retry_id, student_id, json.dumps(selected_answers), correct_count, incorrect_count, date_submitted, mc_feedback_summary, mc_feedback_recommendation)
    )

    homework_id = retry['homework_id']
    first_retry = conn.execute(
        '''
        SELECT id FROM HomeworkRetries
        WHERE homework_id = ? AND student_id = ?
        ORDER BY date_created ASC LIMIT 1
        ''',
        (homework_id, student_id)
    ).fetchone()

    team_challenge = conn.execute(
            'SELECT id FROM TeamChallenges WHERE homework_id = ?', (homework_id,)
        ).fetchone()

    conn.commit()
    conn.close()

    if first_retry and first_retry['id'] == retry_id:
        add_points_and_check_level(student_id, correct_count * 1, allow_bonus=False)
        if team_challenge:
            add_points_to_team(homework_id, student_id, correct_count, allow_bonus=False)
        check_and_award_badges(student_id)
        return {
            "message": "Retry submitted",
            "mc_feedback_summary": mc_feedback_summary,
            "mc_feedback_recommendation": mc_feedback_recommendation,
            "correct_count": correct_count,
            "incorrect_count": incorrect_count
        }, 200
    else:
        return jsonify({
        "mc_feedback_summary": mc_feedback_summary,
        "mc_feedback_recommendation": mc_feedback_recommendation,
        "correct_count": correct_count,
        "incorrect_count": incorrect_count,
        "message": "Already collected points for retry in this HA."
    })

@app.route('/check_retry_open_questions', methods=['POST'])
def check_retry_open_questions():
    data = request.get_json()
    retry_id = data.get('retry_id')
    student_id = data.get('student_id')
    answers = data.get('answers', {})

    conn = get_db_connection()

    # Antworten speichern (Upsert)
    for oq_id, answer in answers.items():
        conn.execute(
            '''
            INSERT INTO HomeworkRetryOpenAnswers (retry_id, student_id, open_question_id, answer, date_submitted)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(retry_id, student_id, open_question_id)
            DO UPDATE SET answer=excluded.answer, date_submitted=excluded.date_submitted
            ''',
            (retry_id, student_id, oq_id, answer, datetime.now().isoformat())
        )

    retry = conn.execute('SELECT homework_id FROM HomeworkRetries WHERE id = ?', (retry_id,)).fetchone()
    if not retry:
        conn.close()
        return jsonify({"error": "Retry not found"}), 404
    homework_id = retry['homework_id']

    homework = conn.execute('SELECT * FROM Homework WHERE id = ?', (homework_id,)).fetchone()
    class_info = conn.execute(
        'SELECT subject, grade_level FROM Classes WHERE id = ?',
        (homework['class_id'],)
    ).fetchone()
    subject = class_info['subject']
    grade_level = class_info['grade_level']
    # Fragen und Musterlösungen laden
    open_questions = conn.execute(
        'SELECT id, question, sample_solution, taxonomy FROM HomeworkRetryOpenQuestions WHERE retry_id = ? AND id IN (%s)' %
        ','.join('?'*len(answers)),
        (retry_id, *answers.keys())
    ).fetchall()

    questions_for_gpt = []
    for oq in open_questions:
        questions_for_gpt.append({
            "id": oq['id'],
            "question": oq['question'],
            "sample_solution": oq['sample_solution'],
            "taxonomy": oq['taxonomy'],
            "student_answer": answers[str(oq['id'])]
        })

    prompt = f"""
    You are an educational assistant. Please grade the following open questions for a student.
    For each question, compare the student's answer with the sample solution. 
    If the answer is correct, reply with "Correct!" and set "is_correct": true.
    If not, explain what is missing or incorrect, and set "is_correct": false.
    After all questions, give a short overall feedback as "summary" and a concrete learning path recommendation as "recommendation".
    Students can Retry by working more open questions or multiple choice questions.
    Formulate the Answers as if you were the student's sidekick. Talk directly to them.

    Homework info:
        - Subject: {subject}
        - Grade: {grade_level}
        - Description: {homework['description']}

    Questions and answers:
    {json.dumps(questions_for_gpt, ensure_ascii=False, indent=2)}

    Please answer in JSON:
    {{
    "feedback": {{
        "<question_id>": {{"result": "...", "is_correct": true/false}},
        ...
    }},
    "summary": "...",
    "recommendation": "..."
    }}
    """

    print("=== Prompt an ChatGPT ===")
    print(prompt)
    print("========================")
    # OpenAI-Call wie gehabt...
    api_key = os.getenv("CHATGPT_API_KEY")
    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    data_api = {
        "model": "gpt-4o",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7
    }

    try:
        response = requests.post(url, headers=headers, json=data_api)
        if response.status_code == 200:
            result = response.json()
            generated_content = result["choices"][0]["message"]["content"]
            try:
                json_start = generated_content.index('{')
                json_end = generated_content.rindex('}')
                json_content = generated_content[json_start:json_end + 1]
                gpt_json = json.loads(json_content)
            except (ValueError, json.JSONDecodeError) as e:
                gpt_json = {"feedback": {}, "summary": "Sorry, automatic grading failed.", "recommendation": ""}
        else:
            gpt_json = {"feedback": {}, "summary": "Sorry, automatic grading failed.", "recommendation": ""}
    except Exception as e:
        gpt_json = {"feedback": {}, "summary": "Sorry, automatic grading failed.", "recommendation": ""}

    # Zähle richtige und falsche Antworten
    correct_count = 0
    wrong_count = 0
    for feedback in gpt_json.get("feedback", {}).values():
        if feedback.get("is_correct") is True:
            correct_count += 1
        else:
            wrong_count += 1

    # Speichere das Ergebnis in der Datenbank (Upsert)
    conn.execute(
        '''
        INSERT INTO HomeworkRetryOpenResults (retry_id, student_id, feedback_json, correct_count, wrong_count, summary, recommendation, date_submitted)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(retry_id, student_id)
        DO UPDATE SET feedback_json=excluded.feedback_json, correct_count=excluded.correct_count, wrong_count=excluded.wrong_count, summary=excluded.summary, recommendation=excluded.recommendation, date_submitted=excluded.date_submitted
        ''',
        (
            retry_id,
            student_id,
            json.dumps(gpt_json.get("feedback", {})),
            correct_count,
            wrong_count,
            gpt_json.get("summary", ""),
            gpt_json.get("recommendation", ""),
            datetime.now().isoformat()
        )
    )

    homework_id = retry['homework_id']
    first_retry = conn.execute(
        '''
        SELECT id FROM HomeworkRetries
        WHERE homework_id = ? AND student_id = ?
        ORDER BY date_created ASC LIMIT 1
        ''',
        (homework_id, student_id)
    ).fetchone()

    team_challenge = conn.execute(
            'SELECT id FROM TeamChallenges WHERE homework_id = ?', (homework_id,)
        ).fetchone()

    conn.commit()
    conn.close()

    if first_retry and first_retry['id'] == retry_id:
        add_points_and_check_level(student_id, correct_count * 2, allow_bonus=False)
        if team_challenge:
            add_points_to_team(homework_id, student_id, correct_count * 2, allow_bonus=False)
        check_and_award_badges(student_id)
        return jsonify({
            "message": "Retry submitted",
            "feedback": gpt_json.get("feedback", {}),
            "summary": gpt_json.get("summary", ""),
            "recommendation": gpt_json.get("recommendation", ""),
            "correct_count": correct_count,
            "wrong_count": wrong_count
        }), 200
    else:
        return jsonify({
            "feedback": gpt_json.get("feedback", {}),
            "summary": gpt_json.get("summary", ""),
            "recommendation": gpt_json.get("recommendation", ""),
            "correct_count": correct_count,
            "wrong_count": wrong_count,
            "message": "Already collected points for retry in this HA."
        })

    
@app.route('/edit_homework/<int:homework_id>/<int:class_id>/<int:teacher_id>', methods=['GET', 'POST'])
def edit_homework(homework_id, class_id, teacher_id):
    import json
    conn = get_db_connection()

    if request.method == 'POST':
        # Daten aktualisieren
        question_ids = request.form.getlist('question_ids')
        questions = request.form.getlist('questions')
        options_list = request.form.getlist('options')
        correct_answers = request.form.getlist('correct_answers')
        explanations = request.form.getlist('explanations')
        taxonomies = request.form.getlist('taxonomies')
        skill_levels = request.form.getlist('skill_levels')

        # Zähle Fragen pro Schwierigkeitsgrad
        skill_count = {1: 0, 4: 0, 8: 0}

        # Nur so viele Einträge wie tatsächlich MC-Fragen vorhanden sind!
        for idx in range(len(question_ids)):
            try:
                options = json.dumps(options_list[idx].split(','))
                skill_level = int(skill_levels[idx])
                conn.execute(
                    '''UPDATE HomeworkQuestions
                       SET question = ?, options = ?, correct_answer = ?, explanation = ?, taxonomy = ?, skill_level = ?
                       WHERE id = ?''',
                    (questions[idx], options, correct_answers[idx], explanations[idx], taxonomies[idx], skill_levels[idx], question_ids[idx])
                )
            except IndexError:
                return f"Fehler: Index {idx} außerhalb der Listenlänge. Prüfe die Eingabefelder!", 400

        # Überprüfe die Bedingung: 10 Fragen pro Schwierigkeitsgrad
        if 'publish' in request.form:
            # Status auf 'published' setzen
            conn.execute('UPDATE Homework SET status = ? WHERE id = ?', ('published', homework_id))
        else:
            # Status auf 'draft' setzen
            conn.execute('UPDATE Homework SET status = ? WHERE id = ?', ('draft', homework_id))

        # Open Questions aktualisieren
        open_question_ids = request.form.getlist('open_question_ids')
        open_questions = request.form.getlist('open_questions')
        sample_solutions = request.form.getlist('sample_solutions')
        open_taxonomies = request.form.getlist('open_taxonomies')

        for idx, oq_id in enumerate(open_question_ids):
            conn.execute(
                '''UPDATE HomeworkOpenQuestions
                   SET question = ?, sample_solution = ?, taxonomy = ?
                   WHERE id = ?''',
                (open_questions[idx], sample_solutions[idx], open_taxonomies[idx], oq_id)
            )

        conn.commit()
        conn.close()
        return redirect(url_for('class_details_teacher', class_id=class_id, teacher_id=teacher_id))

    # Bestehende Daten laden
    homework = conn.execute('SELECT * FROM Homework WHERE id = ?', (homework_id,)).fetchone()
    questions = conn.execute('SELECT * FROM HomeworkQuestions WHERE homework_id = ?', (homework_id,)).fetchall()

    # Neue Abfrage für Open Questions
    open_questions = conn.execute(
        'SELECT * FROM HomeworkOpenQuestions WHERE homework_id = ?', (homework_id,)
    ).fetchall()

    conn.close()

    # JSON-Modul zur Vorlage übergeben
    return render_template('edit_homework.html', 
                           homework=homework, 
                           questions=questions, 
                           open_questions=open_questions,  # <-- Hier übergeben
                           class_id=class_id, 
                           teacher_id=teacher_id, 
                           json=json)



@app.route('/toggle_homework_status/<int:homework_id>', methods=['POST'])
def toggle_homework_status(homework_id):
    conn = get_db_connection()

    # Aktuellen Status der Hausaufgabe abrufen
    current_status = conn.execute(
        'SELECT status FROM Homework WHERE id = ?', (homework_id,)
    ).fetchone()['status']

    # Neuen Status setzen
    new_status = 'draft' if current_status == 'published' else 'published'
    conn.execute(
        'UPDATE Homework SET status = ? WHERE id = ?',
        (new_status, homework_id)
    )

    conn.commit()
    conn.close()

    return redirect(url_for('edit_homework', homework_id=homework_id))

@app.route('/retry_homework', methods=['POST'])
def retry_homework():
    import json
    from datetime import datetime

    api_key = os.getenv("CHATGPT_API_KEY")
    data = request.get_json()
    homework_id = data.get('homework_id')
    student_id = data.get('student_id')
    reason = data.get('reason')
    extra_info = data.get('extra_info', '')
    wrong_questions = data.get('wrong_questions', [])
    class_skill_level = data.get('class_skill_level', 1)
    retry_type = data.get('retry_type', 'mc')

    conn = get_db_connection()

    # Get homework description
    homework = conn.execute('SELECT description, title FROM Homework WHERE id = ?', (homework_id,)).fetchone()
    description = homework['description']
    title = homework['title']

    class_info = conn.execute(
        'SELECT subject, grade_level FROM Classes WHERE id = (SELECT class_id FROM Homework WHERE id = ?)', (homework_id,)
    ).fetchone()
    subject = class_info['subject'] if class_info else ''
    grade_level = class_info['grade_level'] if class_info else ''

    filtered_wrong_questions = []
    for q in wrong_questions:
        # MC-Fragen
        if "options" in q:
            filtered_wrong_questions.append({
                "question": q.get("question"),
                "options": q.get("options"),
                "answer": q.get("answer"),
                "selected": q.get("selected"),
                "explanation": q.get("explanation", ""),
                "taxonomy": q.get("taxonomy", "")
            })
        # Open Questions
        else:
            filtered_wrong_questions.append({
                "question": q.get("question"),
                "sample_solution": q.get("sample_solution"),
                "taxonomy": q.get("taxonomy"),
                "student_answer": q.get("student_answer", "")
            })

    if retry_type == "mc":
        prompt = f"""
        You are an educational assistant on an e-learning platform designed to support personalized, fair, and motivating learning experiences for students. 
        The platform uses generative AI to automatically create and adapt learning content based on student performance. One of its features allows students to retry incorrectly answered homework questions to better understand the concepts and improve their skills. This retry functionality aims to support mastery learning and reduce the pressure of one-time assessments.
        The student now wants to retry a previously assigned homework. Below, you will find the context of the original homework assignment, the student’s current class skill level, the reason they chose to retry, and any additional student-provided information. Most importantly, you will also see the list of questions the student answered incorrectly. These incorrect responses serve as the learning foundation for generating improved follow-up questions.

        Your task:
        Please create **10 new multiple-choice questions** (4 options per question, answer as index (0-based)) that:
        - Cover similar topics or concepts as the incorrectly answered questions.
        - Match the student's current class skill level (1-10 scale, 10 = most advanced).
        - Help the student improve by addressing the specific gaps identified through their incorrect responses.
        - Are **not identical** to the original questions but target the same learning objectives.
        - Depending on wich Questions the Student got Wrong, provide questions for the following types of Blooms Taxonomie: Remembering, Understanding, Applying, Analysing, Evaluating, Creating.

        Homework subject: {subject}
        Homework grade level: {grade_level}
        Homework title: {title}
        Homework description: {description}
        Student class skill level: {class_skill_level}
        Reason for retry: {reason}
        Student's additional info: {extra_info}
        questions the student got wrong:
        {json.dumps(filtered_wrong_questions, ensure_ascii=False, indent=2)}
        Please answer only with JSON in this format:
        [
            {{"question": "...", "options": ["...", "...", "...", "..."], "answer": 0, "explanation": "...", "taxonomy": "..."}}
        ]
        """

        print("=== Prompt an ChatGPT ===")
        print(prompt)
        print("========================")
        # OpenAI API call
        url = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }
        data_api = {
            "model": "gpt-4o",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.7
        }
        response = requests.post(url, headers=headers, json=data_api)
        if response.status_code == 200:
            result = response.json()
            generated_content = result["choices"][0]["message"]["content"]
            try:
                json_start = generated_content.index('[')
                json_end = generated_content.rindex(']')
                json_content = generated_content[json_start:json_end + 1]
                questions = json.loads(json_content)
            except Exception as e:
                conn.close()
                return jsonify({"error": f"Error parsing JSON: {str(e)}"}), 500
        else:
            conn.close()
            return jsonify({"error": f"OpenAI error: {response.text}"}), 500

        # Count previous retries
        retry_count = conn.execute(
            'SELECT COUNT(*) FROM HomeworkRetries WHERE homework_id = ? AND student_id = ?',
            (homework_id, student_id)
        ).fetchone()[0] + 1

        # Save retry meta
        cursor = conn.execute(
            '''INSERT INTO HomeworkRetries 
            (homework_id, student_id, retry_count, reason, extra_info, generated_questions, date_created, retry_type)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
            (homework_id, student_id, retry_count, reason, extra_info, json.dumps(questions), datetime.now().isoformat(), 'mc')
        )
        retry_id = cursor.lastrowid

        # Save each question in HomeworkRetryQuestions
        for q in questions:
            options = json.dumps(q['options'])
            conn.execute(
                '''INSERT INTO HomeworkRetryQuestions
                (retry_id, skill_level, question, correct_answer, explanation, question_type, options, taxonomy)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                (
                    retry_id,
                    class_skill_level,
                    q['question'],
                    q['answer'],
                    q.get('explanation', ''),
                    'multiple_choice',
                    options,
                    q.get('taxonomy', '')
                )
            )

        conn.commit()
        conn.close()
        return jsonify({"retry_id": retry_id}), 200

    elif retry_type == "open_questions":
        prompt = f"""
    You are an educational assistant on an e-learning platform designed to support personalized, fair, and motivating learning experiences for students.
    The platform uses generative AI to automatically create and adapt learning content based on student performance. One of its features allows students to retry incorrectly answered homework questions to better understand the concepts and improve their skills. This retry functionality aims to support mastery learning and reduce the pressure of one-time assessments.
    The student now wants to retry a previously assigned homework. Below, you will find the context of the original homework assignment, the student’s current class skill level, the reason they chose to retry, and any additional student-provided information. Most importantly, you will also see the list of questions the student answered incorrectly. These incorrect responses serve as the learning foundation for generating improved follow-up questions.

    Your task:
    Please create **6 new open-ended questions** (each with taxonomy and a sample_solution) that:
    - Cover similar topics or concepts as the incorrectly answered questions.
    - Match the student's current class skill level (1-10 scale, 10 = most advanced).
    - Help the student improve by addressing the specific gaps identified through their incorrect responses.
    - Are **not identical** to the original questions but target the same learning objectives.
    - For each question, provide a sample_solution that would be considered a very good answer for a student.
    - Depending on wich Questions the Student got Wrong, provide questions for the following types of Blooms Taxonomie: Remembering, Understanding, Applying, Analysing, Evaluating, Creating.

    Homework subject: {subject}
    Homework grade level: {grade_level}
    Homework title: {title}
    Homework description: {description}
    Student class skill level: {class_skill_level}
    Reason for retry: {reason}
    Student's additional info: {extra_info}
    Questions the student got wrong:
    {json.dumps(filtered_wrong_questions, ensure_ascii=False, indent=2)}
        Please answer only with JSON in this format:
        [
          {{"question": "...", "sample_solution": "...", "taxonomy": "..."}},
          ...
        ]
        """
        print("=== Prompt an ChatGPT ===")
        print(prompt)
        print("========================")

        url = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }
        data_api = {
            "model": "gpt-4o",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.7
        }
        response = requests.post(url, headers=headers, json=data_api)
        if response.status_code == 200:
            result = response.json()
            generated_content = result["choices"][0]["message"]["content"]
            try:
                json_start = generated_content.index('[')
                json_end = generated_content.rindex(']')
                json_content = generated_content[json_start:json_end + 1]
                questions = json.loads(json_content)
            except Exception as e:
                conn.close()
                return jsonify({"error": f"Error parsing JSON: {str(e)}"}), 500
        else:
            conn.close()
            return jsonify({"error": f"OpenAI error: {response.text}"}), 500

        # Retry-Count
        retry_count = conn.execute(
            'SELECT COUNT(*) FROM HomeworkRetries WHERE homework_id = ? AND student_id = ?',
            (homework_id, student_id)
        ).fetchone()[0] + 1

        # Speichere Retry-Meta
        cursor = conn.execute(
            '''INSERT INTO HomeworkRetries 
               (homework_id, student_id, retry_count, reason, extra_info, generated_questions, date_created, retry_type)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
            (homework_id, student_id, retry_count, reason, extra_info, json.dumps(questions), datetime.now().isoformat(), 'open')
        )
        retry_id = cursor.lastrowid

        # Speichere jede Frage in HomeworkRetryOpenQuestions (neue Tabelle!)
        for q in questions:
            conn.execute(
                '''INSERT INTO HomeworkRetryOpenQuestions
                   (retry_id, skill_level, question, sample_solution, taxonomy)
                   VALUES (?, ?, ?, ?, ?)''',
                (
                    retry_id,
                    class_skill_level,
                    q['question'],
                    q.get('sample_solution', ''),
                    q.get('taxonomy', '')
                )
            )

        conn.commit()
        conn.close()
        return jsonify({"retry_id": retry_id}), 200

    else:
        conn.close()
        return jsonify({"error": "Unknown retry type"}), 400


##### Gamification

def add_points_and_check_level(student_id, points_to_add, allow_bonus=True):
    conn = get_db_connection()
    today = datetime.now().strftime("%Y-%m-%d")

    # Hole aktuellen Bonus für heute
    bonus_row = conn.execute(
        'SELECT bonus_left FROM DailyBonus WHERE student_id = ? AND date = ?',
        (student_id, today)
    ).fetchone()
    bonus_left = 30 if not bonus_row else bonus_row['bonus_left']

    # Berechne, wie viele Punkte verdoppelt werden
    if allow_bonus:
        double_points = min(points_to_add, bonus_left)
        normal_points = points_to_add - double_points
        total_points = double_points * 2 + normal_points
        bonus_left = max(0, bonus_left - points_to_add)
    else:
        double_points = 0
        normal_points = points_to_add
        total_points = points_to_add  # Kein Bonus bei Retry

    # Update oder Insert Bonus
    if allow_bonus:
        if bonus_row:
            conn.execute(
                'UPDATE DailyBonus SET bonus_left = ? WHERE student_id = ? AND date = ?',
                (bonus_left, student_id, today)
            )
        else:
            conn.execute(
                'INSERT INTO DailyBonus (student_id, date, bonus_left) VALUES (?, ?, ?)',
                (student_id, today, bonus_left)
            )

    # Punkte und Level aktualisieren
    student = conn.execute('SELECT points, level FROM Participants WHERE id = ?', (student_id,)).fetchone()
    if not student:
        conn.close()
        return

    points = student['points'] + total_points
    old_level = student['level']

    thresholds = []
    needed = 25
    total = 0
    for _ in range(1, 30):
        total += needed
        thresholds.append(total)
        needed *= 2

    new_level = 1
    for threshold in thresholds:
        if points >= threshold:
            new_level += 1
        else:
            break

    # Level-Up in Session speichern, falls gestiegen
    if new_level > old_level:
        session['level_up'] = new_level

    conn.execute('UPDATE Participants SET points = ?, level = ? WHERE id = ?', (points, new_level, student_id))
    conn.commit()
    conn.close()

@app.route('/get_daily_bonus')
def get_daily_bonus():
    student_id = request.args.get('student_id', type=int)
    from datetime import datetime
    today = datetime.now().strftime("%Y-%m-%d")
    conn = get_db_connection()
    row = conn.execute(
        'SELECT bonus_left FROM DailyBonus WHERE student_id = ? AND date = ?',
        (student_id, today)
    ).fetchone()
    conn.close()
    bonus_left = row['bonus_left'] if row else 30
    return jsonify({"bonus_left": bonus_left})

def add_points_to_team(homework_id, student_id, points_to_add, allow_bonus=True):
    from datetime import datetime
    conn = get_db_connection()
    today = datetime.now().strftime("%Y-%m-%d")

    # Hole TeamChallenge
    team_challenge = conn.execute(
        'SELECT id, current_score, goal_score, start_time, end_time, success FROM TeamChallenges WHERE homework_id = ?', (homework_id,)
    ).fetchone()
    if not team_challenge:
        conn.close()
        return

    # Hole aktuellen Bonus für heute (pro Schüler, wie bei Solo)
    bonus_row = conn.execute(
        'SELECT bonus_left FROM DailyBonus WHERE student_id = ? AND date = ?',
        (student_id, today)
    ).fetchone()
    bonus_left = 30 if not bonus_row else bonus_row['bonus_left']

    # Berechne, wie viele Punkte verdoppelt werden
    if allow_bonus:
        double_points = min(points_to_add, bonus_left)
        normal_points = points_to_add - double_points
        total_points = double_points * 2 + normal_points
    else:
        total_points = points_to_add

    # Addiere zum aktuellen Team-Score
    new_score = team_challenge['current_score'] + total_points
    conn.execute(
        'UPDATE TeamChallenges SET current_score = ? WHERE id = ?',
        (new_score, team_challenge['id'])
    )

    # Status prüfen und ggf. updaten
    now = datetime.now()
    end_time = team_challenge['end_time']
    if end_time:
        try:
            end_dt = datetime.fromisoformat(end_time)
        except Exception:
            end_dt = None
    else:
        end_dt = None

    # Status nur ändern, wenn noch "open"
    if team_challenge['success'] == 'open':
        # ... Ziel erreicht
        if new_score >= team_challenge['goal_score']:
            now_str = datetime.now().isoformat()
            conn.execute(
                'UPDATE TeamChallenges SET success = ?, completed_at = ? WHERE id = ?',
                ('success', now_str, team_challenge['id'])
            )
        elif end_dt and now > end_dt:
            # Zeit abgelaufen, Ziel nicht erreicht
            if new_score < team_challenge['goal_score']:
                conn.execute(
                    'UPDATE TeamChallenges SET success = ? WHERE id = ?', ('failed', team_challenge['id'])
                )

    conn.commit()
    conn.close()

def check_and_award_badges(user_id):
    conn = get_db_connection()
    new_badges = []
    # Level
    level = conn.execute('SELECT level FROM Participants WHERE id = ?', (user_id,)).fetchone()['level']
    for badge in conn.execute("SELECT * FROM Badges WHERE category = 'level' AND threshold <= ?", (level,)).fetchall():
        if _award_badge(conn, user_id, badge['id']):
            new_badges.append({"name": badge['name'], "description": badge['description']})
    # Homework: MC + Open Questions
    hw_count = conn.execute('''
        SELECT
            (SELECT COUNT(*) FROM HomeworkResults WHERE student_id = ?)
        + (SELECT COUNT(*) FROM HomeworkOpenQuestionsResults WHERE student_id = ?)
    ''', (user_id, user_id)).fetchone()[0]

    for badge in conn.execute("SELECT * FROM Badges WHERE category = 'homework' AND threshold <= ?", (hw_count,)).fetchall():
        if _award_badge(conn, user_id, badge['id']):
            new_badges.append({"name": badge['name'], "description": badge['description']})
    # Retry: MC + Open Questions
    retry_count = conn.execute('''
        SELECT
            (SELECT COUNT(*) FROM HomeworkRetryResults WHERE student_id = ?)
        + (SELECT COUNT(*) FROM HomeworkRetryOpenResults WHERE student_id = ?)
    ''', (user_id, user_id)).fetchone()[0]

    for badge in conn.execute("SELECT * FROM Badges WHERE category = 'retry' AND threshold <= ?", (retry_count,)).fetchall():
        if _award_badge(conn, user_id, badge['id']):
            new_badges.append({"name": badge['name'], "description": badge['description']})
    # Team
    team_count = conn.execute('''
        SELECT COUNT(*) FROM TeamChallenges
        WHERE TeamChallenges.success = 'success'
        AND EXISTS (
                SELECT 1 FROM HomeworkResults
                WHERE HomeworkResults.homework_id = TeamChallenges.homework_id
                AND HomeworkResults.student_id = ?
                AND (
                        TeamChallenges.completed_at IS NULL
                        OR HomeworkResults.date_submitted <= TeamChallenges.completed_at
                    )
            )
        OR EXISTS (
                SELECT 1 FROM HomeworkOpenQuestionsResults
                WHERE HomeworkOpenQuestionsResults.homework_id = TeamChallenges.homework_id
                AND HomeworkOpenQuestionsResults.student_id = ?
                AND (
                        TeamChallenges.completed_at IS NULL
                        OR HomeworkOpenQuestionsResults.date_submitted <= TeamChallenges.completed_at
                    )
            )
    ''', (user_id, user_id)).fetchone()[0]

    for badge in conn.execute("SELECT * FROM Badges WHERE category = 'team' AND threshold <= ?", (team_count,)).fetchall():
        if _award_badge(conn, user_id, badge['id']):
            new_badges.append({"name": badge['name'], "description": badge['description']})
    conn.commit()
    conn.close()
    if new_badges:
        session['new_badges'] = new_badges
    else:
        session.pop('new_badges', None)
    return new_badges

def _award_badge(conn, user_id, badge_id):
    already = conn.execute(
        "SELECT 1 FROM UserBadges WHERE user_id = ? AND badge_id = ?", (user_id, badge_id)
    ).fetchone()
    if not already:
        conn.execute(
            "INSERT INTO UserBadges (user_id, badge_id) VALUES (?, ?)", (user_id, badge_id)
        )

@app.route('/set_favorite_badges', methods=['POST'])
def set_favorite_badges():
    if 'student_id' not in session:
        return redirect('/')
    student_id = session['student_id']
    badge_ids = request.form.getlist('badge_ids[]')  # Array mit bis zu 3 IDs

    conn = get_db_connection()
    conn.execute('DELETE FROM UserFavoriteBadges WHERE user_id = ?', (student_id,))
    for pos, badge_id in enumerate(badge_ids[:3], 1):
        conn.execute(
            'INSERT INTO UserFavoriteBadges (user_id, badge_id, position) VALUES (?, ?, ?)',
            (student_id, badge_id, pos)
        )
    conn.commit()
    conn.close()
    return '', 204


if __name__ == '__main__':
    app.run(debug=True)
