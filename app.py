import gradio as gr

import history_db
from config import DIALECTS, DEFAULT_MODEL_LABEL, MODELS, TONES
from crew import run_crew


def generate_content(
    industry: str,
    target: str,
    theme: str,
    store_name: str,
    dialect_name: str,
    tone_name: str,
    ab_test: bool,
    model_label: str,
):
    history_table = history_db.get_recent()

    if not industry.strip() or not target.strip() or not theme.strip():
        msg = "❌ 業種・ターゲット・テーマをすべて入力してください。"
        return msg, "", msg, msg, msg, history_table

    try:
        result = run_crew(
            industry=industry,
            target=target,
            theme=theme,
            store_name=store_name,
            dialect_name=dialect_name,
            tone_name=tone_name,
            ab_test=ab_test,
            model_label=model_label,
        )

        x_post = result.get("x_post") or "（X投稿文を取得できませんでした）"
        instagram = result.get("instagram") or "（Instagram用コンテンツを取得できませんでした）"
        blog = result.get("blog") or "（ブログ記事を取得できませんでした）"
        hashtags = result.get("hashtags") or "（ハッシュタグを取得できませんでした）"
        x_post_b = result.get("x_post_b") or ""

        x_post_b_display = x_post_b if ab_test else "（A/Bテストは未選択です。チェックボックスをオンにすると2パターン目が生成されます）"
        if ab_test and not x_post_b:
            x_post_b_display = "（Xパターンbを取得できませんでした）"

        history_db.save_record({
            "industry": industry,
            "target": target,
            "theme": theme,
            "store_name": store_name,
            "dialect": dialect_name,
            "tone": tone_name,
            "provider": "CrewAI（Gemini）",
            "model": model_label,
            "x_post": x_post,
            "x_post_b": x_post_b if ab_test else "",
            "instagram": instagram,
            "blog": blog,
            "hashtags": hashtags,
        })
        history_table = history_db.get_recent()

        return x_post, x_post_b_display, instagram, blog, hashtags, history_table

    except ValueError as e:
        msg = f"❌ 設定エラー：{str(e)}"
        return msg, "", msg, msg, msg, history_table
    except Exception as e:
        err_text = str(e)
        if "429" in err_text or "rate" in err_text.lower():
            msg = (
                "❌ 現在このモデルが混雑しています（レート制限）。\n"
                "30秒ほど待つか、別のモデルを選んで再度お試しください。\n\n"
                f"詳細：{err_text}"
            )
        elif "404" in err_text or "does not exist" in err_text:
            msg = (
                "❌ 選択したモデルが現在利用できません（モデル名が変更/廃止された可能性があります）。\n"
                "別のモデルを選択して再度お試しください。\n\n"
                f"詳細：{err_text}"
            )
        else:
            msg = f"❌ エラーが発生しました：{err_text}"
        return msg, "", msg, msg, msg, history_table


# ── Gradio UI ─────────────────────────────────────────────
with gr.Blocks(
    title="SNS・ブログ文章自動生成 AI（CrewAI版）",
    theme=gr.themes.Soft(),
    css=".header-text { text-align: center; padding: 20px 0; }",
) as demo:
    gr.Markdown(
        """
        <div class="header-text">
        <h1>🤖 SNS・ブログ文章自動生成 AI <span style="font-size:0.7em; background:#6c5ce7; color:white; padding:2px 8px; border-radius:4px;">CrewAI版</span></h1>
        <p>CrewAIによる4体のAIエージェント協働パイプライン × 方言・トーン選択 × 深層ターゲット分析 × A/Bテスト × 履歴保存</p>
        </div>
        """,
    )

    with gr.Row():
        with gr.Column(scale=1):
            with gr.Accordion("📝 基本情報", open=True):
                industry_input = gr.Textbox(
                    label="業種",
                    placeholder="例：飲食店、美容院、ITコンサルティング",
                    lines=1,
                )
                target_input = gr.Textbox(
                    label="ターゲット",
                    placeholder="例：30代女性、20代男性会社員、子育て中の主婦",
                    lines=1,
                )
                theme_input = gr.Textbox(
                    label="テーマ",
                    placeholder="例：新メニュー告知、夏キャンペーン、サービス紹介",
                    lines=1,
                )
                store_name_input = gr.Textbox(
                    label="店名・サービス名（任意）",
                    placeholder="例：cafe Sora、ゆらり整体院",
                    info="入力すると、文章中やハッシュタグに自然に組み込まれます",
                    lines=1,
                )

            with gr.Accordion("🎨 文体・スタイル設定", open=True):
                dialect_input = gr.Dropdown(
                    choices=list(DIALECTS.keys()),
                    value="標準語（全国共通）",
                    label="🗾 出力する方言",
                    info="選んだ地域の言葉でコンテンツを生成します",
                )
                tone_input = gr.Dropdown(
                    choices=list(TONES.keys()),
                    value="標準（バランス型）",
                    label="🎨 文章のトーン",
                    info="ブランドの雰囲気に合わせて文体を調整します",
                )
                ab_test_input = gr.Checkbox(
                    label="Xの投稿文を2パターン生成する（A/Bテスト）",
                    value=False,
                )

            with gr.Accordion("🤖 AIモデル設定", open=False):
                model_input = gr.Dropdown(
                    choices=list(MODELS.keys()),
                    value=DEFAULT_MODEL_LABEL,
                    label="モデル（Gemini / 無料枠）",
                    info="CrewAIの全エージェントが共通でこのモデルを使用します",
                )

            generate_btn = gr.Button(
                "⚡ 生成する",
                variant="primary",
                size="lg",
            )

            with gr.Accordion("ℹ️ 処理について", open=False):
                gr.Markdown(
                    """
                    **🤖 CrewAIエージェント構成**

                    1. 🧠 **Strategist** — 深層ターゲット分析・戦略立案
                    2. ✍️ **Writer** — 戦略にもとづく本文執筆
                    3. 🔍 **SEO Editor** — SEO最適化＋品質チェック
                    4. 📱 **Social Adapter** — X/Instagram/ブログ/タグへ並列変換（非同期タスク）

                    各エージェントが役割・ゴール・バックストーリーを持ち、
                    前工程の出力をcontextとして引き継ぎながら協働します。

                    💰 Gemini無料枠で動作
                    📜 生成結果は自動的に履歴へ保存されます
                    """,
                )

        with gr.Column(scale=2, elem_id="result-section"):
            gr.Markdown("### 📤 生成結果")
            with gr.Tabs():
                with gr.Tab("𝕏 X（Twitter）"):
                    x_output = gr.Textbox(
                        label="X投稿文（140文字以内）",
                        lines=6,
                        show_copy_button=True,
                        placeholder="生成するとここに表示されます",
                    )
                with gr.Tab("𝕏 X（パターンB）"):
                    x_output_b = gr.Textbox(
                        label="X投稿文 パターンB（A/Bテスト）",
                        lines=6,
                        show_copy_button=True,
                        placeholder="「A/Bテスト」をオンにして生成すると表示されます",
                    )
                with gr.Tab("📸 Instagram"):
                    instagram_output = gr.Textbox(
                        label="Instagram投稿文",
                        lines=10,
                        show_copy_button=True,
                        placeholder="生成するとここに表示されます",
                    )
                with gr.Tab("📝 ブログ記事"):
                    blog_output = gr.Textbox(
                        label="ブログ記事",
                        lines=15,
                        show_copy_button=True,
                        placeholder="生成するとここに表示されます",
                    )
                with gr.Tab("# ハッシュタグ"):
                    hashtag_output = gr.Textbox(
                        label="ハッシュタグ一覧",
                        lines=6,
                        show_copy_button=True,
                        placeholder="生成するとここに表示されます",
                    )

    with gr.Accordion("📜 生成履歴（クリックで内容を表示）", open=False):
        history_output = gr.Dataframe(
            headers=history_db.get_history_headers(),
            value=history_db.get_recent(),
            interactive=False,
            wrap=True,
        )
        history_refresh_btn = gr.Button("🔄 履歴を更新")

    generate_btn.click(
        fn=generate_content,
        inputs=[
            industry_input, target_input, theme_input, store_name_input,
            dialect_input, tone_input, ab_test_input, model_input,
        ],
        outputs=[x_output, x_output_b, instagram_output, blog_output, hashtag_output, history_output],
        show_progress="full",
        js="""(...args) => {
            const el = document.getElementById('result-section');
            if (el) { el.scrollIntoView({ behavior: 'smooth', block: 'start' }); }
            return args;
        }""",
    )

    history_refresh_btn.click(
        fn=history_db.get_recent,
        inputs=[],
        outputs=[history_output],
    )

    def load_history_record(evt: gr.SelectData):
        record_id = evt.row_value[0]
        rec = history_db.get_record(int(record_id))
        if not rec:
            return gr.update(), gr.update(), gr.update(), gr.update(), gr.update()
        x_b = rec.get("x_post_b") or "（このレコードはA/Bテスト未実施です）"
        return rec.get("x_post", ""), x_b, rec.get("instagram", ""), rec.get("blog", ""), rec.get("hashtags", "")

    history_output.select(
        fn=load_history_record,
        inputs=[],
        outputs=[x_output, x_output_b, instagram_output, blog_output, hashtag_output],
    )

    gr.Markdown(
        """
        ---
        <div style="text-align:center; color:#888; font-size:0.85em;">
        Powered by CrewAI / Gemini × Gradio ｜ 完全無料・商用利用可
        </div>
        """,
    )


if __name__ == "__main__":
    demo.launch(server_port=7864, share=False)
