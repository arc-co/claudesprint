# Hello World CLI

## Overview

A simple command-line tool that greets users by name.

## Constraints

- Python 3.10+
- No external dependencies beyond standard library
- Must be runnable with `python hello.py`

## Deliverables

A working Python script that:
- Accepts an optional name argument
- Prints a personalized greeting
- Has basic error handling

## Work Plan

### Issue 1: Create Hello World Script

Create `hello.py` that greets users.

**Acceptance Criteria:**
- Running `python hello.py` prints "Hello, World!"
- Running `python hello.py Alice` prints "Hello, Alice!"
- The script handles missing arguments gracefully

### Issue 2: Add Unit Tests

Create tests for the hello script.

**Acceptance Criteria:**
- Test default greeting
- Test custom name greeting
- Tests pass with `python -m pytest` or similar
