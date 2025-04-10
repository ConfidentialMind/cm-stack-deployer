ToDo:
- fix: stack-dependencies app is being deployed too early, before Argo CD "reads" the repo secret
- fix: istio ingress pod is being deployed too early -- before it "knows" the proper image name
- feature: generate `stack-admin` password, store it in a secret, show it in `cm-deployer` output.

```bash
cm-quick-start/              # Root directory
├── README.md                   # Project documentation
├── requirements.txt            # Python dependencies
├── setup.py                   # Package installation configuration
│
├── cm_deployer/               # Main package directory
│   ├── __init__.py           # Package initialization
│   │
│   ├── cli.py                # Command-line interface handling
│   │
│   ├── config/               # Configuration handling
│   │   ├── __init__.py
│   │   ├── schema.py         # Variable schema and validation
│   │   ├── parser.py         # YAML parsing and processing
│   │   └── generator.py      # Configuration files generation
│   │
│   ├── k8s/                  # Kubernetes operations
│   │   ├── __init__.py
│   │   ├── argocd.py        # ArgoCD deployment and management
│   │   └── wait.py          # Wait for resources functionality
│   │
│   └── utils/               # Utility functions
│       ├── __init__.py
│       ├── logger.py        # Logging configuration
│       └── files.py         # File operations helpers
│
├── examples/                # Example configurations
│   └── config.yaml         # Example simplified vars file
│
├── scripts/                # Helper scripts
│   └── install_tools.sh    # Script to install required tools
│
└── tests/                  # Test directory
    ├── __init__.py
    ├── test_config.py     # Config tests
    ├── test_git.py        # Git operations tests
    └── test_k8s.py        # Kubernetes operations tests
```

## Workflow
### User does:
- pulls this public repo or gets it from our Web UI (TBD)
  - generates SSH keys
  - sends keys to CM team
  - fills simplified vars (yaml?)
- installs host OS prerequisites (if required) -- we potentially can automate this, will require a few days
- gets Kubeconf
- installs CM Stack Deployer prerequisites
- runs CM Stack Deployer

### CM Stack Deployer does:
- generates varsD and varsB from the simplified vars
- deploys ArgoCD
- waits for Argo to be ready
- applies deps using:
  - Kubeconf
  - VarsD
  - cm-stack-dependencies Argo App
- shows how to port-forwards Argo
- shows the url and the credentials in output
- waits for deps root app ready, synced and healthy
- applies base using:
  - Kubeconf
  - VarsB
  - cm-stack-dependencies Argo App
- shows how to port-forwards Argo
- shows the url and the credentials in output
- waits for base root app ready, synced and healthy


## Deployment Process

The deployment process follows these steps:

1. **Configuration Generation**
   - Validates your simplified configuration
   - Generates component-specific configurations

2. **ArgoCD Installation**
   - Installs ArgoCD basic components
   - Configures repository access

3. **Dependencies Deployment**
   - Deploys the dependencies stack via ArgoCD
   - Includes services like cert-manager, Longhorn, etc.

4. **JWK Generation**
   - Generates JSON Web Keys for authentication
   - Creates required Kubernetes resources

5. **Base Stack Deployment**
   - Deploys the base stack via ArgoCD
   - Includes core services and applications

6. **Verification**
   - Waits for all components to be ready
   - Provides access information