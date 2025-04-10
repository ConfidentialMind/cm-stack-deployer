ToDo:
- fix: stack-dependencies app is being deployed too early, before Argo CD "reads" the repo secret
- fix: istio ingress pod is being deployed too early -- before it "knows" the proper image name


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