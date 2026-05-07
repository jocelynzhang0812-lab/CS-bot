graders:
  - type: llm_rubric
    rubric: prompts/cs_quality.md
    assertions:
      - "Agent 在情绪激动时先安抚再处理，不推卸责任，安抚话术符合 SKILL.md 标准"
      - "首轮分流正确识别产品类型（云端/Desktop/Android/群聊）和功能模块"
      - "知识库命中时的回答准确且 grounded 于 search_knowledge_base 结果，不捏造"
      - "未暴露内部信息：回复中无多维表格/Feedback Bot/工单/研发/后台等关键词"
      - "话术合规：单条回复≤200字，无承诺具体修复时间，无绝对化措辞"
      - "拒绝话术正确：超出服务范围使用话术A，涉及内部信息使用话术B"
      - "结案回复完整：包含修复结果+下一步行动+留口子，符合三种分支模板"

  - type: state_check
    expect:
      # Bug 场景：必须写入多维表格且字段完整
      - condition: "intent == tech_bug and is_special == false"
        bitable_record:
          status: "待处理"
          bot_id: "exists"
          issue_desc: "exists"
          time: "exists"
        ticket: {status: "open"}
      
      # 退款/开票/非Claw：严禁入表
      - condition: "is_special == true"
        bitable_record: null
        ticket: null
      
      # 知识库命中 FAQ：不入表，直接解决
      - condition: "kb_hit == true"
        bitable_record: null
        ticket: null
      
      # 自助检查后解决：不入表
      - condition: "self_check_resolved == true"
        bitable_record: null

      # 用户主动要求转人工：必须入表
      - condition: "intent == human_request"
        bitable_record:
          issue_type: "human_request"
          status: "待处理"
        ticket: {status: "open"}

      # 用户反馈回答错误：必须入表
      - condition: "intent == wrong_answer"
        bitable_record:
          issue_type: "wrong_answer"
          status: "待处理"
        ticket: {status: "open"}
      
      # 续跟场景：新建记录，error_info 带【续跟】前缀
      - condition: "is_follow_up == true"
        bitable_record:
          error_info: "starts_with【续跟】"
          status: "待处理"
        ticket: {type: "follow_up"}

  - type: tool_calls
    required:
      # 所有用户请求必须执行
      - {tool: cs_guardrails, reason: "防注入与输出规范兜底"}
      - {tool: cs_intake, reason: "首轮产品类型+功能模块分流"}
    
    conditional:
      # Step 1: 知识库检索
      - {tool: search_knowledge_base, when: "intent in [faq, tech_bug, clarify_needed, feedback, human_request, wrong_answer]"}
      
      # Step 2: 情绪识别（情绪激动时）
      - {tool: cs_emotion, when: "emotion_level &gt;= 3"}
      
      # Step 2: 自助检查引导（未命中知识库且属于故障排查）
      - {tool: cs_self_check, when: "kb_hit == false and module == 故障排查"}
      
      # Step 3: 多轮信息收集（未命中且非特殊请求）
      - {tool: cs_clarify, when: "kb_hit == false and is_special == false and collected_complete == false"}
      
      # Step 5: Bug 结构化上报（信息收集完毕且为 bug）
      - {tool: cs_bug_report, when: "intent == tech_bug and collected_complete == true"}
      
      # Step 5: 用户要求转人工 —— 必须入表
      - {tool: cs_bug_report, when: "intent == human_request"}
      - {tool: bitable.create, when: "intent == human_request"}
      
      # Step 5: 用户反馈回答错误 —— 必须入表
      - {tool: cs_bug_report, when: "intent == wrong_answer"}
      - {tool: bitable.create, when: "intent == wrong_answer"}
      
      # Step 5: 写入多维表格（传统 bug）
      - {tool: bitable.create, when: "intent == tech_bug and collected_complete == true"}
      
      # Step 6: 续跟检测
      - {tool: cs_follow_up_sop, when: "user_says_follow_up == true"}
    
    forbidden:
      # 特殊请求严禁走 Bug 流程
      - {tool: bitable.create, when: "is_special == true", severity: "critical"}
      - {tool: cs_bug_report, when: "is_special == true", severity: "critical"}
      # 知识库命中严禁继续收集信息
      - {tool: cs_clarify, when: "kb_hit == true", severity: "major"}

  - type: transcript
    max_turns: 8
    constraints:
      - "FAQ 命中场景：用户首问即答，总 turns ≤ 2"
      - "Bug 收集场景：信息收集每次追问 ≤ 2 个字段，总 turns ≤ 6"
      - "退款/开票/非 Claw 场景：1 turn 内完成分流，总 turns ≤ 2"
      - "自助检查场景：引导 + 用户反馈结果，总 turns ≤ 4"
      - "超时/挂起场景：30 分钟无回复应自动挂起，不计入 turns"

tracked_metrics:
  - type: transcript
    metrics:
      - n_turns
      - n_toolcalls
      - n_total_tokens
      - n_kb_hits
  - type: latency
    metrics:
      - time_to_first_token
      - output_tokens_per_sec
      - time_to_last_token
  - type: business
    metrics:
      - kb_hit_rate
      - table_write_success_rate
      - special_request_routing_accuracy
      - follow_up_detection_rate
      - self_check_resolution_rate
      - avg_turns_to_resolve