# ui/widgets.py
# 커스텀 위젯 클래스들 - models에만 의존

from typing import List, Optional, Dict
from PySide6.QtWidgets import (
    QListWidget, QListWidgetItem, QTextEdit, QWidget, QVBoxLayout,
    QHBoxLayout, QLabel, QPushButton, QSplitter, QScrollArea,
    QFrame, QGroupBox, QTreeWidget, QTreeWidgetItem,
    QTreeWidgetItemIterator  # BUG FIX: 누락된 클래스 import
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QTextCharFormat, QTextCursor, QColor
import os
from datetime import datetime

from core.models import FileStatus, Version, FileDiff, FileChangeType


class FileTreeWidget(QTreeWidget):
    """파일 트리 위젯 (폴더 구조 표시)"""
    
    file_double_clicked = Signal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setHeaderLabels(["파일/폴더", "상태"])
        self.setMinimumWidth(350)
        self.itemDoubleClicked.connect(self._on_item_double_clicked)
        self.setColumnWidth(0, 220)
        self.setColumnWidth(1, 100)
        
    def update_files(self, file_statuses: List[FileStatus]):
        self.clear()
        if not file_statuses:
            return
        
        folder_items: Dict[str, QTreeWidgetItem] = {}
        for status in sorted(file_statuses, key=lambda s: s.path):
            path_parts = os.path.normpath(status.path).split(os.sep)
            current_parent = self.invisibleRootItem()
            current_path = ""

            for i, part in enumerate(path_parts[:-1]):
                current_path = os.path.join(current_path, part)
                if current_path not in folder_items:
                    folder_item = QTreeWidgetItem(current_parent, [f"📁 {part}", ""])
                    folder_items[current_path] = folder_item
                current_parent = folder_items[current_path]
            
            file_item = self._create_file_item(status)
            current_parent.addChild(file_item)

        self._update_folder_status()
    
    def _create_file_item(self, status: FileStatus) -> QTreeWidgetItem:
        file_name = os.path.basename(status.path)
        icon = self._get_status_icon(status.change_type)
        status_text = self._get_status_text(status.change_type)
        
        item = QTreeWidgetItem([f"{icon} {file_name}", status_text])
        item.setData(0, Qt.UserRole, status)
        
        if status.change_type == FileChangeType.DELETED:
            item.setForeground(0, QColor(200, 0, 0))
            item.setForeground(1, QColor(200, 0, 0))
        elif status.change_type == FileChangeType.ADDED:
            item.setForeground(0, QColor(0, 150, 0))
            item.setForeground(1, QColor(0, 150, 0))
        elif status.change_type == FileChangeType.MODIFIED:
            item.setForeground(0, QColor(200, 120, 0))
            item.setForeground(1, QColor(200, 120, 0))
        
        tooltip_lines = [
            f"경로: {status.path}",
            f"크기: {status.size_display}",
            f"수정시간: {status.last_modified.strftime('%Y-%m-%d %H:%M:%S') if status.last_modified != datetime.min else '알 수 없음'}"
        ]
        item.setToolTip(0, "\n".join(tooltip_lines))
        
        return item
        
    def _get_status_icon(self, change_type: FileChangeType) -> str:
        return {
            FileChangeType.UNCHANGED: "📄",
            FileChangeType.MODIFIED: "📝",
            FileChangeType.ADDED: "✨",
            FileChangeType.DELETED: "❌"
        }.get(change_type, "❓")
    
    def _get_status_text(self, change_type: FileChangeType) -> str:
        return {
            FileChangeType.UNCHANGED: "정상",
            FileChangeType.MODIFIED: "수정됨",
            FileChangeType.ADDED: "추가됨",
            FileChangeType.DELETED: "삭제됨"
        }.get(change_type, "")
    
    def _update_folder_status(self):
        iterator = QTreeWidgetItemIterator(self)
        while iterator.value():
            item = iterator.value()
            if item.childCount() > 0:
                changed_count = 0
                for i in range(item.childCount()):
                    child = item.child(i)
                    if child.data(0, Qt.UserRole):
                        status = child.data(0, Qt.UserRole)
                        if status.change_type != FileChangeType.UNCHANGED:
                            changed_count += 1
                if changed_count > 0:
                    item.setText(1, f"{changed_count}개 변경")
                    item.setExpanded(True)
            iterator += 1

    def _on_item_double_clicked(self, item: QTreeWidgetItem, column: int):
        status = item.data(0, Qt.UserRole)
        if status:
            self.file_double_clicked.emit(status.path)
    
    def get_selected_file_status(self) -> Optional[FileStatus]:
        current_item = self.currentItem()
        if current_item and current_item.data(0, Qt.UserRole):
            return current_item.data(0, Qt.UserRole)
        return None

# ... 이하 코드 동일 ...
class VersionHistoryWidget(QListWidget):
    """버전 히스토리 위젯 (오른쪽 패널)"""
    
    version_double_clicked = Signal(int)
    version_selection_changed = Signal(Version) # Version 객체를 전달하는 새 시그널

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(350)
        self.itemDoubleClicked.connect(self._on_item_double_clicked)
        self.currentItemChanged.connect(self._on_current_item_changed) # 선택 변경 시그널
        
    def update_versions(self, versions: List[Version], current_version: int):
        self.blockSignals(True) # 업데이트 중 신호 발생 방지
        self.clear()
        
        selected_item = None
        for version in reversed(versions):
            item = QListWidgetItem()
            current_indicator = "📍 " if version.number == current_version else ""
            
            # --- NEW: 자동 로그 요약 정보 표시 ---
            log_summary = version.auto_log_summary
            
            text = f"{current_indicator}v{version.number} - {version.description_short} {log_summary}\n"
            text += f"📅 {version.created_at_display}\n"
            text += f"📄 파일 {len(version.files)}개"
            
            item.setText(text)
            item.setData(Qt.UserRole, version)
            
            if version.number == current_version:
                item.setBackground(QColor(230, 240, 255))
                font = item.font()
                font.setBold(True)
                item.setFont(font)
                selected_item = item
            
            tooltip_lines = [f"버전: v{version.number}", f"설명: {version.description}", f"생성일: {version.created_at_display}", f"포함된 파일: {len(version.files)}개"]
            item.setToolTip("\n".join(tooltip_lines))
            self.addItem(item)
            
        if selected_item:
            self.setCurrentItem(selected_item)
            
        self.blockSignals(False) # 신호 발생 재개
        # 수동으로 첫 선택 아이템에 대한 신호 발생
        if self.currentItem():
            self._on_current_item_changed(self.currentItem(), None)
    
    def _on_current_item_changed(self, current: QListWidgetItem, previous: QListWidgetItem):
        """선택된 아이템이 변경될 때 신호를 보냅니다."""
        if current:
            version = current.data(Qt.UserRole)
            if version:
                self.version_selection_changed.emit(version)
                
    def _on_item_double_clicked(self, item: QListWidgetItem):
        version = item.data(Qt.UserRole)
        if version:
            self.version_double_clicked.emit(version.number)
    
    def get_selected_version(self) -> Optional[Version]:
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
        self.header_label = QLabel()
        self.header_label.setStyleSheet("QLabel { font-weight: bold; padding: 8px; background-color: #f0f0f0; border: 1px solid #ccc; border-radius: 3px; }")
        layout.addWidget(self.header_label)
        self.diff_text = QTextEdit()
        self.diff_text.setReadOnly(True)
        self.diff_text.setFont(QFont("Consolas", 9))
        layout.addWidget(self.diff_text)
        self.stats_label = QLabel()
        self.stats_label.setStyleSheet("QLabel { padding: 4px; background-color: #f8f8f8; border: 1px solid #ddd; font-size: 11px; }")
        layout.addWidget(self.stats_label)
    
    def show_diff(self, diff: FileDiff):
        if not diff.is_text_file:
            self.show_binary_file_diff(diff)
            return
        
        if diff.new_version == -1:
            header = f"v{diff.old_version} ↔ current: {diff.file_path}"
        else:
            header = f"v{diff.old_version} ↔ v{diff.new_version}: {diff.file_path}"
        self.header_label.setText(header)
        
        if not diff.has_changes:
            self.diff_text.setPlainText("변경사항 없음")
            self.stats_label.setText("")
            return
        
        self.diff_text.clear()
        cursor = self.diff_text.textCursor()
        added_format = QTextCharFormat(); added_format.setBackground(QColor(230, 255, 230))
        removed_format = QTextCharFormat(); removed_format.setBackground(QColor(255, 230, 230))
        context_format = QTextCharFormat(); context_format.setForeground(QColor(128, 128, 128))
        normal_format = QTextCharFormat()
        
        for change_type, content in diff.diff_lines:
            if change_type == "added":
                cursor.setCharFormat(added_format); cursor.insertText(f"+ {content}\n")
            elif change_type == "removed":
                cursor.setCharFormat(removed_format); cursor.insertText(f"- {content}\n")
            elif change_type == "context":
                cursor.setCharFormat(context_format); cursor.insertText(f"{content}\n")
            else:
                cursor.setCharFormat(normal_format); cursor.insertText(f"  {content}\n")
        self.show_diff_stats(diff)
    
    def show_binary_file_diff(self, diff: FileDiff):
        self.header_label.setText(f"{diff.file_path} (바이너리 파일)")
        self.diff_text.setPlainText(f"바이너리 파일: {diff.change_summary}")
        self.stats_label.setText("")
    
    def show_diff_stats(self, diff: FileDiff):
        added_lines = sum(1 for change_type, _ in diff.diff_lines if change_type == "added")
        removed_lines = sum(1 for change_type, _ in diff.diff_lines if change_type == "removed")
        self.stats_label.setText(f"추가: +{added_lines}줄, 제거: -{removed_lines}줄")
    
    def clear_diff(self):
        self.header_label.setText("파일을 선택하여 변경사항을 확인하세요")
        self.diff_text.clear()
        self.stats_label.setText("")


class SearchResultWidget(QTreeWidget):
    """검색 결과 위젯"""
    
    result_double_clicked = Signal(dict)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
    
    def setup_ui(self):
        self.setHeaderLabels(["검색 결과", "버전", "파일", "라인"])
        self.setRootIsDecorated(True)
        self.itemDoubleClicked.connect(self._on_item_double_clicked)
        self.setColumnWidth(0, 300); self.setColumnWidth(1, 60); self.setColumnWidth(2, 150); self.setColumnWidth(3, 60)
    
    def show_search_results(self, results: List[dict], query: str):
        self.clear()
        if not results:
            self.addTopLevelItem(QTreeWidgetItem(["검색 결과 없음", "", "", ""]))
            return
        
        file_groups = {}
        for result in results:
            file_path = result["file_path"]
            if file_path not in file_groups: file_groups[file_path] = []
            file_groups[file_path].append(result)
        
        for file_path, file_results in file_groups.items():
            file_item = QTreeWidgetItem([f"📄 {file_path}", "", "", f"({len(file_results)}개)"])
            file_item.setExpanded(True)
            for result in file_results:
                line_content = result["line_content"].strip()
                highlighted_content = line_content.replace(query, f"**{query}**")
                result_item = QTreeWidgetItem([highlighted_content, f"v{result['version'].number}", "", str(result["line_number"])])
                result_item.setData(0, Qt.UserRole, result)
                file_item.addChild(result_item)
            self.addTopLevelItem(file_item)
    
    def _on_item_double_clicked(self, item: QTreeWidgetItem, column: int):
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
        info_group = QGroupBox("프로젝트 정보"); info_layout = QVBoxLayout(info_group)
        self.name_label = QLabel(); self.description_label = QLabel(); self.created_label = QLabel()
        self.version_label = QLabel(); self.files_label = QLabel()
        info_layout.addWidget(self.name_label); info_layout.addWidget(self.description_label); info_layout.addWidget(self.created_label)
        info_layout.addWidget(self.version_label); info_layout.addWidget(self.files_label); layout.addWidget(info_group)
        recent_group = QGroupBox("최근 버전"); recent_layout = QVBoxLayout(recent_group)
        self.recent_versions_list = QListWidget(); self.recent_versions_list.setMaximumHeight(150); recent_layout.addWidget(self.recent_versions_list)
        layout.addWidget(recent_group); layout.addStretch()
    
    def update_project_info(self, project_data: Dict):
        settings = project_data.get("settings", {})
        self.name_label.setText(f"📁 이름: {settings.get('name', 'Unknown')}")
        self.description_label.setText(f"📝 설명: {settings.get('description', '설명 없음')}")
        self.created_label.setText(f"📅 생성일: {settings.get('created_at', 'Unknown')}")
        self.version_label.setText(f"📋 현재 버전: v{project_data.get('current_version', 0)}")
        self.files_label.setText(f"📄 추적 파일: {project_data.get('tracked_files_count', 0)}개")
        
        self.recent_versions_list.clear()
        versions = project_data.get("versions", [])
        for version_data in sorted(versions, key=lambda v: v["number"], reverse=True)[:5]:
            item_text = f"v{version_data['number']} - {version_data['description'][:30]}"
            if len(version_data['description']) > 30: item_text += "..."
            item = QListWidgetItem(item_text); item.setToolTip(version_data['description']); self.recent_versions_list.addItem(item)


class StatusBarWidget(QWidget):
    """상태바 위젯"""
    def __init__(self, parent=None):
        super().__init__(parent); self.setup_ui()
    def setup_ui(self):
        layout = QHBoxLayout(self); layout.setContentsMargins(8, 4, 8, 4)
        self.status_label = QLabel("준비"); self.changed_files_label = QLabel(""); self.version_label = QLabel("")
        layout.addWidget(self.status_label); layout.addStretch(); layout.addWidget(self.changed_files_label)
        layout.addWidget(QLabel("|")); layout.addWidget(self.version_label)
    def update_status(self, status_text: str): self.status_label.setText(status_text)
    def update_changed_files(self, count: int):
        if count > 0:
            self.changed_files_label.setText(f"⚠️ 변경된 파일: {count}개"); self.changed_files_label.setStyleSheet("color: orange; font-weight: bold;")
        else:
            self.changed_files_label.setText("✅ 모든 파일 최신 상태"); self.changed_files_label.setStyleSheet("color: green;")
    def update_version(self, current_version: int, total_versions: int):
        self.version_label.setText(f"v{current_version} (총 {total_versions}개)")