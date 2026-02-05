import re
import sys
from pathlib import Path

from PySide6.QtCore import QProcess, Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QFrame,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QProgressBar,
    QSizePolicy,
    QSpacerItem,
    QScrollArea,
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
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(24, 24, 24, 24)
        root_layout.setSpacing(0)

        card = QWidget(root)
        card.setObjectName("MainCard")
        card_layout = QHBoxLayout(card)
        card_layout.setContentsMargins(24, 24, 24, 24)
        card_layout.setSpacing(24)

        left = QWidget(card)
        left_layout = QVBoxLayout(left)
        left_layout.setSpacing(12)

        header_row = QHBoxLayout()
        icon_badge = QLabel("DL")
        icon_badge.setAlignment(Qt.AlignCenter)
        icon_badge.setObjectName("IconBadge")
        header_title = QLabel("Downloader")
        header_title.setObjectName("HeaderTitle")
        header_row.addWidget(icon_badge)
        header_row.addWidget(header_title)
        header_row.addStretch(1)

        subtitle = QLabel("Paste a URL, pick a folder, and download with yt-dlp + ffmpeg.")
        subtitle.setWordWrap(True)
        subtitle.setObjectName("SubtitleLabel")

        url_label = QLabel("VIDEO LINK")
        url_label.setObjectName("SectionLabel")
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("Paste URL here...")
        
        save_label = QLabel("SAVE LOCATION")
        save_label.setObjectName("SectionLabel")
        folder_row = QHBoxLayout()
        self.folder_input = QLineEdit()
        self.folder_input.setReadOnly(True)
        self.folder_input.setText(human_path(self.default_downloads))
        self.browse_btn = QPushButton("Choose Folder")
        self.browse_btn.setObjectName("FolderButton")
        self.browse_btn.clicked.connect(self._choose_folder)
        folder_row.addWidget(self.folder_input, 1)
        folder_row.addWidget(self.browse_btn)
        
        subfolder_label = QLabel("SUBFOLDER")
        subfolder_label.setObjectName("SectionLabel")
        name_row = QHBoxLayout()
        self.subfolder_combo = QComboBox()
        self.subfolder_combo.setEditable(False)
        self.subfolder_combo.currentTextChanged.connect(self._on_subfolder_changed)
        self.new_sub_btn = QPushButton("New Folder")
        self.new_sub_btn.setObjectName("FolderButton")
        self.new_sub_btn.clicked.connect(self._create_subfolder)
        name_row.addWidget(self.subfolder_combo, 1)
        name_row.addWidget(self.new_sub_btn)


        tweak_group = QWidget()
        tweak_group.setObjectName("OptionsCard")
        tweak_group.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        tweak_layout = QVBoxLayout(tweak_group)
        tweak_layout.setSpacing(10)
        tweak_layout.setContentsMargins(8, 16, 8, 16)

        quality_label = QLabel("QUALITY")
        quality_label.setObjectName("FieldLabel")
        self.quality_combo = QComboBox()
        self.quality_combo.addItems(["Best", "Worst"])

        resolution_label = QLabel("RESOLUTION CAP")
        resolution_label.setObjectName("FieldLabel")
        self.resolution_combo = QComboBox()
        self.resolution_combo.addItems(["No cap", "480p", "720p", "1080p", "1440p", "2160p"])

        codec_label = QLabel("PREFER CODEC")
        codec_label.setObjectName("FieldLabel")
        self.codec_combo = QComboBox()
        self.codec_combo.addItems(["Any", "AV1", "H.264", "HEVC"])

        container_label = QLabel("FORMAT")
        container_label.setObjectName("FieldLabel")
        self.container_combo = QComboBox()

        audio_label = QLabel("AUDIO")
        audio_label.setObjectName("FieldLabel")
        self.audio_only_toggle = QCheckBox("Audio only")
        self.audio_only_toggle.toggled.connect(self._sync_container_options)

        format_label = QLabel("FORMAT SELECTOR")
        format_label.setObjectName("FieldLabel")
        self.format_input = QLineEdit()
        self.format_input.setPlaceholderText("Optional advanced -f string")

        filename_label = QLabel("FILE NAME")
        filename_label.setObjectName("FieldLabel")
        self.filename_input = QLineEdit()
        self.filename_input.setText("New_Video_Export")

        row_quality_format = QHBoxLayout()
        quality_box = QVBoxLayout()
        quality_box.setSpacing(6)
        quality_box.addWidget(quality_label)
        quality_box.addWidget(self.quality_combo)
        format_box = QVBoxLayout()
        format_box.setSpacing(6)
        format_box.addWidget(container_label)
        format_box.addWidget(self.container_combo)
        row_quality_format.addLayout(quality_box, 1)
        row_quality_format.addSpacing(12)
        row_quality_format.addLayout(format_box, 1)

        row_res_codec = QHBoxLayout()
        res_box = QVBoxLayout()
        res_box.setSpacing(6)
        res_box.addWidget(resolution_label)
        res_box.addWidget(self.resolution_combo)
        codec_box = QVBoxLayout()
        codec_box.setSpacing(6)
        codec_box.addWidget(codec_label)
        codec_box.addWidget(self.codec_combo)
        row_res_codec.addLayout(res_box, 1)
        row_res_codec.addSpacing(12)
        row_res_codec.addLayout(codec_box, 1)

        tweak_layout.addLayout(row_quality_format)
        tweak_layout.addLayout(row_res_codec)
        tweak_layout.addWidget(audio_label)
        tweak_layout.addWidget(self.audio_only_toggle)
        tweak_layout.addWidget(format_label)
        tweak_layout.addWidget(self.format_input)
        tweak_layout.addWidget(filename_label)
        tweak_layout.addWidget(self.filename_input)

        action_row = QHBoxLayout()
        self.download_btn = QPushButton("Download")
        self.download_btn.setObjectName("PrimaryButton")
        self.download_btn.clicked.connect(self._start_download)
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setObjectName("GhostButton")
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
        left_content.setObjectName("LeftPanel")
        left_content_layout = QVBoxLayout(left_content)
        left_content_layout.setSpacing(14)
        divider = QFrame()
        divider.setObjectName("Divider")
        divider.setFixedHeight(1)
        divider.setFrameShape(QFrame.HLine)

        left_content_layout.addLayout(header_row)
        left_content_layout.addWidget(divider)
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
        scroll.setStyleSheet("QScrollArea { background: transparent; } QScrollArea > QWidget { background: transparent; }")
        scroll.setWidget(left_content)

        left_layout.addWidget(scroll)

        card_layout.addWidget(left, 1)
        root_layout.addWidget(card)

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
        height = 46
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

        template_text = self.filename_input.text().strip() or "New_Video_Export"
        if "%(ext)" not in template_text:
            template_text = f"{template_text}.%(ext)s"
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

    def _set_status_color(self, error: bool) -> None:
        color = "#b00020" if error else "#2a2a2a"
        self.status.setStyleSheet(f"color: {color};")


    def _apply_styles(self) -> None:
        self.setStyleSheet(
            """
            QMainWindow { background: #fdeff4; }
            QWidget#MainCard {
                background: #ffffff;
                border: 1px solid #f1d7e6;
                border-radius: 28px;
            }
            QWidget#LeftPanel { background: #ffffff; }
            QLabel { color: #1f2430; }
            QLabel#HeaderTitle { font-size: 18px; font-weight: 700; }
            QLabel#SubtitleLabel { color: #8a8f9c; }
            QLabel#SectionLabel {
                color: #f05aa6;
                font-weight: 700;
                font-size: 11px;
            }
            QLabel#FieldLabel {
                color: #a0a4b2;
                font-weight: 600;
                font-size: 11px;
            }
            QLabel#IconBadge {
                background: #ffe1ef;
                color: #f01d85;
                border-radius: 14px;
                min-width: 36px;
                min-height: 36px;
                font-weight: 700;
            }
            QFrame#Divider { background: #f1d7e6; }
            QLineEdit, QComboBox {
                background: #ffffff;
                color: #1f2430;
                min-height: 46px;
                padding: 0px 7px;
                border: 1px solid #f1d7e6;
                border-radius: 14px;
                font-size: 13px;
            }
            QComboBox::drop-down { width: 18px; border: 0px; background: transparent; }
            QComboBox::down-arrow { width: 10px; height: 10px; }
            QComboBox QAbstractItemView { background: #ffffff; color: #1f2430; }
            QCheckBox { color: #1f2430; }
            QPushButton {
                background: #f6eff6;
                color: #1f2430;
                padding: 8px 16px;
                border-radius: 14px;
                font-weight: 600;
                border: 1px solid #f1d7e6;
            }
            QPushButton#PrimaryButton {
                background: #f01d85;
                color: #ffffff;
                border: none;
                min-height: 54px;
                font-size: 14px;
            }
            QPushButton#GhostButton {
                background: #ffffff;
                color: #1f2430;
                border: 1px solid #f1d7e6;
            }
            QPushButton#FolderButton { min-height: 46px; }
            QProgressBar {
                height: 16px;
                border-radius: 8px;
                background: #f6e7f0;
                text-align: center;
                color: #1f2430;
            }
            QProgressBar::chunk {
                background: #f58abf;
                border-radius: 8px;
            }
            QWidget#OptionsCard {
                background: #ffffff;
                border: 1px solid #f1d7e6;
                border-radius: 18px;
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
