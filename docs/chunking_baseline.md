# Chunk 切割基线记录

## 现有切割方式（重构前）

现有 `KnowledgeLoader` 按文档标题层级切割：
- `load_error_code_table`：按 Markdown 表格行切割（每行一个 doc）
- `load_troubleshoot`：按 `##` / `###` 二级标题切割
- `load_policy`：按 `##` / `###` 二级标题切割
- `load_config_guide`：按 `##` / `###` 二级标题切割
- `load_sop`：按 `##` / `###` 二级标题切割
- `load_product_guide`：按 `##` / `###` 二级标题切割
- `load_help_center`：按 `##` / `###` 二级标题切割

**问题**：
- 标题切割粒度不均：有的标题下只有 50 字，有的超过 1000 字
- 没有 overlap，上下文断裂
- 表格行切割太细，丢失上下文
- 长段落未做二次拆分

## 新切割参数（重构后）

使用 `SemanticChunker`：
```python
chunk_size=512
chunk_overlap=64
separators=["\n\n", "\n", "。", "！", "？", " "]
```

**优势**：
- 固定长度，向量嵌入更稳定
- 语义边界优先（段落 → 句子 → 空格）
- 64 字 overlap 保持上下文连贯
- 过长块自动二次拆分

## 对比验证方法

```bash
python scripts/diagnose_retrieval.py > docs/retrieval_before.txt
# 切换为新 chunker 后重跑
python scripts/diagnose_retrieval.py > docs/retrieval_after.txt
diff docs/retrieval_before.txt docs/retrieval_after.txt
```
