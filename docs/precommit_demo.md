# Демонстрація блокування коміту через pre-commit

## Крок 1. Навмисно "поганий" файл

У `scripts/demo_broken.py` було навмисно додано:

- невикористані імпорти (`os`, `sys`);
- невикористану змінну (`unused_variable`);
- порушення форматування (зайві пробіли в дужках, відсутні пробіли навколо
  операторів).

```python
import os
import sys


def broken_function( ):
    unused_variable = 42
    x=1+2
    return   x
```

## Крок 2. Команда, яку виконали

```bash
git add scripts/demo_broken.py
git commit -m "Add demo script with intentional lint errors (pre-commit demo)"
```

## Крок 3. Повний вивід терміналу (коміт заблоковано)

```text
trim trailing whitespace.................................................Passed
fix end of files.........................................................Passed
check for added large files..............................................Passed
check for merge conflicts................................................Passed
check yaml...........................................(no files to check)Skipped
check toml...........................................(no files to check)Skipped
ruff (legacy alias)......................................................Failed
- hook id: ruff
- exit code: 1
- files were modified by this hook

F841 Local variable `unused_variable` is assigned to but never used
 --> scripts/demo_broken.py:4:5
  |
3 | def broken_function( ):
4 |     unused_variable = 42
  |     ^^^^^^^^^^^^^^^
5 |     x=1+2
6 |     return   x
  |
help: Remove assignment to unused variable `unused_variable`

Found 3 errors (2 fixed, 1 remaining).
No fixes available (1 hidden fix can be enabled with the `--unsafe-fixes` option).

black....................................................................Failed
- hook id: black
- files were modified by this hook

reformatted scripts/demo_broken.py

All done! ✨ 🍰 ✨
1 file reformatted.

EXIT_CODE=1
```

`ruff` автоматично прибрав невикористані імпорти (2 з 3 помилок виправлено
автоматично), але `F841` (невикористана локальна змінна) вимагає ручного
втручання — тому хук завершився з помилкою і **git commit не відбувся**.
`black` водночас переформатував файл (прибрав зайві пробіли, розставив
пробіли навколо операторів). Оскільки хуки модифікували файл, зміни
потрібно було переглянути й додати в staging area повторно.

## Крок 4. Виправлення помилки вручну

Після автоматичних виправлень від ruff/black залишилось прибрати
невикористану змінну вручну:

```python
def broken_function():
    x = 1 + 2
    return x
```

## Крок 5. Успішний коміт

```bash
git add scripts/demo_broken.py docs/precommit_demo.md
git commit -m "Add demo script with intentional lint errors (pre-commit demo)"
```

```text
trim trailing whitespace.................................................Passed
fix end of files.........................................................Passed
check for added large files..............................................Passed
check for merge conflicts................................................Passed
check yaml...........................................(no files to check)Skipped
check toml...........................................(no files to check)Skipped
ruff (legacy alias)......................................................Passed
black....................................................................Passed
[main 6ecd4e4] Add demo script with intentional lint errors (pre-commit demo)
 2 files changed, 112 insertions(+)
 create mode 100644 docs/precommit_demo.md
 create mode 100644 scripts/demo_broken.py
```

Коміт успішно пройшов усі хуки (hash `6ecd4e4`).
