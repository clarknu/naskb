"""基于 .naskb 描述数据的检索与问答测试。"""
import json

import pytest

from naskb.common.desc_store import NaskbStore, FileEntry
from naskb.common.fs.local import LocalAdapter
from naskb.common.retrieval import BM25Index, Doc, ask, collect_docs, tokenize


class TestTokenize:
    def test_english_words(self):
        assert "deepseek" in tokenize("DeepSeek API")

    def test_chinese_bigram(self):
        t = tokenize("项目管理")
        assert "项" in t and "项目" in t and "管理" in t

    def test_mixed(self):
        t = tokenize("NAS 知识库 2026")
        assert "nas" in t and "2026" in t and "知识" in t


class TestBM25:
    def _index(self):
        docs = [
            Doc(path="/a/电影笔记.md", kind="file", text="电影 星际穿越 影评 诺兰",
                summary="星际穿越影评", category="影视"),
            Doc(path="/b/装修预算.xlsx", kind="file", text="装修 预算 明细 材料费用",
                summary="装修预算表", category="生活"),
            Doc(path="/c/学习笔记.md", kind="file", text="深度学习 课程笔记 神经网络",
                summary="学习笔记", category="学习"),
        ]
        idx = BM25Index()
        idx.build(docs)
        return idx

    def test_relevance_ranking(self):
        idx = self._index()
        hits = idx.search("装修", top_k=2)
        assert hits and hits[0]["path"] == "/b/装修预算.xlsx"

    def test_cjk_matching(self):
        idx = self._index()
        hits = idx.search("电影", top_k=1)
        assert hits[0]["path"] == "/a/电影笔记.md"

    def test_empty_query(self):
        idx = self._index()
        assert idx.search("不存在的内容xyz") == []

    def test_kind_filter(self):
        docs = [Doc(path="/f", kind="file", text="abc"), Doc(path="/d", kind="folder", text="abc")]
        idx = BM25Index()
        idx.build(docs)
        hits = idx.search("abc", kind="folder")
        assert len(hits) == 1 and hits[0]["kind"] == "folder"


@pytest.fixture
def repo_dir(tmp_path):
    """构造两个目录的 .naskb 仓库，各含一条描述。"""
    root = tmp_path / "kb"
    d1 = root / "影视"
    d2 = root / "学习"
    d1.mkdir(parents=True)
    d2.mkdir(parents=True)
    # 描述条目必须对应真实文件（set_entry 会计算 hash）
    (d1 / "星际穿越.mkv").write_bytes(b"fake video")
    (d2 / "机器学习笔记.pdf").write_bytes(b"%PDF fake")
    fs = LocalAdapter(str(root))
    store = NaskbStore(fs)
    e1 = FileEntry(original_path="星际穿越.mkv", summary="诺兰科幻电影，时间旅行",
                   category="影视", tags=["电影", "科幻"])
    store.set_entry(str(d1 / "星际穿越.mkv"), e1)
    e2 = FileEntry(original_path="机器学习笔记.pdf", summary="深度神经网络基础课程笔记",
                   category="学习", tags=["AI", "课程"])
    store.set_entry(str(d2 / "机器学习笔记.pdf"), e2)
    return root


class TestCollectDocs:
    def test_collect_file_and_folder(self, repo_dir):
        fs = LocalAdapter(str(repo_dir))
        docs = collect_docs(fs, ".")
        paths = [d.path for d in docs]
        assert any(p.endswith("星际穿越.mkv") for p in paths)
        assert any(p.endswith("机器学习笔记.pdf") for p in paths)
        for d in docs:
            assert d.text.strip()

    def test_empty_root(self, tmp_path):
        fs = LocalAdapter(str(tmp_path))
        assert collect_docs(fs, ".") == []


class _FakeChat:
    def __init__(self):
        self.last_prompt = ""

    def complete(self, prompt: str) -> str:
        self.last_prompt = prompt
        return "根据描述，星际穿越是诺兰的科幻电影。\n来源: /a"


class TestAsk:
    def test_ask_uses_retrieved_context(self):
        idx = BM25Index()
        idx.build([Doc(path="/a", kind="file", text="星际穿越 诺兰 科幻",
                       summary="科幻电影", category="影视")])
        fake = _FakeChat()
        result = ask(fake, idx, "星际穿越是谁拍的？")
        assert "星际穿越" in result["answer"]
        assert result["sources"] == ["/a"]
        assert "检索到的内容" in fake.last_prompt

    def test_ask_context_contains_full_text(self):
        """RAG 上下文必须包含完整文本细节（不只是摘要）。"""
        idx = BM25Index()
        full = ("慈水心境租约：甲方王春燕，乙方牛智瀚。"
                "月租金人民币1500元，保证金1500元，水费6元每吨。")
        idx.build([Doc(path="/租约.pdf", kind="file", text=full,
                       summary="甲乙双方签订房屋租赁合同", category="租赁合同")])
        fake = _FakeChat()
        result = ask(fake, idx, "月租金是多少？和谁签的？")
        # 细节文本必须进入 prompt
        assert "王春燕" in fake.last_prompt
        assert "1500" in fake.last_prompt
        assert result["sources"] == ["/租约.pdf"]

    def test_ask_context_budget_trimmed(self):
        """超长文本按 context_chars 预算裁剪，不无限膨胀。"""
        idx = BM25Index()
        long_text = "内容" * 5000  # 10000 字符
        idx.build([Doc(path="/long", kind="file", text=long_text, summary="长文档")])
        fake = _FakeChat()
        ask(fake, idx, "测试", context_chars=1000)
        assert len(fake.last_prompt) < 4000  # 上下文被裁剪

    def test_ask_no_hits(self):
        idx = BM25Index()
        idx.build([Doc(path="/a", kind="file", text="完全无关内容", summary="x")])
        fake = _FakeChat()
        result = ask(fake, idx, "zzz不存在的问题")
        assert "没有找到" in result["answer"]
        assert result["sources"] == []


class TestEndToEnd:
    def test_search_over_repo(self, repo_dir):
        """desc search 核心链路：建索引 → 模糊搜索命中中文描述。"""
        fs = LocalAdapter(str(repo_dir))
        docs = collect_docs(fs, ".")
        idx = BM25Index()
        idx.build(docs)
        hits = idx.search("科幻", top_k=5)
        assert hits and "星际穿越" in hits[0]["path"]
        hits2 = idx.search("课程笔记", top_k=5)
        assert hits2 and "机器学习笔记" in hits2[0]["path"]

    def test_collect_docs_reads_data_file_full_text(self, repo_dir):
        """条目拆分到独立原数据文件后，collect_docs 仍能拿到全文细节。"""
        fs = LocalAdapter(str(repo_dir))
        # 模拟拆分：把星际穿越条目的全文拆进 files/（懒迁移后的形态）
        store = NaskbStore(fs)
        e = store.get_entry(str(repo_dir / "影视" / "星际穿越.mkv"))
        assert e is not None
        full = "星际穿越 诺兰导演 五维空间 墨菲 时间旅行 黑洞"
        e.ocr_text = full
        store.set_entry(str(repo_dir / "影视" / "星际穿越.mkv"), e)
        # 手动模拟懒迁移前的旧状态再走一遍 collect_docs
        docs = collect_docs(fs, ".")
        doc = next(d for d in docs if "星际穿越" in d.path)
        # 检索文本 = 摘要+描述（不含全文——用户拍板）；
        # 全文在 context（RAG 生成阶段使用）
        assert "五维空间" not in doc.text
        assert "五维空间" in doc.context
        assert "黑洞" in doc.context
