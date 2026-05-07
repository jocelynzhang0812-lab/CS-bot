#!/usr/bin/env python3
"""将 帮助中心/ 的 Markdown 文件清洗后迁移到知识库目录"""
import os
import re
import shutil
from pathlib import Path

# 源目录与目标目录
SRC_DIR = Path("帮助中心")
DST_DATA_DIR = Path("csbot/knowledge/data/help_center")
DST_KB_DIR = Path("知识库0501/help_center")

# 确保目标目录存在
DST_DATA_DIR.mkdir(parents=True, exist_ok=True)
DST_KB_DIR.mkdir(parents=True, exist_ok=True)


def clean_md(text: str) -> str:
    """清洗帮助中心 Markdown：去掉 frontmatter、SeoMeta、Frames、Callout 标记等"""
    # 1. 去掉 YAML frontmatter（必须在最开头）
    text = re.sub(r'^---\s*\n.*?\n---\s*\n', '', text, flags=re.DOTALL)

    # 2. 去掉 SeoMeta JSX 组件（自闭合 <SeoMeta ... />）
    text = re.sub(r'<SeoMeta\b[\s\S]*?/>\s*\n?', '', text, flags=re.DOTALL)

    # 3. 去掉 Frames 图片块
    text = re.sub(r'//Frames\s*\n.*?\n//', '', text, flags=re.DOTALL)

    # 4. 去掉 Chat 引用块（形如 //\n💬 用户：...\nChat ...\n//）
    text = re.sub(r'//\s*\n💬\s*\*\*用户\*\*：.*?\nChat\s+[\w-]+\s*\n//', '', text, flags=re.DOTALL)
    # 更宽松的匹配
    text = re.sub(r'//\s*\n💬.*?\n//', '', text, flags=re.DOTALL)

    # 5. 去掉 CodePreview 标记（保留代码内容，只去掉标记）
    text = re.sub(r'CodePreview\s*$', '', text, flags=re.MULTILINE)

    # 6. 去掉 ColumnsContent 标记
    text = re.sub(r'ColumnsContent\s*\n', '\n', text)

    # 7. 去掉 ComparisonBlock 标记
    text = re.sub(r'ComparisonBlock\s*\n', '\n', text)

    # 8. 清理 //Callout ... // 块
    # 先匹配完整块：//Callout 类型\n内容\n//
    def replace_callout(m):
        ctype = m.group(1)
        content = m.group(2).strip()
        return f"> **{ctype}**: {content}\n"
    text = re.sub(r'//Callout\s+(\w+)\s*\n(.*?)\n//', replace_callout, text, flags=re.DOTALL)
    # 再处理残留的 //Callout 标记行
    text = re.sub(r'^//Callout\s+\w+\s*$', '', text, flags=re.MULTILINE)
    text = re.sub(r'^//Callout\s*$', '', text, flags=re.MULTILINE)

    # 9. 清理 // ... // 包裹块（如 Callout、Frames 残留等）
    lines = []
    skip_until_close = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped == '//':
            skip_until_close = not skip_until_close
            continue
        if skip_until_close:
            continue
        lines.append(line)
    text = '\n'.join(lines)

    # 10. 去掉空的图片引用 ![image](...) 和 ![...](...)
    text = re.sub(r'!\[image\]\([^)]+\)\s*\n?', '', text)
    text = re.sub(r'!\[.*?\]\([^)]+\)\s*\n?', '', text)

    # 11. 连续空行压缩
    text = re.sub(r'\n{3,}', '\n\n', text)

    return text.strip()


def merge_category(src_subdir: Path, dst_name: str) -> str:
    """将一个子目录下的所有 .md 合并为一个文件"""
    md_files = sorted(src_subdir.glob("*.md"))
    if not md_files:
        return ""

    parts = [f"# {dst_name}\n"]
    for f in md_files:
        raw = f.read_text(encoding="utf-8")
        cleaned = clean_md(raw)
        if cleaned:
            parts.append(f"\n---\n\n{cleaned}\n")

    return '\n'.join(parts)


def main():
    # 定义合并规则：(源子目录, 输出文件名, 标题)
    categories = [
        ("kimi-api", "kimi-api.md", "Kimi API 帮助文档"),
        ("kimi-code", "kimi-code.md", "Kimi Code 帮助文档"),
        ("membership", "membership-help.md", "会员订阅帮助文档"),
        ("new-user-guide", "new-user-guide.md", "新用户指南"),
        ("others", "others-help.md", "其他常见问题"),
        ("websites", "websites-help.md", "Kimi Websites 帮助文档"),
        ("docs-and-sheets", "docs-and-sheets-help.md", "Kimi Docs & Sheets 帮助文档"),
    ]

    for subdir, fname, title in categories:
        src_path = SRC_DIR / subdir
        if not src_path.exists():
            print(f"⚠️ 跳过不存在目录: {src_path}")
            continue

        content = merge_category(src_path, title)
        if not content.strip():
            print(f"⚠️ 空内容，跳过: {subdir}")
            continue

        # 写入两个目标目录
        for dst_dir in (DST_DATA_DIR, DST_KB_DIR):
            out_path = dst_dir / fname
            out_path.write_text(content, encoding="utf-8")

        print(f"✅ {subdir} -> {fname} ({len(content)} 字符)")

    print("\n🎉 帮助中心内容迁移完成！")


if __name__ == "__main__":
    main()
