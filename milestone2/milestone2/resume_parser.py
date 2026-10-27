import fitz
import docx
 
from extractor import extract_fields
from db import insert_candidate, init_db
 
 
def extract_text_from_pdf(pdf_path):
    """Extract text in actual on-page reading order (top-to-bottom,
    left-to-right), rather than PyMuPDF's default content-stream order
    (which can jumble text extracted from resumes that use icons, tables,
    or styled header blocks) — this matters a lot for heuristics like
    "the candidate's name is the first line of the resume".

    Every block ends with a newline and every page is followed by one, so the
    last line of a page never gets glued to the first line of the next page
    (that used to turn "...Power BI Fundamentals" + "Technical Skills" into one
    line and hide the Skills heading)."""
    doc = fitz.open(pdf_path)
    text = ""
    for page in doc:
        blocks = page.get_text("blocks")
        # Each block: (x0, y0, x1, y1, text, block_no, block_type)
        blocks.sort(key=lambda b: (round(b[1], 1), round(b[0], 1)))
        for b in blocks:
            block_text = b[4]
            if block_text.strip():
                text += block_text if block_text.endswith("\n") else block_text + "\n"
        text += "\n"
    return text
 
 
def extract_text_from_docx(docx_path):
    doc = docx.Document(docx_path)
    text = "\n".join([para.text for para in doc.paragraphs])
    return text
 
 
def extract_text_from_file(file_path):
    if file_path.lower().endswith(".pdf"):
        return extract_text_from_pdf(file_path)
    elif file_path.lower().endswith(".docx"):
        return extract_text_from_docx(file_path)
    else:
        raise ValueError("Unsupported file type. Use PDF or DOCX.")
 
 
def process_resume(file_path, file_name=None):
    file_name = file_name or file_path
    text = extract_text_from_file(file_path)
    profile = extract_fields(text, file_name)
    insert_candidate(profile)
    return profile
 
 
if __name__ == "__main__":
    init_db()
    file_path = "../resume/om sandhan resume.pdf"
    profile = process_resume(file_path)
    for key, value in profile.items():
        if key != "raw_text":
            print(f"{key}: {value}")