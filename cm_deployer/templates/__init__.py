"""Template management for CM Stack Deployer."""

import os
import pkg_resources
from pathlib import Path

def get_template_path(template_name: str) -> Path:
    """Get the path to a template file.
    
    Args:
        template_name: Name of the template file (can include subdirectories)
        
    Returns:
        Path: Path to the template file
    """
    # Try to find the template using pkg_resources (works in installed package)
    try:
        template_path = pkg_resources.resource_filename(
            "cm_deployer", f"templates/{template_name}"
        )
        if os.path.exists(template_path):
            return Path(template_path)
    except (pkg_resources.DistributionNotFound, KeyError):
        pass
    
    # Fallback to local development path
    package_dir = Path(__file__).parent
    template_path = package_dir / template_name
    if template_path.exists():
        return template_path
    
    # Try one more fallback location
    project_templates = Path.cwd() / "cm_deployer" / "templates" / template_name
    if project_templates.exists():
        return project_templates
    
    raise FileNotFoundError(f"Template {template_name} not found")