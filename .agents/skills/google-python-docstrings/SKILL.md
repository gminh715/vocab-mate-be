---
name: google-python-docstrings
description: Write, fix, and standardize Python docstrings in Google style. Use whenever the user asks to add or improve docstrings, convert mixed docstrings to Google format, add missing Args/Returns/Raises/Attributes/Example sections, or make docstrings concise and API-focused.
metadata:
  skill-author: Martanto
---

# Google Python Docstrings Writer

Write concise, practical Python docstrings that follow the Google Python Style Guide.

## Overview

- Focus on API usability: describe what callers need to know, not internal implementation details.
- Prefer short, structured sections (`Args:`, `Returns:`/`Yields:`, `Raises:`, `Example:`).
- Include runnable `Example:` blocks for public APIs so usage is immediately clear.
- Keep language concise and consistent; avoid over-engineered or overly verbose docstrings.

This skill is intentionally trigger-friendly: if a request mentions Python docstrings,
documentation cleanup, or Google-style sections, use this skill by default.

## When to Use This Skill

Invoke this skill when the user asks to write docstrings in Google docstring style.

Use this skill when you are:

- Writing or updating docstrings for Python modules, classes, functions, or methods.
- Standardizing mixed docstring styles into Google-style format.
- Adding missing `Args:`, `Returns:`/`Yields:`, `Raises:`, `Attributes:`, or `Example:` sections.
- Improving unclear, verbose, or inconsistent API documentation.
- Reviewing existing docstrings for compliance and consistency before merging code.

Do not use this skill when you are:

- Writing non-Python documentation (README guides, API specs, or design docs).
- Changing runtime behavior, business logic, or code structure unrelated to docstrings.
- Generating long tutorials better suited for external documentation.

## Output Expectations

- Produce docstrings that are directly usable in source code with minimal cleanup.
- Preserve runtime behavior: edit documentation only unless the user explicitly asks for code changes.
- Prefer minimal, focused rewrites over full-document rewrites.
- If information is missing, write the safest concise docstring that matches visible API behavior.

## Progressive Disclosure

- Start with this file for workflow and triggering guidance.
- Use `references/rules.md` for detailed format rules, compliant/non-compliant examples, and final validation.
- Consult only the relevant rules section for the object type you are documenting (module, function/method, class).

## Quick start

1. **Format basics**: Use triple quotes (`"""`), start with a one-line summary (≤80 chars), and add a blank line before details in multi-line docstrings.
2. **Section structure**: Use unindented section headers ending with `:` (e.g., `Args:`, `Returns:`, `Raises:`, `Example:`), followed by indented (2 or 4 spaces) content.
3. **Field style**: In `Args:` / `Returns:` / `Raises:`, use concise `name (type): Description` entries.
4. **Always include `Example:`** for every public function or method to show practical usage.
5. **Generators**: Use `Yields:` instead of `Returns:`.
6. **Classes**: Document public attributes in an `Attributes:` section (same formatting as `Args:`).
7. **Inline identifier formatting**: Use double-backtick inline code style for values, arguments/parameters, and symbol names (functions, methods, classes, properties), for example ``load_data()``, ``random_state``, or ``"value"``.

## Workflow

1. **Determine docstring scope**
   - **Functions**: Include `Args`, `Returns` (or `Yields`), `Raises`, and `Example:` as needed.
   - **Classes**: Include class docstring, `Attributes:` section for public attributes, and `Example:` showing instantiation.
   - **Modules**: Start with a summary, usage example in docstring, and typical import/call pattern.
   - **Methods**: Omit if decorated with `@override` (unless behavior materially changes). Include `Example:` for public methods.
   - **Public API rule**: Treat names without a leading underscore as public. Private helpers (e.g., `_helper`) do not require `Example:`.

2. **Write the summary line**
   - Descriptive or imperative style (consistent within file).
   - For `@property` descriptors, use descriptive style: `"""The Bigtable path."""` not `"""Returns the Bigtable path."""`.

3. **Structure additional sections**
   - Add blank line after summary if docstring has multiple lines.
   - List sections in order: `Args:`, `Returns:` (or `Yields:`), `Raises:`, `Example:`.
   - Each section name ends with `:`, followed by indented content.
   - Use consistent indentation (2 or 4 spaces per file).
   - Include `Example:` for every public function/method to show practical, runnable usage.

4. **Validate before finalizing**
   - Run through the checklist in `references/rules.md`.
   - Fix inconsistencies in section headers, summary style, and indentation.
   - Ensure examples are realistic and not boilerplate-heavy.

## Common mistakes

- Writing long narrative paragraphs that restate obvious code behavior.
 - Omitting type information in `Args:`/`Returns:` entries.
- Using vague sections like `Raises: Various exceptions may occur.`
- Skipping `Example:` for public APIs.
- Providing huge setup-heavy examples instead of short, focused usage.

## Best practices

- Keep each parameter description to one concise sentence.
- Make `Example:` realistic and quick to read (typically 5-10 lines).
- Prefer doctest-style examples (`>>>`) when practical.
- Show expected output when it helps clarify behavior.
- Keep style consistent within a file (summary tone, indentation, section order).

## Reference Files

Detailed information available in `references/`:

- `rules.md`: full style description and examples.

## Additional Resources

- Google Python Style Guide: https://google.github.io/styleguide/pyguide.html#s3.8-comments-and-docstrings
