from flask import Flask, render_template, request, redirect, url_for, flash
import asyncio
import os
import subprocess
from py3xui import AsyncApi
from dotenv import load_dotenv
from urllib.parse import unquote, urlparse

dotenv_path = os.getenv('DOTENV_PATH', None)
if dotenv_path:
    load_dotenv(dotenv_path)
else:
    load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'changeme')

NODES = {}
i = 1
while True:
    name = os.getenv(f"NODE{i}_NAME")
    host = os.getenv(f"NODE{i}_HOST")
    username = os.getenv(f"NODE{i}_USERNAME")
    password = os.getenv(f"NODE{i}_PASSWORD")
    if not all([name, host, username, password]):
        break
    NODES[name] = {
        "host": host,
        "username": username,
        "password": password
    }
    i += 1

def is_host_online(hostname: str, timeout: int = 1) -> bool:
    try:
        res = subprocess.run(
            ["ping", "-c", "1", "-W", str(timeout), hostname],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        return res.returncode == 0
    except Exception:
        return False

def extract_email(raw_input: str) -> str:
    try:
        if "://" in raw_input and "#" in raw_input:
            parsed = urlparse(raw_input)
            fragment = unquote(parsed.fragment)
            if "-" in fragment:
                return fragment.rsplit('-', 1)[1]
            return fragment
    except Exception:
        pass
    return raw_input.strip()

def get_node_by_domain(domain: str):
    for name, config in NODES.items():
        try:
            node_host = urlparse(config["host"]).hostname
            if domain and domain == node_host:
                return name, config
        except Exception:
            continue
    return None, None

async def get_client_usage(node: dict, email: str):
    api = AsyncApi(
        host=node["host"],
        username=node["username"],
        password=node["password"]
    )
    await api.login()
    client = await api.client.get_by_email(email)
    return client

@app.route('/', methods=['GET', 'POST'])
def index():
    statuses = {}
    for name, cfg in NODES.items():
        try:
            hostname = urlparse(cfg["host"]).hostname
            statuses[name] = is_host_online(hostname)
        except Exception:
            statuses[name] = False

    if request.method == 'POST':
        raw_input = request.form.get('email')
        selected_node = request.form.get('node')

        if raw_input:
            try:
                parsed = urlparse(raw_input)
                domain = parsed.hostname
                if domain:
                    matched_name, matched_node = get_node_by_domain(domain)
                    if matched_node:
                        selected_node = matched_name
                        node_config = matched_node
                    else:
                        flash(f"No matching node found for domain: {domain}", "error")
                        return redirect(url_for('index'))
                else:
                    node_config = NODES.get(selected_node)
            except Exception as e:
                flash(f"Domain extraction error: {e}", "error")
                return redirect(url_for('index'))

            if not node_config:
                flash("Invalid node selection.", "error")
                return redirect(url_for('index'))

            try:
                email = extract_email(raw_input)
                client = asyncio.run(get_client_usage(node_config, email))
                if client:
                    return render_template(
                        'result.html',
                        client=client,
                        node=selected_node,
                        statuses=statuses,
                        nodes=NODES
                    )
                else:
                    flash("No client found with that email or remark.", "error")
            except Exception as e:
                flash(f"Error fetching data: {e}", "error")
        return redirect(url_for('index'))

    return render_template('index.html', nodes=NODES, statuses=statuses)

if __name__ == '__main__':
    port = int(os.getenv('FLASK_PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
