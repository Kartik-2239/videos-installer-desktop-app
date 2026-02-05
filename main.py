import re
import sys
from pathlib import Path

from PySide6.QtCore import QProcess, Qt, QUrl
from PySide6.QtGui import QFont
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QProgressBar,
    QSizePolicy,
    QSpacerItem,
    QScrollArea,
    QSlider,
    QStyle,
    QVBoxLayout,
    QWidget,
)


def human_path(path: Path) -> str:
    try:
        return str(path.resolve())
    except OSError:
        return str(path)


class VideoDownloader(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Lightweight Video Downloader")
        self.setMinimumSize(980, 640)

        self.base_dir = Path(__file__).parent
        self.default_downloads = self.base_dir / "downloads"
        self.default_downloads.mkdir(parents=True, exist_ok=True)

        self.process = QProcess(self)
        self.process.setProcessChannelMode(QProcess.MergedChannels)
        self.process.readyReadStandardOutput.connect(self._on_process_output)
        self.process.finished.connect(self._on_process_finished)
        self.process.errorOccurred.connect(self._on_process_error)

        self._current_output_path: Path | None = None
        self._last_progress = 0
        self._last_info_line = ""

        self._init_ui()
        self._refresh_subfolders()
        self._sync_container_options()
        self._set_input_heights()

    def _init_ui(self) -> None:
        root = QWidget(self)
        root_layout = QHBoxLayout(root)
        root_layout.setContentsMargins(22, 18, 22, 18)
        root_layout.setSpacing(18)

        left = QWidget(root)
        left_layout = QVBoxLayout(left)
        left_layout.setSpacing(10)

        title = QLabel("Download & Preview")
        title_font = QFont()
        title_font.setPointSize(18)
        title_font.setBold(True)
        title.setFont(title_font)

        subtitle = QLabel("Paste a URL, pick a folder, and download with yt-dlp + ffmpeg.")
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet("")

        url_label = QLabel("Video URL")
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("https://...")
        
        save_label = QLabel("Save Location")
        folder_row = QHBoxLayout()
        self.folder_input = QLineEdit()
        self.folder_input.setReadOnly(True)
        self.folder_input.setText(human_path(self.default_downloads))
        self.browse_btn = QPushButton("Choose Folder")
        self.browse_btn.setObjectName("FolderButton")
        self.browse_btn.clicked.connect(self._choose_folder)
        folder_row.addWidget(self.folder_input, 1)
        folder_row.addWidget(self.browse_btn)
        
        subfolder_label = QLabel("Subfolder")
        name_row = QHBoxLayout()
        self.subfolder_combo = QComboBox()
        self.subfolder_combo.setEditable(False)
        self.subfolder_combo.currentTextChanged.connect(self._on_subfolder_changed)
        self.new_sub_btn = QPushButton("New Folder")
        self.new_sub_btn.setObjectName("FolderButton")
        self.new_sub_btn.clicked.connect(self._create_subfolder)
        name_row.addWidget(self.subfolder_combo, 1)
        name_row.addWidget(self.new_sub_btn)


        tweak_group = QGroupBox("Download Options")
        tweak_group.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        tweak_layout = QVBoxLayout(tweak_group)
        tweak_layout.setSpacing(8)
        tweak_layout.setContentsMargins(12, 16, 12, 12)

        quality_label = QLabel("Quality")
        self.quality_combo = QComboBox()
        self.quality_combo.addItems(["Best", "Worst"])

        resolution_label = QLabel("Resolution cap")
        self.resolution_combo = QComboBox()
        self.resolution_combo.addItems(["No cap", "480p", "720p", "1080p", "1440p", "2160p"])

        codec_label = QLabel("Prefer codec")
        self.codec_combo = QComboBox()
        self.codec_combo.addItems(["Any", "AV1", "H.264", "HEVC"])

        container_label = QLabel("Output container")
        self.container_combo = QComboBox()

        audio_label = QLabel("Audio")
        self.audio_only_toggle = QCheckBox("Audio only")
        self.audio_only_toggle.toggled.connect(self._sync_container_options)

        format_label = QLabel("Format selector")
        self.format_input = QLineEdit()
        self.format_input.setPlaceholderText("Optional advanced -f string")

        filename_label = QLabel("Filename template")
        self.filename_input = QLineEdit()
        self.filename_input.setText("%(title).120s.%(ext)s")

        tweak_layout.addWidget(quality_label)
        tweak_layout.addWidget(self.quality_combo)
        tweak_layout.addWidget(resolution_label)
        tweak_layout.addWidget(self.resolution_combo)
        tweak_layout.addWidget(codec_label)
        tweak_layout.addWidget(self.codec_combo)
        tweak_layout.addWidget(container_label)
        tweak_layout.addWidget(self.container_combo)
        tweak_layout.addWidget(audio_label)
        tweak_layout.addWidget(self.audio_only_toggle)
        tweak_layout.addWidget(format_label)
        tweak_layout.addWidget(self.format_input)
        tweak_layout.addWidget(filename_label)
        tweak_layout.addWidget(self.filename_input)

        action_row = QHBoxLayout()
        self.download_btn = QPushButton("Download")
        self.download_btn.clicked.connect(self._start_download)
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self._cancel_download)
        self.cancel_btn.setEnabled(False)
        action_row.addWidget(self.download_btn)
        action_row.addWidget(self.cancel_btn)
        action_row.addItem(QSpacerItem(20, 20))

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setFormat("Ready")

        self.status = QLabel("")
        self.status.setWordWrap(True)
        self.status.setStyleSheet("color: #2a2a2a;")

        left_content = QWidget(left)
        left_content.setStyleSheet("background: #ffffff;")
        left_content_layout = QVBoxLayout(left_content)
        left_content_layout.setSpacing(10)
        left_content_layout.addWidget(title)
        left_content_layout.addWidget(subtitle)
        left_content_layout.addWidget(url_label)
        left_content_layout.addWidget(self.url_input)
        left_content_layout.addWidget(save_label)
        left_content_layout.addLayout(folder_row)
        left_content_layout.addWidget(subfolder_label)
        left_content_layout.addLayout(name_row)
        left_content_layout.addWidget(tweak_group)
        left_content_layout.addLayout(action_row)
        left_content_layout.addWidget(self.progress)
        left_content_layout.addWidget(self.status)
        left_content_layout.addStretch(1)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: #ffffff; } QScrollArea > QWidget { background: #ffffff; }")
        scroll.setWidget(left_content)

        left_layout.addWidget(scroll)

        right = QWidget(root)
        right_layout = QVBoxLayout(right)
        right_layout.setSpacing(12)

        preview_title = QLabel("Preview")
        preview_title.setFont(QFont("Helvetica Neue", 16, QFont.Bold))

        self.video_widget = QVideoWidget()
        self.video_widget.setMinimumSize(240, 360)
        self.video_widget.setStyleSheet("")

        self.player = QMediaPlayer(self)
        self.audio_output = QAudioOutput(self)
        self.audio_output.setVolume(0.6)
        self.player.setAudioOutput(self.audio_output)
        self.player.setVideoOutput(self.video_widget)
        self.player.errorOccurred.connect(self._on_player_error)
        self.player.mediaStatusChanged.connect(self._on_media_status)
        self.player.playbackStateChanged.connect(self._sync_play_button)
        self.player.positionChanged.connect(self._sync_position)
        self.player.durationChanged.connect(self._sync_duration)

        self.preview_label = QLabel("Download a video to preview it here.")
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setStyleSheet("")

        controls_row = QHBoxLayout()
        self.back_btn = QPushButton("Back 10s")
        self.back_btn.clicked.connect(lambda: self._seek_relative(-10000))
        self.play_btn = QPushButton("Play")
        self.play_btn.clicked.connect(self._toggle_play)
        self.forward_btn = QPushButton("Forward 10s")
        self.forward_btn.clicked.connect(lambda: self._seek_relative(10000))
        self.stop_btn = QPushButton("Stop")
        self.stop_btn.clicked.connect(self.player.stop)
        self.open_btn = QPushButton("Open Video")
        self.open_btn.clicked.connect(self._open_video_file)
        self.mute_btn = QPushButton("Mute")
        self.mute_btn.setCheckable(True)
        self.mute_btn.toggled.connect(self._toggle_mute)
        controls_row.addWidget(self.back_btn)
        controls_row.addWidget(self.play_btn)
        controls_row.addWidget(self.forward_btn)
        controls_row.addWidget(self.stop_btn)
        controls_row.addWidget(self.open_btn)
        controls_row.addWidget(self.mute_btn)
        controls_row.addStretch(1)

        self.position_slider = QSlider(Qt.Horizontal)
        self.position_slider.setRange(0, 0)
        self.position_slider.sliderMoved.connect(self.player.setPosition)
        self.position_slider.setFixedHeight(22)
        self.position_slider.setObjectName("SeekSlider")

        volume_row = QHBoxLayout()
        volume_label = QLabel("Volume")
        self.volume_slider = QSlider(Qt.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(60)
        self.volume_slider.valueChanged.connect(self._set_volume)
        volume_row.addWidget(volume_label)
        volume_row.addWidget(self.volume_slider, 1)

        right_layout.addWidget(preview_title)

        preview_card = QWidget()
        preview_card_layout = QVBoxLayout(preview_card)
        preview_card_layout.setContentsMargins(12, 12, 12, 12)
        preview_card_layout.setSpacing(10)
        preview_card_layout.addWidget(self.video_widget)
        preview_card_layout.addWidget(self.preview_label)
        preview_card_layout.addLayout(controls_row)
        preview_card_layout.addWidget(self.position_slider)
        preview_card_layout.addLayout(volume_row)
        preview_card.setObjectName("PreviewCard")

        right_layout.addWidget(preview_card, 1)
        right_layout.addStretch(1)

        root_layout.addWidget(left, 3)
        root_layout.addWidget(right, 4)

        self.setCentralWidget(root)
        self._apply_styles()

    def _choose_folder(self) -> None:
        path = QFileDialog.getExistingDirectory(
            self, "Choose download folder", str(self.default_downloads)
        )
        if path:
            self.folder_input.setText(path)
            self._refresh_subfolders()

    def _create_subfolder(self) -> None:
        base = Path(self.folder_input.text().strip() or self.default_downloads)
        name, ok = QInputDialog.getText(self, "New Folder", "Subfolder name:")
        if not ok or not name.strip():
            return
        folder = self._sanitize_folder_name(name)
        target = base / folder
        target.mkdir(parents=True, exist_ok=True)
        self._refresh_subfolders(select=folder)

    def _refresh_subfolders(self, select: str | None = None) -> None:
        base = Path(self.folder_input.text().strip() or self.default_downloads)
        base.mkdir(parents=True, exist_ok=True)
        folders = sorted([p.name for p in base.iterdir() if p.is_dir()])
        self.subfolder_combo.blockSignals(True)
        self.subfolder_combo.clear()
        self.subfolder_combo.addItems(folders)
        if select and select in folders:
            self.subfolder_combo.setCurrentText(select)
        elif folders:
            self.subfolder_combo.setCurrentIndex(0)
        self.subfolder_combo.blockSignals(False)

    def _on_subfolder_changed(self, _text: str) -> None:
        pass

    def _sanitize_folder_name(self, name: str) -> str:
        cleaned = re.sub(r"[^\w\- ]+", "", name).strip()
        cleaned = cleaned.replace(" ", "-")
        return cleaned or "download"

    def _sync_container_options(self) -> None:
        self.container_combo.blockSignals(True)
        self.container_combo.clear()
        if self.audio_only_toggle.isChecked():
            self.container_combo.addItems(["m4a", "mp3", "opus"])
            self.container_combo.setCurrentText("m4a")
        else:
            self.container_combo.addItems(["mp4", "mkv", "webm"])
            self.container_combo.setCurrentText("mp4")
        self.container_combo.blockSignals(False)

    def _set_input_heights(self) -> None:
        height = 40
        inputs = [
            self.url_input,
            self.folder_input,
            self.subfolder_combo,
            self.quality_combo,
            self.resolution_combo,
            self.codec_combo,
            self.container_combo,
            self.format_input,
            self.filename_input,
        ]
        for widget in inputs:
            widget.setFixedHeight(height)
        self.browse_btn.setFixedHeight(height)
        self.new_sub_btn.setFixedHeight(height)

    def _start_download(self) -> None:
        url = self.url_input.text().strip()
        if not url:
            QMessageBox.warning(self, "Missing URL", "Please paste a video URL.")
            return

        base_folder = Path(self.folder_input.text().strip() or self.default_downloads)
        subfolder = self.subfolder_combo.currentText().strip()
        if not subfolder:
            subfolder = "download"
        target_folder = base_folder / self._sanitize_folder_name(subfolder)
        target_folder.mkdir(parents=True, exist_ok=True)

        template_text = self.filename_input.text().strip() or "%(title).120s.%(ext)s"
        output_template = target_folder / template_text
        self._current_output_path = target_folder
        self._last_progress = 0
        self._last_info_line = ""

        args = ["--newline", "-o", str(output_template)]

        format_override = self.format_input.text().strip()
        audio_only = self.audio_only_toggle.isChecked()
        container = self.container_combo.currentText().strip()

        if format_override:
            args += ["-f", format_override]
        else:
            quality = self.quality_combo.currentText()
            res_cap = self.resolution_combo.currentText()
            codec = self.codec_combo.currentText()

            if audio_only:
                args += ["-f", "ba/b"]
            else:
                fmt = "bv*+ba/b"
                if quality == "Worst":
                    fmt = "bv*+ba/b[quality=lowest]"
                if res_cap != "No cap":
                    height = res_cap.replace("p", "")
                    fmt = f"{fmt}[height<={height}]"
                if codec != "Any":
                    codec_map = {"AV1": "av01", "H.264": "avc1", "HEVC": "hev1"}
                    code = codec_map.get(codec, "")
                    if code:
                        fmt = f"{fmt}[vcodec*={code}]"
                args += ["-f", fmt]

        if audio_only:
            args += ["--extract-audio", "--audio-format", container]
        else:
            args += ["--merge-output-format", container]


        args.append(url)

        self._set_running(True)
        self.progress.setValue(0)
        self.progress.setFormat("Downloading...")
        self.status.setText(f"Saving to {human_path(target_folder)}")
        self._set_status_color(error=False)
        self.preview_label.setText("Downloading... preview will appear when ready.")
        self.player.stop()

        self.process.start("yt-dlp", args)

    def _cancel_download(self) -> None:
        if self.process.state() != QProcess.NotRunning:
            self.process.kill()
        self._set_running(False)
        self.progress.setValue(0)
        self.progress.setFormat("Cancelled")
        self.status.setText("Download cancelled.")
        self._set_status_color(error=True)

    def _set_running(self, running: bool) -> None:
        self.download_btn.setEnabled(not running)
        self.cancel_btn.setEnabled(running)
        self.url_input.setEnabled(not running)
        self.subfolder_combo.setEnabled(not running)

    def _on_process_output(self) -> None:
        data = self.process.readAllStandardOutput().data().decode(errors="ignore")
        for line in data.splitlines():
            self._parse_progress(line)

    def _parse_progress(self, line: str) -> None:
        if not line:
            return

        match = re.search(r"\[download\]\s+(\d{1,3}\.\d+)%", line)
        if match:
            value = int(float(match.group(1)))
            if value != self._last_progress:
                self._last_progress = value
                self.progress.setValue(value)
                self.progress.setFormat(f"{value}%")
            return

        if "Destination:" in line or "Merging formats into" in line:
            self.status.setText(line.strip())
            self._last_info_line = line.strip()
            self._set_status_color(error=False)
            return

        self._last_info_line = line.strip()

    def _on_process_error(self) -> None:
        self._set_running(False)
        self.progress.setValue(0)
        self.progress.setFormat("Error")
        self.status.setText("Failed to start yt-dlp. Is it installed and on PATH?")
        self._set_status_color(error=True)

    def _on_process_finished(self, exit_code: int, _status: QProcess.ExitStatus) -> None:
        self._set_running(False)
        if exit_code != 0:
            self.progress.setFormat("Failed")
            detail = self._last_info_line or "Download failed. Check the URL or yt-dlp output."
            self.status.setText(detail)
            self._set_status_color(error=True)
            return

        self.progress.setValue(100)
        self.progress.setFormat("Done")
        self.status.setText("Download complete.")
        self._set_status_color(error=False)

        latest = self._find_latest_video()
        if latest:
            self._load_preview(latest)
        else:
            self.preview_label.setText("Download complete, but no playable file found.")

    def _find_latest_video(self) -> Path | None:
        if not self._current_output_path or not self._current_output_path.exists():
            return None
        candidates = list(self._current_output_path.glob("*.mp4"))
        if not candidates:
            return None
        return max(candidates, key=lambda p: p.stat().st_mtime)

    def _load_preview(self, path: Path) -> None:
        if not path.exists():
            self.preview_label.setText("Video file not found.")
            return
        self.preview_label.setText("")
        url = QUrl.fromLocalFile(str(path))
        self.player.setSource(url)
        self.player.play()

    def _set_status_color(self, error: bool) -> None:
        color = "#b00020" if error else "#2a2a2a"
        self.status.setStyleSheet(f"color: {color};")

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

    def _sync_duration(self, duration: int) -> None:
        self.position_slider.setRange(0, duration)

    def _toggle_mute(self, checked: bool) -> None:
        self.audio_output.setMuted(checked)
        self.mute_btn.setText("Muted" if checked else "Mute")

    def _set_volume(self, value: int) -> None:
        self.audio_output.setVolume(value / 100)

    def _seek_relative(self, delta_ms: int) -> None:
        position = self.player.position()
        duration = self.player.duration()
        new_pos = max(0, min(position + delta_ms, duration if duration > 0 else 0))
        self.player.setPosition(new_pos)

    def _open_video_file(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Open Video",
            str(self.default_downloads),
            "Video Files (*.mp4 *.mkv *.webm *.mov);;All Files (*)",
        )
        if not file_path:
            return
        self._load_preview(Path(file_path))

    def _on_player_error(self, error: QMediaPlayer.Error, error_string: str) -> None:
        if error == QMediaPlayer.NoError:
            return
        message = error_string or "Playback error."
        self.preview_label.setText(message)
        self.status.setText(message)
        self._set_status_color(error=True)

    def _on_media_status(self, status: QMediaPlayer.MediaStatus) -> None:
        if status == QMediaPlayer.LoadingMedia:
            self.preview_label.setText("Loading video...")
        elif status == QMediaPlayer.BufferingMedia:
            self.preview_label.setText("Buffering...")
        elif status in (QMediaPlayer.LoadedMedia, QMediaPlayer.BufferedMedia):
            self.preview_label.setText("")
        elif status == QMediaPlayer.EndOfMedia:
            self.player.setPosition(0)
            self.player.play()

    def _apply_styles(self) -> None:
        self.setStyleSheet(
            """
            QMainWindow { background: #ffffff; }
            QLabel { color: #000000; }
            QGroupBox { color: #000000; background: #ffffff; }
            QCheckBox { color: #000000; }
            QPushButton {
                background: #ecebff;
                color: #1f1f1f;
                padding: 8px 14px;
                border-radius: 10px;
                font-weight: 600;
                border: 1px solid #d7d4f2;
            }
            QPushButton:disabled {
                color: #777777;
                background: #f1f1f1;
            }
            QProgressBar {
                height: 20px;
                border-radius: 10px;
                background: #eceaf6;
                text-align: center;
                color: #1f1f1f;
            }
            QProgressBar::chunk {
                background: #9aa4ff;
                border-radius: 10px;
            }
            QLineEdit, QComboBox {
                background: #ffffff;
                color: #000000;
                min-height: 40px;
                padding: 0px 10px;
                border: 1px solid #b8b8c9;
                border-radius: 8px;
                font-size: 13px;
            }
            QComboBox::drop-down { width: 26px; }
            QComboBox::drop-down { width: 18px; border: 0px; background: transparent; }
            QComboBox::down-arrow { width: 10px; height: 10px; }
            QComboBox QAbstractItemView {
                background: #ffffff;
                color: #000000;
            }
            QSlider#SeekSlider::groove:horizontal {
                height: 6px;
                background: #e0e0e0;
                border-radius: 3px;
            }
            QSlider#SeekSlider::handle:horizontal {
                width: 14px;
                margin: -6px 0;
                border-radius: 7px;
                background: #6b6b6b;
            }
            QWidget#PreviewCard {
                background: #ffffff;
                border: 1px solid #e2e2e2;
                border-radius: 14px;
            }
            QPushButton#FolderButton {
                min-height: 34px;
            }
            """
        )


def main() -> None:
    app = QApplication(sys.argv)
    app.setWindowIcon(app.style().standardIcon(QStyle.SP_MediaPlay))
    window = VideoDownloader()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
