# main_window.py
import os
import queue
import logging
import datetime
import threading
from io import BytesIO

import requests
from PIL import Image
import customtkinter as ctk

from core.installer import InstallerProcess
from core.version import version
from ui import theme

LOGO_URL = "https://raw.githubusercontent.com/Ascendara/ascendara/refs/heads/main/src/public/icon.png"
VERSION_URL = "https://api.ascendara.app/"

WIDTH, HEIGHT = 860, 540
HERO_WIDTH = 300
SPINNER_FRAMES = 12

# Detect the Windows theme once, before any CTk widgets are created
windows_dark_mode = theme.is_windows_dark_mode()
logging.info(f"Windows dark mode detected: {windows_dark_mode}")
ctk.set_appearance_mode("dark" if windows_dark_mode else "light")
ctk.set_default_color_theme("blue")

STEPS = [
    ("Download", "Fetching the latest release"),
    ("Install", "Running the Ascendara setup"),
    ("Launch", "Opening Ascendara"),
]


class AscendaraInstaller(ctk.CTk):
    def __init__(self):
        """Initialize the main application window"""
        super().__init__()
        logging.info("Initializing main window")

        self.colors = theme.DARK if windows_dark_mode else theme.LIGHT
        self.font = theme.ui_font()
        self.font_semibold = theme.ui_font_semibold()
        self.icon_font = theme.icon_font()

        self.log_window = None
        self.installer = None
        self.after_ids = {}
        self.x = 0
        self.y = 0
        self.closing = False

        # Background threads post UI work here; it is drained on the Tk thread
        self._ui_queue = queue.Queue()

        # State
        self.app_version = None
        self.logo_image = None
        self.step_states = ["pending"] * len(STEPS)
        self.spinner_frame = 0
        self.target_progress = 0.0
        self.shown_progress = 0.0
        self.indeterminate = False
        self.last_status = ""

        self._setup_window()
        self._create_ui()

        logging.info(f"Installer Version {version}")
        self.protocol("WM_DELETE_WINDOW", self.close)

        self._poll_ui_queue()
        self._spinner_tick()
        self._load_remote_assets()

        # Fade in, then start installing
        self.attributes("-alpha", 0.0)
        self.after(20, self._apply_native_styles)
        self.fade_in(completion_callback=self.on_fade_in_complete)

    # ------------------------------------------------------------------ #
    # Window setup
    # ------------------------------------------------------------------ #
    def _setup_window(self):
        """Set up the main window properties"""
        self.title("Ascendara Installer")
        self.resizable(False, False)
        self.overrideredirect(True)  # Frameless window
        self.configure(fg_color=self.colors["bg"])

        scaling = self._get_window_scaling()
        x = int((self.winfo_screenwidth() - WIDTH * scaling) // 2)
        y = int((self.winfo_screenheight() - HEIGHT * scaling) // 2)
        self.geometry(f"{WIDTH}x{HEIGHT}+{x}+{y}")
        logging.info(f"Window positioned at x={x}, y={y}")

        try:
            self.iconbitmap(theme.resource_path("ascendara.ico"))
        except Exception:
            pass

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)

    def _apply_native_styles(self):
        """Rounded corners and a taskbar entry for the frameless window."""
        theme.make_app_window(self)
        self.after(30, lambda: theme.round_corners(self))

    def _font(self, size, weight="normal"):
        if weight == "semibold":
            return ctk.CTkFont(family=self.font_semibold, size=size)
        return ctk.CTkFont(family=self.font, size=size, weight=weight)

    # ------------------------------------------------------------------ #
    # UI construction
    # ------------------------------------------------------------------ #
    def _create_ui(self):
        """Create the complete UI structure"""
        self._create_hero()

        self.panel = ctk.CTkFrame(self, fg_color=self.colors["bg"], corner_radius=0)
        self.panel.grid(row=0, column=1, sticky="nsew")

        self._create_title_bar()
        self._create_footer()
        self._create_progress_card()
        self._create_body()

    def _create_hero(self):
        """Branded gradient panel on the left"""
        self.hero_label = ctk.CTkLabel(self, text="", width=HERO_WIDTH, height=HEIGHT, corner_radius=0)
        self.hero_label.grid(row=0, column=0, sticky="nsw")
        self._render_hero()
        self._make_draggable(self.hero_label)

    def _render_hero(self):
        pil = theme.render_hero(
            HERO_WIDTH, HEIGHT,
            logo=self.logo_image,
            version_text=f"Installer v{version}",
            year=str(datetime.date.today().year),
        )
        self.hero_image = ctk.CTkImage(light_image=pil, dark_image=pil, size=(HERO_WIDTH, HEIGHT))
        self.hero_label.configure(image=self.hero_image)

    def _create_title_bar(self):
        """Window controls in the top-right; the whole strip is draggable"""
        self.title_bar = ctk.CTkFrame(self.panel, fg_color="transparent", height=40, corner_radius=0)
        self.title_bar.pack(fill="x")
        self.title_bar.pack_propagate(False)
        self._make_draggable(self.title_bar)

        self.close_button = self._caption_button("close", self.close, danger=True)
        self.close_button.pack(side="right")
        self.minimize_button = self._caption_button("minimize", lambda: theme.minimize(self))
        self.minimize_button.pack(side="right")

    def _caption_button(self, icon, command, danger=False):
        c = self.colors
        btn = ctk.CTkButton(
            self.title_bar,
            text=theme.glyph(icon),
            font=ctk.CTkFont(family=self.icon_font or self.font, size=10),
            width=46, height=40, corner_radius=0,
            fg_color="transparent",
            hover_color=c["close_hover"] if danger else c["surface_alt"],
            text_color=c["text_muted"],
            command=command,
        )
        if danger:
            btn.bind("<Enter>", lambda e: btn.configure(text_color="#FFFFFF"), add="+")
            btn.bind("<Leave>", lambda e: btn.configure(text_color=c["text_muted"]), add="+")
        return btn

    def _create_body(self):
        """Heading, description and the step list"""
        c = self.colors
        self.body = ctk.CTkFrame(self.panel, fg_color="transparent")
        self.body.pack(fill="both", expand=True, padx=44, pady=(4, 0))
        self._make_draggable(self.body)

        self.eyebrow = ctk.CTkLabel(
            self.body, text="STEP 1 OF 3", font=self._font(11, "semibold"),
            text_color=c["accent"], height=16,
        )
        self.eyebrow.pack(anchor="w")

        self.heading = ctk.CTkLabel(
            self.body, text="Getting things ready", font=self._font(26, "bold"),
            text_color=c["text"], anchor="w",
        )
        self.heading.pack(anchor="w", pady=(2, 0))

        self.subtitle = ctk.CTkLabel(
            self.body,
            text=self._subtitle_text(),
            font=self._font(13), text_color=c["text_muted"],
            justify="left", anchor="w", wraplength=460,
        )
        self.subtitle.pack(anchor="w", pady=(6, 0))

        # Steps
        self.steps_frame = ctk.CTkFrame(self.body, fg_color="transparent")
        self.steps_frame.pack(anchor="w", fill="x", pady=(26, 0))
        self.steps_frame.grid_columnconfigure(1, weight=1)

        self.step_icons, self.step_titles, self.step_captions, self.step_lines = [], [], [], []
        for i, (title, caption) in enumerate(STEPS):
            icon = ctk.CTkLabel(self.steps_frame, text="", width=24, height=24)
            icon.grid(row=i * 2, column=0, rowspan=1, sticky="n", pady=(2, 0))

            text_col = ctk.CTkFrame(self.steps_frame, fg_color="transparent")
            text_col.grid(row=i * 2, column=1, sticky="w", padx=(14, 0))
            t = ctk.CTkLabel(text_col, text=title, font=self._font(13, "semibold"),
                             text_color=c["text_subtle"], height=18, anchor="w")
            t.pack(anchor="w")
            cap = ctk.CTkLabel(text_col, text=caption, font=self._font(12),
                               text_color=c["text_subtle"], height=16, anchor="w")
            cap.pack(anchor="w")

            if i < len(STEPS) - 1:
                line = ctk.CTkFrame(self.steps_frame, width=2, height=14,
                                    fg_color=c["border"], corner_radius=1)
                line.grid(row=i * 2 + 1, column=0, pady=4)
                self.step_lines.append(line)

            self.step_icons.append(icon)
            self.step_titles.append(t)
            self.step_captions.append(cap)

        self._refresh_steps()

    def _create_progress_card(self):
        """Progress bar with status and percentage"""
        c = self.colors
        self.card = ctk.CTkFrame(
            self.panel, fg_color=c["surface"], corner_radius=14,
            border_width=1, border_color=c["border"],
        )
        self.card.pack(side="bottom", fill="x", padx=44, pady=(0, 6))

        top = ctk.CTkFrame(self.card, fg_color="transparent")
        top.pack(fill="x", padx=20, pady=(16, 0))

        self.status_label = ctk.CTkLabel(
            top, text="Preparing…", font=self._font(13, "semibold"),
            text_color=c["text"], anchor="w",
        )
        self.status_label.pack(side="left")

        self.percentage = ctk.CTkLabel(
            top, text="", font=self._font(13, "semibold"),
            text_color=c["text_muted"], anchor="e",
        )
        self.percentage.pack(side="right")

        self.progress_bar = ctk.CTkProgressBar(
            self.card, height=6, corner_radius=3,
            fg_color=c["surface_alt"], progress_color=c["accent"],
            mode="determinate", indeterminate_speed=0.8,
        )
        self.progress_bar.pack(fill="x", padx=20, pady=(12, 0))
        self.progress_bar.set(0)

        self.detail_label = ctk.CTkLabel(
            self.card, text="", font=self._font(12),
            text_color=c["text_subtle"], anchor="w", height=18,
        )
        self.detail_label.pack(fill="x", padx=20, pady=(8, 14))

    def _create_footer(self):
        """Log link on the left, actions on the right"""
        c = self.colors
        self.footer = ctk.CTkFrame(self.panel, fg_color="transparent", height=64)
        self.footer.pack(side="bottom", fill="x", padx=44, pady=(0, 10))
        self.footer.pack_propagate(False)

        self.log_button = ctk.CTkButton(
            self.footer,
            text="View logs",
            font=self._font(12),
            width=0, height=34, corner_radius=8,
            fg_color="transparent", hover_color=c["surface_alt"],
            text_color=c["text_muted"],
            command=self._show_logs,
        )
        self.log_button.pack(side="left", pady=15)

        self.primary_button = ctk.CTkButton(
            self.footer,
            text="Try again",
            font=self._font(13, "semibold"),
            width=110, height=36, corner_radius=10,
            fg_color=c["accent"], hover_color=c["accent_hover"],
            text_color="#FFFFFF",
            command=self._retry,
        )
        # Shown only after a failure

        self.secondary_button = ctk.CTkButton(
            self.footer,
            text="Cancel",
            font=self._font(13),
            width=96, height=36, corner_radius=10,
            fg_color=c["surface_alt"], hover_color=c["surface_hover"],
            text_color=c["text"],
            command=self.close,
        )
        self.secondary_button.pack(side="right", pady=14)

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    def _subtitle_text(self):
        ver = f"version {self.app_version}" if self.app_version else "the latest version"
        return (f"Installing {ver} of Ascendara on your computer. "
                "It will launch automatically once setup is complete.")

    def _make_draggable(self, widget):
        widget.bind("<Button-1>", self._start_window_move, add="+")
        widget.bind("<B1-Motion>", self._on_window_move, add="+")

    def _start_window_move(self, event):
        self.x = event.x_root - self.winfo_x()
        self.y = event.y_root - self.winfo_y()

    def _on_window_move(self, event):
        self.geometry(f"+{event.x_root - self.x}+{event.y_root - self.y}")

    def _schedule(self, key, ms, func):
        if self.closing:
            return
        try:
            self.after_ids[key] = self.after(ms, func)
        except Exception:
            pass

    def _post(self, func, *args):
        """Run func(*args) on the Tk thread (safe to call from any thread)."""
        self._ui_queue.put((func, args))

    def _poll_ui_queue(self):
        try:
            while True:
                func, args = self._ui_queue.get_nowait()
                try:
                    func(*args)
                except Exception as e:
                    logging.error(f"UI update failed: {e}")
        except queue.Empty:
            pass
        self._schedule("ui_queue", 30, self._poll_ui_queue)

    @staticmethod
    def _truncate(text, limit=64):
        return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"

    # ------------------------------------------------------------------ #
    # Remote assets (logo + version), loaded off the UI thread
    # ------------------------------------------------------------------ #
    def _load_remote_assets(self):
        def worker():
            # Logo: bundled copy first, then the repository
            logo = None
            local = theme.resource_path("readme", "icon.png")
            try:
                if os.path.exists(local):
                    logo = Image.open(local)
                    logo.load()
            except Exception as e:
                logging.warning(f"Could not load bundled logo: {e}")
            if logo is None:
                try:
                    r = requests.get(LOGO_URL, timeout=8)
                    if r.status_code == 200:
                        logo = Image.open(BytesIO(r.content))
                        logo.load()
                except Exception as e:
                    logging.error(f"Error loading logo: {e}")
            if logo is not None:
                self._post(self._set_logo, logo)

            try:
                r = requests.get(VERSION_URL, timeout=5)
                if r.status_code == 200:
                    self._post(self._set_app_version, r.json().get("appVer"))
            except Exception as e:
                logging.warning(f"Could not fetch app version: {e}")

        threading.Thread(target=worker, daemon=True).start()

    def _set_logo(self, logo):
        self.logo_image = logo
        self._render_hero()

    def _set_app_version(self, ver):
        if ver:
            self.app_version = ver
            self.subtitle.configure(text=self._subtitle_text())

    # ------------------------------------------------------------------ #
    # Steps & animation
    # ------------------------------------------------------------------ #
    def _set_step(self, index, state):
        self.step_states[index] = state
        self._refresh_steps()

    def _refresh_steps(self):
        c = self.colors
        active = None
        for i, state in enumerate(self.step_states):
            pil = theme.render_step_icon(state, c, frame=self.spinner_frame, frames=SPINNER_FRAMES)
            img = ctk.CTkImage(light_image=pil, dark_image=pil, size=(24, 24))
            self.step_icons[i].configure(image=img)
            self.step_icons[i]._img_ref = img

            if state == "pending":
                title_color, cap_color = c["text_subtle"], c["text_subtle"]
            elif state == "error":
                title_color, cap_color = c["error"], c["text_muted"]
            else:
                title_color, cap_color = c["text"], c["text_muted"]
            self.step_titles[i].configure(text_color=title_color)
            self.step_captions[i].configure(text_color=cap_color)

            if i < len(self.step_lines):
                self.step_lines[i].configure(fg_color=c["accent"] if state == "done" else c["border"])
            if state in ("active", "error") and active is None:
                active = i

        if active is not None:
            self.eyebrow.configure(text=f"STEP {active + 1} OF {len(STEPS)}")

    def _spinner_tick(self):
        """Advance the spinner on whichever step is active"""
        if "active" in self.step_states:
            self.spinner_frame = (self.spinner_frame + 1) % SPINNER_FRAMES
            c = self.colors
            for i, state in enumerate(self.step_states):
                if state == "active":
                    pil = theme.render_step_icon("active", c, frame=self.spinner_frame, frames=SPINNER_FRAMES)
                    img = ctk.CTkImage(light_image=pil, dark_image=pil, size=(24, 24))
                    self.step_icons[i].configure(image=img)
                    self.step_icons[i]._img_ref = img
        self._schedule("spinner", 70, self._spinner_tick)

    def _animate_progress(self):
        """Ease the bar towards the target value"""
        self.after_ids.pop("progress", None)
        if self.indeterminate:
            return
        diff = self.target_progress - self.shown_progress
        if abs(diff) < 0.002:
            self.shown_progress = self.target_progress
        else:
            self.shown_progress += diff * 0.18
        self.progress_bar.set(self.shown_progress)
        self.percentage.configure(text=f"{int(round(self.shown_progress * 100))}%")
        if self.shown_progress != self.target_progress:
            self._schedule("progress", 16, self._animate_progress)

    def _set_indeterminate(self, on):
        if on == self.indeterminate:
            return
        self.indeterminate = on
        if on:
            self.progress_bar.configure(mode="indeterminate")
            self.progress_bar.start()
            self.percentage.configure(text="")
        else:
            self.progress_bar.stop()
            self.progress_bar.configure(mode="determinate")
            self.progress_bar.set(self.shown_progress)

    # ------------------------------------------------------------------ #
    # Installer callbacks (called from the installer thread)
    # ------------------------------------------------------------------ #
    def update_progress(self, progress):
        self._post(self._apply_progress, progress)

    def _update_status(self, text):
        self._post(self._apply_status, text)

    def _on_installation_complete(self, success):
        self._post(self._apply_complete, success)

    # ------------------------------------------------------------------ #
    # UI updates (Tk thread)
    # ------------------------------------------------------------------ #
    def _apply_progress(self, progress):
        if progress is None:
            self._set_indeterminate(True)
            return
        value = float(progress)
        value = value / 100.0 if value > 1.0 else value
        value = min(max(value, 0.0), 1.0)

        self._set_indeterminate(False)
        if value < self.target_progress - 0.5:
            # A fresh download started (e.g. backup mirror)
            self.shown_progress = 0.0
        self.target_progress = value
        if "progress" not in self.after_ids:
            self._animate_progress()

    def _apply_status(self, text):
        logging.info(f"Status update: {text}")
        self.last_status = text
        lower = text.lower()

        if "running installer" in lower:
            self._set_step(0, "done")
            self._set_step(1, "active")
            self.heading.configure(text="Installing Ascendara")
            self.status_label.configure(text="Running setup…")
            self.detail_label.configure(text="Follow any prompts from the Ascendara setup window")
        elif lower.startswith("downloading"):
            self._set_step(0, "active")
            self.heading.configure(text="Downloading Ascendara")
            self.status_label.configure(text="Downloading…")
            self.detail_label.configure(text=self._truncate(text))
        elif "complete" in lower:
            self.detail_label.configure(text=self._truncate(text))
        else:
            self.detail_label.configure(text=self._truncate(text))

    def _apply_complete(self, success):
        c = self.colors
        self._set_indeterminate(False)
        if success:
            logging.info("Installation completed successfully")
            self._set_step(0, "done")
            self._set_step(1, "done")
            self._set_step(2, "active")
            self.target_progress = self.shown_progress = 1.0
            self.progress_bar.set(1.0)
            self.progress_bar.configure(progress_color=c["success"])
            self.percentage.configure(text="100%", text_color=c["success"])
            self.heading.configure(text="You're all set")
            self.subtitle.configure(text="Ascendara was installed successfully and is launching now. "
                                         "This window will close on its own.")
            self.status_label.configure(text="Installation complete")
            self.detail_label.configure(text="Launching Ascendara…")
            self.secondary_button.configure(text="Close")
            self._schedule("launch_done", 1200, lambda: self._set_step(2, "done"))
            self._schedule("auto_close", 2200, self.close)
        else:
            logging.error("Installation failed")
            failed = next((i for i, s in enumerate(self.step_states) if s == "active"), 0)
            self._set_step(failed, "error")
            self.progress_bar.configure(progress_color=c["error"])
            self.percentage.configure(text="", text_color=c["text_muted"])
            self.heading.configure(text="Installation failed")
            self.subtitle.configure(text="Something went wrong while installing Ascendara. "
                                         "Check your connection and try again, or open the logs for details.")
            self.status_label.configure(text="Couldn't finish setup")
            self.detail_label.configure(text=self._truncate(self.last_status or "See logs for details"))
            self.secondary_button.configure(text="Exit")
            self.primary_button.pack(side="right", padx=(10, 0), pady=14, before=self.secondary_button)

    # ------------------------------------------------------------------ #
    # Installation control
    # ------------------------------------------------------------------ #
    def on_fade_in_complete(self):
        logging.info("Fade in complete, starting installation")
        self._start_installation()

    def _start_installation(self):
        """Reset the UI and start the installer thread"""
        c = self.colors
        self.step_states = ["active", "pending", "pending"]
        self._refresh_steps()
        self.heading.configure(text="Getting things ready")
        self.subtitle.configure(text=self._subtitle_text())
        self.status_label.configure(text="Preparing…")
        self.detail_label.configure(text="Connecting to Ascendara servers")
        self.percentage.configure(text="", text_color=c["text_muted"])
        self.progress_bar.configure(progress_color=c["accent"])
        self.target_progress = self.shown_progress = 0.0
        self.progress_bar.set(0)
        self.primary_button.pack_forget()
        self.secondary_button.configure(text="Cancel")
        self._set_indeterminate(True)

        try:
            self.installer = InstallerProcess(
                progress_callback=self.update_progress,
                status_callback=self._update_status,
                completion_callback=self._on_installation_complete,
            )
            self.installer.start()
            logging.info("Installation process started")
        except Exception as e:
            logging.error(f"Failed to start installation: {e}")
            self.last_status = str(e)
            self._apply_complete(False)

    def _retry(self):
        logging.info("Retrying installation")
        self._set_indeterminate(False)
        self._start_installation()

    # ------------------------------------------------------------------ #
    # Logs
    # ------------------------------------------------------------------ #
    def _show_logs(self):
        """Show the log window"""
        logging.info("Opening log window...")
        try:
            if self.log_window is None or not self.log_window.winfo_exists():
                from ui.log_window import LogWindow
                self.log_window = LogWindow(colors=self.colors, dark=windows_dark_mode)
                # Centre it over the installer
                s = self._get_window_scaling()
                lx = int(self.winfo_x() + (WIDTH * s - 820 * s) / 2)
                ly = int(self.winfo_y() + (HEIGHT * s - 520 * s) / 2)
                self.log_window.geometry(f"+{max(lx, 0)}+{max(ly, 0)}")
            win = self.log_window
            win.deiconify()
            # CTkToplevel can lose focus to the parent right after creation,
            # so raise it again once it has been mapped.
            for delay in (0, 150):
                win.after(delay, lambda: win.winfo_exists() and (win.lift(), win.focus_force()))
        except Exception as e:
            logging.error(f"Error showing log window: {e}")
            self.log_window = None

    # ------------------------------------------------------------------ #
    # Fade / close
    # ------------------------------------------------------------------ #
    def fade_in(self, current_alpha=0.0, completion_callback=None):
        """Fade in the window gradually"""
        if current_alpha < 1.0:
            current_alpha = min(current_alpha + 0.08, 1.0)
            self.attributes("-alpha", current_alpha)
            self.after(16, lambda: self.fade_in(current_alpha, completion_callback))
        elif completion_callback:
            completion_callback()

    def close(self):
        """Close the application with a fade"""
        if self.closing:
            return
        self.closing = True

        if self.log_window is not None:
            try:
                if self.log_window.winfo_exists():
                    self.log_window._on_close()
            except Exception as e:
                logging.error(f"Error closing log window: {e}")

        for after_id in list(self.after_ids.values()):
            try:
                self.after_cancel(after_id)
            except Exception:
                pass
        self.after_ids.clear()
        try:
            self.progress_bar.stop()
        except Exception:
            pass
        self._fade_out()

    def _fade_out(self, current_alpha=1.0):
        if current_alpha > 0:
            current_alpha = max(current_alpha - 0.1, 0)
            self.attributes("-alpha", current_alpha)
            self.after(16, lambda: self._fade_out(current_alpha))
        else:
            self.destroy()
