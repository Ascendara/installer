# log_window.py
import os
import re
import logging
import customtkinter as ctk
from utils.logging import log_stream
from ui import theme

LEVEL_RE = re.compile(r"^(\d{2}:\d{2}:\d{2}) - (\w+) - ")


class LogWindow(ctk.CTkToplevel):
    """Log window to display application logs"""

    def __init__(self, *args, colors=None, dark=None, **kwargs):
        super().__init__(*args, **kwargs)

        if dark is None:
            dark = ctk.get_appearance_mode() == "Dark"
        self.dark = dark
        self.colors = colors or (theme.DARK if dark else theme.LIGHT)
        self.font = theme.ui_font()
        self.font_semibold = theme.ui_font_semibold()
        self._last_content = None

        self.title("Ascendara Installer Logs")
        self.geometry("820x520")
        self.minsize(640, 380)
        self.configure(fg_color=self.colors["bg"])
        try:
            self.after(250, lambda: self.iconbitmap(theme.resource_path("ascendara.ico")))
        except Exception:
            pass
        self.after(10, lambda: theme.dark_title_bar(self, self.dark))

        self._create_ui()
        self._update_logs()
        self._schedule_update()
        logging.info("Log window created")

    def _font(self, size, semibold=False):
        return ctk.CTkFont(family=self.font_semibold if semibold else self.font, size=size)

    def _create_ui(self):
        c = self.colors
        self.main_frame = ctk.CTkFrame(self, fg_color="transparent", corner_radius=0)
        self.main_frame.pack(fill="both", expand=True, padx=20, pady=(16, 20))

        # Header
        header = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        header.pack(fill="x", pady=(0, 12))

        title_col = ctk.CTkFrame(header, fg_color="transparent")
        title_col.pack(side="left")
        ctk.CTkLabel(title_col, text="Installer logs", font=ctk.CTkFont(family=self.font, size=18, weight="bold"),
                     text_color=c["text"], height=24, anchor="w").pack(anchor="w")
        ctk.CTkLabel(title_col, text="Live output from this setup session", font=self._font(12),
                     text_color=c["text_muted"], height=16, anchor="w").pack(anchor="w")

        self.count_chip = ctk.CTkLabel(
            header, text="0 lines", font=self._font(11, True),
            fg_color=c["accent_soft"], text_color=c["accent"],
            corner_radius=10, height=22, padx=10,
        )
        self.count_chip.pack(side="right", anchor="n", pady=(2, 0))

        # Log text
        self.log_text = ctk.CTkTextbox(
            self.main_frame,
            font=ctk.CTkFont(family="Consolas", size=12),
            fg_color=c["surface"],
            text_color=c["log_info"],
            border_width=1,
            border_color=c["border"],
            corner_radius=12,
            wrap="none",
            scrollbar_button_color=c["surface_alt"],
            scrollbar_button_hover_color=c["surface_hover"],
        )
        self.log_text.pack(fill="both", expand=True)
        self.log_text.tag_config("time", foreground=c["log_time"])
        self.log_text.tag_config("warn", foreground=c["log_warn"])
        self.log_text.tag_config("error", foreground=c["log_error"])
        self.log_text.configure(state="disabled")

        # Footer
        footer = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        footer.pack(fill="x", pady=(14, 0))

        self.copy_button = ctk.CTkButton(
            footer, text="Copy logs", font=self._font(12, True),
            height=34, width=104, corner_radius=9,
            fg_color=c["accent"], hover_color=c["accent_hover"], text_color="#FFFFFF",
            command=self._copy_logs,
        )
        self.copy_button.pack(side="left", padx=(0, 8))

        self.folder_button = ctk.CTkButton(
            footer, text="Open log folder", font=self._font(12),
            height=34, width=126, corner_radius=9,
            fg_color=c["surface_alt"], hover_color=c["surface_hover"], text_color=c["text"],
            command=self._open_folder,
        )
        self.folder_button.pack(side="left", padx=(0, 8))

        self.clear_button = ctk.CTkButton(
            footer, text="Clear", font=self._font(12),
            height=34, width=72, corner_radius=9,
            fg_color="transparent", hover_color=c["surface_alt"], text_color=c["text_muted"],
            command=self._clear_logs,
        )
        self.clear_button.pack(side="left")

        self.status_label = ctk.CTkLabel(
            footer, text="", font=self._font(12), text_color=c["text_muted"],
        )
        self.status_label.pack(side="right")

        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _update_logs(self):
        """Refresh the log view when new output arrives"""
        try:
            content = log_stream.getvalue()
            if content == self._last_content:
                return
            self._last_content = content

            # Only auto-scroll if the user is already at the bottom
            at_bottom = self.log_text.yview()[1] >= 0.999

            self.log_text.configure(state="normal")
            self.log_text.delete("1.0", "end")
            level = None
            for line in content.splitlines():
                m = LEVEL_RE.match(line)
                if m:
                    level = m.group(2)
                    tag = "error" if level in ("ERROR", "CRITICAL") else "warn" if level == "WARNING" else None
                    self.log_text.insert("end", m.group(1) + "  ", "time")
                    self.log_text.insert("end", line[m.end():] + "\n", tag)
                else:
                    # Continuation lines (tracebacks) inherit the previous level's colour
                    tag = "error" if level in ("ERROR", "CRITICAL") else None
                    self.log_text.insert("end", line + "\n", tag)
            self.log_text.configure(state="disabled")
            if at_bottom:
                self.log_text.see("end")

            line_count = len(content.splitlines())
            self.count_chip.configure(text=f"{line_count} line{'s' if line_count != 1 else ''}")
        except Exception as e:
            print(f"Error updating logs: {e}")

    def _schedule_update(self):
        self.after_id = self.after(1000, self._update_callback)

    def _update_callback(self):
        self._update_logs()
        self._schedule_update()

    def _flash_status(self, text):
        self.status_label.configure(text=text)
        if getattr(self, "_status_after", None):
            self.after_cancel(self._status_after)
        self._status_after = self.after(2500, lambda: self.status_label.configure(text=""))

    def _copy_logs(self):
        self.clipboard_clear()
        self.clipboard_append(log_stream.getvalue())
        self._flash_status("Copied to clipboard")

    def _open_folder(self):
        try:
            base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
            path = os.path.join(base, "Ascendara", "InstallerLogs")
            os.makedirs(path, exist_ok=True)
            os.startfile(path)
        except Exception as e:
            logging.error(f"Could not open log folder: {e}")
            self._flash_status("Couldn't open folder")

    def _clear_logs(self):
        log_stream.seek(0)
        log_stream.truncate(0)
        self._update_logs()
        self._flash_status("Logs cleared")

    def _on_close(self):
        if hasattr(self, "after_id"):
            self.after_cancel(self.after_id)
        if getattr(self, "_status_after", None):
            try:
                self.after_cancel(self._status_after)
            except Exception:
                pass
        self.destroy()
        logging.info("Log window closed")
