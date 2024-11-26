from flask import Flask, render_template, request, redirect, url_for, session
import sqlite3
import json
from datetime import datetime
import openai  # ChatGPT API
import os

openai.api_key = os.getenv("TEST")
test = os.getenv("TEST")

print(test)


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
        'SELECT Participants.name, Participants.skill_level '
        'FROM Participants '
        'JOIN ClassMembers ON Participants.id = ClassMembers.student_id '
        'WHERE ClassMembers.class_id = ?', (class_id,)
    ).fetchall()

    # Hausaufgaben der Klasse abrufen
    homework_list = conn.execute(
        'SELECT id, description, date_created FROM Homework WHERE class_id = ?',
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

    conn.execute('INSERT INTO ClassMembers (class_id, student_id) VALUES (?, ?)', (class_id, student_id))
    conn.commit()
    conn.close()

    return redirect(url_for('student_dashboard', student_id=student_id))


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
        'SELECT Participants.name, Participants.skill_level '
        'FROM Participants '
        'WHERE Participants.id = ?', (student_id,)
    ).fetchone()

    # Hausaufgaben der Klasse abrufen
    homework_list = conn.execute(
        'SELECT id, description, date_created FROM Homework WHERE class_id = ?',
        (class_id,)
    ).fetchall()

    conn.close()

    return render_template(
        'class_details_student.html',
        class_info=class_info,
        student=student,
        student_id=student_id,
        homework_list=homework_list
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


# @app.route('/create_homework', methods=['POST'])
# def create_homework():
    class_id = request.form['class_id']
    description = request.form['description']

    # Hole Kursinformationen
    conn = get_db_connection()
    class_info = conn.execute('SELECT * FROM Classes WHERE id = ?', (class_id,)).fetchone()

    # Generiere Hausaufgaben mit ChatGPT
    prompt = f"""
    Erstelle 3 Versionen einer Hausaufgabe für das Fach {class_info['subject']} in der Jahrgangsstufe {class_info['grade_level']}:
    Zur Refernez, Schüler haben ein Skill_level zwische 1 und 10 wobei 10 das beste/scgwierigste ist
    1. Schwierigkeitsgrad (skill_level 1)
    2. Schwierigkeitsgrad (skill_level 4)
    3. Schwierigkeitsgrad (skill_level 8)
    Hausaufgabenbeschreibung: {description}
    Die Hausaufgabe sollte Multiple-Choice-Fragen und offene Fragen enthalten.
    Gib auch die richtigen Antworten und Erklärungen zurück.

    Es soll insgesamt 15 fragen geben, 5 zu jedem Schwierigkeitsgrad
    Bitte selbst wenn die Antwort eine Zahl ist wie 14x dennoch alles als "type": "text"

    Format:
    [
        {"skill_level": 1, "questions": [
            {"question": "...", "options": ["...", "...", "...", "..."], "answer": "...", "explanation": "...", "type": "multiple_choice"},
            {"question": "...", "answer": "...", "explanation": "...", "type": "text"}
        ]},
        {"skill_level": 4, "questions": [
            {"question": "...", "answer": "...", "explanation": "...", "type": "text"}
        ]},
        {"skill_level": 8, "questions": [
            {"question": "...", "options": ["...", "...", "...", "..."], "answer": "...", "explanation": "...", "type": "multiple_choice"}
        ]}
    ]
    """
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}]
    )
    generated_content = response.choices[0].message['content']

    homework_questions = json.loads(generated_content)  # Falls das Ergebnis JSON ist

    # Speichere Hausaufgabe in der Datenbank
    cursor = conn.execute('INSERT INTO Homework (class_id, description, date_created) VALUES (?, ?, ?)',
                           (class_id, description, datetime.now()))
    homework_id = cursor.lastrowid

    # Speichere die generierten Fragen
    for question_set in homework_questions:
        for question in question_set['questions']:
            conn.execute(
                'INSERT INTO HomeworkQuestions (homework_id, skill_level, question, correct_answer, explanation, question_type) '
                'VALUES (?, ?, ?, ?, ?, ?)',
                (homework_id, question_set['skill_level'], question['question'], question['answer'],
                 question.get('explanation', ''), question.get('type', 'text'))
            )
    conn.commit()
    conn.close()

    return redirect(url_for('class_details_teacher', class_id=class_id, teacher_id=session['teacher_id']))

@app.route('/create_homework', methods=['POST'])
def create_homework():
    class_id = request.form['class_id']
    description = request.form['description']

    # Simulierte Hausaufgaben-Daten (später durch API-Aufruf ersetzt)
    # Simulierte Hausaufgaben-Daten (später durch API-Aufruf ersetzt)
    homework_questions = [
        {"skill_level": 1, "questions": [
            {"question": "Was ist die Ableitung einer konstanten Funktion?", 
            "options": ["0", "1", "f(x)", "x"], 
            "answer": "0", 
            "explanation": "Die Ableitung einer konstanten Funktion ist immer Null.", 
            "type": "multiple_choice"},

            {"question": "Welches Symbol wird oft für die Ableitung einer Funktion verwendet?", 
            "options": ["f'", "Δx", "f(x)", "f''"], 
            "answer": "f'", 
            "explanation": "Das Symbol f' wird oft verwendet, um die Ableitung einer Funktion f(x) darzustellen.", 
            "type": "multiple_choice"},

            {"question": "Die Ableitung beschreibt die ______ der Funktion zu einem Punkt.", 
            "options": ["Division", "Multiplikation", "Steigung", "Addition"], 
            "answer": "Steigung", 
            "explanation": "Die Ableitung beschreibt die Änderungsrate einer Funktion an einem bestimmten Punkt.", 
            "type": "multiple_choice"},

            {"question": "Schreiben Sie die Ableitung der linearen Funktion f(x) = 3x.", 
            "answer": "3", 
            "explanation": "Die Ableitung einer linearen Funktion f(x) = mx ist konstant und entspricht dem Koeffizienten m.", 
            "type": "text"},

            {"question": "Welche geometrische Bedeutung hat die Ableitung an einem Punkt?", 
            "options": ["Tangentenlänge", "Winkelsumme", "Tangentensteigung", "Fläche"], 
            "answer": "Tangentensteigung", 
            "explanation": "Die Ableitung an einem Punkt entspricht der Steigung der Tangente an die Kurve in diesem Punkt.", 
            "type": "multiple_choice"}
        ]},
        {"skill_level": 4, "questions": [
            {"question": "Wie lautet die Ableitung von f(x) = x^2?", 
            "answer": "2x", 
            "explanation": "Die Potenzregel besagt, dass die Ableitung von x^n gleich n*x^(n-1) ist.", 
            "type": "text"},

            {"question": "Bestimmen Sie die Ableitung von f(x) = 5x + 3.", 
            "answer": "5", 
            "explanation": "Die Ableitung einer linearen Funktion ax + b ist a.", 
            "type": "number"},

            {"question": "Was ist die Ableitung von f(x) = x^3?", 
            "answer": "3x^2", 
            "explanation": "Anwendung der Potenzregel: Der Exponent wird als Faktor vorangestellt und der Exponent um eins reduziert.", 
            "type": "text"},

            {"question": "Welche Regel verwenden Sie zum Ableiten von f(x) = 7?", 
            "answer": "Die Regel der konstanten Funktion.", 
            "explanation": "Die Ableitung einer konstanten Funktion ist immer Null.", 
            "type": "text"},

            {"question": "Warum ist die Ableitung von f(x) = 2x^2 + 3 nicht konstant?", 
            "answer": "Sie ist nicht konstant, da sie von x abhängt. Die Ableitung ist 4x.", 
            "explanation": "Die Ableitung ändert sich mit x, da die Potenzregel auf den polynomiellen Teil angewendet wird.", 
            "type": "text"}
        ]},
        {"skill_level": 8, "questions": [
            {"question": "Bestimmen Sie die Ableitung von f(x) = 4x^4.", 
            "options": ["12x^3", "16x^3", "4x^5", "8x^3"], 
            "answer": "16x^3", 
            "explanation": "Durch die Potenzregel erhält man die Ableitung, indem man den Exponenten als Faktor multipliziert und den Exponenten um eins verringert.", 
            "type": "multiple_choice"},

            {"question": "Die Ableitung von f(x) = x^2 + 2x + 1 ist:", 
            "options": ["2x + 2", "x + 2", "2x", "4x + 1"], 
            "answer": "2x + 2", 
            "explanation": "Die Ableitung der Summe ist die Summe der Ableitungen der Einzelfunktionen.", 
            "type": "multiple_choice"},

            {"question": "Was ist die Ableitung von f(x) = x^5?", 
            "answer": "5x^4", 
            "explanation": "Anwendung der Potenzregel für Ableitungen.", 
            "type": "number"},

            {"question": "Die Ableitung der Funktion f(x) = 3x^3 - 4x lautet:", 
            "options": ["3x^2 - 4", "9x^2 - 4", "6x^2 - 4x", "9x^2"], 
            "answer": "9x^2 - 4", 
            "explanation": "Leiten Sie jeden Term der Funktion einzeln ab und summieren Sie die Ergebnisse.", 
            "type": "multiple_choice"},

            {"question": "Warum ist die Ableitung der Funktion f(x) = x^7 - x korrekt als 7x^6 - 1 angegeben?", 
            "options": ["Ja, korrekt", "Nein, sollte 7x^6 + 1 sein", "Nein, sollte -7x^6 sein", "Nein, Ableitung ist konstant"], 
            "answer": "Ja, korrekt", 
            "explanation": "Die Potenzregel wird angewendet, jeder Exponent wird einzeln bearbeitet.", 
            "type": "multiple_choice"}
        ]}
    ]

    # Speichern in der Datenbank
    conn = get_db_connection()
    cursor = conn.execute('INSERT INTO Homework (class_id, description, date_created) VALUES (?, ?, ?)',
                           (class_id, description, datetime.now()))
    homework_id = cursor.lastrowid

    for question_set in homework_questions:
        for question in question_set['questions']:
            options = json.dumps(question.get('options', []))  # Konvertiere die Optionsliste in einen JSON-String
            conn.execute(
                '''INSERT INTO HomeworkQuestions 
                   (homework_id, skill_level, question, correct_answer, explanation, question_type, options) 
                   VALUES (?, ?, ?, ?, ?, ?, ?)''',
                (homework_id, question_set['skill_level'], question['question'], question['answer'],
                 question['explanation'], question['type'], options)
            )
    conn.commit()
    conn.close()

    return redirect(url_for('class_details_teacher', class_id=class_id, teacher_id=session['teacher_id']))

@app.route('/homework/<int:homework_id>/<int:student_id>')
def view_homework_student(homework_id, student_id):
    conn = get_db_connection()
    
    # Klasseninformation abrufen
    class_info = conn.execute(
        'SELECT Classes.id, Classes.class_name, Classes.subject, Teachers.name AS teacher_name '
        'FROM Classes '
        'JOIN Teachers ON Classes.teacher_id = Teachers.id '
        'JOIN Homework ON Classes.id = Homework.class_id '
        'WHERE Homework.id = ?', (homework_id,)
    ).fetchone()

    # Sicherstellen, dass die Klasseninformationen erfolgreich geladen werden
    if not class_info:
        conn.close()
        return "Fehler: Diese Klasse existiert nicht.", 404

    student = conn.execute('SELECT skill_level FROM Participants WHERE id = ?', (student_id,)).fetchone()
    student_skill_level = student['skill_level'] if student else 0

    homework = conn.execute(
        'SELECT id, description, date_created, class_id FROM Homework WHERE id = ?',
        (homework_id,)
    ).fetchone()

    if not homework:
        conn.close()
        return "Fehler: Diese Hausaufgabe existiert nicht.", 404

    question_data = conn.execute(
        'SELECT question, question_type, correct_answer, explanation, options FROM HomeworkQuestions WHERE homework_id = ? AND skill_level <= ?',
        (homework_id, student_skill_level)
    ).fetchall()

    questions = []
    correct_answers = {}
    explanations = {}

    for idx, row in enumerate(question_data):
        question = dict(row)
        question['options'] = json.loads(question['options']) if question['options'] else []
        questions.append(question)
        
        correct_answers[idx + 1] = question['correct_answer']
        explanations[idx + 1] = question['explanation']
    
    conn.close()

    return render_template(
        'view_homework_student.html',
        class_info=class_info,  # Übergibt die Klasseninformationen
        homework=homework,
        questions=questions,
        student_id=student_id,
        correct_answers=correct_answers,
        explanations=explanations
    )

@app.route('/submit_homework', methods=['POST'])
def submit_homework():
    student_id = request.form['student_id']
    homework_id = request.form['homework_id']
    class_id = request.form['class_id']

    answers = []
    correct_count = 0
    incorrect_count = 0

    for key, value in request.form.items():
        if key.startswith("answer_"):
            question_index = int(key.split("_")[1])
            if correct_answers[question_index] == value:
                correct_count += 1
            else:
                incorrect_count += 1

    print(f"Student {student_id} hat {correct_count} richtige und {incorrect_count} falsche Antworten.")

    conn = get_db_connection()

    # Speichere die Ergebnisse in der Datenbank in einer hypothetischen Tabelle 'HomeworkResults'
    conn.execute(
        'INSERT INTO HomeworkResults (homework_id, student_id, correct_count, incorrect_count) '
        'VALUES (?, ?, ?, ?)',
        (homework_id, student_id, correct_count, incorrect_count)
    )
    conn.commit()
    conn.close()

    return redirect(url_for('class_details_student', class_id=class_id, student_id=student_id))


@app.route('/view_homework_teacher/<int:homework_id>/<int:class_id>/<int:teacher_id>')
def view_homework_teacher(homework_id, class_id, teacher_id):
    conn = get_db_connection()
    
    homework = conn.execute('SELECT id, description, date_created FROM Homework WHERE id = ?', (homework_id,)).fetchone()
    if not homework:
        conn.close()
        return "Fehler: Diese Hausaufgabe existiert nicht.", 404

    question_data = conn.execute('SELECT question, question_type, correct_answer, explanation, options FROM HomeworkQuestions WHERE homework_id = ?', (homework_id,)).fetchall()
    
    questions = []
    correct_answers = {}
    explanations = {}

    for idx, row in enumerate(question_data):
        question = dict(row)
        question['options'] = json.loads(question['options']) if question['options'] else []
        questions.append(question)
        
        correct_answers[idx + 1] = question['correct_answer']
        explanations[idx + 1] = question['explanation']
    
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


if __name__ == '__main__':
    app.run(debug=True)
