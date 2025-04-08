from .generator import generate_configs, save_configs, update_base_config_with_jwk
from .schema import SimplifiedConfig, GPUType
from pathlib import Path
import yaml

def load_defaults() -> dict:
    """Load default values from the defaults file.
    
    Returns:
        dict: Default values
    """
    defaults_path = Path(__file__).parent / "defaults.yaml"
    if defaults_path.exists():
        with open(defaults_path, 'r') as f:
            return yaml.safe_load(f)
    return {}

__all__ = ['generate_configs', 'save_configs', 'update_base_config_with_jwk', 
           'SimplifiedConfig', 'GPUType', 'load_defaults']