# core/diff_engine.py
# 파일 비교 및 diff 기능 - models, utils에만 의존

import os
import difflib
from typing import List, Tuple, Optional, Dict

from common.utils import FileUtils, StringUtils, DiffUtils
from core.models import FileDiff, Version, FileChangeType



class DiffEngine:
    """파일 비교 엔진"""

    def __init__(self, project_root: str):
        self.project_root = project_root
        self.versions_dir = os.path.join(project_root, "versions")
    
    def compare_two_paths(self, old_file_path: str, new_file_path: str,
                        old_version_str: str, new_version_str: str, display_file_path: str) -> FileDiff:
        """두 개의 절대 파일 경로를 비교하는 일반적인 메서드"""
        old_content = FileUtils.read_file_content(old_file_path) if os.path.exists(old_file_path) else ""
        new_content = FileUtils.read_file_content(new_file_path) if os.path.exists(new_file_path) else ""

        is_text_file = FileUtils.is_text_file(display_file_path)
        diff_lines = self._calculate_diff_lines(old_content, new_content) if is_text_file else []

        # version 번호는 문자열로 대체될 수 있으므로 int 변환 시 주의
        try: old_v = int(old_version_str)
        except: old_v = -2 # -2는 문자열 버전을 의미
        try: new_v = int(new_version_str) if new_version_str != "current" else -1
        except: new_v = -2

        return FileDiff(
            file_path=display_file_path,
            old_version=old_v,
            new_version=new_v,
            old_content=old_content,
            new_content=new_content,
            is_text_file=is_text_file,
            diff_lines=diff_lines
        )

    def compare_versions(self, old_version: int, new_version: int, file_path: str) -> FileDiff:
        """두 버전 간 특정 파일 비교"""
        old_file_path = os.path.join(self.versions_dir, f"v{old_version}", file_path)
        new_file_path = os.path.join(self.versions_dir, f"v{new_version}", file_path)
        
        return self.compare_two_paths(old_file_path, new_file_path, str(old_version), str(new_version), file_path)

    def compare_with_current(self, version: int, file_path: str) -> FileDiff:
        """특정 버전과 현재 작업 파일 비교"""
        version_file_path = os.path.join(self.versions_dir, f"v{version}", file_path)
        current_file_path = os.path.join(self.project_root, file_path)

        old_content = FileUtils.read_file_content(version_file_path) if os.path.exists(version_file_path) else ""
        new_content = FileUtils.read_file_content(current_file_path) if os.path.exists(current_file_path) else ""

        is_text_file = FileUtils.is_text_file(file_path)
        diff_lines = self._calculate_diff_lines(old_content, new_content) if is_text_file else []

        return FileDiff(
            file_path=file_path,
            old_version=version,
            new_version=-1,  # -1은 current를 의미
            old_content=old_content,
            new_content=new_content,
            is_text_file=is_text_file,
            diff_lines=diff_lines
        )
    
    # NEW: 초기 상태(v0)와 비교하기 위한 메서드
    def compare_with_current_from_empty(self, file_path: str) -> FileDiff:
        """빈 상태(v0)와 현재 작업 파일 비교"""
        current_file_path = os.path.join(self.project_root, file_path)
        
        old_content = "" # 이전 버전이 없으므로 빈 내용
        new_content = FileUtils.read_file_content(current_file_path) if os.path.exists(current_file_path) else ""
        
        is_text_file = FileUtils.is_text_file(file_path)
        diff_lines = self._calculate_diff_lines(old_content, new_content) if is_text_file else []

        return FileDiff(
            file_path=file_path,
            old_version=0,
            new_version=-1,
            old_content=old_content,
            new_content=new_content,
            is_text_file=is_text_file,
            diff_lines=diff_lines
        )

    def _calculate_diff_lines(self, old_content: str, new_content: str) -> List[Tuple[str, str]]:
        """라인별 diff 계산 (difflib 사용)"""
        if old_content == new_content:
            return []
            
        old_lines = StringUtils.normalize_line_endings(old_content).splitlines()
        new_lines = StringUtils.normalize_line_endings(new_content).splitlines()

        diff_lines = []
        differ = difflib.unified_diff(old_lines, new_lines, lineterm='', n=3)

        # unified_diff의 헤더(---, +++)를 건너뜁니다.
        try:
            next(differ)
            next(differ)
        except StopIteration:
            pass

        for line in differ:
            if line.startswith('@@'):
                diff_lines.append(("context", line))
            elif line.startswith('-'):
                diff_lines.append(("removed", line[1:]))
            elif line.startswith('+'):
                diff_lines.append(("added", line[1:]))
            else:
                diff_lines.append(("unchanged", line[1:] if line.startswith(' ') else line))

        return diff_lines

    def get_version_changes(self, old_version: int, new_version: int, all_files: List[str]) -> Dict[str, FileDiff]:
        """두 버전 간 모든 추적 파일의 변경사항"""
        changes = {}
        for file_path in all_files:
            diff = self.compare_versions(old_version, new_version, file_path)
            if diff.has_changes:
                changes[file_path] = diff
        return changes
    
    # ... (이하 SearchEngine, DiffFormatter는 변경사항 없음)
    
# ... (이하 SearchEngine, DiffFormatter는 변경사항 없음)
class SearchEngine:
    """파일 내용 검색 엔진"""
    
    def __init__(self, project_root: str):
        self.project_root = project_root
        self.versions_dir = os.path.join(project_root, "versions")
    
    def search_in_versions(
        self, 
        query: str, 
        versions: List[Version], 
        file_extensions: List[str] = None,
        case_sensitive: bool = False
    ) -> List[dict]:
        """버전들에서 텍스트 검색"""
        results = []
        
        search_query = query if case_sensitive else query.lower()
        
        for version in versions:
            version_dir = os.path.join(self.versions_dir, f"v{version.number}")
            for file_path in version.files:
                # 파일 확장자 필터링
                if file_extensions:
                    if not any(file_path.lower().endswith(ext) for ext in file_extensions):
                        continue
                
                full_path = os.path.join(version_dir, file_path)
                
                if not os.path.exists(full_path) or not FileUtils.is_text_file(full_path):
                    continue
                
                try:
                    with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                        original_lines = f.readlines()
                        
                    for line_num, original_line in enumerate(original_lines, 1):
                        search_line = original_line if case_sensitive else original_line.lower()
                        if search_query in search_line:
                            results.append({
                                "version": version,
                                "file_path": file_path,
                                "line_number": line_num,
                                "line_content": original_line.strip(),
                                "match_text": query,
                            })
                except Exception:
                    continue # 파일 읽기 오류 무시
        
        return results
    
    def search_version_descriptions(self, query: str, versions: List[Version], case_sensitive: bool = False) -> List[Version]:
        """버전 설명에서 검색"""
        results = []
        
        search_query = query if case_sensitive else query.lower()
        
        for version in versions:
            search_text = version.description if case_sensitive else version.description.lower()
            
            if search_query in search_text:
                results.append(version)
        
        return results


class DiffFormatter:
    """Diff 결과 포맷팅 유틸리티"""
    
    @staticmethod
    def format_diff_for_display(diff: FileDiff) -> str:
        """UI 표시용 diff 포맷팅"""
        if not diff.is_text_file:
            return f"바이너리 파일: {diff.change_summary}"
        
        if not diff.has_changes:
            return "변경사항 없음"
        
        lines = []
        
        # 헤더
        if diff.new_version == -1:
            lines.append(f"--- v{diff.old_version}/{diff.file_path}")
            lines.append(f"+++ working/{diff.file_path}")
        else:
            lines.append(f"--- v{diff.old_version}/{diff.file_path}")
            lines.append(f"+++ v{diff.new_version}/{diff.file_path}")
        
        lines.append("")
        
        # diff 라인들
        for change_type, content in diff.diff_lines:
            if change_type == "context":
                lines.append(content)
            elif change_type == "removed":
                lines.append(f"- {content}")
            elif change_type == "added":
                lines.append(f"+ {content}")
            else:
                lines.append(f"  {content}")
        
        return "\n".join(lines)
    
    @staticmethod
    def get_diff_statistics(diff: FileDiff) -> Dict[str, int]:
        """diff 통계 정보"""
        stats = {
            "added_lines": 0,
            "removed_lines": 0,
            "unchanged_lines": 0
        }
        
        for change_type, _ in diff.diff_lines:
            if change_type == "added":
                stats["added_lines"] += 1
            elif change_type == "removed":
                stats["removed_lines"] += 1
            elif change_type == "unchanged":
                stats["unchanged_lines"] += 1
        
        return stats
    
    @staticmethod
    def format_diff_summary(diff: FileDiff) -> str:
        """diff 요약 정보"""
        if not diff.has_changes:
            return "변경 없음"
        
        stats = DiffFormatter.get_diff_statistics(diff)
        
        parts = []
        if stats["added_lines"] > 0:
            parts.append(f"+{stats['added_lines']}")
        if stats["removed_lines"] > 0:
            parts.append(f"-{stats['removed_lines']}")
        
        return " ".join(parts) if parts else "변경사항 있음"