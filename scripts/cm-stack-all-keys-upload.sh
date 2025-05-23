#!/bin/bash

# Variables
cluster_name="<cluster-name>"  # Cluster name

# Repository and key mappings
declare -A repos_keys=(
    ["ConfidentialMind/stack-dependencies"]="cm-stack-dependencies.pub"
    ["ConfidentialMind/stack-base"]="cm-stack-base.pub"
)

echo "Adding deploy keys for cluster: $cluster_name"

# Add deploy keys to repositories
for repo in "${!repos_keys[@]}"; do
    key_file="${repos_keys[$repo]}"
    
    echo "Processing $repo with key $key_file..."
    
    if [[ ! -f "$key_file" ]]; then
        echo "✗ Error: Key file $key_file not found"
        continue
    fi
    
    # Read key and extract first two fields (remove user@hostname part)
    clean_key=$(awk '{print $1 " " $2}' "$key_file")
    
    # Add deploy key to repository
    echo "$clean_key" | gh repo deploy-key add - \
        --repo "$repo" \
        --title "$cluster_name"
    
    if [[ $? -eq 0 ]]; then
        echo "✓ Successfully added deploy key to $repo"
    else
        echo "✗ Failed to add deploy key to $repo"
    fi
done

echo "Done!"