import argparse
import logging
from pathlib import Path

from cm_deployer.config.generator import generate_configs, save_configs
from cm_deployer.git import GitOperations
from cm_deployer.k8s import ArgoCDInstaller
from cm_deployer.utils.logger import setup_logger

logger = logging.getLogger(__name__)

def parse_args():
    parser = argparse.ArgumentParser(description='CM Stack Deployer')
    parser.add_argument('--config', type=Path, default=Path('config.yaml'),
                       help='Path to configuration file')
    parser.add_argument('--secrets-dir', type=Path, default=Path('.secrets'),
                       help='Path to secrets directory')
    parser.add_argument('--output-dir', type=Path, default=Path('generated'),
                       help='Path to output directory')
    parser.add_argument('--debug', action='store_true',
                       help='Enable debug logging')
    return parser.parse_args()

def main():
    args = parse_args()
    setup_logger(debug=args.debug)

    try:
        # Verify kubeconfig exists
        kubeconfig = args.secrets_dir / "kube.conf"
        if not kubeconfig.exists():
            raise FileNotFoundError(f"Kubeconfig not found at {kubeconfig}")

        # Clone repositories
        logger.info("Cloning repositories...")
        git_ops = GitOperations(secrets_dir=args.secrets_dir)
        if not git_ops.clone_cm_repositories():
            raise RuntimeError("Failed to clone repositories")

        # Generate configurations
        logger.info("Generating configurations...")
        deps_config, base_config = generate_configs(args.config, args.secrets_dir)
        save_configs(deps_config, base_config, args.output_dir)

        # Install and configure ArgoCD
        logger.info("Installing ArgoCD...")
        argocd = ArgoCDInstaller(kubeconfig=kubeconfig)
        if not argocd.install():
            raise RuntimeError("Failed to install ArgoCD")

        logger.info("Waiting for ArgoCD to be ready...")
        if not argocd.wait_ready():
            raise RuntimeError("ArgoCD failed to become ready")

        # TODO: Apply configurations to ArgoCD
        logger.info("ArgoCD is ready! You can access it by running:")
        logger.info("kubectl port-forward svc/argocd-server -n argocd 8080:443")
        logger.info("Then visit: https://localhost:8080")

    except Exception as e:
        logger.error(f"Deployment failed: {str(e)}")
        return 1

    logger.info("Deployment completed successfully!")
    return 0

if __name__ == "__main__":
    exit(main())