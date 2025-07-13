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
    
    # --- NEW: 추가된 필드 ---
    change_notes: str = ""  # 사용자가 직접 작성하는 변경 노트
    auto_log: List[Dict[str, str]] = field(default_factory=list) # 자동 변경 로그

    @property
    def created_at_display(self) -> str:
        return self.created_at.strftime('%Y-%m-%d %H:%M')
    
    @property
    def description_short(self) -> str:
        return StringUtils.truncate_text(self.description, 50)

    @property
    def auto_log_summary(self) -> str:
        """자동 로그 요약 (UI 표시용)"""
        if not self.auto_log:
            return ""
        added = sum(1 for log in self.auto_log if log.get("type") == "added")
        removed = sum(1 for log in self.auto_log if log.get("type") == "removed")
        modified = sum(1 for log in self.auto_log if log.get("type") == "modified")
        parts = []
        if added > 0: parts.append(f"+{added}")
        if removed > 0: parts.append(f"-{removed}")
        if modified > 0: parts.append(f"~{modified}")
        return f"({', '.join(parts)})" if parts else ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "number": self.number,
            "description": self.description,
            "created_at": self.created_at.isoformat(),
            "files": self.files,
            "change_notes": self.change_notes,
            "auto_log": self.auto_log
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Version':
        return cls(
            number=data["number"],
            description=data["description"],
            created_at=datetime.fromisoformat(data["created_at"]),
            files=data["files"],
            change_notes=data.get("change_notes", ""), # 이전 버전 호환
            auto_log=data.get("auto_log", [])       # 이전 버전 호환
        )


@dataclass
class ProjectSettings:
    """프로젝트 설정 정보"""
    name: str
    description: str = ""
    created_at: datetime = None
    author: str = ""
    tags: List[str] = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()
        if self.tags is None:
            self.tags = []
    
    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        return {
            "name": self.name,
            "description": self.description,
            "created_at": self.created_at.isoformat(),
            "author": self.author,
            "tags": self.tags
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ProjectSettings':
        """딕셔너리에서 설정 객체 생성"""
        created_at = datetime.fromisoformat(data["created_at"]) if "created_at" in data else datetime.now()
        return cls(
            name=data["name"],
            description=data.get("description", ""),
            created_at=created_at,
            author=data.get("author", ""),
            tags=data.get("tags", [])
        )


@dataclass
class FileDiff:
    """파일 diff 정보"""
    file_path: str
    old_version: int
    new_version: int
    old_content: str = ""
    new_content: str = ""
    is_text_file: bool = True
    diff_lines: List[tuple] = None  # (change_type, line_content)
    
    def __post_init__(self):
        if self.diff_lines is None:
            self.diff_lines = []
    
    @property
    def has_changes(self) -> bool:
        """변경사항 존재 여부"""
        return self.old_content != self.new_content
    
    @property
    def change_summary(self) -> str:
        """변경사항 요약"""
        if not self.has_changes:
            return "변경 없음"
        
        if not self.old_content:
            return "새 파일"
        elif not self.new_content:
            return "파일 삭제"
        else:
            return "파일 수정"


@dataclass 
class SearchResult:
    """검색 결과 항목"""
    version: Version
    file_path: str
    line_number: int
    line_content: str
    match_text: str
    context_before: List[str] = None
    context_after: List[str] = None
    
    def __post_init__(self):
        if self.context_before is None:
            self.context_before = []
        if self.context_after is None:
            self.context_after = []
    
    @property
    def display_text(self) -> str:
        """표시용 텍스트"""
        return f"v{self.version.number} - {os.path.basename(self.file_path)} (Line {self.line_number})"


class ProjectData:
    """프로젝트 전체 데이터를 담는 컨테이너"""
    
    def __init__(self):
        self.settings: ProjectSettings = None
        self.current_version: int = 0
        self.tracked_files: List[str] = []
        self.versions: List[Version] = []
        self.file_hashes: Dict[str, str] = {}  # 파일경로 -> 해시
        
    def to_dict(self) -> Dict[str, Any]:
        """전체 프로젝트 데이터를 딕셔너리로 변환"""
        return {
            "settings": self.settings.to_dict() if self.settings else {},
            "current_version": self.current_version,
            "tracked_files": self.tracked_files,
            "versions": [v.to_dict() for v in self.versions],
            "file_hashes": self.file_hashes
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ProjectData':
        """딕셔너리에서 프로젝트 데이터 생성"""
        project_data = cls()
        
        # 설정 정보 로드
        if "settings" in data and data["settings"]:
            project_data.settings = ProjectSettings.from_dict(data["settings"])
        
        # 기본 정보 로드
        project_data.current_version = data.get("current_version", 0)
        project_data.tracked_files = data.get("tracked_files", [])
        project_data.file_hashes = data.get("file_hashes", {})
        
        # 버전 정보 로드
        for version_data in data.get("versions", []):
            version = Version.from_dict(version_data)
            project_data.versions.append(version)
        
        return project_data
    
    def get_version_by_number(self, version_number: int) -> Optional[Version]:
        """버전 번호로 버전 객체 찾기"""
        for version in self.versions:
            if version.number == version_number:
                return version
        return None
    
    def get_latest_version(self) -> Optional[Version]:
        """최신 버전 반환"""
        if not self.versions:
            return None
        return max(self.versions, key=lambda v: v.number)
    
    def add_version(self, version: Version):
        """새 버전 추가"""
        self.versions.append(version)
        self.current_version = version.number
    
    def update_file_hash(self, file_path: str, hash_value: str):
        """파일 해시 업데이트"""
        self.file_hashes[file_path] = hash_value
    
    def get_file_hash(self, file_path: str) -> str:
        """파일 해시 조회"""
        return self.file_hashes.get(file_path, "")