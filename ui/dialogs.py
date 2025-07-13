# ui/dialogs.py
# 다이얼로그 클래스들 - core, ui/widgets에 의존

import os
from typing import List, Tuple, Optional, Dict
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QGridLayout,
    QLineEdit, QTextEdit, QPushButton, QLabel, QCheckBox,
    QFileDialog, QListWidget, QListWidgetItem, QMessageBox,
    QGroupBox, QScrollArea, QTabWidget, QComboBox, QSpinBox,
    QSplitter, QTreeWidget, QTreeWidgetItem, QProgressBar
)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QFont

from core.models import FileStatus, Version, ProjectSettings, FileDiff
from ui.widgets import DiffViewerWidget, SearchResultWidget


class ProjectSetupDialog(QDialog):
    """새 프로젝트 설정 다이얼로그"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("새 프로젝트 생성")
        self.setFixedSize(600, 500)
        self.setup_ui()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # 기본 정보
        basic_group = QGroupBox("기본 정보")
        basic_layout = QFormLayout(basic_group)
        
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("프로젝트 이름을 입력하세요")
        basic_layout.addRow("프로젝트 이름 *:", self.name_edit)
        
        self.description_edit = QTextEdit()
        self.description_edit.setPlaceholderText("프로젝트 설명을 입력하세요 (선택사항)")
        self.description_edit.setMaximumHeight(80)
        basic_layout.addRow("설명:", self.description_edit)
        
        self.author_edit = QLineEdit()
        self.author_edit.setPlaceholderText("작성자 이름 (선택사항)")
        basic_layout.addRow("작성자:", self.author_edit)
        
        layout.addWidget(basic_group)
        
        # 초기 파일 선택
        file_group = QGroupBox("관리할 파일 선택")
        file_layout = QVBoxLayout(file_group)
        
        file_buttons = QHBoxLayout()
        self.add_files_btn = QPushButton("📁 파일 추가")
        self.add_folder_btn = QPushButton("📂 폴더 추가")
        self.remove_files_btn = QPushButton("🗑️ 제거")
        self.clear_files_btn = QPushButton("🧹 모두 제거")
        
        file_buttons.addWidget(self.add_files_btn)
        file_buttons.addWidget(self.add_folder_btn)
        file_buttons.addWidget(self.remove_files_btn)
        file_buttons.addWidget(self.clear_files_btn)
        file_buttons.addStretch()
        file_layout.addLayout(file_buttons)
        
        self.files_list = QListWidget()
        file_layout.addWidget(self.files_list)
        
        layout.addWidget(file_group)
        
        # 버튼
        buttons = QHBoxLayout()
        self.ok_btn = QPushButton("프로젝트 생성")
        self.cancel_btn = QPushButton("취소")
        
        self.ok_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                font-weight: bold;
                padding: 10px 20px;
                border-radius: 5px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        
        buttons.addStretch()
        buttons.addWidget(self.cancel_btn)
        buttons.addWidget(self.ok_btn)
        layout.addLayout(buttons)
        
        # 시그널 연결
        self.add_files_btn.clicked.connect(self.add_files)
        self.add_folder_btn.clicked.connect(self.add_folder)
        self.remove_files_btn.clicked.connect(self.remove_files)
        self.clear_files_btn.clicked.connect(self.clear_files)
        self.ok_btn.clicked.connect(self.accept_dialog)
        self.cancel_btn.clicked.connect(self.reject)
    
    def add_files(self):
        """파일 추가"""
        files, _ = QFileDialog.getOpenFileNames(
            self, "관리할 파일 선택", "", "All Files (*)"
        )
        
        for file_path in files:
            if not self.is_file_already_added(file_path):
                item = QListWidgetItem(f"📄 {os.path.basename(file_path)}")
                item.setData(Qt.UserRole, file_path)
                item.setToolTip(file_path)
                self.files_list.addItem(item)
    
    def add_folder(self):
        """폴더 추가 (폴더 내 모든 파일)"""
        folder_path = QFileDialog.getExistingDirectory(
            self, "관리할 폴더 선택"
        )
        
        if folder_path:
            # 폴더 내 모든 파일 추가
            for root, dirs, files in os.walk(folder_path):
                for file in files:
                    file_path = os.path.join(root, file)
                    if not self.is_file_already_added(file_path):
                        rel_path = os.path.relpath(file_path, folder_path)
                        item = QListWidgetItem(f"📄 {rel_path}")
                        item.setData(Qt.UserRole, file_path)
                        item.setToolTip(file_path)
                        self.files_list.addItem(item)
    
    def is_file_already_added(self, file_path: str) -> bool:
        """파일이 이미 추가되었는지 확인"""
        for i in range(self.files_list.count()):
            if self.files_list.item(i).data(Qt.UserRole) == file_path:
                return True
        return False
    
    def remove_files(self):
        """선택된 파일 제거"""
        current_row = self.files_list.currentRow()
        if current_row >= 0:
            self.files_list.takeItem(current_row)
    
    def clear_files(self):
        """모든 파일 제거"""
        reply = QMessageBox.question(
            self, "확인", "모든 파일을 제거하시겠습니까?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.files_list.clear()
    
    def get_values(self) -> Tuple[str, List[str], ProjectSettings]:
        """입력값 반환"""
        name = self.name_edit.text().strip()
        description = self.description_edit.toPlainText().strip()
        author = self.author_edit.text().strip()
        
        files = []
        for i in range(self.files_list.count()):
            file_path = self.files_list.item(i).data(Qt.UserRole)
            files.append(file_path)
        
        settings = ProjectSettings(
            name=name,
            description=description,
            author=author
        )
        
        return name, files, settings
    
    def accept_dialog(self):
        """확인 버튼 처리"""
        name, files, settings = self.get_values()
        
        if not name:
            QMessageBox.warning(self, "입력 오류", "프로젝트 이름을 입력해주세요.")
            return
        
        # 파일이 없어도 프로젝트 생성 가능
        if not files:
            reply = QMessageBox.question(
                self, "확인", 
                "관리할 파일이 없습니다. 빈 프로젝트로 생성하시겠습니까?\n\n"
                "나중에 프로젝트 폴더에 파일을 추가한 후 '🔄 싱크' 버튼으로 동기화할 수 있습니다.",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply != QMessageBox.Yes:
                return
        
        super().accept()


class ProjectSettingsDialog(QDialog):
    """프로젝트 설정 편집 다이얼로그"""
    
    def __init__(self, current_settings: ProjectSettings, parent=None):
        super().__init__(parent)
        self.current_settings = current_settings
        self.setWindowTitle("프로젝트 설정")
        self.setFixedSize(500, 400)
        self.setup_ui()
        self.load_current_settings()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # 기본 정보
        basic_group = QGroupBox("기본 정보")
        basic_layout = QFormLayout(basic_group)
        
        self.name_edit = QLineEdit()
        basic_layout.addRow("프로젝트 이름:", self.name_edit)
        
        self.description_edit = QTextEdit()
        self.description_edit.setMaximumHeight(100)
        basic_layout.addRow("설명:", self.description_edit)
        
        self.author_edit = QLineEdit()
        basic_layout.addRow("작성자:", self.author_edit)
        
        layout.addWidget(basic_group)
        
        # 태그
        tags_group = QGroupBox("태그")
        tags_layout = QVBoxLayout(tags_group)
        
        tags_input_layout = QHBoxLayout()
        self.tag_input = QLineEdit()
        self.tag_input.setPlaceholderText("태그를 입력하고 Enter를 누르세요")
        self.add_tag_btn = QPushButton("추가")
        
        tags_input_layout.addWidget(self.tag_input)
        tags_input_layout.addWidget(self.add_tag_btn)
        tags_layout.addLayout(tags_input_layout)
        
        self.tags_list = QListWidget()
        self.tags_list.setMaximumHeight(100)
        tags_layout.addWidget(self.tags_list)
        
        remove_tag_layout = QHBoxLayout()
        self.remove_tag_btn = QPushButton("선택된 태그 제거")
        remove_tag_layout.addStretch()
        remove_tag_layout.addWidget(self.remove_tag_btn)
        tags_layout.addLayout(remove_tag_layout)
        
        layout.addWidget(tags_group)
        
        # 생성 정보 (읽기 전용)
        info_group = QGroupBox("생성 정보")
        info_layout = QFormLayout(info_group)
        
        self.created_label = QLabel()
        info_layout.addRow("생성일:", self.created_label)
        
        layout.addWidget(info_group)
        
        # 버튼
        buttons = QHBoxLayout()
        self.ok_btn = QPushButton("저장")
        self.cancel_btn = QPushButton("취소")
        
        self.ok_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                font-weight: bold;
                padding: 8px 16px;
                border-radius: 4px;
            }
        """)
        
        buttons.addStretch()
        buttons.addWidget(self.cancel_btn)
        buttons.addWidget(self.ok_btn)
        layout.addLayout(buttons)
        
        # 시그널 연결
        self.tag_input.returnPressed.connect(self.add_tag)
        self.add_tag_btn.clicked.connect(self.add_tag)
        self.remove_tag_btn.clicked.connect(self.remove_tag)
        self.ok_btn.clicked.connect(self.accept_dialog)
        self.cancel_btn.clicked.connect(self.reject)
    
    def load_current_settings(self):
        """현재 설정 로드"""
        self.name_edit.setText(self.current_settings.name)
        self.description_edit.setPlainText(self.current_settings.description)
        self.author_edit.setText(self.current_settings.author)
        self.created_label.setText(self.current_settings.created_at.strftime('%Y-%m-%d %H:%M:%S'))
        
        # 태그 로드
        for tag in self.current_settings.tags:
            self.tags_list.addItem(tag)
    
    def add_tag(self):
        """태그 추가"""
        tag = self.tag_input.text().strip()
        if tag and not self.is_tag_exists(tag):
            self.tags_list.addItem(tag)
            self.tag_input.clear()
    
    def is_tag_exists(self, tag: str) -> bool:
        """태그가 이미 존재하는지 확인"""
        for i in range(self.tags_list.count()):
            if self.tags_list.item(i).text() == tag:
                return True
        return False
    
    def remove_tag(self):
        """선택된 태그 제거"""
        current_row = self.tags_list.currentRow()
        if current_row >= 0:
            self.tags_list.takeItem(current_row)
    
    def get_settings(self) -> ProjectSettings:
        """수정된 설정 반환"""
        tags = []
        for i in range(self.tags_list.count()):
            tags.append(self.tags_list.item(i).text())
        
        return ProjectSettings(
            name=self.name_edit.text().strip(),
            description=self.description_edit.toPlainText().strip(),
            author=self.author_edit.text().strip(),
            created_at=self.current_settings.created_at,
            tags=tags
        )
    
    def accept_dialog(self):
        """확인 버튼 처리"""
        settings = self.get_settings()
        
        if not settings.name:
            QMessageBox.warning(self, "입력 오류", "프로젝트 이름을 입력해주세요.")
            return
        
        super().accept()


class SaveOptionsDialog(QDialog):
    """저장 옵션 선택 다이얼로그"""
    
    def __init__(self, modified_files: List[FileStatus], current_version: int, parent=None):
        super().__init__(parent)
        self.modified_files = modified_files
        self.current_version = current_version
        self.setWindowTitle("저장 옵션 선택")
        self.setFixedSize(650, 550)
        self.setup_ui()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # 변경된 파일 목록
        files_group = QGroupBox(f"변경된 파일 ({len(self.modified_files)}개)")
        files_layout = QVBoxLayout(files_group)
        
        files_list = QListWidget()
        files_list.setMaximumHeight(150)
        for file_status in self.modified_files:
            item = QListWidgetItem(file_status.display_name)
            item.setToolTip(f"경로: {file_status.path}\n크기: {file_status.size_display}")
            files_list.addItem(item)
        
        files_layout.addWidget(files_list)
        layout.addWidget(files_group)
        
        # 저장 옵션
        options_group = QGroupBox("저장 방법 선택")
        options_layout = QVBoxLayout(options_group)
        
        # 현재 버전에 저장
        current_option = QGroupBox()
        current_layout = QVBoxLayout(current_option)
        
        self.save_current_btn = QPushButton(f"📝 현재 버전(v{self.current_version})에 저장")
        self.save_current_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                font-weight: bold;
                padding: 15px;
                border-radius: 6px;
                text-align: left;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
        """)
        
        current_desc = QLabel("• 현재 버전을 덮어씁니다\n• 버전 번호는 변경되지 않습니다\n• 이전 상태는 복구할 수 없습니다")
        current_desc.setStyleSheet("color: #666; margin-left: 10px; font-size: 11px;")
        
        current_layout.addWidget(self.save_current_btn)
        current_layout.addWidget(current_desc)
        options_layout.addWidget(current_option)
        
        # 구분선
        separator = QLabel()
        separator.setFixedHeight(10)
        options_layout.addWidget(separator)
        
        # 새 버전 생성
        new_option = QGroupBox()
        new_layout = QVBoxLayout(new_option)
        
        self.new_version_btn = QPushButton(f"🆕 새 버전(v{self.current_version + 1}) 생성")
        self.new_version_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                font-weight: bold;
                padding: 15px;
                border-radius: 6px;
                text-align: left;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        
        new_desc = QLabel("• 새로운 버전을 생성합니다\n• 이전 버전은 그대로 보존됩니다\n• 언제든 이전 버전으로 롤백 가능합니다")
        new_desc.setStyleSheet("color: #666; margin-left: 10px; font-size: 11px;")
        
        new_layout.addWidget(self.new_version_btn)
        new_layout.addWidget(new_desc)
        
        # 설명 입력
        desc_layout = QFormLayout()
        self.description_edit = QTextEdit()
        self.description_edit.setPlaceholderText("새 버전에 대한 설명을 입력하세요")
        self.description_edit.setMaximumHeight(80)
        desc_layout.addRow("변경사항 설명:", self.description_edit)
        
        new_layout.addLayout(desc_layout)
        options_layout.addWidget(new_option)
        
        layout.addWidget(options_group)
        
        # 취소 버튼
        cancel_layout = QHBoxLayout()
        self.cancel_btn = QPushButton("취소")
        self.cancel_btn.setStyleSheet("padding: 8px 16px;")
        cancel_layout.addStretch()
        cancel_layout.addWidget(self.cancel_btn)
        layout.addLayout(cancel_layout)
        
        # 시그널 연결
        self.save_current_btn.clicked.connect(self.save_to_current)
        self.new_version_btn.clicked.connect(self.create_new_version)
        self.cancel_btn.clicked.connect(self.reject)
    
    def save_to_current(self):
        """현재 버전에 저장"""
        reply = QMessageBox.question(
            self, "확인",
            f"현재 버전(v{self.current_version})을 덮어쓰시겠습니까?\n\n"
            "이 작업은 되돌릴 수 없습니다.",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.result_type = "current"
            self.accept()
    
    def create_new_version(self):
        """새 버전 생성"""
        description = self.description_edit.toPlainText().strip()
        if not description:
            QMessageBox.warning(self, "입력 오류", "새 버전에 대한 설명을 입력해주세요.")
            return
        
        self.result_type = "new"
        self.description = description
        self.accept()
    
    def get_result(self) -> Tuple[str, str]:
        """결과 반환 (타입, 설명)"""
        if hasattr(self, 'result_type'):
            description = getattr(self, 'description', '')
            return self.result_type, description
        return "", ""


class DiffViewerDialog(QDialog):
    """Diff 뷰어 다이얼로그"""
    
    def __init__(self, diff: FileDiff, parent=None):
        super().__init__(parent)
        self.diff = diff
        self.setWindowTitle(f"변경사항 비교 - {diff.file_path}")
        self.setGeometry(100, 100, 800, 600)
        self.setup_ui()
        self.show_diff()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Diff 뷰어
        self.diff_viewer = DiffViewerWidget()
        layout.addWidget(self.diff_viewer)
        
        # 버튼
        buttons = QHBoxLayout()
        self.close_btn = QPushButton("닫기")
        self.close_btn.setDefault(True)
        
        buttons.addStretch()
        buttons.addWidget(self.close_btn)
        layout.addLayout(buttons)
        
        # 시그널 연결
        self.close_btn.clicked.connect(self.accept)
    
    def show_diff(self):
        """diff 표시"""
        self.diff_viewer.show_diff(self.diff)


class SearchDialog(QDialog):
    """검색 다이얼로그"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("파일 내용 검색")
        self.setGeometry(100, 100, 700, 500)
        self.search_results = []
        self.setup_ui()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # 검색 설정
        search_group = QGroupBox("검색 설정")
        search_layout = QFormLayout(search_group)
        
        self.query_edit = QLineEdit()
        self.query_edit.setPlaceholderText("검색할 텍스트를 입력하세요")
        search_layout.addRow("검색어:", self.query_edit)
        
        options_layout = QHBoxLayout()
        self.case_sensitive_cb = QCheckBox("대소문자 구분")
        self.file_extensions_edit = QLineEdit()
        self.file_extensions_edit.setPlaceholderText("예: .py,.js,.txt (비워두면 모든 텍스트 파일)")
        
        options_layout.addWidget(self.case_sensitive_cb)
        options_layout.addWidget(QLabel("파일 확장자:"))
        options_layout.addWidget(self.file_extensions_edit)
        search_layout.addRow("옵션:", options_layout)
        
        search_buttons = QHBoxLayout()
        self.search_btn = QPushButton("🔍 검색")
        self.clear_btn = QPushButton("🧹 지우기")
        search_buttons.addWidget(self.search_btn)
        search_buttons.addWidget(self.clear_btn)
        search_buttons.addStretch()
        search_layout.addRow("", search_buttons)
        
        layout.addWidget(search_group)
        
        # 검색 결과
        results_group = QGroupBox("검색 결과")
        results_layout = QVBoxLayout(results_group)
        
        self.results_widget = SearchResultWidget()
        results_layout.addWidget(self.results_widget)
        
        layout.addWidget(results_group)
        
        # 버튼
        buttons = QHBoxLayout()
        self.close_btn = QPushButton("닫기")
        
        buttons.addStretch()
        buttons.addWidget(self.close_btn)
        layout.addLayout(buttons)
        
        # 시그널 연결
        self.query_edit.returnPressed.connect(self.perform_search)
        self.search_btn.clicked.connect(self.perform_search)
        self.clear_btn.clicked.connect(self.clear_results)
        self.close_btn.clicked.connect(self.accept)
        self.results_widget.result_double_clicked.connect(self.on_result_selected)
    
    def perform_search(self):
        """검색 수행 (외부에서 구현)"""
        query = self.query_edit.text().strip()
        if not query:
            QMessageBox.warning(self, "입력 오류", "검색어를 입력해주세요.")
            return
        
        # 외부에서 이 시그널을 연결하여 검색 로직 구현
        self.search_requested.emit(
            query,
            self.get_file_extensions(),
            self.case_sensitive_cb.isChecked()
        )
    
    def get_file_extensions(self) -> List[str]:
        """파일 확장자 목록 반환"""
        ext_text = self.file_extensions_edit.text().strip()
        if not ext_text:
            return []
        
        extensions = [ext.strip() for ext in ext_text.split(',')]
        return [ext if ext.startswith('.') else f'.{ext}' for ext in extensions if ext]
    
    def show_search_results(self, results: List[dict]):
        """검색 결과 표시"""
        self.search_results = results
        query = self.query_edit.text().strip()
        self.results_widget.show_search_results(results, query)
    
    def clear_results(self):
        """검색 결과 지우기"""
        self.results_widget.clear()
        self.search_results = []
    
    def on_result_selected(self, result_data: dict):
        """검색 결과 선택 처리"""
        # 외부에서 이 시그널을 연결하여 처리
        self.result_selected.emit(result_data)
    
    # 시그널 정의
    search_requested = Signal(str, list, bool)  # query, extensions, case_sensitive
    result_selected = Signal(dict)  # result_data


class VersionCompareDialog(QDialog):
    """버전 비교 다이얼로그"""
    
    def __init__(self, versions: List[Version], current_version: int, parent=None):
        super().__init__(parent)
        self.versions = versions
        self.current_version = current_version
        self.setWindowTitle("버전 비교")
        self.setGeometry(100, 100, 900, 700)
        self.setup_ui()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # 버전 선택
        selection_group = QGroupBox("비교할 버전 선택")
        selection_layout = QFormLayout(selection_group)
        
        self.old_version_combo = QComboBox()
        self.new_version_combo = QComboBox()
        
        # 버전 목록 채우기
        for version in self.versions:
            version_text = f"v{version.number} - {version.description_short}"
            self.old_version_combo.addItem(version_text, version.number)
            self.new_version_combo.addItem(version_text, version.number)
        
        # working 버전 추가
        self.new_version_combo.addItem("current (현재 작업)", -1)
        
        selection_layout.addRow("이전 버전:", self.old_version_combo)
        selection_layout.addRow("새 버전:", self.new_version_combo)
        
        compare_btn = QPushButton("비교하기")
        compare_btn.clicked.connect(self.compare_versions)
        selection_layout.addRow("", compare_btn)
        
        layout.addWidget(selection_group)
        
        # 비교 결과
        self.results_widget = QTabWidget()
        layout.addWidget(self.results_widget)
        
        # 버튼
        buttons = QHBoxLayout()
        self.close_btn = QPushButton("닫기")
        buttons.addStretch()
        buttons.addWidget(self.close_btn)
        layout.addLayout(buttons)
        
        # 시그널 연결
        self.close_btn.clicked.connect(self.accept)
    
    def compare_versions(self):
        """버전 비교 수행"""
        old_version = self.old_version_combo.currentData()
        new_version = self.new_version_combo.currentData()
        
        if old_version is None or new_version is None:
            return
        
        # 외부에서 이 시그널을 연결하여 비교 로직 구현
        self.comparison_requested.emit(old_version, new_version)
    
    def show_comparison_results(self, changes: Dict[str, FileDiff]):
        """비교 결과 표시"""
        self.results_widget.clear()
        
        if not changes:
            no_changes_widget = QLabel("변경사항이 없습니다.")
            no_changes_widget.setAlignment(Qt.AlignCenter)
            self.results_widget.addTab(no_changes_widget, "결과")
            return
        
        for file_path, diff in changes.items():
            diff_viewer = DiffViewerWidget()
            diff_viewer.show_diff(diff)
            
            tab_name = os.path.basename(file_path)
            self.results_widget.addTab(diff_viewer, tab_name)
    
    # 시그널 정의
    comparison_requested = Signal(int, int)  # old_version, new_version


class ProgressDialog(QDialog):
    """진행률 표시 다이얼로그"""
    
    def __init__(self, title: str = "작업 중...", parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setFixedSize(400, 120)
        self.setModal(True)
        self.setup_ui()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        self.message_label = QLabel("작업을 수행 중입니다...")
        layout.addWidget(self.message_label)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)  # 무한 진행률
        layout.addWidget(self.progress_bar)
        
        self.cancel_btn = QPushButton("취소")
        self.cancel_btn.clicked.connect(self.reject)
        
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(self.cancel_btn)
        layout.addLayout(button_layout)
    
    def update_message(self, message: str):
        """메시지 업데이트"""
        self.message_label.setText(message)
    
    def set_progress(self, value: int, maximum: int = 100):
        """진행률 설정"""
        self.progress_bar.setRange(0, maximum)
        self.progress_bar.setValue(value)
    
    def set_indeterminate(self):
        """무한 진행률 설정"""
        self.progress_bar.setRange(0, 0)