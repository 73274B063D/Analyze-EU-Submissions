import os
import pymupdf4llm
import mammoth

def test_conversion(filename):
    path = os.path.join("attachments/14842", filename)
    if not os.path.exists(path):
        print(f"File not found: {path}")
        return

    print(f"Converting {filename}...")
    try:
        md_text = ""
        # Check header
        is_pdf = False
        with open(path, "rb") as f:
            if f.read(4) == b'%PDF':
                is_pdf = True
        
        if is_pdf:
            print("Detected PDF signature.")
            md_text = pymupdf4llm.to_markdown(path)
        elif filename.lower().endswith('.docx'):
             # Try mammoth only if not PDF
            with open(path, "rb") as docx_file:
                 result = mammoth.convert_to_markdown(docx_file)
                 md_text = result.value
                 messages = result.messages
                 if messages:
                     print(f"Mammoth messages: {messages}")

        print(f"--- START MARKDOWN for {filename} ---")
        print(md_text[:500]) # Print first 500 chars
        print("--- END PREVIEW ---")
        
    except Exception as e:
        print(f"Error converting {filename}: {e}")

if __name__ == "__main__":
    # Test a PDF
    test_conversion("090166e525b9306c_Eclipse_Foundation_feedback_on_Chips_Act.pdf")
    # Test a DOCX
    # 090166e525a172c7_Chips Act 2 consultation.docx failed
    # Try ESA feedback
    test_conversion("090166e525506a41_ESA feedback to EU Chips Act 2.0.docx")
