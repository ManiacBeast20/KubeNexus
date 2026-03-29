#!/bin/bash
echo -e "\e[36m🚀 Starting KubeNexus Automated Bootstrap...\e[0m"

if ! minikube status | grep -q 'Running'; then
    echo -e "\e[33mStarting Minikube...\e[0m"
    minikube start
fi

echo -e "\e[33mEnsuring metrics-server is active...\e[0m"
minikube addons enable metrics-server >/dev/null 2>&1

if ! helm ls -n monitoring -q | grep -q '^monitoring$'; then
    echo -e "\e[33mInstalling Prometheus & Grafana Analytics Stack (this may take a minute)...\e[0m"
    helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
    helm repo update
    helm install monitoring prometheus-community/kube-prometheus-stack --namespace monitoring --create-namespace --wait
fi

echo -e "\e[33mDeploying KubeNexus Infrastructure...\e[0m"
kubectl label namespace kubenexus app.kubernetes.io/managed-by=Helm --overwrite 2>/dev/null
kubectl annotate namespace kubenexus meta.helm.sh/release-name=kubenexus meta.helm.sh/release-namespace=kubenexus --overwrite 2>/dev/null
helm upgrade --install kubenexus helm/kubenexus -n kubenexus --create-namespace

echo -e "\e[33mWaiting for core services to spin up...\e[0m"
kubectl rollout status deployment/monitoring-grafana -n monitoring --timeout=150s 2>/dev/null
kubectl rollout status deployment/kubenexus-frontend -n kubenexus --timeout=120s
kubectl rollout status deployment/kubenexus-backend -n kubenexus --timeout=120s

echo -e "\e[33mBinding Front-End & Dashboard to Localhost...\e[0m"
pkill -f "kubectl --namespace monitoring port-forward svc/monitoring-grafana 3000:80" || true
pkill -f "kubectl --namespace kubenexus port-forward svc/kubenexus-frontend-service 8080:80" || true

nohup kubectl --namespace monitoring port-forward svc/monitoring-grafana 3000:80 >/dev/null 2>&1 &
nohup kubectl --namespace kubenexus port-forward svc/kubenexus-frontend-service 8080:80 >/dev/null 2>&1 &

sleep 3

FRONTEND_URL="http://localhost:8080"

echo ""
echo -e "\e[32m=======================================================\e[0m"
echo -e "\e[32m✅ KUBENEXUS IS FULLY OPERATIONAL\e[0m"
echo -e "\e[32m=======================================================\e[0m"
echo -e "\e[36m🗣️ Frontend Web Interface  : $FRONTEND_URL\e[0m"
echo -e "\e[36m📊 Grafana Dashboard       : http://localhost:3000\e[0m"
echo -e "\e[90m   (Login credentials      : admin / prom-operator)\e[0m"
echo "======================================================="
echo ""

echo -e "\e[33mOpening Dashboards...\e[0m"
xdg-open "http://localhost:3000" 2>/dev/null || open "http://localhost:3000" 2>/dev/null || true
xdg-open "$FRONTEND_URL" 2>/dev/null || open "$FRONTEND_URL" 2>/dev/null || true
