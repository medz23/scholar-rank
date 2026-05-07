let localStrikes = 0;

(async function loadStrikes() {
	try {
		const res = await fetch(window.API_URLS.getStrikes);
		if (res.ok) {
			const data = await res.json();
			localStrikes = data.strikes || 0;
			if (localStrikes >= 3) {
				lockScreen();
			}
		}
	} catch (e) {
		console.error("Failed to load strikes");
	}
})();

function enforceFullscreen() {
	document.documentElement.requestFullscreen().catch(err => {
		alert("You must allow fullscreen to take this exam.");
	});
}

function lockScreen() {
	document.body.innerHTML = `
        <div style='height: 100vh; background: #0f141e; display: flex; align-items: center; justify-content: center; flex-direction: column;'>
            <h1 style='color: #ff4757;'>Exam Terminated</h1>
            <p style='color: #cbd5e1;'>You left the environment too many times.</p>
        </div>
    `;
}

document.addEventListener("visibilitychange", async () => {
    if (document.visibilityState === 'hidden') {
        if (window.__intentionalNav) return;
        localStrikes++;

		try {
			const res = await fetch(window.API_URLS.logStrike, {method: 'POST'});
			if (res.ok) {
				const data = await res.json();
				localStrikes = data.strikes;
			}
		} catch (e) {
			console.error("Failed to log strike");
		}

		if (localStrikes >= 3) {
			lockScreen();
		} else {
			alert(`WARNING: You left the exam environment! Strike ${localStrikes}/3`);
		}
	}
});

['paste', 'copy', 'cut'].forEach(evt => {
	document.addEventListener(evt, (e) => {
		e.preventDefault();
		alert("Action Prohibited: Copying and Pasting are disabled during the exam.");
	});
});