#!/usr/bin/env python3
"""
Mini -  A tiny terminal (curses) text editor.


Usage:
  python3 mini.py <file>

Nano-style keys ONLY for save/quit:
  Ctrl+O  WriteOut (save)
  Ctrl+X  Exit

Other keys:
  Ctrl+F  Find
  Ctrl+G  Go to line
  Ctrl+L  Redraw
  Arrows/Home/End/PgUp/PgDn, Enter, Backspace, Delete

Status bar shows:
  - filename
  - last modified time
  - location (line:col)
"""

from __future__ import annotations

import curses
import os
import sys
import time
import termios
from dataclasses import dataclass

CTRL_O = 15  # ^O
CTRL_X = 24  # ^X
CTRL_F = 6   # ^F
CTRL_G = 7   # ^G
CTRL_L = 12  # ^L


@dataclass
class Status:
    msg: str = ""
    dirty: bool = False


def fmt_mtime(path: str) -> str:
    try:
        ts = os.path.getmtime(path)
        return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts))
    except Exception:
        return "N/A"


class Editor:
    def __init__(self, path: str):
        self.path = path
        self.lines: list[str] = []
        self.cx = 0
        self.cy = 0
        self.rowoff = 0
        self.coloff = 0
        self.status = Status()
        self._loaded_mtime = fmt_mtime(path)
        self._load()

    def _load(self) -> None:
        try:
            with open(self.path, "r", encoding="utf-8", errors="replace") as f:
                data = f.read().splitlines()
            self.lines = data if data else [""]
            self.status.msg = "Opened"
            self.status.dirty = False
            self._loaded_mtime = fmt_mtime(self.path)
        except FileNotFoundError:
            self.lines = [""]
            self.status.msg = "New file"
            self.status.dirty = False
            self._loaded_mtime = "N/A"
        except Exception as e:
            self.lines = [""]
            self.status.msg = f"Error loading: {e}"
            self.status.dirty = False
            self._loaded_mtime = "N/A"

    def save(self) -> None:
        try:
            d = os.path.dirname(self.path)
            if d:
                os.makedirs(d, exist_ok=True)
            with open(self.path, "w", encoding="utf-8") as f:
                f.write("\n".join(self.lines))
                f.write("\n")
            self.status.msg = "Wrote file"
            self.status.dirty = False
            self._loaded_mtime = fmt_mtime(self.path)
        except Exception as e:
            self.status.msg = f"Write error: {e}"

    # ----- editing -----
    def _clamp_cursor(self) -> None:
        self.cy = max(0, min(self.cy, len(self.lines) - 1))
        self.cx = max(0, min(self.cx, len(self.lines[self.cy])))

    def insert_char(self, ch: str) -> None:
        s = self.lines[self.cy]
        self.lines[self.cy] = s[: self.cx] + ch + s[self.cx :]
        self.cx += len(ch)
        self.status.dirty = True

    def insert_newline(self) -> None:
        s = self.lines[self.cy]
        left, right = s[: self.cx], s[self.cx :]
        self.lines[self.cy] = left
        self.lines.insert(self.cy + 1, right)
        self.cy += 1
        self.cx = 0
        self.status.dirty = True

    def backspace(self) -> None:
        if self.cx > 0:
            s = self.lines[self.cy]
            self.lines[self.cy] = s[: self.cx - 1] + s[self.cx :]
            self.cx -= 1
            self.status.dirty = True
            return
        if self.cy > 0:
            prev = self.lines[self.cy - 1]
            cur = self.lines[self.cy]
            self.cx = len(prev)
            self.lines[self.cy - 1] = prev + cur
            del self.lines[self.cy]
            self.cy -= 1
            self.status.dirty = True

    def delete(self) -> None:
        s = self.lines[self.cy]
        if self.cx < len(s):
            self.lines[self.cy] = s[: self.cx] + s[self.cx + 1 :]
            self.status.dirty = True
            return
        if self.cy < len(self.lines) - 1:
            self.lines[self.cy] = s + self.lines[self.cy + 1]
            del self.lines[self.cy + 1]
            self.status.dirty = True

    # ----- movement -----
    def left(self) -> None:
        if self.cx > 0:
            self.cx -= 1
        elif self.cy > 0:
            self.cy -= 1
            self.cx = len(self.lines[self.cy])

    def right(self) -> None:
        s = self.lines[self.cy]
        if self.cx < len(s):
            self.cx += 1
        elif self.cy < len(self.lines) - 1:
            self.cy += 1
            self.cx = 0

    def up(self) -> None:
        if self.cy > 0:
            self.cy -= 1
            self.cx = min(self.cx, len(self.lines[self.cy]))

    def down(self) -> None:
        if self.cy < len(self.lines) - 1:
            self.cy += 1
            self.cx = min(self.cx, len(self.lines[self.cy]))

    def home(self) -> None:
        self.cx = 0

    def end(self) -> None:
        self.cx = len(self.lines[self.cy])

    def page_up(self, n: int) -> None:
        self.cy = max(0, self.cy - n)
        self.cx = min(self.cx, len(self.lines[self.cy]))

    def page_down(self, n: int) -> None:
        self.cy = min(len(self.lines) - 1, self.cy + n)
        self.cx = min(self.cx, len(self.lines[self.cy]))

    # ----- prompts -----
    def _prompt(self, stdscr, prompt: str) -> str | None:
        h, w = stdscr.getmaxyx()
        buf = ""
        while True:
            stdscr.move(h - 1, 0)
            stdscr.clrtoeol()
            stdscr.addnstr(h - 1, 0, (prompt + buf), w - 1, curses.A_REVERSE)
            stdscr.refresh()
            k = stdscr.getch()
            if k == 27:  # ESC
                self.status.msg = "Cancelled"
                return None
            if k in (10, 13):
                return buf
            if k in (curses.KEY_BACKSPACE, 127, 8):
                buf = buf[:-1]
                continue
            if 32 <= k <= 126:
                buf += chr(k)

    def _confirm_exit(self, stdscr) -> bool:
        if not self.status.dirty:
            return True
        ans = self._prompt(stdscr, "Save modified buffer? (y/N): ")
        if ans and ans.lower().startswith("y"):
            self.save()
            return True
        return bool(ans and ans.lower().startswith("n"))

    def find(self, stdscr) -> None:
        q = self._prompt(stdscr, "Search: ")
        if not q:
            return
        start_y, start_x = self.cy, self.cx
        for passno in (0, 1):
            y_range = range(start_y, len(self.lines)) if passno == 0 else range(0, start_y + 1)
            for y in y_range:
                x0 = start_x if (passno == 0 and y == start_y) else 0
                idx = self.lines[y].find(q, x0)
                if idx != -1:
                    self.cy, self.cx = y, idx
                    self.status.msg = "Found"
                    return
        self.status.msg = "Not found"

    def goto_line(self, stdscr) -> None:
        s = self._prompt(stdscr, "Go to line: ")
        if not s:
            return
        try:
            n = max(1, int(s))
            self.cy = min(len(self.lines) - 1, n - 1)
            self.cx = min(self.cx, len(self.lines[self.cy]))
            self.status.msg = f"Line {n}"
        except ValueError:
            self.status.msg = "Invalid number"

    # ----- view/scroll -----
    def _scroll(self, text_h: int, w: int) -> None:
        self._clamp_cursor()
        if self.cy < self.rowoff:
            self.rowoff = self.cy
        if self.cy >= self.rowoff + text_h:
            self.rowoff = self.cy - text_h + 1
        if self.cx < self.coloff:
            self.coloff = self.cx
        if self.cx >= self.coloff + w:
            self.coloff = self.cx - w + 1

    # ----- draw -----
    def draw(self, stdscr) -> None:
        stdscr.erase()
        h, w = stdscr.getmaxyx()
        text_h = max(1, h - 2)  # status + help

        self._scroll(text_h, w - 1)

        for y in range(text_h):
            fy = self.rowoff + y
            if fy >= len(self.lines):
                break
            seg = self.lines[fy][self.coloff : self.coloff + (w - 1)]
            stdscr.addnstr(y, 0, seg, w - 1)

        # status bar (filename / modified / location)
        name = os.path.basename(self.path) or self.path
        mod = "*" if self.status.dirty else ""
        mtime = self._loaded_mtime
        loc = f"Ln {self.cy+1}, Col {self.cx+1}"
        left = f" {name}{mod} "
        mid = f" Modified: {mtime} "
        right = f" {loc} "

        # fit status bar
        bar = left
        if len(bar) + len(mid) + len(right) <= w - 1:
            bar += mid
            bar = bar.ljust((w - 1) - len(right)) + right
        else:
            # compact if terminal is narrow
            compact = f" {name}{mod} | {loc} "
            bar = compact[: w - 1].ljust(w - 1)

        stdscr.addnstr(h - 2, 0, bar, w - 1, curses.A_REVERSE)

        # nano-style help line for save/exit only
        help_line = "^O WriteOut   ^X Exit"
        help_line = help_line.ljust(w - 1)
        stdscr.addnstr(h - 1, 0, help_line, w - 1, curses.A_REVERSE)

        # cursor
        cy = self.cy - self.rowoff
        cx = self.cx - self.coloff
        if 0 <= cy < text_h and 0 <= cx < w:
            stdscr.move(cy, cx)

        stdscr.refresh()

    def run(self, stdscr) -> int:
        curses.use_default_colors()
        curses.curs_set(1)
        stdscr.keypad(True)
        stdscr.timeout(-1)

        while True:
            self.draw(stdscr)
            k = stdscr.getch()

            if k == CTRL_L:
                stdscr.clear()
                continue

            # Nano-style save/quit ONLY
            if k == CTRL_O:
                self.save()
                continue
            if k == CTRL_X:
                if self._confirm_exit(stdscr):
                    return 0
                self.status.msg = "Exit cancelled"
                continue

            if k == CTRL_F:
                self.find(stdscr)
                continue
            if k == CTRL_G:
                self.goto_line(stdscr)
                continue

            if k == curses.KEY_UP:
                self.up()
            elif k == curses.KEY_DOWN:
                self.down()
            elif k == curses.KEY_LEFT:
                self.left()
            elif k == curses.KEY_RIGHT:
                self.right()
            elif k == curses.KEY_HOME:
                self.home()
            elif k == curses.KEY_END:
                self.end()
            elif k == curses.KEY_NPAGE:
                self.page_down(max(1, (stdscr.getmaxyx()[0] - 2)))
            elif k == curses.KEY_PPAGE:
                self.page_up(max(1, (stdscr.getmaxyx()[0] - 2)))
            elif k in (10, 13):
                self.insert_newline()
            elif k in (curses.KEY_BACKSPACE, 127, 8):
                self.backspace()
            elif k == curses.KEY_DC:
                self.delete()
            elif 32 <= k <= 126:
                self.insert_char(chr(k))

        return 0


def _disable_ixon() -> tuple[int, list[int]] | None:
    # Ensure Ctrl+O/Ctrl+X are delivered properly on systems with weird flow configs
    try:
        fd = sys.stdin.fileno()
        if not os.isatty(fd):
            return None
        old = termios.tcgetattr(fd)
        new = termios.tcgetattr(fd)
        new[0] = new[0] & ~(termios.IXON | termios.IXOFF)
        termios.tcsetattr(fd, termios.TCSANOW, new)
        return fd, old
    except Exception:
        return None


def _restore_term(state) -> None:
    if not state:
        return
    fd, old = state
    try:
        termios.tcsetattr(fd, termios.TCSANOW, old)
    except Exception:
        pass

def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: mini_cli_editor.py <file>")
        return 2

    path = sys.argv[1]
    ed = Editor(path)

    term_state = _disable_ixon()
    try:
        return curses.wrapper(lambda stdscr: ed.run(stdscr))
    finally:
        _restore_term(term_state)
if __name__ == "__main__":
    raise SystemExit(main())

