from flask import Flask, render_template, request, redirect, url_for, session
import sqlite3
import json
from datetime import datetime
from openai  import OpenAI# ChatGPT API
import os
import openai
import requests


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
        SELECT id, title, date_created, status
        FROM Homework
        WHERE class_id = ?
        ''', (class_id,)
    ).fetchall()

    # Durchschnittswerte für Graphen berechnen
    dates = []
    titles = []
    avg_correct_counts = []
    avg_skill_levels = []

    for hw in homework_list:
        # Prüfen, ob es Bearbeitungen gibt
        count_results = conn.execute(
            '''
            SELECT COUNT(*) as count
            FROM HomeworkResults
            WHERE homework_id = ?
            ''', (hw['id'],)
        ).fetchone()['count']

        # Nur Hausaufgaben mit Bearbeitungen berücksichtigen
        if count_results > 0:
            # Datum und Titel erfassen
            date_created = hw['date_created']
            if isinstance(date_created, str):
                try:
                    date_created = datetime.strptime(date_created, '%Y-%m-%d')
                except ValueError:
                    date_created = datetime.strptime(date_created, '%Y-%m-%d %H:%M:%S')
            dates.append(date_created.strftime('%Y-%m-%d'))
            titles.append(hw['title'])

            # Durchschnitt der richtigen Antworten
            avg_correct = conn.execute(
                '''
                SELECT ROUND(AVG(correct_count), 0) AS avg_correct
                FROM HomeworkResults
                WHERE homework_id = ?
                ''', (hw['id'],)
            ).fetchone()['avg_correct'] or 0
            avg_correct_counts.append(avg_correct)

            # Durchschnitt des Klassenskill-Levels
            avg_skill = conn.execute(
                '''
                SELECT ROUND(AVG(new_class_skill_level), 0) AS avg_skill
                FROM HomeworkResults
                WHERE homework_id = ?
                ''', (hw['id'],)
            ).fetchone()['avg_skill'] or 0
            avg_skill_levels.append(avg_skill)

    conn.close()

    return render_template(
        'class_details_teacher.html',
        class_info=class_info,
        students=students,
        teacher_id=teacher_id,
        homework_list=homework_list,
        dates=dates,
        titles=titles,
        avg_correct_counts=avg_correct_counts,
        avg_skill_levels=avg_skill_levels
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

    # Hausaufgabenergebnisse und Skill-Level-Verlauf abrufen
    results = conn.execute(
        '''
        SELECT 
            HomeworkResults.correct_count, 
            HomeworkResults.date_submitted, 
            Homework.title, 
            HomeworkResults.new_class_skill_level
        FROM HomeworkResults
        JOIN Homework ON HomeworkResults.homework_id = Homework.id
        WHERE HomeworkResults.student_id = ? AND Homework.class_id = ?
        ORDER BY HomeworkResults.date_submitted ASC
        ''',
        (student_id, class_id)
    ).fetchall()

    # Initialisiere Listen für Graphendaten
    dates, titles, correct_counts, skill_levels = [], [], [], []

    for result in results:
        # Datum umwandeln, falls nötig
        try:
            date_submitted = datetime.strptime(result['date_submitted'], '%Y-%m-%d')
        except (ValueError, TypeError):
            date_submitted = result['date_submitted']
        dates.append(date_submitted.strftime('%Y-%m-%d'))

        titles.append(result['title'])
        correct_counts.append(result['correct_count'])
        skill_levels.append(result['new_class_skill_level'])

    mean_correct = round(sum(correct_counts) / len(correct_counts), 2) if correct_counts else 0

    conn.close()

    return render_template(
        'student_details.html',
        student_info=student_info,
        class_id=class_id,
        teacher_id=teacher_id,
        dates=dates,
        titles=titles,
        correct_counts=correct_counts,
        mean_correct=mean_correct,
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

    # Verlauf des gesamten Skill-Levels nur für bearbeitete Hausaufgaben
    skill_history = conn.execute(
        '''
        SELECT 
            HomeworkResults.date_submitted, 
            Homework.title, 
            HomeworkResults.new_skill_level,
            Classes.class_name  -- Klassennamen hinzufügen
        FROM HomeworkResults
        JOIN Homework ON HomeworkResults.homework_id = Homework.id
        JOIN Classes ON Homework.class_id = Classes.id  -- Annahme, dass Homework eine class_id hat
        WHERE HomeworkResults.student_id = ?
        ORDER BY HomeworkResults.date_submitted
        ''',
        (student_id,)
    ).fetchall()

    # Graphen vorbereiten
    dates = []
    titles = []
    skill_levels = []
    class_names = []  # Neue Liste für die Klassennamen

    for entry in skill_history:
        dates.append(entry['date_submitted'])
        titles.append(entry['title'])
        skill_levels.append(entry['new_skill_level'])
        class_names.append(entry['class_name'])  # Klassennamen sammeln

    all_classes = conn.execute('SELECT id, class_name FROM Classes').fetchall()
    all_classes_dict = [{'id': int(class_['id']), 'class_name': class_['class_name']} for class_ in all_classes]

    conn.close()

    return render_template(
        'student_dashboard.html',
        student=student,
        joined_classes=joined_classes,
        dates=dates,
        skill_levels=skill_levels,
        titles=titles,
        class_names=class_names,
        all_classes=all_classes_dict
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
    import json
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
                WHEN HomeworkResults.date_submitted IS NOT NULL THEN 'Done'
                ELSE 'Offen'
            END AS status
        FROM Homework
        LEFT JOIN HomeworkResults ON Homework.id = HomeworkResults.homework_id
        AND HomeworkResults.student_id = ?
        WHERE Homework.class_id = ?  AND Homework.status = 'published'
        ''', (student_id, class_id)
    ).fetchall()

 # Daten für Graphen vorbereiten – nur bearbeitete Hausaufgaben
    homework_results = conn.execute(
        '''
        SELECT 
            HomeworkResults.correct_count, 
            HomeworkResults.date_submitted, 
            Homework.title, 
            HomeworkResults.new_class_skill_level  -- Verwenden des Klassenskill-Levels
        FROM HomeworkResults
        JOIN Homework ON HomeworkResults.homework_id = Homework.id
        WHERE HomeworkResults.student_id = ? AND Homework.class_id = ?
        ORDER BY HomeworkResults.date_submitted ASC
        ''',
        (student_id, class_id)  # <-- Zwei Parameter, da die zusätzliche JOIN-Bedingung entfernt wurde
    ).fetchall()

    # Graphdaten erstellen
    dates = []
    titles = []
    correct_counts = []
    skill_levels = []

    for result in homework_results:
        # Datum konvertieren
        date_submitted = result['date_submitted']
        if isinstance(date_submitted, str):
            date_submitted = datetime.strptime(date_submitted, '%Y-%m-%d')
        dates.append(date_submitted.strftime('%Y-%m-%d'))
        titles.append(result['title'])
        correct_counts.append(result['correct_count'])
        skill_levels.append(result['new_class_skill_level'])  # Verwenden des neuen Klassenskill-Levels

    conn.close()

    return render_template(
        'class_details_student.html',
        class_info=class_info,
        student=student,
        student_id=student_id,
        homework_list=homework_list,
        dates=dates,
        titles=titles,
        correct_counts=correct_counts,
        skill_levels=skill_levels
    )



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


### Hausaufgabenerstellung ###


@app.route('/create_homework', methods=['POST'])
def create_homework():
    import json
    from datetime import datetime

    api_key = os.getenv("CHATGPT_API_KEY")

    class_id = request.form['class_id']
    description = request.form['description']
    title = request.form['title']
    teacher_id = request.form['teacher_id']

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

    Based on Bloom's Taxonomy, the questions should be divided into the task types Remembering Understanding Applying Analysing Evaluating Creating.
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
            'INSERT INTO Homework (class_id, description, title, date_created) VALUES (?, ?, ?, ?)',
            (class_id, description, title, datetime.now().date())
        )
        homework_id = cursor.lastrowid

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
        SELECT CASE 
                   WHEN HomeworkResults.date_submitted IS NOT NULL THEN 'Done'
                   ELSE 'Open'
               END AS status
        FROM Homework
        LEFT JOIN HomeworkResults ON Homework.id = HomeworkResults.homework_id
        AND HomeworkResults.student_id = ?
        WHERE Homework.id = ?
        ''', (student_id, homework_id)
    ).fetchone()

    # Abrufen des Skill-Levels des Schülers
    student = conn.execute(
        'SELECT class_skill_level FROM ClassMembers WHERE student_id = ?', (student_id,)
    ).fetchone()
    student_skill_level = student['class_skill_level'] if student else 0

    # Skill-Level-Bereich definieren
    if student_skill_level <= 3:
        skill_level = 1
    elif student_skill_level <= 7:
        skill_level = 4
    else:
        skill_level = 8

    # Hausaufgabe abrufen
    homework = conn.execute(
        'SELECT id, title, description, date_created, class_id FROM Homework WHERE id = ?',
        (homework_id,)
    ).fetchone()

    if not homework:
        conn.close()
        return "Fehler: Diese Hausaufgabe existiert nicht.", 404

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

    conn.close()

    return render_template(
        'view_homework_student.html',
        homework=homework,
        questions=questions,
        class_info=class_info,
        student_id=student_id,
        correct_answers=correct_answers,
        explanations=explanations,
        homework_status=homework_status['status']  # Den Status zur Vorlage übergeben
    )


@app.route('/view_homework_teacher/<int:homework_id>/<int:class_id>/<int:teacher_id>')
def view_homework_teacher(homework_id, class_id, teacher_id):
    import json
    conn = get_db_connection()

    # Abrufen der Hausaufgabendetails
    homework = conn.execute(
        'SELECT id, title, description, date_created FROM Homework WHERE id = ?',
        (homework_id,)
    ).fetchone()

    if not homework:
        conn.close()
        return "Fehler: Hausaufgabe nicht gefunden", 404

    # Abrufen aller Fragen ohne Berücksichtigung des Skill-Levels
    question_data = conn.execute(
        'SELECT question, correct_answer, explanation, options, taxonomy, skill_level FROM HomeworkQuestions WHERE homework_id = ?',
        (homework_id,)
    ).fetchall()

    questions = []
    correct_answers = {}
    explanations = {}

    for idx, row in enumerate(question_data):
        question = dict(row)
        question['options'] = [{'index': i, 'option': opt} for i, opt in enumerate(json.loads(question['options']))]
        questions.append({'index': idx, **question})
        correct_answers[idx] = int(question['correct_answer'])  # Sicherstellen, dass die Antwort als Nummer vorliegt
        explanations[idx] = question['explanation']

    conn.close()

    return render_template(
        'view_homework_teacher.html',
        homework=homework,
        questions=questions,
        class_info={'id': class_id},
        teacher_id=teacher_id,
        correct_answers=correct_answers,
        explanations=explanations
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
    conn = get_db_connection()

    # JSON-Daten aus der Anfrage holen
    data = request.get_json()
    homework_id = data.get('homework_id')
    student_id = data.get('student_id')
    correct_count = int(data.get('correct_count'))
    incorrect_count = int(data.get('incorrect_count'))

    # Datum der Abgabe erfassen
    date_submitted = datetime.now().date()

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

        # Neue Bewertung basierend auf der Leistung
        if correct_count > 7:
            class_skill_level = min(10, class_skill_level + 1)  # Erhöhen (max 10)
        elif correct_count < 4:
            class_skill_level = max(1, class_skill_level - 1)  # Senken (min 1)

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

        # Ergebnis speichern mit neuen Skill-Levels
        conn.execute(
            '''
            INSERT INTO HomeworkResults (homework_id, student_id, correct_count, 
                                         incorrect_count, date_submitted, 
                                         new_class_skill_level, new_skill_level)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ''',
            (homework_id, student_id, correct_count, incorrect_count, date_submitted,
             class_skill_level, avg_class_skill)
        )

        conn.commit()
        conn.close()

        # Erfolgsmeldung mit neuem Skill Level
        return {
            "message": "Results successfully saved",
            "correct_count": correct_count,
            "class_skill_level": class_skill_level,
            "overall_skill_level": avg_class_skill
        }, 200

    except Exception as e:
        return f"Ein Fehler ist aufgetreten: {str(e)}", 500

    
@app.route('/edit_homework/<int:homework_id>/<int:class_id>/<int:teacher_id>', methods=['GET', 'POST'])
def edit_homework(homework_id, class_id, teacher_id):
    import json
    conn = get_db_connection()

    if request.method == 'POST':
        # Daten aktualisieren
        questions = request.form.getlist('questions')
        options_list = request.form.getlist('options')
        correct_answers = request.form.getlist('correct_answers')
        explanations = request.form.getlist('explanations')
        taxonomies = request.form.getlist('taxonomies')
        skill_levels = request.form.getlist('skill_levels')

        # Zähle Fragen pro Schwierigkeitsgrad
        skill_count = {1: 0, 4: 0, 8: 0}

        for idx, question_id in enumerate(request.form.getlist('question_ids')):
            # Verarbeite die Optionen
            options = json.dumps(options_list[idx].split(','))

            # Prüfe, ob das Skill-Level gültig ist
            try:
                skill_level = int(skill_levels[idx])
                if skill_level in skill_count:
                    skill_count[skill_level] += 1
            except ValueError:
                return "Ungültiger Schwierigkeitsgrad.", 400

            # Aktualisiere die Frage in der Datenbank
            conn.execute(
                '''UPDATE HomeworkQuestions
                   SET question = ?, options = ?, correct_answer = ?, explanation = ?, taxonomy = ?, skill_level = ?
                   WHERE id = ?''',
                (questions[idx], options, correct_answers[idx], explanations[idx], taxonomies[idx], skill_levels[idx], question_id)
            )

        # Überprüfe die Bedingung: 10 Fragen pro Schwierigkeitsgrad
        if 'publish' in request.form:
            if any(count != 10 for count in skill_count.values()):
                conn.close()
                return "A homework assignment can only be published if it contains exactly 10 questions per level of difficulty.", 400

            # Status auf 'published' setzen
            conn.execute('UPDATE Homework SET status = ? WHERE id = ?', ('published', homework_id))
        else:
            # Status auf 'draft' setzen
            conn.execute('UPDATE Homework SET status = ? WHERE id = ?', ('draft', homework_id))

        conn.commit()
        conn.close()

        # Zurück zur Klassenansicht
        return redirect(url_for('class_details_teacher', class_id=class_id, teacher_id=teacher_id))

    # Bestehende Daten laden
    homework = conn.execute('SELECT * FROM Homework WHERE id = ?', (homework_id,)).fetchone()
    questions = conn.execute('SELECT * FROM HomeworkQuestions WHERE homework_id = ?', (homework_id,)).fetchall()
    conn.close()

    # JSON-Modul zur Vorlage übergeben
    return render_template('edit_homework.html', 
                           homework=homework, 
                           questions=questions, 
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

    # Zurück zur Bearbeitungsansicht
    return redirect(url_for('edit_homework', homework_id=homework_id))



if __name__ == '__main__':
    app.run(debug=True)
