# ui/widgets.py
# 커스텀 위젯 클래스들 - models에만 의존

from typing import List, Optional, Dict
from PySide6.QtWidgets import (
    QListWidget, QListWidgetItem, QTextEdit, QWidget, QVBoxLayout,
    QHBoxLayout, QLabel, QPushButton, QSplitter, QScrollArea,
    QFrame, QGroupBox, QTreeWidget, QTreeWidgetItem
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QTextCharFormat, QTextCursor, QColor

from core.models import FileStatus, Version, FileDiff, FileChangeType


class FileTreeWidget(QTreeWidget):
    """파일 트리 위젯 (폴더 구조 표시)"""
    
    file_double_clicked = Signal(str)  # 파일 경로
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setHeaderLabels(["파일/폴더", "상태"])
        self.setMinimumWidth(350)
        self.itemDoubleClicked.connect(self._on_item_double_clicked)
        
        # 컬럼 너비 설정
        self.setColumnWidth(0, 250)
        self.setColumnWidth(1, 80)
        
    def update_files(self, file_statuses: List[FileStatus]):
        """파일 상태 목록을 트리 구조로 업데이트"""
        self.clear()
        
        if not file_statuses:
            return
        
        # 폴더별로 그룹화
        folder_items = {}  # folder_path -> QTreeWidgetItem
        root_files = []    # 루트 레벨 파일들
        
        for status in file_statuses:
            path_parts = status.path.split('/')
            
            if len(path_parts) == 1:
                # 루트 레벨 파일
                root_files.append(status)
            else:
                # 폴더 안의 파일
                folder_path = '/'.join(path_parts[:-1])
                
                # 폴더 아이템 생성 (없으면)
                if folder_path not in folder_items:
                    folder_item = QTreeWidgetItem([f"📁 {folder_path}", ""])
                    folder_item.setExpanded(True)  # 기본으로 펼쳐진 상태
                    folder_items[folder_path] = folder_item
                    self.addTopLevelItem(folder_item)
                
                # 파일 아이템을 폴더에 추가
                file_item = self._create_file_item(status)
                folder_items[folder_path].addChild(file_item)
        
        # 루트 레벨 파일들 추가
        for status in root_files:
            file_item = self._create_file_item(status)
            self.addTopLevelItem(file_item)
        
        # 폴더 상태 업데이트
        self._update_folder_status(folder_items)
    
    def _create_file_item(self, status: FileStatus) -> QTreeWidgetItem:
        """파일 아이템 생성"""
        file_name = status.name
        status_text = self._get_status_text(status.change_type)
        
        item = QTreeWidgetItem([status.display_name, status_text])
        item.setData(0, Qt.UserRole, status)
        
        # 상태에 따른 색상 설정
        if status.change_type == FileChangeType.DELETED:
            item.setBackground(0, QColor(255, 230, 230))  # 연한 빨강
        elif status.change_type == FileChangeType.ADDED:
            item.setBackground(0, QColor(230, 255, 230))  # 연한 초록
        elif status.change_type == FileChangeType.MODIFIED:
            item.setBackground(0, QColor(255, 250, 230))  # 연한 노랑
        
        # 툴팁 설정
        tooltip_lines = [
            f"경로: {status.path}",
            f"크기: {status.size_display}",
            f"수정시간: {status.last_modified.strftime('%Y-%m-%d %H:%M:%S')}"
        ]
        item.setToolTip(0, "\n".join(tooltip_lines))
        
        return item
    
    def _get_status_text(self, change_type: FileChangeType) -> str:
        """상태 텍스트 반환"""
        status_map = {
            FileChangeType.UNCHANGED: "정상",
            FileChangeType.MODIFIED: "변경됨",
            FileChangeType.ADDED: "새로 생김",
            FileChangeType.DELETED: "삭제됨"
        }
        return status_map.get(change_type, "")
    
    def _update_folder_status(self, folder_items: Dict[str, QTreeWidgetItem]):
        """폴더 상태 업데이트 (포함된 파일 상태 요약)"""
        for folder_path, folder_item in folder_items.items():
            child_count = folder_item.childCount()
            changed_count = 0
            
            for i in range(child_count):
                child_item = folder_item.child(i)
                child_status = child_item.data(0, Qt.UserRole)
                
                if child_status and child_status.change_type != FileChangeType.UNCHANGED:
                    changed_count += 1
            
            # 폴더 상태 텍스트 업데이트
            if changed_count > 0:
                status_text = f"{changed_count}개 변경"
                folder_item.setText(1, status_text)
                folder_item.setBackground(0, QColor(255, 250, 230))  # 연한 노랑
            else:
                folder_item.setText(1, f"{child_count}개 파일")
    
    def _on_item_double_clicked(self, item: QTreeWidgetItem, column: int):
        """아이템 더블클릭 처리"""
        status = item.data(0, Qt.UserRole)
        if status:  # 파일인 경우만 (폴더는 status가 없음)
            self.file_double_clicked.emit(status.path)
    
    def get_selected_file_status(self) -> Optional[FileStatus]:
        """선택된 파일 상태 반환"""
        current_item = self.currentItem()
        if current_item:
            return current_item.data(0, Qt.UserRole)
        return None


class VersionHistoryWidget(QListWidget):
    """버전 히스토리 위젯 (오른쪽 패널)"""
    
    version_double_clicked = Signal(int)  # 버전 번호
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(350)
        self.itemDoubleClicked.connect(self._on_item_double_clicked)
        
    def update_versions(self, versions: List[Version], current_version: int):
        """버전 목록 업데이트"""
        self.clear()
        
        for version in reversed(versions):  # 최신순 정렬
            item = QListWidgetItem()
            
            # 현재 버전 표시
            current_indicator = "📍 " if version.number == current_version else ""
            text = f"{current_indicator}v{version.number} - {version.description_short}\n"
            text += f"📅 {version.created_at_display}\n"
            text += f"📄 파일 {len(version.files)}개"
            
            item.setText(text)
            item.setData(Qt.UserRole, version)
            
            # 현재 버전 강조
            if version.number == current_version:
                item.setBackground(QColor(230, 240, 255))  # 연한 파랑
                font = item.font()
                font.setBold(True)
                item.setFont(font)
            
            # 툴팁 설정
            tooltip_lines = [
                f"버전: v{version.number}",
                f"설명: {version.description}",
                f"생성일: {version.created_at_display}",
                f"포함된 파일: {len(version.files)}개"
            ]
            item.setToolTip("\n".join(tooltip_lines))
            
            self.addItem(item)
    
    def _on_item_double_clicked(self, item: QListWidgetItem):
        """아이템 더블클릭 처리"""
        version = item.data(Qt.UserRole)
        if version:
            self.version_double_clicked.emit(version.number)
    
    def get_selected_version(self) -> Optional[Version]:
        """선택된 버전 반환"""
        current_item = self.currentItem()
        if current_item:
            return current_item.data(Qt.UserRole)
        return None


class DiffViewerWidget(QWidget):
    """Diff 뷰어 위젯"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # 헤더
        self.header_label = QLabel()
        self.header_label.setStyleSheet("""
            QLabel {
                font-weight: bold;
                padding: 8px;
                background-color: #f0f0f0;
                border: 1px solid #ccc;
                border-radius: 3px;
            }
        """)
        layout.addWidget(self.header_label)
        
        # diff 내용
        self.diff_text = QTextEdit()
        self.diff_text.setReadOnly(True)
        self.diff_text.setFont(QFont("Consolas", 9))  # 고정폭 폰트
        layout.addWidget(self.diff_text)
        
        # 통계 정보
        self.stats_label = QLabel()
        self.stats_label.setStyleSheet("""
            QLabel {
                padding: 4px;
                background-color: #f8f8f8;
                border: 1px solid #ddd;
                font-size: 11px;
            }
        """)
        layout.addWidget(self.stats_label)
    
    def show_diff(self, diff: FileDiff):
        """diff 표시"""
        if not diff.is_text_file:
            self.show_binary_file_diff(diff)
            return
        
        # 헤더 설정
        if diff.new_version == -1:
            header = f"v{diff.old_version} ↔ current: {diff.file_path}"
        else:
            header = f"v{diff.old_version} ↔ v{diff.new_version}: {diff.file_path}"
        
        self.header_label.setText(header)
        
        # diff 내용 표시
        if not diff.has_changes:
            self.diff_text.setPlainText("변경사항 없음")
            self.stats_label.setText("")
            return
        
        self.diff_text.clear()
        cursor = self.diff_text.textCursor()
        
        # 색상 포맷 설정
        added_format = QTextCharFormat()
        added_format.setBackground(QColor(230, 255, 230))  # 연한 초록
        
        removed_format = QTextCharFormat()
        removed_format.setBackground(QColor(255, 230, 230))  # 연한 빨강
        
        context_format = QTextCharFormat()
        context_format.setForeground(QColor(128, 128, 128))  # 회색
        
        normal_format = QTextCharFormat()
        
        # diff 라인별 표시
        for change_type, content in diff.diff_lines:
            if change_type == "added":
                cursor.setCharFormat(added_format)
                cursor.insertText(f"+ {content}\n")
            elif change_type == "removed":
                cursor.setCharFormat(removed_format)
                cursor.insertText(f"- {content}\n")
            elif change_type == "context":
                cursor.setCharFormat(context_format)
                cursor.insertText(f"{content}\n")
            else:
                cursor.setCharFormat(normal_format)
                cursor.insertText(f"  {content}\n")
        
        # 통계 정보 표시
        self.show_diff_stats(diff)
    
    def show_binary_file_diff(self, diff: FileDiff):
        """바이너리 파일 diff 표시"""
        self.header_label.setText(f"{diff.file_path} (바이너리 파일)")
        self.diff_text.setPlainText(f"바이너리 파일: {diff.change_summary}")
        self.stats_label.setText("")
    
    def show_diff_stats(self, diff: FileDiff):
        """diff 통계 정보 표시"""
        added_lines = sum(1 for change_type, _ in diff.diff_lines if change_type == "added")
        removed_lines = sum(1 for change_type, _ in diff.diff_lines if change_type == "removed")
        
        stats_text = f"추가: +{added_lines}줄, 제거: -{removed_lines}줄"
        self.stats_label.setText(stats_text)
    
    def clear_diff(self):
        """diff 내용 지우기"""
        self.header_label.setText("파일을 선택하여 변경사항을 확인하세요")
        self.diff_text.clear()
        self.stats_label.setText("")


class SearchResultWidget(QTreeWidget):
    """검색 결과 위젯"""
    
    result_double_clicked = Signal(dict)  # 검색 결과 딕셔너리
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
    
    def setup_ui(self):
        self.setHeaderLabels(["검색 결과", "버전", "파일", "라인"])
        self.setRootIsDecorated(True)
        self.itemDoubleClicked.connect(self._on_item_double_clicked)
        
        # 컬럼 너비 설정
        self.setColumnWidth(0, 300)
        self.setColumnWidth(1, 60)
        self.setColumnWidth(2, 150)
        self.setColumnWidth(3, 60)
    
    def show_search_results(self, results: List[dict], query: str):
        """검색 결과 표시"""
        self.clear()
        
        if not results:
            no_result_item = QTreeWidgetItem(["검색 결과 없음", "", "", ""])
            self.addTopLevelItem(no_result_item)
            return
        
        # 파일별로 그룹화
        file_groups = {}
        for result in results:
            file_path = result["file_path"]
            if file_path not in file_groups:
                file_groups[file_path] = []
            file_groups[file_path].append(result)
        
        # 파일별 트리 아이템 생성
        for file_path, file_results in file_groups.items():
            file_item = QTreeWidgetItem([f"📄 {file_path}", "", "", f"({len(file_results)}개)"])
            file_item.setExpanded(True)
            
            for result in file_results:
                version = result["version"]
                line_content = result["line_content"].strip()
                
                # 검색어 하이라이트
                highlighted_content = line_content.replace(
                    query, f"**{query}**"
                )
                
                result_item = QTreeWidgetItem([
                    highlighted_content,
                    f"v{version.number}",
                    "",
                    str(result["line_number"])
                ])
                result_item.setData(0, Qt.UserRole, result)
                
                file_item.addChild(result_item)
            
            self.addTopLevelItem(file_item)
    
    def _on_item_double_clicked(self, item: QTreeWidgetItem, column: int):
        """아이템 더블클릭 처리"""
        result_data = item.data(0, Qt.UserRole)
        if result_data:
            self.result_double_clicked.emit(result_data)


class ProjectInfoWidget(QWidget):
    """프로젝트 정보 표시 위젯"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # 프로젝트 기본 정보
        info_group = QGroupBox("프로젝트 정보")
        info_layout = QVBoxLayout(info_group)
        
        self.name_label = QLabel()
        self.description_label = QLabel()
        self.created_label = QLabel()
        self.version_label = QLabel()
        self.files_label = QLabel()
        
        info_layout.addWidget(self.name_label)
        info_layout.addWidget(self.description_label)
        info_layout.addWidget(self.created_label)
        info_layout.addWidget(self.version_label)
        info_layout.addWidget(self.files_label)
        
        layout.addWidget(info_group)
        
        # 최근 버전들
        recent_group = QGroupBox("최근 버전")
        recent_layout = QVBoxLayout(recent_group)
        
        self.recent_versions_list = QListWidget()
        self.recent_versions_list.setMaximumHeight(150)
        recent_layout.addWidget(self.recent_versions_list)
        
        layout.addWidget(recent_group)
        layout.addStretch()
    
    def update_project_info(self, project_data: Dict):
        """프로젝트 정보 업데이트"""
        settings = project_data.get("settings", {})
        
        self.name_label.setText(f"📁 이름: {settings.get('name', 'Unknown')}")
        self.description_label.setText(f"📝 설명: {settings.get('description', '설명 없음')}")
        self.created_label.setText(f"📅 생성일: {settings.get('created_at', 'Unknown')}")
        self.version_label.setText(f"📋 현재 버전: v{project_data.get('current_version', 0)}")
        self.files_label.setText(f"📄 추적 파일: {project_data.get('tracked_files_count', 0)}개")
        
        # 최근 버전들 표시
        self.recent_versions_list.clear()
        versions = project_data.get("versions", [])
        recent_versions = sorted(versions, key=lambda v: v["number"], reverse=True)[:5]
        
        for version_data in recent_versions:
            item_text = f"v{version_data['number']} - {version_data['description'][:30]}"
            if len(version_data['description']) > 30:
                item_text += "..."
            
            item = QListWidgetItem(item_text)
            item.setToolTip(version_data['description'])
            self.recent_versions_list.addItem(item)


class StatusBarWidget(QWidget):
    """상태바 위젯"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
    
    def setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        
        self.status_label = QLabel("준비")
        self.changed_files_label = QLabel("")
        self.version_label = QLabel("")
        
        layout.addWidget(self.status_label)
        layout.addStretch()
        layout.addWidget(self.changed_files_label)
        layout.addWidget(QLabel("|"))
        layout.addWidget(self.version_label)
    
    def update_status(self, status_text: str):
        """상태 텍스트 업데이트"""
        self.status_label.setText(status_text)
    
    def update_changed_files(self, count: int):
        """변경된 파일 수 업데이트"""
        if count > 0:
            self.changed_files_label.setText(f"⚠️ 변경된 파일: {count}개")
            self.changed_files_label.setStyleSheet("color: orange; font-weight: bold;")
        else:
            self.changed_files_label.setText("✅ 모든 파일 최신 상태")
            self.changed_files_label.setStyleSheet("color: green;")
    
    def update_version(self, current_version: int, total_versions: int):
        """버전 정보 업데이트"""
        self.version_label.setText(f"v{current_version} (총 {total_versions}개)")