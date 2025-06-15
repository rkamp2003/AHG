import sqlite3

DB_PATH = 'ahg/database.db'  # Passe den Pfad ggf. an

def fill_new_class_skill_level():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # Setze new_class_skill_level überall auf 3
    c.execute("UPDATE HomeworkOpenQuestionsResults SET new_skill_level = 4")
    conn.commit()
    conn.close()
    print("Alle new_class_skill_level auf 3 gesetzt.")

if __name__ == "__main__":
    fill_new_class_skill_level()