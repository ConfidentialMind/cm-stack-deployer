# CM Stack Deployer

A simplified deployment tool for CM Stack on Kubernetes.

## Overview

CM Stack Deployer automates the deployment of Confidential Mind's application stack on Kubernetes clusters using ArgoCD. It simplifies the deployment process by generating configurations from a simplified YAML file and automating the installation of all required components.

## Prerequisites

Before using CM Stack Deployer, ensure you have:

1. **Kubernetes Cluster**
   - A running Kubernetes cluster (1.23+ recommended)
   - A valid kubeconfig file with admin permissions

2. **SSH Keys**
   - Generate SSH keys for accessing the CM Stack repositories
   - Obtain permission to access the following repositories:
     - `git@github.com:ConfidentialMind/stack-dependencies.git`
     - `git@github.com:ConfidentialMind/stack-base.git`
     - `git@github.com:ConfidentialMind/stack.git`

3. **Required Tools**
   - kubectl (1.23+)
   - Helm (3.8+)
   - Python (3.8+)

4. **Docker Registry Access**
   - Obtain access to CM's container registry - `confidentialmind.azurecr.io`

## Installation

### Install CM Stack Deployer

```bash
# Clone the repository
git clone https://github.com/ConfidentialMind/cm-stack-deployer.git
cd cm-stack-deployer

# Install the package
pip install -e .

# Alternatively, install from PyPI
pip install cm-deployer
```

## Configuration

### 1. Prepare Directory Structure

Create a deployment directory with the following structure:

```
deployment/
├── config.yaml           # Your simplified configuration file
└── .secrets/             # Directory containing sensitive files
    ├── cm-images.json    # Container registry credentials
    ├── cm-stack-base     # SSH private key for stack-base repo
    ├── cm-stack-base.pub # SSH public key for stack-base repo
    ├── cm-stack-dependencies     # SSH private key for dependencies repo
    ├── cm-stack-dependencies.pub # SSH public key for dependencies repo
    ├── cm-stack-main     # SSH private key for main repo
    ├── cm-stack-main.pub # SSH public key for main repo
    └── kube.conf         # Kubernetes config file
```

### 2. Modify Configuration File

Copy `examples/config.yaml` to `deployment/config.yaml` and modify it according to your requirements.
All the parameters in the file have simple descriptions.

### 3. Prepare Secrets

1. **SSH Keys**: Generate SSH keys for repository access
   
   - Generate keys for each repository
   
   ```bash
   ssh-keygen -t ed25519 -f .secrets/cm-stack-dependencies
   ssh-keygen -t ed25519 -f .secrets/cm-stack-base
   ssh-keygen -t ed25519 -f .secrets/cm-stack-main
   ```
   
   -  Share public keys with CM team to grant repository access
   
   ```bash
   cat .secrets/cm-stack-dependencies.pub
   cat .secrets/cm-stack-base.pub
   cat .secrets/cm-stack-main.pub
   ```

2. **CM Docker Registry**: Save `cm-images.json` file with registry credentials *obtained from CM team.* to `deployment/.secrets/cm-images.json`

3. **Kubeconfig**: Copy your kubeconfig to `deployment/.secrets/kube.conf`

## Deployment

Run the CM Stack Deployer with your configuration:

```bash
# Navigate to your deployment directory
cd deployment

# Run the deployer
cm-deploy
```
> CM Stack Deployer will use `config.yaml` and `.secrets/*` from the directory it's executed from.
> It is possible to point it to other configs and secrets: `cm-deploy --config config.yaml --secrets-dir .secrets --output-dir generated`

### Advanced Options (optional)

```bash
# config.yaml path
--config

# Secrets directory path
--secrets-dir

# Generated configs path
--output-dir

# Enable debug logging
--debug

# Skip dependencies deployment (if already deployed)
--skip-deps

# Skip base deployment
--skip-base

# Skip JWK generation
--skip-jwk

# Specify custom JWK directory
--jwk-dir .secrets/jwk-keys
```

## Further steps

1. Open `https://portal.<your-subdomain.example.com>`
2. Ask CM team for temporary username and password
3. proceed to [Portal Quickstart guide](https://docs.confidentialmind.com/files/0f5bd320-2b35-4acd-8566-ec51ec5a691b) 

## Accessing Deployed Services

After successful deployment, you'll be provided with access information:

1. **ArgoCD UI**
   - Access via port forwarding: `kubectl port-forward svc/argocd-server -n argocd 8080:443`
   - URL: https://localhost:8080
   - Credentials will be displayed in the deployment output

2. **CM Stack Services**
   - Access the services using the domain configured in your `config.yaml`:
     - Auth service: `https://auth.example.com`
     - API service: `https://api.example.com`
     - Portal: `https://portal.example.com`
     - Tools: `https://tools.example.com`

## Troubleshooting

### Common Issues

1. **ArgoCD fails to start**
   - Ensure your cluster has sufficient resources
   - Check ArgoCD logs: `kubectl logs -n argocd -l app.kubernetes.io/name=argocd-server`

2. **Repository access issues**
   - Verify SSH keys are correctly added to repositories
   - Check repository secret: `kubectl get secret -n argocd cm-stack-dependencies -o yaml`

3. **Deployment timeout**
   - Increase timeouts with `--timeout` flag
   - Check resource constraints in your cluster

4. **TLS issues**
   - Ensure DNS is properly configured for your domain
   - Check cert-manager logs: `kubectl logs -n cert-manager -l app=cert-manager`

### Getting Help

For additional help, check the following:

- Logs: Enable debug logging with `--debug` flag
- Check component status: `kubectl get pods -A`
- ArgoCD Applications: `kubectl get applications -n argocd`

## Known Issues

- The stack-dependencies app may be deployed too early, before Argo CD reads the repo secret
  - Workaround -- restart Argo CD pods
- Istio ingress pod may be deployed too early, before it knows the proper image name
  - Workaround -- restart Istio Ingress pod
## License

Copyright © 2025 Confidential Mind. All rights reserved.
