# main_window.py
import os
import logging
import threading
import time
import requests
from io import BytesIO
from PIL import Image
import customtkinter as ctk
from core.installer import InstallerProcess
from core.version import version

# Windows dark mode detection helper
def is_windows_dark_mode():
    try:
        import winreg
        registry = winreg.ConnectRegistry(None, winreg.HKEY_CURRENT_USER)
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
        key = winreg.OpenKey(registry, key_path)
        # Value 1 means light mode, 0 means dark mode
        apps_use_light_theme, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
        winreg.CloseKey(key)
        return apps_use_light_theme == 0
    except Exception as e:
        logging.warning(f"Could not detect Windows dark mode: {e}")
        return False
        

# Detect Windows dark mode once before initializing CTk
windows_dark_mode = is_windows_dark_mode()
logging.info(f"Windows dark mode detected: {windows_dark_mode}")

if windows_dark_mode:
    ctk.set_appearance_mode("dark")
else:
    ctk.set_appearance_mode("light")

# Set default color theme
ctk.set_default_color_theme("blue")

class AscendaraInstaller(ctk.CTk):
    def __init__(self):
        """Initialize the main application window"""
        super().__init__()
    
        logging.info("Initializing main window")
            
        # Set up colors for light theme
        self.light_colors = {
            "bg_primary": "#F5F0FF",
            "bg_secondary": "#EBE4FF",
            "bg_tertiary": "#E0D6FF",
            "text_primary": "#6A3CB5",
            "text_secondary": "#8A6BF0",
            "accent": "#8A6BF0",
            "accent_hover": "#7A5BE0",
            "success": "#4CAF50",
            "error": "#F44336"
        }

        self.dark_colors = {
            "bg_primary": "#1E1E2F",
            "bg_secondary": "#2C2C3E",
            "bg_tertiary": "#3A3A4E",
            "text_primary": "#C0C0FF",
            "text_secondary": "#A0A0F0",
            "accent": "#8A6BF0",
            "accent_hover": "#7A5BE0",
            "success": "#4CAF50",
            "error": "#F44336"
        }

        self.colors = self.light_colors if not windows_dark_mode else self.dark_colors

        
        # Set up animation properties
        self.frame_time = 1.0 / 60.0  # Target 60 FPS
        self.animation_running = False
        
        # Initialize log window reference
        self.log_window = None
        
        # Initialize installer reference
        self.installer = None
        
        # Track after callbacks
        self.after_ids = {}
        
        # Initialize variables
        self.x = 0
        self.y = 0
        self._indeterminate_active = False
        
        # Configure window
        logging.info("Setting up window...")
        self._setup_window()
        
        # Create UI elements
        self._create_ui()
        
        logging.info(f"Installer Version {version}")
        
        # Start animation loop
        self._start_animation_loop()
        
        # Fade in the window
        self.attributes('-alpha', 0.0)
        self.fade_in(completion_callback=self.on_fade_in_complete)
        
    def _setup_window(self):
        """Set up the main window properties"""
        logging.info("Configuring window properties...")
        self.title("Ascendara Installer")
        self.geometry("850x550")
        self.resizable(False, False)
        self.overrideredirect(True)  # Frameless window
        
        # Center window on screen
        x = (self.winfo_screenwidth() - 850) // 2
        y = (self.winfo_screenheight() - 550) // 2
        self.geometry(f"850x550+{x}+{y}")
        logging.info(f"Window positioned at x={x}, y={y}")
        
        # Configure grid
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)
        
    def _create_ui(self):
        """Create the complete UI structure"""
        # Create main container
        self.main_frame = ctk.CTkFrame(
            self, 
            fg_color=self.colors["bg_primary"],
            corner_radius=0
        )
        self.main_frame.grid(row=0, column=0, sticky="nsew")
        
        # Create title bar
        self._create_title_bar()
        
        # Create content area
        self._create_content_area()
        
        # Create status bar
        self._create_status_bar()
    
    def _create_title_bar(self):
        """Create a custom title bar"""
        # Title bar container
        self.title_bar = ctk.CTkFrame(
            self.main_frame,
            fg_color=self.colors["bg_secondary"],
            height=40,
            corner_radius=0
        )
        self.title_bar.pack(fill="x")
        
        # Make the title bar draggable
        self.title_bar.bind("<Button-1>", self._start_window_move)
        self.title_bar.bind("<B1-Motion>", self._on_window_move)
        
        # Title
        self.window_title = ctk.CTkLabel(
            self.title_bar,
            text="Ascendara Installer",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            text_color=self.colors["text_primary"]
        )
        self.window_title.pack(side="left", padx=15, pady=10)
        
        # Window controls container
        self.controls_frame = ctk.CTkFrame(
            self.title_bar,
            fg_color="transparent"
        )
        self.controls_frame.pack(side="right", padx=10)
        
        # Log button
        self.log_button = ctk.CTkButton(
            self.controls_frame,
            text="📋",
            font=ctk.CTkFont(size=13),
            width=35,
            height=28,
            corner_radius=5,
            fg_color=self.colors["bg_tertiary"],
            hover_color=self.colors["accent"],
            text_color=self.colors["text_primary"],
            command=self._show_logs
        )
        self.log_button.pack(side="left", padx=5, pady=6)
        
        # Minimize button
        self.minimize_button = ctk.CTkButton(
            self.controls_frame,
            text="−",
            font=ctk.CTkFont(size=13),
            width=35,
            height=28,
            corner_radius=5,
            fg_color=self.colors["bg_tertiary"],
            hover_color=self.colors["accent"],
            text_color=self.colors["text_primary"],
            command=self.iconify
        )
        self.minimize_button.pack(side="left", padx=5, pady=6)
        
        # Close button
        self.close_button = ctk.CTkButton(
            self.controls_frame,
            text="×",
            font=ctk.CTkFont(size=13),
            width=35,
            height=28,
            corner_radius=5,
            fg_color="#F44336",
            hover_color="#D32F2F",
            text_color="#FFFFFF",
            command=self.close
        )
        self.close_button.pack(side="left", padx=5, pady=6)
    
    def _create_content_area(self):
        """Create the main content area"""
        # Content container
        self.content_area = ctk.CTkFrame(
            self.main_frame,
            fg_color=self.colors["bg_primary"],
            corner_radius=0
        )
        self.content_area.pack(fill="both", expand=True)
        
        # Create logo section
        self._create_logo_section()
        
        # Welcome section
        self._create_welcome_section()
        
        # Progress section
        self._create_progress_section()
        
        # Install button
        self.install_button = ctk.CTkButton(
            self.content_area,
            text="Install",
            font=ctk.CTkFont(family="Segoe UI", size=16, weight="bold"),
            width=150,
            height=40,
            corner_radius=10,
            fg_color=self.colors["accent"],
            hover_color=self.colors["accent_hover"],
            text_color="#FFFFFF",
            command=self._on_install_click
        )
        self.install_button.pack(pady=(20, 0))
        
        # Exit button
        self.exit_button = ctk.CTkButton(
            self.content_area,
            text="Exit",
            font=ctk.CTkFont(family="Segoe UI", size=16, weight="bold"),
            width=150,
            height=40,
            corner_radius=10,
            fg_color=self.colors["bg_secondary"],
            hover_color=self.colors["bg_tertiary"],
            text_color=self.colors["text_primary"],
            command=self.close
        )
        self.exit_button.pack(pady=(10, 0))
    
    def _create_logo_section(self):
        """Create the logo section in the center top"""
        # Logo container
        self.logo_frame = ctk.CTkFrame(
            self.content_area,
            fg_color="transparent",
            height=150
        )
        self.logo_frame.pack(fill="x", pady=(30, 0))
        
        # Try to load logo from URL
        try:
            logo_url = "https://raw.githubusercontent.com/Ascendara/ascendara/refs/heads/main/src/public/icon.png"
            response = requests.get(logo_url)
            if response.status_code == 200:
                logo_image = Image.open(BytesIO(response.content))
                logo_image = logo_image.resize((100, 100), Image.Resampling.LANCZOS)
                self.logo_photo = ctk.CTkImage(light_image=logo_image, dark_image=logo_image, size=(100, 100))
                
                self.logo_label = ctk.CTkLabel(
                    self.logo_frame,
                    text="",
                    image=self.logo_photo
                )
                self.logo_label.pack(pady=10)
            else:
                self._create_fallback_logo()
        except Exception as e:
            logging.error(f"Error loading logo: {e}")
            self._create_fallback_logo()
    
    def _create_fallback_logo(self):
        """Create a fallback logo when image loading fails"""
        # Outer circle
        self.logo_outer = self._create_circle_image(100, self.colors["accent"])
        
        # Create label with the image
        self.logo_label = ctk.CTkLabel(
            self.logo_frame,
            text="A",
            font=ctk.CTkFont(family="Segoe UI", size=40, weight="bold"),
            text_color=self.colors["text_primary"],
            image=self.logo_outer,
            compound="center"
        )
        self.logo_label.pack(pady=10)
    
    def _create_welcome_section(self):
        """Create the welcome/header section"""
        # Welcome container
        self.welcome_frame = ctk.CTkFrame(
            self.content_area,
            fg_color="transparent"
        )
        self.welcome_frame.pack(fill="x", padx=60, pady=(10, 20))
        
        # Main title
        self.main_title = ctk.CTkLabel(
            self.welcome_frame,
            text="Welcome to Ascendara",
            font=ctk.CTkFont(family="Segoe UI", size=32, weight="bold"),
            text_color=self.colors["text_primary"]
        )
        self.main_title.pack(anchor="center")
        
        # Subtitle
        try:
            response = requests.get("https://api.ascendara.app/")
            if response.status_code == 200:
                data = response.json()
                app_ver = data["appVer"]
                subtitle_text = f"Installing version {app_ver} on your computer"
            else:
                subtitle_text = "Installing the latest version on your computer"
        except:
            subtitle_text = "Installing the latest version on your computer"
        
        self.subtitle = ctk.CTkLabel(
            self.welcome_frame,
            text=subtitle_text,
            font=ctk.CTkFont(family="Segoe UI", size=16),
            text_color=self.colors["text_secondary"]
        )
        self.subtitle.pack(anchor="center", pady=(5, 0))
        
        # Description
        self.description = ctk.CTkLabel(
            self.welcome_frame,
            text="This process will take just a moment.\nThe application will launch automatically when installation is complete.",
            font=ctk.CTkFont(family="Segoe UI", size=14),
            text_color=self.colors["text_secondary"],
            justify="center"
        )
        self.description.pack(anchor="center", pady=(10, 0))
    
    def _create_progress_section(self):
        """Create the installation progress section"""
        # Progress container
        self.progress_frame = ctk.CTkFrame(
            self.content_area,
            fg_color=self.colors["bg_secondary"],
            corner_radius=15
        )
        self.progress_frame.pack(fill="x", padx=60, pady=20)
        
        # Progress header
        self.progress_header = ctk.CTkFrame(
            self.progress_frame,
            fg_color="transparent"
        )
        self.progress_header.pack(fill="x", padx=20, pady=(20, 10))
        
        # Progress title
        self.progress_title = ctk.CTkLabel(
            self.progress_header,
            text="Installation Progress",
            font=ctk.CTkFont(family="Segoe UI", size=18, weight="bold"),
            text_color=self.colors["text_primary"]
        )
        self.progress_title.pack(side="left")
        
        # Status label
        self.status_label = ctk.CTkLabel(
            self.progress_header,
            text="Preparing...",
            font=ctk.CTkFont(family="Segoe UI", size=14),
            text_color=self.colors["text_secondary"]
        )
        self.status_label.pack(side="right")
        
        # Progress bar container
        self.progress_bar_frame = ctk.CTkFrame(
            self.progress_frame,
            fg_color="transparent"
        )
        self.progress_bar_frame.pack(fill="x", padx=20, pady=(10, 20))
        
        # Progress bar
        self.progress_bar = ctk.CTkProgressBar(
            self.progress_bar_frame,
            width=600,
            height=15,
            corner_radius=7,
            fg_color=self.colors["bg_primary"],
            progress_color=self.colors["accent"],
            mode="determinate"
        )
        self.progress_bar.pack(fill="x", pady=5)
        self.progress_bar.set(0)
        
        # Progress details
        self.progress_details_frame = ctk.CTkFrame(
            self.progress_frame,
            fg_color="transparent"
        )
        self.progress_details_frame.pack(fill="x", padx=20, pady=(0, 20))
        
        # Current task
        self.current_task = ctk.CTkLabel(
            self.progress_details_frame,
            text="",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color=self.colors["text_secondary"]
        )
        self.current_task.pack(side="left")
        
        # Percentage
        self.percentage = ctk.CTkLabel(
            self.progress_details_frame,
            text="0%",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            text_color=self.colors["text_primary"]
        )
        self.percentage.pack(side="right")
    
    def _create_status_bar(self):
        """Create the status bar at the bottom"""
        # Status bar container
        self.status_bar = ctk.CTkFrame(
            self.main_frame,
            fg_color=self.colors["bg_secondary"],
            height=25,
            corner_radius=0
        )
        self.status_bar.pack(side="bottom", fill="x")
        
        # Status text
        self.status_text = ctk.CTkLabel(
            self.status_bar,
            text="Ready to install",
            font=ctk.CTkFont(family="Segoe UI", size=10),
            text_color=self.colors["text_secondary"]
        )
        self.status_text.pack(side="left", padx=10, pady=2)
        
        # Copyright
        self.copyright = ctk.CTkLabel(
            self.status_bar,
            text=" 2025 Ascendara",
            font=ctk.CTkFont(family="Segoe UI", size=10),
            text_color=self.colors["text_secondary"]
        )
        self.copyright.pack(side="right", padx=10, pady=2)
    
    def _start_animation_loop(self):
        """Start a high-performance animation loop running at 60 FPS"""
        self.animation_running = True
        animation_thread = threading.Thread(target=self._animation_loop)
        animation_thread.daemon = True
        animation_thread.start()
        logging.info("Animation loop started")
    
    def _animation_loop(self):
        """Main animation loop that runs at 60 FPS"""
        while self.animation_running:
            start_time = time.time()
            
            # Update UI on the main thread
            self.after(0, self._update_animation_frame)
            
            # Calculate time to sleep to maintain FPS
            elapsed = time.time() - start_time
            sleep_time = max(0, self.frame_time - elapsed)
            time.sleep(sleep_time)
    
    def _update_animation_frame(self):
        """Update a single frame of animation"""
        if hasattr(self, 'progress_bar') and self.progress_bar.cget("mode") == "indeterminate":
            # Only update the indeterminate progress if it's actually in that mode
            # This prevents conflicts with determinate progress updates
            if not hasattr(self, '_indeterminate_active') or self._indeterminate_active:
                # Get the current progress value
                current = self.progress_bar.get()
                
                # Create a smooth back-and-forth animation
                new_value = (current + 0.02) % 1.0
                self.progress_bar.set(new_value)
    
    def _create_circle_image(self, size, color):
        """Create a circular image of specified size and color"""
        # Create a blank image with alpha channel
        image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        
        # Get a drawing context
        from PIL import ImageDraw
        draw = ImageDraw.Draw(image)
        
        # Draw a filled circle
        draw.ellipse((0, 0, size, size), fill=color)
        
        # Convert to CTkImage
        return ctk.CTkImage(light_image=image, dark_image=image, size=(size, size))
    
    def _start_window_move(self, event):
        """Start window dragging"""
        self.x = event.x
        self.y = event.y
    
    def _on_window_move(self, event):
        """Handle window dragging"""
        deltax = event.x - self.x
        deltay = event.y - self.y
        x = self.winfo_x() + deltax
        y = self.winfo_y() + deltay
        self.geometry(f"+{x}+{y}")
    
    def _show_logs(self):
        """Show the log window"""
        import logging
        logging.info("Opening log window...")
        
        try:
            # Check if log window exists and is still valid
            if self.log_window is None or not self.log_window.winfo_exists():
                # Import here to avoid circular imports
                from ui.log_window import LogWindow
                logging.info("Creating new log window")
                self.log_window = LogWindow()
                self.log_window.focus_force()  # Bring to front
                logging.info("Log window created successfully")
            else:
                # If window exists, just bring it to front
                logging.info("Focusing existing log window")
                self.log_window.focus_force()
                logging.info("Log window focused")
        except Exception as e:
            logging.error(f"Error showing log window: {e}")
            # Reset log window reference and try again
            self.log_window = None
            try:
                from ui.log_window import LogWindow
                logging.info("Retrying log window creation after error")
                self.log_window = LogWindow()
                logging.info("Log window created successfully on retry")
            except Exception as e2:
                logging.error(f"Failed to create log window on retry: {e2}")
    
    def on_fade_in_complete(self):
        """Called when fade in is complete"""
        logging.info("Fade in complete, starting installation")
        self._start_installation()
    
    def _start_installation(self):
        """Start the installation process"""
        # Update status
        self._update_status("Starting installation...")
        
        # Set progress bar to indeterminate mode
        self.progress_bar.configure(mode="indeterminate")
        self.progress_bar.start()
        self._indeterminate_active = True
        
        # Start the installer process
        installer = InstallerProcess(
            progress_callback=self.update_progress,
            status_callback=self._update_status,
            completion_callback=self._on_installation_complete
        )
        installer.start()
    
    def fade_in(self, current_alpha=0.0, completion_callback=None):
        """Fade in the window gradually"""
        if current_alpha < 1.0:
            current_alpha += 0.05
            self.attributes('-alpha', current_alpha)
            self.after(20, lambda: self.fade_in(current_alpha, completion_callback))
            logging.info(f"Fading in window: {current_alpha:.2f}")
        elif completion_callback:
            completion_callback()
    
    def fade_out(self, current_alpha=1.0, on_complete=None):
        """Fade out the window gradually"""
        if current_alpha > 0:
            current_alpha -= 0.05
            self.attributes('-alpha', current_alpha)
            self.after(20, lambda: self.fade_out(current_alpha, on_complete))
        elif on_complete:
            on_complete()
    
    def close(self):
        """Close the application with fade effect"""
        # Close log window if open
        if self.log_window is not None and hasattr(self.log_window, 'winfo_exists') and self.log_window.winfo_exists():
            try:
                self.log_window._on_close()
            except Exception as e:
                import logging
                logging.error(f"Error closing log window: {e}")
        
        # Cancel any pending after callbacks
        for widget_id, after_id in list(self.after_ids.items()):
            try:
                self.after_cancel(after_id)
            except Exception:
                pass
        self.after_ids.clear()
        
        # Start fade out
        self._fade_out()
    
    def _fade_out(self, current_alpha=1.0):
        """Fade out the window gradually"""
        if current_alpha > 0:
            current_alpha -= 0.05
            self.attributes('-alpha', current_alpha)
            after_id = self.after(20, lambda: self._fade_out(current_alpha))
            self.after_ids['fade_out'] = after_id
        else:
            self.destroy()
    
    def update_progress(self, progress):
        """Update the installation progress"""
        if progress is None:
            # If progress is None, we're in indeterminate mode
            if self.progress_bar.cget("mode") != "indeterminate":
                self.progress_bar.configure(mode="indeterminate")
                self.progress_bar.start()
                self._indeterminate_active = True
            return
        
        # If we were in indeterminate mode, switch to determinate
        if self.progress_bar.cget("mode") == "indeterminate":
            self._indeterminate_active = False
            self.progress_bar.stop()
            self.progress_bar.configure(mode="determinate")
            # Small delay to ensure the transition is smooth
            self.after(50, lambda: self._update_determinate_progress(progress))
        else:
            self._update_determinate_progress(progress)
    
    def _update_determinate_progress(self, progress):
        """Update progress in determinate mode"""
        # Ensure progress is between 0 and 1
        # The downloader sends progress as a percentage (0-100)
        # We need to normalize it to 0-1 for the progress bar
        if progress > 1.0:
            normalized_progress = min(max(float(progress) / 100.0, 0.0), 1.0)
        else:
            normalized_progress = min(max(float(progress), 0.0), 1.0)
        
        # Update progress bar
        self.progress_bar.set(normalized_progress)
        
        # Update percentage text (0-100%)
        percentage_text = f"{int(normalized_progress * 100)}%"
        self.percentage.configure(text=percentage_text)
        
        # Update task text based on progress
        if normalized_progress < 0.3:
            self.current_task.configure(text="Downloading components...")
        elif normalized_progress < 0.6:
            self.current_task.configure(text="Extracting files...")
        elif normalized_progress < 0.9:
            self.current_task.configure(text="Configuring application...")
        else:
            self.current_task.configure(text="Finalizing installation...")
    
    def _update_status(self, text):
        """Update the status text"""
        self.status_label.configure(text=text)
        self.status_text.configure(text=text)
    
    def _on_installation_complete(self, success):
        """Handle installation completion"""
        if success:
            self.status_label.configure(text="Installation Complete!")
            self.status_text.configure(text="Installation complete - Launching application...")
            self.current_task.configure(text="Installation completed successfully")
            self.progress_bar.configure(progress_color=self.colors["success"])
            # Close after a delay
            self.after(2000, self.close)
        else:
            self.status_label.configure(text="Installation Failed")
            self.status_text.configure(text="Installation failed - See logs for details")
            self.current_task.configure(text="An error occurred during installation")
            self.progress_bar.configure(progress_color=self.colors["error"])
    
    def _on_install_click(self):
        """Handle install button click"""
        logging.info("Install button clicked")
        
        # Disable buttons during installation
        self.install_button.configure(state="disabled")
        self.exit_button.configure(state="disabled")
        
        # Update UI for installation
        self.current_task.configure(text="Preparing installation...")
        self.percentage.configure(text="0%")
        
        # Clear previous installer if exists
        if self.installer:
            self.installer = None
        
        # Create and start installer process
        try:
            from core.installer import InstallerProcess
            logging.info("Creating installer process")
            self.installer = InstallerProcess(
                progress_callback=self.update_progress,
                status_callback=self._update_status_text,
                completion_callback=self._on_installation_complete
            )
            logging.info("Starting installer process")
            self.installer.start()
            logging.info("Installation process started")
        except Exception as e:
            logging.error(f"Failed to start installation: {e}")
            self._on_installation_error(str(e))
    
    def _update_status_text(self, text):
        """Update the status text"""
        logging.info(f"Status update: {text}")
        self.status_text.configure(text=text)
        self.current_task.configure(text=text)
    
    def _on_installation_error(self, error):
        """Handle installation error"""
        self.status_label.configure(text="Installation Failed")
        self.status_text.configure(text="Installation failed - See logs for details")
        self.current_task.configure(text="An error occurred during installation")
        self.progress_bar.configure(progress_color=self.colors["error"])
        self.install_button.configure(state="normal")
        self.exit_button.configure(state="normal")