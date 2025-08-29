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
from .job_titles import JOB_TITLE_KEYWORDS

logger = logging.getLogger('job_applications')

# Lazy initialization of SentenceTransformer
_model = None

# Load a resume-specific NER model from HuggingFace
_resume_ner_tokenizer = None
_resume_ner_model = None
_resume_ner_pipeline = None

def get_sentence_transformer_model():
    """Lazily load the SentenceTransformer model."""
    global _model
    if _model is None:
        try:
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
    global _resume_ner_tokenizer, _resume_ner_model, _resume_ner_pipeline
    if _resume_ner_pipeline is None:
        try:
            model_name = "dslim/bert-base-NER"
            _resume_ner_tokenizer = AutoTokenizer.from_pretrained(model_name)
            _resume_ner_model = AutoModelForTokenClassification.from_pretrained(model_name)
            _resume_ner_pipeline = pipeline(
                "ner",
                model=_resume_ner_model,
                tokenizer=_resume_ner_tokenizer,
                aggregation_strategy="simple"
            )
            logger.info("Loaded HuggingFace NER pipeline")
        except Exception as e:
            logger.exception(f"Failed to load NER model: {str(e)}")
            raise RuntimeError("Unable to initialize NER model")
    return _resume_ner_pipeline

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

def parse_resume(file_path):
    """Parse resume from a remote URL or local file and extract text."""
    try:
        logger.debug(f"Processing file_path: {file_path}")
        temp_file_path = None
        text = ""

        is_url = file_path.startswith(('http://', 'https://'))
        if is_url:
            logger.info(f"Downloading remote resume: {file_path}")
            headers = {"Authorization": f"Bearer {settings.SUPABASE_KEY}"}
            response = requests.get(file_path, headers=headers)
            if response.status_code != 200:
                logger.error(f"Failed to download file: {file_path}, status code: {response.status_code}")
                return ""
            file_content = response.content
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')
            temp_file.write(file_content)
            temp_file.close()
            temp_file_path = temp_file.name
            full_path = temp_file_path
        else:
            logger.info(f"Processing local resume file: {file_path}")
            full_path = file_path

        ext = os.path.splitext(full_path)[1].lower()
        if ext == '.pdf':
            try:
                with pdfplumber.open(full_path) as pdf:
                    text = '\n'.join([page.extract_text() or '' for page in pdf.pages])
            except Exception as e:
                logger.error(f"pdfplumber failed: {str(e)}. Falling back to pdfminer.")
                text = extract_text(full_path)
            text = clean_resume_text(text)
            logger.debug(f"Extracted resume text (first 1000 chars): {text[:1000]}")
        elif ext in ['.docx', '.doc']:
            doc = Document(full_path)
            text = '\n'.join([para.text for para in doc.paragraphs])
            text = clean_resume_text(text)
            logger.debug(f"Extracted resume text (first 1000 chars): {text[:1000]}")
        else:
            logger.error(f"Unsupported file type: {ext}")
            text = ""

        if temp_file_path and os.path.exists(temp_file_path):
            os.unlink(temp_file_path)
            logger.debug(f"Cleaned up temporary file: {temp_file_path}")
        return text
    except Exception as e:
        logger.exception(f"Error parsing resume {file_path}: {str(e)}")
        if temp_file_path and os.path.exists(temp_file_path):
            os.unlink(temp_file_path)
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

def extract_resume_fields(resume_text):
    """
    Extracts structured fields from resume text using NER, regex, and heuristics.
    Fields: full_name, email, phone, qualification, experience, knowledge_skill, employment_gaps
    """
    try:
        extracted_data = {
            "full_name": "",
            "email": "",
            "phone": "",
            "qualification": "",
            "experience": [],
            "knowledge_skill": "",
            "employment_gaps": []
        }

        ner = get_resume_ner_pipeline()
        entities = ner(resume_text)

        # Group entities by label
        grouped = {}
        for ent in entities:
            label = ent['entity_group']
            grouped.setdefault(label, []).append(ent['word'])

        # --- FULL NAME EXTRACTION ---
        full_name = ""
        if "PER" in grouped and grouped["PER"]:
            candidate = grouped["PER"][0].strip()
            if (2 <= len(candidate.split()) <= 4 and
                not any(char.isdigit() for char in candidate) and
                not candidate.isupper()):
                full_name = candidate
        if not full_name:
            for line in resume_text.split('\n'):
                line = line.strip()
                if (line and 2 <= len(line.split()) <= 4 and
                    not any(char.isdigit() for char in line) and
                    not line.isupper() and
                    not re.search(r'[@\-]', line)):
                    full_name = line
                    break
        if not full_name and "PER" in grouped and grouped["PER"]:
            full_name = grouped["PER"][0].strip()
        extracted_data["full_name"] = full_name

        # Regex for email, phone, degree, skills
        email_match = re.search(r'[\w\.-]+@[\w\.-]+', resume_text)
        phone_match = re.search(r'(\+?\d{1,3}[\s-]?)?(\(?\d{3}\)?[\s-]?)?\d{3}[\s-]?\d{4}', resume_text)
        degree_match = re.findall(r'(Bachelor|Master|B\.Sc|M\.Sc|Ph\.D|Bachelors?|Masters?|Doctorate|Diploma|Certificate)', resume_text, re.IGNORECASE)
        skill_match = re.findall(r'(?:Tools\s*&\s*Technologies|skills?|technologies|proficiencies|expertise)[:\-]?\s*(.*)', resume_text, re.IGNORECASE)

        if email_match:
            extracted_data["email"] = email_match.group(0)
        if phone_match:
            extracted_data["phone"] = phone_match.group(0)
        if degree_match:
            extracted_data["qualification"] = ", ".join(set(degree_match))
        if skill_match:
            extracted_data["knowledge_skill"] = ", ".join([match[1].strip() for match in skill_match])

        # Extract experience and gaps
        experience = extract_experience_entries(resume_text)

        # Format experience entries for output
        extracted_data["experience"] = [
            f"{e['title']} at {e['company']} ({e['start']} - {e['end']})"
            for e in experience if not e["is_gap"]
        ]

        # Enhanced gap calculation
        job_entries = sorted(
            [e for e in experience if not e["is_gap"] and parse_job_date(e["start"])],
            key=lambda x: parse_job_date(x["start"])
        )
        
        gaps = []
        for i in range(1, len(job_entries)):
            prev_end = parse_job_date(job_entries[i-1]["end"])
            curr_start = parse_job_date(job_entries[i]["start"])
            
            if not prev_end or not curr_start:
                continue
                
            # Handle "Present" in previous job
            if job_entries[i-1]["end"].lower() == "present":
                prev_end = datetime.now()
                
            gap_months = (curr_start.year - prev_end.year) * 12 + (curr_start.month - prev_end.month)
            
            if gap_months > 1:  # Only consider gaps >1 month
                gaps.append({
                    "gap_start": prev_end.strftime("%Y-%m"),
                    "gap_end": curr_start.strftime("%Y-%m"),
                    "duration_months": gap_months
                })

        extracted_data["employment_gaps"] = sorted(
            gaps,
            key=lambda x: parse_job_date(x["gap_start"] + "-01") or datetime(2000, 1, 1)
        )

        logger.debug(f"Extracted resume data: {extracted_data}")
        return extracted_data
    except Exception as e:
        logger.exception(f"Error extracting fields from resume: {str(e)}")
        return {}