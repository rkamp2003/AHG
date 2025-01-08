import requests
import os
import json

def create_homework_with_api():
    # API-Schlüssel aus Umgebungsvariablen oder festlegen
    api_key = os.getenv("CHATGPT_API_KEY")  # Alternativ: direkt angeben, z. B. "dein-api-schlüssel"

    # Prompt für die Hausaufgabe
    prompt = """
    Erstelle Hausaufgabe für das Fach Mathematik in der Jahrgangsstufe 10:
    Zur Referenz: Schüler haben ein Skill_level zwischen 1 und 10, wobei 10 das beste/schwierigste ist.

    Hausaufgabenbeschreibung: Einführung in die Differentialrechnung.

    Orientiert an Blooms Taxonomy sollen die Fragen in die Aufgabentypen Remembering Understanding Applying Analyzing Evaluating Creating aufgeteilt werden.
    1. Schwierigkeitsgrad (skill_level 1) 3 * Remembering, 3 * Understanding, 3 * Applying, 1 * Analyzing
    2. Schwierigkeitsgrad (skill_level 4) 2 * Remembering, 3 * Understanding, 3 * Applying, 2 * Analyzing
    3. Schwierigkeitsgrad (skill_level 8) 2 * Remembering, 2 * Understanding, 3 * Applying, 3 * Analyzing
    Die Hausaufgabe sollte ausschließlich Multiple-Choice-Fragen enthalten. 
    Jede Frage sollte vier Antwortmöglichkeiten haben und die richtige Antwort sollte als Index (0-basiert) zurückgegeben werden.

    Erstelle insgesamt 5 Fragen für Testzwecke.
    Bitte nur mit JSON-Inhalt antworten in dem folgenden Format:
    Format:
    [
        {"skill_level": 1, "questions": [
            {"question": "...", "options": ["...", "...", "...", "..."], "answer": 0, "explanation": "...", "taxonomy": "..."}
        ]}
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
        "model": "gpt-4o-mini",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7
    }

    
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

     

        print(question_data)

        print("Generierte Fragen:")
        for q in question_data:
            print(q)

        return question_data
    else:
        print(f"Fehler: {response.status_code} - {response.text}")
        return None


create_homework_with_api()



question_data = [{'skill_level': 1, 'questions': [{'question': 'Was ist die Ableitung von f(x) = x^2?', 'options': ['2x', 'x', 'x^2', 'x^3'], 'answer': 0, 'explanation': 'Die Ableitung von x^2 ist 2x, basierend auf der Potenzregel.', 'taxonomy': 'Remembering'}, {'question': 'Welches Symbol wird häufig für die Ableitung verwendet?', 'options': ['∫', 'd/dx', 'Σ', 'lim'], 'answer': 1, 'explanation': 'Das Symbol d/dx steht für die Ableitung einer Funktion bezüglich x.', 'taxonomy': 'Remembering'}, {'question': 'Was beschreibt die Steigung einer Funktion an einem Punkt?', 'options': ['Die Funktion selbst', 'Die Ableitung', 'Der Schnittpunkt mit der y-Achse', 'Die Integrationskonstante'], 'answer': 1, 'explanation': 'Die Ableitung beschreibt die Steigung der Funktion an einem bestimmten Punkt.', 'taxonomy': 'Remembering'}, {'question': 'Welcher der folgenden Begriffe bezieht sich auf die Untersuchung der Änderungen in einer Funktion?', 'options': ['Differentialrechnung', 'Integralrechnung', 'Algebra', 'Geometrie'], 'answer': 0, 'explanation': 'Die Differentialrechnung beschäftigt sich mit der Untersuchung von Änderungen in Funktionen.', 'taxonomy': 'Understanding'}, {'question': 'Was ist die Bedeutung der Ableitung an einem Punkt?', 'options': ['Es ist der Funktionswert', 'Es ist die maximale Steigung', 'Es ist die Geschwindigkeit der Veränderung', 'Es ist die Fläche unter der Kurve'], 'answer': 2, 'explanation': 'Die Ableitung an einem Punkt gibt die Geschwindigkeit der Veränderung der Funktion an diesem Punkt an.', 'taxonomy': 'Understanding'}, {'question': "Wenn f(x) = 3x^3, was ist f'(x)?", 'options': ['3x^2', '9x^2', '6x', '3x^3'], 'answer': 1, 'explanation': 'Die Ableitung von 3x^3 ist 9x^2, gemäß der Potenzregel.', 'taxonomy': 'Understanding'}, {'question': 'Berechne die Ableitung von f(x) = 5x - 2.', 'options': ['5', '-2', '0', '10'], 'answer': 0, 'explanation': 'Die Ableitung von 5x - 2 ist konstant 5.', 'taxonomy': 'Applying'}, {'question': 'Wie lautet die Ableitung von f(x) = sin(x)?', 'options': ['cos(x)', '-cos(x)', 'sin(x)', 'tan(x)'], 'answer': 0, 'explanation': 'Die Ableitung von sin(x) ist cos(x).', 'taxonomy': 'Applying'}, {'question': 'Berechne die Ableitung von f(x) = x^2 + 3x + 1.', 'options': ['2x + 3', 'x + 3', 'x^2 + 3', '3x + 1'], 'answer': 0, 'explanation': 'Die Ableitung ist 2x + 3, basierend auf den Ableitungsregeln.', 'taxonomy': 'Applying'}, {'question': 'Bestimme, ob die Funktion f(x) = x^2 eine maximale oder minimale Steigung bei x=0 hat.', 'options': ['Maximale Steigung', 'Minimale Steigung', 'Keine Steigung', 'Unbestimmt'], 'answer': 1, 'explanation': "Die Ableitung f'(x) = 2x ist bei x=0 gleich 0, was auf einen Minimalpunkt hinweist.", 'taxonomy': 'Analyzing'}]}]




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
