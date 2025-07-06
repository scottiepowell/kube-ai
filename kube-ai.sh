#!/usr/bin/env bash
set -euo pipefail

CLUSTER_NAME=ai
REGISTRY_NAME=registry.localhost
REGISTRY_PORT=5000

install_kubectl() {
  if ! command -v kubectl &>/dev/null; then
    echo "[INFO] kubectl not found. Installing..."
    curl -LO "https://dl.k8s.io/release/$(curl -sL https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
    chmod +x kubectl
    sudo mv kubectl /usr/local/bin/
    echo "[INFO] kubectl installed."
  else
    echo "[INFO] kubectl already installed."
  fi
}

create_k3d_registry() {
  # 1) Remove any plain Docker container listening on that port
  conflict=$(docker ps --filter "publish=${REGISTRY_PORT}" --format '{{.Names}}' | head -n1 || true)
  if [ -n "$conflict" ]; then
    echo "[INFO] Removing raw Docker registry '$conflict' on port ${REGISTRY_PORT}..."
    docker rm -f "$conflict"
  fi

  # 2) If k3d-managed registry exists, skip
  if k3d registry list | awk '{print $1}' | grep -xq "${REGISTRY_NAME}"; then
    echo "[INFO] k3d registry '${REGISTRY_NAME}' already exists."
  else
    echo "[INFO] Creating k3d-managed registry '${REGISTRY_NAME}' on port ${REGISTRY_PORT}..."
    k3d registry create "${REGISTRY_NAME}" --port "${REGISTRY_PORT}"
  fi
}

install_kubectl
create_k3d_registry

if k3d cluster list | grep -q "^${CLUSTER_NAME}[[:space:]]"; then
  echo "[INFO] Cluster '${CLUSTER_NAME}' already exists; skipping creation."
else
  echo "[INFO] Creating k3d cluster '${CLUSTER_NAME}'..."
  k3d cluster create "${CLUSTER_NAME}" \
    --agents 2 \
    --port "80:80@loadbalancer" \
    --registry-use "${REGISTRY_NAME}:${REGISTRY_PORT}"
fi

echo "[INFO] Waiting for nodes Ready..."
kubectl wait --for=condition=Ready nodes --all --timeout=120s

echo "[INFO] Applying manifests..."
kubectl apply -f autogen-k8s.yaml
kubectl apply -f autogen-ingress.yaml

cat <<EOF

✅ Done! Next steps on rebuild:

  docker build -t ${REGISTRY_NAME}:${REGISTRY_PORT}/ai/autogen:0.4 .
  docker push ${REGISTRY_NAME}:${REGISTRY_PORT}/ai/autogen:0.4
  kubectl rollout restart deployment/autogen -n ai

EOF