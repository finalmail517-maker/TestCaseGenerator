import os
import shutil
from pathlib import Path
from typing import List, Optional, Dict, Tuple
import subprocess
import tempfile
import json
from datetime import datetime
from logger import get_app_logger

logger = get_app_logger("git_handler")

class GitHandler:
    """Handle Git repository operations with diff detection and incremental testing"""
    
    def __init__(self):
        self.repos_dir = Path("temp_repos")
        self.repos_dir.mkdir(exist_ok=True)
        
        # Store for tracking repository states
        self.repo_states_file = self.repos_dir / "repo_states.json"
        self.repo_states = self._load_repo_states()
        
        # Supported code file extensions
        self.code_extensions = {
            '.py', '.js', '.jsx', '.ts', '.tsx', '.java', '.cpp', '.c',
            '.cs', '.go', '.rb', '.php', '.swift', '.kt', '.rs', '.scala',
            '.r', '.m', '.h', '.hpp'
        }
    
    def clone_or_pull_repository(
        self,
        repo_url: str,
        branch: str = "main",
        depth: int = 1
    ) -> Tuple[Path, Dict]:
        """
        Clone repository or pull latest changes if already exists
        
        Args:
            repo_url: URL of the Git repository
            branch: Branch to clone/pull
            depth: Clone depth (1 for shallow clone)
            
        Returns:
            Tuple of (repo_path, change_info)
            change_info contains: has_changes, changed_files, previous_commit, current_commit
        """
        repo_name = self._sanitize_repo_name(repo_url)
        repo_path = self.repos_dir / repo_name
        
        change_info = {
            'has_changes': False,
            'changed_files': [],
            'new_files': [],
            'deleted_files': [],
            'modified_files': [],
            'previous_commit': None,
            'current_commit': None,
            'is_new_repo': False
        }
        
        # Check if repo already exists
        if repo_path.exists() and (repo_path / '.git').exists():
            print(f"Repository already exists at {repo_path}")
            print("Pulling latest changes...")
            
            try:
                # Get current commit before pulling
                previous_commit = self._get_current_commit(repo_path)
                change_info['previous_commit'] = previous_commit
                
                # Pull latest changes
                result = subprocess.run(
                    ['git', 'pull', 'origin', branch],
                    cwd=repo_path,
                    capture_output=True,
                    text=True,
                    timeout=300
                )
                
                if result.returncode != 0:
                    raise Exception(f"Git pull failed: {result.stderr}")
                
                # Get new commit after pulling
                current_commit = self._get_current_commit(repo_path)
                change_info['current_commit'] = current_commit
                
                # Check if there are changes
                if previous_commit != current_commit:
                    change_info['has_changes'] = True
                    
                    # Get list of changed files
                    diff_info = self._get_diff_between_commits(
                        repo_path, 
                        previous_commit, 
                        current_commit
                    )
                    change_info.update(diff_info)
                    
                    print(f"✓ Changes detected: {len(change_info['changed_files'])} files changed")
                    print(f"  - Modified: {len(change_info['modified_files'])}")
                    print(f"  - New: {len(change_info['new_files'])}")
                    print(f"  - Deleted: {len(change_info['deleted_files'])}")
                else:
                    print("✓ No changes detected - repository is up to date")
                
                # Update repo state
                self._save_repo_state(repo_url, repo_path, current_commit)
                
                return repo_path, change_info
                
            except Exception as e:
                print(f"Error pulling repository: {e}")
                print("Removing existing repo and cloning fresh...")
                shutil.rmtree(repo_path)
        
        # Clone repository (first time or after error)
        change_info['is_new_repo'] = True
        change_info['has_changes'] = True  # Treat as changes since it's new
        
        try:
            cmd = [
                'git', 'clone',
                '--branch', branch,
                '--depth', str(depth),
                repo_url,
                str(repo_path)
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300
            )
            
            if result.returncode != 0:
                raise Exception(f"Git clone failed: {result.stderr}")
            
            # Get initial commit
            current_commit = self._get_current_commit(repo_path)
            change_info['current_commit'] = current_commit
            
            # Get all code files as "new" files
            code_files = self.get_code_files(repo_path)
            change_info['new_files'] = [str(f.relative_to(repo_path)) for f in code_files]
            change_info['changed_files'] = change_info['new_files']
            
            # Save repo state
            self._save_repo_state(repo_url, repo_path, current_commit)
            
            print(f"✓ Repository cloned: {len(change_info['new_files'])} code files found")
            
            return repo_path, change_info
            
        except subprocess.TimeoutExpired:
            raise Exception("Git clone operation timed out")
        except Exception as e:
            raise Exception(f"Failed to clone repository: {str(e)}")
    
    def get_changed_code_files(
        self,
        repo_path: Path,
        changed_files: List[str]
    ) -> List[Path]:
        """
        Get full paths of changed code files
        
        Args:
            repo_path: Path to repository
            changed_files: List of relative file paths
            
        Returns:
            List of absolute paths to changed code files
        """
        code_files = []
        
        for file_path in changed_files:
            full_path = repo_path / file_path
            
            if full_path.exists() and full_path.suffix.lower() in self.code_extensions:
                # Skip very large files (> 1MB)
                if full_path.stat().st_size < 1_000_000:
                    code_files.append(full_path)
        
        return code_files
    
    def _get_current_commit(self, repo_path: Path) -> str:
        """Get current commit hash"""
        try:
            result = subprocess.run(
                ['git', 'rev-parse', 'HEAD'],
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=10
            )
            return result.stdout.strip() if result.returncode == 0 else 'unknown'
        except Exception:
            return 'unknown'
    
    def _get_diff_between_commits(
        self,
        repo_path: Path,
        old_commit: str,
        new_commit: str
    ) -> Dict[str, List[str]]:
        """
        Get diff between two commits
        
        Returns:
            Dictionary with changed_files, modified_files, new_files, deleted_files
        """
        diff_info = {
            'changed_files': [],
            'modified_files': [],
            'new_files': [],
            'deleted_files': []
        }
        
        try:
            # Get diff with file status
            result = subprocess.run(
                ['git', 'diff', '--name-status', f'{old_commit}..{new_commit}'],
                cwd=repo_path,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')
                
                for line in lines:
                    if not line:
                        continue
                    
                    parts = line.split('\t', 1)
                    if len(parts) != 2:
                        continue
                    
                    status, filepath = parts
                    
                    # Only include code files
                    if Path(filepath).suffix.lower() in self.code_extensions:
                        diff_info['changed_files'].append(filepath)
                        
                        if status == 'A':
                            diff_info['new_files'].append(filepath)
                        elif status == 'D':
                            diff_info['deleted_files'].append(filepath)
                        elif status == 'M':
                            diff_info['modified_files'].append(filepath)
        
        except Exception as e:
            print(f"Error getting diff: {e}")
        
        return diff_info
    
    def get_function_changes(self, repo_path, modified_files, parser):
        """
        Detect function-level changes in modified files.
        
        Args:
            repo_path: Path to the git repository
            modified_files: List of modified file paths (relative to repo root)
            parser: CodeParser instance to parse code
            
        Returns:
            dict: {
                'added_functions': {filename: [function_names]},
                'removed_functions': {filename: [function_names]},
                'modified_functions': {filename: [function_names]}
            }
        """
        result = {
            'added_functions': {},
            'removed_functions': {},
            'modified_functions': {}
        }
        
        for file_path in modified_files:
            try:
                # Get current version
                current_file = Path(repo_path) / file_path
                if not current_file.exists():
                    continue
                    
                with open(current_file, 'r', encoding='utf-8', errors='ignore') as f:
                    current_code = f.read()
                
                # Parse current version to get functions
                current_parsed = parser.parse_code(current_code, current_file.name)
                current_functions = {}
                for chunk in current_parsed.get('chunks', []):
                    if chunk.get('type') == 'function':
                        func_name = chunk.get('name', '')
                        if func_name:
                            current_functions[func_name] = chunk.get('code', '')
                
                # Try to get previous version from git
                try:
                    old_code = subprocess.check_output(
                        ['git', 'show', f'HEAD~1:{file_path}'],
                        cwd=repo_path,
                        stderr=subprocess.DEVNULL,
                        text=True,
                        timeout=10
                    )
                    
                    # Parse old version to get functions
                    old_parsed = parser.parse_code(old_code, Path(file_path).name)
                    old_functions = {}
                    for chunk in old_parsed.get('chunks', []):
                        if chunk.get('type') == 'function':
                            func_name = chunk.get('name', '')
                            if func_name:
                                old_functions[func_name] = chunk.get('code', '')
                    
                    # Calculate changes
                    old_func_names = set(old_functions.keys())
                    current_func_names = set(current_functions.keys())
                    
                    # Added functions
                    added = current_func_names - old_func_names
                    if added:
                        result['added_functions'][current_file.name] = list(added)
                        logger.info(f"➕ Added functions in {current_file.name}: {added}")
                    
                    # Removed functions
                    removed = old_func_names - current_func_names
                    if removed:
                        result['removed_functions'][current_file.name] = list(removed)
                        logger.info(f"🗑️ Removed functions in {current_file.name}: {removed}")
                    
                    # Modified functions (exist in both but code changed)
                    common = old_func_names & current_func_names
                    modified = []
                    for func_name in common:
                        if old_functions[func_name] != current_functions[func_name]:
                            modified.append(func_name)
                    
                    if modified:
                        result['modified_functions'][current_file.name] = modified
                        logger.info(f"✏️ Modified functions in {current_file.name}: {modified}")
                        
                except subprocess.CalledProcessError:
                    # File is new (no previous version) - all functions are "added"
                    if current_functions:
                        result['added_functions'][current_file.name] = list(current_functions.keys())
                        logger.info(f"➕ New file with functions: {current_file.name}")
                except subprocess.TimeoutExpired:
                    logger.warning(f"⚠️ Timeout getting old version of {file_path}")
                    
            except Exception as e:
                logger.warning(f"⚠️ Error detecting function changes in {file_path}: {e}")
        
        return result
    
    def _load_repo_states(self) -> Dict:
        """Load repository states from disk"""
        if self.repo_states_file.exists():
            try:
                with open(self.repo_states_file, 'r') as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}
    
    def _save_repo_state(self, repo_url: str, repo_path: Path, commit_hash: str):
        """Save repository state"""
        self.repo_states[repo_url] = {
            'path': str(repo_path),
            'commit': commit_hash,
            'last_updated': datetime.now().isoformat()
        }
        
        with open(self.repo_states_file, 'w') as f:
            json.dump(self.repo_states, f, indent=2)
    
    def get_previous_test_file(self, repo_url: str) -> Optional[Path]:
        """Get path to previous test file for this repository"""
        repo_name = self._sanitize_repo_name(repo_url)
        test_outputs_dir = Path("test_outputs")
        
        # Look for most recent test file for this repo
        pattern = f"test_cases_{repo_name}_*.csv"
        test_files = sorted(test_outputs_dir.glob(pattern), reverse=True)
        
        if test_files:
            return test_files[0]
        
        return None
    
    def clone_repository(
        self,
        repo_url: str,
        branch: str = "main",
        depth: int = 1
    ) -> Path:
        """
        Clone a Git repository (legacy method for backwards compatibility)
        
        Args:
            repo_url: URL of the Git repository
            branch: Branch to clone
            depth: Clone depth (1 for shallow clone)
            
        Returns:
            Path to cloned repository
        """
        repo_path, _ = self.clone_or_pull_repository(repo_url, branch, depth)
        return repo_path
    
    def get_code_files(self, repo_path: Path, max_files: int = 100) -> List[Path]:
        """
        Get all code files from repository
        
        Args:
            repo_path: Path to repository
            max_files: Maximum number of files to return
            
        Returns:
            List of code file paths
        """
        code_files = []
        
        # Exclude common directories
        exclude_dirs = {
            '.git', 'node_modules', 'venv', '.venv', 'env',
            '__pycache__', 'dist', 'build', 'target', '.idea',
            'vendor', 'deps', '.next'
        }
        
        for root, dirs, files in os.walk(repo_path):
            # Filter out excluded directories
            dirs[:] = [d for d in dirs if d not in exclude_dirs]
            
            for file in files:
                file_path = Path(root) / file
                
                # Check if it's a code file
                if file_path.suffix.lower() in self.code_extensions:
                    # Skip very large files (> 1MB)
                    if file_path.stat().st_size < 1_000_000:
                        code_files.append(file_path)
                        
                        if len(code_files) >= max_files:
                            return code_files
        
        return code_files
    
    def get_repo_structure(self, repo_path: Path) -> dict:
        """Get repository structure information"""
        structure = {
            'total_files': 0,
            'code_files': 0,
            'directories': 0,
            'file_types': {},
            'languages': set()
        }
        
        language_map = {
            '.py': 'Python',
            '.js': 'JavaScript',
            '.jsx': 'JavaScript',
            '.ts': 'TypeScript',
            '.tsx': 'TypeScript',
            '.java': 'Java',
            '.cpp': 'C++',
            '.c': 'C',
            '.cs': 'C#',
            '.go': 'Go',
            '.rb': 'Ruby',
            '.php': 'PHP',
            '.rs': 'Rust',
        }
        
        for root, dirs, files in os.walk(repo_path):
            if '.git' not in root:
                structure['directories'] += len(dirs)
                structure['total_files'] += len(files)
                
                for file in files:
                    ext = Path(file).suffix.lower()
                    
                    if ext in self.code_extensions:
                        structure['code_files'] += 1
                        structure['file_types'][ext] = structure['file_types'].get(ext, 0) + 1
                        
                        if ext in language_map:
                            structure['languages'].add(language_map[ext])
        
        structure['languages'] = list(structure['languages'])
        return structure
    
    def _sanitize_repo_name(self, repo_url: str) -> str:
        """Extract and sanitize repository name from URL"""
        # Extract repo name from URL
        name = repo_url.rstrip('/').split('/')[-1]
        
        # Remove .git extension
        if name.endswith('.git'):
            name = name[:-4]
        
        # Remove invalid characters
        name = ''.join(c for c in name if c.isalnum() or c in '-_')
        
        return name or 'repo'
    
    def get_file_content(self, file_path: Path) -> Optional[str]:
        """
        Read file content safely
        
        Args:
            file_path: Path to file
            
        Returns:
            File content or None if error
        """
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                return f.read()
        except Exception:
            return None
    
    def cleanup(self, repo_path: Path = None):
        """Clean up cloned repositories"""
        if repo_path and repo_path.exists():
            shutil.rmtree(repo_path)
        elif self.repos_dir.exists():
            # Don't remove the entire directory, just old repos
            # Keep the repo_states.json file
            pass
    
    def get_commit_info(self, repo_path: Path) -> dict:
        """Get latest commit information"""
        try:
            # Get latest commit hash
            result = subprocess.run(
                ['git', 'rev-parse', 'HEAD'],
                cwd=repo_path,
                capture_output=True,
                text=True
            )
            commit_hash = result.stdout.strip() if result.returncode == 0 else 'unknown'
            
            # Get commit message
            result = subprocess.run(
                ['git', 'log', '-1', '--pretty=%B'],
                cwd=repo_path,
                capture_output=True,
                text=True
            )
            commit_message = result.stdout.strip() if result.returncode == 0 else 'unknown'
            
            # Get commit author
            result = subprocess.run(
                ['git', 'log', '-1', '--pretty=%an'],
                cwd=repo_path,
                capture_output=True,
                text=True
            )
            author = result.stdout.strip() if result.returncode == 0 else 'unknown'
            
            # Get commit date
            result = subprocess.run(
                ['git', 'log', '-1', '--pretty=%ai'],
                cwd=repo_path,
                capture_output=True,
                text=True
            )
            date = result.stdout.strip() if result.returncode == 0 else 'unknown'
            
            return {
                'hash': commit_hash[:7],
                'full_hash': commit_hash,
                'message': commit_message,
                'author': author,
                'date': date
            }
        except Exception:
            return {
                'hash': 'unknown',
                'full_hash': 'unknown',
                'message': 'unknown',
                'author': 'unknown',
                'date': 'unknown'
            }