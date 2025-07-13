# core/project.py
# 프로젝트 관리 클래스 - models, utils, diff_engine에만 의존

import os
import shutil
from datetime import datetime
from typing import List, Optional, Dict, Tuple

from common.utils import FileUtils, PathManager, JsonUtils, ValidationUtils
from core.models import (
    ProjectData, ProjectSettings, Version, FileStatus,
    FileChangeType, FileDiff
)
from core.diff_engine import DiffEngine, SearchEngine


class Project:
    """프로젝트 관리 클래스"""

    def __init__(self, project_root: str, path_manager: PathManager):
        self.root_path = project_root
        self.path_manager = path_manager
        self.project_name = os.path.basename(project_root)
        self.data = ProjectData()
        self.diff_engine = DiffEngine(project_root)
        self.search_engine = SearchEngine(project_root)
        self.versions_dir = os.path.join(project_root, "versions")
        self.config_path = os.path.join(project_root, "project.json")

    @property
    def current_version_dir(self) -> Optional[str]:
        if self.current_version == 0:
            return None # v0 상태에서는 작업 폴더가 없음
        return os.path.join(self.versions_dir, f"v{self.current_version}")

    def get_working_file_path(self, relative_path: str) -> str:
        if not self.current_version_dir:
            # v0 상태의 파일은 존재하지 않음 (이론상)
            return os.path.join(self.root_path, relative_path) # 임시 경로
        return os.path.join(self.current_version_dir, relative_path)

    def save_config(self):
        JsonUtils.save_json(self.data.to_dict(), self.config_path)

    @classmethod
    def create_new(cls, project_name: str, path_manager: PathManager,
                   initial_files: Optional[List[str]] = None, 
                   project_settings: Optional[ProjectSettings] = None) -> 'Project':
        """
        프로젝트 뼈대를 생성하고, 초기 파일이 있으면 v1을 생성합니다.
        """
        is_valid, error_msg = ValidationUtils.is_valid_project_name(project_name)
        if not is_valid: raise ValueError(error_msg)
        
        project_root = path_manager.get_project_root(project_name)
        if os.path.exists(project_root) and os.listdir(project_root):
            raise ValueError(f"프로젝트 '{project_name}'이 이미 존재하며 비어있지 않습니다.")
        
        # 1. 뼈대 생성
        FileUtils.ensure_dir(project_root)
        project = cls(project_root, path_manager)
        if project_settings is None:
            project_settings = ProjectSettings(name=project_name)
        project.data.settings = project_settings
        FileUtils.ensure_dir(project.versions_dir)
        
        # 2. 초기 파일이 있으면 v1 생성, 없으면 빈 프로젝트로 저장
        if initial_files:
            project.create_new_version("프로젝트 초기 생성", initial_files_from_outside=initial_files)
        else:
            project.save_config()
            
        return project

    def create_new_version(self, description: str, initial_files_from_outside: Optional[List[str]] = None):
        """
        새 버전을 생성합니다.
        - v1 생성 시: 외부 파일들을 v1 폴더로 복사합니다.
        - v2+ 생성 시: 이전 버전 폴더의 내용을 새 버전 폴더로 복사합니다.
        """
        is_valid, error_msg = ValidationUtils.is_valid_version_description(description)
        if not is_valid: raise ValueError(error_msg)

        new_version_num = self.data.current_version + 1
        new_version_dir = os.path.join(self.versions_dir, f"v{new_version_num}")
        FileUtils.ensure_dir(new_version_dir)
        
        files_for_this_version = []

        if self.current_version == 0 and initial_files_from_outside:
            # === v1 생성 로직 ===
            for external_path in initial_files_from_outside:
                file_name = os.path.basename(external_path)
                dest_path = os.path.join(new_version_dir, file_name)
                shutil.copy2(external_path, dest_path)
                files_for_this_version.append(file_name)
            # 프로젝트의 전체 추적 목록을 이 파일들로 초기화
            self.data.tracked_files = files_for_this_version[:]
        else:
            # === v2, v3... 생성 로직 ===
            source_dir = self.current_version_dir
            if source_dir and os.path.exists(source_dir):
                for item in os.listdir(source_dir):
                    s = os.path.join(source_dir, item)
                    d = os.path.join(new_version_dir, item)
                    if os.path.isdir(s):
                        shutil.copytree(s, d)
                    else:
                        shutil.copy2(s, d)
                # 이전 버전의 파일 목록을 그대로 가져옴
                files_for_this_version = [f for f in os.listdir(new_version_dir) if os.path.isfile(os.path.join(new_version_dir, f))]

        # 메타데이터 업데이트
        self.data.current_version = new_version_num
        self.update_file_hashes() # 새 버전 폴더 기준으로 해시 업데이트

        new_version = Version(
            number=new_version_num, description=description,
            created_at=datetime.now(), files=files_for_this_version
        )
        self.data.versions.append(new_version)
        self.save_config()
        return new_version

    def add_tracked_files(self, file_paths: List[str]):
        """외부 파일을 '현재 작업 버전 폴더'로 복사하고 추적 목록에 추가합니다."""
        if not self.current_version_dir:
            raise Exception("Cannot add files: No active version. Please create a version first.")

        for file_path in file_paths:
            file_name = os.path.basename(file_path)
            dest_path = os.path.join(self.current_version_dir, file_name)
            
            if os.path.abspath(file_path) != os.path.abspath(dest_path):
                shutil.copy2(file_path, dest_path)
            
            if file_name not in self.data.tracked_files:
                self.data.tracked_files.append(file_name)
            
            current_version_obj = self.data.get_version_by_number(self.current_version)
            if current_version_obj and file_name not in current_version_obj.files:
                current_version_obj.files.append(file_name)

        self.save_config()

    def update_file_hashes(self):
        """'현재 작업 버전 폴더'를 기준으로 파일 해시를 업데이트합니다."""
        self.data.file_hashes.clear()
        if not self.current_version_dir or not os.path.exists(self.current_version_dir):
            return

        for root, _, files in os.walk(self.current_version_dir):
            for file in files:
                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, self.current_version_dir)
                norm_rel_path = os.path.normpath(rel_path).replace('\\', '/')
                self.data.update_file_hash(norm_rel_path, FileUtils.get_file_hash(full_path))

    # ... 이하 다른 메서드들은 이전과 동일하게 유지 ...
    @classmethod
    def load_from_config(cls, config_path: str, path_manager: PathManager) -> 'Project':
        config_data = JsonUtils.load_json(config_path)
        project_root = os.path.dirname(config_path)
        project = cls(project_root, path_manager)
        project.data = ProjectData.from_dict(config_data)
        if project.data.settings is None:
            project.data.settings = ProjectSettings(name=project.project_name)
        return project

    def get_file_statuses(self) -> List[FileStatus]:
        statuses = []
        if not self.current_version_dir: return []
        
        base_path_for_status = self.current_version_dir
        
        current_version_obj = self.data.get_version_by_number(self.current_version)
        files_to_check = current_version_obj.files if current_version_obj else []

        for rel_path in files_to_check:
            working_file_path = self.get_working_file_path(rel_path)
            previous_hash = self.data.get_file_hash(rel_path)
            status = FileStatus.create_from_file(working_file_path, base_path_for_status, previous_hash)
            statuses.append(status)
        return statuses

    def save_to_current_version(self) -> bool:
        if self.current_version == 0:
            raise Exception("Cannot save to version 0. Please create a new version.")

        self.update_file_hashes()
        current_version_obj = self.data.get_version_by_number(self.current_version)
        if current_version_obj:
            current_version_obj.files = list(self.data.file_hashes.keys())
            current_version_obj.created_at = datetime.now()
        self.save_config()
        return True

    def rollback_to_version(self, version_number: int) -> bool:
        target_version = self.data.get_version_by_number(version_number)
        if not target_version:
            return False
        self.data.current_version = version_number
        self.save_config()
        return True

    def sync_project_folder(self) -> Dict[str, List[str]]:
        baseline_files = set()
        if self.current_version > 0:
            current_version_obj = self.data.get_version_by_number(self.current_version)
            if current_version_obj:
                baseline_files = set(current_version_obj.files)

        working_dir_files = set()
        if self.current_version_dir and os.path.exists(self.current_version_dir):
             for root, _, files in os.walk(self.current_version_dir):
                for file in files:
                    full_path = os.path.join(root, file)
                    rel_path = os.path.relpath(full_path, self.current_version_dir)
                    working_dir_files.add(os.path.normpath(rel_path).replace('\\', '/'))
        
        changes = {
            "added": sorted(list(working_dir_files - baseline_files)),
            "removed": sorted(list(baseline_files - working_dir_files)),
            "existing": sorted(list(working_dir_files & baseline_files))
        }
        return changes

    def apply_sync_changes(self, changes: Dict[str, List[str]]):
        tracked_set = set(self.data.tracked_files)
        tracked_set.update(changes["added"])
        self.data.tracked_files = sorted(list(tracked_set))

        if self.current_version > 0:
            current_version_obj = self.data.get_version_by_number(self.current_version)
            if current_version_obj:
                current_files_set = set(current_version_obj.files)
                current_files_set.update(changes["added"])
                current_files_set.difference_update(changes["removed"])
                current_version_obj.files = sorted(list(current_files_set))
        
        self.save_config()

    def remove_tracked_file(self, relative_path: str) -> bool:
        if relative_path in self.data.tracked_files:
            self.data.tracked_files.remove(relative_path)
        
        if self.current_version > 0:
            current_version_obj = self.data.get_version_by_number(self.current_version)
            if current_version_obj and relative_path in current_version_obj.files:
                current_version_obj.files.remove(relative_path)
        
        file_to_delete = self.get_working_file_path(relative_path)
        if os.path.exists(file_to_delete):
            os.remove(file_to_delete)

        self.save_config()
        return True

    def update_settings(self, settings: ProjectSettings):
        self.data.settings = settings
        self.save_config()

    def compare_with_current(self, version_number: int, file_path: str) -> FileDiff:
        old_version_file_path = os.path.join(self.versions_dir, f"v{version_number}", file_path)
        current_version_file_path = self.get_working_file_path(file_path)
        
        return self.diff_engine.compare_two_paths(
            old_version_file_path, current_version_file_path,
            str(version_number), "current", file_path
        )

    def get_version_changes(self, old_version: int, new_version: int) -> Dict[str, FileDiff]:
        old_v_obj = self.data.get_version_by_number(old_version)
        new_v_obj = self.data.get_version_by_number(new_version)
        if not old_v_obj or not new_v_obj: return {}
        all_files = set(old_v_obj.files) | set(new_v_obj.files)
        changes = {}
        for file_path in all_files:
            diff = self.diff_engine.compare_versions(old_version, new_version, file_path)
            if diff.has_changes:
                changes[file_path] = diff
        return changes
        
    def get_version_changes_with_working(self, version_number: int) -> Dict[str, FileDiff]:
        v_obj = self.data.get_version_by_number(version_number)
        current_files = set()
        if self.current_version_dir and os.path.exists(self.current_version_dir):
            current_files = set(os.listdir(self.current_version_dir))
        
        if not v_obj: return {}
        all_files = set(v_obj.files) | current_files
        changes = {}
        for file_path in all_files:
            diff = self.compare_with_current(version_number, file_path)
            if diff.has_changes:
                changes[file_path] = diff
        return changes

    def search_in_versions(self, query: str, file_extensions: List[str] = None, case_sensitive: bool = False) -> List[dict]:
        return self.search_engine.search_in_versions(query, self.data.versions, file_extensions, case_sensitive)

    @property
    def current_version(self) -> int: return self.data.current_version
    @property
    def tracked_files(self) -> List[str]: return self.data.tracked_files.copy()
    @property
    def versions(self) -> List[Version]: return self.data.versions.copy()
    @property
    def settings(self) -> ProjectSettings: return self.data.settings


class ProjectManager:
    def __init__(self, working_directory: str = None):
        self.path_manager = PathManager(working_directory)
    def create_project(self, name: str, initial_files: List[str] = None, project_settings: ProjectSettings = None) -> Project:
        return Project.create_new(name, self.path_manager, initial_files, project_settings)
    def load_project(self, config_path: str) -> Project:
        return Project.load_from_config(config_path, self.path_manager)