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
    Zur Referenz: Schüler haben ein Skill_level zwischen 1 und 10, wobei 10 das beste/schwierigste ist.
    1. Schwierigkeitsgrad (skill_level 1)
    2. Schwierigkeitsgrad (skill_level 4)
    3. Schwierigkeitsgrad (skill_level 8)

    Hausaufgabenbeschreibung: {description}

    Die Hausaufgabe sollte ausschließlich Multiple-Choice-Fragen enthalten. 
    Jede Frage sollte vier Antwortmöglichkeiten haben und die richtige Antwort sollte als Index (0-basiert) zurückgegeben werden.

    Erstelle insgesamt 15 Fragen: 5 Fragen pro Schwierigkeitsgrad.

    Format:
    [
        {"skill_level": 1, "questions": [
            {"question": "...", "options": ["...", "...", "...", "..."], "answer": 0, "explanation": "..."},
            {"question": "...", "options": ["...", "...", "...", "..."], "answer": 1, "explanation": "..."}
        ]},
        {"skill_level": 4, "questions": [
            {"question": "...", "options": ["...", "...", "...", "..."], "answer": 2, "explanation": "..."}
        ]},
        {"skill_level": 8, "questions": [
            {"question": "...", "options": ["...", "...", "...", "..."], "answer": 3, "explanation": "..."}
        ]}
    ]
    """
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}]
    )
    generated_content = response.choices[0].message['content']

    question_data = json.loads(generated_content)  # Falls das Ergebnis JSON ist

    homework_questions = []
    for idx, row in enumerate(question_data):
        question = dict(row)
        question['options'] = [{'index': i, 'option': opt} for i, opt in enumerate(json.loads(question['options']))]
        homework_questions.append(question)


    conn = get_db_connection()
    cursor = conn.execute(
        'INSERT INTO Homework (class_id, description, title, date_created) VALUES (?, ?, ?, ?)',
        (class_id, description, title, datetime.now())
    )
    homework_id = cursor.lastrowid

    # Speichern der Fragen
    for question_set in homework_questions:
        skill_level = question_set['skill_level']
        for question in question_set['questions']:
            options = json.dumps(question['options'])
            conn.execute(
                '''INSERT INTO HomeworkQuestions
                   (homework_id, skill_level, question, correct_answer, explanation, question_type, options)
                   VALUES (?, ?, ?, ?, ?, 'multiple_choice', ?)''',
                (homework_id, skill_level, question['question'], question['answer'], question['explanation'], options)
            )

    conn.commit()
    conn.close()

    return redirect(url_for('class_details_teacher', class_id=class_id, teacher_id=session['teacher_id']))

@app.route('/create_homework', methods=['POST'])
def create_homework():
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
                "question": "Was beschreibt die Ableitung einer Funktion?",
                "options": [
                    "Die Fläche unter der Funktion",
                    "Die Steigung der Funktion an einem Punkt",
                    "Den Schnittpunkt mit der y-Achse",
                    "Die Anzahl der Nullstellen"
                ],
                "answer": 1,
                "explanation": "Die Ableitung beschreibt die Steigung der Funktion an einem bestimmten Punkt."
            },
            {
                "question": "Was ist die Ableitung von f(x) = 2x?",
                "options": [
                    "f'(x) = 2",
                    "f'(x) = x",
                    "f'(x) = 2x²",
                    "f'(x) = 1/2x"
                ],
                "answer": 0,
                "explanation": "Die Ableitung von 2x ist 2, da der Exponent von x um 1 reduziert wird."
            },
            {
                "question": "Welche Funktion hat eine konstante Ableitung von 3?",
                "options": [
                    "f(x) = 3x",
                    "f(x) = x³",
                    "f(x) = x² + 3",
                    "f(x) = x + 3"
                ],
                "answer": 0,
                "explanation": "Die Funktion f(x) = 3x hat eine konstante Ableitung von 3, da die Steigung konstant ist."
            },
            {
                "question": "Was ist die Ableitung einer konstanten Funktion f(x) = 5?",
                "options": [
                    "f'(x) = 5",
                    "f'(x) = 1",
                    "f'(x) = 0",
                    "f'(x) = x"
                ],
                "answer": 2,
                "explanation": "Die Ableitung einer konstanten Funktion ist immer 0."
            },
            {
                "question": "Welche Aussage ist wahr über die Ableitung einer linearen Funktion?",
                "options": [
                    "Die Ableitung ist immer gleich der Funktion.",
                    "Die Ableitung ist konstant.",
                    "Die Ableitung ist immer null.",
                    "Die Ableitung verändert sich an jedem Punkt."
                ],
                "answer": 1,
                "explanation": "Die Ableitung einer linearen Funktion ist konstant, da die Steigung nicht variiert."
            }
        ]
    },
    {
        "skill_level": 4,
        "questions": [
            {
                "question": "Was ist die Ableitung von f(x) = x²?",
                "options": [
                    "f'(x) = 2x",
                    "f'(x) = x",
                    "f'(x) = 2x²",
                    "f'(x) = 1"
                ],
                "answer": 0,
                "explanation": "Die Ableitung von x² ist 2x, da der Exponent 2 um 1 reduziert wird und der ursprüngliche Exponent als Faktor dient."
            },
            {
                "question": "Berechne die Ableitung von f(x) = 3x³.",
                "options": [
                    "f'(x) = 9x²",
                    "f'(x) = 3x²",
                    "f'(x) = 6x",
                    "f'(x) = 3x³"
                ],
                "answer": 0,
                "explanation": "Die Regel besagt, dass der Exponent mit dem Faktor multipliziert wird, also 3 * 3 = 9 und der Exponent um 1 reduziert wird."
            },
            {
                "question": "Welche der folgenden Funktionen hat die Ableitung f'(x) = 4x³?",
                "options": [
                    "f(x) = x⁴",
                    "f(x) = x³",
                    "f(x) = x⁴ + 1",
                    "f(x) = x³ + 4"
                ],
                "answer": 0,
                "explanation": "Die Funktion f(x) = x⁴ hat die Ableitung f'(x) = 4x³ nach der Potenzregel."
            },
            {
                "question": "Was ist die Ableitung von f(x) = 2x² + 3x?",
                "options": [
                    "f'(x) = 4x + 3",
                    "f'(x) = 2x + 3",
                    "f'(x) = 4x² + 3",
                    "f'(x) = 2x²"
                ],
                "answer": 0,
                "explanation": "Die Ableitung von 2x² ist 4x, und die Ableitung von 3x ist 3."
            },
            {
                "question": "Für welche Funktion gilt: f'(x) = 6x + 2?",
                "options": [
                    "f(x) = 6x² + 2x",
                    "f(x) = 3x² + 2x",
                    "f(x) = 3x² + x",
                    "f(x) = 6x + 2"
                ],
                "answer": 1,
                "explanation": "Die Ableitung von 3x² ist 6x und die Ableitung von 2x ist 2."
            }
        ]
    },
    {
        "skill_level": 8,
        "questions": [
            {
                "question": "Was ist die Ableitung von f(x) = x³ - 2x² + x?",
                "options": [
                    "f'(x) = 3x² - 4x + 1",
                    "f'(x) = 3x² - 4x",
                    "f'(x) = 3x² - 2x + 1",
                    "f'(x) = 2x³ - 4x² + x"
                ],
                "answer": 0,
                "explanation": "Die Ableitung von x³ ist 3x², von -2x² ist -4x, und von x ist 1."
            },
            {
                "question": "Berechne die Ableitung von f(x) = 4x³ - x² + 6.",
                "options": [
                    "f'(x) = 12x² - 2x",
                    "f'(x) = 12x² - x + 6",
                    "f'(x) = 12x³ - 2x",
                    "f'(x) = 4x² - x"
                ],
                "answer": 0,
                "explanation": "Die Ableitung von 4x³ ist 12x², die Ableitung von -x² ist -2x, und die Ableitung der Konstanten 6 ist 0."
            },
            {
                "question": "Welche Funktion hat die Ableitung f'(x) = 5x⁴ - 3x²?",
                "options": [
                    "f(x) = x⁵ - x³",
                    "f(x) = 5x³ - 3x²",
                    "f(x) = x⁵ - x³ + C",
                    "f(x) = x⁴ - x³"
                ],
                "answer": 2,
                "explanation": "Die Funktion f(x) = x⁵ - x³ hat die Ableitung f'(x) = 5x⁴ - 3x². Die Konstante C fällt bei der Ableitung weg."
            },
            {
                "question": "Was ist die Ableitung von f(x) = 2x⁴ - x³ + 5x?",
                "options": [
                    "f'(x) = 8x³ - 3x² + 5",
                    "f'(x) = 8x³ - 3x²",
                    "f'(x) = 2x³ - 3x² + 5",
                    "f'(x) = 8x³ + x² + 5"
                ],
                "answer": 0,
                "explanation": "Die Ableitung von 2x⁴ ist 8x³, von -x³ ist -3x², und von 5x ist 5."
            },
            {
                "question": "Bestimme die Ableitung von f(x) = x³ + 2x² - 3x + 7.",
                "options": [
                    "f'(x) = 3x² + 4x - 3",
                    "f'(x) = 3x² + 4x + 3",
                    "f'(x) = 3x² - 4x + 3",
                    "f'(x) = x² + 2x - 3"
                ],
                "answer": 0,
                "explanation": "Die Ableitung von x³ ist 3x², von 2x² ist 4x, und von -3x ist -3. Die Konstante 7 fällt weg."
            }
        ]
    }
]
    homework_questions = []
    for idx, row in enumerate(question_data):
        question = dict(row)
        question['options'] = [{'index': i, 'option': opt} for i, opt in enumerate(json.loads(question['options']))]
        homework_questions.append(question)


    conn = get_db_connection()
    cursor = conn.execute(
        'INSERT INTO Homework (class_id, description, title, date_created) VALUES (?, ?, ?, ?)',
        (class_id, description, title, datetime.now())
    )
    homework_id = cursor.lastrowid

    # Speichern der Fragen
    for question_set in homework_questions:
        skill_level = question_set['skill_level']
        for question in question_set['questions']:
            options = json.dumps(question['options'])
            conn.execute(
                '''INSERT INTO HomeworkQuestions
                   (homework_id, skill_level, question, correct_answer, explanation, question_type, options)
                   VALUES (?, ?, ?, ?, ?, 'multiple_choice', ?)''',
                (homework_id, skill_level, question['question'], question['answer'], question['explanation'], options)
            )

    conn.commit()
    conn.close()

    return redirect(url_for('class_details_teacher', class_id=class_id, teacher_id=session['teacher_id']))



@app.route('/homework/<int:homework_id>/<int:student_id>')
def view_homework_student(homework_id, student_id):
    import json
    conn = get_db_connection()

    homework = conn.execute(
        'SELECT id, title, description, date_created FROM Homework WHERE id = ?',
        (homework_id,)
    ).fetchone()

    if not homework:
        conn.close()
        return "Fehler: Diese Hausaufgabe existiert nicht.", 404

    question_data = conn.execute(
        'SELECT question, options, correct_answer, explanation FROM HomeworkQuestions WHERE homework_id = ?',
        (homework_id,)
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
    import json
    conn = get_db_connection()

    homework = conn.execute(
        'SELECT id, title, description, date_created FROM Homework WHERE id = ?',
        (homework_id,)
    ).fetchone()

    if not homework:
        return "Fehler: Hausaufgabe nicht gefunden", 404

    question_data = conn.execute(
        'SELECT question, options, correct_answer, explanation FROM HomeworkQuestions WHERE homework_id = ?',
        (homework_id,)
    ).fetchall()

    questions = []
    
    for row in question_data:
        question = dict(row)
        question['options'] = json.loads(question['options'])
        questions.append(question)

    conn.close()

    return render_template(
        'view_homework_teacher.html',
        homework=homework,
        questions=questions,
        class_info={'id': class_id},
        teacher_id=teacher_id,
        correct_answers={idx: q['correct_answer'] for idx, q in enumerate(questions)},
        explanations={idx: q['explanation'] for idx, q in enumerate(questions)}
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
