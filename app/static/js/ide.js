require.config({
	paths: {'vs': 'https://cdnjs.cloudflare.com/ajax/libs/monaco-editor/0.36.1/min/vs'}
});

window.addEventListener("load", function () {
	require(['vs/editor/editor.main'], function () {
		const startCode = document.getElementById('start-code-template').textContent;

		window.editor = monaco.editor.create(document.getElementById('editor'), {
			value: startCode || '# Write your solution here\n',
			language: 'python',
			theme: 'vs',
			automaticLayout: true,
			fontSize: 14,
			minimap: {enabled: false},
			scrollBeyondLastLine: false,
		});
	});
});

async function runCode(problemId) {
	const code = window.editor.getValue();
	const terminal = document.getElementById('terminal');
	terminal.innerHTML = '';
	appendLine(terminal, '$ Running tests in sandbox...', '#eab308');
	appendLine(terminal, '');

	setButtonsDisabled(true);

	try {
		const response = await fetch(window.API_URLS.runCode, {
			method: 'POST',
			headers: {'Content-Type': 'application/json'},
			body: JSON.stringify({code: code, problem_id: problemId})
		});

		const data = await response.json();

		if (!response.ok) {
			appendLine(terminal, `Server error (${response.status}): ${data.error || 'Unknown error'}`, '#ff6b6b');
			return;
		}

		if (data.error) {
			appendLine(terminal, `Error: ${data.error}`, '#ff6b6b');
			if (data.test_results && data.test_results.length > 0) {
				printResultsToTerminal(data.test_results, terminal);
			}
			return;
		}

		if (!data.test_results || data.test_results.length === 0) {
			appendLine(terminal, '$ No test cases defined for this problem yet.', '#eab308');
			return;
		}

		printResultsToTerminal(data.test_results, terminal);
	} catch (err) {
		appendLine(terminal, `Network error: ${err.message}`, '#ff6b6b');
		appendLine(terminal, 'Check your connection and try again.', '#94a3b8');
	} finally {
		setButtonsDisabled(false);
	}
}

async function submitExam(problemId) {
	if (!confirm("Are you sure you want to submit? This action is final.")) {
		return;
	}

	const code = window.editor.getValue();
	const terminal = document.getElementById('terminal');
	terminal.innerHTML = '';
	appendLine(terminal, '$ Submitting solution... Please wait.', '#00b894');

	setButtonsDisabled(true);

	try {
		const response = await fetch(window.API_URLS.submitCode, {
			method: 'POST',
			headers: {'Content-Type': 'application/json'},
			body: JSON.stringify({code: code, problem_id: problemId})
		});

		const data = await response.json();

		if (!response.ok) {
			appendLine(terminal, `Submission error (${response.status}): ${data.error || 'Unknown error'}`, '#ff6b6b');
			setButtonsDisabled(false);
			return;
		}

		if (data.error && !data.redirect_url) {
			appendLine(terminal, `Error: ${data.error}`, '#ff6b6b');
			setButtonsDisabled(false);
			return;
		}

		if (data.redirect_url) {
    window.__intentionalNav = true;
    window.location.href = data.redirect_url;
}
	} catch (err) {
		appendLine(terminal, `Submission failed: ${err.message}`, '#ff6b6b');
		appendLine(terminal, 'Check your connection and try again.', '#94a3b8');
		setButtonsDisabled(false);
	}
}

function printResultsToTerminal(results, terminal) {
	let passedCount = 0;
	const total = results.length;

	results.forEach((res, index) => {
		const testNum = index + 1;

		if (res.passed) {
			passedCount++;
			appendLine(terminal, `✓ Test ${testNum}: PASSED`, '#00b894');
		} else {
			appendLine(terminal, `✗ Test ${testNum}: FAILED`, '#ff6b6b');
		}

		if (res.input && res.input !== '[hidden]') {
			appendLine(terminal, `  Input:    ${formatDisplay(res.input)}`, '#94a3b8');
		}

		if (res.expected && res.expected !== '[hidden]') {
			appendLine(terminal, `  Expected: ${formatDisplay(res.expected)}`, '#94a3b8');
		}

		if (!res.passed) {
			if (res.output !== null && res.output !== undefined && res.output !== '[hidden]') {
				appendLine(terminal, `  Output:   ${formatDisplay(res.output)}`, '#fbbf24');
			}
			if (res.error) {
				appendLine(terminal, `  Error:    ${res.error}`, '#ff6b6b');
			}
		}

		if (testNum < total) {
			appendLine(terminal, '  ─────────────────────────────', '#334155');
		}
	});

	appendLine(terminal, '');

	const color = passedCount === total ? '#00b894' : '#ff6b6b';
	appendLine(terminal, `$ Result: ${passedCount}/${total} tests passed.`, color);
}

function appendLine(terminal, text, color) {
	const line = document.createElement('div');
	line.textContent = text;
	if (color) line.style.color = color;
	line.style.fontFamily = "'Consolas', 'Courier New', monospace";
	line.style.fontSize = '13px';
	line.style.lineHeight = '1.6';
	line.style.whiteSpace = 'pre-wrap';
	line.style.wordBreak = 'break-all';
	terminal.appendChild(line);
}

function formatDisplay(value) {
	if (typeof value !== 'string') return String(value);
	try {
		const parsed = JSON.parse(value);
		return JSON.stringify(parsed);
	} catch {
		return value;
	}
}

function setButtonsDisabled(disabled) {
	document.querySelectorAll('.action-bar button').forEach(btn => {
		btn.disabled = disabled;
		btn.style.opacity = disabled ? '0.5' : '1';
	});
}