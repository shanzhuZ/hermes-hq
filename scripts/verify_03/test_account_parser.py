# -*- coding: utf-8 -*-
"""核查步骤1 种子账号解析：放宽规则 + 语义邻近。"""

import unittest

from verify_03 import account_parser as ap


class AccountParserTest(unittest.TestCase):
    def test_user_oral_twitter_at(self):
        msg = "account-intelligence-verification 账号核查推特用户 @elonmusk"
        got = ap.parse_input_accounts(user_message=msg, assistant_text="")
        self.assertEqual(1, len(got))
        self.assertEqual("twitter", got[0]["platform"])
        self.assertEqual("elonmusk", got[0]["account_handle"])

    def test_assistant_kv_list(self):
        text = (
            "步骤1。执行种子账号接收与确认环节\n\n"
            "本次核查的种子账号如下：\n"
            "- 平台：twitter（推特）\n"
            "- 用户名：@elonmusk\n\n"
            "共 1 个种子账号，仅此一个平台。现进入步骤2。"
        )
        self.assertTrue(ap.looks_like_step1_confirmation(text))
        got = ap.parse_input_accounts(user_message="", assistant_text=text)
        self.assertEqual(1, len(got))
        self.assertEqual("twitter", got[0]["platform"])
        self.assertEqual("elonmusk", got[0]["account_handle"])

    def test_confirm_block(self):
        text = "[种子账号确认]\ntwitter | elonmusk\nweibo | foo_bar\n[/种子账号确认]"
        got = ap.parse_from_confirm_block(text)
        self.assertEqual(
            [("twitter", "elonmusk"), ("weibo", "foo_bar")],
            [(x["platform"], x["account_handle"]) for x in got],
        )

    def test_legacy_colon_pair(self):
        msg = "账号核查 推特账号：whyyoutouzhele"
        got = ap.parse_from_user_message(msg)
        self.assertEqual("twitter", got[0]["platform"])
        self.assertEqual("whyyoutouzhele", got[0]["account_handle"])

    def test_url_twitter(self):
        got = ap.parse_from_urls("主页 https://x.com/elonmusk 请核查")
        self.assertEqual(1, len(got))
        self.assertEqual(("twitter", "elonmusk"), (got[0]["platform"], got[0]["account_handle"]))

    def test_semantic_nearby(self):
        text = "种子账号如下\n平台 twitter\n请确认 @elonmusk 为唯一种子"
        self.assertTrue(ap.looks_like_step1_confirmation(text))
        got = ap.extract_accounts_semantic(text)
        self.assertTrue(any(x["platform"] == "twitter" and x["account_handle"] == "elonmusk" for x in got))

    def test_merge_user_and_assistant(self):
        u = "account-intelligence-verification 账号核查推特用户 @elonmusk"
        a = "步骤1。确认种子\n- 平台：twitter\n- 用户名：@elonmusk"
        got = ap.parse_input_accounts(user_message=u, assistant_text=a)
        self.assertEqual(1, len(got))


if __name__ == "__main__":
    unittest.main()
