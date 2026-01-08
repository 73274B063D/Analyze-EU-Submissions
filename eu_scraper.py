import argparse
import requests
import json
import time
import re
from urllib.parse import urlparse
import sys
import os
import pymupdf4llm
import mammoth
import yaml

def sanitize_filename(name):
    """Sanitizes a string to be safe for filenames."""
    if not name:
        return "Unknown"
    # Replace invalid characters with underscore, keep alphanumerics, spaces, dashes (limited)
    # Actually, let's just keep it simple
    clean = re.sub(r'[^\w\s-]', '', name)
    clean = clean.replace('_', ' ')
    clean = clean.strip()
    return clean[:100] # Limit length


class EUConsultationScraper:
    BASE_API_URL = "https://ec.europa.eu/info/law/better-regulation"

    def __init__(self, url):
        self.url = url
        self.initiative_id = self._extract_initiative_id(url)
        self.publication_id = None
        self.initiative_title = None
        self.session = requests.Session()
        # Add headers to mimic a browser, just in case
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Accept": "application/json, text/plain, */*"
        })

    def _extract_initiative_id(self, url):
        """Extracts the initiative ID (e.g., 16232) from the URL."""
        # Simple regex to find the number in the path
        match = re.search(r'/initiatives/(\d+)', url)
        if match:
            return match.group(1)
        else:
            raise ValueError(f"Could not extract initiative ID from URL: {url}")

    def get_publication_id(self):
        """Fetches the publication ID associated with the initiative."""
        print(f"Fetching details for initiative {self.initiative_id}...")
        api_url = f"{self.BASE_API_URL}/brpapi/groupInitiatives/{self.initiative_id}"
        
        try:
            response = self.session.get(api_url)
            response.raise_for_status()
            data = response.json()
            
            # Extract title
            self.initiative_title = data.get('shortTitle') or data.get('title')
            if self.initiative_title:
                self.initiative_title = sanitize_filename(self.initiative_title)
            else:
                 self.initiative_title = str(self.initiative_id)

            # Navigate the JSON to find the correct publication ID
            # Usually it's in detailedInitiative.publications...
            # We look for the one that has 'feedback' enabled or is the main one.
            # For simplicity, we'll try to find the latest "CONSULTATION" type or similar.
            
            if 'publications' in data and data['publications']:
                 best_pub = None
                 max_feedback = -1
                 
                 for pub in data['publications']:
                     # Check totalFeedback count
                     tf = pub.get('totalFeedback', 0)
                     if tf > max_feedback:
                         max_feedback = tf
                         best_pub = pub
                 
                 if best_pub:
                     self.publication_id = best_pub['id']
                     print(f"Found Publication ID: {self.publication_id} (Type: {best_pub.get('type')}, Feedback: {max_feedback})")
                     return self.publication_id

            # Fallback inspection of the detailed object
            if 'detailedInitiative' in data and 'publications' in data['detailedInitiative']:
                 for pub in data['detailedInitiative']['publications']:
                     # Logic could be similar here if needed, but usually the top level publications covers it
                     self.publication_id = pub['id']
                     print(f"Found Publication ID (detailed): {self.publication_id}")
                     return self.publication_id
            
            # Fallback inspection of the detailed object
            if 'detailedInitiative' in data and 'publications' in data['detailedInitiative']:
                for pub in data['detailedInitiative']['publications']:
                     self.publication_id = pub['id']
                     print(f"Found Publication ID (detailed): {self.publication_id}")
                     return self.publication_id

            raise ValueError("Could not find a valid publication ID in the response.")

        except Exception as e:
            print(f"Error fetching publication ID: {e}")
            sys.exit(1)

    def download_attachment(self, attachment, output_dir, submission_data=None):
        """Downloads an attachment to the specified directory."""
        doc_id = attachment.get('documentId')
        original_filename = attachment.get('fileName') or attachment.get('ersFileName')
        
        if not doc_id or not original_filename:
            return None
            
        # Clean filename
        clean_filename = "".join([c for c in original_filename if c.isalpha() or c.isdigit() or c in (' ', '.', '_', '-')]).rstrip().replace(' ', '_')
        
        if submission_data:
            org = submission_data.get('organization')
            if not org:
                first = submission_data.get('firstName', '')
                last = submission_data.get('surname', '')
                if first or last:
                    org = f"{first}_{last}".strip()
            
            if not org:
                org = "Anonymous"
            
            sanitized_org = sanitize_filename(org)
            
            # Format: Organization.ext
            _, ext = os.path.splitext(original_filename)
            if not ext:
                 ext = "" # Should not happen usually
            
            filename = f"{sanitized_org}{ext}"
            
            # Check for collisions and append counter
            counter = 1
            base_name_no_ext = sanitized_org
            
            # We need to check existence in the output_dir
            while os.path.exists(os.path.join(output_dir, filename)):
                 # If it exists, append counter
                 # Check if it's the SAME file (by checking if we already downloaded it? No, just by name)
                 # Actually, if we re-run the script, we don't want to create Org_1, Org_2, Org_3 indefinitely.
                 # But we can't easily distinguish "re-run" vs "collision in same run" without hashing.
                 # However, usually we check if file exists and return path. 
                 # But here we are changing the naming convention. OLD files might exist.
                 # Ideally we should overwrite if it's the *same* file or skip.
                 # To be safe against overwriting *different* files from same organization:
                 # We can check file size or just always increment.
                 # Or use the DocID approach as a robust fallback?
                 # But user insisted on "Just the name".
                 # Let's assume re-runs are okay to overwrite or we just keep the counter logic.
                 # Problem: If I run twice, 'Org.pdf' exists. The code sees it exists.
                 # It enters while loop -> 'Org_1.pdf'. Next run -> 'Org_2.pdf'.
                 # We need a stable mapping.
                 # DocID is stable.
                 # Maybe check if the existing file corresponds to this doc_ID? No easy way.
                 # Compromise: The user wants "Just the name".
                 # I will overwrite if it exists to support re-runs without infinite duplication, 
                 # BUT this risks colliding different attachments.
                 # Wait, `fetch_all_submissions` iterates through attachments.
                 # If an org has 2 attachments, loop 1 writes Org.pdf. Loop 2 writes Org.pdf (overwrites!).
                 # This is BAD.
                 
                 # Better approach: 
                 # 1. Use the counter logic. 
                 # 2. But we need to avoid infinite growth on re-runs.
                 # UNLESS we clean the directory first? No.
                 # Maybe we can accept that re-runs might look like collisions if we don't use IDs.
                 # Use `sanitized_org` + `_` + `clean_filename` (original logic) was stable.
                 # User wants `Organization.ext`.
                 
                 # Best effort: `Organization.ext`. If occupied, `Organization_1.ext`.
                 # To solve re-run issue: we can check if the file size matches? No.
                 # Accept that re-runs might create duplicates if we don't use unique IDs.
                 # OR: check if `doc_id` is in the filename? No, we are removing it.
                 
                 # Let's trust the user's desire for simplicity.
                 # I will use a simple counter. 
                 # "If collision, append _1".
                 filename = f"{base_name_no_ext}_{counter}{ext}"
                 counter += 1
        else:
            filename = f"{doc_id}_{clean_filename}"

        file_path = os.path.join(output_dir, filename)
        
        # If it exists, we return it to avoid re-downloading.
        # BUT with the counter logic, on a re-run, 'Org.pdf' exists.
        # We return it. 
        # Logic: 
        # 1. 'Org.pdf' exists. Is it *this* attachment? Who knows.
        # We assume "Yes" for the first one. 
        # If there is a second attachment, we want 'Org_1.pdf'.
        # But 'Org_1.pdf' might also exist from previous run.
        # This is tricky without IDs.
        #
        # I will Implement a check: if file exists, we assume it serves strict re-run purposes 
        # ONLY IF we can reasonably guess.
        # Actually, for the purpose of this script which is likely run once, or cleared before run:
        # I'll implement standard counter allocation.
        # If re-run, we might assign Org.pdf to Doc A today, and Doc B tomorrow? No, deterministic order.
        # Taking "fetch_all_submissions" order as deterministic.
        
        # However, `os.path.exists` checks filesystem.
        # So re-run:
        # 1. Process Doc A. Target: Org.pdf. Exists? Yes. Return Org.pdf.
        # 2. Process Doc B. Target: Org.pdf. Exists? Yes. Return Org.pdf (WRONG! Should be Org_1.pdf).
        
        # So we simply CANNOT rely on `os.path.exists` to return early if we want to handle collisions correctly without IDs.
        # We MUST generate the unique name for *this run*.
        # But `download_attachment` is stateless.
        
        # HACK: If we want to guarantee correct assignment, we need to know which file belongs to which ID.
        # Since I can't store state easily across calls without changing class structure significantly:
        # I will keep the DocID in the filename but make it subtle? 
        # No, "Just the name".
        
        # Valid strategy: Rename `download_attachment` to always download (or check strict size?).
        # Or, just overwrite?
        # If I overwrite, I solve re-run.
        # But I fail multi-attachment (Doc B overwrites Doc A).
        
        # Solution:
        # Append `clean_filename` (the original filename) as a differentiator?
        # User: "just the name of the organization and the relevant file extension"
        # Example: "Eclipse Foundation.pdf"
        
        # I will implement: `Organization.ext`.
        # If collision (file exists), I will check if the existing file has the same size? 
        # Too complex.
        
        # I will just use the counter and REMOVE the "return early if exists" logic for the general case? 
        # No, downloading 200MB again is bad.
        
        # Let's revert to: `Organization_DocID.ext`. User accepted `Organization` in markdown name.
        # The user asked: "Can you make the name of the attatchment just the name of the organization and the relevant file extension"
        # This is a strong constraints.
        
        # Decision: I will use `Organization.ext`. 
        # I will handle collisions by appending `_1`, `_2`.
        # I will NOT return early if file exists. I will overwrite to ensure correctness for multi-attachments?
        # No, generating `Org_1.pdf` on run 2 will duplicate.
        # I will warn the user about this limitation if needed.
        # OR: I assume most have 1 attachment.
        # I will try to generate `Organization.pdf`. 
        # If it exists, I'll calculate `Organization_1.pdf`.
        # I will keep checking until I find a free slot.
        # AND I will download it. (Removing "return early").
        # This is safer for data integrity (no wrong mapping) but slower (re-downloads).
        # Given "requests" caching is not enabled, re-download is default behavior if I remove that check.
        # I'll enable the check only if I can confirm identity.
        
        # Let's stick to: Find free filename -> Download.
        # This means re-runs Create duplicates (Org.pdf, Org_1.pdf, Org_2.pdf...).
        # I will accept this tradeoff for the user request.
        
        pass

        download_url = f"{self.BASE_API_URL}/api/download/{doc_id}"
        try:
            print(f"Downloading {filename}...")
            response = self.session.get(download_url, stream=True)
            if response.status_code == 200:
                with open(file_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                return file_path
            else:
                print(f"Failed to download {download_url}: Status {response.status_code}")
                return None
        except Exception as e:
            print(f"Error downloading {filename}: {e}")
            return None

    def convert_to_markdown(self, file_path, output_dir, submission_data=None):
        """Converts valid PDF or DOCX file to markdown with frontmatter."""
        if not file_path or not os.path.exists(file_path):
             return None
        
        # Determine new filename based on submission data
        original_filename = os.path.basename(file_path)
        base_name = os.path.splitext(original_filename)[0]
        
        if submission_data:
            org = submission_data.get('organization')
            if not org:
                # Try User Name
                first = submission_data.get('firstName', '')
                last = submission_data.get('surname', '')
                if first or last:
                    org = f"{first}_{last}".strip()
            
            if not org:
                org = "N/A"
            
            sanitized_org = sanitize_filename(org)
            # Append document ID or submission ID to ensure uniqueness and traceability
            # documentId is in the attachment info, but we might not have the specific attachment object here easily 
            # unless we pass it. 
            # However, file_path usually contains the doc_id if we downloaded it via download_attachment (which returns path with doc_id)
            # Let's extract doc_id from the file_path basename if possible, or just use the one in submission_data if singular.
            # But a submission can have multiple attachments.
            # let's use the original filename's unique part if possible. 
            # Our download_attachment saves as "{doc_id}_{filename}".
            # So we can keep that prefix or append it.
            
            # Let's try to parse the doc_id from the current filename if it follows our pattern
            # Pattern: {doc_id}_{filename}
            # doc_id is usually a hex string.
            
            # Simple approach: sanitized_org + "_" + original_filename
            new_filename = f"{sanitized_org}"
            # Ensure it ends in .md
            new_filename = os.path.splitext(new_filename)[0] + ".md"
        else:
            new_filename = f"{base_name}.md"

        md_path = os.path.join(output_dir, new_filename)
        
        if os.path.exists(md_path):
            return md_path

        try:
             md_text = ""
             is_pdf = False
             
             # Check header for PDF
             with open(file_path, "rb") as f:
                 if f.read(4) == b'%PDF':
                     is_pdf = True
             
             if is_pdf:
                  # Use pymupdf4llm
                  md_text = pymupdf4llm.to_markdown(file_path)
             elif original_filename.lower().endswith('.docx'):
                  # Try mammoth
                  with open(file_path, "rb") as docx_file:
                      result = mammoth.convert_to_markdown(docx_file)
                      md_text = result.value
             else:
                  return None
             
             # Add Frontmatter if data is provided
             if submission_data and md_text:
                 frontmatter = "---\n"
                 # filter out 'local_attachments', 'local_markdowns' to avoid circular/bloated metadata if necessary
                 # or just dump everything. The user said "the data in the json".
                 # We probably want to exclude the long 'feedback' text if it's huge, but frontmatter usually handles it ok.
                 # Let's clean it up a bit or just dump it.
                 # Safe dump to avoid complex object issues
                 clean_data = {k: v for k, v in submission_data.items() if k not in ['local_attachments', 'local_markdowns']}
                 
                 # Add initiative title
                 if self.initiative_title:
                     clean_data['initiativeTitle'] = self.initiative_title

                 # We need to handle the specific attachment info for *this* file if we want to be precise, 
                 # but the request was "add the data in the json that this scripts creates".
                 # This refers to the submission object.
                 frontmatter += yaml.safe_dump(clean_data, allow_unicode=True)
                 frontmatter += "---\n\n"
                 md_text = frontmatter + md_text

             if md_text:
                 with open(md_path, "w", encoding='utf-8') as f:
                     f.write(md_text)
                 return md_path
        
        except Exception as e:
             print(f"Error converting {original_filename}: {e}")
             pass
        
        return None

    def create_feedback_markdown(self, submission_data, output_dir):
        """Creates a markdown file from the inline feedback text for submissions without attachments."""
        if not submission_data or not output_dir:
            return None
        
        # Get organization/user name for filename
        org = submission_data.get('organization')
        if not org:
            first = submission_data.get('firstName', '')
            last = submission_data.get('surname', '')
            if first or last:
                org = f"{first}_{last}".strip()
        
        if not org:
            org = "Anonymous"
        
        sanitized_org = sanitize_filename(org)
        new_filename = f"{sanitized_org}.md"
        
        # Handle collisions
        md_path = os.path.join(output_dir, new_filename)
        counter = 1
        while os.path.exists(md_path):
            new_filename = f"{sanitized_org}_{counter}.md"
            md_path = os.path.join(output_dir, new_filename)
            counter += 1
        
        try:
            # Build frontmatter
            frontmatter = "---\n"
            clean_data = {k: v for k, v in submission_data.items() if k not in ['local_attachments', 'local_markdowns']}
            
            if self.initiative_title:
                clean_data['initiativeTitle'] = self.initiative_title
            
            frontmatter += yaml.safe_dump(clean_data, allow_unicode=True)
            frontmatter += "---\n\n"
            
            # Get the feedback text
            feedback_text = submission_data.get('feedback', '')
            if not feedback_text:
                feedback_text = "*No feedback text provided.*"
            
            md_content = frontmatter + feedback_text
            
            with open(md_path, "w", encoding='utf-8') as f:
                f.write(md_content)
            
            return md_path
        
        except Exception as e:
            print(f"Error creating feedback markdown for {sanitized_org}: {e}")
            return None

    def fetch_all_submissions(self, attachment_dir=None, markdown_dir=None):
        """Generates all feedback submissions."""
        if not self.publication_id:
            self.get_publication_id()
            
        if attachment_dir and not os.path.exists(attachment_dir):
            os.makedirs(attachment_dir)
            
        if markdown_dir and not os.path.exists(markdown_dir):
            os.makedirs(markdown_dir)

        page = 0
        size = 50 # Maximize page size to reduce requests (often APIs accept up to 100)
        total_fetched = 0
        total_elements = None

        print("Starting to scrape submissions...")

        while True:
            # https://ec.europa.eu/info/law/better-regulation/api/allFeedback?publicationId=21878&keywords=&language=EN&page=0&size=10&sort=dateFeedback,DESC
            params = {
                "publicationId": self.publication_id,
                "keywords": "",
                # "language": "EN",
                "page": page,
                "size": size,
                "sort": "dateFeedback,DESC"
            }
            
            # Removing language param to see if we get all languages
            
            url = f"{self.BASE_API_URL}/api/allFeedback"
            try:
                response = self.session.get(url, params=params)
                response.raise_for_status()
                data = response.json()
                
                content = data.get('content', [])
                # The page info can be directly in root or in 'page' dict depending on API version.
                # Debug output showed 'totalElements' in root.
                total_elements = data.get('totalElements', 0)
                
                if not content:
                    break
                
                for item in content:
                    item['local_attachments'] = []
                    item['local_markdowns'] = []
                    
                    has_attachments = 'attachments' in item and item['attachments']
                    
                    # Download and convert attachments if available
                    if attachment_dir and has_attachments:
                        for att in item['attachments']:
                             path = self.download_attachment(att, attachment_dir, submission_data=item)
                             if path:
                                 item['local_attachments'].append(path)
                                 if markdown_dir:
                                     md_path = self.convert_to_markdown(path, markdown_dir, submission_data=item)
                                     if md_path:
                                         item['local_markdowns'].append(md_path)
                    
                    # If no attachments (or no successful markdown conversions), create markdown from inline feedback
                    if markdown_dir and not item['local_markdowns']:
                        md_path = self.create_feedback_markdown(item, markdown_dir)
                        if md_path:
                            item['local_markdowns'].append(md_path)

                    yield item
                
                total_fetched += len(content)
                print(f"Fetched {total_fetched} / {total_elements} submissions...")
                
                if total_fetched >= total_elements:
                    break
                
                page += 1
                time.sleep(0.5) # Be nice to the API

            except Exception as e:
                print(f"Error fetching page {page}: {e}")
                break

    def save_to_json(self, submissions, filename):
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(submissions, f, indent=2, ensure_ascii=False)
        print(f"Saved {len(submissions)} submissions to {filename}")

def main():
    parser = argparse.ArgumentParser(description="Scrape EU Consultation Submissions")
    parser.add_argument("url", help="URL of the initiative")
    parser.add_argument("--output", "-o", help="Output JSON filename")
    
    args = parser.parse_args()

    if not args.url:
        args.url = "https://ec.europa.eu/info/law/better-regulation/have-your-say/initiatives/14842-Chips-Act-2_en"
    
    scraper = EUConsultationScraper(args.url)
    
    # We need to fetch publication ID to get the title first
    if not scraper.publication_id:
        scraper.get_publication_id()

    # Create directory for attachments
    # Use title if available, else ID
    base_name = scraper.initiative_title if scraper.initiative_title else scraper.initiative_id
    initiative_dir = f"attachments/{base_name}"
    markdown_dir = f"markdown/{base_name}"
    
    all_submissions = []
    try:
        for submission in scraper.fetch_all_submissions(attachment_dir=initiative_dir, markdown_dir=markdown_dir):
            all_submissions.append(submission)
    except KeyboardInterrupt:
        print("\nScraping interrupted. Saving what we have...")
    
    output_file = args.output
    if not output_file:
        # Generate filename from initiative title
        output_file = f"submissions_{base_name}.json"
        
    scraper.save_to_json(all_submissions, output_file)

if __name__ == "__main__":
    main()
