#!/usr/bin/env python3
"""
Kimi Claw 产品功能分类器
帮助 Agent 根据用户问题识别所属产品类型和功能模块

支持四种产品类型：
- cloud: 云端部署 Kimi Claw
- desktop: Kimi Claw Desktop（桌面端）
- android: Kimi Claw Android（移动端）
- group_chat: Claw 群聊产品
"""

import re
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from enum import Enum


class ProductType(Enum):
    """产品类型枚举"""
    CLOUD = "cloud"
    DESKTOP = "desktop"
    ANDROID = "android"
    GROUP_CHAT = "group_chat"
    UNKNOWN = "unknown"


class FunctionModule(Enum):
    """功能模块枚举"""
    # 通用模块
    BASIC = "basic"              # 基础认知
    INSTALL = "install"          # 下载安装
    CONFIG = "config"            # 配置设置
    CHANNEL = "channel"          # 聊天渠道
    UPGRADE = "upgrade"          # 升级版本
    DEBUG = "debug"              # 故障排查
    MEMORY = "memory"            # 记忆上下文
    FILE = "file"                # 文件收发
    COMMAND = "command"          # 命令终端
    RATE_LIMIT = "rate_limit"    # 额度限制
    FEISHU = "feishu"            # 飞书专用
    FEEDBACK = "feedback"        # 反馈交流

    # Android 特有
    AUTOMATION = "automation"    # 自动化操控
    DASHBOARD = "dashboard"      # Dashboard
    BACKUP = "backup"            # 备份恢复
    SECURITY = "security"        # 安全限制
    PERMISSION = "permission"    # 权限管理

    # 群聊特有
    GROUP_CREATE = "group_create"    # 创建管理
    GROUP_RULE = "group_rule"        # 群规设置
    THREAD = "thread"                # Thread话题
    ROLE = "role"                    # 角色协作
    WORKSPACE = "workspace"          # 工作空间


@dataclass
class ClassificationResult:
    """分类结果"""
    product_type: ProductType
    function_module: FunctionModule
    confidence: float
    matched_keywords: List[str]
    suggestion_qa: Optional[str] = None


class ClawClassifier:
    """Kimi Claw 产品功能分类器"""

    def __init__(self):
        # 产品类型关键词映射
        self.product_keywords = {
            ProductType.CLOUD: [
                "云端", "云实例", "远程服务器", "网页创建", "一键部署",
                "web ssh", "ssh", "终端", "命令行", "gateway", "网关",
                "修复配置", "恢复初始设置", "bot id", "云主机",
                "allegretto", "会员到期", "7天保留", "删除bot"
            ],
            ProductType.DESKTOP: [
                "桌面端", "桌面客户端", "我的电脑", "mac", "windows",
                ".kimi_openclaw", "本地电脑", "pc端", "电脑端",
                "finder", "访达", "隐藏文件夹", "command+shift",
                "重启桌面", "桌面版", "desktop"
            ],
            ProductType.ANDROID: [
                "安卓", "android", "手机", "移动端", "app", "闲置手机",
                "dashboard", "自动化", "操控手机", "打开app", "点击",
                "滑动", "截图", "无障碍服务", "自启动", "后台运行",
                "电池优化", "权限授予", "存储空间", "5gb",
                "skillhub", "备份恢复", "版本升级", "扫码下载",
                "应用商店", "微信claw", "飞书扫码", "淘宝", "美团",
                "高德地图", "小红书", "抖音", "银行", "支付", "证券",
                "受限应用", "金融app", "安全须知", "插电", "wifi"
            ],
            ProductType.GROUP_CHAT: [
                "群聊", "群组", "group", "conductor", "指挥",
                "thread", "话题", "群规", "group goal", "群目标",
                "角色扮演", "多agent", "多claw", "协作", "worker",
                "邀请链接", "群主", "围观", "发言权", "bot拉入",
                "群成员", "群管理", "工作空间", "产物", "@机器人",
                "项目经理", "角色碰撞", "专业分工", "跨设备互动"
            ]
        }

        # 功能模块关键词映射
        self.module_keywords = {
            # 通用模块
            FunctionModule.BASIC: [
                "是什么", "介绍", "基础", "认知", "区别", "对比",
                "什么是", "怎么用", "如何使用"
            ],
            FunctionModule.INSTALL: [
                "下载", "安装", "创建", "部署", "初始化", "首次",
                "step", "步骤", "流程", "配置完成"
            ],
            FunctionModule.CONFIG: [
                "配置", "设置", "修改", "调整", "参数", "config",
                "yaml", "人设", "昵称", "身份", "角色"
            ],
            FunctionModule.CHANNEL: [
                "渠道", "微信", "飞书", "企业微信", "微博", "钉钉",
                "聊天频道", "接入", "绑定", "扫码", "机器人",
                "群聊策略", "dmPolicy", "groupPolicy", "配对"
            ],
            FunctionModule.UPGRADE: [
                "升级", "更新", "版本", "手动升级", "openclaw版本",
                "插件版本", "兼容", "适配", "推送", "回退"
            ],
            FunctionModule.DEBUG: [
                "故障", "排查", "修复", "错误", "报错", "失败",
                "断开", "连不上", "卡住", "慢", "无响应",
                "重启", "gateway", "网关", "日志", "诊断",
                "doctor", "fix", "timeout", "expired"
            ],
            FunctionModule.MEMORY: [
                "记忆", "失忆", "上下文", "session", "历史",
                "记住", "memory", "凌晨4点", "重置", "丢失",
                "续费", "保留", "备份记忆", "导出记忆"
            ],
            FunctionModule.FILE: [
                "文件", "下载", "上传", "收发", "产物", "工作空间",
                "workspace", "图片", "文档", "100mb", "压缩"
            ],
            FunctionModule.COMMAND: [
                "命令", "指令", "/", "斜杠", "help", "status",
                "new", "reset", "skills", "cron", "config",
                "terminal", "终端", "ssh", "shell", "bash"
            ],
            FunctionModule.RATE_LIMIT: [
                "额度", "限制", "rate limit", "token", "超限",
                "并发", "rpm", "tpm", "tpd", "tier", "充值",
                "余额", "quota", "exhausted", "繁忙"
            ],
            FunctionModule.FEISHU: [
                "飞书", "feishu", "lark", "bot id", "app id",
                "app secret", "扫码", "授权", "auth", "配对",
                "approve", "群聊策略", "doctor", "fix"
            ],
            FunctionModule.FEEDBACK: [
                "反馈", "交流群", "客服", "帮助", "支持",
                "问题", "bug", "建议", "联系", "技术人员"
            ],

            # Android 特有
            FunctionModule.AUTOMATION: [
                "自动化", "操控", "模拟点击", "滑动", "输入",
                "打开app", "淘宝", "美团", "高德", "地图",
                "小红书", "抖音", "购物", "导航", "出行",
                "远程操控", "手机操作", "app控制"
            ],
            FunctionModule.DASHBOARD: [
                "dashboard", "主界面", "网关状态", "运行时长",
                "实时日志", "搜索日志", "筛选", "自动追底",
                "刷新", "渠道管理", "设置页面"
            ],
            FunctionModule.BACKUP: [
                "备份", "恢复", "导出", "导入", "迁移",
                "更换手机", "重装", "卸载", "配置文件",
                "自动备份", "手动备份", "备份列表"
            ],
            FunctionModule.SECURITY: [
                "安全", "隐私", "敏感", "隔离", "金融",
                "银行", "支付", "证券", "保险", "受限",
                "禁止访问", "风险", "资金", "保护"
            ],
            FunctionModule.PERMISSION: [
                "权限", "授权", "通知", "存储", "后台",
                "自启动", "电池优化", "耗电管理", "无障碍",
                "忽略电池优化", "完全允许后台", "锁屏"
            ],

            # 群聊特有
            FunctionModule.GROUP_CREATE: [
                "创建群聊", "发起群聊", "群名称", "群目标",
                "group goal", "邀请", "加入", "移除", "群主",
                "群成员", "发言权", "可见范围", "围观"
            ],
            FunctionModule.GROUP_RULE: [
                "群规", "规则", "行为准则", "语言风格", "输出格式",
                "工作约束", "角色分工", "模板", "统一"
            ],
            FunctionModule.THREAD: [
                "thread", "话题", "子任务", "拆分", "分配",
                "进度", "独立上下文", "不污染", "跟进"
            ],
            FunctionModule.ROLE: [
                "角色", "扮演", "conductor", "指挥", "worker",
                "协作", "分工", "碰撞", "多agent", "多claw",
                "苏格拉底", "尼采", "立场", "分析角度"
            ],
            FunctionModule.WORKSPACE: [
                "工作空间", "产物", "文件", "预览", "下载",
                "结果", "交付", "bot产物", "所有文件"
            ]
        }

        # QA 建议映射（用于快速定位答案）
        self.qa_suggestions = {
            (ProductType.CLOUD, FunctionModule.DEBUG): "参考云端部署故障排查 Q11-Q20",
            (ProductType.CLOUD, FunctionModule.CHANNEL): "参考平台接入 Q14-Q16",
            (ProductType.CLOUD, FunctionModule.MEMORY): "参考记忆与续费 Q24",
            (ProductType.DESKTOP, FunctionModule.INSTALL): "参考创建与删除 Q26-Q29",
            (ProductType.DESKTOP, FunctionModule.DEBUG): "参考重启方式 Q30",
            (ProductType.ANDROID, FunctionModule.INSTALL): "参考下载安装 Q4-Q9",
            (ProductType.ANDROID, FunctionModule.DASHBOARD): "参考Dashboard Q10-Q15",
            (ProductType.ANDROID, FunctionModule.AUTOMATION): "参考自动化 Q24-Q25",
            (ProductType.ANDROID, FunctionModule.SECURITY): "参考安全限制 Q26-Q27",
            (ProductType.GROUP_CHAT, FunctionModule.GROUP_CREATE): "参考创建管理 Q4-Q6",
            (ProductType.GROUP_CHAT, FunctionModule.ROLE): "参考角色协作 Q1-Q2, Q17",
            (ProductType.GROUP_CHAT, FunctionModule.THREAD): "参考Thread机制 Q10",
        }

    def _calculate_match_score(self, text: str, keywords: List[str]) -> Tuple[float, List[str]]:
        """计算文本与关键词的匹配分数"""
        text_lower = text.lower()
        matched = []
        score = 0

        for keyword in keywords:
            keyword_lower = keyword.lower()
            if keyword_lower in text_lower:
                matched.append(keyword)
                # 完整词匹配权重更高
                if re.search(r'\b' + re.escape(keyword_lower) + r'\b', text_lower):
                    score += 2
                else:
                    score += 1

        # 归一化分数
        max_score = len(keywords) * 2
        normalized_score = min(score / max_score * 10, 10) if max_score > 0 else 0

        return normalized_score, matched

    def classify(self, user_question: str) -> ClassificationResult:
        """
        分类用户问题

        Args:
            user_question: 用户原始问题

        Returns:
            ClassificationResult: 分类结果
        """
        # Step 1: 识别产品类型
        product_scores = {}
        product_matches = {}

        for product, keywords in self.product_keywords.items():
            score, matched = self._calculate_match_score(user_question, keywords)
            product_scores[product] = score
            product_matches[product] = matched

        # 选择得分最高的产品类型
        best_product = max(product_scores, key=product_scores.get)
        product_confidence = product_scores[best_product]

        # 如果所有产品得分都很低，标记为未知
        if product_confidence < 1:
            best_product = ProductType.UNKNOWN

        # Step 2: 识别功能模块
        module_scores = {}
        module_matches = {}

        for module, keywords in self.module_keywords.items():
            score, matched = self._calculate_match_score(user_question, keywords)
            module_scores[module] = score
            module_matches[module] = matched

        # 选择得分最高的功能模块
        best_module = max(module_scores, key=module_scores.get)
        module_confidence = module_scores[best_module]

        # 综合置信度
        total_confidence = (product_confidence + module_confidence) / 2

        # 合并匹配到的关键词
        all_matched = list(set(
            product_matches.get(best_product, []) + 
            module_matches.get(best_module, [])
        ))

        # 查找建议 QA
        suggestion = self.qa_suggestions.get((best_product, best_module))

        return ClassificationResult(
            product_type=best_product,
            function_module=best_module,
            confidence=round(total_confidence, 2),
            matched_keywords=all_matched,
            suggestion_qa=suggestion
        )

    def classify_with_details(self, user_question: str) -> Dict:
        """返回详细分类信息"""
        result = self.classify(user_question)

        return {
            "用户问题": user_question,
            "产品类型": result.product_type.value,
            "产品类型中文": self._get_product_name(result.product_type),
            "功能模块": result.function_module.value,
            "功能模块中文": self._get_module_name(result.function_module),
            "置信度": result.confidence,
            "匹配关键词": result.matched_keywords,
            "建议查阅": result.suggestion_qa or "请查看对应产品类型的相关章节",
            "处理建议": self._get_handling_suggestion(result)
        }

    def _get_product_name(self, product: ProductType) -> str:
        """获取产品类型中文名"""
        names = {
            ProductType.CLOUD: "云端部署 Kimi Claw",
            ProductType.DESKTOP: "Kimi Claw Desktop（桌面端）",
            ProductType.ANDROID: "Kimi Claw Android（移动端）",
            ProductType.GROUP_CHAT: "Claw 群聊产品",
            ProductType.UNKNOWN: "未知类型"
        }
        return names.get(product, "未知")

    def _get_module_name(self, module: FunctionModule) -> str:
        """获取功能模块中文名"""
        names = {
            FunctionModule.BASIC: "基础认知",
            FunctionModule.INSTALL: "下载安装",
            FunctionModule.CONFIG: "配置设置",
            FunctionModule.CHANNEL: "聊天渠道",
            FunctionModule.UPGRADE: "升级版本",
            FunctionModule.DEBUG: "故障排查",
            FunctionModule.MEMORY: "记忆上下文",
            FunctionModule.FILE: "文件收发",
            FunctionModule.COMMAND: "命令终端",
            FunctionModule.RATE_LIMIT: "额度限制",
            FunctionModule.FEISHU: "飞书专用",
            FunctionModule.FEEDBACK: "反馈交流",
            FunctionModule.AUTOMATION: "自动化操控",
            FunctionModule.DASHBOARD: "Dashboard",
            FunctionModule.BACKUP: "备份恢复",
            FunctionModule.SECURITY: "安全限制",
            FunctionModule.PERMISSION: "权限管理",
            FunctionModule.GROUP_CREATE: "创建管理",
            FunctionModule.GROUP_RULE: "群规设置",
            FunctionModule.THREAD: "Thread话题",
            FunctionModule.ROLE: "角色协作",
            FunctionModule.WORKSPACE: "工作空间"
        }
        return names.get(module, "未知")

    def _get_handling_suggestion(self, result: ClassificationResult) -> str:
        """获取处理建议"""
        suggestions = {
            ProductType.CLOUD: "请查阅《云端部署 Kimi Claw 知识库》",
            ProductType.DESKTOP: "请查阅《Kimi Claw Desktop 知识库》",
            ProductType.ANDROID: "请查阅《Kimi Claw Android 知识库》",
            ProductType.GROUP_CHAT: "请查阅《Claw 群聊产品知识库》",
            ProductType.UNKNOWN: "无法确定产品类型，建议询问用户具体使用场景"
        }

        base = suggestions.get(result.product_type, "")
        if result.suggestion_qa:
            base += f"，{result.suggestion_qa}"

        return base


# ============== 使用示例 ==============

def demo():
    """演示分类器使用"""
    classifier = ClawClassifier()

    test_questions = [
        # 云端问题
        "我的云端 Claw 连不上网了，提示 Bot 未连接",
        "怎么在网页端创建 Kimi Claw？",
        "微信消息没有同步到网页端怎么办？",
        "会员到期后记忆能保留多久？",
        "飞书群里 @机器人没有反应",

        # 桌面端问题
        "桌面客户端怎么删除？.kimi_openclaw 文件夹在哪里？",
        "Mac 上 Desktop 版对话卡住了怎么重启？",
        "桌面端支持命令行吗？",

        # Android 问题
        "安卓手机怎么下载 Kimi Claw？",
        "Dashboard 上网关一直显示正在启动",
        "怎么让 Claw 帮我打开淘宝买东西？",
        "手机锁屏后就掉线了怎么办？",
        "哪些银行 App 不能操控？",
        "如何备份 Android Claw 的配置？",

        # 群聊问题
        "怎么创建一个 Claw 群聊？",
        "群规怎么设置？",
        "Thread 是什么？",
        "群里 @机器人没反应",
        "怎么让多个 Claw 协作写报告？",

        # 模糊问题
        "我的 Claw 不回消息了",
        "怎么升级 OpenClaw？",
    ]

    print("=" * 80)
    print("Kimi Claw 产品功能分类器 - 演示")
    print("=" * 80)

    for question in test_questions:
        result = classifier.classify_with_details(question)
        print(f"\n【问题】{result['用户问题']}")
        print(f"  → 产品: {result['产品类型中文']} ({result['产品类型']})")
        print(f"  → 模块: {result['功能模块中文']} ({result['功能模块']})")
        print(f"  → 置信度: {result['置信度']}")
        print(f"  → 关键词: {', '.join(result['匹配关键词'][:5])}")
        print(f"  → 建议: {result['处理建议']}")
        print("-" * 60)


if __name__ == "__main__":
    demo()
