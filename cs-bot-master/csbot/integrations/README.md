# integrations/README.md

### 1. 多维表格通信
- 与 Feedback Bot 的所有通信通过共享多维表格完成
- 字段定义、读写职责、写入模板详见 references/airtable-schema.md
- 写入/轮询/结案/超时提醒等表格操作
- 不在用户群暴露表格 URL、工单编号、研发进度等

---
建议在 integrations/feishu_table.py、feedback_bot.py 等文件实现上述逻辑。
