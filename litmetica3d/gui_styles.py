"""Qt styles used by the v0.5 desktop interface."""

DARK_STYLE = r"""
QWidget {
    background: #0b0f17;
    color: #e8edf5;
    font-family: "Segoe UI", "Microsoft YaHei UI";
    font-size: 14px;
}
QMainWindow { background: #0b0f17; }
#Sidebar { background: #101622; border-right: 1px solid #202a3a; }
#Brand { color: #f7fbff; font-size: 18px; font-weight: 800; letter-spacing: 1px; }
#PageTitle { font-size: 25px; font-weight: 750; color: #f6f9fe; }
#HeroTitle { font-size: 23px; font-weight: 750; color: #ffffff; }
#CardTitle { font-size: 17px; font-weight: 700; color: #f3f7fd; }
#ActivityTitle { font-size: 22px; font-weight: 750; }
#Muted { color: #8d9aaf; }
#AccentText { color: #52e0bd; font-size: 12px; font-weight: 700; letter-spacing: 1px; }
#FieldLabel { color: #aeb9ca; font-size: 12px; font-weight: 650; }
#StatusLabel { color: #c5d0df; font-size: 12px; }
#Card, #BottomBar {
    background: #121925;
    border: 1px solid #222d3e;
    border-radius: 14px;
}
#Hero {
    background: #14202b;
    border: 1px solid #27564f;
    border-radius: 16px;
}
#HeroBadge {
    background: #183a36;
    color: #64e5c5;
    border: 1px solid #2b6b60;
    border-radius: 12px;
    padding: 12px 18px;
    font-weight: 700;
}
#ResourcePanel { background: #151d2a; border: 1px solid #283347; border-radius: 12px; }
#NavButton {
    text-align: left;
    border: none;
    border-radius: 10px;
    padding: 12px 14px;
    color: #9da9bb;
    background: transparent;
    font-weight: 600;
}
#NavButton:hover { background: #182131; color: #e8edf5; }
#NavButton:checked { background: #17332f; color: #5de1c0; }
QPushButton {
    background: #1a2331;
    border: 1px solid #303c50;
    border-radius: 9px;
    padding: 9px 16px;
    font-weight: 600;
}
QPushButton:hover { background: #222d3e; border-color: #435168; }
QPushButton:disabled { color: #586477; background: #131a25; border-color: #202a39; }
#PrimaryButton { background: #38c9a7; color: #071510; border-color: #38c9a7; }
#PrimaryButton:hover { background: #52ddba; border-color: #52ddba; }
#SecondaryButton { background: #1b2e3a; border-color: #2d5a62; color: #77e1cb; }
#GhostButton { background: transparent; }
#DangerButton { background: #2b1b25; border-color: #633148; color: #ff9db6; }
#PresetButton, #ModeButton {
    text-align: left;
    background: #151e2b;
    border: 1px solid #29364a;
    padding: 13px 16px;
}
#PresetButton:hover, #ModeButton:hover { border-color: #3cc8a8; background: #172a2c; }
#ModeButton:checked { border: 2px solid #48d3b1; background: #16302d; color: #70e8ca; }
QLineEdit, QComboBox, QDoubleSpinBox, QListWidget, QPlainTextEdit {
    background: #0d131d;
    border: 1px solid #2a3547;
    border-radius: 8px;
    padding: 8px 10px;
    selection-background-color: #2b8f7b;
}
QLineEdit:focus, QComboBox:focus, QDoubleSpinBox:focus, QListWidget:focus, QPlainTextEdit:focus {
    border: 1px solid #45cfad;
}
QComboBox::drop-down { border: none; width: 28px; }
QComboBox QAbstractItemView { background: #151d29; border: 1px solid #344257; selection-background-color: #235e53; }
QListWidget { padding: 6px; alternate-background-color: #101824; }
QListWidget::item { padding: 9px; border-radius: 6px; }
QListWidget::item:selected { background: #1d544a; color: #eafff9; }
QPlainTextEdit { font-family: "Cascadia Mono", "Consolas"; font-size: 12px; }
QCheckBox { spacing: 9px; color: #c7d0dd; }
QCheckBox::indicator { width: 18px; height: 18px; border: 1px solid #435168; border-radius: 5px; background: #0d131d; }
QCheckBox::indicator:checked { background: #42cfad; border-color: #42cfad; }
QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {
    subcontrol-origin: border;
    width: 22px;
    background: #172131;
    border-left: 1px solid #2a3547;
}
QDoubleSpinBox::up-button { subcontrol-position: top right; border-top-right-radius: 7px; }
QDoubleSpinBox::down-button { subcontrol-position: bottom right; border-bottom-right-radius: 7px; }
QDoubleSpinBox::up-button:hover, QDoubleSpinBox::down-button:hover { background: #235e53; }
QProgressBar { background: #101722; border: none; border-radius: 4px; min-height: 7px; max-height: 7px; }
QProgressBar::chunk { background: #43d2ae; border-radius: 4px; }
QScrollArea { background: transparent; }
QScrollBar:vertical { background: transparent; width: 10px; margin: 2px; }
QScrollBar::handle:vertical { background: #2c384a; min-height: 40px; border-radius: 5px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
"""

LIGHT_STYLE = r"""
QWidget {
    background: #f3f6f9;
    color: #17202d;
    font-family: "Segoe UI", "Microsoft YaHei UI";
    font-size: 14px;
}
QMainWindow { background: #f3f6f9; }
#Sidebar { background: #ffffff; border-right: 1px solid #dbe2ea; }
#Brand { color: #101820; font-size: 18px; font-weight: 800; letter-spacing: 1px; }
#PageTitle { font-size: 25px; font-weight: 750; }
#HeroTitle { font-size: 23px; font-weight: 750; }
#CardTitle { font-size: 17px; font-weight: 700; }
#ActivityTitle { font-size: 22px; font-weight: 750; }
#Muted { color: #687588; }
#AccentText { color: #087f69; font-size: 12px; font-weight: 700; }
#FieldLabel { color: #546175; font-size: 12px; font-weight: 650; }
#Card, #BottomBar { background: #ffffff; border: 1px solid #dbe3ec; border-radius: 14px; }
#Hero { background: #eaf8f4; border: 1px solid #b5e4d9; border-radius: 16px; }
#HeroBadge { background: #d9f4ec; color: #087d68; border: 1px solid #9ed8ca; border-radius: 12px; padding: 12px 18px; font-weight: 700; }
#ResourcePanel { background: #f5f8fb; border: 1px solid #dce4ed; border-radius: 12px; }
#NavButton { text-align: left; border: none; border-radius: 10px; padding: 12px 14px; color: #667487; background: transparent; font-weight: 600; }
#NavButton:hover { background: #f0f4f7; color: #17202d; }
#NavButton:checked { background: #dff4ee; color: #087f69; }
QPushButton { background: #f6f8fa; border: 1px solid #ccd6e1; border-radius: 9px; padding: 9px 16px; font-weight: 600; }
QPushButton:hover { background: #edf2f6; border-color: #aebdcb; }
QPushButton:disabled { color: #a0a9b5; background: #f2f4f6; }
#PrimaryButton { background: #159f84; color: white; border-color: #159f84; }
#PrimaryButton:hover { background: #118d75; }
#SecondaryButton { background: #eaf7f4; border-color: #a9d8cd; color: #087866; }
#GhostButton { background: transparent; }
#DangerButton { background: #fff0f3; border-color: #efbec9; color: #b53654; }
#PresetButton, #ModeButton { text-align: left; background: #f7f9fb; border: 1px solid #d6dfe8; padding: 13px 16px; }
#PresetButton:hover, #ModeButton:hover { border-color: #49aa96; background: #eef9f6; }
#ModeButton:checked { border: 2px solid #159f84; background: #e1f5ef; color: #087866; }
QLineEdit, QComboBox, QDoubleSpinBox, QListWidget, QPlainTextEdit { background: #ffffff; border: 1px solid #ccd7e2; border-radius: 8px; padding: 8px 10px; selection-background-color: #55bba5; }
QLineEdit:focus, QComboBox:focus, QDoubleSpinBox:focus, QListWidget:focus, QPlainTextEdit:focus { border: 1px solid #169f84; }
QComboBox::drop-down { border: none; width: 28px; }
QComboBox QAbstractItemView { background: white; border: 1px solid #ccd7e2; selection-background-color: #d9f2eb; }
QListWidget { padding: 6px; alternate-background-color: #f6f8fa; }
QListWidget::item { padding: 9px; border-radius: 6px; }
QListWidget::item:selected { background: #d9f2eb; color: #087866; }
QPlainTextEdit { font-family: "Cascadia Mono", "Consolas"; font-size: 12px; }
QCheckBox { spacing: 9px; }
QCheckBox::indicator { width: 18px; height: 18px; border: 1px solid #aebbc9; border-radius: 5px; background: white; }
QCheckBox::indicator:checked { background: #159f84; border-color: #159f84; }
QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {
    subcontrol-origin: border;
    width: 22px;
    background: #edf2f6;
    border-left: 1px solid #ccd7e2;
}
QDoubleSpinBox::up-button { subcontrol-position: top right; border-top-right-radius: 7px; }
QDoubleSpinBox::down-button { subcontrol-position: bottom right; border-bottom-right-radius: 7px; }
QDoubleSpinBox::up-button:hover, QDoubleSpinBox::down-button:hover { background: #d9f2eb; }
QProgressBar { background: #e2e8ee; border: none; border-radius: 4px; min-height: 7px; max-height: 7px; }
QProgressBar::chunk { background: #159f84; border-radius: 4px; }
QScrollArea { background: transparent; }
QScrollBar:vertical { background: transparent; width: 10px; margin: 2px; }
QScrollBar::handle:vertical { background: #bac5d1; min-height: 40px; border-radius: 5px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
"""
