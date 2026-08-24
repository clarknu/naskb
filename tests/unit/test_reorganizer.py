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


class TestSafetyValidation:
    """P0-1 越界硬校验：plan 阶段过滤 + apply 阶段双保险。"""

    def test_plan_rejects_out_of_root_to(self, messy_dir):
        """目标路径越界（root 之外）→ 进 rejected，不进入 moves。"""
        store = NaskbStore(LocalAdapter(str(messy_dir)))
        outside = str(messy_dir.parent / "外来" / "发票1.pdf")
        plan_data = {
            "plan_name": "越界",
            "rationale": "",
            "new_folders": [],
            "moves": [
                {"from": str(messy_dir / "发票1.pdf"), "to": outside,
                 "reason": "越界"},
                {"from": str(messy_dir / "照片1.jpg"),
                 "to": str(messy_dir / "图片" / "照片1.jpg"), "reason": "合法"},
            ],
        }
        rz = Reorganizer(llm_client=_FakePlanLLM(plan_data))
        plan = rz.plan(store, ".")
        assert len(plan["moves"]) == 1
        assert plan["moves"][0]["from"].endswith("照片1.jpg")
        assert len(plan["rejected"]) == 1
        assert "越界" in plan["rejected"][0]["reason"]

    def test_plan_rejects_dotdot_and_naskb(self, messy_dir):
        """`..` 穿越 与 .naskb 仓库内部路径 → 全部 rejected。"""
        store = NaskbStore(LocalAdapter(str(messy_dir)))
        plan_data = {
            "plan_name": "攻击路径",
            "rationale": "",
            "new_folders": [],
            "moves": [
                {"from": str(messy_dir / "发票1.pdf"),
                 "to": str(messy_dir / ".." / "逃逸.pdf"), "reason": ".."},
                {"from": str(messy_dir / "照片1.jpg"),
                 "to": str(messy_dir / ".naskb" / "x.jpg"), "reason": "仓库"},
            ],
        }
        rz = Reorganizer(llm_client=_FakePlanLLM(plan_data))
        plan = rz.plan(store, ".")
        assert plan["moves"] == []
        assert len(plan["rejected"]) == 2

    def test_plan_rejects_source_not_in_listing(self, messy_dir):
        """LLM 幻觉出不存在的源路径 → rejected（防移不存在的文件）。"""
        store = NaskbStore(LocalAdapter(str(messy_dir)))
        plan_data = {
            "plan_name": "幻觉路径",
            "rationale": "",
            "new_folders": [],
            "moves": [
                {"from": str(messy_dir / "幻觉文件.pdf"),
                 "to": str(messy_dir / "财务" / "幻觉文件.pdf"), "reason": "不存在"},
            ],
        }
        rz = Reorganizer(llm_client=_FakePlanLLM(plan_data))
        plan = rz.plan(store, ".")
        assert plan["moves"] == []
        assert len(plan["rejected"]) == 1
        assert "清单" in plan["rejected"][0]["reason"]

    def test_plan_allows_dir_move_via_ancestor(self, tmp_path):
        """目录级 move：from 是含文件的目录（不在 items，但为文件祖先）→ 合法。"""
        root = tmp_path / "tree"
        (root / "发票").mkdir(parents=True)
        (root / "发票" / "a.pdf").write_bytes(b"%PDF")
        (root / "b.jpg").write_bytes(b"jpg")
        store = NaskbStore(LocalAdapter(str(root)))
        store.set_entry(str(root / "发票" / "a.pdf"),
                        FileEntry(original_path="a.pdf", summary="票", category=""))
        store.set_entry(str(root / "b.jpg"),
                        FileEntry(original_path="b.jpg", summary="图", category=""))
        plan_data = {
            "plan_name": "目录归并",
            "rationale": "",
            "new_folders": ["财务"],
            "moves": [
                {"from": str(root / "发票"), "to": str(root / "财务" / "发票"),
                 "reason": "整目录归财务"},
            ],
        }
        rz = Reorganizer(llm_client=_FakePlanLLM(plan_data))
        plan = rz.plan(store, ".")
        assert len(plan["moves"]) == 1
        assert plan["rejected"] == []

    def test_apply_blocks_out_of_root_when_root_in_plan(self, messy_dir):
        """apply 双保险：plan 带 root 时越界 move 被拦截且文件未移动。"""
        store = NaskbStore(LocalAdapter(str(messy_dir)))
        rz = Reorganizer(llm_client=None)
        plan = {
            "root": str(messy_dir),
            "moves": [
                {"from": str(messy_dir / "发票1.pdf"),
                 "to": str(messy_dir.parent / "外部" / "发票1.pdf"), "reason": "越界"},
            ],
        }
        result = rz.apply(store, plan)
        assert result["moved"] == []
        assert len(result["rejected"]) == 1
        assert (messy_dir / "发票1.pdf").exists()      # 未移动
        assert not (messy_dir.parent / "外部" / "发票1.pdf").exists()

    def test_apply_legacy_plan_without_root_still_works(self, messy_dir):
        """无 root 的旧 plan（现有调用方）行为不变：不拦截、正常移动。"""
        store = NaskbStore(LocalAdapter(str(messy_dir)))
        rz = Reorganizer(llm_client=None)
        plan = {"moves": [
            {"from": str(messy_dir / "发票1.pdf"),
             "to": str(messy_dir / "财务" / "发票1.pdf"), "reason": ""},
        ]}
        result = rz.apply(store, plan)
        assert len(result["moved"]) == 1
        assert result["failed"] == []
        assert result["rejected"] == []


class TestSnapshotRecheck:
    """P0-3 apply 快照复检：源消失 → not_found；内容已变 → stale_source。"""

    def _store_with_hash(self, root, name, content):
        store = NaskbStore(LocalAdapter(str(root)))
        f = root / name
        f.write_text(content, encoding="utf-8")
        _alg, h = store.compute_hash(str(f))
        store.set_entry(str(f), FileEntry(original_path=name, summary="s",
                                          category="c", file_hash=h))
        return store, f, h

    def test_apply_moves_when_snapshot_matches(self, tmp_path):
        root = tmp_path / "t"
        root.mkdir(parents=True)
        store, f, h = self._store_with_hash(root, "a.txt", "AAA")
        rz = Reorganizer(llm_client=None)
        plan = {"root": str(root),
                "moves": [{"from": str(f), "to": str(root / "子" / "a.txt"),
                           "reason": ""}]}
        snap = {os.path.normcase(os.path.normpath(str(f))): h}
        result = rz.apply(store, plan, snap)
        assert len(result["moved"]) == 1
        assert result["failed"] == []
        assert (root / "子" / "a.txt").exists()

    def test_apply_rejects_stale_source(self, tmp_path):
        """plan 生成后文件内容被改动 → stale_source，不移动。"""
        root = tmp_path / "t"
        root.mkdir(parents=True)
        store, f, h = self._store_with_hash(root, "a.txt", "AAA")
        f.write_text("BBB", encoding="utf-8")          # 内容已变
        rz = Reorganizer(llm_client=None)
        plan = {"root": str(root),
                "moves": [{"from": str(f), "to": str(root / "子" / "a.txt"),
                           "reason": ""}]}
        snap = {os.path.normcase(os.path.normpath(str(f))): h}
        result = rz.apply(store, plan, snap)
        assert result["moved"] == []
        assert len(result["failed"]) == 1
        assert result["failed"][0]["reason"] == "stale_source"
        assert (root / "a.txt").exists()               # 未移动
        assert not (root / "子" / "a.txt").exists()

    def test_apply_rejects_not_found(self, tmp_path):
        """plan 生成后源文件被删除 → not_found，不移动。"""
        root = tmp_path / "t"
        root.mkdir(parents=True)
        store, f, h = self._store_with_hash(root, "a.txt", "AAA")
        f.unlink()                                     # 文件消失
        rz = Reorganizer(llm_client=None)
        plan = {"root": str(root),
                "moves": [{"from": str(f), "to": str(root / "子" / "a.txt"),
                           "reason": ""}]}
        snap = {os.path.normcase(os.path.normpath(str(f))): h}
        result = rz.apply(store, plan, snap)
        assert result["moved"] == []
        assert len(result["failed"]) == 1
        assert result["failed"][0]["reason"] == "not_found"

    def test_plan_returns_snapshot_with_hash(self, tmp_path):
        """plan 携带 snapshot：collect 中已分析条目的 file_hash 进入快照。"""
        root = tmp_path / "t"
        root.mkdir(parents=True)
        store, f, h = self._store_with_hash(root, "a.txt", "AAA")
        (root / "b.txt").write_text("B", encoding="utf-8")   # 无条目 → 无 hash
        rz = Reorganizer(llm_client=None)
        plan = rz.plan(store, ".")
        snap = plan["snapshot"]
        assert snap.get(os.path.normcase(os.path.normpath(str(f)))) == h
        assert len(snap) == 1                                # 仅已分析条目


class TestConflictThreeTier:
    """P0-2 冲突三档：同内容 noop / 目标无元数据 meta_only / 否则 rename。"""

    def _mk(self, tmp_path, name="a.txt", content="A"):
        root = tmp_path / "t"
        root.mkdir(parents=True)
        f = root / name
        f.write_text(content, encoding="utf-8")
        return root, f

    def test_same_content_noop(self, tmp_path):
        """内容相同 → noop：两边文件都不动，源条目保留。"""
        root, src = self._mk(tmp_path, content="same")
        dst_dir = root / "目标"
        dst_dir.mkdir()
        dst = dst_dir / "a.txt"
        dst.write_text("same", encoding="utf-8")
        store = NaskbStore(LocalAdapter(str(root)))
        store.set_entry(str(src), FileEntry(original_path="a.txt",
                                            summary="s", category="c"))
        rz = Reorganizer(llm_client=None)
        plan = {"root": str(root),
                "moves": [{"from": str(src), "to": str(dst), "reason": ""}]}
        result = rz.apply(store, plan)
        assert result["moved"] == []
        assert result["failed"] == []
        assert len(result["noops"]) == 1
        assert src.exists() and dst.exists()         # 啥也不干
        assert store.get_entry(str(src)) is not None  # 源条目保留

    def test_meta_only_when_target_has_no_analysis(self, tmp_path):
        """内容不同且目标无元数据 → meta_only：元数据迁移、文件不动、
        目标指纹重算为目标实际值。"""
        root, src = self._mk(tmp_path, content="source-content")
        dst_dir = root / "目标"
        dst_dir.mkdir()
        dst = dst_dir / "a.txt"
        dst.write_text("different-content", encoding="utf-8")
        store = NaskbStore(LocalAdapter(str(root)))
        store.set_entry(str(src), FileEntry(original_path="a.txt",
                                            summary="源摘要", category="财务",
                                            tags=["发票"]))
        rz = Reorganizer(llm_client=None)
        plan = {"root": str(root),
                "moves": [{"from": str(src), "to": str(dst), "reason": ""}]}
        result = rz.apply(store, plan)
        assert result["moved"] == []
        assert len(result["meta_onlys"]) == 1
        assert src.exists() and dst.exists()         # 文件不动
        t = store.get_entry(str(dst))
        assert t is not None and t.category == "财务" and t.summary == "源摘要"
        _alg, h = store.compute_hash(str(dst))
        assert t.file_hash == h                      # 指纹为目标实际值

    def test_rename_when_target_has_analysis(self, tmp_path):
        """内容不同且目标已有元数据 → rename 后移动，目标不被覆盖。"""
        root, src = self._mk(tmp_path, content="source-content")
        dst_dir = root / "目标"
        dst_dir.mkdir()
        dst = dst_dir / "a.txt"
        dst.write_text("different-content", encoding="utf-8")
        store = NaskbStore(LocalAdapter(str(root)))
        store.set_entry(str(src), FileEntry(original_path="a.txt",
                                            summary="源", category="c"))
        store.set_entry(str(dst), FileEntry(original_path="a.txt",
                                            summary="目标已有", category="c"))
        rz = Reorganizer(llm_client=None)
        plan = {"root": str(root),
                "moves": [{"from": str(src), "to": str(dst), "reason": ""}]}
        result = rz.apply(store, plan)
        assert len(result["moved"]) == 1
        assert result["failed"] == []
        assert not src.exists()                      # 源已移动
        assert dst.exists()                          # 原目标未被覆盖
        renamed = dst_dir / "a (1).txt"
        assert renamed.exists()
        assert result["moved"][0][1].endswith("a (1).txt")

    def test_rename_increments_suffix(self, tmp_path):
        """rename 后缀递增：` (1)` 被占用时用 ` (2)`。"""
        root, src = self._mk(tmp_path, content="source-content")
        dst_dir = root / "目标"
        dst_dir.mkdir()
        dst = dst_dir / "a.txt"
        dst.write_text("different-1", encoding="utf-8")
        (dst_dir / "a (1).txt").write_text("different-2", encoding="utf-8")
        store = NaskbStore(LocalAdapter(str(root)))
        store.set_entry(str(src), FileEntry(original_path="a.txt",
                                            summary="源", category="c"))
        store.set_entry(str(dst), FileEntry(original_path="a.txt",
                                            summary="目标", category="c"))
        rz = Reorganizer(llm_client=None)
        plan = {"root": str(root),
                "moves": [{"from": str(src), "to": str(dst), "reason": ""}]}
        result = rz.apply(store, plan)
        assert len(result["moved"]) == 1
        assert (dst_dir / "a (2).txt").exists()

    def test_file_vs_dir_conflict(self, tmp_path):
        """文件移到已存在目录路径 → failed[conflict]，源不动。"""
        root, src = self._mk(tmp_path, content="x")
        dst_dir = root / "目标目录"
        dst_dir.mkdir()
        store = NaskbStore(LocalAdapter(str(root)))
        store.set_entry(str(src), FileEntry(original_path="a.txt",
                                            summary="s", category="c"))
        rz = Reorganizer(llm_client=None)
        plan = {"root": str(root),
                "moves": [{"from": str(src), "to": str(dst_dir), "reason": ""}]}
        result = rz.apply(store, plan)
        assert result["moved"] == []
        assert len(result["failed"]) == 1
        assert result["failed"][0]["reason"] == "conflict"
        assert src.exists()

    def test_dir_merge_three_tier(self, tmp_path):
        """目录合并：目标已有同名文件时逐文件三档判定。"""
        root = tmp_path / "t"
        src_dir = root / "源"
        dst_dir = root / "目标"
        src_dir.mkdir(parents=True)
        dst_dir.mkdir(parents=True)
        (src_dir / "same.txt").write_text("SAME", encoding="utf-8")
        (src_dir / "new.txt").write_text("新文件", encoding="utf-8")
        (dst_dir / "same.txt").write_text("SAME", encoding="utf-8")
        store = NaskbStore(LocalAdapter(str(root)))
        store.set_entry(str(src_dir / "same.txt"), FileEntry(
            original_path="same.txt", summary="s", category="c"))
        store.set_entry(str(src_dir / "new.txt"), FileEntry(
            original_path="new.txt", summary="n", category="c"))
        rz = Reorganizer(llm_client=None)
        plan = {"root": str(root),
                "moves": [{"from": str(src_dir), "to": str(dst_dir),
                           "reason": "合并"}]}
        result = rz.apply(store, plan)
        assert len(result["moved"]) == 1             # new.txt 移入
        assert len(result["noops"]) == 1             # same.txt 同内容不动
        assert (dst_dir / "new.txt").exists()
        assert (src_dir / "same.txt").exists()       # noop：源保留
        assert (dst_dir / "same.txt").exists()


class _StubConfig:
    """服务方法测试用最小 config 替身。"""

    def __init__(self, work_path):
        self.work_path = str(work_path)
        self.exclusions = {"folder": []}
        self.desc_repo_name = ".naskb"
        self.pg_enabled = False
        self.webdav_user = ""
        self.nas_list = []


class _FakeEmb:
    """向量索引测试用伪嵌入（与 test_vector_index 同款）。"""

    def encode(self, texts):
        import numpy as np
        v = np.ones((len(texts), 4))
        return v / np.linalg.norm(v, axis=1, keepdims=True)

    def encode_one(self, text):
        import numpy as np
        v = np.ones(4)
        return v / np.linalg.norm(v)

    def close(self):
        pass


class TestApplyWithHousekeeping:
    """P1-2 服务方法：互斥锁 + 级联 + 整理后同步。"""

    def _mk(self, tmp_path):
        root = tmp_path / "t"
        root.mkdir(parents=True)
        f = root / "a.txt"
        f.write_text("A", encoding="utf-8")
        store = NaskbStore(LocalAdapter(str(root)))
        store.set_entry(str(f), FileEntry(original_path="a.txt",
                                          summary="s", category="c"))
        return root, f, store

    def test_moves_and_sync_skipped(self, tmp_path):
        """基本执行：移动成功，sync 标记 skipped（无索引/无 PG）。"""
        root, f, store = self._mk(tmp_path)
        cfg = _StubConfig(tmp_path / "work")
        rz = Reorganizer(llm_client=None)
        plan = {"root": str(root),
                "moves": [{"from": str(f), "to": str(root / "子" / "a.txt"),
                           "reason": ""}]}
        result = rz.apply_with_housekeeping(store, plan, None, config=cfg)
        assert len(result["moved"]) == 1
        assert result["sync"]["vector_index"] == "skipped（无本地向量索引）"
        assert result["sync"]["pg"] == "skipped"
        # 锁已释放（无残留 .lock）
        plans = os.path.join(str(tmp_path / "work"), "plans")
        assert os.path.isdir(plans)
        assert not [n for n in os.listdir(plans) if n.endswith(".lock")]

    def test_lock_blocks_concurrent_apply(self, tmp_path):
        """root 已被锁定 → 拒绝执行；释放后可正常执行。"""
        from naskb.common.plan_store import RootLock
        root, f, store = self._mk(tmp_path)
        cfg = _StubConfig(tmp_path / "work")
        rz = Reorganizer(llm_client=None)
        plan = {"root": str(root),
                "moves": [{"from": str(f), "to": str(root / "子" / "a.txt"),
                           "reason": ""}]}
        lock = RootLock(str(tmp_path / "work"), str(root))
        assert lock.acquire()
        try:
            with pytest.raises(RuntimeError):
                rz.apply_with_housekeeping(store, plan, None, config=cfg)
        finally:
            lock.release()
        # 锁释放后成功执行，文件确实移动
        result = rz.apply_with_housekeeping(store, plan, None, config=cfg)
        assert len(result["moved"]) == 1
        assert (root / "子" / "a.txt").exists()

    def test_remaps_vector_index_after_move(self, tmp_path):
        """整理后本地向量索引 remap：paths 更新、无需重嵌入（P1-3 联动）。"""
        from naskb.common.retrieval import Doc
        from naskb.common.vector_index import VectorIndex
        root, f, store = self._mk(tmp_path)
        work = tmp_path / "work"
        idx = VectorIndex(_FakeEmb(), str(work))
        idx.build([Doc(path=str(f), kind="file", text="s",
                       summary="s", category="c")])
        cfg = _StubConfig(work)
        rz = Reorganizer(llm_client=None)
        plan = {"root": str(root),
                "moves": [{"from": str(f), "to": str(root / "子" / "a.txt"),
                           "reason": ""}]}
        result = rz.apply_with_housekeeping(store, plan, None, config=cfg,
                                            sync=True)
        assert len(result["moved"]) == 1
        assert result["sync"]["vector_index"].startswith("ok")
        # 索引路径已更新为新位置
        idx2 = VectorIndex(None, str(work))
        assert idx2.load()
        assert str(root / "子" / "a.txt") in idx2.paths()
        assert str(f) not in idx2.paths()
