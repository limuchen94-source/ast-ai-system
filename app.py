import streamlit as st
import google.generativeai as genai
import json
import re
import plotly.graph_objects as go
from datetime import datetime

# ─────────────────────────────────────────────
#  頁面基本設定
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="AST 分科測驗 AI 系統",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────
#  全域 CSS
# ─────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+TC:wght@400;500;700&display=swap');

html, body, [class*="css"] {
    font-family: 'Noto Sans TC', sans-serif;
}

/* ── 頂部標題 ── */
.main-header {
    background: linear-gradient(135deg, #1e3a5f 0%, #2563a8 100%);
    color: white;
    padding: 1.4rem 2rem;
    border-radius: 12px;
    margin-bottom: 1.6rem;
    text-align: center;
}
.main-header h1 { margin: 0; font-size: 1.9rem; font-weight: 700; letter-spacing: 0.02em; }
.main-header p  { margin: 0.3rem 0 0; font-size: 0.9rem; opacity: 0.85; }

/* ── 題目框 ── */
.question-box {
    background: #f8faff;
    border-left: 5px solid #2563a8;
    padding: 1.4rem 1.6rem;
    border-radius: 8px;
    line-height: 1.85;
    font-size: 0.97rem;
    margin: 0.8rem 0 1.2rem;
    white-space: pre-wrap;
}

/* ── 解析框 ── */
.analysis-box {
    background: #f0fdf4;
    border-left: 5px solid #16a34a;
    padding: 1.2rem 1.5rem;
    border-radius: 8px;
    line-height: 1.8;
    font-size: 0.95rem;
    white-space: pre-wrap;
}

/* ── 錯誤分析框 ── */
.error-box {
    background: #fff7ed;
    border-left: 5px solid #ea580c;
    padding: 1.2rem 1.5rem;
    border-radius: 8px;
    line-height: 1.8;
    font-size: 0.95rem;
}

/* ── 標籤 chip ── */
.chip {
    display: inline-block;
    background: #e0eaff;
    color: #1e3a5f;
    border-radius: 20px;
    padding: 0.2rem 0.8rem;
    font-size: 0.82rem;
    font-weight: 600;
    margin-right: 0.4rem;
}

/* ── 步驟說明框 ── */
.step-box {
    background: #f8faff;
    border: 1px solid #c7d9f5;
    border-radius: 10px;
    padding: 1.2rem 1.5rem;
    margin-bottom: 1rem;
}
.step-title { font-weight: 700; color: #1e3a5f; font-size: 1rem; margin-bottom: 0.4rem; }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
#  課綱結構（108 課綱加深加廣選修）
# ─────────────────────────────────────────────
CURRICULUM = {
    "數學甲": {
        "微積分": ["極限與連續性", "微分法則與應用", "積分法則與應用", "微積分基本定理"],
        "向量與空間幾何": ["向量運算", "空間中直線與平面", "二次曲面簡介"],
        "矩陣與行列式": ["矩陣運算", "行列式計算", "線性方程組"],
        "數列與級數": ["等差等比數列", "遞推關係", "無窮級數與斂散"],
        "複數與多項式": ["複數四則運算", "多項式根的分佈", "代數基本定理"],
    },
    "數學乙": {
        "推論統計": ["抽樣分佈", "信賴區間估計", "假設檢定概念"],
        "微積分基礎": ["函數極限概念", "導數與切線斜率", "定積分與面積"],
        "數學建模": ["線性規劃進階", "指數對數成長模型", "迴歸分析基礎"],
        "排列組合與機率": ["排列組合進階", "條件機率", "期望值與變異數"],
    },
    "物理": {
        "電磁感應": ["法拉第定律", "楞次定律", "自感與互感", "交流電路 RLC"],
        "量子現象": ["光電效應", "波爾原子模型", "波粒二象性", "海森堡不確定原理"],
        "波動與光學": ["惠更斯原理", "薄膜干涉", "單縫雙縫繞射", "偏振光"],
        "相對論基礎": ["伽利略相對性", "狹義相對論假設", "時間膨脹與長度收縮", "質能等價"],
        "核物理": ["原子核結構", "放射性衰變定律", "核分裂與核融合", "輻射防護"],
        "熱力學": ["熱力學第一定律", "熱力學第二定律與熵", "卡諾循環效率"],
    },
    "化學": {
        "有機化學": ["官能基分類與命名", "取代與消去反應", "加成與氧化反應", "高分子合成"],
        "化學平衡": ["勒沙特列原理", "平衡常數 Kc/Kp", "緩衝溶液原理"],
        "電化學": ["氧化還原半反應", "伏打電池與電動勢", "電解與法拉第定律", "腐蝕與防護"],
        "酸鹼化學": ["強弱酸鹼平衡", "水解與pH計算", "中和滴定進階"],
        "熱化學": ["赫斯定律應用", "標準生成熱", "鍵能估算反應熱"],
        "綠色化學": ["原子經濟性計算", "永續合成原則", "廢棄物減量策略"],
    },
}

# ─────────────────────────────────────────────
#  Session State 初始化
# ─────────────────────────────────────────────
def _init_state():
    defaults = {
        "history": [],
        "current_question": None,
        "current_analysis": None,
        "current_mode": None,
        "current_topic": None,
        "current_subject": None,
        "subject_scores": {
            s: {"P": 50.0, "S": 50.0, "L": 50.0, "count": 0}
            for s in CURRICULUM
        },
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

_init_state()

# ─────────────────────────────────────────────
#  Gemini 模型
# ─────────────────────────────────────────────
@st.cache_resource(show_spinner=False)
def _get_model(api_key: str):
    genai.configure(api_key=api_key)
    return genai.GenerativeModel(
        "gemini-1.5-flash",
        generation_config=genai.types.GenerationConfig(
            temperature=0.72,
            max_output_tokens=4096,
        ),
    )

# ─────────────────────────────────────────────
#  Prompt 模板
# ─────────────────────────────────────────────
MODE_INSTRUCTIONS = {
    "模擬考題": (
        "模擬真實分科測驗風格。題幹須包含真實情境（學術研究/生活場景），"
        "字數 300-500 字，至少描述一張圖表數據供學生判讀。"
        "認知層次以「應用、分析」為主（佔 70%），記憶層次不超過 10%。"
    ),
    "創新訓練": (
        "融入近 12 個月科技時事（生成式 AI、半導體先進製程、低軌衛星、ESG/淨零、"
        "諾貝爾獎最新成果）。須包含 15% 大學初階概念延伸，並在題幹提供足夠的"
        "引導資訊（Scaffolding）讓學生現場學習（On-the-spot learning）。"
        "設計「反思型」非選擇題子題，要求學生評論實驗設計缺陷或提出改進方案。"
    ),
    "弱點診斷": (
        "針對此主題最常見的 2-3 個迷思概念設計診斷題。"
        "誘答選項必須對應典型錯誤邏輯（非隨機干擾）。"
        "確保答對者為真正理解，而非猜題。"
    ),
}

DIFF_MAP = {"簡單": "0.70–0.85", "中等": "0.40–0.60", "困難": "0.15–0.35"}

def build_question_prompt(subject, chapter, topic, difficulty, mode, time_event=""):
    extra = f"本題請融入以下時事主題：{time_event}。" if time_event else ""
    return f"""你是台灣分科測驗（AST）首席命題專家，依據 108 課綱加深加廣選修精神出題。

## 命題參數
- 科目：{subject}
- 章節：{chapter} → 主題：{topic}
- 難易度：{difficulty}（預估 P 值 {DIFF_MAP.get(difficulty, '0.40–0.60')}）
- 命題模式：{mode}

## 命題指令
{MODE_INSTRUCTIONS.get(mode, MODE_INSTRUCTIONS["模擬考題"])}
{extra}

## 16 維度命題框架（請自行勾選並確保符合）
1.課綱覆蓋率 2.歷屆軌跡迴避 3.情境化命題 4.混合題型 5.探究與實作 6.圖表判讀
7.跨單元整合 8.Bloom 認知層次 9.P/D 值控制 10.時事融入 11.大學預備知能
12.迷思概念誘答 13.文字量管控 14.論證鏈結 15.友善包容 16.與學測區隔

## 必須以純 JSON 輸出（不加 Markdown 圍欄）
{{
  "question_text": "完整題幹（情境+問題，300–500字）",
  "question_type": "單選題 | 多選題 | 混合題",
  "options": {{"A": "...", "B": "...", "C": "...", "D": "..."}},
  "correct_answer": "A",
  "has_short_answer": false,
  "short_answer_prompt": "（若混合題填入非選擇題要求，否則留空）",
  "intent": "命題意旨（80–120字）",
  "curriculum_ref": "對應課綱條目（精確至主題）",
  "p_value_est": "0.XX",
  "d_value_est": "0.XX",
  "cognitive_level": "應用 | 分析 | 評鑑 | 創造",
  "misconceptions": ["常見迷思1", "常見迷思2"],
  "detailed_solution": "詳細解析（步驟清楚，至少 300字）",
  "scoring_rubric": "非選擇題評分細則（若無非選擇題則填 N/A）",
  "distractor_analysis": {{"A": "設計原因", "B": "設計原因", "C": "設計原因", "D": "設計原因"}}
}}"""

def build_analysis_prompt(subject, topic, q_text, student_ans, correct_ans, short_ans=""):
    return f"""你是分科測驗學習診斷分析師，請分析學生作答狀況。

科目：{subject} | 主題：{topic}
題幹（節錄）：{q_text[:600]}
正確答案：{correct_ans}
學生選擇：{student_ans}
學生非選擇題作答：{short_ans or "（無）"}

請以純 JSON 輸出：
{{
  "is_correct": true,
  "p_score": 85,
  "s_score": 80,
  "l_score": 75,
  "error_type": "無（答對）| 公式代入錯誤 | 圖表解讀偏差 | 定義理解模糊 | 計算失誤 | 概念混淆",
  "weak_point": "具體弱點（40字內）",
  "improvement": "改進建議（80字內）",
  "key_concept": "本題核心概念（40字內）",
  "follow_up_topics": ["建議複習主題1", "建議複習主題2"]
}}

評分說明：
- p_score：答對 75–100（依解析完整度），答錯依錯誤嚴重度 15–55
- s_score：從解題策略品質推斷（無法判斷給 60）
- l_score：從邏輯一致性推斷（無法判斷給 60）"""

# ─────────────────────────────────────────────
#  工具函式
# ─────────────────────────────────────────────
def parse_json(text: str):
    text = text.strip()
    for pattern in [r"```json\s*([\s\S]*?)```", r"```\s*([\s\S]*?)```"]:
        m = re.search(pattern, text)
        if m:
            text = m.group(1)
            break
    try:
        return json.loads(text)
    except Exception:
        m = re.search(r"\{[\s\S]*\}", text)
        if m:
            try:
                return json.loads(m.group())
            except Exception:
                pass
    return None

def update_scores(subject: str, analysis: dict):
    s = st.session_state.subject_scores[subject]
    n = s["count"]
    for k, field in [("P", "p_score"), ("S", "s_score"), ("L", "l_score")]:
        s[k] = round((s[k] * n + analysis.get(field, 60)) / (n + 1), 1)
    s["count"] = n + 1

def radar_chart():
    subjects = list(st.session_state.subject_scores.keys())
    categories = ["P 正確率", "S 策略分", "L 邏輯穩定"]
    colors = ["#2563a8", "#16a34a", "#ea580c", "#9333ea"]
    fig = go.Figure()
    for i, subj in enumerate(subjects):
        sc = st.session_state.subject_scores[subj]
        if sc["count"] == 0:
            continue
        vals = [sc["P"], sc["S"], sc["L"], sc["P"]]
        cats = categories + [categories[0]]
        fig.add_trace(go.Scatterpolar(
            r=vals, theta=cats, fill="toself",
            name=subj, opacity=0.65,
            line=dict(color=colors[i % len(colors)], width=2),
        ))
    fig.update_layout(
        polar=dict(radialaxis=dict(visible=True, range=[0, 100], tickfont=dict(size=11))),
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=-0.25),
        title=dict(text="學習能力雷達圖", x=0.5, font=dict(size=15)),
        height=420,
        margin=dict(t=50, b=60, l=20, r=20),
        font=dict(family="Noto Sans TC, sans-serif"),
    )
    return fig

def render_question_and_submit(mode_key: str, subject: str, topic: str):
    """Render question, answer input, and submit button. Returns True after submission."""
    q = st.session_state.current_question
    if not q or st.session_state.get("current_mode") != mode_key:
        return

    st.markdown("---")
    # Metadata chips
    chips_html = (
        f'<span class="chip">🧠 {q.get("cognitive_level","分析")}</span>'
        f'<span class="chip">📈 P≈{q.get("p_value_est","?")} D≈{q.get("d_value_est","?")}</span>'
        f'<span class="chip">📚 {q.get("curriculum_ref","")[:28]}</span>'
    )
    st.markdown(chips_html, unsafe_allow_html=True)

    st.markdown(f'<div class="question-box">{q.get("question_text","")}</div>',
                unsafe_allow_html=True)

    answer_key = f"radio_{mode_key}"
    selected = "A"
    if q.get("options"):
        selected = st.radio(
            "請選擇答案：",
            list(q["options"].keys()),
            format_func=lambda x: f"**{x}**　{q['options'][x]}",
            key=answer_key,
        )

    short_ans = ""
    if q.get("has_short_answer"):
        st.markdown(f"**✏️ 非選擇題：** {q.get('short_answer_prompt','')}")
        short_ans = st.text_area("你的作答：", key=f"short_{mode_key}", height=130)

    if st.button("✅ 提交答案", key=f"submit_{mode_key}", type="primary"):
        api_key = st.session_state.get("api_key", "")
        if not api_key:
            st.error("請先在左側輸入 API Key")
            return
        with st.spinner("AI 正在診斷你的作答..."):
            try:
                model = _get_model(api_key)
                prompt = build_analysis_prompt(
                    subject, topic,
                    q["question_text"], selected,
                    q["correct_answer"], short_ans,
                )
                resp = model.generate_content(prompt)
                analysis = parse_json(resp.text)
                if analysis:
                    st.session_state.current_analysis = analysis
                    update_scores(subject, analysis)
                    st.session_state.history.append({
                        "time": datetime.now().strftime("%H:%M"),
                        "subject": subject,
                        "topic": topic,
                        "mode": mode_key,
                        "correct": analysis.get("is_correct", False),
                        "p_score": analysis.get("p_score", 50),
                    })
                else:
                    st.error("分析結果解析失敗，請重試")
            except Exception as e:
                st.error(f"API 錯誤：{e}")

def render_analysis(mode_key: str, q: dict):
    """Render analysis result block."""
    if st.session_state.get("current_mode") != mode_key:
        return
    analysis = st.session_state.current_analysis
    if not analysis:
        return

    st.markdown("---")
    st.markdown("### 📊 作答分析")

    if analysis.get("is_correct"):
        st.success("🎉 答對了！概念掌握良好。")
    else:
        st.error(f"❌ 答案不正確。正確答案為：**{q.get('correct_answer','')}**")

    c1, c2, c3 = st.columns(3)
    c1.metric("P 概念正確率", f"{analysis.get('p_score',0):.0f} / 100")
    c2.metric("S 解題策略", f"{analysis.get('s_score',0):.0f} / 100")
    c3.metric("L 邏輯穩定度", f"{analysis.get('l_score',0):.0f} / 100")

    with st.expander("📖 詳細解析", expanded=True):
        st.markdown(
            f'<div class="analysis-box">{q.get("detailed_solution","（無解析）")}</div>',
            unsafe_allow_html=True,
        )

    if not analysis.get("is_correct"):
        with st.expander("⚠️ 錯誤診斷與建議"):
            st.markdown(
                f'<div class="error-box">'
                f'<b>錯誤類型：</b>{analysis.get("error_type","")}<br><br>'
                f'<b>弱點說明：</b>{analysis.get("weak_point","")}<br><br>'
                f'<b>改進建議：</b>{analysis.get("improvement","")}<br><br>'
                f'<b>建議複習：</b>{"　→　".join(analysis.get("follow_up_topics",[]))}'
                f'</div>',
                unsafe_allow_html=True,
            )

    with st.expander("🔍 命題意旨與選項設計說明"):
        st.markdown(f"**命題意旨：** {q.get('intent','')}")
        st.markdown(f"**核心概念：** {analysis.get('key_concept','')}")
        if q.get("distractor_analysis"):
            st.markdown("**各選項設計原因：**")
            for opt, reason in q["distractor_analysis"].items():
                st.markdown(f"- **{opt}**：{reason}")

# ─────────────────────────────────────────────
#  側邊欄
# ─────────────────────────────────────────────
with st.sidebar:
    st.markdown("## ⚙️ 系統設定")

    api_key_input = st.text_input(
        "🔑 Gemini API Key",
        type="password",
        placeholder="貼上你的 API Key",
        help="免費取得：https://aistudio.google.com/app/apikey",
    )
    if api_key_input:
        st.session_state["api_key"] = api_key_input
        st.success("✅ API Key 已設定")
    else:
        st.warning("⚠️ 尚未設定 API Key")
        st.markdown(
            "[🔗 前往 Google AI Studio 免費申請](https://aistudio.google.com/app/apikey)",
            unsafe_allow_html=False,
        )

    st.divider()
    st.markdown("## 📚 學科設定")
    subject = st.selectbox("科目", list(CURRICULUM.keys()), key="sel_subject")
    chapter = st.selectbox("章節", list(CURRICULUM[subject].keys()), key="sel_chapter")
    topic = st.selectbox("主題", CURRICULUM[subject][chapter], key="sel_topic")

    st.divider()
    difficulty = st.select_slider(
        "難易度",
        options=["簡單", "中等", "困難"],
        value="中等",
        key="sel_difficulty",
    )

    st.divider()
    st.markdown("## 📊 本次學習統計")
    total_q = sum(s["count"] for s in st.session_state.subject_scores.values())
    correct_q = sum(1 for h in st.session_state.history if h.get("correct"))
    st.metric("已作答", f"{total_q} 題")
    if total_q:
        st.metric("答對率", f"{correct_q/total_q*100:.1f}%")

# ─────────────────────────────────────────────
#  頂部標題
# ─────────────────────────────────────────────
st.markdown("""
<div class="main-header">
  <h1>🎓 AST 分科測驗 AI 智慧命題系統</h1>
  <p>108 課綱加深加廣選修 ｜ 16 維度命題框架 ｜ Gemini AI 驅動 ｜ 數學甲乙・物理・化學</p>
</div>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
#  主要分頁
# ─────────────────────────────────────────────
tab_mock, tab_innov, tab_diag, tab_hist = st.tabs([
    "📝 模擬考題",
    "🔬 創新訓練",
    "🎯 弱點診斷",
    "📊 學習歷程",
])

# ══════════════════════════════════════════════
#  分頁 1 ── 模擬考題
# ══════════════════════════════════════════════
with tab_mock:
    c_left, c_right = st.columns([3, 1])
    with c_left:
        st.markdown("### 📝 模擬考題生成")
        st.markdown(
            f"**科目：** {subject}　**章節：** {chapter}　**主題：** {topic}　**難度：** {difficulty}"
        )
    with c_right:
        gen_mock = st.button("🎲 生成題目", key="btn_gen_mock", use_container_width=True)

    if gen_mock:
        api_key = st.session_state.get("api_key", "")
        if not api_key:
            st.error("請先在左側輸入 Gemini API Key")
        else:
            with st.spinner("AI 正在依據 16 維度命題框架生成題目，請稍候..."):
                try:
                    model = _get_model(api_key)
                    prompt = build_question_prompt(subject, chapter, topic, difficulty, "模擬考題")
                    resp = model.generate_content(prompt)
                    q_data = parse_json(resp.text)
                    if q_data:
                        st.session_state.current_question = q_data
                        st.session_state.current_analysis = None
                        st.session_state.current_mode = "模擬考題"
                        st.session_state.current_topic = topic
                        st.session_state.current_subject = subject
                    else:
                        st.error("❌ 題目格式解析失敗，請重試")
                except Exception as e:
                    st.error(f"API 錯誤：{e}")

    render_question_and_submit("模擬考題", subject, topic)
    if st.session_state.current_question:
        render_analysis("模擬考題", st.session_state.current_question)

# ══════════════════════════════════════════════
#  分頁 2 ── 創新訓練
# ══════════════════════════════════════════════
with tab_innov:
    c_left, c_right = st.columns([3, 1])
    with c_left:
        st.markdown("### 🔬 創新考題訓練")
        st.markdown(
            "融入最新科技時事與大學初階概念，訓練「On-the-spot Learning」應變能力"
        )
        time_event = st.text_input(
            "🌐 指定時事主題（選填）",
            placeholder="例：生成式 AI 晶片設計、鈣鈦礦太陽能電池...",
            key="inp_time_event",
        )
    with c_right:
        st.markdown("&nbsp;", unsafe_allow_html=True)
        gen_innov = st.button("🚀 生成創新題", key="btn_gen_innov", use_container_width=True)

    if gen_innov:
        api_key = st.session_state.get("api_key", "")
        if not api_key:
            st.error("請先在左側輸入 Gemini API Key")
        else:
            with st.spinner("AI 正在結合時事與大學概念生成創新考題..."):
                try:
                    model = _get_model(api_key)
                    prompt = build_question_prompt(
                        subject, chapter, topic, difficulty, "創新訓練", time_event
                    )
                    resp = model.generate_content(prompt)
                    q_data = parse_json(resp.text)
                    if q_data:
                        st.session_state.current_question = q_data
                        st.session_state.current_analysis = None
                        st.session_state.current_mode = "創新訓練"
                        st.session_state.current_topic = topic
                        st.session_state.current_subject = subject
                    else:
                        st.error("❌ 題目格式解析失敗，請重試")
                except Exception as e:
                    st.error(f"API 錯誤：{e}")

    render_question_and_submit("創新訓練", subject, topic)
    if st.session_state.current_question:
        render_analysis("創新訓練", st.session_state.current_question)

# ══════════════════════════════════════════════
#  分頁 3 ── 弱點診斷
# ══════════════════════════════════════════════
with tab_diag:
    c_left, c_right = st.columns([3, 1])
    with c_left:
        st.markdown("### 🎯 精準弱點診斷")
        st.markdown(
            "系統針對此主題最常見的**迷思概念**設計診斷題，誘答選項對應典型邏輯錯誤，精準定位你的學習盲點。"
        )
    with c_right:
        gen_diag = st.button("🔍 生成診斷題", key="btn_gen_diag", use_container_width=True)

    if gen_diag:
        api_key = st.session_state.get("api_key", "")
        if not api_key:
            st.error("請先在左側輸入 Gemini API Key")
        else:
            with st.spinner("AI 正在生成弱點診斷題..."):
                try:
                    model = _get_model(api_key)
                    prompt = build_question_prompt(
                        subject, chapter, topic, difficulty, "弱點診斷"
                    )
                    resp = model.generate_content(prompt)
                    q_data = parse_json(resp.text)
                    if q_data:
                        st.session_state.current_question = q_data
                        st.session_state.current_analysis = None
                        st.session_state.current_mode = "弱點診斷"
                        st.session_state.current_topic = topic
                        st.session_state.current_subject = subject
                    else:
                        st.error("❌ 題目格式解析失敗，請重試")
                except Exception as e:
                    st.error(f"API 錯誤：{e}")

    if (
        st.session_state.current_question
        and st.session_state.get("current_mode") == "弱點診斷"
    ):
        q = st.session_state.current_question
        if q.get("misconceptions"):
            with st.expander("⚠️ 本題針對的常見迷思概念（建議作答後再展開）"):
                for m in q["misconceptions"]:
                    st.markdown(f"• {m}")

    render_question_and_submit("弱點診斷", subject, topic)
    if st.session_state.current_question:
        render_analysis("弱點診斷", st.session_state.current_question)

# ══════════════════════════════════════════════
#  分頁 4 ── 學習歷程
# ══════════════════════════════════════════════
with tab_hist:
    st.markdown("### 📊 學習歷程分析")
    total_q = sum(s["count"] for s in st.session_state.subject_scores.values())

    if total_q == 0:
        st.info("📝 開始作答後，這裡會顯示你的學習歷程與能力雷達圖。")
        st.markdown("""
<div class="step-box">
<div class="step-title">🚀 快速開始</div>
1. 在左側選擇 <b>科目 → 章節 → 主題</b><br>
2. 前往「模擬考題」或「弱點診斷」頁面點擊生成按鈕<br>
3. 作答並提交後，系統自動記錄 <b>P（正確率）、S（策略）、L（邏輯）</b> 三維分數<br>
4. 回到此頁面查看雷達圖與作答記錄
</div>
""", unsafe_allow_html=True)
    else:
        # 統計摘要
        correct_q = sum(1 for h in st.session_state.history if h.get("correct"))
        avg_p = sum(
            s["P"] for s in st.session_state.subject_scores.values() if s["count"] > 0
        ) / max(1, sum(1 for s in st.session_state.subject_scores.values() if s["count"] > 0))

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("總作答題數", total_q)
        c2.metric("答對題數", correct_q)
        c3.metric("整體正確率", f"{correct_q/total_q*100:.1f}%")
        c4.metric("平均 P 分", f"{avg_p:.1f}")

        st.markdown("---")

        # 雷達圖 + 各科分數
        col_radar, col_detail = st.columns([3, 2])
        with col_radar:
            st.plotly_chart(radar_chart(), use_container_width=True)
        with col_detail:
            st.markdown("#### 各科目詳細分數")
            for subj, sc in st.session_state.subject_scores.items():
                if sc["count"] > 0:
                    st.markdown(f"**{subj}**（{sc['count']} 題）")
                    cc1, cc2, cc3 = st.columns(3)
                    p_delta = round(sc["P"] - 60, 1)
                    cc1.metric("P", f"{sc['P']:.1f}", delta=p_delta,
                               delta_color="normal" if p_delta >= 0 else "inverse")
                    cc2.metric("S", f"{sc['S']:.1f}")
                    cc3.metric("L", f"{sc['L']:.1f}")
                    st.divider()

        # 弱點建議
        weak_subjects = [
            subj for subj, sc in st.session_state.subject_scores.items()
            if sc["count"] > 0 and sc["P"] < 60
        ]
        if weak_subjects:
            st.warning(
                f"📌 **建議加強科目：** {'、'.join(weak_subjects)}（P 分低於 60，概念理解需補強）"
            )

        # 作答記錄表
        if st.session_state.history:
            st.markdown("#### 📋 作答記錄（最近 20 筆）")
            rows = []
            for h in reversed(st.session_state.history[-20:]):
                rows.append({
                    "時間": h.get("time", ""),
                    "科目": h.get("subject", ""),
                    "主題": h.get("topic", ""),
                    "模式": h.get("mode", ""),
                    "結果": "✅ 正確" if h.get("correct") else "❌ 錯誤",
                    "P 分": f"{h.get('p_score', 0):.0f}",
                })
            st.dataframe(rows, use_container_width=True, hide_index=True)

        if st.button("🗑️ 清除本次記錄", type="secondary"):
            st.session_state.history = []
            st.session_state.subject_scores = {
                s: {"P": 50.0, "S": 50.0, "L": 50.0, "count": 0} for s in CURRICULUM
            }
            st.rerun()
