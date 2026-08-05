from __future__ import annotations

import fnmatch
import hashlib
import json
import os
import re
import shlex
import subprocess
import tempfile
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Iterable

import project_guardian_inventory as inventory


SCHEMA_VERSION = 6
WORK_ITEM_KINDS = {"question", "bug", "feature", "refactor", "architecture", "maintenance"}
REQUIREMENT_PROFILES = {"product", "internal", "defect"}
CONTRACT_PHASES = {"discovery", "solution_design", "design_review", "ready"}
DECISION_SIGNALS = {
    "user_visible_behavior",
    "scope_or_priority",
    "business_rule",
    "data_or_privacy",
    "external_contract",
    "commercial_tradeoff",
    "irreversible_or_costly",
    "requirements_conflict",
    "low_confidence",
}
CONTRACT_UPDATE_FIELDS = {
    "problem_statement",
    "goal",
    "stakeholders",
    "user_scenarios",
    "current_state",
    "functional_requirements",
    "quality_requirements",
    "constraints",
    "preferences",
    "assumptions",
    "acceptance_criteria",
    "non_goals",
    "protected_behaviors",
}
CONTRACT_LIST_FIELDS = CONTRACT_UPDATE_FIELDS - {"problem_statement", "goal", "current_state"}
REQUIRED_CONTRACT_FIELDS = {
    "product": (
        "problem_statement",
        "goal",
        "stakeholders",
        "user_scenarios",
        "current_state",
        "functional_requirements",
        "constraints",
        "acceptance_criteria",
        "non_goals",
        "protected_behaviors",
    ),
    "internal": (
        "goal",
        "current_state",
        "functional_requirements",
        "constraints",
        "acceptance_criteria",
        "non_goals",
        "protected_behaviors",
    ),
    "defect": (
        "problem_statement",
        "goal",
        "user_scenarios",
        "current_state",
        "acceptance_criteria",
        "non_goals",
        "protected_behaviors",
    ),
}
EVIDENCE_KINDS = {
    "automated_guard",
    "baseline",
    "target",
    "related",
    "full",
    "independent_review",
    "integration",
    "test_integrity_review",
    "architecture",
}
ACTIVE_STATUSES = {
    "discovering_requirements",
    "needs_user_decision",
    "designing_solution",
    "reviewing_design",
    "defined",
    "diagnosing",
    "scoped",
    "implementing",
    "verifying",
    "architecture_review",
    "ready_for_user_confirmation",
    "blocked",
}
READY_ONBOARDING_STATUSES = {"ready", "ready_with_warnings"}
MODEL_ORCHESTRATION_PROFILE = "adaptive-risk-v2"
PREVIOUS_ADAPTIVE_ORCHESTRATION_PROFILE = "adaptive-risk-v1"
ADAPTIVE_ORCHESTRATION_PROFILES = {
    PREVIOUS_ADAPTIVE_ORCHESTRATION_PROFILE,
    MODEL_ORCHESTRATION_PROFILE,
}
LEGACY_FIXED_ORCHESTRATION_PROFILE = "sol-luna-sol"
ORCHESTRATION_STAGES = {"planning", "execution", "review", "major_fix", "final_review"}
ORCHESTRATION_STATUSES = {"created", "running", "completed", "blocked", "failed"}
RISK_LEVELS = {"low", "standard", "high"}
RISK_SIGNALS = {
    "new_project",
    "architecture_change",
    "core_algorithm",
    "security_or_authorization",
    "data_integrity_or_migration",
    "financial_or_business_critical",
    "concurrency_or_resource",
    "public_api_or_protocol",
    "commercial_release",
    "cross_module_change",
    "test_integrity_change",
    "repeated_failure",
    "product_quality_stalled",
    "scope_drift",
    "major_review_finding",
    "localized_change",
    "routine_maintenance",
    "test_or_docs_only",
    "single_module_change",
    "legacy_high_assurance",
}
HIGH_RISK_SIGNALS = {
    "new_project",
    "architecture_change",
    "core_algorithm",
    "security_or_authorization",
    "data_integrity_or_migration",
    "financial_or_business_critical",
    "concurrency_or_resource",
    "public_api_or_protocol",
    "commercial_release",
    "cross_module_change",
    "repeated_failure",
    "product_quality_stalled",
    "scope_drift",
    "major_review_finding",
    "legacy_high_assurance",
}
LOW_RISK_SIGNALS = {"localized_change", "routine_maintenance", "test_or_docs_only", "single_module_change"}
JUDGMENT_EXECUTION_SIGNALS = {
    "new_project",
    "architecture_change",
    "data_integrity_or_migration",
    "public_api_or_protocol",
    "cross_module_change",
    "repeated_failure",
    "scope_drift",
}
PREVIOUS_RISK_ROUTE_MODELS = {
    "low": {
        "planning": ("gpt-5.6-terra", "medium"),
        "execution": ("gpt-5.6-luna", "high"),
        "review": ("gpt-5.6-terra", "medium"),
    },
    "standard": {
        "planning": ("gpt-5.6-terra", "high"),
        "execution": ("gpt-5.6-luna", "xhigh"),
        "review": ("gpt-5.6-terra", "high"),
    },
    "high": {
        "planning": ("gpt-5.6-sol", "xhigh"),
        "execution_focused": ("gpt-5.6-luna", "xhigh"),
        "execution_judgment": ("gpt-5.6-terra", "xhigh"),
        "review": ("gpt-5.6-sol", "xhigh"),
    },
}
RISK_ROUTE_MODELS = {
    "low": {
        "planning": ("gpt-5.6-terra", "medium"),
        "execution": ("gpt-5.6-luna", "max"),
        "review": ("gpt-5.6-terra", "medium"),
    },
    "standard": {
        "planning": ("gpt-5.6-terra", "high"),
        "execution": ("gpt-5.6-luna", "max"),
        "review": ("gpt-5.6-terra", "high"),
    },
    "high": {
        "planning": ("gpt-5.6-sol", "max"),
        "execution_focused": ("gpt-5.6-luna", "max"),
        "execution_judgment": ("gpt-5.6-terra", "xhigh"),
        "review": ("gpt-5.6-sol", "xhigh"),
    },
}
ORCHESTRATION_OUTCOMES = {
    "planning": {"ready", "needs_clarification", "blocked"},
    "execution": {"implemented", "failed", "blocked"},
    "review": {"passed", "minor_findings", "major_bug", "blocked"},
    "major_fix": {"fixed", "failed", "blocked"},
    "final_review": {"passed", "findings", "blocked"},
}
RISK_LEVEL_LABELS = {
    "low": "低风险",
    "standard": "标准风险",
    "high": "高风险",
}
MODEL_LABELS = {
    "gpt-5.6-sol": "GPT-5.6 Sol",
    "gpt-5.6-terra": "GPT-5.6 Terra",
    "gpt-5.6-luna": "GPT-5.6 Luna",
}
STAGE_ROLE_LABELS = {
    "planning": "规划",
    "execution": "执行",
    "review": "独立审查",
    "major_fix": "修复重大 Bug",
    "final_review": "最终复审",
}

AUTOMATED_GUARD_SENSITIVE_PATHS = (
    "**/migrations/**",
    "**/migration/**",
    "**/schema/**",
    "**/schemas/**",
    "**/protocol/**",
    "**/protocols/**",
    "**/auth/**",
    "**/security/**",
    "**/package.json",
    "**/package-lock.json",
    "**/pnpm-lock.yaml",
    "**/yarn.lock",
    "**/*.csproj",
    "**/*.sln",
)

ONBOARDING_LABELS = {
    "not_scanned": "尚未扫描",
    "needs_base_selection": "需判断真实代码基线",
    "needs_test_validation": "需验证测试基线",
    "blocked": "项目接入被阻塞",
    "ready": "可以开始开发",
    "ready_with_warnings": "可以开发，但有基线警告",
}

WORK_ITEM_STATUS_LABELS = {
    "discovering_requirements": "正在问清需求",
    "needs_user_decision": "需要你决定",
    "designing_solution": "正在比较方案",
    "reviewing_design": "正在审查需求文档",
    "defined": "需求已登记",
    "diagnosing": "正在找原因",
    "scoped": "范围已锁定",
    "implementing": "正在开发",
    "verifying": "正在验证",
    "architecture_review": "正在检查架构",
    "ready_for_user_confirmation": "等待你确认合并",
    "blocked": "任务被阻塞",
    "completed": "已完成",
}

CONTRACT_PHASE_LABELS = {
    "discovery": "需求访谈",
    "solution_design": "方案设计",
    "design_review": "文档审查",
    "ready": "可执行合同",
}


class GuardianError(RuntimeError):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _clean_text_list(values: Iterable[Any] | None) -> list[str]:
    return list(dict.fromkeys(str(value).strip() for value in (values or []) if str(value).strip()))


def _requirement_profile_for_kind(kind: str) -> str:
    if kind == "bug":
        return "defect"
    if kind in {"refactor", "maintenance"}:
        return "internal"
    return "product"


def _empty_design_contract(original_request: str, profile: str) -> dict[str, Any]:
    return {
        "original_request": original_request.strip(),
        "discovery_mode": "adaptive",
        "profile": profile,
        "phase": "discovery",
        "revision": 1,
        "problem_statement": "",
        "goal": "",
        "stakeholders": [],
        "user_scenarios": [],
        "current_state": "",
        "functional_requirements": [],
        "quality_requirements": [],
        "constraints": [],
        "preferences": [],
        "assumptions": [],
        "acceptance_criteria": [],
        "non_goals": [],
        "protected_behaviors": [],
        "clarified_summary": None,
        "open_question": None,
        "question_log": [],
        "approaches": [],
        "recommendation": None,
        "selected_approach": None,
        "open_decision": None,
        "decision_log": [],
        "revision_history": [],
        "review": None,
        "updated_at": utc_now(),
    }


def _upgrade_contract(contract: dict[str, Any], kind: str) -> bool:
    changed = False
    defaults: dict[str, Any] = {
        "discovery_mode": "legacy",
        "profile": _requirement_profile_for_kind(kind),
        "phase": "ready",
        "revision": 1,
        "problem_statement": "",
        "stakeholders": [],
        "user_scenarios": [],
        "current_state": "",
        "functional_requirements": [],
        "quality_requirements": [],
        "constraints": [],
        "preferences": [],
        "assumptions": [],
        "clarified_summary": contract.get("goal"),
        "open_question": None,
        "question_log": [],
        "approaches": [],
        "recommendation": None,
        "selected_approach": None,
        "open_decision": None,
        "decision_log": [],
        "revision_history": [],
        "review": {"outcome": "legacy_ready", "summary": "升级前已定义的执行合同"},
        "updated_at": utc_now(),
    }
    for key, value in defaults.items():
        if key not in contract:
            contract[key] = value
            changed = True
    return changed


def _contract_missing_dimensions(contract: dict[str, Any]) -> list[str]:
    if contract.get("discovery_mode") != "adaptive":
        return []
    profile = contract.get("profile")
    required = REQUIRED_CONTRACT_FIELDS.get(profile, ())
    return [field for field in required if not contract.get(field)]


def _contract_ready(item: dict[str, Any]) -> bool:
    contract = item.get("contract") or {}
    if contract.get("discovery_mode") != "adaptive":
        return bool(contract.get("original_request") and contract.get("goal"))
    return (
        contract.get("phase") == "ready"
        and not _contract_missing_dimensions(contract)
        and bool(contract.get("selected_approach"))
        and (contract.get("review") or {}).get("outcome") == "passed"
    )


def _contract_phase_status(phase: str) -> str:
    return {
        "discovery": "discovering_requirements",
        "solution_design": "designing_solution",
        "design_review": "reviewing_design",
        "ready": "defined",
    }.get(phase, "defined")


def _run_matches_contract_revision(item: dict[str, Any], run: dict[str, Any]) -> bool:
    contract = item.get("contract") or {}
    if contract.get("discovery_mode") != "adaptive":
        return True
    return run.get("contract_revision") == contract.get("revision")


def _touch_contract(contract: dict[str, Any]) -> None:
    contract["revision"] = int(contract.get("revision", 0)) + 1
    contract["updated_at"] = utc_now()


def _design_contract_view(item: dict[str, Any], include_markdown: bool = False) -> dict[str, Any]:
    contract = item.get("contract") or {}
    selected = contract.get("selected_approach") or {}
    view = {
        "item_id": item.get("id"),
        "title": item.get("title"),
        "status": item.get("status"),
        "status_label": WORK_ITEM_STATUS_LABELS.get(item.get("status"), item.get("status")),
        "discovery_mode": contract.get("discovery_mode", "legacy"),
        "profile": contract.get("profile"),
        "phase": contract.get("phase", "ready"),
        "phase_label": CONTRACT_PHASE_LABELS.get(contract.get("phase", "ready"), contract.get("phase")),
        "revision": contract.get("revision", 1),
        "requirements_complete": not _contract_missing_dimensions(contract),
        "missing_dimensions": _contract_missing_dimensions(contract),
        "open_question": contract.get("open_question"),
        "open_decision": contract.get("open_decision"),
        "recommendation": contract.get("recommendation"),
        "selected_approach": selected,
        "review": contract.get("review"),
        "contract": contract,
        "artifact_uri": f"guardian://work-items/{item.get('id')}/design-contract",
    }
    if include_markdown:
        view["markdown"] = _render_design_contract_markdown(item)
    return view


def _markdown_list(values: Iterable[str]) -> str:
    cleaned = _clean_text_list(values)
    return "\n".join(f"- {value}" for value in cleaned) if cleaned else "- 暂无"


def _render_design_contract_markdown(item: dict[str, Any]) -> str:
    contract = item.get("contract") or {}
    approaches = contract.get("approaches") or []
    approach_text = []
    for approach in approaches:
        approach_text.extend(
            [
                f"### {approach.get('name', approach.get('id', '方案'))}",
                str(approach.get("summary") or ""),
                f"- 需求匹配：{approach.get('fit_score', '未评分')}/10",
                f"- 工作量：{approach.get('effort', '未知')}；风险：{approach.get('risk', '未知')}",
                f"- 优点：{'；'.join(approach.get('pros') or []) or '暂无'}",
                f"- 缺点：{'；'.join(approach.get('cons') or []) or '暂无'}",
            ]
        )
    selected = contract.get("selected_approach") or {}
    review = contract.get("review") or {}
    return "\n".join(
        [
            f"# 需求与设计合同：{item.get('title', '')}",
            "",
            f"状态：{CONTRACT_PHASE_LABELS.get(contract.get('phase', 'ready'), contract.get('phase', 'ready'))}",
            f"版本：{contract.get('revision', 1)}",
            "",
            "## 用户原始要求",
            str(contract.get("original_request") or ""),
            "",
            "## 问题与目标",
            str(contract.get("problem_statement") or "暂无单独的问题描述"),
            "",
            str(contract.get("goal") or "暂无明确目标"),
            "",
            "## 使用者与场景",
            _markdown_list(contract.get("stakeholders") or []),
            _markdown_list(contract.get("user_scenarios") or []),
            "",
            "## 已验证的当前状态",
            str(contract.get("current_state") or "暂无"),
            "",
            "## 功能要求",
            _markdown_list(contract.get("functional_requirements") or []),
            "",
            "## 质量与限制",
            _markdown_list(contract.get("quality_requirements") or []),
            _markdown_list(contract.get("constraints") or []),
            "",
            "## 验收标准",
            _markdown_list(contract.get("acceptance_criteria") or []),
            "",
            "## 非目标与受保护行为",
            _markdown_list(contract.get("non_goals") or []),
            _markdown_list(contract.get("protected_behaviors") or []),
            "",
            "## 比较过的方案",
            "\n".join(approach_text) if approach_text else "暂无",
            "",
            "## 推荐与最终方案",
            str((contract.get("recommendation") or {}).get("reason") or "暂无推荐"),
            str(selected.get("name") or selected.get("summary") or "尚未选择"),
            "",
            "## 文档审查",
            str(review.get("summary") or "尚未审查"),
        ]
    ).strip() + "\n"


def _empty_risk_assessment() -> dict[str, Any]:
    return {
        "assessed": False,
        "level": None,
        "signals": [],
        "summary": None,
        "execution_track": None,
        "source": "automatic",
        "assessed_at": None,
    }


def _derive_risk_route(kind: str, signals: Iterable[str]) -> tuple[str, str]:
    signal_set = set(signals)
    if kind == "architecture" or signal_set & HIGH_RISK_SIGNALS:
        level = "high"
    elif kind == "maintenance" and signal_set and signal_set <= LOW_RISK_SIGNALS:
        level = "low"
    else:
        level = "standard"
    execution_track = "judgment" if level == "high" and signal_set & JUDGMENT_EXECUTION_SIGNALS else "focused"
    return level, execution_track


def _orchestration_profile(item: dict[str, Any]) -> str:
    return (item.get("orchestration") or {}).get("profile") or MODEL_ORCHESTRATION_PROFILE


def _route_models(item: dict[str, Any]) -> dict[str, dict[str, tuple[str, str]]]:
    if _orchestration_profile(item) == PREVIOUS_ADAPTIVE_ORCHESTRATION_PROFILE:
        return PREVIOUS_RISK_ROUTE_MODELS
    return RISK_ROUTE_MODELS


def _review_mode(item: dict[str, Any]) -> str:
    assessment = (item.get("orchestration") or {}).get("risk_assessment") or {}
    if _orchestration_profile(item) == MODEL_ORCHESTRATION_PROFILE and assessment.get("level") == "low":
        return "automated_guard"
    if assessment.get("level") == "standard":
        return "focused"
    return "full"


def _major_stage_model(item: dict[str, Any], stage: str) -> tuple[str, str]:
    if stage == "major_fix" and _orchestration_profile(item) == MODEL_ORCHESTRATION_PROFILE:
        return "gpt-5.6-sol", "max"
    return "gpt-5.6-sol", "xhigh"


def _expected_stage_model(item: dict[str, Any], stage: str) -> tuple[str, str]:
    if stage in {"major_fix", "final_review"}:
        return _major_stage_model(item, stage)
    assessment = (item.get("orchestration") or {}).get("risk_assessment") or {}
    if not assessment.get("assessed") or assessment.get("level") not in RISK_LEVELS:
        raise GuardianError("Assess the work item's risk before recording model stages")
    level = assessment["level"]
    routes = _route_models(item)
    if stage == "execution" and level == "high":
        track = assessment.get("execution_track") or "focused"
        return routes[level][f"execution_{track}"]
    return routes[level][stage]


def _reasoning_effort_matches(run: dict[str, Any], expected_effort: str) -> bool:
    actual = run.get("reasoning_effort")
    if actual == expected_effort:
        return True
    return (
        expected_effort == "max"
        and actual == "xhigh"
        and bool(run.get("capability_fallback"))
        and bool(run.get("fallback_reason"))
    )


def _stage_label(item: dict[str, Any], stage: str) -> str:
    model, effort = _expected_stage_model(item, stage)
    return f"{MODEL_LABELS.get(model, model)} · {effort.capitalize()} {STAGE_ROLE_LABELS[stage]}"


def _run_stage_label(run: dict[str, Any]) -> str:
    model = MODEL_LABELS.get(run.get("model"), run.get("model", "未知模型"))
    actual = str(run.get("reasoning_effort") or "").capitalize()
    expected = str(run.get("expected_reasoning_effort") or "").capitalize()
    effort = f"{expected}→{actual} 能力回退" if run.get("capability_fallback") else actual
    role = STAGE_ROLE_LABELS.get(run.get("stage"), run.get("stage", "当前阶段"))
    return f"{model} · {effort} {role}".replace(" ·  ", " ")


def _risk_route_view(item: dict[str, Any]) -> dict[str, Any]:
    assessment = (item.get("orchestration") or {}).get("risk_assessment") or _empty_risk_assessment()
    if not assessment.get("assessed"):
        return {
            "assessed": False,
            "level": None,
            "level_label": "待自动判断",
            "signals": [],
            "summary": None,
            "execution_track": None,
            "stages": [],
        }
    stages = []
    for stage in ("planning", "execution"):
        model, effort = _expected_stage_model(item, stage)
        stages.append(
            {
                "stage": stage,
                "role": STAGE_ROLE_LABELS[stage],
                "model": model,
                "model_label": MODEL_LABELS.get(model, model),
                "reasoning_effort": effort,
                "label": _stage_label(item, stage),
                "fallback_reasoning_effort": "xhigh" if effort == "max" else None,
            }
        )
    review_mode = _review_mode(item)
    if review_mode == "automated_guard":
        stages.append(
            {
                "stage": "automated_guard",
                "role": "自动门禁",
                "model": None,
                "model_label": None,
                "reasoning_effort": None,
                "label": "自动范围、测试完整性与漂移门禁",
                "fallback_review": _stage_label(item, "review"),
            }
        )
    else:
        model, effort = _expected_stage_model(item, "review")
        stages.append(
            {
                "stage": "review",
                "role": STAGE_ROLE_LABELS["review"],
                "model": model,
                "model_label": MODEL_LABELS.get(model, model),
                "reasoning_effort": effort,
                "label": _stage_label(item, "review"),
                "review_mode": review_mode,
            }
        )
    return {
        "assessed": True,
        "level": assessment["level"],
        "level_label": RISK_LEVEL_LABELS[assessment["level"]],
        "signals": list(assessment.get("signals", [])),
        "summary": assessment.get("summary"),
        "execution_track": assessment.get("execution_track"),
        "source": assessment.get("source", "automatic"),
        "assessed_at": assessment.get("assessed_at"),
        "profile": _orchestration_profile(item),
        "review_mode": review_mode,
        "stages": stages,
        "major_bug_route": [
            {
                "stage": "major_fix",
                "model": "gpt-5.6-sol",
                "reasoning_effort": _major_stage_model(item, "major_fix")[1],
                "label": _stage_label(item, "major_fix"),
            },
            {
                "stage": "final_review",
                "model": "gpt-5.6-sol",
                "reasoning_effort": "xhigh",
                "label": "GPT-5.6 Sol · Xhigh 最终复审",
            },
        ],
    }


def data_root() -> Path:
    explicit = os.environ.get("PROJECT_GUARDIAN_DATA") or os.environ.get("PLUGIN_DATA")
    if explicit:
        root = Path(explicit)
    elif os.name == "nt" and os.environ.get("LOCALAPPDATA"):
        root = Path(os.environ["LOCALAPPDATA"]) / "ProjectGuardian"
    else:
        root = Path.home() / ".local" / "share" / "project-guardian"
    root.mkdir(parents=True, exist_ok=True)
    (root / "projects").mkdir(exist_ok=True)
    (root / "worktrees").mkdir(exist_ok=True)
    return root


def normalize_path(value: str | os.PathLike[str]) -> str:
    return str(Path(value).expanduser().resolve(strict=False))


def _path_key(value: str | os.PathLike[str]) -> str:
    return os.path.normcase(normalize_path(value))


def _is_within(child: str | os.PathLike[str], parent: str | os.PathLike[str]) -> bool:
    child_key = Path(_path_key(child))
    parent_key = Path(_path_key(parent))
    try:
        child_key.relative_to(parent_key)
        return True
    except ValueError:
        return False


def project_id(root: str | os.PathLike[str]) -> str:
    return hashlib.sha256(_path_key(root).encode("utf-8")).hexdigest()[:16]


def _project_file(root: str | os.PathLike[str]) -> Path:
    return data_root() / "projects" / f"{project_id(root)}.json"


@contextmanager
def _file_lock(target: Path, timeout: float = 8.0):
    lock = target.with_suffix(target.suffix + ".lock")
    deadline = time.monotonic() + timeout
    fd: int | None = None
    while fd is None:
        try:
            fd = os.open(str(lock), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, f"{os.getpid()} {time.time()}".encode("ascii"))
        except FileExistsError:
            try:
                if time.time() - lock.stat().st_mtime > 60:
                    lock.unlink(missing_ok=True)
                    continue
            except OSError:
                pass
            if time.monotonic() >= deadline:
                raise GuardianError(f"Timed out waiting for state lock: {lock}")
            time.sleep(0.05)
    try:
        yield
    finally:
        if fd is not None:
            os.close(fd)
        lock.unlink(missing_ok=True)


def _read_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise GuardianError(f"Project is not initialized: {path.stem}") from exc
    except json.JSONDecodeError as exc:
        raise GuardianError(f"Project state is invalid JSON: {path}") from exc


def _empty_onboarding() -> dict[str, Any]:
    return {
        "status": "not_scanned",
        "can_start_work": False,
        "scanned_at": None,
        "canonical_base": None,
        "base_recommendation": None,
        "blockers": ["Project inventory has not been scanned"],
        "warnings": [],
        "test_validation": [],
    }


def _upgrade_state(state: dict[str, Any]) -> bool:
    changed = False
    if int(state.get("schema_version", 1)) < SCHEMA_VERSION:
        state["schema_version"] = SCHEMA_VERSION
        changed = True
    settings = state.setdefault("settings", {})
    if "worktree_owner" not in settings:
        settings["worktree_owner"] = "codex"
        changed = True
    if settings.get("model_orchestration_profile") in {
        LEGACY_FIXED_ORCHESTRATION_PROFILE,
        PREVIOUS_ADAPTIVE_ORCHESTRATION_PROFILE,
    }:
        settings["model_orchestration_profile"] = MODEL_ORCHESTRATION_PROFILE
        changed = True
    elif "model_orchestration_profile" not in settings:
        settings["model_orchestration_profile"] = MODEL_ORCHESTRATION_PROFILE
        changed = True
    git = state.setdefault("git", {})
    if "common_dir" not in git:
        try:
            git["common_dir"] = inventory.git_common_dir(state["root"])
        except (inventory.InventoryError, OSError, KeyError):
            git["common_dir"] = None
        changed = True
    if "onboarding" not in state:
        state["onboarding"] = _empty_onboarding()
        changed = True
    if "inventory" not in state:
        state["inventory"] = {"branches": [], "worktrees": [], "scanned_at": None}
        changed = True
    architecture = state.setdefault("architecture", {})
    for key, default in (("module_notes", []), ("protected_paths", []), ("graph", None)):
        if key not in architecture:
            architecture[key] = default
            changed = True
    for item in state.setdefault("work_items", []):
        contract = item.setdefault("contract", {})
        if _upgrade_contract(contract, item.get("kind", "feature")):
            changed = True
        if "task" not in item:
            item["task"] = None
            changed = True
        if "scope_conflicts" not in item:
            item["scope_conflicts"] = []
            changed = True
        if "depends_on" not in item:
            item["depends_on"] = []
            changed = True
        if "orchestration" not in item:
            # Existing work stays merge-compatible; newly created work uses the model pipeline.
            item["orchestration"] = {"profile": "legacy", "runs": []}
            changed = True
        orchestration = item["orchestration"]
        if orchestration.get("profile") == LEGACY_FIXED_ORCHESTRATION_PROFILE:
            # Preserve already-started work on its original route. New work uses v2.
            orchestration["profile"] = PREVIOUS_ADAPTIVE_ORCHESTRATION_PROFILE
            orchestration["risk_assessment"] = {
                "assessed": True,
                "level": "high",
                "signals": ["legacy_high_assurance"],
                "summary": "从旧版固定 Sol-Luna-Sol 流程迁移，保留原有高保障门槛",
                "execution_track": "focused",
                "source": "migration",
                "assessed_at": state.get("updated_at") or utc_now(),
            }
            changed = True
        elif orchestration.get("profile") in ADAPTIVE_ORCHESTRATION_PROFILES and "risk_assessment" not in orchestration:
            orchestration["risk_assessment"] = _empty_risk_assessment()
            changed = True
    return changed


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    value["updated_at"] = utc_now()
    handle, temporary = tempfile.mkstemp(prefix=path.name, suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2, sort_keys=False)
            stream.write("\n")
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _run_git(root: str | os.PathLike[str], args: Iterable[str], check: bool = True) -> str:
    command = ["git", *args]
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    completed = subprocess.run(
        command,
        cwd=normalize_path(root),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=flags,
        timeout=120,
    )
    if check and completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise GuardianError(f"Git command failed ({' '.join(command)}): {detail}")
    return completed.stdout.strip()


def _git_root(path: str | os.PathLike[str]) -> str:
    root = _run_git(path, ["rev-parse", "--show-toplevel"])
    if not root:
        raise GuardianError(f"Not a Git repository: {path}")
    return normalize_path(root)


def _default_branch(root: str) -> str:
    remote_head = _run_git(root, ["symbolic-ref", "--quiet", "--short", "refs/remotes/origin/HEAD"], check=False)
    if remote_head.startswith("origin/"):
        return remote_head.removeprefix("origin/")
    for candidate in ("main", "master"):
        if _run_git(root, ["show-ref", "--verify", "--quiet", f"refs/heads/{candidate}"], check=False) == "":
            probe = subprocess.run(
                ["git", "show-ref", "--verify", "--quiet", f"refs/heads/{candidate}"],
                cwd=root,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
            if probe.returncode == 0:
                return candidate
    branch = _run_git(root, ["branch", "--show-current"], check=False)
    return branch or "HEAD"


def _load_project(root: str | os.PathLike[str]) -> dict[str, Any]:
    repo = _git_root(root)
    state = _read_json(_project_file(repo))
    _upgrade_state(state)
    if _path_key(state["root"]) != _path_key(repo):
        raise GuardianError("Stored project root does not match the requested repository")
    return state


def _find_item(project: dict[str, Any], item_id: str) -> dict[str, Any]:
    for item in project.get("work_items", []):
        if item.get("id") == item_id:
            return item
    raise GuardianError(f"Unknown work item: {item_id}")


def _mutate_project(root: str | os.PathLike[str], mutator):
    repo = _git_root(root)
    path = _project_file(repo)
    with _file_lock(path):
        state = _read_json(path)
        _upgrade_state(state)
        result = mutator(state)
        _write_json(path, state)
        return result


def project_init(project_root: str, name: str | None = None, test_commands: list[str] | None = None) -> dict[str, Any]:
    root = _git_root(project_root)
    path = _project_file(root)
    if path.exists():
        with _file_lock(path):
            state = _read_json(path)
            changed = _upgrade_state(state)
            if name and state.get("name") != name:
                state["name"] = name
                changed = True
            if test_commands is not None and list(test_commands) != state.get("test_commands", []):
                state["test_commands"] = list(test_commands)
                state["onboarding"] = _empty_onboarding()
                changed = True
            if changed:
                _write_json(path, state)
            return state
    head = _run_git(root, ["rev-parse", "HEAD"])
    state = {
        "schema_version": SCHEMA_VERSION,
        "project_id": project_id(root),
        "name": name or Path(root).name,
        "root": root,
        "created_at": utc_now(),
        "updated_at": utc_now(),
        "git": {
            "default_branch": _default_branch(root),
            "initial_head": head,
            "common_dir": inventory.git_common_dir(root),
        },
        "test_commands": list(test_commands or []),
        "settings": {
            "worktree_owner": "codex",
            "model_orchestration_profile": MODEL_ORCHESTRATION_PROFILE,
        },
        "onboarding": _empty_onboarding(),
        "inventory": {"branches": [], "worktrees": [], "scanned_at": None},
        "architecture": {
            "module_notes": [],
            "protected_paths": [],
            "graph": None,
        },
        "work_items": [],
    }
    with _file_lock(path):
        if path.exists():
            return _read_json(path)
        _write_json(path, state)
    return state


def list_projects() -> list[dict[str, Any]]:
    projects = []
    for path in sorted((data_root() / "projects").glob("*.json")):
        try:
            state = _read_json(path)
            _upgrade_state(state)
            projects.append(
                {
                    "project_id": state["project_id"],
                    "name": state["name"],
                    "root": state["root"],
                    "updated_at": state["updated_at"],
                    "active_items": sum(1 for item in state.get("work_items", []) if item.get("status") in ACTIVE_STATUSES),
                    "onboarding_status": state.get("onboarding", {}).get("status", "not_scanned"),
                    "can_start_work": bool(state.get("onboarding", {}).get("can_start_work")),
                }
            )
        except GuardianError:
            continue
    return projects


def guardian_health(project_root: str | None = None) -> dict[str, Any]:
    result: dict[str, Any] = {
        "ok": True,
        "server_version": "0.3.0",
        "schema_version": SCHEMA_VERSION,
        "stdio_encoding": getattr(__import__("sys").stdout, "encoding", None),
        "data_root": str(data_root()),
    }
    if project_root:
        try:
            project = _load_project(project_root)
            result["project"] = {
                "id": project["project_id"],
                "name": project["name"],
                "onboarding_status": project["onboarding"]["status"],
                "can_start_work": project["onboarding"]["can_start_work"],
            }
        except GuardianError as exc:
            result["project_error"] = str(exc)
    return result


def _command_anchors(command: str) -> list[str]:
    try:
        tokens = shlex.split(command, posix=os.name != "nt")
    except ValueError:
        tokens = command.split()
    suffixes = (".sln", ".slnx", ".csproj", ".fsproj", ".vbproj", ".py", ".json", ".toml", ".yaml", ".yml")
    anchors = []
    for token in tokens:
        value = token.strip("\"'").replace("\\", "/").removeprefix("./")
        if value.lower().endswith(suffixes):
            anchors.append(value)
    return anchors


def _test_validation(commands: list[str], files: set[str], previous: list[dict[str, Any]], commit: str) -> list[dict[str, Any]]:
    by_command = {entry.get("command"): entry for entry in previous}
    values = []
    for command in commands:
        anchors = _command_anchors(command)
        missing = [anchor for anchor in anchors if anchor not in files]
        old = by_command.get(command) or {}
        same_commit = old.get("commit") == commit
        if missing:
            status = "missing_target"
        elif same_commit and old.get("status") in {"passed", "failed"}:
            status = old["status"]
        else:
            status = "not_run"
        values.append(
            {
                "command": command,
                "anchors": anchors,
                "missing_targets": missing,
                "status": status,
                "commit": commit if status in {"passed", "failed"} else None,
                "summary": old.get("summary") if same_commit else None,
                "recorded_at": old.get("recorded_at") if same_commit else None,
            }
        )
    return values


def _refresh_onboarding(project: dict[str, Any]) -> dict[str, Any]:
    onboarding = project.setdefault("onboarding", _empty_onboarding())
    blockers: list[str] = []
    warnings: list[str] = []
    canonical = onboarding.get("canonical_base")
    if not onboarding.get("scanned_at"):
        status = "not_scanned"
        blockers.append("Project inventory has not been scanned")
    elif not canonical:
        status = "needs_base_selection"
        blockers.append("The repository's canonical code line is ambiguous")
        graph = project.get("architecture", {}).get("graph") or {}
        if graph.get("provisional"):
            warnings.append(f"The code graph is a preview from recommended ref {graph.get('ref')}")
    else:
        validation = onboarding.get("test_validation", [])
        missing = [entry for entry in validation if entry.get("status") == "missing_target"]
        not_run = [entry for entry in validation if entry.get("status") == "not_run"]
        failed = [entry for entry in validation if entry.get("status") == "failed"]
        if missing:
            status = "blocked"
            blockers.append("One or more registered test commands target files absent from the canonical base")
        elif not_run:
            status = "needs_test_validation"
            blockers.append("Registered baseline commands have not been run against the canonical base")
        else:
            status = "ready"
            if failed:
                status = "ready_with_warnings"
                warnings.append("The baseline has recorded failures; preserve them as pre-existing evidence")
            if not project.get("test_commands"):
                status = "ready_with_warnings"
                warnings.append("No project-level test command is registered")

        ref = canonical.get("ref")
        dirty = [
            row
            for row in project.get("inventory", {}).get("worktrees", [])
            if row.get("branch") == ref and row.get("dirty")
        ]
        if dirty:
            warnings.append("The canonical branch has an existing dirty worktree; its uncommitted state is not in the canonical commit")
        graph = project.get("architecture", {}).get("graph") or {}
        if graph.get("truncated"):
            warnings.append("The code graph reached its configured scan limit")

    onboarding["status"] = status
    onboarding["can_start_work"] = status in READY_ONBOARDING_STATUSES
    onboarding["blockers"] = blockers
    onboarding["warnings"] = list(dict.fromkeys(warnings))
    return onboarding


def scan_project(project_root: str, canonical_ref: str | None = None) -> dict[str, Any]:
    project = _load_project(project_root)
    root = project["root"]
    try:
        scanned = inventory.scan_repository(root, project["git"]["default_branch"], requested_ref=canonical_ref)
    except inventory.InventoryError as exc:
        raise GuardianError(str(exc)) from exc
    now = utc_now()

    def mutate(state: dict[str, Any]):
        previous_validation = state.get("onboarding", {}).get("test_validation", [])
        state["inventory"] = {
            "branches": scanned["branches"],
            "worktrees": scanned["worktrees"],
            "scanned_at": now,
        }
        base = scanned["base"]
        selected = base.get("selected")
        state["onboarding"]["scanned_at"] = now
        state["onboarding"]["base_recommendation"] = base.get("recommended")
        state["onboarding"]["base_candidates"] = base.get("candidates", [])[:20]
        state["onboarding"]["base_selection_reason"] = base.get("reason")
        state["onboarding"]["canonical_base"] = (
            {
                "ref": selected["ref"],
                "commit": selected["commit"],
                "selected_at": now,
                "selected_by": "explicit" if canonical_ref else "automatic",
            }
            if selected
            else None
        )
        state["architecture"]["graph"] = scanned.get("graph")
        files = set(inventory.list_tree(root, selected["commit"])) if selected else set()
        state["onboarding"]["test_validation"] = (
            _test_validation(state.get("test_commands", []), files, previous_validation, selected["commit"])
            if selected
            else []
        )
        return {
            "project_id": state["project_id"],
            "onboarding": _refresh_onboarding(state),
            "inventory_summary": {
                "branches": len(scanned["branches"]),
                "worktrees": len(scanned["worktrees"]),
                "dirty_worktrees": sum(1 for row in scanned["worktrees"] if row.get("dirty")),
            },
            "graph_summary": _graph_summary(state["architecture"].get("graph")),
        }

    return _mutate_project(root, mutate)


def select_project_base(project_root: str, base_ref: str, reason: str) -> dict[str, Any]:
    if not base_ref.strip() or not reason.strip():
        raise GuardianError("base_ref and reason are required")
    result = scan_project(project_root, canonical_ref=base_ref.strip())

    def mutate(state: dict[str, Any]):
        canonical = state["onboarding"].get("canonical_base")
        if canonical:
            canonical["selection_reason"] = reason.strip()
            canonical["selected_by"] = "agent_or_user"
        return state["onboarding"]

    result["onboarding"] = _mutate_project(project_root, mutate)
    return result


def record_project_validation(
    project_root: str,
    command: str,
    success: bool,
    summary: str,
) -> dict[str, Any]:
    if not summary.strip():
        raise GuardianError("Validation summary is required")

    def mutate(state: dict[str, Any]):
        canonical = state["onboarding"].get("canonical_base")
        if not canonical:
            raise GuardianError("Select a canonical base before recording validation")
        if command not in state.get("test_commands", []):
            raise GuardianError("The command is not registered for this project")
        entries = state["onboarding"].setdefault("test_validation", [])
        entry = next((value for value in entries if value.get("command") == command), None)
        if entry is None:
            entry = {"command": command, "anchors": _command_anchors(command), "missing_targets": []}
            entries.append(entry)
        if entry.get("missing_targets"):
            raise GuardianError(
                "Cannot validate a command whose targets are absent from the canonical base: "
                + ", ".join(entry["missing_targets"])
            )
        entry.update(
            {
                "status": "passed" if success else "failed",
                "commit": canonical["commit"],
                "summary": summary.strip(),
                "recorded_at": utc_now(),
            }
        )
        return _refresh_onboarding(state)

    return _mutate_project(project_root, mutate)


def _graph_summary(graph: dict[str, Any] | None) -> dict[str, Any]:
    graph = graph or {}
    return {
        "commit": graph.get("commit"),
        "ref": graph.get("ref"),
        "provisional": bool(graph.get("provisional")),
        "files": graph.get("file_count", 0),
        "source_files": graph.get("source_file_count", 0),
        "modules": len(graph.get("modules", [])),
        "symbols": len(graph.get("symbols", [])),
        "truncated": bool(graph.get("truncated")),
    }


def _follow_up_action(
    action_id: str,
    label: str,
    prompt: str,
    description: str,
    *,
    requires_confirmation: bool = False,
    thread_id: str | None = None,
) -> dict[str, Any]:
    action = {
        "id": action_id,
        "kind": "open_task" if thread_id else "follow_up",
        "label": label,
        "description": description,
        "prompt": prompt,
        "requires_confirmation": requires_confirmation,
    }
    if thread_id:
        action["thread_id"] = thread_id
    return action


def _project_guidance(project: dict[str, Any]) -> dict[str, Any]:
    onboarding = _refresh_onboarding(project)
    status = onboarding["status"]
    root = project["root"]
    active_items = [item for item in project.get("work_items", []) if item.get("status") in ACTIVE_STATUSES]
    confirmations = [item for item in active_items if item.get("status") == "ready_for_user_confirmation"]

    if status == "not_scanned":
        summary = "Guardian 还没有读取这个项目的分支、工作树和代码结构。"
        primary = _follow_up_action(
            "scan-project",
            "扫描项目并生成项目图",
            f"使用 Project Guardian 扫描项目 {root}。扫描完成后立即重新打开项目图，并用小白能懂的话告诉我下一步只需要做什么。",
            "只读取 Git 和代码结构，不修改项目文件。",
        )
    elif status == "needs_base_selection":
        summary = "代码已经找到，但哪条分支代表当前真实可运行版本还不确定。"
        primary = _follow_up_action(
            "review-base",
            "让 Codex 判断真实基线",
            f"使用 Project Guardian 检查项目 {root} 的基线候选、分支关系和脏工作树，判断哪条代码线最能代表当前可运行版本；证据不足时只问我一个必要问题。完成后重新打开项目图。",
            "基线未确定前，Guardian 会阻止自动开发，避免在错误分支继续写代码。",
        )
    elif status == "needs_test_validation":
        commands = [entry.get("command") for entry in onboarding.get("test_validation", []) if entry.get("status") == "not_run"]
        command_text = "、".join(value for value in commands if value) or "已登记的基线测试"
        summary = f"真实代码基线已经选定，还需要确认它原本能否通过测试：{command_text}。"
        primary = _follow_up_action(
            "validate-baseline",
            "验证项目测试基线",
            f"使用 Project Guardian 在项目 {root} 的已选真实基线上运行并记录尚未验证的测试命令。不要修改代码；完成后重新打开项目图并告诉我结果和下一步。",
            "这一步只建立开发前的真实测试底账。",
        )
    elif status == "blocked":
        blocker = onboarding.get("blockers", ["项目接入条件未满足"])[0]
        summary = f"Guardian 已暂停开发，因为：{blocker}。"
        primary = _follow_up_action(
            "explain-onboarding-blocker",
            "查看阻塞原因和解决办法",
            f"使用 Project Guardian 检查项目 {root} 当前接入阻塞的证据，用小白能懂的话解释原因，并执行安全且不修改代码的恢复步骤；需要我决定时只问一个问题。完成后重新打开项目图。",
            "先恢复可信基线，再开始功能开发。",
        )
    elif confirmations:
        item = confirmations[0]
        summary = f"“{item['title']}”已经完成验证，正在等待你决定是否合并。"
        primary = _follow_up_action(
            "review-merge",
            "查看合并前证据",
            f"使用 Project Guardian 检查项目 {root} 的工作项 {item['id']}，用小白能懂的话列出完成内容、测试、偏离和风险；只有在我明确确认后才允许合并。",
            "该按钮只展示证据，不代表同意合并。",
            requires_confirmation=True,
            thread_id=(item.get("task") or {}).get("thread_id"),
        )
    elif active_items:
        item = active_items[0]
        contract = item.get("contract") or {}
        contract_view = _design_contract_view(item)
        item_status = WORK_ITEM_STATUS_LABELS.get(item.get("status"), item.get("status", "进行中"))
        orchestration = item.get("orchestration") or {}
        runs = orchestration.get("runs", [])
        assessment = orchestration.get("risk_assessment") or {}
        risk_text = RISK_LEVEL_LABELS.get(assessment.get("level"), "待自动判断风险")
        if runs:
            latest = runs[-1]
            latest_stage = _run_stage_label(latest)
        elif assessment.get("assessed"):
            latest_stage = _stage_label(item, "planning")
        else:
            latest_stage = "自动判断任务风险与模型路线"
        if item.get("status") == "needs_user_decision":
            decision = contract.get("open_question") or contract.get("open_decision") or {}
            prompt_text = decision.get("prompt") or "当前方案存在一个需要你决定的产品取舍。"
            summary = f"“{item['title']}”暂时没有开始写代码，因为需要你决定：{prompt_text}"
            primary = _follow_up_action(
                "answer-requirement-decision",
                "回答这个需求问题",
                f"继续项目 {root} 的工作项 {item['id']}。先读取 get_design_contract，只向我展示并解释当前唯一未决问题：{prompt_text}；收到我的回答后记录决定，再继续需求或方案流程。",
                "这个选择会影响产品行为、范围或长期方案，所以 Guardian 不会替你猜。",
                thread_id=(item.get("task") or {}).get("thread_id"),
            )
        elif item.get("status") == "discovering_requirements":
            missing = "、".join(contract_view.get("missing_dimensions") or []) or "尚未确认的关键需求"
            summary = f"“{item['title']}”正在问清真实需求，还没有创建开发工作树。当前需要补充：{missing}。"
            primary = _follow_up_action(
                "continue-requirement-discovery",
                "继续问清需求",
                f"使用 Project Guardian 继续项目 {root} 的工作项 {item['id']} 的需求访谈。先读取 get_design_contract 和已有项目事实，只问一个会改变方案、但当前仍缺失的问题；不要询问可从代码查到的技术细节。",
                "回答会自动进入同一份需求与设计合同。",
            )
        elif item.get("status") == "designing_solution":
            summary = f"“{item['title']}”的需求已经基本清楚，正在比较可行方案并选择当前条件下的最优解。"
            primary = _follow_up_action(
                "continue-solution-design",
                "生成并比较方案",
                f"使用 Project Guardian 继续项目 {root} 的工作项 {item['id']}。读取需求与设计合同，比较有实际差异的方案并给出最优推荐；只有存在重大取舍或低把握时才问我。",
                "最小版本、完整版本和分阶段方案都只是候选，不预设答案。",
            )
        elif item.get("status") == "reviewing_design":
            summary = f"“{item['title']}”已经选出方案，正在独立检查文档是否完整、一致、清晰、不过度扩张且可以实施。"
            primary = _follow_up_action(
                "review-design-contract",
                "审查需求与设计文档",
                f"使用 Project Guardian 审查项目 {root} 的工作项 {item['id']} 的设计合同。检查完整性、一致性、清晰度、范围和可行性；能从项目查明的问题自动修正文档，涉及用户意图时只问我一个问题。",
                "文档通过前不会建立执行工作树。",
            )
        else:
            summary = f"当前优先任务是“{item['title']}”，状态：{item_status}，{risk_text}，当前步骤：{latest_stage}。"
            primary = _follow_up_action(
                "continue-work-item",
                f"继续：{item['title']}",
                f"使用 Project Guardian 继续项目 {root} 的工作项 {item['id']}。先读取任务合同、当前证据和允许修改范围，只继续尚未完成的下一步；完成本轮后重新打开项目图。",
                "继续原任务和原工作树，避免重复开工。",
                thread_id=(item.get("task") or {}).get("thread_id"),
            )
    else:
        summary = "项目已经接入。现在直接告诉 Codex：要增加什么功能，或者哪里表现不对。"
        primary = _follow_up_action(
            "start-request",
            "开始一个新功能或问题",
            f"我要为项目 {root} 提出一个新项目、功能或问题。请使用 Project Guardian 自动识别类型：新项目或功能先建立需求访谈，问题先诊断；只问会改变方案的必要问题，需求清楚后再选择最优方案和工作树。",
            "Guardian 会先问清需求、建立一份设计合同，再自动拆分、定位代码和选择任务。",
        )

    secondary = [
        _follow_up_action(
            "show-branches",
            "查看各分支在做什么",
            f"打开项目 {root} 的 Guardian 项目图并切到“分支与工作树”，说明每条分支的内容、是否有未提交修改以及属于哪个 Codex 任务。",
            "适合看已有代码分散在哪里。",
        ),
        _follow_up_action(
            "show-modules",
            "查看功能、文件和函数",
            f"打开项目 {root} 的 Guardian 项目图并切到“功能模块”。等我选择模块后，显示相关文件、函数、参数、依赖和测试。",
            "适合在提出功能前了解代码位置。",
        ),
        _follow_up_action(
            "show-progress",
            "查看已完成和未完成",
            f"打开项目 {root} 的 Guardian 项目图并切到“开发任务”，按正在处理、等待确认、被阻塞和已完成说明当前进度。",
            "适合随时检查开发进度。",
        ),
    ]
    return {
        "status": status,
        "status_label": ONBOARDING_LABELS.get(status, status),
        "summary": summary,
        "primary_action": primary,
        "secondary_actions": secondary,
        "reopen": {
            "phrase": "打开项目图",
            "alternative_phrases": ["项目进度", "我下一步做什么", "查看分支和工作树"],
            "instruction": "Guardian 每轮会在回复下方自动显示迷你项目图；需要完整内容时输入“打开项目图”。它不是左侧固定页面。",
        },
    }


def create_work_item(
    project_root: str,
    title: str,
    original_request: str,
    goal: str,
    kind: str,
    acceptance_criteria: list[str],
    non_goals: list[str],
    protected_behaviors: list[str],
    parent_id: str | None = None,
) -> dict[str, Any]:
    if kind not in WORK_ITEM_KINDS:
        raise GuardianError(f"Unsupported work item kind: {kind}")
    if not title.strip() or not original_request.strip() or not goal.strip():
        raise GuardianError("title, original_request, and goal are required")

    def mutate(project: dict[str, Any]):
        onboarding = _refresh_onboarding(project)
        if kind != "question" and not onboarding["can_start_work"]:
            detail = "; ".join(onboarding["blockers"]) or onboarding["status"]
            raise GuardianError(f"Project onboarding is not ready for change work: {detail}")
        if parent_id:
            _find_item(project, parent_id)
        item = {
            "id": f"wi-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}",
            "title": title.strip(),
            "kind": kind,
            "parent_id": parent_id,
            "status": "diagnosing" if kind == "question" else "defined",
            "contract": {
                "original_request": original_request.strip(),
                "goal": goal.strip(),
                "acceptance_criteria": [value.strip() for value in acceptance_criteria if value.strip()],
                "non_goals": [value.strip() for value in non_goals if value.strip()],
                "protected_behaviors": [value.strip() for value in protected_behaviors if value.strip()],
            },
            "scope": {
                "allowed_changes": [],
                "impacted_nodes": [],
                "architecture_notes": [],
            },
            "base_commit": None,
            "branch": None,
            "worktree_path": None,
            "task": None,
            "orchestration": {
                "profile": "diagnosis-only" if kind == "question" else project.get("settings", {}).get(
                    "model_orchestration_profile", MODEL_ORCHESTRATION_PROFILE
                ),
                "risk_assessment": None if kind == "question" else _empty_risk_assessment(),
                "runs": [],
            },
            "last_scan": None,
            "evidence": [],
            "scope_conflicts": [],
            "depends_on": [],
            "consecutive_failures": 0,
            "architecture_review_required": kind == "architecture",
            "created_at": utc_now(),
            "updated_at": utc_now(),
        }
        _upgrade_contract(item["contract"], kind)
        project["work_items"].append(item)
        return item

    return _mutate_project(project_root, mutate)


def get_work_item(project_root: str, item_id: str) -> dict[str, Any]:
    return _find_item(_load_project(project_root), item_id)


def get_design_contract(project_root: str, item_id: str) -> dict[str, Any]:
    """Return the single human- and agent-facing requirement/design document."""
    return _design_contract_view(get_work_item(project_root, item_id), include_markdown=True)


def start_requirement_discovery(
    project_root: str,
    title: str,
    original_request: str,
    kind: str,
    profile: str,
    parent_id: str | None = None,
) -> dict[str, Any]:
    """Start read-only product discovery before planning, task creation, or worktree binding."""
    if kind not in WORK_ITEM_KINDS - {"question"}:
        raise GuardianError(f"Requirement discovery needs a change kind, got: {kind}")
    if profile not in REQUIREMENT_PROFILES:
        raise GuardianError(f"Unsupported requirement profile: {profile}")
    if not title.strip() or not original_request.strip():
        raise GuardianError("title and original_request are required")

    def mutate(project: dict[str, Any]):
        if parent_id:
            _find_item(project, parent_id)
        now = utc_now()
        item = {
            "id": f"wi-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}",
            "title": title.strip(),
            "kind": kind,
            "parent_id": parent_id,
            "status": "discovering_requirements",
            "contract": _empty_design_contract(original_request, profile),
            "scope": {"allowed_changes": [], "impacted_nodes": [], "architecture_notes": []},
            "base_commit": None,
            "branch": None,
            "worktree_path": None,
            "task": None,
            "orchestration": {
                "profile": project.get("settings", {}).get(
                    "model_orchestration_profile", MODEL_ORCHESTRATION_PROFILE
                ),
                "risk_assessment": _empty_risk_assessment(),
                "runs": [],
            },
            "last_scan": None,
            "evidence": [],
            "scope_conflicts": [],
            "depends_on": [],
            "consecutive_failures": 0,
            "architecture_review_required": kind == "architecture",
            "created_at": now,
            "updated_at": now,
        }
        project["work_items"].append(item)
        return _design_contract_view(item)

    return _mutate_project(project_root, mutate)


def update_requirement_discovery(
    project_root: str,
    item_id: str,
    updates: dict[str, Any] | None = None,
    resolved_question_id: str | None = None,
    answer: str | None = None,
    next_question: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Persist clarified facts and at most one next product question."""
    updates = updates or {}
    unsupported = sorted(set(updates) - CONTRACT_UPDATE_FIELDS)
    if unsupported:
        raise GuardianError(f"Unsupported contract updates: {', '.join(unsupported)}")

    def mutate(project: dict[str, Any]):
        item = _find_item(project, item_id)
        contract = item.get("contract") or {}
        if contract.get("discovery_mode") != "adaptive":
            raise GuardianError("This work item does not use adaptive requirement discovery")
        if contract.get("phase") not in {"discovery", "solution_design", "design_review"}:
            raise GuardianError("A ready design contract cannot be silently rewritten; start a new revision item")

        open_question = contract.get("open_question")
        if resolved_question_id:
            if not open_question or open_question.get("id") != resolved_question_id:
                raise GuardianError("The resolved question does not match the single open question")
            if not answer or not answer.strip():
                raise GuardianError("A user answer is required to resolve the open question")
            contract.setdefault("question_log", []).append(
                {
                    **open_question,
                    "answer": answer.strip(),
                    "answered_at": utc_now(),
                    "source": "user",
                }
            )
            contract["open_question"] = None
        elif answer is not None:
            raise GuardianError("answer requires resolved_question_id")

        for field, value in updates.items():
            if field in CONTRACT_LIST_FIELDS:
                if not isinstance(value, list):
                    raise GuardianError(f"Contract field {field} must be a list")
                contract[field] = _clean_text_list(value)
            else:
                if not isinstance(value, str):
                    raise GuardianError(f"Contract field {field} must be text")
                contract[field] = value.strip()

        if next_question:
            if contract.get("open_question"):
                raise GuardianError("Resolve the current requirement question before asking another")
            prompt = str(next_question.get("prompt") or "").strip()
            dimension = str(next_question.get("dimension") or "").strip()
            reason = str(next_question.get("reason") or "").strip()
            if not prompt or not dimension or not reason:
                raise GuardianError("A requirement question needs dimension, prompt, and reason")
            options = []
            recommended_count = 0
            for raw in next_question.get("options") or []:
                option_id = str(raw.get("id") or "").strip()
                label = str(raw.get("label") or "").strip()
                description = str(raw.get("description") or "").strip()
                recommended = bool(raw.get("recommended"))
                if not option_id or not label or not description:
                    raise GuardianError("Each requirement option needs id, label, and description")
                recommended_count += int(recommended)
                options.append(
                    {"id": option_id, "label": label, "description": description, "recommended": recommended}
                )
            if recommended_count > 1:
                raise GuardianError("Only one requirement option may be recommended")
            contract["open_question"] = {
                "id": f"rq-{uuid.uuid4().hex[:10]}",
                "dimension": dimension,
                "prompt": prompt,
                "reason": reason,
                "options": options,
                "asked_at": utc_now(),
            }
            item["status"] = "needs_user_decision"
        else:
            item["status"] = _contract_phase_status(contract.get("phase", "discovery"))

        _touch_contract(contract)
        item["updated_at"] = utc_now()
        return _design_contract_view(item)

    return _mutate_project(project_root, mutate)


def finalize_requirement_discovery(project_root: str, item_id: str, clarified_summary: str) -> dict[str, Any]:
    if not clarified_summary.strip():
        raise GuardianError("A clarified requirement summary is required")

    def mutate(project: dict[str, Any]):
        item = _find_item(project, item_id)
        contract = item.get("contract") or {}
        if contract.get("discovery_mode") != "adaptive" or contract.get("phase") != "discovery":
            raise GuardianError("The work item is not in requirement discovery")
        if contract.get("open_question"):
            raise GuardianError("Resolve the open requirement question before finalizing discovery")
        missing = _contract_missing_dimensions(contract)
        if missing:
            raise GuardianError("Requirement discovery is incomplete: " + ", ".join(missing))
        contract["clarified_summary"] = clarified_summary.strip()
        contract["phase"] = "solution_design"
        item["status"] = "designing_solution"
        _touch_contract(contract)
        item["updated_at"] = utc_now()
        return _design_contract_view(item)

    return _mutate_project(project_root, mutate)


def record_solution_design(
    project_root: str,
    item_id: str,
    complexity: str,
    approaches: list[dict[str, Any]],
    recommendation_id: str,
    recommendation_reason: str,
    confidence: float,
    decision_signals: list[str] | None = None,
    decision_question: str | None = None,
) -> dict[str, Any]:
    if complexity not in {"simple", "nontrivial"}:
        raise GuardianError("complexity must be simple or nontrivial")
    if not 0 <= confidence <= 1:
        raise GuardianError("confidence must be between 0 and 1")
    signals = sorted(set(_clean_text_list(decision_signals)))
    unsupported = sorted(set(signals) - DECISION_SIGNALS)
    if unsupported:
        raise GuardianError(f"Unsupported decision signals: {', '.join(unsupported)}")
    if confidence < 0.75 and "low_confidence" not in signals:
        signals.append("low_confidence")
        signals.sort()
    normalized = []
    seen: set[str] = set()
    for raw in approaches:
        approach_id = str(raw.get("id") or "").strip()
        name = str(raw.get("name") or "").strip()
        summary = str(raw.get("summary") or "").strip()
        if not approach_id or not name or not summary or approach_id in seen:
            raise GuardianError("Each solution approach needs a unique id, name, and summary")
        seen.add(approach_id)
        fit_score = int(raw.get("fit_score", -1))
        if not 0 <= fit_score <= 10:
            raise GuardianError("Each approach fit_score must be between 0 and 10")
        normalized.append(
            {
                "id": approach_id,
                "name": name,
                "summary": summary,
                "fit_score": fit_score,
                "effort": str(raw.get("effort") or "unknown").strip(),
                "risk": str(raw.get("risk") or "unknown").strip(),
                "pros": _clean_text_list(raw.get("pros")),
                "cons": _clean_text_list(raw.get("cons")),
                "reuses": _clean_text_list(raw.get("reuses")),
            }
        )
    if not normalized or (complexity == "nontrivial" and len(normalized) < 2):
        raise GuardianError("Nontrivial solution design requires at least two meaningfully different approaches")
    if recommendation_id not in seen or not recommendation_reason.strip():
        raise GuardianError("A valid recommendation and its requirement-based reason are required")

    def mutate(project: dict[str, Any]):
        item = _find_item(project, item_id)
        contract = item.get("contract") or {}
        if contract.get("discovery_mode") != "adaptive" or contract.get("phase") != "solution_design":
            raise GuardianError("Complete requirement discovery before recording solution design")
        if contract.get("open_question"):
            raise GuardianError("Resolve the open requirement question before comparing solutions")
        recommended = next(value for value in normalized if value["id"] == recommendation_id)
        contract["approaches"] = normalized
        contract["recommendation"] = {
            "approach_id": recommendation_id,
            "reason": recommendation_reason.strip(),
            "confidence": confidence,
            "decision_signals": signals,
        }
        if signals:
            if not decision_question or not decision_question.strip():
                raise GuardianError("A material trade-off requires one beginner-facing decision question")
            contract["selected_approach"] = None
            contract["open_decision"] = {
                "id": f"decision-{uuid.uuid4().hex[:10]}",
                "prompt": decision_question.strip(),
                "reason": recommendation_reason.strip(),
                "signals": signals,
                "recommended_option_id": recommendation_id,
                "options": [
                    {
                        "id": value["id"],
                        "label": value["name"],
                        "description": value["summary"],
                        "recommended": value["id"] == recommendation_id,
                    }
                    for value in normalized
                ],
                "asked_at": utc_now(),
            }
            item["status"] = "needs_user_decision"
        else:
            contract["selected_approach"] = recommended
            contract["open_decision"] = None
            contract.setdefault("decision_log", []).append(
                {
                    "id": f"decision-{uuid.uuid4().hex[:10]}",
                    "source": "guardian_recommendation",
                    "selected_option_id": recommendation_id,
                    "reason": recommendation_reason.strip(),
                    "confidence": confidence,
                    "decided_at": utc_now(),
                }
            )
            contract["phase"] = "design_review"
            item["status"] = "reviewing_design"
        _touch_contract(contract)
        item["updated_at"] = utc_now()
        return _design_contract_view(item)

    return _mutate_project(project_root, mutate)


def record_solution_decision(
    project_root: str,
    item_id: str,
    decision_id: str,
    selected_option_id: str,
    answer: str,
) -> dict[str, Any]:
    if not answer.strip():
        raise GuardianError("The user's decision answer is required")

    def mutate(project: dict[str, Any]):
        item = _find_item(project, item_id)
        contract = item.get("contract") or {}
        decision = contract.get("open_decision")
        if not decision or decision.get("id") != decision_id:
            raise GuardianError("The resolved decision does not match the open solution decision")
        approach = next(
            (value for value in contract.get("approaches", []) if value.get("id") == selected_option_id),
            None,
        )
        if approach is None:
            raise GuardianError("The selected option is not one of the proposed solution approaches")
        contract["selected_approach"] = approach
        contract.setdefault("decision_log", []).append(
            {
                **decision,
                "source": "user",
                "selected_option_id": selected_option_id,
                "answer": answer.strip(),
                "decided_at": utc_now(),
            }
        )
        contract["open_decision"] = None
        contract["phase"] = "design_review"
        item["status"] = "reviewing_design"
        _touch_contract(contract)
        item["updated_at"] = utc_now()
        return _design_contract_view(item)

    return _mutate_project(project_root, mutate)


def review_design_contract(
    project_root: str,
    item_id: str,
    reviewer_thread_id: str,
    scores: dict[str, Any],
    outcome: str,
    summary: str,
    findings: list[str] | None = None,
) -> dict[str, Any]:
    dimensions = {"completeness", "consistency", "clarity", "scope", "feasibility"}
    if set(scores) != dimensions:
        raise GuardianError("Design review scores must cover completeness, consistency, clarity, scope, and feasibility")
    normalized_scores = {key: int(value) for key, value in scores.items()}
    if any(value < 0 or value > 10 for value in normalized_scores.values()):
        raise GuardianError("Design review scores must be between 0 and 10")
    if outcome not in {"passed", "needs_revision"}:
        raise GuardianError("Design review outcome must be passed or needs_revision")
    if not reviewer_thread_id.strip() or not summary.strip():
        raise GuardianError("reviewer_thread_id and summary are required")
    if outcome == "passed" and min(normalized_scores.values()) < 7:
        raise GuardianError("A design contract cannot pass while a review dimension is below 7")

    def mutate(project: dict[str, Any]):
        item = _find_item(project, item_id)
        contract = item.get("contract") or {}
        if contract.get("discovery_mode") != "adaptive" or contract.get("phase") != "design_review":
            raise GuardianError("Select a solution approach before reviewing the design contract")
        planning_threads = {
            run.get("thread_id")
            for run in (item.get("orchestration") or {}).get("runs", [])
            if run.get("stage") == "planning"
        }
        if reviewer_thread_id.strip() in planning_threads:
            raise GuardianError("The design contract needs a cold reviewer task, not the planning task that authored it")
        if contract.get("open_question") or contract.get("open_decision"):
            raise GuardianError("Resolve open user decisions before completing design review")
        if not contract.get("selected_approach"):
            raise GuardianError("Design review requires a selected solution approach")
        missing = _contract_missing_dimensions(contract)
        if missing:
            raise GuardianError("Design contract is incomplete: " + ", ".join(missing))
        contract["review"] = {
            "outcome": outcome,
            "summary": summary.strip(),
            "scores": normalized_scores,
            "findings": _clean_text_list(findings),
            "reviewer_thread_id": reviewer_thread_id.strip(),
            "reviewed_at": utc_now(),
        }
        if outcome == "passed":
            contract["phase"] = "ready"
            item["status"] = "defined"
        else:
            contract["phase"] = "solution_design"
            item["status"] = "designing_solution"
        _touch_contract(contract)
        item["updated_at"] = utc_now()
        return _design_contract_view(item, include_markdown=True)

    return _mutate_project(project_root, mutate)


def reopen_design_contract(project_root: str, item_id: str, reason: str) -> dict[str, Any]:
    """Reopen a reviewed contract when implementation evidence invalidates the chosen design."""
    if not reason.strip():
        raise GuardianError("A concrete contract revision reason is required")

    def mutate(project: dict[str, Any]):
        item = _find_item(project, item_id)
        contract = item.get("contract") or {}
        if contract.get("discovery_mode") != "adaptive" or contract.get("phase") != "ready":
            raise GuardianError("Only a reviewed adaptive design contract can be reopened")
        contract.setdefault("revision_history", []).append(
            {
                "revision": contract.get("revision"),
                "reason": reason.strip(),
                "selected_approach_id": (contract.get("selected_approach") or {}).get("id"),
                "review_summary": (contract.get("review") or {}).get("summary"),
                "superseded_at": utc_now(),
            }
        )
        contract["phase"] = "solution_design"
        contract["review"] = None
        contract["open_question"] = None
        contract["open_decision"] = None
        contract["selected_approach"] = None
        item["status"] = "designing_solution"
        item["merge_readiness"] = None
        _touch_contract(contract)
        item["updated_at"] = utc_now()
        return _design_contract_view(item, include_markdown=True)

    return _mutate_project(project_root, mutate)


def assess_work_item_risk(
    project_root: str,
    item_id: str,
    signals: list[str],
    summary: str,
) -> dict[str, Any]:
    """Persist an automatic, evidence-based model route without asking the user to choose a model."""
    normalized_signals = sorted({value.strip() for value in signals if value.strip()})
    unsupported = sorted(set(normalized_signals) - RISK_SIGNALS)
    if unsupported:
        raise GuardianError(f"Unsupported risk signals: {', '.join(unsupported)}")
    if not summary.strip():
        raise GuardianError("Risk assessment summary is required")

    def mutate(project: dict[str, Any]):
        item = _find_item(project, item_id)
        if item.get("kind") == "question":
            raise GuardianError("Diagnosis-only work items do not use a model risk route")
        orchestration = item.setdefault("orchestration", {"profile": MODEL_ORCHESTRATION_PROFILE, "runs": []})
        if orchestration.get("profile") not in ADAPTIVE_ORCHESTRATION_PROFILES | {"legacy"}:
            raise GuardianError(f"Unsupported orchestration profile: {orchestration.get('profile')}")
        previous = orchestration.get("risk_assessment") or _empty_risk_assessment()
        runs = orchestration.get("runs", [])
        effective_signals = normalized_signals
        if runs and previous.get("assessed"):
            effective_signals = sorted(set(previous.get("signals", [])) | set(normalized_signals))
        level, execution_track = _derive_risk_route(item.get("kind", "feature"), effective_signals)
        ranks = {"low": 0, "standard": 1, "high": 2}
        if runs and previous.get("assessed") and ranks[level] < ranks[previous["level"]]:
            raise GuardianError("Risk cannot be downgraded after a model stage has started")
        now = utc_now()
        if orchestration.get("profile") == "legacy":
            orchestration["profile"] = MODEL_ORCHESTRATION_PROFILE
        orchestration["risk_assessment"] = {
            "assessed": True,
            "level": level,
            "signals": effective_signals,
            "summary": summary.strip(),
            "execution_track": execution_track,
            "source": "automatic",
            "assessed_at": now,
        }
        item["updated_at"] = now
        return {
            "item_id": item_id,
            "profile": orchestration["profile"],
            "route": _risk_route_view(item),
            "previous_level": previous.get("level") if previous.get("assessed") else None,
            "existing_runs_revalidated": bool(runs),
        }

    return _mutate_project(project_root, mutate)


def _safe_branch_part(kind: str, item_id: str) -> str:
    suffix = re.sub(r"[^a-z0-9-]+", "-", item_id.lower()).strip("-")[-24:]
    return f"pg/{kind}-{suffix}"


def bind_work_item(
    project_root: str,
    item_id: str,
    thread_id: str,
    worktree_path: str | None = None,
    host_id: str | None = None,
    task_title: str | None = None,
) -> dict[str, Any]:
    if not thread_id.strip():
        raise GuardianError("thread_id is required")
    project = _load_project(project_root)
    item = _find_item(project, item_id)
    if item["kind"] != "question" and not _contract_ready(item):
        raise GuardianError("Complete and review the requirement/design contract before binding an execution worktree")
    if (
        item["kind"] != "question"
        and (item.get("contract") or {}).get("discovery_mode") == "adaptive"
        and _orchestration_profile(item) in ADAPTIVE_ORCHESTRATION_PROFILES
    ):
        latest_plan = _latest_stage_run(item, {"planning"})
        if (
            not latest_plan
            or latest_plan.get("status") != "completed"
            or latest_plan.get("outcome") != "ready"
            or not _run_matches_current_route(item, latest_plan, "planning")
            or not _run_matches_contract_revision(item, latest_plan)
        ):
            raise GuardianError("Bind requires completed planning for the current design-contract revision and risk route")
    normalized_worktree = normalize_path(worktree_path) if worktree_path else None
    if item["kind"] != "question" and not normalized_worktree:
        raise GuardianError("Change items must bind to the Codex task's Git worktree")
    if normalized_worktree:
        if not inventory.same_repository(project["root"], normalized_worktree):
            raise GuardianError("The supplied worktree does not belong to this project")
        if item["kind"] != "question" and _path_key(normalized_worktree) == _path_key(project["root"]):
            raise GuardianError("Change items cannot bind to the registered local checkout")
        head = _run_git(normalized_worktree, ["rev-parse", "HEAD"])
        branch = _run_git(normalized_worktree, ["branch", "--show-current"], check=False) or None
    else:
        head = None
        branch = None

    def mutate(state: dict[str, Any]):
        mutable = _find_item(state, item_id)
        for other in state.get("work_items", []):
            if other["id"] == item_id or other.get("status") not in ACTIVE_STATUSES:
                continue
            other_task = other.get("task") or {}
            if other_task.get("thread_id") == thread_id:
                raise GuardianError(f"Codex task is already bound to work item {other['id']}")
            if normalized_worktree and other.get("worktree_path") and _path_key(other["worktree_path"]) == _path_key(normalized_worktree):
                raise GuardianError(f"Worktree is already bound to work item {other['id']}")
        mutable["task"] = {
            "thread_id": thread_id.strip(),
            "host_id": host_id.strip() if host_id else None,
            "title": task_title.strip() if task_title else None,
            "bound_at": utc_now(),
        }
        if normalized_worktree:
            mutable["worktree_path"] = normalized_worktree
            mutable["branch"] = branch
            mutable["base_commit"] = mutable.get("base_commit") or head
        mutable["updated_at"] = utc_now()
        return {
            "item_id": item_id,
            "task": mutable["task"],
            "worktree_path": mutable.get("worktree_path"),
            "branch": mutable.get("branch"),
            "base_commit": mutable.get("base_commit"),
        }

    return _mutate_project(project_root, mutate)


def _latest_stage_run(item: dict[str, Any], stages: set[str]) -> dict[str, Any] | None:
    matches = [
        value
        for value in (item.get("orchestration") or {}).get("runs", [])
        if value.get("stage") in stages
    ]
    return matches[-1] if matches else None


def _run_matches_current_route(item: dict[str, Any], run: dict[str, Any], stage: str) -> bool:
    expected_model, expected_effort = _expected_stage_model(item, stage)
    return run.get("model") == expected_model and _reasoning_effort_matches(run, expected_effort)


def record_task_stage(
    project_root: str,
    item_id: str,
    stage: str,
    thread_id: str,
    model: str,
    reasoning_effort: str,
    status: str,
    summary: str,
    outcome: str | None = None,
    artifact: str | None = None,
    host_id: str | None = None,
    fallback_reason: str | None = None,
) -> dict[str, Any]:
    if stage not in ORCHESTRATION_STAGES:
        raise GuardianError(f"Unsupported orchestration stage: {stage}")
    if status not in ORCHESTRATION_STATUSES:
        raise GuardianError(f"Unsupported orchestration status: {status}")
    if not thread_id.strip() or not summary.strip():
        raise GuardianError("thread_id and summary are required")
    if status == "completed":
        if outcome not in ORCHESTRATION_OUTCOMES[stage]:
            allowed = ", ".join(sorted(ORCHESTRATION_OUTCOMES[stage]))
            raise GuardianError(f"Completed stage {stage} requires one of these outcomes: {allowed}")
    elif outcome is not None:
        raise GuardianError("outcome is only accepted when status is completed")

    project = _load_project(project_root)
    item = _find_item(project, item_id)
    profile = (item.get("orchestration") or {}).get("profile")
    if profile == "diagnosis-only":
        raise GuardianError("Diagnosis-only work items do not use the implementation model pipeline")
    if profile == "legacy":
        raise GuardianError("Assess the work item's risk before starting the adaptive model pipeline")
    if profile not in ADAPTIVE_ORCHESTRATION_PROFILES:
        raise GuardianError(f"Unsupported orchestration profile: {profile}")
    expected_model, expected_effort = _expected_stage_model(item, stage)
    capability_fallback = (
        model == expected_model
        and expected_effort == "max"
        and reasoning_effort == "xhigh"
        and bool(fallback_reason and fallback_reason.strip())
    )
    if model != expected_model or (reasoning_effort != expected_effort and not capability_fallback):
        raise GuardianError(
            f"Stage {stage} requires {expected_model} with {expected_effort} reasoning for the current risk route; "
            "xhigh is accepted only as an explicit capability fallback from max"
        )
    owner_thread = (item.get("task") or {}).get("thread_id")
    latest_plan = _latest_stage_run(item, {"planning"})
    latest_execution = _latest_stage_run(item, {"execution"})
    if stage == "planning" and status == "completed" and outcome == "ready" and not _contract_ready(item):
        raise GuardianError("Planning cannot become ready until the requirement/design contract passes review")
    if stage == "execution":
        if not _contract_ready(item):
            raise GuardianError("Execution requires a reviewed requirement/design contract")
        if not owner_thread:
            raise GuardianError("Bind the execution task before recording its execution stage")
        if owner_thread != thread_id.strip():
            raise GuardianError("The execution stage must use the work item's owning Codex task")
        if (
            not latest_plan
            or latest_plan.get("status") != "completed"
            or latest_plan.get("outcome") != "ready"
            or not _run_matches_current_route(item, latest_plan, "planning")
            or not _run_matches_contract_revision(item, latest_plan)
        ):
            raise GuardianError("Execution requires a current-contract planning outcome of ready from the current risk route")
    if stage in {"review", "final_review"} and owner_thread == thread_id.strip():
        raise GuardianError("Independent review must run in a different Codex task from execution")
    if stage == "review":
        if (
            not latest_execution
            or latest_execution.get("status") != "completed"
            or latest_execution.get("outcome") != "implemented"
            or not _run_matches_current_route(item, latest_execution, "execution")
        ):
            raise GuardianError("Review requires a completed execution outcome of implemented from the current risk route")
    if stage == "major_fix":
        latest_review = _latest_stage_run(item, {"review", "final_review"})
        if not latest_review or latest_review.get("outcome") != "major_bug":
            raise GuardianError("A Sol major-fix stage requires a preceding review outcome of major_bug")
        if thread_id.strip() in {owner_thread, latest_review.get("thread_id")}:
            raise GuardianError("A Sol major-fix stage must use a separate Codex task from execution and review")
    if stage == "final_review":
        latest_fix = _latest_stage_run(item, {"major_fix"})
        if not latest_fix or latest_fix.get("status") != "completed" or latest_fix.get("outcome") != "fixed":
            raise GuardianError("Final review requires a completed Sol major-fix stage")
        if latest_fix.get("thread_id") == thread_id.strip():
            raise GuardianError("Final review must use a different Codex task from the Sol major fixer")

    fingerprint = None
    if status == "completed" and stage != "planning" and item.get("worktree_path") and item.get("base_commit"):
        fingerprint = worktree_fingerprint(item["worktree_path"], item["base_commit"])

    def mutate(state: dict[str, Any]):
        mutable = _find_item(state, item_id)
        orchestration = mutable.setdefault(
            "orchestration",
            {"profile": MODEL_ORCHESTRATION_PROFILE, "risk_assessment": _empty_risk_assessment(), "runs": []},
        )
        runs = orchestration.setdefault("runs", [])
        run = next(
            (
                value
                for value in runs
                if value.get("stage") == stage and value.get("thread_id") == thread_id.strip()
            ),
            None,
        )
        now = utc_now()
        if run is None:
            run = {
                "id": f"run-{uuid.uuid4().hex[:10]}",
                "stage": stage,
                "thread_id": thread_id.strip(),
                "created_at": now,
            }
            runs.append(run)
        run.update(
            {
                "host_id": host_id.strip() if host_id else None,
                "model": model,
                "reasoning_effort": reasoning_effort,
                "capability_fallback": capability_fallback,
                "fallback_reason": fallback_reason.strip() if fallback_reason else None,
                "expected_model": expected_model,
                "expected_reasoning_effort": expected_effort,
                "risk_level": (orchestration.get("risk_assessment") or {}).get("level"),
                "execution_track": (orchestration.get("risk_assessment") or {}).get("execution_track"),
                "status": status,
                "summary": summary.strip(),
                "outcome": outcome,
                "artifact": artifact.strip() if artifact else None,
                "contract_revision": (mutable.get("contract") or {}).get("revision"),
                "fingerprint": fingerprint,
                "updated_at": now,
            }
        )
        mutable["updated_at"] = now
        return orchestration

    return _mutate_project(project_root, mutate)


def prepare_worktree(
    project_root: str,
    item_id: str,
    base_ref: str | None = None,
    allow_guardian_create: bool = False,
) -> dict[str, Any]:
    project = _load_project(project_root)
    item = _find_item(project, item_id)
    if item["kind"] == "question":
        raise GuardianError("Diagnosis-only questions do not receive a worktree; create a change item after diagnosis")
    if item.get("worktree_path"):
        return {
            "item_id": item_id,
            "worktree_path": item["worktree_path"],
            "branch": item["branch"],
            "base_commit": item["base_commit"],
            "reused": True,
        }
    if project.get("settings", {}).get("worktree_owner", "codex") == "codex" and not allow_guardian_create:
        raise GuardianError(
            "Codex owns worktree creation for this project. Create or move the Codex task to a worktree, then call bind_work_item."
        )
    root = project["root"]
    canonical = project.get("onboarding", {}).get("canonical_base") or {}
    chosen_base = base_ref or canonical.get("commit")
    if not chosen_base:
        raise GuardianError("No canonical base is selected; complete project onboarding first")
    base_commit = _run_git(root, ["rev-parse", chosen_base])
    branch = _safe_branch_part(item["kind"], item_id)
    destination = data_root() / "worktrees" / project["project_id"] / item_id
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        raise GuardianError(f"Untracked worktree destination already exists: {destination}")
    branch_exists = subprocess.run(
        ["git", "show-ref", "--verify", "--quiet", f"refs/heads/{branch}"],
        cwd=root,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    ).returncode == 0
    if branch_exists:
        raise GuardianError(f"Guardian branch already exists but is not registered: {branch}")
    _run_git(root, ["worktree", "add", "-b", branch, str(destination), base_commit])

    def mutate(state: dict[str, Any]):
        mutable = _find_item(state, item_id)
        mutable["base_commit"] = base_commit
        mutable["branch"] = branch
        mutable["worktree_path"] = normalize_path(destination)
        mutable["status"] = "defined"
        mutable["updated_at"] = utc_now()
        return {
            "item_id": item_id,
            "worktree_path": mutable["worktree_path"],
            "branch": branch,
            "base_commit": base_commit,
            "reused": False,
        }

    return _mutate_project(root, mutate)


def _normalize_pattern(value: str) -> str:
    pattern = value.strip().replace("\\", "/")
    if not pattern or pattern.startswith("/") or re.match(r"^[A-Za-z]:", pattern):
        raise GuardianError(f"Scope path must be repository-relative: {value}")
    if any(part == ".." for part in pattern.split("/")):
        raise GuardianError(f"Scope path cannot escape the repository: {value}")
    return pattern.removeprefix("./")


def _static_pattern_prefix(pattern: str) -> str:
    positions = [position for token in "*?[" if (position := pattern.find(token)) >= 0]
    end = min(positions) if positions else len(pattern)
    return pattern[:end].rstrip("/")


def _patterns_overlap(left: str, right: str) -> bool:
    left_prefix = _static_pattern_prefix(left)
    right_prefix = _static_pattern_prefix(right)
    if not left_prefix or not right_prefix:
        return True
    return (
        left_prefix == right_prefix
        or left_prefix.startswith(right_prefix + "/")
        or right_prefix.startswith(left_prefix + "/")
        or fnmatch.fnmatch(left_prefix, right)
        or fnmatch.fnmatch(right_prefix, left)
    )


def _scope_conflicts(
    project: dict[str, Any],
    item_id: str,
    allowed_changes: list[dict[str, str]],
    impacted_nodes: list[str],
    depends_on: list[str],
) -> list[dict[str, Any]]:
    conflicts = []
    intended_paths = [entry["path"] for entry in allowed_changes]
    intended_nodes = set(impacted_nodes)
    for other in project.get("work_items", []):
        if other.get("id") == item_id or other.get("status") not in ACTIVE_STATUSES:
            continue
        other_paths = [entry.get("path", "") for entry in other.get("scope", {}).get("allowed_changes", [])]
        path_pairs = sorted(
            {f"{left} <> {right}" for left in intended_paths for right in other_paths if _patterns_overlap(left, right)}
        )
        shared_nodes = sorted(intended_nodes & set(other.get("scope", {}).get("impacted_nodes", [])))
        if path_pairs or shared_nodes:
            conflicts.append(
                {
                    "item_id": other["id"],
                    "title": other.get("title"),
                    "path_overlaps": path_pairs,
                    "shared_nodes": shared_nodes,
                    "serialized": other["id"] in depends_on,
                }
            )
    return conflicts


def set_change_scope(
    project_root: str,
    item_id: str,
    allowed_changes: list[dict[str, str]],
    impacted_nodes: list[str] | None = None,
    architecture_notes: list[str] | None = None,
    depends_on: list[str] | None = None,
) -> dict[str, Any]:
    normalized = []
    for entry in allowed_changes:
        pattern = _normalize_pattern(str(entry.get("path", "")))
        reason = str(entry.get("reason", "")).strip()
        if not reason:
            raise GuardianError(f"Every allowed path needs a reason: {pattern}")
        normalized.append({"path": pattern, "reason": reason})
    if not normalized:
        raise GuardianError("At least one allowed change is required before editing")

    def mutate(project: dict[str, Any]):
        item = _find_item(project, item_id)
        normalized_nodes = [str(value).strip() for value in (impacted_nodes or []) if str(value).strip()]
        normalized_dependencies = [str(value).strip() for value in (depends_on or []) if str(value).strip()]
        for dependency in normalized_dependencies:
            if dependency == item_id:
                raise GuardianError("A work item cannot depend on itself")
            _find_item(project, dependency)
        conflicts = _scope_conflicts(project, item_id, normalized, normalized_nodes, normalized_dependencies)
        item["scope"] = {
            "allowed_changes": normalized,
            "impacted_nodes": normalized_nodes,
            "architecture_notes": [str(value).strip() for value in (architecture_notes or []) if str(value).strip()],
        }
        item["depends_on"] = normalized_dependencies
        item["scope_conflicts"] = conflicts
        unresolved = [conflict for conflict in conflicts if not conflict["serialized"]]
        waiting = [
            dependency
            for dependency in normalized_dependencies
            if _find_item(project, dependency).get("status") not in {"completed", "merged", "cancelled"}
        ]
        item["status"] = "blocked" if unresolved or waiting else "scoped"
        item["updated_at"] = utc_now()
        return {
            **item["scope"],
            "depends_on": normalized_dependencies,
            "conflicts": conflicts,
            "blocked": item["status"] == "blocked",
        }

    return _mutate_project(project_root, mutate)


def _path_reason(path: str, allowed_changes: list[dict[str, str]]) -> str | None:
    normalized = path.replace("\\", "/")
    for entry in allowed_changes:
        pattern = entry["path"]
        if fnmatch.fnmatch(normalized, pattern):
            return entry["reason"]
        prefix = pattern.rstrip("/")
        if not any(token in prefix for token in "*?[") and (normalized == prefix or normalized.startswith(prefix + "/")):
            return entry["reason"]
    return None


def _changed_files(worktree: str, base_commit: str) -> list[str]:
    tracked = _run_git(worktree, ["diff", "--name-only", "--diff-filter=ACDMRTUXB", base_commit], check=False)
    untracked = _run_git(worktree, ["ls-files", "--others", "--exclude-standard"], check=False)
    values = {line.strip().replace("\\", "/") for line in (tracked + "\n" + untracked).splitlines() if line.strip()}
    return sorted(values)


def _changed_file_statuses(worktree: str, base_commit: str) -> list[dict[str, str]]:
    rows: dict[str, str] = {}
    raw = _run_git(worktree, ["diff", "--name-status", "--find-renames", base_commit], check=False)
    for line in raw.splitlines():
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        status = parts[0]
        path = parts[-1].strip().replace("\\", "/")
        if path:
            rows[path] = status
    for relative in _run_git(worktree, ["ls-files", "--others", "--exclude-standard"], check=False).splitlines():
        path = relative.strip().replace("\\", "/")
        if path:
            rows[path] = "A"
    return [{"path": path, "status": rows[path]} for path in sorted(rows)]


def _looks_like_test(path: str) -> bool:
    value = path.replace("\\", "/")
    return bool(
        re.search(r"(^|/)(tests?|__tests__)(/|$)", value, re.IGNORECASE)
        or re.search(r"(\.test\.|\.spec\.|Tests?\.cs$|_test\.py$)", value, re.IGNORECASE)
    )


def worktree_fingerprint(worktree: str, base_commit: str) -> str:
    digest = hashlib.sha256()
    digest.update(base_commit.encode("ascii", errors="ignore"))
    diff = subprocess.run(
        ["git", "diff", "--binary", base_commit],
        cwd=worktree,
        capture_output=True,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        timeout=120,
    )
    digest.update(diff.stdout)
    for relative in _run_git(worktree, ["ls-files", "--others", "--exclude-standard"], check=False).splitlines():
        relative = relative.strip()
        if not relative:
            continue
        digest.update(relative.replace("\\", "/").encode("utf-8"))
        candidate = Path(worktree) / relative
        if candidate.is_file():
            with candidate.open("rb") as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(chunk)
    return digest.hexdigest()


def scan_changes(project_root: str, item_id: str) -> dict[str, Any]:
    project = _load_project(project_root)
    item = _find_item(project, item_id)
    worktree = item.get("worktree_path")
    base_commit = item.get("base_commit")
    if not worktree or not base_commit:
        raise GuardianError("Prepare the worktree before scanning changes")
    changed = _changed_files(worktree, base_commit)
    mapped = []
    orphan = []
    for path in changed:
        reason = _path_reason(path, item.get("scope", {}).get("allowed_changes", []))
        if reason:
            mapped.append({"path": path, "reason": reason})
        else:
            orphan.append(path)
    graph = project.get("architecture", {}).get("graph") or {}
    file_modules = {entry.get("path"): entry.get("module_id") for entry in graph.get("files", [])}
    declared_nodes = set(item.get("scope", {}).get("impacted_nodes", []))
    declared_modules = {value for value in declared_nodes if value.startswith("module:")}
    declared_modules.update(
        symbol.get("module_id")
        for symbol in graph.get("symbols", [])
        if symbol.get("id") in declared_nodes and symbol.get("module_id")
    )
    changed_modules = sorted({file_modules[path] for path in changed if file_modules.get(path)})
    unexpected_modules = sorted(set(changed_modules) - declared_modules) if graph.get("modules") else []
    change_statuses = _changed_file_statuses(worktree, base_commit)
    scan = {
        "changed_files": changed,
        "change_statuses": change_statuses,
        "mapped_changes": mapped,
        "orphan_changes": orphan,
        "test_files_changed": [path for path in changed if _looks_like_test(path)],
        "test_files_deleted": [
            row["path"] for row in change_statuses if row["status"].startswith("D") and _looks_like_test(row["path"])
        ],
        "changed_modules": changed_modules,
        "unexpected_impacted_nodes": unexpected_modules,
        "fingerprint": worktree_fingerprint(worktree, base_commit),
        "scanned_at": utc_now(),
    }

    def mutate(state: dict[str, Any]):
        mutable = _find_item(state, item_id)
        mutable["last_scan"] = scan
        mutable["status"] = "blocked" if orphan or unexpected_modules else "verifying"
        mutable["updated_at"] = utc_now()
        return scan

    return _mutate_project(project_root, mutate)


def record_evidence(
    project_root: str,
    item_id: str,
    kind: str,
    success: bool,
    summary: str,
    command: str | None = None,
    artifact: str | None = None,
    _generated: bool = False,
) -> dict[str, Any]:
    if kind not in EVIDENCE_KINDS:
        raise GuardianError(f"Unsupported evidence kind: {kind}")
    if kind == "automated_guard" and not _generated:
        raise GuardianError("automated_guard evidence must be generated by run_automated_guard")
    project = _load_project(project_root)
    item = _find_item(project, item_id)
    worktree = item.get("worktree_path")
    base_commit = item.get("base_commit")
    fingerprint = None
    commit = None
    if worktree and base_commit:
        fingerprint = worktree_fingerprint(worktree, base_commit)
        commit = _run_git(worktree, ["rev-parse", "HEAD"])
    evidence = {
        "id": f"ev-{uuid.uuid4().hex[:10]}",
        "kind": kind,
        "success": bool(success),
        "summary": summary.strip(),
        "command": command.strip() if command else None,
        "artifact": artifact.strip() if artifact else None,
        "commit": commit,
        "fingerprint": fingerprint,
        "recorded_at": utc_now(),
    }
    if not evidence["summary"]:
        raise GuardianError("Evidence summary is required")

    def mutate(state: dict[str, Any]):
        mutable = _find_item(state, item_id)
        mutable["evidence"].append(evidence)
        if kind == "architecture" and success:
            mutable["architecture_review_required"] = False
        mutable["updated_at"] = utc_now()
        return evidence

    return _mutate_project(project_root, mutate)


def _matches_any_path(path: str, patterns: Iterable[str]) -> bool:
    normalized = path.replace("\\", "/")
    for pattern in patterns:
        normalized_pattern = str(pattern).replace("\\", "/")
        if fnmatch.fnmatch(normalized, normalized_pattern):
            return True
        if normalized_pattern.startswith("**/") and fnmatch.fnmatch(normalized, normalized_pattern[3:]):
            return True
    return False


def run_automated_guard(project_root: str, item_id: str) -> dict[str, Any]:
    """Run deterministic low-risk scope, drift, and test-integrity checks."""
    project = _load_project(project_root)
    item = _find_item(project, item_id)
    assessment = (item.get("orchestration") or {}).get("risk_assessment") or {}
    if _orchestration_profile(item) != MODEL_ORCHESTRATION_PROFILE or assessment.get("level") != "low":
        raise GuardianError("Automated guard is available only for v2 low-risk work items")
    scan = item.get("last_scan") or {}
    if not item.get("worktree_path") or not item.get("base_commit"):
        raise GuardianError("Bind a worktree before running the automated guard")
    current_fingerprint = worktree_fingerprint(item["worktree_path"], item["base_commit"])
    protected_paths = project.get("architecture", {}).get("protected_paths", [])
    protected_patterns = [
        value.get("path") if isinstance(value, dict) else value
        for value in protected_paths
        if value
    ]
    changed_files = scan.get("changed_files", [])
    checks = [
        {
            "id": "fresh_scan",
            "passed": bool(scan) and scan.get("fingerprint") == current_fingerprint,
            "detail": "变更扫描与当前候选代码指纹一致",
        },
        {
            "id": "non_empty",
            "passed": bool(changed_files),
            "detail": "候选版本包含可验证的变更",
        },
        {
            "id": "declared_scope",
            "passed": not scan.get("orphan_changes"),
            "detail": "所有修改文件都属于声明范围",
        },
        {
            "id": "declared_impact",
            "passed": not scan.get("unexpected_impacted_nodes"),
            "detail": "没有跨入未声明模块",
        },
        {
            "id": "scope_conflicts",
            "passed": not [entry for entry in item.get("scope_conflicts", []) if not entry.get("serialized")],
            "detail": "没有未处理的并行范围冲突",
        },
        {
            "id": "test_deletion",
            "passed": not scan.get("test_files_deleted"),
            "detail": "没有删除测试文件",
        },
        {
            "id": "protected_paths",
            "passed": not any(_matches_any_path(path, protected_patterns) for path in changed_files),
            "detail": "没有修改项目保护路径",
        },
        {
            "id": "sensitive_paths",
            "passed": not any(_matches_any_path(path, AUTOMATED_GUARD_SENSITIVE_PATHS) for path in changed_files),
            "detail": "没有触及依赖、迁移、协议、安全或项目结构文件",
        },
        {
            "id": "single_module",
            "passed": len(scan.get("changed_modules", [])) <= 1,
            "detail": "修改保持在单一模块内",
        },
    ]
    failed = [check for check in checks if not check["passed"]]
    success = not failed
    summary = (
        "自动门禁通过：范围、模块、保护路径和测试完整性未发现升级信号"
        if success
        else "自动门禁需要 AI 复审：" + "；".join(check["detail"] for check in failed)
    )
    evidence = record_evidence(
        project_root,
        item_id,
        "automated_guard",
        success,
        summary,
        command="guardian:automated_guard",
        _generated=True,
    )
    return {
        "item_id": item_id,
        "success": success,
        "fingerprint": current_fingerprint,
        "checks": checks,
        "failed_checks": [check["id"] for check in failed],
        "requires_ai_review": not success,
        "fallback_review": _stage_label(item, "review") if failed else None,
        "evidence": evidence,
    }


def record_attempt(project_root: str, item_id: str, success: bool, summary: str) -> dict[str, Any]:
    def mutate(project: dict[str, Any]):
        item = _find_item(project, item_id)
        if not summary.strip():
            raise GuardianError("Attempt summary is required")
        fingerprint = None
        commit = None
        if item.get("worktree_path") and item.get("base_commit"):
            fingerprint = worktree_fingerprint(item["worktree_path"], item["base_commit"])
            commit = _run_git(item["worktree_path"], ["rev-parse", "HEAD"])
        if success:
            item["consecutive_failures"] = 0
        else:
            item["consecutive_failures"] = int(item.get("consecutive_failures", 0)) + 1
        if item["consecutive_failures"] >= 2:
            item["architecture_review_required"] = True
            item["status"] = "architecture_review"
            if item.get("kind") != "question":
                orchestration = item.setdefault(
                    "orchestration",
                    {"profile": MODEL_ORCHESTRATION_PROFILE, "risk_assessment": _empty_risk_assessment(), "runs": []},
                )
                previous = orchestration.get("risk_assessment") or _empty_risk_assessment()
                signals = sorted(set(previous.get("signals", [])) | {"repeated_failure"})
                orchestration["profile"] = MODEL_ORCHESTRATION_PROFILE
                orchestration["risk_assessment"] = {
                    "assessed": True,
                    "level": "high",
                    "signals": signals,
                    "summary": "连续两次失败，已自动升级到高风险 Sol Max 架构路线",
                    "execution_track": "judgment",
                    "source": "automatic_escalation",
                    "assessed_at": utc_now(),
                }
        item.setdefault("attempt_log", []).append(
            {
                "success": bool(success),
                "summary": summary.strip(),
                "commit": commit,
                "fingerprint": fingerprint,
                "recorded_at": utc_now(),
            }
        )
        item["updated_at"] = utc_now()
        result = {
            "consecutive_failures": item["consecutive_failures"],
            "architecture_review_required": item["architecture_review_required"],
            "status": item["status"],
            "fingerprint": fingerprint,
        }
        if item.get("kind") != "question":
            result["risk_route"] = _risk_route_view(item)
        return result

    return _mutate_project(project_root, mutate)


def _latest_evidence(item: dict[str, Any], kind: str) -> dict[str, Any] | None:
    matches = [entry for entry in item.get("evidence", []) if entry.get("kind") == kind]
    return matches[-1] if matches else None


def _documentation_only_scan(scan: dict[str, Any] | None) -> bool:
    if not scan or not scan.get("changed_files"):
        return False
    documentation_names = {
        "readme",
        "changelog",
        "contributing",
        "license",
        "code_of_conduct",
        "security",
        "authors",
    }
    for raw in scan["changed_files"]:
        path = PurePosixPath(str(raw).replace("\\", "/"))
        stem = path.stem.lower()
        if path.parts and path.parts[0].lower() == "docs":
            continue
        if path.suffix.lower() in {".md", ".rst", ".adoc"}:
            continue
        if stem not in documentation_names:
            return False
    return True


def _required_evidence_kinds(item: dict[str, Any], scan: dict[str, Any] | None) -> list[str]:
    assessment = (item.get("orchestration") or {}).get("risk_assessment") or {}
    if _orchestration_profile(item) == MODEL_ORCHESTRATION_PROFILE and assessment.get("level") == "low":
        guard = _latest_evidence(item, "automated_guard")
        review_gate = "independent_review" if guard and not guard.get("success") else "automated_guard"
        if _documentation_only_scan(scan):
            return ["target", review_gate]
        return ["target", "related", review_gate, "integration"]
    if assessment.get("level") == "low" and _documentation_only_scan(scan):
        return ["target", "independent_review"]
    return ["target", "related", "full", "independent_review", "integration"]


def _orchestration_blockers(item: dict[str, Any], current_fingerprint: str | None) -> list[dict[str, str]]:
    orchestration = item.get("orchestration") or {}
    if orchestration.get("profile") not in ADAPTIVE_ORCHESTRATION_PROFILES:
        return []
    blockers: list[dict[str, str]] = []
    runs = orchestration.get("runs", [])
    assessment = orchestration.get("risk_assessment") or {}
    if not assessment.get("assessed"):
        return [
            {
                "gate": "model_orchestration",
                "reason": "The work item risk has not been assessed, so no model route is authorized",
            }
        ]

    planning_model, planning_effort = _expected_stage_model(item, "planning")
    execution_model, execution_effort = _expected_stage_model(item, "execution")
    review_model, review_effort = _expected_stage_model(item, "review")

    planning = [
        run
        for run in runs
        if run.get("stage") == "planning"
        and run.get("status") == "completed"
        and run.get("outcome") == "ready"
        and run.get("model") == planning_model
        and _reasoning_effort_matches(run, planning_effort)
        and _run_matches_contract_revision(item, run)
    ]
    if not planning:
        blockers.append(
            {
                "gate": "model_orchestration",
                "reason": f"No completed {planning_model} {planning_effort} planning stage is recorded for the current risk route and design-contract revision",
            }
        )

    executions = [
        run
        for run in runs
        if run.get("stage") == "execution"
        and run.get("status") == "completed"
        and run.get("outcome") == "implemented"
        and run.get("model") == execution_model
        and _reasoning_effort_matches(run, execution_effort)
    ]
    if not executions:
        blockers.append(
            {
                "gate": "model_orchestration",
                "reason": f"No completed {execution_model} {execution_effort} execution stage is recorded for the current risk route",
            }
        )

    changes = [
        run
        for run in runs
        if (
            run.get("stage") == "execution"
            and run.get("status") == "completed"
            and run.get("outcome") == "implemented"
            and run.get("model") == execution_model
            and _reasoning_effort_matches(run, execution_effort)
        )
        or (
            run.get("stage") == "major_fix"
            and run.get("status") == "completed"
            and run.get("outcome") == "fixed"
        )
    ]
    latest_change = max(changes, key=lambda run: run.get("updated_at", ""), default=None)
    guard = _latest_evidence(item, "automated_guard")
    review_required = _review_mode(item) != "automated_guard" or bool(guard and not guard.get("success"))
    passing_reviews = [
        run
        for run in runs
        if run.get("stage") in {"review", "final_review"}
        and run.get("status") == "completed"
        and run.get("outcome") == "passed"
        and (
            (
                run.get("stage") == "review"
                and run.get("model") == review_model
                and _reasoning_effort_matches(run, review_effort)
            )
            or (
                run.get("stage") == "final_review"
                and run.get("model") == _major_stage_model(item, "final_review")[0]
                and _reasoning_effort_matches(run, _major_stage_model(item, "final_review")[1])
            )
        )
    ]
    latest_review = max(passing_reviews, key=lambda run: run.get("updated_at", ""), default=None)
    if review_required and latest_review is None:
        blockers.append(
            {
                "gate": "model_orchestration",
                "reason": f"No independent {review_model} {review_effort} passing review is recorded for the current risk route",
            }
        )
    elif review_required and latest_change and latest_review.get("updated_at", "") < latest_change.get("updated_at", ""):
        blockers.append(
            {
                "gate": "model_orchestration",
                "reason": "The passing independent review predates the latest implementation or major fix",
            }
        )
    elif review_required and current_fingerprint and latest_review.get("fingerprint") != current_fingerprint:
        blockers.append(
            {
                "gate": "model_orchestration",
                "reason": "The passing independent review is stale for the current worktree fingerprint",
            }
        )
    return blockers


def check_merge_readiness(project_root: str, item_id: str) -> dict[str, Any]:
    project = _load_project(project_root)
    item = _find_item(project, item_id)
    blockers: list[dict[str, str]] = []
    onboarding = _refresh_onboarding(project)
    if not onboarding["can_start_work"]:
        blockers.append({"gate": "project_onboarding", "reason": "; ".join(onboarding["blockers"])})
    if item["kind"] == "question":
        blockers.append({"gate": "change_goal", "reason": "Diagnosis-only items are not merge candidates"})
    contract = item.get("contract", {})
    if not _contract_ready(item):
        blockers.append({"gate": "design_contract", "reason": "Requirement/design contract is not reviewed and ready"})
    for key in ("original_request", "goal", "acceptance_criteria", "non_goals", "protected_behaviors"):
        if not contract.get(key):
            blockers.append({"gate": "contract", "reason": f"Missing contract field: {key}"})
    if not item.get("worktree_path"):
        blockers.append({"gate": "worktree", "reason": "No isolated worktree is registered"})
    if not (item.get("task") or {}).get("thread_id"):
        blockers.append({"gate": "codex_task", "reason": "No Codex task is bound to this work item"})
    unresolved_conflicts = [entry for entry in item.get("scope_conflicts", []) if not entry.get("serialized")]
    if unresolved_conflicts:
        blockers.append(
            {
                "gate": "parallel_scope",
                "reason": "Scope overlaps active work items: " + ", ".join(entry["item_id"] for entry in unresolved_conflicts),
            }
        )
    waiting = [
        dependency
        for dependency in item.get("depends_on", [])
        if _find_item(project, dependency).get("status") not in {"completed", "merged", "cancelled"}
    ]
    if waiting:
        blockers.append({"gate": "dependency", "reason": "Waiting for work items: " + ", ".join(waiting)})
    scan = item.get("last_scan")
    if not scan:
        blockers.append({"gate": "change_scan", "reason": "Changes have not been scanned"})
        current_fingerprint = None
    else:
        current_fingerprint = worktree_fingerprint(item["worktree_path"], item["base_commit"])
        if current_fingerprint != scan.get("fingerprint"):
            blockers.append({"gate": "change_scan", "reason": "Changes were modified after the last scan"})
        if not scan.get("changed_files"):
            blockers.append({"gate": "change_scan", "reason": "No changed files are present"})
        if scan.get("orphan_changes"):
            blockers.append(
                {"gate": "scope", "reason": "Unmapped changes: " + ", ".join(scan["orphan_changes"])}
            )
        if scan.get("unexpected_impacted_nodes"):
            blockers.append(
                {
                    "gate": "impact_map",
                    "reason": "Changed modules were not declared as impacted: "
                    + ", ".join(scan["unexpected_impacted_nodes"]),
                }
            )

    blockers.extend(_orchestration_blockers(item, current_fingerprint))

    baseline = _latest_evidence(item, "baseline")
    if not baseline:
        blockers.append({"gate": "baseline", "reason": "Pre-change baseline evidence is missing"})
    required_success = _required_evidence_kinds(item, scan)
    if scan and scan.get("test_files_changed"):
        required_success.append("test_integrity_review")
    if item.get("architecture_review_required"):
        required_success.append("architecture")
    for kind in required_success:
        evidence = _latest_evidence(item, kind)
        if not evidence:
            blockers.append({"gate": kind, "reason": f"Required evidence is missing: {kind}"})
            continue
        if not evidence.get("success"):
            blockers.append({"gate": kind, "reason": f"Latest evidence failed: {evidence.get('summary', kind)}"})
            continue
        if current_fingerprint and evidence.get("fingerprint") != current_fingerprint:
            blockers.append({"gate": kind, "reason": "Evidence is stale for the current worktree fingerprint"})

    ready = not blockers

    def mutate(state: dict[str, Any]):
        mutable = _find_item(state, item_id)
        mutable["status"] = "ready_for_user_confirmation" if ready else (
            "architecture_review" if mutable.get("architecture_review_required") else "blocked"
        )
        mutable["merge_readiness"] = {
            "ready": ready,
            "blockers": blockers,
            "checked_at": utc_now(),
            "fingerprint": current_fingerprint,
        }
        mutable["updated_at"] = utc_now()
        return mutable["merge_readiness"]

    return _mutate_project(project_root, mutate)


def complete_work_item(
    project_root: str,
    item_id: str,
    merge_commit: str,
    summary: str,
    target_ref: str | None = None,
) -> dict[str, Any]:
    if not merge_commit.strip() or not summary.strip():
        raise GuardianError("merge_commit and summary are required")
    project = _load_project(project_root)
    item = _find_item(project, item_id)
    if not (item.get("merge_readiness") or {}).get("ready"):
        raise GuardianError("The work item has not passed merge readiness")
    resolved = _run_git(project["root"], ["rev-parse", "--verify", f"{merge_commit.strip()}^{{commit}}"])
    target = target_ref or (project.get("onboarding", {}).get("canonical_base") or {}).get("ref")
    if not target:
        raise GuardianError("A target_ref is required when the project has no canonical branch")
    reachable = subprocess.run(
        ["git", "merge-base", "--is-ancestor", resolved, target],
        cwd=project["root"],
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    ).returncode == 0
    if not reachable:
        raise GuardianError(f"Merge commit is not reachable from target ref: {target}")
    current_fingerprint = worktree_fingerprint(item["worktree_path"], item["base_commit"])
    if current_fingerprint != item["merge_readiness"].get("fingerprint"):
        raise GuardianError("The candidate changed after merge readiness was checked")
    for relative in (item.get("last_scan") or {}).get("changed_files", []):
        candidate = Path(item["worktree_path"]) / relative
        merged_blob = _run_git(project["root"], ["rev-parse", "--verify", f"{resolved}:{relative}"], check=False)
        if candidate.is_file():
            candidate_blob = _run_git(
                item["worktree_path"],
                ["hash-object", "--path", relative, relative],
                check=False,
            )
            if not merged_blob or merged_blob != candidate_blob:
                raise GuardianError(f"Merge commit does not contain the verified candidate file: {relative}")
        elif merged_blob:
            raise GuardianError(f"Merge commit still contains a file deleted by the verified candidate: {relative}")

    def mutate(state: dict[str, Any]):
        mutable = _find_item(state, item_id)
        mutable["status"] = "completed"
        mutable["completion"] = {
            "merge_commit": resolved,
            "target_ref": target,
            "summary": summary.strip(),
            "completed_at": utc_now(),
        }
        mutable["updated_at"] = utc_now()
        return mutable["completion"]

    return _mutate_project(project_root, mutate)


def _children(project: dict[str, Any], parent_id: str | None) -> list[dict[str, Any]]:
    return [item for item in project.get("work_items", []) if item.get("parent_id") == parent_id]


def _mindmap_label(item: dict[str, Any]) -> str:
    title = re.sub(r"[\r\n]+", " ", item["title"]).replace('"', "'")
    assessment = (item.get("orchestration") or {}).get("risk_assessment") or {}
    risk = RISK_LEVEL_LABELS.get(assessment.get("level"), "待判风险") if item.get("kind") != "question" else "只读诊断"
    phase = CONTRACT_PHASE_LABELS.get(
        (item.get("contract") or {}).get("phase", "ready"),
        (item.get("contract") or {}).get("phase", "ready"),
    )
    return f"{title} - {phase} - {item['status']} - {risk}"


def _mindmap_text(value: Any) -> str:
    return re.sub(r"[()\[\]{}\r\n]+", " ", str(value)).strip() or "unknown"


def _render_mindmap(project: dict[str, Any]) -> str:
    lines = ["mindmap", f"  root(({project['name']}))"]

    onboarding = _refresh_onboarding(project)
    lines.extend(["    项目接入", f"      {_mindmap_text(onboarding['status'])}"])
    canonical = onboarding.get("canonical_base")
    if canonical:
        lines.append(f"      基线 {_mindmap_text(canonical['ref'])} {_mindmap_text(canonical['commit'][:8])}")
    for blocker in onboarding.get("blockers", [])[:5]:
        lines.append(f"      阻塞 {_mindmap_text(blocker)}")

    graph = project.get("architecture", {}).get("graph") or {}
    lines.append("    功能模块")
    modules = graph.get("modules", [])
    if modules:
        for module in modules[:40]:
            lines.append(
                f"      {_mindmap_text(module['name'])} - {module.get('source_file_count', 0)} source {module.get('test_file_count', 0)} test"
            )
    else:
        lines.append("      尚未生成代码地图")

    lines.append("    分支与工作树")
    worktrees = project.get("inventory", {}).get("worktrees", [])
    if worktrees:
        bindings = {
            _path_key(item["worktree_path"]): item
            for item in project.get("work_items", [])
            if item.get("worktree_path")
        }
        for row in worktrees[:30]:
            owner = bindings.get(_path_key(row["path"]))
            branch = row.get("branch") or "detached"
            state = "dirty" if row.get("dirty") else "clean"
            suffix = f" - {owner['title']}" if owner else " - unassigned"
            lines.append(f"      {_mindmap_text(branch)} - {state}{_mindmap_text(suffix)}")
    else:
        lines.append("      尚未扫描")

    lines.append("    开发任务")

    def append(parent_id: str | None, indent: int):
        for item in _children(project, parent_id):
            lines.append(" " * indent + _mindmap_label(item))
            append(item["id"], indent + 2)

    before = len(lines)
    append(None, 6)
    if len(lines) == before:
        lines.append("      尚无工作节点")
    return "\n".join(lines)


def get_project_map(project_root: str) -> dict[str, Any]:
    project = _load_project(project_root)
    onboarding = _refresh_onboarding(project)
    guidance = _project_guidance(project)
    items = []
    for item in project.get("work_items", []):
        last_scan = item.get("last_scan") or {}
        items.append(
            {
                "id": item["id"],
                "title": item["title"],
                "kind": item["kind"],
                "parent_id": item.get("parent_id"),
                "status": item["status"],
                "branch": item.get("branch"),
                "worktree_path": item.get("worktree_path"),
                "task": item.get("task"),
                "orchestration": item.get("orchestration"),
                "risk_route": _risk_route_view(item),
                "design_contract": _design_contract_view(item),
                "changed_files": len(last_scan.get("changed_files", [])),
                "orphan_changes": len(last_scan.get("orphan_changes", [])),
                "architecture_review_required": item.get("architecture_review_required", False),
                "merge_ready": bool((item.get("merge_readiness") or {}).get("ready")),
                "scope_conflicts": item.get("scope_conflicts", []),
            }
        )
    bindings = {
        _path_key(item["worktree_path"]): item
        for item in project.get("work_items", [])
        if item.get("worktree_path")
    }
    worktrees = []
    for row in project.get("inventory", {}).get("worktrees", []):
        value = dict(row)
        owner = bindings.get(_path_key(row["path"]))
        value["work_item_id"] = owner.get("id") if owner else None
        value["thread_id"] = (owner.get("task") or {}).get("thread_id") if owner else None
        value["title"] = owner.get("title") if owner else None
        worktrees.append(value)
    branch_owners: dict[str, dict[str, Any]] = {}
    for item in project.get("work_items", []):
        if item.get("branch"):
            branch_owners[item["branch"]] = item
    for row in worktrees:
        if row.get("branch") and row.get("work_item_id"):
            branch_owners[row["branch"]] = _find_item(project, row["work_item_id"])
    branches = []
    for row in project.get("inventory", {}).get("branches", []):
        value = dict(row)
        owner = branch_owners.get(row["name"])
        value["work_item_id"] = owner.get("id") if owner else None
        value["thread_id"] = (owner.get("task") or {}).get("thread_id") if owner else None
        value["title"] = owner.get("title") if owner else None
        branches.append(value)
    return {
        "project_id": project["project_id"],
        "name": project["name"],
        "root": project["root"],
        "onboarding": onboarding,
        "can_start_work": onboarding["can_start_work"],
        "inventory": {
            "branches": branches,
            "worktrees": worktrees,
            "scanned_at": project.get("inventory", {}).get("scanned_at"),
        },
        "graph_summary": _graph_summary(project.get("architecture", {}).get("graph")),
        "modules": (project.get("architecture", {}).get("graph") or {}).get("modules", []),
        "items": items,
        "model_orchestration_profile": project.get("settings", {}).get("model_orchestration_profile"),
        "guidance": guidance,
        "mermaid": _render_mindmap(project),
        "updated_at": project["updated_at"],
    }


def get_project_dashboard(project_root: str) -> dict[str, Any]:
    """Return a beginner-facing, deterministic view model for the in-conversation project map."""
    project = _load_project(project_root)
    onboarding = _refresh_onboarding(project)
    guidance = _project_guidance(project)
    graph = project.get("architecture", {}).get("graph") or {}
    inventory_state = project.get("inventory", {})
    worktrees = inventory_state.get("worktrees", [])
    bindings = {
        _path_key(item["worktree_path"]): item
        for item in project.get("work_items", [])
        if item.get("worktree_path")
    }

    branch_rows = []
    for branch in inventory_state.get("branches", []):
        branch_worktrees = [row for row in worktrees if row.get("branch") == branch.get("name")]
        owners = [bindings.get(_path_key(row["path"])) for row in branch_worktrees]
        owner = next((value for value in owners if value), None)
        branch_rows.append(
            {
                "name": branch.get("name"),
                "commit": branch.get("commit"),
                "last_commit_subject": branch.get("last_commit_subject"),
                "source_file_count": branch.get("source_file_count", 0),
                "file_count": branch.get("file_count", 0),
                "top_areas": branch.get("top_areas", [])[:6],
                "ahead_of_canonical": branch.get("ahead_of_canonical"),
                "behind_canonical": branch.get("behind_canonical"),
                "worktree_count": len(branch_worktrees),
                "dirty_worktrees": sum(1 for row in branch_worktrees if row.get("dirty")),
                "work_item_id": owner.get("id") if owner else None,
                "work_item_title": owner.get("title") if owner else None,
                "thread_id": (owner.get("task") or {}).get("thread_id") if owner else None,
                "inspect_action": _follow_up_action(
                    f"inspect-branch:{branch.get('name')}",
                    "查看这个分支在做什么",
                    f"使用 Project Guardian 的 get_branch_map 查看项目 {project['root']} 的分支 {branch.get('name')}，用小白能懂的话说明它的主要内容、与真实基线的差异、工作树状态和所属 Codex 任务。",
                    "只读取该分支的持久化资料。",
                ),
            }
        )

    module_rows = []
    for module in graph.get("modules", []):
        module_rows.append(
            {
                "id": module.get("id"),
                "name": module.get("name"),
                "kind": module.get("kind"),
                "root": module.get("root"),
                "source_file_count": module.get("source_file_count", 0),
                "test_file_count": module.get("test_file_count", 0),
                "dependency_count": len(module.get("dependencies", [])),
                "inspect_action": _follow_up_action(
                    f"inspect-module:{module.get('id')}",
                    "查看函数与参数",
                    f"使用 Project Guardian 的 get_module_map 查看项目 {project['root']} 的模块 {module.get('id')}，用小白能懂的话说明它负责什么，并列出关键文件、函数、参数、依赖和相关测试。",
                    "按需读取一个模块，避免把所有代码塞进当前上下文。",
                ),
            }
        )

    item_rows = []
    for item in project.get("work_items", []):
        last_scan = item.get("last_scan") or {}
        contract_view = _design_contract_view(item)
        item_rows.append(
            {
                "id": item.get("id"),
                "title": item.get("title"),
                "kind": item.get("kind"),
                "status": item.get("status"),
                "status_label": WORK_ITEM_STATUS_LABELS.get(item.get("status"), item.get("status")),
                "branch": item.get("branch"),
                "worktree_path": item.get("worktree_path"),
                "thread_id": (item.get("task") or {}).get("thread_id"),
                "orchestration": item.get("orchestration"),
                "risk_route": _risk_route_view(item),
                "design_contract": {
                    key: contract_view.get(key)
                    for key in (
                        "phase",
                        "phase_label",
                        "revision",
                        "requirements_complete",
                        "missing_dimensions",
                        "open_question",
                        "open_decision",
                        "recommendation",
                        "selected_approach",
                        "review",
                        "artifact_uri",
                    )
                },
                "changed_files": len(last_scan.get("changed_files", [])),
                "orphan_changes": len(last_scan.get("orphan_changes", [])),
                "scope_conflicts": len(item.get("scope_conflicts", [])),
                "merge_ready": bool((item.get("merge_readiness") or {}).get("ready")),
            }
        )

    return {
        "dashboard_version": 5,
        "project": {
            "id": project["project_id"],
            "name": project["name"],
            "root": project["root"],
            "updated_at": project["updated_at"],
        },
        "state": {
            "status": onboarding["status"],
            "status_label": guidance["status_label"],
            "summary": guidance["summary"],
            "can_start_work": onboarding["can_start_work"],
            "blockers": onboarding.get("blockers", []),
            "warnings": onboarding.get("warnings", []),
            "canonical_base": onboarding.get("canonical_base"),
            "base_recommendation": onboarding.get("base_recommendation"),
        },
        "metrics": {
            "branches": len(inventory_state.get("branches", [])),
            "worktrees": len(worktrees),
            "dirty_worktrees": sum(1 for row in worktrees if row.get("dirty")),
            "unassigned_worktrees": sum(1 for row in worktrees if not bindings.get(_path_key(row["path"]))),
            "modules": len(graph.get("modules", [])),
            "source_files": graph.get("source_file_count", 0),
            "symbols": len(graph.get("symbols", [])),
            "active_items": sum(1 for item in project.get("work_items", []) if item.get("status") in ACTIVE_STATUSES),
            "waiting_for_merge_confirmation": sum(
                1 for item in project.get("work_items", []) if item.get("status") == "ready_for_user_confirmation"
            ),
            "discovering_requirements": sum(
                1 for item in project.get("work_items", []) if item.get("status") == "discovering_requirements"
            ),
            "waiting_for_product_decision": sum(
                1 for item in project.get("work_items", []) if item.get("status") == "needs_user_decision"
            ),
            "high_risk_items": sum(
                1
                for item in project.get("work_items", [])
                if ((item.get("orchestration") or {}).get("risk_assessment") or {}).get("level") == "high"
            ),
        },
        "model_routing": {
            "profile": project.get("settings", {}).get("model_orchestration_profile"),
            "automatic": True,
            "user_selects_model": False,
            "luna_default_reasoning_effort": "max",
            "max_fallback_reasoning_effort": "xhigh",
            "high_risk_planning_model": "gpt-5.6-sol",
            "high_risk_planning_effort": "max",
            "major_bug_model": "gpt-5.6-sol",
            "major_bug_reasoning_effort": "max",
            "low_risk_review_mode": "automated_guard_with_ai_fallback",
        },
        "next_step": guidance,
        "how_to_use": [
            {"step": 1, "title": "自动看到项目状态", "detail": "Guardian 每轮结束都会在回复底部显示迷你项目图。"},
            {"step": 2, "title": "正常说需求", "detail": "直接说新项目、功能或哪里表现不对；Guardian 自动识别类型。"},
            {"step": 3, "title": "先问清再开发", "detail": "新项目和功能先进入需求访谈；只有真实产品取舍才需要你决定。"},
            {"step": 4, "title": "需要时展开", "detail": "点击“展开完整项目图”查看设计合同、分支、模块、函数和开发任务。"},
        ],
        "sections": {
            "requirements": [
                {
                    "item_id": row["id"],
                    "title": row["title"],
                    "status": row["status"],
                    "status_label": row["status_label"],
                    **row["design_contract"],
                }
                for row in item_rows
            ],
            "branches": branch_rows,
            "modules": module_rows,
            "items": item_rows,
        },
    }


def get_verification_plan(project_root: str, item_id: str) -> dict[str, Any]:
    """Return a compact, fingerprint-aware gate plan so unchanged evidence can be reused."""
    project = _load_project(project_root)
    item = _find_item(project, item_id)
    scan = item.get("last_scan")
    fingerprint = None
    if item.get("worktree_path") and item.get("base_commit"):
        fingerprint = worktree_fingerprint(item["worktree_path"], item["base_commit"])
    required = ["baseline", *_required_evidence_kinds(item, scan)]
    if scan and scan.get("test_files_changed"):
        required.append("test_integrity_review")
    if item.get("architecture_review_required"):
        required.append("architecture")
    required = list(dict.fromkeys(required))
    gates = []
    reusable = []
    pending = []
    for kind in required:
        evidence = _latest_evidence(item, kind)
        if not evidence:
            status = "missing"
        elif not evidence.get("success"):
            status = "failed"
        elif kind == "baseline" or not fingerprint or evidence.get("fingerprint") == fingerprint:
            status = "reusable"
            reusable.append(kind)
        else:
            status = "stale"
        if status != "reusable":
            pending.append(kind)
        gates.append(
            {
                "kind": kind,
                "status": status,
                "evidence_id": evidence.get("id") if evidence else None,
                "summary": evidence.get("summary") if evidence else None,
            }
        )
    canonical = (project.get("onboarding") or {}).get("canonical_base") or {}
    target_ref = canonical.get("ref")
    target_head = _run_git(project["root"], ["rev-parse", "--verify", target_ref], check=False) if target_ref else None
    model_review = [kind for kind in pending if kind == "independent_review"]
    automated = [kind for kind in pending if kind in {"automated_guard", "test_integrity_review"}]
    tests = [kind for kind in pending if kind not in set(model_review + automated + ["architecture"])]
    return {
        "item_id": item_id,
        "candidate": {
            "fingerprint": fingerprint,
            "scan_fingerprint": (scan or {}).get("fingerprint"),
            "scan_is_current": bool(fingerprint and scan and scan.get("fingerprint") == fingerprint),
            "target_ref": target_ref,
            "target_head": target_head or None,
        },
        "review_mode": _review_mode(item),
        "gates": gates,
        "reusable_evidence": reusable,
        "pending_evidence": pending,
        "parallel_groups": {
            "tests": tests,
            "automated": automated,
            "independent_review": model_review,
            "architecture": [kind for kind in pending if kind == "architecture"],
        },
        "instruction": "复用同一候选指纹下已通过的证据；其余测试、自动门禁和独立复审可并行执行。",
    }


def get_work_context(project_root: str, item_id: str) -> dict[str, Any]:
    """Return the bounded context capsule used for task handoff instead of replaying a whole conversation."""
    item = get_work_item(project_root, item_id)
    runs = (item.get("orchestration") or {}).get("runs", [])
    latest_runs: dict[str, dict[str, Any]] = {}
    for run in runs:
        latest_runs[run.get("stage", "unknown")] = {
            key: run.get(key)
            for key in (
                "id",
                "stage",
                "thread_id",
                "model",
                "reasoning_effort",
                "capability_fallback",
                "status",
                "outcome",
                "summary",
                "artifact",
                "contract_revision",
                "fingerprint",
                "updated_at",
            )
        }
    scan = item.get("last_scan") or {}
    return {
        "context_version": 2,
        "item_id": item_id,
        "title": item.get("title"),
        "kind": item.get("kind"),
        "status": item.get("status"),
        "contract": item.get("contract"),
        "design_contract": {
            key: _design_contract_view(item).get(key)
            for key in (
                "phase",
                "phase_label",
                "revision",
                "requirements_complete",
                "missing_dimensions",
                "recommendation",
                "selected_approach",
                "review",
                "artifact_uri",
            )
        },
        "scope": item.get("scope"),
        "task": item.get("task"),
        "branch": item.get("branch"),
        "worktree_path": item.get("worktree_path"),
        "risk_route": _risk_route_view(item),
        "latest_stage_runs": list(latest_runs.values()),
        "change_summary": {
            "changed_files": scan.get("changed_files", []),
            "orphan_changes": scan.get("orphan_changes", []),
            "changed_modules": scan.get("changed_modules", []),
            "unexpected_impacted_nodes": scan.get("unexpected_impacted_nodes", []),
            "fingerprint": scan.get("fingerprint"),
        },
        "verification": get_verification_plan(project_root, item_id),
        "attempts": {
            "consecutive_failures": item.get("consecutive_failures", 0),
            "latest": (item.get("attempt_log") or [])[-1:] or [],
        },
        "context_policy": "只加载该胶囊、精确相关模块和符号；不要重放完整历史会话或完整项目图。",
    }


def get_project_closeout(project_root: str) -> dict[str, Any]:
    """Return the compact project map that should be rendered automatically at the end of each Guardian turn."""
    project = _load_project(project_root)
    onboarding = _refresh_onboarding(project)
    guidance = _project_guidance(project)
    active = [item for item in project.get("work_items", []) if item.get("status") in ACTIVE_STATUSES]
    primary_item = active[0] if active else None
    state_material = {
        "updated_at": project.get("updated_at"),
        "onboarding": onboarding.get("status"),
        "items": [(item.get("id"), item.get("status"), item.get("updated_at")) for item in active],
    }
    state_version = hashlib.sha256(
        json.dumps(state_material, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()[:16]
    compact_items = []
    for item in active[:8]:
        route = _risk_route_view(item)
        runs = (item.get("orchestration") or {}).get("runs", [])
        latest = runs[-1] if runs else None
        compact_items.append(
            {
                "id": item.get("id"),
                "title": item.get("title"),
                "status": item.get("status"),
                "status_label": WORK_ITEM_STATUS_LABELS.get(item.get("status"), item.get("status")),
                "risk": route.get("level_label"),
                "current_stage": (
                    _run_stage_label(latest)
                    if latest
                    else (route.get("stages") or [{}])[0].get("label")
                ),
                "branch": item.get("branch"),
                "thread_id": (item.get("task") or {}).get("thread_id"),
                "merge_ready": bool((item.get("merge_readiness") or {}).get("ready")),
                "contract_phase": (item.get("contract") or {}).get("phase", "ready"),
                "contract_phase_label": CONTRACT_PHASE_LABELS.get(
                    (item.get("contract") or {}).get("phase", "ready"),
                    (item.get("contract") or {}).get("phase", "ready"),
                ),
                "open_question": (item.get("contract") or {}).get("open_question"),
                "open_decision": (item.get("contract") or {}).get("open_decision"),
                "design_artifact_uri": f"guardian://work-items/{item.get('id')}/design-contract",
            }
        )
    expand_action = _follow_up_action(
        "expand-project-map",
        "展开完整项目图",
        f"使用 Project Guardian 打开项目 {project['root']} 的完整项目图，显示开发任务、分支与工作树、功能模块和使用说明。",
        "按需展开完整资料；日常回复只显示迷你项目图以节省上下文。",
    )
    return {
        "closeout_version": 2,
        "state_version": state_version,
        "auto_render": True,
        "render_position": "reply_end",
        "project": {"id": project["project_id"], "name": project["name"], "root": project["root"]},
        "state": {
            "status": onboarding.get("status"),
            "status_label": guidance.get("status_label"),
            "summary": guidance.get("summary"),
        },
        "active_item": compact_items[0] if compact_items else None,
        "mini_map": compact_items,
        "alerts": {
            "blocked": sum(1 for item in active if item.get("status") == "blocked"),
            "drift": sum(1 for item in active if (item.get("last_scan") or {}).get("orphan_changes")),
            "waiting_for_merge": sum(1 for item in active if item.get("status") == "ready_for_user_confirmation"),
            "needs_user_decision": sum(1 for item in active if item.get("status") == "needs_user_decision"),
        },
        "primary_action": guidance.get("primary_action"),
        "expand_action": expand_action,
        "reopen": guidance.get("reopen"),
        "display_policy": "每轮自动显示迷你项目图；首次接入、风险升级、复审失败或等待合并时自动展开完整图。",
    }


def get_branch_map(project_root: str, branch: str) -> dict[str, Any]:
    project = _load_project(project_root)
    row = next(
        (value for value in project.get("inventory", {}).get("branches", []) if value.get("name") == branch),
        None,
    )
    if row is None:
        raise GuardianError(f"Unknown branch in persisted inventory: {branch}")
    worktrees = [
        value for value in project.get("inventory", {}).get("worktrees", []) if value.get("branch") == branch
    ]
    items = []
    for item in project.get("work_items", []):
        owns_branch = item.get("branch") == branch
        owns_worktree = any(
            item.get("worktree_path") and _path_key(item["worktree_path"]) == _path_key(worktree["path"])
            for worktree in worktrees
        )
        if owns_branch or owns_worktree:
            items.append(
                {
                    "id": item["id"],
                    "title": item["title"],
                    "status": item["status"],
                    "task": item.get("task"),
                }
            )
    return {
        "project_id": project["project_id"],
        "canonical_base": project.get("onboarding", {}).get("canonical_base"),
        "branch": row,
        "worktrees": worktrees,
        "work_items": items,
        "assigned": bool(items),
    }


def get_module_map(project_root: str, module_id: str) -> dict[str, Any]:
    project = _load_project(project_root)
    graph = project.get("architecture", {}).get("graph") or {}
    module = next((value for value in graph.get("modules", []) if value.get("id") == module_id), None)
    if module is None:
        raise GuardianError(f"Unknown module: {module_id}")
    files = [entry for entry in graph.get("files", []) if entry.get("module_id") == module_id]
    symbols = [entry for entry in graph.get("symbols", []) if entry.get("module_id") == module_id]
    return {
        "project_id": project["project_id"],
        "commit": graph.get("commit"),
        "module": module,
        "files": files,
        "symbols": symbols,
        "symbol_count": len(symbols),
    }


def search_code_graph(project_root: str, query: str, limit: int = 50) -> dict[str, Any]:
    needle = query.strip().lower()
    if not needle:
        raise GuardianError("query is required")
    limit = max(1, min(int(limit), 100))
    project = _load_project(project_root)
    graph = project.get("architecture", {}).get("graph") or {}
    matches: list[dict[str, Any]] = []
    for module in graph.get("modules", []):
        haystack = " ".join(str(module.get(key, "")) for key in ("id", "name", "root", "manifest")).lower()
        if needle in haystack:
            matches.append({"type": "module", **module})
    for entry in graph.get("files", []):
        if needle in entry.get("path", "").lower():
            matches.append({"type": "file", **entry})
    for symbol in graph.get("symbols", []):
        haystack = " ".join(
            str(symbol.get(key, "")) for key in ("name", "qualified_name", "signature", "file", "module_id")
        ).lower()
        if needle in haystack:
            matches.append({"type": "symbol", **symbol})
    return {
        "project_id": project["project_id"],
        "commit": graph.get("commit"),
        "query": query,
        "matches": matches[:limit],
        "total_matches": len(matches),
        "truncated": len(matches) > limit,
    }


def find_context(cwd: str) -> dict[str, Any] | None:
    target = normalize_path(cwd)
    try:
        target_repo_root = inventory.git_root(target)
        target_common_dir = inventory.git_common_dir(target)
    except (inventory.InventoryError, OSError):
        target_repo_root = None
        target_common_dir = None
    for summary in list_projects():
        try:
            project = _read_json(_project_file(summary["root"]))
        except GuardianError:
            continue
        for item in project.get("work_items", []):
            worktree = item.get("worktree_path")
            if worktree and _is_within(target, worktree):
                return {"mode": "worktree", "project": project, "item": item}
        project_common_dir = project.get("git", {}).get("common_dir")
        if target_common_dir and project_common_dir and os.path.normcase(target_common_dir) == os.path.normcase(project_common_dir):
            if target_repo_root and _path_key(target_repo_root) != _path_key(project["root"]):
                return {
                    "mode": "unbound_worktree",
                    "project": project,
                    "item": None,
                    "worktree_path": target_repo_root,
                }
            return {"mode": "local", "project": project, "item": None}
        if _is_within(target, project["root"]):
            return {"mode": "local", "project": project, "item": None}
    return None


def scope_allows(item: dict[str, Any], relative_path: str) -> tuple[bool, str | None]:
    reason = _path_reason(relative_path.replace("\\", "/"), item.get("scope", {}).get("allowed_changes", []))
    return (reason is not None, reason)
