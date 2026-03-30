Write-Host '🚀 Starting KubeNexus Automated Bootstrap...' -ForegroundColor Cyan

# Check Docker Engine
Write-Host 'Checking Docker Engine...' -ForegroundColor Yellow
& docker info > $null 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host 'Docker is not running. Starting Docker Desktop...' -ForegroundColor Yellow
    $dockerPath = "C:\Program Files\Docker\Docker\Docker Desktop.exe"
    if (Test-Path $dockerPath) {
        Start-Process $dockerPath
        Write-Host 'Waiting for Docker to initialize (this may take a minute)...' -ForegroundColor Yellow
        while ($true) {
            & docker info > $null 2>&1
            if ($LASTEXITCODE -eq 0) { break }
            Start-Sleep -Seconds 2
        }
        Write-Host 'Docker is ready!' -ForegroundColor Green
    } else {
        Write-Host 'ERROR: Docker Desktop not found at default path. Please start Docker manually.' -ForegroundColor Red
        exit 1
    }
}

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
kubectl rollout status deployment/monitoring-grafana -n monitoring --timeout=150s 2>$null | Out-Null
kubectl rollout status deployment/kubenexus-frontend -n kubenexus --timeout=120s
kubectl rollout status deployment/kubenexus-backend -n kubenexus --timeout=120s

Write-Host 'Binding Front-End & Dashboard to Localhost...' -ForegroundColor Yellow
Stop-Process -Name 'kubectl' -ErrorAction SilentlyContinue 
Start-Process powershell -WindowStyle Hidden -ArgumentList '-Command kubectl --namespace monitoring port-forward svc/monitoring-grafana 3000:80'
Start-Process powershell -WindowStyle Hidden -ArgumentList '-Command kubectl --namespace kubenexus port-forward svc/kubenexus-frontend-service 8080:80'

$frontendUrl = "http://localhost:8080"

Write-Host ""
Write-Host @"
██╗  ██╗██╗   ██╗██████╗ ███████╗███╗   ██╗███████╗██╗  ██╗██╗   ██╗███████╗
██║ ██╔╝██║   ██║██╔══██╗██╔════╝████╗  ██║██╔════╝╚██╗██╔╝██║   ██║██╔════╝
█████╔╝ ██║   ██║██████╔╝█████╗  ██╔██╗ ██║█████╗   ╚███╔╝ ██║   ██║███████╗
██╔═██╗ ██║   ██║██╔══██╗██╔══╝  ██║╚██╗██║██╔══╝   ██╔██╗ ██║   ██║╚════██║
██║  ██╗╚██████╔╝██████╔╝███████╗██║ ╚████║███████╗██╔╝ ██╗╚██████╔╝███████║
╚═╝  ╚═╝ ╚═════╝ ╚═════╝ ╚══════╝╚═╝  ╚═══╝╚══════╝╚═╝  ╚═╝ ╚═════╝ ╚══════╝
"@ -ForegroundColor Green
Write-Host "                     ✨ IS NOW LIVE ✨" -ForegroundColor Green
Write-Host "=======================================================" -ForegroundColor Green 
Write-Host "🗣️ Frontend Web Interface  : $frontendUrl" -ForegroundColor Cyan
Write-Host '📊 Grafana Dashboard       : http://localhost:3000' -ForegroundColor Cyan
Write-Host '   (Login credentials      : admin / prom-operator)' -ForegroundColor DarkGray
Write-Host '======================================================='
Write-Host ''

Write-Host 'Opening Grafana Dashboard...' -ForegroundColor Yellow
Start-Process 'http://localhost:3000'
Write-Host 'Opening KubeNexus Frontend...' -ForegroundColor Yellow
Start-Process $frontendUrl
