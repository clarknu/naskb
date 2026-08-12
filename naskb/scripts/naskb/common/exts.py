"""文件类型判定与忽略规则（v2 统一入口）。

集中管理：支持类型白名单、被忽略文件的名称推断映射、系统垃圾文件黑名单。
batch.py（批量分析）/ cli.py（单文件命令）/ desc_store.py（scan 报告）共用，
避免各文件自维护一份集合导致不一致。

被忽略文件语义（用户拍板）：
- 单个文件被忽略 → 不去分析内容，仅按文件名/扩展名记录可能的内容意义
- 整个目录被忽略 → 目录级元数据（folder.json），用目录名+内部文件名推断用途
- 隐藏目录（.git 等）与系统垃圾文件（Thumbs.db 等）→ 完全跳过，不记录
"""
from __future__ import annotations

import mimetypes
from pathlib import Path

# ═══════════════════════════════════════════════════════════════════
# 支持分析的类型白名单（进入完整分析：文档/图片/音频/视频）
# ═══════════════════════════════════════════════════════════════════

DOC_EXTS = {".txt", ".md", ".pdf", ".docx", ".xlsx", ".pptx", ".doc", ".xls",
            ".km", ".mmap", ".csv", ".json", ".rtf"}
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".tif",
              ".tiff", ".heic", ".avif"}
AUDIO_EXTS = {".mp3", ".wav", ".m4a", ".flac", ".aac", ".ogg", ".wma",
              ".amr", ".opus"}
VIDEO_EXTS = {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".ts",
              ".m4v", ".webm", ".mpg", ".mpeg", ".rmvb", ".3gp"}
SUPPORTED_EXTS = DOC_EXTS | IMAGE_EXTS | AUDIO_EXTS | VIDEO_EXTS

# ═══════════════════════════════════════════════════════════════════
# 被忽略文件：扩展名 → 可能的内容意义（仅按名称记录，不分析内容）
# ═══════════════════════════════════════════════════════════════════

IGNORED_EXT_MEANING = {
    # 代码 / 脚本
    ".py": "Python 源代码", ".pyw": "Python 脚本", ".pyc": "Python 字节码缓存",
    ".js": "JavaScript 脚本", ".mjs": "JavaScript 模块", ".cjs": "JavaScript 脚本",
    ".ts": "TypeScript 源代码", ".jsx": "React JSX 源码", ".tsx": "React TSX 源码",
    ".java": "Java 源代码", ".class": "Java 字节码", ".jar": "Java 程序包",
    ".c": "C 源代码", ".h": "C 头文件", ".cpp": "C++ 源代码", ".hpp": "C++ 头文件",
    ".cs": "C# 源代码", ".go": "Go 源代码", ".rs": "Rust 源代码",
    ".sh": "Shell 脚本", ".bash": "Bash 脚本", ".bat": "Windows 批处理脚本",
    ".cmd": "Windows 命令脚本", ".ps1": "PowerShell 脚本",
    ".vue": "Vue 组件源码", ".php": "PHP 源代码", ".rb": "Ruby 源代码",
    ".swift": "Swift 源代码", ".kt": "Kotlin 源代码", ".lua": "Lua 脚本",
    ".pl": "Perl 脚本", ".r": "R 脚本", ".m": "MATLAB/Objective-C 源码",
    ".sql": "SQL 脚本", ".ipynb": "Jupyter 笔记本",
    ".csproj": ".NET 工程文件", ".sln": "Visual Studio 解决方案",
    ".vcxproj": "Visual C++ 工程文件", ".xcodeproj": "Xcode 工程目录",
    ".iml": "IntelliJ 模块文件", ".gradle": "Gradle 构建脚本",
    ".groovy": "Groovy 脚本", ".dart": "Dart 源代码", ".scala": "Scala 源代码",
    ".hs": "Haskell 源代码", ".ex": "Elixir 源代码", ".erl": "Erlang 源代码",
    ".clj": "Clojure 源代码", ".asm": "汇编源码", ".s": "汇编源码",
    ".f": "Fortran 源代码", ".vb": "Visual Basic 源代码",
    # 配置 / 数据
    ".yaml": "YAML 配置文件", ".yml": "YAML 配置文件", ".xml": "XML 文件",
    ".toml": "TOML 配置文件", ".ini": "配置文件", ".cfg": "配置文件",
    ".conf": "配置文件", ".properties": "Java 属性配置",
    ".db": "数据库文件", ".sqlite": "SQLite 数据库", ".sqlite3": "SQLite 数据库",
    ".dbf": "dBase 数据库文件", ".geojson": "GeoJSON 地理数据",
    ".lock": "依赖锁文件", ".map": "sourcemap 映射文件",
    ".tsbuildinfo": "TypeScript 构建缓存", ".pdb": "程序调试符号文件",
    # 网页
    ".html": "网页文件", ".htm": "网页文件", ".css": "CSS 样式表",
    ".scss": "SCSS 样式源码", ".less": "LESS 样式源码", ".sass": "Sass 样式源码",
    # 程序 / 安装包 / 系统
    ".exe": "Windows 可执行程序", ".dll": "Windows 动态链接库",
    ".msi": "Windows 安装包", ".iso": "光盘镜像文件",
    ".apk": "Android 安装包", ".ipa": "iOS 应用包", ".dmg": "macOS 磁盘镜像",
    ".pkg": "安装包文件", ".deb": "Debian 软件包", ".rpm": "RPM 软件包",
    ".so": "Linux 共享库", ".dylib": "macOS 动态库", ".a": "静态库文件",
    ".o": "编译目标文件", ".obj": "编译目标文件", ".wasm": "WebAssembly 模块",
    ".whl": "Python wheel 安装包", ".egg": "Python egg 包",
    ".sys": "系统驱动文件", ".drv": "驱动程序文件",
    ".nupkg": "NuGet 软件包", ".gem": "Ruby 软件包", ".crate": "Rust 软件包",
    # 压缩 / 归档
    ".zip": "ZIP 压缩包", ".rar": "RAR 压缩包", ".7z": "7-Zip 压缩包",
    ".tar": "tar 打包文件", ".gz": "gzip 压缩文件", ".bz2": "bzip2 压缩文件",
    ".xz": "xz 压缩文件", ".zst": "zstd 压缩文件",
    # 设计 / 媒体工程文件
    ".psd": "Photoshop 源文件", ".ai": "Adobe Illustrator 文件",
    ".svg": "SVG 矢量图", ".eps": "EPS 矢量图", ".fig": "Figma 设计文件",
    ".sketch": "Sketch 设计文件", ".xmind": "XMind 思维导图",
    ".mm": "FreeMind 思维导图", ".ppt": "老版 PowerPoint 演示文稿",
    ".wps": "WPS 文字文档", ".et": "WPS 表格文档",
    # 邮件 / 办公
    ".msg": "Outlook 邮件文件", ".eml": "邮件文件",
    ".odt": "OpenDocument 文档", ".ods": "OpenDocument 表格",
    ".odp": "OpenDocument 演示",
    # 字体 / 杂项
    ".ttf": "字体文件", ".otf": "字体文件", ".woff": "Web 字体", ".woff2": "Web 字体",
    ".tmp": "临时文件", ".bak": "备份文件", ".old": "旧版本文件",
    ".patch": "补丁文件", ".diff": "差异补丁文件", ".po": "翻译文件",
    ".mo": "编译后的翻译文件", ".swf": "Flash 动画", ".fla": "Flash 源文件",
    ".part": "未完成下载的临时文件", ".crdownload": "浏览器未完成下载文件",
    ".lnk": "快捷方式文件", ".url": "网址快捷方式", ".torrent": "BT 种子文件",
}

# ═══════════════════════════════════════════════════════════════════
# 被忽略文件：无扩展名/点开头的知名文件名 → 可能意义（按文件名小写匹配）
# ═══════════════════════════════════════════════════════════════════

FILE_NAME_MEANING = {
    "dockerfile": "Docker 容器构建文件",
    "makefile": "Make 构建脚本",
    "cmakelists.txt": "CMake 构建配置",
    "license": "许可证文本",
    "copying": "许可证文本",
    "readme": "说明文档",
    "changelog": "变更日志",
    "go.mod": "Go 模块定义",
    "go.sum": "Go 依赖校验文件",
    "gemfile": "Ruby 依赖清单",
    "gemfile.lock": "Ruby 依赖锁文件",
    "vagrantfile": "Vagrant 虚拟机配置",
    "procfile": "进程声明文件",
    "cargo.lock": "Rust 依赖锁文件",
    "yarn.lock": "yarn 依赖锁文件",
    "pnpm-lock.yaml": "pnpm 依赖锁文件",
    "poetry.lock": "Poetry 依赖锁文件",
    "composer.lock": "Composer 依赖锁文件",
    "pipfile": "Python 依赖声明（Pipenv）",
    "pipfile.lock": "Python 依赖锁文件（Pipenv）",
    ".env": "环境变量配置文件",
    ".gitignore": "Git 忽略规则文件",
    ".gitattributes": "Git 属性文件",
    ".gitmodules": "Git 子模块定义",
    ".dockerignore": "Docker 构建忽略规则",
    ".editorconfig": "编辑器风格配置",
    ".prettierrc": "Prettier 格式化配置",
    ".babelrc": "Babel 转译配置",
    ".npmrc": "npm 配置",
    ".eslintrc": "ESLint 配置",
    ".flake8": "flake8 配置",
    ".pylintrc": "pylint 配置",
    ".htaccess": "Apache 服务器配置",
    ".vimrc": "Vim 配置",
    ".bashrc": "Bash 配置",
    ".zshrc": "zsh 配置",
    ".gitconfig": "Git 全局配置",
    "terraform.lock.hcl": "Terraform 依赖锁文件",
}

# ═══════════════════════════════════════════════════════════════════
# 系统垃圾文件：完全跳过（不记录、不统计）
# ═══════════════════════════════════════════════════════════════════
# Thumbs.db 等是系统自动生成的缓存文件，记录无意义。
SYSTEM_FILES = {
    "thumbs.db", ".ds_store", "desktop.ini", ".localized", ".directory",
    "ehthumbs.db", ".thumbnails", ".fseventsd", ".spotlight-v100",
}


def is_supported(ext: str) -> bool:
    """扩展名（小写）是否进入完整分析。"""
    return ext in SUPPORTED_EXTS


def is_system_file(name: str) -> bool:
    """系统垃圾文件（大小写不敏感）。"""
    return name.lower() in SYSTEM_FILES


def is_word_lock(name: str) -> bool:
    """Word/Office 打开文档时的临时锁文件（~$xxx.docx）。"""
    return name.startswith("~$")


def meaning_of(name: str) -> str:
    """按文件名/扩展名推断被忽略文件可能的内容意义。

    优先扩展名映射，其次知名文件名（小写匹配），最后兜底。
    """
    ext = Path(name).suffix.lower()
    if ext in IGNORED_EXT_MEANING:
        return IGNORED_EXT_MEANING[ext]
    m = FILE_NAME_MEANING.get(name.lower())
    if m:
        return m
    if ext:
        return f"{ext} 类型文件"
    return "无扩展名文件"


def guess_mime(name: str) -> str:
    """按文件名猜 MIME（忽略文件不做内容分析，仅记录类型）。"""
    return mimetypes.guess_type(name)[0] or "application/octet-stream"
