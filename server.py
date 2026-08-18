# -*- coding: utf-8 -*-
"""
SummerTECH-CAMP 2026 音声対話システム サーバー

- ブラウザ(Chrome)がUI。音声認識はブラウザ側の Web Speech API で行う
- このサーバーは「AIへの問い合わせ」「会話履歴の保存」「音声合成(TTS)」を担当する
- 起動方法:  python server.py  →  http://localhost:5001 をChromeで開く
"""

import argparse
import io
import json
import os

import requests
from flask import Flask, jsonify, render_template, request, send_file, send_from_directory

app = Flask(__name__)

# ----------------------------------------------------------------------
# 起動オプション
#   --speech : 音声入出力＋全カスタマイズ機能を使えるモード（従来の動作）
#   --admin  : APIキー設定画面を表示するモード（生徒に配るPCでは付けない）
#   何も付けない場合はテキスト入力のみのモードで、LLMはGPT固定・音声合成なし
# ----------------------------------------------------------------------
def parse_args():
    parser = argparse.ArgumentParser(description="SummerTECH-CAMP 2026 音声対話システム")
    parser.add_argument("--speech", action="store_true", help="音声入出力とAI/TTSのカスタマイズを有効にする")
    parser.add_argument("--admin", action="store_true", help="APIキー設定画面を有効にする")
    return parser.parse_args()


_args = parse_args()
SPEECH_MODE = _args.speech
ADMIN_MODE = _args.admin
DEFAULT_TEXT_ONLY_MODEL = "gpt-5.4-nano"

# ファイルの置き場所（このファイルと同じフォルダ）
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
CONVERSATION_PATH = os.path.join(BASE_DIR, "conversation.json")
ICON_DIR = os.path.join(BASE_DIR, "images")
ICON_EXTENSIONS = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg")

# VOICEVOXエンジンのアドレス（VOICEVOXアプリを起動しておくと使える）
VOICEVOX_URL = "http://127.0.0.1:50021"

# プロフィール（システム側の名前・アイコン、ユーザー側の名前）の初期値
DEFAULT_PROFILE = {
    "system_name": "AI",
    "system_icon": "🤖",
    "user_name": "あなた",
}

# 利用できるAIとモデルの一覧（プルダウンに表示される。先頭がデフォルト選択）
AI_PROVIDERS = {
    "openai": {
        "label": "OpenAI (GPT)",
        "models": ["gpt-5.4-nano"],
    },
    "gemini": {
        "label": "Google Gemini",
        "models": ["gemini-3.1-flash-lite"],
    },
    "claude": {
        "label": "Anthropic Claude",
        "models": ["claude-haiku-4-5"],
    },
    "simple": {
        "label": "内蔵簡易AI（APIキー不要）",
        "models": ["pattern-bot"],
    },
}


# ----------------------------------------------------------------------
# 設定ファイル（APIキー）の読み書き
# ----------------------------------------------------------------------
def load_config():
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_config(config):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


def get_api_key(provider):
    """設定ファイル → 環境変数 の順でAPIキーを探す"""
    config = load_config()
    env_names = {
        "openai": "OPENAI_API_KEY",
        "gemini": "GEMINI_API_KEY",
        "claude": "ANTHROPIC_API_KEY",
    }
    key = config.get(f"{provider}_api_key", "")
    if not key and provider in env_names:
        key = os.environ.get(env_names[provider], "")
    return key


def get_profile():
    """システム側の名前・アイコン、ユーザー側の名前を取得（未設定なら初期値）"""
    config = load_config()
    profile = dict(DEFAULT_PROFILE)
    for key in DEFAULT_PROFILE:
        value = (config.get(key) or "").strip()
        if value:
            profile[key] = value
    return profile


def list_icon_images():
    """images/ に置かれた画像ファイル名の一覧（アイコン選択肢）"""
    if not os.path.isdir(ICON_DIR):
        return []
    return sorted(
        f for f in os.listdir(ICON_DIR)
        if f.lower().endswith(ICON_EXTENSIONS)
    )


def resolve_system_icon_url(icon_value):
    """system_iconの値がimages内の画像ファイル名なら配信用URLを返す（絵文字ならNone）"""
    if icon_value in list_icon_images():
        return f"/images/{icon_value}"
    return None


# ----------------------------------------------------------------------
# 会話履歴の読み書き（conversation.json）
# ----------------------------------------------------------------------
def load_conversation():
    if os.path.exists(CONVERSATION_PATH):
        try:
            with open(CONVERSATION_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data.get("messages"), list):
                return data
        except (json.JSONDecodeError, OSError):
            pass
    return {"messages": []}


def save_conversation(data):
    with open(CONVERSATION_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ----------------------------------------------------------------------
# 内蔵簡易AI（APIキーなしで動くパターン応答ボット）
# ----------------------------------------------------------------------
def simple_ai_reply(text):
    """キーワードに反応して返事をする簡単なチャットボット"""
    rules = [
        (["こんにちは", "こんにちわ"], "こんにちは！今日はどんなことを話しましょうか？"),
        (["おはよう"], "おはようございます！今日も元気にいきましょう！"),
        (["こんばんは"], "こんばんは！夜はゆっくり過ごせていますか？"),
        (["ありがとう"], "どういたしまして！お役に立ててうれしいです。"),
        (["名前"], "わたしはSummerTECH-CAMPの簡易対話ボットです。よろしくね！"),
        (["天気"], "ごめんなさい、わたしは天気を調べられません。窓の外を見てみてください！"),
        (["好き"], "いいですね！わたしはおしゃべりが好きです。"),
        (["疲れ"], "おつかれさまです。少し休憩しましょう！"),
        (["さようなら", "バイバイ", "ばいばい"], "さようなら！また話しかけてくださいね。"),
        (["音声認識"], "音声認識はChromeのWeb Speech APIを使っています。すごい技術ですよね！"),
        (["AI", "人工知能", "えーあい"], "AIについて興味があるんですね！プルダウンから本物のAIにも切り替えられますよ。"),
    ]
    for keywords, reply in rules:
        if any(k in text for k in keywords):
            return reply
    if text.endswith("？") or text.endswith("?") or "何" in text or "どう" in text:
        return f"「{text}」…いい質問ですね！わたしは簡易ボットなので、くわしくは本物のAIに聞いてみてください。"
    return f"「{text}」なんですね。もっと聞かせてください！"


# ----------------------------------------------------------------------
# 各AIサービスへの問い合わせ
# ----------------------------------------------------------------------
def chat_with_openai(messages, system_prompt, model):
    api_key = get_api_key("openai")
    if not api_key:
        raise RuntimeError("OpenAIのAPIキーが設定されていません（設定画面から登録してください）")
    payload = {
        "model": model,
        "messages": [{"role": "system", "content": system_prompt}] + messages,
    }
    res = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {api_key}"},
        json=payload,
        timeout=60,
    )
    res.raise_for_status()
    return res.json()["choices"][0]["message"]["content"]


def chat_with_gemini(messages, system_prompt, model):
    api_key = get_api_key("gemini")
    if not api_key:
        raise RuntimeError("GeminiのAPIキーが設定されていません（設定画面から登録してください）")
    contents = []
    for m in messages:
        role = "user" if m["role"] == "user" else "model"
        contents.append({"role": role, "parts": [{"text": m["content"]}]})
    payload = {
        "system_instruction": {"parts": [{"text": system_prompt}]},
        "contents": contents,
    }
    res = requests.post(
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
        headers={"x-goog-api-key": api_key},
        json=payload,
        timeout=60,
    )
    res.raise_for_status()
    return res.json()["candidates"][0]["content"]["parts"][0]["text"]


def chat_with_claude(messages, system_prompt, model):
    api_key = get_api_key("claude")
    if not api_key:
        raise RuntimeError("ClaudeのAPIキーが設定されていません（設定画面から登録してください）")
    import anthropic

    client = anthropic.Anthropic(api_key=api_key)
    response = client.messages.create(
        model=model,
        max_tokens=2048,
        system=system_prompt,
        messages=messages,
    )
    if response.stop_reason == "refusal":
        return "（この話題にはお答えできません。別の話題でお話ししましょう）"
    return "".join(b.text for b in response.content if b.type == "text")


# ----------------------------------------------------------------------
# Webページ
# ----------------------------------------------------------------------
@app.route("/")
def index():
    profile = get_profile()
    profile["system_icon_url"] = resolve_system_icon_url(profile["system_icon"])
    return render_template(
        "index.html",
        providers=AI_PROVIDERS,
        profile=profile,
        speech_mode=SPEECH_MODE,
        admin_mode=ADMIN_MODE,
    )


@app.route("/settings")
def settings():
    return render_template("settings.html", speech_mode=SPEECH_MODE, admin_mode=ADMIN_MODE)


# ----------------------------------------------------------------------
# API：会話
# ----------------------------------------------------------------------
@app.route("/api/chat", methods=["POST"])
def api_chat():
    data = request.get_json()
    text = (data.get("text") or "").strip()
    provider = data.get("provider", "openai")
    model = data.get("model", "")
    default_prompt = (
        "あなたには感情がありません. 事実だけを淡々と述べて会話してください。返事は50文字以内で短く話してください。"
        if SPEECH_MODE
        else "あなたは高校生と楽しく会話するアシスタントです。返事は50文字以内で短く話してください。"
    )
    system_prompt = (data.get("system_prompt") or "").strip() or default_prompt

    if not SPEECH_MODE:
        # テキスト専用モードではLLMをGPT固定にする（クライアントからの指定は無視）
        provider = "openai"
        model = DEFAULT_TEXT_ONLY_MODEL

    if not text:
        return jsonify({"error": "テキストが空です"}), 400

    conv = load_conversation()
    conv["messages"].append({"role": "user", "content": text})
    # APIに送る履歴（長くなりすぎないよう直近20件まで）
    history = conv["messages"][-20:]

    try:
        if provider == "openai":
            reply = chat_with_openai(history, system_prompt, model or "gpt-5.4-nano")
        elif provider == "gemini":
            reply = chat_with_gemini(history, system_prompt, model or "gemini-3.1-flash-lite")
        elif provider == "claude":
            reply = chat_with_claude(history, system_prompt, model or "claude-haiku-4-5")
        else:
            reply = simple_ai_reply(text)
    except Exception as e:
        conv["messages"].pop()  # 失敗したらユーザー発話を履歴から取り消す
        return jsonify({"error": str(e)}), 500

    conv["messages"].append({"role": "assistant", "content": reply})
    save_conversation(conv)
    return jsonify({"reply": reply})


@app.route("/api/history", methods=["GET"])
def api_history():
    return jsonify(load_conversation())


@app.route("/api/reset", methods=["POST"])
def api_reset():
    save_conversation({"messages": []})
    return jsonify({"ok": True})


# ----------------------------------------------------------------------
# API：音声合成（TTS）
# ----------------------------------------------------------------------
@app.route("/api/tts", methods=["POST"])
def api_tts():
    if not SPEECH_MODE:
        return jsonify({"error": "この起動モードでは音声合成は利用できません"}), 403

    data = request.get_json()
    text = (data.get("text") or "").strip()
    engine = data.get("engine", "gtts")
    if not text:
        return jsonify({"error": "テキストが空です"}), 400

    try:
        if engine == "voicevox":
            speaker = int(data.get("speaker", 3))  # 3 = ずんだもん（ノーマル）
            query = requests.post(
                f"{VOICEVOX_URL}/audio_query",
                params={"text": text, "speaker": speaker},
                timeout=30,
            )
            query.raise_for_status()
            audio = requests.post(
                f"{VOICEVOX_URL}/synthesis",
                params={"speaker": speaker},
                json=query.json(),
                timeout=60,
            )
            audio.raise_for_status()
            return send_file(io.BytesIO(audio.content), mimetype="audio/wav")
        else:  # gtts
            from gtts import gTTS

            buf = io.BytesIO()
            gTTS(text=text, lang="ja").write_to_fp(buf)
            buf.seek(0)
            return send_file(buf, mimetype="audio/mpeg")
    except requests.exceptions.ConnectionError:
        return jsonify({"error": "VOICEVOXエンジンに接続できません。VOICEVOXアプリを起動してください"}), 500
    except Exception as e:
        return jsonify({"error": f"音声合成に失敗しました: {e}"}), 500


# ----------------------------------------------------------------------
# API：設定（APIキー）
# ----------------------------------------------------------------------
def mask_key(key):
    """キーの一部だけ見せる（例：sk-a****23）"""
    if not key:
        return ""
    if len(key) <= 8:
        return "****"
    return key[:4] + "****" + key[-2:]


@app.route("/api/config", methods=["GET"])
def api_config_get():
    if not ADMIN_MODE:
        return jsonify({"error": "この機能は現在無効です"}), 403

    config = load_config()
    return jsonify({
        "openai_api_key": mask_key(get_api_key("openai")),
        "gemini_api_key": mask_key(get_api_key("gemini")),
        "claude_api_key": mask_key(get_api_key("claude")),
        "saved_in_file": {
            "openai": bool(config.get("openai_api_key")),
            "gemini": bool(config.get("gemini_api_key")),
            "claude": bool(config.get("claude_api_key")),
        },
    })


@app.route("/api/config", methods=["POST"])
def api_config_post():
    if not ADMIN_MODE:
        return jsonify({"error": "この機能は現在無効です"}), 403

    data = request.get_json()
    config = load_config()
    for provider in ("openai", "gemini", "claude"):
        key_name = f"{provider}_api_key"
        value = data.get(key_name)
        if value is not None and value != "":
            config[key_name] = value.strip()
        if data.get(f"clear_{provider}"):
            config.pop(key_name, None)
    save_config(config)
    return jsonify({"ok": True})


# ----------------------------------------------------------------------
# API：設定（プロフィール = システム側の名前・アイコン、ユーザー側の名前）
# ----------------------------------------------------------------------
@app.route("/api/profile", methods=["GET"])
def api_profile_get():
    return jsonify(get_profile())


@app.route("/api/icons", methods=["GET"])
def api_icons_get():
    """images/ に置かれているアイコン用画像ファイルの一覧"""
    return jsonify(list_icon_images())


@app.route("/images/<path:filename>")
def serve_icon_image(filename):
    """images/ に置かれたアイコン用画像ファイルを配信する"""
    return send_from_directory(ICON_DIR, filename)


@app.route("/api/profile", methods=["POST"])
def api_profile_post():
    if not SPEECH_MODE:
        return jsonify({"error": "この機能は現在無効です"}), 403

    data = request.get_json()
    config = load_config()
    for key in DEFAULT_PROFILE:
        if key in data:
            value = (data.get(key) or "").strip()
            if value:
                config[key] = value
            else:
                config.pop(key, None)
    save_config(config)
    return jsonify(get_profile())


if __name__ == "__main__":
    print("=" * 50)
    print(" SummerTECH-CAMP 2026 音声対話システム")
    print(f" モード: {'音声対話（--speech）' if SPEECH_MODE else 'テキスト専用（デフォルト）'} / 管理者機能: {'有効（--admin）' if ADMIN_MODE else '無効'}")
    print(" Chromeで http://localhost:5001 を開いてください")
    print("=" * 50)
    app.run(host="127.0.0.1", port=5001, debug=True)
