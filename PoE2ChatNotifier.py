import sys
import os
import time
import psutil
import configparser
import ast
from collections import deque
from concurrent.futures import ThreadPoolExecutor
import subprocess
from appdirs import user_data_dir

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QAction, QTextEdit,
    QPushButton, QHBoxLayout, QMessageBox, QSystemTrayIcon, QMenu,
    QFileDialog, QColorDialog, QDialog, QLabel, QComboBox,
    QSpinBox, QFormLayout, QGroupBox, QCheckBox, QSlider
)
from PyQt5.QtCore import pyqtSignal, Qt, QObject, QEvent
from PyQt5.QtGui import QPalette, QColor, QIcon, QTextCursor, QFont


class WorkerSignals(QObject):
    log_line = pyqtSignal(str, str, str, str, str)
    system_line = pyqtSignal(str, str)


class SettingsDialog(QDialog):
    def __init__(self, parent=None, config=None, chat_colors=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.config = config
        self.chat_colors = chat_colors
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout()

        appearance_group = QGroupBox("Appearance")
        appearance_layout = QFormLayout()
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["Dark", "Light"])
        current_theme = self.config.get("theme", "Dark")
        idx = self.theme_combo.findText(current_theme)
        if idx >= 0:
            self.theme_combo.setCurrentIndex(idx)
        self.theme_combo.currentIndexChanged.connect(self.on_theme_changed)

        self.font_spinbox = QSpinBox()
        self.font_spinbox.setRange(8, 48)
        self.font_spinbox.setValue(int(self.config.get("font_size", "12")))
        self.font_spinbox.valueChanged.connect(self.on_font_changed)

        appearance_layout.addRow(QLabel("Theme:"), self.theme_combo)
        appearance_layout.addRow(QLabel("Font Size:"), self.font_spinbox)
        appearance_group.setLayout(appearance_layout)
        main_layout.addWidget(appearance_group)

        colors_group = QGroupBox("Chat Colors")
        colors_layout = QFormLayout()
        self.color_buttons = {}
        for cat, col in self.chat_colors.items():
            b = QPushButton()
            b.setStyleSheet(f"background-color: {col}")
            b.setFixedWidth(50)
            b.clicked.connect(lambda _, c=cat: self.select_color(c))
            self.color_buttons[cat] = b
            colors_layout.addRow(QLabel(f"{cat}:"), b)
        colors_group.setLayout(colors_layout)
        main_layout.addWidget(colors_group)

        notifications_group = QGroupBox("Notifications")
        notifications_layout = QFormLayout()
        self.sound_button = QPushButton("Select Sound")
        self.sound_button.clicked.connect(self.select_sound)
        notifications_layout.addRow(QLabel("Sound:"), self.sound_button)

        self.whisper_notify_checkbox = QCheckBox("Enable Whisper Notifications")
        en = self.config.get("enable_whisper_notifications", "True")
        self.whisper_notify_checkbox.setChecked(en == "True")
        self.whisper_notify_checkbox.stateChanged.connect(self.on_whisper_notify_changed)
        notifications_layout.addRow(QLabel(""), self.whisper_notify_checkbox)

        vol_layout = QHBoxLayout()
        self.volume_slider = QSlider(Qt.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(int(self.config.get("notify_volume", "100")))
        self.volume_slider.valueChanged.connect(self.on_volume_changed)

        self.test_button = QPushButton("Test")
        self.test_button.clicked.connect(self.test_notification)
        vol_layout.addWidget(self.volume_slider)
        vol_layout.addWidget(self.test_button)
        notifications_layout.addRow(QLabel("Volume:"), vol_layout)
        notifications_group.setLayout(notifications_layout)
        main_layout.addWidget(notifications_group)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        default_btn = QPushButton("Default")
        default_btn.clicked.connect(self.reset_to_default)
        btn_layout.addWidget(default_btn)
        main_layout.addLayout(btn_layout)

        self.setLayout(main_layout)

    def on_theme_changed(self):
        if self.parent():
            th = self.theme_combo.currentText()
            self.parent().config["theme"] = th
            self.parent().save_config()
            self.parent().apply_theme(th)
            self.parent().display_messages()

    def on_font_changed(self, val):
        if self.parent():
            self.parent().config["font_size"] = str(val)
            self.parent().save_config()
            self.parent().console.setFont(QFont("Arial", val))
            self.parent().display_messages()

    def on_whisper_notify_changed(self, st):
        if self.parent():
            enabled = (st == Qt.Checked)
            self.parent().config["enable_whisper_notifications"] = "True" if enabled else "False"
            self.parent().save_config()

    def on_volume_changed(self, val):
        if self.parent():
            self.parent().config["notify_volume"] = str(val)
            self.parent().save_config()

    def select_color(self, category):
        c = QColorDialog.getColor()
        if c.isValid():
            self.chat_colors[category] = c.name()
            self.color_buttons[category].setStyleSheet(f"background-color: {c.name()}")
            if self.parent():
                self.parent().config["chat_colors"] = self.chat_colors
                self.parent().save_config()
                self.parent().display_messages()

    def select_sound(self):
        opts = QFileDialog.Options()
        fp, _ = QFileDialog.getOpenFileName(
            self, "Select Sound", "", "Audio Files (*.wav *.mp3);;All Files (*)", options=opts
        )
        if fp:
            snd = os.path.basename(fp)
            self.config["notify_sound"] = f"bin/{snd}"
            try:
                dest = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bin", snd)
                with open(fp, "rb") as s, open(dest, "wb") as d:
                    d.write(s.read())
                if self.parent():
                    self.parent().config["notify_sound"] = f"bin/{snd}"
                    self.parent().save_config()
                    self.parent().notify_path = os.path.join(self.parent().program_dir, f"bin/{snd}")
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Failed to update sound: {e}")

    def test_notification(self):
        if self.parent() and hasattr(self.parent(), "simulate_whisper"):
            self.parent().simulate_whisper("CynicaGaming", "Test whisper from CynicaGaming!")

    def reset_to_default(self):
        df = {
            "notify_sound": "bin/notify.wav",
            "theme": "Dark",
            "font_size": "12",
            "chat_colors": {
                "Local": "green",
                "Global": "red",
                "Party": "blue",
                "Whisper": "purple",
                "Trade": "orange",
                "Guild": "grey",
                "System": "yellow",
            },
            "enable_whisper_notifications": "True",
            "notify_volume": "100",
        }
        self.config.update(df)
        self.chat_colors = df["chat_colors"].copy()
        if self.parent():
            for k, v in df.items():
                self.parent().config[k] = v if isinstance(v, dict) else str(v)
            self.parent().save_config()
            self.parent().notify_path = os.path.join(self.parent().program_dir, df["notify_sound"])
            self.parent().apply_theme(df["theme"])
            self.parent().console.setFont(QFont("Arial", int(df["font_size"])))
            self.parent().display_messages()

        self.theme_combo.setCurrentText(df["theme"])
        self.font_spinbox.setValue(int(df["font_size"]))
        self.whisper_notify_checkbox.setChecked(True)
        self.volume_slider.setValue(int(df["notify_volume"]))
        for c, b in self.color_buttons.items():
            b.setStyleSheet(f"background-color: {self.chat_colors[c]}")


class POEChatParserApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.config = {}
        self.stop_flag = False
        self.load_config()

        self.program_dir = os.path.dirname(os.path.abspath(__file__))
        self.icon_path = os.path.join(self.program_dir, "bin", "icon.ico")
        self.tray_icon_path = os.path.join(self.program_dir, "bin", "icon_tray.ico")

        snd = self.config.get("notify_sound", "bin/notify.wav")
        if not snd.startswith("bin/"):
            snd = "bin/" + snd
        self.notify_path = os.path.join(self.program_dir, snd)

        self.setWindowTitle("Chat Notifier")
        self.setGeometry(100, 100, 800, 300)
        self.setMinimumSize(600, 200)
        self.setWindowIcon(QIcon(self.icon_path))

        tray_str = self.config.get("minimize_to_tray", "False")
        self.minimize_to_tray = (tray_str == "True")
        self.file_path = self.get_poe_log_path()

        self.executor = ThreadPoolExecutor(max_workers=4)
        self.signals = WorkerSignals()
        self.signals.log_line.connect(self.on_log_line)
        self.signals.system_line.connect(self.on_system_line)

        self.messages = deque(maxlen=200)
        self.unread_whispers = 0

        self.setup_menu()
        self.setup_central_widget()
        self.setup_tray_icon()
        self.apply_theme(self.config.get("theme", "Dark"))

        if self.file_path and os.path.isfile(self.file_path):
            self.executor.submit(self.monitor_file, self.file_path)
        else:
            self.signals.system_line.emit("Path of Exile log file not found.", "red")

        self.installEventFilter(self)

    def load_config(self):
        data_dir = user_data_dir("PoEChatNotifier", "MyCompany", roaming=True)
        os.makedirs(data_dir, exist_ok=True)
        cfg_path = os.path.join(data_dir, "config.ini")

        parser = configparser.ConfigParser()
        if os.path.isfile(cfg_path):
            parser.read(cfg_path)
            if "Settings" in parser:
                for k, v in parser["Settings"].items():
                    if k == "chat_colors":
                        try:
                            self.config[k] = ast.literal_eval(v)
                        except:
                            self.config[k] = {
                                "Local": "green",
                                "Global": "red",
                                "Party": "blue",
                                "Whisper": "purple",
                                "Trade": "orange",
                                "Guild": "grey",
                                "System": "yellow",
                            }
                    else:
                        self.config[k] = v
        else:
            self.config = {
                "notify_sound": "bin/notify.wav",
                "theme": "Dark",
                "font_size": "12",
                "chat_colors": str({
                    "Local": "green",
                    "Global": "red",
                    "Party": "blue",
                    "Whisper": "purple",
                    "Trade": "orange",
                    "Guild": "grey",
                    "System": "yellow",
                }),
                "enable_whisper_notifications": "True",
                "notify_volume": "100",
                "minimize_to_tray": "False",
            }

    def save_config(self):
        data_dir = user_data_dir("PoEChatNotifier", "MyCompany", roaming=True)
        os.makedirs(data_dir, exist_ok=True)
        cfg_path = os.path.join(data_dir, "config.ini")

        parser = configparser.ConfigParser()
        parser["Settings"] = {}
        for k, v in self.config.items():
            if isinstance(v, dict):
                parser["Settings"][k] = str(v)
            else:
                parser["Settings"][k] = str(v)
        with open(cfg_path, "w", encoding="utf-8") as f:
            parser.write(f)

    def get_poe_log_path(self):
        for proc in psutil.process_iter(["name", "exe"]):
            if proc.info["name"] and proc.info["name"].lower().startswith("pathofexile"):
                return os.path.join(os.path.dirname(proc.info["exe"]), "logs", "Client.txt")
        return None

    def setup_menu(self):
        mb = self.menuBar()
        fm = mb.addMenu("File")
        ex_act = QAction("Exit", self)
        ex_act.triggered.connect(self.close)
        fm.addAction(ex_act)

        tray_act = QAction("Minimize to System Tray", self, checkable=True)
        tray_act.setChecked(self.minimize_to_tray)
        tray_act.triggered.connect(self.toggle_tray)
        fm.addAction(tray_act)

        em = mb.addMenu("Edit")
        st_act = QAction("Settings", self)
        st_act.triggered.connect(self.open_settings)
        em.addAction(st_act)

        hm = mb.addMenu("Help")
        ab_act = QAction("About", self)
        ab_act.triggered.connect(self.show_about)
        hm.addAction(ab_act)

    def setup_central_widget(self):
        cw = QWidget()
        self.setCentralWidget(cw)
        self.console = QTextEdit()
        self.console.setReadOnly(True)
        self.console.setFont(QFont("Arial", int(self.config.get("font_size", "12"))))

        if isinstance(self.config.get("chat_colors"), str):
            try:
                self.config["chat_colors"] = ast.literal_eval(self.config["chat_colors"])
            except:
                self.config["chat_colors"] = {
                    "Local": "green",
                    "Global": "red",
                    "Party": "blue",
                    "Whisper": "purple",
                    "Trade": "orange",
                    "Guild": "grey",
                    "System": "yellow",
                }

        self.channel_filters = {}
        for cat in self.config["chat_colors"].keys():
            self.channel_filters[cat] = True

        self.filter_layout = QHBoxLayout()
        self.filter_layout.setSpacing(5)
        self.filter_layout.setContentsMargins(0, 0, 0, 0)

        btn_style = """
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
        self.filter_buttons = {}
        for c in self.config["chat_colors"].keys():
            b = QPushButton(c)
            b.setCheckable(True)
            b.setChecked(True)
            b.setStyleSheet(btn_style)
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(self.channel_toggle_clicked)
            self.filter_buttons[c] = b
            self.filter_layout.addWidget(b)

        layout = QVBoxLayout()
        layout.addLayout(self.filter_layout)
        layout.addWidget(self.console)
        cw.setLayout(layout)

    def setup_tray_icon(self):
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(QIcon(self.tray_icon_path))
        tray_menu = QMenu()
        restore_act = QAction("Restore", self)
        restore_act.triggered.connect(self.restore_from_tray)
        tray_menu.addAction(restore_act)

        exit_act = QAction("Exit", self)
        exit_act.triggered.connect(self.close)
        tray_menu.addAction(exit_act)

        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self.tray_icon_activated)
        if self.minimize_to_tray:
            self.tray_icon.show()

    def tray_icon_activated(self, reason):
        if reason == QSystemTrayIcon.DoubleClick:
            self.restore_from_tray()

    def toggle_tray(self, checked):
        self.minimize_to_tray = checked
        self.config["minimize_to_tray"] = "True" if checked else "False"
        self.save_config()
        if checked and self.isMinimized():
            self.tray_icon.show()
        elif not checked:
            self.tray_icon.hide()

    def open_settings(self):
        d = SettingsDialog(self, config=self.config, chat_colors=self.config["chat_colors"])
        d.exec_()

    def apply_theme(self, theme):
        if theme == "Dark":
            pal = QPalette()
            pal.setColor(QPalette.Window, QColor(53, 53, 53))
            pal.setColor(QPalette.WindowText, Qt.white)
            pal.setColor(QPalette.Base, QColor(25, 25, 25))
            pal.setColor(QPalette.AlternateBase, QColor(53, 53, 53))
            pal.setColor(QPalette.ToolTipBase, Qt.white)
            pal.setColor(QPalette.ToolTipText, Qt.white)
            pal.setColor(QPalette.Text, Qt.white)
            pal.setColor(QPalette.Button, QColor(53, 53, 53))
            pal.setColor(QPalette.ButtonText, Qt.white)
            pal.setColor(QPalette.BrightText, Qt.red)
            pal.setColor(QPalette.Link, QColor(42, 130, 218))
            pal.setColor(QPalette.Highlight, QColor(42, 130, 218))
            pal.setColor(QPalette.HighlightedText, Qt.black)
            self.setPalette(pal)
            self.console.setStyleSheet("QTextEdit { background-color: #191919; color: white; }")
        else:
            pal = QPalette()
            pal.setColor(QPalette.Window, Qt.white)
            pal.setColor(QPalette.WindowText, Qt.black)
            pal.setColor(QPalette.Base, QColor(240, 240, 240))
            pal.setColor(QPalette.AlternateBase, QColor(225, 225, 225))
            pal.setColor(QPalette.ToolTipBase, Qt.black)
            pal.setColor(QPalette.ToolTipText, Qt.black)
            pal.setColor(QPalette.Text, Qt.black)
            pal.setColor(QPalette.Button, QColor(225, 225, 225))
            pal.setColor(QPalette.ButtonText, Qt.black)
            pal.setColor(QPalette.BrightText, Qt.red)
            pal.setColor(QPalette.Link, QColor(0, 0, 255))
            pal.setColor(QPalette.Highlight, QColor(0, 120, 215))
            pal.setColor(QPalette.HighlightedText, Qt.white)
            self.setPalette(pal)
            self.console.setStyleSheet("QTextEdit { background-color: white; color: black; }")

    def on_log_line(self, content, timestamp, channel, username, category):
        self.messages.append((content, timestamp, channel, username, category))
        self.display_messages()

    def on_system_line(self, msg, color):
        cat = "System"
        self.messages.append((msg, None, None, None, cat))
        self.display_messages()

    def log_to_console(self, content, timestamp=None, channel=None, username=None, category=None):
        theme = self.config.get("theme", "Dark")
        text_color = "white" if theme == "Dark" else "black"
        col = self.config["chat_colors"].get(category, "white")
        h = ""
        if timestamp:
            h += f'<span style="color:{col}">[{timestamp}] </span>'
        if channel and username:
            h += f'<span style="color:{col}">{channel}{username}: </span>'
        elif username:
            h += f'<span style="color:{col}">{username}: </span>'
        h += f'<span style="color:{text_color}">{content}</span><br>'
        self.console.insertHtml(h)
        self.console.moveCursor(QTextCursor.End)

    def display_messages(self):
        self.console.blockSignals(True)
        self.console.clear()
        for c, t, ch, u, cat in self.messages:
            if cat is None or self.channel_filters.get(cat, True):
                self.log_to_console(c, t, ch, u, cat)
        self.console.blockSignals(False)
        self.update_title()

    def channel_toggle_clicked(self):
        for cat, b in self.filter_buttons.items():
            self.channel_filters[cat] = b.isChecked()
        self.display_messages()

    def monitor_file(self, path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                f.seek(0, os.SEEK_END)
                while not self.stop_flag:
                    line = f.readline()
                    if line:
                        self.executor.submit(self.process_line, line.strip())
                    else:
                        time.sleep(0.1)
        except Exception as e:
            self.signals.system_line.emit(f"Error: {e}", "red")

    def process_line(self, line):
        try:
            ts = self.extract_timestamp(line)
            msg = self.extract_message(line)
            parsed = self.parse_message(msg)
            if not parsed:
                return
            ch, user, cont, cat = parsed
            if cat == "Whisper" and ch.strip().startswith("@From"):
                self.unread_whispers += 1
                en = self.config.get("enable_whisper_notifications", "True")
                if en == "True":
                    self.executor.submit(self.play_notify)
                    if self.isMinimized():
                        QApplication.alert(self)
            self.signals.log_line.emit(cont, ts, ch, user, cat)
        except Exception as ex:
            self.signals.system_line.emit(f"Error processing line: {ex}", "red")

    def extract_timestamp(self, line):
        s = line.find(" ") + 1
        e = line.find(" ", s)
        return line[s:e][:5]

    def extract_message(self, line):
        ms = line.rfind("] ") + 2
        return line[ms:].strip()

    def play_notify(self):
        v = self.config.get("notify_volume", "100")
        vol_int = int(v)
        ffplay_vol = min(max(int(vol_int * 2.56), 0), 256)
        if os.path.isfile(self.notify_path):
            try:
                ffplay = os.path.join(self.program_dir, "bin", "ffplay.exe")
                startupinfo = None
                creationflags = 0
                if os.name == "nt":
                    startupinfo = subprocess.STARTUPINFO()
                    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                    creationflags = subprocess.CREATE_NO_WINDOW

                subprocess.run(
                    [
                        ffplay, "-nodisp", "-autoexit", "-loglevel", "quiet",
                        "-volume", str(ffplay_vol), self.notify_path
                    ],
                    shell=False,
                    startupinfo=startupinfo,
                    creationflags=creationflags
                )
            except Exception as e:
                self.signals.system_line.emit(f"Failed to play sound: {e}", "red")
        else:
            self.signals.system_line.emit(f"Sound not found: {self.notify_path}", "red")

    def simulate_whisper(self, username, message):
        t = time.strftime("%H:%M", time.localtime())
        ch = "@From "
        cat = "Whisper"
        self.signals.log_line.emit(message, t, ch, username, cat)
        en = self.config.get("enable_whisper_notifications", "True")
        if en == "True":
            self.executor.submit(self.play_notify)
            if self.isMinimized():
                QApplication.alert(self)

    def parse_message(self, msg):
        if ":" not in msg:
            return None
        up, cont = msg.split(":", 1)
        up = up.strip()
        if msg.startswith("##"):
            c = "#"; cat = "Global"
        elif msg.startswith("$$"):
            c = "$"; cat = "Trade"
        elif msg.startswith("#"):
            c = "#"; cat = "Global"
        elif msg.startswith("$"):
            c = "$"; cat = "Trade"
        elif msg.startswith("&"):
            c = "&"; cat = "Guild"
        elif msg.startswith("%"):
            c = "%"; cat = "Party"
        elif msg.startswith("@From "):
            c = "@From "; cat = "Whisper"
        elif msg.startswith("@To "):
            c = "@To "; cat = "Whisper"
        elif msg.startswith("System:"):
            c = "System"; cat = "System"
        else:
            c = ""; cat = "Local"
        user = up[len(c):].strip()
        return c, user, cont.strip(), cat

    def show_about(self):
        QMessageBox.about(self, "About", "<div style='text-align:center;'>Chat Notifier<br>Version 1.0</div>")

    def restore_from_tray(self):
        self.showNormal()
        self.activateWindow()
        self.tray_icon.hide()
        self.unread_whispers = 0
        self.update_title()

    def changeEvent(self, event):
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
        if self.unread_whispers > 0:
            self.setWindowTitle(f"Chat Notifier ({self.unread_whispers})")
        else:
            self.setWindowTitle("Chat Notifier")

    def closeEvent(self, event):
        self.stop_flag = True
        self.executor.shutdown(wait=False)
        event.accept()


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    prog_dir = os.path.dirname(os.path.abspath(__file__))
    icn = os.path.join(prog_dir, "bin", "icon.ico")
    app.setWindowIcon(QIcon(icn))

    w = POEChatParserApp()
    w.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
