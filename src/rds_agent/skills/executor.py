"""Skills/SOP 执行器 - 管理 Skill 实例和执行调度"""

from typing import Dict, List, Optional, Type

from rds_agent.skills.base import (
    BaseSkill,
    SkillState,
    SkillType,
)
from rds_agent.utils.logger import get_logger

logger = get_logger("skills_executor")


class SkillExecutor:
    """Skill 执行器 - 负责 Skill 注册、查找和执行

    核心职责：
    1. 注册和管理各类 Skill 实例
    2. 根据 SkillType 查找对应的 Skill
    3. 执行 Skill 并返回结果
    """

    def __init__(self, mysql_client=None, tools_registry: Dict = None):
        """初始化执行器

        Args:
            mysql_client: MySQL 数据库客户端
            tools_registry: 工具函数注册表
        """
        self.mysql_client = mysql_client
        self.tools_registry = tools_registry or {}

        # Skill 注册表
        self._skills: Dict[SkillType, BaseSkill] = {}

        # 自动注册已定义的 Skill
        self._auto_register()

    def _auto_register(self) -> None:
        """自动注册已定义的 Skill 类"""
        try:
            from rds_agent.skills.cpu_skill import CPUAnalysisSkill
            self.register_skill(CPUAnalysisSkill)
        except ImportError:
            logger.debug("CPUAnalysisSkill 未找到，跳过注册")

        try:
            from rds_agent.skills.storage_skill import StorageAnalysisSkill
            self.register_skill(StorageAnalysisSkill)
        except ImportError:
            logger.debug("StorageAnalysisSkill 未找到，跳过注册")

        try:
            from rds_agent.skills.sql_skill import SQLOptimizationSkill
            self.register_skill(SQLOptimizationSkill)
        except ImportError:
            logger.debug("SQLOptimizationSkill 未找到，跳过注册")

        try:
            from rds_agent.skills.connection_skill import ConnectionAnalysisSkill
            self.register_skill(ConnectionAnalysisSkill)
        except ImportError:
            logger.debug("ConnectionAnalysisSkill 未找到，跳过注册")

    def register_skill(self, skill_class: Type[BaseSkill]) -> None:
        """注册 Skill 类

        Args:
            skill_class: Skill 类（不是实例）
        """
        skill_instance = skill_class(
            mysql_client=self.mysql_client,
            tools_registry=self.tools_registry
        )
        skill_type = skill_instance.skill_type
        self._skills[skill_type] = skill_instance
        logger.info(f"已注册 Skill: {skill_type.value}")

    def get_skill(self, skill_type: SkillType) -> Optional[BaseSkill]:
        """获取指定类型的 Skill

        Args:
            skill_type: Skill 类型

        Returns:
            Skill 实例，不存在返回 None
        """
        return self._skills.get(skill_type)

    def execute(
        self,
        skill_type: SkillType,
        instance_name: str,
        initial_context: Optional[Dict] = None
    ) -> SkillState:
        """执行指定类型的 Skill

        Args:
            skill_type: Skill 类型
            instance_name: 目标实例名称
            initial_context: 初始上下文数据

        Returns:
            SkillState 执行状态和结果

        Raises:
            ValueError: Skill 类型未注册
        """
        skill = self.get_skill(skill_type)

        if not skill:
            logger.error(f"Skill 未注册: {skill_type.value}")
            raise ValueError(f"Skill 未注册: {skill_type.value}")

        logger.info(f"执行 Skill: {skill_type.value}, 实例: {instance_name}")

        result = skill.execute(instance_name, initial_context)

        logger.info(
            f"Skill 执行完成: {skill_type.value}, "
            f"根因: {result.get('root_cause')}"
        )

        return result

    def list_skills(self) -> List[SkillType]:
        """列出已注册的 Skill 类型"""
        return list(self._skills.keys())

    def has_skill(self, skill_type: SkillType) -> bool:
        """检查 Skill 是否已注册"""
        return skill_type in self._skills


# 全局单例
_skill_executor: Optional[SkillExecutor] = None


def get_skill_executor(
    mysql_client=None,
    tools_registry: Dict = None
) -> SkillExecutor:
    """获取 Skill 执行器单例

    Args:
        mysql_client: MySQL 数据库客户端
        tools_registry: 工具函数注册表

    Returns:
        SkillExecutor 实例
    """
    global _skill_executor

    if _skill_executor is None:
        _skill_executor = SkillExecutor(mysql_client, tools_registry)
    elif mysql_client or tools_registry:
        # 更新配置
        if mysql_client:
            _skill_executor.mysql_client = mysql_client
        if tools_registry:
            _skill_executor.tools_registry = tools_registry

    return _skill_executor


def create_skill_executor(
    mysql_client=None,
    tools_registry: Dict = None
) -> SkillExecutor:
    """创建新的 Skill 执行器实例

    Args:
        mysql_client: MySQL 数据库客户端
        tools_registry: 工具函数注册表

    Returns:
        新的 SkillExecutor 实例
    """
    return SkillExecutor(mysql_client, tools_registry)