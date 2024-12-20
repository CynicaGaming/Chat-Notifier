import sys
import os
import time
import psutil
import json
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from playsound import playsound
from PyQt5.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QAction,
    QTextEdit,
    QPushButton,
    QHBoxLayout,
    QMessageBox,
    QSystemTrayIcon,
    QMenu,
    QFileDialog,
    QColorDialog,
    QDialog,
    QLabel,
    QComboBox,
    QSpinBox,
    QFormLayout,
    QGroupBox,
    QCheckBox,
)
from PyQt5.QtCore import pyqtSignal, Qt, QObject, QEvent, QTimer
from PyQt5.QtGui import QPalette, QColor, QIcon, QTextCursor, QFont


class WorkerSignals(QObject):
    """
    Defines custom signals for logging and system messages.
    """
    log_line = pyqtSignal(str, str, str, str, str)  # content, timestamp, channel, username, category
    system_line = pyqtSignal(str, str)  # msg, color


class SettingsDialog(QDialog):
    """
    Dialog for configuring application settings, including theme, font size,
    chat colors, and notification preferences.
    """

    def __init__(self, parent=None, config=None, chat_colors=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.config = config
        self.chat_colors = chat_colors
        self.init_ui()

    def init_ui(self):
        """
        Initializes the settings dialog UI components, organizing them into
        grouped sections for better aesthetics and usability.
        """
        main_layout = QVBoxLayout()

        # Appearance Group
        appearance_group = QGroupBox("Appearance")
        appearance_layout = QFormLayout()

        # Theme Selection
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["Dark", "Light"])
        current_theme = self.config.get("theme", "Dark")
        index = self.theme_combo.findText(current_theme)
        if index >= 0:
            self.theme_combo.setCurrentIndex(index)
        appearance_layout.addRow(QLabel("Theme:"), self.theme_combo)

        # Font Size Selection
        self.font_spinbox = QSpinBox()
        self.font_spinbox.setRange(8, 48)
        self.font_spinbox.setValue(self.config.get("font_size", 12))
        appearance_layout.addRow(QLabel("Font Size:"), self.font_spinbox)

        appearance_group.setLayout(appearance_layout)
        main_layout.addWidget(appearance_group)

        # Chat Colors Group
        colors_group = QGroupBox("Chat Colors")
        colors_layout = QFormLayout()

        self.color_buttons = {}
        for category, color in self.chat_colors.items():
            button = QPushButton()
            button.setStyleSheet(f"background-color: {color}")
            button.setFixedWidth(50)
            button.clicked.connect(lambda _, cat=category: self.select_color(cat))
            self.color_buttons[category] = button
            colors_layout.addRow(QLabel(f"{category}:"), button)

        colors_group.setLayout(colors_layout)
        main_layout.addWidget(colors_group)

        # Notifications Group
        notifications_group = QGroupBox("Notifications")
        notifications_layout = QFormLayout()

        # Notification Sound Selection
        self.sound_button = QPushButton("Select Sound")
        self.sound_button.clicked.connect(self.select_sound)
        notifications_layout.addRow(QLabel("Notification Sound:"), self.sound_button)

        # Enable Whisper Notifications Checkbox
        self.whisper_notify_checkbox = QCheckBox("Enable Whisper Notifications")
        self.whisper_notify_checkbox.setChecked(
            self.config.get("enable_whisper_notifications", True)
        )
        notifications_layout.addRow(QLabel(""), self.whisper_notify_checkbox)

        notifications_group.setLayout(notifications_layout)
        main_layout.addWidget(notifications_group)

        # Save, Cancel, and Default Buttons
        buttons_layout = QHBoxLayout()
        buttons_layout.addStretch()

        save_button = QPushButton("Save")
        save_button.clicked.connect(self.save_settings)
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)
        default_button = QPushButton("Default")
        default_button.clicked.connect(self.reset_to_default)
        buttons_layout.addWidget(default_button)
        buttons_layout.addWidget(save_button)
        buttons_layout.addWidget(cancel_button)

        main_layout.addLayout(buttons_layout)
        self.setLayout(main_layout)

    def select_color(self, category):
        """
        Opens a color dialog to allow the user to select a color for a specific
        chat category.

        Args:
            category (str): The chat category to customize.
        """
        color = QColorDialog.getColor()
        if color.isValid():
            self.chat_colors[category] = color.name()
            self.color_buttons[category].setStyleSheet(f"background-color: {color.name()}")

    def select_sound(self):
        """
        Opens a file dialog for the user to select a custom notification sound.
        The selected sound is copied to the application's directory.
        """
        options = QFileDialog.Options()
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Notification Sound",
            "",
            "Audio Files (*.wav *.mp3);;All Files (*)",
            options=options,
        )
        if file_path:
            # Update the notify_sound in config
            self.config["notify_sound"] = os.path.basename(file_path)
            # Copy the selected sound to the program directory
            try:
                dest_path = os.path.join(
                    os.path.dirname(os.path.abspath(__file__)), "notify.wav"
                )
                with open(file_path, "rb") as src, open(dest_path, "wb") as dst:
                    dst.write(src.read())
                QMessageBox.information(self, "Success", "Notification sound updated.")
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Failed to update sound: {e}")

    def save_settings(self):
        """
        Saves the user's settings to the configuration file and closes the dialog.
        """
        self.config["theme"] = self.theme_combo.currentText()
        self.config["font_size"] = self.font_spinbox.value()
        self.config["chat_colors"] = self.chat_colors
        self.config["enable_whisper_notifications"] = self.whisper_notify_checkbox.isChecked()

        # Save to config.json
        config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
        try:
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=4)
            QMessageBox.information(self, "Success", "Settings saved successfully.")
            self.accept()
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to save settings: {e}")

    def reset_to_default(self):
        """
        Resets the settings to their default values.
        """
        default_config = {
            "theme": "Dark",
            "font_size": 12,
            "chat_colors": {
                "Local": "green",
                "Global": "red",
                "Party": "blue",
                "Whisper": "purple",
                "Trade": "orange",
                "Guild": "grey",
                "System": "yellow",
            },
            "enable_whisper_notifications": True,
            "notify_sound": "notify.wav",
        }
        self.config.update(default_config)
        self.chat_colors = default_config["chat_colors"].copy()
        self.theme_combo.setCurrentText(default_config["theme"])
        self.font_spinbox.setValue(default_config["font_size"])
        self.whisper_notify_checkbox.setChecked(default_config["enable_whisper_notifications"])
        for category, button in self.color_buttons.items():
            button.setStyleSheet(f"background-color: {self.chat_colors[category]}")
        QMessageBox.information(self, "Default Settings", "Settings have been reset to default.")


class POEChatParserApp(QMainWindow):
    """
    Main application window for the Path of Exile Chat Notifier. It monitors
    the game's log file, displays chat messages, and provides notification
    functionalities based on user settings.
    """

    def __init__(self):
        super().__init__()

        # Load configuration settings
        self.load_config()

        # Initialize paths for resources
        program_dir = os.path.dirname(os.path.abspath(__file__))
        self.icon_path = os.path.join(program_dir, self.config.get("icon", "icon.ico"))
        self.tray_icon_path = os.path.join(
            program_dir, self.config.get("tray_icon", "icon_tray.ico")
        )
        self.notify_path = os.path.join(
            program_dir, self.config.get("notify_sound", "notify.wav")
        )

        # Configure window properties
        self.setWindowTitle("Chat Notifier")
        self.setGeometry(100, 100, 800, 300)
        self.setMinimumSize(600, 200)
        self.setWindowIcon(QIcon(self.icon_path))

        # Initialize flags and settings
        self.stop_flag = False
        self.minimize_to_tray = self.config.get("minimize_to_tray", False)
        self.file_path = self.get_poe_log_path()

        # Initialize ThreadPoolExecutor for background tasks
        self.executor = ThreadPoolExecutor(max_workers=4)

        # Initialize signal handlers for inter-thread communication
        self.signals = WorkerSignals()
        self.signals.log_line.connect(self.on_log_line)
        self.signals.system_line.connect(self.on_system_line)

        # Initialize message storage with deque for efficient FIFO
        # Changed to store (content, timestamp, channel, username, category)
        self.messages = deque(maxlen=self.config["message_limits"].get("Global", 100) + 100)

        # Initialize unread whispers count
        self.unread_whispers = 0

        # Setup UI components
        self.setup_menu()
        self.setup_central_widget()
        self.setup_tray_icon()

        # Apply the selected theme
        self.apply_theme(self.config.get("theme", "Dark"))

        # Start monitoring the log file if available
        if self.file_path and os.path.isfile(self.file_path):
            self.executor.submit(self.monitor_file, self.file_path)
        else:
            self.signals.system_line.emit("Path of Exile log file not found.", "red")

        # Setup configuration reload timer
        self.reload_timer = QTimer()
        self.reload_timer.timeout.connect(self.check_config_update)
        self.reload_timer.start(5000)  # Check every 5 seconds

        # Install event filter to handle window events
        self.installEventFilter(self)

    def load_config(self):
        """
        Loads configuration settings from an external JSON file. If loading
        fails, default settings are applied.
        """
        config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                self.config = json.load(f)
        except Exception as e:
            print(f"Failed to load config.json: {e}")
            # Default configuration if loading fails
            self.config = {
                "icon": "icon.ico",
                "tray_icon": "icon_tray.ico",
                "notify_sound": "notify.wav",
                "theme": "Dark",
                "font_size": 12,
                "chat_colors": {
                    "Local": "green",
                    "Global": "red",
                    "Party": "blue",
                    "Whisper": "purple",
                    "Trade": "orange",
                    "Guild": "grey",
                    "System": "yellow",
                },
                "ignored_users": [
                    "Delay",
                    "Connecting",
                    "Tile",
                    "Doodad",
                    "Height",
                    "Abnormal",
                    "Async",
                    "Abnormal disconnect",
                    "Height Map Texture",
                    "Async connecting to wdc01.login.pathofexile2.com",
                ],
                "message_limits": {
                    "Local": 100,
                    "Global": 100,
                    "Party": 100,
                    "Whisper": 200,
                    "Trade": 100,
                    "Guild": 100,
                    "System": 50,
                },
                "minimize_to_tray": False,
                "enable_whisper_notifications": True,
            }

    def setup_menu(self):
        """
        Creates the menu bar with File, Edit, and Help menus, including
        actions for exiting the application, toggling system tray minimization,
        accessing settings, and viewing about information.
        """
        menubar = self.menuBar()

        # File menu with Exit and Minimize to Tray options
        file_menu = menubar.addMenu("File")
        exit_action = QAction("Exit", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        minimize_action = QAction("Minimize to System Tray", self, checkable=True)
        minimize_action.setChecked(self.minimize_to_tray)
        minimize_action.triggered.connect(self.toggle_tray)
        file_menu.addAction(minimize_action)

        # Edit menu with Settings option
        edit_menu = menubar.addMenu("Edit")
        settings_action = QAction("Settings", self)
        settings_action.triggered.connect(self.open_settings)
        edit_menu.addAction(settings_action)

        # Help menu with About option
        help_menu = menubar.addMenu("Help")
        about_action = QAction("About", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)

    def setup_central_widget(self):
        """
        Configures the main content area with chat filters and the chat
        display console.
        """
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Initialize the chat display console
        self.console = QTextEdit()
        self.console.setReadOnly(True)
        self.console.setFont(QFont("Arial", self.config.get("font_size", 12)))

        # Define default states for channel filters (all enabled by default)
        self.channel_filters = {category: True for category in self.config["chat_colors"].keys()}

        # Create layout for filter buttons
        self.filter_layout = QHBoxLayout()
        self.filter_layout.setSpacing(5)
        self.filter_layout.setContentsMargins(0, 0, 0, 0)

        # Define uniform style for filter buttons
        button_style = """
            QPushButton {
                background-color: #3a3a3a;
                border: 1px solid #444444;
                padding: 5px 10px;
                margin: 0;
                color: white;
                border-radius: 4px;
            }
            QPushButton:checked {
                background-color: #666666;
            }
            QPushButton:hover {
                background-color: #555555;
            }
        """

        # Initialize and add filter buttons to the layout
        self.filter_buttons = {}
        for category in self.channel_filters.keys():
            btn = QPushButton(category)
            btn.setCheckable(True)
            btn.setChecked(True)
            btn.clicked.connect(self.channel_toggle_clicked)
            btn.setStyleSheet(button_style)
            btn.setCursor(Qt.PointingHandCursor)
            self.filter_buttons[category] = btn
            self.filter_layout.addWidget(btn)

        # Assemble the central layout
        layout = QVBoxLayout()
        layout.addLayout(self.filter_layout)
        layout.addWidget(self.console)
        central_widget.setLayout(layout)

    def setup_tray_icon(self):
        """
        Sets up the system tray icon with a context menu that allows the user
        to restore the application or exit.
        """
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(QIcon(self.tray_icon_path))
        tray_menu = QMenu()

        restore_action = QAction("Restore", self)
        restore_action.triggered.connect(self.restore_from_tray)
        tray_menu.addAction(restore_action)

        exit_tray_action = QAction("Exit", self)
        exit_tray_action.triggered.connect(self.close)
        tray_menu.addAction(exit_tray_action)

        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self.tray_icon_activated)
        if self.minimize_to_tray:
            self.tray_icon.show()

    def tray_icon_activated(self, reason):
        """
        Handles activation events for the system tray icon, restoring the
        application window on a double-click.
        """
        if reason == QSystemTrayIcon.DoubleClick:
            self.restore_from_tray()

    def get_poe_log_path(self):
        """
        Determines the Path of Exile log file path by inspecting running processes.

        Returns:
            str or None: The path to the Client.txt log file if the game is running,
                         otherwise None.
        """
        for proc in psutil.process_iter(["name", "exe"]):
            if proc.info["name"] and proc.info["name"].lower().startswith("pathofexile"):
                poe_exe = proc.info["exe"]
                return os.path.join(os.path.dirname(poe_exe), "logs", "Client.txt")
        return None

    def toggle_tray(self, checked):
        """
        Enables or disables minimizing the application to the system tray based
        on the user's preference.

        Args:
            checked (bool): True to enable minimizing to tray, False to disable.
        """
        self.minimize_to_tray = checked
        self.config["minimize_to_tray"] = checked
        self.save_config()
        if checked and self.isMinimized():
            self.tray_icon.show()
        elif not checked:
            self.tray_icon.hide()

    def open_settings(self):
        """
        Opens the settings dialog, allowing the user to customize application
        preferences. After saving, updates the UI accordingly without clearing
        existing messages.
        """
        dialog = SettingsDialog(
            self,
            config=self.config.copy(),
            chat_colors=self.config["chat_colors"].copy(),
        )
        if dialog.exec_():
            # Reload configuration after settings are saved
            self.load_config()
            self.apply_theme(self.config.get("theme", "Dark"))
            # Update font size
            self.console.setFont(QFont("Arial", self.config.get("font_size", 12)))
            # Update chat colors
            self.config["chat_colors"] = dialog.chat_colors
            # Recreate filter buttons with uniform styles
            for category, button in self.filter_buttons.items():
                button.setStyleSheet(self.get_button_style())
            # Refresh message display
            self.display_messages()
            # Update tray icon in case it was changed
            self.tray_icon.setIcon(QIcon(self.tray_icon_path))
            # Update minimize to tray based on new settings
            if self.minimize_to_tray:
                self.tray_icon.show()
            else:
                self.tray_icon.hide()

    def get_button_style(self):
        """
        Returns a uniform stylesheet for all filter buttons to maintain a
        consistent appearance.

        Returns:
            str: The stylesheet string for filter buttons.
        """
        return """
            QPushButton {
                background-color: #3a3a3a;
                border: 1px solid #444444;
                padding: 5px 10px;
                margin: 0;
                color: white;
                border-radius: 4px;
            }
            QPushButton:checked {
                background-color: #666666;
            }
            QPushButton:hover {
                background-color: #555555;
            }
        """

    def apply_theme(self, theme):
        """
        Applies the selected theme to the application, adjusting the palette
        and styles accordingly.

        Args:
            theme (str): The selected theme, either "Dark" or "Light".
        """
        if theme == "Dark":
            palette = QPalette()
            palette.setColor(QPalette.Window, QColor(53, 53, 53))
            palette.setColor(QPalette.WindowText, Qt.white)
            palette.setColor(QPalette.Base, QColor(25, 25, 25))
            palette.setColor(QPalette.AlternateBase, QColor(53, 53, 53))
            palette.setColor(QPalette.ToolTipBase, Qt.white)
            palette.setColor(QPalette.ToolTipText, Qt.white)
            palette.setColor(QPalette.Text, Qt.white)
            palette.setColor(QPalette.Button, QColor(53, 53, 53))
            palette.setColor(QPalette.ButtonText, Qt.white)
            palette.setColor(QPalette.BrightText, Qt.red)
            palette.setColor(QPalette.Link, QColor(42, 130, 218))
            palette.setColor(QPalette.Highlight, QColor(42, 130, 218))
            palette.setColor(QPalette.HighlightedText, Qt.black)
            self.setPalette(palette)
        else:  # Light theme
            palette = QPalette()
            palette.setColor(QPalette.Window, Qt.white)
            palette.setColor(QPalette.WindowText, Qt.black)
            palette.setColor(QPalette.Base, QColor(240, 240, 240))
            palette.setColor(QPalette.AlternateBase, QColor(225, 225, 225))
            palette.setColor(QPalette.ToolTipBase, Qt.black)
            palette.setColor(QPalette.ToolTipText, Qt.black)
            palette.setColor(QPalette.Text, Qt.black)
            palette.setColor(QPalette.Button, QColor(225, 225, 225))
            palette.setColor(QPalette.ButtonText, Qt.black)
            palette.setColor(QPalette.BrightText, Qt.red)
            palette.setColor(QPalette.Link, QColor(0, 0, 255))
            palette.setColor(QPalette.Highlight, QColor(0, 120, 215))
            palette.setColor(QPalette.HighlightedText, Qt.white)
            self.setPalette(palette)

        # Adjust console styles based on theme
        if theme == "Dark":
            self.console.setStyleSheet("QTextEdit { background-color: #191919; color: white; }")
        else:
            self.console.setStyleSheet("QTextEdit { background-color: white; color: black; }")

    def on_log_line(self, content, timestamp, channel, username, category):
        """
        Processes and stores a new log line from the game, then updates the
        chat display.

        Args:
            content (str): The message content.
            timestamp (str): The timestamp of the message.
            channel (str): The chat channel.
            username (str): The username of the sender.
            category (str): The chat category.
        """
        self.messages.append((content, timestamp, channel, username, category))
        self.display_messages()

    def on_system_line(self, msg, color):
        """
        Handles system-generated messages by storing them and updating the
        chat display.

        Args:
            msg (str): The system message.
            color (str): The color associated with system messages.
        """
        category = "System"
        self.messages.append((msg, None, None, None, category))
        self.display_messages()

    def log_to_console(
        self, message, timestamp=None, channel=None, username=None, category=None
    ):
        """
        Formats and inserts a message into the console display.

        Args:
            message (str): The message content.
            timestamp (str, optional): The timestamp of the message.
            channel (str, optional): The chat channel.
            username (str, optional): The username of the sender.
            category (str, optional): The chat category.
        """
        color = self.config["chat_colors"].get(category, "white")
        html = ""
        if timestamp:
            html += f'<span style="color:{color}">[{timestamp}] </span>'
        if channel and username:
            html += f'<span style="color:{color}">{channel}{username}: </span>'
        elif username:
            html += f'<span style="color:{color}">{username}: </span>'
        html += f'<span style="color:{self.get_console_text_color()}">{message}</span><br>'
        self.console.insertHtml(html)
        self.console.moveCursor(QTextCursor.End)

    def get_console_text_color(self):
        """
        Determines the text color for the console based on the current theme.

        Returns:
            str: The color name ("white" for Dark theme, "black" for Light theme).
        """
        if self.config.get("theme", "Dark") == "Dark":
            return "white"
        else:
            return "black"

    def display_messages(self):
        """
        Refreshes the console display based on current messages and active
        channel filters. This method ensures that chat colors reflect the latest
        settings.
        """
        self.console.blockSignals(True)
        self.console.clear()
        for content, timestamp, channel, username, category in self.messages:
            if username and username in self.config["ignored_users"]:
                continue
            if category is None or self.channel_filters.get(category, True):
                self.log_to_console(
                    content,
                    timestamp=timestamp,
                    channel=channel,
                    username=username,
                    category=category,
                )
        self.console.blockSignals(False)
        self.update_title()

    def channel_toggle_clicked(self):
        """
        Updates filter settings when a channel filter button is toggled,
        then refreshes the chat display accordingly.
        """
        for category, button in self.filter_buttons.items():
            self.channel_filters[category] = button.isChecked()
        self.display_messages()

    def monitor_file(self, file_path):
        """
        Continuously monitors the log file for new entries, processing each
        new line as it arrives.

        Args:
            file_path (str): The path to the Path of Exile Client.txt log file.
        """
        try:
            with open(file_path, "r", encoding="utf-8") as file:
                file.seek(0, os.SEEK_END)  # Move to the end of the file
                while not self.stop_flag:
                    line = file.readline()
                    if line:
                        self.executor.submit(self.process_line, line.strip())
                    else:
                        time.sleep(0.1)  # Sleep briefly to reduce CPU usage
        except Exception as e:
            self.signals.system_line.emit(f"Error: {e}", "red")

    def process_line(self, line):
        """
        Parses and processes a single line from the log file, emitting signals
        for valid messages.

        Args:
            line (str): A single line from the log file.
        """
        try:
            timestamp = self.extract_timestamp(line)
            message = self.extract_message(line)
            parsed = self.parse_message(message)
            if not parsed:
                return
            channel, username, content, category = parsed

            if username and username in self.config["ignored_users"]:
                return

            # Only trigger notifications for "@From " whisper messages
            if category == "Whisper" and channel.strip().startswith("@From"):
                self.unread_whispers += 1
                if self.config.get("enable_whisper_notifications", True):
                    self.executor.submit(self.play_notify)
                    if self.isMinimized():
                        QApplication.alert(self)

            self.signals.log_line.emit(
                content,
                timestamp,
                channel,
                username,
                category,
            )
        except Exception as e:
            self.signals.system_line.emit(f"Error processing line: {e}", "yellow")

    def extract_timestamp(self, line):
        """
        Extracts the timestamp from a log line.

        Args:
            line (str): A single line from the log file.

        Returns:
            str: The extracted timestamp.
        """
        time_start = line.find(" ") + 1
        time_end = line.find(" ", time_start)
        return line[time_start:time_end][:5]

    def extract_message(self, line):
        """
        Extracts the message content from a log line.

        Args:
            line (str): A single line from the log file.

        Returns:
            str: The extracted message content.
        """
        message_start = line.rfind("] ") + 2
        return line[message_start:].strip()

    def play_notify(self):
        """
        Plays the notification sound if the file exists.
        """
        if os.path.isfile(self.notify_path):
            playsound(self.notify_path)

    def parse_message(self, message):
        """
        Analyzes a message to determine its category and relevant details.

        Args:
            message (str): The message content.

        Returns:
            tuple or None: A tuple containing channel, username, content, and category
                           if the message is valid, otherwise None.
        """
        if ":" not in message:
            return None

        username_part, content = message.split(":", 1)
        username_part = username_part.strip()

        # Normalize channel symbols by reducing multiple symbols to one
        if message.startswith("##"):
            channel = "#"
            category = "Global"
        elif message.startswith("$$"):
            channel = "$"
            category = "Trade"
        elif message.startswith("#"):
            channel = "#"
            category = "Global"
        elif message.startswith("$"):
            channel = "$"
            category = "Trade"
        elif message.startswith("&"):
            channel = "&"
            category = "Guild"
        elif message.startswith("%"):
            channel = "%"
            category = "Party"
        elif message.startswith("@From "):
            channel = "@From "
            category = "Whisper"
        elif message.startswith("@To "):
            channel = "@To "
            category = "Whisper"
        elif message.startswith("System:"):
            channel = "System"
            category = "System"
        else:
            channel = ""
            category = "Local"

        # Remove channel symbol from username
        if category == "System":
            username = None
        elif category == "Whisper":
            username = username_part[len(channel):].strip()
        else:
            # For "Global", "Trade", "Guild", "Party", "Local"
            # Remove only the leading channel symbol(s)
            username = username_part.lstrip(channel).strip()

        return channel, username, content.strip(), category

    def show_about(self):
        """
        Displays the About dialog with application information.
        """
        QMessageBox.about(
            self,
            "About",
            "<div style='text-align:center;'>Chat Notifier<br>Version 0.4</div>",
        )

    def restore_from_tray(self):
        """
        Restores the application window from the system tray.
        """
        self.showNormal()
        self.activateWindow()
        self.tray_icon.hide()
        self.unread_whispers = 0
        self.update_title()

    def changeEvent(self, event):
        """
        Handles changes in window state, such as minimizing, to manage system
        tray visibility and unread whispers count.

        Args:
            event (QEvent): The event object.
        """
        if event.type() == QEvent.WindowStateChange:
            if self.minimize_to_tray and self.isMinimized():
                self.hide()
                self.tray_icon.show()
            elif not self.minimize_to_tray and self.isMinimized():
                self.tray_icon.hide()
        elif event.type() == QEvent.ActivationChange:
            if self.isActiveWindow() and self.unread_whispers > 0:
                self.unread_whispers = 0
                self.update_title()
        super().changeEvent(event)

    def update_title(self):
        """
        Updates the window title to reflect the number of unread whispers.
        """
        if self.unread_whispers > 0:
            self.setWindowTitle(f"Chat Notifier ({self.unread_whispers})")
        else:
            self.setWindowTitle("Chat Notifier")

    def reload_config(self):
        """
        Reloads the configuration from the config file and updates the UI
        accordingly without clearing existing messages.
        """
        self.load_config()
        self.apply_theme(self.config.get("theme", "Dark"))
        self.channel_filters = {category: True for category in self.config["chat_colors"].keys()}
        for btn in self.filter_buttons.values():
            btn.setChecked(True)
        # Update font size
        self.console.setFont(QFont("Arial", self.config.get("font_size", 12)))
        # Update chat colors
        self.config["chat_colors"] = self.config.get("chat_colors", {})
        # Recreate filter buttons with uniform styles
        for category, button in self.filter_buttons.items():
            button.setStyleSheet(self.get_button_style())
        # Refresh message display
        self.display_messages()
        # Update tray icon in case it was changed
        self.tray_icon.setIcon(QIcon(self.tray_icon_path))
        # Update minimize to tray based on new settings
        if self.minimize_to_tray:
            self.tray_icon.show()
        else:
            self.tray_icon.hide()

    def check_config_update(self):
        """
        Checks if the configuration file has been updated and reloads it.
        Placeholder for future implementation.
        """
        pass  # Implement dynamic config reloading if needed

    def save_config(self):
        """
        Saves the current configuration to the config file.
        """
        config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
        try:
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=4)
        except Exception as e:
            self.signals.system_line.emit(f"Failed to save config: {e}", "red")

    def closeEvent(self, event):
        """
        Handles the application close event to ensure a graceful shutdown by
        stopping background threads.

        Args:
            event (QCloseEvent): The close event object.
        """
        self.stop_flag = True
        self.executor.shutdown(wait=False)
        event.accept()


def main():
    """
    Initializes and runs the application.
    """
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    program_dir = os.path.dirname(os.path.abspath(__file__))
    icon_path = os.path.join(program_dir, "icon.ico")
    app.setWindowIcon(QIcon(icon_path))

    # Instantiate and display the main application window
    window = POEChatParserApp()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
