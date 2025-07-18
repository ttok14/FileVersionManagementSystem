# main.py
# 메인 애플리케이션 - 모든 모듈 조합

import sys
import os
import shutil
import subprocess
from typing import Optional, Dict, List
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QSplitter, QGroupBox, QMessageBox, QFileDialog, QMenuBar,
    QMenu, QStatusBar, QToolBar, QTabWidget, QPushButton, QLabel,
    QTextEdit
)
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QAction, QKeySequence, QIcon, QFont

# 프로젝트 모듈 import
from common.utils import ValidationUtils, FileUtils
from core.models import ProjectSettings, FileStatus, Version, FileDiff, FileChangeType
from core.project import Project, ProjectManager
from ui.widgets import (
    FileTreeWidget, VersionHistoryWidget, DiffViewerWidget,
    ProjectInfoWidget, StatusBarWidget
)
from ui.dialogs import (
    ProjectSetupDialog, ProjectSettingsDialog, SaveOptionsDialog,
    DiffViewerDialog, SearchDialog, VersionCompareDialog, ProgressDialog
)


class MainWindow(QMainWindow):
    """메인 윈도우"""

    def __init__(self):
        super().__init__()
        self.project_manager = ProjectManager()
        self.current_project: Optional[Project] = None
        self.file_tree: Optional[FileTreeWidget] = None
        self.version_history: Optional[VersionHistoryWidget] = None
        self.diff_viewer: Optional[DiffViewerWidget] = None
        # --- NEW: 내용 표시를 위한 위젯 추가 ---
        self.content_viewer: Optional[QTextEdit] = None
        self.project_info: Optional[ProjectInfoWidget] = None
        self.status_widget: Optional[StatusBarWidget] = None
        self.version_note_tab: Optional[QWidget] = None
        self.version_note_edit: Optional[QTextEdit] = None
        self.save_note_btn: Optional[QPushButton] = None
        self.search_dialog: Optional[SearchDialog] = None
        self.compare_dialog: Optional[VersionCompareDialog] = None
        
        self.setup_ui()
        self.setup_menus()
        self.setup_toolbar()
        self.setup_statusbar()
        self.setup_shortcuts()
        
        self.enable_project_actions(False)

    def save_changes(self):
        """변경사항 저장 또는 새 버전 생성 시, 현재 열린 노트도 함께 저장합니다."""
        if not self.current_project: return
        
        try:
            # --- NEW: 버전 저장 전, 현재 노트 내용을 먼저 저장합니다. ---
            self.save_current_note(show_message=False)

            modified_files = self.current_project.get_modified_files()
            
            if not modified_files:
                reply = QMessageBox.question(self, "확인", "변경된 파일이 없습니다.\n그래도 새 버전을 만드시겠습니까?", QMessageBox.Yes | QMessageBox.No)
                if reply == QMessageBox.No:
                    # '현재 버전에 저장'은 비활성화
                    dialog = SaveOptionsDialog(modified_files, self.current_project.current_version, self.current_project.latest_version_number + 1, self)
                    dialog.save_current_btn.setEnabled(False)
                    dialog.save_current_btn.setToolTip("변경된 파일이 없어 저장할 내용이 없습니다.")
                    if dialog.exec() and dialog.result_type == "new":
                        new_version = self.current_project.create_new_version(dialog.description)
                        self.refresh_all_ui()
                        QMessageBox.information(self, "성공", f"v{new_version.number} 버전이 생성되었습니다.")
                    return

            next_version_num = self.current_project.latest_version_number + 1
            dialog = SaveOptionsDialog(modified_files, self.current_project.current_version, next_version_num, self)

            if dialog.exec():
                save_type, description = dialog.get_result()
                if save_type == "current":
                    if self.current_project.save_to_current_version():
                        self.refresh_all_ui()
                        QMessageBox.information(self, "성공", f"v{self.current_project.current_version}에 현재 상태가 저장되었습니다.")
                    else:
                        QMessageBox.warning(self, "경고", "현재 버전에 저장할 수 없습니다.")

                elif save_type == "new":
                    new_version = self.current_project.create_new_version(description)
                    self.refresh_all_ui()
                    QMessageBox.information(self, "성공", f"v{new_version.number} 버전이 생성되었습니다.")
        except Exception as e:
            QMessageBox.critical(self, "오류", f"저장 실패:\n{str(e)}")

    def save_current_note(self, show_message=True):
        """'노트 저장' 버튼 또는 다른 저장 로직에서 호출됩니다."""
        if not self.current_project: return
        
        selected_version = self.version_history.get_selected_version()
        if not selected_version:
            if show_message:
                QMessageBox.warning(self, "알림", "노트를 저장할 버전을 선택해주세요.")
            return
            
        notes_text = self.version_note_edit.toPlainText()
        
        # 노트 내용이 실제로 변경되었을 때만 저장
        if selected_version.change_notes != notes_text:
            try:
                success = self.current_project.update_version_notes(selected_version.number, notes_text)
                if success and show_message:
                    self.statusBar().showMessage(f"v{selected_version.number}의 노트가 저장되었습니다.", 2000)
            except Exception as e:
                if show_message:
                    QMessageBox.critical(self, "오류", f"노트 저장 중 예외 발생: {e}")

    def setup_ui(self):
        self.setWindowTitle("심플 파일 버전 관리")
        self.setGeometry(100, 100, 1400, 800)
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_splitter = QSplitter(Qt.Horizontal)
        left_panel = self.create_file_panel()
        main_splitter.addWidget(left_panel)
        center_panel = self.create_center_panel()
        main_splitter.addWidget(center_panel)
        right_panel = self.create_version_panel()
        main_splitter.addWidget(right_panel)
        main_splitter.setSizes([350, 600, 350])
        main_layout.addWidget(main_splitter)

    def create_file_panel(self) -> QWidget:
        panel = QGroupBox("📄 파일 상태")
        layout = QVBoxLayout(panel)
        self.file_tree = FileTreeWidget()
        layout.addWidget(self.file_tree)
        file_buttons = QHBoxLayout()
        self.sync_btn = QPushButton("🔄 싱크 (F5)")
        self.sync_btn.setToolTip("현재 폴더의 모든 변경사항(추가/삭제/수정)을 감지합니다")
        self.sync_btn.setStyleSheet("""
            QPushButton { background-color: #4CAF50; color: white; font-weight: bold; padding: 8px 12px; border-radius: 4px; }
            QPushButton:hover { background-color: #45a049; }
        """)
        self.add_files_btn = QPushButton("➕ 파일 추가")
        self.remove_files_btn = QPushButton("➖ 파일 제거")
        file_buttons.addWidget(self.sync_btn)
        file_buttons.addWidget(QLabel("|"))
        file_buttons.addWidget(self.add_files_btn)
        file_buttons.addWidget(self.remove_files_btn)
        file_buttons.addStretch()
        layout.addLayout(file_buttons)
        self.file_tree.file_double_clicked.connect(self.on_file_double_clicked)
        self.file_tree.itemSelectionChanged.connect(self.on_file_selection_changed)
        # --- NEW: 컨텍스트 메뉴 시그널 연결 ---
        self.file_tree.open_in_explorer_requested.connect(self.open_in_explorer)
        self.file_tree.open_file_requested.connect(self.open_file)
        self.sync_btn.clicked.connect(self.perform_sync)
        self.add_files_btn.clicked.connect(self.add_files_to_track)
        self.remove_files_btn.clicked.connect(self.remove_files_from_track)
        return panel

    def create_center_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        tab_widget = QTabWidget()

        # --- NEW: '내용' 탭을 먼저 추가 ---
        self.content_viewer = QTextEdit()
        self.content_viewer.setReadOnly(True)
        self.content_viewer.setFont(QFont("Consolas", 9))
        self.content_viewer.setPlaceholderText("왼쪽 목록에서 파일을 선택하면 내용이 여기에 표시됩니다.")
        tab_widget.addTab(self.content_viewer, "📄 내용")

        # --- MODIFIED: '변경사항' 탭을 두 번째로 추가 ---
        self.diff_viewer = DiffViewerWidget()
        tab_widget.addTab(self.diff_viewer, "🔍 변경사항")
        
        self.version_note_tab = self.create_version_note_tab()
        tab_widget.addTab(self.version_note_tab, "📝 버전 노트")
        self.project_info = ProjectInfoWidget()
        tab_widget.addTab(self.project_info, "📋 프로젝트 정보")
        layout.addWidget(tab_widget)
        return panel

    def create_version_note_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        self.version_note_edit = QTextEdit()
        self.version_note_edit.setPlaceholderText("선택된 버전에 대한 노트를 작성하세요...")
        layout.addWidget(self.version_note_edit)
        button_layout = QHBoxLayout()
        self.save_note_btn = QPushButton("💾 노트 저장")
        self.save_note_btn.setToolTip("현재 작성된 노트 내용을 이 버전에 저장합니다.")
        button_layout.addStretch()
        button_layout.addWidget(self.save_note_btn)
        layout.addLayout(button_layout)
        self.save_note_btn.clicked.connect(self.save_current_note)
        return widget

    def create_version_panel(self) -> QWidget:
        panel = QGroupBox("📚 버전 히스토리")
        layout = QVBoxLayout(panel)
        self.version_history = VersionHistoryWidget()
        layout.addWidget(self.version_history)
        version_buttons = QHBoxLayout()
        self.rollback_btn = QPushButton("⏪ 버전 전환")
        self.compare_btn = QPushButton("🔍 비교")
        version_buttons.addWidget(self.rollback_btn)
        version_buttons.addWidget(self.compare_btn)
        version_buttons.addStretch()
        layout.addLayout(version_buttons)
        self.version_history.version_double_clicked.connect(self.on_version_double_clicked)
        self.version_history.version_selection_changed.connect(self.on_version_selection_changed)
        self.rollback_btn.clicked.connect(self.rollback_to_version)
        self.compare_btn.clicked.connect(self.show_version_compare_dialog)
        return panel

    def setup_menus(self):
        menubar = self.menuBar()
        file_menu = menubar.addMenu("파일(&F)")
        self.new_project_action = QAction("새 프로젝트(&N)", self); self.new_project_action.setShortcut(QKeySequence.New); self.new_project_action.triggered.connect(self.create_new_project); file_menu.addAction(self.new_project_action)
        self.open_project_action = QAction("프로젝트 열기(&O)", self); self.open_project_action.setShortcut(QKeySequence.Open); self.open_project_action.triggered.connect(self.open_project); file_menu.addAction(self.open_project_action)
        file_menu.addSeparator()
        self.save_action = QAction("저장(&S)", self); self.save_action.setShortcut(QKeySequence.Save); self.save_action.triggered.connect(self.save_changes); file_menu.addAction(self.save_action)
        file_menu.addSeparator()
        self.exit_action = QAction("종료(&X)", self); self.exit_action.setShortcut(QKeySequence.Quit); self.exit_action.triggered.connect(self.close); file_menu.addAction(self.exit_action)
        edit_menu = menubar.addMenu("편집(&E)")
        self.sync_action = QAction("싱크(&Y)", self); self.sync_action.setShortcut(QKeySequence("F5")); self.sync_action.triggered.connect(self.perform_sync); edit_menu.addAction(self.sync_action)
        edit_menu.addSeparator()
        self.search_action = QAction("검색(&F)", self); self.search_action.setShortcut(QKeySequence.Find); self.search_action.triggered.connect(self.show_search_dialog); edit_menu.addAction(self.search_action)
        project_menu = menubar.addMenu("프로젝트(&P)")
        self.project_settings_action = QAction("프로젝트 설정(&S)", self); self.project_settings_action.triggered.connect(self.edit_project_settings); project_menu.addAction(self.project_settings_action)
        project_menu.addSeparator()
        self.add_files_action = QAction("파일 추가(&A)", self); self.add_files_action.triggered.connect(self.add_files_to_track); project_menu.addAction(self.add_files_action)
        view_menu = menubar.addMenu("보기(&V)")
        self.show_diff_action = QAction("변경사항 보기(&D)", self); self.show_diff_action.triggered.connect(self.show_selected_file_diff); view_menu.addAction(self.show_diff_action)
        self.compare_versions_action = QAction("버전 비교(&C)", self); self.compare_versions_action.triggered.connect(self.show_version_compare_dialog); view_menu.addAction(self.compare_versions_action)
        help_menu = menubar.addMenu("도움말(&H)")
        self.about_action = QAction("정보(&A)", self); self.about_action.triggered.connect(self.show_about); help_menu.addAction(self.about_action)

    def setup_toolbar(self):
        toolbar = self.addToolBar("메인"); toolbar.setMovable(False)
        toolbar.addAction(self.new_project_action); toolbar.addAction(self.open_project_action); toolbar.addSeparator()
        toolbar.addAction(self.save_action); toolbar.addAction(self.sync_action); toolbar.addSeparator()
        toolbar.addAction(self.search_action)

    def setup_statusbar(self):
        self.status_widget = StatusBarWidget(); self.statusBar().addPermanentWidget(self.status_widget); self.status_widget.update_status("준비")

    def setup_shortcuts(self): pass

    def enable_project_actions(self, enabled: bool):
        actions = [self.save_action, self.sync_action, self.search_action, self.project_settings_action, self.add_files_action, self.show_diff_action, self.compare_versions_action]
        buttons = [self.sync_btn, self.add_files_btn, self.remove_files_btn, self.rollback_btn, self.compare_btn]
        for item in actions + buttons: item.setEnabled(enabled)

    def create_new_project(self):
        dialog = ProjectSetupDialog(self)
        if dialog.exec():
            project_name, initial_files, settings = dialog.get_values()
            try:
                project = self.project_manager.create_project(project_name, initial_files, settings)
                self.load_project(project)
                QMessageBox.information(self, "성공", f"프로젝트 '{project_name}'이 생성되었습니다.")
            except Exception as e:
                QMessageBox.critical(self, "오류", f"프로젝트 생성 실패:\n{str(e)}")

    def open_project(self):
        project_file, _ = QFileDialog.getOpenFileName(self, "프로젝트 파일 선택", "", "Project Files (project.json)")
        if project_file:
            try:
                project = self.project_manager.load_project(project_file)
                self.load_project(project)
            except Exception as e:
                QMessageBox.critical(self, "오류", f"프로젝트 로드 실패:\n{str(e)}")

    def load_project(self, project: Project):
        self.current_project = project
        self.setWindowTitle(f"심플 파일 버전 관리 - {project.settings.name}")
        self.refresh_all_ui()
        self.enable_project_actions(True)
        self.status_widget.update_status(f"프로젝트 '{project.settings.name}' 로드됨")

    def refresh_all_ui(self):
        if not self.current_project: return
        self.refresh_file_status()
        self.refresh_version_history()
        self.refresh_project_info()

    def refresh_file_status(self):
        if not self.current_project: return
        try:
            file_statuses = self.current_project.get_file_statuses()
            self.file_tree.update_files(file_statuses)
            modified_count = len([s for s in file_statuses if s.change_type != FileChangeType.UNCHANGED])
            self.status_widget.update_changed_files(modified_count)
            if modified_count > 0: self.status_widget.update_status(f"변경된 파일 {modified_count}개 감지됨")
            else: self.status_widget.update_status("모든 파일이 최신 상태입니다")
        except Exception as e:
            QMessageBox.critical(self, "오류", f"파일 상태 표시 실패:\n{str(e)}")

    def perform_sync(self):
        if not self.current_project: return
        try:
            changes = self.current_project.get_all_changes()
            added, removed, modified = changes["added"], changes["removed"], changes["modified"]
            if not added and not removed and not modified:
                QMessageBox.information(self, "동기화 완료", "프로젝트에 변경사항이 없습니다.")
                self.refresh_file_status()
                return
            message_parts = []
            if added: message_parts.append(f"✨ 새로 추가된 파일: {len(added)}개")
            if removed: message_parts.append(f"❌ 삭제된 파일: {len(removed)}개")
            if modified: message_parts.append(f"⚠️ 내용이 변경된 파일: {len(modified)}개")
            message = "\n".join(message_parts) + "\n\n파일 목록을 동기화하시겠습니까?\n(내용 변경은 '저장'해야 반영됩니다)"
            reply = QMessageBox.question(self, "폴더 동기화", message, QMessageBox.Yes | QMessageBox.No)
            if reply == QMessageBox.Yes:
                self.current_project.apply_sync_changes(changes)
                self.refresh_file_status()
                QMessageBox.information(self, "성공", "파일 목록 동기화가 완료되었습니다.")
        except Exception as e:
            QMessageBox.critical(self, "오류", f"동기화 실패:\n{str(e)}")

    def rollback_to_version(self):
        if not self.current_project: return
        selected_version = self.version_history.get_selected_version()
        if not selected_version:
            QMessageBox.information(self, "알림", "전환할 버전을 선택해주세요.")
            return
        reply = QMessageBox.question(self, "확인", f"작업 버전을 v{selected_version.number}으로 전환하시겠습니까?\n\n(현재 작업 내용은 저장되지 않습니다)", QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            try:
                if self.current_project.rollback_to_version(selected_version.number):
                    self.refresh_all_ui()
                    QMessageBox.information(self, "성공", f"작업 버전을 v{selected_version.number}으로 전환했습니다.")
                else:
                    QMessageBox.warning(self, "경고", "버전 전환에 실패했습니다.")
            except Exception as e:
                QMessageBox.critical(self, "오류", f"버전 전환 실패:\n{str(e)}")

    def on_version_selection_changed(self, version: Version):
        if version:
            self.version_note_edit.setText(version.change_notes)
        else:
            self.version_note_edit.clear()

    def closeEvent(self, event):
        if self.current_project:
            try:
                modified_files = self.current_project.get_modified_files()
                if modified_files:
                    reply = QMessageBox.question(self, "확인", f"저장되지 않은 변경사항이 {len(modified_files)}개 있습니다.\n저장하지 않고 종료하시겠습니까?", QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel)
                    if reply == QMessageBox.Cancel:
                        event.ignore(); return
                    elif reply == QMessageBox.No:
                        self.save_changes()
                        event.ignore(); return
            except Exception: pass
        event.accept()

    def refresh_version_history(self):
        if not self.current_project: return
        try:
            self.version_history.update_versions(self.current_project.versions, self.current_project.current_version)
            self.status_widget.update_version(self.current_project.current_version, len(self.current_project.versions))
        except Exception as e:
            QMessageBox.critical(self, "오류", f"버전 히스토리 새로고침 실패:\n{str(e)}")

    def refresh_project_info(self):
        if not self.current_project: return
        try:
            project_data = {"settings": self.current_project.data.settings.to_dict(), "current_version": self.current_project.current_version, "tracked_files_count": len(self.current_project.tracked_files), "versions": [v.to_dict() for v in self.current_project.versions]}
            self.project_info.update_project_info(project_data)
        except Exception as e:
            QMessageBox.critical(self, "오류", f"프로젝트 정보 새로고침 실패:\n{str(e)}")

    def add_files_to_track(self):
        if not self.current_project: return
        files, _ = QFileDialog.getOpenFileNames(self, "추적할 파일 선택", "", "All Files (*)")
        if files:
            try:
                self.current_project.add_tracked_files(files)
                self.perform_sync()
                QMessageBox.information(self, "성공", f"{len(files)}개 파일이 추가되었습니다.")
            except Exception as e:
                QMessageBox.critical(self, "오류", f"파일 추가 실패:\n{str(e)}")

    def remove_files_from_track(self):
        if not self.current_project: return
        selected_status = self.file_tree.get_selected_file_status()
        if not selected_status:
            QMessageBox.information(self, "알림", "제거할 파일을 선택해주세요."); return
        reply = QMessageBox.question(self, "확인", f"'{selected_status.name}' 파일을 추적 목록에서 제거하고 실제 파일도 삭제하시겠습니까?", QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            try:
                if self.current_project.remove_tracked_file(selected_status.path):
                    self.perform_sync()
                    QMessageBox.information(self, "성공", "파일이 제거되었습니다.")
                else:
                    QMessageBox.warning(self, "경고", "파일 제거에 실패했습니다.")
            except Exception as e:
                QMessageBox.critical(self, "오류", f"파일 제거 실패:\n{str(e)}")

    def show_selected_file_diff(self):
        if not self.current_project: return
        selected_status = self.file_tree.get_selected_file_status()
        if not selected_status:
            QMessageBox.information(self, "알림", "비교할 파일을 선택해주세요."); return
        try:
            diff = self.current_project.compare_with_current(self.current_project.current_version, selected_status.path)
            DiffViewerDialog(diff, self).exec()
        except Exception as e:
            QMessageBox.critical(self, "오류", f"파일 비교 실패:\n{str(e)}")

    def show_version_compare_dialog(self):
        if not self.current_project or len(self.current_project.versions) < 2:
            QMessageBox.information(self, "알림", "비교할 버전이 부족합니다. (최소 2개 필요)"); return
        self.compare_dialog = VersionCompareDialog(self.current_project.versions, self.current_project.current_version, self)
        self.compare_dialog.comparison_requested.connect(self.compare_versions)
        self.compare_dialog.exec()

    def compare_versions(self, old_version, new_version):
        if not self.current_project: return
        try:
            changes = self.current_project.get_version_changes_with_working(old_version) if new_version == -1 else self.current_project.get_version_changes(old_version, new_version)
            if hasattr(self, 'compare_dialog') and self.compare_dialog:
                self.compare_dialog.show_comparison_results(changes)
        except Exception as e:
            QMessageBox.critical(self, "오류", f"버전 비교 실패:\n{str(e)}")

    def show_search_dialog(self):
        if not self.current_project:
            QMessageBox.information(self, "알림", "먼저 프로젝트를 열어주세요."); return
        if not self.search_dialog:
            self.search_dialog = SearchDialog(self)
            self.search_dialog.search_requested.connect(self.perform_search)
            self.search_dialog.result_selected.connect(self.on_search_result_selected)
        self.search_dialog.show(); self.search_dialog.raise_()

    def perform_search(self, query, file_extensions, case_sensitive):
        if not self.current_project: return
        try:
            results = self.current_project.search_in_versions(query, file_extensions, case_sensitive)
            if self.search_dialog:
                self.search_dialog.show_search_results(results)
        except Exception as e:
            QMessageBox.critical(self, "오류", f"검색 실패:\n{str(e)}")

    def on_search_result_selected(self, result_data):
        try:
            diff = self.current_project.compare_with_current(result_data["version"].number, result_data["file_path"])
            self.diff_viewer.show_diff(diff)
        except Exception as e:
            QMessageBox.critical(self, "오류", f"검색 결과 표시 실패:\n{str(e)}")

    def edit_project_settings(self):
        if not self.current_project: return
        dialog = ProjectSettingsDialog(self.current_project.settings, self)
        if dialog.exec():
            try:
                new_settings = dialog.get_settings()
                self.current_project.update_settings(new_settings)
                self.refresh_project_info()
                self.setWindowTitle(f"심플 파일 버전 관리 - {new_settings.name}")
                QMessageBox.information(self, "성공", "프로젝트 설정이 저장되었습니다.")
            except Exception as e:
                QMessageBox.critical(self, "오류", f"설정 저장 실패:\n{str(e)}")

    def on_file_double_clicked(self, file_path): self.show_selected_file_diff()

    def on_file_selection_changed(self):
        """파일 선택이 변경될 때 '내용' 탭과 '변경사항' 탭을 모두 업데이트합니다."""
        selected_status = self.file_tree.get_selected_file_status()
        
        # 뷰어 초기화
        self.diff_viewer.clear_diff()
        self.content_viewer.clear()

        if selected_status and self.current_project:
            try:
                # 1. '변경사항' 탭 업데이트 (기존 로직)
                diff = self.current_project.compare_with_current(self.current_project.current_version, selected_status.path)
                self.diff_viewer.show_diff(diff)

                # 2. '내용' 탭 업데이트 (신규 로직)
                if selected_status.change_type == FileChangeType.DELETED:
                    self.content_viewer.setPlainText("삭제된 파일입니다.")
                elif not selected_status.is_text_file:
                    self.content_viewer.setPlainText(f"바이너리 파일은 내용을 표시할 수 없습니다.\n\n파일 경로: {selected_status.path}\n파일 크기: {selected_status.size_display}")
                else:
                    # 현재 작업 버전 디렉토리에서 파일 경로를 가져옴
                    file_path_in_version = self.current_project.get_working_file_path(selected_status.path)
                    if os.path.exists(file_path_in_version):
                        content = FileUtils.read_file_content(file_path_in_version)
                        self.content_viewer.setPlainText(content)
                    else:
                        self.content_viewer.setPlainText("파일을 찾을 수 없습니다.")

            except Exception as e:
                self.diff_viewer.clear_diff()
                self.content_viewer.setPlainText(f"파일 내용을 불러오는 중 오류가 발생했습니다:\n{e}")
        else:
            self.content_viewer.setPlaceholderText("왼쪽 목록에서 파일을 선택하면 내용이 여기에 표시됩니다.")

    def on_version_double_clicked(self, version_number): self.rollback_to_version()
    def show_about(self): QMessageBox.about(self, "정보", "심플 파일 버전 관리 v1.0\n\n간단하고 직관적인 파일 버전 관리 도구입니다.")

    # --- NEW: 컨텍스트 메뉴 액션 핸들러 ---
    def open_in_explorer(self, relative_path: str):
        """선택된 파일 또는 폴더의 위치를 탐색기에서 엽니다."""
        if not self.current_project: return
        try:
            full_path = self.current_project.get_working_file_path(relative_path)
            
            if not os.path.exists(full_path):
                QMessageBox.warning(self, "경고", "존재하지 않는 파일 또는 폴더입니다.")
                return

            directory = os.path.dirname(full_path) if os.path.isfile(full_path) else full_path
            
            if sys.platform == "win32":
                os.startfile(os.path.realpath(directory))
            elif sys.platform == "darwin":  # macOS
                subprocess.run(["open", directory])
            else:  # Linux
                subprocess.run(["xdg-open", directory])
        except Exception as e:
            QMessageBox.critical(self, "오류", f"탐색기 열기 실패:\n{str(e)}")

    def open_file(self, relative_path: str):
        """선택된 파일을 기본 연결 프로그램으로 엽니다."""
        if not self.current_project: return
        try:
            full_path = self.current_project.get_working_file_path(relative_path)
            if not os.path.isfile(full_path):
                QMessageBox.warning(self, "경고", "존재하지 않는 파일입니다.")
                return
            
            if sys.platform == "win32":
                os.startfile(full_path)
            elif sys.platform == "darwin":
                subprocess.run(["open", full_path])
            else:
                subprocess.run(["xdg-open", full_path])
        except Exception as e:
            QMessageBox.critical(self, "오류", f"파일 열기 실패:\n{str(e)}")


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("심플 파일 버전 관리"); app.setApplicationVersion("1.0.0"); app.setOrganizationName("SimpleDev")
    app.setStyleSheet("""
        QMainWindow { background-color: #f5f5f5; }
        QGroupBox { font-weight: bold; border: 2px solid #cccccc; border-radius: 8px; margin-top: 1ex; padding-top: 10px; background-color: white; }
        QGroupBox::title { subcontrol-origin: margin; left: 15px; padding: 0 8px 0 8px; background-color: white; }
        QTreeWidget, QListWidget { border: 1px solid #dddddd; border-radius: 6px; background-color: white; alternate-background-color: #f9f9f9; }
        QListWidget::item { padding: 10px; border-bottom: 1px solid #eeeeee; min-height: 20px; }
        QTreeWidget::item:selected, QListWidget::item:selected { background-color: #0078d7; color: white; }
        QTreeWidget::item:hover, QListWidget::item:hover { background-color: #e3f2fd; }
        QTreeWidget::item:selected:hover, QListWidget::item:selected:hover { background-color: #005a9e; }
        QTreeWidget::item { padding: 8px; min-height: 20px; }
        QPushButton { padding: 8px 16px; border: 1px solid #cccccc; border-radius: 6px; background-color: #ffffff; font-weight: normal; min-height: 16px; }
        QPushButton:hover { background-color: #f0f0f0; border-color: #999999; }
        QPushButton:pressed { background-color: #e0e0e0; }
        QPushButton:disabled { background-color: #f5f5f5; color: #999999; border-color: #dddddd; }
        QTextEdit { border: 1px solid #dddddd; border-radius: 6px; background-color: white; font-family: 'Consolas', 'Monaco', monospace; }
        QTabWidget::pane { border: 1px solid #cccccc; border-radius: 6px; background-color: white; }
        QTabBar::tab { padding: 8px 16px; margin-right: 2px; background-color: #f0f0f0; border: 1px solid #cccccc; border-bottom: none; border-top-left-radius: 6px; border-top-right-radius: 6px; }
        QTabBar::tab:selected { background-color: white; border-bottom: 1px solid white; }
        QMenuBar { background-color: #f8f8f8; border-bottom: 1px solid #cccccc; }
        QMenuBar::item { padding: 6px 12px; background-color: transparent; }
        QMenuBar::item:selected { background-color: #e0e0e0; border-radius: 4px; }
        QStatusBar { background-color: #f8f8f8; border-top: 1px solid #cccccc; }
        QToolBar { background-color: #f8f8f8; border-bottom: 1px solid #cccccc; spacing: 4px; padding: 4px; }
        QSplitter::handle { background-color: #cccccc; width: 2px; height: 2px; }
        QSplitter::handle:hover { background-color: #2196F3; }
    """)
    window = MainWindow()
    window.show()
    window.status_widget.update_status("새 프로젝트를 생성하거나 기존 프로젝트를 열어주세요")
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
