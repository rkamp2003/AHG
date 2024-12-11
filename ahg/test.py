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