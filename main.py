# main.py
# 메인 애플리케이션 - 모든 모듈 조합

import sys
import os
import shutil
from typing import Optional, Dict, List
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QSplitter, QGroupBox, QMessageBox, QFileDialog, QMenuBar,
    QMenu, QStatusBar, QToolBar, QTabWidget, QPushButton, QLabel
)
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QAction, QKeySequence, QIcon

# 프로젝트 모듈 import
from common.utils import ValidationUtils
from core.models import ProjectSettings, FileStatus, Version, FileDiff
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

        # UI 구성요소들
        self.file_tree: Optional[FileTreeWidget] = None
        self.version_history: Optional[VersionHistoryWidget] = None
        self.diff_viewer: Optional[DiffViewerWidget] = None
        self.project_info: Optional[ProjectInfoWidget] = None
        self.status_widget: Optional[StatusBarWidget] = None

        # 다이얼로그들
        self.search_dialog: Optional[SearchDialog] = None
        self.compare_dialog: Optional[VersionCompareDialog] = None

        self.setup_ui()
        self.setup_menus()
        self.setup_toolbar()
        self.setup_statusbar()
        self.setup_shortcuts()
        self.setup_auto_refresh()

        # 초기 상태 설정 (메뉴 생성 후)
        self.enable_project_actions(False)

    def create_new_project(self):
        """새 프로젝트 생성"""
        dialog = ProjectSetupDialog(self)
        if dialog.exec():
            project_name, initial_files, settings = dialog.get_values()

            try:
                # BUG FIX: 프로젝트 생성과 관련된 모든 로직(폴더 생성, 파일 복사)은
                # ProjectManager에게 위임합니다. UI 계층에서는 데이터만 전달합니다.
                project = self.project_manager.create_project(
                    project_name, initial_files, settings
                )
                self.load_project(project)
                QMessageBox.information(
                    self, "성공",
                    f"프로젝트 '{project_name}'이 생성되었습니다."
                )

            except Exception as e:
                QMessageBox.critical(self, "오류", f"프로젝트 생성 실패:\n{str(e)}")

    # ... 이하 MainWindow의 다른 메서드들은 이전과 동일합니다 ...
    # ... (생략) ...
    def setup_ui(self):
        """UI 구성"""
        self.setWindowTitle("심플 파일 버전 관리")
        self.setGeometry(100, 100, 1400, 800)
        
        # 중앙 위젯
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 메인 레이아웃
        main_layout = QHBoxLayout(central_widget)
        
        # 메인 스플리터 (3분할)
        main_splitter = QSplitter(Qt.Horizontal)
        
        # 왼쪽: 파일 목록
        left_panel = self.create_file_panel()
        main_splitter.addWidget(left_panel)
        
        # 중앙: diff 뷰어 + 프로젝트 정보
        center_panel = self.create_center_panel()
        main_splitter.addWidget(center_panel)
        
        # 오른쪽: 버전 히스토리
        right_panel = self.create_version_panel()
        main_splitter.addWidget(right_panel)
        
        # 스플리터 비율 설정 (파일목록:중앙:버전히스토리 = 3:5:3)
        main_splitter.setSizes([350, 600, 350])
        
        main_layout.addWidget(main_splitter)
        
    def create_file_panel(self) -> QWidget:
        """파일 목록 패널 생성"""
        panel = QGroupBox("📄 파일 상태")
        layout = QVBoxLayout(panel)
        
        self.file_tree = FileTreeWidget()
        layout.addWidget(self.file_tree)
        
        # 파일 관리 버튼들
        file_buttons = QHBoxLayout()
        self.sync_btn = QPushButton("🔄 싱크")
        self.sync_btn.setToolTip("프로젝트 폴더의 모든 파일을 자동으로 감지하여 추적 목록에 추가합니다")
        self.sync_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                font-weight: bold;
                padding: 8px 12px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        
        self.add_files_btn = QPushButton("➕ 파일 추가")
        self.remove_files_btn = QPushButton("➖ 파일 제거")
        
        file_buttons.addWidget(self.sync_btn)
        file_buttons.addWidget(QLabel("|"))  # 구분선
        file_buttons.addWidget(self.add_files_btn)
        file_buttons.addWidget(self.remove_files_btn)
        file_buttons.addStretch()
        
        layout.addLayout(file_buttons)
        
        # 시그널 연결
        self.file_tree.file_double_clicked.connect(self.on_file_double_clicked)
        self.file_tree.itemSelectionChanged.connect(self.on_file_selection_changed)
        self.sync_btn.clicked.connect(self.sync_project_folder)
        self.add_files_btn.clicked.connect(self.add_files_to_track)
        self.remove_files_btn.clicked.connect(self.remove_files_from_track)
        
        return panel
        
    def create_center_panel(self) -> QWidget:
        """중앙 패널 생성 (diff 뷰어 + 프로젝트 정보)"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        
        # 탭 위젯
        tab_widget = QTabWidget()
        
        # Diff 뷰어 탭
        self.diff_viewer = DiffViewerWidget()
        tab_widget.addTab(self.diff_viewer, "🔍 변경사항")
        
        # 프로젝트 정보 탭
        self.project_info = ProjectInfoWidget()
        tab_widget.addTab(self.project_info, "📋 프로젝트 정보")
        
        layout.addWidget(tab_widget)
        
        return panel
        
    def create_version_panel(self) -> QWidget:
        """버전 히스토리 패널 생성"""
        panel = QGroupBox("📚 버전 히스토리")
        layout = QVBoxLayout(panel)
        
        self.version_history = VersionHistoryWidget()
        layout.addWidget(self.version_history)
        
        # 버전 관리 버튼들
        version_buttons = QHBoxLayout()
        self.rollback_btn = QPushButton("⏪ 롤백")
        self.compare_btn = QPushButton("🔍 비교")
        
        version_buttons.addWidget(self.rollback_btn)
        version_buttons.addWidget(self.compare_btn)
        version_buttons.addStretch()
        
        layout.addLayout(version_buttons)
        
        # 시그널 연결
        self.version_history.version_double_clicked.connect(self.on_version_double_clicked)
        self.version_history.itemSelectionChanged.connect(self.on_version_selection_changed)
        self.rollback_btn.clicked.connect(self.rollback_to_version)
        self.compare_btn.clicked.connect(self.show_version_compare_dialog)
        
        return panel
    
    def setup_menus(self):
        """메뉴바 설정"""
        menubar = self.menuBar()
        
        # 파일 메뉴
        file_menu = menubar.addMenu("파일(&F)")
        
        self.new_project_action = QAction("새 프로젝트(&N)", self)
        self.new_project_action.setShortcut(QKeySequence.New)
        self.new_project_action.triggered.connect(self.create_new_project)
        file_menu.addAction(self.new_project_action)
        
        self.open_project_action = QAction("프로젝트 열기(&O)", self)
        self.open_project_action.setShortcut(QKeySequence.Open)
        self.open_project_action.triggered.connect(self.open_project)
        file_menu.addAction(self.open_project_action)
        
        file_menu.addSeparator()
        
        self.save_action = QAction("저장(&S)", self)
        self.save_action.setShortcut(QKeySequence.Save)
        self.save_action.triggered.connect(self.save_changes)
        file_menu.addAction(self.save_action)
        
        file_menu.addSeparator()
        
        self.exit_action = QAction("종료(&X)", self)
        self.exit_action.setShortcut(QKeySequence.Quit)
        self.exit_action.triggered.connect(self.close)
        file_menu.addAction(self.exit_action)
        
        # 편집 메뉴
        edit_menu = menubar.addMenu("편집(&E)")
        
        self.refresh_action = QAction("새로고침(&R)", self)
        self.refresh_action.setShortcut(QKeySequence("F5"))
        self.refresh_action.triggered.connect(self.refresh_file_status)
        edit_menu.addAction(self.refresh_action)
        
        self.sync_action = QAction("폴더 동기화(&Y)", self)
        self.sync_action.setShortcut(QKeySequence("Ctrl+R"))
        self.sync_action.triggered.connect(self.sync_project_folder)
        edit_menu.addAction(self.sync_action)
        
        edit_menu.addSeparator()
        
        self.search_action = QAction("검색(&F)", self)
        self.search_action.setShortcut(QKeySequence.Find)
        self.search_action.triggered.connect(self.show_search_dialog)
        edit_menu.addAction(self.search_action)
        
        # 프로젝트 메뉴
        project_menu = menubar.addMenu("프로젝트(&P)")
        
        self.project_settings_action = QAction("프로젝트 설정(&S)", self)
        self.project_settings_action.triggered.connect(self.edit_project_settings)
        project_menu.addAction(self.project_settings_action)
        
        project_menu.addSeparator()
        
        self.add_files_action = QAction("파일 추가(&A)", self)
        self.add_files_action.triggered.connect(self.add_files_to_track)
        project_menu.addAction(self.add_files_action)
        
        # 보기 메뉴
        view_menu = menubar.addMenu("보기(&V)")
        
        self.show_diff_action = QAction("변경사항 보기(&D)", self)
        self.show_diff_action.triggered.connect(self.show_selected_file_diff)
        view_menu.addAction(self.show_diff_action)
        
        self.compare_versions_action = QAction("버전 비교(&C)", self)
        self.compare_versions_action.triggered.connect(self.show_version_compare_dialog)
        view_menu.addAction(self.compare_versions_action)
        
        # 도움말 메뉴
        help_menu = menubar.addMenu("도움말(&H)")
        
        self.about_action = QAction("정보(&A)", self)
        self.about_action.triggered.connect(self.show_about)
        help_menu.addAction(self.about_action)
    
    def setup_toolbar(self):
        """툴바 설정"""
        toolbar = self.addToolBar("메인")
        toolbar.setMovable(False)
        
        # 주요 액션들 추가
        toolbar.addAction(self.new_project_action)
        toolbar.addAction(self.open_project_action)
        toolbar.addSeparator()
        toolbar.addAction(self.save_action)
        toolbar.addAction(self.refresh_action)
        toolbar.addAction(self.sync_action)
        toolbar.addSeparator()
        toolbar.addAction(self.search_action)
        
    def setup_statusbar(self):
        """상태바 설정"""
        self.status_widget = StatusBarWidget()
        self.statusBar().addPermanentWidget(self.status_widget)
        self.status_widget.update_status("준비")
        
    def setup_shortcuts(self):
        """단축키 설정"""
        # 이미 메뉴에서 설정했지만, 추가 단축키들
        pass
        
    def setup_auto_refresh(self):
        """자동 새로고침 설정"""
        # 포커스 감지용 타이머 (윈도우가 포커스를 받을 때 새로고침)
        self.focus_timer = QTimer()
        self.focus_timer.timeout.connect(self.on_focus_gained)
        self.focus_timer.setSingleShot(True)
        
    def enable_project_actions(self, enabled: bool):
        """프로젝트 관련 액션 활성화/비활성화"""
        actions = [
            self.save_action, self.refresh_action, self.sync_action, self.search_action,
            self.project_settings_action, self.add_files_action,
            self.show_diff_action, self.compare_versions_action
        ]
        
        buttons = [
            self.sync_btn, self.add_files_btn, self.remove_files_btn,
            self.rollback_btn, self.compare_btn
        ]
        
        for action in actions:
            action.setEnabled(enabled)
            
        for button in buttons:
            button.setEnabled(enabled)
    
    def open_project(self):
        """기존 프로젝트 열기"""
        project_file, _ = QFileDialog.getOpenFileName(
            self, "프로젝트 파일 선택", "", "Project Files (project.json)"
        )
        
        if project_file:
            try:
                project = self.project_manager.load_project(project_file)
                self.load_project(project)
                
            except Exception as e:
                QMessageBox.critical(self, "오류", f"프로젝트 로드 실패:\n{str(e)}")
                
    def load_project(self, project: Project):
        """프로젝트 로드"""
        self.current_project = project
        
        # 윈도우 제목 업데이트
        self.setWindowTitle(f"심플 파일 버전 관리 - {project.settings.name}")
        
        # UI 업데이트
        self.refresh_all_ui()
        
        # 액션 활성화
        self.enable_project_actions(True)
        
        # 상태 업데이트
        self.status_widget.update_status(f"프로젝트 '{project.settings.name}' 로드됨")
        
    def refresh_all_ui(self):
        """모든 UI 새로고침"""
        if not self.current_project:
            return
            
        # 파일 상태 새로고침
        self.refresh_file_status()
        
        # 버전 히스토리 새로고침
        self.refresh_version_history()
        
        # 프로젝트 정보 새로고침
        self.refresh_project_info()
        
    def refresh_file_status(self):
        """파일 상태 새로고침"""
        if not self.current_project:
            return
            
        try:
            file_statuses = self.current_project.get_file_statuses()
            self.file_tree.update_files(file_statuses)
            
            # 상태바 업데이트
            modified_count = len([s for s in file_statuses if s.change_type.value != "unchanged"])
            self.status_widget.update_changed_files(modified_count)
            
            if modified_count > 0:
                self.status_widget.update_status(f"변경된 파일 {modified_count}개")
            else:
                self.status_widget.update_status("모든 파일이 최신 상태입니다")
                
        except Exception as e:
            QMessageBox.critical(self, "오류", f"파일 상태 새로고침 실패:\n{str(e)}")
        
    def refresh_version_history(self):
        """버전 히스토리 새로고침"""
        if not self.current_project:
            return
            
        try:
            self.version_history.update_versions(
                self.current_project.versions, 
                self.current_project.current_version
            )
            
            # 상태바 버전 정보 업데이트
            self.status_widget.update_version(
                self.current_project.current_version,
                len(self.current_project.versions)
            )
            
        except Exception as e:
            QMessageBox.critical(self, "오류", f"버전 히스토리 새로고침 실패:\n{str(e)}")
        
    def refresh_project_info(self):
        """프로젝트 정보 새로고침"""
        if not self.current_project:
            return
            
        try:
            project_data = {
                "settings": self.current_project.data.settings.to_dict(),
                "current_version": self.current_project.current_version,
                "tracked_files_count": len(self.current_project.tracked_files),
                "versions": [v.to_dict() for v in self.current_project.versions]
            }
            
            self.project_info.update_project_info(project_data)
            
        except Exception as e:
            QMessageBox.critical(self, "오류", f"프로젝트 정보 새로고침 실패:\n{str(e)}")
    
    def add_files_to_track(self):
        """추적할 파일 추가"""
        if not self.current_project:
            return
            
        files, _ = QFileDialog.getOpenFileNames(
            self, "추적할 파일 선택", "", "All Files (*)"
        )
        
        if files:
            try:
                self.current_project.add_tracked_files(files)
                self.refresh_file_status()
                
                QMessageBox.information(
                    self, "성공", 
                    f"{len(files)}개 파일이 추가되었습니다."
                )
                
            except Exception as e:
                QMessageBox.critical(self, "오류", f"파일 추가 실패:\n{str(e)}")
                
    def sync_project_folder(self):
        """프로젝트 폴더 동기화"""
        if not self.current_project:
            return
        
        try:
            # 프로젝트 폴더 스캔
            changes = self.current_project.sync_project_folder()
            
            if not changes["added"] and not changes["removed"]:
                QMessageBox.information(
                    self, "동기화 완료", 
                    "프로젝트 폴더에 변경사항이 없습니다."
                )
                return
            
            # 변경사항 표시
            message_parts = []
            if changes["added"]:
                message_parts.append(f"📁 새로 발견된 파일: {len(changes['added'])}개")
            if changes["removed"]:
                message_parts.append(f"❌ 삭제된 파일: {len(changes['removed'])}개")
            if changes["existing"]:
                message_parts.append(f"✅ 기존 파일: {len(changes['existing'])}개")
            
            message = "\n".join(message_parts)
            message += "\n\n동기화를 진행하시겠습니까?"
            
            reply = QMessageBox.question(
                self, "폴더 동기화", message,
                QMessageBox.Yes | QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                # 변경사항 적용
                self.current_project.apply_sync_changes(changes)
                
                # UI 새로고침
                self.refresh_file_status()
                
                QMessageBox.information(
                    self, "성공", 
                    f"동기화가 완료되었습니다.\n"
                    f"추가: {len(changes['added'])}개, "
                    f"제거: {len(changes['removed'])}개"
                )
                
        except Exception as e:
            QMessageBox.critical(self, "오류", f"동기화 실패:\n{str(e)}")
    
    def remove_files_from_track(self):
        """추적 파일 제거"""
        if not self.current_project:
            return
            
        selected_status = self.file_tree.get_selected_file_status()
        if not selected_status:
            QMessageBox.information(self, "알림", "제거할 파일을 선택해주세요.")
            return
            
        reply = QMessageBox.question(
            self, "확인", 
            f"'{selected_status.name}' 파일을 추적 목록에서 제거하시겠습니까?\n\n"
            "파일 자체는 삭제되지 않습니다.",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            try:
                success = self.current_project.remove_tracked_file(selected_status.path)
                if success:
                    self.refresh_file_status()
                    QMessageBox.information(self, "성공", "파일이 추적 목록에서 제거되었습니다.")
                else:
                    QMessageBox.warning(self, "경고", "파일 제거에 실패했습니다.")
                    
            except Exception as e:
                QMessageBox.critical(self, "오류", f"파일 제거 실패:\n{str(e)}")
    
    def save_changes(self):
        """변경사항 저장"""
        if not self.current_project:
            return
            
        try:
            # 변경된 파일들 확인
            modified_files = self.current_project.get_modified_files()
            
            if not modified_files:
                QMessageBox.information(self, "알림", "변경된 파일이 없습니다.")
                return
                
            # 저장 옵션 다이얼로그
            dialog = SaveOptionsDialog(
                modified_files, 
                self.current_project.current_version, 
                self
            )
            
            if dialog.exec():
                save_type, description = dialog.get_result()
                
                if save_type == "current":
                    # 현재 버전에 저장
                    success = self.current_project.save_to_current_version()
                    if success:
                        self.refresh_all_ui()
                        QMessageBox.information(
                            self, "성공", 
                            f"v{self.current_project.current_version}에 저장되었습니다."
                        )
                    else:
                        QMessageBox.warning(self, "경고", "현재 버전에 저장할 수 없습니다.")
                        
                elif save_type == "new":
                    # 새 버전 생성
                    new_version = self.current_project.create_new_version(description)
                    self.refresh_all_ui()
                    QMessageBox.information(
                        self, "성공", 
                        f"v{new_version.number} 버전이 생성되었습니다."
                    )
                
        except Exception as e:
            QMessageBox.critical(self, "오류", f"저장 실패:\n{str(e)}")
    
    def rollback_to_version(self):
        """선택된 버전으로 롤백"""
        if not self.current_project:
            return
            
        selected_version = self.version_history.get_selected_version()
        if not selected_version:
            QMessageBox.information(self, "알림", "롤백할 버전을 선택해주세요.")
            return
            
        reply = QMessageBox.question(
            self, "확인", 
            f"v{selected_version.number} 버전으로 롤백하시겠습니까?\n\n"
            f"설명: {selected_version.description}\n"
            f"생성일: {selected_version.created_at_display}\n\n"
            "현재 작업 중인 파일들이 해당 버전의 내용으로 변경됩니다.\n"
            "버전 번호는 변경되지 않습니다.",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            try:
                # 롤백이 아닌 버전 전환으로 로직 변경
                success = self.current_project.rollback_to_version(selected_version.number)
                if success:
                    # UI 전체 새로고침 필요
                    self.refresh_all_ui()
                    QMessageBox.information(
                        self, "성공",
                        f"작업 버전을 v{selected_version.number}으로 전환했습니다." # 메시지 수정
                    )
                else:
                    QMessageBox.warning(self, "경고", "버전 전환에 실패했습니다.") # 메시지 수정
                    
            except Exception as e:
                QMessageBox.critical(self, "오류", f"버전 전환 실패:\n{str(e)}") # 메시지 수정
    
    def show_selected_file_diff(self):
        """선택된 파일의 diff 표시"""
        if not self.current_project:
            return
            
        selected_status = self.file_tree.get_selected_file_status()
        if not selected_status:
            QMessageBox.information(self, "알림", "비교할 파일을 선택해주세요.")
            return
            
        try:
            # 현재 버전과 working 파일 비교
            diff = self.current_project.compare_with_current(
                self.current_project.current_version, 
                selected_status.path
            )
            
            # diff 다이얼로그 표시
            dialog = DiffViewerDialog(diff, self)
            dialog.exec()
            
        except Exception as e:
            QMessageBox.critical(self, "오류", f"파일 비교 실패:\n{str(e)}")
    
    def show_version_compare_dialog(self):
        """버전 비교 다이얼로그 표시"""
        if not self.current_project:
            return
            
        if len(self.current_project.versions) < 2:
            QMessageBox.information(self, "알림", "비교할 버전이 부족합니다. (최소 2개 필요)")
            return
            
        self.compare_dialog = VersionCompareDialog(
            self.current_project.versions,
            self.current_project.current_version,
            self
        )
        
        # 비교 요청 시그널 연결
        self.compare_dialog.comparison_requested.connect(self.compare_versions)
        self.compare_dialog.exec()
    
    def compare_versions(self, old_version: int, new_version: int):
        """버전 비교 수행"""
        if not self.current_project:
            return
            
        try:
            if new_version == -1:  # working 버전
                changes = self.current_project.get_version_changes_with_working(old_version)
            else:
                changes = self.current_project.get_version_changes(old_version, new_version)
            
            if hasattr(self, 'compare_dialog') and self.compare_dialog:
                self.compare_dialog.show_comparison_results(changes)
            
        except Exception as e:
            QMessageBox.critical(self, "오류", f"버전 비교 실패:\n{str(e)}")
    
    def show_search_dialog(self):
        """검색 다이얼로그 표시"""
        if not self.current_project:
            QMessageBox.information(self, "알림", "먼저 프로젝트를 열어주세요.")
            return
            
        if not self.search_dialog:
            self.search_dialog = SearchDialog(self)
            self.search_dialog.search_requested.connect(self.perform_search)
            self.search_dialog.result_selected.connect(self.on_search_result_selected)
        
        self.search_dialog.show()
        self.search_dialog.raise_()
        
    def perform_search(self, query: str, file_extensions: List[str], case_sensitive: bool):
        """검색 수행"""
        if not self.current_project:
            return
            
        try:
            results = self.current_project.search_in_versions(
                query, file_extensions, case_sensitive
            )
            
            if self.search_dialog:
                self.search_dialog.show_search_results(results)
                
        except Exception as e:
            QMessageBox.critical(self, "오류", f"검색 실패:\n{str(e)}")
    
    def on_search_result_selected(self, result_data: dict):
        """검색 결과 선택 처리"""
        try:
            version = result_data["version"]
            file_path = result_data["file_path"]
            
            diff = self.current_project.compare_with_current(version.number, file_path)
            
            self.diff_viewer.show_diff(diff)
            
        except Exception as e:
            QMessageBox.critical(self, "오류", f"검색 결과 표시 실패:\n{str(e)}")
    
    def edit_project_settings(self):
        """프로젝트 설정 편집"""
        if not self.current_project:
            return
            
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
    
    def on_file_double_clicked(self, file_path: str):
        """파일 더블클릭 처리 - diff 표시"""
        if not self.current_project:
            return
            
        try:
            diff = self.current_project.compare_with_current(
                self.current_project.current_version, 
                file_path
            )
            self.diff_viewer.show_diff(diff)
            
        except Exception as e:
            QMessageBox.critical(self, "오류", f"파일 비교 실패:\n{str(e)}")
    
    def on_file_selection_changed(self):
        """파일 선택 변경 처리"""
        selected_status = self.file_tree.get_selected_file_status()
        if selected_status and self.current_project:
            try:
                diff = self.current_project.compare_with_current(
                    self.current_project.current_version, 
                    selected_status.path
                )
                self.diff_viewer.show_diff(diff)
            except:
                self.diff_viewer.clear_diff()
        else:
            self.diff_viewer.clear_diff()
    
    def on_version_double_clicked(self, version_number: int):
        """버전 더블클릭 처리 - 롤백 확인"""
        if not self.current_project:
            return
        
        if version_number != self.current_project.current_version:
            selected_version = self.current_project.data.get_version_by_number(version_number)
            
            if selected_version:
                reply = QMessageBox.question(
                    self, "롤백 확인", 
                    f"v{selected_version.number} 버전으로 롤백하시겠습니까?",
                    QMessageBox.Yes | QMessageBox.No
                )
                
                if reply == QMessageBox.Yes:
                    try:
                        success = self.current_project.rollback_to_version(version_number)
                        if success:
                            self.refresh_file_status()
                            QMessageBox.information(
                                self, "성공", 
                                f"v{version_number} 버전으로 롤백되었습니다."
                            )
                    except Exception as e:
                        QMessageBox.critical(self, "오류", f"롤백 실패:\n{str(e)}")
    
    def on_version_selection_changed(self):
        """버전 선택 변경 처리"""
        pass
    
    def on_focus_gained(self):
        """포커스 받을 때 처리"""
        if self.current_project:
            self.refresh_file_status()
    
    def show_about(self):
        """정보 다이얼로그 표시"""
        QMessageBox.about(
            self, "정보",
            "심플 파일 버전 관리 v1.0\n\n"
            "간단하고 직관적인 파일 버전 관리 도구입니다.\n"
            "복잡한 Git 없이도 파일 변경사항을 추적하고\n"
            "버전별로 관리할 수 있습니다."
        )
    
    def focusInEvent(self, event):
        """윈도우가 포커스를 받을 때"""
        super().focusInEvent(event)
        self.focus_timer.start(200)
    
    def closeEvent(self, event):
        """윈도우 닫기 이벤트"""
        if self.current_project:
            try:
                modified_files = self.current_project.get_modified_files()
                if modified_files:
                    reply = QMessageBox.question(
                        self, "확인",
                        f"저장되지 않은 변경사항이 {len(modified_files)}개 있습니다.\n"
                        "저장하지 않고 종료하시겠습니까?",
                        QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel
                    )
                    
                    if reply == QMessageBox.Cancel:
                        event.ignore()
                        return
                    elif reply == QMessageBox.No:
                        self.save_changes()
                        event.ignore()
                        return
            except:
                pass
        
        event.accept()


def main():
    """메인 함수"""
    app = QApplication(sys.argv)
    
    app.setApplicationName("심플 파일 버전 관리")
    app.setApplicationVersion("1.0.0")
    app.setOrganizationName("SimpleDev")
    
    app.setStyleSheet("""
        QMainWindow { background-color: #f5f5f5; }
        QGroupBox { font-weight: bold; border: 2px solid #cccccc; border-radius: 8px; margin-top: 1ex; padding-top: 10px; background-color: white; }
        QGroupBox::title { subcontrol-origin: margin; left: 15px; padding: 0 8px 0 8px; background-color: white; }
        QTreeWidget, QListWidget { border: 1px solid #dddddd; border-radius: 6px; background-color: white; alternate-background-color: #f9f9f9; }
        QListWidget::item { padding: 10px; border-bottom: 1px solid #eeeeee; min-height: 20px; }
        QListWidget::item:selected, QTreeWidget::item:selected { background-color: #e3f2fd; }
        QListWidget::item:hover, QTreeWidget::item:hover { background-color: #f0f8ff; }
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