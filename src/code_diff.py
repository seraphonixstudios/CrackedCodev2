"""Code Diff / Patch Generation v2.9.0 - Generate and apply git-style diffs.

Instead of outputting entire files, the AI can generate unified diffs
for precise modifications to existing code.

Usage:
    from src.code_diff import generate_patch, apply_patch, parse_diff
    
    patch = generate_patch(original_text, modified_text, filename="utils.py")
    new_text = apply_patch(original_text, patch)
"""

import re
from dataclasses import dataclass
from typing import List, Optional, Tuple

from src.logger_config import get_logger

logger = get_logger("CodeDiff")


# ── Data Models ────────────────────────────────────────────────────────────

@dataclass
class Hunk:
    """A single hunk in a unified diff."""
    old_start: int
    old_count: int
    new_start: int
    new_count: int
    lines: List[str]  # Each line prefixed with ' ', '+', '-'
    header: str = ""


@dataclass
class Diff:
    """A parsed unified diff."""
    old_file: str
    new_file: str
    hunks: List[Hunk]


# ── Patch Generation ───────────────────────────────────────────────────────

def generate_patch(old_text: str, new_text: str, old_file: str = "a/file.py",
                   new_file: str = "b/file.py", context: int = 3) -> str:
    """Generate a unified diff between old_text and new_text.
    
    Args:
        old_text: Original file content
        new_text: Modified file content
        old_file: Old filename label
        new_file: New filename label
        context: Number of context lines around changes
    
    Returns:
        Unified diff as a string
    """
    old_lines = old_text.splitlines()
    new_lines = new_text.splitlines()
    
    # Simple LCS-based diff (simplified for production use)
    diff = _compute_diff(old_lines, new_lines)
    
    # Build unified diff output
    output = []
    output.append(f"--- {old_file}")
    output.append(f"+++ {new_file}")
    
    for hunk in _group_into_hunks(diff, context):
        output.append(_format_hunk_header(hunk))
        for line in hunk.lines:
            output.append(line)
    
    return "\n".join(output) + "\n"


def _compute_diff(old_lines: List[str], new_lines: List[str]) -> List[Tuple[str, str]]:
    """Compute line-by-line diff using Myers' algorithm (simplified).
    
    Returns list of (action, line) where action is ' ' (same), '+' (added), '-' (removed).
    """
    # Use difflib for robustness
    import difflib
    
    result = []
    sm = difflib.SequenceMatcher(None, old_lines, new_lines)
    
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == 'equal':
            for line in old_lines[i1:i2]:
                result.append((' ', line))
        elif tag == 'delete':
            for line in old_lines[i1:i2]:
                result.append(('-', line))
        elif tag == 'insert':
            for line in new_lines[j1:j2]:
                result.append(('+', line))
        elif tag == 'replace':
            for line in old_lines[i1:i2]:
                result.append(('-', line))
            for line in new_lines[j1:j2]:
                result.append(('+', line))
    
    return result


def _group_into_hunks(diff: List[Tuple[str, str]], context: int) -> List[Hunk]:
    """Group diff lines into hunks with context."""
    if not diff:
        return []
    
    # Find change regions
    changes = [i for i, (action, _) in enumerate(diff) if action != ' ']
    if not changes:
        return []
    
    # Group nearby changes into hunks
    hunks = []
    current_hunk_lines = []
    current_changes = []
    
    for change_idx in changes:
        if not current_changes or change_idx - current_changes[-1] <= context * 2 + 1:
            current_changes.append(change_idx)
        else:
            # Finalize current hunk
            hunk = _create_hunk(diff, current_changes, context)
            if hunk:
                hunks.append(hunk)
            current_changes = [change_idx]
    
    # Finalize last hunk
    if current_changes:
        hunk = _create_hunk(diff, current_changes, context)
        if hunk:
            hunks.append(hunk)
    
    return hunks


def _create_hunk(diff: List[Tuple[str, str]], change_indices: List[int], context: int) -> Optional[Hunk]:
    """Create a hunk from a group of changes."""
    start = max(0, change_indices[0] - context)
    end = min(len(diff), change_indices[-1] + context + 1)
    
    lines = diff[start:end]
    
    # Calculate old/new line numbers
    old_start = 1
    new_start = 1
    for i in range(start):
        action, _ = diff[i]
        if action in (' ', '-'):
            old_start += 1
        if action in (' ', '+'):
            new_start += 1
    
    old_count = sum(1 for action, _ in lines if action in (' ', '-'))
    new_count = sum(1 for action, _ in lines if action in (' ', '+'))
    
    formatted_lines = [f"{action}{line}" for action, line in lines]
    
    return Hunk(
        old_start=old_start,
        old_count=old_count,
        new_start=new_start,
        new_count=new_count,
        lines=formatted_lines,
    )


def _format_hunk_header(hunk: Hunk) -> str:
    """Format the hunk header line."""
    old_range = hunk.old_start if hunk.old_count == 1 else f"{hunk.old_start},{hunk.old_count}"
    new_range = hunk.new_start if hunk.new_count == 1 else f"{hunk.new_start},{hunk.new_count}"
    return f"@@ -{old_range} +{new_range} @@"


# ── Patch Application ──────────────────────────────────────────────────────

def apply_patch(original_text: str, patch_text: str) -> str:
    """Apply a unified diff patch to original text.
    
    Args:
        original_text: Original file content
        patch_text: Unified diff patch
    
    Returns:
        Patched text
    """
    diff = parse_diff(patch_text)
    if not diff or not diff.hunks:
        return original_text
    
    lines = original_text.splitlines()
    
    # Apply hunks from bottom to top to preserve line numbers
    for hunk in reversed(diff.hunks):
        lines = _apply_hunk(lines, hunk)
    
    return "\n".join(lines) + ("\n" if original_text.endswith("\n") else "")


def _apply_hunk(lines: List[str], hunk: Hunk) -> List[str]:
    """Apply a single hunk to a list of lines."""
    old_idx = hunk.old_start - 1
    new_lines = lines[:old_idx]
    
    for line in hunk.lines:
        prefix = line[0]
        content = line[1:]
        
        if prefix == ' ':
            # Context line - must match
            if old_idx < len(lines) and lines[old_idx] == content:
                new_lines.append(content)
                old_idx += 1
            else:
                raise ValueError(f"Context mismatch at line {old_idx + 1}: expected '{content}'")
        elif prefix == '-':
            # Removed line - must match
            if old_idx < len(lines) and lines[old_idx] == content:
                old_idx += 1  # Skip it
            else:
                raise ValueError(f"Removal mismatch at line {old_idx + 1}: expected '{content}'")
        elif prefix == '+':
            # Added line
            new_lines.append(content)
    
    # Append remaining lines after hunk
    new_lines.extend(lines[old_idx:])
    
    return new_lines


# ── Diff Parsing ───────────────────────────────────────────────────────────

def parse_diff(patch_text: str) -> Optional[Diff]:
    """Parse a unified diff into a Diff object."""
    lines = patch_text.splitlines()
    
    if len(lines) < 2:
        return None
    
    old_file = ""
    new_file = ""
    hunks = []
    
    i = 0
    while i < len(lines):
        line = lines[i]
        
        if line.startswith("--- "):
            old_file = line[4:]
        elif line.startswith("+++ "):
            new_file = line[4:]
        elif line.startswith("@@ "):
            # Parse hunk header
            hunk, i = _parse_hunk(lines, i)
            if hunk:
                hunks.append(hunk)
        
        i += 1
    
    return Diff(old_file=old_file, new_file=new_file, hunks=hunks)


def _parse_hunk(lines: List[str], start_idx: int) -> Tuple[Optional[Hunk], int]:
    """Parse a single hunk starting at start_idx."""
    header = lines[start_idx]
    
    # Parse @@ -old_start,old_count +new_start,new_count @@
    match = re.match(r'@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@', header)
    if not match:
        return None, start_idx
    
    old_start = int(match.group(1))
    old_count = int(match.group(2)) if match.group(2) else 1
    new_start = int(match.group(3))
    new_count = int(match.group(4)) if match.group(4) else 1
    
    hunk_lines = []
    i = start_idx + 1
    
    while i < len(lines):
        line = lines[i]
        if line.startswith("@@ ") or line.startswith("--- ") or line.startswith("+++ "):
            break
        if line.startswith((' ', '+', '-')):
            hunk_lines.append(line)
        i += 1
    
    return Hunk(
        old_start=old_start,
        old_count=old_count,
        new_start=new_start,
        new_count=new_count,
        lines=hunk_lines,
        header=header,
    ), i - 1


# ── High-Level Helpers ─────────────────────────────────────────────────────

def generate_patch_from_files(old_path: str, new_path: str) -> str:
    """Generate a patch from two file paths."""
    with open(old_path, "r", encoding="utf-8") as f:
        old_text = f.read()
    with open(new_path, "r", encoding="utf-8") as f:
        new_text = f.read()
    
    return generate_patch(
        old_text, new_text,
        old_file=f"a/{Path(old_path).name}",
        new_file=f"b/{Path(new_path).name}",
    )


def apply_patch_to_file(file_path: str, patch_text: str) -> bool:
    """Apply a patch directly to a file."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            original = f.read()
        
        patched = apply_patch(original, patch_text)
        
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(patched)
        
        return True
    except Exception as e:
        logger.error(f"Failed to apply patch to {file_path}: {e}")
        return False


# Import Path for type hints
from pathlib import Path
