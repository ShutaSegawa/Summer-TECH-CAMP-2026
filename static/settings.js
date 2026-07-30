// APIキー設定画面のプログラム

const fields = ["openai", "gemini", "claude"];

// 現在の設定状況を表示（キー本体は伏せ字で表示される）
async function loadStatus() {
  const res = await fetch("/api/config");
  const data = await res.json();
  for (const p of fields) {
    const status = document.getElementById(`${p}-status`);
    const masked = data[`${p}_api_key`];
    if (masked) {
      status.textContent = `✅ 設定済み（${masked}）`;
    } else {
      status.textContent = "未設定";
      status.style.color = "#999";
    }
  }
}

document.getElementById("save-button").addEventListener("click", async () => {
  const body = {};
  for (const p of fields) {
    const value = document.getElementById(`${p}-key`).value.trim();
    if (value) body[`${p}_api_key`] = value;
  }
  const res = await fetch("/api/config", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const msg = document.getElementById("save-message");
  if (res.ok) {
    msg.textContent = "保存しました！";
    for (const p of fields) document.getElementById(`${p}-key`).value = "";
    loadStatus();
    setTimeout(() => (msg.textContent = ""), 3000);
  } else {
    msg.textContent = "保存に失敗しました";
    msg.style.color = "#ea4335";
  }
});

loadStatus();
