from flask import Flask, render_template, request, redirect, url_for
import sqlite3


app = Flask(__name__)

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
    email = request.form.get('email')  # Verwende .get(), um Fehler zu vermeiden
    password = request.form.get('password')

    if not email or not password:
        return "Fehler: Bitte füllen Sie alle Felder aus.", 400

    conn = get_db_connection()
    teacher = conn.execute('SELECT * FROM Teachers WHERE email = ? AND password = ?', (email, password)).fetchone()
    conn.close()

    if teacher:
        return redirect(url_for('teacher_dashboard', teacher_id=teacher['id']))
    else:
        return "Anmeldedaten ungültig. Bitte versuchen Sie es erneut."
    
# Lehrer-Dashboard
@app.route('/teacher_dashboard/<int:teacher_id>')
def teacher_dashboard(teacher_id):
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
    
    # Informationen zur Klasse und zum Lehrer abrufen
    class_info = conn.execute(
        'SELECT Classes.class_name, Classes.subject, Teachers.name AS teacher_name '
        'FROM Classes '
        'JOIN Teachers ON Classes.teacher_id = Teachers.id '
        'WHERE Classes.id = ?', (class_id,)
    ).fetchone()

    # Liste der Schüler in dieser Klasse abrufen
    students = conn.execute(
        'SELECT Participants.name, Participants.skill_level '
        'FROM Participants '
        'JOIN ClassMembers ON Participants.id = ClassMembers.student_id '
        'WHERE ClassMembers.class_id = ?', (class_id,)
    ).fetchall()

    conn.close()

    return render_template('class_details_teacher.html', class_info=class_info, students=students, teacher_id=teacher_id)


### STUDENT ###


# Schüler-Login
@app.route('/login_student', methods=['POST'])
def login_student():
    email = request.form['email']
    password = request.form['password']

    if not email or not password:
        return "Fehler: Bitte füllen Sie alle Felder aus.", 400

    conn = get_db_connection()
    student = conn.execute('SELECT * FROM Participants WHERE email = ? AND password = ?', (email, password)).fetchone()
    conn.close()

    if student:
        return redirect(url_for('student_dashboard', student_id=student['id']))
    else:
        return "Schüler-ID nicht gefunden. Bitte versuchen Sie es erneut."
    

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


@app.route('/student_dashboard/<int:student_id>')
def student_dashboard(student_id):
    conn = get_db_connection()
    student = conn.execute('SELECT * FROM Participants WHERE id = ?', (student_id,)).fetchone()
    joined_classes = conn.execute(
        'SELECT Classes.* FROM Classes JOIN ClassMembers ON Classes.id = ClassMembers.class_id WHERE ClassMembers.student_id = ?',
        (student_id,)
    ).fetchall()
    
    all_classes = conn.execute('SELECT id, class_name FROM Classes').fetchall()
    all_classes_dict = [{'id': class_['id'], 'class_name': class_['class_name']} for class_ in all_classes]
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
        'SELECT Classes.class_name, Classes.subject, Teachers.name AS teacher_name '
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

    return render_template('class_details_student.html', class_info=class_info, student=student, student_id=student_id)


if __name__ == '__main__':
    app.run(debug=True)
