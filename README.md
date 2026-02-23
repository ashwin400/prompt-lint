# prompt-lint

Static analyzer for LLM prompts. Scores your prompts 0-100 and tells you exactly what to fix.

Zero dependencies. Works offline. No API key needed.

```bash
python3 prompt_lint.py prompt.txt
```

---

## Why

Vague prompts produce vague outputs. Most people write "make this better" when they should write "rewrite this in a professional tone, keeping it under 100 words, with a clear call to action at the end." This tool catches the difference.

## Install

```bash
curl -O https://raw.githubusercontent.com/ashwin400/prompt-lint/main/prompt_lint.py
python3 prompt_lint.py your-prompt.txt
```

## Usage

```bash
# Analyze a prompt file
python3 prompt_lint.py prompt.txt

# Analyze a string directly
python3 prompt_lint.py --text "Make this email better"

# JSON output
python3 prompt_lint.py prompt.txt --json

# Strict mode (exit 1 if score < 70)
python3 prompt_lint.py prompt.txt --min-score 70
```

## What It Scores

**Structure (30 points)**
- Role defined ("You are a...")
- Clear task/objective
- Output format specified
- Examples provided (few-shot)
- Constraints defined

**Clarity (40 points)**
- Specific vs vague language ("improve this" scores lower than "rewrite in 3 bullet points")
- Measurable success criteria
- No ambiguous pronouns or instructions

**Completeness (30 points)**
- Context provided
- Edge cases addressed
- Tone/audience specified

## Example Output

```
prompt-lint: prompt.txt

Score: 34/100  POOR

FINDINGS

● CRITICAL  No role or persona defined
  Add "You are a [role]" at the start of your prompt.
  Example: "You are a senior software engineer reviewing a pull request."

● HIGH  Vague instruction detected: "make it better"
  Replace with specific, measurable language.
  Example: "Rewrite in active voice, under 150 words, with a hook in the first sentence."

● HIGH  No output format specified
  Tell the model exactly how to format the response.
  Example: "Respond as a JSON object with keys: title, summary, action_items"

◐ MEDIUM  No examples provided
  Add 1-2 examples of desired input/output (few-shot prompting).

○ LOW  No constraints defined
  Consider adding: length limits, prohibited content, tone requirements.

SUGGESTIONS
  Structure: +18 pts  (add role + output format)
  Clarity:   +31 pts  (replace vague phrases with specific instructions)
  Potential: 83/100
```

## CI Integration

```yaml
- name: Lint prompts
  run: |
    for f in prompts/*.txt; do
      python3 prompt_lint.py "$f" --min-score 60
    done
```

## Requirements

Python 3.9+. No dependencies. Analyzes prompts of any length.
