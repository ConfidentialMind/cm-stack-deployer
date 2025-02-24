User does:
- pulls this public repo or gets it from our Web UI (TBD)
  - sends keys to CM
  - fills simplified vars (yaml?)
- installs host OS prerequisites (if required) -- we potentially can automate this, will require a few days
- gets Kubeconf
- installs tools
- runs Tofu

Tofu does:
- git clone deps using .secrets/cm-stack-dependencies
- git clone base using .secrets/cm-stack-base
- generates varsD and varsB from the simplified vars
- deploys ArgoCD
- waits for Argo to be ready
- applies deps using:
  - Kubeconf
  - VarsD
  - cm-stack-dependencies
- waits for deps root app ready, synced and healthy
- shows how to port-forwards Argo
- shows the url and the credentials in output
- applies base using:
  - Kubeconf
  - VarsB
  - cm-stack-dependencies
- waits for base root app ready, synced and healthy

Benefits:
- user does not want to puke, while reading docs and once again while installing
- I don't want to puke each time updating the docs