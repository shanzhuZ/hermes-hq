# -*- coding: utf-8 -*-
"""v3 写报状态机关键防回归测试。"""

import unittest
from unittest.mock import Mock, patch

from report_04 import (
    engine,
    gates,
    orchestrator,
    phases,
    report_parser,
    session_continue,
    sink,
    stream_steps,
)
from report_04.task_store import _v3_identity_verdict


class _FakeStore:
    def __init__(self):
        self.status_calls = []
        self.materialized = 0
        self.validated = 0
        self.events = []

    def set_step_status(self, task_id, step_key, status, **kwargs):
        self.status_calls.append((task_id, step_key, status, kwargs))
        self.events.append(("status", step_key, status))

    def materialize_step4_from_candidates(self, task_id):
        self.materialized += 1
        self.events.append(("materialize", task_id))
        return []

    def run_validated_accounts(self, task_id):
        self.validated += 1


class V3FlowGuardTest(unittest.TestCase):
    @staticmethod
    def _current_template_report(include_economy=True):
        economy = "（五）经济状况\n未获取可核实信息。\n" if include_economy else ""
        return (
            "测试人物 公开资料核查报告\n"
            "一、基本情况\n人物基本履历与公开影响力。" + "公开资料。" * 20 + "\n"
            "社交媒体：\n- 推特/X：未核实\n"
            "（一）教育经历\n未核实。\n"
            "（二）工作经历\n未核实。\n"
            "（三）性格特点\n未核实，未作推断。\n"
            "（四）家庭成员情况\n未核实。\n"
            + economy
            + "二、在职在岗情况\n"
            "（一）工作单位基本情况\n未核实。\n"
            "（二）在岗情况\n未核实。\n"
            "（三）岗位职能\n未核实。\n"
            "三、人脉资源\n未获取可核实公开关系。\n"
            "四、政治立场\n"
            "（一）对华态度\n未核实。\n"
            "（二）对所在国政治态度\n未核实。\n"
            "（三）对美政治态度\n未核实。\n"
            "五、污点劣迹\n（一）本次公开检索未命中可靠负面记录。\n"
            "六、公开表达与专业关注点\n未获取可核实公开表达。\n"
            "七、身份核验与综合结论\n身份核验结论。\n"
            "八、主要来源\n1. 官方来源 https://example.com\n"
        )

    def test_legacy_stream_keys_do_not_alias_v3_identity(self):
        self.assertNotEqual(phases.STREAM_PARENT_STEP_KEY, phases.IDENTITY_STEP_KEY)
        self.assertNotEqual(phases.STREAM_TEXT_STEP_KEY, phases.IDENTITY_STEP_KEY)
        self.assertNotEqual(phases.STREAM_IMAGE_STEP_KEY, phases.IDENTITY_STEP_KEY)

    def test_v3_image_pipeline_is_noop(self):
        store = _FakeStore()
        with patch.object(stream_steps, "_is_v3_report", return_value=True):
            stream_steps.start_step5_image_pipeline(store, "task-v3")
        self.assertEqual([], store.status_calls)

    def test_v3_conclusion_waits_for_candidate_profiles(self):
        store = _FakeStore()
        with patch.object(stream_steps, "_is_v3_report", return_value=True), \
                patch("report_04.gates.discovery_steps_terminal", return_value=True), \
                patch("report_04.gates.step3_profiles_terminal", return_value=False), \
                patch("report_04.intake.is_person_path", return_value=False), \
                patch.object(stream_steps, "get_step_status", return_value="pending"):
            ok = stream_steps.apply_text_conclusion_from_assistant(
                store,
                "task-v3",
                "[账号认定结论]\nvalidated_accounts:\n"
                "- twitter | alice | https://x.com/alice | 同一人\n"
                "excluded_accounts: none",
            )
        self.assertFalse(ok)
        self.assertEqual(1, store.materialized)
        self.assertEqual("running", store.status_calls[-1][2])

    def test_v3_conclusion_completes_without_image_gate(self):
        store = _FakeStore()
        with patch.object(stream_steps, "_is_v3_report", return_value=True), \
                patch("report_04.gates.discovery_steps_terminal", return_value=True), \
                patch("report_04.gates.step3_profiles_terminal", return_value=True), \
                patch("report_04.intake.is_person_path", return_value=False), \
                patch.object(stream_steps, "get_step_status", return_value="running"):
            ok = stream_steps.apply_text_conclusion_from_assistant(
                store,
                "task-v3",
                "[账号认定结论]\nvalidated_accounts:\n"
                "- twitter | alice | https://x.com/alice | 同一人\n"
                "excluded_accounts: none",
            )
        self.assertTrue(ok)
        self.assertEqual("completed", store.status_calls[-1][2])
        self.assertEqual(1, store.validated)

    def test_v3_rejects_unstructured_identity_conclusion(self):
        store = _FakeStore()
        with patch.object(stream_steps, "_is_v3_report", return_value=True), \
                patch("report_04.gates.discovery_steps_terminal", return_value=True), \
                patch("report_04.gates.step3_profiles_terminal", return_value=True), \
                patch("report_04.intake.is_person_path", return_value=False), \
                patch.object(stream_steps, "get_step_status", return_value="running"):
            ok = stream_steps.apply_text_conclusion_from_assistant(
                store,
                "task-v3",
                "[账号认定结论]\n看起来是同一个人。",
            )
        self.assertFalse(ok)
        self.assertEqual(0, store.validated)

    def test_v3_skipped_identity_is_not_terminal(self):
        with patch.object(
            gates,
            "get_step_status",
            side_effect=lambda _task_id, key: "skipped" if key == "step3_identity" else None,
        ):
            self.assertFalse(gates.identity_step_terminal("task-v3"))

    def test_v3_gate_does_not_skip_running_seed_step(self):
        statuses = {
            "step1_seed": "running",
            "step2_maigret": "pending",
            "step3_identity": "pending",
            "step3_profiles": "pending",
            "step4_osint_web": "pending",
            "step5_posts": "pending",
            "step7_report": "pending",
        }
        with patch("report_04.intake.intake_open", return_value=False), \
                patch("report_04.intake.is_person_path", return_value=False), \
                patch("report_04.gates.can_run_step7_collect", return_value=False), \
                patch("report_04.gates.can_advance_to_analysis", return_value={"ok": False}), \
                patch("report_04.gates.is_v3_report_tree", return_value=True), \
                patch("report_04.gates.discovery_steps_terminal", return_value=False), \
                patch("report_04.gates.identity_step_terminal", return_value=False), \
                patch.object(
                    orchestrator,
                    "get_step_status",
                    side_effect=lambda _task_id, key: statuses.get(key),
                ):
            self.assertEqual("step1_seed", orchestrator.infer_gate_step("task-v3"))

    def test_identity_starts_before_profiles_are_materialized(self):
        store = _FakeStore()
        with patch("report_04.gates.is_v3_report_tree", return_value=True), \
                patch.object(engine, "can_advance_to_step5", return_value={"ok": True}), \
                patch.object(engine, "get_step_status", return_value="pending"):
            self.assertTrue(engine.ensure_v3_identity_started(store, "task-v3"))
        self.assertEqual(("status", "step3_identity", "running"), store.events[0])
        self.assertEqual(("materialize", "task-v3"), store.events[1])

    def test_pre_post_call_continuation_uses_collect_kind(self):
        with patch.object(session_continue, "_can_run_step7", return_value=False):
            self.assertEqual(
                "collect",
                session_continue._action_to_continue_kind("call", "task-v3"),
            )
        with patch.object(session_continue, "build_next_action_hint", return_value="继续认定"):
            message = session_continue.build_continue_message("collect", "task-v3")
        self.assertIn("前半段流程尚未收口", message)
        self.assertIn("继续认定", message)

    def test_collect_continuation_is_not_blocked_by_video_write_gate(self):
        store = _FakeStore()
        spawned = Mock(return_value=True)
        session_continue._INFLIGHT.clear()
        with patch.object(session_continue, "has_final_report", return_value=False), \
                patch.object(session_continue, "infer_continue_kind", return_value="collect"), \
                patch.object(session_continue, "next_agent_action", return_value="call"), \
                patch.object(session_continue, "_payload", return_value={}), \
                patch.object(session_continue, "_write_payload"), \
                patch.object(session_continue.db, "fetch_one", return_value={
                    "status": "running",
                    "session_id": "session-1",
                }), \
                patch.object(session_continue.db, "execute"), \
                patch.object(session_continue, "spawn_detached_continue", spawned), \
                patch("report_04.gates.analysis_steps_terminal", return_value=True), \
                patch("report_04.video_report.can_write_report_after_videos",
                      return_value={"ok": False}):
            ok = session_continue.maybe_continue_agent_session(
                store,
                "task-v3",
                reason="test_collect",
                force=True,
            )
        self.assertTrue(ok)
        self.assertEqual("collect", spawned.call_args.args[2])

    def test_intake_web_output_is_tagged_step0(self):
        with patch("report_04.intake.intake_open", return_value=True):
            collect_step, output_step = sink._resolve_collect_phase(
                _FakeStore(),
                "task-v3",
                "web_search",
                None,
                seed_collect=False,
            )
        self.assertIsNone(collect_step)
        self.assertEqual(phases.INTAKE_STEP_KEY, output_step)

    def test_v3_conclusion_verdict_uses_explicit_lists(self):
        conclusion = (
            "validated_accounts:\n"
            "- twitter | alice | https://x.com/alice | 同一人\n"
            "excluded_accounts:\n"
            "- github | alice-dev | https://github.com/alice-dev | 无关同名\n"
        )
        self.assertEqual(
            "validated",
            _v3_identity_verdict(
                conclusion,
                account_id="alice",
                account_handle="alice",
                profile_url="https://x.com/alice",
            ),
        )
        self.assertEqual(
            "rejected",
            _v3_identity_verdict(
                conclusion,
                account_id="alice-dev",
                account_handle="alice-dev",
                profile_url="https://github.com/alice-dev",
            ),
        )

    def test_current_docx_report_template_is_accepted(self):
        self.assertTrue(
            report_parser.is_final_report(self._current_template_report())
        )

    def test_current_docx_report_missing_fixed_item_is_rejected(self):
        self.assertFalse(
            report_parser.is_final_report(
                self._current_template_report(include_economy=False)
            )
        )


if __name__ == "__main__":
    unittest.main()
