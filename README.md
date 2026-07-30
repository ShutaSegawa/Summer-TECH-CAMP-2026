# SummerTECH-CAMP 2026 音声対話システム

高校生向け実習（2日間）で使用する、ブラウザで動く音声対話システムです。
マイクに話しかけると、リアルタイムで音声認識され、選んだAIが返事をして、合成音声で読み上げます。

[Summer-TECH-CAMP2024版](https://github.com/odakazu66/Summer-TECH-CAMP2024) を全面リニューアルしたものです。

## 特徴

- **UIはGoogle Chrome**（Pythonサーバー + Webブラウザ構成）
- **リアルタイム音声認識**：ChromeのWeb Speech APIを使用（APIキー不要・認識の途中結果も画面に表示）
- **AIをプルダウンで切替**：OpenAI (GPT) / Google Gemini / Anthropic Claude / 内蔵簡易AI（キー不要）
- **音声合成**：VOICEVOX（ずんだもん等）/ gTTS（キー不要）
- **プロンプト（AIへの指示）を画面上で自由に編集**して、AIの性格を変えられる
- APIキーは別画面（設定画面）または `config.json` で管理

## 必要なもの

- Google Chrome
- Python 3.10以上
- （VOICEVOXの声を使う場合）[VOICEVOX](https://voicevox.hiroshiba.jp/) アプリ
- （GPT/Gemini/Claudeを使う場合）各サービスのAPIキー。内蔵簡易AIはキーなしで動きます

## インストール

```bash
git clone https://github.com/sayonari/SummerTECH-CAMP-2026-voice-dialogue.git
cd SummerTECH-CAMP-2026-voice-dialogue
pip install -r requirements.txt
```

## 使い方

```bash
python server.py
```

起動したら、**Google Chrome** で http://localhost:5001 を開きます。

1. 画面右上の「⚙️ APIキー設定」からAPIキーを登録（内蔵簡易AIだけ使うなら不要）
2. 左パネルで「使うAI」「モデル」「音声合成エンジン」を選ぶ
3. 「プロンプト」欄でAIの性格を自由に書き換える
4. 🎤 マイクONボタンを押して話しかける（またはテキスト入力欄から送信）

APIキーは設定画面のかわりに、`config.example.json` を `config.json` にコピーして直接書き込むこともできます。

## 会話履歴

会話は `conversation.json` に保存されます。画面の「🗑️ 会話をリセット」ボタンで消去できます。

## 注意

- APIキーは絶対に公開しないでください（`config.json` はGit管理対象外になっています）
- 音声認識はChromeのWeb Speech APIを使うため、ブラウザはGoogle Chromeを使用してください

## ライセンス

MIT License
