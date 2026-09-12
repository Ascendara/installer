# log_window.py
import customtkinter as ctk
import tkinter as tk
from utils.logging import log_stream
import logging

class LogWindow(ctk.CTkToplevel):
    """Log window to display application logs"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Configure window
        self.title("Ascendara Installer Logs")
        self.geometry("800x500")
        self.minsize(700, 400)
        
        # Set colors
        self.colors = {
            "bg_primary": "#F5F0FF",
            "bg_secondary": "#EBE4FF", 
            "text_primary": "#6A3CB5",
            "accent": "#8A6BF0",
            "border": "#D8C9FF"
        }
        
        # Configure appearance
        self.configure(fg_color=self.colors["bg_primary"])
        
        # Create UI
        self._create_ui()
        
        # Update logs initially
        self._update_logs()
        
        # Set up auto-update
        self._schedule_update()
        
        # Log window creation
        logging.info("Log window created")
    
    def _create_ui(self):
        """Create the UI elements"""
        # Main frame
        self.main_frame = ctk.CTkFrame(
            self,
            fg_color=self.colors["bg_primary"],
            corner_radius=0
        )
        self.main_frame.pack(fill="both", expand=True, padx=15, pady=15)
        
        # Title
        self.title_label = ctk.CTkLabel(
            self.main_frame,
            text="Installation Logs",
            font=ctk.CTkFont(family="Segoe UI", size=16, weight="bold"),
            text_color=self.colors["text_primary"]
        )
        self.title_label.pack(pady=(0, 10))
        
        # Log text widget
        self.log_text = ctk.CTkTextbox(
            self.main_frame,
            font=ctk.CTkFont(family="Consolas", size=12),
            fg_color=self.colors["bg_secondary"],
            text_color=self.colors["text_primary"],
            border_width=1,
            border_color=self.colors["border"],
            corner_radius=8,
            wrap="none"
        )
        self.log_text.pack(fill="both", expand=True)
        
        # Button frame
        self.button_frame = ctk.CTkFrame(
            self.main_frame,
            fg_color="transparent"
        )
        self.button_frame.pack(fill="x", pady=(10, 0))
        
        # Copy button
        self.copy_button = ctk.CTkButton(
            self.button_frame,
            text="Copy Logs",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            height=32,
            corner_radius=5,
            fg_color=self.colors["accent"],
            text_color="#FFFFFF",
            command=self._copy_logs
        )
        self.copy_button.pack(side="left", padx=(0, 10))
        
        # Clear button
        self.clear_button = ctk.CTkButton(
            self.button_frame,
            text="Clear Logs",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            height=32,
            corner_radius=5,
            fg_color=self.colors["accent"],
            text_color="#FFFFFF",
            command=self._clear_logs
        )
        self.clear_button.pack(side="left")
        
        # Status label
        self.status_label = ctk.CTkLabel(
            self.button_frame,
            text="",
            font=ctk.CTkFont(family="Segoe UI", size=10),
            text_color=self.colors["text_primary"]
        )
        self.status_label.pack(side="right")
        
        # Set up protocol for window close
        self.protocol("WM_DELETE_WINDOW", self._on_close)
    
    def _update_logs(self):
        """Update log content"""
        try:
            # Get log content
            log_content = log_stream.getvalue()
            
            # Update text widget
            self.log_text.delete(1.0, "end")
            self.log_text.insert("1.0", log_content)
            
            # Scroll to end
            self.log_text.see("end")
            
            # Update status
            line_count = log_content.count('\n') + 1 if log_content else 0
            self.status_label.configure(text=f"{line_count} lines")
        except Exception as e:
            print(f"Error updating logs: {e}")
    
    def _schedule_update(self):
        """Schedule the next log update"""
        self.after_id = self.after(1000, self._update_callback)
    
    def _update_callback(self):
        """Callback for updating logs"""
        self._update_logs()
        self._schedule_update()
    
    def _copy_logs(self):
        """Copy logs to clipboard"""
        log_content = self.log_text.get(1.0, "end-1c")
        self.clipboard_clear()
        self.clipboard_append(log_content)
        
        # Show confirmation
        self.status_label.configure(text="Logs copied to clipboard")
        line_count = log_content.count("\n") + 1 if log_content else 0
        self.after(3000, lambda: self.status_label.configure(
            text=f"{line_count} lines"
        ))
    
    def _clear_logs(self):
        """Clear log content"""
        # Clear the StringIO object
        log_stream.seek(0)
        log_stream.truncate(0)
        
        # Update the display
        self.log_text.delete(1.0, "end")
        self.status_label.configure(text="Logs cleared")
        self.after(3000, lambda: self.status_label.configure(text="0 lines"))
    
    def _on_close(self):
        """Handle window close event"""
        # Cancel the scheduled update
        if hasattr(self, 'after_id'):
            self.after_cancel(self.after_id)
        
        # Destroy the window
        self.destroy()
        logging.info("Log window closed")