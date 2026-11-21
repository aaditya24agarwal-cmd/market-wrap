"""
WORKER 2: THE WRITER (version with retries + backup models)
Reads data.json (made by collector.py) and prompt.txt (the writing guide +
sample post), asks an AI to write the LinkedIn post, prints it, and saves it
as post.txt.

If Google's servers are busy, it waits, retries, and then tries the next
model on the list, and it tells you what it is doing the whole time.

Needs:   pip install google-genai
Key:     export GEMINI_API_KEY="your key"   (in the same Terminal window)
Run:     python writer.py
"""

import json
import os
import re
import sys
import time
from datetime import datetime

# ---- SETTINGS YOU CAN CHANGE ------------------------------------------
WRITER = "gemini"                 # "gemini" (free)  or  "claude" (paid, needs ANTHROPIC_API_KEY)
GEMINI_MODELS = [                 # tried in this order; first one that works wins
    "gemini-3.8-flash",
    "gemini-3.7-flash",
    "gemini-3.6-flash",
    "gemini-3.5-flash",
]
TRIES_PER_MODEL = 2               # how many times to try each model
TIMEOUT_SECONDS = 40              # give up on one try after this long
WAIT_SECONDS = 5                  # pause between tries
CLAUDE_MODEL = "claude-sonnet-5-5"
GUIDE_FILE = "prompt.txt"
SAMPLE_MARKER = "=== SAMPLE POST ==="
# -----------------------------------------------------------------------


def load_system_prompt():
    """Read prompt.txt: everything before the marker is the guide, after it is the sample."""
    try:
        with open(GUIDE_FILE, encoding="utf-8") as f:
            text = f.read()
    except FileNotFoundError:
        sys.exit(f"{GUIDE_FILE} not found. Put it in the same folder as writer.py.")

    guide, _, sample = text.partition(SAMPLE_MARKER)
    system = guide.strip()
    if sample.strip():
        system += (
            "\n\nHERE IS ONE SAMPLE POST. Copy its FORMAT, VOICE and LEVEL OF EXPLANATION. "
            "Its numbers, story and wording come from an imaginary day, so NEVER reuse "
            "them. Write a fresh post from the real data you are given.\n\n"
            "----- SAMPLE POST START -----\n"
            + sample.strip()
            + "\n----- SAMPLE POST END -----"
        )
    return system


def nice_date(iso_date):
    """2026-11-20 -> Fri 20 Nov 2026 (so the AI never has to guess the weekday)."""
    try:
        return datetime.strptime(iso_date, "%Y-%m-%d").strftime("%a %d %b %Y")
    except ValueError:
        return iso_date


def build_prompt(data):
    market_lines = []
    for m in data["markets"]:
        unit = "bps" if m["kind"] == "yield" else "%"
        market_lines.append(
            f"- {m['group']} | {m['name']}: {m['last']:,} "
            f"({m['change']:+}{unit}) as of {nice_date(m['as_of'])}"
        )
    headline_lines = [f"- [{h['source']}] {h['title']}" for h in data["headlines"]]
    return (
        f"Data collected at: {data['generated_at']}\n\n"
        "MARKET NUMBERS (latest close vs previous close):\n"
        + "\n".join(market_lines)
        + "\n\nNEWS HEADLINES (context only):\n"
        + "\n".join(headline_lines)
        + "\n\nWrite today's post now."
    )


def check_numbers(post, data):
    """Warn about any number in the post that is not in the collected data."""
    allowed = []
    for m in data["markets"]:
        allowed += [abs(m["change"]), abs(m["last"]), abs(m["prev"])]
    unmatched = []
    for raw in re.findall(r"\d[\d,]*\.?\d*", post):
        s = raw.rstrip(".,").replace(",", "")
        if not s:
            continue
        has_decimal = "." in s
        value = float(s)
        if not has_decimal and (value < 1000 or 1990 <= value <= 2100):
            continue  # small whole numbers (100 bps, S&P 500) and years are skipped
        tolerance = 0.0051 if has_decimal else 0.51
        if not any(abs(value - a) <= tolerance for a in allowed):
            unmatched.append(raw.rstrip(".,"))
    return unmatched


def make_client(key):
    """Create the Gemini client with a time limit and no hidden silent retries."""
    from google import genai
    from google.genai import types

    timeout_ms = TIMEOUT_SECONDS * 1000
    try:
        options = types.HttpOptions(
            timeout=timeout_ms,
            retry_options=types.HttpRetryOptions(attempts=1),
        )
    except Exception:
        options = types.HttpOptions(timeout=timeout_ms)
    return genai.Client(api_key=key, http_options=options)


def call_model(client, model, system, prompt):
    from google.genai import types

    response = client.models.generate_content(
        model=model,
        contents=prompt,
        config=types.GenerateContentConfig(system_instruction=system, temperature=0.7),
    )
    return response.text


def write_with_gemini(system, prompt):
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        sys.exit("No GEMINI_API_KEY found. Run the export line in this Terminal window first.")

    client = make_client(key)
    for model in GEMINI_MODELS:
        for attempt in range(1, TRIES_PER_MODEL + 1):
            print(f"Trying {model} (attempt {attempt} of {TRIES_PER_MODEL})...")
            try:
                text = call_model(client, model, system, prompt)
                if text and text.strip():
                    print(f"Success with {model}.\n")
                    return text
                print("  Got an empty answer.")
            except Exception as err:
                print(f"  Failed: {type(err).__name__}: {str(err)[:120]}")
            time.sleep(WAIT_SECONDS)
        print(f"Moving on from {model}.\n")
    sys.exit("All models failed. Wait a few minutes and run  python writer.py  again.")


def write_with_claude(system, prompt):
    if not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit("No ANTHROPIC_API_KEY found.")
    import anthropic  # needs: pip install anthropic

    client = anthropic.Anthropic()
    message = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=1000,
        system=system,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text


def main():
    try:
        with open("data.json", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        sys.exit("data.json not found. Run  python collector.py  first.")

    system = load_system_prompt()
    prompt = build_prompt(data)
    print(f"Writing the post with {WRITER}...\n")
    if WRITER == "gemini":
        post = write_with_gemini(system, prompt)
    else:
        post = write_with_claude(system, prompt)
    post = post.strip()

    with open("post.txt", "w", encoding="utf-8") as f:
        f.write(post)

    print("=" * 50)
    print(post)
    print("=" * 50)
    print(f"\n{len(post)} characters. Saved to post.txt")

    unmatched = check_numbers(post, data)
    if unmatched:
        print("\nNUMBER CHECK: these numbers are NOT in data.json, so check them before posting:")
        print("  " + ", ".join(unmatched))
    else:
        print("\nNUMBER CHECK: every number in the post matches data.json.")


if __name__ == "__main__":
    main()
