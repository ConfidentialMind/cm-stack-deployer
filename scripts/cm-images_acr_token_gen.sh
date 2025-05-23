#!/bin/bash

# Configuration
cluster_name="<cluster-name>"  # Cluster name
validity="3600"                # Token validity in days
registry="confidentialmind"

# Transform cluster name to be Azure-compliant
# Replace non-alphanumeric characters with hyphens
normalized_name=$(echo "$cluster_name" | sed 's/[^a-zA-Z0-9-]/-/g')

# Truncate to fit within 50 char limit (accounting for '-readonly' suffix = 9 chars)
max_base_length=41
if [ ${#normalized_name} -gt $max_base_length ]; then
    normalized_name="${normalized_name:0:$max_base_length}"
fi

# Add -readonly suffix
token_name="${normalized_name}-readonly"

echo "Original cluster name: $cluster_name"
echo "Normalized token name: $token_name"
echo "Registry: ${registry}.azurecr.io"
echo "Validity: ${validity} days"

# Create the ACR token and capture the output
token_output=$(az acr token create \
  --name "$token_name" \
  --registry "$registry" \
  --scope-map _repositories_pull \
  --expiration-in-days "$validity" \
  --output json)

# Check if token creation was successful
if [ $? -ne 0 ]; then
    echo "Error: Failed to create ACR token"
    exit 1
fi

# Extract the password (using password1)
password=$(echo "$token_output" | jq -r '.credentials.passwords[] | select(.name=="password1") | .value')

# Check if password was extracted successfully
if [ -z "$password" ] || [ "$password" = "null" ]; then
    echo "Error: Failed to extract password from token output"
    exit 1
fi

# Create the cm-images.json file
cat > cm-images.json << EOF
{
  "auths": {
    "${registry}.azurecr.io": {
      "username": "$token_name",
      "password": "$password"
    }
  }
}
EOF

echo "Successfully created cm-images.json"
echo "Username: $token_name"
echo "Password: $password"
echo ""
echo "You can now use this file for Docker authentication:"
echo "docker login ${registry}.azurecr.io -u $token_name -p $password"