Write-Host "🚀 Starting KubeNexus Automated Bootstrap..." -ForegroundColor Cyan

# Check Minikube
$minikubeStatus = minikube status --format "{{.Host}}"
if ($minikubeStatus -ne "Running") {
    Write-Host "Starting Minikube..." -ForegroundColor Yellow
    minikube start
}

# Enable metrics-server for HPA
Write-Host "Ensuring metrics-server is active..." -ForegroundColor Yellow
minikube addons enable metrics-server | Out-Null

# Install Prometheus Stack if missing
$monitoringExists = helm ls -n monitoring -q | Select-String "monitoring"
if (-not $monitoringExists) {
    Write-Host "Installing Prometheus & Grafana Analytics Stack (this may take a minute)..." -ForegroundColor Yellow
    helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
    helm repo update
    helm install monitoring prometheus-community/kube-prometheus-stack --namespace monitoring --create-namespace --wait
}

# Install KubeNexus (this automatically creates the Grafana Dashboard ConfigMap too!)
Write-Host "Deploying KubeNexus Infrastructure..." -ForegroundColor Yellow
helm upgrade --install kubenexus helm/kubenexus -n kubenexus --create-namespace

# Wait for Frontend and Backend to be ready
Write-Host "Waiting for core services to spin up..." -ForegroundColor Yellow
kubectl rollout status deployment/kubenexus-frontend -n kubenexus --timeout=120s
kubectl rollout status deployment/kubenexus-backend -n kubenexus --timeout=120s

# Setup background port-forwarding for Grafana
Write-Host "Binding Monitoring Dashboard to Localhost:3000..." -ForegroundColor Yellow
# Stop any lingering kubectl port-forwards to avoid conflict
Stop-Process -Name "kubectl" -ErrorAction SilentlyContinue 
Start-Process powershell -WindowStyle Hidden -ArgumentList "-Command kubectl --namespace monitoring port-forward svc/monitoring-grafana 3000:80"

Start-Sleep -Seconds 3

# Fetch the active URL from Minikube
$frontendUrl = minikube service kubenexus-frontend-service -n kubenexus --url

Write-Host "`n=======================================================" -ForegroundColor Green
Write-Host "✅ KUBENEXUS IS FULLY OPERATIONAL" -ForegroundColor Green
Write-Host "=======================================================" 
Write-Host "🗣️ Frontend Web Interface  : $frontendUrl" -ForegroundColor Cyan
Write-Host "📊 Grafana Dashboard        : http://localhost:3000" -ForegroundColor Cyan
Write-Host "   (Login credentials       : admin / prom-operator)" -ForegroundColor DarkGray
Write-Host "=======================================================`n"

Write-Host "Opening Grafana Dashboard..." -ForegroundColor Yellow
Start-Process "http://localhost:3000"
Write-Host "Opening KubeNexus Frontend..." -ForegroundColor Yellow
Start-Process $frontendUrl
