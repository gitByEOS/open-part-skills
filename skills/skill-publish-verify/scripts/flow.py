"""skill-publish-verify flow:隔离 → 取包 → 装依赖 → 使用 skill → 校验产物 → 写报告。

线性链,两个 TO_AGENT 断点:agent_run(agent 以新用户身份使用 skill)、
agent_report(agent 写可用性报告)。前 3 节点纯脚本准备隔离环境,verify_artifact
收集事实不判定,判断交给 agent_report 与用户。
"""

from esflow import flow, edge


@flow(id="skill-publish-verify", title="发布前黑盒验证")
class SkillPublishVerifyFlow:
    nodes = ["isolate_env", "copy_skill", "install_deps", "preflight_target",
             "agent_run", "verify_artifact", "agent_report"]
    edges = [
        edge("isolate_env", "copy_skill"),
        edge("copy_skill", "install_deps"),
        edge("install_deps", "preflight_target"),
        edge("preflight_target", "agent_run"),
        edge("agent_run", "verify_artifact"),
        edge("verify_artifact", "agent_report"),
    ]
