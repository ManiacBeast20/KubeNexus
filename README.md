<div align="center">

<pre>
██╗  ██╗██╗   ██╗██████╗ ███████╗███╗   ██╗███████╗██╗  ██╗██╗   ██╗███████╗
██║ ██╔╝██║   ██║██╔══██╗██╔════╝████╗  ██║██╔════╝╚██╗██╔╝██║   ██║██╔════╝
█████╔╝ ██║   ██║██████╔╝█████╗  ██╔██╗ ██║█████╗   ╚███╔╝ ██║   ██║███████╗
██╔═██╗ ██║   ██║██╔══██╗██╔══╝  ██║╚██╗██║██╔══╝   ██╔██╗ ██║   ██║╚════██║
██║  ██╗╚██████╔╝██████╔╝███████╗██║ ╚████║███████╗██╔╝ ██╗╚██████╔╝███████║
╚═╝  ╚═╝ ╚═════╝ ╚═════╝ ╚══════╝╚═╝  ╚═══╝╚══════╝╚═╝  ╚═╝ ╚═════╝ ╚══════╝
</pre>

**Voice & Text Driven Natural Language Kubernetes Automation**

*Talk to your Kubernetes cluster in plain English or voice — KubeNexus handles the rest.*

[![Docker](https://img.shields.io/badge/Docker-mohammedomar02-blue?logo=docker)](https://hub.docker.com/u/mohammedomar02)
[![Kubernetes](https://img.shields.io/badge/Kubernetes-Minikube-326CE5?logo=kubernetes)](https://minikube.sigs.k8s.io/)
[![Python](https://img.shields.io/badge/Python-3.13-3776AB?logo=python)](https://python.org)
[![Helm](https://img.shields.io/badge/Helm-v4.1.3-0F1689?logo=helm)](https://helm.sh)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)

</div>

---

## 🎯 What Is KubeNexus?

KubeNexus is an AI-powered platform that runs **inside** your Kubernetes cluster and lets you deploy and manage resources using plain English or voice commands — no YAML, no kubectl knowledge required.

It goes beyond simple deployment by automatically detecting and fixing errors using an AI self-healing loop powered by a local LLM (Ollama).

---

## ✨ Key Features

- 🗣️ **Natural Language & Voice** — describe deployments in plain English or speak them out loud
- 🤖 **AI Self Healing** — detects ImagePullBackOff, typos, and errors and fixes them automatically
- 🗄️ **Multi-service Support** — deploy apps with PostgreSQL, MySQL, Redis databases and HPA
- 🔔 **Real-Time Alerts** — native Discord webhooks & SMTP email notifications for deployments and AI fixes
- 🔒 **Security First** — RBAC, Secrets, ConfigMaps, Trivy image scanning
- 📊 **Live Monitoring** — Prometheus metrics + Grafana dashboards
- 📦 **One Command Install** — fully packaged as a Helm chart
- 🏠 **Fully Local** — runs entirely on your machine, no cloud or API keys required

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        Your Browser                         │
│                    (Voice / Text Input)                     │
└─────────────────────────┬───────────────────────────────────┘
                          │ HTTP
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                    Minikube Cluster                         │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐   │
│  │                 kubenexus namespace                  │   │
│  │                                                      │   │ 
│  │   ┌──────────────────┐    ┌───────────────────────┐  │   │
│  │   │  Frontend Pod    │    │    Backend Pod        │  │   │
│  │   │  (nginx)         │───►│    (FastAPI)          │  │   │
│  │   │                  │    │                       │  │   │
│  │   │  - Serves UI     │    │  - Intent extraction  │  │   │
│  │   │  - Voice input   │    │  - YAML generation    │  │   │
│  │   │  - Status display│    │  - K8s API calls      │  │   │
│  │   └──────────────────┘    │  - AI self healing    │  │   │
│  │                           │  - Metrics /metrics   │  │   │
│  │                           └──────────┬────────────┘  │   │
│  │                                      │               │   │
│  │          ┌───────────────────────────┤               │   │
│  │          │                           │               │   │
│  │          ▼                           ▼               │   │
│  │   ┌─────────────┐         ┌─────────────────────┐    │   │
│  │   │ Ollama LLM  │         │   Kubernetes API    │    │   │
│  │   │(host machine│         │                     │    │   │
│  │   │ gemma3:1b)  │         │  Creates/manages:   │    │   │
│  │   │             │         │  - Deployments      │    │   │
│  │   │ - Extract   │         │  - Services         │    │   │
│  │   │   intent    │         │  - Secrets          │    │   │
│  │   │ - Analyze   │         │  - ConfigMaps       │    │   │
│  │   │   errors    │         │  - HPAs             │    │   │
│  │   └─────────────┘         └─────────────────────┘    │   │
│  │                                                      │   │
│  │   ┌──────────────┐    ┌────────────────────────┐     │   │
│  │   │  Prometheus  │    │        Grafana         │     │   │
│  │   │              │───►│                        │     │   │
│  │   │  Scrapes:    │    │  - Deployment metrics  │     │   │
│  │   │  - /metrics  │    │  - Self heal events    │     │   │
│  │   │  - K8s state │    │  - Cluster health      │     │   │
│  │   └──────────────┘    └────────────────────────┘     │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

---

## 🤖 AI Self Healing Flow

```
You say: "Deploy ngix with 3 replicas"  ← typo!
                    │
                    ▼
         KubeNexus deploys with
         image: ngix:latest
                    │
                    ▼
         Pod fails: ImagePullBackOff
                    │
                    ▼
         AI Watcher detects error
                    │
                    ▼
         AI identifies typo:
         ngix → nginx:latest
                    │
                    ▼
         Auto patches deployment
                    │
                    ▼
         ✅ All pods running
         No human intervention needed
```

---

## 🛠️ Tech Stack

| Component | Technology | Purpose |
|-----------|------------|---------|
| Kubernetes | Minikube | Local cluster |
| Packaging | Helm v4 | One-command install |
| Frontend | HTML + JS + Web Speech API | UI + Voice input |
| Backend | Python FastAPI | Core logic |
| LLM | Ollama (gemma3:1b) | Intent extraction + error analysis |
| Monitoring | Prometheus + Grafana | Metrics + dashboards |
| Alerts | Discord Webhook + SMTP | Real-time notifications |
| CI/CD | GitHub Actions | Automated build + scan |
| Image Scanning | Trivy | Security gate |
| Access Control | RBAC + ServiceAccount | Least privilege |
| Config | ConfigMaps | Externalized config |
| Secrets | K8s Secrets | Secure credentials |
| Auto Scaling | HPA | Scale on demand |

---

## 📋 Prerequisites

- [Minikube](https://minikube.sigs.k8s.io/docs/start/)
- [Helm](https://helm.sh/docs/intro/install/)
- [kubectl](https://kubernetes.io/docs/tasks/tools/)
- [Ollama](https://ollama.com/) with `gemma3:1b` model
- [Docker](https://www.docker.com/)

---

## 🚀 Quick Start

**Method 1: Windows 1-Click Automation**
The easiest way to spin up the entire infrastructure (Minikube, Helm, Prometheus, Grafana, and KubeNexus) is by running the orchestrator script:
```powershell
.\start.ps1
```
The script will automate the setup, bind the Grafana dashboard via ConfigMap, print your active frontend URL to the terminal, and open your browser automatically.

**Method 2: Manual Installation Steps**

**Step 1 — Install Ollama and pull the model:**
```bash
ollama pull gemma3:1b
```

**Step 2 — Clone the repo:**
```bash
git clone https://github.com/ManiacBeast20/KubeNexus.git
cd KubeNexus
```

**Step 3 — Start Minikube:**
```bash
minikube start
```

**Step 4 — Install KubeNexus:**
```bash
helm install kubenexus helm/kubenexus
```

**Step 5 — Access the UI:**
```bash
minikube service kubenexus-frontend-service -n kubenexus --url
```

Open the URL in Chrome or Edge and start deploying!

---

## 💬 Example Requests

```
"Deploy nginx with 3 replicas"

"Deploy my app using nginx with a PostgreSQL database 
 and autoscale at 70% CPU"

"Deploy myapp using mohammedomar02/myapp:latest 
 with Redis cache and 2 replicas"

"Deploy WordPress with a MySQL database"

"Deploy ngix with 3 replicas"  ← AI will auto-fix the typo!
```

---

## 📈 Testing Auto-Scaling (HPA)

KubeNexus relies on the Kubernetes Metrics Server to drive its HorizontalPodAutoscaler.

**Step 1 — Enable Metrics Server:**
```bash
minikube addons enable metrics-server
```

**Step 2 — Generate Load:**
Run a busybox pod in a loop to artificially spike CPU pressure on the backend service:
```bash
kubectl run -i --tty load-generator --rm --image=busybox:1.28 --restart=Never -- /bin/sh -c "while sleep 0.01; do wget -q -O- http://kubenexus-backend-service:8000/health; done"
```

**Step 3 — Watch it Scale:**
Open another terminal pane and watch the HPA spin up from 1 to 5 pods:
```bash
kubectl get hpa -n kubenexus -w
```

---

## 📊 Monitoring Setup

> **Note:** If you used the `.\start.ps1` script to install, this setup is already completed for you and the custom KubeNexus Grafana Dashboard is hot-loaded automatically!

```bash
# Add Prometheus repo
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update

# Install Prometheus + Grafana stack
helm install monitoring prometheus-community/kube-prometheus-stack \
  --namespace monitoring --create-namespace

# Access Grafana
kubectl --namespace monitoring port-forward svc/monitoring-grafana 3000:80
```

Open `http://localhost:3000` — login with username `admin`.

**Custom KubeNexus metrics available in Grafana:**
- `kubenexus_deployments_total` — total deployment requests
- `kubenexus_deployments_success` — successful deployments
- `kubenexus_self_heals_total` — AI self healing events
- `kubenexus_ollama_latency_seconds` — LLM response time

---

## 🗂️ Project Structure

```
KubeNexus/
├── backend/
│   ├── main.py              # FastAPI backend + AI logic
│   ├── requirements.txt     # Python dependencies
│   └── Dockerfile           # Backend container
├── frontend/
│   ├── index.html           # UI with voice recognition
│   ├── nginx.conf           # nginx reverse proxy config
│   ├── logo.png             # KubeNexus logo
│   └── Dockerfile           # Frontend container
├── helm/
│   └── kubenexus/
│       ├── Chart.yaml       # Helm chart metadata
│       ├── values.yaml      # Configurable values
│       └── templates/
│           ├── namespace.yaml
│           ├── configmap.yaml
│           ├── secret.yaml
│           ├── serviceaccount.yaml
│           ├── rbac.yaml
│           ├── backend-deployment.yaml
│           ├── backend-service.yaml
│           ├── frontend-deployment.yaml
│           ├── frontend-service.yaml
│           └── hpa.yaml
└── .github/
    └── workflows/
        └── ci.yaml          # CI/CD pipeline
```

---

## 🔒 Security Design

```
┌─────────────────────────────────────────────┐
│              Security Layers                │
│                                             │
│  CI/CD Pipeline                             │
│  └── Trivy scans images before push         │
│      Blocks critical CVEs automatically     │
│                                             │
│  Kubernetes RBAC                            │
│  └── ServiceAccount: kubenexus-sa           │
│      ClusterRole: least privilege           │
│      Only what backend needs — nothing more │
│                                             │
│  Secrets Management                         │
│  └── All credentials in K8s Secrets         │
│      Never hardcoded in code                │
│                                             │
│  ConfigMaps                                 │
│  └── All config externalized                │
│      Change without rebuilding image        │
│                                             │
│  Resource Limits                            │
│  └── CPU + memory limits on all pods        │
│      Prevents resource abuse                │
└─────────────────────────────────────────────┘
```

---

## 📦 Docker Images

| Image | Docker Hub |
|-------|-----------|
| Backend | `mohammedomar02/kubenexus-backend:latest` |
| Frontend | `mohammedomar02/kubenexus-frontend:latest` |

---

## 🔧 Configuration

All configuration is managed via `helm/kubenexus/values.yaml`:

```yaml
namespace: kubenexus

backend:
  image: mohammedomar02/kubenexus-backend
  tag: latest
  replicas: 1
  port: 8000

frontend:
  image: mohammedomar02/kubenexus-frontend
  tag: latest
  replicas: 1
  port: 80
  nodePort: 30080

ollama:
  host: http://host.minikube.internal:11434
  model: gemma3:1b

alerts:
  discordWebhookUrl: "https://discord.com/api/webhooks/YOUR_WEBHOOK_URL"
  mailUsername: "youremail@gmail.com"
  mailPassword: "your-app-password"
```

---

## 🏗️ Build Stages

| Stage | Description | Status |
|-------|-------------|--------|
| 1 | Project structure + GitHub repo | ✅ Done |
| 2 | Backend FastAPI + Ollama integration | ✅ Done |
| 3 | Kubernetes API integration | ✅ Done |
| 4 | Frontend + Voice recognition | ✅ Done |
| 5 | AI self healing loop | ✅ Done |
| 6 | Dockerized + pushed to Docker Hub | ✅ Done |
| 7 | Helm chart | ✅ Done |
| 8 | RBAC + ConfigMaps + Secrets | ✅ Done |
| 9 | Prometheus + Grafana | ✅ Done |
| 10 | HPA testing | ✅ Done |
| 11 | CI/CD + Trivy | ✅ Done |
| 12 | 1-Click Automation Scripts | ✅ Done |

---

## 🌍 Real World Use Cases

**Developer Self Service**
Developers deploy their own services without writing YAML or waiting for DevOps team approval. Reduces deployment time from days to seconds.

**Managed Hosting Business**
A company providing hosting services can deploy customer applications instantly using natural language — one sentence per customer onboarding.

**On-Call Incident Response**
Instead of waking up engineers at 3am, KubeNexus detects pod failures, analyzes root cause using AI, and auto-fixes common issues — mean time to resolution drops from 45 minutes to seconds.

**Junior Engineer Onboarding**
New engineers deploy production-grade Kubernetes workloads correctly from day one without needing to know YAML syntax.

---

## 👤 Author

**Mohammed Omar (Moe)**
[@ManiacBeast20](https://github.com/ManiacBeast20)


---

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.
