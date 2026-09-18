class Question:
    def __init__(self, id, question_text, category, status='published'):
        self.id = id
        self.question_text = question_text
        self.category = category
        self.status = status
