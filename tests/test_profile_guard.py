"""외부 API나 실제 계정 없이 실행하는 회귀 테스트."""
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from profile_guard import MAX_BYTES, audit_profile, main

SVG = '<svg xmlns="http://www.w3.org/2000/svg"><circle><animate attributeName="opacity" values="0;1;0" dur="2s" repeatCount="indefinite"/></circle></svg>'


class ProfileGuardTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "card.svg").write_text(SVG, encoding="utf-8")
        self.write('<div align="center"><img src="./card.svg" alt="카드"></div>')

    def write(self, text):
        (self.root / "README.md").write_text(text, encoding="utf-8")

    def result(self, expected=None):
        return audit_profile(self.root, expected)

    def test_animated_card_passes(self):
        self.assertTrue(self.result(1)["ok"])
        self.assertFalse(self.result()["browser_animation_verified"])

    def test_does_not_modify_files(self):
        before = {p.name: p.read_bytes() for p in self.root.iterdir()}
        self.result()
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.root.iterdir()})

    def test_static_text_fails(self):
        self.write('<img src="card.svg" alt="카드">추가 소개문')
        self.assertFalse(self.result()["ok"])

    def test_markdown_heading_fails(self):
        self.write('# 수상 경력\n<img src="card.svg" alt="카드">')
        self.assertFalse(self.result()["ok"])

    def test_comments_and_whitespace_pass(self):
        self.write('<!-- 보이지 않는 메모 -->\n<br><img src="card.svg" alt="카드"/>\n')
        self.assertTrue(self.result()["ok"])

    def test_missing_readme_fails(self):
        (self.root / "README.md").unlink()
        self.assertFalse(self.result()["ok"])

    def test_missing_image_fails(self):
        (self.root / "card.svg").unlink()
        self.assertFalse(self.result()["ok"])

    def test_non_animated_svg_fails(self):
        (self.root / "card.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg"/>')
        self.assertFalse(self.result()["ok"])

    def test_wrong_svg_namespace_fails(self):
        (self.root / "card.svg").write_text('<svg><animate/></svg>')
        self.assertFalse(self.result()["ok"])

    def test_css_animation_detected(self):
        (self.root / "card.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg"><style>@keyframes pulse {to {opacity:0}}</style></svg>')
        self.assertEqual(self.result()["images"][0]["animation_evidence"], ["css-keyframes"])

    def test_invalid_xml_fails(self):
        (self.root / "card.svg").write_text('<svg>')
        self.assertFalse(self.result()["ok"])

    def test_dtd_rejected(self):
        (self.root / "card.svg").write_text('<!DOCTYPE svg>' + SVG)
        self.assertFalse(self.result()["ok"])

    def test_remote_images_rejected(self):
        for source in ('https://example.com/card.svg', '//example.com/card.svg', 'data:image/svg+xml,test'):
            with self.subTest(source=source):
                self.write(f'<img src="{source}" alt="카드">')
                self.assertFalse(self.result()["ok"])

    def test_escaping_path_rejected(self):
        for source in ('../outside.svg', '%2E%2E/outside.svg', '%5Coutside.svg'):
            with self.subTest(source=source):
                self.write(f'<img src="{source}" alt="카드">')
                self.assertFalse(self.result()["ok"])

    def test_absolute_image_path_rejected(self):
        source = (self.root / "card.svg").as_posix()
        self.write(f'<img src="{source}" alt="카드">')
        self.assertFalse(self.result()["ok"])

    def test_symlink_escape_rejected(self):
        with tempfile.TemporaryDirectory() as other:
            target = Path(other) / 'outside.svg'
            target.write_text(SVG)
            link = self.root / 'linked.svg'
            try:
                link.symlink_to(target)
            except (OSError, NotImplementedError):
                self.skipTest('이 환경에서는 심볼릭 링크를 만들 수 없습니다.')
            self.write('<img src="linked.svg" alt="카드">')
            self.assertFalse(self.result()["ok"])

    def test_png_rejected(self):
        (self.root / 'card.png').write_text(SVG)
        self.write('<img src="card.png" alt="카드">')
        self.assertFalse(self.result()["ok"])

    def test_missing_alt_fails(self):
        self.write('<img src="card.svg">')
        self.assertFalse(self.result()["ok"])

    def test_count_mismatch_fails(self):
        self.assertFalse(self.result(6)["ok"])

    def test_empty_document_fails(self):
        self.write('')
        self.assertFalse(self.result()["ok"])

    def test_extra_html_tag_fails(self):
        self.write('<h1></h1><img src="card.svg" alt="카드">')
        self.assertFalse(self.result()["ok"])

    def test_oversize_svg_fails(self):
        (self.root / "card.svg").write_bytes(b' ' * (MAX_BYTES + 1))
        self.assertFalse(self.result()["ok"])

    def test_invalid_utf8_fails(self):
        (self.root / "card.svg").write_bytes(b'\xff')
        self.assertFalse(self.result()["ok"])

    def test_invalid_expected_count_raises(self):
        with self.assertRaises(ValueError):
            self.result(0)

    def test_cli_pass_and_fail(self):
        for expected, code in ((1, 0), (6, 1)):
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                self.assertEqual(main([str(self.root), '--expected-images', str(expected)]), code)
            self.assertEqual(json.loads(output.getvalue())["ok"], code == 0)


if __name__ == '__main__':
    unittest.main()
