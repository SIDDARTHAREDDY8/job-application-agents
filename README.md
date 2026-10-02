# Job-Application Agents (LLM-agnostic)

Autonomous agents that take a job hunt from signal to submitted application:

1. **Sourcer** — extracts structured job leads from raw text (HN hiring threads, X posts, career pages, VC boards)
2. **Tailor** — rewrites your resume bullets to mirror each JD (never invents facts)
3. **Outreach** — drafts a short, problem-first application email (not a cover letter)
4. **ApplyAgent** — actually submits: sends via **Gmail** (resume attached) or drives **Playwright** through job boards and ATS forms
5. **Coordinator** — runs source → dedupe → tailor → draft → apply, with JSON state

Any LLM can drive them: OpenAI, Anthropic, Gemini, Ollama, OpenRouter, Groq, Together, DeepSeek, Mistral, LM Studio, or any OpenAI-compatible endpoint. Runs on any computer: everything is `pip install` + `.env`.

---

## 1. Setup

```bash
git clone https://github.com/YOUR_USERNAME/job-application-agents.git
cd job-application-agents
pip install -r requirements.txt
playwright install chromium        # only needed for the board-apply route

cp .env.example .env
cp config/candidate.example.yaml config/candidate.yaml
```

Edit `config/candidate.yaml` with **your** details (including `form_answers` for application forms). The agents never invent facts — everything they write traces back to this file.

## 2. Connect an LLM

All LLM config lives in `.env`. Pick **one** provider:

| Provider | `.env` settings |
|---|---|
| **OpenAI** | `LLM_PROVIDER=openai` + `LLM_API_KEY=sk-...` |
| **Anthropic** | `LLM_PROVIDER=anthropic` + `LLM_API_KEY=sk-ant-...` |
| **Gemini** | `LLM_PROVIDER=gemini` + `LLM_API_KEY=...` (from Google AI Studio) |
| **Ollama** (local, free) | `LLM_PROVIDER=ollama` (no key needed). Optional: `LLM_MODEL=llama3.1:8b`, `LLM_BASE_URL=http://localhost:11434/v1` |
| **OpenRouter** | `LLM_PROVIDER=openrouter` + `LLM_API_KEY=...` |
| **Groq** | `LLM_PROVIDER=groq` + `LLM_API_KEY=gsk_...` |
| **Together** | `LLM_PROVIDER=together` + `LLM_API_KEY=...` |
| **LM Studio** (local) | `LLM_PROVIDER=lmstudio` (no key; start the server first) |
| **Any OpenAI-compatible API** | `LLM_PROVIDER=custom` + `LLM_BASE_URL=https://...` + `LLM_API_KEY=...` |

Optional overrides (any provider):

```bash
LLM_MODEL=gpt-4o-mini        # default per provider if omitted
LLM_TEMPERATURE=0.7
LLM_MAX_TOKENS=2000
```

### Quick examples

**Ollama (local, no API key):**
```bash
ollama pull llama3.1:8b
# .env:
LLM_PROVIDER=ollama
LLM_MODEL=llama3.1:8b
```

**Anthropic:**
```bash
# .env:
LLM_PROVIDER=anthropic
LLM_API_KEY=sk-ant-your-key
LLM_MODEL=claude-sonnet-4-20250514
```

**OpenRouter (many models, one key):**
```bash
# .env:
LLM_PROVIDER=openrouter
LLM_API_KEY=sk-or-your-key
LLM_MODEL=openai/gpt-4o-mini
```

### Switching models in code

```python
from src.llm import create

llm = create(provider="anthropic", model="claude-sonnet-4-20250514", api_key="sk-ant-...")
# or: llm = create(provider="ollama", model="llama3.1:8b")
# or: llm = create(provider="custom", model="my-model",
#                 base_url="https://my-endpoint/v1", api_key="...")
```

## 3. Run (draft mode — safe)

```bash
python -m src.main --input examples/sample_signal.txt --dry-run
```

This runs source → dedupe → tailor → draft and prints the results. It sends nothing, submits nothing, writes no state.

## 4. Connect Gmail (email-apply route)

Jobs with a contact email are applied to by email, resume attached. Two modes:

**SMTP (simplest):**
```bash
# .env:
GMAIL_MODE=smtp
GMAIL_ADDRESS=you@gmail.com
GMAIL_APP_PASSWORD=xxxx-xxxx-xxxx-xxxx
```
Create the app password at Google Account → Security → 2-Step Verification → App passwords.

**Gmail API (OAuth):**
```bash
# .env:
GMAIL_MODE=api
GMAIL_ADDRESS=you@gmail.com
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
```
(Get these at Google Cloud → APIs & Services → Credentials → OAuth client ID, Desktop app. Enable the Gmail API.) First run opens a browser to authorize; the token is cached in `state/gmail_token.json`.

## 5. Connect the browser (board-apply route)

Job-board and ATS applications are driven with Playwright:

```bash
playwright install chromium
```

**First run — log in once:**
```bash
python -m src.main --search-board linkedin --query "AI Engineer" --headed
```
A browser window opens. Log in to the board manually, then press Enter in the terminal. The session persists in `state/browser_profile/` — later runs are headless and stay logged in. Repeat for each board you use (Indeed, Dice, ZipRecruiter, Glassdoor).

**Search a board directly:**
```bash
python -m src.main --search-board linkedin --query "AI Engineer" --location "Remote"
python -m src.main --search-board indeed --query "ML Platform Engineer" --location "New York"
```

**Full apply run (actually submits):**
```bash
python -m src.main --input my_signals.txt --max-jobs 5 --resume resume.pdf --board-apply
```

How a board apply works: the agent opens the job page, extracts every form field (with labels), asks your LLM to map your `candidate.yaml` data onto the fields, fills them, uploads your resume, clicks submit — and counts the application **only** if a confirmation marker ("application received", "thank you for applying", …) appears on the page. CAPTCHAs and OTP screens abort the item with a note instead of being retried.

Supported boards/ATS: `greenhouse`, `lever`, `ashby`, `workable` (single-page ATS forms) and `linkedin`, `indeed`, `dice`, `ziprecruiter`, `glassdoor` (guided multi-step flows). Board selectors change over time — treat the classic-board adapters as best-effort and check the screenshot in `state/` when something looks off.

## 6. MCP connections

Any MCP server can be plugged in alongside (or instead of) the built-ins:

```bash
# .env:
MCP_SERVERS={"playwright": {"command": "npx", "args": ["-y", "@playwright/mcp@latest"]}}
```

```python
from src.connectors import MCPClient

client = MCPClient.from_env("playwright")
print(client.describe_sync())          # what tools the server offers
client.call_tool_sync("browser_navigate", {"url": "https://example.com"})
```

SSE servers work too: `{"mytools": {"url": "http://localhost:8000/sse"}}`.

## 7. Use agents individually

```python
from dotenv import load_dotenv
load_dotenv()
import yaml
from src.llm import from_env
from src.agents import SourcerAgent, TailorAgent, OutreachAgent, ApplyAgent
from src.connectors.gmail import from_env as gmail_from_env
from src.browser import PlaywrightManager

llm = from_env()  # reads .env
candidate = yaml.safe_load(open("config/candidate.yaml"))

jobs = SourcerAgent(llm, candidate).extract(open("my_signals.txt").read())["jobs"]
tailored = TailorAgent(llm, candidate).tailor(jobs[0]["jd_text"])
email = OutreachAgent(llm, candidate).draft(jobs[0], tailored)

with PlaywrightManager(headless=True) as driver:
    applier = ApplyAgent(llm, candidate, driver=driver, gmail=gmail_from_env())
    result = applier.apply(jobs[0], tailored, resume_path="resume.pdf", dry_run=False)
print(result["status"], result.get("note"))
```

## 8. How it works

```
raw hiring signals (you collect: HN, X posts, career pages, board searches)
        |
   SourcerAgent  ->  {company, role, jd_text, contact_email, apply_url, ...}  (JSON only)
        |
   dedupe vs state/applications.json (company+role, email)
        |
   TailorAgent   ->  resume bullets reworded for the JD (facts unchanged)
        |
   OutreachAgent ->  {subject, body}  80-150 words, problem-first (always drafted)
        |
   ApplyAgent --- contact_email? ---> GmailSender -> send + receipt
        |                                    (applied only with a message id)
        +--- board/ATS URL? ---> Playwright -> fill via LLM -> upload resume
                                 -> submit -> confirmation marker?
                                                (applied only if seen)
        |
   state/applications.json  (dry-run writes nothing)
```

Rules the machine enforces: dry-run is the default; a send counts only with a provider receipt; a board submit counts only with an on-page confirmation; CAPTCHA/OTP aborts the item; nothing is ever retried blindly.

## 9. Project layout

```
src/
  llm/
    base.py        # LLMClient interface
    factory.py     # create() / from_env() - the "connect any LLM" entry point
    providers.py   # OpenAI-compatible, Anthropic, Gemini implementations
  agents/
    sourcer.py     # extract structured jobs from raw text
    tailor.py      # JD-tailored resume bullets
    outreach.py    # problem-first application email
    apply.py       # ApplyAgent: routes email vs board, verifies everything
    coordinator.py # end-to-end run + dedupe + state
  connectors/
    gmail.py       # GmailSender: SMTP (app password) or Gmail API (OAuth)
    mcp_client.py  # MCPClient: plug any MCP server into the agents
  browser/
    playwright_driver.py  # PlaywrightManager: persistent session, form extraction
  boards/
    base.py        # BoardAdapter + shared ATS / guided-apply flows
    registry.py    # get_adapter(url) -> adapter
    greenhouse.py lever.py ashby.py workable.py      # ATS adapters
    linkedin.py indeed.py dice.py ziprecruiter.py glassdoor.py  # board adapters
  main.py          # CLI
config/
  candidate.example.yaml   # your facts + form_answers (copy to candidate.yaml)
examples/
  sample_signal.txt
```

## 10. Notes

- The agents output **drafts** in dry-run mode. Review before any real run — you own the sends.
- Never put secrets in `config/`; keys live only in `.env` (git-ignored).
- Board sites change their markup; when an adapter misbehaves, open the screenshot in `state/` and update the selectors in `src/boards/<board>.py`.
- Keep automation human-paced on boards you care about; aggressive use risks the account.
- Built from a production job-hunt machine that runs these lanes daily; this repo is the portable, sanitized core — same pipeline, any model, any computer.
