from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from horbot.agent.context import ContextBuilder


class AttachmentContextTests(unittest.TestCase):
    def test_build_user_content_includes_pdf_text(self):
        with TemporaryDirectory() as tmpdir:
            builder = ContextBuilder(workspace=Path(tmpdir), use_hierarchical=False)
            content = builder._build_user_content(
                "请帮我总结附件",
                media=None,
                files=[{
                    "category": "document",
                    "original_name": "report.pdf",
                    "filename": "report.pdf",
                    "mime_type": "application/pdf",
                    "extracted_text": "这是 PDF 的正文内容。",
                }],
            )

            self.assertIsInstance(content, str)
            self.assertIn("请帮我总结附件", content)
            self.assertIn("PDF文档: report.pdf", content)
            self.assertIn("这是 PDF 的正文内容。", content)

    def test_build_user_content_includes_docx_text(self):
        with TemporaryDirectory() as tmpdir:
            builder = ContextBuilder(workspace=Path(tmpdir), use_hierarchical=False)
            content = builder._build_user_content(
                "请阅读这份文档",
                media=None,
                files=[{
                    "category": "document",
                    "original_name": "brief.docx",
                    "filename": "brief.docx",
                    "mime_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    "extracted_text": "这是 Word 文档里的第一段。",
                }],
            )

            self.assertIsInstance(content, str)
            self.assertIn("请阅读这份文档", content)
            self.assertIn("Word文档: brief.docx", content)
            self.assertIn("这是 Word 文档里的第一段。", content)

    def test_build_user_content_includes_xlsx_and_pptx_text(self):
        with TemporaryDirectory() as tmpdir:
            builder = ContextBuilder(workspace=Path(tmpdir), use_hierarchical=False)
            content = builder._build_user_content(
                "请总结表格和演示文稿",
                media=None,
                files=[
                    {
                        "category": "document",
                        "original_name": "roadmap.xlsx",
                        "filename": "roadmap.xlsx",
                        "mime_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        "extracted_text": "里程碑\t4月上线",
                    },
                    {
                        "category": "document",
                        "original_name": "demo.pptx",
                        "filename": "demo.pptx",
                        "mime_type": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
                        "extracted_text": "第一页：Horbot 规划",
                    },
                ],
            )

            self.assertIsInstance(content, str)
            self.assertIn("Excel表格: roadmap.xlsx", content)
            self.assertIn("里程碑\t4月上线", content)
            self.assertIn("PowerPoint演示文稿: demo.pptx", content)
            self.assertIn("第一页：Horbot 规划", content)


if __name__ == "__main__":
    unittest.main()
