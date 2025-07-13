# common/utils.py
# 순수 유틸리티 모듈 - 다른 모듈에 의존성 없음

import os
import json
import shutil
import hashlib
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional, Tuple, Any


class FileUtils:
    """파일 관련 유틸리티"""
    
    @staticmethod
    def get_file_hash(file_path: str) -> str:
        """파일의 MD5 해시값 계산"""
        if not os.path.exists(file_path):
            return ""
            
        hash_md5 = hashlib.md5()
        try:
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_md5.update(chunk)
            return hash_md5.hexdigest()
        except (IOError, OSError):
            return ""
    
    @staticmethod
    def get_file_mtime(file_path: str) -> datetime:
        """파일 수정 시간 반환"""
        try:
            timestamp = os.path.getmtime(file_path)
            return datetime.fromtimestamp(timestamp)
        except (OSError, IOError):
            return datetime.min
    
    @staticmethod
    def get_file_size(file_path: str) -> int:
        """파일 크기 반환 (bytes)"""
        try:
            return os.path.getsize(file_path)
        except (OSError, IOError):
            return 0
    
    @staticmethod
    def read_file_content(file_path: str, encoding: str = 'utf-8') -> str:
        """파일 내용 읽기 (텍스트 파일용)"""
        try:
            with open(file_path, 'r', encoding=encoding, errors='ignore') as f:
                return f.read()
        except (IOError, OSError, UnicodeError):
            return ""
    
    @staticmethod
    def is_text_file(file_path: str) -> bool:
        """텍스트 파일 여부 판단"""
        text_extensions = {
            '.txt', '.py', '.js', '.html', '.css', '.json', '.xml', '.md',
            '.yml', '.yaml', '.ini', '.cfg', '.conf', '.log', '.sql',
            '.c', '.cpp', '.h', '.java', '.cs', '.php', '.rb', '.go',
            '.rs', '.kt', '.swift', '.scala', '.sh', '.bat', '.ps1'
        }
        
        ext = Path(file_path).suffix.lower()
        return ext in text_extensions
    
    @staticmethod
    def is_large_file(file_path: str, threshold_mb: int = 10) -> bool:
        """대용량 파일 여부 판단"""
        size_bytes = FileUtils.get_file_size(file_path)
        size_mb = size_bytes / (1024 * 1024)
        return size_mb > threshold_mb
    
    @staticmethod
    def copy_file_preserve_structure(src: str, dst_dir: str, base_dir: str) -> str:
        """상대 경로 구조를 유지하며 파일 복사"""
        rel_path = os.path.relpath(src, base_dir)
        dst_path = os.path.join(dst_dir, rel_path)
        
        # 대상 디렉토리 생성
        os.makedirs(os.path.dirname(dst_path), exist_ok=True)
        
        # 파일 복사
        shutil.copy2(src, dst_path)
        return dst_path
    
    @staticmethod
    def ensure_dir(directory: str):
        """디렉토리가 없으면 생성"""
        os.makedirs(directory, exist_ok=True)


class PathManager:
    """경로 관리 유틸리티"""
    
    def __init__(self, working_directory: str = None):
        self.working_directory = working_directory or os.getcwd()
    
    def get_project_root(self, project_name: str) -> str:
        """프로젝트 루트 경로 반환 (실제 작업 공간)"""
        return os.path.join(self.working_directory, project_name)
    
    def get_project_config_path(self, project_name: str) -> str:
        """프로젝트 설정 파일 경로"""
        return os.path.join(self.get_project_root(project_name), "project.json")
    
    def get_versions_dir(self, project_name: str) -> str:
        """버전 디렉토리 경로"""
        return os.path.join(self.get_project_root(project_name), "versions")
    
    def get_version_dir(self, project_name: str, version: int) -> str:
        """특정 버전 디렉토리 경로"""
        return os.path.join(self.get_versions_dir(project_name), f"v{version}")
    
    def get_work_file_path(self, project_name: str, relative_path: str) -> str:
        """프로젝트 루트 기준 파일 절대경로"""
        return os.path.join(self.get_project_root(project_name), relative_path)


class JsonUtils:
    """JSON 관련 유틸리티"""
    
    @staticmethod
    def save_json(data: Any, file_path: str, indent: int = 2):
        """JSON 파일로 저장"""
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=indent, ensure_ascii=False, default=str)
    
    @staticmethod
    def load_json(file_path: str) -> Any:
        """JSON 파일 로드"""
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    @staticmethod
    def safe_load_json(file_path: str, default: Any = None) -> Any:
        """안전하게 JSON 파일 로드 (오류시 기본값 반환)"""
        try:
            return JsonUtils.load_json(file_path)
        except (IOError, OSError, json.JSONDecodeError):
            return default


class StringUtils:
    """문자열 관련 유틸리티"""
    
    @staticmethod
    def truncate_text(text: str, max_length: int = 100, suffix: str = "...") -> str:
        """텍스트 길이 제한"""
        if len(text) <= max_length:
            return text
        return text[:max_length - len(suffix)] + suffix
    
    @staticmethod
    def normalize_line_endings(text: str) -> str:
        """줄바꿈 문자 정규화 (\\n으로 통일)"""
        return text.replace('\r\n', '\n').replace('\r', '\n')
    
    @staticmethod
    def safe_filename(filename: str) -> str:
        """파일명에 사용할 수 없는 문자 제거"""
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            filename = filename.replace(char, '_')
        return filename.strip()


class DiffUtils:
    """텍스트 diff 관련 유틸리티"""
    
    @staticmethod
    def get_line_diff(old_text: str, new_text: str) -> List[Tuple[str, str]]:
        """라인별 diff 계산 (간단한 구현)"""
        old_lines = StringUtils.normalize_line_endings(old_text).split('\n')
        new_lines = StringUtils.normalize_line_endings(new_text).split('\n')
        
        # 간단한 diff 알고리즘 (더 정교한 알고리즘은 difflib 사용 가능)
        result = []
        max_len = max(len(old_lines), len(new_lines))
        
        for i in range(max_len):
            old_line = old_lines[i] if i < len(old_lines) else ""
            new_line = new_lines[i] if i < len(new_lines) else ""
            
            if old_line == new_line:
                result.append(("unchanged", old_line))
            elif not old_line:
                result.append(("added", new_line))
            elif not new_line:
                result.append(("removed", old_line))
            else:
                result.append(("changed", f"{old_line} → {new_line}"))
        
        return result


class ValidationUtils:
    """입력 검증 유틸리티"""
    
    @staticmethod
    def is_valid_project_name(name: str) -> Tuple[bool, str]:
        """프로젝트 이름 유효성 검사"""
        if not name or not name.strip():
            return False, "프로젝트 이름을 입력해주세요."
        
        name = name.strip()
        
        if len(name) > 50:
            return False, "프로젝트 이름은 50자 이하로 입력해주세요."
        
        # 파일시스템에서 사용할 수 없는 문자 체크
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            if char in name:
                return False, f"프로젝트 이름에 '{char}' 문자는 사용할 수 없습니다."
        
        return True, ""
    
    @staticmethod
    def is_valid_version_description(description: str) -> Tuple[bool, str]:
        """버전 설명 유효성 검사"""
        if not description or not description.strip():
            return False, "버전 설명을 입력해주세요."
        
        description = description.strip()
        
        if len(description) > 200:
            return False, "버전 설명은 200자 이하로 입력해주세요."
        
        return True, ""