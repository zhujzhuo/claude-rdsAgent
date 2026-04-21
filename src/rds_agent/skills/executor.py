"""Skills/SOP 执行器 - 管理 Skill 实例和执行调度

支持两种 Skill 定义方式：
1. Python 文件定义 (静态 Skill 类)
2. Markdown 文档定义 (动态生成)
"""

from pathlib import Path
from typing import Dict, List, Optional, Type, Union

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
    4. 支持从 Markdown 文档动态加载 Skill
    """

    def __init__(
        self,
        mysql_client=None,
        tools_registry: Dict = None,
        load_markdown: bool = True,
    ):
        """初始化执行器

        Args:
            mysql_client: MySQL 数据库客户端
            tools_registry: 工具函数注册表
            load_markdown: 是否加载 Markdown Skill
        """
        self.mysql_client = mysql_client
        self.tools_registry = tools_registry or {}

        # Skill 注册表
        self._skills: Dict[SkillType, BaseSkill] = {}

        # 自动注册 Python Skill
        self._auto_register()

        # 加载 Markdown Skill
        if load_markdown:
            self._load_markdown_skills()

    def _auto_register(self) -> None:
        """自动注册 Python Skill 类"""
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

    def _load_markdown_skills(self) -> None:
        """加载 Markdown Skill 文档"""
        try:
            from rds_agent.skills.parser import (
                SkillGenerator,
                MarkdownSkill,
            )

            generator = SkillGenerator()
            skills_dir = generator.skills_dir

            if not skills_dir.exists():
                logger.debug("Markdown Skills 目录不存在")
                return

            skill_files = generator.parser.list_skill_files()

            for file_path in skill_files:
                if file_path.name == "README.md":
                    continue

                try:
                    skill = MarkdownSkill(
                        str(file_path),
                        mysql_client=self.mysql_client,
                        tools_registry=self.tools_registry,
                    )
                    skill_type = skill.skill_type

                    # 如果已存在，不覆盖 Python Skill
                    if skill_type not in self._skills:
                        self._skills[skill_type] = skill
                        logger.info(f"从 Markdown 加载 Skill: {skill_type.value}")
                    else:
                        logger.debug(f"Skill {skill_type.value} 已存在，跳过 Markdown 版本")

                except Exception as e:
                    logger.warning(f"加载 Markdown Skill 失败: {file_path} - {e}")

        except ImportError:
            logger.debug("Markdown Skill 解析器未找到")

    def register_skill(
        self,
        skill_class: Union[Type[BaseSkill], BaseSkill],
        overwrite: bool = False,
    ) -> None:
        """注册 Skill

        Args:
            skill_class: Skill 类或实例
            overwrite: 是否覆盖已存在的 Skill
        """
        # 如果传入的是类，创建实例
        if isinstance(skill_class, type):
            skill_instance = skill_class(
                mysql_client=self.mysql_client,
                tools_registry=self.tools_registry,
            )
        else:
            skill_instance = skill_class

        skill_type = skill_instance.skill_type

        if skill_type in self._skills and not overwrite:
            logger.debug(f"Skill {skill_type.value} 已存在，跳过注册")
            return

        self._skills[skill_type] = skill_instance
        logger.info(f"已注册 Skill: {skill_type.value}")

    def register_markdown_skill(
        self,
        markdown_path: str,
        overwrite: bool = False,
    ) -> bool:
        """从 Markdown 文件注册 Skill

        Args:
            markdown_path: Markdown 文件路径
            overwrite: 是否覆盖已存在的 Skill

        Returns:
            是否成功注册
        """
        try:
            from rds_agent.skills.parser import MarkdownSkill

            skill = MarkdownSkill(
                markdown_path,
                mysql_client=self.mysql_client,
                tools_registry=self.tools_registry,
            )

            self.register_skill(skill, overwrite)
            return True

        except Exception as e:
            logger.error(f"注册 Markdown Skill 失败: {markdown_path} - {e}")
            return False

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

    def reload_markdown_skills(self) -> int:
        """重新加载 Markdown Skill

        Returns:
            加载的 Skill 数量
        """
        count = 0
        try:
            from rds_agent.skills.parser import SkillGenerator, MarkdownSkill

            generator = SkillGenerator()
            skill_files = generator.parser.list_skill_files()

            for file_path in skill_files:
                if file_path.name == "README.md":
                    continue

                try:
                    skill = MarkdownSkill(
                        str(file_path),
                        mysql_client=self.mysql_client,
                        tools_registry=self.tools_registry,
                    )
                    skill_type = skill.skill_type
                    self._skills[skill_type] = skill
                    count += 1
                    logger.info(f"重新加载 Markdown Skill: {skill_type.value}")

                except Exception as e:
                    logger.warning(f"重新加载失败: {file_path} - {e}")

        except ImportError:
            logger.warning("Markdown Skill 解析器未找到")

        return count


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