# Google Docstring Rules & Examples

## Execution Contract

Use this document as generation policy for docstring-writing behavior.

- Treat all rules as normative (`must`/`should`) when writing or revising docstrings.
- Optimize for API clarity and caller usability, not implementation commentary.
- Prefer minimal edits that improve compliance without changing runtime behavior.
- If rules conflict with existing project conventions, follow project conventions and keep style consistent.

### How to apply this document

- Start with the object-type section you need (module, function/method, class).
- Use examples as patterns, not templates to copy blindly.
- Apply only relevant rules; avoid unnecessary rewrites.

### Validation loop

1. Draft or revise docstring.
2. Compare against the relevant compliant/non-compliant examples.
3. Run the Validation Checklist.
4. Tighten wording and remove redundancy.

## Table of Contents

### Foundations

- [Basic Structure](#basic-structure)
- [Args, Returns, Raises](#args-returns-raises)
- [Length Guardrails](#length-guardrails)

### By Object Type

- [Module Docstrings](#module-docstrings)
- [Function/Method Docstrings](#functionmethod-docstrings)
- [Class Docstrings](#class-docstrings)

### Practical Guidance

- [Examples](#examples)
- [Edge Cases & Common Patterns](#edge-cases--common-patterns)

### Process

- [How to apply this document](#how-to-apply-this-document)
- [Validation loop](#validation-loop)

### Review Aids

- [Compliance Summary](#compliance-summary)
- [Validation Checklist](#validation-checklist)

## Basic Structure

```
"""One-line summary ending with a period.

Optional detailed description spanning multiple lines.
Keep it concise; avoid over-explanation.

Sections below for complex docstrings.
"""
```

- **Summary line**: One sentence, <=80 characters, ending with `.`, `?`, or `!`
- **Blank line**: Separate summary from detailed content (multi-line only)
- **Sections**: Unindented headers with `:`, indented content (2-4 spaces, consistent per file)
- **Canonical section order (functions/methods)**: `Args:`, `Returns:` (or `Yields:`), `Raises:`, `Example:`
- **Class section order**: Summary/description, `Attributes:`, then method-level sections in each method docstring
- **Args entry format**: Use `name (type): Description.` and include `optional` when applicable
- **Returns entry format**: Use `type: Description.`
- **Attributes entry format**: Use `name (type): Description.`

### Section consistency policy

- Use `Example:` (singular) consistently in this guide.
- Use one indentation style per file (2 or 4 spaces).
- Keep summary style consistent per file (imperative or descriptive).

### Inline identifier formatting

- Write function/method or class names using double-backtick inline code style, for example: ``load_data()``.
- Write variable values using double-backtick inline code style, for example: ``"value"``.
- Write variable, argument, or parameter names using double-backtick inline code style, for example: ``argument``.

Example paragraph:

  Creates a single ``ModelTrainer`` for all classifiers so that resampling
  and feature selection are performed once per seed and reused across classifiers,
  eliminating redundant computation. Runs ``fit()`` on the shared trainer, then
  builds and persists per-classifier training results in ``self.trained_models``
  as a mapping of classifier name to trained-model registry CSV path, and
  returns the same mapping.

### When to omit sections

- Omit `Returns:` when the function returns `None`.
- Omit `Raises:` for API misuse/precondition violations (do not make misuse behavior part of the API contract).
- Omit overridden method docstrings when `@override` is present and behavior is unchanged.
- Omit detailed sections when a one-line docstring is sufficient for trivial, obvious behavior.

---

## Module Docstrings

### Compliant example

This example shows a concise module summary with a focused usage snippet.

```python
"""Utilities for data processing and transformation.

This module provides high-level functions for loading, cleaning, and
normalizing datasets. Typical usage:

  data = load_csv('input.csv')
  cleaned = data.drop_nulls().normalize()
"""
```

### Non-compliant example

This example shows vague, redundant wording that does not add actionable context.

```python
"""
This is a module for data processing.
It has functions that do things like loading and cleaning.
You can use it by importing it and calling the functions.
"""
```

**Rules**
- Start with a one-line summary.
- Add usage examples if module is part of public API.
- Keep descriptions concise; assume readers know Python.

---

## Function/Method Docstrings

### Compliant example — Simple function

This example shows a clean baseline format with Args, Returns, and Raises.

```python
def fetch_rows(table_handle, keys, require_all_keys=False):
    """Fetches rows from a table.

    Args:
      table_handle (Table): An open Table instance.
      keys (Sequence[str]): A sequence of strings representing row keys.
      require_all_keys (bool, optional): If True, only return rows with all keys set.

    Returns:
      dict[str, tuple[str, ...]]: A mapping of keys to row data.

    Raises:
      IOError: If table access fails.
    """
```

### Compliant example — With type annotations

This example shows that `Args:` and `Returns:` still include concise types.

```python
def fetch_rows(
    table_handle: Table,
    keys: Sequence[str],
    require_all_keys: bool = False,
) -> Mapping[str, tuple[str, ...]]:
    """Fetches rows from a table.

    Retrieves rows by key, optionally requiring all keys to be present.

    Args:
      table_handle (Table): An open Table instance.
      keys (Sequence[str]): Row keys to fetch.
      require_all_keys (bool, optional): If True, omit rows with missing keys.

    Returns:
      Mapping[str, tuple[str, ...]]: A mapping of keys to row data.

    Raises:
      IOError: If table access fails.
    """
```

### Compliant example — Generator

This example shows correct use of `Yields:` for generator functions.

```python
def generate_items(data):
    """Yields processed items from data.

    Args:
      data (Iterable[Any]): An iterable of raw items.

    Yields:
      dict[str, Any]: Processed item dicts with 'id' and 'value' keys.
    """
```

### Non-compliant example — Over-detailed

This example shows excessive narrative detail that should be trimmed for clarity.

```python
def fetch_rows(table_handle, keys, require_all_keys=False):
    """
    This function fetches rows from a table. You pass it a table handle
    and a list of keys. It will then query the table and return the rows
    that match those keys. If require_all_keys is True, it will only
    return rows where all the keys you asked for are present. The return
    value is a dictionary that maps the keys to tuples of strings, where
    each tuple represents a row. If something goes wrong, it raises an
    IOError exception.

    Caveat: This only works if the table is already open.
    Note: Performance may degrade with large key sets.
    Limitation: Only supports string keys.
    Details: Internally uses a hash map for O(1) lookups.
    """
```

**Rules**
- Include argument type in `Args:` entries using `name (type):` format.
- Include return type in `Returns:` entries using `type:` format.
- One sentence per parameter; describe *what* it is, not obvious details.
- List only *documented* exceptions (not every possible error).

---

## Class Docstrings

### Compliant example

```python
class DataCache:
    """In-memory cache for dataset access.

    Attributes:
      max_size (int): Maximum number of items to store.
      ttl (int): Time-to-live in seconds for cached items.
    """

    def __init__(self, max_size=1000, ttl=3600):
        """Initializes the cache.

        Args:
          max_size (int, optional): Maximum items. Defaults to 1000.
          ttl (int, optional): Expiry time in seconds. Defaults to 3600.
        """
        self.max_size = max_size
        self.ttl = ttl
```

### Non-compliant example — Redundant or unclear

```python
class DataCache:
    """
    This is a class that represents a cache. The cache stores data
    and retrieves it. It is a good idea to use this class when you
    need a cache. The cache has attributes and methods.
    """
```

**Rules**
- Start with "The [noun]..." or action style: describe *what it represents*.
- Do not write "Class that..." or "This class provides..."
- Document public attributes in `Attributes:` section using `name (type):` format.
- Method docstrings follow function rules (omit if `@override`, unless behavior changes).

---

## Args, Returns, Raises

`Args:` describes each input the caller provides and any important constraints.
Keep each entry to one sentence focused on what the value represents in API use.
Use `name (type):` format, for example `random_state (int, optional):`.

`Returns:` explains what the function gives back, including structure when needed.
Describe the returned value from the caller's perspective, not internal computation.
Use `type:` format, for example `str: Path to generated output.`

`Raises:` documents exceptions callers should expect during normal, valid use.
List specific, meaningful exception types and the condition that triggers each one.

Canonical mini-template:

```python
"""
Args:
  random_state (int, optional): Initial random state seed. Defaults to 0.
  total_seed (int, optional): Total number of seeds to run. Defaults to 500.
  sampling_strategy (str | float, optional): Under-sampling ratio for
    balancing classes. Defaults to 0.75.

Returns:
  str: Path to the significant features CSV if feature selection
    produced at least one feature.

Raises:
  ValueError: If sampling_strategy is outside the accepted range.
"""
```

### Compliant example — Concise

```python
"""
Args:
  learning_rate (float): Initial learning rate. Must be > 0.
  momentum (float, optional): Momentum factor. Defaults to 0.9.

Returns:
  Model: A trained model instance.

Raises:
  ValueError: If learning_rate <= 0.
  FileNotFoundError: If checkpoint path does not exist.
"""
```

### Non-compliant example — Vague or verbose

```python
"""
Args:
  learning_rate: The learning rate parameter that controls how much
                 the model weights are updated on each iteration. It
                 should be a positive number. If it's too high, the
                 model may diverge. If it's too low, training will
                 be slow. Experience shows 0.001 to 0.1 is good.
  momentum: This is another parameter related to momentum.

Returns:
  This function returns a model. The model is trained. You can use it
  to make predictions.

Raises:
  Various exceptions may be raised depending on input.
"""
```

---

## Examples

### Compliant example — Interactive session (doctest style)

```python
def train_model(features_csv, labels_csv, classifiers=None):
    """Trains a model on given data.

    Args:
      features_csv (str): Path to CSV with feature data.
      labels_csv (str): Path to CSV with label data.
      classifiers (list[str] | None, optional):
        List of classifier names (e.g., ['rf', 'xgb']).

    Returns:
      Model: A trained model instance.

    Example:
      >>> trainer = ModelTrainer(
      ...     features_csv="data/features.csv",
      ...     labels_csv="data/labels.csv",
      ...     classifiers=["rf", "xgb"],
      ... )
      >>> trainer.train(random_state=0, total_seed=5)
      Training RF... Done (0.92 accuracy)
      Training XGB... Done (0.95 accuracy)
    """
```

### Compliant example — Simple usage

```python
def load_data(path):
    """Loads dataset from file.

    Args:
      path (str): Path to data file.

    Returns:
      DataFrame: A DataFrame with loaded data.

    Example:
      >>> data = load_data('data.csv')
      >>> print(data.shape)
      (1000, 5)
    """
```

### Compliant example — Realistic code block

```python
def filter_records(records, min_age=18):
    """Filters records by age.

    Args:
      records (list[dict[str, int]]): List of record dicts with 'age' key.
      min_age (int, optional): Minimum age threshold.

    Returns:
      list[dict[str, int]]: Filtered records.

    Example:
      >>> records = [
      ...     {'id': 1, 'age': 25},
      ...     {'id': 2, 'age': 17},
      ...     {'id': 3, 'age': 30},
      ... ]
      >>> filtered = filter_records(records, min_age=18)
      >>> len(filtered)
      2
    """
```

### Non-compliant example — Vague or missing

```python
def train_model(features_csv, labels_csv, classifiers=None):
    """Trains a model.

    Example:
      Use this function to train a model on your data.
    """
```

### Non-compliant example — Too long or unrelated

```python
def train_model(features_csv, labels_csv):
    """Trains a model.

    Example:
      >>> import pandas as pd
      >>> import numpy as np
      >>> from sklearn import metrics
      >>> from sklearn.model_selection import train_test_split
      >>> # ... 50 more lines of setup code ...
    """
```

**Rules**
- Use **doctest style** (lines starting with `>>>` for input, output on next line).
- Indent Example block 2-4 spaces (consistent with Args/Returns).
- Show **realistic, complete usage** in 5-10 lines.
- Include expected output only when it clarifies behavior.
- Avoid fake or noisy output that can drift from real behavior.
- Use `...` (ellipsis) for line continuation in multi-line statements.
- Avoid setup boilerplate; assume imports are done.
- Example should be *runnable* (or clearly explainable if not).
- `Example:` is required for public APIs (no leading underscore) and optional for private helpers (e.g., `_helper`).

---

## Edge Cases & Common Patterns

### Variable-length Arguments

```python
def process(*items, verbose=False):
    """Processes items in batch.

    Args:
      *items (Any): Variable number of items to process.
      verbose (bool, optional): If True, print progress.

    Returns:
      list[Any]: A list of processed items.
    """
```

### Keyword Arguments

```python
def configure(**options):
    """Configures the system.

    Args:
      **options (Any): Configuration key-value pairs. Common keys:
        - 'timeout': Max seconds to wait (default: 30).
        - 'retries': Number of retry attempts (default: 3).
    """
```

### Complex Return Values

```python
def analyze(data):
    """Analyzes data and returns metrics.

    Returns:
      tuple[float, float, int]: A tuple of (mean, std_dev, count).
    """
```

### @property

```python
@property
def age(self):
    """The user's age in years."""
    return self._age
```

Use descriptive style, not "Returns the...".

---

## Length Guardrails

- Keep most docstrings to: summary + one short paragraph, unless complexity requires more.
- Keep parameter descriptions to one sentence in most cases.
- Prefer concise API-facing behavior over implementation detail.
- If a section grows too long, move deep detail to external docs and keep docstring focused.

---

## Compliance Summary

| Do | Don't |
|---|---|
| Keep it brief; assume Python knowledge | Write obvious details ("This function does X") |
| Use imperative style for summaries | Use passive voice or "This function..." |
| Use `name (type):` for all `Args:` entries | Omit types in `Args:` entries |
| Use `type:` for `Returns:` entries | Omit return types in `Returns:` entries |
| Use `name (type):` for `Attributes:` entries | Omit types in `Attributes:` entries |
| Use `Yields:` for generators | Use `Returns:` for generators |
| Omit `Returns:` for `None` returns | Add empty or redundant `Returns:` sections |
| Omit `Raises:` for API misuse errors | Document misuse/precondition errors as API guarantees |
| Document public attributes | Document private/internal details |
| List only important exceptions | List every possible error |
| Use `@override` to skip trivial docs | Write "See base class" without `@override` |
| Include `Example:` for every public API | Require `Example:` for private helpers |
| Use `Example:` header consistently | Mix `Example:` and `Examples:` in one file |
| Show realistic, complete code snippets | Show 50 lines of setup boilerplate |
| Use doctest style (`>>>`) for examples | Use prose or pseudo-code for examples |
| Include output only when it clarifies behavior | Add noisy or fake output lines |
| One-line descriptions per parameter | Multi-sentence explanations per parameter |
| Keep to summary + short paragraph by default | Turn every docstring into long-form documentation |
| Be consistent within a file | Mix styles or indentation levels |

---

## Validation Checklist

- [ ] Summary line is <=80 characters and ends with `.`, `?`, or `!`
- [ ] Blank line separates summary from details (multi-line docstrings)
- [ ] `Args:` lists all parameters concisely
- [ ] `Args:` uses `name (type):` format for each parameter
- [ ] `Returns:` describes return value(s) clearly (omit if return is `None`)
- [ ] `Returns:` uses `type:` format for each return value
- [ ] `Raises:` lists only documented exceptions
- [ ] `Raises:` excludes API misuse/precondition errors
- [ ] `Example:` shows realistic usage (5-10 lines, doctest style)
- [ ] `Example:` is present for public APIs and optional for private helpers
- [ ] For classes: `Attributes:` documents public attributes
- [ ] `Attributes:` uses `name (type):` format for each public attribute
- [ ] For generators: use `Yields:` not `Returns:`
- [ ] Section headers and indentation are consistent (`Example:`, 2 or 4 spaces)
- [ ] Indentation is consistent (2 or 4 spaces)
- [ ] No over-explanation; assume competent readers
