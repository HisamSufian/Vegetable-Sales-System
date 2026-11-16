# Sufi Vegetable Sales System

A private web app for a vegetable wholesale business: trips, sales, stock, farm owner and customer
money, profit and statements. FastAPI + Jinja2 + HTMX, Supabase (Postgres), hosted on Render.
One login. English only. AED only. Time zone Asia/Dubai.

## Run it on your PC (PowerShell, from the project folder)
```
venv\Scripts\activate
uvicorn app.main:app --reload
```
Open http://127.0.0.1:8000

## Tests (money maths and backup files; no database needed)
```
python -m unittest discover -s tests -t . -v
```
Run them before every deploy.

## Settings (.env on your PC, Environment Variables on Render)
`DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD, SUPABASE_URL, SUPABASE_KEY, ADMIN_EMAIL,
SESSION_SECRET, APP_ENV` (use `production` on Render). See `.env.example`. Never commit the real `.env`.

## Database files (run in this order in Supabase -> SQL Editor)
`sql/000_reset.sql` (empties the database; only for a fresh start), then `001` to `010`.
Each `0xx` file is run once. Never edit one that has already been run: add a new numbered file instead.

## Render web service
- Build: `pip install -r requirements.txt`
- Start: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- Python version: the `.python-version` file. Plan: Free.
- Keep-alive: cron-job.org calls `https://YOUR-APP.onrender.com/health` every 10 minutes.

## Backup
Settings -> "Download backup (zip)". One CSV per table, built on demand (nothing is stored on Render).

## Go-live checklist
1. Download a backup (Settings).
2. Clear the test data: run ONE of `sql/manual_clear_all_data.sql` or
   `sql/manual_clear_transactions_keep_profiles.sql` in the Supabase SQL Editor.
3. Fill in Settings: business name, phone, statement footer.
4. Render -> Environment: `APP_ENV=production`, and a NEW random `SESSION_SECRET`
   (`python -c "import secrets; print(secrets.token_hex(32))"`).
5. Supabase -> Authentication: sign-ups switched off, one user, a strong password.
6. cron-job.org: the job shows 200 OK; switch on its failure e-mail.
7. Check the Render Billing page (free hours) and that this is your only free Render service.
8. Install the app on your phone and do one test sale.

## Changing the system later
- Business rules live in `app/services` (`calc.py` money, `stock.py` stock). Change them there and
  add a test in `tests/`.
- Database changes are new numbered SQL files in `sql/`. Take a backup first.
- Make changes in a Git branch, test on your PC, then merge into `main` (Render deploys `main`).
