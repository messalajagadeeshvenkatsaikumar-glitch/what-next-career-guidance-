from flask import Blueprint, jsonify, request, current_app, session
from .services import get_question, create_question, update_question, delete_question

question_management_bp = Blueprint('question_management', __name__, url_prefix='/api/questions')


def _db():
    return current_app.extensions['main_db']()


def _require_admin():
    if not session.get('is_admin'):
        return jsonify({'error': 'Admin authentication required.'}), 401
    return None


def _serialize(row):
    return dict(row) if row else None


@question_management_bp.get('')
def list_questions():
    unauthorized = _require_admin()
    if unauthorized:
        return unauthorized
    rows = _db().execute('SELECT id,question_text,category,status,created_at,updated_at FROM questions ORDER BY id').fetchall()
    return jsonify([_serialize(r) for r in rows])


@question_management_bp.get('/<int:question_id>')
def read_question(question_id):
    unauthorized = _require_admin()
    if unauthorized:
        return unauthorized
    row = get_question(_db(), question_id)
    return (jsonify(_serialize(row)) if row else (jsonify({'error':'Question not found.'}), 404))


@question_management_bp.post('')
def add_question():
    unauthorized = _require_admin()
    if unauthorized:
        return unauthorized
    p = request.get_json(silent=True) or {}
    text, category = str(p.get('question_text','')).strip(), str(p.get('category','')).strip()
    status = str(p.get('status','draft')).strip().lower()
    if not text or not category or status not in {'draft','published','archived'}:
        return jsonify({'error':'question_text, category and a valid status are required.'}), 400
    row = create_question(_db(), text, category, status)
    return jsonify({'message':'Question created.','question':_serialize(row)}), 201


@question_management_bp.put('/<int:question_id>')
def edit_question(question_id):
    unauthorized = _require_admin()
    if unauthorized:
        return unauthorized
    p = request.get_json(silent=True) or {}
    text, category = str(p.get('question_text','')).strip(), str(p.get('category','')).strip()
    status = str(p.get('status','draft')).strip().lower()
    if not text or not category or status not in {'draft','published','archived'}:
        return jsonify({'error':'question_text, category and a valid status are required.'}), 400
    row = update_question(_db(), question_id, text, category, status)
    return (jsonify({'message':'Question updated.','question':_serialize(row)}) if row
            else (jsonify({'error':'Question not found.'}), 404))


@question_management_bp.delete('/<int:question_id>')
def remove_question(question_id):
    unauthorized = _require_admin()
    if unauthorized:
        return unauthorized
    if not delete_question(_db(), question_id):
        return jsonify({'error':'Question not found.'}), 404
    return jsonify({'message':'Question deleted.'})
