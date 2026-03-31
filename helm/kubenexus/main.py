from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from prometheus_fastapi_instrumentator import Instrumentator
from prometheus_client import Counter, Histogram
import requests
import yaml
import os
import json
import base64
import time
import threading
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from kubernetes import client, config

app = FastAPI()

# Prometheus metrics
DEPLOYMENTS_TOTAL = Counter(
    'kubenexus_deployments_total',
    'Total number of deployment requests'
)

DEPLOYMENTS_SUCCESS = Counter(
    'kubenexus_deployments_success',
    'Total number of successful deployments'
)

SELF_HEALS_TOTAL = Counter(
    'kubenexus_self_heals_total',
    'Total number of AI self healing events'
)

OLLAMA_LATENCY = Histogram(
    'kubenexus_ollama_latency_seconds',
    'Ollama response latency in seconds'
)

# Instrument FastAPI
Instrumentator().instrument(app).expose(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gemma3:1b")

DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "")
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "465"))
MAIL_USERNAME = os.getenv("MAIL_USERNAME", "")
MAIL_PASSWORD = os.getenv("MAIL_PASSWORD", "")

def send_discord_alert(title, description):
    if not DISCORD_WEBHOOK_URL: return
    try:
        requests.post(DISCORD_WEBHOOK_URL, json={"content": f"**{title}**\n{description}"})
    except Exception as e:
        print(f"Discord error: {e}")

def send_email_alert(subject, body):
    if not MAIL_USERNAME or not MAIL_PASSWORD: return
    try:
        msg = MIMEMultipart()
        msg['From'] = "KubeNexus AI"
        msg['To'] = MAIL_USERNAME
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))
        
        with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) as server:
            server.login(MAIL_USERNAME, MAIL_PASSWORD)
            server.send_message(msg)
    except Exception as e:
        print(f"Email error: {e}")

# Load Kubernetes config
try:
    config.load_incluster_config()
except:
    config.load_kube_config()

# ── Templates ──────────────────────────────────────────

def generate_deployment_yaml(name, image, replicas=1, port=80):
    return {
        "apiVersion": "apps/v1",
        "kind": "Deployment",
        "metadata": {"name": name},
        "spec": {
            "replicas": replicas,
            "selector": {"matchLabels": {"app": name}},
            "template": {
                "metadata": {"labels": {"app": name}},
                "spec": {
                    "containers": [{
                        "name": name,
                        "image": image,
                        "ports": [{"containerPort": port}]
                    }]
                }
            }
        }
    }

def generate_service_yaml(name, port=80, service_type="NodePort"):
    return {
        "apiVersion": "v1",
        "kind": "Service",
        "metadata": {"name": f"{name}-service"},
        "spec": {
            "selector": {"app": name},
            "ports": [{"port": port, "targetPort": port}],
            "type": service_type
        }
    }

def generate_hpa_yaml(name, cpu_threshold=70):
    return {
        "apiVersion": "autoscaling/v2",
        "kind": "HorizontalPodAutoscaler",
        "metadata": {"name": f"{name}-hpa"},
        "spec": {
            "scaleTargetRef": {
                "apiVersion": "apps/v1",
                "kind": "Deployment",
                "name": name
            },
            "minReplicas": 1,
            "maxReplicas": 10,
            "metrics": [{
                "type": "Resource",
                "resource": {
                    "name": "cpu",
                    "target": {
                        "type": "Utilization",
                        "averageUtilization": cpu_threshold
                    }
                }
            }]
        }
    }

def generate_secret_yaml(name, data):
    encoded = {k: base64.b64encode(v.encode()).decode() for k, v in data.items()}
    return {
        "apiVersion": "v1",
        "kind": "Secret",
        "metadata": {"name": f"{name}-secret"},
        "type": "Opaque",
        "data": encoded
    }

def generate_postgres_deployment_yaml():
    return {
        "apiVersion": "apps/v1",
        "kind": "Deployment",
        "metadata": {"name": "postgres"},
        "spec": {
            "replicas": 1,
            "selector": {"matchLabels": {"app": "postgres"}},
            "template": {
                "metadata": {"labels": {"app": "postgres"}},
                "spec": {
                    "containers": [{
                        "name": "postgres",
                        "image": "postgres:latest",
                        "ports": [{"containerPort": 5432}],
                        "env": [
                            {
                                "name": "POSTGRES_PASSWORD",
                                "valueFrom": {
                                    "secretKeyRef": {
                                        "name": "postgres-secret",
                                        "key": "password"
                                    }
                                }
                            },
                            {
                                "name": "POSTGRES_DB",
                                "value": "appdb"
                            }
                        ]
                    }]
                }
            }
        }
    }

def generate_mysql_deployment_yaml():
    return {
        "apiVersion": "apps/v1",
        "kind": "Deployment",
        "metadata": {"name": "mysql"},
        "spec": {
            "replicas": 1,
            "selector": {"matchLabels": {"app": "mysql"}},
            "template": {
                "metadata": {"labels": {"app": "mysql"}},
                "spec": {
                    "containers": [{
                        "name": "mysql",
                        "image": "mysql:latest",
                        "ports": [{"containerPort": 3306}],
                        "env": [
                            {
                                "name": "MYSQL_ROOT_PASSWORD",
                                "valueFrom": {
                                    "secretKeyRef": {
                                        "name": "mysql-secret",
                                        "key": "password"
                                    }
                                }
                            },
                            {
                                "name": "MYSQL_DATABASE",
                                "value": "appdb"
                            }
                        ]
                    }]
                }
            }
        }
    }

# ── Apply manifest to cluster ──────────────────────────

def apply_manifest(manifest):
    kind = manifest.get("kind")
    name = manifest.get("metadata", {}).get("name")
    namespace = manifest.get("metadata", {}).get("namespace", "default")

    try:
        if kind == "Deployment":
            api = client.AppsV1Api()
            api.create_namespaced_deployment(namespace=namespace, body=manifest)
        elif kind == "Service":
            api = client.CoreV1Api()
            api.create_namespaced_service(namespace=namespace, body=manifest)
        elif kind == "ConfigMap":
            api = client.CoreV1Api()
            api.create_namespaced_config_map(namespace=namespace, body=manifest)
        elif kind == "Secret":
            api = client.CoreV1Api()
            api.create_namespaced_secret(namespace=namespace, body=manifest)
        elif kind == "HorizontalPodAutoscaler":
            api = client.AutoscalingV2Api()
            api.create_namespaced_horizontal_pod_autoscaler(namespace=namespace, body=manifest)
        elif kind == "ServiceAccount":
            api = client.CoreV1Api()
            api.create_namespaced_service_account(namespace=namespace, body=manifest)
        else:
            return {"kind": kind, "name": name, "status": "skipped - unsupported kind"}

        return {"kind": kind, "name": name, "status": "created"}

    except Exception as e:
        return {"kind": kind, "name": name, "status": f"error: {str(e)}"}

# ── Common image typo corrections ──────────────────────

IMAGE_CORRECTIONS = {
    "ngix": "nginx:latest",
    "ngnix": "nginx:latest",
    "niginx": "nginx:latest",
    "nginix": "nginx:latest",
    "nginx": "nginx:latest",
    "postgress": "postgres:latest",
    "postgresl": "postgres:latest",
    "reddis": "redis:latest",
    "rediss": "redis:latest",
    "apche": "apache:latest",
    "appache": "apache:latest",
    "monogo": "mongo:latest",
    "monggo": "mongo:latest",
    "msql": "mysql:latest",
    "mysqll": "mysql:latest",
}

def correct_image_typo(image_name):
    base = image_name.split(":")[0].lower()
    if base in IMAGE_CORRECTIONS:
        return IMAGE_CORRECTIONS[base], True
    return image_name, False

# ── AI Self Healing ────────────────────────────────────

def analyze_and_fix_pod(pod_name, deployment_name, original_image, namespace="default"):
    v1 = client.CoreV1Api()
    apps_v1 = client.AppsV1Api()

    try:
        events = v1.list_namespaced_event(
            namespace=namespace,
            field_selector=f"involvedObject.name={pod_name}"
        )
        event_messages = [e.message for e in events.items if e.message]
    except:
        event_messages = []

    try:
        logs = v1.read_namespaced_pod_log(
            name=pod_name,
            namespace=namespace,
            tail_lines=20
        )
    except:
        logs = "No logs available"

    # First try hardcoded typo correction
    corrected_image, was_typo = correct_image_typo(original_image)

    if was_typo:
        analysis = {
            "root_cause": f"Typo in image name: '{original_image}' does not exist",
            "is_auto_fixable": True,
            "fix_type": "image_correction",
            "fix_value": corrected_image,
            "message": f"Image '{original_image}' appears to be a typo. Auto correcting to '{corrected_image}'",
            "auto_fixed": False
        }
    else:
        start_time = time.time()
        analysis_prompt = f"""A Kubernetes pod has an ImagePullBackOff error.

Requested image: {original_image}
Error events: {json.dumps(event_messages)}

This is likely a typo in the image name. Common corrections:
- ngix -> nginx
- ngnix -> nginx
- postgress -> postgres
- reddis -> redis

Respond ONLY in this exact JSON format:
{{
  "root_cause": "one sentence explanation",
  "is_auto_fixable": true or false,
  "fix_type": "image_correction or none",
  "fix_value": "corrected docker image name with :latest tag or empty string",
  "message": "human readable explanation"
}}"""

        response = requests.post(
            f"{OLLAMA_HOST}/api/generate",
            json={
                "model": OLLAMA_MODEL,
                "system": "You are a Kubernetes debugging expert. Always respond with valid JSON only. No markdown.",
                "prompt": analysis_prompt,
                "stream": False
            }
        )
        OLLAMA_LATENCY.observe(time.time() - start_time)

        raw = response.json().get("response", "").strip()
        if raw.startswith("```"):
            raw = "\n".join(raw.split("\n")[1:])
        if raw.endswith("```"):
            raw = "\n".join(raw.split("\n")[:-1])
        raw = raw.strip()

        try:
            analysis = json.loads(raw)
            analysis["auto_fixed"] = False
        except:
            analysis = {
                "root_cause": "Could not analyze error",
                "is_auto_fixable": False,
                "fix_type": "none",
                "fix_value": "",
                "message": "AI could not determine the fix. Please check the image name manually.",
                "auto_fixed": False
            }

    # Apply fix if possible
    if analysis.get("is_auto_fixable") and analysis.get("fix_type") == "image_correction":
        fix_value = analysis.get("fix_value", "")
        if fix_value and " " not in fix_value:
            try:
                deployment = apps_v1.read_namespaced_deployment(
                    name=deployment_name,
                    namespace=namespace
                )
                deployment.spec.template.spec.containers[0].image = fix_value
                apps_v1.patch_namespaced_deployment(
                    name=deployment_name,
                    namespace=namespace,
                    body=deployment
                )
                analysis["auto_fixed"] = True
                SELF_HEALS_TOTAL.inc()
            except Exception as e:
                analysis["auto_fixed"] = False
                analysis["fix_error"] = str(e)

    return analysis


# Shared watch results store
watch_store = {}

def watch_pods_background(deployment_name, watch_id, original_image, namespace="default"):
    v1 = client.CoreV1Api()
    watch_store[watch_id] = {"status": "watching", "events": []}

    max_attempts = 12
    attempt = 0
    fixed_pods = set()

    while attempt < max_attempts:
        time.sleep(10)
        attempt += 1

        try:
            pods = v1.list_namespaced_pod(
                namespace=namespace,
                label_selector=f"app={deployment_name}"
            )
        except:
            break

        all_running = True

        for pod in pods.items:
            pod_name = pod.metadata.name
            container_statuses = pod.status.container_statuses or []

            for cs in container_statuses:
                waiting = cs.state.waiting
                if waiting and pod_name not in fixed_pods:
                    reason = waiting.reason
                    all_running = False

                    if reason in ["ImagePullBackOff", "ErrImagePull"]:
                        watch_store[watch_id]["events"].append({
                            "type": "error_detected",
                            "pod": pod_name,
                            "error": reason,
                            "message": f"⚠️ {reason} detected on {pod_name}"
                        })

                        analysis = analyze_and_fix_pod(
                            pod_name,
                            deployment_name,
                            original_image,
                            namespace
                        )
                        fixed_pods.add(pod_name)

                        watch_store[watch_id]["events"].append({
                            "type": "analysis",
                            "pod": pod_name,
                            "root_cause": analysis.get("root_cause"),
                            "message": f"🤖 AI Analysis: {analysis.get('message')}",
                            "auto_fixed": analysis.get("auto_fixed", False)
                        })

                        if analysis.get("auto_fixed"):
                            watch_store[watch_id]["events"].append({
                                "type": "fix_applied",
                                "pod": pod_name,
                                "message": f"🔧 Auto fixed image to: {analysis.get('fix_value')}"
                            })
                            send_discord_alert("🔧 AI Self-Heal Initiated", f"Pod: `{pod_name}`\nError: `ImagePullBackOff`\nFix Applied: Swapped image to `{analysis.get('fix_value')}`")
                            send_email_alert("KubeNexus AI Self-Heal Event", f"Pod {pod_name} encountered an ImagePullBackOff error. KubeNexus correctly analyzed the issue and automatically applied a patch swamping the image to {analysis.get('fix_value')}.")

                    elif reason == "CrashLoopBackOff":
                        watch_store[watch_id]["events"].append({
                            "type": "error_detected",
                            "pod": pod_name,
                            "error": reason,
                            "message": f"⚠️ CrashLoopBackOff detected on {pod_name} — check application logs"
                        })
                        fixed_pods.add(pod_name)

        if all_running and pods.items:
            watch_store[watch_id]["events"].append({
                "type": "success",
                "message": "✅ All pods are running successfully"
            })
            watch_store[watch_id]["status"] = "complete"
            break

    if watch_store[watch_id]["status"] == "watching":
        watch_store[watch_id]["status"] = "timeout"

# ── Routes ─────────────────────────────────────────────

class DeployRequest(BaseModel):
    request: str

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/deploy")
def deploy(body: DeployRequest):
    DEPLOYMENTS_TOTAL.inc()

    # Step 1 - Use Ollama to extract intent as JSON
    start_time = time.time()
    intent_prompt = f"""I need you to fill in a JSON template based on a user request.

User request: "{body.request}"

Here is an example:
User request: "deploy nginx with 3 replicas"
Output:
{{"app_name": "nginx", "image": "nginx:latest", "replicas": 3, "port": 80, "needs_database": false, "database_type": "", "cpu_threshold": 70, "needs_hpa": false}}

Another example:
User request: "deploy my app using myuser/myapp:v1 with postgres database and autoscale at 60 percent"
Output:
{{"app_name": "myapp", "image": "myuser/myapp:v1", "replicas": 1, "port": 80, "needs_database": true, "database_type": "postgres", "cpu_threshold": 60, "needs_hpa": true}}

Now fill in the JSON for this request: "{body.request}"
Output JSON only, nothing else:"""

    response = requests.post(
        f"{OLLAMA_HOST}/api/generate",
        json={
            "model": OLLAMA_MODEL,
            "system": "You are a JSON extraction expert. Always respond with valid JSON only. No explanations. No markdown. No extra text.",
            "prompt": intent_prompt,
            "stream": False
        },
        timeout=60.0
    )
    OLLAMA_LATENCY.observe(time.time() - start_time)

    raw = response.json().get("response", "").strip()

    if raw.startswith("```"):
        raw = "\n".join(raw.split("\n")[1:])
    if raw.endswith("```"):
        raw = "\n".join(raw.split("\n")[:-1])
    raw = raw.strip()

    try:
        intent = json.loads(raw)
    except:
        return {"error": "Could not understand the request. Please try again.", "raw": raw}

    app_name = intent.get("app_name", "myapp")
    image = intent.get("image", "nginx:latest")
    replicas = int(intent.get("replicas", 1))
    port = int(intent.get("port", 80))
    database_type = intent.get("database_type", "")
    cpu_threshold = int(intent.get("cpu_threshold", 70))

    needs_database = intent.get("needs_database", False) or (database_type in ["postgres", "mysql", "redis"])
    needs_hpa = intent.get("needs_hpa", False) or any(word in body.request.lower() for word in ["autoscale", "hpa", "auto scale", "scaling", "scale"])

    # Build manifests
    manifests = []
    manifests.append(generate_deployment_yaml(app_name, image, replicas, port))
    manifests.append(generate_service_yaml(app_name, port))

    if needs_hpa:
        manifests.append(generate_hpa_yaml(app_name, cpu_threshold))

    if needs_database:
        if database_type == "postgres":
            manifests.append(generate_secret_yaml("postgres", {
                "password": "postgres123",
                "database-url": "postgresql://postgres:postgres123@postgres-service:5432/appdb"
            }))
            manifests.append(generate_postgres_deployment_yaml())
            manifests.append(generate_service_yaml("postgres", 5432, "ClusterIP"))
        elif database_type == "redis":
            manifests.append(generate_deployment_yaml("redis", "redis:latest", 1, 6379))
            manifests.append(generate_service_yaml("redis", 6379, "ClusterIP"))
        elif database_type == "mysql":
            manifests.append(generate_secret_yaml("mysql", {
                "password": "mysql123"
            }))
            manifests.append(generate_mysql_deployment_yaml())
            manifests.append(generate_service_yaml("mysql", 3306, "ClusterIP"))

    # Apply all manifests
    results = []
    all_success = True
    for manifest in manifests:
        result = apply_manifest(manifest)
        results.append(result)
        if "error" in result["status"]:
            all_success = False

    if all_success:
        DEPLOYMENTS_SUCCESS.inc()
        send_discord_alert("✅ KubeNexus Successfully Deployed", f"App: `{app_name}`\nImage: `{image}`\nReplicas: `{replicas}`\nDatabase: `{database_type if database_type else 'None'}`\nAutoscaling: `{'Enabled' if needs_hpa else 'Disabled'}`")
        send_email_alert("✅ KubeNexus New Manifest Deployed", f"KubeNexus successfully interpreted a voice command and applied an orchestration manifest mapping App: {app_name} | Image: {image} | Replicas: {replicas}.")

    # Start background watcher
    watch_id = f"{app_name}-{int(time.time())}"
    thread = threading.Thread(
        target=watch_pods_background,
        args=(app_name, watch_id, image),
        daemon=True
    )
    thread.start()

    return {
        "status": "success",
        "intent": intent,
        "deployed": results,
        "watch_id": watch_id
    }

@app.get("/watch/{watch_id}")
def get_watch_status(watch_id: str):
    if watch_id not in watch_store:
        return {"status": "not_found", "events": []}
    return watch_store[watch_id]