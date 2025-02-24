import pytest
from pathlib import Path
import yaml
import json
import shutil

from cm_deployer.config.schema import SimplifiedConfig, GPUType
from cm_deployer.config.generator import generate_configs, ConfigGenerator, save_configs

# Test directories setup
TEST_ROOT = Path(__file__).parent
EXAMPLES_DIR = TEST_ROOT / "examples"
SECRETS_DIR = TEST_ROOT / ".secrets"
OUTPUT_DIR = TEST_ROOT / "output"
TLS_DIR = SECRETS_DIR / "tls"

@pytest.fixture(scope="session")
def setup_test_directories():
    """Create test directories and cleanup after all tests."""
    EXAMPLES_DIR.mkdir(exist_ok=True)
    SECRETS_DIR.mkdir(exist_ok=True)
    TLS_DIR.mkdir(exist_ok=True)
    OUTPUT_DIR.mkdir(exist_ok=True)
    
    yield
    
    # Cleanup after tests
    shutil.rmtree(EXAMPLES_DIR)
    shutil.rmtree(SECRETS_DIR)
    shutil.rmtree(OUTPUT_DIR)

@pytest.fixture(scope="session")
def example_config(setup_test_directories):
    """Create an example config.yaml."""
    config = {
        "base_domain": "test.example.com",
        "tls": {
            "enabled": True,
            "email": "admin@example.com",
            "use_own_cert": False
        },
        "storage": {
            "deploy_longhorn": True,
            "snapshot_class": "longhorn"
        },
        "database_backup": {
            "enabled": True,
            "retention_days": 7,
            "schedule": "0 0 */4 * * *"
        },
        "gpu": "nvidia"
    }
    
    config_path = EXAMPLES_DIR / "config.yaml"
    with open(config_path, "w") as f:
        yaml.dump(config, f)
    
    return config_path

@pytest.fixture(scope="session")
def secrets_files(setup_test_directories):
    """Create all required secret files."""
    # Registry auth
    registry_auth = {
        "auths": {
            "confidentialmind.azurecr.io": {
                "auth": "dGVzdDp0ZXN0",
                "email": "test@example.com"
            }
        }
    }
    registry_path = SECRETS_DIR / "cm-images.json"
    with open(registry_path, "w") as f:
        json.dump(registry_auth, f)

    # Repository SSH keys
    deps_key = """-----BEGIN OPENSSH PRIVATE KEY-----
test-deps-key-content
-----END OPENSSH PRIVATE KEY-----"""
    
    base_key = """-----BEGIN OPENSSH PRIVATE KEY-----
test-base-key-content
-----END OPENSSH PRIVATE KEY-----"""

    deps_path = SECRETS_DIR / "cm-stack-dependencies"
    base_path = SECRETS_DIR / "cm-stack-base"
    
    deps_path.write_text(deps_key)
    base_path.write_text(base_key)

    return {
        "registry": registry_path,
        "deps_key": deps_path,
        "base_key": base_path,
        "registry_content": registry_auth,
        "deps_key_content": deps_key,
        "base_key_content": base_key
    }

def test_generate_deps_config(example_config, secrets_files):
    """Test Dependencies configuration generation."""
    deps_config, _ = generate_configs(example_config, SECRETS_DIR)
    
    # Verify structure
    assert deps_config == {
        "deploy": {
            "cert_manager": True,
            "longhorn_csi": True,
            "nvidia_plugin": True
        }
    }

def test_generate_base_config(example_config, secrets_files):
    """Test Base configuration generation."""
    _, base_config = generate_configs(example_config, SECRETS_DIR)
    
    # Verify structure
    assert base_config["base_domain"] == "test.example.com"
    
    # TLS configuration
    assert base_config["tls"]["enabled"] is True
    assert base_config["tls"]["certManager"]["enabled"] is True
    assert base_config["tls"]["certManager"]["email"] == "admin@example.com"
    assert base_config["tls"]["ownCert"]["useOwnCert"] is False
    
    # Database configuration
    assert base_config["db"]["backup"]["enabled"] is True
    assert base_config["db"]["backup"]["retentionPolicy"] == "7d"
    assert base_config["db"]["backup"]["schedule"] == "0 0 */4 * * *"
    assert base_config["db"]["backup"]["volumeSnapshot"]["className"] == "longhorn"
    
    # Secrets verification
    assert base_config["secrets"]["cmImageRegistryKey"] == json.dumps(secrets_files["registry_content"])
    assert base_config["secrets"]["cmStackBaseRepoKey"] == secrets_files["base_key_content"]
    assert base_config["secrets"]["cmStackRepoTektonKey"] == secrets_files["deps_key_content"]

def test_save_configs(example_config, secrets_files):
    """Test saving configurations to files."""
    deps_config, base_config = generate_configs(example_config, SECRETS_DIR)
    save_configs(deps_config, base_config, OUTPUT_DIR)
    
    # Verify files were created
    assert (OUTPUT_DIR / "deps-values.yaml").exists()
    assert (OUTPUT_DIR / "base-values.yaml").exists()
    
    # Verify content can be loaded
    with open(OUTPUT_DIR / "deps-values.yaml") as f:
        loaded_deps = yaml.safe_load(f)
        assert loaded_deps == deps_config
    
    with open(OUTPUT_DIR / "base-values.yaml") as f:
        loaded_base = yaml.safe_load(f)
        assert loaded_base == base_config

def test_missing_secrets(example_config):
    """Test error handling when secrets are missing."""
    # Create empty secrets directory
    empty_secrets = TEST_ROOT / "empty_secrets"
    empty_secrets.mkdir(exist_ok=True)
    
    try:
        with pytest.raises(FileNotFoundError):
            generate_configs(example_config, empty_secrets)
    finally:
        shutil.rmtree(empty_secrets)

if __name__ == "__main__":
    # Create necessary directories
    for dir_path in [EXAMPLES_DIR, SECRETS_DIR, TLS_DIR, OUTPUT_DIR]:
        dir_path.mkdir(parents=True, exist_ok=True)

    # Create example config
    config = {
        "base_domain": "test.example.com",
        "tls": {
            "enabled": True,
            "email": "admin@example.com",
            "use_own_cert": False
        },
        "storage": {
            "deploy_longhorn": True,
            "snapshot_class": "longhorn"
        },
        "database_backup": {
            "enabled": True,
            "retention_days": 7,
            "schedule": "0 0 */4 * * *"
        },
        "gpu": "nvidia"
    }
    
    with open(EXAMPLES_DIR / "config.yaml", "w") as f:
        yaml.dump(config, f)

    # Create secret files
    registry_auth = {
        "auths": {
            "confidentialmind.azurecr.io": {
                "auth": "dGVzdDp0ZXN0",
                "email": "test@example.com"
            }
        }
    }
    with open(SECRETS_DIR / "cm-images.json", "w") as f:
        json.dump(registry_auth, f)

    deps_key = """-----BEGIN OPENSSH PRIVATE KEY-----
test-deps-key-content
-----END OPENSSH PRIVATE KEY-----"""
    
    base_key = """-----BEGIN OPENSSH PRIVATE KEY-----
test-base-key-content
-----END OPENSSH PRIVATE KEY-----"""

    with open(SECRETS_DIR / "cm-stack-dependencies", "w") as f:
        f.write(deps_key)
    with open(SECRETS_DIR / "cm-stack-base", "w") as f:
        f.write(base_key)

    # Generate and save configs
    deps_config, base_config = generate_configs(
        EXAMPLES_DIR / "config.yaml",
        SECRETS_DIR
    )
    
    save_configs(deps_config, base_config, OUTPUT_DIR)
    
    print("\nDependencies config:")
    print("===================")
    with open(OUTPUT_DIR / "deps-values.yaml") as f:
        print(f.read())
    
    print("\nBase config:")
    print("===========")
    with open(OUTPUT_DIR / "base-values.yaml") as f:
        print(f.read())