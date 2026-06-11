---
title: SNS Content Generator (CrewAI Edition)
emoji: 🤖
colorFrom: indigo
colorTo: purple
sdk: gradio
sdk_version: 4.44.1
app_file: app.py
pinned: false
license: mit
---

# 🤖 AI投稿文メーカー(SNS投稿＆ブログ記事)（CrewAI版）

[CrewAI](https://github.com/crewAIInc/crewAI) を用いて、**4体のAIエージェントが役割分担・協働**しながらSNS・ブログ文章を自動生成するアプリです。
Gemini無料枠（[Google AI Studio](https://aistudio.google.com)）をLLMバックエンドとして使用しています。

姉妹プロジェクト（マルチプロバイダー・並列処理版）：[sns-content-generator](https://github.com/df0521/sns-content-generator)

## 🎯 使い方

1. **基本情報**（業種・ターゲット・テーマ・店名（任意））を入力
2. **文体・スタイル設定**で方言・トーンを選択（必要に応じてA/Bテストをオン）
3. （任意）**AIモデル設定**で使用するGeminiモデルを選択
4. 「⚡ 生成する」ボタンをクリック
5. CrewAIの4エージェントが順番に協働し、X（パターンA/B）・Instagram・ブログ・ハッシュタグを生成
6. タブ切り替えで各コンテンツを確認、過去の生成結果は「📜 生成履歴」から再表示可能

## 🤖 CrewAIエージェント構成

| エージェント | 役割 | 実行方式 |
|---|---|---|
| 🧠 Strategist | 業種・ターゲット・テーマから深層ターゲット分析と戦略を立案 | 順次実行 |
| ✍️ Writer | 戦略・方言・トーンをもとにコンテンツ本文を執筆 | 順次実行（Strategistの出力をcontextとして引き継ぎ） |
| 🔍 SEO Editor | 本文にSEOキーワードを自然に組み込み最適化 | 順次実行（Writerの出力をcontextとして引き継ぎ） |
| 📱 Social Adapter | X（A/Bパターン）・Instagram・ブログ・ハッシュタグへ変換 | **非同期実行（`async_execution=True`）で並列処理** |

各エージェントは `role` / `goal` / `backstory` を持ち、`Crew`（`Process.sequential`）の中で
前工程のタスク出力を `context` として受け取りながら連携して動作します。
STEP4の4タスク（X/Instagram/ブログ/ハッシュタグ）は `async_execution=True` により並列実行され、処理時間を短縮しています。

## ✨ 主な機能

- **CrewAIマルチエージェント構成**：role/goal/backstory/contextを活用したエージェント協働パイプライン
- **方言・地域選択**：8地域の方言でコンテンツを生成
- **トーン&マナー選択**：標準／高級感・上品／親しみやすい・カジュアル／勢い・セール訴求／誠実・信頼感重視
- **店名・サービス名指定（任意）**：文章やハッシュタグに自然に組み込み
- **A/Bテスト生成**：X投稿文を訴求軸の異なる2パターンで生成
- **生成履歴の保存・閲覧**：SQLiteに自動保存し、一覧から過去の結果を再表示

## 🛠️ 使用技術

- [CrewAI](https://github.com/crewAIInc/crewAI) — マルチエージェントオーケストレーションフレームワーク
- [LiteLLM](https://github.com/BerriAI/litellm)（CrewAI内蔵） — Gemini APIへの接続
- [Google Gemini](https://aistudio.google.com) — LLM（無料枠）
- [Gradio](https://gradio.app) — Web UI
- [SQLite](https://www.sqlite.org/) — 生成履歴の保存

## 🔑 ローカル実行

```bash
# 1. 依存パッケージをインストール
pip install -r requirements.txt

# 2. .envファイルを作成
cp .env.example .env
# .envを編集してGEMINI_API_KEYを設定

# 3. アプリを起動
python app.py
```

ブラウザで http://localhost:7864 を開いてください。

## 💰 コスト

すべて**無料**で動作します。

- Gemini API：無料枠の範囲で利用可能
- HuggingFace Spaces：無料プランで公開可能（生成履歴はサーバー再起動で消える点に注意）
