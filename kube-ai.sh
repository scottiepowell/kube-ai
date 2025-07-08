#!/usr/bin/env bash
set -euo pipefail

CLUSTER_NAME=ai
REGISTRY_NAME=registry.localhost
REGISTRY_PORT=5000

# ────────────────────────────────────────────────────────────────────────────
install_kubectl() {
  if ! command -v kubectl &>/dev/null; then
    echo "[INFO] Installing kubectl…"
    curl -Lo kubectl "https://dl.k8s.io/release/$(curl -sL https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
    chmod +x kubectl
    sudo mv kubectl /usr/local/bin/
  else
    echo "[INFO] kubectl already installed."
  fi
}

create_k3d_registry() {
  # 1) Tear down any “raw” registry on that port so k3d can win
  if conflict=$(docker ps --filter "publish=${REGISTRY_PORT}" --format '{{.Names}}' | head -n1); then
    [[ -n $conflict ]] && {
      echo "[INFO] Removing raw Docker registry '$conflict'…"
      docker rm -f "$conflict"
    }
  fi

  # 2) Create (or reuse) a k3d-managed registry
  if k3d registry list | awk '{print $1}' | grep -qx "${REGISTRY_NAME}"; then
    echo "[INFO] k3d registry '${REGISTRY_NAME}' already exists."
  else
    echo "[INFO] Creating k3d-managed registry '${REGISTRY_NAME}' on port ${REGISTRY_PORT}…"
    k3d registry create "${REGISTRY_NAME}" --port "${REGISTRY_PORT}"
  fi
}

create_k3d_cluster() {
  if k3d cluster list | grep -q "^${CLUSTER_NAME}[[:space:]]"; then
    echo "[INFO] Cluster '${CLUSTER_NAME}' exists; skipping creation."
  else
    echo "[INFO] Creating k3d cluster '${CLUSTER_NAME}'…"
    k3d cluster create "${CLUSTER_NAME}" \
      --agents 2 \
      --port "80:80@loadbalancer" \
      --registry-use "${REGISTRY_NAME}:${REGISTRY_PORT}"
  fi
}

deploy_manifests() {
  echo "[INFO] Waiting for all nodes to be Ready…"
  kubectl wait nodes --all --for=condition=Ready --timeout=120s

  echo "[INFO] Applying Kubernetes manifests…"
  kubectl apply -f autogen-k8s.yaml
  kubectl apply -f autogen-ingress.yaml
}

run_skaffold() {
  PROFILE=${1:-dev}
  echo "[INFO] 🚀 Launching Skaffold dev (profile=$PROFILE)…"
  skaffold dev \
    --profile="$PROFILE" \
    --cleanup=false \    # leave namespace & pods intact on failure
    --no-prune \         # keep all your pushed images
    -v trace             # maximum verbosity
}

# ────────────────────────────────────────────────────────────────────────────
# If the first argument is "skaffold", do cluster+registry setup once, then
# drop into Skaffold’s dev loop; otherwise run the normal deploy flow.
if [[ "${1-}" == "skaffold" ]]; then
  install_kubectl
  create_k3d_registry
  create_k3d_cluster
  run_skaffold "${2-}"
  exit 0
fi

# ────────────────────────────────────────────────────────────────────────────
# Normal one-off flow:
install_kubectl
create_k3d_registry
create_k3d_cluster
deploy_manifests

cat <<EOF

✅ Cluster & registry are ready!

Next steps to rebuild & push your image:

  docker build -t ${REGISTRY_NAME}:${REGISTRY_PORT}/ai/autogen:0.4 .
  docker push ${REGISTRY_NAME}:${REGISTRY_PORT}/ai/autogen:0.4
  kubectl rollout restart deployment/autogen -n ai

Or jump into a Skaffold dev loop for iterative development:

  ./kube-ai.sh skaffold   # defaults to profile 'dev'

EOF