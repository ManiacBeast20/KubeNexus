from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from prometheus_fastapi_instrumentator import Instrumentator
from prometheus_client import Counter, Histogram
import requests
import os
import json
import base64
import time
import threading
import smtplib
import traceback
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from kubernetes import client, config

app = FastAPI()

# ── Metrics ────────────────────────────────────────────
DEPLOYMENTS_TOTAL  = Counter('kubenexus_deployments_total',  'Total deployments')
DEPLOYMENTS_SUCCESS = Counter('kubenexus_deployments_success', 'Successful deployments')
SELF_HEALS_TOTAL   = Counter('kubenexus_self_heals_total',   'AI self-heals')
OLLAMA_LATENCY     = Histogram('kubenexus_ollama_latency_seconds', 'AI latency')

Instrumentator().instrument(app).expose(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Config ─────────────────────────────────────────────
OLLAMA_HOST      = os.getenv("OLLAMA_HOST",       "http://host.minikube.internal:11434")
OLLAMA_MODEL     = os.getenv("OLLAMA_MODEL",       "gemma3:1b")
DISCORD_WEBHOOK  = os.getenv("DISCORD_WEBHOOK_URL", "")
MAIL_USER        = os.getenv("MAIL_USERNAME",       "")
MAIL_PASS        = os.getenv("MAIL_PASSWORD",       "")

# ── Global error handler ────────────────────────────────
@app.exception_handler(Exception)
async def global_handler(request: Request, exc: Exception):
    traceback.print_exc()
    return JSONResponse(status_code=500, content={"error": str(exc)})

# ── Alerts ─────────────────────────────────────────────
def send_discord(title, body):
    if not DISCORD_WEBHOOK:
        return
    try:
        requests.post(DISCORD_WEBHOOK, json={"content": f"**{title}**\n{body}"}, timeout=5)
    except Exception as e:
        print(f"Discord error: {e}")

def send_email(subject, body):
    if not MAIL_USER or not MAIL_PASS:
        return
    try:
        msg = MIMEMultipart()
        msg['From']    = "KubeNexus AI"
        msg['To']      = MAIL_USER
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
            s.login(MAIL_USER, MAIL_PASS)
            s.send_message(msg)
    except Exception as e:
        print(f"Email error: {e}")

# ── Kubernetes ─────────────────────────────────────────
try:
    config.load_incluster_config()
except Exception:
    config.load_kube_config()

# ── AI helper ──────────────────────────────────────────
def call_ollama(system_prompt: str, user_prompt: str, timeout: float = 60.0):
    """Call Ollama and return parsed JSON. Returns None on any failure."""
    try:
        t0 = time.time()
        resp = requests.post(
            f"{OLLAMA_HOST}/api/generate",
            json={"model": OLLAMA_MODEL, "system": system_prompt, "prompt": user_prompt, "stream": False},
            timeout=timeout,
        )
        OLLAMA_LATENCY.observe(time.time() - t0)
        raw = resp.json().get("response", "").strip()
        # Strip markdown code fences if present
        if "```json" in raw:
            raw = raw.split("```json")[1].split("```")[0].strip()
        elif "```" in raw:
            raw = raw.split("```")[1].split("```")[0].strip()
        return json.loads(raw)
    except Exception as e:
        print(f"Ollama error: {e}")
        return None

# ── Image typo correction ─────────────────────────────
IMAGE_FIXES = {

    # ── nginx ────────────────────────────────────────────
    "ngix":       "nginx:latest",  "ngnix":      "nginx:latest",
    "niginx":     "nginx:latest",  "nginix":     "nginx:latest",
    "nignx":      "nginx:latest",  "nxig":       "nginx:latest",
    "nignix":     "nginx:latest",  "nginxx":     "nginx:latest",
    "enginx":     "nginx:latest",  "ngnx":       "nginx:latest",
    "ngixn":      "nginx:latest",  "nxginx":     "nginx:latest",
    "ngigx":      "nginx:latest",

    # ── postgres ─────────────────────────────────────────
    "postgress":  "postgres:latest",  "postgresl":  "postgres:latest",
    "posgres":    "postgres:latest",  "posgtres":   "postgres:latest",
    "posgress":   "postgres:latest",  "postgre":    "postgres:latest",
    "postgrse":   "postgres:latest",  "postgers":   "postgres:latest",
    "potgres":    "postgres:latest",  "postgresq":  "postgres:latest",
    "postres":    "postgres:latest",  "psotgres":   "postgres:latest",
    "psql":       "postgres:latest",  "postgresdb": "postgres:latest",
    "pgsql":      "postgres:latest",  "psotgress":  "postgres:latest",

    # ── redis ─────────────────────────────────────────────
    "reddis":     "redis:latest",  "rediss":     "redis:latest",
    "rdeis":      "redis:latest",  "reddiss":    "redis:latest",
    "reids":      "redis:latest",  "redsi":      "redis:latest",
    "rdis":       "redis:latest",  "reds":       "redis:latest",
    "redies":     "redis:latest",  "riddis":     "redis:latest",

    # ── mysql ─────────────────────────────────────────────
    "msql":       "mysql:latest",  "mysqll":     "mysql:latest",
    "myslq":      "mysql:latest",  "mysqk":      "mysql:latest",
    "myssql":     "mysql:latest",  "mysq":       "mysql:latest",
    "mssql":      "mysql:latest",  "myqsl":      "mysql:latest",
    "mysqldb":    "mysql:latest",  "musql":      "mysql:latest",

    # ── mongo / mongodb ───────────────────────────────────
    "monogo":     "mongo:latest",  "monggo":     "mongo:latest",
    "mangodb":    "mongo:latest",  "mongdb":     "mongo:latest",
    "mondgo":     "mongo:latest",  "mongodo":    "mongo:latest",
    "mango":      "mongo:latest",  "mongod":     "mongo:latest",
    "mongobd":    "mongo:latest",  "mogno":      "mongo:latest",
    "mongodb":    "mongo:latest",  "mognodb":    "mongo:latest",
    "monodb":     "mongo:latest",

    # ── apache (httpd) ────────────────────────────────────
    "apche":      "httpd:latest",  "appache":    "httpd:latest",
    "apachee":    "httpd:latest",  "apachi":     "httpd:latest",
    "apach":      "httpd:latest",  "apcahe":     "httpd:latest",
    "apache":     "httpd:latest",  "apachhe":    "httpd:latest",
    "apcahe":     "httpd:latest",  "appache":    "httpd:latest",

    # ── node / nodejs ─────────────────────────────────────
    "nodejs":     "node:latest",   "nodjs":      "node:latest",
    "nod":        "node:latest",   "nodee":      "node:latest",
    "ndoe":       "node:latest",   "nde":        "node:latest",
    "noode":      "node:latest",   "ndoe":       "node:latest",
    "noedjs":     "node:latest",   "ode":        "node:latest",

    # ── python ────────────────────────────────────────────
    "pythn":      "python:latest", "pyhton":     "python:latest",
    "pyton":      "python:latest", "pytho":      "python:latest",
    "pythong":    "python:latest", "pyython":    "python:latest",
    "pthon":      "python:latest", "ptyhon":     "python:latest",
    "pyhon":      "python:latest", "pythonn":    "python:latest",

    # ── ubuntu ────────────────────────────────────────────
    "ubunu":      "ubuntu:latest", "ubundu":     "ubuntu:latest",
    "ubunto":     "ubuntu:latest", "ubunut":     "ubuntu:latest",
    "ubutu":      "ubuntu:latest", "ubuntuu":    "ubuntu:latest",
    "ubunti":     "ubuntu:latest", "ubbutnu":    "ubuntu:latest",
    "ubuuntu":    "ubuntu:latest",

    # ── alpine ────────────────────────────────────────────
    "alpin":      "alpine:latest", "alpne":      "alpine:latest",
    "alpie":      "alpine:latest", "alpnie":     "alpine:latest",
    "alpien":     "alpine:latest", "alpinee":    "alpine:latest",
    "aline":      "alpine:latest", "apline":     "alpine:latest",

    # ── rabbitmq ─────────────────────────────────────────
    "rabitmq":    "rabbitmq:latest", "rabbtmq":  "rabbitmq:latest",
    "rabitqm":    "rabbitmq:latest", "rabbitqm": "rabbitmq:latest",
    "rabiitmq":   "rabbitmq:latest", "rabbitmg": "rabbitmq:latest",
    "rabbitmqu":  "rabbitmq:latest", "rabbit":   "rabbitmq:latest",
    "rabbitmqq":  "rabbitmq:latest", "raabbitmq":"rabbitmq:latest",

    # ── elasticsearch ─────────────────────────────────────
    "elasticsrach":   "elasticsearch:latest",
    "elasticserach":  "elasticsearch:latest",
    "elastisearch":   "elasticsearch:latest",
    "elasticearch":   "elasticsearch:latest",
    "elastcsearch":   "elasticsearch:latest",
    "elasicsearch":   "elasticsearch:latest",
    "elsaticsearch":  "elasticsearch:latest",
    "elastic":        "elasticsearch:latest",
    "elastisearh":    "elasticsearch:latest",

    # ── kafka ─────────────────────────────────────────────
    "kafak":      "bitnami/kafka:latest", "kafke":   "bitnami/kafka:latest",
    "kafkka":     "bitnami/kafka:latest", "kafqa":   "bitnami/kafka:latest",
    "kafkae":     "bitnami/kafka:latest", "kafkaa":  "bitnami/kafka:latest",
    "kakfa":      "bitnami/kafka:latest",

    # ── wordpress ─────────────────────────────────────────
    "wordpres":   "wordpress:latest", "wordperss":  "wordpress:latest",
    "wordprss":   "wordpress:latest", "wordpreess": "wordpress:latest",
    "worpdress":  "wordpress:latest", "wordpresss": "wordpress:latest",
    "wodrpress":  "wordpress:latest", "wrodpress":  "wordpress:latest",

    # ── jenkins ───────────────────────────────────────────
    "jenins":     "jenkins/jenkins:lts", "jenkis":    "jenkins/jenkins:lts",
    "jenkinss":   "jenkins/jenkins:lts", "jenkisn":   "jenkins/jenkins:lts",
    "jenikins":   "jenkins/jenkins:lts", "jenkin":    "jenkins/jenkins:lts",
    "jenkns":     "jenkins/jenkins:lts", "jnekins":   "jenkins/jenkins:lts",

    # ── grafana ───────────────────────────────────────────
    "grafanna":   "grafana/grafana:latest", "graffana": "grafana/grafana:latest",
    "grafna":     "grafana/grafana:latest", "grafan":   "grafana/grafana:latest",
    "garfana":    "grafana/grafana:latest", "grafanaa": "grafana/grafana:latest",
    "grfana":     "grafana/grafana:latest",

    # ── prometheus ────────────────────────────────────────
    "prometeus":  "prom/prometheus:latest", "promtheus":  "prom/prometheus:latest",
    "prometuhs":  "prom/prometheus:latest", "premetheus": "prom/prometheus:latest",
    "promethues": "prom/prometheus:latest", "pometheus":  "prom/prometheus:latest",
    "prometheuss":"prom/prometheus:latest",

    # ── memcached ─────────────────────────────────────────
    "memcache":   "memcached:latest", "memcahced":  "memcached:latest",
    "memcachedd": "memcached:latest", "memcahce":   "memcached:latest",
    "memached":   "memcached:latest", "memchaced":  "memcached:latest",

    # ── mariadb ───────────────────────────────────────────
    "maridb":     "mariadb:latest", "maradb":     "mariadb:latest",
    "maraidb":    "mariadb:latest", "mairdb":     "mariadb:latest",
    "mariaddb":   "mariadb:latest", "mariabd":    "mariadb:latest",
    "mairadb":    "mariadb:latest", "mariabdb":   "mariadb:latest",

    # ── tomcat ────────────────────────────────────────────
    "tmmcat":     "tomcat:latest", "tomccat":    "tomcat:latest",
    "tomact":     "tomcat:latest", "tomcatt":    "tomcat:latest",
    "tomcta":     "tomcat:latest", "tmcat":      "tomcat:latest",
    "ttomcat":    "tomcat:latest",

    # ── golang ────────────────────────────────────────────
    "goland":     "golang:latest", "golng":      "golang:latest",
    "glang":      "golang:latest", "golangn":    "golang:latest",
    "golan":      "golang:latest", "golag":      "golang:latest",
    "golangg":    "golang:latest",

    # ── haproxy ───────────────────────────────────────────
    "haproxuy":   "haproxy:latest", "haproxyy":  "haproxy:latest",
    "haproxxy":   "haproxy:latest", "haprox":    "haproxy:latest",
    "hapoxy":     "haproxy:latest", "harpoxy":   "haproxy:latest",

    # ── traefik ───────────────────────────────────────────
    "traeifk":    "traefik:latest", "traefki":   "traefik:latest",
    "traefix":    "traefik:latest", "trafik":    "traefik:latest",
    "traefkik":   "traefik:latest", "traefikk":  "traefik:latest",

    # ── zookeeper ─────────────────────────────────────────
    "zookeper":   "zookeeper:latest", "zookepeer": "zookeeper:latest",
    "zooekeper":  "zookeeper:latest", "zokeeeper": "zookeeper:latest",
    "zookeepr":   "zookeeper:latest",

    # ── cassandra ─────────────────────────────────────────
    "cassandara": "cassandra:latest", "casandra":  "cassandra:latest",
    "cassadnra":  "cassandra:latest", "cassandr":  "cassandra:latest",
    "casandara":  "cassandra:latest", "cassandrai":"cassandra:latest",
}


def fix_image(image: str) -> str:
    """Correct common image name typos. Always strip whitespace first."""
    image = image.strip()
    base  = image.split(":")[0].lower().strip()
    return IMAGE_FIXES.get(base, image)

def make_deployment(name, image, replicas=1, port=80):
    return {
        "apiVersion": "apps/v1", "kind": "Deployment",
        "metadata": {"name": name},
        "spec": {
            "replicas": replicas,
            "selector": {"matchLabels": {"app": name}},
            "template": {
                "metadata": {"labels": {"app": name}},
                "spec": {
                    "containers": [
                        {
                            "name": name,
                            "image": image,
                            "ports": [{"containerPort": port}],
                            "resources": {
                                "requests": {"cpu": "100m", "memory": "128Mi"},
                                "limits": {"cpu": "500m", "memory": "512Mi"}
                            }
                        }
                    ]
                }
            }
        }
    }

def make_service(name, port=80, svc_type="NodePort"):
    return {
        "apiVersion": "v1", "kind": "Service",
        "metadata": {"name": f"{name}-service"},
        "spec": {
            "selector": {"app": name},
            "ports": [{"port": port, "targetPort": port}],
            "type": svc_type
        }
    }

def make_hpa(name, threshold=70, min_replicas=1):
    return {
        "apiVersion": "autoscaling/v2", "kind": "HorizontalPodAutoscaler",
        "metadata": {"name": f"{name}-hpa"},
        "spec": {
            "scaleTargetRef": {"apiVersion": "apps/v1", "kind": "Deployment", "name": name},
            "minReplicas": min_replicas,
            "maxReplicas": max(10, min_replicas + 5),
            "metrics": [{"type": "Resource", "resource": {"name": "cpu", "target": {"type": "Utilization", "averageUtilization": threshold}}}]
        }
    }

def make_secret(name, data: dict):
    return {
        "apiVersion": "v1", "kind": "Secret",
        "metadata": {"name": f"{name}-secret"},
        "type": "Opaque",
        "data": {k: base64.b64encode(v.encode()).decode() for k, v in data.items()}
    }

def apply_manifest(manifest: dict) -> dict:
    kind = manifest.get("kind")
    name = manifest.get("metadata", {}).get("name")
    ns   = manifest.get("metadata", {}).get("namespace", "default")
    try:
        if kind == "Deployment":
            client.AppsV1Api().create_namespaced_deployment(ns, manifest)
        elif kind == "Service":
            client.CoreV1Api().create_namespaced_service(ns, manifest)
        elif kind == "Secret":
            client.CoreV1Api().create_namespaced_secret(ns, manifest)
        elif kind == "HorizontalPodAutoscaler":
            client.AutoscalingV2Api().create_namespaced_horizontal_pod_autoscaler(ns, manifest)
        else:
            return {"kind": kind, "name": name, "status": "skipped"}
        return {"kind": kind, "name": name, "status": "created"}
    except Exception as e:
        return {"kind": kind, "name": name, "status": f"error: {e}"}

# ── Self-Healing ────────────────────────────────────────
watch_store: dict = {}

def _heal_pod(pod_name, deployment_name, image, namespace):
    """Detect and fix a bad image on a deployment."""
    apps = client.AppsV1Api()
    try:
        # Always read the REAL current image from the cluster
        dep = apps.read_namespaced_deployment(deployment_name, namespace)
        current_image = dep.spec.template.spec.containers[0].image.strip()
        fixed = fix_image(current_image)

        if fixed != current_image:
            print(f"[HEAL] Fixing {deployment_name}: '{current_image}' → '{fixed}'")
            dep.spec.template.spec.containers[0].image = fixed
            apps.patch_namespaced_deployment(deployment_name, namespace, dep)
            SELF_HEALS_TOTAL.inc()
            send_discord("🔧 AI Self-Heal", f"Fixed `{deployment_name}`: `{current_image}` → `{fixed}`")
            return fixed
        else:
            print(f"[HEAL] No fix needed for '{current_image}' on {deployment_name}")
            return None
    except Exception as e:
        print(f"[HEAL ERROR] {deployment_name}: {e}")
        return None

def _watch_bg(app_name, watch_id, image, namespace="default"):
    v1 = client.CoreV1Api()
    watch_store[watch_id] = {"status": "watching", "events": []}

    def log(msg, etype="info"):
        watch_store[watch_id]["events"].append({"type": etype, "message": msg})

    fixed_pods: set = set()
    for _ in range(12):  # 2 minutes max
        time.sleep(10)
        try:
            pods = v1.list_namespaced_pod(namespace, label_selector=f"app={app_name}")
            all_ok = True
            for p in pods.items:
                pname = p.metadata.name
                for cs in (p.status.container_statuses or []):
                    w = cs.state.waiting
                    if w:
                        all_ok = False
                        reason = w.reason or ""
                        # Handle ALL image-related failures
                        BAD_IMAGE_REASONS = (
                            "ImagePullBackOff",
                            "ErrImagePull",
                            "InvalidImageName",
                            "ErrImageNeverPull",
                        )
                        if reason in BAD_IMAGE_REASONS and pname not in fixed_pods:
                            log(f"⚠️ {reason} on {pname} — AI analysing...", "error_detected")
                            result = _heal_pod(pname, app_name, image, namespace)
                            fixed_pods.add(pname)
                            if result:
                                log(f"🔧 Auto-fixed: image corrected to `{result}`", "fix_applied")
                            else:
                                log(f"⚠️ Could not auto-fix {pname} — image may be genuinely invalid", "error_detected")
                        elif reason == "CrashLoopBackOff" and pname not in fixed_pods:
                            log(f"⚠️ CrashLoopBackOff on {pname} — check logs", "error_detected")
                            fixed_pods.add(pname)
            if all_ok and pods.items:
                log("✅ All pods running successfully!", "success")
                watch_store[watch_id]["status"] = "complete"
                return
        except Exception as e:
            log(f"Monitor error: {e}", "error_detected")
            break

    if watch_store[watch_id]["status"] == "watching":
        watch_store[watch_id]["status"] = "timeout"

# ── Routes ─────────────────────────────────────────────

class DeployRequest(BaseModel):
    request: str

@app.get("/health")
@app.get("/api/health")
def health():
    return {"status": "ok", "timestamp": time.time()}

@app.post("/deploy")
@app.post("/api/deploy")
def deploy(body: DeployRequest):
    DEPLOYMENTS_TOTAL.inc()

    # --- Parse intent with AI ---
    intent = call_ollama(
        system_prompt=(
            "You are a JSON extraction expert. "
            "Always respond with valid JSON only. No explanations, no markdown, no extra text."
        ),
        user_prompt=(
            f"Extract the deployment intent from this user request: \"{body.request}\"\n\n"
            "Return ONLY valid JSON, nothing else:\n"
            "{\"app_name\": \"nginx\", \"image\": \"nginx:latest\", \"replicas\": 1, \"port\": 80, "
            "\"needs_database\": false, \"database_type\": \"\", \"needs_hpa\": false, \"cpu_threshold\": 70}\n\n"
            "Rules:\n"
            "- app_name: the application name the user wants to deploy\n"
            "- image: the docker image name from the request (e.g. 'ngix' becomes 'ngix:latest')\n"
            "- needs_hpa: true if user mentions autoscale, autoscaling, hpa, scaling\n"
            "- needs_database: true if user mentions postgres, mysql, redis, database\n"
            "- database_type: 'postgres', 'mysql', or 'redis' if mentioned, else empty string\n"
            "- cpu_threshold: the CPU percentage number if mentioned, else 70\n"
            f"User request: \"{body.request}\""
        ),
    )

    if not intent:
        return JSONResponse(
            status_code=400,
            content={"error": "AI could not parse your command. Try: 'deploy nginx with 3 replicas'"}
        )

    app_name     = str(intent.get("app_name", "myapp")).lower().replace(" ", "-")
    image        = fix_image(str(intent.get("image", "nginx:latest")))
    replicas     = max(1, int(intent.get("replicas", 1)))
    port         = int(intent.get("port", 80))
    db_type      = str(intent.get("database_type", "")).lower().strip()

    # Keyword fallbacks — small AI model often misses these
    raw_lower    = body.request.lower()
    needs_db     = bool(intent.get("needs_database", False)) or \
                   db_type in ("postgres", "mysql", "redis") or \
                   any(w in raw_lower for w in ("postgres", "mysql", "redis", "database", " db "))
    needs_hpa    = bool(intent.get("needs_hpa", False)) or \
                   any(w in raw_lower for w in ("autoscal", "hpa", "auto scale", "autoscale", "scaling", " scale"))

    # Extract cpu_threshold from raw request if AI returned default 70
    cpu_thresh = int(intent.get("cpu_threshold", 70))
    if cpu_thresh == 70:  # AI returned default — try to parse from raw request
        import re
        m = re.search(r'(\d+)\s*%?\s*cpu', raw_lower)
        if not m:
            m = re.search(r'cpu\s*(\d+)', raw_lower)
        if m:
            cpu_thresh = int(m.group(1))

    # --- Build manifests ---
    manifests = [
        make_deployment(app_name, image, replicas, port),
        make_service(app_name, port),
    ]
    if needs_hpa:
        manifests.append(make_hpa(app_name, cpu_thresh, min_replicas=replicas))
    if needs_db:
        if db_type == "postgres":
            pg_deploy = make_deployment("postgres", "postgres:latest", 1, 5432)
            pg_deploy["spec"]["template"]["spec"]["containers"][0]["env"] = [
                {"name": "POSTGRES_PASSWORD", "value": "postgres123"},
                {"name": "POSTGRES_DB",       "value": "appdb"},
            ]
            manifests += [
                make_secret("postgres", {
                    "password": "postgres123",
                    "database-url": "postgresql://postgres:postgres123@postgres-service:5432/appdb"
                }),
                pg_deploy,
                make_service("postgres", 5432, "ClusterIP"),
            ]
        elif db_type == "mysql":
            mysql_deploy = make_deployment("mysql", "mysql:latest", 1, 3306)
            mysql_deploy["spec"]["template"]["spec"]["containers"][0]["env"] = [
                {"name": "MYSQL_ROOT_PASSWORD", "value": "mysql123"},
                {"name": "MYSQL_DATABASE",       "value": "appdb"},
            ]
            manifests += [
                make_secret("mysql", {"password": "mysql123"}),
                mysql_deploy,
                make_service("mysql", 3306, "ClusterIP"),
            ]
        elif db_type == "redis":
            manifests += [
                make_deployment("redis", "redis:latest", 1, 6379),
                make_service("redis", 6379, "ClusterIP"),
            ]

    # --- Apply ---
    deployed = [apply_manifest(m) for m in manifests]
    all_ok   = all("error" not in r["status"] for r in deployed)

    if all_ok:
        DEPLOYMENTS_SUCCESS.inc()
        send_discord("🚀 KubeNexus Deployed",
                     f"App: `{app_name}` | Image: `{image}` | Replicas: `{replicas}`")
        send_email("✅ KubeNexus New Deployment",
                   f"App {app_name} | Image {image} | Replicas {replicas}")

    # --- Start background watcher ---
    watch_id = f"{app_name}-{int(time.time())}"
    threading.Thread(target=_watch_bg, args=(app_name, watch_id, image), daemon=True).start()

    return {
        "status":    "initiated",
        "watch_id":  watch_id,
        "app_name":  app_name,
        "intent":    {**intent, "app_name": app_name},   # ensure app_name key always present
        "deployed":  deployed,                            # frontend reads `deployed`
    }

@app.get("/watch/{watch_id}")
@app.get("/api/watch/{watch_id}")
def get_watch(watch_id: str):
    return watch_store.get(watch_id, {"status": "not_found", "events": []})