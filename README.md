# Django Quiz App

A web-based quiz platform where students take timed practice tests with instant
scoring and feedback, and instructors build question banks and quizzes and
track performance. Built with Django, Django REST Framework, and Bootstrap.

See [`PRD_Django_Quiz_App.md`](PRD_Django_Quiz_App.md) for the original product
requirements this app was built against.

## Features

**Students**
- Browse quizzes by category, difficulty, and duration
- Timed quiz-taking with countdown auto-submit, question navigation (next/prev/jump),
  mark-for-review, and progress indicator
- Instant scoring with a question-by-question review, correct answers, and explanations
- Personal dashboard: quiz history, average score, score trend chart, weak-area
  breakdown by category
- Global and per-quiz leaderboards
- Adaptive practice quizzes that select questions weighted toward the
  difficulty levels a student has historically struggled with

**Instructors / admins**
- Manage categories, questions (single-choice, multi-select, true/false, with
  optional images), choices, and quizzes via the Django admin
- Bulk-import questions from a CSV template, validated up front — a bad file
  is rejected with row-by-row errors and nothing is written until the whole
  file is clean
- Per-quiz analytics: completion rate, average score, pass count, most-missed
  questions
- CSV export of quiz results
- Question tagging

**Platform**
- Email verification on registration, and reminder emails for quizzes that
  are about to time out or were auto-submitted (via a management command
  meant to run on a schedule)
- A read-only + attempt-taking JSON API (Django REST Framework, token auth)
  for a future mobile client
- Accessibility basics: skip link, keyboard-navigable quiz UI, ARIA live
  regions for the timer/progress, labeled form controls, alt text on question
  images

## Tech stack

- **Backend:** Django 5.2 (LTS), Django REST Framework
- **Frontend:** Django templates + Bootstrap 5 (via CDN), vanilla JS, Chart.js
- **Database:** SQLite (dev). PostgreSQL is a drop-in swap for production —
  see [Production notes](#production-notes)
- **Auth:** Django's built-in auth with a custom `User` model (`role`:
  student/instructor), DRF token auth for the API
- **Images:** Pillow

## Project layout

```
config/       Django project settings, root URLconf
accounts/     Custom User model, registration, login, password reset, email verification
quizzes/      Core domain: categories, questions, choices, quizzes, attempts, grading,
              instructor analytics, bulk import, leaderboard
              quizzes/services.py   shared grading/selection logic (used by the web
                                    views, the API, and the reminder command)
              quizzes/management/commands/send_quiz_reminders.py
api/          DRF serializers/views/urls for the JSON API
templates/    All HTML templates (Bootstrap-based)
static/       Project static files
media/        User-uploaded question images (created at runtime, gitignored)
```

## Setup

Requires Python 3.10+.

```bash
python3 -m venv .venv
source .venv/bin/activate          # .venv\Scripts\activate on Windows
pip install -r requirements.txt

python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Visit `http://127.0.0.1:8000/`. Log in to `/admin/` with your superuser to
create categories, questions, and quizzes. To let another account act as an
instructor, either set its `role` to `Instructor` or give it `is_staff` —
either one unlocks the `/manage/` analytics section, but note `is_staff` is
also required to log into `/admin/` itself to manage content.

### Environment variables (email)

By default, emails (registration verification, quiz reminders) are printed to
the console — nothing is configured or required to run the app locally.

To send real email, copy `.env.example` to `.env` and fill in SMTP
credentials (the template includes step-by-step instructions for Gmail App
Passwords). `.env` is gitignored; the app falls back to the console backend
automatically if `EMAIL_HOST_USER` isn't set.

### Quiz reminder emails

`send_quiz_reminders` auto-submits any quiz attempt whose timer has expired
and emails students whose attempt is about to run out of time. It's designed
to run periodically, e.g. via cron:

```bash
python manage.py send_quiz_reminders                      # run for real
python manage.py send_quiz_reminders --dry-run             # preview only
python manage.py send_quiz_reminders --reminder-minutes 10  # customize the warning window
```

### Bulk question import

From `/manage/questions/import/` (instructor accounts only), download the CSV
template for the exact column format, or use this shape directly:

```
category,question_text,question_type,difficulty,explanation,choices,correct_answers,tags
General Science,What is the boiling point of water (Celsius)?,single,easy,Water boils at 100C at sea level.,100|90|80|120,100,chemistry|physics
```

`question_type` is one of `single`, `multi`, `true_false`. Choices, correct
answers, and tags are pipe (`|`) separated. The category must already exist;
tags are created automatically. The whole file is validated before anything
is written — if any row has an error, nothing is imported.

## JSON API

Base path: `/api/v1/`. Auth is via DRF token auth (`Authorization: Token <key>`).

| Endpoint | Method | Auth | Description |
|---|---|---|---|
| `/auth/register/` | POST | none | Create a student account, returns a token |
| `/auth/token/` | POST | none | Exchange username/password for a token |
| `/categories/` | GET | none | List categories |
| `/quizzes/` | GET | none | List active quizzes (`?category=`, `?difficulty=`, `?duration=`) |
| `/quizzes/{id}/` | GET | none | Quiz detail |
| `/quizzes/{id}/start/` | POST | token | Start or resume an attempt; returns questions with choices (no answer key) |
| `/attempts/{id}/` | GET | token | Current attempt state (for resuming) |
| `/attempts/{id}/submit/` | POST | token | Submit `{"answers": [{"question_id": 1, "choice_ids": [3]}]}`; grades and returns the result |
| `/attempts/{id}/result/` | GET | token | Full result with correct answers and explanations |
| `/history/` | GET | token | The authenticated user's completed attempts |

Correct answers are never exposed until after an attempt is submitted or
finalized. A user can only see their own attempts.

## Testing

There is no automated test suite yet (`accounts/tests.py`, `quizzes/tests.py`,
and `api/tests.py` are just Django's empty boilerplate stubs — `python manage.py
test` will run but exercise nothing). Each feature was verified manually
during development via scripted HTTP flows (registration → start quiz →
submit → grading → results) rather than unit tests. Adding real test coverage
is a good next step before relying on this in production.

## Production notes

This was built and tested against SQLite for local development, per the PRD.
Before deploying:

- Switch `DATABASES` in `config/settings.py` to PostgreSQL (the PRD's
  recommended production database)
- Set `DEBUG = False`, a real `SECRET_KEY` (move it to an environment
  variable), and `ALLOWED_HOSTS`
- Serve static/media files properly (e.g. WhiteNoise or a CDN, not Django's
  dev server)
- Put `send_quiz_reminders` on an actual cron schedule
- Configure real SMTP credentials (see [Environment variables](#environment-variables-email))
