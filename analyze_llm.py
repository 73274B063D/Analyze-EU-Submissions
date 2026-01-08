
import os
import glob
import json
import pandas as pd
import re
import yaml
from dotenv import load_dotenv
from openai import OpenAI
from fpdf import FPDF
import time
import sys

def safe_print(text):
    """Safely prints text, handling Unicode encoding errors."""
    try:
        print(text)
    except UnicodeEncodeError:
        # Fallback: encode to ASCII with error handling
        print(text.encode('ascii', 'replace').decode('ascii'))

def sanitize_for_pdf(text):
    """Sanitizes text for PDF output by replacing problematic Unicode characters."""
    if not text:
        return ""
    # Replace common problematic Unicode characters with ASCII equivalents
    replacements = {
        '\u2011': '-',  # Non-breaking hyphen
        '\u2013': '-',  # En dash
        '\u2014': '--',  # Em dash
        '\u2018': "'",  # Left single quotation mark
        '\u2019': "'",  # Right single quotation mark
        '\u201C': '"',  # Left double quotation mark
        '\u201D': '"',  # Right double quotation mark
        '\u2026': '...',  # Ellipsis
    }
    result = str(text)
    for unicode_char, ascii_char in replacements.items():
        result = result.replace(unicode_char, ascii_char)
    # Fallback: encode to ASCII with error handling for any remaining problematic characters
    try:
        result.encode('latin-1')
    except UnicodeEncodeError:
        result = result.encode('ascii', 'replace').decode('ascii')
    return result


# Configuration

target_file = "The Centre for Future Generations.md"
target_org = "Centre for Future Generations"
base_dir = "markdown/2025 Strategic Foresight Report"
model = "gpt-5-mini"

# Load environment variables
load_dotenv()

# Initialize OpenAI Client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Keys used to store LLM analysis in frontmatter
LLM_KEYS = ['llm_alignment_score', 'llm_verdict', 'llm_agreements', 'llm_disagreements']

def parse_frontmatter(content):
    """Parses YAML frontmatter from markdown content. Returns (frontmatter_dict, body)."""
    match = re.match(r'^---\r?\n(.*?)\r?\n---\r?\n?(.*)', content, flags=re.DOTALL)
    if match:
        try:
            fm = yaml.safe_load(match.group(1)) or {}
            body = match.group(2)
            return fm, body
        except yaml.YAMLError:
            return {}, content
    return {}, content

def has_llm_data(frontmatter):
    """Checks if frontmatter already contains LLM analysis data."""
    return all(key in frontmatter for key in LLM_KEYS)

def get_llm_data_from_frontmatter(frontmatter):
    """Extracts LLM analysis data from frontmatter."""
    return {
        'alignment_score': frontmatter.get('llm_alignment_score'),
        'verdict': frontmatter.get('llm_verdict'),
        'alignment_summary': frontmatter.get('llm_agreements'),
        'divergence_summary': frontmatter.get('llm_disagreements')
    }

def update_frontmatter_with_llm(filepath, llm_result):
    """Updates a markdown file's frontmatter with LLM analysis results."""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    frontmatter, body = parse_frontmatter(content)
    
    # Add LLM data
    frontmatter['llm_alignment_score'] = llm_result.get('alignment_score')
    frontmatter['llm_verdict'] = llm_result.get('verdict')
    frontmatter['llm_agreements'] = llm_result.get('alignment_summary')
    frontmatter['llm_disagreements'] = llm_result.get('divergence_summary')
    
    # Rebuild the file
    new_content = "---\n" + yaml.dump(frontmatter, allow_unicode=True, default_flow_style=False, sort_keys=False) + "---\n" + body
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(new_content)

def load_markdown_files(directory):
    """Loads all markdown files from the directory. Returns filepaths, filenames, raw contents, and bodies."""
    files = glob.glob(os.path.join(directory, "*.md"))
    filepaths = []
    filenames = []
    raw_contents = []
    bodies = []
    
    safe_print(f"Found {len(files)} markdown files in {directory}")
    
    for f in files:
        try:
            with open(f, 'r', encoding='utf-8') as file:
                content = file.read()
                _, body = parse_frontmatter(content)
                filepaths.append(f)
                filenames.append(os.path.basename(f))
                raw_contents.append(content)
                bodies.append(body)
        except Exception as e:
            safe_print(f"Error reading {f}: {e}")
            
    return filepaths, filenames, raw_contents, bodies

def compare_submissions(target_org, target_text, other_org, other_text):
    """Uses OpenAI to compare two submissions."""
    
    prompt = f"""
    You are an expert policy analyst. Compare the following two submissions to the EU Chips Act consultation.
    
    Task: Analyze the alignment between Submission A and Submission B.
    
    Output a JSON object with the following fields:
    - "alignment_score": An integer from 0 (Completely Opposed) to 10 (Perfectly Aligned).
    - "alignment_summary": A concise summary (2-3 sentences) of key points where they AGREE.
    - "divergence_summary": A concise summary (2-3 sentences) of key points where they DISAGREE or have different priorities.
    - "verdict": One of "Likely Ally", "Neutral", "Opponent".
    
    For the alignment and divergence summaries, do not reference what the submission from our organisation is about we know what is in there. Focus on where there is agreement, and where there is divergence.
    
    Ensure the output is valid JSON.

    Submission A (Our Organization - {target_org}):
    {target_text} 
    End of Submission A
    
    Submission B (Other Organization - {other_org}):
    {other_text}
    
    End of Submission B
    """
    
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are a helpful assistant that outputs JSON."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"}
        )
        content = response.choices[0].message.content
        return json.loads(content)
    except Exception as e:
        safe_print(f"Error analyzing {other_org}: {e}")
        return {
            "alignment_score": 0,
            "alignment_summary": "Error",
            "divergence_summary": f"Analysis failed: {e}",
            "verdict": "Error"
        }

def generate_pdf_report(df, target_org, output_path="llm_analysis_report.pdf"):
    """Generates a PDF report of the alignment analysis."""
    
    class PDF(FPDF):
        def header(self):
            self.set_font('Helvetica', 'B', 16)
            safe_org = sanitize_for_pdf(target_org)
            self.cell(0, 10, f'Stakeholder Alignment Report: {safe_org}', ln=True, align='C')
            self.ln(5)
        
        def footer(self):
            self.set_y(-15)
            self.set_font('Helvetica', 'I', 8)
            self.cell(0, 10, f'Page {self.page_no()}', align='C')
    
    pdf = PDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    
    # Store link destinations for each organization
    org_links = {}
    
    # Table of Contents
    pdf.set_font('Helvetica', 'B', 16)
    safe_org = sanitize_for_pdf(target_org)
    pdf.cell(0, 10, 'Table of Contents', ln=True, align='C')
    pdf.ln(10)
    
    pdf.set_font('Helvetica', 'B', 10)
    pdf.set_fill_color(240, 240, 240)
    pdf.cell(100, 8, 'Organization', border=1, fill=True)
    pdf.cell(25, 8, 'Score', border=1, fill=True, align='C')
    pdf.cell(65, 8, 'Verdict', border=1, fill=True, align='C')
    pdf.ln()
    
    # Create links in ToC - we'll set destinations later
    pdf.set_font('Helvetica', '', 9)
    toc_y_start = pdf.get_y()
    for idx, (_, row) in enumerate(df.iterrows()):
        org_name = sanitize_for_pdf(str(row['Organization']))
        org_key = str(row['Organization'])  # Use original for key
        # Truncate long names for ToC display
        display_name = org_name[:45] + '...' if len(org_name) > 45 else org_name
        score = row['LLM_Alignment_Score']
        verdict = sanitize_for_pdf(str(row['Verdict']))
        
        # Create link - we'll set the destination when we create the detailed section
        link_id = pdf.add_link()
        org_links[org_key] = link_id
        
        y_pos = pdf.get_y()
        pdf.link(10, y_pos, 100, 6, link_id)
        pdf.cell(100, 6, display_name, border=1)
        pdf.cell(25, 6, str(score), border=1, align='C')
        pdf.cell(65, 6, verdict, border=1, align='C')
        pdf.ln()
    
    pdf.add_page()
    
    # Summary stats
    pdf.set_font('Helvetica', 'B', 12)
    pdf.cell(0, 10, f'Total Stakeholders Analyzed: {len(df)}', ln=True)
    
    allies = df[df['Verdict'] == 'Likely Ally']
    opponents = df[df['Verdict'] == 'Opponent']
    neutrals = df[df['Verdict'] == 'Neutral']
    
    pdf.set_font('Helvetica', '', 10)
    pdf.cell(0, 8, f'Likely Allies: {len(allies)} | Neutral: {len(neutrals)} | Opponents: {len(opponents)}', ln=True)
    pdf.ln(5)
    
    # Top Allies Section
    pdf.set_font('Helvetica', 'B', 14)
    pdf.set_fill_color(200, 230, 200)
    pdf.cell(0, 10, 'Top Allies (High Alignment)', ln=True, fill=True)
    pdf.ln(3)
    
    top_allies = df.head(10)
    for _, row in top_allies.iterrows():
        org_key = str(row['Organization'])
        if org_key in org_links:
            # Set destination for this organization (page and y position)
            pdf.set_link(org_links[org_key], page=pdf.page_no(), y=pdf.get_y())
        
        pdf.set_font('Helvetica', 'B', 11)
        score = row['LLM_Alignment_Score']
        org_name = sanitize_for_pdf(row['Organization'])
        verdict = sanitize_for_pdf(row['Verdict'])
        pdf.cell(0, 8, f"{org_name} - Score: {score}/10 ({verdict})", ln=True)
        
        pdf.set_font('Helvetica', '', 9)
        agreements = sanitize_for_pdf(str(row['Agreements']))
        pdf.multi_cell(0, 5, f"Agreements: {agreements}")
        pdf.ln(2)
        pdf.set_font('Helvetica', '', 9)
        disagreements = sanitize_for_pdf(str(row['Disagreements']))
        pdf.multi_cell(0, 5, f"Disagreements: {disagreements}")
        pdf.ln(2)
    
    # Top Opponents Section
    pdf.add_page()
    pdf.set_font('Helvetica', 'B', 14)
    pdf.set_fill_color(230, 200, 200)
    pdf.cell(0, 10, 'Top Opponents/Divergent (Low Alignment)', ln=True, fill=True)
    pdf.ln(3)
    
    top_opponents = df.tail(10).sort_values(by="LLM_Alignment_Score", ascending=True)
    for _, row in top_opponents.iterrows():
        org_key = str(row['Organization'])
        if org_key in org_links:
            # Set destination for this organization (page and y position)
            pdf.set_link(org_links[org_key], page=pdf.page_no(), y=pdf.get_y())
        
        pdf.set_font('Helvetica', 'B', 11)
        score = row['LLM_Alignment_Score']
        org_name = sanitize_for_pdf(row['Organization'])
        verdict = sanitize_for_pdf(row['Verdict'])
        pdf.cell(0, 8, f"{org_name} - Score: {score}/10 ({verdict})", ln=True)
        
        pdf.set_font('Helvetica', '', 9)
        agreements = sanitize_for_pdf(str(row['Agreements']))
        pdf.multi_cell(0, 5, f"Agreements: {agreements}")
        pdf.ln(2)
        pdf.set_font('Helvetica', '', 9)
        disagreements = sanitize_for_pdf(str(row['Disagreements']))
        pdf.multi_cell(0, 5, f"Disagreements: {disagreements}")
        pdf.ln(2)
    
    # Detailed sections for all organizations
    pdf.add_page()
    pdf.set_font('Helvetica', 'B', 14)
    pdf.cell(0, 10, 'Detailed Analysis - All Organizations', ln=True)
    pdf.ln(5)
    
    # Create detailed sections for all organizations
    for _, row in df.iterrows():
        org_key = str(row['Organization'])
        if org_key in org_links:
            # Set destination for this organization (page and y position)
            pdf.set_link(org_links[org_key], page=pdf.page_no(), y=pdf.get_y())
        
        pdf.set_font('Helvetica', 'B', 11)
        score = row['LLM_Alignment_Score']
        org_name = sanitize_for_pdf(row['Organization'])
        verdict = sanitize_for_pdf(row['Verdict'])
        pdf.cell(0, 8, f"{org_name} - Score: {score}/10 ({verdict})", ln=True)
        
        pdf.set_font('Helvetica', '', 9)
        agreements = sanitize_for_pdf(str(row['Agreements']))
        pdf.multi_cell(0, 5, f"Agreements: {agreements}")
        pdf.ln(2)
        pdf.set_font('Helvetica', '', 9)
        disagreements = sanitize_for_pdf(str(row['Disagreements']))
        pdf.multi_cell(0, 5, f"Disagreements: {disagreements}")
        pdf.ln(5)
    
    # Full table
    pdf.add_page()
    pdf.set_font('Helvetica', 'B', 14)
    pdf.cell(0, 10, 'Full Results Summary', ln=True)
    pdf.ln(3)
    
    # Table header
    pdf.set_font('Helvetica', 'B', 9)
    pdf.set_fill_color(220, 220, 220)
    pdf.cell(80, 8, 'Organization', border=1, fill=True)
    pdf.cell(20, 8, 'Score', border=1, fill=True, align='C')
    pdf.cell(30, 8, 'Verdict', border=1, fill=True, align='C')
    pdf.ln()
    
    # Table rows
    pdf.set_font('Helvetica', '', 8)
    for _, row in df.iterrows():
        org_name = sanitize_for_pdf(str(row['Organization'])[:40])
        verdict = sanitize_for_pdf(str(row['Verdict'])[:15])
        pdf.cell(80, 7, org_name, border=1)
        pdf.cell(20, 7, str(row['LLM_Alignment_Score']), border=1, align='C')
        pdf.cell(30, 7, verdict, border=1, align='C')
        pdf.ln()
    
    pdf.output(output_path)
    safe_print(f"PDF report saved to {output_path}")

def analyze_llm(base_dir, target_file, target_org, model):
    # Configuration
    if not os.path.exists(base_dir):
        # Fallback search
        subdirs = [d for d in os.listdir("markdown") if os.path.isdir(os.path.join("markdown", d))]
        if subdirs:
            base_dir = os.path.join("markdown", subdirs[0])
        else:
            safe_print("Markdown directory not found.")
            return
    
    # 1. Load Data
    filepaths, filenames, raw_contents, bodies = load_markdown_files(base_dir)
    if target_file not in filenames:
        safe_print("Target file not found.")
        return
    
    target_index = filenames.index(target_file)
    target_text = bodies[target_index]
    
    # 2. Analyze all submissions
    indices_to_analyze = [i for i in range(len(filenames)) if i != target_index]
    
    safe_print(f"\n--- LLM Analysis of {len(indices_to_analyze)} submissions ---")
    
    results = []
    cached_count = 0
    api_count = 0
    
    for idx in indices_to_analyze:
        other_filepath = filepaths[idx]
        other_filename = filenames[idx]
        other_text = bodies[idx]
        other_org = os.path.splitext(other_filename)[0]
        
        # Check if LLM data already exists in frontmatter
        frontmatter, _ = parse_frontmatter(raw_contents[idx])
        
        if has_llm_data(frontmatter):
            # Use cached data from frontmatter
            llm_result = get_llm_data_from_frontmatter(frontmatter)
            safe_print(f"[CACHED] {other_org}")
            cached_count += 1
        else:
            # Make LLM call and update the file
            safe_print(f"[API] Analyzing {other_org}...")
            llm_result = compare_submissions(target_org, target_text, other_org, other_text)
            
            # Save results to frontmatter
            update_frontmatter_with_llm(other_filepath, llm_result)
            api_count += 1
            
            # Rate limit safety
            time.sleep(0.5)
        
        result_entry = {
            "Organization": other_org,
            "LLM_Alignment_Score": llm_result.get('alignment_score'),
            "Verdict": llm_result.get('verdict'),
            "Agreements": llm_result.get('alignment_summary'),
            "Disagreements": llm_result.get('divergence_summary')
        }
        results.append(result_entry)
    
    safe_print(f"\n--- Summary: {cached_count} cached, {api_count} API calls ---") 

    # Save Results
    df = pd.DataFrame(results)
    
    # Sort by LLM Score
    df = df.sort_values(by="LLM_Alignment_Score", ascending=False)
    
    csv_path = "llm_analysis_report.csv"
    df.to_csv(csv_path, index=False)
    safe_print(f"\nAnalysis complete. Saved to {csv_path}")
    
    # Generate Markdown Summary
    md_path = "llm_analysis_summary.md"
    with open(md_path, 'w', encoding='utf-8') as f:
        f.write(f"# AI Analysis: Centre for Future Generations Alignment\n\n")
        f.write(f"Analyzed {len(results)} submissions.\n\n")
        
        f.write("## Top Allies (High Alignment Score)\n")
        top_allies = df.head(10)
        for _, row in top_allies.iterrows():
            f.write(f"### {row['Organization']} (Score: {row['LLM_Alignment_Score']}/10)\n")
            f.write(f"- **Verdict**: {row['Verdict']}\n")
            f.write(f"- **Agreements**: {row['Agreements']}\n")
            f.write(f"- **Disagreements**: {row['Disagreements']}\n\n")
            
        f.write("## Top Opponents/Divergent (Low Alignment Score)\n")
        top_opponents = df.tail(10).sort_values(by="LLM_Alignment_Score", ascending=True)
        for _, row in top_opponents.iterrows():
            f.write(f"### {row['Organization']} (Score: {row['LLM_Alignment_Score']}/10)\n")
            f.write(f"- **Verdict**: {row['Verdict']}\n")
            f.write(f"- **Agreements**: {row['Agreements']}\n")
            f.write(f"- **Disagreements**: {row['Disagreements']}\n\n")
            
    safe_print(f"Markdown summary saved to {md_path}")
    
    # Generate PDF Report
    generate_pdf_report(df, target_org)

if __name__ == "__main__":
    analyze_llm(base_dir, target_file, target_org, model)
