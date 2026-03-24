from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import requests
import yaml
import os
import json
import base64
from kubernetes import client, config

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gemma3:1b")

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

# ── Routes ─────────────────────────────────────────────

class DeployRequest(BaseModel):
    request: str

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/deploy")
def deploy(body: DeployRequest):
    # Step 1 - Use Ollama to extract intent as JSON
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
        }
    )

    raw = response.json()["response"].strip()

    # Strip markdown if present
    if raw.startswith("```"):
        raw = "\n".join(raw.split("\n")[1:])
    if raw.endswith("```"):
        raw = "\n".join(raw.split("\n")[:-1])
    raw = raw.strip()

    # Step 2 - Parse intent
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

   # Fix inconsistencies from LLM
    needs_database = intent.get("needs_database", False) or (database_type in ["postgres", "mysql", "redis"])
    needs_hpa = intent.get("needs_hpa", False) or any(word in body.request.lower() for word in ["autoscale", "hpa", "auto scale", "scaling", "scale"])

    # Step 3 - Build manifests from templates
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
            manifests.append(generate_deployment_yaml("mysql", "mysql:latest", 1, 3306))
            manifests.append(generate_service_yaml("mysql", 3306, "ClusterIP"))

    # Step 4 - Apply all manifests
    results = []
    for manifest in manifests:
        result = apply_manifest(manifest)
        results.append(result)

    return {
        "status": "success",
        "intent": intent,
        "deployed": results
    }