"""文件夹结构重组规划测试。"""
import os

import pytest

from naskb.common.desc_store import FileEntry, NaskbStore
from naskb.common.fs.local import LocalAdapter
from naskb.common.reorganizer import Reorganizer


@pytest.fixture
def messy_dir(tmp_path):
    root = tmp_path / "messy"
    root.mkdir(parents=True)
    (root / "发票1.pdf").write_bytes(b"%PDF fake")
    (root / "照片1.jpg").write_bytes(b"fake jpg")
    (root / "项目计划.txt").write_text("计划", encoding="utf-8")
    fs = LocalAdapter(str(root))
    store = NaskbStore(fs)
    for name, cat in (("发票1.pdf", "财务"), ("照片1.jpg", "图片"),
                      ("项目计划.txt", "文档")):
        store.set_entry(str(root / name),
                        FileEntry(original_path=name, summary=f"{cat}文件",
                                  category=cat))
    return root


class _FakePlanLLM:
    def __init__(self, plan):
        self._plan = plan

    def complete_json(self, prompt: str) -> dict:
        assert "文件清单" in prompt
        return self._plan


class TestCollect:
    def test_collect_items_with_category(self, messy_dir):
        store = NaskbStore(LocalAdapter(str(messy_dir)))
        rz = Reorganizer()
        data = rz.collect(store, ".")
        assert data["total"] == 3
        cats = {it["category"] for it in data["items"]}
        assert cats == {"财务", "图片", "文档"}


class TestPlan:
    def test_plan_no_llm(self, messy_dir):
        store = NaskbStore(LocalAdapter(str(messy_dir)))
        rz = Reorganizer(llm_client=None)
        plan = rz.plan(store, ".")
        assert plan["moves"] == []
        assert "无方案" in plan["plan_name"]

    def test_plan_with_llm(self, messy_dir):
        store = NaskbStore(LocalAdapter(str(messy_dir)))
        plan_data = {
            "plan_name": "按类型归类",
            "rationale": "把平铺文件按类别收进子目录",
            "new_folders": ["财务", "图片", "文档"],
            "moves": [
                {"from": str(messy_dir / "发票1.pdf"), "to": str(messy_dir / "财务" / "发票1.pdf"),
                 "reason": "财务凭证"},
                {"from": str(messy_dir / "照片1.jpg"), "to": str(messy_dir / "图片" / "照片1.jpg"),
                 "reason": "照片归档"},
                {"from": "", "to": "缺from应被过滤", "reason": ""},
            ],
        }
        rz = Reorganizer(llm_client=_FakePlanLLM(plan_data))
        plan = rz.plan(store, ".")
        assert plan["plan_name"] == "按类型归类"
        assert len(plan["moves"]) == 2  # 缺 from 的条目被过滤
        assert plan["moves"][0]["to"].endswith(os.path.join("财务", "发票1.pdf"))

    def test_plan_filters_noop_moves(self, messy_dir):
        """from == to 的 no-op 移动应在 plan 阶段被过滤。"""
        store = NaskbStore(LocalAdapter(str(messy_dir)))
        same = str(messy_dir / "发票1.pdf")
        plan_data = {
            "plan_name": "含 no-op",
            "rationale": "",
            "new_folders": [],
            "moves": [
                {"from": same, "to": same, "reason": "无需移动"},
                {"from": str(messy_dir / "照片1.jpg"),
                 "to": str(messy_dir / "图片" / "照片1.jpg"), "reason": "归档"},
            ],
        }
        rz = Reorganizer(llm_client=_FakePlanLLM(plan_data))
        plan = rz.plan(store, ".")
        assert len(plan["moves"]) == 1
        assert plan["moves"][0]["from"].endswith("照片1.jpg")

    def test_collect_returns_all_files(self, tmp_path):
        """collect 全量返回，不再截断前 N 个文件。"""
        root = tmp_path / "big"
        root.mkdir(parents=True)
        for i in range(50):
            (root / f"f{i}.txt").write_text("x", encoding="utf-8")
        store = NaskbStore(LocalAdapter(str(root)))
        rz = Reorganizer(max_files=10)   # 文件数远超单片上限
        data = rz.collect(store, ".")
        assert data["total"] == 50
        assert len(data["items"]) == 50   # 不截断

    def test_plan_chunked_two_stage(self, tmp_path):
        """文件超上限 → 分片两阶段：阶段 A 逐片归类，阶段 B 汇总成案。

        阶段 A 的 folder 全部来自分片清单（不遗漏），阶段 B 只基于汇总。
        """
        root = tmp_path / "big"
        (root / "发票").mkdir(parents=True)
        (root / "照片").mkdir(parents=True)
        for i in range(30):
            (root / "发票" / f"票{i}.pdf").write_bytes(b"%PDF fake")
            (root / "照片" / f"片{i}.jpg").write_bytes(b"fake")
        store = NaskbStore(LocalAdapter(str(root)))
        for p in store._fs.list_files(".", recursive=True):
            if not p.is_dir:
                store.set_entry(p.path, FileEntry(original_path=p.name,
                                                  summary="内容", category=""))

        class _TwoStageLLM:
            def __init__(self):
                self.calls = []

            def complete_json(self, prompt):
                if "归类汇总" in prompt:
                    # 阶段 B：最终方案（moves 基于阶段 A 的 folder 生成）
                    self.calls.append("B")
                    return {
                        "plan_name": "两阶段方案",
                        "rationale": "汇总",
                        "new_folders": ["财务", "照片"],
                        "moves": [
                            {"from": str(root / "发票"),
                             "to": str(root / "财务" / "发票"), "reason": "归财务"},
                            {"from": str(root / "照片"),
                             "to": str(root / "照片"), "reason": "no-op"},
                        ],
                    }
                # 阶段 A：逐片归类
                self.calls.append("A")
                folders = []
                for line in prompt.splitlines():
                    if line.startswith("【目录】"):
                        folders.append(line.split("【目录】")[1].split("（")[0])
                return {"groups": [
                    {"folder": f, "target": "财务" if "发票" in f else "照片",
                     "reason": "test"} for f in folders]}

        llm = _TwoStageLLM()
        rz = Reorganizer(llm_client=llm, max_files=10)
        plan = rz.plan(store, ".")
        # 阶段 A 调用了 2 次（60 文件 / 10 每片 > 1），阶段 B 1 次
        assert llm.calls.count("A") == 2, llm.calls
        assert llm.calls.count("B") == 1
        assert plan["plan_name"] == "两阶段方案"
        assert len(plan["moves"]) == 1          # no-op 被过滤
        assert plan["moves"][0]["from"].endswith("发票")
        assert plan["moves"][0]["to"].endswith(os.path.join("财务", "发票"))


class TestApply:
    def test_apply_moves_files_and_entries(self, messy_dir):
        store = NaskbStore(LocalAdapter(str(messy_dir)))
        rz = Reorganizer(llm_client=None)
        plan = {
            "moves": [
                {"from": str(messy_dir / "发票1.pdf"),
                 "to": str(messy_dir / "财务" / "发票1.pdf"), "reason": ""},
                {"from": str(messy_dir / "照片1.jpg"),
                 "to": str(messy_dir / "图片" / "照片1.jpg"), "reason": ""},
            ],
        }
        result = rz.apply(store, plan)
        assert len(result["moved"]) == 2
        assert result["failed"] == []
        # 文件真的移动了
        assert (messy_dir / "财务" / "发票1.pdf").exists()
        assert not (messy_dir / "发票1.pdf").exists()
        # 描述条目跟随到新位置且在新目录仓库中可查
        moved = store.get_entry(str(messy_dir / "财务" / "发票1.pdf"))
        assert moved is not None and moved.category == "财务"

    def test_apply_failure_reported(self, messy_dir):
        store = NaskbStore(LocalAdapter(str(messy_dir)))
        rz = Reorganizer(llm_client=None)
        plan = {"moves": [{"from": str(messy_dir / "不存在的.pdf"),
                           "to": str(messy_dir / "x" / "y.pdf"), "reason": ""}]}
        result = rz.apply(store, plan)
        assert result["moved"] == []
        assert len(result["failed"]) == 1

    def test_apply_moves_whole_directory(self, tmp_path):
        """目录级移动：from 是目录时递归移动其下所有文件，条目跟随。"""
        root = tmp_path / "tree"
        src = root / "旧项目"
        (src / "子目录").mkdir(parents=True)
        (src / "a.txt").write_text("A", encoding="utf-8")
        (src / "子目录" / "b.txt").write_text("B", encoding="utf-8")
        store = NaskbStore(LocalAdapter(str(root)))
        for p in (src / "a.txt", src / "子目录" / "b.txt"):
            store.set_entry(str(p), FileEntry(original_path=p.name,
                                              summary="条目", category="项目"))
        rz = Reorganizer(llm_client=None)
        plan = {"moves": [{"from": str(src), "to": str(root / "归档项目"),
                           "reason": "整目录归档"}]}
        result = rz.apply(store, plan)
        assert len(result["moved"]) == 2
        assert result["failed"] == []
        assert (root / "归档项目" / "a.txt").exists()
        assert (root / "归档项目" / "子目录" / "b.txt").exists()
        assert not (src / "a.txt").exists()
        # 条目跟随到新位置
        assert store.get_entry(str(root / "归档项目" / "a.txt")) is not None
        assert store.get_entry(str(root / "归档项目" / "子目录" / "b.txt")) is not None

    def test_apply_moves_artifacts(self, tmp_path):
        """整仓跟随：目录移动时 .naskb（artifacts/folder.json/meta.json）迁到
        目标，源 .naskb 空壳移除；目标已有的 folder.json 保留。"""
        root = tmp_path / "tree"
        src = root / "旧项目"
        (src / ".naskb" / "artifacts" / "a文档").mkdir(parents=True)
        (src / ".naskb" / "artifacts" / "a文档" / "a.md").write_text(
            "MinerU 产物", encoding="utf-8")
        (src / ".naskb" / "folder.json").write_text("{}", encoding="utf-8")
        (src / ".naskb" / "meta.json").write_text("{}", encoding="utf-8")
        (src / "a.txt").write_text("A", encoding="utf-8")
        store = NaskbStore(LocalAdapter(str(root)))
        store.set_entry(str(src / "a.txt"), FileEntry(original_path="a.txt",
                                                      summary="条目", category=""))
        rz = Reorganizer(llm_client=None)
        plan = {"moves": [{"from": str(src), "to": str(root / "归档项目"),
                           "reason": "整目录归档"}]}
        result = rz.apply(store, plan)
        assert result["failed"] == []
        # artifacts 迁到目标目录的 .naskb 下
        assert (root / "归档项目" / ".naskb" / "artifacts" / "a文档" / "a.md").exists()
        # folder.json / meta.json 跟随
        assert (root / "归档项目" / ".naskb" / "folder.json").exists()
        assert (root / "归档项目" / ".naskb" / "meta.json").exists()
        # 源 .naskb 空壳移除（整仓跟随，旧位置不留仓库）
        assert not (src / ".naskb").exists()
        # 源目录已无任何文件 → 按"空目录删除"原则整体移除
        assert not src.exists()
        assert str(src) in result["removed_dirs"]

    def test_apply_keeps_existing_target_folder_json(self, tmp_path):
        """目标目录已有 folder.json 时保留目标（不覆盖新生成）。"""
        root = tmp_path / "tree"
        src = root / "旧项目"
        src.mkdir(parents=True)
        (src / "a.txt").write_text("A", encoding="utf-8")
        store = NaskbStore(LocalAdapter(str(root)))
        store.set_entry(str(src / "a.txt"), FileEntry(original_path="a.txt",
                                                      summary="条目", category=""))
        dst = root / "新目录"
        dst.mkdir(parents=True)
        (dst / ".naskb").mkdir(parents=True)
        (dst / ".naskb" / "folder.json").write_text('{"new": true}',
                                                    encoding="utf-8")
        rz = Reorganizer(llm_client=None)
        plan = {"moves": [{"from": str(src), "to": str(dst), "reason": "合并"}]}
        result = rz.apply(store, plan)
        assert result["failed"] == []
        assert (dst / "a.txt").exists()
        assert '"new": true' in (dst / ".naskb" / "folder.json").read_text(
            encoding="utf-8")

    def test_apply_removes_empty_source_dir(self, tmp_path):
        """整目录搬空后源目录被删除（只删空目录树），affected_dirs 返回。"""
        root = tmp_path / "tree"
        src = root / "旧项目"
        src.mkdir(parents=True)
        (src / "a.txt").write_text("A", encoding="utf-8")
        store = NaskbStore(LocalAdapter(str(root)))
        store.set_entry(str(src / "a.txt"), FileEntry(original_path="a.txt",
                                                      summary="条目", category=""))
        rz = Reorganizer(llm_client=None)
        plan = {"moves": [{"from": str(src), "to": str(root / "归档项目"),
                           "reason": "整目录归档"}]}
        result = rz.apply(store, plan)
        assert result["failed"] == []
        # 源目录被搬空 → 删除（来源文件夹不再需要）
        assert not src.exists()
        assert (root / "归档项目" / "a.txt").exists()
        # affected_dirs 含源/目标及父目录（供 folder.json 级联）
        assert str(src) in result["affected_dirs"]
        assert str(root / "归档项目") in result["affected_dirs"]
        assert str(src) in result["removed_dirs"]

    def test_apply_keeps_nonempty_source_dir(self, tmp_path):
        """源目录仍有其他文件时保留（只删空目录）。"""
        root = tmp_path / "tree"
        src = root / "旧项目"
        src.mkdir(parents=True)
        (src / "a.txt").write_text("A", encoding="utf-8")
        (src / "b.txt").write_text("B", encoding="utf-8")   # 不移动
        store = NaskbStore(LocalAdapter(str(root)))
        store.set_entry(str(src / "a.txt"), FileEntry(original_path="a.txt",
                                                      summary="条目", category=""))
        rz = Reorganizer(llm_client=None)
        plan = {"moves": [{"from": str(src / "a.txt"),
                           "to": str(root / "归档" / "a.txt"), "reason": "移文件"}]}
        result = rz.apply(store, plan)
        assert result["failed"] == []
        assert src.exists()                      # 非空 → 保留
        assert (src / "b.txt").exists()
        assert result["removed_dirs"] == []      # 没有删除任何目录

    def test_apply_child_before_parent(self, tmp_path):
        """子路径优先：即使方案里父目录移动排在子目录之前，也先移子目录。"""
        root = tmp_path / "tree"
        parent = root / "原创文章"
        child = parent / "本科"
        child.mkdir(parents=True)
        (child / "a.pdf").write_bytes(b"%PDF")
        (parent / "b.txt").write_text("B", encoding="utf-8")
        store = NaskbStore(LocalAdapter(str(root)))
        for p in (child / "a.pdf", parent / "b.txt"):
            store.set_entry(str(p), FileEntry(original_path=p.name,
                                              summary="条目", category=""))
        rz = Reorganizer(llm_client=None)
        plan = {"moves": [
            # 故意乱序：父目录移动在前、子目录抽取在后
            {"from": str(parent), "to": str(root / "03_工作与经营" / "原创文章"),
             "reason": "父先"},
            {"from": str(child), "to": str(root / "08_学习" / "本科"),
             "reason": "子后"},
        ]}
        result = rz.apply(store, plan)
        assert result["failed"] == [], result["failed"]
        assert len(result["moved"]) == 2
        # 子目录先被抽走，父目录再整体移动，互不冲突
        assert (root / "08_学习" / "本科" / "a.pdf").exists()
        assert (root / "03_工作与经营" / "原创文章" / "b.txt").exists()
        assert store.get_entry(str(root / "08_学习" / "本科" / "a.pdf")) is not None
