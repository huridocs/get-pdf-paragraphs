import json
import os
import shutil

import mongomock as mongomock
import pymongo as pymongo
from fastapi.testclient import TestClient
from unittest import TestCase
from app import app
from data.ExtractionData import ExtractionData

client = TestClient(app)


class TestApp(TestCase):
    def test_info(self):
        response = client.get("/info")
        self.assertEqual(200, response.status_code)

    def test_error(self):
        response = client.get("/error")
        self.assertEqual(500, response.status_code)
        self.assertEqual(
            {"detail": "This is a test error from the error endpoint"}, response.json()
        )

    def test_async_extraction(self):
        tenant = "tenant_add_task"

        shutil.rmtree(f"../docker_volume/to_extract/{tenant}", ignore_errors=True)

        with open("./test_files/test.pdf", "rb") as stream:
            files = {"file": stream}
            response = client.post(f"/async_extraction/{tenant}", files=files)

        self.assertEqual(200, response.status_code)
        self.assertTrue(
            os.path.exists(f"../docker_volume/to_extract/{tenant}/test.pdf")
        )

        shutil.rmtree(f"../docker_volume/to_extract/{tenant}", ignore_errors=True)

    def test_extract_paragraphs(self):
        with open("./test_files/test.pdf", "rb") as stream:
            files = {"file": stream}
            response = client.get("/", files=files)

        segments_boxes = json.loads(response.json())
        pages = [
            segment_box["page_number"] for segment_box in segments_boxes["paragraphs"]
        ]

        self.assertEqual(200, response.status_code)
        self.assertLess(15, len(segments_boxes["paragraphs"]))
        self.assertEqual("A/INF/76/1", segments_boxes["paragraphs"][0]["text"])
        self.assertEqual(612, segments_boxes["page_width"])
        self.assertEqual(792, segments_boxes["page_height"])
        self.assertEqual(1, min(pages))
        self.assertEqual(2, max(pages))

    @mongomock.patch(servers=["mongodb://127.0.0.1:28017"])
    def test_get_paragraphs_from_db(self):
        mongo_client = pymongo.MongoClient("mongodb://127.0.0.1:28017")
        tenant = "tenant_to_get_paragraphs"
        pdf_file_name = "pdf_file_name.pdf"
        json_data = [
            {
                "tenant": "wrong tenant",
                "file_name": "wrong tenant",
                "paragraphs": [],
            },
            {
                "tenant": tenant,
                "file_name": pdf_file_name,
                "paragraphs": [
                    {
                        "left": 1,
                        "top": 2,
                        "width": 3,
                        "height": 4,
                        "page_number": 5,
                        "text": "1",
                    },
                    {
                        "left": 6,
                        "top": 7,
                        "width": 8,
                        "height": 9,
                        "page_number": 10,
                        "text": "2",
                    },
                ],
                "page_height": 1,
                "page_width": 2,
            },
            {
                "tenant": "wrong tenant_2",
                "file_name": "wrong tenant",
                "paragraphs": [],
            },
        ]

        mongo_client.pdf_paragraph.paragraphs.insert_many(json_data)

        response = client.get(f"/get_paragraphs/{tenant}/{pdf_file_name}")

        extraction_data = ExtractionData(**json.loads(response.json()))

        self.assertEqual(200, response.status_code)
        self.assertEqual(tenant, extraction_data.tenant)
        self.assertEqual(pdf_file_name, extraction_data.file_name)
        self.assertEqual(2, len(extraction_data.paragraphs))
        self.assertEqual(1, extraction_data.page_height)
        self.assertEqual(2, extraction_data.page_width)
        self.assertEqual(
            [1, 2, 3, 4, 5, "1"], list(extraction_data.paragraphs[0].dict().values())
        )
        self.assertEqual(
            [6, 7, 8, 9, 10, "2"], list(extraction_data.paragraphs[1].dict().values())
        )
        self.assertIsNone(
            mongo_client.pdf_paragraph.paragraphs.find_one(
                {"tenant": tenant, "pdf_file_name": pdf_file_name}
            )
        )

    @mongomock.patch(servers=["mongodb://127.0.0.1:28017"])
    def test_get_paragraphs_when_no_data(self):
        tenant = "tenant_to_get_paragraphs"
        pdf_file_name = "pdf_file_name"

        response = client.get(f"/get_paragraphs/{tenant}/{pdf_file_name}")

        self.assertEqual(404, response.status_code)

    def test_get_xml(self):
        tenant = "tenant_to_get_paragraphs"
        xml_file_name = "test.xml"
        pdf_file_name = "test.pdf"

        shutil.rmtree(f"../docker_volume/xml/{tenant}", ignore_errors=True)
        os.makedirs(f"../docker_volume/xml/{tenant}")
        shutil.copyfile(
            "./test_files/test.xml", f"../docker_volume/xml/{tenant}/{xml_file_name}"
        )

        response = client.get(f"/get_xml/{tenant}/{pdf_file_name}")

        self.assertEqual(200, response.status_code)
        self.assertIsNotNone(response.content)
        self.assertEqual(
            "text/plain; charset=utf-8", response.headers.get("content-type")
        )
        self.assertFalse(
            os.path.exists(f"../docker_volume/xml/{tenant}/{xml_file_name}")
        )

        shutil.rmtree(f"../docker_volume/xml/{tenant}", ignore_errors=True)

    def test_get_xml_when_no_xml(self):
        tenant = "tenant_to_get_paragraphs"
        pdf_file_name = "test.pdf"

        response = client.get(f"/get_xml/{tenant}/{pdf_file_name}")

        self.assertEqual(404, response.status_code)