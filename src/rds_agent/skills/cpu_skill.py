"""CPU 分析 Skill - CPU 使用率问题标准化诊断"""

from typing import Any, Dict

from rds_agent.skills.base import (
    BaseSkill,
    SkillState,
    SkillType,
    SOP,
    SOPStep,
    StepStatus,
)
from rds_agent.skills.sops.cpu_sop import CPU_ANALYSIS_SOP
from rds_agent.utils.logger import get_logger

logger = get_logger("cpu_skill")


class CPUAnalysisSkill(BaseSkill):
    """CPU 使用率分析 Skill

    标准化诊断流程：
    1. 获取 CPU 监控数据
    2. 检查会话数突增（关键：判断根因）
    3. 获取 CPU 高峰 Profiling
    4. 获取慢 SQL（与 Profiling 对比）
    5. 分析关键 SQL 执行计划
    6. 检查锁等待
    7. 检查 Buffer Pool 命中率
    8. 根因分析
    9. 生成优化建议

    关键特性：
    - 决策点：会话突增 > 50% → 根因定位为业务突增
    - 避免 LLM 因果颠倒问题
    """

    skill_type = SkillType.CPU_ANALYSIS
    sop = CPU_ANALYSIS_SOP

    def __init__(self, mysql_client=None, tools_registry: Dict = None):
        """初始化 CPU 分析 Skill

        Args:
            mysql_client: MySQL 数据库客户端
            tools_registry: 工具函数注册表
        """
        super().__init__(mysql_client, tools_registry)
        self.sop = CPU_ANALYSIS_SOP

    def get_sop(self) -> SOP:
        """获取 CPU 分析 SOP"""
        return CPU_ANALYSIS_SOP

    def _analyze_output(self, step: SOPStep, output: Any) -> str:
        """分析步骤输出

        Args:
            step: SOP 步骤定义
            output: 步骤输出数据

        Returns:
            分析结论字符串
        """
        if output is None:
            return "未获取到数据"

        analysis_map = {
            "get_monitoring_data": self._analyze_monitoring_data,
            "check_session_change": self._analyze_session_change,
            "get_profiling": self._analyze_profiling,
            "get_slow_queries": self._analyze_slow_queries,
            "analyze_sql_plan": self._analyze_sql_plan,
            "check_lock_status": self._analyze_lock_status,
            "check_buffer_pool": self._analyze_buffer_pool,
            "root_cause_analysis": self._analyze_root_cause,
            "generate_recommendations": self._analyze_recommendations,
        }

        analyzer = analysis_map.get(step.name, self._default_analyzer)
        return analyzer(output)

    def _analyze_monitoring_data(self, output: Any) -> str:
        """分析 CPU 监控数据"""
        if isinstance(output, dict):
            cpu_usage = output.get("cpu_usage", 0)
            peak_time = output.get("peak_time", "")

            if cpu_usage > 90:
                return f"CPU 使用率严重过高：{cpu_usage}%，高峰时段：{peak_time}"
            elif cpu_usage > 70:
                return f"CPU 使用率偏高：{cpu_usage}%，高峰时段：{peak_time}"
            else:
                return f"CPU 使用率正常：{cpu_usage}%"

        return f"CPU 监控数据：{output}"

    def _analyze_session_change(self, output: Any) -> str:
        """分析会话数变化 - 关键步骤"""
        if isinstance(output, dict):
            current_sessions = output.get("current_sessions", 0)
            avg_sessions = output.get("avg_sessions", 0)
            change_rate = output.get("change_rate", 0)

            # 计算变化率（如果未提供）
            if change_rate == 0 and avg_sessions > 0:
                change_rate = ((current_sessions - avg_sessions) / avg_sessions) * 100

            # 存储变化率到上下文（供决策点使用）
            self.state["context"]["session_change_rate"] = change_rate

            if change_rate > 50:
                return (
                    f"会话数突增：当前 {current_sessions}，"
                    f"平均 {avg_sessions}，变化率 {change_rate:.1f}%"
                )
            elif change_rate > 20:
                return (
                    f"会话数略有增长：当前 {current_sessions}，"
                    f"变化率 {change_rate:.1f}%"
                )
            else:
                return f"会话数稳定：当前 {current_sessions}，变化率 {change_rate:.1f}%"

        return f"会话数据：{output}"

    def _analyze_profiling(self, output: Any) -> str:
        """分析 Profiling 数据"""
        if isinstance(output, dict):
            top_operations = output.get("top_operations", [])

            if not top_operations:
                return "未获取到 Profiling 数据"

            # 提取高 CPU 操作
            high_cpu_ops = [
                op for op in top_operations
                if op.get("cpu_time", 0) > 100
            ]

            if high_cpu_ops:
                ops_str = ", ".join([
                    f"{op.get('operation', 'unknown')} ({op.get('cpu_time', 0)}ms)"
                    for op in high_cpu_ops[:3]
                ])
                return f"高 CPU 操作：{ops_str}"

            return "未发现明显高 CPU 操作"

        return f"Profiling 数据：{output}"

    def _analyze_slow_queries(self, output: Any) -> str:
        """分析慢 SQL"""
        if isinstance(output, dict):
            slow_queries = output.get("slow_queries", [])
            count = output.get("count", 0)

            if count == 0:
                return "未发现慢 SQL"

            # 存储慢 SQL 数量
            self.state["context"]["slow_query_count"] = count

            # 提取 SQL 模式
            sql_patterns = output.get("sql_patterns", [])
            if sql_patterns:
                patterns_str = ", ".join(sql_patterns[:3])
                return f"发现 {count} 条慢 SQL，模式：{patterns_str}"

            return f"发现 {count} 条慢 SQL"

        return f"慢 SQL 数据：{output}"

    def _analyze_sql_plan(self, output: Any) -> str:
        """分析 SQL 执行计划"""
        if isinstance(output, dict):
            issues = output.get("issues", [])

            if not issues:
                return "SQL 执行计划正常"

            issues_str = ", ".join(issues[:3])
            return f"执行计划问题：{issues_str}"

        return f"执行计划数据：{output}"

    def _analyze_lock_status(self, output: Any) -> str:
        """分析锁等待"""
        if isinstance(output, dict):
            lock_wait_count = output.get("lock_wait_count", 0)

            # 存储锁等待数量
            self.state["context"]["lock_wait_count"] = lock_wait_count

            if lock_wait_count > 10:
                return f"存在严重锁等待：{lock_wait_count} 个锁等待"
            elif lock_wait_count > 0:
                return f"存在少量锁等待：{lock_wait_count} 个"
            else:
                return "无锁等待"

        return f"锁状态数据：{output}"

    def _analyze_buffer_pool(self, output: Any) -> str:
        """分析 Buffer Pool"""
        if isinstance(output, dict):
            hit_rate = output.get("hit_rate", 100)

            # 存储命中率
            self.state["context"]["buffer_pool_hit_rate"] = hit_rate

            if hit_rate < 90:
                return f"Buffer Pool 命中率低：{hit_rate}%"
            elif hit_rate < 95:
                return f"Buffer Pool 命中率偏低：{hit_rate}%"
            else:
                return f"Buffer Pool 命中率正常：{hit_rate}%"

        return f"Buffer Pool 数据：{output}"

    def _analyze_root_cause(self, output: Any) -> str:
        """分析根因分析结果"""
        if isinstance(output, dict):
            root_cause = output.get("root_cause", "")
            confidence = output.get("confidence", "")

            if root_cause:
                self.state["root_cause"] = root_cause
                return f"根因：{root_cause}（置信度：{confidence}）"

            return "未能定位根因"

        return f"根因分析：{output}"

    def _analyze_recommendations(self, output: Any) -> str:
        """分析建议"""
        if isinstance(output, list):
            if not output:
                return "无优化建议"

            return f"生成 {len(output)} 条优化建议"

        return f"建议数据：{output}"

    def _default_analyzer(self, output: Any) -> str:
        """默认分析器"""
        return f"步骤输出：{str(output)[:100]}"

    def _generate_recommendations(self) -> list:
        """生成优化建议"""
        recommendations = []
        context = self.state["context"]
        root_cause = self.state.get("root_cause", "")

        # 根据根因生成针对性建议
        if "业务突增" in root_cause:
            recommendations.append("评估业务增长趋势，考虑扩容或读写分离")
            recommendations.append("检查是否有不必要的全表扫描查询")
            recommendations.append("优化连接池配置，限制最大连接数")

        elif "SQL" in root_cause or "慢查询" in root_cause:
            recommendations.append("优化慢 SQL 执行计划")
            recommendations.append("添加必要的索引")
            recommendations.append("避免全表扫描和大结果集")

        elif "锁等待" in root_cause:
            recommendations.append("排查锁冲突的业务逻辑")
            recommendations.append("优化事务设计，减少锁持有时间")
            recommendations.append("考虑使用乐观锁或减少锁粒度")

        elif "Buffer Pool" in root_cause:
            recommendations.append("增加 Buffer Pool 大小")
            recommendations.append("优化热点数据访问模式")
            recommendations.append("检查是否有大量冷数据读取")

        else:
            recommendations.append("持续监控 CPU 使用率")
            recommendations.append("定期检查慢 SQL 和 Profiling 数据")

        # 通用建议
        recommendations.append("建立性能基线，定期进行性能巡检")

        return recommendations