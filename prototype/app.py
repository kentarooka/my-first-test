"""
さくら学習塾 保護者対応AIチャットボット プロトタイプ

- 規約に基づいて保護者からの問い合わせに自動対応
- 個別判断が必要な場合は塾長にエスカレーション
- Flask + Claude API で構築
- APIキー未設定時はデモモードで動作
"""

import os
import re
from datetime import datetime
from pathlib import Path

from flask import Flask, render_template, request, jsonify

app = Flask(__name__)

# --- 設定 ---
MODEL = "claude-sonnet-4-20250514"
DEMO_MODE = not os.environ.get("ANTHROPIC_API_KEY")

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

# --- デモモード用の定型応答 ---
DEMO_RESPONSES = {
    "振替": {
        "response": (
            "ご連絡ありがとうございます。\n\n"
            "授業の振替についてご案内いたします。\n\n"
            "規約第2条に基づき、以下のルールとなっております。\n\n"
            "・振替は月2回まで可能です\n"
            "・授業日の前日18:00までにご連絡ください\n"
            "・当日のご連絡の場合は振替不可となります\n"
            "・欠席日から1ヶ月以内に振替を実施してください\n\n"
            "振替先の曜日・時間は空き状況に応じてご案内いたします。"
            "ご希望の日時がございましたらお知らせください。"
        ),
        "escalated": False
    },
    "授業料|費用|料金|いくら|月謝": {
        "response": (
            "お問い合わせありがとうございます。\n\n"
            "規約第1条に基づき、月額授業料は以下のとおりです。\n\n"
            "【小学生コース】\n"
            "・週1回：月額 12,000円\n"
            "・週2回：月額 20,000円\n\n"
            "【中学生コース】\n"
            "・週1回：月額 18,000円\n"
            "・週2回：月額 30,000円\n"
            "・週3回：月額 40,000円\n\n"
            "【高校生コース】\n"
            "・週1回：月額 22,000円\n"
            "・週2回：月額 38,000円\n\n"
            "入塾金は15,000円です（兄弟姉妹の2人目以降は免除）。\n"
            "教材費は半期ごとに5,000円〜10,000円を別途いただいております。"
        ),
        "escalated": False
    },
    "退塾|やめたい|退会": {
        "response": (
            "ご連絡いただきありがとうございます。\n\n"
            "退塾の手続きについてご案内いたします。\n\n"
            "規約第3条に基づき、退塾をご希望の場合は、退塾希望月の前月15日までに「退塾届」をご提出ください。\n\n"
            "例：3月末で退塾をご希望の場合 → 2月15日までにご提出\n\n"
            "期日を過ぎた場合は、翌月分の授業料が発生いたしますのでご注意ください。\n\n"
            "退塾届は塾の受付にてお渡ししております。"
        ),
        "escalated": False
    },
    "休塾|休み|休ませたい": {
        "response": (
            "ご連絡ありがとうございます。\n\n"
            "休塾についてご案内いたします。\n\n"
            "規約第3条に基づき、休塾をご希望の場合は以下の手続きとなります。\n\n"
            "・休塾届をご提出ください\n"
            "・休塾期間中は月額3,000円の在籍維持費がかかります\n"
            "・休塾期間は最長3ヶ月です\n"
            "・3ヶ月を超える場合は一度退塾の扱いとなります\n"
            "・復帰時に入塾金は不要です\n\n"
            "休塾届は塾の受付にてお渡ししております。"
        ),
        "escalated": False
    },
    "補習|追加.*授業|特別": {
        "response": (
            "お問い合わせありがとうございます。\n\n"
            "追加授業・補習についてご案内いたします。\n\n"
            "規約第5条に基づき、定期テスト前の特別補習は塾の判断で無料実施する場合がございます（任意参加）。\n\n"
            "通常授業以外の追加授業をご希望の場合は、以下の追加料金が発生いたします。\n\n"
            "・小学生：1コマ 3,000円\n"
            "・中学生：1コマ 4,000円\n"
            "・高校生：1コマ 5,000円\n\n"
            "なお、講師の空き状況によりご希望に添えない場合がございます。\n"
            "「毎日」「無料で」といった規約外のご要望には対応いたしかねますのでご了承ください。"
        ),
        "escalated": False
    },
    "先生.*変え|講師.*変更|担当.*変え": {
        "response": (
            "ご相談いただきありがとうございます。\n"
            "お子さまのことを思ってのことと存じます。\n\n"
            "規約第4条に基づき、講師の配置は生徒の学力・性格を考慮して塾側で決定しております。"
            "保護者の方からの講師の指名・変更のご要望には原則としてお応えしておりません。\n\n"
            "ただし、お子さまとの相性に著しい問題がある場合は、塾長が状況を確認のうえ対応いたします。\n\n"
            "この件につきましては、塾長に確認のうえ、改めてご連絡いたします。"
        ),
        "escalated": True
    },
    "いじ|トラブル|けんか|喧嘩|意地悪": {
        "response": (
            "ご心配をおかけしており申し訳ございません。\n"
            "お子さまの安全は最優先事項です。\n\n"
            "こちらの件は、塾長が直接状況を確認し対応いたします。\n\n"
            "塾長に確認のうえ、改めてご連絡いたします。\n"
            "詳しい状況（いつ頃から、どのようなことがあったか）を教えていただけると、"
            "より迅速に対応できます。"
        ),
        "escalated": True
    },
    "値下げ|安く|高い|割引|払いたくない": {
        "response": (
            "ご連絡ありがとうございます。\n\n"
            "授業料につきましては、規約第1条に定められた料金体系にて"
            "すべての生徒の皆さまに公平にご案内しております。\n\n"
            "個別の値下げ・割引には対応いたしかねますので、何卒ご理解ください。\n\n"
            "なお、兄弟姉妹でご通塾の場合は、2人目以降の入塾金が免除となります。\n\n"
            "ご不明な点がございましたら、お気軽にお問い合わせください。"
        ),
        "escalated": False
    },
}

DEMO_DEFAULT = {
    "response": (
        "お問い合わせありがとうございます。\n\n"
        "いただいたご質問の内容を確認いたします。\n"
        "塾長に確認のうえ、改めてご連絡いたします。\n\n"
        "お急ぎの場合は、お電話（000-0000-0000）にてお問い合わせください。"
    ),
    "escalated": True
}


def get_demo_response(user_message: str) -> dict:
    """デモモード：キーワードマッチで定型応答を返す"""
    for pattern, resp in DEMO_RESPONSES.items():
        if re.search(pattern, user_message):
            return dict(resp)
    return dict(DEMO_DEFAULT)


# --- 会話履歴の管理（メモリ内、プロトタイプ用） ---
conversations: dict[str, list[dict]] = {}
escalation_log: list[dict] = []


def get_ai_response(session_id: str, user_message: str) -> dict:
    """Claude APIを呼び出して回答を取得する"""
    from anthropic import Anthropic

    if session_id not in conversations:
        conversations[session_id] = []

    conversations[session_id].append({
        "role": "user",
        "content": user_message
    })

    client = Anthropic()

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
        # 表示用にタグを除去
        assistant_message = assistant_message.replace("【要エスカレーション】", "").strip()

    return {
        "response": assistant_message,
        "escalated": needs_escalation
    }


def handle_message(session_id: str, user_message: str) -> dict:
    """メッセージ処理の統合エントリポイント"""
    if DEMO_MODE:
        result = get_demo_response(user_message)
    else:
        result = get_ai_response(session_id, user_message)

    # エスカレーションログに記録
    if result["escalated"]:
        escalation_log.append({
            "timestamp": datetime.now().isoformat(),
            "session_id": session_id,
            "parent_message": user_message,
            "ai_response": result["response"]
        })

    return result


# --- ルーティング ---

@app.route("/")
def index():
    """チャット画面"""
    return render_template("index.html", demo_mode=DEMO_MODE)


@app.route("/chat", methods=["POST"])
def chat():
    """チャットAPIエンドポイント"""
    data = request.get_json()
    user_message = data.get("message", "").strip()
    session_id = data.get("session_id", "default")

    if not user_message:
        return jsonify({"error": "メッセージが空です"}), 400

    try:
        result = handle_message(session_id, user_message)
    except Exception as e:
        return jsonify({"error": f"エラーが発生しました: {e}"}), 500
    return jsonify(result)


@app.route("/escalations")
def escalations():
    """エスカレーション一覧（塾長用ダッシュボード）"""
    return render_template("escalations.html", logs=escalation_log, demo_mode=DEMO_MODE)


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
    print("さくら学習塾 保護者対応AIチャットボット 起動中...")
    if DEMO_MODE:
        print("[デモモード] APIキー未設定のため、定型応答で動作します")
        print("  本番モード: export ANTHROPIC_API_KEY='your-key' を設定して再起動")
    print(f"チャット画面: http://localhost:5000")
    print(f"塾長用ダッシュボード: http://localhost:5000/escalations")
    app.run(debug=False, port=5000)
