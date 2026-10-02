# Job-Application Agents (LLM-agnostic)

Autonomous agents that turn hiring signals into tailored applications:

1. **Sourcer** - extracts structured job leads from raw text (HN hiring threads, X posts, career pages, VC boards)
2. **Tailor** - rewrites your resume bullets to mirror each JD (never invents facts)
3. **Outreach** - drafts a short, problem-first application email (not a cover letter)
4. **Coordinator** - runs source -> dedupe -> tailor -> draft, with JSON state

Any LLM can drive them: OpenAI, Anthropic, Gemini, Ollama, OpenRouter, Groq, Together, DeepSeek, Mistral, LM Studio, or any OpenAI-compatible endpoint.

---

## 1. Setup

```bash
git clone https://github.com/YOUR_USERNAME/job-application-agents.git
cd job-application-agents
pip install -r requirements.txt

cp .env.example .env
cp config/candidate.example.yaml config/candidate.yaml
```

Edit `config/candidate.yaml` with **your** details. The agents never invent facts -
everything they write traces back to this file.

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

## 3. Run

```bash
# Dry run: drafts only, writes nothing
python -m src.main --input examples/sample_signal.txt --dry-run

# Real run: saves drafts to state/applications.json
python -m src.main --input examples/sample_signal.txt --max-jobs 5
```

Your hiring signals go in a text file: paste HN "Who is hiring" excerpts, founder
X posts, career-page text, VC board listings - the Sourcer structures them.

## 4. Use agents individually

```python
from dotenv import load_dotenv
load_dotenv()
import yaml
from src.llm import from_env
from src.agents import SourcerAgent, TailorAgent, OutreachAgent

llm = from_env()  # reads .env
candidate = yaml.safe_load(open("config/candidate.yaml"))

jobs = SourcerAgent(llm, candidate).extract(open("my_signals.txt").read())["jobs"]
tailored = TailorAgent(llm, candidate).tailor(jobs[0]["jd_text"])
email = OutreachAgent(llm, candidate).draft(jobs[0], tailored)
print(email["subject"])
print(email["body"])
```

## 5. How it works

```
raw hiring signals (you collect)
        |
   SourcerAgent  ->  {company, role, jd_text, contact_email, ...}  (JSON only)
        |
   dedupe vs state/applications.json (company+role, email)
        |
   TailorAgent   ->  resume bullets reworded for the JD (facts unchanged)
        |
   OutreachAgent ->  {subject, body}  80-150 words, problem-first
        |
   state/applications.json  (dry-run writes nothing)
```

The LLM only ever returns JSON or email text. Sending is deliberately left to you -
wire `Coordinator` output to your own Gmail / ATS / mailer.

## 6. Project layout

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
    coordinator.py # end-to-end run + dedupe + state
  main.py          # CLI
config/
  candidate.example.yaml
examples/
  sample_signal.txt
```

## 7. Notes

- The agents output **drafts**. Review before sending - you own the send.
- Never put secrets in `config/`; keys live only in `.env` (git-ignored).
- Built from a production job-hunt machine that runs these lanes daily; this repo is the portable, sanitized core.
