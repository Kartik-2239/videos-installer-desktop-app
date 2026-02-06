from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QByteArray, Qt, QSize, QUrl
from PySide6.QtGui import QIcon, QPainter, QPixmap, QImage, QColor, QFont
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSlider,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from services.state import AppState

AUDIO_EXTENSIONS = {
    ".mp3",
    ".mp2",
    ".mp1",
    ".m4a",
    ".m4b",
    ".m4p",
    ".aac",
    ".wav",
    ".flac",
    ".ogg",
    ".opus",
    ".aiff",
    ".aif",
    ".aifc",
    ".wma",
    ".alac",
    ".amr",
    ".caf",
}

ARTWORK_FILES = (
    "cover.jpg",
    "cover.png",
    "folder.jpg",
    "folder.png",
    "album.jpg",
    "album.png",
    "artwork.jpg",
    "artwork.png",
)

DEFAULT_ARTWORK_DIR = Path(__file__).resolve().parent.parent / "assets" / "artwork"


def svg_icon(svg: str, size: int) -> QIcon:
    image = QImage(size, size, QImage.Format_ARGB32)
    image.fill(Qt.transparent)
    painter = QPainter(image)
    renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))
    renderer.render(painter)
    painter.end()
    return QIcon(QPixmap.fromImage(image))


class PlayerPage(QWidget):
    def __init__(self, state: AppState, on_theme_change, on_navigate) -> None:
        super().__init__()
        self.state = state
        self.on_theme_change = on_theme_change
        self.on_navigate = on_navigate

        self._audio_dir: Path | None = None
        self._current_track: Path | None = None
        self._artwork_pixmap: QPixmap | None = None
        self._using_placeholder = True
        self._using_default = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        card = QWidget(self)
        card.setObjectName("MainCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(20, 20, 20, 20)
        card_layout.setSpacing(16)

        nav_bar = QHBoxLayout()
        icon_badge = QLabel("PL")
        icon_badge.setAlignment(Qt.AlignCenter)
        icon_badge.setObjectName("IconBadge")
        header_title = QLabel("Orca Player")
        header_title.setObjectName("HeaderTitle")
        home_btn = QPushButton("Home")
        home_btn.setObjectName("NavButton")
        home_btn.clicked.connect(lambda: self.on_navigate("home"))
        nav_bar.addWidget(icon_badge)
        nav_bar.addWidget(header_title)
        nav_bar.addWidget(home_btn)
        nav_bar.addStretch(1)

        self.theme_toggle = QToolButton()
        self.theme_toggle.setObjectName("ThemeToggle")
        self.theme_toggle.setCheckable(True)
        self._sun_icon = svg_icon(
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="#f01d85">'
            '<circle cx="12" cy="12" r="5"/>'
            "</svg>",
            12,
        )
        self._moon_icon = svg_icon(
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="#f7c6de">'
            '<path d="M21 14.5A8.5 8.5 0 1 1 9.5 3a7 7 0 1 0 11.5 11.5Z"/></svg>',
            12,
        )
        self.theme_toggle.setIcon(self._sun_icon)
        self.theme_toggle.setIconSize(QSize(12, 12))
        self.theme_toggle.toggled.connect(self._on_theme_toggled)
        nav_bar.addWidget(self.theme_toggle)

        top_divider = QFrame()
        top_divider.setObjectName("Divider")
        top_divider.setFixedHeight(1)
        top_divider.setFrameShape(QFrame.HLine)

        content_row = QHBoxLayout()
        content_row.setSpacing(24)

        left_col = QVBoxLayout()
        left_col.setSpacing(12)

        artwork_frame = QFrame()
        artwork_frame.setObjectName("ArtworkFrame")
        artwork_layout = QVBoxLayout(artwork_frame)
        artwork_layout.setContentsMargins(16, 16, 16, 16)
        artwork_layout.setSpacing(0)

        self.artwork_label = QLabel()
        self.artwork_label.setObjectName("ArtworkImage")
        self.artwork_label.setAlignment(Qt.AlignCenter)
        self.artwork_label.setFixedSize(240, 240)
        artwork_layout.addWidget(self.artwork_label, 0, Qt.AlignCenter)

        self.track_title = QLabel("No track selected")
        self.track_title.setObjectName("TrackTitle")
        self.track_subtitle = QLabel("Pick a folder to list audio files.")
        self.track_subtitle.setObjectName("TrackSubtitle")

        controls_card = QFrame()
        controls_card.setObjectName("ControlsCard")
        controls_layout = QVBoxLayout(controls_card)
        controls_layout.setContentsMargins(12, 12, 12, 12)
        controls_layout.setSpacing(8)

        self.player = QMediaPlayer(self)
        self.audio_output = QAudioOutput(self)
        self.audio_output.setVolume(0.6)
        self.player.setAudioOutput(self.audio_output)
        self.player.playbackStateChanged.connect(self._sync_play_button)
        self.player.positionChanged.connect(self._sync_position)
        self.player.durationChanged.connect(self._sync_duration)

        self.position_slider = QSlider(Qt.Horizontal)
        self.position_slider.setRange(0, 0)
        self.position_slider.setObjectName("SeekSlider")
        self.position_slider.sliderMoved.connect(self.player.setPosition)

        time_row = QHBoxLayout()
        self.current_time = QLabel("00:00")
        self.current_time.setObjectName("TimeLabel")
        self.total_time = QLabel("00:00")
        self.total_time.setObjectName("TimeLabel")
        time_row.addWidget(self.current_time)
        time_row.addStretch(1)
        time_row.addWidget(self.total_time)

        button_row = QHBoxLayout()
        self.play_btn = QPushButton("Play")
        self.play_btn.setObjectName("ControlButton")
        self.play_btn.setEnabled(False)
        self.play_btn.clicked.connect(self._toggle_play)
        self.mute_btn = QPushButton("Mute")
        self.mute_btn.setObjectName("ControlButton")
        self.mute_btn.setCheckable(True)
        self.mute_btn.toggled.connect(self._toggle_mute)
        self.volume_label = QLabel("VOL")
        self.volume_label.setObjectName("FieldLabel")
        self.volume_slider = QSlider(Qt.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(60)
        self.volume_slider.setObjectName("VolumeSlider")
        self.volume_slider.setFixedWidth(140)
        self.volume_slider.valueChanged.connect(self._set_volume)
        button_row.addWidget(self.play_btn)
        button_row.addWidget(self.mute_btn)
        button_row.addStretch(1)
        button_row.addWidget(self.volume_label)
        button_row.addWidget(self.volume_slider)

        controls_layout.addWidget(self.position_slider)
        controls_layout.addLayout(time_row)
        controls_layout.addLayout(button_row)

        left_col.addWidget(artwork_frame, 0, Qt.AlignTop)
        left_col.addWidget(self.track_title)
        left_col.addWidget(self.track_subtitle)
        left_col.addWidget(controls_card)
        left_col.addStretch(1)

        right_col = QVBoxLayout()
        right_col.setSpacing(10)

        library_label = QLabel("LIBRARY")
        library_label.setObjectName("SectionLabel")

        folder_row = QHBoxLayout()
        self.folder_input = QLineEdit()
        self.folder_input.setReadOnly(True)
        self.browse_btn = QPushButton("Choose Folder")
        self.browse_btn.setObjectName("FolderButton")
        self.browse_btn.clicked.connect(self._choose_audio_dir)
        folder_row.addWidget(self.folder_input, 1)
        folder_row.addWidget(self.browse_btn)

        self.track_list = QListWidget()
        self.track_list.setObjectName("TrackList")
        self.track_list.setSelectionMode(QAbstractItemView.SingleSelection)
        self.track_list.itemSelectionChanged.connect(self._on_track_selected)
        self.track_list.itemDoubleClicked.connect(self._play_selected)

        self.library_hint = QLabel("No audio files found in this folder.")
        self.library_hint.setObjectName("SubtitleLabel")
        self.library_hint.setVisible(False)

        right_col.addWidget(library_label)
        right_col.addLayout(folder_row)
        right_col.addWidget(self.track_list, 1)
        right_col.addWidget(self.library_hint)

        content_row.addLayout(left_col, 1)
        content_row.addLayout(right_col, 1)

        card_layout.addLayout(nav_bar)
        card_layout.addWidget(top_divider)
        card_layout.addLayout(content_row)

        layout.addWidget(card)
        self.apply_state(state)

    def apply_state(self, state: AppState) -> None:
        self.volume_slider.setValue(state.volume)
        self.mute_btn.setChecked(state.muted)
        self.set_theme(state.theme)

        audio_dir = state.audio_dir or state.last_folder_path
        if audio_dir and Path(audio_dir).is_dir():
            self._load_audio_dir(Path(audio_dir))
        else:
            self._set_placeholder_artwork()

    def update_state(self, state: AppState) -> None:
        state.volume = self.volume_slider.value()
        state.muted = self.mute_btn.isChecked()
        if self.folder_input.text():
            state.audio_dir = self.folder_input.text()

    def _choose_audio_dir(self) -> None:
        start_dir = self.folder_input.text() or self.state.last_folder_path
        selected = QFileDialog.getExistingDirectory(self, "Choose Audio Folder", start_dir)
        if not selected:
            return
        self._load_audio_dir(Path(selected))

    def _load_audio_dir(self, directory: Path) -> None:
        self._audio_dir = directory
        self.folder_input.setText(str(directory))
        self.state.audio_dir = str(directory)
        audio_files = sorted(
            [path for path in directory.iterdir() if path.is_file() and path.suffix.lower() in AUDIO_EXTENSIONS],
            key=lambda path: path.name.lower(),
        )

        self.track_list.blockSignals(True)
        self.track_list.clear()
        for path in audio_files:
            item = QListWidgetItem(path.stem)
            item.setData(Qt.UserRole, str(path))
            self.track_list.addItem(item)
        self.track_list.blockSignals(False)

        has_files = bool(audio_files)
        self.library_hint.setVisible(not has_files)

        self._set_artwork_from_dir(directory)

        if has_files:
            self.track_list.setCurrentRow(0)
        else:
            self._current_track = None
            self.player.stop()
            self.play_btn.setEnabled(False)
            self.track_title.setText("No track selected")
            self.track_subtitle.setText("Pick a folder to list audio files.")

    def _on_track_selected(self) -> None:
        items = self.track_list.selectedItems()
        if not items:
            return
        item = items[0]
        path_str = item.data(Qt.UserRole)
        if not path_str:
            return
        path = Path(path_str)
        autoplay = self.player.playbackState() == QMediaPlayer.PlayingState
        self._set_current_track(path, autoplay=autoplay)

    def _play_selected(self, item: QListWidgetItem) -> None:
        path_str = item.data(Qt.UserRole)
        if not path_str:
            return
        self._set_current_track(Path(path_str), autoplay=True)

    def _set_current_track(self, path: Path, autoplay: bool = False) -> None:
        if not path.exists():
            return
        self._current_track = path
        self.player.setSource(QUrl.fromLocalFile(str(path)))
        self.track_title.setText(path.stem)
        self.track_subtitle.setText(path.name)
        self.play_btn.setEnabled(True)
        if autoplay:
            self.player.play()

    def _toggle_play(self) -> None:
        if self.player.playbackState() == QMediaPlayer.PlayingState:
            self.player.pause()
        else:
            self.player.play()

    def _sync_play_button(self) -> None:
        if self.player.playbackState() == QMediaPlayer.PlayingState:
            self.play_btn.setText("Pause")
        else:
            self.play_btn.setText("Play")

    def _sync_position(self, position: int) -> None:
        if not self.position_slider.isSliderDown():
            self.position_slider.setValue(position)
        self.current_time.setText(self._format_time(position))

    def _sync_duration(self, duration: int) -> None:
        self.position_slider.setRange(0, duration)
        self.total_time.setText(self._format_time(duration))

    def _toggle_mute(self, checked: bool) -> None:
        self.audio_output.setMuted(checked)
        self.mute_btn.setText("Muted" if checked else "Mute")

    def _set_volume(self, value: int) -> None:
        self.audio_output.setVolume(value / 100)

    def _format_time(self, ms: int) -> str:
        total_seconds = max(0, ms // 1000)
        minutes = total_seconds // 60
        seconds = total_seconds % 60
        return f"{minutes:02d}:{seconds:02d}"

    def _set_artwork_from_dir(self, directory: Path | None) -> None:
        if directory is None:
            if not self._set_default_artwork():
                self._set_placeholder_artwork()
            return
        for name in ARTWORK_FILES:
            candidate = directory / name
            if candidate.exists():
                pixmap = QPixmap(str(candidate))
                if not pixmap.isNull():
                    self._artwork_pixmap = pixmap
                    self._using_placeholder = False
                    self._using_default = False
                    self._apply_artwork_pixmap()
                    return
        if not self._set_default_artwork():
            self._set_placeholder_artwork()

    def _set_default_artwork(self) -> bool:
        if not DEFAULT_ARTWORK_DIR.exists():
            return False
        candidates = sorted(
            [p for p in DEFAULT_ARTWORK_DIR.iterdir() if p.is_file() and p.suffix.lower() in {".png", ".jpg", ".jpeg"}],
            key=lambda p: p.name.lower(),
        )
        if not candidates:
            return False
        pixmap = QPixmap(str(candidates[0]))
        if pixmap.isNull():
            return False
        self._artwork_pixmap = pixmap
        self._using_placeholder = False
        self._using_default = True
        self._apply_artwork_pixmap()
        return True

    def _apply_artwork_pixmap(self) -> None:
        if not self._artwork_pixmap:
            return
        target = self.artwork_label.size()
        scaled = self._artwork_pixmap.scaled(target, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
        self.artwork_label.setPixmap(scaled)

    def _set_placeholder_artwork(self) -> None:
        size = self.artwork_label.size() or QSize(240, 240)
        pixmap = QPixmap(size)
        pixmap.fill(Qt.transparent)

        if self.state.theme == "Dark":
            base = QColor("#1c141a")
            accent = QColor("#b25574")
            text = QColor("#e9e1e6")
        else:
            base = QColor("#fff7fb")
            accent = QColor("#f01d85")
            text = QColor("#1f2430")

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(pixmap.rect(), base)
        painter.setPen(accent)
        painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(pixmap.rect().adjusted(8, 8, -8, -8), 16, 16)
        painter.setPen(text)
        font = QFont()
        font.setPointSize(12)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(pixmap.rect(), Qt.AlignCenter, "No Artwork")
        painter.end()

        self._artwork_pixmap = pixmap
        self._using_placeholder = True
        self._using_default = False
        self._apply_artwork_pixmap()

    def _on_theme_toggled(self, checked: bool) -> None:
        if checked:
            self.theme_toggle.setIcon(self._moon_icon)
            self.on_theme_change("Dark")
        else:
            self.theme_toggle.setIcon(self._sun_icon)
            self.on_theme_change("Light")

    def set_theme(self, theme: str) -> None:
        self.theme_toggle.blockSignals(True)
        self.theme_toggle.setChecked(theme == "Dark")
        self.theme_toggle.blockSignals(False)
        self.theme_toggle.setIcon(self._moon_icon if theme == "Dark" else self._sun_icon)
        if self._using_placeholder:
            self._set_placeholder_artwork()
