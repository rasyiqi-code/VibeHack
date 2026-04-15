"""
vibehack/core/editor.py — Surgical File Manipulation Utility.

Provides precise tools for reading, writing, and editing files without 
relying on error-prone shell commands like 'sed'.
"""
import os
import sys
import json
import shlex
from pathlib import Path

def read_file(path: str, start: int = 1, end: int = None) -> str:
    """Read a file with line numbers for surgical editing."""
    p = Path(path)
    if not p.exists():
        return f"Error: File '{path}' not found."
    
    try:
        content = p.read_text(errors="replace")
        lines = content.splitlines()
        total = len(lines)
        end = end or total
        
        # Adjust 1-based indexing to 0-based
        start_idx = max(0, start - 1)
        end_idx = min(total, end)
        
        subset = lines[start_idx:end_idx]
        output = []
        for i, line in enumerate(subset, start=start_idx + 1):
            output.append(f"{i:4} | {line}")
            
        header = f"--- File: {path} (Lines {start}-{end} of {total}) ---\n"
        return header + "\n".join(output)
    except Exception as e:
        return f"Error reading file: {e}"

def write_file(path: str, content: str) -> str:
    """Overwrite a file with new content."""
    try:
        Path(path).write_text(content)
        return f"Successfully wrote to '{path}'."
    except Exception as e:
        return f"Error writing to file: {e}"

def replace_text(path: str, old: str, new: str, allow_multiple: bool = False) -> str:
    """Surgical text replacement."""
    p = Path(path)
    if not p.exists():
        return f"Error: File '{path}' not found."
    
    try:
        content = p.read_text(errors="replace")
        count = content.count(old)
        
        if count == 0:
            return f"Error: Could not find exact match for replacement in '{path}'."
        if count > 1 and not allow_multiple:
            return f"Error: Found {count} occurrences of old text in '{path}'. Use 'allow_multiple=true' to replace all."
            
        new_content = content.replace(old, new)
        p.write_text(new_content)
        return f"Successfully replaced {count} occurrence(s) in '{path}'."
    except Exception as e:
        return f"Error during replacement: {e}"

def find_in_dir(dir_path: str, pattern: str = "*", recursive: bool = True) -> str:
    """Efficiently list directory structure with filtering."""
    p = Path(dir_path)
    if not p.is_dir():
        return f"Error: '{dir_path}' is not a directory."
    
    try:
        walker = p.rglob(pattern) if recursive else p.glob(pattern)
        results = []
        for path in walker:
            try:
                rel = path.relative_to(p)
                type_str = "[DIR] " if path.is_dir() else "[FILE]"
                results.append(f"{type_str} {rel}")
            except Exception:
                continue
            
        if not results:
            return f"No matches found for '{pattern}' in '{dir_path}'."
            
        # Limit to 100 results to save tokens
        if len(results) > 100:
            results = sorted(results)[:100] + [f"... and {len(results)-100} more matches."]
        else:
            results = sorted(results)
            
        return f"--- Directory Structure: {dir_path} ---\n" + "\n".join(results)
    except Exception as e:
        return f"Error listing directory: {e}"

def handle_internal_command(command: str) -> str:
    """Routes an internal command to the editor logic."""
    try:
        tokens = shlex.split(command)
    except ValueError:
        return "Error: Malformed internal command tokens."
        
    if not tokens:
        return "Error: Empty command."
        
    base = tokens[0]
    args = tokens[1:]
    
    if base == "vibehack-read":
        if not args: return "Usage: vibehack-read <file> [start] [end]"
        start = int(args[1]) if len(args) > 1 else 1
        end = int(args[2]) if len(args) > 2 else None
        return read_file(args[0], start, end)
        
    if base == "vibehack-write":
        if len(args) < 2: return "Usage: vibehack-write <file> <content>"
        return write_file(args[0], args[1])
        
    if base == "vibehack-edit":
        if len(args) < 3: return "Usage: vibehack-edit <file> <old_text> <new_text> [allow_multiple:true|false]"
        allow_multiple = args[3].lower() == "true" if len(args) > 3 else False
        return replace_text(args[0], args[1], args[2], allow_multiple)
        
    if base == "vibehack-find":
        if not args: return "Usage: vibehack-find <dir> [pattern] [recursive:true|false]"
        pattern = args[1] if len(args) > 1 else "*"
        recursive = args[2].lower() != "false" if len(args) > 2 else True
        return find_in_dir(args[0], pattern, recursive)
        
    return f"Error: Unknown internal command '{base}'"

def main():
    if len(sys.argv) < 2:
        print("Usage: vibehack-edit <command> [args...]")
        sys.exit(1)
        
    # Standard CLI wrapper
    cmd = sys.argv[1]
    args = sys.argv[2:]
    
    if cmd == "read":
        start = int(args[1]) if len(args) > 1 else 1
        end = int(args[2]) if len(args) > 2 else None
        print(read_file(args[0], start, end))
    elif cmd == "write":
        print(write_file(args[0], args[1]))
    elif cmd == "replace":
        allow_multiple = args[3].lower() == "true" if len(args) > 3 else False
        print(replace_text(args[0], args[1], args[2], allow_multiple))
    elif cmd == "find":
        pattern = args[1] if len(args) > 1 else "*"
        recursive = args[2].lower() != "false" if len(args) > 2 else True
        print(find_in_dir(args[0], pattern, recursive))
    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)

if __name__ == "__main__":
    main()
