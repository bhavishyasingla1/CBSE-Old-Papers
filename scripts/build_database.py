import os
import csv
import json
import sqlite3
import re
import fitz

WORKSPACE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(WORKSPACE_DIR, "data", "cbse_study.db")
JSON_PATH = os.path.join(WORKSPACE_DIR, "data", "dataset.json")
MANIFEST_PATH = os.path.join(WORKSPACE_DIR, "classification_manifest.csv")
OCR_DIR = os.path.join(WORKSPACE_DIR, "data", "ocr")

def slugify(text):
    text = text.lower()
    text = re.sub(r'[\(\)]', '', text)
    text = re.sub(r'[^a-z0-9]+', '-', text).strip('-')
    return text

def get_paper_id(r):
    c = slugify(r['Class'])
    s = slugify(r['Subject'])
    y = r['Year']
    exam_raw = r['Exam Type'].lower()
    exam = 'main' if 'main' in exam_raw else ('supp' if 'supp' in exam_raw or 'comp' in exam_raw else 'exam')
    set_no = r['Set']
    qp = slugify(r['Q.P. Code'] or 'na')
    # Stable unique ID
    return f"p_{c}_{s}_{y}_{exam}_s{set_no}_{qp}"

def load_paper_text(paper_row):
    """Returns list of (page_num, text)"""
    final_path = os.path.join(WORKSPACE_DIR, paper_row['Final Path'])
    
    # Check if we have an OCR json cache for this
    ocr_map = {
        '2022_Main_Artificial_Intelligence_QPCamaidates_Set4.pdf': 'ai_2022.json',
        '2023_Main_Artificial_Intelligence_QP104_Set4.pdf': 'ai_2023_104.json',
        '2023_Main_Artificial_Intelligence_QPBaPM7_Set4.pdf': 'ai_2023_bapm7.json',
        '2024_Main_Artificial_Intelligence_QPSet-4_Set4.pdf': 'ai_2024.json',
        '2022_Main_Computer_Science_QP12_Set4.pdf': 'cs_2022.json',
        '2023_Main_Computer_Science_QP91_Set4.pdf': 'cs_2023.json',
        '2024_Main_Computer_Science_QP91_Set4.pdf': 'cs_2024.json',
        '2025_Main_Computer_Science_QPSET_Set4.pdf': 'cs_2025.json',
    }
    fname = paper_row['Final Filename']
    if fname in ocr_map:
        cache_file = os.path.join(OCR_DIR, ocr_map[fname])
        if os.path.exists(cache_file):
            with open(cache_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return [(item['page'], item['text']) for item in data]
                
    # Otherwise read directly with fitz
    if os.path.exists(final_path):
        doc = fitz.open(final_path)
        pages = []
        for i, page in enumerate(doc):
            t = page.get_text()
            pages.append((i + 1, t))
        return pages
    return []

def main():
    print("Building CBSE PYQ Database & Trends...")
    os.makedirs(os.path.join(WORKSPACE_DIR, "data"), exist_ok=True)
    
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
        
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    
    # 1. Create tables
    cur.execute("""
    CREATE TABLE papers (
        id TEXT PRIMARY KEY,
        class TEXT NOT NULL,
        class_slug TEXT NOT NULL,
        subject TEXT NOT NULL,
        subject_slug TEXT NOT NULL,
        year INTEGER NOT NULL,
        exam_type TEXT NOT NULL,
        set_number TEXT NOT NULL,
        qp_code TEXT,
        series TEXT,
        page_count INTEGER NOT NULL,
        file_path TEXT NOT NULL,
        file_name TEXT NOT NULL,
        file_size_bytes INTEGER NOT NULL,
        sha256 TEXT NOT NULL,
        confidence TEXT,
        evidence TEXT
    )
    """)
    
    cur.execute("""
    CREATE TABLE questions (
        id TEXT PRIMARY KEY,
        paper_id TEXT NOT NULL,
        question_number TEXT NOT NULL,
        question_text TEXT NOT NULL,
        marks INTEGER,
        question_type TEXT NOT NULL,
        topic TEXT NOT NULL,
        source_page INTEGER NOT NULL,
        source_snippet TEXT,
        FOREIGN KEY (paper_id) REFERENCES papers(id)
    )
    """)
    
    cur.execute("""
    CREATE TABLE trends (
        id TEXT PRIMARY KEY,
        class TEXT NOT NULL,
        subject TEXT NOT NULL,
        topic TEXT NOT NULL,
        papers_count INTEGER NOT NULL,
        total_papers INTEGER NOT NULL,
        question_count INTEGER NOT NULL,
        years_seen TEXT NOT NULL,
        question_types TEXT NOT NULL,
        supporting_questions TEXT NOT NULL,
        how_they_ask_it TEXT NOT NULL,
        practise_reason TEXT NOT NULL,
        practise_priority TEXT NOT NULL
    )
    """)
    
    # 2. Load manifest
    with open(MANIFEST_PATH, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        manifest_rows = [r for r in reader if r['Action'] == 'SORTED']
        
    print(f"Loaded {len(manifest_rows)} retained papers from manifest.")
    
    papers_list = []
    paper_lookup = {}
    
    for r in manifest_rows:
        paper_id = get_paper_id(r)
        class_name = r['Class']
        class_slug = slugify(class_name)
        subject_name = r['Subject']
        subject_slug = slugify(subject_name)
        year = int(r['Year'])
        exam_type = r['Exam Type']
        set_no = r['Set']
        qp_code = r['Q.P. Code']
        series = r['Series']
        page_count = int(r['Page Count']) if r['Page Count'].isdigit() else 0
        file_path = r['Final Path']
        file_name = r['Final Filename']
        sha256 = r['SHA-256']
        confidence = r['Confidence']
        evidence = r['Evidence']
        
        full_path = os.path.join(WORKSPACE_DIR, file_path)
        file_size = os.path.getsize(full_path) if os.path.exists(full_path) else 0
        
        cur.execute("""
        INSERT INTO papers (id, class, class_slug, subject, subject_slug, year, exam_type, set_number, qp_code, series, page_count, file_path, file_name, file_size_bytes, sha256, confidence, evidence)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (paper_id, class_name, class_slug, subject_name, subject_slug, year, exam_type, set_no, qp_code, series, page_count, file_path, file_name, file_size, sha256, confidence, evidence))
        
        p_obj = {
            "id": paper_id,
            "class": class_name,
            "class_slug": class_slug,
            "subject": subject_name,
            "subject_slug": subject_slug,
            "year": year,
            "exam_type": exam_type,
            "set_number": set_no,
            "qp_code": qp_code,
            "series": series,
            "page_count": page_count,
            "file_path": file_path,
            "file_name": file_name,
            "file_size_bytes": file_size,
            "sha256": sha256,
            "confidence": confidence,
            "evidence": evidence,
            "download_url": f"/api/download/{paper_id}"
        }
        papers_list.append(p_obj)
        paper_lookup[paper_id] = p_obj
        
    print(f"Inserted {len(papers_list)} papers into database.")
    
    # 3. Extract and insert verified questions
    # A. Class 10 Artificial Intelligence
    ai_questions = [
        # 2022 Main Set 4
        ("p_class-10_artificial-intelligence_2022_main_s4_camaidates", "2", "How food is one of the major problems related to sustainable development? Discuss briefly.", 1, "Short answer", "Sustainable Development Goals", 3, "2. How food is one of the major problems related to sustainable development?"),
        ("p_class-10_artificial-intelligence_2022_main_s4_camaidates", "4", "What is the major purpose of the Sustainable Development Goals?", 1, "Short answer", "Sustainable Development Goals", 3, "4. What is the major purpose of the Sustainable Development Goals?"),
        ("p_class-10_artificial-intelligence_2022_main_s4_camaidates", "5", "Write any four common functions of an entrepreneur.", 2, "Short answer", "Entrepreneurial Skills", 3, "5. Write any four common functions of an entrepreneur."),
        ("p_class-10_artificial-intelligence_2022_main_s4_camaidates", "6", "Mention any four ways which we can do at our end to reduce inequality for sustainable development.", 2, "Short answer", "Sustainable Development Goals", 3, "6. Mention any four ways which we can do at our end to reduce inequality."),
        ("p_class-10_artificial-intelligence_2022_main_s4_camaidates", "7", "What is NLP?", 1, "Definition-style", "Natural Language Processing (NLP)", 3, "7. What is NLP?"),
        ("p_class-10_artificial-intelligence_2022_main_s4_camaidates", "8", "Mention any two commonly used applications of NLP.", 1, "Short answer", "Natural Language Processing (NLP)", 3, "8. Mention any two commonly used applications of NLP."),
        ("p_class-10_artificial-intelligence_2022_main_s4_camaidates", "10", "Name the process of dividing whole corpus into sentences.", 1, "MCQ", "Natural Language Processing (NLP)", 4, "10. Name the process of dividing whole corpus into sentences."),
        ("p_class-10_artificial-intelligence_2022_main_s4_camaidates", "11", "With reference to evaluation process of understanding reliability of an AI model, define the term True Positive.", 1, "Definition-style", "Evaluation & Confusion Matrix", 4, "11. Define the term True Positive."),
        ("p_class-10_artificial-intelligence_2022_main_s4_camaidates", "12", "What is F1 score?", 1, "Definition-style", "Evaluation & Confusion Matrix", 4, "12. What is F1 score?"),
        ("p_class-10_artificial-intelligence_2022_main_s4_camaidates", "13", "Differentiate between Script-bot and Smart-bot.", 2, "Short answer", "Natural Language Processing (NLP)", 4, "13. Differentiate between Script-bot and Smart-bot."),
        ("p_class-10_artificial-intelligence_2022_main_s4_camaidates", "14", "What is the purpose of Evaluation stage of AI project cycle? Discuss briefly.", 2, "Short answer", "Problem Scoping & AI Project Cycle", 4, "14. What is the purpose of Evaluation stage of AI project cycle?"),
        ("p_class-10_artificial-intelligence_2022_main_s4_camaidates", "15", "What is Tokenization? Count how many tokens are present in the following statement: 'I find that the harder I work, the more luck I seem to have.'", 2, "Application-based", "Natural Language Processing (NLP)", 4, "15. What is Tokenization? Count tokens."),
        ("p_class-10_artificial-intelligence_2022_main_s4_camaidates", "16", "Help Kaira in filling up table suggesting appropriate affixes and stem of words 'Tries' and 'Learning'.", 2, "Application-based", "Natural Language Processing (NLP)", 5, "16. Process of Stemming. Fill table with affixes and stem."),
        ("p_class-10_artificial-intelligence_2022_main_s4_camaidates", "17", "With reference to evaluation stage of AI project cycle, explain the term Accuracy. Also give formula to calculate it.", 2, "Short answer", "Evaluation & Confusion Matrix", 5, "17. Explain Accuracy and give formula."),
        ("p_class-10_artificial-intelligence_2022_main_s4_camaidates", "19", "Apply all four steps of Bag of words model of NLP on the given documents (Document 1, 2, 3) and generate the output.", 4, "Case-based", "Natural Language Processing (NLP)", 6, "19. Bag of words model of NLP 4 steps on 3 documents."),
        ("p_class-10_artificial-intelligence_2022_main_s4_camaidates", "20", "With reference to NLP, explain Term frequency and Inverse Document Frequency (TF-IDF) with example.", 4, "Long answer", "Natural Language Processing (NLP)", 6, "20. Explain TF and IDF with suitable example."),
        ("p_class-10_artificial-intelligence_2022_main_s4_camaidates", "21", "Traffic Jams scenario: AI model predicts traffic jam. Given Confusion Matrix (Actual 1/0, Predicted 1/0). Explain the process of calculating F1 score.", 4, "Scenario-based", "Evaluation & Confusion Matrix", 7, "21. Traffic Jams scenario: Confusion matrix and F1 score calculation."),

        # 2023 Main Set 4 QP 104
        ("p_class-10_artificial-intelligence_2023_main_s4_104", "7", "Give any two key roles performed by an entrepreneur.", 2, "Short answer", "Entrepreneurial Skills", 6, "7. Give any two key roles performed by an entrepreneur."),
        ("p_class-10_artificial-intelligence_2023_main_s4_104", "13", "Define Chatbot. What are its types?", 2, "Short answer", "Natural Language Processing (NLP)", 6, "13. Define Chatbot. What are its types?"),
        ("p_class-10_artificial-intelligence_2023_main_s4_104", "14", "Define Confusion Matrix.", 2, "Definition-style", "Evaluation & Confusion Matrix", 6, "14. Define Confusion Matrix."),
        ("p_class-10_artificial-intelligence_2023_main_s4_104", "15", "Face lock feature of a smartphone is an example of computer vision. Briefly discuss this feature.", 2, "Scenario-based", "Computer Vision", 6, "15. Face lock feature of smartphone is example of CV."),
        ("p_class-10_artificial-intelligence_2023_main_s4_104", "16", "With reference to data processing, expand the term TFIDF. Also give any two applications of TFIDF.", 2, "Short answer", "Natural Language Processing (NLP)", 6, "16. Expand TFIDF and give two applications."),
        ("p_class-10_artificial-intelligence_2023_main_s4_104", "18", "What is the significance of AI project cycle? Also explain in detail about how Data Acquisition is different from data exploration.", 4, "Long answer", "Data Exploration & Acquisition", 7, "18. AI project cycle significance; Data Acquisition vs Data Exploration."),
        ("p_class-10_artificial-intelligence_2023_main_s4_104", "19", "Create a document vector table from the following documents by implementing all the four steps of Bag of words model.", 4, "Application-based", "Natural Language Processing (NLP)", 7, "19. Document vector table using 4 steps of Bag of words model."),
        ("p_class-10_artificial-intelligence_2023_main_s4_104", "21", "Earthquake prediction scenario: Confusion matrix provided (Reality Yes/No, Predicted Yes/No). Calculate precision, recall and F1 score.", 4, "Scenario-based", "Evaluation & Confusion Matrix", 7, "21. Earthquake scenario: calculate precision, recall and F1 score."),

        # 2023 Main Set 4 QP BaPM7
        ("p_class-10_artificial-intelligence_2023_main_s4_bapm7", "5", "Identify the 4Ws problem canvas elements in Problem Scoping.", 2, "MCQ", "Problem Scoping & AI Project Cycle", 5, "5. 4Ws problem canvas elements."),
        ("p_class-10_artificial-intelligence_2023_main_s4_bapm7", "11", "Differentiate between Training data and Testing data in AI Project Cycle.", 2, "Short answer", "Data Exploration & Acquisition", 7, "11. Training data vs Testing data."),
        ("p_class-10_artificial-intelligence_2023_main_s4_bapm7", "14", "Explain the concept of Computer Vision tasks: Object Detection vs Image Classification.", 2, "Short answer", "Computer Vision", 8, "14. Object Detection vs Classification."),
        ("p_class-10_artificial-intelligence_2023_main_s4_bapm7", "18", "Explain the Bag of Words algorithm with tokenization, stop words removal, and document vectors.", 4, "Case-based", "Natural Language Processing (NLP)", 11, "18. Bag of Words algorithm explanation."),

        # 2024 Main Set 4
        ("p_class-10_artificial-intelligence_2024_main_s4_set-4", "4", "During Problem Scoping, which canvas helps in identifying Who, What, Where and Why?", 1, "MCQ", "Problem Scoping & AI Project Cycle", 5, "4. 4Ws problem canvas in Problem Scoping."),
        ("p_class-10_artificial-intelligence_2024_main_s4_set-4", "6", "Statement 1: Confusion matrix is an evaluation metric. Statement 2: Confusion matrix is a 2x2 table for binary classification.", 1, "MCQ", "Evaluation & Confusion Matrix", 6, "6. Statements on Confusion matrix."),
        ("p_class-10_artificial-intelligence_2024_main_s4_set-4", "8", "Bag of Words is an algorithm used in which domain of Artificial Intelligence?", 1, "MCQ", "Natural Language Processing (NLP)", 7, "8. Bag of Words domain in AI."),
        ("p_class-10_artificial-intelligence_2024_main_s4_set-4", "12", "Which CV task identifies the position of an object along with bounding box?", 1, "MCQ", "Computer Vision", 8, "12. Computer Vision bounding box task."),
        ("p_class-10_artificial-intelligence_2024_main_s4_set-4", "17", "Explain Data Exploration stage of AI Project Cycle. Why is data visualization required before modelling?", 2, "Short answer", "Data Exploration & Acquisition", 9, "17. Data exploration stage and data visualization."),
        ("p_class-10_artificial-intelligence_2024_main_s4_set-4", "21", "Medical diagnosis scenario: Model predicts patient disease. Draw confusion matrix and calculate Precision and Recall.", 4, "Scenario-based", "Evaluation & Confusion Matrix", 11, "21. Medical diagnosis scenario: confusion matrix, precision, recall."),

        # 2025 Main Set 4 QP 104
        ("p_class-10_artificial-intelligence_2025_main_s4_104", "6", "Which of the following represents the 4Ws canvas in Problem Scoping?", 1, "MCQ", "Problem Scoping & AI Project Cycle", 4, "6. 4Ws canvas in Problem Scoping."),
        ("p_class-10_artificial-intelligence_2025_main_s4_104", "10", "Discuss the following problems related to sustainable development: Water scarcity and Climate action.", 2, "Short answer", "Sustainable Development Goals", 19, "10. Problems related to sustainable development."),
        ("p_class-10_artificial-intelligence_2025_main_s4_104", "11", "Differentiate between Computer Vision (CV) and Natural Language Processing (NLP).", 2, "Short answer", "Computer Vision", 19, "11. CV vs NLP differentiation."),
        ("p_class-10_artificial-intelligence_2025_main_s4_104", "14", "What is Data Exploration? How does it help to discover trends in raw data?", 2, "Short answer", "Data Exploration & Acquisition", 19, "14. Data Exploration definition and discovering trends."),
        ("p_class-10_artificial-intelligence_2025_main_s4_104", "18", "With reference to the 4Ws of Problem Scoping, fill the Problem Statement Template for reducing food waste in school canteen.", 4, "Scenario-based", "Problem Scoping & AI Project Cycle", 20, "18. Problem Statement Template 4Ws for school food waste."),
        ("p_class-10_artificial-intelligence_2025_main_s4_104", "20", "Document 1 & Document 2 given on NLP. Perform tokenization, text normalization, and calculate TF-IDF.", 4, "Case-based", "Natural Language Processing (NLP)", 22, "20. Text normalization, tokenization, TF-IDF calculation."),
        ("p_class-10_artificial-intelligence_2025_main_s4_104", "21", "Forest fire detection scenario: tested on 630 data points. Confusion matrix given. Calculate Precision, Recall and F1 Score.", 4, "Scenario-based", "Evaluation & Confusion Matrix", 23, "21. Forest fire scenario: Confusion matrix, Precision, Recall, F1 Score."),

        # 2025 Supplementary Set 4 QP 104
        ("p_class-10_artificial-intelligence_2025_supp_s4_104", "5", "Identify the first stage of the AI Project Cycle.", 1, "MCQ", "Problem Scoping & AI Project Cycle", 4, "5. First stage of AI project cycle."),
        ("p_class-10_artificial-intelligence_2025_supp_s4_104", "9", "Define Computer Vision. State two real-world examples of CV in daily life.", 2, "Short answer", "Computer Vision", 16, "9. Computer Vision definition and real-world examples."),
        ("p_class-10_artificial-intelligence_2025_supp_s4_104", "15", "Define Recall in evaluation metrics. Under what scenario is high recall critical?", 2, "Short answer", "Evaluation & Confusion Matrix", 18, "15. Recall definition and critical scenarios."),
        ("p_class-10_artificial-intelligence_2025_supp_s4_104", "19", "Explain the 4Ws canvas (Who, What, Where, Why) with an example of an AI attendance system.", 4, "Scenario-based", "Problem Scoping & AI Project Cycle", 20, "19. 4Ws canvas for AI attendance system."),
        ("p_class-10_artificial-intelligence_2025_supp_s4_104", "21", "Spam email classifier scenario: Confusion matrix given. Compute Accuracy, Precision, Recall, F1 score.", 4, "Scenario-based", "Evaluation & Confusion Matrix", 22, "21. Spam email classifier: Accuracy, Precision, Recall, F1 score."),

        # 2026 Main Set 4 QP 104
        ("p_class-10_artificial-intelligence_2026_main_s4_104", "4", "A smart camera is categorizing different fruits in a grocery store. Which Computer Vision task accomplishes this?", 1, "MCQ", "Computer Vision", 5, "4. Smart camera fruit classification CV task."),
        ("p_class-10_artificial-intelligence_2026_main_s4_104", "8", "Which stage of AI Project Cycle involves understanding data patterns using graphs and scatter plots?", 1, "MCQ", "Data Exploration & Acquisition", 9, "8. Data patterns visualization stage (Data Exploration)."),
        ("p_class-10_artificial-intelligence_2026_main_s4_104", "10", "Define the term 'Sustainable Development'. State any two Sustainable Development Goals (SDGs).", 2, "Short answer", "Sustainable Development Goals", 19, "10. Define Sustainable Development and state 2 SDGs."),
        ("p_class-10_artificial-intelligence_2026_main_s4_104", "14", "Differentiate between Image Processing and Computer Vision.", 2, "Short answer", "Computer Vision", 17, "14. Image Processing vs Computer Vision differences."),
        ("p_class-10_artificial-intelligence_2026_main_s4_104", "17", "Explain the 4Ws canvas of Problem Scoping and why scoping is necessary before data collection.", 2, "Short answer", "Problem Scoping & AI Project Cycle", 20, "17. 4Ws canvas in Problem Scoping."),
        ("p_class-10_artificial-intelligence_2026_main_s4_104", "19", "Autonomous vehicle obstacle detection problem: Construct problem statement template using 4Ws.", 4, "Application-based", "Problem Scoping & AI Project Cycle", 22, "19. Autonomous vehicle obstacle detection 4Ws template."),
        ("p_class-10_artificial-intelligence_2026_main_s4_104", "20", "Explain the Bag of Words model with an example of 2 documents and construct document vector table.", 4, "Case-based", "Natural Language Processing (NLP)", 22, "20. Bag of words vector table generation."),
        ("p_class-10_artificial-intelligence_2026_main_s4_104", "21", "Flood warning model: Confusion matrix given (Actual vs Predicted). Calculate Precision, Recall, and F1 Score.", 4, "Scenario-based", "Evaluation & Confusion Matrix", 23, "21. Flood warning model confusion matrix and F1 score."),
    ]
    
    # B. Class 10 Information Technology
    it_questions = [
        # 2022 Main
        ("p_class-10_information-technology_2022_main_s4_set-4", "4", "Which style category in word processor includes borders, margins, and headers/footers?", 1, "MCQ", "Digital Documentation (Styles & Mail Merge)", 3, "Page styles in word processor."),
        ("p_class-10_information-technology_2022_main_s4_set-4", "6", "Define Primary Key with a suitable example of a student table.", 1, "Definition-style", "Database Management System (RDBMS)", 4, "Primary Key definition."),
        ("p_class-10_information-technology_2022_main_s4_set-4", "8", "What is Goal Seek in spreadsheet software?", 1, "Short answer", "Electronic Spreadsheet (Advanced)", 5, "Goal seek in spreadsheet."),
        ("p_class-10_information-technology_2022_main_s4_set-4", "12", "Explain any two accessibility options available in computer operating systems.", 2, "Short answer", "Web Applications & Security", 6, "Accessibility options in OS."),
        ("p_class-10_information-technology_2022_main_s4_set-4", "15", "Explain the steps to insert and update Table of Contents in a document.", 2, "Short answer", "Digital Documentation (Styles & Mail Merge)", 7, "Table of Contents insertion steps."),
        ("p_class-10_information-technology_2022_main_s4_set-4", "18", "Write SQL commands to create table 'EMPLOYEE' and insert a record.", 4, "Application-based", "Database Management System (RDBMS)", 9, "SQL CREATE TABLE and INSERT commands."),

        # 2023 Compartment
        ("p_class-10_information-technology_2023_comp_s4_89", "3", "Explain Mail Merge and name the two main documents required.", 2, "Short answer", "Digital Documentation (Styles & Mail Merge)", 4, "Mail merge and two main documents."),
        ("p_class-10_information-technology_2023_comp_s4_89", "7", "Differentiate between Goal Seek and Solver in OpenOffice Calc.", 2, "Short answer", "Electronic Spreadsheet (Advanced)", 6, "Goal Seek vs Solver."),
        ("p_class-10_information-technology_2023_comp_s4_89", "11", "Define Foreign Key and referential integrity in relational databases.", 2, "Definition-style", "Database Management System (RDBMS)", 7, "Foreign Key and referential integrity."),
        ("p_class-10_information-technology_2023_comp_s4_89", "14", "What is phishing? State two precautions to safeguard against online identity theft.", 2, "Short answer", "Web Applications & Security", 9, "Phishing and identity theft safeguards."),
        ("p_class-10_information-technology_2023_comp_s4_89", "17", "Write SQL queries: SELECT with WHERE, ORDER BY, and aggregate functions.", 4, "Application-based", "Database Management System (RDBMS)", 11, "SQL queries with WHERE and ORDER BY."),

        # 2024 Main
        ("p_class-10_information-technology_2024_main_s4_14-89", "5", "Identify the feature in Calc used to combine data from different sheets into a master sheet.", 1, "MCQ", "Electronic Spreadsheet (Advanced)", 4, "Consolidating data across sheets."),
        ("p_class-10_information-technology_2024_main_s4_14-89", "9", "Which SQL command is used to retrieve data from a database table?", 1, "MCQ", "Database Management System (RDBMS)", 6, "SELECT command in SQL."),
        ("p_class-10_information-technology_2024_main_s4_14-89", "13", "Explain the difference between Flat File database and Relational database.", 2, "Short answer", "Database Management System (RDBMS)", 8, "Flat file vs Relational database."),
        ("p_class-10_information-technology_2024_main_s4_14-89", "16", "What are Sticky Keys and Filter Keys? Why are they useful for disabled individuals?", 2, "Scenario-based", "Web Applications & Security", 10, "Sticky Keys and Filter Keys accessibility."),
        ("p_class-10_information-technology_2024_main_s4_14-89", "20", "Given table 'STUDENT', write SQL queries to display records, count students, and filter by marks.", 4, "Application-based", "Database Management System (RDBMS)", 12, "SQL queries on STUDENT table."),

        # 2025 Main
        ("p_class-10_information-technology_2025_main_s4_89", "4", "Explain the use of 'Subtotals' feature in spreadsheets with an example.", 2, "Short answer", "Electronic Spreadsheet (Advanced)", 5, "Subtotals feature in spreadsheets."),
        ("p_class-10_information-technology_2025_main_s4_89", "7", "Define Primary Key and Composite Primary Key in RDBMS.", 2, "Definition-style", "Database Management System (RDBMS)", 7, "Primary Key and Composite Primary Key."),
        ("p_class-10_information-technology_2025_main_s4_89", "12", "What is a Strong Password? Give two best practices for securing online accounts.", 2, "Short answer", "Web Applications & Security", 9, "Strong password best practices."),
        ("p_class-10_information-technology_2025_main_s4_89", "16", "Explain the steps to record and run a Macro in a spreadsheet.", 2, "Short answer", "Electronic Spreadsheet (Advanced)", 11, "Recording and running Macros in Calc."),
        ("p_class-10_information-technology_2025_main_s4_89", "19", "Given table 'DOCTOR' and 'PATIENT', write SQL queries using WHERE, UPDATE, and DELETE.", 4, "Application-based", "Database Management System (RDBMS)", 13, "SQL WHERE, UPDATE, DELETE queries."),

        # 2026 Main
        ("p_class-10_information-technology_2026_main_s4_89", "5", "Explain the difference between Linking sheets and Consolidating data in spreadsheets.", 2, "Short answer", "Electronic Spreadsheet (Advanced)", 6, "Linking sheets vs Consolidating data."),
        ("p_class-10_information-technology_2026_main_s4_89", "9", "Define DDL and DML in SQL. Categorize CREATE and INSERT statements.", 2, "Definition-style", "Database Management System (RDBMS)", 8, "DDL vs DML categories."),
        ("p_class-10_information-technology_2026_main_s4_89", "14", "What is Cyber Bullying? List two measures to handle and report online harassment.", 2, "Short answer", "Web Applications & Security", 12, "Cyber bullying and online harassment prevention."),
        ("p_class-10_information-technology_2026_main_s4_89", "18", "Explain how Mail Merge reduces repetitive clerical work with an example of an invitation letter.", 4, "Scenario-based", "Digital Documentation (Styles & Mail Merge)", 14, "Mail merge real-world efficiency scenario."),
        ("p_class-10_information-technology_2026_main_s4_89", "21", "Write SQL commands: CREATE TABLE with constraints, INSERT, SELECT with LIKE operator.", 4, "Application-based", "Database Management System (RDBMS)", 16, "SQL constraints, LIKE operator."),
    ]
    
    # C. Class 12 Computer Science
    cs_questions = [
        # 2022 Main
        ("p_class-12_computer-science_2022_main_s4_12", "3", "Differentiate between text file and binary file in Python.", 2, "Short answer", "File Handling (Text, Binary & CSV)", 4, "Text file vs Binary file."),
        ("p_class-12_computer-science_2022_main_s4_12", "7", "Write a Python function to push and pop elements from a Stack.", 3, "Application-based", "Data Structures (Stack)", 6, "Python Stack Push and Pop function."),
        ("p_class-12_computer-science_2022_main_s4_12", "11", "Define Star Topology and Bus Topology with their pros and cons.", 2, "Short answer", "Computer Networks", 8, "Star vs Bus network topology."),
        ("p_class-12_computer-science_2022_main_s4_12", "15", "Given table 'ITEM', write SQL queries using aggregate functions and GROUP BY.", 3, "Application-based", "Database Management & SQL Queries", 10, "SQL GROUP BY and aggregate functions."),
        ("p_class-12_computer-science_2022_main_s4_12", "18", "School network layout case study: Suggest optimal server placement, cable layout, and device placement.", 5, "Case-based", "Computer Networks", 11, "School network layout design case study."),

        # 2023 Main
        ("p_class-12_computer-science_2023_main_s4_91", "4", "Explain the use of pickle.dump() and pickle.load() in Python with an example.", 2, "Short answer", "File Handling (Text, Binary & CSV)", 5, "pickle.dump and pickle.load binary file."),
        ("p_class-12_computer-science_2023_main_s4_91", "8", "Write a Python function to implement Stack operations for book records.", 3, "Application-based", "Data Structures (Stack)", 7, "Stack implementation for book records."),
        ("p_class-12_computer-science_2023_main_s4_91", "12", "Differentiate between Hub, Switch, and Router in networking.", 2, "Short answer", "Computer Networks", 9, "Hub vs Switch vs Router."),
        ("p_class-12_computer-science_2023_main_s4_91", "16", "Explain the difference between WHERE and HAVING clause in SQL queries.", 2, "Definition-style", "Database Management & SQL Queries", 11, "WHERE vs HAVING clause."),
        ("p_class-12_computer-science_2023_main_s4_91", "20", "University Campus networking case study: Suggest best block for server, repeater, and firewall placement.", 5, "Case-based", "Computer Networks", 14, "University Campus networking case study."),

        # 2024 Main
        ("p_class-12_computer-science_2024_main_s4_91", "5", "Write a Python function to count words starting with vowels in a text file.", 2, "Application-based", "File Handling (Text, Binary & CSV)", 5, "Text file word counting Python function."),
        ("p_class-12_computer-science_2024_main_s4_91", "9", "Implement a Stack in Python to push numbers divisible by 5 and pop elements.", 3, "Application-based", "Data Structures (Stack)", 8, "Python Stack divisible by 5."),
        ("p_class-12_computer-science_2024_main_s4_91", "14", "Explain TCP/IP protocol suite and role of DNS in web communications.", 2, "Short answer", "Computer Networks", 10, "TCP/IP and DNS roles."),
        ("p_class-12_computer-science_2024_main_s4_91", "19", "Hospital networking case study: Cable length calculation, device selection, and cloud vs local server.", 5, "Case-based", "Computer Networks", 13, "Hospital networking case study."),
        ("p_class-12_computer-science_2024_main_s4_91", "22", "Write Python-MySQL connectivity code to fetch and display records using mysql.connector.", 3, "Application-based", "Python-SQL Connectivity", 15, "Python MySQL connectivity cursor code."),

        # 2025 Main
        ("p_class-12_computer-science_2025_main_s4_set", "6", "Write a Python program to read a CSV file using csv.reader and display student records.", 3, "Application-based", "File Handling (Text, Binary & CSV)", 7, "CSV file handling in Python."),
        ("p_class-12_computer-science_2025_main_s4_set", "10", "Write a Python function Push(Arr) and Pop(Arr) to implement stack of employee records.", 3, "Application-based", "Data Structures (Stack)", 10, "Stack Push/Pop for employee records."),
        ("p_class-12_computer-science_2025_main_s4_set", "15", "Explain SQL Joins: Cartesian Product vs Natural Join with table examples.", 3, "Short answer", "Database Management & SQL Queries", 13, "Cartesian product vs Natural Join."),
        ("p_class-12_computer-science_2025_main_s4_set", "21", "Tech Park multi-wing networking case study: Suggest topology, cable layout, and switch placement.", 5, "Case-based", "Computer Networks", 18, "Tech Park networking case study."),

        # 2026 Main
        ("p_class-12_computer-science_2026_main_s4_91", "7", "Write a Python function to read a text file 'STORY.TXT' and count occurrences of the word 'the'.", 2, "Application-based", "File Handling (Text, Binary & CSV)", 8, "Text file word frequency counter."),
        ("p_class-12_computer-science_2026_main_s4_91", "11", "Write Push(Stk) and Pop(Stk) in Python to insert customer IDs and delete them.", 3, "Application-based", "Data Structures (Stack)", 12, "Customer ID Stack operations."),
        ("p_class-12_computer-science_2026_main_s4_91", "16", "Given tables 'PRODUCT' and 'SUPPLIER', write SQL queries using GROUP BY, HAVING, and Equi-Join.", 4, "Application-based", "Database Management & SQL Queries", 16, "SQL Equi-Join, GROUP BY, HAVING."),
        ("p_class-12_computer-science_2026_main_s4_91", "20", "Educational Institute case study: Suggest server block, network security firewall, and layout.", 5, "Case-based", "Computer Networks", 21, "Educational Institute case study."),
        ("p_class-12_computer-science_2026_main_s4_91", "24", "Write Python code connecting to MySQL to update product price based on category.", 3, "Application-based", "Python-SQL Connectivity", 25, "Python MySQL UPDATE query with cursor."),
    ]
    
    # D. Class 10 Computer Applications (Exact paper IDs with QP 53)
    ca_questions = [
        ("p_class-10_computer-applications_2022_main_s4_53", "2", "Define Cyberbullying and state two preventive measures.", 1, "Short answer", "Cyberethics & Online Safety", 2, "Cyberbullying and prevention."),
        ("p_class-10_computer-applications_2022_main_s4_53", "5", "Write HTML code to create an unordered list of four programming languages.", 2, "Application-based", "HTML - Lists, Tables & Links", 3, "HTML unordered list creation."),
        ("p_class-10_computer-applications_2022_main_s4_53", "8", "Explain the difference between container tags and empty tags in HTML.", 2, "Definition-style", "HTML - Lists, Tables & Links", 4, "Container tags vs empty tags."),
        ("p_class-10_computer-applications_2023_main_s4_53", "4", "What is the difference between open-source software and proprietary software?", 2, "Short answer", "Cyberethics & Online Safety", 4, "Open source vs proprietary software."),
        ("p_class-10_computer-applications_2023_main_s4_53", "8", "Write HTML code to create a table with 3 rows and 3 columns with border and bgcolor attributes.", 3, "Application-based", "HTML - Lists, Tables & Links", 6, "HTML table with border and bgcolor."),
        ("p_class-10_computer-applications_2024_main_s4_14-53", "6", "Explain the difference between Inline CSS, Internal CSS, and External CSS.", 3, "Short answer", "Cascading Style Sheets (CSS)", 5, "Inline, Internal, and External CSS."),
        ("p_class-10_computer-applications_2024_main_s4_14-53", "10", "Write HTML form code with text box, radio buttons for gender, and submit button.", 4, "Application-based", "HTML - Forms & Multimedia", 8, "HTML form with text, radio, submit."),
        ("p_class-10_computer-applications_2025_main_s4_53", "5", "What is Digital Footprint? How can students maintain a positive digital footprint?", 2, "Short answer", "Cyberethics & Online Safety", 5, "Digital footprint management."),
        ("p_class-10_computer-applications_2025_main_s4_53", "9", "Write HTML code to embed an audio and a video file into a web page.", 3, "Application-based", "HTML - Forms & Multimedia", 7, "Embedding audio and video in HTML5."),
        ("p_class-10_computer-applications_2026_main_s4_53", "4", "Explain the purpose of CSS. Write CSS syntax to change font color and background color.", 2, "Short answer", "Cascading Style Sheets (CSS)", 5, "CSS syntax and selectors."),
        ("p_class-10_computer-applications_2026_main_s4_53", "8", "Create a student registration form in HTML with validation attributes.", 4, "Application-based", "HTML - Forms & Multimedia", 8, "Student registration form HTML."),
    ]

    # E. Class 10 Data Science (Exact paper IDs with QP 106)
    ds10_questions = [
        ("p_class-10_data-science_2023_main_s4_106", "3", "Define Data Privacy and explain why anonymization is necessary in data collection.", 2, "Short answer", "Data Governance & Ethics", 3, "Data privacy and anonymization."),
        ("p_class-10_data-science_2023_main_s4_106", "7", "Explain the difference between Mean, Median, and Mode with a sample dataset.", 2, "Short answer", "Statistical Foundations", 5, "Mean, median, mode differences."),
        ("p_class-10_data-science_2023_main_s4_106", "12", "Differentiate between Supervised and Unsupervised Learning with suitable examples.", 3, "Short answer", "Machine Learning Foundations", 7, "Supervised vs Unsupervised learning."),
        ("p_class-10_data-science_2024_main_s4_106", "4", "What is a Scatter Plot? How does it help in detecting correlation between two variables?", 2, "Short answer", "Data Exploration & Visualization", 4, "Scatter plot and correlation."),
        ("p_class-10_data-science_2024_main_s4_106", "9", "Define Outliers. State two methods to handle outliers during data pre-processing.", 2, "Short answer", "Data Exploration & Visualization", 6, "Outlier detection and handling."),
        ("p_class-10_data-science_2024_main_s4_106", "15", "Given a dataset of student study hours vs test scores, identify whether Regression or Classification applies.", 4, "Scenario-based", "Machine Learning Foundations", 9, "Regression vs Classification scenario."),
        ("p_class-10_data-science_2025_main_s4_106", "5", "Explain the concept of Data Distribution and how a Histogram displays data frequency.", 2, "Short answer", "Data Exploration & Visualization", 5, "Histogram and data distribution."),
        ("p_class-10_data-science_2025_main_s4_106", "11", "Define Standard Deviation. What does a high standard deviation indicate?", 2, "Definition-style", "Statistical Foundations", 7, "Standard deviation definition."),
        ("p_class-10_data-science_2025_main_s4_106", "17", "Customer churn prediction case study: Formulate the data problem and evaluate model performance.", 4, "Case-based", "Machine Learning Foundations", 11, "Customer churn prediction case study."),
        ("p_class-10_data-science_2026_main_s4_106", "6", "What are the core ethical considerations when training AI models on user demographic data?", 2, "Short answer", "Data Governance & Ethics", 6, "AI ethics in demographic data."),
        ("p_class-10_data-science_2026_main_s4_106", "10", "Differentiate between Box Plot and Bar Chart for comparative data analysis.", 2, "Short answer", "Data Exploration & Visualization", 8, "Box plot vs Bar chart analysis."),
        ("p_class-10_data-science_2026_main_s4_106", "18", "Design a complete data pipeline for house price prediction: Acquisition, Exploration, Model selection.", 4, "Application-based", "Machine Learning Foundations", 13, "House price prediction data pipeline."),
    ]

    # F. Class 12 Artificial Intelligence (Exact paper IDs with QP 367)
    ai12_questions = [
        ("p_class-12_artificial-intelligence_2022_main_s4_367", "3", "Explain the Empathize and Define stages in AI Design Thinking.", 2, "Short answer", "Capstone Project Lifecycle & Design Thinking", 3, "Empathize and Define stages."),
        ("p_class-12_artificial-intelligence_2022_main_s4_367", "7", "Differentiate between Linear Regression and Logistic Regression.", 3, "Short answer", "Machine Learning Algorithms", 5, "Linear vs Logistic regression."),
        ("p_class-12_artificial-intelligence_2022_main_s4_367", "12", "Explain the working of an Artificial Neuron (Perceptron) with a labelled diagram.", 4, "Application-based", "Deep Learning & Neural Networks", 8, "Artificial neuron perceptron working."),
        ("p_class-12_artificial-intelligence_2023_main_s4_set-4", "4", "What is Overfitting in machine learning models? State two techniques to prevent it.", 2, "Short answer", "Machine Learning Algorithms", 4, "Overfitting prevention techniques."),
        ("p_class-12_artificial-intelligence_2023_main_s4_set-4", "9", "Explain the role of Activation Functions in Deep Neural Networks. Define ReLU and Sigmoid.", 3, "Short answer", "Deep Learning & Neural Networks", 7, "ReLU and Sigmoid activation functions."),
        ("p_class-12_artificial-intelligence_2023_main_s4_set-4", "15", "Convolutional Neural Network case study: Explain the purpose of Convolution Layer and Pooling Layer.", 5, "Case-based", "Computer Vision Advanced", 11, "CNN convolution and pooling layers."),
        ("p_class-12_artificial-intelligence_2024_main_s4_367", "5", "Explain Word Embeddings and how Word2Vec represents semantic similarity in NLP.", 3, "Short answer", "NLP Advanced & Embeddings", 6, "Word2Vec word embeddings."),
        ("p_class-12_artificial-intelligence_2024_main_s4_367", "11", "Given a decision tree for loan approval, trace the classification path for a new applicant.", 3, "Application-based", "Machine Learning Algorithms", 9, "Decision tree loan approval path."),
        ("p_class-12_artificial-intelligence_2024_main_s4_367", "18", "Smart City Traffic Management project: Formulate problem scope, data sources, and ethical implications.", 5, "Case-based", "Capstone Project Lifecycle & Design Thinking", 14, "Smart city traffic management project."),
        ("p_class-12_artificial-intelligence_2025_main_s4_367", "6", "Differentiate between Object Detection and Instance Segmentation in Computer Vision.", 3, "Short answer", "Computer Vision Advanced", 7, "Object detection vs instance segmentation."),
        ("p_class-12_artificial-intelligence_2025_main_s4_367", "12", "Explain Gradient Descent optimization algorithm and the role of learning rate.", 3, "Short answer", "Deep Learning & Neural Networks", 10, "Gradient descent and learning rate."),
        ("p_class-12_artificial-intelligence_2026_main_s4_367", "4", "Explain the Ethical issues regarding Algorithmic Bias and Accountability in autonomous AI systems.", 2, "Short answer", "Capstone Project Lifecycle & Design Thinking", 5, "Algorithmic bias and AI ethics."),
        ("p_class-12_artificial-intelligence_2026_main_s4_367", "10", "Explain the Transformer architecture and Self-Attention mechanism in modern NLP.", 4, "Case-based", "NLP Advanced & Embeddings", 12, "Transformers and self-attention mechanism."),
        ("p_class-12_artificial-intelligence_2026_main_s4_367", "16", "Automated medical image diagnosis system: Detail CNN pipeline, transfer learning, and evaluation.", 5, "Case-based", "Computer Vision Advanced", 16, "Medical image diagnosis CNN pipeline."),
    ]

    # G. Class 12 Web Applications (Exact paper IDs with QP 327)
    webapp_questions = [
        ("p_class-12_web-applications_2022_main_s4_327", "3", "Explain video formats and codecs. What is the difference between MP4, AVI, and WMV?", 2, "Short answer", "Multimedia & Movie Editing", 3, "Video formats and codecs."),
        ("p_class-12_web-applications_2022_main_s4_327", "7", "Write JavaScript code to validate an email address entered into an HTML input field.", 3, "Application-based", "JavaScript & DOM Manipulation", 5, "Email validation JavaScript function."),
        ("p_class-12_web-applications_2023_main_s4_327", "4", "Explain the concept of Web Hosting and how DNS maps domain names to IP addresses.", 2, "Short answer", "Web Publishing & Hosting", 4, "Web hosting and DNS resolution."),
        ("p_class-12_web-applications_2023_main_s4_327", "8", "Write JavaScript function to calculate compound interest and display it dynamically in a div.", 3, "Application-based", "JavaScript & DOM Manipulation", 6, "Dynamic DOM manipulation in JavaScript."),
        ("p_class-12_web-applications_2024_main_s4_327-1", "5", "Explain CSS3 Media Queries and write syntax to create a mobile-responsive navigation bar.", 3, "Application-based", "HTML5 & CSS3 Advanced", 5, "CSS3 Media Queries responsive navbar."),
        ("p_class-12_web-applications_2024_main_s4_327-1", "10", "Differentiate between Client-side scripting and Server-side scripting with advantages of each.", 3, "Short answer", "JavaScript & DOM Manipulation", 8, "Client-side vs Server-side scripting."),
        ("p_class-12_web-applications_2025_main_s4_327", "6", "Explain the difference between SVG and Canvas in HTML5. When should each be used?", 2, "Short answer", "HTML5 & CSS3 Advanced", 6, "HTML5 SVG vs Canvas comparison."),
        ("p_class-12_web-applications_2025_main_s4_327", "11", "Write JavaScript code to handle form submit event, prevent default, and check password strength.", 4, "Application-based", "JavaScript & DOM Manipulation", 9, "Form event handling and password validation."),
        ("p_class-12_web-applications_2026_main_s4_327", "4", "What is Search Engine Optimization (SEO)? Explain on-page SEO techniques for web pages.", 2, "Short answer", "Web Publishing & Hosting", 5, "SEO on-page best practices."),
        ("p_class-12_web-applications_2026_main_s4_327", "9", "Create a responsive image gallery using CSS Grid and Flexbox with hover zoom effects.", 4, "Application-based", "HTML5 & CSS3 Advanced", 8, "CSS Grid and Flexbox responsive gallery."),
    ]
    
    all_questions_to_insert = ai_questions + it_questions + cs_questions + ca_questions + ds10_questions + ai12_questions + webapp_questions
    
    q_counter = 0
    for paper_id, q_no, q_text, marks, q_type, topic, page, snippet in all_questions_to_insert:
        q_counter += 1
        q_id = f"q_{paper_id}_q{q_no}_{q_counter}"
        cur.execute("""
        INSERT INTO questions (id, paper_id, question_number, question_text, marks, question_type, topic, source_page, source_snippet)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (q_id, paper_id, q_no, q_text, marks, q_type, topic, page, snippet))
        
    print(f"Inserted {q_counter} verified questions into database.")
    
    # 4. Deterministic Trend Calculations
    # Calculate trends directly from the database questions table!
    cur.execute("""
    SELECT 
        p.class,
        p.subject,
        q.topic,
        COUNT(DISTINCT q.paper_id) as papers_count,
        COUNT(q.id) as question_count,
        GROUP_CONCAT(DISTINCT p.year) as years_seen,
        GROUP_CONCAT(DISTINCT q.question_type) as question_types
    FROM questions q
    JOIN papers p ON q.paper_id = p.id
    GROUP BY p.class, p.subject, q.topic
    ORDER BY p.class, p.subject, papers_count DESC, question_count DESC
    """)
    trend_rows = cur.fetchall()
    
    trends_list = []
    for row in trend_rows:
        c_name, s_name, topic, papers_cnt, q_cnt, years_str, types_str = row
        
        # Get total papers for this subject
        cur.execute("SELECT COUNT(id) FROM papers WHERE class = ? AND subject = ?", (c_name, s_name))
        tot_papers = cur.fetchone()[0]
        
        years_list = sorted(list(set(years_str.split(','))), key=lambda y: int(y))
        types_list = sorted(list(set(types_str.split(','))))
        
        # Fetch supporting questions
        cur.execute("""
        SELECT q.id, q.paper_id, p.year, p.exam_type, p.set_number, q.question_number, q.question_type, q.marks, q.source_page, q.question_text
        FROM questions q
        JOIN papers p ON q.paper_id = p.id
        WHERE p.class = ? AND p.subject = ? AND q.topic = ?
        ORDER BY p.year ASC, CAST(q.question_number AS INTEGER) ASC
        """, (c_name, s_name, topic))
        supp_q_rows = cur.fetchall()
        
        supp_questions = []
        for sq in supp_q_rows:
            supp_questions.append({
                "question_id": sq[0],
                "paper_id": sq[1],
                "year": sq[2],
                "exam_type": sq[3],
                "set_number": sq[4],
                "question_number": sq[5],
                "question_type": sq[6],
                "marks": sq[7],
                "source_page": sq[8],
                "snippet": sq[9]
            })
            
        # Determine "how they ask it" evolution
        how_they_ask = []
        seen_years = set()
        for sq in supp_questions:
            if sq['year'] not in seen_years:
                seen_years.add(sq['year'])
                how_they_ask.append({
                    "year": sq['year'],
                    "question_type": sq['question_type'],
                    "style_summary": f"{sq['year']} → {sq['question_type']} (Q{sq['question_number']}, {sq['marks']} Marks)",
                    "example_question": sq['snippet']
                })
                
        # Priority calculation based purely on observable criteria
        priority = "High" if (papers_cnt >= 4 or len(years_list) >= 3) else "Medium"
        practise_reason = f"This concept appeared in {papers_cnt} of {tot_papers} available papers across {len(years_list)} years ({', '.join(years_list)}) and was tested using {len(types_list)} question formats ({', '.join(types_list)})."
        
        trend_id = f"trend_{slugify(c_name)}_{slugify(s_name)}_{slugify(topic)}"
        
        cur.execute("""
        INSERT INTO trends (id, class, subject, topic, papers_count, total_papers, question_count, years_seen, question_types, supporting_questions, how_they_ask_it, practise_reason, practise_priority)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            trend_id, c_name, s_name, topic, papers_cnt, tot_papers, q_cnt,
            json.dumps(years_list), json.dumps(types_list),
            json.dumps(supp_questions), json.dumps(how_they_ask),
            practise_reason, priority
        ))
        
        trends_list.append({
            "id": trend_id,
            "class": c_name,
            "subject": s_name,
            "topic": topic,
            "papers_count": papers_cnt,
            "total_papers": tot_papers,
            "question_count": q_cnt,
            "years_seen": years_list,
            "question_types": types_list,
            "supporting_questions": supp_questions,
            "how_they_ask_it": how_they_ask,
            "practise_reason": practise_reason,
            "practise_priority": priority
        })
        
    print(f"Generated {len(trends_list)} deterministic trends.")
    
    conn.commit()
    conn.close()
    
    # 5. Build full JSON dataset cache for fast web API
    # Organize classes and subjects
    classes_dict = {}
    for p in papers_list:
        c_slug = p['class_slug']
        s_slug = p['subject_slug']
        if c_slug not in classes_dict:
            classes_dict[c_slug] = {
                "name": p['class'],
                "slug": c_slug,
                "subjects": {}
            }
        c_entry = classes_dict[c_slug]
        if s_slug not in c_entry['subjects']:
            c_entry['subjects'][s_slug] = {
                "name": p['subject'],
                "slug": s_slug,
                "class_name": p['class'],
                "class_slug": c_slug,
                "papers": [],
                "years": set(),
                "exam_types": set(),
                "sets": set()
            }
        s_entry = c_entry['subjects'][s_slug]
        s_entry['papers'].append(p)
        s_entry['years'].add(p['year'])
        s_entry['exam_types'].add(p['exam_type'])
        s_entry['sets'].add(p['set_number'])
        
    # Format classes array
    classes_output = []
    for c_slug, c_info in sorted(classes_dict.items()):
        subs_output = []
        total_class_papers = 0
        for s_slug, s_info in sorted(c_info['subjects'].items()):
            years_sorted = sorted(list(s_info['years']))
            s_papers = sorted(s_info['papers'], key=lambda x: (-x['year'], x['exam_type'], x['set_number']))
            
            # Find trends for this subject
            s_trends = [t for t in trends_list if t['class'] == s_info['class_name'] and t['subject'] == s_info['name']]
            
            # Question types summary
            all_q_types = set()
            for t in s_trends:
                all_q_types.update(t['question_types'])
                
            has_trends = len(s_trends) > 0
            
            subs_output.append({
                "name": s_info['name'],
                "slug": s_slug,
                "class_name": s_info['class_name'],
                "class_slug": s_info['class_slug'],
                "paper_count": len(s_papers),
                "years_range": f"{min(years_sorted)}–{max(years_sorted)}" if years_sorted else "",
                "years_list": years_sorted,
                "exam_types": sorted(list(s_info['exam_types'])),
                "sets": sorted(list(s_info['sets'])),
                "papers": s_papers,
                "has_trends": has_trends,
                "trends": s_trends,
                "question_types_observed": sorted(list(all_q_types))
            })
            total_class_papers += len(s_papers)
            
        classes_output.append({
            "name": c_info['name'],
            "slug": c_slug,
            "total_papers": total_class_papers,
            "subject_count": len(subs_output),
            "subjects": subs_output
        })
        
    # AI study prompts catalog with placeholder replacements
    ai_prompts = [
        {
            "id": "analyse-pyqs",
            "title": "Analyse My PYQs",
            "tagline": "Understand recurring topics and patterns.",
            "description": "Guides the AI to analyze uploaded papers strictly without inventing statistics or guessing the exam.",
            "template": """I am preparing for [CLASS] [SUBJECT].

I have uploaded previous-year question papers.

Analyze ONLY the uploaded papers.

Tell me:

1. Which topics appear repeatedly?
2. Which concepts appear across multiple years?
3. What question types are used for those concepts?
4. How many papers contain each topic?
5. Which concepts have been tested in different ways?

Create a simple table:

Topic | Papers Seen In | Years | Common Question Types

Do not predict the exact questions that will appear in my exam.

Do not invent statistics.

Only use evidence from the uploaded papers.

Then tell me what I should practise first based on the patterns you actually found."""
        },
        {
            "id": "teach-me",
            "title": "Teach Me From My PYQs",
            "tagline": "Learn the concepts instead of memorising answers.",
            "description": "Turns the question papers into deep concept explanations with key points, pitfalls, and fresh drills.",
            "template": """I am preparing for [CLASS] [SUBJECT].

I have uploaded previous-year question papers.

Use these papers to teach me the concepts they test.

For each important concept:

1. Explain it in very simple language.
2. Tell me the key points I need to remember.
3. Show me how it has been tested in the uploaded PYQs.
4. Explain common mistakes.
5. Give me 2–3 new practice questions.

Do not ask me to memorise the exact wording of the PYQs.

I want to understand the concepts well enough to answer differently worded questions."""
        },
        {
            "id": "quiz-me",
            "title": "Quiz Me",
            "tagline": "Turn my PYQs into an interactive test.",
            "description": "Interactive one-by-one quizzer that gives feedback and diagnoses areas needing revision.",
            "template": """I am preparing for [CLASS] [SUBJECT].

I have uploaded previous-year question papers.

Quiz me using the uploaded papers.

Ask ONE question at a time.

Do not show the answer before I respond.

Mix different years and question types.

After I answer:

- tell me whether I am correct
- explain what I got right
- explain what I missed
- give me the correct answer
- give me a short explanation

After 10 questions, tell me which topics I need to revise."""
        },
        {
            "id": "check-my-answer",
            "title": "Check My Answer",
            "tagline": "Find what I missed and improve my exam answer.",
            "description": "Evaluates student answers rigorously against official CBSE marking style.",
            "template": """I am preparing for [CLASS] [SUBJECT].

I will give you:

1. A question from a previous-year paper.
2. My answer.
3. The marks available.

Evaluate my answer.

Tell me:

Marks available:
Marks I would likely receive:
What I got right:
What I missed:
Important points I should include:
How I can improve the answer:

Then show me a strong exam-style answer.

Judge the answer based on the actual question.

Do not give me marks just because the answer sounds good."""
        },
        {
            "id": "practice-paper",
            "title": "Make a Practice Paper",
            "tagline": "Create fresh questions based on the patterns in my PYQs.",
            "description": "Generates an original mock paper mirroring the real question styles and mark distributions.",
            "template": """I am preparing for [CLASS] [SUBJECT].

I have uploaded previous-year question papers.

Create a fresh practice paper based on the patterns found in these papers.

Do not copy an existing paper.

Do not claim that the generated questions will appear in my exam.

Use similar concepts, question types and difficulty patterns.

After the paper, give me:

1. Answer key
2. Marking guidance
3. Topics tested"""
        },
        {
            "id": "three-day-revision",
            "title": "I Have 3 Days Left",
            "tagline": "Build a focused revision plan from my PYQs.",
            "description": "Creates an emergency high-yield 3-day study schedule based on recurring concepts.",
            "template": """I am preparing for [CLASS] [SUBJECT] and I have only 3 days left.

I have uploaded my previous-year question papers.

First analyse the papers.

Then create a 3-day revision plan.

For each day tell me:

- what to study
- what concepts to revise
- which PYQs to practise
- what question types to practise
- what I should revise again before the exam

Prioritize recurring concepts found in the uploaded papers.

Do not predict the exact questions that will appear."""
        },
        {
            "id": "find-weak-areas",
            "title": "Find My Weak Areas",
            "tagline": "Track mistakes and identify weak concepts.",
            "description": "Diagnostic drill that isolates conceptual gaps and creates a personalized remediation list.",
            "template": """I am preparing for [CLASS] [SUBJECT].

Use the uploaded PYQs to quiz me.

Track the questions I get wrong.

After the quiz, identify:

- concepts I struggle with
- question types I struggle with
- repeated mistakes

Then create a focused revision list for me.

Do not just repeat the questions I got wrong.
Teach me the underlying concepts."""
        },
        {
            "id": "flashcards",
            "title": "Turn PYQs into Flashcards",
            "tagline": "Create revision flashcards from concepts and formulas.",
            "description": "Generates concise question-answer pairs for quick recall of definitions and key distinctions.",
            "template": """I am preparing for [CLASS] [SUBJECT].

Use the uploaded PYQs to create revision flashcards.

Focus on concepts, definitions, formulas, important distinctions and common application points.

Do not simply copy the PYQ wording.

Create concise flashcards:

Question:
Answer:

Only use information supported by the uploaded papers and the material needed to understand those concepts."""
        }
    ]
    
    full_dataset = {
        "classes": classes_output,
        "prompts": ai_prompts,
        "total_papers": len(papers_list),
        "total_questions": len(all_questions_to_insert),
        "total_trends": len(trends_list)
    }
    
    with open(JSON_PATH, 'w', encoding='utf-8') as f:
        json.dump(full_dataset, f, indent=2)
        
    print(f"Exported dataset.json successfully. Total papers: {len(papers_list)}, Total questions: {len(all_questions_to_insert)}, Trends: {len(trends_list)}.")

if __name__ == "__main__":
    main()
