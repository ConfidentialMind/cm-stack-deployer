from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional
import yaml

class GPUType(Enum):
    NONE = "none"
    NVIDIA = "nvidia"
    AMD = "amd"  # Reserved for future use

@dataclass
class TLSConfig:
    enabled: bool
    email: str
    use_own_cert: bool

@dataclass
class StorageConfig:
    deploy_longhorn: bool
    snapshot_class: str

@dataclass
class DatabaseBackupConfig:
    enabled: bool
    retention_days: int
    schedule: str

@dataclass
class GitRevisionConfig:
    """Configuration for git repository revisions."""
    dependencies: str = "main"
    base: str = "main"

@dataclass
class SimplifiedConfig:
    base_domain: str
    tls: TLSConfig
    storage: StorageConfig
    database_backup: DatabaseBackupConfig
    gpu: GPUType
    git_revision: GitRevisionConfig = field(default_factory=GitRevisionConfig)

    @classmethod
    def from_yaml(cls, path: Path) -> 'SimplifiedConfig':
        """Load and validate configuration from YAML file."""
        with open(path) as f:
            data = yaml.safe_load(f)

        # Handle git_revision configuration if present
        git_revision = GitRevisionConfig()
        if 'git_revision' in data:
            git_data = data['git_revision']
            if 'dependencies' in git_data:
                git_revision.dependencies = git_data['dependencies']
            if 'base' in git_data:
                git_revision.base = git_data['base']

        return cls(
            base_domain=data['base_domain'],
            tls=TLSConfig(
                enabled=data['tls']['enabled'],
                email=data['tls']['email'],
                use_own_cert=data['tls']['use_own_cert']
            ),
            storage=StorageConfig(
                deploy_longhorn=data['storage']['deploy_longhorn'],
                snapshot_class=data['storage']['snapshot_class']
            ),
            database_backup=DatabaseBackupConfig(
                enabled=data['database_backup']['enabled'],
                retention_days=data['database_backup']['retention_days'],
                schedule=data['database_backup']['schedule']
            ),
            gpu=GPUType(data['gpu']),
            git_revision=git_revision
        )

    def validate(self) -> None:
        """Validate configuration values."""
        if not self.base_domain:
            raise ValueError("base_domain must not be empty")
        
        if self.tls.enabled and not self.tls.email:
            raise ValueError("email is required when TLS is enabled")
        
        if not 1 <= self.database_backup.retention_days <= 30:
            raise ValueError("retention_days must be between 1 and 30")
        
        # Add more validation as needed