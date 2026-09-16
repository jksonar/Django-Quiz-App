# Product Requirements Document: Django Quiz App

**Document Owner:** [Your Name]
**Status:** Draft v1.0
**Last Updated:** September 16, 2026

---

## 1. Overview

### 1.1 Purpose
A web-based quiz platform built on Django that lets students take practice tests, review their performance, and improve mastery of subjects through repeated self-testing. Instructors/admins can create and manage question banks, quizzes, and track student progress.

### 1.2 Problem Statement
Students preparing for exams often lack a structured, low-friction way to practice with realistic test conditions (timed, scored, instant feedback) and to see where they're weak. Educators need an easy way to author and assign practice tests without building infrastructure from scratch.

### 1.3 Goals
- Let students take subject-wise or topic-wise practice tests anytime.
- Provide instant scoring, answer explanations, and performance analytics.
- Give instructors/admins a simple interface to create, edit, and organize quiz content.
- Track historical performance so students can measure improvement over time.

### 1.4 Non-Goals (v1)
- Live/proctored exams with webcam monitoring.
- Payment/subscription billing.
- Mobile native apps (web-responsive only for v1).
- AI-generated questions (may be a future phase).

---

## 2. Target Users & Personas

| Persona | Description | Key Needs |
|---|---|---|
| **Student** | High school/college student or exam aspirant | Practice tests, instant feedback, progress tracking |
| **Instructor/Admin** | Teacher or content creator | Create/manage questions, quizzes, categories; view class performance |
| **Guest (optional)** | Unregistered visitor | Try a sample quiz before signing up |

---

## 3. User Stories

### Student
- As a student, I want to browse quizzes by subject/category so I can find relevant practice tests.
- As a student, I want to take a timed quiz so I can simulate real exam conditions.
- As a student, I want to see my score and correct answers immediately after submission.
- As a student, I want to view explanations for wrong answers so I can learn from mistakes.
- As a student, I want to see my quiz history and score trends so I can track improvement.
- As a student, I want to retake a quiz to try improving my score.
- As a student, I want to bookmark/flag difficult questions for later review.

### Instructor/Admin
- As an admin, I want to create categories/subjects to organize quizzes.
- As an admin, I want to add, edit, and delete questions (MCQ, true/false, multi-select).
- As an admin, I want to group questions into a quiz with settings (time limit, passing score, shuffle).
- As an admin, I want to view aggregate student performance per quiz.
- As an admin, I want to import questions in bulk (CSV/Excel) to save time.

---

## 4. Functional Requirements

### 4.1 User Management
- Student & admin registration/login (Django auth, email verification optional).
- Role-based access control (student vs. instructor/admin vs. superuser).
- Profile page with basic info and quiz history.
- Password reset flow.

### 4.2 Quiz & Question Management (Admin)
- CRUD for Categories/Subjects (e.g., Math, Science, English).
- CRUD for Questions:
  - Question types: Single-choice MCQ, Multi-select, True/False.
  - Fields: question text, options, correct answer(s), explanation, difficulty level, category, tags.
  - Support image upload within a question (optional, v1.1).
- CRUD for Quizzes:
  - Title, description, category, difficulty, time limit, number of questions, passing score %, shuffle questions/options toggle, active/inactive status.
  - Ability to select questions manually or auto-generate randomly from a category pool.
- Bulk import questions via CSV template.

### 4.3 Quiz Taking (Student)
- Quiz listing page with filters (category, difficulty, duration).
- Quiz detail/instructions page before starting.
- Timed quiz-taking interface:
  - Countdown timer, auto-submit on timeout.
  - Question navigation (next/previous, jump to question, mark for review).
  - Progress indicator (e.g., "Question 5 of 20").
- Auto-save answers as the student progresses (prevent loss on refresh/disconnect).
- Submission and instant results page:
  - Score, percentage, pass/fail status.
  - Question-by-question review with correct answers and explanations.

### 4.4 Results & Analytics
- Student dashboard: quiz history, average score, score trend chart, weak-area breakdown by category.
- Admin dashboard: quiz-level analytics (average score, completion rate, most-missed questions).
- Downloadable/exportable results (CSV) for admins.

### 4.5 Notifications (optional, v1.1)
- Email confirmation on registration.
- Optional reminder emails for incomplete/assigned quizzes.

---

## 5. Non-Functional Requirements

| Category | Requirement |
|---|---|
| **Performance** | Quiz page loads in <2s; supports 500 concurrent quiz-takers (v1 target) |
| **Security** | CSRF protection, password hashing (Django default), rate-limiting on login, no client-side exposure of correct answers before submission |
| **Scalability** | Database designed to scale (PostgreSQL recommended over SQLite for production) |
| **Availability** | 99% uptime target |
| **Accessibility** | WCAG 2.1 AA basics (keyboard navigation, alt text, contrast) |
| **Responsiveness** | Fully usable on desktop, tablet, and mobile browsers |
| **Browser Support** | Latest 2 versions of Chrome, Firefox, Safari, Edge |

---

## 6. Technical Considerations

### 6.1 Suggested Stack
- **Backend:** Django + Django REST Framework (if API-driven frontend is desired)
- **Frontend:** Django templates + Bootstrap/Tailwind, or a separate React/Vue frontend consuming a DRF API
- **Database:** PostgreSQL (production), SQLite (local dev)
- **Auth:** Django's built-in auth system, extendable with `django-allauth` if social login is needed
- **Task Queue (optional):** Celery + Redis for scheduled reminder emails
- **Deployment:** Docker + Gunicorn + Nginx; hosting on Render/Railway/AWS/Heroku

### 6.2 Core Data Model (high-level)

- **User** (Django auth, extended with Profile: role, avatar)
- **Category** (name, description)
- **Question** (category FK, text, type, options, correct_answer, explanation, difficulty, image)
- **Choice** (question FK, text, is_correct) — for MCQ options
- **Quiz** (title, category FK, description, time_limit, pass_score, shuffle, is_active)
- **QuizQuestion** (quiz FK, question FK, order) — join table
- **Attempt** (user FK, quiz FK, start_time, end_time, score, status)
- **AttemptAnswer** (attempt FK, question FK, selected_choice(s), is_correct)

### 6.3 Key Screens/Pages
1. Landing / quiz catalog page
2. Quiz detail & instructions page
3. Quiz-taking interface
4. Results/review page
5. Student dashboard (history & analytics)
6. Admin: question bank manager
7. Admin: quiz builder
8. Admin: analytics dashboard
9. Auth pages (login, register, password reset)

---

## 7. Success Metrics (KPIs)

- Number of quizzes completed per week/month.
- Average quiz completion rate (started vs. finished).
- Student return rate (retakes / repeat visits within 30 days).
- Average score improvement across repeated attempts on same category.
- Admin content creation velocity (questions/quizzes added per week).

---

## 8. Milestones & Phasing

| Phase | Scope | Target Timeline |
|---|---|---|
| **Phase 1 (MVP)** | Auth, question/quiz CRUD, quiz-taking flow, instant results | Weeks 1–4 |
| **Phase 2** | Student dashboard & analytics, admin analytics, bulk import | Weeks 5–6 |
| **Phase 3** | Notifications, image support in questions, accessibility polish | Weeks 7–8 |
| **Phase 4 (Stretch)** | Question tagging & adaptive difficulty, leaderboard, API for mobile | Post-launch |

*(Timeline is illustrative — adjust to your team's actual velocity.)*

---

## 9. Risks & Open Questions

- **Open:** Should quizzes be assignable to specific students/classes, or fully self-serve/open catalog?
- **Open:** Is a leaderboard or gamification (badges, streaks) in scope for v1?
- **Open:** Do we need multi-tenancy (multiple schools/organizations) or single-institution use?
- **Risk:** Auto-save during quiz-taking adds complexity (need to handle network drops gracefully).
- **Risk:** Bulk question import needs strong validation to avoid malformed quizzes.

---

## 10. Appendix
- Wireframes/mockups: TBD
- API spec (if DRF is used): TBD
- Glossary: MCQ = Multiple Choice Question; Pass Score = minimum % required to pass a quiz
