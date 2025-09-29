 
#utils/screen.py
#
import logging
import os
import re
import tempfile
import requests
from datetime import datetime
from dateutil.parser import parse as parse_date
from django.conf import settings
from pdfminer.high_level import extract_text
import pdfplumber
from docx import Document
from sentence_transformers import SentenceTransformer, util
from transformers import AutoTokenizer, AutoModelForTokenClassification, pipeline
import torch
import mimetypes
import signal
import threading
import functools
from .job_titles import JOB_TITLE_KEYWORDS

logger = logging.getLogger('job_applications')

# Lazy initialization of SentenceTransformer
_model = None

# Load a resume-specific NER model from HuggingFace
_resume_ner_tokenizer = None
_resume_ner_model = None
_resume_ner_pipeline = None

# Global variables for model caching
_model = None
_resume_ner_tokenizer = None
_resume_ner_model = None
_resume_ner_pipeline = None
_model_lock = threading.Lock()

def get_sentence_transformer_model():
    """Lazily load the SentenceTransformer model."""
    global _model
    if _model is None:
        try:
            with _model_lock:
                if _model is None:  # Double-check locking
                    _model = SentenceTransformer('all-MiniLM-L6-v2')
                    device = torch.device('cpu')
                    if _model.device.type == 'meta':
                        _model.to_empty(device=device)
                    else:
                        _model.to(device)
                    logger.info("Loaded SentenceTransformer model on CPU")
        except Exception as e:
            logger.exception(f"Failed to load SentenceTransformer model: {str(e)}")
            raise RuntimeError("Unable to initialize sentence transformer model")
    return _model

def get_resume_ner_pipeline():
    """Lazily load the NER pipeline with proper caching."""
    global _resume_ner_tokenizer, _resume_ner_model, _resume_ner_pipeline

    if _resume_ner_pipeline is None:
        try:
            with _model_lock:
                if _resume_ner_pipeline is None:  # Double-check locking
                    logger.info("Loading NER model...")
                    model_name = "dslim/bert-base-NER"
                    _resume_ner_tokenizer = AutoTokenizer.from_pretrained(model_name)
                    _resume_ner_model = AutoModelForTokenClassification.from_pretrained(model_name)
                    _resume_ner_pipeline = pipeline(
                        "ner",
                        model=_resume_ner_model,
                        tokenizer=_resume_ner_tokenizer,
                        aggregation_strategy="simple",
                        device=-1  # Use CPU
                    )
                    logger.info("Loaded HuggingFace NER pipeline")
        except Exception as e:
            logger.exception(f"Failed to load NER model: {str(e)}")
            # Create a simple fallback pipeline
            _resume_ner_pipeline = lambda x: []

    return _resume_ner_pipeline

def simple_ner_fallback(text):
    """Simple fallback NER implementation when the full model fails to load."""
    # Extract names using simple regex patterns
    name_pattern = r'^[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+$'
    names = []
    for line in text.split('\n'):
        line = line.strip()
        if re.match(name_pattern, line) and len(line.split()) <= 4:
            names.append(line)

    # Extract emails and phones with regex
    email_match = re.search(r'[\w\.-]+@[\w\.-]+', text)
    phone_match = re.search(r'(\+?\d{1,3}[\s-]?)?(\(?\d{3}\)?[\s-]?)?\d{3}[\s-]?\d{4}', text)

    return [
        {'entity_group': 'PER', 'word': name} for name in names[:1]
    ] + (
        [{'entity_group': 'EMAIL', 'word': email_match.group(0)}] if email_match else []
    ) + (
        [{'entity_group': 'PHONE', 'word': phone_match.group(0)}] if phone_match else []
    )


def screen_resume(resume_text, job_description):
    """Compute similarity score between resume and job description."""
    try:
        if not resume_text or not job_description:
            logger.warning(f"Empty input: resume_text={bool(resume_text)}, job_description={bool(job_description)}")
            return 0.0
        model = get_sentence_transformer_model()
        resume_emb = model.encode(resume_text, convert_to_tensor=True)
        jd_emb = model.encode(job_description, convert_to_tensor=True)
        score = util.pytorch_cos_sim(resume_emb, jd_emb).item()
        return round(score * 100, 2)
    except Exception as e:
        logger.exception(f"Error screening resume: {str(e)}")
        return 0.0

def clean_resume_text(text):
    """Clean resume text to handle OCR artifacts, normalize formatting, and remove repetitive lines."""
    # Remove timestamp-like patterns (e.g., "8/4/25, 9/23 AM")
    text = re.sub(r'^\d{1,2}/\d{1,2}/\d{2,4},\s*\d{1,2}/\d{2}\s*(?:AM|PM)\n?', '', text, flags=re.MULTILINE)
    # Fix common OCR errors
    text = re.sub(r'Co-1', 'Coordinator', text, flags=re.IGNORECASE)
    # Remove URLs (e.g., "https://stackedit.io/app#")
    text = re.sub(r'https?://\S+', '', text)
    # Remove markdown hashtags
    text = re.sub(r'^\s*#+\s*', '', text, flags=re.MULTILINE)
    # Normalize whitespace around parentheses
    text = re.sub(r'\s*\(\s*', ' (', text)
    text = re.sub(r'\s*\)\s*', ') ', text)
    # Remove repetitive lines
    lines = text.split('\n')
    seen = set()
    unique_lines = []
    for line in lines:
        line = line.strip()
        if line and line not in seen:
            unique_lines.append(line)
            seen.add(line)
    text = '\n'.join(unique_lines)
    # Normalize whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    return text





class TimeoutError(Exception):
    pass

def timeout(seconds=30, error_message="Function call timed out"):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            def handle_timeout(signum, frame):
                raise TimeoutError(error_message)

            # Set the signal handler and a alarm
            signal.signal(signal.SIGALRM, handle_timeout)
            signal.alarm(seconds)
            try:
                result = func(*args, **kwargs)
            finally:
                # Cancel the alarm
                signal.alarm(0)
            return result
        return wrapper
    return decorator

@timeout(30, "PDF parsing timed out after 30 seconds")
def safe_parse_pdf(full_path):
    """Safely parse PDF with timeout"""
    try:
        with pdfplumber.open(full_path) as pdf:
            return '\n'.join([page.extract_text() or '' for page in pdf.pages])
    except Exception as e:
        logger.error(f"pdfplumber failed: {str(e)}. Falling back to pdfminer.")
        return extract_text(full_path)

import pytesseract
from PIL import Image
import io

def parse_resume(file_path):
    """Parse resume from a local file and extract text with OCR fallback."""
    try:
        logger.info(f"Processing file: {file_path}")
        text = ""

        # Get file extension
        _, ext = os.path.splitext(file_path)
        ext = ext.lower()

        if ext == '.pdf':
            # Try text extraction first
            try:
                # Try pdfplumber first
                try:
                    with pdfplumber.open(file_path) as pdf:
                        text = '\n'.join([page.extract_text() or '' for page in pdf.pages])
                    logger.info(f"pdfplumber extracted {len(text)} characters")
                except Exception as e:
                    logger.error(f"pdfplumber failed: {str(e)}")
                    text = ""

                # If pdfplumber failed or extracted little text, try pdfminer
                if not text or len(text.strip()) < 100:
                    logger.info("Trying pdfminer as fallback")
                    try:
                        text = extract_text(file_path)
                        logger.info(f"pdfminer extracted {len(text)} characters")
                    except Exception as e:
                        logger.error(f"pdfminer also failed: {str(e)}")
                        text = ""

                # If still no text, try OCR
                if not text or len(text.strip()) < 100:
                    logger.info("Text extraction failed, trying OCR")
                    text = extract_text_with_ocr(file_path)

            except Exception as e:
                logger.error(f"PDF parsing failed: {str(e)}")
                text = ""
        elif ext in ['.docx', '.doc']:
            try:
                doc = Document(file_path)
                text = '\n'.join([para.text for para in doc.paragraphs])
                logger.info(f"Word document extracted {len(text)} characters")
            except Exception as e:
                logger.error(f"Failed to parse Word document: {str(e)}")
                text = ""
        else:
            logger.error(f"Unsupported file type: {ext}")
            text = ""

        text = clean_resume_text(text)
        logger.info(f"Final cleaned text length: {len(text)}")

        if text:
            logger.debug(f"Sample of extracted text: {text[:500]}")
        else:
            logger.warning("No text could be extracted from the resume")

        return text
    except Exception as e:
        logger.exception(f"Error parsing resume {file_path}: {str(e)}")
        return ""

def extract_text_with_ocr(file_path):
    """Extract text from PDF using OCR for image-based documents."""
    try:
        text = ""
        with pdfplumber.open(file_path) as pdf:
            for page_num, page in enumerate(pdf.pages):
                # Extract images from the page
                if page.images:
                    for img in page.images:
                        # Extract and OCR each image
                        try:
                            img_data = page.to_image().original
                            pil_image = Image.open(io.BytesIO(img_data))
                            ocr_text = pytesseract.image_to_string(pil_image)
                            text += ocr_text + "\n"
                        except Exception as e:
                            logger.error(f"OCR failed for image on page {page_num}: {str(e)}")

                # Also try to extract any text that might be there
                page_text = page.extract_text() or ""
                text += page_text + "\n"

        logger.info(f"OCR extracted {len(text)} characters")
        return text
    except Exception as e:
        logger.error(f"OCR extraction failed: {str(e)}")
        return ""



def parse_job_date(date_str):
    """Parse job dates with robust handling of formatting variations."""
    try:
        # Normalize and clean date string
        date_str = re.sub(r'\bSept\b', 'September', date_str, flags=re.IGNORECASE)
        date_str = re.sub(r'[📝•\-*]\s*', '', date_str)  # Remove emojis/bullets
        date_str = re.sub(r'\*\*', '', date_str)  # Remove bold markers
        date_str = date_str.replace('–', '-').replace('—', '-').strip()

        # Handle present/future dates
        if "present" in date_str.lower():
            return datetime.now()

        parsed_date = parse_date(date_str, fuzzy=True)
        return parsed_date
    except Exception as e:
        logger.warning(f"Failed to parse date: {date_str}, error: {str(e)}")
        return None

def extract_experience_entries(resume_text):
    """Extract experience entries with improved structure handling."""
    experience = []
    gap_titles = "Career Break|Gap|Employment Gap|Sabbatical|Leave|Break"

    # 1. First detect explicit gaps
    gap_pattern = re.compile(
        rf'\(?(?P<title>{gap_titles})\s*:\s*'
        r'(?P<start>(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\.?\s+\d{4})\s*[–\-]\s*'
        r'(?P<end>(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\.?\s+\d{4}|Present)\s*\)?',
        re.IGNORECASE | re.MULTILINE
    )

    gap_matches = gap_pattern.finditer(resume_text)
    for m in gap_matches:
        entry = {
            "title": m.group('title').strip(),
            "company": "",
            "start": m.group('start'),
            "end": m.group('end'),
            "is_gap": True
        }
        logger.debug(f"Matched gap entry (regex): {entry}")
        experience.append(entry)

    # 2. Improved job detection with markdown awareness
    job_pattern = re.compile(
        r'(?P<title>^#{1,3}\s*.+?$|^[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\s*(?:[A-Z]{2,}|Manager|Engineer|Analyst|Specialist)\b)',
        re.IGNORECASE | re.MULTILINE
    )

    # Find all potential job title markers
    matches = list(job_pattern.finditer(resume_text))
    for i, m in enumerate(matches):
        title = re.sub(r'^#{1,3}\s*', '', m.group('title')).strip()

        # Skip if title matches gap pattern
        if re.search(rf'\b({gap_titles})\b', title, re.IGNORECASE):
            continue

        # Look for company in next 1-3 lines
        company = "Unknown"
        start_date = ""
        end_date = ""

        # Search in subsequent lines
        next_lines = resume_text[m.end():].split('\n')[:5]
        for line in next_lines:
            line = line.strip()

            # Detect company (italic or plain text)
            if not company or company == "Unknown":  # Allow updating if "Unknown"
                company_match = re.search(r'(\*[^*]+\*)|([A-Z][a-z]+(?:\s+[A-Za-z]+)*)', line)
                if company_match:
                    company = re.sub(r'\*', '', company_match.group(0)).strip()

            # Detect date range (with flexible formatting)
            date_match = re.search(
                r'(\d{4}\s*[–\-]\s*(?:Present|\d{4}))|'
                r'((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4}\s*[–\-]\s*(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4}|Present)',
                line,
                re.IGNORECASE
            )
            if date_match and not start_date:
                dates = date_match.group(0)
                if '–' in dates:
                    start_date, end_date = dates.split('–', 1)
                elif '-' in dates:
                    start_date, end_date = dates.split('-', 1)
                else:
                    start_date = dates
                    end_date = "Present"

                # Clean date strings
                start_date = start_date.strip()
                end_date = end_date.strip()
                break

        # Create entry if dates found
        if start_date:
            entry = {
                "title": title,
                "company": company,
                "start": start_date,
                "end": end_date,
                "is_gap": False
            }
            # Check for duplicates before adding
            if not any(e["title"] == entry["title"] and e["start"] == entry["start"] for e in experience):
                logger.debug(f"Matched job entry: {title} at {company} ({start_date} - {end_date})")
                experience.append(entry)

    # 3. Add fallback: Find date ranges anywhere in text
    date_range_pattern = re.compile(
        r'(\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4}\s*[–\-]\s*(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4}\b)|'
        r'(\b\d{4}\s*[–\-]\s*\d{4}\b)|'
        r'(\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4}\s*[–\-]\s*Present\b)',
        re.IGNORECASE
    )

    for match in date_range_pattern.finditer(resume_text):
        date_range = match.group(0)
        if '–' in date_range:
            start_date, end_date = date_range.split('–', 1)
        else:
            start_date, end_date = date_range.split('-', 1)

        # Find nearest preceding text as title
        context_start = max(0, match.start() - 100)
        context = resume_text[context_start:match.start()]
        title_match = re.search(r'([^\n]{5,50})\n*$', context)
        title = title_match.group(1).strip() if title_match else "Unknown Position"

        # Create entry if not already captured
        if not any(e["start"] == start_date.strip() for e in experience):
            entry = {
                "title": title,
                "company": "Unknown",
                "start": start_date.strip(),
                "end": end_date.strip(),
                "is_gap": False
            }
            experience.append(entry)

    return experience



def extract_name_from_resume(resume_text):
    """
    Attempts to extract the full name from resume text using multiple patterns:
    1. Explicit "First Name" and "Last Name" labels.
    2. Full name line at the top of the document.
    """
    # Try pattern 1: First Name: John, Last Name: Doe
    first_name_match = re.search(r'First Name[:\-]?\s*([A-Z][a-z]+)', resume_text, re.IGNORECASE)
    last_name_match = re.search(r'Last Name[:\-]?\s*([A-Z][a-z]+)', resume_text, re.IGNORECASE)

    if first_name_match and last_name_match:
        return f"{first_name_match.group(1)} {last_name_match.group(1)}"

    # Try pattern 2: Full name at top of resume (e.g., John Doe)
    full_name_match = re.search(r'^([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)', resume_text, re.MULTILINE)
    if full_name_match:
        return full_name_match.group(1)

    return ""



def extract_name_from_filename(filename):
    """
    Extracts a name from the resume filename if it resembles a full name.
    Example: "Blessing Okonkwo.pdf" => "Blessing Okonkwo"
    """
    name_part = os.path.splitext(filename)[0]
    if re.match(r'^[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+$', name_part):
        return name_part
    return ""

def extract_resume_fields(resume_text, resume_filename=None):
    """
    Extracts structured fields from resume text using NER, regex, and heuristics.
    Optionally takes `resume_filename` for fallback name extraction.
    """
    try:
        logger.info(f"Extracting fields from resume text of length: {len(resume_text)}")

        extracted_data = {
            "full_name": "",
            "email": "",
            "phone": "",
            "qualification": "",
            "experience": [],
            "knowledge_skill": "",
            "employment_gaps": []
        }

        if not resume_text or len(resume_text.strip()) < 50:
            logger.warning("Resume text is too short or empty, skipping extraction")
            return extracted_data

        # Email
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        email_match = re.search(email_pattern, resume_text)
        if email_match:
            extracted_data["email"] = email_match.group(0)
            logger.info(f"Found email: {email_match.group(0)}")

        # Phone
        phone_pattern = r'(\+?(\d{1,3})?[\s-]?)?(\(?\d{3}\)?[\s-]?)?\d{3}[\s-]?\d{4}'
        phone_match = re.search(phone_pattern, resume_text)
        if phone_match:
            extracted_data["phone"] = phone_match.group(0)
            logger.info(f"Found phone: {phone_match.group(0)}")

        # Full name (from text)
        full_name = extract_name_from_resume(resume_text)
        if full_name:
            extracted_data["full_name"] = full_name
            logger.info(f"Found full name from text: {full_name}")
        elif resume_filename:
            # Try fallback: name from filename
            full_name = extract_name_from_filename(resume_filename)
            if full_name:
                extracted_data["full_name"] = full_name
                logger.info(f"Fallback: extracted full name from filename: {full_name}")
            else:
                logger.warning("Could not extract full name.")
        else:
            logger.warning("Could not extract full name.")

        # Qualifications
        qualification_patterns = [
            r'(Bachelor|B\.?Sc|B\.?Eng|B\.?Tech|B\.?Com)',
            r'(Master|M\.?Sc|M\.?Eng|M\.?Tech|M\.?Com)',
            r'(Ph\.?D|Doctorate)',
            r'(Diploma|Certificate|Associate)',
            r'(High School|Secondary School)'
        ]
        qualifications = []
        for pattern in qualification_patterns:
            matches = re.findall(pattern, resume_text, re.IGNORECASE)
            qualifications.extend(matches)
        if qualifications:
            extracted_data["qualification"] = ", ".join(set(qualifications))
            logger.info(f"Found qualifications: {extracted_data['qualification']}")

        # Skills
        skill_patterns = [
            r'(?:Skills|Technologies|Proficiencies|Expertise)[:\s]*(.*?)(?:\n\n|\n[A-Z]|$)',
            r'(?:Programming Languages|Frameworks|Tools)[:\s]*(.*?)(?:\n\n|\n[A-Z]|$)'
        ]
        skills = []
        for pattern in skill_patterns:
            match = re.search(pattern, resume_text, re.IGNORECASE | re.DOTALL)
            if match:
                skills_text = match.group(1)
                skill_items = re.findall(r'[A-Za-z+.#]+', skills_text)
                skills.extend(skill_items)
        if skills:
            extracted_data["knowledge_skill"] = ", ".join(set(skills))
            logger.info(f"Found skills: {extracted_data['knowledge_skill']}")

        # Experience
        experience_pattern = r'(\d+)\s*(?:years?|yrs?)\s*(?:of|experience)'
        experience_match = re.search(experience_pattern, resume_text, re.IGNORECASE)
        if experience_match:
            extracted_data["experience"] = [f"{experience_match.group(1)} years of experience"]
            logger.info(f"Found experience: {extracted_data['experience']}")

        logger.info(f"Final extracted data: {extracted_data}")
        return extracted_data

    except Exception as e:
        logger.exception(f"Error extracting fields from resume: {str(e)}")
        return {}
