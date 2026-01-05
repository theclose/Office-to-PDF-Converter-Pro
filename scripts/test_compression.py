"""
Test script for advanced PDF compression.
Run this to test the new compression engine.
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.pdf_tools import compress_pdf_advanced, estimate_compression, COMPRESSION_PRESETS


def format_size(bytes_size):
    """Format bytes as human-readable size."""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes_size < 1024:
            return f"{bytes_size:.1f} {unit}"
        bytes_size /= 1024
    return f"{bytes_size:.1f} TB"


def test_compression(pdf_path: str):
    """Test compression on a PDF file with all presets."""
    
    print("=" * 70)
    print("🔬 ADVANCED PDF COMPRESSION TEST")
    print("=" * 70)
    
    if not os.path.exists(pdf_path):
        print(f"❌ File not found: {pdf_path}")
        return
    
    original_size = os.path.getsize(pdf_path)
    print(f"\n📄 Input: {pdf_path}")
    print(f"📊 Original size: {format_size(original_size)}")
    
    # Show presets
    print("\n📋 Available Presets:")
    for name, preset in COMPRESSION_PRESETS.items():
        print(f"   • {name}: {preset['description']} (Expected: {preset.get('expected_reduction', 'N/A')})")
    
    # Estimate compression
    print("\n📈 Compression Estimates:")
    for quality in ["low", "medium", "high", "extreme", "lossless"]:
        est = estimate_compression(pdf_path, quality)
        print(f"   • {quality}: {format_size(est['estimated_size'])} ({est['estimated_reduction']:.0f}% reduction)")
    
    # Test with medium preset
    print("\n" + "=" * 70)
    print("🚀 Running MEDIUM compression...")
    print("=" * 70)
    
    output_path = pdf_path.replace(".pdf", "_compressed_medium.pdf")
    success, reduction, stats = compress_pdf_advanced(pdf_path, output_path, quality="medium")
    
    if success:
        print("\n✅ Compression successful!")
        print(f"\n📊 Results:")
        print(f"   Original:     {format_size(stats['original_size'])}")
        print(f"   Compressed:   {format_size(stats['new_size'])}")
        print(f"   Reduction:    {stats['reduction_percent']:.1f}%")
        print(f"   Saved:        {format_size(stats.get('saved_bytes', 0))}")
        print(f"\n📷 Image Stats:")
        print(f"   Found:        {stats['images_found']}")
        print(f"   Optimized:    {stats['images_optimized']}")
        print(f"   Skipped:      {stats['images_skipped']}")
        print(f"\n⚙️ Settings:")
        print(f"   Preset:       {stats['preset']}")
        print(f"   Target DPI:   {stats['target_dpi']}")
        print(f"   JPEG Quality: {stats['jpeg_quality']}%")
        print(f"\n📁 Output: {output_path}")
    else:
        print(f"\n❌ Compression failed: {stats.get('error', 'Unknown error')}")
    
    # Test with low preset (max compression)
    print("\n" + "=" * 70)
    print("🚀 Running LOW (maximum) compression...")
    print("=" * 70)
    
    output_path_low = pdf_path.replace(".pdf", "_compressed_low.pdf")
    success, reduction, stats = compress_pdf_advanced(pdf_path, output_path_low, quality="low")
    
    if success:
        print("\n✅ Low compression successful!")
        print(f"   Original:     {format_size(stats['original_size'])}")
        print(f"   Compressed:   {format_size(stats['new_size'])}")
        print(f"   Reduction:    {stats['reduction_percent']:.1f}%")
    
    print("\n" + "=" * 70)
    print("✅ TEST COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    # Find a test PDF
    test_pdfs = [
        "test.pdf",
        "sample.pdf", 
        "tests/sample.pdf",
        "docs/test.pdf",
    ]
    
    # Check for command line argument
    if len(sys.argv) > 1:
        test_compression(sys.argv[1])
    else:
        # Try to find a test PDF
        found = False
        for pdf in test_pdfs:
            if os.path.exists(pdf):
                test_compression(pdf)
                found = True
                break
        
        if not found:
            print("=" * 70)
            print("🔬 ADVANCED PDF COMPRESSION - No test file found")
            print("=" * 70)
            print("\nUsage: python test_compression.py <pdf_file>")
            print("\nOr create a test.pdf file in the current directory.")
            print("\n📋 Available Presets:")
            for name, preset in COMPRESSION_PRESETS.items():
                print(f"   • {name}: {preset['description']}")
