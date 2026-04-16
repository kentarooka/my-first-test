# さくら学習塾 保護者対応AIチャットボット（プロトタイプ）

## 概要

塾の規約に基づいて保護者からの問い合わせに自動対応するAIチャットボット。
先生が「断る」「説明する」負担から解放され、個別対応が必要なものだけ塾長にエスカレーションする。

## 画面

| URL | 用途 |
|---|---|
| `http://localhost:5000` | 保護者向けチャット画面 |
| `http://localhost:5000/escalations` | 塾長用ダッシュボード（要対応一覧） |

## セットアップ

```bash
# 1. 依存パッケージのインストール
pip install -r requirements.txt

# 2. APIキーの設定
export ANTHROPIC_API_KEY='your-api-key-here'

# 3. 起動
python app.py
```

## ファイル構成

```
prototype/
├── app.py                  # メインアプリケーション
├── policies.md             # 塾の規約（AIが参照する）
├── faq.md                  # よくある問い合わせTOP10
├── requirements.txt        # 依存パッケージ
├── README.md               # このファイル
└── templates/
    ├── index.html           # 保護者向けチャットUI
    └── escalations.html     # 塾長用ダッシュボード
```

## カスタマイズ方法

- `policies.md` を実際の塾の規約に差し替える
- `faq.md` を実際のよくある質問に更新する
- `app.py` の `SYSTEM_PROMPT` でAIの振る舞いを調整する

## テスト用の質問例

### AIが対応できるもの
- 「来週の木曜日を振替にできますか？」
- 「中学2年で週2回の場合、月額いくらですか？」
- 「退塾の手続きを教えてください」

### エスカレーションされるもの
- 「先生を変えてください」
- 「うちの子が友達にいじわるされています」
- 「授業料を値下げしてほしい」
