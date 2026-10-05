"""Inline styles: they must take effect (the satellite C/N0 bars rendered empty)
and must not be blocked by the Content-Security-Policy of the page they are on.

Two separate ways an inline `style="width:..."` can fail:
  1. width/height on an element that is `display: inline` is ignored by CSS.
     That was the C/N0 bar bug: <i class="barfill" style="width:72%"> with no
     display in its rule.
  2. a CSP without 'unsafe-inline' in style-src drops style attributes. The
     legacy pages build style attributes in HTML strings, so their CSP must keep
     it; /app/ is strict, so its code must never build style attributes.
"""

import re
import unittest
from pathlib import Path

from tests import _env  # noqa: F401
from gps_time_pi import security

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "gps_time_pi" / "static"
TEMPLATES = ROOT / "gps_time_pi" / "templates"
LEGACY_SOURCES = sorted(STATIC.glob("*.js")) + sorted(TEMPLATES.glob("*.html"))
INLINE_TAGS = "i|span|b|em|small|strong|a|u|label|code"
SIZED_INLINE = re.compile(rf"<({INLINE_TAGS})\b([^>]*?)style=\"([^\"]*\b(?:width|height)\s*:[^\"]*)\"", re.S)
BOXED = re.compile(r"display\s*:\s*(block|inline-block|flex|inline-flex|grid|inline-grid)")


def css_rules():
    text = "\n".join(p.read_text(encoding="utf-8") for p in sorted(STATIC.glob("*.css")))
    rules = {}
    for selectors, body in re.findall(r"([^{}]+)\{([^{}]*)\}", text):
        for sel in selectors.split(","):
            m = re.fullmatch(r"\s*\.([A-Za-z0-9_-]+)\s*", sel)
            if m:
                rules.setdefault(m.group(1), []).append(body)
    return rules


class TestSizedInlineElements(unittest.TestCase):
    def test_every_inline_element_given_a_size_can_take_one(self):
        rules = css_rules()
        found = 0
        for path in LEGACY_SOURCES:
            for tag, attrs, style in SIZED_INLINE.findall(path.read_text(encoding="utf-8")):
                found += 1
                if BOXED.search(style):
                    continue
                classes = (re.search(r'class="([^"]*)"', attrs) or [None, ""])[1].split()
                boxed = any(BOXED.search(body) for c in classes for body in rules.get(c, []))
                self.assertTrue(boxed, f"{path.name}: <{tag} class=\"{' '.join(classes)}\" style=\"{style}\"> is "
                                       "display:inline, so its width/height is ignored; give its class a display")
        self.assertGreaterEqual(found, 2, "the scan should see the satellite bars")

    def test_satellite_bar_fill_is_a_block(self):
        fills = css_rules().get("barfill")
        self.assertTrue(fills and any(BOXED.search(b) for b in fills))
        js = (STATIC / "dashboard.js").read_text(encoding="utf-8")
        self.assertIn('<i class="barfill" style="width:${Math.min(100,(s.snr||0)*2)}%"></i>', js)


class TestCspAllowsWhatThePagesUse(unittest.TestCase):
    def test_legacy_pages_that_use_style_attributes_are_served_a_csp_that_allows_them(self):
        js_uses_style = any('style="' in p.read_text(encoding="utf-8") for p in STATIC.glob("*.js"))
        checked = 0
        for tpl in sorted(TEMPLATES.glob("*.html")):
            html = tpl.read_text(encoding="utf-8")
            if 'style="' in html or (js_uses_style and "<script" in html):
                csp = security.csp_for_html(html)
                style_src = re.search(r"style-src[^;]*", csp).group(0)
                self.assertIn("'unsafe-inline'", style_src, tpl.name)
                checked += 1
        self.assertGreaterEqual(checked, 5)

    def test_scripts_never_get_unsafe_inline(self):
        for tpl in sorted(TEMPLATES.glob("*.html")):
            script_src = re.search(r"script-src[^;]*", security.csp_for_html(tpl.read_text(encoding="utf-8"))).group(0)
            self.assertNotIn("unsafe-inline", script_src, tpl.name)

    def test_strict_csp_for_the_new_ui_has_no_inline_exception(self):
        self.assertIn("style-src 'self'", security.CSP_STRICT)
        self.assertNotIn("unsafe-inline", security.CSP_STRICT)

    def test_new_ui_never_builds_style_attributes_the_strict_csp_would_drop(self):
        # React's style={{...}} sets properties through the DOM, which a CSP does not
        # block. HTML strings and style attributes would be dropped silently.
        banned = re.compile(r"dangerouslySetInnerHTML|\.innerHTML\b|insertAdjacentHTML|setAttribute\(\s*['\"]style['\"]|\.cssText\b|style=\"")
        offenders = []
        for path in sorted((ROOT / "web" / "src").rglob("*.ts*")):
            if path.name.endswith((".test.ts", ".d.ts")):
                continue
            for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if banned.search(line) and not line.lstrip().startswith(("//", "*", "/*")):
                    offenders.append(f"{path.relative_to(ROOT)}:{n}: {line.strip()[:100]}")
        self.assertEqual(offenders, [])
        index = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
        self.assertNotIn('style="', index)
        self.assertNotRegex(index, r"<style\b")


if __name__ == "__main__":
    unittest.main()
