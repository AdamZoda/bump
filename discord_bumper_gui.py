import os
import sys
import time
import threading
import queue
import urllib.request
import json
import hashlib
import subprocess
import webbrowser
import tkinter as tk
from tkinter import messagebox
from tkinter import ttk
from tkinter.scrolledtext import ScrolledText

# Check and import dependencies
try:
    import pyautogui
    import win32gui
    import win32con
    from win32com.client import Dispatch
except ImportError:
    pass

try:
    from PIL import Image, ImageTk
except ImportError:
    pass

# ==========================================
# CONFIGURATION SECURITE & MISES A JOUR
# ==========================================
# JSON attendu :
# {
#   "blocked": false,
#   "version": "1.0.0",
#   "message": "OK",
#   "url_mise_a_jour": "https://github.com/..."
# }
CHECK_URL = "https://raw.githubusercontent.com/AdamZoda/bump/main/config.json"
CURRENT_VERSION = "1.0.2"
PASSWORD_HASH = "5fbde9bb9c3fd8c224020057695ac4664a3fa134bdcd4f0550e2fad2202a14bf" # sha256 of "bump"

class DiscordBumperApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Bumper Multi-Bot - Control Panel")
        self.root.geometry("400x180")  # Compact geometry for the loading splash
        self.root.configure(bg="#313338")  # Discord Dark Theme background
        self.root.resizable(False, False)
        
        # Threading state variables
        self.log_queue = queue.Queue()
        self.is_running = False
        self.stop_event = threading.Event()
        self.offline_mode = False
        
        # Get own HWND to exclude it from window searching
        self.my_hwnd = None
        
        # Paths for custom logo branding (compatible with PyInstaller _MEIPASS)
        if getattr(sys, 'frozen', False):
            self.base_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
            self.asset_dir = getattr(sys, '_MEIPASS', self.base_dir)
        else:
            self.base_dir = os.path.dirname(os.path.abspath(__file__))
            self.asset_dir = self.base_dir
            
        self.logo_png_path = os.path.join(self.asset_dir, "logo-V2.png")
        self.logo_ico_path = os.path.join(self.base_dir, "logo.ico")
        self._auth_cache_path = os.path.join(self.base_dir, ".auth_cache")
        self._settings_cache_path = os.path.join(self.base_dir, ".settings_cache")
        
        self.setup_styles()
        
        # Check requirements first
        self.missing_libs = []
        try:
            import pyautogui
        except ImportError:
            self.missing_libs.append("pyautogui")
            
        try:
            import win32gui
            import win32con
            from win32com.client import Dispatch
        except ImportError:
            self.missing_libs.append("pywin32")
            
        try:
            from PIL import Image, ImageTk
        except ImportError:
            self.missing_libs.append("Pillow")
            
        try:
            import pyperclip
        except ImportError:
            self.missing_libs.append("pyperclip")
        
        # Convert logo PNG to ICO immediately at startup so it's active for loading/login windows
        if not os.path.exists(self.logo_ico_path) and os.path.exists(self.logo_png_path):
            self.convert_png_to_ico(self.logo_png_path, self.logo_ico_path)
            
        # Set Window Title Icon immediately
        if os.path.exists(self.logo_ico_path):
            try:
                self.root.iconbitmap(self.logo_ico_path)
            except Exception:
                pass
                
        if self.missing_libs:
            self.create_diagnostics_widgets()
        else:
            self.create_loading_widgets()
            # Start checking updates
            self.check_updates_and_status()

    def setup_styles(self):
        # Color scheme inspired by Discord Dark Mode
        self.bg_color = "#313338"       # Discord background
        self.card_color = "#2b2d31"     # Dark card background
        self.input_bg = "#1e1f22"       # Rich dark input background
        self.text_color = "#dbdee1"     # Light gray text
        self.white_color = "#ffffff"    # Pure white
        self.blurple_color = "#5865f2"  # Discord Blurple primary
        self.blurple_hover = "#4752c4"  # Hover state Blurple
        self.green_color = "#2ecc71"    # Success green
        self.red_color = "#e74c3c"      # Error red
        self.yellow_color = "#f1c40f"   # Warning yellow

    def create_loading_widgets(self):
        self.loading_frame = tk.Frame(self.root, bg=self.bg_color)
        self.loading_frame.pack(fill="both", expand=True)

        # Logo on loading screen
        if os.path.exists(self.logo_png_path):
            try:
                pil_img = Image.open(self.logo_png_path).resize((56, 56), Image.Resampling.LANCZOS)
                self._loading_logo = ImageTk.PhotoImage(pil_img)
                tk.Label(self.loading_frame, image=self._loading_logo, bg=self.bg_color).pack(pady=(20, 6))
            except Exception:
                pass

        self.loading_label = tk.Label(
            self.loading_frame,
            text="Vérification de la licence...",
            font=("Segoe UI", 10, "bold"),
            bg=self.bg_color,
            fg=self.text_color
        )
        self.loading_label.pack()

        self.loading_sub = tk.Label(
            self.loading_frame,
            text="Connexion au serveur...",
            font=("Segoe UI", 8),
            bg=self.bg_color,
            fg="#949ba4"
        )
        self.loading_sub.pack(pady=(2, 16))

        # Animated dots
        self._dot_count = 0
        self._animate_dots()

    def _animate_dots(self):
        dots = "." * (self._dot_count % 4)
        if hasattr(self, "loading_sub") and self.loading_sub.winfo_exists():
            self.loading_sub.config(text=f"Connexion au serveur{dots}")
            self._dot_count += 1
            self._dot_timer = self.root.after(400, self._animate_dots)

    def create_diagnostics_widgets(self):
        # Resize window to fit setup assistant
        self.root.geometry("460x490")
        
        self.diag_frame = tk.Frame(self.root, bg=self.bg_color)
        self.diag_frame.pack(fill="both", expand=True)
        
        # Header
        header = tk.Frame(self.diag_frame, bg=self.bg_color, pady=15)
        header.pack(fill="x")
        
        # Load logo for diagnostics header
        if os.path.exists(self.logo_png_path):
            try:
                pil_img = Image.open(self.logo_png_path)
                aspect_ratio = pil_img.width / pil_img.height
                target_height = 45
                target_width = int(target_height * aspect_ratio)
                self.diag_logo_image = ImageTk.PhotoImage(pil_img.resize((target_width, target_height), Image.Resampling.LANCZOS))
                
                logo_label = tk.Label(header, image=self.diag_logo_image, bg=self.bg_color)
                logo_label.pack(side="left", padx=(30, 10))
            except Exception:
                pass
                
        title_frame = tk.Frame(header, bg=self.bg_color)
        title_frame.pack(side="left")
        
        tk.Label(
            title_frame, 
            text="ASSISTANT CONFIGURATION", 
            font=("Segoe UI", 12, "bold"), 
            bg=self.bg_color, 
            fg=self.white_color
        ).pack(anchor="w")
        
        tk.Label(
            title_frame, 
            text="Composants manquants détectés", 
            font=("Segoe UI", 8, "italic"), 
            bg=self.bg_color, 
            fg=self.red_color
        ).pack(anchor="w")
        
        # Form Container
        card = tk.Frame(self.diag_frame, bg=self.card_color, bd=0, highlightbackground="#232428", highlightthickness=1)
        card.pack(fill="both", expand=True, padx=25, pady=(0, 15))
        
        tk.Label(
            card, 
            text="Statut des prérequis :", 
            font=("Segoe UI", 10, "bold"), 
            bg=self.card_color, 
            fg=self.text_color
        ).pack(anchor="w", padx=15, pady=(15, 5))
        
        # List requirements
        reqs = [
            ("Python (Interpréteur)", "Installé", True),
            ("Librairie 'pyautogui'", "Manquant" if "pyautogui" in self.missing_libs else "Installé", "pyautogui" not in self.missing_libs),
            ("Librairie 'pywin32'", "Manquant" if "pywin32" in self.missing_libs else "Installé", "pywin32" not in self.missing_libs),
            ("Librairie 'Pillow'", "Manquant" if "Pillow" in self.missing_libs else "Installé", "Pillow" not in self.missing_libs),
            ("Librairie 'pyperclip'", "Manquant" if "pyperclip" in self.missing_libs else "Installé", "pyperclip" not in self.missing_libs),
        ]
        
        for name, status, ok in reqs:
            row = tk.Frame(card, bg=self.card_color, pady=4)
            row.pack(fill="x", padx=15)
            
            icon = "✔️" if ok else "❌"
            color = self.green_color if ok else self.red_color
            
            tk.Label(row, text=icon, fg=color, bg=self.card_color, font=("Segoe UI", 10)).pack(side="left", padx=(0, 8))
            tk.Label(row, text=name, fg=self.text_color, bg=self.card_color, font=("Segoe UI", 9)).pack(side="left")
            tk.Label(row, text=status, fg=color, bg=self.card_color, font=("Segoe UI", 9, "bold")).pack(side="right")
            
        # Explanations
        info_frame = tk.Frame(card, bg=self.input_bg, pady=10, padx=10)
        info_frame.pack(fill="x", padx=15, pady=15)
        
        tk.Label(
            info_frame, 
            text="Pour corriger cela, copiez et exécutez la commande suivante\ndans votre terminal ou cliquez sur 'Installation Auto'.",
            font=("Segoe UI", 8), 
            bg=self.input_bg, 
            fg="#949ba4",
            justify="left"
        ).pack(anchor="w")
        
        cmd_var = tk.StringVar(value="pip install pyautogui pywin32 Pillow pyperclip")
        cmd_entry = tk.Entry(
            info_frame, 
            textvariable=cmd_var,
            font=("Consolas", 9), 
            bg=self.card_color, 
            fg=self.white_color, 
            bd=0, 
            state="readonly"
        )
        cmd_entry.pack(fill="x", pady=(8, 2), ipady=3)
        
        # Copy button helper
        def copy_cmd():
            self.root.clipboard_clear()
            self.root.clipboard_append("pip install pyautogui pywin32 Pillow pyperclip")
            messagebox.showinfo("Copier", "Commande copiée dans le presse-papiers !")
            
        # Action Buttons inside card
        btn_row = tk.Frame(card, bg=self.card_color)
        btn_row.pack(fill="x", padx=15, pady=(0, 15))
        
        copy_btn = tk.Button(
            btn_row, 
            text="📋  Copier", 
            font=("Segoe UI", 9, "bold"), 
            bg="#4e5058", 
            fg=self.white_color, 
            bd=0, 
            cursor="hand2", 
            command=copy_cmd
        )
        copy_btn.pack(side="left", fill="x", expand=True, padx=(0, 5), ipady=5)
        
        def run_installer():
            if os.path.exists("install.bat"):
                subprocess.Popen(["cmd.exe", "/c", "start install.bat"])
                self.root.destroy()
                sys.exit(0)
            else:
                messagebox.showerror("Erreur", "Fichier install.bat introuvable.")
                
        inst_btn = tk.Button(
            btn_row, 
            text="🔧  Installation Auto", 
            font=("Segoe UI", 9, "bold"), 
            bg=self.blurple_color, 
            fg=self.white_color, 
            bd=0, 
            cursor="hand2", 
            command=run_installer
        )
        inst_btn.pack(side="right", fill="x", expand=True, padx=(5, 0), ipady=5)
        
        # Footer
        tk.Label(
            self.diag_frame,
            text="Visitez https://python.org pour installer Python.",
            font=("Segoe UI", 8, "underline"),
            bg=self.bg_color,
            fg=self.blurple_color,
            cursor="hand2"
        ).pack(side="bottom", pady=(0, 15))
        
        # Bind the footer link to open browser
        self.diag_frame.bind_class("Label", "<Button-1>", lambda e: webbrowser.open("https://www.python.org/downloads/") if "python.org" in e.widget.cget("text") else None)

    def show_login_screen(self):
        if hasattr(self, "loading_frame") and self.loading_frame:
            self.loading_frame.destroy()

        # Check if we have a remembered password — auto login
        if self._load_cached_auth():
            return  # Already launched main app

        self.root.geometry("420x360")
        
        self.login_frame = tk.Frame(self.root, bg=self.bg_color)
        self.login_frame.pack(fill="both", expand=True)
        
        login_header = tk.Frame(self.login_frame, bg=self.bg_color, pady=15)
        login_header.pack(fill="x")
        
        # Load logo for login header (wider and taller, keeping aspect ratio)
        if os.path.exists(self.logo_png_path):
            try:
                pil_img = Image.open(self.logo_png_path)
                aspect_ratio = pil_img.width / pil_img.height
                target_height = 45
                target_width = int(target_height * aspect_ratio)
                self.login_logo_image = ImageTk.PhotoImage(pil_img.resize((target_width, target_height), Image.Resampling.LANCZOS))
                
                logo_label = tk.Label(login_header, image=self.login_logo_image, bg=self.bg_color)
                logo_label.pack(side="left", padx=(30, 10))
            except Exception:
                pass
                
        title_frame = tk.Frame(login_header, bg=self.bg_color)
        title_frame.pack(side="left")

        tk.Label(
            title_frame,
            text="BUMPER MULTI-BOT",
            font=("Segoe UI", 12, "bold"),
            bg=self.bg_color,
            fg=self.white_color
        ).pack(anchor="w")

        tk.Label(
            title_frame,
            text="Authentification requise",
            font=("Segoe UI", 8, "italic"),
            bg=self.bg_color,
            fg="#949ba4"
        ).pack(anchor="w")

        # Version badge top-right
        tk.Label(
            login_header,
            text=f"v{CURRENT_VERSION}",
            font=("Segoe UI", 8, "bold"),
            bg=self.blurple_color,
            fg=self.white_color,
            padx=6, pady=2
        ).pack(side="right", padx=(0, 20), anchor="n")
        
        # Form Container
        form_card = tk.Frame(self.login_frame, bg=self.card_color, bd=0, highlightbackground="#232428", highlightthickness=1)
        form_card.pack(fill="both", expand=True, padx=25, pady=(0, 20))
        
        tk.Label(
            form_card, 
            text="Mot de passe :", 
            font=("Segoe UI", 10, "bold"), 
            bg=self.card_color, 
            fg=self.text_color
        ).pack(anchor="w", padx=15, pady=(15, 2))
        
        self.password_var = tk.StringVar()
        self.password_entry = tk.Entry(
            form_card, 
            textvariable=self.password_var,
            show="*", 
            font=("Segoe UI", 11), 
            bg=self.input_bg, 
            fg=self.white_color, 
            insertbackground=self.white_color,
            bd=0, 
            highlightthickness=1, 
            highlightbackground="#1e1f22", 
            highlightcolor=self.blurple_color
        )
        self.password_entry.pack(fill="x", padx=15, ipady=5)
        self.password_entry.focus()
        self.password_entry.bind("<Return>", lambda e: self.validate_password())
        
        self.error_label = tk.Label(
            form_card,
            text="",
            font=("Segoe UI", 9, "bold"),
            bg=self.card_color,
            fg=self.red_color
        )
        self.error_label.pack(anchor="w", padx=15, pady=(5, 0))

        # Remember password checkbox
        self.remember_var = tk.BooleanVar(value=False)
        remember_cb = tk.Checkbutton(
            form_card,
            text="Se souvenir du mot de passe",
            variable=self.remember_var,
            font=("Segoe UI", 9),
            bg=self.card_color,
            fg="#949ba4",
            activebackground=self.card_color,
            activeforeground=self.text_color,
            selectcolor=self.input_bg,
            cursor="hand2"
        )
        remember_cb.pack(anchor="w", padx=15, pady=(4, 0))

        submit_btn = tk.Button(
            form_card,
            text="🔑  VALIDER",
            font=("Segoe UI", 10, "bold"),
            bg=self.blurple_color,
            fg=self.white_color,
            activebackground=self.blurple_hover,
            activeforeground=self.white_color,
            bd=0,
            cursor="hand2",
            command=self.validate_password
        )
        submit_btn.pack(fill="x", padx=15, pady=(10, 12), ipady=6)
        submit_btn.bind("<Enter>", lambda e: submit_btn.configure(bg=self.blurple_hover))
        submit_btn.bind("<Leave>", lambda e: submit_btn.configure(bg=self.blurple_color))

        # Footer version
        tk.Label(
            self.login_frame,
            text=f"Bumper Multi-Bot  •  Version {CURRENT_VERSION}",
            font=("Segoe UI", 7),
            bg=self.bg_color,
            fg="#4e5058"
        ).pack(side="bottom", pady=(0, 6))

    def load_settings(self):
        defaults = {
            "cmd": "/bump",
            "bot_count": "10",
            "target_app": "Discord (App)",
            "enable_multi_server": False,
            "server_list": [],
            "show_scheduling": False,
            "enable_interval": False,
            "interval_val": "5",
            "interval_unit": "Minutes",
            "enable_daily": False,
            "daily_times": "12:00, 18:30"
        }
        try:
            if os.path.exists(self._settings_cache_path):
                with open(self._settings_cache_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    defaults.update(data)
        except Exception:
            pass
        return defaults

    def save_settings(self):
        try:
            data = {
                "cmd": self.cmd_entry.get().strip(),
                "bot_count": self.count_spinbox.get().strip(),
                "target_app": self.app_target_var.get(),
                "enable_multi_server": self.enable_multi_server_var.get(),
                "server_list": list(self.server_list),
                "show_scheduling": self.show_scheduling_var.get(),
                "enable_interval": self.enable_interval_var.get(),
                "interval_val": self.interval_spinbox.get().strip(),
                "interval_unit": self.unit_var.get(),
                "enable_daily": self.enable_daily_var.get(),
                "daily_times": self.daily_entry.get().strip()
            }
            with open(self._settings_cache_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

    def _load_cached_auth(self):
        """If a saved hash exists and matches PASSWORD_HASH, auto-login."""
        try:
            if os.path.exists(self._auth_cache_path):
                with open(self._auth_cache_path, 'r') as f:
                    saved_hash = f.read().strip()
                if saved_hash == PASSWORD_HASH:
                    # Saved hash is still valid — launch main app directly
                    self.root.geometry("640x600")
                    self.create_widgets()
                    self.run_logo_and_shortcut_logic()
                    return True
                else:
                    # Password changed — delete old cache
                    os.remove(self._auth_cache_path)
        except Exception:
            pass
        return False

    def _save_cached_auth(self, password_hash):
        """Save hash locally for auto-login next time."""
        try:
            with open(self._auth_cache_path, 'w') as f:
                f.write(password_hash)
        except Exception:
            pass

    def validate_password(self):
        entered_password = self.password_var.get().strip()
        if not entered_password:
            self.error_label.config(text="Veuillez saisir un mot de passe.")
            return

        entered_hash = hashlib.sha256(entered_password.encode('utf-8')).hexdigest()

        if entered_hash == PASSWORD_HASH:
            # Save hash if "remember" is checked
            if self.remember_var.get():
                self._save_cached_auth(entered_hash)
            else:
                # Remove cache if unchecked
                try:
                    if os.path.exists(self._auth_cache_path):
                        os.remove(self._auth_cache_path)
                except Exception:
                    pass
            self.login_frame.destroy()
            self.root.geometry("640x600")
            self.create_widgets()
            self.run_logo_and_shortcut_logic()
        else:
            self.error_label.config(text="Mot de passe incorrect.")
            self.password_entry.delete(0, "end")
            self.password_entry.focus()

    def run_logo_and_shortcut_logic(self):
        # Convert PNG to ICO
        if not os.path.exists(self.logo_ico_path) and os.path.exists(self.logo_png_path):
            self.convert_png_to_ico(self.logo_png_path, self.logo_ico_path)
            
        # Set title icon
        if os.path.exists(self.logo_ico_path):
            try:
                self.root.iconbitmap(self.logo_ico_path)
            except Exception:
                pass
                
        # Create Desktop Shortcut
        self.check_and_create_shortcut()
        
        # Get active HWND
        self.root.update_idletasks()
        try:
            self.my_hwnd = self.root.winfo_id()
        except Exception:
            pass

    def create_widgets(self):
        settings = self.load_settings()

        # Keep the full interface reachable on short screens.
        real_root = self.root
        self.main_canvas = tk.Canvas(real_root, bg=self.bg_color, highlightthickness=0)
        self.main_scrollbar = tk.Scrollbar(real_root, orient="vertical", command=self.main_canvas.yview)
        self.main_canvas.configure(yscrollcommand=self.main_scrollbar.set)
        self.main_scrollbar.pack(side="right", fill="y")
        self.main_canvas.pack(side="left", fill="both", expand=True)
        self.main_content = tk.Frame(self.main_canvas, bg=self.bg_color)
        self.main_canvas_window = self.main_canvas.create_window(
            (0, 0), window=self.main_content, anchor="nw"
        )
        self.main_content.bind(
            "<Configure>",
            lambda e: self.main_canvas.configure(scrollregion=self.main_canvas.bbox("all"))
        )
        self.main_canvas.bind(
            "<Configure>",
            lambda e: self.main_canvas.itemconfigure(self.main_canvas_window, width=e.width)
        )
        self.main_canvas.bind_all(
            "<MouseWheel>",
            lambda e: self.main_canvas.yview_scroll(int(-e.delta / 120), "units")
        )
        self.root = self.main_content
        
        # Header Label Frame
        header_frame = tk.Frame(self.root, bg=self.bg_color, pady=10)
        header_frame.pack(fill="x")
        
        # Load and resize logo PNG for header next to title (larger, keeping aspect ratio)
        self.logo_image = None
        if os.path.exists(self.logo_png_path):
            try:
                pil_img = Image.open(self.logo_png_path)
                target_height = 50
                aspect_ratio = pil_img.width / pil_img.height
                target_width = int(target_height * aspect_ratio)
                
                resized_img = pil_img.resize((target_width, target_height), Image.Resampling.LANCZOS)
                self.logo_image = ImageTk.PhotoImage(resized_img)
                
                logo_label = tk.Label(header_frame, image=self.logo_image, bg=self.bg_color)
                logo_label.pack(side="left", padx=(20, 10))
            except Exception:
                pass
                
        title_label_frame = tk.Frame(header_frame, bg=self.bg_color)
        title_label_frame.pack(side="left", fill="both", expand=True)
        
        title_label = tk.Label(
            title_label_frame, 
            text="DISCORD MULTI-BOT BUMPER", 
            font=("Segoe UI", 13, "bold"), 
            bg=self.bg_color, 
            fg=self.white_color,
            anchor="w"
        )
        title_label.pack(anchor="w")
        
        subtitle_label = tk.Label(
            title_label_frame, 
            text="Automatisation sécurisée des commandes slash sur plusieurs comptes", 
            font=("Segoe UI", 8, "italic"), 
            bg=self.bg_color, 
            fg="#949ba4",
            anchor="w"
        )
        subtitle_label.pack(anchor="w")

        # Core Settings Container Card
        settings_frame = tk.Frame(self.root, bg=self.card_color, bd=0, highlightbackground="#232428", highlightthickness=1)
        settings_frame.pack(fill="x", padx=20, pady=5)
        
        settings_frame.columnconfigure(0, weight=1)
        settings_frame.columnconfigure(1, weight=1)
        
        # Command Input Field
        cmd_label_frame = tk.Frame(settings_frame, bg=self.card_color)
        cmd_label_frame.grid(row=0, column=0, padx=15, pady=(12, 4), sticky="w")
        
        tk.Label(
            cmd_label_frame, 
            text="Commande slash :", 
            font=("Segoe UI", 10, "bold"), 
            bg=self.card_color, 
            fg=self.text_color
        ).pack(anchor="w")
        
        self.cmd_entry = tk.Entry(
            settings_frame, 
            font=("Segoe UI", 11), 
            bg=self.input_bg, 
            fg=self.white_color, 
            insertbackground=self.white_color,
            bd=0, 
            highlightthickness=1, 
            highlightbackground="#1e1f22", 
            highlightcolor=self.blurple_color,
            disabledbackground="#2b2d31",
            disabledforeground="#72767d"
        )
        self.cmd_entry.insert(0, settings.get("cmd", "/bump"))
        self.cmd_entry.grid(row=1, column=0, padx=15, pady=(0, 12), ipady=6, sticky="we")
        
        # Bot Count Input Field
        count_label_frame = tk.Frame(settings_frame, bg=self.card_color)
        count_label_frame.grid(row=0, column=1, padx=15, pady=(12, 4), sticky="w")
        
        tk.Label(
            count_label_frame, 
            text="Nombre de bots :", 
            font=("Segoe UI", 10, "bold"), 
            bg=self.card_color, 
            fg=self.text_color
        ).pack(anchor="w")
        
        self.count_spinbox = tk.Spinbox(
            settings_frame, 
            from_=1, 
            to=100, 
            font=("Segoe UI", 11), 
            bg=self.input_bg, 
            fg=self.white_color, 
            insertbackground=self.white_color,
            buttonbackground="#2b2d31",
            bd=0, 
            highlightthickness=1, 
            highlightbackground="#1e1f22", 
            highlightcolor=self.blurple_color,
            disabledbackground="#2b2d31",
            disabledforeground="#72767d"
        )
        self.count_spinbox.delete(0, "end")
        self.count_spinbox.insert(0, settings.get("bot_count", "10"))
        self.count_spinbox.grid(row=1, column=1, padx=15, pady=(0, 12), ipady=5, sticky="we")

        # Target App Selection Field
        app_label_frame = tk.Frame(settings_frame, bg=self.card_color)
        app_label_frame.grid(row=2, column=0, columnspan=2, padx=15, pady=(4, 4), sticky="w")
        
        tk.Label(
            app_label_frame, 
            text="Application cible :", 
            font=("Segoe UI", 10, "bold"), 
            bg=self.card_color, 
            fg=self.text_color
        ).pack(anchor="w")
        
        self.app_target_var = tk.StringVar(value=settings.get("target_app", "Discord (App)"))
        
        # Combobox style matching dark theme (configuring styles)
        style = ttk.Style()
        style.theme_use('clam')
        style.configure(
            "TCombobox", 
            fieldbackground=self.input_bg, 
            background="#2b2d31", 
            foreground=self.white_color, 
            arrowcolor=self.white_color
        )
        style.map(
            "TCombobox",
            fieldbackground=[("disabled", "#2b2d31"), ("readonly", self.input_bg)],
            foreground=[("disabled", "#72767d"), ("readonly", self.white_color)],
            arrowcolor=[("disabled", "#72767d"), ("readonly", self.white_color)]
        )
        
        self.app_target_menu = ttk.Combobox(
            settings_frame, 
            textvariable=self.app_target_var, 
            values=["Discord (App)", "Brave", "Chrome", "Firefox", "Edge"], 
            state="readonly", 
            style="TCombobox"
        )
        self.app_target_menu.grid(row=3, column=0, columnspan=2, padx=15, pady=(0, 12), ipady=5, sticky="we")

        # ── Multi-Server Section ──────────────────────────────────────────────
        self.server_list = list(settings.get("server_list", []))
        
        self.enable_multi_server_var = tk.BooleanVar(value=settings.get("enable_multi_server", False))
        self.multi_server_cb = tk.Checkbutton(
            self.root,
            text="🌐  Activer le bump multi-serveur",
            font=("Segoe UI", 10, "bold"),
            bg=self.bg_color,
            fg=self.text_color,
            activebackground=self.bg_color,
            activeforeground=self.white_color,
            selectcolor="#1e1f22",
            var=self.enable_multi_server_var,
            command=self.toggle_multi_server_panel
        )
        self.multi_server_cb.pack(anchor="w", padx=20, pady=(8, 4))
        
        # Multi-server panel (hidden by default)
        self.multi_server_frame = tk.LabelFrame(
            self.root, 
            text=" Serveurs Cibles ", 
            font=("Segoe UI", 10, "bold"), 
            bg=self.bg_color, 
            fg=self.white_color, 
            bd=1, 
            relief="solid", 
            padx=15, 
            pady=10
        )
        
        # Add server row: Entry + Button
        add_row = tk.Frame(self.multi_server_frame, bg=self.bg_color)
        add_row.pack(fill="x", pady=(0, 8))
        
        self.server_name_entry = tk.Entry(
            add_row,
            font=("Segoe UI", 10),
            bg=self.input_bg,
            fg=self.white_color,
            insertbackground=self.white_color,
            bd=0,
            highlightthickness=1,
            highlightbackground="#1e1f22",
            highlightcolor=self.blurple_color
        )
        self.server_name_entry.pack(side="left", fill="x", expand=True, ipady=5, padx=(0, 8))
        self.server_name_entry.bind("<Return>", lambda e: self.add_server())
        
        self.add_server_btn = tk.Button(
            add_row,
            text="➕  Ajouter",
            font=("Segoe UI", 9, "bold"),
            bg=self.blurple_color,
            fg=self.white_color,
            activebackground=self.blurple_hover,
            activeforeground=self.white_color,
            bd=0,
            cursor="hand2",
            command=self.add_server
        )
        self.add_server_btn.pack(side="right", ipady=4, ipadx=8)
        self.add_server_btn.bind("<Enter>", lambda e: self.add_server_btn.configure(bg=self.blurple_hover))
        self.add_server_btn.bind("<Leave>", lambda e: self.add_server_btn.configure(bg=self.blurple_color))
        
        # Scrollable list of servers
        self.server_list_container = tk.Frame(self.multi_server_frame, bg=self.input_bg, bd=0, highlightthickness=1, highlightbackground="#232428")
        self.server_list_container.pack(fill="x")
        
        # Canvas + scrollbar for scrollable server tags
        self.server_canvas = tk.Canvas(self.server_list_container, bg=self.input_bg, highlightthickness=0, height=90)
        self.server_scrollbar = tk.Scrollbar(self.server_list_container, orient="vertical", command=self.server_canvas.yview)
        self.server_inner_frame = tk.Frame(self.server_canvas, bg=self.input_bg)
        
        self.server_inner_frame.bind("<Configure>", lambda e: self.server_canvas.configure(scrollregion=self.server_canvas.bbox("all")))
        self.server_canvas.create_window((0, 0), window=self.server_inner_frame, anchor="nw")
        self.server_canvas.configure(yscrollcommand=self.server_scrollbar.set)
        
        self.server_canvas.pack(side="left", fill="both", expand=True)
        self.server_scrollbar.pack(side="right", fill="y")
        
        # Info label
        tk.Label(
            self.multi_server_frame,
            text="Le bot utilisera Ctrl+K pour naviguer vers chaque serveur et trouver le salon #bump.",
            font=("Segoe UI", 8, "italic"),
            bg=self.bg_color,
            fg="#949ba4",
            wraplength=550,
            justify="left"
        ).pack(anchor="w", pady=(6, 0))
        
        # Populate saved servers
        self.refresh_server_list_ui()

        # Checkbox to toggle advanced scheduling options panel
        self.show_scheduling_var = tk.BooleanVar(value=settings.get("show_scheduling", False))
        self.show_sched_cb = tk.Checkbutton(
            self.root,
            text="⚙️  Options de planification avancées",
            font=("Segoe UI", 10, "bold"),
            bg=self.bg_color,
            fg=self.text_color,
            activebackground=self.bg_color,
            activeforeground=self.white_color,
            selectcolor="#1e1f22",
            var=self.show_scheduling_var,
            command=self.toggle_scheduling_panel
        )
        self.show_sched_cb.pack(anchor="w", padx=20, pady=(8, 4))

        # Scheduling Options Section (LabelFrame - hidden by default, packed via toggle)
        self.sched_frame = tk.LabelFrame(
            self.root, 
            text=" Options de Planification ", 
            font=("Segoe UI", 10, "bold"), 
            bg=self.bg_color, 
            fg=self.white_color, 
            bd=1, 
            relief="solid", 
            padx=15, 
            pady=10
        )
        
        # 1. Interval-based repetition checkbox
        self.enable_interval_var = tk.BooleanVar(value=settings.get("enable_interval", False))
        self.interval_cb = tk.Checkbutton(
            self.sched_frame, 
            text="Activer la répétition par intervalle", 
            font=("Segoe UI", 10, "bold"), 
            bg=self.bg_color, 
            fg=self.text_color, 
            activebackground=self.bg_color, 
            activeforeground=self.text_color,
            selectcolor="#1e1f22",
            var=self.enable_interval_var,
            command=self.toggle_scheduling_fields
        )
        self.interval_cb.grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 4))
        
        # Interval inputs sub-frame
        interval_input_frame = tk.Frame(self.sched_frame, bg=self.bg_color)
        interval_input_frame.grid(row=1, column=0, columnspan=2, sticky="w", padx=20, pady=(0, 8))
        
        tk.Label(
            interval_input_frame, 
            text="Répéter chaque :", 
            font=("Segoe UI", 10), 
            bg=self.bg_color, 
            fg=self.text_color
        ).pack(side="left", padx=(0, 10))
        
        self.interval_spinbox = tk.Spinbox(
            interval_input_frame, 
            from_=1, 
            to=3600, 
            width=8,
            font=("Segoe UI", 10), 
            bg=self.input_bg, 
            fg=self.white_color, 
            insertbackground=self.white_color,
            buttonbackground="#2b2d31",
            bd=0, 
            highlightthickness=1, 
            highlightbackground="#1e1f22", 
            highlightcolor=self.blurple_color,
            disabledbackground="#2b2d31",
            disabledforeground="#72767d"
        )
        self.interval_spinbox.delete(0, "end")
        self.interval_spinbox.insert(0, settings.get("interval_val", "5"))
        self.interval_spinbox.pack(side="left", padx=5)
        
        self.unit_var = tk.StringVar(value=settings.get("interval_unit", "Minutes"))
        
        self.unit_option_menu = ttk.Combobox(
            interval_input_frame, 
            textvariable=self.unit_var, 
            values=["Secondes", "Minutes", "Heures"], 
            width=10, 
            state="readonly", 
            style="TCombobox"
        )
        self.unit_option_menu.pack(side="left", padx=5)
        
        # 2. Daily Fixed Times scheduling checkbox
        self.enable_daily_var = tk.BooleanVar(value=settings.get("enable_daily", False))
        self.daily_cb = tk.Checkbutton(
            self.sched_frame, 
            text="Activer la planification à heures fixes", 
            font=("Segoe UI", 10, "bold"), 
            bg=self.bg_color, 
            fg=self.text_color, 
            activebackground=self.bg_color, 
            activeforeground=self.text_color,
            selectcolor="#1e1f22",
            var=self.enable_daily_var,
            command=self.toggle_scheduling_fields
        )
        self.daily_cb.grid(row=2, column=0, columnspan=2, sticky="w", pady=(4, 4))
        
        # Daily inputs sub-frame
        daily_input_frame = tk.Frame(self.sched_frame, bg=self.bg_color)
        daily_input_frame.grid(row=3, column=0, columnspan=2, sticky="w", padx=20, pady=(0, 4))
        
        tk.Label(
            daily_input_frame, 
            text="Heures de lancement quotidiennes (format HH:MM, séparées par virgules) :", 
            font=("Segoe UI", 10), 
            bg=self.bg_color, 
            fg=self.text_color
        ).pack(anchor="w", pady=(0, 2))
        
        self.daily_entry = tk.Entry(
            daily_input_frame, 
            width=50,
            font=("Segoe UI", 10), 
            bg=self.input_bg, 
            fg=self.white_color, 
            insertbackground=self.white_color,
            bd=0, 
            highlightthickness=1, 
            highlightbackground="#1e1f22", 
            highlightcolor=self.blurple_color,
            disabledbackground="#2b2d31",
            disabledforeground="#72767d"
        )
        self.daily_entry.insert(0, settings.get("daily_times", "12:00, 18:30"))
        self.daily_entry.pack(fill="x", ipady=4)
        
        # Initialize enabling/disabling states based on checkboxes
        self.toggle_scheduling_fields()
        
        # Action Buttons Frame
        self.btn_frame = tk.Frame(self.root, bg=self.bg_color)
        self.btn_frame.pack(fill="x", padx=20, pady=5)
        
        # Two-column layout for DÉMARRER and ARRÊTER
        self.btn_frame.columnconfigure(0, weight=3)
        self.btn_frame.columnconfigure(1, weight=1)
        
        self.run_btn = tk.Button(
            self.btn_frame, 
            text="🚀  DÉMARRER", 
            font=("Segoe UI", 11, "bold"), 
            bg=self.blurple_color, 
            fg=self.white_color, 
            activebackground=self.blurple_hover, 
            activeforeground=self.white_color,
            bd=0, 
            cursor="hand2", 
            command=self.start_bump_thread
        )
        self.run_btn.grid(row=0, column=0, padx=(0, 10), ipady=8, sticky="we")
        self.run_btn.bind("<Enter>", lambda e: self.run_btn.configure(bg=self.blurple_hover) if self.run_btn["state"] == "normal" else None)
        self.run_btn.bind("<Leave>", lambda e: self.run_btn.configure(bg=self.blurple_color) if self.run_btn["state"] == "normal" else None)
        
        self.stop_btn = tk.Button(
            self.btn_frame, 
            text="🛑  ARRÊTER", 
            font=("Segoe UI", 11, "bold"), 
            bg="#4e5058", # Inactive gray
            fg=self.white_color, 
            activebackground=self.red_color, 
            activeforeground=self.white_color,
            bd=0, 
            cursor="hand2", 
            state="disabled",
            command=self.stop_automation
        )
        self.stop_btn.grid(row=0, column=1, ipady=8, sticky="we")
        self.stop_btn.bind("<Enter>", lambda e: self.stop_btn.configure(bg=self.red_color) if self.stop_btn["state"] == "normal" else None)
        self.stop_btn.bind("<Leave>", lambda e: self.stop_btn.configure(bg="#da373c") if self.stop_btn["state"] == "normal" else None)
        
        # Console Section
        console_label_frame = tk.Frame(self.root, bg=self.bg_color)
        console_label_frame.pack(fill="x", padx=20, pady=(10, 2))
        
        tk.Label(
            console_label_frame, 
            text="Console de suivi en temps réel :", 
            font=("Segoe UI", 10, "bold"), 
            bg=self.bg_color, 
            fg=self.text_color
        ).pack(anchor="w")
        
        # Scrollable console using standard ScrolledText
        self.console = ScrolledText(
            self.root, 
            font=("Consolas", 9), 
            bg=self.input_bg, 
            fg="#f2f3f5", 
            insertbackground=self.white_color,
            bd=0, 
            highlightthickness=1, 
            highlightbackground="#232428",
            padx=10,
            pady=10
        )
        self.console.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        
        # Coloring tags config
        self.console.tag_config("info", foreground=self.text_color)
        self.console.tag_config("success", foreground=self.green_color)
        self.console.tag_config("warning", foreground=self.yellow_color)
        self.console.tag_config("error", foreground=self.red_color)
        self.console.tag_config("system", foreground="#949ba4", font=("Consolas", 9, "italic"))
        
        # Log default first messages that were queued
        if getattr(self, "offline_mode", False):
            self.log("Console initialisée. [Démarrage Hors-Ligne]", "warning")
            self.log("⚠️ Impossible de se connecter au serveur de mise à jour. L'application s'exécute localement.", "warning")
        else:
            self.log("Console initialisée. Licence validée avec succès.", "success")
        
        # Restore toggle state after all widgets are packed
        self.root = real_root
        self.toggle_multi_server_panel()
        self.toggle_scheduling_panel()
        self.main_canvas.configure(scrollregion=self.main_canvas.bbox("all"))

    def log(self, message, msg_type="info"):
        timestamp = time.strftime("[%H:%M:%S] ")
        self.log_queue.put((timestamp + message + "\n", msg_type))

    def process_log_queue(self):
        while not self.log_queue.empty():
            try:
                msg, msg_type = self.log_queue.get_nowait()
                # Check if console widget is initialized
                if hasattr(self, "console") and self.console:
                    self.console.configure(state="normal")
                    self.console.insert("end", msg, msg_type)
                    self.console.configure(state="disabled")
                    self.console.see("end")  # Scroll to bottom
            except queue.Empty:
                break
        self.root.after(100, self.process_log_queue)

    def convert_png_to_ico(self, png_path, ico_path):
        try:
            img = Image.open(png_path)
            icon_sizes = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
            img.save(ico_path, format="ICO", sizes=icon_sizes)
            return True
        except Exception:
            return False

    def check_and_create_shortcut(self):
        if sys.platform != "win32":
            return
            
        try:
            desktop = os.path.join(os.path.expanduser("~"), "Desktop")
            shortcut_path = os.path.join(desktop, "Bumper Multi-Bot.lnk")
            
            if not os.path.exists(shortcut_path):
                shell = Dispatch('WScript.Shell')
                shortcut = shell.CreateShortCut(shortcut_path)
                
                # Check if running as a compiled PyInstaller EXE
                if getattr(sys, 'frozen', False):
                    shortcut.TargetPath = os.path.abspath(sys.argv[0])
                    shortcut.Arguments = ""
                    shortcut.WorkingDirectory = os.path.dirname(os.path.abspath(sys.argv[0]))
                else:
                    script_path = os.path.abspath(sys.argv[0])
                    python_exe = sys.executable.replace("python.exe", "pythonw.exe")
                    shortcut.TargetPath = python_exe
                    shortcut.Arguments = f'"{script_path}"'
                    shortcut.WorkingDirectory = os.path.dirname(script_path)
                
                if os.path.exists(self.logo_ico_path):
                    shortcut.IconLocation = self.logo_ico_path
                    
                shortcut.Description = "Bumper Discord Multi-Bot"
                shortcut.save()
        except Exception:
            pass

    def check_updates_and_status(self):
        # Always run the security check — no bypass allowed
        threading.Thread(target=self._run_security_check, daemon=True).start()

    def _run_security_check(self):
        # Verification is always mandatory
        if not CHECK_URL:
            self.root.after(0, self._handle_connection_error, "CHECK_URL non configurée.")
            return

        try:
            req = urllib.request.Request(CHECK_URL, headers={'User-Agent': 'BumperApp/1.0'})
            with urllib.request.urlopen(req, timeout=8) as response:
                data = json.loads(response.read().decode('utf-8'))

                # 1. Check block/kill-switch
                if data.get("blocked", False):
                    self.root.after(0, self._handle_blocked_app, data.get("message", "Accès refusé."))
                    return

                # 2. Check for mandatory update
                latest_version = data.get("version", CURRENT_VERSION)
                if latest_version != CURRENT_VERSION:
                    update_url = data.get("url_mise_a_jour", "")
                    self.root.after(0, self._handle_auto_update, latest_version, update_url)
                    return

                # 3. All good — show login
                self.root.after(0, self.show_login_screen)

        except urllib.error.HTTPError as e:
            if e.code == 404:
                # config.json absent du serveur — laisser passer (fichier pas encore déployé)
                self.root.after(0, self.show_login_screen)
            else:
                self.offline_mode = True
                self.root.after(0, self.show_login_screen)
        except Exception as e:
            self.offline_mode = True
            self.root.after(0, self.show_login_screen)

    def _handle_auto_update(self, new_version, update_url):
        """Show update loader, download new script, relaunch."""
        # Stop dot animation
        if hasattr(self, "_dot_timer"):
            self.root.after_cancel(self._dot_timer)

        # Update the loading screen text
        if hasattr(self, "loading_label") and self.loading_label.winfo_exists():
            self.loading_label.config(text=f"Mise à jour v{new_version} en cours...", fg=self.yellow_color)
        if hasattr(self, "loading_sub") and self.loading_sub.winfo_exists():
            self.loading_sub.config(text="Téléchargement... veuillez patienter")

        # Progress bar
        self._progress_frame = tk.Frame(self.loading_frame, bg=self.bg_color)
        self._progress_frame.pack(fill="x", padx=40, pady=(4, 0))
        self._progress_bar = ttk.Progressbar(self._progress_frame, mode='indeterminate', length=300)
        self._progress_bar.pack(fill="x")
        self._progress_bar.start(12)

        # Run download in thread
        threading.Thread(target=self._download_and_relaunch, args=(update_url, new_version), daemon=True).start()

    def _download_and_relaunch(self, update_url, new_version):
        script_path = os.path.abspath(sys.argv[0])
        try:
            if update_url:
                req = urllib.request.Request(update_url, headers={'User-Agent': 'BumperApp/1.0'})
                with urllib.request.urlopen(req, timeout=30) as r:
                    new_code = r.read()
                # Write new version
                with open(script_path, 'wb') as f:
                    f.write(new_code)
                self.root.after(0, self._relaunch_app)
            else:
                # No URL — show message and exit so user can get it manually
                self.root.after(0, self._handle_mandatory_update,
                    f"Nouvelle version {new_version} disponible.\nTéléchargez la dernière version manuellement.")
        except Exception as e:
            self.root.after(0, self._handle_mandatory_update,
                f"Échec du téléchargement v{new_version}.\nDétails : {e}")

    def _relaunch_app(self):
        if hasattr(self, "loading_label") and self.loading_label.winfo_exists():
            self.loading_label.config(text="Mise à jour terminée ! Relancement...", fg=self.green_color)
        self.root.after(1500, self._do_relaunch)

    def _do_relaunch(self):
        self.root.destroy()
        os.execv(sys.executable, [sys.executable] + sys.argv)

    def _handle_blocked_app(self, reason):
        messagebox.showerror(
            "Accès Refusé", 
            f"Cette application a été désactivée par son créateur.\n\nRaison : {reason}\n\nFermeture de l'application."
        )
        self.root.destroy()
        sys.exit(0)

    def _handle_mandatory_update(self, msg):
        messagebox.showerror(
            "Mise à jour obligatoire", 
            f"Veuillez télécharger la dernière version pour continuer.\n\n{msg}\n\nL'application va se fermer."
        )
        self.root.destroy()
        sys.exit(0)

    def _handle_connection_error(self, msg):
        messagebox.showerror(
            "Erreur de Connexion", 
            f"Impossible de démarrer l'application sans connexion Internet active.\n\n{msg}\n\nL'application va se fermer."
        )
        self.root.destroy()
        sys.exit(0)

    def _compute_geometry(self):
        """Compute the window height dynamically based on active panels."""
        h = 560  # base height with multi-server checkbox row
        if self.enable_multi_server_var.get():
            h += 220
        if self.show_scheduling_var.get():
            h += 230
        self.root.geometry(f"640x{h}")

    def toggle_scheduling_panel(self):
        if self.show_scheduling_var.get():
            self.sched_frame.pack(fill="x", padx=20, pady=10, before=self.btn_frame)
        else:
            self.sched_frame.pack_forget()
        self._compute_geometry()

    def toggle_scheduling_fields(self):
        # Enable/disable interval controls based on the checkbox state
        interval_state = "normal" if self.enable_interval_var.get() else "disabled"
        self.interval_spinbox.config(state=interval_state)
        
        # Readonly state for Combobox when enabled, disabled state when checked out
        if self.enable_interval_var.get():
            self.unit_option_menu.config(state="readonly")
        else:
            self.unit_option_menu.config(state="disabled")
        
        # Enable/disable daily controls based on the checkbox state
        daily_state = "normal" if self.enable_daily_var.get() else "disabled"
        self.daily_entry.config(state=daily_state)

    def toggle_multi_server_panel(self):
        if self.enable_multi_server_var.get():
            self.multi_server_frame.pack(fill="x", padx=20, pady=10, before=self.show_sched_cb)
        else:
            self.multi_server_frame.pack_forget()
        self._compute_geometry()

    def add_server(self):
        name = self.server_name_entry.get().strip()
        if not name:
            return
        if name in self.server_list:
            return  # Avoid duplicates
        self.server_list.append(name)
        self.server_name_entry.delete(0, "end")
        self.refresh_server_list_ui()
        self.server_name_entry.focus()

    def remove_server(self, name):
        if name in self.server_list:
            self.server_list.remove(name)
        self.refresh_server_list_ui()

    def refresh_server_list_ui(self):
        # Clear existing widgets
        for widget in self.server_inner_frame.winfo_children():
            widget.destroy()
        
        if not self.server_list:
            tk.Label(
                self.server_inner_frame,
                text="  Aucun serveur ajouté. Tapez un nom ci-dessus et cliquez ➕",
                font=("Segoe UI", 9, "italic"),
                bg=self.input_bg,
                fg="#72767d"
            ).pack(anchor="w", padx=8, pady=10)
            return
        
        for idx, server_name in enumerate(self.server_list):
            row = tk.Frame(self.server_inner_frame, bg="#2b2d31" if idx % 2 == 0 else self.input_bg)
            row.pack(fill="x", padx=4, pady=2)
            
            # Server number badge
            tk.Label(
                row,
                text=f" {idx + 1}.",
                font=("Consolas", 9, "bold"),
                bg=row.cget("bg"),
                fg=self.blurple_color,
                width=4
            ).pack(side="left")
            
            # Server name
            tk.Label(
                row,
                text=server_name,
                font=("Segoe UI", 10),
                bg=row.cget("bg"),
                fg=self.white_color,
                anchor="w"
            ).pack(side="left", fill="x", expand=True, padx=(4, 0))
            
            # Delete button
            sn = server_name  # capture for closure
            del_btn = tk.Button(
                row,
                text="❌",
                font=("Segoe UI", 8),
                bg=row.cget("bg"),
                fg=self.red_color,
                activebackground=self.red_color,
                activeforeground=self.white_color,
                bd=0,
                cursor="hand2",
                command=lambda s=sn: self.remove_server(s)
            )
            del_btn.pack(side="right", padx=4, pady=2)

    def set_gui_state(self, enabled):
        state = "normal" if enabled else "disabled"
        self.cmd_entry.config(state=state)
        self.count_spinbox.config(state=state)
        self.show_sched_cb.config(state=state)
        self.interval_cb.config(state=state)
        self.daily_cb.config(state=state)
        self.multi_server_cb.config(state=state)
        
        if enabled:
            self.app_target_menu.config(state="readonly")
            self.server_name_entry.config(state="normal")
            self.add_server_btn.config(state="normal")
            self.toggle_scheduling_fields()
            self.run_btn.config(state="normal", text="🚀  DÉMARRER", bg=self.blurple_color)
            self.stop_btn.config(state="disabled", bg="#4e5058")
        else:
            # Force disable all inputs when running
            self.app_target_menu.config(state="disabled")
            self.server_name_entry.config(state="disabled")
            self.add_server_btn.config(state="disabled")
            self.interval_spinbox.config(state="disabled")
            self.unit_option_menu.config(state="disabled")
            self.daily_entry.config(state="disabled")
            
            self.run_btn.config(state="disabled", text="⚡  PLANIFICATION ACTIVE...", bg="#2b2d31")
            self.stop_btn.config(state="normal", bg="#da373c")

    def start_bump_thread(self):
        if self.is_running:
            return
            
        cmd = self.cmd_entry.get().strip()
        try:
            bot_count = int(self.count_spinbox.get().strip())
        except ValueError:
            messagebox.showerror("Erreur de saisie", "Le nombre de bots doit être un entier valide.")
            return
            
        if not cmd:
            messagebox.showerror("Erreur de saisie", "La commande ne peut pas être vide.")
            return
            
        if bot_count < 1:
            messagebox.showerror("Erreur de saisie", "Le nombre de bots doit être d'au moins 1.")
            return

        # Save settings locally
        self.save_settings()

        self.is_running = True
        self.stop_event.clear()
        self.set_gui_state(False)
        
        # Start execution thread
        self.worker_thread = threading.Thread(target=self.run_bump_process, args=(cmd, bot_count), daemon=True)
        self.worker_thread.start()

    def stop_automation(self):
        if not self.is_running:
            return
        self.log("🛑 Demande d'arrêt envoyée... Clôture en cours.", "warning")
        self.stop_event.set()

    def navigate_to_server(self, server_name):
        self.log(f"🌐 Navigation vers le serveur : '{server_name}'...", "info")
        # 1. Open Quick Switcher (Ctrl + K)
        pyautogui.hotkey("ctrl", "k")
        time.sleep(0.5)
        
        # 2. Clear anything in the quick switcher
        pyautogui.hotkey("ctrl", "a")
        time.sleep(0.1)
        pyautogui.press("delete")
        time.sleep(0.2)
        
        # 3. Write target search term (server name only)
        search_query = server_name
        try:
            import pyperclip
            old_clip = pyperclip.paste()
            pyperclip.copy(search_query)
            time.sleep(0.1)
            pyautogui.hotkey("ctrl", "v")
            time.sleep(0.3)
            if old_clip:
                pyperclip.copy(old_clip)
        except Exception:
            pyautogui.write(search_query, interval=0.04)
            time.sleep(0.3)
            
        # 4. Wait for search results
        time.sleep(0.8)
        
        # 5. Press Enter to confirm navigation
        pyautogui.press("enter")
        
        # 6. Wait for Discord channel load
        time.sleep(1.5)

    def execute_single_bump(self, command, bot_count):
        target_app = self.app_target_var.get()
        self.log(f"Recherche de la fenêtre pour {target_app}...", "info")
        hwnd_discord = None
        
        def enum_windows_callback(hwnd, extra):
            nonlocal hwnd_discord
            if hwnd == self.my_hwnd:
                return True
            if win32gui.IsWindowVisible(hwnd):
                title = win32gui.GetWindowText(hwnd).lower()
                
                # Check match based on selected target app
                match = False
                if target_app == "Discord (App)":
                    if "discord" in title and "overlay" not in title and "control panel" not in title:
                        # Exclude browsers in Discord App mode
                        if not any(b in title for b in ["brave", "chrome", "firefox", "edge", "opera", "browser"]):
                            match = True
                elif target_app == "Brave":
                    if "brave" in title:
                        match = True
                elif target_app == "Chrome":
                    if "chrome" in title:
                        match = True
                elif target_app == "Firefox":
                    if "firefox" in title:
                        match = True
                elif target_app == "Edge":
                    if "edge" in title:
                        match = True
                        
                if match:
                    hwnd_discord = hwnd
            return True
            
        win32gui.EnumWindows(enum_windows_callback, None)
        
        if not hwnd_discord:
            self.log(f"❌ Fenêtre {target_app} introuvable. Veuillez vous assurer que l'application est lancée.", "error")
            return False

        full_title = win32gui.GetWindowText(hwnd_discord)
        self.log(f"Fenêtre {target_app} trouvée : '{full_title}' (HWND: {hwnd_discord}).", "success")
        
        # Friendly warning check for browser targeting
        if target_app != "Discord (App)" and "discord" not in full_title.lower():
            self.log(f"⚠️ Attention : L'onglet actif de {target_app} ne semble pas être Discord. Assurez-vous que l'onglet Discord est visible.", "warning")
        
        try:
            # Restore window if minimized
            if win32gui.IsIconic(hwnd_discord):
                self.log("Restauration de la fenêtre Discord minimisée...", "info")
                win32gui.ShowWindow(hwnd_discord, win32con.SW_RESTORE)
                time.sleep(0.5)
                
            # Set focus to Discord
            self.log("Activation de la fenêtre Discord...", "info")
            try:
                win32gui.SetForegroundWindow(hwnd_discord)
            except Exception as e:
                self.log(f"⚠️ Avertissement lors de la mise au premier plan : {e}", "warning")
            time.sleep(0.5)
            
            # Click bottom-middle of the window (chat input field)
            rect = win32gui.GetWindowRect(hwnd_discord)
            left, top, right, bottom = rect
            width = right - left
            
            click_x = left + (width // 2)
            click_y = bottom - 50
            
            self.log(f"Clic dans la zone de chat Discord à la position ({click_x}, {click_y})...", "info")
            pyautogui.click(click_x, click_y)
            time.sleep(0.5)
            
            # Determine list of channels/servers to bump
            multi_server_active = self.enable_multi_server_var.get()
            targets = self.server_list if (multi_server_active and self.server_list) else [None]
            
            for target_idx, target_server in enumerate(targets):
                if self.stop_event.is_set():
                    self.log("🛑 Exécution interrompue par l'utilisateur.", "warning")
                    return False
                    
                if target_server:
                    self.log(f"🌐 [Serveur {target_idx + 1}/{len(targets)}] Début de la séquence pour : {target_server}", "success")
                    self.navigate_to_server(target_server)
                    
                    # Click inside chat area again after navigation to ensure focus
                    pyautogui.click(click_x, click_y)
                    time.sleep(0.5)
                
                # Keystroke automation loop for current channel
                for i in range(bot_count):
                    if self.stop_event.is_set():
                        self.log("🛑 Exécution interrompue par l'utilisateur.", "warning")
                        return False
                        
                    bot_num = i + 1
                    self.log(f"🤖 [Bot {bot_num}/{bot_count}] Préparation...", "info")
                    
                    # Clear chat (Ctrl+A then Delete)
                    pyautogui.hotkey("ctrl", "a")
                    time.sleep(0.1)
                    pyautogui.press("delete")
                    time.sleep(0.1)
                    
                    # Paste command via clipboard to avoid keyboard layout (AZERTY vs QWERTY) mismatch errors
                    self.log(f"🤖 [Bot {bot_num}/{bot_count}] Copie et collage de la commande...", "info")
                    try:
                        import pyperclip
                        # Backup old clipboard
                        old_clipboard = pyperclip.paste()
                        # Set command to clipboard
                        pyperclip.copy(command)
                        time.sleep(0.1)
                        # Paste command using Ctrl+V
                        pyautogui.hotkey("ctrl", "v")
                        time.sleep(0.2)
                        # Restore old clipboard
                        if old_clipboard:
                            pyperclip.copy(old_clipboard)
                    except Exception as e:
                        self.log(f"⚠️ Erreur presse-papiers ({e}), repli sur la saisie manuelle...", "warning")
                        pyautogui.write(command, interval=0.04)
                    
                    # Autocomplete wait (checking for stop_event periodically)
                    self.log(f"🤖 [Bot {bot_num}/{bot_count}] Attente de l'autocomplétion (1.5s)...", "info")
                    for _ in range(15):
                        if self.stop_event.is_set():
                            self.log("🛑 Exécution interrompue par l'utilisateur.", "warning")
                            return False
                        time.sleep(0.1)
                    
                    # Navigate menu
                    if i > 0:
                        self.log(f"🤖 [Bot {bot_num}/{bot_count}] Navigation : pressions sur Bas x {i}...", "info")
                        for _ in range(i):
                            if self.stop_event.is_set():
                                self.log("🛑 Exécution interrompue par l'utilisateur.", "warning")
                                return False
                            pyautogui.press("down")
                            time.sleep(0.1)
                    
                    # Validate selection
                    self.log(f"🤖 [Bot {bot_num}/{bot_count}] Validation avec Tab...", "info")
                    pyautogui.press("tab")
                    time.sleep(0.5)
                    
                    # Send command
                    self.log(f"🤖 [Bot {bot_num}/{bot_count}] Envoi de la commande avec Entrée !", "success")
                    pyautogui.press("enter")
                    
                    # Delay between bots
                    if i < bot_count - 1:
                        delay = 3.0
                        self.log(f"Délai d'attente anti-spam de {delay}s avant le bot suivant...", "system")
                        for _ in range(int(delay * 10)):
                            if self.stop_event.is_set():
                                self.log("🛑 Exécution interrompue par l'utilisateur.", "warning")
                                return False
                            time.sleep(0.1)
                
                # Cooldown between servers
                if target_server and target_idx < len(targets) - 1:
                    cooldown = 5.0
                    self.log(f"⏳ Attente de {cooldown}s de sécurité avant le serveur suivant...", "system")
                    for _ in range(int(cooldown * 10)):
                        if self.stop_event.is_set():
                            self.log("🛑 Exécution interrompue par l'utilisateur.", "warning")
                            return False
                        time.sleep(0.1)
                            
            self.log("✅ Automatisation d'envoi terminée !", "success")
            return True
            
        except Exception as e:
            self.log(f"❌ Erreur lors de l'exécution physique : {e}", "error")
            return False

    def run_bump_process(self, command, bot_count):
        # Read the scheduling panel state first
        show_scheduling = self.show_scheduling_var.get()
        use_interval = self.enable_interval_var.get() if show_scheduling else False
        use_daily = self.enable_daily_var.get() if show_scheduling else False
        
        interval_val = 0
        interval_unit = "Minutes"
        if use_interval:
            try:
                interval_val = int(self.interval_spinbox.get().strip())
                interval_unit = self.unit_var.get()
            except ValueError:
                self.log("❌ Valeur d'intervalle invalide.", "error")
                self.is_running = False
                self.root.after(0, lambda: self.set_gui_state(True))
                return
                
        daily_times = []
        if use_daily:
            times_str = self.daily_entry.get().strip()
            if not times_str:
                self.log("❌ Liste d'heures vide pour la planification.", "error")
                self.is_running = False
                self.root.after(0, lambda: self.set_gui_state(True))
                return
            for t in times_str.split(","):
                t = t.strip()
                if not t:
                    continue
                try:
                    time.strptime(t, "%H:%M")
                    daily_times.append(t)
                except ValueError:
                    self.log(f"❌ Format d'heure invalide : '{t}'. Utilisez le format HH:MM (ex: 12:00, 18:30).", "error")
                    self.is_running = False
                    self.root.after(0, lambda: self.set_gui_state(True))
                    return
            if not daily_times:
                self.log("❌ Aucune heure valide saisie pour la planification.", "error")
                self.is_running = False
                self.root.after(0, lambda: self.set_gui_state(True))
                return

        self.log("⚙️ Initialisation du gestionnaire de planification...", "system")
        
        # Calculate interval seconds
        interval_seconds = 0
        if use_interval:
            multiplier = 1
            if interval_unit == "Secondes":
                multiplier = 1
            elif interval_unit == "Minutes":
                multiplier = 60
            elif interval_unit == "Heures":
                multiplier = 3600
            interval_seconds = interval_val * multiplier

        # 1. Single run mode (if no scheduling is active)
        if not use_interval and not use_daily:
            self.execute_single_bump(command, bot_count)
            self.is_running = False
            self.root.after(0, lambda: self.set_gui_state(True))
            return

        # 2. Scheduling loop mode
        last_daily_runs = {} # Track runs to avoid double execution in the same minute
        
        # If interval repetition is enabled, run the first execution immediately
        next_interval_run = 0
        if use_interval:
            self.log("🔄 [Planificateur] Lancement immédiat de la première boucle d'intervalle...", "success")
            self.execute_single_bump(command, bot_count)
            next_interval_run = time.time() + interval_seconds
            
        last_logged_rem = -1

        self.log("⏳ [Planificateur] En attente de la prochaine exécution planifiée...", "success")
        
        while not self.stop_event.is_set():
            now = time.time()
            current_time_struct = time.localtime()
            current_date_str = time.strftime("%Y-%m-%d", current_time_struct)
            current_time_str = time.strftime("%H:%M", current_time_struct)
            
            # Check Daily schedule triggers
            if use_daily:
                for target_time in daily_times:
                    key = f"{current_date_str}_{target_time}"
                    if current_time_str == target_time and key not in last_daily_runs:
                        self.log(f"⏰ [Planificateur] Heure programmée atteinte ({target_time}). Lancement...", "success")
                        self.execute_single_bump(command, bot_count)
                        last_daily_runs[key] = True
                        break # Break inner loop, continue checking
            
            # Check Interval schedule triggers
            if use_interval:
                if now >= next_interval_run:
                    self.log("🔄 [Planificateur] Intervalle expiré. Lancement de la boucle...", "success")
                    self.execute_single_bump(command, bot_count)
                    next_interval_run = time.time() + interval_seconds
                    last_logged_rem = -1
                else:
                    remaining = int(next_interval_run - now)
                    if remaining > 0 and (remaining != last_logged_rem) and (remaining % 10 == 0 or remaining <= 5):
                        h = remaining // 3600
                        m = (remaining % 3600) // 60
                        s = remaining % 60
                        time_str = ""
                        if h > 0:
                            time_str += f"{h}h "
                        if m > 0 or h > 0:
                            time_str += f"{m}m "
                        time_str += f"{s}s"
                        self.log(f"⏳ [Planificateur] Prochain bump automatique dans {time_str}...", "info")
                        last_logged_rem = remaining
            
            # Sleep in tiny increments to keep the stop button responsive
            for _ in range(10):
                if self.stop_event.is_set():
                    break
                time.sleep(0.1)

        self.log("🛑 Planificateur désactivé. Mode manuel restauré.", "system")
        
        # Reset state and restore GUI inputs
        self.is_running = False
        self.root.after(0, lambda: self.set_gui_state(True))

if __name__ == "__main__":
    # ─── Fix taskbar icon on Windows ───────────────────────────────────────────
    # Without this, Windows groups the app under python.exe and shows Python icon.
    # Setting a unique AppUserModelID makes Windows treat it as its own app.
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            u"BumperMultiBot.DiscordBumper.1.0"
        )
    except Exception:
        pass

    # Enable high-DPI scaling on Windows
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass

    root = tk.Tk()
    app = DiscordBumperApp(root)
    root.mainloop()
