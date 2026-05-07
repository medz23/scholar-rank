import base64
import json
import logging
import threading

import docker

logger = logging.getLogger(__name__)

MAX_CONCURRENT = 15
QUEUE_TIMEOUT = 120
CONTAINER_TIMEOUT = 30

_docker_client = None
_docker_lock = threading.Lock()
_semaphore = threading.Semaphore(MAX_CONCURRENT)


def _get_docker_client():
    global _docker_client
    if _docker_client is None:
        with _docker_lock:
            if _docker_client is None:
                _docker_client = docker.from_env(timeout=120)
                # Pre-pull the image so first submissions don't hang
                try:
                    _docker_client.images.get("python:3.12-slim")
                    logger.info("[EXECUTOR] python:3.12-slim image found locally.")
                except docker.errors.ImageNotFound:
                    logger.info("[EXECUTOR] Pulling python:3.12-slim ...")
                    _docker_client.images.pull("python:3.12-slim")
                    logger.info("[EXECUTOR] Pull complete.")
    return _docker_client


def run_tests(student_code, test_cases, function_name=None):
    """
    Run all test cases in a SINGLE Docker container.

    Data is passed via base64-encoded environment variable — no volumes,
    no helper containers. One container does everything.
    """
    client = _get_docker_client()

    if not test_cases:
        return []

    test_inputs = []
    for tc in test_cases:
        test_inputs.append({
            "id": tc.id,
            "input_data": tc.input_data,
            "expected_output": tc.expected_output,
            "is_hidden": getattr(tc, 'is_hidden', False),
        })

    harness_code = _build_harness(function_name)

    payload = json.dumps({
        "student_code": student_code,
        "tests": test_inputs,
        "harness": harness_code,
    })
    payload_b64 = base64.b64encode(payload.encode('utf-8')).decode('ascii')

    bootstrap_script = (
        "import json, base64, os, sys;"
        "data = json.loads(base64.b64decode(os.environ['PAYLOAD']));"
        "open('/tmp/student_code.py','w').write(data['student_code']);"
        "json.dump(data['tests'], open('/tmp/tests.json','w'));"
        "open('/tmp/harness.py','w').write(data['harness']);"
        "exec(open('/tmp/harness.py').read())"
    )

    try:
        acquired = _semaphore.acquire(timeout=QUEUE_TIMEOUT)
        if not acquired:
            logger.warning("[EXECUTOR] Semaphore timeout — all %d slots busy for %ds",
                           MAX_CONCURRENT, QUEUE_TIMEOUT)
            return [
                {"test_id": tc.id, "passed": False, "input": tc.input_data,
                 "expected": tc.expected_output, "output": None,
                 "error": "Server busy — too many students running tests. Please try again in a few seconds."}
                for tc in test_cases
            ]

        try:
            container_output = client.containers.run(
                image="python:3.12-slim",
                command=["python3", "-c", bootstrap_script],
                environment={"PAYLOAD": payload_b64},
                network_disabled=True,
                mem_limit="128m",
                cpu_period=100000,
                cpu_quota=50000,
                pids_limit=64,
                read_only=True,
                tmpfs={"/tmp": "size=64m,noexec"},
                remove=True,
                stderr=True,
                stdout=True,
                detach=False,
            )
        finally:
            _semaphore.release()

        output = container_output.decode('utf-8').strip()
        results = json.loads(output)
        return results

    except docker.errors.ContainerError as e:
        error_msg = e.stderr.decode('utf-8')[:500] if e.stderr else "Container error"
        return [
            {"test_id": tc.id, "passed": False, "input": tc.input_data,
             "expected": tc.expected_output, "output": None, "error": error_msg}
            for tc in test_cases
        ]
    except json.JSONDecodeError:
        return [
            {"test_id": tc.id, "passed": False, "input": tc.input_data,
             "expected": tc.expected_output, "output": None, "error": "Invalid output from test runner"}
            for tc in test_cases
        ]
    except Exception as e:
        logger.exception("[EXECUTOR] Unexpected error running tests")
        return [
            {"test_id": tc.id, "passed": False, "input": tc.input_data,
             "expected": tc.expected_output, "output": None, "error": f"Execution Error: {str(e)[:300]}"}
            for tc in test_cases
        ]


def _build_harness(function_name=None):
    if function_name:
        return f'''
import json, sys, io, traceback, signal

class TimeoutError(Exception):
    pass

def timeout_handler(signum, frame):
    raise TimeoutError("Time limit exceeded")

PER_TEST_TIMEOUT = 5

def normalize_for_compare(value):
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return [normalize_for_compare(v) for v in value]
    if isinstance(value, dict):
        return {{k: normalize_for_compare(v) for k, v in sorted(value.items())}}
    return str(value)

def compare_outputs(actual, expected_str):
    try:
        expected_parsed = json.loads(expected_str)
        return normalize_for_compare(actual) == normalize_for_compare(expected_parsed)
    except (json.JSONDecodeError, TypeError):
        pass
    return format_output(actual).strip() == expected_str.strip()

def format_output(value):
    if value is None:
        return "None"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (list, dict, tuple)):
        return json.dumps(value, separators=(",", ":"))
    return str(value)

with open("/tmp/tests.json") as f:
    tests = json.load(f)

namespace = {{}}
try:
    exec(open("/tmp/student_code.py").read(), namespace)
except Exception as e:
    results = [{{"test_id": t["id"], "passed": False,
                "input": t["input_data"], "expected": t["expected_output"],
                "output": None, "error": f"Code failed to load: {{e}}"}} for t in tests]
    print(json.dumps(results))
    sys.exit(0)

fn = namespace.get("{function_name}")
if fn is None:
    results = [{{"test_id": t["id"], "passed": False,
                "input": t["input_data"], "expected": t["expected_output"],
                "output": None, "error": "Function '{function_name}' not defined in your code"}} for t in tests]
    print(json.dumps(results))
    sys.exit(0)

results = []
for t in tests:
    try:
        raw_input = t["input_data"]
        input_data = json.loads(raw_input)

        if isinstance(input_data, dict):
            args = []
            kwargs = input_data
        elif isinstance(input_data, list):
            args = input_data
            kwargs = {{}}
        else:
            args = [input_data]
            kwargs = {{}}

        old_stdout = sys.stdout
        sys.stdout = buffer = io.StringIO()

        signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(PER_TEST_TIMEOUT)

        try:
            result = fn(*args, **kwargs)
        finally:
            signal.alarm(0)
            printed = buffer.getvalue().strip()
            sys.stdout = old_stdout

        if result is not None:
            output_display = format_output(result)
            passed = compare_outputs(result, t["expected_output"])
        else:
            output_display = printed
            passed = printed.strip() == t["expected_output"].strip()

        results.append({{
            "test_id": t["id"],
            "passed": passed,
            "input": t["input_data"] if not t.get("is_hidden") else "[hidden]",
            "expected": t["expected_output"] if not t.get("is_hidden") else "[hidden]",
            "output": output_display if not t.get("is_hidden") else ("[hidden]" if not passed else output_display),
            "error": None
        }})

    except TimeoutError:
        sys.stdout = sys.__stdout__
        results.append({{
            "test_id": t["id"], "passed": False,
            "input": t["input_data"] if not t.get("is_hidden") else "[hidden]",
            "expected": t["expected_output"] if not t.get("is_hidden") else "[hidden]",
            "output": None,
            "error": f"Time Limit Exceeded ({{PER_TEST_TIMEOUT}}s)"
        }})
    except Exception as e:
        sys.stdout = sys.__stdout__
        tb = traceback.format_exc()
        err_lines = [l for l in tb.strip().split("\\n") if l.strip()]
        short_err = err_lines[-1] if err_lines else str(e)
        results.append({{
            "test_id": t["id"], "passed": False,
            "input": t["input_data"] if not t.get("is_hidden") else "[hidden]",
            "expected": t["expected_output"] if not t.get("is_hidden") else "[hidden]",
            "output": None,
            "error": short_err[:400]
        }})

print(json.dumps(results))
'''
    else:
        return '''
import json, sys, subprocess

with open("/tmp/tests.json") as f:
    tests = json.load(f)

results = []
for t in tests:
    try:
        proc = subprocess.run(
            ["python3", "/tmp/student_code.py"],
            input=t["input_data"],
            capture_output=True, text=True, timeout=10
        )
        output = proc.stdout.strip()
        stderr = proc.stderr.strip()
        error = None

        if proc.returncode != 0:
            err_lines = [l for l in stderr.split("\\n") if l.strip()]
            error = err_lines[-1] if err_lines else f"Exit code {proc.returncode}"

        expected = t["expected_output"].strip()
        passed = output == expected

        results.append({
            "test_id": t["id"],
            "passed": passed,
            "input": t["input_data"] if not t.get("is_hidden") else "[hidden]",
            "expected": expected if not t.get("is_hidden") else "[hidden]",
            "output": output if not t.get("is_hidden") else ("[hidden]" if not passed else output),
            "error": error
        })
    except subprocess.TimeoutExpired:
        results.append({
            "test_id": t["id"], "passed": False,
            "input": t["input_data"] if not t.get("is_hidden") else "[hidden]",
            "expected": t["expected_output"] if not t.get("is_hidden") else "[hidden]",
            "output": None,
            "error": "Time Limit Exceeded (10s)"
        })
    except Exception as e:
        results.append({
            "test_id": t["id"], "passed": False,
            "input": t["input_data"] if not t.get("is_hidden") else "[hidden]",
            "expected": t["expected_output"] if not t.get("is_hidden") else "[hidden]",
            "output": None,
            "error": str(e)[:300]
        })

print(json.dumps(results))
'''