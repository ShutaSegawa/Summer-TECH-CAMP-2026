// SummerTECH-CAMP 2026 音声対話システム（ブラウザ側プログラム）
//
// 役割：
//  - ChromeのWeb Speech APIでリアルタイム音声認識（途中結果も画面に表示）
//  - 確定した発話をサーバー(/api/chat)に送り、AIの返事をもらう
//  - 返事をサーバー(/api/tts)で音声合成して再生（再生中は認識を一時停止）

// ---------- 画面の部品 ----------
// SPEECH_MODEがfalse（テキスト専用モード）のときは、AI/TTSの選択やマイク関連の
// 要素はそもそもHTMLに存在しない（index.htmlのJinja条件分岐で描画されない）
const providerSelect = document.getElementById("provider-select");
const modelSelect = document.getElementById("model-select");
const systemPrompt = document.getElementById("system-prompt");
const ttsSelect = document.getElementById("tts-select");
const speakerSelect = document.getElementById("speaker-select");
const speakerRow = document.getElementById("voicevox-speaker-row");
const chatArea = document.getElementById("chat-area");
const interimArea = document.getElementById("interim-area");
const interimText = document.getElementById("interim-text");
const statusBar = document.getElementById("status-bar");
const micButton = document.getElementById("mic-button");
const textInput = document.getElementById("text-input");
const sendButton = document.getElementById("send-button");
const resetButton = document.getElementById("reset-button");

// ---------- 状態 ----------
let micOn = false;          // ユーザーがマイクをONにしているか
let recognizing = false;    // 音声認識が実際に動いているか
let speaking = false;       // AIの声を再生中か（再生中は認識を止める）
let currentAudio = null;

// ---------- AIプルダウンの初期化 ----------
// （テキスト専用モードではAI/TTSの選択UIごと非表示なので、この初期化は不要）
if (SPEECH_MODE) {
  const updateModelSelect = () => {
    const provider = providerSelect.value;
    const models = AI_PROVIDERS[provider].models;
    modelSelect.innerHTML = "";
    for (const m of models) {
      const opt = document.createElement("option");
      opt.value = m;
      opt.textContent = m;
      modelSelect.appendChild(opt);
    }
  };
  providerSelect.addEventListener("change", updateModelSelect);
  updateModelSelect();

  // TTSエンジンの切替（VOICEVOX以外のときは話者選択を隠す）
  const updateTtsRow = () => {
    speakerRow.style.display = ttsSelect.value === "voicevox" ? "" : "none";
  };
  ttsSelect.addEventListener("change", updateTtsRow);
  updateTtsRow();
}

// ---------- 会話表示 ----------
function addBubble(who, text) {
  const welcome = chatArea.querySelector(".welcome-message");
  if (welcome) welcome.remove();

  const row = document.createElement("div");
  row.className = "message-row " + who;

  if (who === "ai") {
    const avatar = document.createElement("div");
    avatar.className = "avatar";
    if (PROFILE.system_icon_url) {
      const img = document.createElement("img");
      img.src = PROFILE.system_icon_url;
      img.alt = "";
      avatar.appendChild(img);
    } else {
      avatar.textContent = PROFILE.system_icon;
    }
    row.appendChild(avatar);
  }

  const div = document.createElement("div");
  div.className = "bubble " + who;
  const label = document.createElement("span");
  label.className = "who";
  label.textContent = who === "user" ? PROFILE.user_name : who === "ai" ? PROFILE.system_name : "エラー";
  div.appendChild(label);
  div.appendChild(document.createTextNode(text));
  row.appendChild(div);

  chatArea.appendChild(row);
  chatArea.scrollTop = chatArea.scrollHeight;
}

function setStatus(msg) {
  statusBar.textContent = msg;
}

// ---------- 音声認識（Web Speech API） ----------
// テキスト専用モードではマイクボタンごとHTMLに存在しないため、音声認識まわりは
// SPEECH_MODEのときだけ初期化する
let recognition = null;
let startRecognition = () => {};
let stopRecognition = () => {};

if (SPEECH_MODE) {
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;

  if (!SpeechRecognition) {
    micButton.disabled = true;
    setStatus("⚠️ このブラウザは音声認識に対応していません。Google Chromeを使ってください。");
  } else {
    recognition = new SpeechRecognition();
    recognition.lang = "ja-JP";
    recognition.continuous = true;      // 話し続けても認識を続ける
    recognition.interimResults = true;  // 途中結果もリアルタイムに受け取る

    recognition.onstart = () => {
      recognizing = true;
      setStatus("🎙️ 聞き取り中… 話しかけてください");
    };

    recognition.onresult = (event) => {
      let interim = "";
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const result = event.results[i];
        if (result.isFinal) {
          const text = result[0].transcript.trim();
          interimText.textContent = "";
          interimArea.hidden = true;
          if (text) sendMessage(text);
        } else {
          interim += result[0].transcript;
        }
      }
      if (interim) {
        // 認識の途中結果をリアルタイム表示
        interimArea.hidden = false;
        interimText.textContent = interim;
      }
    };

    recognition.onerror = (event) => {
      if (event.error === "not-allowed") {
        setStatus("⚠️ マイクの使用が許可されていません。アドレスバーのマイクアイコンから許可してください。");
        micOn = false;
        updateMicButton();
      } else if (event.error !== "no-speech" && event.error !== "aborted") {
        setStatus("⚠️ 音声認識エラー: " + event.error);
      }
    };

    recognition.onend = () => {
      recognizing = false;
      // マイクONのままなら自動で再開（AIの声の再生中は再開しない）
      if (micOn && !speaking) {
        try { recognition.start(); } catch (e) { /* すでに開始済みなら無視 */ }
      }
    };
  }

  startRecognition = () => {
    if (recognition && !recognizing && !speaking) {
      try { recognition.start(); } catch (e) { /* すでに開始済みなら無視 */ }
    }
  };

  stopRecognition = () => {
    if (recognition && recognizing) {
      recognition.stop();
    }
    interimArea.hidden = true;
    interimText.textContent = "";
  };

  const updateMicButton = () => {
    if (micOn) {
      micButton.classList.add("recording");
      micButton.textContent = "⏹ マイクOFF";
    } else {
      micButton.classList.remove("recording");
      micButton.textContent = "🎤 マイクON";
      setStatus("");
    }
  };

  micButton.addEventListener("click", () => {
    micOn = !micOn;
    updateMicButton();
    if (micOn) {
      startRecognition();
    } else {
      stopRecognition();
    }
  });
}

// ---------- AIとの会話 ----------
async function sendMessage(text) {
  addBubble("user", text);
  setStatus("🤖 AIが考え中…");

  try {
    const body = { text: text, system_prompt: systemPrompt.value };
    if (SPEECH_MODE) {
      body.provider = providerSelect.value;
      body.model = modelSelect.value;
    }
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await res.json();
    if (!res.ok) {
      addBubble("error", data.error || "サーバーエラーが発生しました");
      setStatus("");
      return;
    }
    addBubble("ai", data.reply);
    setStatus("");
    if (SPEECH_MODE) await speak(data.reply);
  } catch (e) {
    addBubble("error", "サーバーに接続できません: " + e.message);
    setStatus("");
  }
}

// ---------- 音声合成（サーバー側TTS） ----------
// 返事を文単位に分割し、1文目の再生中に2文目以降を裏で合成しておくことで
// 「話し始めるまでの待ち時間」を短縮する（句点・感嘆符・疑問符・改行で区切る）
function splitSentences(text) {
  return text
    .split(/(?<=[。！？\n])/)
    .map((s) => s.trim())
    .filter((s) => s.length > 0);
}

async function fetchTtsAudio(text, engine, speaker) {
  const res = await fetch("/api/tts", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text: text, engine: engine, speaker: speaker }),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.error || "音声合成に失敗しました");
  }
  const blob = await res.blob();
  return URL.createObjectURL(blob);
}

async function speak(text) {
  const engine = ttsSelect.value;
  if (engine === "none") return;

  const sentences = splitSentences(text);
  if (sentences.length === 0) return;
  const speaker = speakerSelect.value;

  // エコー対策：AIの声をマイクが拾わないよう、再生中は認識を止める
  speaking = true;
  stopRecognition();
  setStatus("🔊 AIが話しています…");

  try {
    let nextAudio = fetchTtsAudio(sentences[0], engine, speaker);
    for (let i = 0; i < sentences.length; i++) {
      const url = await nextAudio;
      // 次の文の合成を裏で開始しておく（最後の文なら不要）
      nextAudio = i + 1 < sentences.length ? fetchTtsAudio(sentences[i + 1], engine, speaker) : null;
      await playAudio(url);
    }
  } catch (e) {
    addBubble("error", "音声合成に失敗しました: " + e.message);
  } finally {
    speaking = false;
    setStatus("");
    if (micOn) startRecognition();  // マイクONなら認識を再開
  }
}

function playAudio(url) {
  return new Promise((resolve) => {
    currentAudio = new Audio(url);
    currentAudio.onended = () => { URL.revokeObjectURL(url); resolve(); };
    currentAudio.onerror = () => { URL.revokeObjectURL(url); resolve(); };
    currentAudio.play().catch(() => resolve());
  });
}

// ---------- キーボード入力 ----------
function sendFromInput() {
  const text = textInput.value.trim();
  if (!text) return;
  textInput.value = "";
  sendMessage(text);
}

sendButton.addEventListener("click", sendFromInput);
textInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.isComposing) sendFromInput();
});

// ---------- リセット ----------
resetButton.addEventListener("click", async () => {
  if (!confirm("会話の履歴をすべて消しますか？")) return;
  await fetch("/api/reset", { method: "POST" });
  const message = SPEECH_MODE
    ? "会話をリセットしました。マイクボタン🎤を押して話しかけてみよう！"
    : "会話をリセットしました。下の入力欄からメッセージを送ってみよう！";
  chatArea.innerHTML = `<div class="welcome-message">${message}</div>`;
});

// ---------- 起動時：過去の会話履歴を読み込む ----------
async function loadHistory() {
  try {
    const res = await fetch("/api/history");
    const data = await res.json();
    for (const m of data.messages || []) {
      addBubble(m.role === "user" ? "user" : "ai", m.content);
    }
  } catch (e) { /* 履歴がなくても問題なし */ }
}
loadHistory();
