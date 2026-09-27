import unittest

from app.provenance import infer_document_provenance


class DocumentProvenanceTests(unittest.TestCase):
    def test_extracts_jurisdiction_and_revision_from_title_page(self):
        text = "August 20, 2024, Rev. Page 1\nUnion City, Georgia \nZoning Ordinance"
        self.assertEqual(infer_document_provenance([text]), {
            "jurisdiction": "Union City, Georgia",
            "version": "August 20, 2024, Rev.",
        })

    def test_extracts_supplement_version_and_marks_missing_version_unknown(self):
        charleston = "SUPPLEMENT NO. 25\nNovember 2025\nZONING CODE\nCity of\nCHARLESTON, SOUTH CAROLINA"
        self.assertEqual(infer_document_provenance([charleston]), {
            "jurisdiction": "Charleston, South Carolina",
            "version": "Supplement No. 25, November 2025",
        })
        urbana = "The Urbana Zoning Ordinance permits such uses."
        self.assertEqual(infer_document_provenance([urbana]), {"jurisdiction": "Urbana"})

    def test_table_cell_that_looks_like_place_name_is_not_a_jurisdiction(self):
        table = "Generalized Summary of\nZoning Regulations\nAccessory Living\nQuarters, Home \nOccupations"
        self.assertNotIn("jurisdiction", infer_document_provenance([table]))


if __name__ == "__main__":
    unittest.main()
