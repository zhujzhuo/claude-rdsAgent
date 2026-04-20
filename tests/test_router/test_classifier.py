"""问题分类器测试"""

import pytest

from rds_agent.router.classifier import (
    QuestionCategory,
    QuestionClassifier,
    get_classifier,
    classify_question,
)
from rds_agent.skills.base import SkillType


class TestQuestionClassifier:
    """问题分类器测试"""

    def test_init(self):
        """测试初始化"""
        classifier = QuestionClassifier()
        assert classifier is not None

    def test_simple_qa_what_is(self):
        """测试简单问答 - 是什么"""
        classifier = QuestionClassifier()
        category, skill_type = classifier.classify("什么是 Buffer Pool？")
        assert category == QuestionCategory.SIMPLE_QA
        assert skill_type is None

    def test_simple_qa_how_to(self):
        """测试简单问答 - 如何"""
        classifier = QuestionClassifier()
        category, skill_type = classifier.classify("如何优化 MySQL 性能？")
        assert category == QuestionCategory.SIMPLE_QA
        assert skill_type is None

    def test_simple_qa_why(self):
        """测试简单问答 - 为什么"""
        classifier = QuestionClassifier()
        category, skill_type = classifier.classify("为什么会产生慢查询？")
        assert category == QuestionCategory.SIMPLE_QA
        assert skill_type is None

    def test_simple_qa_difference(self):
        """测试简单问答 - 区别"""
        classifier = QuestionClassifier()
        category, skill_type = classifier.classify("InnoDB 和 MyISAM 有什么区别？")
        assert category == QuestionCategory.SIMPLE_QA
        assert skill_type is None

    def test_simple_qa_excluded_with_instance(self):
        """测试简单问答排除 - 涉及实例"""
        classifier = QuestionClassifier()
        # 涉及实例名称，不属于简单问答
        category, skill_type = classifier.classify("db-01 是什么配置？")
        assert category != QuestionCategory.SIMPLE_QA

    def test_simple_qa_excluded_with_diagnosis(self):
        """测试简单问答排除 - 涉及诊断"""
        classifier = QuestionClassifier()
        # 涉及诊断关键词，不属于简单问答
        category, skill_type = classifier.classify("如何诊断性能问题？")
        assert category != QuestionCategory.SIMPLE_QA

    def test_sop_skill_cpu(self):
        """测试 SOP Skill - CPU 分析"""
        classifier = QuestionClassifier()
        category, skill_type = classifier.classify("db-01 的 CPU 使用率过高")
        assert category == QuestionCategory.SOP_SKILL
        assert skill_type == SkillType.CPU_ANALYSIS

    def test_sop_skill_cpu_spike(self):
        """测试 SOP Skill - CPU 飙升"""
        classifier = QuestionClassifier()
        category, skill_type = classifier.classify("db-prod CPU 飙升")
        assert category == QuestionCategory.SOP_SKILL
        assert skill_type == SkillType.CPU_ANALYSIS

    def test_sop_skill_storage(self):
        """测试 SOP Skill - 存储分析"""
        classifier = QuestionClassifier()
        category, skill_type = classifier.classify("db-01 磁盘空间不足")
        assert category == QuestionCategory.SOP_SKILL
        assert skill_type == SkillType.STORAGE_ANALYSIS

    def test_sop_skill_storage_growth(self):
        """测试 SOP Skill - 存储增长"""
        classifier = QuestionClassifier()
        category, skill_type = classifier.classify("分析 db-01 的存储增长点")
        assert category == QuestionCategory.SOP_SKILL
        assert skill_type == SkillType.STORAGE_ANALYSIS

    def test_sop_skill_sql_optimization(self):
        """测试 SOP Skill - SQL 优化"""
        classifier = QuestionClassifier()
        category, skill_type = classifier.classify("优化 db-01 的慢 SQL")
        assert category == QuestionCategory.SOP_SKILL
        assert skill_type == SkillType.SQL_OPTIMIZATION

    def test_sop_skill_connection(self):
        """测试 SOP Skill - 连接分析"""
        classifier = QuestionClassifier()
        category, skill_type = classifier.classify("db-01 连接数过高")
        assert category == QuestionCategory.SOP_SKILL
        assert skill_type == SkillType.CONNECTION_ANALYSIS

    def test_sop_skill_no_instance(self):
        """测试 SOP Skill - 无实例名称，降级"""
        classifier = QuestionClassifier()
        # 有 CPU 关键词但无实例名称，降级为 GENERAL
        category, skill_type = classifier.classify("CPU 使用率过高怎么办")
        assert category == QuestionCategory.GENERAL
        assert skill_type is None

    def test_general_performance(self):
        """测试 GENERAL - 性能诊断"""
        classifier = QuestionClassifier()
        category, skill_type = classifier.classify("db-01 的性能情况")
        assert category == QuestionCategory.GENERAL
        assert skill_type is None

    def test_general_diagnosis(self):
        """测试 GENERAL - 诊断"""
        classifier = QuestionClassifier()
        category, skill_type = classifier.classify("帮我诊断 db-01")
        assert category == QuestionCategory.GENERAL
        assert skill_type is None

    def test_general_full_inspection(self):
        """测试 GENERAL - 完整巡检"""
        classifier = QuestionClassifier()
        category, skill_type = classifier.classify("对 db-01 做完整巡检")
        assert category == QuestionCategory.GENERAL
        assert skill_type is None

    def test_general_chat(self):
        """测试 GENERAL - 闲聊"""
        classifier = QuestionClassifier()
        category, skill_type = classifier.classify("你好")
        assert category == QuestionCategory.GENERAL
        assert skill_type is None

    def test_extract_instance_db_pattern(self):
        """测试实例提取 - db-xxx 模式"""
        classifier = QuestionClassifier()
        instance = classifier._extract_instance("查看 db-prod-01 的信息")
        assert instance == "db-prod-01"

    def test_extract_instance_inst_pattern(self):
        """测试实例提取 - inst-xxx 模式"""
        classifier = QuestionClassifier()
        instance = classifier._extract_instance("检查 inst-test-01")
        assert instance == "inst-test-01"

    def test_extract_instance_no_match(self):
        """测试实例提取 - 无匹配"""
        classifier = QuestionClassifier()
        instance = classifier._extract_instance("查看所有实例列表")
        assert instance is None


class TestGetClassifier:
    """get_classifier 函数测试"""

    def test_get_classifier_singleton(self):
        """测试单例模式"""
        classifier1 = get_classifier()
        classifier2 = get_classifier()
        assert classifier1 is classifier2


class TestClassifyQuestion:
    """classify_question 便捷函数测试"""

    def test_classify_question(self):
        """测试便捷函数"""
        category, skill_type = classify_question("什么是 Buffer Pool")
        assert category == QuestionCategory.SIMPLE_QA
        assert skill_type is None