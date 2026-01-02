import unittest
import os
import sys
from PyPDF2 import PdfReader

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

class TestPDFDatasheets(unittest.TestCase):
    """Tests for PDF technical datasheet generation."""
    
    @classmethod
    def setUpClass(cls):
        """Setup test fixtures."""
        cls.pdf_dir = os.path.join("output", "datasheets", "pieces")
        cls.expected_piece_count = 58
        
    def test_output_directory_exists(self):
        """Verify that the output directory was created."""
        self.assertTrue(os.path.exists(self.pdf_dir), 
                       f"Output directory '{self.pdf_dir}' does not exist")
    
    def test_all_pdfs_generated(self):
        """Verify that all 58 PDFs were generated."""
        if not os.path.exists(self.pdf_dir):
            self.skipTest("Output directory does not exist")
        
        pdf_files = [f for f in os.listdir(self.pdf_dir) if f.endswith('.pdf')]
        self.assertEqual(len(pdf_files), self.expected_piece_count,
                        f"Expected {self.expected_piece_count} PDFs, found {len(pdf_files)}")
    
    def test_pdf_file_sizes_valid(self):
        """Verify that all PDFs have reasonable file sizes (>10KB, <1MB)."""
        if not os.path.exists(self.pdf_dir):
            self.skipTest("Output directory does not exist")
        
        pdf_files = [f for f in os.listdir(self.pdf_dir) if f.endswith('.pdf')]
        
        for pdf_file in pdf_files:
            filepath = os.path.join(self.pdf_dir, pdf_file)
            size = os.path.getsize(filepath)
            
            # PDFs should be between 10KB and 1MB
            self.assertGreater(size, 10 * 1024, 
                             f"{pdf_file} is too small ({size} bytes), likely corrupt")
            self.assertLess(size, 1024 * 1024,
                           f"{pdf_file} is too large ({size} bytes), unexpected")
    
    def test_sample_pdfs_are_valid(self):
        """Verify that sample PDFs can be read and are not corrupt."""
        if not os.path.exists(self.pdf_dir):
            self.skipTest("Output directory does not exist")
        
        # Test a few representative PDFs
        sample_pdfs = [
            'piston_puissance.pdf',
            'vilebrequin_corps.pdf',
            'paliers_bielle_maneton.pdf',
            'joint_tournant_arbre_sortie.pdf'
        ]
        
        for pdf_name in sample_pdfs:
            filepath = os.path.join(self.pdf_dir, pdf_name)
            
            if not os.path.exists(filepath):
                self.fail(f"Sample PDF '{pdf_name}' not found")
            
            try:
                reader = PdfReader(filepath)
                
                # PDF should have at least 1 page
                self.assertGreaterEqual(len(reader.pages), 1,
                                       f"{pdf_name} has no pages")
                
                # Try to extract text from first page (basic integrity check)
                page = reader.pages[0]
                text = page.extract_text()
                
                # Should contain the piece name marker
                self.assertIn("FICHE TECHNIQUE", text,
                            f"{pdf_name} missing header text")
                
            except Exception as e:
                self.fail(f"Failed to read {pdf_name}: {e}")
    
    def test_specific_pieces_exist(self):
        """Verify that critical piece PDFs exist."""
        critical_pieces = [
            'cylindre_chemise.pdf',
            'piston_puissance.pdf',
            'bielle_corps.pdf',
            'vilebrequin_corps.pdf',
            'arbre_sortie_portee_sortie.pdf',
            'carter_bati.pdf'
        ]
        
        for pdf_name in critical_pieces:
            filepath = os.path.join(self.pdf_dir, pdf_name)
            self.assertTrue(os.path.exists(filepath),
                          f"Critical piece PDF '{pdf_name}' does not exist")
    
    def test_pdf_metadata_present(self):
        """Verify that PDFs contain proper metadata."""
        if not os.path.exists(self.pdf_dir):
            self.skipTest("Output directory does not exist")
        
        sample_pdf = os.path.join(self.pdf_dir, 'piston_puissance.pdf')
        
        if not os.path.exists(sample_pdf):
            self.skipTest("Sample PDF not found")
        
        try:
            reader = PdfReader(sample_pdf)
            
            # Verify PDF has metadata
            self.assertIsNotNone(reader.metadata, "PDF metadata is missing")
            
        except Exception as e:
            self.fail(f"Failed to read PDF metadata: {e}")

class TestPDFContent(unittest.TestCase):
    """Tests for PDF content structure."""
    
    def test_piston_pdf_contains_specifications(self):
        """Verify that piston PDF contains expected specifications."""
        pdf_path = os.path.join("output", "datasheets", "pieces", "piston_puissance.pdf")
        
        if not os.path.exists(pdf_path):
            self.skipTest("Piston PDF not found")
        
        try:
            reader = PdfReader(pdf_path)
            text = ""
            for page in reader.pages:
                text += page.extract_text()
            
            # Check for expected sections
            self.assertIn("SPÉCIFICATIONS TECHNIQUES", text,
                         "Missing specifications section")
            self.assertIn("RÉSISTANCES MÉCANIQUES", text,
                         "Missing resistance section")
            
        except Exception as e:
            self.fail(f"Failed to verify PDF content: {e}")

if __name__ == '__main__':
    # Run tests with verbose output
    unittest.main(verbosity=2)
