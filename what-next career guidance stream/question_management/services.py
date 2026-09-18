import json

CATEGORIES = [
    'Engineering & Technology', 'Medical & Healthcare', 'Commerce & Business',
    'Arts & Humanities', 'Creative & Design', 'Government & Public Service'
]

QUESTION_SEED = [
    ('I enjoy solving mathematical or logical puzzles.', 'Engineering & Technology'),
    ('I like understanding how machines, gadgets, or software work.', 'Engineering & Technology'),
    ('I would enjoy building or coding something from scratch.', 'Engineering & Technology'),
    ("I'm interested in biology and how the human body works.", 'Medical & Healthcare'),
    ("I feel fulfilled when I help someone who is unwell or in distress.", 'Medical & Healthcare'),
    ("I can stay calm and focused in high-pressure situations.", 'Medical & Healthcare'),
    ('I enjoy working with numbers, budgets, or financial planning.', 'Commerce & Business'),
    ('I like the idea of starting or managing a business.', 'Commerce & Business'),
    ("I'm curious about markets, trade, or investments.", 'Commerce & Business'),
    ('I enjoy reading about history, society, or human behavior.', 'Arts & Humanities'),
    ('I like debating ideas and forming well-reasoned arguments.', 'Arts & Humanities'),
    ("I'm interested in law, justice, or social issues.", 'Arts & Humanities'),
    ('I express myself well through drawing, design, or writing creatively.', 'Creative & Design'),
    ('I notice and appreciate aesthetics, color, and visual composition.', 'Creative & Design'),
    ('I enjoy imagining and creating original stories or designs.', 'Creative & Design'),
    ('I feel a strong sense of duty toward public service or the nation.', 'Government & Public Service'),
    ("I'm comfortable with discipline, structure, and following procedures.", 'Government & Public Service'),
    ('I would like a career that involves serving or leading communities.', 'Government & Public Service'),
    ('Basic logic puzzle: I enjoy finding the next number in a simple sequence.', 'Engineering & Technology'),
    ('Basic logic puzzle: I can quickly identify patterns in shapes, letters, or symbols.', 'Engineering & Technology'),
    ('Basic logic puzzle: I like solving simple ordering and matching problems.', 'Engineering & Technology'),
    ('Basic logic puzzle: I enjoy working out which statement must be true from a few clues.', 'Engineering & Technology'),
    ('Basic logic puzzle: I can spot the odd item out and explain why it does not belong.', 'Engineering & Technology'),
    ('Basic logic puzzle: I enjoy using a simple process of elimination to reach an answer.', 'Engineering & Technology'),
    ('Medium logic puzzle: I enjoy solving multi-step deduction problems with several clues.', 'Engineering & Technology'),
    ('Medium logic puzzle: I can compare different possibilities and remove the ones that cannot work.', 'Engineering & Technology'),
    ('Medium logic puzzle: I like reasoning through seating, scheduling, or arrangement problems.', 'Engineering & Technology'),
    ('Medium logic puzzle: I enjoy finding hidden rules in number or symbol patterns.', 'Engineering & Technology'),
    ('Medium logic puzzle: I can connect several pieces of information to reach a logical conclusion.', 'Engineering & Technology'),
    ('Medium logic puzzle: I enjoy puzzles that require planning more than one step ahead.', 'Engineering & Technology'),
]
OPTIONS = [('Not like me', 0), ('A little like me', 1), ('Like me', 2), ('Very much like me', 3)]


def ensure_seed_data(db, career_data):
    for category, info in career_data.items():
        values = (category, info['blurb'], json.dumps(info['courses']),
                  json.dumps(info['colleges']), json.dumps(info['jobs']),
                  json.dumps(info['roadmap']))
        db.execute(
            '''INSERT INTO career_recommendations (category, blurb, courses, colleges, jobs, roadmap)
               VALUES (%s,%s,%s,%s,%s,%s)
               ON DUPLICATE KEY UPDATE blurb=VALUES(blurb), courses=VALUES(courses),
               colleges=VALUES(colleges), jobs=VALUES(jobs), roadmap=VALUES(roadmap)''',
            values
        )
    for text, category in QUESTION_SEED:
        db.execute(
                '''INSERT INTO questions (question_text, category, status)
                    SELECT %s,%s,'published'
               WHERE NOT EXISTS (SELECT 1 FROM questions WHERE question_text=%s)''',
            (text, category, text)
        )
    for q in db.execute('SELECT id FROM questions ORDER BY id').fetchall():
        for label, score in OPTIONS:
            db.execute(
                     '''INSERT INTO question_options (question_id, option_text, score)
                         SELECT %s,%s,%s
                   WHERE NOT EXISTS (SELECT 1 FROM question_options WHERE question_id=%s AND score=%s)''',
                (q['id'], label, score, q['id'], score)
            )
    db.commit()


def get_published_questions(db):
    rows = db.execute(
        '''SELECT q.id,q.question_text AS text,q.category,q.status,
                  qo.id AS option_id,qo.option_text,qo.score
           FROM questions q JOIN question_options qo ON qo.question_id=q.id
           WHERE q.status='published' ORDER BY q.id,qo.score'''
    ).fetchall()
    grouped = {}
    for row in rows:
        item = grouped.setdefault(row['id'], {'id': row['id'], 'text': row['text'],
            'category': row['category'], 'status': row['status'], 'options': []})
        item['options'].append({'id': row['option_id'], 'text': row['option_text'], 'score': row['score']})
    return list(grouped.values())


def get_question(db, question_id):
    return db.execute(
        'SELECT id,question_text,category,status,created_at,updated_at FROM questions WHERE id=%s',
        (question_id,)).fetchone()


def create_question(db, question_text, category, status='draft'):
    cur = db.execute('INSERT INTO questions (question_text,category,status) VALUES (%s,%s,%s)',
                     (question_text, category, status))
    for label, score in OPTIONS:
        db.execute('INSERT INTO question_options (question_id,option_text,score) VALUES (%s,%s,%s)',
                   (cur.lastrowid, label, score))
    db.commit()
    return get_question(db, cur.lastrowid)


def update_question(db, question_id, question_text, category, status):
    cur = db.execute('UPDATE questions SET question_text=%s,category=%s,status=%s WHERE id=%s',
                     (question_text, category, status, question_id))
    if cur.rowcount == 0:
        db.rollback(); return None
    db.commit(); return get_question(db, question_id)


def delete_question(db, question_id):
    cur = db.execute('DELETE FROM questions WHERE id=%s', (question_id,))
    db.commit(); return cur.rowcount > 0


def score_and_record(db, user_id, answers):
    scores = {c: 0 for c in CATEGORIES}
    question_rows = db.execute("SELECT id FROM questions WHERE status='published'").fetchall()
    valid_ids = {r['id'] for r in question_rows}
    if set(answers) != valid_ids:
        raise ValueError('Please answer every question before submitting.')
    for question_id, option_id in answers.items():
        option = db.execute(
            '''SELECT qo.id,qo.score,q.category FROM question_options qo
               JOIN questions q ON q.id=qo.question_id
               WHERE qo.question_id=%s AND qo.score=%s AND q.status='published' ''',
            (question_id, option_id)).fetchone()
        if option is None:
            raise ValueError('One or more quiz answers are invalid.')
        scores[option['category']] += int(option['score'])
        db.execute('INSERT INTO user_responses (user_id,question_id,option_id,score) VALUES (%s,%s,%s,%s)',
                   (user_id, question_id, option['id'], option['score']))
    return max(scores, key=scores.get), scores
