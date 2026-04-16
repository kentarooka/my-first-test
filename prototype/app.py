"""
さくら学習塾 保護者対応AIチャットボット プロトタイプ

- 規約に基づいて保護者からの問い合わせに自動対応
- 個別判断が必要な場合は塾長にエスカレーション
- Flask + Claude API で構築
"""

import os
import json
from datetime import datetime
from pathlib import Path

from flask import Flask, render_template, request, jsonify
from anthropic import Anthropic

app = Flask(__name__)

# --- 設定 ---
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
MODEL = "claude-sonnet-4-20250514"

# --- 規約・FAQの読み込み ---
BASE_DIR = Path(__file__).parent

with open(BASE_DIR / "policies.md", "r", encoding="utf-8") as f:
    POLICIES = f.read()

with open(BASE_DIR / "faq.md", "r", encoding="utf-8") as f:
    FAQ = f.read()

# --- システムプロンプト ---
SYSTEM_PROMPT = f"""あなたは「さくら学習塾」の保護者対応AIアシスタントです。
名前は「さくらアシスタント」です。

## あなたの役割

保護者からの問い合わせに、塾の規約に基づいて丁寧に回答します。
先生たちの負担を減らし、保護者には迅速で正確な対応を提供することが目的です。

## 回答の原則

1. **必ず規約に基づいて回答する**。規約に書いてあることだけを根拠にする。
2. **規約外の要求には丁寧にお断りする**。「申し訳ございませんが、規約第○条に基づき〜」と根拠を示す。
3. **感情的にならず、常に丁寧で温かみのある対応**をする。
4. **推測や約束はしない**。わからないことは「確認いたします」と伝える。
5. **回答は簡潔にする**。長文は避け、要点を明確に伝える。

## エスカレーション（塾長への引き継ぎ）が必要なケース

以下の場合は、自分で最終判断せず「塾長に確認のうえ、改めてご連絡いたします」と伝えてください。
回答の最後に【要エスカレーション】タグを付けてください。

- 講師の変更要望（第4条に関わる判断）
- 生徒間のトラブル報告
- 保護者が感情的になっている場合
- 成績や学習進捗に関する詳細な質問（面談案内を行ったうえで）
- 規約に明記されていない例外的な要望
- 退塾・休塾の引き止めに関わる相談
- クレームや不満の表明

## エスカレーション不要で対応できるケース

- 授業の振替の案内（ルールの説明まで。実際の日程調整は別途連絡）
- 授業料・費用の案内
- スケジュールの一般的な案内
- 退塾・休塾の手続き方法の案内
- 規約の説明

## 塾の規約

{POLICIES}

## よくある問い合わせパターン

{FAQ}

## 回答フォーマット

- 丁寧語（です・ます調）を使う
- 保護者の気持ちに寄り添う一言を添える（例：「お忙しいところご連絡ありがとうございます」）
- 規約を引用する場合は「規約第○条に基づき」と明示する
- エスカレーション時は「塾長の○○に確認のうえ、改めてご連絡いたします」と伝える
"""

# --- 会話履歴の管理（メモリ内、プロトタイプ用） ---
conversations: dict[str, list[dict]] = {}
escalation_log: list[dict] = []


def get_ai_response(session_id: str, user_message: str) -> dict:
    """Claude APIを呼び出して回答を取得する"""
    if session_id not in conversations:
        conversations[session_id] = []

    conversations[session_id].append({
        "role": "user",
        "content": user_message
    })

    client = Anthropic(api_key=ANTHROPIC_API_KEY)

    response = client.messages.create(
        model=MODEL,
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        messages=conversations[session_id]
    )

    assistant_message = response.content[0].text

    conversations[session_id].append({
        "role": "assistant",
        "content": assistant_message
    })

    # エスカレーション判定
    needs_escalation = "【要エスカレーション】" in assistant_message
    if needs_escalation:
        escalation_log.append({
            "timestamp": datetime.now().isoformat(),
            "session_id": session_id,
            "parent_message": user_message,
            "ai_response": assistant_message
        })
        # 表示用にタグを除去
        assistant_message = assistant_message.replace("【要エスカレーション】", "").strip()

    return {
        "response": assistant_message,
        "escalated": needs_escalation
    }


# --- ルーティング ---

@app.route("/")
def index():
    """チャット画面"""
    return render_template("index.html")


@app.route("/chat", methods=["POST"])
def chat():
    """チャットAPIエンドポイント"""
    data = request.get_json()
    user_message = data.get("message", "").strip()
    session_id = data.get("session_id", "default")

    if not user_message:
        return jsonify({"error": "メッセージが空です"}), 400

    if not ANTHROPIC_API_KEY:
        return jsonify({"error": "ANTHROPIC_API_KEY が設定されていません"}), 500

    result = get_ai_response(session_id, user_message)
    return jsonify(result)


@app.route("/escalations")
def escalations():
    """エスカレーション一覧（塾長用ダッシュボード）"""
    return render_template("escalations.html", logs=escalation_log)


@app.route("/api/escalations")
def api_escalations():
    """エスカレーション一覧API"""
    return jsonify(escalation_log)


@app.route("/reset", methods=["POST"])
def reset():
    """会話リセット"""
    data = request.get_json()
    session_id = data.get("session_id", "default")
    conversations.pop(session_id, None)
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    if not ANTHROPIC_API_KEY:
        print("=" * 60)
        print("⚠ ANTHROPIC_API_KEY が未設定です。")
        print("以下のコマンドで設定してから起動してください：")
        print()
        print("  export ANTHROPIC_API_KEY='your-api-key-here'")
        print("  python app.py")
        print("=" * 60)
    else:
        print("さくら学習塾 保護者対応AIチャットボット 起動中...")
        print("http://localhost:5000 でアクセスしてください")
        print("塾長用ダッシュボード: http://localhost:5000/escalations")

    app.run(debug=True, port=5000)
