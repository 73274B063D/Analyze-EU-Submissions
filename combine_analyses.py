"""
Combines and compares LLM and Embeddings analysis results.

This script merges results from both analysis methods and generates
comparison reports showing alignment and divergence between the two approaches.
"""

import os
import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional
import json
import re
import yaml
from fpdf import FPDF
import matplotlib.pyplot as plt
import seaborn as sns
import warnings
warnings.filterwarnings('ignore')

def safe_print(text):
    """Safely prints text, handling Unicode encoding errors."""
    try:
        print(text)
    except UnicodeEncodeError:
        print(text.encode('ascii', 'replace').decode('ascii'))

def sanitize_for_pdf(text):
    """Sanitizes text for PDF output."""
    if not text:
        return ""
    replacements = {
        '\u2011': '-',
        '\u2013': '-',
        '\u2014': '--',
        '\u2018': "'",
        '\u2019': "'",
        '\u201C': '"',
        '\u201D': '"',
        '\u2026': '...',
    }
    result = str(text)
    for unicode_char, ascii_char in replacements.items():
        result = result.replace(unicode_char, ascii_char)
    try:
        result.encode('latin-1')
    except UnicodeEncodeError:
        result = result.encode('ascii', 'replace').decode('ascii')
    return result

def load_llm_results(initiative_base_dir: str) -> Optional[pd.DataFrame]:
    """Loads LLM analysis results from CSV."""
    # initiative_base_dir is like "outputs/2025 Strategic Foresight Report"
    llm_csv = os.path.join(initiative_base_dir, "llm", "llm_analysis_report.csv")
    if os.path.exists(llm_csv):
        return pd.read_csv(llm_csv)
    return None

def load_embeddings_results(initiative_base_dir: str) -> Optional[Tuple[pd.DataFrame, pd.DataFrame]]:
    """Loads embeddings analysis results (org summary and similarity pairs)."""
    # initiative_base_dir is like "outputs/2025 Strategic Foresight Report"
    org_summary_csv = os.path.join(initiative_base_dir, "embeddings", "embeddings_org_summary.csv")
    similarity_pairs_csv = os.path.join(initiative_base_dir, "embeddings", "embeddings_similarity_pairs.csv")
    
    org_summary = None
    similarity_pairs = None
    
    if os.path.exists(org_summary_csv):
        org_summary = pd.read_csv(org_summary_csv)
    
    if os.path.exists(similarity_pairs_csv):
        similarity_pairs = pd.read_csv(similarity_pairs_csv)
    
    if org_summary is not None or similarity_pairs is not None:
        return org_summary, similarity_pairs
    return None

def normalize_org_name(name: str) -> str:
    """Normalizes organization names for matching."""
    if pd.isna(name) or name is None:
        return ""
    return str(name).strip().lower()

def combine_results(
    llm_df: pd.DataFrame,
    embeddings_org_summary: pd.DataFrame,
    target_org: str = "Centre for Future Generations"
) -> pd.DataFrame:
    """Combines LLM and embeddings results into a single DataFrame."""
    
    # Create normalized name mappings (filter out NaN/None)
    llm_names = {normalize_org_name(name): name for name in llm_df['Organization'].dropna().unique()}
    embeddings_names = {normalize_org_name(name): name for name in embeddings_org_summary['Organization'].dropna().unique()}
    
    # Find common organizations
    common_orgs = set(llm_names.keys()) & set(embeddings_names.keys())
    
    combined_data = []
    
    for norm_name in common_orgs:
        llm_name = llm_names[norm_name]
        emb_name = embeddings_names[norm_name]
        
        llm_row = llm_df[llm_df['Organization'] == llm_name].iloc[0]
        emb_row = embeddings_org_summary[embeddings_org_summary['Organization'] == emb_name].iloc[0]
        
        # Normalize LLM score to 0-1 scale (it's 0-10)
        llm_score_norm = llm_row['LLM_Alignment_Score'] / 10.0 if pd.notna(llm_row['LLM_Alignment_Score']) else 0.0
        emb_score = emb_row['Average_Similarity'] if pd.notna(emb_row['Average_Similarity']) else 0.0
        
        # Calculate difference and correlation
        score_diff = abs(llm_score_norm - emb_score)
        score_avg = (llm_score_norm + emb_score) / 2.0
        
        combined_data.append({
            'Organization': llm_name,
            'Initiative': emb_row.get('Initiative', ''),
            'LLM_Score': llm_row['LLM_Alignment_Score'],
            'LLM_Score_Normalized': llm_score_norm,
            'LLM_Verdict': llm_row['Verdict'],
            'Embeddings_Score': emb_score,
            'Embeddings_Cluster': int(emb_row.get('Cluster', -1)),
            'Score_Difference': score_diff,
            'Score_Average': score_avg,
            'Agreement_Level': 'High' if score_diff < 0.15 else ('Medium' if score_diff < 0.3 else 'Low'),
            'LLM_Agreements': llm_row.get('Agreements', ''),
            'LLM_Disagreements': llm_row.get('Disagreements', '')
        })
    
    combined_df = pd.DataFrame(combined_data)
    
    # Sort by average score (highest alignment first)
    combined_df = combined_df.sort_values('Score_Average', ascending=False)
    
    return combined_df

def generate_comparison_report(
    combined_df: pd.DataFrame,
    output_dir: str,
    target_org: str = "Centre for Future Generations"
):
    """Generates comparison reports in CSV, Markdown, and PDF formats."""
    
    # Save CSV
    csv_path = os.path.join(output_dir, "combined_analysis_report.csv")
    combined_df.to_csv(csv_path, index=False)
    safe_print(f"Saved combined analysis to {csv_path}")
    
    # Generate Markdown report
    md_path = os.path.join(output_dir, "combined_analysis_report.md")
    with open(md_path, 'w', encoding='utf-8') as f:
        f.write("# Combined LLM and Embeddings Analysis Report\n\n")
        f.write(f"**Target Organization**: {target_org}\n\n")
        f.write(f"**Total Organizations Analyzed**: {len(combined_df)}\n\n")
        
        # Statistics
        f.write("## Summary Statistics\n\n")
        f.write(f"- **Average LLM Score**: {combined_df['LLM_Score'].mean():.2f}/10\n")
        f.write(f"- **Average Embeddings Score**: {combined_df['Embeddings_Score'].mean():.3f}\n")
        f.write(f"- **Average Score Difference**: {combined_df['Score_Difference'].mean():.3f}\n")
        f.write(f"- **High Agreement** (diff < 0.15): {len(combined_df[combined_df['Agreement_Level'] == 'High'])}\n")
        f.write(f"- **Medium Agreement** (0.15 ≤ diff < 0.3): {len(combined_df[combined_df['Agreement_Level'] == 'Medium'])}\n")
        f.write(f"- **Low Agreement** (diff ≥ 0.3): {len(combined_df[combined_df['Agreement_Level'] == 'Low'])}\n\n")
        
        # Top aligned organizations
        f.write("## Top 20 Most Aligned Organizations (Combined Score)\n\n")
        top_orgs = combined_df.head(20)
        for _, row in top_orgs.iterrows():
            f.write(f"### {row['Organization']}\n")
            f.write(f"- **LLM Score**: {row['LLM_Score']}/10 ({row['LLM_Verdict']})\n")
            f.write(f"- **Embeddings Score**: {row['Embeddings_Score']:.3f}\n")
            f.write(f"- **Combined Average**: {row['Score_Average']:.3f}\n")
            f.write(f"- **Agreement Level**: {row['Agreement_Level']}\n")
            f.write(f"- **Embeddings Cluster**: {row['Embeddings_Cluster']}\n\n")
        
        # Divergences
        f.write("## Organizations with Divergent Scores\n\n")
        f.write("These organizations show significant differences between LLM and embeddings analysis:\n\n")
        divergent = combined_df[combined_df['Agreement_Level'] == 'Low'].head(10)
        for _, row in divergent.iterrows():
            f.write(f"### {row['Organization']}\n")
            f.write(f"- **LLM Score**: {row['LLM_Score']}/10\n")
            f.write(f"- **Embeddings Score**: {row['Embeddings_Score']:.3f}\n")
            f.write(f"- **Difference**: {row['Score_Difference']:.3f}\n\n")
    
    safe_print(f"Saved markdown report to {md_path}")
    
    # Generate PDF report
    pdf_path = os.path.join(output_dir, "combined_analysis_report.pdf")
    generate_comparison_pdf(combined_df, pdf_path, target_org)
    
    return csv_path, md_path, pdf_path

def generate_comparison_pdf(
    combined_df: pd.DataFrame,
    output_path: str,
    target_org: str = "Centre for Future Generations"
):
    """Generates a PDF report comparing LLM and embeddings results."""
    
    class PDF(FPDF):
        def header(self):
            self.set_font('Helvetica', 'B', 16)
            self.cell(0, 10, 'Combined LLM & Embeddings Analysis', ln=True, align='C')
            self.ln(5)
        
        def footer(self):
            self.set_y(-15)
            self.set_font('Helvetica', 'I', 8)
            self.cell(0, 10, f'Page {self.page_no()}', align='C')
    
    pdf = PDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    
    # Title
    pdf.set_font('Helvetica', 'B', 20)
    pdf.cell(0, 20, 'Combined Analysis Report', ln=True, align='C')
    pdf.ln(10)
    pdf.set_font('Helvetica', '', 12)
    pdf.cell(0, 10, f'Target Organization: {sanitize_for_pdf(target_org)}', ln=True, align='C')
    pdf.cell(0, 10, f'Total Organizations: {len(combined_df)}', ln=True, align='C')
    pdf.ln(15)
    
    # Summary Statistics
    pdf.set_font('Helvetica', 'B', 16)
    pdf.cell(0, 10, 'Summary Statistics', ln=True)
    pdf.ln(5)
    
    pdf.set_font('Helvetica', '', 10)
    stats = [
        f"Average LLM Score: {combined_df['LLM_Score'].mean():.2f}/10",
        f"Average Embeddings Score: {combined_df['Embeddings_Score'].mean():.3f}",
        f"Average Score Difference: {combined_df['Score_Difference'].mean():.3f}",
        f"High Agreement (diff < 0.15): {len(combined_df[combined_df['Agreement_Level'] == 'High'])}",
        f"Medium Agreement (0.15 <= diff < 0.3): {len(combined_df[combined_df['Agreement_Level'] == 'Medium'])}",
        f"Low Agreement (diff >= 0.3): {len(combined_df[combined_df['Agreement_Level'] == 'Low'])}"
    ]
    
    for stat in stats:
        pdf.cell(0, 8, sanitize_for_pdf(stat), ln=True)
    
    pdf.ln(10)
    
    # Comparison Table
    pdf.set_font('Helvetica', 'B', 16)
    pdf.cell(0, 10, 'Top 30 Most Aligned Organizations', ln=True)
    pdf.ln(5)
    
    pdf.set_font('Helvetica', 'B', 8)
    pdf.set_fill_color(240, 240, 240)
    pdf.cell(60, 7, 'Organization', border=1, fill=True)
    pdf.cell(20, 7, 'LLM Score', border=1, fill=True, align='C')
    pdf.cell(25, 7, 'Emb Score', border=1, fill=True, align='C')
    pdf.cell(25, 7, 'Average', border=1, fill=True, align='C')
    pdf.cell(20, 7, 'Agreement', border=1, fill=True, align='C')
    pdf.cell(20, 7, 'Cluster', border=1, fill=True, align='C')
    pdf.cell(20, 7, 'Verdict', border=1, fill=True, align='C')
    pdf.ln()
    
    pdf.set_font('Helvetica', '', 7)
    top_orgs = combined_df.head(30)
    for _, row in top_orgs.iterrows():
        # Color code by agreement level
        if row['Agreement_Level'] == 'High':
            pdf.set_fill_color(200, 255, 200)
        elif row['Agreement_Level'] == 'Medium':
            pdf.set_fill_color(255, 255, 200)
        else:
            pdf.set_fill_color(255, 200, 200)
        
        org = sanitize_for_pdf(str(row['Organization'])[:28])
        pdf.cell(60, 6, org, border=1, fill=True)
        pdf.cell(20, 6, f"{row['LLM_Score']:.1f}", border=1, fill=True, align='C')
        pdf.cell(25, 6, f"{row['Embeddings_Score']:.3f}", border=1, fill=True, align='C')
        pdf.cell(25, 6, f"{row['Score_Average']:.3f}", border=1, fill=True, align='C')
        pdf.cell(20, 6, row['Agreement_Level'], border=1, fill=True, align='C')
        pdf.cell(20, 6, str(int(row['Embeddings_Cluster'])), border=1, fill=True, align='C')
        verdict = sanitize_for_pdf(str(row['LLM_Verdict'])[:8])
        pdf.cell(20, 6, verdict, border=1, fill=True, align='C')
        pdf.ln()
    
    # Divergences section
    pdf.add_page()
    pdf.set_font('Helvetica', 'B', 16)
    pdf.set_fill_color(255, 200, 200)
    pdf.cell(0, 10, 'Organizations with Divergent Scores', ln=True, fill=True)
    pdf.ln(5)
    
    pdf.set_font('Helvetica', '', 9)
    pdf.cell(0, 6, 'These organizations show significant differences between LLM and embeddings analysis:', ln=True)
    pdf.ln(5)
    
    divergent = combined_df[combined_df['Agreement_Level'] == 'Low'].head(20)
    for idx, (_, row) in enumerate(divergent.iterrows(), 1):
        pdf.set_font('Helvetica', 'B', 10)
        org = sanitize_for_pdf(row['Organization'])
        pdf.cell(0, 8, f"{idx}. {org}", ln=True)
        
        pdf.set_font('Helvetica', '', 9)
        pdf.cell(0, 6, f"  LLM Score: {row['LLM_Score']}/10 ({row['LLM_Verdict']})", ln=True)
        pdf.cell(0, 6, f"  Embeddings Score: {row['Embeddings_Score']:.3f}", ln=True)
        pdf.cell(0, 6, f"  Difference: {row['Score_Difference']:.3f}", ln=True)
        pdf.ln(3)
    
    # Correlation analysis
    pdf.add_page()
    pdf.set_font('Helvetica', 'B', 16)
    pdf.cell(0, 10, 'Correlation Analysis', ln=True)
    pdf.ln(5)
    
    correlation = combined_df['LLM_Score_Normalized'].corr(combined_df['Embeddings_Score'])
    pdf.set_font('Helvetica', '', 10)
    pdf.cell(0, 8, f"Pearson Correlation: {correlation:.3f}", ln=True)
    
    if correlation > 0.7:
        interpretation = "Strong positive correlation - methods agree well"
    elif correlation > 0.4:
        interpretation = "Moderate positive correlation - methods show some agreement"
    elif correlation > 0:
        interpretation = "Weak positive correlation - methods show limited agreement"
    else:
        interpretation = "Negative correlation - methods disagree"
    
    pdf.cell(0, 8, f"Interpretation: {interpretation}", ln=True)
    pdf.ln(10)
    
    # Save PDF
    pdf.output(output_path)
    safe_print(f"Saved PDF report to {output_path}")

def create_comparison_visualization(
    combined_df: pd.DataFrame,
    output_dir: str
):
    """Creates visualization comparing LLM and embeddings scores."""
    
    plt.figure(figsize=(12, 8))
    
    # Scatter plot
    plt.scatter(combined_df['LLM_Score_Normalized'], 
                combined_df['Embeddings_Score'],
                c=combined_df['Score_Difference'],
                cmap='RdYlGn_r',
                s=100,
                alpha=0.6,
                edgecolors='black',
                linewidth=0.5)
    
    plt.colorbar(label='Score Difference')
    plt.xlabel('LLM Score (Normalized 0-1)', fontsize=12)
    plt.ylabel('Embeddings Score (0-1)', fontsize=12)
    plt.title('LLM vs Embeddings Alignment Scores', fontsize=14, pad=20)
    plt.grid(True, alpha=0.3)
    
    # Add diagonal line (perfect agreement)
    plt.plot([0, 1], [0, 1], 'r--', alpha=0.5, label='Perfect Agreement')
    plt.legend()
    
    plt.tight_layout()
    
    viz_path = os.path.join(output_dir, "llm_embeddings_comparison.png")
    plt.savefig(viz_path, dpi=300, bbox_inches='tight')
    plt.close()
    
    safe_print(f"Saved comparison visualization to {viz_path}")

def process_initiative(initiative_base_dir: str, target_org: str = "Centre for Future Generations"):
    """Processes a single initiative's combined analysis."""
    
    safe_print(f"\nProcessing: {initiative_base_dir}")
    
    # Load results
    llm_df = load_llm_results(initiative_base_dir)
    embeddings_results = load_embeddings_results(initiative_base_dir)
    
    if llm_df is None:
        safe_print(f"  No LLM results found for {initiative_base_dir}")
        return None
    
    if embeddings_results is None:
        safe_print(f"  No embeddings results found for {initiative_base_dir}")
        return None
    
    embeddings_org_summary, _ = embeddings_results
    
    if embeddings_org_summary is None:
        safe_print(f"  No embeddings org summary found for {initiative_base_dir}")
        return None
    
    # Combine results
    combined_df = combine_results(llm_df, embeddings_org_summary, target_org)
    
    if len(combined_df) == 0:
        safe_print(f"  No common organizations found between LLM and embeddings results")
        return None
    
    # Create combined output directory
    combined_dir = os.path.join(initiative_base_dir, "combined")
    os.makedirs(combined_dir, exist_ok=True)
    
    # Generate reports
    csv_path, md_path, pdf_path = generate_comparison_report(combined_df, combined_dir, target_org)
    
    # Create visualization
    try:
        create_comparison_visualization(combined_df, combined_dir)
    except Exception as e:
        safe_print(f"  Warning: Could not create visualization: {e}")
    
    return combined_df

def main():
    """Main function to combine analyses across all initiatives."""
    safe_print("=" * 60)
    safe_print("Combined LLM and Embeddings Analysis")
    safe_print("=" * 60)
    
    base_output_dir = "outputs"
    
    if not os.path.exists(base_output_dir):
        safe_print(f"Output directory {base_output_dir} not found.")
        safe_print("Please run analyze_llm.py and analyze_embeddings.py first.")
        return
    
    # Process all initiatives
    initiative_dirs = []
    
    # Check for all_initiatives
    all_initiatives_dir = os.path.join(base_output_dir, "all_initiatives")
    if os.path.exists(all_initiatives_dir):
        initiative_dirs.append(("all_initiatives", all_initiatives_dir))
    
    # Check for individual initiatives
    for item in os.listdir(base_output_dir):
        item_path = os.path.join(base_output_dir, item)
        if os.path.isdir(item_path) and item != "all_initiatives":
            initiative_dirs.append((item, item_path))
    
    if not initiative_dirs:
        safe_print("No initiative directories found.")
        return
    
    safe_print(f"\nFound {len(initiative_dirs)} initiative(s) to process:")
    for name, path in initiative_dirs:
        safe_print(f"  - {name}")
    
    # Process each initiative
    all_combined = []
    for name, path in initiative_dirs:
        combined_df = process_initiative(path, "Centre for Future Generations")
        if combined_df is not None:
            combined_df['Initiative_Name'] = name
            all_combined.append(combined_df)
    
    if all_combined:
        # Create cross-initiative combined report
        if len(all_combined) > 1:
            safe_print("\n--- Creating Cross-Initiative Combined Report ---")
            all_combined_df = pd.concat(all_combined, ignore_index=True)
            
            combined_dir = os.path.join(base_output_dir, "all_initiatives", "combined")
            os.makedirs(combined_dir, exist_ok=True)
            
            csv_path, md_path, pdf_path = generate_comparison_report(
                all_combined_df, combined_dir, "Centre for Future Generations"
            )
            
            try:
                create_comparison_visualization(all_combined_df, combined_dir)
            except Exception as e:
                safe_print(f"Warning: Could not create visualization: {e}")
    
    safe_print("\n" + "=" * 60)
    safe_print("Combined Analysis Complete!")
    safe_print("=" * 60)

if __name__ == "__main__":
    main()
