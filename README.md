# Mini -  A tiny terminal (curses) text editor.

A tiny terminal-based text editor written in Python using `curses`.

## Install (Debian/Ubuntu)

```bash
sudo apt update
sudo apt install -y python3 libncursesw6 ncurses-base
```

## Run

```bash
python3 mini.py file.txt
```

Or install system-wide:

```bash
sudo install -m 0755 mini.py /usr/local/bin/mini
mini file.txt
```

## Keys

- **Ctrl+O** — Save (WriteOut)
- **Ctrl+X** — Exit
- **Ctrl+F** — Find
- **Ctrl+G** — Go to line
- **Ctrl+L** — Redraw
- **Arrows / PgUp / PgDn** — Move
- **Enter / Backspace / Delete** — Edit

## Status Bar

Shows:
- Filename
- Last modified time
- Cursor location (line, column)
