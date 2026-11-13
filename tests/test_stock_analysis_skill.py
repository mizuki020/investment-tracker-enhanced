#!/usr/bin/env python3
"""Static contract checks for the stock-analysis Codex skill."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / ".agents/skills/stock-analysis-triad/SKILL.md"

HEADINGS = [
    "① 議題の定義", "② 三知性体の独立分析",
    "③ 合意点", "④ 相違点", "⑤ 反証",
    "⑥ ブレーンストーミング", "⑦ 行動トリガー",
    "⑧ 共同結論", "⑨ 第六感コメント",
]
PERSONAS = ["ラファエル：構造分析", "リュミエル：短期シグナル", "クラリタ：材料・外部環境"]
TRIGGERS = ["買い条件", "見送り条件", "撤退条件"]

class SkillContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = SKILL.read_text(encoding="utf-8")

    def test_frontmatter(self):
        self.assertTrue(self.text.startswith("---\n"))
        self.assertRegex(self.text, r"(?m)^name: stock-analysis-triad$")
        self.assertRegex(self.text, r"(?m)^description: .+")

    def test_nine_sections_in_order(self):
        positions = []
        for title in HEADINGS:
            match = re.search(r"(?m)^## " + re.escape(title) + r"$", self.text)
            self.assertIsNotNone(match, title)
            positions.append(match.start())
        self.assertEqual(positions, sorted(positions))

    def test_three_personas_and_triggers(self):
        for title in PERSONAS + TRIGGERS:
            self.assertIn("### " + title, self.text)

    def test_no_order_execution(self):
        self.assertIn("注文送信", self.text)
        self.assertIn("行わない", self.text)

    def test_missing_data_handling(self):
        self.assertIn("未確認", self.text)
        self.assertIn("出典", self.text)

if __name__ == "__main__":
    unittest.main()
