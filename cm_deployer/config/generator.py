import json
from pathlib import Path
from typing import Optional, Tuple
import yaml

from .schema import SimplifiedConfig, GPUType

class ConfigGenerator:
    def __init__(self, config: SimplifiedConfig, secrets_dir: Path):
        """Initialize generator with config and secrets directory.
        
        Args:
            config: Validated simplified configuration
            secrets_dir: Path to directory containing secrets
        """
        self.config = config
        self.secrets_dir = secrets_dir

    def _read_file_content(self, path: Path) -> str:
        """Read file content as string."""
        if not path.exists():
            raise FileNotFoundError(f"Required file not found: {path}")
        return path.read_text()

    def _load_registry_auth(self) -> str:
        """Load registry authentication JSON as string."""
        return self._read_file_content(self.secrets_dir / 'cm-images.json')

    def _load_repo_key(self, key_name: str) -> str:
        """Load repository SSH key as string."""
        return self._read_file_content(self.secrets_dir / key_name)

    def _load_tls_cert(self) -> Tuple[Optional[str], Optional[str]]:
        """Load TLS certificate and key if use_own_cert is True."""
        if not self.config.tls.use_own_cert:
            return None, None

        cert = self._read_file_content(self.secrets_dir / 'tls' / 'fullchain.pem')
        key = self._read_file_content(self.secrets_dir / 'tls' / 'privkey.pem')
        return cert, key

    def generate_deps_config(self) -> dict:
        """Generate configuration for Stack Dependencies."""
        return {
            'deploy': {
                'cert_manager': self.config.tls.enabled,  # Auto-deploy if TLS is enabled
                'longhorn_csi': self.config.storage.deploy_longhorn,
                'nvidia_plugin': self.config.gpu == GPUType.NVIDIA
            }
        }

    def generate_base_config(self) -> dict:
        """Generate configuration for Stack Base.
        
        Following Terraform's approach in passing variables to Helm/K8s.
        """
        # Load required secrets as raw strings
        registry_auth = self._load_registry_auth()
        deps_key = self._load_repo_key('cm-stack-dependencies')
        base_key = self._load_repo_key('cm-stack-base')
        cert, key = self._load_tls_cert() if self.config.tls.use_own_cert else (None, None)

        base_config = {
            'base_domain': self.config.base_domain,
            
            'tls': {
                'enabled': self.config.tls.enabled,
                'certManager': {
                    'enabled': self.config.tls.enabled and not self.config.tls.use_own_cert,
                    'email': self.config.tls.email
                },
                'ownCert': {
                    'useOwnCert': self.config.tls.use_own_cert,
                    'fullchainCertificate': cert,
                    'privateKey': key
                }
            },

            'db': {
                'backup': {
                    'enabled': self.config.database_backup.enabled,
                    'volumeSnapshot': {
                        'className': self.config.storage.snapshot_class
                    },
                    'retentionPolicy': f"{self.config.database_backup.retention_days}d",
                    'schedule': self.config.database_backup.schedule
                }
            },

            # Pass secrets as raw strings, letting Helm/K8s handle the parsing
            'secrets': {
                'cmImageRegistryKey': registry_auth,
                'cmStackBaseRepoKey': base_key,
                'cmStackRepoTektonKey': deps_key  # Note: check if this is the correct mapping
            }
        }

        return base_config

def generate_configs(config_path: Path, secrets_dir: Path) -> Tuple[dict, dict]:
    """Generate both configurations from simplified config file."""
    # Load and validate configuration
    config = SimplifiedConfig.from_yaml(config_path)
    config.validate()

    # Generate configurations
    generator = ConfigGenerator(config, secrets_dir)
    deps_config = generator.generate_deps_config()
    base_config = generator.generate_base_config()

    return deps_config, base_config

def save_configs(deps_config: dict, base_config: dict, output_dir: Path) -> None:
    """Save generated configurations to files."""
    output_dir.mkdir(parents=True, exist_ok=True)

    with open(output_dir / 'deps-values.yaml', 'w') as f:
        yaml.dump(deps_config, f, default_flow_style=False)

    with open(output_dir / 'base-values.yaml', 'w') as f:
        yaml.dump(base_config, f, default_flow_style=False)