import os

from dotenv import load_dotenv
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_openrouter import ChatOpenRouter
import streamlit as st
from wiki_store import WikiStore

# --------------------------------------------------
# 页面设置
# --------------------------------------------------
st.set_page_config(
    page_title="My LLM Wiki",
    page_icon="📚",
    layout="wide",
)

# --------------------------------------------------
# 环境变量与基本设置
# --------------------------------------------------
load_dotenv()
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "openrouter/free")
OPENROUTER_APP_NAME = os.getenv("OPENROUTER_APP_NAME", "My LLM Wiki Chatbot")
OPENROUTER_APP_URL = os.getenv("OPENROUTER_APP_URL", "http://localhost:8501")

TOP_K = 4
MAX_PAGE_CHARS = 12_000
MAX_TOTAL_CONTEXT_CHARS = 35_000
MAX_HISTORY_MESSAGES = 6


# --------------------------------------------------
# Wiki Store
# --------------------------------------------------
@st.cache_resource
def load_wiki_store() -> WikiStore:
    """读取网站项目自己的 Wiki 副本并建立检索索引。

    当前应用只读取 Wiki，不修改任何 Markdown 文件。
    """
    wiki_store = WikiStore()
    wiki_store.load()
    return wiki_store


# --------------------------------------------------
# OpenRouter 模型
# --------------------------------------------------
@st.cache_resource
def load_chat_model() -> ChatOpenRouter:
    """建立 LangChain ChatOpenRouter 模型。

    模型对象会被 Streamlit 缓存，避免每次提问都重新建立。
    """
    if not OPENROUTER_API_KEY:
        raise RuntimeError(
            "尚未设置 OPENROUTER_API_KEY。请在 .env 文件中加入 OpenRouter API Key。"
        )
    return ChatOpenRouter(
        model=OPENROUTER_MODEL,
        temperature=0.8,
    )


# --------------------------------------------------
# Wiki 上下文
# --------------------------------------------------
def build_context(results: list[dict]) -> str:
    """把检索出的 Wiki 页面组合成模型上下文。

    每个页面会有固定编号。模型回答中的 [1]、[2] 将对应这些编号。
    """
    sections = []
    total_length = 0

    for index, result in enumerate(results, start=1):
        page_content = result.get("body", result.get("content", ""))
        page_content = page_content[:MAX_PAGE_CHARS]

        section = f"""=== WIKI PAGE {index} ===
Citation: [{index}]
Path: {result.get("path", "unknown")}
Title: {result.get("title", "Untitled")}
Reviewed: {result.get("reviewed", False)}
Confidence: {result.get("confidence", "unknown")}
Status: {result.get("status", "unknown")}

{page_content}""".strip()

        if total_length + len(section) > MAX_TOTAL_CONTEXT_CHARS:
            break

        sections.append(section)
        total_length += len(section)

    return "\n\n".join(sections)


def convert_history_to_langchain_messages(
    conversation_history: list[dict],
) -> list:
    """将 Streamlit session 中的对话记录转换为 LangChain Message 对象。

    sources 等 UI 字段不会发送给模型。
    """
    messages = []
    recent_history = conversation_history[-MAX_HISTORY_MESSAGES:]

    for message in recent_history:
        role = message.get("role")
        content = message.get("content", "")
        if not content:
            continue
        if role == "user":
            messages.append(HumanMessage(content=content))
        elif role == "assistant":
            messages.append(AIMessage(content=content))

    return messages


# --------------------------------------------------
# LLM 回答
# --------------------------------------------------
def answer_question(
    question: str,
    search_results: list[dict],
    conversation_history: list[dict],
) -> str:
    """使用 ChatOpenRouter 根据检索出的 Wiki 页面回答问题。"""
    if not search_results:
        return "当前 Wiki 中没有找到与这个问题明显相关的页面。"

    model = load_chat_model()
    context = build_context(search_results)
    if not context:
        return "当前 Wiki 检索到了页面，但页面没有可用内容。"

    system_prompt = """
你是一个只读的 LLM Wiki 问答助手。
你只能根据本次提供的 Wiki 页面回答问题。

回答规则：
1. 不得使用没有出现在 Wiki 上下文中的事实。
2. 不得声称已经查看本次上下文以外的文件。
3. 不得使用模型自身知识补充 Wiki 中缺少的内容。
4. 如果 Wiki 没有足够资料，必须明确回答：“当前 Wiki 资料不足。”
5. 如果资料不足，应说明 Wiki 缺少哪一类资料。
6. 区分以下内容：
   - Wiki 明确记载的内容
   - 根据多个 Wiki 页面形成的综合判断
   - 不确定内容
7. 回答中的事实或结论应使用 [1]、[2] 等编号引用。
8. 引用编号必须对应本次提供的 Wiki 页面。
9. 不得创造不存在的引用编号。
10. 不得声称已经修改、更新或写回任何文件。
11. 使用与用户相同的语言回答。
12. 回答应优先清楚、直接和结构化。
""".strip()

    query_prompt = f"""
以下是从 Wiki 中检索出的相关页面：
{context}

用户当前问题：
{question}

请严格根据以上 Wiki 页面回答。

引用要求：
- 使用 [1]、[2] 等页面编号。
- 每项重要事实或结论后都应标明引用。
- 不要引用未提供的页面。
- 如果页面内容不足，请明确说明。
""".strip()

    messages = [
        SystemMessage(content=system_prompt),
        *convert_history_to_langchain_messages(conversation_history),
        HumanMessage(content=query_prompt),
    ]

    response = model.invoke(messages)
    if isinstance(response.content, str):
        return response.content

    # 某些模型可能返回结构化 content block。
    return str(response.content)


# --------------------------------------------------
# 初始化 Wiki
# --------------------------------------------------
try:
    store = load_wiki_store()
except Exception as error:
    st.error(f"无法载入 Wiki：{error}")
    st.info("请先确认网站项目已经同步知识 repo，并且 data/source-repo/wiki/ 存在。")
    st.stop()

# --------------------------------------------------
# Streamlit UI
# --------------------------------------------------
st.title("📚 My LLM Wiki")
st.caption("从网站项目自己的 Wiki 副本中检索知识，并通过 OpenRouter 模型生成回答。")

if "messages" not in st.session_state:
    st.session_state.messages = []

# --------------------------------------------------
# Sidebar
# --------------------------------------------------
with st.sidebar:
    st.header("Wiki 状态")
    document_count = len(store.documents)
    reviewed_count = sum(
        1 for document in store.documents if document.get("reviewed") is True
    )

    st.metric("Markdown 页面", document_count)
    st.metric("已审核页面", reviewed_count)
    st.write(f"模型：`{OPENROUTER_MODEL}`")
    st.write("知识来源：`data/source-repo/wiki/`")
    st.divider()

    if st.button("重新载入 Wiki", use_container_width=True):
        st.cache_resource.clear()
        st.rerun()

    if st.button("清除对话", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

# --------------------------------------------------
# 显示历史消息
# --------------------------------------------------
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        sources = message.get("sources", [])
        if sources:
            with st.expander("参考 Wiki 页面"):
                for index, source in enumerate(sources, start=1):
                    st.markdown(f"**[{index}] {source['title']}**")
                    st.code(source["path"], language=None)

# --------------------------------------------------
# 用户提问
# --------------------------------------------------
question = st.chat_input("请针对 Wiki 内容提问")

if question:
    # 保存当前问题加入前的对话历史，防止当前问题被发送给 LLM 两次
    previous_history = st.session_state.messages.copy()
    st.session_state.messages.append({"role": "user", "content": question})

    with st.chat_message("user"):
        st.markdown(question)

    try:
        search_results = store.search(question=question, top_k=TOP_K)
    except TypeError:
        # 兼容 search() 没有使用命名参数的写法
        search_results = store.search(question, top_k=TOP_K)

    with st.chat_message("assistant"):
        if not search_results:
            answer = "当前 Wiki 中没有找到与这个问题明显相关的页面。"
            st.warning(answer)
        else:
            with st.status("正在查询 Wiki...", expanded=False) as status:
                st.write(f"找到 {len(search_results)} 个相关页面。")
                try:
                    answer = answer_question(
                        question=question,
                        search_results=search_results,
                        conversation_history=previous_history,
                    )
                    status.update(label="Wiki 查询完成", state="complete")
                except Exception as error:
                    answer = f"生成回答失败：{type(error).__name__}: {error}"
                    status.update(label="回答生成失败", state="error")

            st.markdown(answer)

            with st.expander("参考 Wiki 页面", expanded=True):
                for index, result in enumerate(search_results, start=1):
                    reviewed_text = (
                        "已审核" if result.get("reviewed") is True else "未审核"
                    )
                    title = result.get("title", "Untitled")
                    path = result.get("path", "unknown")
                    confidence = result.get("confidence", "unknown")
                    score = result.get("score", 0.0)

                    st.markdown(f"**[{index}] {title}**")
                    st.code(path, language=None)
                    st.caption(
                        f"{reviewed_text} · Confidence: {confidence} · 相关度: {score:.3f}"
                    )

            sources = [
                {
                    "path": result.get("path", "unknown"),
                    "title": result.get("title", "Untitled"),
                }
                for result in search_results
            ]
            st.session_state.messages.append(
                {
                    "role": "assistant",
                    "content": answer,
                    "sources": sources,
                }
            )
