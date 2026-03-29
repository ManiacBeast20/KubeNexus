Write-Host '🚀 Starting KubeNexus Automated Bootstrap...' -ForegroundColor Cyan

$minikubeStatus = minikube status --format '{{.Host}}'
if ($minikubeStatus -ne 'Running') {
    Write-Host 'Starting Minikube...' -ForegroundColor Yellow
    minikube start
}

Write-Host 'Ensuring metrics-server is active...' -ForegroundColor Yellow
minikube addons enable metrics-server | Out-Null

$monitoringExists = helm ls -n monitoring -q | Select-String 'monitoring'
if (-not $monitoringExists) {
    Write-Host 'Installing Prometheus & Grafana Analytics Stack (this may take a minute)...' -ForegroundColor Yellow
    helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
    helm repo update
    helm install monitoring prometheus-community/kube-prometheus-stack --namespace monitoring --create-namespace --wait
}

Write-Host 'Deploying KubeNexus Infrastructure...' -ForegroundColor Yellow
# Override any existing namespace ownership data that throws errors
kubectl label namespace kubenexus app.kubernetes.io/managed-by=Helm --overwrite 2>$null | Out-Null
kubectl annotate namespace kubenexus meta.helm.sh/release-name=kubenexus meta.helm.sh/release-namespace=kubenexus --overwrite 2>$null | Out-Null
helm upgrade --install kubenexus helm/kubenexus -n kubenexus --create-namespace

Write-Host 'Waiting for core services to spin up...' -ForegroundColor Yellow
kubectl rollout status deployment/kubenexus-frontend -n kubenexus --timeout=120s
kubectl rollout status deployment/kubenexus-backend -n kubenexus --timeout=120s

Write-Host 'Binding Monitoring Dashboard to Localhost:3000...' -ForegroundColor Yellow
Stop-Process -Name 'kubectl' -ErrorAction SilentlyContinue 
Start-Process powershell -WindowStyle Hidden -ArgumentList '-Command kubectl --namespace monitoring port-forward svc/monitoring-grafana 3000:80'

# Fetch the active URL dynamically (avoids Minikube tunnel blocking on Windows)
$minikubeIp = (minikube ip).Trim()
$frontendPort = (kubectl get svc kubenexus-frontend-service -n kubenexus -o jsonpath='{.spec.ports[0].nodePort}').Trim()
$frontendUrl = "http://${minikubeIp}:${frontendPort}"

Write-Host ''
Write-Host '=======================================================' -ForegroundColor Green
Write-Host '✅ KUBENEXUS IS FULLY OPERATIONAL' -ForegroundColor Green
Write-Host '=======================================================' 
Write-Host "🗣️ Frontend Web Interface  : $frontendUrl" -ForegroundColor Cyan
Write-Host '📊 Grafana Dashboard       : http://localhost:3000' -ForegroundColor Cyan
Write-Host '   (Login credentials      : admin / prom-operator)' -ForegroundColor DarkGray
Write-Host '======================================================='
Write-Host ''

Write-Host 'Opening Grafana Dashboard...' -ForegroundColor Yellow
Start-Process 'http://localhost:3000'
Write-Host 'Opening KubeNexus Frontend...' -ForegroundColor Yellow
Start-Process $frontendUrl
