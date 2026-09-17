import random
from datetime import timedelta

from django.utils import timezone

from .models import Attempt, AttemptAnswer, Choice, Question


def ordered_questions(question_order):
    """Fetch questions for an attempt in the order stored on it.

    Looks questions up directly by id (not scoped to a quiz's fixed question
    set), since adaptive attempts pull questions ad hoc from the category pool
    rather than from a fixed QuizQuestion set.
    """
    questions_by_id = {
        q.id: q for q in Question.objects.filter(id__in=question_order).prefetch_related('choices')
    }
    return [questions_by_id[qid] for qid in question_order if qid in questions_by_id]


def time_remaining_seconds(attempt):
    deadline = attempt.start_time + timedelta(minutes=attempt.quiz.time_limit_minutes)
    return (deadline - timezone.now()).total_seconds()


def grade_and_complete_answers(attempt, answers, timed_out=False):
    """Grade an attempt given a mapping of {question_id: [selected_choice_id, ...]}."""
    questions = ordered_questions(attempt.question_order)
    correct_count = 0

    for question in questions:
        selected_ids = {int(v) for v in answers.get(question.id, [])}
        correct_ids = set(question.choices.filter(is_correct=True).values_list('id', flat=True))
        is_correct = bool(selected_ids) and selected_ids == correct_ids

        answer, _ = AttemptAnswer.objects.update_or_create(
            attempt=attempt, question=question, defaults={'is_correct': is_correct}
        )
        answer.selected_choices.set(Choice.objects.filter(id__in=selected_ids))
        if is_correct:
            correct_count += 1

    total = len(questions) or 1
    attempt.correct_count = correct_count
    attempt.score_percent = round((correct_count / total) * 100, 2)
    attempt.status = Attempt.Status.TIMED_OUT if timed_out else Attempt.Status.COMPLETED
    attempt.end_time = timezone.now()
    attempt.save()
    return attempt


def grade_and_complete(attempt, post_data, timed_out=False):
    """Grade an attempt from a Django request.POST-like object (web form submission)."""
    questions = ordered_questions(attempt.question_order)
    answers = {}
    for question in questions:
        if hasattr(post_data, 'getlist'):
            answers[question.id] = post_data.getlist(f'question_{question.id}')
    return grade_and_complete_answers(attempt, answers, timed_out=timed_out)


def select_fixed_questions(quiz):
    question_ids = list(quiz.questions.values_list('id', flat=True))
    if quiz.shuffle_questions:
        random.shuffle(question_ids)
    return question_ids


def select_adaptive_questions(user, quiz):
    """Pick `quiz.adaptive_question_count` questions from the quiz's category pool,
    weighted toward the difficulty levels the student has historically struggled
    with in that category. Falls back to even weighting when there's no history.
    """
    pool = list(quiz.category.questions.values_list('id', 'difficulty'))
    if not pool:
        return []

    by_difficulty = {}
    for question_id, difficulty in pool:
        by_difficulty.setdefault(difficulty, []).append(question_id)

    difficulties = list(by_difficulty.keys())

    history = AttemptAnswer.objects.filter(
        attempt__user=user,
        attempt__quiz__category=quiz.category,
        attempt__status__in=[Attempt.Status.COMPLETED, Attempt.Status.TIMED_OUT],
        question__difficulty__in=difficulties,
    ).values_list('question__difficulty', 'is_correct')

    seen = {d: [0, 0] for d in difficulties}  # difficulty -> [attempts, correct]
    for difficulty, is_correct in history:
        seen[difficulty][0] += 1
        if is_correct:
            seen[difficulty][1] += 1

    # Weight = inverse accuracy (weaker difficulty drawn more often); an untried
    # difficulty gets a neutral 0.5 "accuracy" so it's neither favored nor starved.
    weights = {}
    for difficulty in difficulties:
        attempts, correct = seen[difficulty]
        accuracy = (correct / attempts) if attempts else 0.5
        weights[difficulty] = max(1 - accuracy, 0.1)

    total_weight = sum(weights.values())
    target_count = min(quiz.adaptive_question_count, len(pool))

    counts_per_difficulty = {}
    remaining = target_count
    for difficulty in difficulties[:-1]:
        share = round(target_count * weights[difficulty] / total_weight)
        share = min(share, len(by_difficulty[difficulty]), remaining)
        counts_per_difficulty[difficulty] = share
        remaining -= share
    counts_per_difficulty[difficulties[-1]] = min(remaining, len(by_difficulty[difficulties[-1]]))

    selected = []
    for difficulty, count in counts_per_difficulty.items():
        selected.extend(random.sample(by_difficulty[difficulty], count))

    # Top up from any remaining pool if rounding left us short of the target.
    if len(selected) < target_count:
        remaining_pool = [qid for qid, _ in pool if qid not in selected]
        top_up = min(target_count - len(selected), len(remaining_pool))
        selected.extend(random.sample(remaining_pool, top_up))

    random.shuffle(selected)
    return selected
