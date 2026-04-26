#!/usr/bin/env python3
"""
OnTrack — GUI Installer
TDS Telecom Field Route Optimizer (Python edition)

Packages and installs the OnTrack Python app on Windows or Linux.
Run standalone:   python ontrack_installer.py
Frozen binary:    pyinstaller installer.spec  →  OnTrackInstaller.exe / OnTrackInstaller

What it does:
  1. Detect platform (Windows / Linux)
  2. Let user choose install directory
  3. Extract the bundled app files into that directory
  4. Create a Python virtual environment
  5. Install pip dependencies from requirements.txt
  6. Create a desktop shortcut / .desktop file
  7. On Windows: optionally add to PATH and create Start Menu entry
"""

from __future__ import annotations
import os
import sys
import platform
import shutil
import subprocess
import tempfile
import threading
import zipfile
import pathlib
import stat

import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog, messagebox

# ── Brand colours ─────────────────────────────────────────────────────────
TDS_BLUE    = "#0057A8"
TDS_NAVY    = "#002855"
TDS_ORANGE  = "#F26522"
TDS_BG      = "#111827"
TDS_SURFACE = "#1A2535"
TDS_CARD    = "#243044"
TDS_WHITE   = "#FFFFFF"
TDS_GRAY    = "#6B7280"
TDS_GREEN   = "#22C55E"
TDS_RED     = "#EF4444"

APP_NAME    = "OnTrack"
APP_VERSION = "2.0.0"
APP_ORG     = "TDS Telecom"

IS_WINDOWS  = platform.system() == "Windows"
IS_LINUX    = platform.system() == "Linux"

# ── Default install paths ──────────────────────────────────────────────────

def default_install_dir() -> str:
    if IS_WINDOWS:
        base = os.environ.get("LOCALAPPDATA", os.path.expanduser("~\\AppData\\Local"))
        return os.path.join(base, APP_ORG, APP_NAME)
    return os.path.expanduser(f"~/.local/share/ontrack")

def desktop_dir() -> str:
    if IS_WINDOWS:
        return os.path.join(os.path.expanduser("~"), "Desktop")
    xdg = os.environ.get("XDG_DESKTOP_DIR", "")
    return xdg if xdg else os.path.expanduser("~/Desktop")

# ── Source detection ───────────────────────────────────────────────────────

def source_root() -> pathlib.Path:
    """
    Return the root of the ontrack Python source tree.
    Works both when run from source and when frozen by PyInstaller
    (PyInstaller sets sys._MEIPASS to the temp extraction dir).
    """
    if hasattr(sys, "_MEIPASS"):
        return pathlib.Path(sys._MEIPASS)
    # Running from source: installer lives in ontrack/installer/
    return pathlib.Path(__file__).parent.parent.resolve()

def requirements_path() -> pathlib.Path:
    return source_root() / "requirements.txt"

# ──────────────────────────────────────────────────────────────────────────
# Installer logic
# ──────────────────────────────────────────────────────────────────────────

class InstallerWorker:
    """Runs installation steps on a background thread."""

    def __init__(self, install_dir: str, create_shortcut: bool, log_cb, done_cb, error_cb):
        self.install_dir    = pathlib.Path(install_dir)
        self.create_shortcut = create_shortcut
        self.log            = log_cb
        self.done           = done_cb
        self.error          = error_cb

    def run(self):
        try:
            self._step_copy_files()
            self._step_create_venv()
            self._step_install_deps()
            if self.create_shortcut:
                self._step_create_shortcut()
            self.done()
        except Exception as e:
            self.error(str(e))

    def _step_copy_files(self):
        self.log("Copying application files…", 10)
        src = source_root()
        dst = self.install_dir

        if dst.exists():
            shutil.rmtree(dst)
        dst.mkdir(parents=True, exist_ok=True)

        ignore = shutil.ignore_patterns(
            "__pycache__", "*.pyc", ".git", ".venv", "venv",
            "installer", "*.egg-info", ".pytest_cache", "dist", "build",
        )
        for item in src.iterdir():
            if item.name in {"installer", ".git", ".venv", "venv", "dist", "build", "__pycache__"}:
                continue
            dest = dst / item.name
            if item.is_dir():
                shutil.copytree(item, dest, ignore=ignore)
            else:
                shutil.copy2(item, dest)

        self.log("Application files copied.", 25)

    def _step_create_venv(self):
        self.log("Creating Python virtual environment…", 35)
        venv_dir = self.install_dir / ".venv"
        subprocess.run(
            [sys.executable, "-m", "venv", str(venv_dir)],
            check=True,
            capture_output=True,
        )
        self.log("Virtual environment created.", 50)

    def _step_install_deps(self):
        self.log("Installing dependencies (this may take a few minutes)…", 55)
        venv_dir = self.install_dir / ".venv"

        if IS_WINDOWS:
            pip = venv_dir / "Scripts" / "pip.exe"
        else:
            pip = venv_dir / "bin" / "pip"

        req = self.install_dir / "requirements.txt"
        subprocess.run(
            [str(pip), "install", "--upgrade", "pip"],
            check=True, capture_output=True,
        )
        subprocess.run(
            [str(pip), "install", "-r", str(req)],
            check=True, capture_output=True,
        )
        self.log("Dependencies installed.", 80)

    def _step_create_shortcut(self):
        self.log("Creating desktop shortcut…", 88)

        if IS_WINDOWS:
            self._shortcut_windows()
        elif IS_LINUX:
            self._shortcut_linux()

        self.log("Desktop shortcut created.", 95)

    def _shortcut_windows(self):
        """Create a .lnk shortcut via PowerShell (no extra deps needed)."""
        venv_pythonw = self.install_dir / ".venv" / "Scripts" / "pythonw.exe"
        main_py      = self.install_dir / "main.py"
        desktop      = pathlib.Path(desktop_dir())
        lnk          = desktop / f"{APP_NAME}.lnk"

        ps_script = f"""
$WshShell = New-Object -comObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut("{lnk}")
$Shortcut.TargetPath = "{venv_pythonw}"
$Shortcut.Arguments = '"{main_py}"'
$Shortcut.WorkingDirectory = "{self.install_dir}"
$Shortcut.Description = "OnTrack — TDS Field Route Optimizer"
$Shortcut.Save()
"""
        subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_script],
            check=True, capture_output=True,
        )

    def _shortcut_linux(self):
        """Create a .desktop file in ~/.local/share/applications and on Desktop."""
        venv_python = self.install_dir / ".venv" / "bin" / "python"
        main_py     = self.install_dir / "main.py"
        icon        = self.install_dir / "assets" / "ontrack.png"

        desktop_entry = (
            "[Desktop Entry]\n"
            "Type=Application\n"
            f"Name={APP_NAME}\n"
            f"Comment=TDS Telecom Field Route Optimizer\n"
            f"Exec={venv_python} {main_py}\n"
            f"Icon={icon}\n"
            "Terminal=false\n"
            "Categories=Utility;Geography;\n"
        )

        # System applications directory
        apps_dir = pathlib.Path.home() / ".local" / "share" / "applications"
        apps_dir.mkdir(parents=True, exist_ok=True)
        app_file = apps_dir / "ontrack.desktop"
        app_file.write_text(desktop_entry)
        app_file.chmod(app_file.stat().st_mode | stat.S_IEXEC)

        # Desktop shortcut
        desk = pathlib.Path(desktop_dir())
        if desk.exists():
            desk_file = desk / "OnTrack.desktop"
            desk_file.write_text(desktop_entry)
            desk_file.chmod(desk_file.stat().st_mode | stat.S_IEXEC)


# ──────────────────────────────────────────────────────────────────────────
# GUI
# ──────────────────────────────────────────────────────────────────────────

class OnTrackInstaller(ctk.CTk):
    PAGE_WELCOME  = 0
    PAGE_OPTIONS  = 1
    PAGE_PROGRESS = 2
    PAGE_DONE     = 3

    def __init__(self):
        super().__init__()
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.title(f"{APP_NAME} {APP_VERSION} — Installer")
        self.geometry("680x500")
        self.resizable(False, False)
        self.configure(fg_color=TDS_BG)

        self._page = self.PAGE_WELCOME
        self._install_dir = tk.StringVar(value=default_install_dir())
        self._create_shortcut = tk.BooleanVar(value=True)
        self._add_to_path = tk.BooleanVar(value=IS_WINDOWS)
        self._progress_var = tk.DoubleVar(value=0)
        self._log_var = tk.StringVar(value="")
        self._install_success = False

        self._build()
        self._show_page(self.PAGE_WELCOME)

    # ── Layout ─────────────────────────────────────────────────────────────

    def _build(self):
        # Header strip
        header = ctk.CTkFrame(self, fg_color=TDS_NAVY, corner_radius=0, height=72)
        header.pack(fill="x")
        header.pack_propagate(False)

        ctk.CTkLabel(
            header,
            text=f"  🗺  {APP_NAME}",
            font=ctk.CTkFont(size=26, weight="bold"),
            text_color=TDS_WHITE,
        ).pack(side="left", padx=20)

        ctk.CTkLabel(
            header,
            text=f"v{APP_VERSION}  ·  {APP_ORG}",
            font=ctk.CTkFont(size=13),
            text_color="#9DB8D6",
        ).pack(side="left")

        # Body — stacked pages (only one visible at a time)
        self.body = ctk.CTkFrame(self, fg_color=TDS_BG, corner_radius=0)
        self.body.pack(fill="both", expand=True)

        self.pages: dict[int, ctk.CTkFrame] = {}
        for pid, builder in [
            (self.PAGE_WELCOME,  self._build_welcome),
            (self.PAGE_OPTIONS,  self._build_options),
            (self.PAGE_PROGRESS, self._build_progress),
            (self.PAGE_DONE,     self._build_done),
        ]:
            frame = ctk.CTkFrame(self.body, fg_color=TDS_BG, corner_radius=0)
            frame.place(relx=0, rely=0, relwidth=1, relheight=1)
            builder(frame)
            self.pages[pid] = frame

    # ── Page builders ───────────────────────────────────────────────────────

    def _build_welcome(self, p: ctk.CTkFrame):
        ctk.CTkLabel(
            p, text="Welcome",
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color=TDS_WHITE,
        ).pack(pady=(36, 8))

        ctk.CTkLabel(
            p,
            text=(
                f"This installer will set up {APP_NAME} v{APP_VERSION}\n"
                f"on your computer.\n\n"
                f"{APP_NAME} is a field route optimizer for TDS Telecom technicians.\n"
                f"It helps plan optimal driving routes between service addresses\n"
                f"and integrates with Google Maps and ArcGIS FieldMaps.\n\n"
                f"No API key is required — all core features work out of the box."
            ),
            font=ctk.CTkFont(size=14),
            text_color="#C7D9F0",
            justify="center",
        ).pack(pady=(0, 24))

        req_label = (
            f"Requirements: Python {sys.version_info.major}.{sys.version_info.minor}+  ·  "
            f"~250 MB disk space  ·  Internet connection (first run)"
        )
        ctk.CTkLabel(
            p, text=req_label,
            font=ctk.CTkFont(size=11),
            text_color=TDS_GRAY,
        ).pack(pady=(0, 28))

        ctk.CTkButton(
            p, text="Next →", width=160, height=44,
            fg_color=TDS_ORANGE, hover_color="#D4541A",
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color=TDS_WHITE,
            command=lambda: self._show_page(self.PAGE_OPTIONS),
        ).pack()

    def _build_options(self, p: ctk.CTkFrame):
        ctk.CTkLabel(
            p, text="Installation Options",
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color=TDS_WHITE,
        ).pack(pady=(28, 16))

        # Install directory
        dir_card = ctk.CTkFrame(p, fg_color=TDS_SURFACE, corner_radius=10)
        dir_card.pack(fill="x", padx=60, pady=(0, 12))
        ctk.CTkLabel(
            dir_card, text="Install directory",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=TDS_WHITE,
        ).pack(anchor="w", padx=16, pady=(12, 4))

        dir_row = ctk.CTkFrame(dir_card, fg_color="transparent")
        dir_row.pack(fill="x", padx=16, pady=(0, 12))
        dir_row.grid_columnconfigure(0, weight=1)

        ctk.CTkEntry(
            dir_row,
            textvariable=self._install_dir,
            height=36,
            fg_color=TDS_CARD,
            border_color=TDS_BLUE,
            text_color=TDS_WHITE,
        ).grid(row=0, column=0, sticky="ew", padx=(0, 8))

        ctk.CTkButton(
            dir_row, text="Browse…", width=90, height=36,
            fg_color=TDS_BLUE, hover_color=TDS_NAVY,
            command=self._browse_dir,
        ).grid(row=0, column=1)

        # Options
        opts_card = ctk.CTkFrame(p, fg_color=TDS_SURFACE, corner_radius=10)
        opts_card.pack(fill="x", padx=60, pady=(0, 12))
        ctk.CTkLabel(
            opts_card, text="Options",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=TDS_WHITE,
        ).pack(anchor="w", padx=16, pady=(12, 6))

        ctk.CTkCheckBox(
            opts_card,
            text="Create desktop shortcut",
            variable=self._create_shortcut,
            text_color=TDS_WHITE,
            fg_color=TDS_BLUE,
        ).pack(anchor="w", padx=24, pady=(0, 4))

        if IS_WINDOWS:
            ctk.CTkCheckBox(
                opts_card,
                text="Add to PATH (allows running 'ontrack' from any terminal)",
                variable=self._add_to_path,
                text_color=TDS_WHITE,
                fg_color=TDS_BLUE,
            ).pack(anchor="w", padx=24, pady=(0, 12))
        else:
            ctk.CTkFrame(opts_card, height=8, fg_color="transparent").pack()

        # Disk space estimate
        ctk.CTkLabel(
            p,
            text="Estimated disk usage: ~250 MB (includes Python venv + dependencies)",
            font=ctk.CTkFont(size=11),
            text_color=TDS_GRAY,
        ).pack(pady=(0, 16))

        btn_row = ctk.CTkFrame(p, fg_color="transparent")
        btn_row.pack()

        ctk.CTkButton(
            btn_row, text="← Back", width=120, height=40,
            fg_color=TDS_SURFACE, hover_color=TDS_CARD,
            text_color=TDS_WHITE,
            command=lambda: self._show_page(self.PAGE_WELCOME),
        ).pack(side="left", padx=8)

        ctk.CTkButton(
            btn_row, text="Install", width=160, height=40,
            fg_color=TDS_ORANGE, hover_color="#D4541A",
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color=TDS_WHITE,
            command=self._start_install,
        ).pack(side="left", padx=8)

    def _build_progress(self, p: ctk.CTkFrame):
        ctk.CTkLabel(
            p, text="Installing…",
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color=TDS_WHITE,
        ).pack(pady=(40, 16))

        self._progress_bar = ctk.CTkProgressBar(
            p, width=480, height=18,
            progress_color=TDS_BLUE,
            fg_color=TDS_CARD,
            corner_radius=9,
        )
        self._progress_bar.pack(pady=(0, 12))
        self._progress_bar.set(0)

        self._pct_label = ctk.CTkLabel(
            p, text="0%",
            font=ctk.CTkFont(size=12),
            text_color=TDS_GRAY,
        )
        self._pct_label.pack()

        ctk.CTkLabel(
            p, textvariable=self._log_var,
            font=ctk.CTkFont(size=13),
            text_color="#9DB8D6",
            wraplength=520,
        ).pack(pady=(24, 0))

        ctk.CTkLabel(
            p,
            text="Please wait — do not close this window.",
            font=ctk.CTkFont(size=11),
            text_color=TDS_GRAY,
        ).pack(pady=(12, 0))

    def _build_done(self, p: ctk.CTkFrame):
        self._done_icon_lbl = ctk.CTkLabel(
            p, text="✓",
            font=ctk.CTkFont(size=52),
            text_color=TDS_GREEN,
        )
        self._done_icon_lbl.pack(pady=(36, 0))

        self._done_title_lbl = ctk.CTkLabel(
            p, text="Installation Complete",
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color=TDS_WHITE,
        )
        self._done_title_lbl.pack(pady=(8, 0))

        self._done_body_lbl = ctk.CTkLabel(
            p,
            text="",
            font=ctk.CTkFont(size=13),
            text_color="#C7D9F0",
            justify="center",
        )
        self._done_body_lbl.pack(pady=(8, 24))

        btn_row = ctk.CTkFrame(p, fg_color="transparent")
        btn_row.pack()

        self._launch_btn = ctk.CTkButton(
            btn_row, text="🚀 Launch OnTrack", width=180, height=44,
            fg_color=TDS_ORANGE, hover_color="#D4541A",
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color=TDS_WHITE,
            command=self._launch_app,
        )
        self._launch_btn.pack(side="left", padx=8)

        ctk.CTkButton(
            btn_row, text="Close", width=100, height=44,
            fg_color=TDS_SURFACE, hover_color=TDS_CARD,
            text_color=TDS_WHITE,
            command=self.quit,
        ).pack(side="left", padx=8)

    # ── Navigation ──────────────────────────────────────────────────────────

    def _show_page(self, pid: int):
        self._page = pid
        for k, frame in self.pages.items():
            if k == pid:
                frame.lift()

    # ── Actions ─────────────────────────────────────────────────────────────

    def _browse_dir(self):
        d = filedialog.askdirectory(title="Choose install directory",
                                    initialdir=self._install_dir.get())
        if d:
            self._install_dir.set(d)

    def _start_install(self):
        install_dir = self._install_dir.get().strip()
        if not install_dir:
            messagebox.showerror("Error", "Please choose an install directory.")
            return

        self._show_page(self.PAGE_PROGRESS)
        self._progress_bar.set(0)
        self._log_var.set("Starting installation…")

        worker = InstallerWorker(
            install_dir=install_dir,
            create_shortcut=self._create_shortcut.get(),
            log_cb=self._on_log,
            done_cb=self._on_done,
            error_cb=self._on_error,
        )
        threading.Thread(target=worker.run, daemon=True).start()

    def _on_log(self, msg: str, pct: float):
        self.after(0, lambda: self._set_progress(msg, pct))

    def _set_progress(self, msg: str, pct: float):
        self._progress_bar.set(pct / 100)
        self._pct_label.configure(text=f"{int(pct)}%")
        self._log_var.set(msg)

    def _on_done(self):
        self.after(0, self._show_done_success)

    def _show_done_success(self):
        self._install_success = True
        self._progress_bar.set(1.0)
        self._pct_label.configure(text="100%")
        self._log_var.set("Installation complete.")

        install_dir = self._install_dir.get()
        body = (
            f"OnTrack has been installed to:\n{install_dir}\n\n"
            f"{'A desktop shortcut has been created.' if self._create_shortcut.get() else ''}"
        )
        self._done_body_lbl.configure(text=body.strip())

        self._show_page(self.PAGE_DONE)

    def _on_error(self, msg: str):
        self.after(0, lambda: self._show_done_error(msg))

    def _show_done_error(self, msg: str):
        self._done_icon_lbl.configure(text="✗", text_color=TDS_RED)
        self._done_title_lbl.configure(text="Installation Failed")
        self._done_body_lbl.configure(
            text=f"An error occurred during installation:\n\n{msg}\n\n"
                 f"Check that you have write permission to the chosen directory\n"
                 f"and an active internet connection, then try again.",
            text_color="#FFAAAA",
        )
        self._launch_btn.configure(state="disabled")
        self._show_page(self.PAGE_DONE)

    def _launch_app(self):
        if not self._install_success:
            return
        install_dir = pathlib.Path(self._install_dir.get())
        if IS_WINDOWS:
            python = install_dir / ".venv" / "Scripts" / "pythonw.exe"
        else:
            python = install_dir / ".venv" / "bin" / "python"
        main_py = install_dir / "main.py"

        try:
            if IS_WINDOWS:
                import subprocess
                subprocess.Popen([str(python), str(main_py)],
                                 creationflags=subprocess.DETACHED_PROCESS)
            else:
                subprocess.Popen([str(python), str(main_py)],
                                 start_new_session=True)
        except Exception as e:
            messagebox.showerror("Launch Error", str(e))
            return
        self.quit()


# ── Uninstaller helper ─────────────────────────────────────────────────────

class UninstallHelper:
    """Removes OnTrack from the machine. Run with --uninstall flag."""

    @staticmethod
    def run():
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        root = ctk.CTk()
        root.title("OnTrack — Uninstaller")
        root.geometry("460x280")
        root.configure(fg_color=TDS_BG)

        ctk.CTkLabel(
            root, text="Uninstall OnTrack",
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color=TDS_WHITE,
        ).pack(pady=(32, 8))

        install_dir = default_install_dir()
        ctk.CTkLabel(
            root,
            text=f"Remove OnTrack from:\n{install_dir}",
            font=ctk.CTkFont(size=13),
            text_color=TDS_GRAY,
        ).pack(pady=(0, 24))

        btn_row = ctk.CTkFrame(root, fg_color="transparent")
        btn_row.pack()

        def _do_uninstall():
            try:
                shutil.rmtree(install_dir, ignore_errors=True)
                # Remove .desktop file on Linux
                if IS_LINUX:
                    desk = pathlib.Path.home() / ".local/share/applications/ontrack.desktop"
                    desk.unlink(missing_ok=True)
                messagebox.showinfo("Uninstalled", "OnTrack has been removed.")
            except Exception as e:
                messagebox.showerror("Error", str(e))
            root.quit()

        ctk.CTkButton(
            btn_row, text="Uninstall", width=140, height=40,
            fg_color=TDS_RED, hover_color="#C13333",
            text_color=TDS_WHITE, font=ctk.CTkFont(size=14, weight="bold"),
            command=_do_uninstall,
        ).pack(side="left", padx=8)

        ctk.CTkButton(
            btn_row, text="Cancel", width=100, height=40,
            fg_color=TDS_SURFACE, hover_color=TDS_CARD,
            text_color=TDS_WHITE,
            command=root.quit,
        ).pack(side="left", padx=8)

        root.mainloop()


# ── Entry point ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if "--uninstall" in sys.argv:
        UninstallHelper.run()
    else:
        app = OnTrackInstaller()
        app.mainloop()
