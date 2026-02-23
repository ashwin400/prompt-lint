#!/usr/bin/env python3
"""
prompt-lint — LLM Prompt Quality Analyzer

Analyzes prompt quality across multiple dimensions:
- Structure (role, task, format, examples, constraints)
- Clarity (specific vs vague language)
- Completeness (context, success criteria, edge cases)
- Anti-patterns (common prompt mistakes)

Zero dependencies. Python 3.9+ stdlib only.
"""

import utils.transport
import utils.session
import argparse
import json
import re
import sys
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List, Dict, Tuple


@dataclass
class Finding:
    """A single prompt quality finding."""
    severity: str  # CRITICAL, HIGH, MEDIUM, LOW
    category: str  # structure, clarity, completeness, anti-pattern
    message: str
    line: int = 0
    suggestion: str = ""


@dataclass
class PromptScore:
    """Overall prompt quality score."""
    total: int  # 0-100
    structure: int  # Has role, task, format, examples, constraints
    clarity: int  # Specific vs vague
    completeness: int  # Context, success criteria, edge cases
    findings: List[Finding]


class PromptLinter:
    """Analyzes LLM prompts for quality issues."""

    # Vague phrases that reduce prompt quality
    VAGUE_PHRASES = [
        r'\bmake (it )?better\b',
        r'\bimprove (this|that)\b',
        r'\boptimize (this|that)\b',
        r'\bfix (this|that)\b',
        r'\bsome (kind of|sort of)\b',
        r'\bthings?\b(?! like)',  # "things" without examples
        r'\bstuff\b',
        r'\betc\.?\b(?! examples)',  # etc without prior examples
        r'\band so on\b',
        r'\bwhatever\b',
        r'\bkind of\b',
        r'\bsort of\b',
    ]

    # Good structure markers
    STRUCTURE_MARKERS = {
        'role': [r'you are (a |an )?', r'act as (a |an )?', r'persona:', r'role:'],
        'task': [r'your (task|job|goal) is', r'you (must|should|will)', r'objective:', r'task:'],
        'format': [r'output (format|as)', r'respond (in|with|as)', r'format:', r'return (a |an )?'],
        'examples': [r'(for )?example:', r'e\.g\.', r'such as', r'like:', r'sample:'],
        'constraints': [r'(do not|don\'t|never)', r'(must|should) not', r'constraints?:', r'rules?:', r'avoid'],
    }

    # Completeness markers
    COMPLETENESS_MARKERS = {
        'context': [r'context:', r'background:', r'given (that)?', r'assume', r'note that'],
        'success': [r'success (criteria|metrics)', r'you (will )?know (it\'s|you\'re) (done|successful)', r'goals?:', r'objectives?:'],
        'edge_cases': [r'edge case', r'special case', r'if .+ then', r'handle (when|if)', r'exception'],
    }

    def __init__(self, text: str, filepath: str = ""):
        self.text = text
        self.filepath = filepath
        self.lines = text.split('\n')
        self.findings: List[Finding] = []

    def lint(self) -> PromptScore:
        """Run all checks and return score."""
        # Run checks
        self._check_vagueness()
        self._check_structure()
        self._check_completeness()
        self._check_anti_patterns()

        # Calculate scores
        structure_score = self._score_structure()
        clarity_score = self._score_clarity()
        completeness_score = self._score_completeness()

        # Total score (weighted average)
        total = int(
            structure_score * 0.30 +
            clarity_score * 0.40 +
            completeness_score * 0.30
        )

        return PromptScore(
            total=total,
            structure=structure_score,
            clarity=clarity_score,
            completeness=completeness_score,
            findings=sorted(self.findings, key=lambda f: (
                {'CRITICAL': 0, 'HIGH': 1, 'MEDIUM': 2, 'LOW': 3}[f.severity],
                f.line
            ))
        )

    def _check_vagueness(self):
        """Detect vague language."""
        for i, line in enumerate(self.lines, 1):
            for pattern in self.VAGUE_PHRASES:
                if re.search(pattern, line, re.IGNORECASE):
                    self.findings.append(Finding(
                        severity='HIGH',
                        category='clarity',
                        message=f'Vague language detected: "{re.search(pattern, line, re.IGNORECASE).group()}"',
                        line=i,
                        suggestion='Be specific: what exactly should be improved? Define measurable criteria.'
                    ))

    def _check_structure(self):
        """Check for structural elements."""
        text_lower = self.text.lower()

        # Check for role definition
        if not any(re.search(p, text_lower) for p in self.STRUCTURE_MARKERS['role']):
            self.findings.append(Finding(
                severity='MEDIUM',
                category='structure',
                message='No role/persona defined',
                suggestion='Define who the LLM should act as (e.g., "You are a senior software engineer...")'
            ))

        # Check for clear task
        if not any(re.search(p, text_lower) for p in self.STRUCTURE_MARKERS['task']):
            self.findings.append(Finding(
                severity='HIGH',
                category='structure',
                message='No clear task/objective defined',
                suggestion='Explicitly state the task (e.g., "Your task is to...")'
            ))

        # Check for output format
        if not any(re.search(p, text_lower) for p in self.STRUCTURE_MARKERS['format']):
            self.findings.append(Finding(
                severity='MEDIUM',
                category='structure',
                message='No output format specified',
                suggestion='Specify expected output format (markdown, JSON, bullet points, etc.)'
            ))

        # Check for examples
        if len(self.text) > 200 and not any(re.search(p, text_lower) for p in self.STRUCTURE_MARKERS['examples']):
            self.findings.append(Finding(
                severity='LOW',
                category='structure',
                message='No examples provided (few-shot prompting)',
                suggestion='Consider adding 1-3 examples of desired output'
            ))

        # Check for constraints
        if not any(re.search(p, text_lower) for p in self.STRUCTURE_MARKERS['constraints']):
            self.findings.append(Finding(
                severity='LOW',
                category='structure',
                message='No explicit constraints defined',
                suggestion='Define boundaries (what NOT to do, limits, requirements)'
            ))

    def _check_completeness(self):
        """Check for completeness markers."""
        text_lower = self.text.lower()

        # Check for context
        if len(self.text) > 100 and not any(re.search(p, text_lower) for p in self.COMPLETENESS_MARKERS['context']):
            self.findings.append(Finding(
                severity='MEDIUM',
                category='completeness',
                message='Missing context/background information',
                suggestion='Provide context: what problem are we solving? Why does this matter?'
            ))

        # Check for success criteria
        if not any(re.search(p, text_lower) for p in self.COMPLETENESS_MARKERS['success']):
            self.findings.append(Finding(
                severity='HIGH',
                category='completeness',
                message='No success criteria defined',
                suggestion='Define what "done" looks like: how will you know the output is correct?'
            ))

        # Check for edge case handling
        if len(self.text) > 300 and not any(re.search(p, text_lower) for p in self.COMPLETENESS_MARKERS['edge_cases']):
            self.findings.append(Finding(
                severity='LOW',
                category='completeness',
                message='No edge case handling specified',
                suggestion='Consider edge cases: what if input is empty/invalid/unexpected?'
            ))

    def _check_anti_patterns(self):
        """Detect common anti-patterns."""
        # Too short
        if len(self.text) < 50:
            self.findings.append(Finding(
                severity='CRITICAL',
                category='anti-pattern',
                message='Prompt is too short (< 50 chars)',
                suggestion='Expand with context, task definition, and expected output'
            ))

        # Too long without structure
        if len(self.text) > 1000 and '\n\n' not in self.text:
            self.findings.append(Finding(
                severity='MEDIUM',
                category='anti-pattern',
                message='Long prompt without clear structure (no paragraphs)',
                suggestion='Break into sections with headers or blank lines'
            ))

        # All caps (yelling)
        if len(re.findall(r'\b[A-Z]{4,}\b', self.text)) > 3:
            self.findings.append(Finding(
                severity='LOW',
                category='anti-pattern',
                message='Excessive ALL CAPS usage',
                suggestion='Use **bold** or *emphasis* for importance instead'
            ))

        # Question without clear intent
        if self.text.strip().endswith('?') and len(self.text) < 100:
            self.findings.append(Finding(
                severity='MEDIUM',
                category='anti-pattern',
                message='Bare question without context or format specification',
                suggestion='Add context and specify how to answer (format, depth, examples)'
            ))

        # Multiple disconnected questions
        question_count = len(re.findall(r'\?', self.text))
        if question_count > 3 and 'choose one' not in self.text.lower():
            self.findings.append(Finding(
                severity='MEDIUM',
                category='anti-pattern',
                message=f'{question_count} questions in one prompt',
                suggestion='Focus on one question, or explicitly ask to answer all'
            ))

    def _score_structure(self) -> int:
        """Score structural quality (0-100)."""
        text_lower = self.text.lower()
        points = 100

        # Deduct for missing elements
        if not any(re.search(p, text_lower) for p in self.STRUCTURE_MARKERS['role']):
            points -= 15
        if not any(re.search(p, text_lower) for p in self.STRUCTURE_MARKERS['task']):
            points -= 25
        if not any(re.search(p, text_lower) for p in self.STRUCTURE_MARKERS['format']):
            points -= 20
        if len(self.text) > 200 and not any(re.search(p, text_lower) for p in self.STRUCTURE_MARKERS['examples']):
            points -= 15
        if not any(re.search(p, text_lower) for p in self.STRUCTURE_MARKERS['constraints']):
            points -= 10

        return max(0, points)

    def _score_clarity(self) -> int:
        """Score clarity (0-100)."""
        points = 100

        # Deduct for vague phrases
        for pattern in self.VAGUE_PHRASES:
            matches = len(re.findall(pattern, self.text, re.IGNORECASE))
            points -= matches * 10

        # Deduct for anti-patterns
        if len(self.text) < 50:
            points -= 40
        if len(self.text) > 1000 and '\n\n' not in self.text:
            points -= 15

        return max(0, min(100, points))

    def _score_completeness(self) -> int:
        """Score completeness (0-100)."""
        text_lower = self.text.lower()
        points = 100

        # Deduct for missing elements
        if len(self.text) > 100 and not any(re.search(p, text_lower) for p in self.COMPLETENESS_MARKERS['context']):
            points -= 20
        if not any(re.search(p, text_lower) for p in self.COMPLETENESS_MARKERS['success']):
            points -= 30
        if len(self.text) > 300 and not any(re.search(p, text_lower) for p in self.COMPLETENESS_MARKERS['edge_cases']):
            points -= 15

        return max(0, points)


def format_score_color(score: int) -> str:
    """Return ANSI color code for score."""
    if score >= 80:
        return '\033[92m'  # Green
    elif score >= 60:
        return '\033[93m'  # Yellow
    elif score >= 40:
        return '\033[38;5;208m'  # Orange
    else:
        return '\033[91m'  # Red


def format_severity_color(severity: str) -> str:
    """Return ANSI color for severity."""
    colors = {
        'CRITICAL': '\033[91m',  # Red
        'HIGH': '\033[38;5;208m',  # Orange
        'MEDIUM': '\033[93m',  # Yellow
        'LOW': '\033[94m',  # Blue
    }
    return colors.get(severity, '')


def print_report(score: PromptScore, filepath: str = "", verbose: bool = False, color: bool = True):
    """Print human-readable report."""
    reset = '\033[0m' if color else ''
    bold = '\033[1m' if color else ''

    # Header
    print(f"\n{bold}Prompt Quality Report{reset}")
    if filepath:
        print(f"File: {filepath}")
    print()

    # Overall score
    score_color = format_score_color(score.total) if color else ''
    grade = 'A' if score.total >= 80 else 'B' if score.total >= 60 else 'C' if score.total >= 40 else 'D' if score.total >= 20 else 'F'
    print(f"{bold}Overall Score:{reset} {score_color}{score.total}/100{reset} ({grade})")
    print()

    # Dimension scores
    print(f"{bold}Dimension Breakdown:{reset}")
    print(f"  Structure:    {format_score_color(score.structure) if color else ''}{score.structure}/100{reset}")
    print(f"  Clarity:      {format_score_color(score.clarity) if color else ''}{score.clarity}/100{reset}")
    print(f"  Completeness: {format_score_color(score.completeness) if color else ''}{score.completeness}/100{reset}")
    print()

    # Findings summary
    severity_counts = {'CRITICAL': 0, 'HIGH': 0, 'MEDIUM': 0, 'LOW': 0}
    for f in score.findings:
        severity_counts[f.severity] += 1

    print(f"{bold}Findings Summary:{reset}")
    for sev in ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW']:
        count = severity_counts[sev]
        if count > 0:
            color_code = format_severity_color(sev) if color else ''
            print(f"  {color_code}{sev}:{reset} {count}")
    print()

    # Detailed findings
    if score.findings:
        print(f"{bold}Issues Found:{reset}")
        for f in score.findings:
            sev_color = format_severity_color(f.severity) if color else ''
            location = f" (line {f.line})" if f.line > 0 else ""
            print(f"\n  {sev_color}[{f.severity}]{reset} {f.category.upper()}{location}")
            print(f"  {f.message}")
            if verbose and f.suggestion:
                print(f"  💡 {f.suggestion}")
    else:
        print(f"{bold}✅ No issues found!{reset}")

    print()


def main():
    parser = argparse.ArgumentParser(
        description='Analyze LLM prompt quality',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  python3 prompt_lint.py prompt.txt
  python3 prompt_lint.py --verbose prompt.md
  python3 prompt_lint.py --json prompts/*.txt
  python3 prompt_lint.py --threshold 70 system-prompt.txt
        '''
    )
    parser.add_argument('files', nargs='+', help='Prompt file(s) to analyze')
    parser.add_argument('--verbose', '-v', action='store_true', help='Show suggestions for each finding')
    parser.add_argument('--json', action='store_true', help='Output JSON instead of human-readable')
    parser.add_argument('--no-color', action='store_true', help='Disable color output')
    parser.add_argument('--threshold', type=int, metavar='N', help='Exit 1 if score below threshold')

    args = parser.parse_args()

    results = []
    exit_code = 0

    for filepath in args.files:
        path = Path(filepath)
        if not path.exists():
            print(f"Error: {filepath} not found", file=sys.stderr)
            exit_code = 1
            continue

        text = path.read_text()
        linter = PromptLinter(text, str(path))
        score = linter.lint()

        if args.json:
            results.append({
                'file': str(path),
                'score': asdict(score)
            })
        else:
            print_report(score, str(path), args.verbose, not args.no_color)

        # Check threshold
        if args.threshold and score.total < args.threshold:
            exit_code = 1

    # Output JSON if requested
    if args.json:
        print(json.dumps(results, indent=2))

    sys.exit(exit_code)


if __name__ == '__main__':
    main()
