from flask import Flask, render_template, request, redirect, url_for, session
import sqlite3
import os


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
    classes = conn.execute('SELECT * FROM Classes WHERE teacher_id = ?', (teacher_id,)).fetchall()
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

    conn = get_db_connection()
    conn.execute('INSERT INTO Classes (class_name, subject, teacher_id) VALUES (?, ?, ?)',
                 (class_name, subject, teacher_id))
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

    # Liste der Schüler abrufen (optional, je nach Anforderung)
    students = conn.execute(
        'SELECT Participants.name, Participants.skill_level '
        'FROM Participants '
        'JOIN ClassMembers ON Participants.id = ClassMembers.student_id '
        'WHERE ClassMembers.class_id = ?', (class_id,)
    ).fetchall()

    conn.close()

    print("class_info:", class_info)  # Debugging: Verifiziere Class Info

    return render_template('class_details_teacher.html', class_info=class_info, students=students, teacher_id=teacher_id)


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
    conn.execute('INSERT INTO Participants (name, email, password) VALUES (?, ?, ?)', (name, email, password))
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

    conn.close()

    print("class_info:", class_info)  # Debugging-Info
    print("class_id:", class_info['id']) if class_info else print("class_info ist None")

    return render_template('class_details_student.html', class_info=class_info, student=student, student_id=student_id)



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




if __name__ == '__main__':
    app.run(debug=True)
