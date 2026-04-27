import contextlib
import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from zipfile import ZIP_DEFLATED, ZipFile

from horbot.agent.skills import SkillsLoader
from horbot.utils import pptx_overflow


def _build_slide_xml(
    *,
    shape_name: str,
    body_texts: list[str],
    width_emu: int,
    height_emu: int,
    font_size: int,
    autofit: str,
) -> str:
    paragraphs = []
    for text in body_texts:
        escaped = (
            text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )
        paragraphs.append(
            f"""
      <a:p>
        <a:pPr><a:lnSpc><a:spcPct val="118000"/></a:lnSpc></a:pPr>
        <a:r><a:rPr lang="en-US" sz="{font_size}"/><a:t>{escaped}</a:t></a:r>
        <a:endParaRPr lang="en-US" sz="{font_size}"/>
      </a:p>"""
        )

    autofit_xml = {
        "noAutofit": "<a:noAutofit/>",
        "normAutofit": '<a:normAutofit fontScale="92000" lnSpcReduction="20000"/>',
        "spAutoFit": "<a:spAutoFit/>",
    }[autofit]

    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sld xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
  <p:cSld>
    <p:spTree>
      <p:sp>
        <p:nvSpPr>
          <p:cNvPr id="2" name="{shape_name}"/>
          <p:cNvSpPr txBox="1"/>
          <p:nvPr><p:ph type="body"/></p:nvPr>
        </p:nvSpPr>
        <p:spPr>
          <a:xfrm>
            <a:off x="914400" y="914400"/>
            <a:ext cx="{width_emu}" cy="{height_emu}"/>
          </a:xfrm>
        </p:spPr>
        <p:txBody>
          <a:bodyPr wrap="square">{autofit_xml}</a:bodyPr>
          <a:lstStyle/>
          {''.join(paragraphs)}
        </p:txBody>
      </p:sp>
    </p:spTree>
  </p:cSld>
</p:sld>
"""


def create_overflow_test_pptx(path: Path, slides: list[dict[str, object]]) -> None:
    overrides = "\n".join(
        f'  <Override PartName="/ppt/slides/slide{index}.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml"/>'
        for index in range(1, len(slides) + 1)
    )
    content_types = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/ppt/presentation.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"/>
{overrides}
</Types>
"""
    rels = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="ppt/presentation.xml"/>
</Relationships>
"""
    slide_ids = "\n".join(
        f'    <p:sldId id="{255 + index}" r:id="rId{index}"/>'
        for index in range(1, len(slides) + 1)
    )
    presentation = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:presentation xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <p:sldSz cx="9144000" cy="6858000"/>
  <p:sldIdLst>
{slide_ids}
  </p:sldIdLst>
</p:presentation>
"""
    presentation_rels = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
""" + "\n".join(
        f'  <Relationship Id="rId{index}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide" Target="slides/slide{index}.xml"/>'
        for index in range(1, len(slides) + 1)
    ) + """
</Relationships>
"""

    with ZipFile(path, "w", ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", content_types)
        archive.writestr("_rels/.rels", rels)
        archive.writestr("ppt/presentation.xml", presentation)
        archive.writestr("ppt/_rels/presentation.xml.rels", presentation_rels)
        for index, slide in enumerate(slides, start=1):
            archive.writestr(
                f"ppt/slides/slide{index}.xml",
                _build_slide_xml(
                    shape_name=str(slide["shape_name"]),
                    body_texts=list(slide["body_texts"]),
                    width_emu=int(slide["width_emu"]),
                    height_emu=int(slide["height_emu"]),
                    font_size=int(slide["font_size"]),
                    autofit=str(slide["autofit"]),
                ),
            )


class PptxOverflowDetectorTests(unittest.TestCase):
    def test_detector_flags_small_dense_body_box(self):
        with TemporaryDirectory() as tmpdir:
            pptx_path = Path(tmpdir) / "overflow-demo.pptx"
            create_overflow_test_pptx(
                pptx_path,
                [
                    {
                        "shape_name": "Summary",
                        "body_texts": ["Short overview paragraph for the first slide."],
                        "width_emu": 5486400,
                        "height_emu": 2743200,
                        "font_size": 2000,
                        "autofit": "normAutofit",
                    },
                    {
                        "shape_name": "Dense Body",
                        "body_texts": [
                            "This paragraph is intentionally long and repeated so the detector sees a crowded text box with too much copy for the available height. " * 2,
                            "Second paragraph keeps the box dense and makes the estimated text height exceed the available area quickly.",
                            "Third paragraph adds even more pressure to the same body shape so the slide should clearly be flagged.",
                        ],
                        "width_emu": 4200000,
                        "height_emu": 900000,
                        "font_size": 2400,
                        "autofit": "noAutofit",
                    },
                ],
            )

            report = pptx_overflow.analyze_pptx_text_overflow(pptx_path, min_score=0.55)

            self.assertEqual(report["slide_count"], 2)
            self.assertEqual(report["suspicious_slide_count"], 1)
            suspicious_slide = report["suspicious_slides"][0]
            self.assertEqual(suspicious_slide["slide_number"], 2)
            self.assertGreaterEqual(suspicious_slide["max_risk_score"], 0.7)
            reasons = suspicious_slide["shapes"][0]["reasons"]
            self.assertIn("estimated_text_height_exceeds_box", reasons)
            self.assertIn("no_autofit", reasons)

    def test_no_autofit_scores_higher_than_norm_autofit_for_same_copy(self):
        with TemporaryDirectory() as tmpdir:
            pptx_path = Path(tmpdir) / "compare-autofit.pptx"
            shared_copy = [
                "Repeated product update text that is long enough to stress a small body box and expose different autofit risk levels. " * 2,
                "Another dense paragraph keeps the example close to the box limit.",
            ]
            create_overflow_test_pptx(
                pptx_path,
                [
                    {
                        "shape_name": "No Autofit",
                        "body_texts": shared_copy,
                        "width_emu": 4200000,
                        "height_emu": 1150000,
                        "font_size": 2200,
                        "autofit": "noAutofit",
                    },
                    {
                        "shape_name": "Norm Autofit",
                        "body_texts": shared_copy,
                        "width_emu": 4200000,
                        "height_emu": 1150000,
                        "font_size": 2200,
                        "autofit": "normAutofit",
                    },
                ],
            )

            report = pptx_overflow.analyze_pptx_text_overflow(
                pptx_path,
                min_score=0.0,
                include_all_shapes=True,
            )
            slide_one_score = report["slides"][0]["shapes"][0]["risk_score"]
            slide_two_score = report["slides"][1]["shapes"][0]["risk_score"]

            self.assertGreater(slide_one_score, slide_two_score)

    def test_cli_json_output_and_builtin_skill_reference_exist(self):
        with TemporaryDirectory() as tmpdir:
            pptx_path = Path(tmpdir) / "cli-demo.pptx"
            create_overflow_test_pptx(
                pptx_path,
                [
                    {
                        "shape_name": "Quick Check",
                        "body_texts": ["Short copy only."],
                        "width_emu": 5486400,
                        "height_emu": 2743200,
                        "font_size": 1800,
                        "autofit": "normAutofit",
                    }
                ],
            )

            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                exit_code = pptx_overflow.main([str(pptx_path), "--json"])

            payload = json.loads(output.getvalue())
            self.assertEqual(exit_code, 0)
            self.assertEqual(payload["slide_count"], 1)

        with TemporaryDirectory() as tmpdir:
            loader = SkillsLoader(workspace=Path(tmpdir))
            content = loader.load_skill("auto-officecli-ppt")

            self.assertIsNotNone(content)
            assert content is not None
            self.assertIn("references/officecli-ppt-structural-overflow-detector.md", content)
            self.assertIn("references/officecli-ppt-render-verification-export.md", content)

    def test_attach_render_verification_reports_unavailable_when_no_renderer_exists(self):
        with TemporaryDirectory() as tmpdir:
            pptx_path = Path(tmpdir) / "no-renderer.pptx"
            create_overflow_test_pptx(
                pptx_path,
                [
                    {
                        "shape_name": "Dense Body",
                        "body_texts": [
                            "This paragraph is intentionally long and repeated so the detector sees a crowded text box with too much copy for the available height. " * 2,
                            "Another paragraph keeps the box dense enough to stay suspicious.",
                        ],
                        "width_emu": 4200000,
                        "height_emu": 900000,
                        "font_size": 2400,
                        "autofit": "noAutofit",
                    },
                ],
            )
            report = pptx_overflow.analyze_pptx_text_overflow(pptx_path, min_score=0.55)
            with patch("horbot.utils.pptx_overflow.detect_render_verification_capabilities") as mocked_caps:
                mocked_caps.return_value = {
                    "available_renderers": [],
                    "preferred_renderer": "",
                    "capabilities": {},
                }
                enriched = pptx_overflow.attach_render_verification(report)

            self.assertEqual(enriched["render_verification"]["status"], "unavailable")
            self.assertIn("No supported PPT renderers", enriched["render_verification"]["reason"])

    def test_export_render_verification_assets_prefers_libreoffice_when_selected(self):
        with TemporaryDirectory() as tmpdir:
            pptx_path = Path(tmpdir) / "render-me.pptx"
            create_overflow_test_pptx(
                pptx_path,
                [
                    {
                        "shape_name": "Body",
                        "body_texts": ["Render me to PDF for review."],
                        "width_emu": 5486400,
                        "height_emu": 2743200,
                        "font_size": 2000,
                        "autofit": "normAutofit",
                    }
                ],
            )
            output_dir = Path(tmpdir) / "rendered"
            output_dir.mkdir(parents=True, exist_ok=True)

            def fake_run(command, check, capture_output, text, timeout):
                self.assertIn("--convert-to", command)
                (output_dir / "render-me.pdf").write_bytes(b"%PDF-1.4\n%fake\n")

                class Result:
                    returncode = 0
                    stdout = "converted"
                    stderr = ""

                return Result()

            with patch("horbot.utils.pptx_overflow.shutil.which") as mocked_which, patch(
                "horbot.utils.pptx_overflow.subprocess.run",
                side_effect=fake_run,
            ):
                mocked_which.side_effect = lambda name: "/usr/local/bin/soffice" if name in {"soffice", "libreoffice"} else None
                result = pptx_overflow.export_render_verification_assets(
                    pptx_path,
                    output_dir=output_dir,
                    renderer="libreoffice",
                    timeout_sec=20,
                )

            self.assertEqual(result["status"], "rendered_pdf")
            self.assertEqual(result["renderer"], "libreoffice")
            self.assertTrue((output_dir / "render-me.pdf").exists())

    def test_export_render_verification_assets_auto_falls_back_to_next_renderer(self):
        with TemporaryDirectory() as tmpdir:
            pptx_path = Path(tmpdir) / "fallback-render.pptx"
            create_overflow_test_pptx(
                pptx_path,
                [
                    {
                        "shape_name": "Body",
                        "body_texts": ["Fallback render path."],
                        "width_emu": 5486400,
                        "height_emu": 2743200,
                        "font_size": 2000,
                        "autofit": "normAutofit",
                    }
                ],
            )
            output_dir = Path(tmpdir) / "rendered"
            output_dir.mkdir(parents=True, exist_ok=True)

            with patch("horbot.utils.pptx_overflow.detect_render_verification_capabilities") as mocked_caps, patch(
                "horbot.utils.pptx_overflow._export_pdf_via_powerpoint",
                side_effect=RuntimeError("powerpoint failed"),
            ), patch(
                "horbot.utils.pptx_overflow._export_pdf_via_keynote",
            ) as mocked_keynote:
                mocked_caps.return_value = {
                    "available_renderers": ["powerpoint", "keynote"],
                    "preferred_renderer": "powerpoint",
                    "capabilities": {},
                }
                mocked_keynote.return_value = {
                    "renderer": "keynote",
                    "pdf_path": str(output_dir / "fallback-render.verification.pdf"),
                    "stdout": "",
                }
                result = pptx_overflow.export_render_verification_assets(
                    pptx_path,
                    output_dir=output_dir,
                    renderer="auto",
                    timeout_sec=20,
                )

            self.assertEqual(result["renderer"], "keynote")
            self.assertEqual(result["attempted_renderers"], ["powerpoint", "keynote"])

    def test_cli_json_output_can_include_render_verification(self):
        with TemporaryDirectory() as tmpdir:
            pptx_path = Path(tmpdir) / "verify-render-cli.pptx"
            create_overflow_test_pptx(
                pptx_path,
                [
                    {
                        "shape_name": "Dense Body",
                        "body_texts": [
                            "This paragraph is intentionally long and repeated so the detector sees a crowded text box with too much copy for the available height. " * 2,
                            "Second paragraph keeps the same slide suspicious for render export.",
                        ],
                        "width_emu": 4200000,
                        "height_emu": 900000,
                        "font_size": 2400,
                        "autofit": "noAutofit",
                    },
                ],
            )

            with patch("horbot.utils.pptx_overflow.attach_render_verification") as mocked_attach:
                mocked_attach.side_effect = lambda report, **kwargs: {
                    **report,
                    "render_verification": {
                        "status": "rendered_pdf",
                        "renderer": "libreoffice",
                        "pdf_path": "/tmp/review.pdf",
                    },
                }
                output = io.StringIO()
                with contextlib.redirect_stdout(output):
                    exit_code = pptx_overflow.main([str(pptx_path), "--json", "--verify-render"])

            payload = json.loads(output.getvalue())
            self.assertEqual(exit_code, 0)
            self.assertEqual(payload["render_verification"]["renderer"], "libreoffice")


if __name__ == "__main__":
    unittest.main()
