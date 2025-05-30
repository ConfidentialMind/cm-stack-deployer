import argparse
import logging
import sys
import shutil
from pathlib import Path

from cm_deployer import __name__, __version__, __copyright__, __logo__
from cm_deployer.config.generator import generate_configs, save_configs, update_base_config_with_jwk
from cm_deployer.config.schema import SimplifiedConfig
from cm_deployer.jwk import JWKGenerator
from cm_deployer.k8s import ArgoCDInstaller, ArgoCDApplication, ArgoCDAppWaiter, RepoSecretManager, ArgoCDComponentManager, IstioJWKResourceProvisioner
from cm_deployer.utils.logger import setup_logger

logger = logging.getLogger(__name__)

# Repository information
REPOSITORIES = {
    "dependencies": {
        "name": "cm-stack-dependencies",
        "url": "git@github.com:ConfidentialMind/stack-dependencies.git",
        "key": "cm-stack-dependencies"
    },
    "base": {
        "name": "cm-stack-base",
        "url": "git@github.com:ConfidentialMind/stack-base.git",
        "key": "cm-stack-base"
    }
}

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
    parser.add_argument('--skip-deps', action='store_true',
                       help='Skip dependencies deployment')
    parser.add_argument('--skip-base', action='store_true',
                       help='Skip base deployment')
    parser.add_argument('--jwk-dir', type=Path, default=Path('.secrets/jwk-keys'),
                       help='Path to store JWK files')
    parser.add_argument('--skip-jwk', action='store_true',
                       help='Skip JWK generation')
    parser.add_argument('--skip-argocd-restart', action='store_true',
                       help='Skip ArgoCD components restart after creating repository secrets')
    return parser.parse_args()

def display_argocd_access(credentials):
    """Display ArgoCD access information."""
    logger.info("======== ArgoCD Access Information: ========")
    logger.info(" NOTE: The below credentials are for advanced setup and debugging mostly.")
    logger.info(" You don't need to access Argo CD for the daily use of CM Stack.")
    logger.info(" 1. Run the following command to set up port forwarding:")
    logger.info("    kubectl port-forward svc/argocd-server -n argocd 8080:443")
    logger.info(" 2. Open your browser and navigate to: https://localhost:8080")
    logger.info(" 3. Login with the following credentials:")
    logger.info(f"    Username: {credentials['username']}")
    logger.info(f"    Password: {credentials['password']}")
    logger.info(" NOTE: If your local port 8080 is in use by another process, pls use a different port.")
    logger.info(" NOTE: You may see a certificate warning in your browser. This is expected.")
    logger.info("=============================================")

def main():
    # Print the logo
    terminal_width = shutil.get_terminal_size().columns    
    centered_logo = '\n'.join(line.center(terminal_width) for line in __logo__.splitlines())
    print(centered_logo, file=sys.stdout)
    print(f"{__name__} v{__version__} {__copyright__}\n".center(terminal_width), file=sys.stdout)
    
    
    # Proceed with initialization
    args = parse_args()
    setup_logger(debug=args.debug)

    try:
        # Verify kubeconfig exists
        kubeconfig = args.secrets_dir / "kube.conf"
        if not kubeconfig.exists():
            raise FileNotFoundError(f"Kubeconfig not found at {kubeconfig}")

        # Load configuration to get target revisions
        config = SimplifiedConfig.from_yaml(args.config)
        deps_revision = config.git_revision.dependencies
        base_revision = config.git_revision.base
        
        logger.info(f"Using dependencies revision from config: {deps_revision}")
        logger.info(f"Using base revision from config: {base_revision}")

        # Generate configurations
        logger.info("Generating configurations...")
        deps_config, base_config = generate_configs(args.config, args.secrets_dir)
        save_configs(deps_config, base_config, args.output_dir)

        # Install ArgoCD (basic installation)
        logger.info("Installing ArgoCD (basic installation)...")
        argocd = ArgoCDInstaller(kubeconfig=kubeconfig)
        if not argocd.install():
            raise RuntimeError("Failed to install ArgoCD")

        logger.info("Waiting for ArgoCD server to be ready...")
        if not argocd.wait_ready():
            raise RuntimeError("ArgoCD server failed to become ready")
        
        # Initialize component manager to use for all ArgoCD operations
        component_manager = ArgoCDComponentManager(kubeconfig=kubeconfig)
        
        # Wait for all ArgoCD pods to become ready initially
        logger.info("Waiting for all ArgoCD pods to become ready initially...")
        if not component_manager.wait_for_all_argocd_pods_ready():
            logger.warning("Some ArgoCD pods are not ready. Proceeding anyway, but there might be issues.")
        else:
            logger.info("All ArgoCD pods are initially ready")

        # Create repository secrets for ArgoCD
        logger.info("Creating repository secrets for ArgoCD...")
        repo_secret_manager = RepoSecretManager(kubeconfig=kubeconfig)
        
        # Create secret for dependencies repository
        deps_info = REPOSITORIES["dependencies"]
        deps_key_path = args.secrets_dir / deps_info["key"]
        if not deps_key_path.exists():
            raise FileNotFoundError(f"Dependencies SSH key not found: {deps_key_path}")
            
        if not repo_secret_manager.create_repo_secret(
            secret_name=deps_info["name"],
            repo_url=deps_info["url"],
            ssh_key_path=deps_key_path
        ):
            raise RuntimeError(f"Failed to create repository secret for {deps_info['name']}")
            
        # Create secret for base repository
        base_info = REPOSITORIES["base"]
        base_key_path = args.secrets_dir / base_info["key"]
        if not base_key_path.exists():
            raise FileNotFoundError(f"Base SSH key not found: {base_key_path}")
            
        if not repo_secret_manager.create_repo_secret(
            secret_name=base_info["name"],
            repo_url=base_info["url"],
            ssh_key_path=base_key_path
        ):
            raise RuntimeError(f"Failed to create repository secret for {base_info['name']}")

        # Restart ArgoCD components to refresh repository configuration
        if not args.skip_argocd_restart:
            logger.info("Restarting ArgoCD components to refresh repository configuration...")
            if not component_manager.restart_argocd_components():
                logger.warning("Failed to restart some ArgoCD components. This might lead to repository access issues.")
                logger.warning("If you encounter issues, you may need to manually restart ArgoCD pods.")
            else:
                logger.info("All ArgoCD components have been restarted and are ready")
        else:
            logger.info("Skipping ArgoCD components restart as requested")

        # Initialize application manager and waiter
        app_manager = ArgoCDApplication(kubeconfig=kubeconfig)
        waiter = ArgoCDAppWaiter(kubeconfig=kubeconfig)
        
        if not args.skip_deps:
            # Apply Dependencies application with target revision
            logger.info(f"Applying Dependencies application with target revision: {deps_revision}...")
            if not app_manager.create_dependencies_app(deps_config, target_revision=deps_revision):
                raise RuntimeError("Failed to create Dependencies application")
                
            # Get and display ArgoCD credentials
            logger.info("Dependencies application has been deployed.")
            credentials = argocd.get_argocd_credentials()
            logger.info("While waiting for it to become ready, you can access ArgoCD UI:")
            display_argocd_access(credentials)

            # Wait for Dependencies application to be ready
            logger.info("Waiting for Dependencies application to be ready...")
            logger.info("This will also deploy and configure the cm-argocd-self-config application")
            if not waiter.wait_for_app_ready("cm-stack-dependencies-root-app"):
                raise RuntimeError("Dependencies application failed to become ready")
            
            logger.info("Dependencies application is ready!")
        else:
            logger.info("Skipping Dependencies deployment")
            logger.warning("Note: Skipping the Dependencies app means ArgoCD will not be fully configured")

        if not args.skip_base:
            # Provisionin JWK for stack-base (unless skipped)
            if not args.skip_jwk:
                logger.info("Generating JWK for stack-base...")
                # Use JWKGenerator to generate the keys
                jwk_generator = JWKGenerator(base_dir=args.jwk_dir)
                if not jwk_generator.generate_jwk():
                    raise RuntimeError("Failed to generate JWK")
                
                # Read JWK files
                private_key, jwk = jwk_generator.read_jwk_files()
                if not private_key or not jwk:
                    raise RuntimeError("Failed to read JWK files")
                
                # Use IstioJWKResourceProvisioner to create Kubernetes resources
                logger.info("Provisioning Istio JWK resources...")
                istio_provisioner = IstioJWKResourceProvisioner(kubeconfig=kubeconfig)
                if not istio_provisioner.provision_resources(private_key, jwk):
                    raise RuntimeError("Failed to provision Istio JWK resources in Kubernetes")
                
                # Update base_config with JWK content
                logger.info("Updating base configuration with JWK...")
                base_config = update_base_config_with_jwk(base_config, jwk)
            else:
                logger.info("Skipping JWK generation as requested")
                # Warn if JWK is likely needed
                logger.warning("Note: Stack Base typically requires JWK configuration. Make sure it's already set up.")
            
            # Save updated configuration
            save_configs(deps_config, base_config, args.output_dir)
            
            # Apply Base application with target revision
            logger.info(f"Applying Base application with target revision: {base_revision}...")
            if not app_manager.create_base_app(base_config, target_revision=base_revision):
                raise RuntimeError("Failed to create Base application")
                
            # Get and display ArgoCD credentials
            logger.info("Base application has been deployed.")
            credentials = argocd.get_argocd_credentials()
            logger.info("While waiting for it to become ready, you can access ArgoCD UI:")
            display_argocd_access(credentials)

            # Wait for Base application to be ready
            logger.info("Waiting for Base application to be ready...")
            if not waiter.wait_for_app_ready("cm-stack-base"):
                raise RuntimeError("Base application failed to become ready")
                
            logger.info("Base application is ready!")
        else:
            logger.info("Skipping Base deployment")

        # Get ArgoCD credentials for final display
        credentials = argocd.get_argocd_credentials()

        # Display success message and access instructions
        logger.info("\n")
        logger.info("="*50)
        logger.info("DEPLOYMENT COMPLETED SUCCESSFULLY!")
        logger.info("="*50 + "\n")
        
        logger.info("To access the ArgoCD UI:")
        display_argocd_access(credentials)
        
        logger.info("To access your deployed applications:")
        if not args.skip_deps:
            logger.info("Stack Dependencies: Check ArgoCD UI dependencies status")
        if not args.skip_base:
            logger.info(f"Stack Base: Access via the URLs configured in your domain (https://portal.{base_config.get('base_domain', 'unknown')})")
        
        return 0

    except Exception as e:
        logger.error(f"Deployment failed: {str(e)}")
        return 1

if __name__ == "__main__":
    exit(main())