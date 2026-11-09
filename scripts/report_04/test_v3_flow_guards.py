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

    def test_maigret_parent_is_lit_when_child_running(self):
        store = _FakeStore()
        statuses = {"step2_maigret": "running", "phase_discovery": "pending"}

        def _gst(_task_id, key):
            return statuses.get(key)

        def _set(_task_id, step_key, status, **_kwargs):
            statuses[step_key] = status

        with patch("report_04.sink.get_step_status", side_effect=_gst), \
                patch.object(store, "set_step_status", side_effect=_set):
            from report_04.sink import _ensure_maigret_parent_lit

            _ensure_maigret_parent_lit(store, "task-v3")
        self.assertEqual("running", statuses["phase_discovery"])

    def test_hold_discovery_demotes_maigret_child_and_parent(self):
        store = _FakeStore()
        statuses = {
            "step1_seed": "running",
            "step2_maigret": "running",
            "phase_discovery": "running",
        }

        def _gst(_task_id, key):
            return statuses.get(key)

        def _set(_task_id, step_key, status, **_kwargs):
            statuses[step_key] = status

        with patch("report_04.sink.get_step_status", side_effect=_gst), \
                patch.object(store, "set_step_status", side_effect=_set):
            from report_04.sink import _hold_discovery_until_seed

            _hold_discovery_until_seed(store, "task-v3")
        self.assertEqual("pending", statuses["step2_maigret"])
        self.assertEqual("pending", statuses["phase_discovery"])

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
        # soft 收口：单缺「经济状况」仍可过；大面积缺二级项才拒收
        thin = (
            self._current_template_report()
            .replace("（一）教育经历\n未核实。\n", "")
            .replace("（二）工作经历\n未核实。\n", "")
            .replace("（三）性格特点\n未核实，未作推断。\n", "")
            .replace("（四）家庭成员情况\n未核实。\n", "")
            .replace("（五）经济状况\n未获取可核实信息。\n", "")
        )
        self.assertFalse(report_parser.is_final_report(thin))

    def test_abbreviated_subsection_titles_are_accepted(self):
        """二级标题常见缩写（家庭成员/工作单位）允许入库。"""
        report = (
            self._current_template_report()
            .replace("（四）家庭成员情况", "（四）家庭成员")
            .replace("（一）工作单位基本情况", "（一）工作单位")
        )
        self.assertTrue(report_parser.follows_current_report_template_soft(report))
        self.assertTrue(report_parser.is_final_report(report))
        self.assertFalse(report_parser.follows_current_report_template(report))

    def test_named_header_and_optional_photo_are_preserved(self):
        report = self._current_template_report().replace(
            "测试人物 公开资料核查报告\n",
            "# 测试人物 公开资料核查报告\n"
            "（原名：Test Person）\n"
            "![测试人物本人照片](https://example.com/person.jpg)\n"
            "照片来源：官方人物页｜https://example.com/profile\n",
            1,
        )
        self.assertTrue(report_parser.is_final_report(report))
        self.assertTrue(
            report_parser.prepare_final_report_body(report).startswith(
                "# 测试人物 公开资料核查报告"
            )
        )

    def test_generic_header_or_photo_placeholder_is_rejected(self):
        generic = self._current_template_report().replace(
            "测试人物 公开资料核查报告",
            "公开资料核查报告",
            1,
        )
        self.assertFalse(report_parser.is_final_report(generic))
        placeholder = self._current_template_report().replace(
            "测试人物 公开资料核查报告\n",
            "测试人物 公开资料核查报告\n照片来源：暂无照片\n",
            1,
        )
        self.assertFalse(report_parser.is_final_report(placeholder))

    def test_web_coverage_classifier_uses_template_topics(self):
        topics = sink._classify_web_coverage_topics(
            {
                "query": (
                    '"Test Person" education university family spouse '
                    'income net worth personality biography'
                )
            },
            "结果中即使出现 politics 也不应误归类",
        )
        self.assertEqual(["basic"], topics)
        politics = sink._classify_web_coverage_topics(
            {"query": '"Test Person" China US political views policy'},
            "",
        )
        self.assertEqual(["politics"], politics)

    def test_web_coverage_update_records_sources_and_missing_groups(self):
        store = _FakeStore()
        with patch.object(sink, "_load_web_coverage", return_value={}), \
                patch.object(sink, "get_step_status", return_value="running"):
            sink._update_web_coverage(
                store,
                "task-v3",
                tool_name="web_search",
                tool_args={
                    "query": '"Test Person" education family income biography'
                },
                tool_output='{"url":"https://example.com/profile","title":"Profile"}',
            )
        payload = store.status_calls[-1][3]["payload"]
        self.assertEqual(
            "evidence_found",
            payload["template_coverage"]["basic"]["status"],
        )
        self.assertIn(
            "https://example.com/profile",
            payload["template_coverage"]["basic"]["sources"],
        )
        self.assertFalse(payload["coverage_complete"])

    def test_ab_budget_is_expanded_for_template_coverage(self):
        with patch("report_04.intake.is_person_path", return_value=False):
            from report_04.intake import bump_osint_budget_for_person

            self.assertEqual((8, 12, 480), bump_osint_budget_for_person("task-v3"))

    def test_extract_account_id_from_linkedin_target_urls(self):
        from collect_01.normalizers.base import account_id_from_tool_args

        self.assertEqual(
            "catarina-cottinelli-da-costa-952596a5",
            account_id_from_tool_args(
                {
                    "targetUrls": [
                        "https://www.linkedin.com/in/catarina-cottinelli-da-costa-952596a5"
                    ]
                }
            ),
        )
        self.assertIsNone(
            account_id_from_tool_args({"datasetId": "iiNFICqGrlttmodYi", "limit": 30})
        )
        self.assertEqual(
            "alice",
            account_id_from_tool_args({"screen_name": "alice"}),
        )

    def test_first_str_unwraps_media_dict_and_clips_avatar(self):
        from collect_01.normalizers.base import first_str, profile_row

        url = (
            "https://media.licdn.com/dms/image/v2/D5603AQHa5d6DY7mLRQ/"
            "profile-displayphoto-crop_800_800/B56ZuSQAarGsAI-/0/1767685228784"
            "?e=1795651200&v=beta&t=2MQddDBJ0mmygy-234pIcMMYNI-TnH1DbuV2SfOgugo"
        )
        self.assertEqual(url, first_str({"url": url, "sizes": [{"url": "x"}]}))
        self.assertNotIn("{", first_str({"url": url}) or "")
        row = profile_row(
            {"task_id": "t1", "tool_output_id": 1},
            platform="linkedin",
            account_id="ACoA",
            avatar_url={"url": url + ("x" * 600), "sizes": []},
            profile_url="https://www.linkedin.com/in/demo",
        )
        self.assertTrue(str(row["avatar_url"]).startswith("https://"))
        self.assertLessEqual(len(row["avatar_url"]), 512)
        self.assertNotIn("sizes", str(row["avatar_url"]))

    def test_linkedin_profile_picture_object_becomes_url(self):
        from collect_01.normalizers import apify

        items = [
            {
                "id": "ACoAABZVUs4B6iEFBV809kPH8F0NL7imon9PeXA",
                "publicIdentifier": "catarina-cottinelli-da-costa-952596a5",
                "firstName": "Catarina",
                "lastName": "Cottinelli",
                "headline": "Director",
                "profilePicture": {
                    "url": (
                        "https://media.licdn.com/dms/image/v2/D5603AQHa5d6DY7mLRQ/"
                        "profile-displayphoto-crop_800_800/x"
                    ),
                    "sizes": [{"url": "https://example.com/small.jpg"}],
                },
            }
        ]
        ctx = {"task_id": "task-li-avatar", "tool_output_id": 1}
        profiles, _posts = apify._linkedin_items(ctx, items)
        self.assertEqual(1, len(profiles))
        self.assertTrue(str(profiles[0]["avatar_url"]).startswith("https://media.licdn.com/"))
        self.assertLessEqual(len(profiles[0]["avatar_url"]), 512)

    def test_linkedin_posts_use_ctx_account_when_author_fields_stripped(self):
        from collect_01.normalizers import apify

        items = [
            {
                "type": "post",
                "content": "Congresso do Meio Milénio de Camões",
                "postedAt.date": "2024-02-23T05:29:59.422Z",
                "shareLinkedinUrl": (
                    "https://www.linkedin.com/feed/update/"
                    "urn:li:ugcPost:7166665474037039104"
                ),
                "engagement.likes": 17,
                "engagement.comments": 2,
            }
        ]
        ctx = {
            "task_id": "task-linkedin-unknown",
            "account_id": "catarina-cottinelli-da-costa-952596a5",
        }
        with patch("collect_01.db.fetch_one", return_value=None):
            _profiles, posts = apify._linkedin_items(ctx, items)
        self.assertEqual(1, len(posts))
        self.assertEqual(
            "catarina-cottinelli-da-costa-952596a5",
            posts[0]["account_id"],
        )
        self.assertEqual(
            "urn:li:ugcPost:7166665474037039104",
            posts[0]["content_id"],
        )
        self.assertTrue(str(posts[0].get("content_url") or "").endswith(
            "urn:li:ugcPost:7166665474037039104"
        ))

    def test_linkedin_posts_prefer_seed_profile_account_id(self):
        from collect_01.normalizers import apify

        items = [{"type": "post", "content": "hello from macau"}]
        ctx = {
            "task_id": "task-linkedin-profile",
            "account_id": "catarina-cottinelli-da-costa-952596a5",
        }
        with patch(
            "collect_01.db.fetch_one",
            return_value={
                "account_id": "ACoAABZVUs4B6iEFBV809kPH8F0NL7imon9PeXA",
                "account_handle": "catarina-cottinelli-da-costa-952596a5",
            },
        ):
            _profiles, posts = apify._linkedin_items(ctx, items)
        self.assertEqual(1, len(posts))
        self.assertEqual(
            "ACoAABZVUs4B6iEFBV809kPH8F0NL7imon9PeXA",
            posts[0]["account_id"],
        )

    def test_linkedin_posts_read_dotted_author_keys(self):
        from collect_01.normalizers import apify

        items = [
            {
                "type": "post",
                "content": "hello",
                "author.publicIdentifier": "other-person-123",
                "author.id": "ACoAOTHER",
            }
        ]
        ctx = {"task_id": "task-linkedin-dotted"}
        with patch("collect_01.db.fetch_one", return_value=None), \
                patch("collect_01.db.fetch_all", return_value=[]):
            _profiles, posts = apify._linkedin_items(ctx, items)
        self.assertEqual(1, len(posts))
        # 无被采主页时才保留条目作者
        self.assertEqual("other-person-123", posts[0]["account_id"])

    def test_linkedin_profile_posts_force_seed_account_even_if_repost(self):
        from collect_01.normalizers import apify

        items = [
            {
                "type": "post",
                "content": "company share on timeline",
                "author.publicIdentifier": "atelier-daciano-da-costa",
                "author.universalName": "atelier-daciano-da-costa",
            }
        ]
        ctx = {
            "task_id": "task-linkedin-repost",
            "account_id": "catarina-cottinelli-da-costa-952596a5",
        }
        with patch(
            "collect_01.db.fetch_one",
            return_value={
                "account_id": "ACoAABZVUs4B6iEFBV809kPH8F0NL7imon9PeXA",
                "account_handle": "catarina-cottinelli-da-costa-952596a5",
            },
        ):
            _profiles, posts = apify._linkedin_items(ctx, items)
        self.assertEqual(1, len(posts))
        self.assertEqual(
            "ACoAABZVUs4B6iEFBV809kPH8F0NL7imon9PeXA",
            posts[0]["account_id"],
        )

if __name__ == "__main__":
    unittest.main()
