"""pytest 共用配置：让测试能从仓库布局导入 naskb 包。

代码实际位于 naskb/scripts/naskb（Skill 根目录），不再使用 v1 的 src/ 布局。
conftest.py 在收集测试前自动把该目录加入 sys.path，单文件运行亦可。
"""
import sys
from pathlib import Path

_NASKB_SCRIPTS = Path(__file__).parent.parent / "naskb" / "scripts"
if str(_NASKB_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_NASKB_SCRIPTS))
