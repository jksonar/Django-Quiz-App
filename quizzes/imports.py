import csv
import io

from django.db import transaction

from .models import Category, Choice, Question

REQUIRED_COLUMNS = {'category', 'question_text', 'question_type', 'choices', 'correct_answers'}
VALID_TYPES = {choice[0] for choice in Question.Type.choices}
VALID_DIFFICULTIES = {choice[0] for choice in Question.Difficulty.choices}


def parse_questions_csv(uploaded_file):
    """Parse and validate an uploaded CSV of questions.

    Returns (rows, errors). `rows` is a list of dicts ready to create Question/Choice
    objects; empty if `errors` is non-empty. Nothing is written to the database here.
    """
    errors = []
    rows = []

    try:
        text = uploaded_file.read().decode('utf-8-sig')
    except UnicodeDecodeError:
        return [], ['File is not valid UTF-8 text. Please export the CSV as UTF-8.']

    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None:
        return [], ['The file is empty or has no header row.']

    header = {(name or '').strip().lower() for name in reader.fieldnames}
    missing = REQUIRED_COLUMNS - header
    if missing:
        return [], [f"Missing required column(s): {', '.join(sorted(missing))}"]

    categories_by_name = {c.name.lower(): c for c in Category.objects.all()}

    for line_num, raw_row in enumerate(reader, start=2):
        row = {(k or '').strip().lower(): (v or '').strip() for k, v in raw_row.items()}
        row_errors = []

        category_name = row.get('category', '')
        category = categories_by_name.get(category_name.lower())
        if not category_name:
            row_errors.append('category is required')
        elif not category:
            row_errors.append(f"unknown category '{category_name}' (create it first)")

        text_value = row.get('question_text', '')
        if not text_value:
            row_errors.append('question_text is required')

        question_type = row.get('question_type', '').lower()
        if question_type not in VALID_TYPES:
            row_errors.append(f"question_type must be one of {sorted(VALID_TYPES)}")

        difficulty = row.get('difficulty', '').lower() or Question.Difficulty.MEDIUM
        if difficulty not in VALID_DIFFICULTIES:
            row_errors.append(f"difficulty must be one of {sorted(VALID_DIFFICULTIES)}")

        choices_raw = row.get('choices', '')
        choice_texts = [c.strip() for c in choices_raw.split('|') if c.strip()]
        if len(choice_texts) < 2:
            row_errors.append('choices must contain at least 2 pipe-separated options')
        if len(choice_texts) != len(set(choice_texts)):
            row_errors.append('choices contains duplicate options')

        correct_raw = row.get('correct_answers', '')
        correct_texts = [c.strip() for c in correct_raw.split('|') if c.strip()]
        if not correct_texts:
            row_errors.append('correct_answers is required')
        elif choice_texts:
            unknown_correct = set(correct_texts) - set(choice_texts)
            if unknown_correct:
                row_errors.append(f"correct_answers not found in choices: {', '.join(sorted(unknown_correct))}")
            if question_type in ('single', 'true_false') and len(correct_texts) != 1:
                row_errors.append(f"question_type '{question_type}' requires exactly 1 correct answer")

        if row_errors:
            errors.append(f"Row {line_num}: {'; '.join(row_errors)}")
            continue

        rows.append({
            'category': category,
            'text': text_value,
            'question_type': question_type,
            'difficulty': difficulty,
            'explanation': row.get('explanation', ''),
            'choices': [(c, c in correct_texts) for c in choice_texts],
        })

    if not rows and not errors:
        errors.append('No data rows found in the file.')

    return rows, errors


@transaction.atomic
def commit_questions(rows, created_by):
    created = []
    for row in rows:
        question = Question.objects.create(
            category=row['category'],
            text=row['text'],
            question_type=row['question_type'],
            difficulty=row['difficulty'],
            explanation=row['explanation'],
            created_by=created_by,
        )
        Choice.objects.bulk_create([
            Choice(question=question, text=choice_text, is_correct=is_correct)
            for choice_text, is_correct in row['choices']
        ])
        created.append(question)
    return created
