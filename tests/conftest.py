import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest

# Add the project root to the Python path so 'app' module can be imported
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def _is_localhost_url(url: str) -> bool:
	return url.startswith("http://localhost:") or url.startswith("http://127.0.0.1:")


def _port_is_open(host: str, port: int) -> bool:
	with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
		sock.settimeout(0.5)
		return sock.connect_ex((host, port)) == 0


@pytest.fixture(scope="session", autouse=True)
def ensure_local_streamlit_server():
	os.environ["MOCK_AI"] = "true"
	app_url = os.environ.get("APP_URL", "http://localhost:8505")
	if not _is_localhost_url(app_url):
		yield
		return

	host = "127.0.0.1"
	port = int(app_url.rsplit(":", 1)[-1])
	if _port_is_open(host, port):
		yield
		return

	command = [
		sys.executable,
		"-m",
		"streamlit",
		"run",
		"app/streamlit_app.py",
		"--server.address",
		host,
		"--server.port",
		str(port),
		"--server.headless",
		"true",
		"--browser.gatherUsageStats",
		"false",
	]
	# Write Streamlit output to a log file for CI debugging
	log_dir = project_root / "temp_artifacts"
	try:
		log_dir.mkdir(parents=True, exist_ok=True)
	except Exception:
		pass
	log_file = log_dir / "streamlit_server.log"
	log_fh = open(str(log_file), "a", encoding="utf-8")
	process = subprocess.Popen(
		command,
		cwd=str(project_root),
		stdout=log_fh,
		stderr=subprocess.STDOUT,
	)

	try:
		# Give Streamlit more time to start on CI runners
		deadline = time.time() + 120
		while time.time() < deadline:
			if process.poll() is not None:
				# include a snippet of the log to aid debugging
				try:
					log_fh.flush()
					with open(str(log_file), "r", encoding="utf-8", errors="ignore") as _f:
						tail = _f.read()[-4000:]
				except Exception:
					tail = ""
				raise RuntimeError(f"Streamlit exited early with code {process.returncode}\n---log tail---\n{tail}")
			if _port_is_open(host, port):
				break
			time.sleep(0.5)
		else:
			try:
				log_fh.flush()
				with open(str(log_file), "r", encoding="utf-8", errors="ignore") as _f:
					tail = _f.read()[-4000:]
			except Exception:
				tail = ""
			raise RuntimeError(f"Streamlit did not start on {app_url}\n---log tail---\n{tail}")

		yield
	finally:
		if process.poll() is None:
			process.terminate()
			try:
				process.wait(timeout=15)
			except Exception:
				process.kill()
		try:
			log_fh.close()
		except Exception:
			pass
