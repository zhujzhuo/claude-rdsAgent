"""Skills/SOP 基类定义 - 标准化诊断流程框架"""

from abc import ABC, abstractmethod
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, TypedDict

from pydantic import BaseModel, Field

from rds_agent.utils.logger import get_logger

logger = get_logger("skills_base")


class SkillType(str, Enum):
    """Skill 类型 - 专业垂直问题分类"""

    CPU_ANALYSIS = "cpu_analysis"           # CPU 使用率问题分析
    STORAGE_ANALYSIS = "storage_analysis"    # 存储磁盘问题分析
    SQL_OPTIMIZATION = "sql_optimization"    # SQL 优化流程
    CONNECTION_ANALYSIS = "connection_analysis"  # 连接问题分析
    PERFORMANCE_ANALYSIS = "performance_analysis"  # 性能分析


class StepStatus(str, Enum):
    """步骤执行状态"""

    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"  # 条件不满足时跳过


class StepResult(BaseModel):
    """单个步骤执行结果"""

    step_name: str = Field(..., description="步骤名称")
    status: StepStatus = Field(default=StepStatus.PENDING)
    output: Any = Field(default=None, description="步骤输出数据")
    analysis: str = Field(default="", description="分析结论")
    next_action: str = Field(default="", description="下一步建议")
    error: Optional[str] = Field(default=None)
    timestamp: datetime = Field(default_factory=datetime.now)


class SOPStep(BaseModel):
    """SOP 步骤定义 - 标准化诊断流程中的单个步骤"""

    name: str = Field(..., description="步骤名称")
    description: str = Field(default="", description="步骤描述")
    tool_name: str = Field(..., description="调用的工具名称")
    tool_params: Dict[str, Any] = Field(
        default_factory=dict,
        description="工具参数模板，支持 $变量引用"
    )
    condition: Optional[str] = Field(
        default=None,
        description="执行条件表达式，如 '$cpu_usage > 70'"
    )
    analysis_prompt: str = Field(default="", description="分析提示词")
    decision_rules: List[Dict] = Field(
        default_factory=list,
        description="决策规则，根据结果决定后续动作"
    )
    dependencies: List[str] = Field(
        default_factory=list,
        description="依赖的前置步骤名称"
    )
    timeout: int = Field(default=30, description="超时时间(秒)")
    skip_on_condition: bool = Field(
        default=False,
        description="条件不满足时是否跳过而非失败"
    )

    def build_params(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """构建实际参数（从上下文填充变量）

        Args:
            context: 执行上下文，包含实例名称、历史数据等

        Returns:
            实际参数字典
        """
        params = {}
        for key, template in self.tool_params.items():
            if isinstance(template, str) and template.startswith("$"):
                # 从上下文引用变量，如 "$instance_name"
                var_name = template[1:]
                params[key] = context.get(var_name)
            elif isinstance(template, dict):
                # 递归处理嵌套参数
                params[key] = self._build_nested_params(template, context)
            else:
                params[key] = template
        return params

    def _build_nested_params(
        self,
        template: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """处理嵌套参数"""
        result = {}
        for key, value in template.items():
            if isinstance(value, str) and value.startswith("$"):
                var_name = value[1:]
                result[key] = context.get(var_name)
            else:
                result[key] = value
        return result


class SOP(BaseModel):
    """标准操作流程定义 - 精确规划的诊断流程"""

    name: str = Field(..., description="SOP 名称")
    skill_type: SkillType = Field(..., description="关联的 Skill 类型")
    description: str = Field(default="", description="流程描述")
    version: str = Field(default="1.0", description="版本号")

    steps: List[SOPStep] = Field(
        default_factory=list,
        description="步骤列表，按顺序执行"
    )

    # 决策点定义：根据某步骤结果决定后续路径
    decision_points: Dict[str, Dict] = Field(
        default_factory=dict,
        description="决策点配置，key为步骤名"
    )

    # 最终结论模板
    conclusion_template: str = Field(
        default="",
        description="结论生成模板，支持 {变量} 引用"
    )

    # 元数据
    author: str = Field(default="", description="创建者")
    created_at: datetime = Field(default_factory=datetime.now)
    tags: List[str] = Field(default_factory=list, description="标签")


class SkillState(TypedDict):
    """Skill 执行状态"""

    skill_type: str
    sop_name: str
    instance_name: str

    # 执行上下文（存储各步骤的数据）
    context: Dict[str, Any]

    # 步骤执行结果
    step_results: List[Dict[str, Any]]

    # 当前步骤索引
    current_step: int

    # 执行进度 (0-100)
    progress: int

    # 最终结论
    conclusion: Optional[str]

    # 根因定位（核心产出）
    root_cause: Optional[str]

    # 关键发现
    key_findings: List[str]

    # 优化建议
    recommendations: List[str]

    # 错误信息
    error: Optional[str]


class BaseSkill(ABC):
    """Skill 基类 - 所有标准化诊断流程的抽象基类

    子类需要实现：
    - get_sop(): 返回该 Skill 的 SOP 定义
    - _analyze_output(): 分析步骤输出
    - _generate_conclusion(): 生成最终结论
    """

    skill_type: SkillType
    sop: SOP

    def __init__(self, mysql_client=None, tools_registry: Dict[str, Callable] = None):
        """
        初始化 Skill

        Args:
            mysql_client: MySQL 数据库客户端
            tools_registry: 工具函数注册表
        """
        self.mysql_client = mysql_client
        self.tools_registry = tools_registry or {}

        # 初始化状态
        self.state: SkillState = {
            "skill_type": self.skill_type.value,
            "sop_name": self.sop.name if hasattr(self, 'sop') else "",
            "instance_name": "",
            "context": {},
            "step_results": [],
            "current_step": 0,
            "progress": 0,
            "conclusion": None,
            "root_cause": None,
            "key_findings": [],
            "recommendations": [],
            "error": None,
        }

    @abstractmethod
    def get_sop(self) -> SOP:
        """获取该 Skill 的 SOP 定义

        Returns:
            SOP 流程定义
        """
        pass

    def execute(
        self,
        instance_name: str,
        initial_context: Optional[Dict] = None
    ) -> SkillState:
        """执行 Skill 流程

        Args:
            instance_name: 目标实例名称
            initial_context: 初始上下文数据

        Returns:
            SkillState 执行状态和结果
        """
        # 初始化
        self.state["instance_name"] = instance_name
        self.state["context"] = initial_context or {}
        self.state["context"]["instance_name"] = instance_name

        sop = self.get_sop()
        self.state["sop_name"] = sop.name

        logger.info(f"开始执行 Skill: {self.skill_type}, 实例: {instance_name}")
        logger.info(f"SOP: {sop.name}, 步骤数: {len(sop.steps)}")

        # 按顺序执行步骤
        for i, step in enumerate(sop.steps):
            self.state["current_step"] = i

            # 检查依赖
            if not self._check_dependencies(step):
                self._skip_step(step, "依赖步骤未满足")
                continue

            # 检查执行条件
            if step.condition and not self._evaluate_condition(step.condition):
                if step.skip_on_condition:
                    self._skip_step(step, "执行条件不满足")
                    continue
                else:
                    logger.warning(f"步骤 {step.name} 条件不满足，跳过")
                    continue

            # 执行步骤
            result = self._execute_step(step)
            self.state["step_results"].append(result.model_dump())

            # 处理决策点
            if step.name in sop.decision_points:
                self._handle_decision_point(step.name, result)

            # 更新进度
            self.state["progress"] = int((i + 1) / len(sop.steps) * 100)
            logger.info(f"进度: {self.state['progress']}%, 步骤: {step.name}")

        # 生成最终结论
        self._generate_conclusion()

        logger.info(f"Skill 执行完成: {self.skill_type}")
        logger.info(f"根因: {self.state.get('root_cause')}")

        return self.state

    def _execute_step(self, step: SOPStep) -> StepResult:
        """执行单个步骤

        Args:
            step: SOP 步骤定义

        Returns:
            StepResult 执行结果
        """
        result = StepResult(
            step_name=step.name,
            status=StepStatus.RUNNING,
            timestamp=datetime.now()
        )

        logger.info(f"执行步骤: {step.name} - {step.description}")

        try:
            # 构建参数
            params = step.build_params(self.state["context"])

            # 获取工具函数
            tool_func = self._get_tool(step.tool_name)

            if tool_func:
                # 调用工具
                logger.debug(f"调用工具: {step.tool_name}, 参数: {params}")
                output = tool_func(**params)
                result.output = output

                # 分析输出
                analysis = self._analyze_output(step, output)
                result.analysis = analysis

                # 更新上下文
                self.state["context"][step.name] = {
                    "output": output,
                    "analysis": analysis,
                }

                result.status = StepStatus.SUCCESS
                logger.info(f"步骤成功: {step.name}")
            else:
                # 工具不存在
                result.status = StepStatus.FAILED
                result.error = f"工具 {step.tool_name} 不存在"
                logger.error(f"步骤失败: {step.name} - {result.error}")

        except Exception as e:
            result.status = StepStatus.FAILED
            result.error = str(e)
            logger.error(f"步骤异常: {step.name} - {e}")

        return result

    def _get_tool(self, tool_name: str) -> Optional[Callable]:
        """获取工具函数

        Args:
            tool_name: 工具名称

        Returns:
            工具函数，如果不存在返回 None
        """
        # 从注册表获取
        if tool_name in self.tools_registry:
            return self.tools_registry[tool_name]

        # 尝试从 tools 模块动态获取
        try:
            from rds_agent.tools import get_all_langchain_tools
            tools_dict = {t.name: t for t in get_all_langchain_tools()}
            if tool_name in tools_dict:
                return tools_dict[tool_name].invoke
        except ImportError:
            pass

        # 特殊工具处理
        if tool_name == "llm_analysis":
            return self._llm_analysis_tool

        if tool_name == "generate_recommendations":
            return self._generate_recommendations_tool

        return None

    def _llm_analysis_tool(self, context: Dict, prompt: str) -> Dict:
        """LLM 分析工具"""
        from rds_agent.core.nodes import get_llm

        llm = get_llm()
        full_prompt = f"{prompt}\n\n上下文数据：\n{context}"
        response = llm.invoke(full_prompt)

        return {"analysis": response}

    def _generate_recommendations_tool(
        self,
        root_cause: str = None
    ) -> List[str]:
        """生成建议工具"""
        return self._generate_recommendations()

    @abstractmethod
    def _analyze_output(self, step: SOPStep, output: Any) -> str:
        """分析步骤输出（子类实现）

        Args:
            step: SOP 步骤定义
            output: 步骤输出数据

        Returns:
            分析结论字符串
        """
        pass

    def _check_dependencies(self, step: SOPStep) -> bool:
        """检查步骤依赖是否满足

        Args:
            step: SOP 步骤定义

        Returns:
            是否满足依赖
        """
        for dep_name in step.dependencies:
            # 检查依赖步骤是否成功执行
            dep_result = None
            for result in self.state["step_results"]:
                if result["step_name"] == dep_name:
                    dep_result = result
                    break

            if not dep_result:
                logger.warning(f"依赖步骤 {dep_name} 未执行")
                return False

            if dep_result["status"] != StepStatus.SUCCESS.value:
                logger.warning(f"依赖步骤 {dep_name} 未成功")
                return False

        return True

    def _evaluate_condition(self, condition: str) -> bool:
        """评估执行条件

        Args:
            condition: 条件表达式，如 "$cpu_usage > 70"

        Returns:
            是否满足条件
        """
        try:
            # 替换变量引用
            eval_condition = condition
            for key, value in self.state["context"].items():
                if isinstance(value, (int, float, bool)):
                    eval_condition = eval_condition.replace(f"${key}", str(value))
                elif isinstance(value, str):
                    eval_condition = eval_condition.replace(f"${key}", f"'{value}'")
                elif isinstance(value, dict):
                    # 处理嵌套引用，如 $get_monitoring_data.cpu_usage
                    for sub_key, sub_value in value.items():
                        if isinstance(sub_value, (int, float)):
                            eval_condition = eval_condition.replace(
                                f"${key}.{sub_key}",
                                str(sub_value)
                            )

            # 评估表达式
            result = eval(eval_condition)
            logger.debug(f"条件评估: {condition} -> {result}")
            return bool(result)

        except Exception as e:
            logger.warning(f"条件评估失败: {condition} - {e}")
            return False

    def _handle_decision_point(
        self,
        step_name: str,
        result: StepResult
    ) -> None:
        """处理决策点

        Args:
            step_name: 步骤名称
            result: 步骤结果
        """
        sop = self.get_sop()
        decision_config = sop.decision_points.get(step_name)

        if not decision_config:
            return

        # 检查决策规则
        for rule_name, rule_config in decision_config.items():
            condition = rule_config.get("condition")
            if condition and self._evaluate_condition(condition):
                # 执行规则动作
                if "root_cause" in rule_config:
                    self.state["root_cause"] = rule_config["root_cause"]
                    logger.info(f"决策点定位根因: {rule_config['root_cause']}")

                if "skip_steps" in rule_config:
                    # 标记要跳过的步骤
                    self.state["context"]["_skip_steps"] = rule_config["skip_steps"]

                logger.info(f"决策点触发: {rule_name}")

    def _skip_step(self, step: SOPStep, reason: str) -> None:
        """跳过步骤

        Args:
            step: SOP 步骤定义
            reason: 跳过原因
        """
        result = StepResult(
            step_name=step.name,
            status=StepStatus.SKIPPED,
            analysis=f"跳过原因: {reason}",
            timestamp=datetime.now()
        )
        self.state["step_results"].append(result.model_dump())
        logger.info(f"跳过步骤: {step.name} - {reason}")

    def _generate_conclusion(self) -> None:
        """生成最终结论"""
        sop = self.get_sop()
        context = self.state["context"]

        # 收集关键发现
        key_findings = []
        for result in self.state["step_results"]:
            if result["status"] == StepStatus.SUCCESS.value and result["analysis"]:
                key_findings.append(f"- {result['step_name']}: {result['analysis'][:100]}")
        self.state["key_findings"] = key_findings

        # 生成建议
        recommendations = self._generate_recommendations()
        self.state["recommendations"] = recommendations

        # 使用模板生成结论
        if sop.conclusion_template:
            try:
                conclusion = sop.conclusion_template.format(
                    instance_name=self.state["instance_name"],
                    root_cause=self.state.get("root_cause", "未定位到根因"),
                    key_findings="\n".join(key_findings),
                    recommendations="\n".join(recommendations),
                    **context
                )
                self.state["conclusion"] = conclusion
            except KeyError as e:
                logger.warning(f"结论模板变量缺失: {e}")
                self.state["conclusion"] = self._generate_default_conclusion()
        else:
            self.state["conclusion"] = self._generate_default_conclusion()

    def _generate_default_conclusion(self) -> str:
        """生成默认结论"""
        lines = [
            f"## {self.skill_type.value} 分析报告",
            f"",
            f"**实例**: {self.state['instance_name']}",
            f"",
            f"### 根因定位",
            f"{self.state.get('root_cause', '需要进一步分析')}",
            f"",
            f"### 关键发现",
        ]

        for finding in self.state["key_findings"]:
            lines.append(finding)

        lines.append("")
        lines.append("### 优化建议")

        for rec in self.state["recommendations"]:
            lines.append(f"- {rec}")

        return "\n".join(lines)

    def _generate_recommendations(self) -> List[str]:
        """生成优化建议（子类可覆盖）"""
        recommendations = []
        context = self.state["context"]

        # 通用建议
        recommendations.append("持续监控相关指标")

        # 根据根因添加建议
        root_cause = self.state.get("root_cause")
        if root_cause:
            recommendations.append(f"针对根因({root_cause})制定优化方案")

        return recommendations