# core/models.py
# 데이터 모델 클래스들 - utils에만 의존

import os
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from typing import List, Dict, Optional, Any

from common.utils import FileUtils, StringUtils


class FileChangeType(Enum):
    """파일 변경 타입"""
    UNCHANGED = "unchanged"
    MODIFIED = "modified" 
    ADDED = "added"
    DELETED = "deleted"


@dataclass
class FileStatus:
    """파일 상태 정보"""
    path: str
    name: str
    change_type: FileChangeType
    last_modified: datetime
    current_hash: str = ""
    previous_hash: str = ""
    file_size: int = 0
    is_text_file: bool = True
    
    @property
    def display_name(self) -> str:
        icons = {
            FileChangeType.UNCHANGED: "📄",
            FileChangeType.MODIFIED: "📝",
            FileChangeType.ADDED: "✨", 
            FileChangeType.DELETED: "❌"
        }
        return f"{icons.get(self.change_type, '❓')} {self.name}"
    
    @property
    def size_display(self) -> str:
        if self.file_size < 1024: return f"{self.file_size} B"
        elif self.file_size < 1024 * 1024: return f"{self.file_size // 1024} KB"
        else: return f"{self.file_size // (1024 * 1024)} MB"
    
    @classmethod
    def create_from_file(cls, file_path: str, base_path: str, previous_hash: str = "") -> 'FileStatus':
        rel_path = os.path.relpath(file_path, base_path) if os.path.isabs(file_path) else file_path
        name = os.path.basename(file_path)
        
        if os.path.exists(file_path):
            current_hash = FileUtils.get_file_hash(file_path)
            last_modified = FileUtils.get_file_mtime(file_path)
            file_size = FileUtils.get_file_size(file_path)
            is_text_file = FileUtils.is_text_file(file_path)
            
            if not previous_hash and current_hash:
                change_type = FileChangeType.ADDED
            elif current_hash != previous_hash:
                change_type = FileChangeType.MODIFIED
            else:
                change_type = FileChangeType.UNCHANGED
        else:
            current_hash, last_modified, file_size, is_text_file = "", datetime.min, 0, True
            change_type = FileChangeType.DELETED
        
        return cls(
            path=rel_path, name=name, change_type=change_type, last_modified=last_modified,
            current_hash=current_hash, previous_hash=previous_hash, file_size=file_size, is_text_file=is_text_file
        )


@dataclass
class Version:
    """버전 정보"""
    number: int
    description: str
    created_at: datetime
    files: List[str]
    change_notes: str = ""  # 사용자가 직접 작성하는 변경 노트

    @property
    def created_at_display(self) -> str:
        return self.created_at.strftime('%Y-%m-%d %H:%M')
    
    @property
    def description_short(self) -> str:
        return StringUtils.truncate_text(self.description, 50)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "number": self.number,
            "description": self.description,
            "created_at": self.created_at.isoformat(),
            "files": self.files,
            "change_notes": self.change_notes
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Version':
        return cls(
            number=data["number"],
            description=data["description"],
            created_at=datetime.fromisoformat(data["created_at"]),
            files=data.get("files", []),
            change_notes=data.get("change_notes", "")
        )


@dataclass
class ProjectSettings:
    """프로젝트 설정 정보"""
    name: str
    description: str = ""
    created_at: datetime = None
    author: str = ""
    tags: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self, dict_factory=lambda x: {k: v for (k, v) in x if v is not None})

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ProjectSettings':
        data['created_at'] = datetime.fromisoformat(data['created_at']) if 'created_at' in data else datetime.now()
        return cls(**data)


@dataclass
class FileDiff:
    """파일 diff 정보"""
    file_path: str
    old_version: int
    new_version: int
    old_content: str = ""
    new_content: str = ""
    is_text_file: bool = True
    diff_lines: List[tuple] = field(default_factory=list)
    
    @property
    def has_changes(self) -> bool:
        return self.old_content != self.new_content
    
    @property
    def change_summary(self) -> str:
        if not self.has_changes: return "변경 없음"
        if not self.old_content: return "새 파일"
        elif not self.new_content: return "파일 삭제"
        else: return "파일 수정"


@dataclass 
class SearchResult:
    """검색 결과 항목"""
    version: Version
    file_path: str
    line_number: int
    line_content: str
    match_text: str
    context_before: List[str] = field(default_factory=list)
    context_after: List[str] = field(default_factory=list)
    
    @property
    def display_text(self) -> str:
        return f"v{self.version.number} - {os.path.basename(self.file_path)} (Line {self.line_number})"


class ProjectData:
    """프로젝트 전체 데이터를 담는 컨테이너"""
    def __init__(self):
        self.settings: ProjectSettings = None
        self.current_version: int = 0
        self.tracked_files: List[str] = []
        self.versions: List[Version] = []
        self.file_hashes: Dict[str, str] = {}
        
    def to_dict(self) -> Dict[str, Any]:
        return {
            "settings": self.settings.to_dict() if self.settings else {},
            "current_version": self.current_version,
            "tracked_files": self.tracked_files,
            "versions": [v.to_dict() for v in self.versions],
            "file_hashes": self.file_hashes
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ProjectData':
        project_data = cls()
        if "settings" in data and data["settings"]:
            project_data.settings = ProjectSettings.from_dict(data["settings"])
        project_data.current_version = data.get("current_version", 0)
        project_data.tracked_files = data.get("tracked_files", [])
        project_data.file_hashes = data.get("file_hashes", {})
        project_data.versions = [Version.from_dict(v_data) for v_data in data.get("versions", [])]
        return project_data
    
    def get_version_by_number(self, version_number: int) -> Optional[Version]:
        for version in self.versions:
            if version.number == version_number:
                return version
        return None
    
    def get_latest_version(self) -> Optional[Version]:
        if not self.versions:
            return None
        return max(self.versions, key=lambda v: v.number)
    
    def add_version(self, version: Version):
        self.versions.append(version)
        self.current_version = version.number
    
    def update_file_hash(self, file_path: str, hash_value: str):
        self.file_hashes[file_path] = hash_value
    
    def get_file_hash(self, file_path: str) -> str:
        return self.file_hashes.get(file_path, "")