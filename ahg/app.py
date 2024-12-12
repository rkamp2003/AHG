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
        return "Anmeldedaten ungültig. Bitte versuchen Sie es erneut."


    
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
    conn = get_db_connection()
    
    # Hole vollständige Klasseninformationen
    class_info = conn.execute(
        'SELECT Classes.id, Classes.class_name, Classes.subject, Teachers.name AS teacher_name '
        'FROM Classes '
        'JOIN Teachers ON Classes.teacher_id = Teachers.id '
        'WHERE Classes.id = ? AND teacher_id = ?',
        (class_id, teacher_id)
    ).fetchone()

    if not class_info:
        conn.close()
        return "Fehler: Klasse existiert nicht oder Berechtigungen fehlen.", 404

    # Liste der Schüler abrufen
    students = conn.execute(
        '''
        SELECT Participants.id, Participants.name, ClassMembers.class_skill_level
        FROM Participants
        JOIN ClassMembers ON Participants.id = ClassMembers.student_id
        WHERE ClassMembers.class_id = ?
        ''', (class_id,)
    ).fetchall()

    # Hausaufgaben der Klasse abrufen
    homework_list = conn.execute(
        'SELECT id, description, title,  date_created FROM Homework WHERE class_id = ?',
        (class_id,)
    ).fetchall()

    conn.close()

    return render_template(
        'class_details_teacher.html',
        class_info=class_info,
        students=students,
        teacher_id=teacher_id,
        homework_list=homework_list
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
    conn = get_db_connection()

    # Hole Schülerinformationen
    student_info = conn.execute(
        'SELECT id, name, email, skill_level FROM Participants WHERE id = ?',
        (student_id,)
    ).fetchone()

    if not student_info:
        conn.close()
        return "Fehler: Schüler existiert nicht.", 404

    # Hausaufgabenergebnisse und Datum abrufen
    homework_results = conn.execute(
        '''
        SELECT 
            HomeworkResults.correct_count, 
            HomeworkResults.date_submitted,
            Homework.title
        FROM HomeworkResults
        JOIN Homework ON HomeworkResults.homework_id = Homework.id
        WHERE HomeworkResults.student_id = ? AND Homework.class_id = ?
        ORDER BY HomeworkResults.date_submitted ASC
        ''',
        (student_id, class_id)
    ).fetchall()

    # Daten für den Zeitreihenplot vorbereiten
    # Konvertiere das Feld `date_submitted` beim Abrufen
    dates = []
    for result in homework_results:
        try:
            # Falls das Feld als String vorliegt
            date_submitted = datetime.strptime(result['date_submitted'], '%Y-%m-%d')
        except (ValueError, TypeError):
            # Falls das Feld bereits ein datetime-Objekt ist
            date_submitted = result['date_submitted']
        dates.append(date_submitted.strftime('%Y-%m-%d'))
    correct_counts = [result['correct_count'] for result in homework_results]

    # Durchschnitt berechnen
    mean_correct = round(sum(correct_counts) / len(correct_counts), 2) if correct_counts else 0

    # Füge eine Liste der Titel hinzu
    titles = [result['title'] for result in homework_results]

    conn.close()

    return render_template(
        'student_details.html',
        student_info=student_info,
        class_id=class_id,
        teacher_id=teacher_id,
        dates=dates,
        titles=titles,
        correct_counts=correct_counts,
        mean_correct=mean_correct
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
    student = conn.execute('SELECT * FROM Participants WHERE id = ?', (student_id,)).fetchone()
    joined_classes = conn.execute(
        'SELECT Classes.*, Teachers.name AS teacher_name '
        'FROM Classes '
        'JOIN ClassMembers ON Classes.id = ClassMembers.class_id '
        'JOIN Teachers ON Classes.teacher_id = Teachers.id '
        'WHERE ClassMembers.student_id = ?',
        (student_id,)
    ).fetchall()

    # Konvertiere die Datenbankzeilen in eine Liste von Dictionaries
    all_classes = conn.execute('SELECT id, class_name FROM Classes').fetchall()
    all_classes_dict = [{'id': int(class_['id']), 'class_name': class_['class_name']} for class_ in all_classes]
    conn.close()

    return render_template('student_dashboard.html', student=student, joined_classes=joined_classes, all_classes=all_classes_dict)




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
    conn = get_db_connection()

    # Informationen zur Klasse und zum Lehrer abrufen
    class_info = conn.execute(
        'SELECT Classes.id, Classes.class_name, Classes.subject, Teachers.name AS teacher_name '
        'FROM Classes '
        'JOIN Teachers ON Classes.teacher_id = Teachers.id '
        'WHERE Classes.id = ?', (class_id,)
    ).fetchone()

    # Informationen zum Schüler abrufen
    student = conn.execute(
        '''
        SELECT Participants.name, Participants.email, ClassMembers.class_skill_level
        FROM Participants
        JOIN ClassMembers ON Participants.id = ClassMembers.student_id
        WHERE Participants.id = ? AND ClassMembers.class_id = ?
        ''', (student_id, class_id)
    ).fetchone()

    # Hausaufgaben der Klasse abrufen
    homework_list = conn.execute(
        '''
        SELECT 
            Homework.id, 
            Homework.title, 
            Homework.date_created, 
            CASE WHEN HomeworkResults.date_submitted IS NOT NULL THEN 'Erledigt' ELSE 'Offen' END AS status
        FROM Homework
        LEFT JOIN HomeworkResults ON Homework.id = HomeworkResults.homework_id AND HomeworkResults.student_id = ?
        WHERE Homework.class_id = ?
        ''',
        (student_id, class_id)
    ).fetchall()

    # Informationen zu den Ergebnissen dieser Klasse abrufen
    homework_results = conn.execute(
        '''
        SELECT 
            HomeworkResults.correct_count, 
            HomeworkResults.date_submitted,
            Homework.title
        FROM HomeworkResults
        JOIN Homework ON HomeworkResults.homework_id = Homework.id
        WHERE HomeworkResults.student_id = ? AND Homework.class_id = ?
        ORDER BY HomeworkResults.date_submitted ASC
        ''',
        (student_id, class_id)
    ).fetchall()

    # Konvertiere das Feld `date_submitted` beim Abrufen
    dates = []
    for result in homework_results:
        try:
            # Falls das Feld als String vorliegt
            date_submitted = datetime.strptime(result['date_submitted'], '%Y-%m-%d')
        except (ValueError, TypeError):
            # Falls das Feld bereits ein datetime-Objekt ist
            date_submitted = result['date_submitted']
        dates.append(date_submitted.strftime('%Y-%m-%d'))
    titles = [result['title'] for result in homework_results]
    correct_counts = [result['correct_count'] for result in homework_results]

    # Durchschnittliche richtige Antworten pro Hausaufgabe
    mean_correct = round(sum(correct_counts) / len(correct_counts), 2) if correct_counts else 0

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
        mean_correct=mean_correct
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

    # Hole Klasseninformationen aus der Datenbank
    conn = get_db_connection()
    class_info = conn.execute(
        'SELECT subject, grade_level FROM Classes WHERE id = ?',
        (class_id,)
    ).fetchone()

    # Generiere Hausaufgaben mit ChatGPT
    prompt = f"""
    Erstelle Hausaufgabe für das Fach {class_info['subject']} in der Jahrgangsstufe {class_info['grade_level']}:
    Zur Referenz: Schüler haben ein Skill_level zwischen 1 und 10, wobei 10 das beste/schwierigste ist.

    Hausaufgabenbeschreibung: {description}

    Orientiert an Blooms Taxonomy sollen die Fragen in die Aufgabentypen Remembering Understanding Applying Analyzing Evaluating Creating aufgeteilt werden.
    1. Schwierigkeitsgrad (skill_level 1) 3 * Remembering, 3 * Understanding, 3 * Applying, 1 * Analyzing
    2. Schwierigkeitsgrad (skill_level 4) 2 * Remembering, 3 * Understanding, 3 * Applying, 2 * Analyzing
    3. Schwierigkeitsgrad (skill_level 8) 2 * Remembering, 2 * Understanding, 3 * Applying, 3 * Analyzing
    Die Hausaufgabe sollte ausschließlich Multiple-Choice-Fragen enthalten. 
    Jede Frage sollte vier Antwortmöglichkeiten haben und die richtige Antwort sollte als Index (0-basiert) zurückgegeben werden.

    Erstelle insgesamt 30 Fragen: 10 Fragen pro Schwierigkeitsgrad.
    Bitte nur mit JSON-Inhalt antworten in dem folgenden Format:
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

    return redirect(url_for('class_details_teacher', class_id=class_id, teacher_id=session.get('teacher_id')))

#@app.route('/create_homework', methods=['POST'])
#def create_homework():
    import json
    from datetime import datetime

    class_id = request.form['class_id']
    description = request.form['description']
    title = request.form['title'] 

    # Beispielhafte API-Antwort von ChatGPT (simuliert)
    question_data = [
    {
        "skill_level": 1,
        "questions": [
            {
                "question": "Was ist die Ableitung von f(x) = 5x?",
                "options": ["5", "0", "x", "1"],
                "answer": 0,
                "explanation": "Die Ableitung einer Funktion der Form ax ist a.",
                "taxonomy": "Remembering"
            },
            {
                "question": "Was ist die Ableitung von f(x) = x^2?",
                "options": ["2x", "x", "2x^2", "0"],
                "answer": 0,
                "explanation": "Die Ableitung von x^n ist n*x^(n-1).",
                "taxonomy": "Remembering"
            },
            {
                "question": "Wie lautet die Ableitungsregel für konstante Funktionen?",
                "options": ["1", "x", "0", "derselbe Wert"],
                "answer": 2,
                "explanation": "Die Ableitung einer konstanten Funktion ist immer 0.",
                "taxonomy": "Remembering"
            },
            {
                "question": "Welche Regel verwendest du, um die Ableitung von f(x) = 3x^3 - 2x zu finden?",
                "options": ["Produktregel", "Kettenregel", "Quotientenregel", "Potenzregel"],
                "answer": 3,
                "explanation": "Hier benutzt man die Potenzregel, weil man Terme in Form von x^n hat.",
                "taxonomy": "Understanding"
            },
            {
                "question": "Welche Ableitung ergibt sich aus der Funktion f(x) = x^3 + 2x?",
                "options": ["3x^2 + 2", "3x^2", "2x^2 + 3", "x^3"],
                "answer": 0,
                "explanation": "Anwenden der Potenzregel auf jedes Glied ergibt 3x^2 + 2.",
                "taxonomy": "Understanding"
            },
            {
                "question": "Warum ist die Ableitung einer linearen Funktion konstant?",
                "options": ["Weil der Anstieg konstant bleibt", "Weil die Funktion immer 0 ist", "Weil x eine Konstante ist", "Weil die Funktion nicht linear ist"],
                "answer": 0,
                "explanation": "Der Anstieg einer linearen Funktion ist immer konstant.",
                "taxonomy": "Understanding"
            },
            {
                "question": "Berechne die Ableitung von f(x) = 7x^2.",
                "options": ["14x", "7x", "14x^2", "0"],
                "answer": 0,
                "explanation": "Anwendung der Potenzregel ergibt 2*7*x^(2-1) = 14x.",
                "taxonomy": "Applying"
            },
            {
                "question": "Finde die Ableitung von f(x) = 4x^3 - 5x + 6.",
                "options": ["12x^2 - 5", "12x^2", "4x^2", "1"],
                "answer": 0,
                "explanation": "Anwendung der Potenzregel ergibt 4*3*x^(3-1) - 5.",
                "taxonomy": "Applying"
            },
            {
                "question": "Berechne die Ableitung der Funktion f(x) = 10.",
                "options": ["0", "1", "10", "x"],
                "answer": 0,
                "explanation": "Die Ableitung einer Konstanten ist 0.",
                "taxonomy": "Applying"
            },
            {
                "question": "Welche Funktion hat die Ableitung 6x?",
                "options": ["x^3", "3x^2", "x^2", "3x"],
                "answer": 1,
                "explanation": "Die Ableitung von 3x^2 ist 6x.",
                "taxonomy": "Analyzing"
            }
        ]
    },
    {
        "skill_level": 4,
        "questions": [
            {
                "question": "Was ist die Ableitung von f(x) = 8?",
                "options": ["0", "8x", "1", "x"],
                "answer": 0,
                "explanation": "Die Ableitung einer Konstanten ist immer 0.",
                "taxonomy": "Remembering"
            },
            {
                "question": "Was ist die Ableitung von f(x) = 2x^3?",
                "options": ["6x^2", "2x^2", "3x^2", "6x"],
                "answer": 0,
                "explanation": "Anwendung der Potenzregel ergibt 3*2*x^(3-1) = 6x^2.",
                "taxonomy": "Remembering"
            },
            {
                "question": "Was ist die Regel zur Ableitung eines Produktes zweier Funktionen?",
                "options": ["Potenzregel", "Produktregel", "Kettenregel", "Quotientenregel"],
                "answer": 1,
                "explanation": "Die Produktregel beschreibt die Ableitung eines Produktes von zwei Funktionen.",
                "taxonomy": "Understanding"
            },
            {
                "question": "Identifiziere die richtige Ableitung von f(x) = x^2 - 3x + 4.",
                "options": ["2x - 3", "x - 3", "2x", "3x - 4"],
                "answer": 0,
                "explanation": "Anwendung der Potenzregel ergibt 2x - 3.",
                "taxonomy": "Understanding"
            },
            {
                "question": "Warum wird die Produktregel nicht bei f(x) = 2x + 3 verwendet?",
                "options": ["Es gibt keine Produkte von Funktionen", "x ist keine Variable", "Die Funktion ist trivial", "Die Funktion hat konstante Terme"],
                "answer": 0,
                "explanation": "Die Funktion enthält keine Produkte zweier Funktionen.",
                "taxonomy": "Understanding"
            },
            {
                "question": "Berechne die Ableitung von f(x) = 5x^3 - 2x^2 + 7.",
                "options": ["15x^2 - 4x", "15x^2", "5x^3", "4x^2"],
                "answer": 0,
                "explanation": "Potenzregel anwenden: 3*5*x^(3-1) - 2*2*x^(2-1).",
                "taxonomy": "Applying"
            },
            {
                "question": "Berechne die Ableitung von f(x) = 4x^4 - x^2.",
                "options": ["16x^3 - 2x", "12x^3", "4x^3", "x^2"],
                "answer": 0,
                "explanation": "Potenzregel: 4*4*x^(4-1) - 2*x^(2-1).",
                "taxonomy": "Applying"
            },
            {
                "question": "Berechne die Ableitung von f(x) = 6x - 3.",
                "options": ["6", "1", "6x", "0"],
                "answer": 0,
                "explanation": "Die Funktion ist linear, daher ist die Ableitung der Koeffizient von x.",
                "taxonomy": "Applying"
            },
            {
                "question": "Identifiziere die Funktion mit der Ableitung 4x^3.",
                "options": ["x^4", "x^3", "2x^3", "4x^2"],
                "answer": 0,
                "explanation": "Die Ableitung von x^4 ist 4x^3.",
                "taxonomy": "Analyzing"
            },
            {
                "question": "Welche Ableitung gehört zur Funktion f(x) = x^2 * (3x + 2)?",
                "options": ["6x^2 + 4x", "x^2 + 3x", "6x^2 + 4", "3x + 2"],
                "answer": 2,
                "explanation": "Produktregel und Potenzregel anwenden für f(x).",
                "taxonomy": "Analyzing"
            }
        ]
    },
    {
        "skill_level": 8,
        "questions": [
            {
                "question": "Was ist die Ableitung von f(x) = 7?",
                "options": ["0", "7", "1", "x"],
                "answer": 0,
                "explanation": "Die Ableitung jeder Konstante ist 0.",
                "taxonomy": "Remembering"
            },
            {
                "question": "Was ist die Ableitung von f(x) = 5x^5?",
                "options": ["25x^4", "5x^4", "10x^5", "x^5"],
                "answer": 0,
                "explanation": "Anwendung der Potenzregel ergibt 5*5*x^(5-1) = 25x^4.",
                "taxonomy": "Remembering"
            },
            {
                "question": "Was ist die Ableitung einer Summe von Funktionen?",
                "options": ["Potenzregel", "Kettenregel", "Summe der Ableitungen", "Ableitung des Produkts"],
                "answer": 2,
                "explanation": "Die Ableitung einer Summe ist die Summe der Ableitungen.",
                "taxonomy": "Understanding"
            },
            {
                "question": "Warum ist die Kettenregel notwendig?",
                "options": ["Um Ableitungen von zusammengesetzten Funktionen zu finden", "Um Konstante zu differenzieren", "Um unbestimmte Integrale zu lösen", "Um lineare Funktionen zu integrieren"],
                "answer": 0,
                "explanation": "Die Kettenregel wird beim Ableiten von zusammengesetzten Funktionen genutzt.",
                "taxonomy": "Understanding"
            },
            {
                "question": "Warum benötigt f(x) = 3x^2 * (x^2 + 1) die Produktregel?",
                "options": ["Funktion besteht aus einem Produkt zweier Funktionen", "Existiert keine Lösung", "Funktion ist linear", "Konstante wird addiert"],
                "answer": 0,
                "explanation": "Produktregel ist notwendig, da es ein Produkt zweier Funktionen ist.",
                "taxonomy": "Analyzing"
            },
            {
                "question": "Berechne die Ableitung von f(x) = 3x^4 - x^3 + 2x^2.",
                "options": ["12x^3 - 3x^2 + 4x", "12x^3", "3x^3 - 2x", "x^2 - x"],
                "answer": 0,
                "explanation": "Jedes Glied getrennt ableiten: Potenzregel anwenden.",
                "taxonomy": "Applying"
            },
            {
                "question": "Berechne die Ableitung von f(x) = (x^2 + 1)^3.",
                "options": ["6x(x^2 + 1)^2", "3(x^2 + 1)^2", "6x^2 + 1", "x^3"],
                "answer": 0,
                "explanation": "Anwendung der Kettenregel: Außendefunktion mit der Ableitung der Innendefunktion multiplizieren.",
                "taxonomy": "Applying"
            },
            {
                "question": "Berechne die Ableitung von f(x) = ln(x) * x^2.",
                "options": ["2x ln(x) + x", "x ln(x) + 2x", "3x ln(x)", "2x ln(x) + x^2"],
                "answer": 1,
                "explanation": "Produktregel anwenden: (ln(x) * 2x) + (1/x * x^2).",
                "taxonomy": "Applying"
            },
            {
                "question": "Analysiere die Ableitung der Funktion f(x) = 2x^3 * sin(x).",
                "options": ["6x^2 sin(x) + 2x^3 cos(x)", "x^2 sin(x)", "6x^2 cos(x)", "sin(x) + x^3"],
                "answer": 0,
                "explanation": "Produktregel anwenden: (6x^2 * sin(x)) + (2x^3 * cos(x)).",
                "taxonomy": "Analyzing"
            },
            {
                "question": "Welche Funktion hat die Ableitung 15x^4 + sin(x)?",
                "options": ["sin(x) + 3x^5", "5x^5 - cos(x)", "3x^5 + x", "x^5"],
                "answer": 1,
                "explanation": "Die Ableitung von 5x^5 ist 25x^4, und die von –cos(x) ist sin(x).",
                "taxonomy": "Analyzing"
            }
        ]
    }
]
    try:
        conn = get_db_connection()
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

    return redirect(url_for('class_details_teacher', class_id=class_id, teacher_id=session.get('teacher_id')))



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
        explanations=explanations
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

    data = request.get_json()
    homework_id = data.get('homework_id')
    student_id = data.get('student_id')
    correct_count = data.get('correct_count')
    incorrect_count = data.get('incorrect_count')

    # Datum der Abgabe speichern
    date_submitted = datetime.now().date()

    try:
        # Ergebnis in der Datenbank speichern
        conn.execute(
            '''
            INSERT INTO HomeworkResults (homework_id, student_id, correct_count, incorrect_count, date_submitted)
            VALUES (?, ?, ?, ?, ?)
            ''',
            (homework_id, student_id, correct_count, incorrect_count, date_submitted)
        )

        conn.commit()
        conn.close()
        return "Ergebnisse erfolgreich gespeichert", 200
    except Exception as e:
        return f"Ein Fehler ist aufgetreten: {str(e)}", 500    


if __name__ == '__main__':
    app.run(debug=True)
