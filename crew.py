"""CrewAIによる4ステップ・マルチエージェントSNSコンテンツ生成パイプライン。

STEP1 Strategist  : 深層ターゲット分析・コンテンツ戦略立案
STEP2 Writer      : 戦略にもとづく本文執筆
STEP3 SEO Editor  : SEO最適化・品質チェック
STEP4 Social Adapter（複数エージェントを非同期実行） : X / Instagram / ブログ / ハッシュタグへ変換
"""

import os

# テレメトリ・トレーシング送信を無効化し、各タスクの待ち時間を短縮する
# （CrewAIインポート前に設定する必要がある）
os.environ.setdefault("CREWAI_DISABLE_TELEMETRY", "true")
os.environ.setdefault("OTEL_SDK_DISABLED", "true")

from crewai import Agent, Crew, LLM, Process, Task
from dotenv import load_dotenv

from config import DIALECTS, MODELS, TONES

load_dotenv()


# 出力の冒頭につきがちな「前置き」を検出するためのパターン
_PREAMBLE_PATTERNS = (
    "承知", "かしこまり", "了解", "わかりました", "もちろん",
    "以下に", "以下が", "こちらが", "こちらは", "では、", "では作成",
    "それでは", "ご要望", "ご依頼", "作成しました", "出力します",
    "Here is", "Here's", "Sure", "Certainly", "Below is",
)


def clean_output(text: str) -> str:
    """LLM出力から前置き文・コードフェンス・思考過程の混入を取り除く。"""
    if not text:
        return text

    text = text.strip()

    if text.startswith("```"):
        lines = text.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    for tag_start, tag_end in (("<think>", "</think>"), ("<reasoning>", "</reasoning>")):
        while tag_start in text and tag_end in text:
            start_idx = text.index(tag_start)
            end_idx = text.index(tag_end) + len(tag_end)
            text = (text[:start_idx] + text[end_idx:]).strip()

    for _ in range(2):
        lines = text.split("\n", 1)
        first_line = lines[0].strip()
        if any(first_line.startswith(p) for p in _PREAMBLE_PATTERNS) and len(lines) > 1:
            text = lines[1].lstrip("\n").strip()
        else:
            break

    return text.strip()


def get_llm(model: str, temperature: float, max_tokens: int | None = None) -> LLM:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key or "your_" in api_key:
        raise ValueError(
            "GEMINI_API_KEY が設定されていません。\n"
            ".env ファイルに GEMINI_API_KEY=your_key を追加してください。\n"
            "APIキー取得：https://aistudio.google.com"
        )
    kwargs = {"model": model, "api_key": api_key, "temperature": temperature}
    if max_tokens is not None:
        kwargs["max_tokens"] = max_tokens
    return LLM(**kwargs)


def run_crew(
    industry: str,
    target: str,
    theme: str,
    store_name: str,
    dialect_name: str,
    tone_name: str,
    ab_test: bool,
    model_label: str,
) -> dict:
    """CrewAIのCrewを構築・実行し、生成結果を辞書で返す。"""

    model = MODELS.get(model_label, MODELS[next(iter(MODELS))])

    dialect = DIALECTS.get(dialect_name, DIALECTS["標準語（全国共通）"])
    dialect_instruction = dialect["instruction"]
    dialect_region = dialect["region"]
    dialect_example = dialect["example_phrase"]

    tone_instruction = TONES.get(tone_name, TONES["標準（バランス型）"])

    store_name = (store_name or "").strip()
    if store_name:
        store_info_line = f"店舗・サービス名：{store_name}"
        store_strategy_note = (
            f"- 店舗・サービス名「{store_name}」をブランドとしてどう印象づけるか、"
            f"覚えてもらいやすくするためのフレーズの使い方も提案してください。"
        )
        store_writing_rule = (
            f"- 店舗・サービス名「{store_name}」を、書き出しまたは締めくくり部分で"
            f"1回、自然な形で登場させてください（不自然な連呼は避ける）。"
        )
        store_seo_rule = (
            f"- 「{store_name}」を地域名・業種と組み合わせたローカルSEOキーワード"
            f"（例：{dialect_region} {industry} {store_name}）として自然に1箇所組み込んでください。"
        )
        store_social_rule = (
            f"- X・Instagram・ブログのいずれにも、店舗・サービス名「{store_name}」を"
            f"最低1回は自然に含めてください（特にCTA部分や見出しで効果的です）。"
        )
        store_hashtag_rule = (
            f"6. 店舗名タグ：「{store_name}」を活かしたタグ（例：#{store_name}）を1個"
        )
    else:
        store_info_line = ""
        store_strategy_note = ""
        store_writing_rule = ""
        store_seo_rule = ""
        store_social_rule = ""
        store_hashtag_rule = ""

    # ── エージェント定義 ──────────────────────────────
    strategist = Agent(
        role="日本市場専門の消費者行動アナリスト",
        goal="ターゲットの深層心理・ペルソナ・購買行動を分析し、刺さるコンテンツ戦略を立案する",
        backstory=(
            "あなたは長年、日本国内の小売・飲食・サービス業のマーケティングリサーチに従事してきた"
            "消費者行動アナリストです。地域性や世代特有の価値観を踏まえた分析に定評があります。"
        ),
        llm=get_llm(model, 0.5),
        verbose=False,
        max_iter=3,
    )

    writer = Agent(
        role="日本語コンテンツ専門のプロライター",
        goal="戦略分析にもとづき、ターゲットの心に響く日本語コンテンツ本文を執筆する",
        backstory=(
            "あなたは地域密着型の店舗・サービスのSNS文章を数多く手がけてきたコピーライターです。"
            "方言やトーンを自在に使い分け、読者の感情を動かす文章を書くのが得意です。"
        ),
        llm=get_llm(model, 0.7),
        verbose=False,
        max_iter=3,
    )

    seo_editor = Agent(
        role="日本語SEOの専門家",
        goal="文章の読みやすさとSEO効果を両立させるよう本文を最適化する",
        backstory=(
            "あなたはWebマーケティング会社でSEOディレクターを務めた経験を持ち、"
            "検索流入とユーザー体験を両立させる文章編集を専門としています。"
        ),
        llm=get_llm(model, 0.5),
        verbose=False,
        max_iter=3,
    )

    def make_social_adapter(temperature: float = 0.7, max_tokens: int | None = None) -> Agent:
        # 並列実行（async_execution）するタスクは、それぞれ専用のAgentインスタンスを
        # 用意する必要がある（同一インスタンスの並行invokeはCrewAIで許可されていない）。
        return Agent(
            role="日本のSNSマーケティング専門家",
            goal="最適化済みの本文を各SNSプラットフォームに最適な形式へ変換する",
            backstory=(
                "あなたはX・Instagram・ブログ運用代行を専門とするSNSマーケターです。"
                "プラットフォームごとの文化やユーザー行動を熟知しています。"
            ),
            llm=get_llm(model, temperature, max_tokens=max_tokens),
            verbose=False,
            max_iter=3,
        )

    social_adapter_x = make_social_adapter(0.7)
    social_adapter_instagram = make_social_adapter(0.7)
    social_adapter_blog = make_social_adapter(0.6)
    social_adapter_hashtags = make_social_adapter(0.5)
    social_adapter_x_b = make_social_adapter(0.8)
    # 集約タスク専用：「完了」の一言だけを出力させるため、生成トークン数を絞り高速化する
    social_adapter_finalize = make_social_adapter(0.1, max_tokens=20)
    social_adapter_finalize.max_iter = 1

    # ── STEP1: Strategist ──────────────────────────────
    task_strategy = Task(
        description=f"""あなたは日本市場専門の消費者行動アナリストです。
必ず自然な日本語で回答してください。英語は使わないでください。

以下の情報をもとに、詳細なターゲット分析とコンテンツ戦略を日本語で作成してください。

【基本情報】
業種：{industry}
ターゲット：{target}
テーマ：{theme}
対象地域：{dialect_region}
トーン&マナー：{tone_name}（{tone_instruction}）
{store_info_line}

【ステップ1】まずターゲットのペルソナを具体的に描写してください
- 年齢・性別・職業・家族構成・年収帯（推定）
- 居住エリアと生活環境
- 典型的な1日のスケジュール
- 趣味・関心事・よく使うSNS

【ステップ2】深層心理を分析してください
- 日常の悩み・不安・不満（顕在ニーズ）
- 本人も気づいていない潜在的な欲求（潜在ニーズ）
- 購買決断を後押しする感情的トリガー3つ

【ステップ3】コンテンツ戦略を立案してください
- 最も響く訴求ポイントTOP3（優先順位付き）
- 使うべき具体的なキーワード・フレーズ5つ
- {dialect_region}地域の文化・価値観を活かした独自の切り口
- 絶対に避けるべきNG表現
  ※特に「業種：{industry}」が提供する商品・サービスの形態（例：飲食店なら来店して食事を楽しむ、小売店なら商品を購入する、サービス業なら施術・サービスを受ける、など）と矛盾する表現は厳禁です。
  　例：飲食店（外食）なのに「手間なし」「後片付けが楽」「自宅で簡単」のような“家庭での調理・準備”を前提とした表現を使わないこと。
{store_strategy_note}

すべて日本語で、具体的かつ詳細に記述してください。""",
        expected_output="ペルソナ描写・深層心理分析・コンテンツ戦略を含む詳細な日本語の分析レポート（前置き・末尾コメントなし）",
        agent=strategist,
    )

    # ── STEP2: Writer ──────────────────────────────────
    task_writing = Task(
        description=f"""あなたは日本語コンテンツ専門のプロライターです。
必ず自然な日本語で執筆してください。英語は絶対に使わないでください。
{dialect_instruction}
方言の例文：「{dialect_example}」
このような言葉遣いで、読者の心に響く文章を書いてください。
{tone_instruction}

前のタスクで作成された戦略分析をもとに、コンテンツ本文を400〜600文字で執筆してください。

【執筆の手順】
1. まず読者が「あ、自分のことだ」と思う具体的な場面・状況を描写する（導入：80〜100文字）
2. その悩みや欲求に寄り添いながら、{industry}の{theme}がどう解決するかを伝える（本文：250〜350文字）
3. 読者が行動したくなる締めくくりを書く（まとめ：70〜100文字）

【絶対ルール】
- {dialect_instruction}
- 方言の例：「{dialect_example}」を参考に自然な{dialect_region}の言葉遣いで
- 専門用語は使わず、ターゲットが日常で使う言葉を選ぶ
- 体言止め・感嘆符・改行を効果的に使いテンポよく読める文章にする
- 英語・カタカナ語は最小限に抑える
- 合計400〜600文字になるようにしてください
- 業種「{industry}」の提供形態（来店・購入・利用など）と矛盾する表現は使わないこと（例：飲食店なのに「手間なし」「後片付けが楽」「自宅で簡単」など家庭での調理を前提とした表現はNG）
{store_writing_rule}

本文のみを出力してください（説明・タイトル・前置き・末尾コメントは一切不要）。""",
        expected_output="400〜600文字の日本語コンテンツ本文のみ（前置き・タイトル・コメントなし）",
        agent=writer,
        context=[task_strategy],
    )

    # ── STEP3: SEO Editor ───────────────────────────────
    task_seo = Task(
        description=f"""あなたは日本語SEOの専門家です。
必ず自然な日本語で出力してください。英語は使わないでください。

前のタスクで作成された本文をSEO最適化し、さらに品質を向上させてください。

【業種】{industry}
【テーマ】{theme}
【ターゲット】{target}
【地域】{dialect_region}
【方言ルール】{dialect_instruction}

【最適化の手順】
1. ターゲットが検索するキーワード（例：{industry} {theme}、{target}向け など）を本文に自然に組み込む
2. 文章の流れを確認し、読みにくい箇所を修正する
3. {dialect_region}の方言・言葉遣いが自然かチェックし、不自然な箇所を修正する
4. 体言止めや改行を活用してテンポよく読めるか確認する
5. 400〜600文字の文字数を維持する
{store_seo_rule}

最適化・改善後の本文のみを出力してください（説明・前置き・コメントは一切不要）。""",
        expected_output="SEO最適化済みの日本語本文のみ（前置き・説明・コメントなし）",
        agent=seo_editor,
        context=[task_writing],
    )

    # ── STEP4: Social Adapter（並列実行） ─────────────────
    social_common_rules = f"""- すべて日本語で執筆（英語不可）
- {dialect_instruction}
- 方言例：「{dialect_example}」を参考に自然な言葉遣いで
- ターゲット：{target}に響く表現を使う
- {tone_instruction}
- 業種「{industry}」の提供形態（来店・購入・利用など）と矛盾する表現は使わないこと
  （例：飲食店なのに「手間なし」「後片付けが楽」「自宅で簡単」など家庭での調理を前提とした表現はNG）
{store_social_rule}"""

    task_x_a = Task(
        description=f"""あなたは日本のSNSマーケティング専門家です。
必ず自然な日本語で出力してください。英語は使わないでください。
出力は本文のみとし、前置き・説明・コメント・タイトル・見出し記号は一切書かないでください。

前のタスクで作成された最適化済み本文をもとに、X（Twitter）投稿文を作成してください。

【共通ルール】
{social_common_rules}

【作成手順】
1. 最初の1行：思わずスクロールを止める強いフック（疑問形・共感のいずれか）
2. 中間：具体的なベネフィットを2〜3行で
3. 最後：行動を促す一言

※140文字以内・改行を効果的に使う
X投稿文の本文のみを出力してください。""",
        expected_output="140文字以内のX投稿文（本文のみ、前置き・説明なし）",
        agent=social_adapter_x,
        context=[task_seo],
        async_execution=True,
    )

    task_instagram = Task(
        description=f"""あなたは日本のSNSマーケティング専門家です。
必ず自然な日本語で出力してください。英語は使わないでください。
出力は本文のみとし、前置き・説明・コメント・タイトル・見出し記号は一切書かないでください。

前のタスクで作成された最適化済み本文をもとに、Instagram投稿文を作成してください。

【共通ルール】
{social_common_rules}

【作成手順】
1. 最初の1行：絵文字で始まる興味を引く書き出し
2. 共感できる「あるある」や状況描写
3. 解決策・価値の提供
4. 絵文字を段落ごとに1〜2個使い読みやすく
5. 最後にCTA（「保存して」「コメントで教えて」など）

※300〜500文字
Instagram投稿文の本文のみを出力してください。""",
        expected_output="300〜500文字のInstagram投稿文（本文のみ、前置き・説明なし）",
        agent=social_adapter_instagram,
        context=[task_seo],
        async_execution=True,
    )

    task_blog = Task(
        description=f"""あなたは日本のSNSマーケティング専門家です。
必ず自然な日本語で出力してください。英語は使わないでください。
出力は本文のみとし、前置き・説明・コメントは一切書かないでください。

前のタスクで作成された最適化済み本文をもとに、ブログ記事を作成してください。

【共通ルール】
{social_common_rules}

【作成手順】
1. ##導入見出し：読者の悩みに共感する書き出し（150文字）
2. ##本文見出し：解決策・価値の提供（350文字）
3. ##まとめ見出し：行動を促す締めくくり（150文字）

※見出しにSEOキーワード（{industry}・{theme}）を含める
※合計600〜800文字
ブログ記事本文のみを出力してください。""",
        expected_output="600〜800文字のブログ記事（本文のみ、前置き・説明なし）",
        agent=social_adapter_blog,
        context=[task_seo],
        async_execution=True,
    )

    hashtag_common_rules = f"""【業種】{industry}　【テーマ】{theme}　【ターゲット】{target}　【地域】{dialect_region}"""

    task_hashtags = Task(
        description=f"""あなたは日本のSNSハッシュタグ戦略の専門家です。
必ず日本語のハッシュタグのみで出力してください。英語は使わないでください。
出力はハッシュタグの一覧のみとし、説明文・前置き・コメントは一切書かないでください。

前のタスクで作成された最適化済み本文をもとに、SNS投稿用のハッシュタグを作成してください。

{hashtag_common_rules}

【作成手順】
1. 大カテゴリタグ（業種関連）：3〜4個
2. テーマ特化タグ：3〜4個
3. ターゲット属性タグ：2〜3個
4. 地域タグ（{dialect_region}関連）：2〜3個
5. トレンドタグ：1〜2個
{store_hashtag_rule}

※合計12〜15個・#タグ形式で列挙してください。""",
        expected_output="12〜15個の日本語ハッシュタグの一覧のみ（説明・前置きなし）",
        agent=social_adapter_hashtags,
        context=[task_seo],
        async_execution=True,
    )

    tasks = [task_strategy, task_writing, task_seo, task_x_a, task_instagram, task_blog, task_hashtags]

    task_x_b = None
    if ab_test:
        task_x_b = Task(
            description=f"""あなたは日本のSNSマーケティング専門家です。
必ず自然な日本語で出力してください。英語は使わないでください。
出力は本文のみとし、前置き・説明・コメント・タイトル・見出し記号は一切書かないでください。

前のタスクで作成された最適化済み本文をもとに、X（Twitter）投稿文を作成してください。

【共通ルール】
{social_common_rules}

【作成手順】
1. 最初の1行：数字・意外性・ベネフィット直球のいずれかを使った強いフック
   （「疑問形」や「あるある共感」は別パターンで使用済みのため避けること）
2. 中間：具体的なベネフィットを2〜3行で
3. 最後：行動を促す一言

※140文字以内・改行を効果的に使う
※もう1つの案（疑問形・共感型）とは異なる訴求軸・切り口にすること
X投稿文の本文のみを出力してください。""",
            expected_output="140文字以内のX投稿文・パターンB（本文のみ、前置き・説明なし）",
            agent=social_adapter_x_b,
            context=[task_seo],
            async_execution=True,
        )
        tasks.append(task_x_b)

    # CrewAIの仕様上、非同期タスクで終わるCrewは末尾に1つしか置けないため、
    # 並列実行した各タスクの完了を待ち合わせる「集約タスク」を最後に追加する。
    task_finalize = Task(
        description="前のタスクで作成されたX投稿文・Instagram投稿文・ブログ記事・ハッシュタグが"
        "すべて生成されたことを確認し、「完了」とだけ出力してください。",
        expected_output="「完了」の一言のみ",
        agent=social_adapter_finalize,
        context=tasks[3:],
    )
    tasks.append(task_finalize)

    agents = [
        strategist, writer, seo_editor,
        social_adapter_x, social_adapter_instagram, social_adapter_blog,
        social_adapter_hashtags, social_adapter_finalize,
    ]
    if ab_test:
        agents.append(social_adapter_x_b)

    crew = Crew(
        agents=agents,
        tasks=tasks,
        process=Process.sequential,
        verbose=False,
    )

    crew.kickoff()

    result = {
        "x_post": clean_output(task_x_a.output.raw if task_x_a.output else ""),
        "instagram": clean_output(task_instagram.output.raw if task_instagram.output else ""),
        "blog": clean_output(task_blog.output.raw if task_blog.output else ""),
        "hashtags": clean_output(task_hashtags.output.raw if task_hashtags.output else ""),
        "x_post_b": clean_output(task_x_b.output.raw if (task_x_b and task_x_b.output) else ""),
    }
    return result
