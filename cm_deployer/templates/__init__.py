"""Template management for CM Stack Deployer."""

from pathlib import Path


def get_template_path(template_name: str) -> Path:
    """Get the path to a template file.
    
    Args:
        template_name: Name of the template file (can include subdirectories)
        
    Returns:
        Path: Path to the template file
    
    Raises:
        FileNotFoundError: If template file cannot be found
    """
    # Since this __init__.py is in cm_deployer/templates/,
    # Path(__file__).parent gives us the templates directory
    templates_dir = Path(__file__).parent
    template_path = templates_dir / template_name
    
    if not template_path.exists():
        raise FileNotFoundError(f"Template '{template_name}' not found at {template_path}")
    
    return template_path