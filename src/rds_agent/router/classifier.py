"""问题分类器 - 三层问题分类路由"""

import re
from enum import Enum
from typing import Optional, Tuple

from rds_agent.skills.base import SkillType
from rds_agent.utils.logger import get_logger

logger = get_logger("router_classifier")


class QuestionCategory(str, Enum):
    """问题分类 - 三层路由"""

    SIMPLE_QA = "simple_qa"    # 简单常识问答 - 知识库回答
    SOP_SKILL = "sop_skill"    # 专业垂直类问题 - SOP/Skills 执行
    GENERAL = "general"        # 泛化问题 - Agent 自行规划


class QuestionClassifier:
    """问题分类器 - 根据用户问题进行三层分类

    分类规则：
    1. SIMPLE_QA: 纯知识问答，不涉及实例
       - 关键词："是什么"、"如何"、"为什么"、"原理"、"区别"、"最佳实践"
       - 排除：涉及实例名称（db-、inst-）、诊断分析类词汇

    2. SOP_SKILL: 专业垂直问题，有明确问题类型 + 实例
       - CPU_ANALYSIS: "CPU使用率"、"CPU过高"、"CPU打满"
       - STORAGE_ANALYSIS: "磁盘空间"、"存储增长"、"增长点"
       - SQL_OPTIMIZATION: "SQL优化"、"慢SQL优化"、"执行计划"
       - CONNECTION_ANALYSIS: "连接数过高"、"会话突增"

    3. GENERAL: 不满足上述两类的问题
    """

    # 简单问答关键词
    SIMPLE_QA_KEYWORDS = [
        "是什么", "什么是", "如何", "怎么", "为什么", "原因是什么",
        "原理", "机制", "概念", "区别", "对比", "最佳实践",
        "推荐", "建议", "如何理解", "怎样理解", "介绍一下",
        "解释", "讲解", "说明", "帮我理解", "能解释",
    ]

    # 排除简单问答的关键词（涉及实例或诊断）
    EXCLUDE_SIMPLE_KEYWORDS = [
        "实例", "db-", "inst-", "服务器", "主机",
        "诊断", "分析", "检查", "排查", "巡检",
        "问题", "异常", "故障", "报警", "慢查询",
        "性能", "CPU", "内存", "磁盘", "连接",
    ]

    # SOP Skill 关键词映射
    SOP_SKILL_KEYWORDS = {
        SkillType.CPU_ANALYSIS: [
            "CPU使用率", "CPU过高", "CPU打满", "CPU飙升",
            "CPU占用", "CPU利用率", "CPU满", "CPU问题",
            "处理器", "CPU异常", "CPU报警",
        ],
        SkillType.STORAGE_ANALYSIS: [
            "磁盘空间", "存储空间", "磁盘增长", "存储增长",
            "增长点", "空间不足", "磁盘满", "存储满",
            "磁盘占用", "存储占用", "磁盘问题", "存储问题",
            "表空间", "ibdata", "磁盘分析",
        ],
        SkillType.SQL_OPTIMIZATION: [
            "SQL优化", "慢SQL优化", "优化SQL", "执行计划",
            "SQL调优", "语句优化", "查询优化", "SQL分析",
            "慢查询优化", "SQL性能", "SQL问题",
        ],
        SkillType.CONNECTION_ANALYSIS: [
            "连接数过高", "会话突增", "连接数", "会话数",
            "连接问题", "会话问题", "Threads_connected",
            "max_connections", "连接满", "会话激增",
        ],
    }

    # 实例名称模式
    INSTANCE_PATTERNS = [
        r"db-[a-zA-Z0-9\-]+",       # db-prod-01
        r"inst-[a-zA-Z0-9\-]+",     # inst-test-01
        r"实例\s+[a-zA-Z0-9\-]+",   # 实例 prod-01
        r"[a-zA-Z0-9\-]+\s*实例",   # prod-01 实例
    ]

    def __init__(self):
        """初始化分类器"""
        # 构建正则表达式
        self._instance_regex = re.compile(
            "|".join(self.INSTANCE_PATTERNS),
            re.IGNORECASE
        )

    def classify(self, message: str) -> Tuple[QuestionCategory, Optional[SkillType]]:
        """分类用户问题

        Args:
            message: 用户输入消息

        Returns:
            Tuple[QuestionCategory, Optional[SkillType]]
            - 问题分类
            - 如果是 SOP_SKILL，返回对应的 SkillType
        """
        message_lower = message.lower()

        # Step 1: 检查是否是 SOP_SKILL
        skill_type = self._detect_sop_skill(message)
        if skill_type:
            # SOP Skill 需要有实例名称
            instance = self._extract_instance(message)
            if instance:
                logger.info(
                    f"分类为 SOP_SKILL: {skill_type.value}, "
                    f"实例: {instance}"
                )
                return QuestionCategory.SOP_SKILL, skill_type
            else:
                # 有 Skill 关键词但无实例，降级为 GENERAL
                logger.info(
                    f"检测到 Skill 关键词但无实例: {skill_type.value}, "
                    f"降级为 GENERAL"
                )
                return QuestionCategory.GENERAL, None

        # Step 2: 检查是否是 SIMPLE_QA
        if self._is_simple_qa(message):
            logger.info(f"分类为 SIMPLE_QA: {message[:50]}")
            return QuestionCategory.SIMPLE_QA, None

        # Step 3: 默认为 GENERAL
        logger.info(f"分类为 GENERAL: {message[:50]}")
        return QuestionCategory.GENERAL, None

    def _is_simple_qa(self, message: str) -> bool:
        """检查是否是简单问答

        Args:
            message: 用户消息

        Returns:
            是否是简单问答
        """
        # 检查是否包含简单问答关键词
        has_simple_keyword = any(
            kw in message for kw in self.SIMPLE_QA_KEYWORDS
        )

        # 检查是否包含排除关键词
        has_exclude_keyword = any(
            kw in message for kw in self.EXCLUDE_SIMPLE_KEYWORDS
        )

        # 简单问答：有简单关键词，且没有排除关键词
        return has_simple_keyword and not has_exclude_keyword

    def _detect_sop_skill(self, message: str) -> Optional[SkillType]:
        """检测 SOP Skill 类型

        Args:
            message: 用户消息

        Returns:
            SkillType 或 None
        """
        for skill_type, keywords in self.SOP_SKILL_KEYWORDS.items():
            for keyword in keywords:
                if keyword.lower() in message.lower():
                    return skill_type

        return None

    def _extract_instance(self, message: str) -> Optional[str]:
        """提取实例名称

        Args:
            message: 用户消息

        Returns:
            实例名称或 None
        """
        match = self._instance_regex.search(message)
        if match:
            return match.group(0).strip()
        return None

    def get_skill_keywords(self, skill_type: SkillType) -> list:
        """获取指定 Skill 的关键词列表"""
        return self.SOP_SKILL_KEYWORDS.get(skill_type, [])


# 全局分类器实例
_classifier: Optional[QuestionClassifier] = None


def get_classifier() -> QuestionClassifier:
    """获取分类器单例"""
    global _classifier
    if _classifier is None:
        _classifier = QuestionClassifier()
    return _classifier


def classify_question(message: str) -> Tuple[QuestionCategory, Optional[SkillType]]:
    """分类问题的便捷函数"""
    return get_classifier().classify(message)