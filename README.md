# Job-Application Agents

Think of this like a small robot team that hunts jobs for you. You give the robots a brain (any AI model you like), and they find job posts, rewrite your resume for each one, and apply — by email or straight on job websites.

No single company is required. Any brain, any computer.

---

## Parts list (what you need)

- **Python 3.10+** on your computer
- **A brain** — an AI model. Free local option works, paid keys work too
- **Gmail** *(optional)* — only if you want the robots to send emails
- **A browser** *(optional)* — only if you want the robots to apply on job websites

---

## Assembly — 5 simple steps

### Step 1: Get the parts

```bash
git clone https://github.com/YOUR_USERNAME/job-application-agents.git
cd job-application-agents
pip install -r requirements.txt
```

If you want website applying later, also run:

```bash
playwright install chromium
```

### Step 2: Tell the robots who you are

```bash
cp config/candidate.example.yaml config/candidate.yaml
```

Open `config/candidate.yaml` in any text editor and fill in your name, skills, jobs, and how you answer application forms. **This file is the single source of truth** — the robots never invent facts, everything they write comes from here. It stays on your computer and is never uploaded.

### Step 3: Plug in a brain (pick ONE)

```bash
cp .env.example .env
```

Open `.env` and set two lines. Easiest first:

**Free, runs on your own computer (Ollama):**
```bash
# 1) install ollama from https://ollama.com, then: ollama pull llama3.1:8b
LLM_PROVIDER=ollama
LLM_MODEL=llama3.1:8b
```

**Or OpenAI:**
```bash
LLM_PROVIDER=openai
LLM_API_KEY=sk-your-key-here
```

**Or Anthropic:**
```bash
LLM_PROVIDER=anthropic
LLM_API_KEY=sk-ant-your-key-here
```

More options (Gemini, Groq, Together, OpenRouter, LM Studio, or any custom server) are listed with examples in `.env.example`. Switching brains later = changing these two lines. Nothing else changes.

### Step 4 (optional): Plug in Gmail

Only needed if you want robots to send application emails.

```bash
# in .env:
GMAIL_MODE=smtp
GMAIL_ADDRESS=you@gmail.com
GMAIL_APP_PASSWORD=xxxx-xxxx-xxxx-xxxx
```

Get the app password at: Google Account → Security → 2-Step Verification → App passwords. (Safer than your real password, and you can revoke it anytime.)

### Step 5 (optional): Teach the robots your logins

Only needed if you want robots to apply on job websites (LinkedIn, Indeed, Dice, …).

```bash
python -m src.main --search-board linkedin --query "AI Engineer" --headed
```

A real browser window opens. **Log in yourself**, then press Enter in the terminal. The login is saved on your computer, so future runs can work without showing the browser. Repeat once per website.

### Step 6 (optional): Put it on autopilot — the cron job

Tired of running it by hand? A cron job is an alarm clock for your computer: it runs the robots for you on a schedule.

**1. Install the schedule** (default: every day at 9:30 AM, in safe dry-run mode):

```bash
./scripts/install_cron.sh
```

This creates `state/input.txt` for you. **Paste your real job posts into that file** — the cron job reads it every run.

**2. When the drafts look good, switch it to live** (actually applies):

```bash
./scripts/install_cron.sh --live --resume resume.pdf --time 09:30
```

Other useful options: `--time 18:00` (run at 6 PM), `--max-jobs 10` (up to 10 jobs per run).

Every run appends results to `state/applications.json` (never applies twice to the same job) and logs to `state/logs/`.

**Check / remove it:**
```bash
crontab -l                    # see the installed schedule
./scripts/uninstall_cron.sh   # remove it
```

**On Windows:** open Task Scheduler → Create Basic Task → set it to run daily, with the action `python -m src.main --input state/input.txt` starting in the project folder.

---

## Running the robots

**Test run — safe, changes nothing, sends nothing:**
```bash
python -m src.main --input examples/sample_signal.txt --dry-run
```

**Real run — actually applies (needs Step 4 and/or 5 done):**
```bash
python -m src.main --input my_jobs.txt --max-jobs 5 --resume resume.pdf --board-apply
```

**Search a job website directly:**
```bash
python -m src.main --search-board indeed --query "ML Engineer" --location "Remote"
```

Where do job posts come from? You paste them into a text file — a Hacker News hiring thread, founder posts, career pages, anything. The Sourcer robot (below) turns that mess into neat job cards.

---

## The robots — what each one does

**1. Sourcer — the scout.**
Reads messy text (job posts you pasted) and writes neat job cards: company, role, location, the full job description, and the contact email if the post has one. Skips anything you've already touched.

**2. Tailor — the resume writer.**
Takes one job description and rewrites your resume bullets to speak that job's language. It may reword, but it never invents — every fact comes from your `candidate.yaml`.

**3. Outreach — the email writer.**
Writes a short application email (80–150 words). It opens with something specific about the company, ties one of your real achievements to their job, and ends with one simple ask. Not a boring cover letter.

**4. ApplyAgent — the hands.**
The only robot that touches the outside world. For each job it picks a route:
- *Has a contact email?* → sends the email through your Gmail with your resume attached. Counts as done only when Gmail confirms it sent.
- *Has a job-website link?* → opens the page in the browser, reads every field on the application form, asks the brain what to type where, uploads your resume, clicks submit. Counts as done only when the page says "application received" (or similar).
- *Neither?* → marks it "needs you" and moves on. It never guesses or fakes a submission.

If it hits a CAPTCHA or a phone-code screen, it stops that job and tells you — it never tries to sneak past human checks.

**5. Coordinator — the manager.**
Runs the whole team in order: scout → dedupe (skip jobs you already applied to) → tailor → draft email → apply. Remembers everything in `state/applications.json` so the next run never repeats work.

```
you paste job posts
        ↓
   [Sourcer] makes neat job cards
        ↓
   [Coordinator] skips jobs you already did
        ↓
   [Tailor] rewrites your resume per job
        ↓
   [Outreach] drafts the email
        ↓
   [ApplyAgent] sends it or applies on the website
        ↓
   saved to state/applications.json — never applied twice
```

---

## If something breaks

- **"No brain connected"** → check `LLM_PROVIDER` and `LLM_API_KEY` in `.env`.
- **Emails won't send** → check `GMAIL_ADDRESS` / `GMAIL_APP_PASSWORD` in `.env`.
- **Website applying acts weird** → job sites change their pages often. Look at the screenshot saved in `state/` to see what the robot saw.
- **A job needs a login** → redo Step 5 for that website.
- **Start over safely** → every real run is preceded by `--dry-run`. Drafts cost nothing.

Keys live only in `.env` (never uploaded to GitHub). Your personal details live only in `config/candidate.yaml` (never uploaded either).

## Developers

Run the test suite (no API keys needed — the tests use a fake brain):

```bash
pip install -r requirements-dev.txt
python -m pytest tests/ -q
```
