import os
import subprocess
from pathlib import Path
import tempfile
import stat
from typing import Optional
import logging
from enum import Enum, auto

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class RepoAction(Enum):
    SKIP = auto()
    PULL = auto()
    CLONE = auto()

class GitOperations:
    def __init__(self, secrets_dir: str = '.secrets'):
        """Initialize GitOperations with the path to secrets directory.
        
        Args:
            secrets_dir: Path to the directory containing SSH keys and other secrets.
                        Can be relative to current working directory or absolute.
        """
        # Get the absolute path of the current working directory
        cwd = Path.cwd()
        # Convert the secrets_dir to an absolute path
        self.secrets_dir = (cwd / secrets_dir).resolve()
        self.ssh_wrapper_script = None
        
        logger.debug(f"Initialized GitOperations with secrets directory: {self.secrets_dir}")
        
    def _create_ssh_wrapper(self, key_path: Path) -> str:
        """Create a temporary GIT_SSH wrapper script to use a specific SSH key.
        
        Args:
            key_path: Absolute path to the SSH private key
            
        Returns:
            Path to the created wrapper script
        """
        wrapper_content = f'''#!/bin/bash
ssh -i "{key_path}" -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null "$@"
'''
        
        # Create temporary file for the wrapper script
        fd, path = tempfile.mkstemp(prefix='git-ssh-wrapper-', suffix='.sh')
        os.write(fd, wrapper_content.encode())
        os.close(fd)
        
        # Make the wrapper script executable
        os.chmod(path, stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)
        
        return path

    def _is_git_repo(self, path: str) -> bool:
        """Check if the given path is a git repository.
        
        Args:
            path: Path to check
            
        Returns:
            bool: True if path is a git repository
        """
        try:
            subprocess.run(['git', 'rev-parse', '--git-dir'],
                         cwd=path,
                         stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE,
                         check=True)
            return True
        except subprocess.CalledProcessError:
            return False

    def _handle_existing_repo(self, target_dir: str, force: bool = False) -> RepoAction:
        """Handle cases where target directory already exists.
        
        Args:
            target_dir: Directory to check
            force: If True, skips prompting and forces pull
            
        Returns:
            RepoAction: The action to take (SKIP, PULL, or CLONE)
        """
        target_path = Path(target_dir).resolve()
        
        if not target_path.exists():
            return RepoAction.CLONE

        if not self._is_git_repo(target_path):
            if force:
                logger.info(f"Removing existing directory: {target_path}")
                shutil.rmtree(target_path)
                return RepoAction.CLONE
            
            response = input(f"\nDirectory {target_path} exists and is not a git repository.\n"
                           f"Do you want to remove it and clone? [y/N]: ").lower()
            if response == 'y':
                shutil.rmtree(target_path)
                return RepoAction.CLONE
            return RepoAction.SKIP

        if force:
            return RepoAction.PULL
            
        response = input(f"\nRepository already exists at {target_path}.\n"
                        f"Do you want to fetch and reset to origin? [Y/n]: ").lower()
        if response == 'n':
            return RepoAction.SKIP
        return RepoAction.PULL

    def _setup_git_env(self, key_name: str) -> dict:
        """Set up git environment with SSH wrapper.
        
        Args:
            key_name: Name of the SSH key file
            
        Returns:
            dict: Environment variables for git operations
            
        Raises:
            FileNotFoundError: If SSH key is not found
        """
        key_path = self.secrets_dir / key_name
        if not key_path.exists():
            raise FileNotFoundError(f"SSH key not found: {key_path}")
        
        logger.debug(f"Using SSH key: {key_path}")
        
        # Ensure key has correct permissions
        key_path.chmod(0o600)
        
        # Create SSH wrapper script
        self.ssh_wrapper_script = self._create_ssh_wrapper(key_path)
        
        # Set up environment with custom SSH command
        env = os.environ.copy()
        env['GIT_SSH'] = self.ssh_wrapper_script
        
        return env

    def clone_repository(self, 
                        repo_url: str, 
                        target_dir: str, 
                        key_name: str,
                        branch: Optional[str] = None,
                        force: bool = False) -> bool:
        """Clone or update a git repository using SSH authentication.
        
        Args:
            repo_url: SSH URL of the git repository
            target_dir: Directory where to clone the repository
            key_name: Name of the SSH key file in secrets directory
            branch: Optional branch name to checkout
            force: If True, skips prompting and forces pull for existing repos
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Convert target_dir to absolute path
            target_path = Path(target_dir).resolve()
            
            action = self._handle_existing_repo(target_path, force)
            
            if action == RepoAction.SKIP:
                logger.info(f"Skipping repository: {target_path}")
                return True

            env = self._setup_git_env(key_name)

            if action == RepoAction.PULL:
                logger.info(f"Fetching and resetting in {target_path}")
                # Fetch latest changes
                subprocess.run(['git', 'fetch', 'origin'], 
                             cwd=target_path,
                             env=env,
                             check=True,
                             stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE)
                
                # Reset to origin's HEAD
                subprocess.run(['git', 'reset', '--hard', 'origin/HEAD'],
                             cwd=target_path,
                             env=env,
                             check=True,
                             stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE)
                
                # Clean untracked files and directories
                subprocess.run(['git', 'clean', '-fd'],
                             cwd=target_path,
                             env=env,
                             check=True,
                             stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE)
            else:  # CLONE
                logger.info(f"Cloning {repo_url} into {target_path}")
                cmd = ['git', 'clone']
                if branch:
                    cmd.extend(['-b', branch])
                cmd.extend([repo_url, str(target_path)])
                
                subprocess.run(cmd, 
                             env=env,
                             check=True,
                             stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE)
            
            return True
            
        except FileNotFoundError as e:
            logger.error(f"SSH key error: {e}")
            return False
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Git operation failed: {e.stderr.decode()}")
            return False
            
        finally:
            # Clean up temporary SSH wrapper script
            if self.ssh_wrapper_script and os.path.exists(self.ssh_wrapper_script):
                os.remove(self.ssh_wrapper_script)

def clone_cm_repositories(work_dir: str = '.', force: bool = False) -> bool:
    """Clone both CM Stack Dependencies and Base repositories.
    
    Args:
        work_dir: Working directory for cloning repositories
        force: If True, skips prompting and forces pull for existing repos
        
    Returns:
        bool: True if both repositories were cloned successfully
    """
    # Convert work_dir to absolute path
    work_path = Path(work_dir).resolve()
    git_ops = GitOperations()
    success = True
    
    # Clone Dependencies repository
    deps_success = git_ops.clone_repository(
        repo_url="git@github.com:ConfidentialMind/stack-dependencies.git",
        target_dir=work_path / "stack-dependencies",
        key_name="cm-stack-dependencies",
        force=force
    )
    
    # Clone Base repository
    base_success = git_ops.clone_repository(
        repo_url="git@github.com:ConfidentialMind/stack-base.git",
        target_dir=work_path / "stack-base",
        key_name="cm-stack-base",
        force=force
    )
    
    return deps_success and base_success

if __name__ == "__main__":
    # Example usage
    success = clone_cm_repositories()
    if success:
        print("Repository operations completed successfully")
    else:
        print("Failed to complete repository operations")