"""
Embeddings-based alignment analysis across all submissions.

This script uses local sentence-transformers to generate embeddings for all submissions
and identify alignment patterns across all organizations without requiring API calls.
"""

import os
import glob
import json
import re
import yaml
import pandas as pd
import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.cluster import KMeans, DBSCAN
from sklearn.decomposition import PCA
import matplotlib.pyplot as plt
import seaborn as sns
from typing import List, Tuple, Dict
import warnings
from fpdf import FPDF
warnings.filterwarnings('ignore')

def safe_print(text):
    """Safely prints text, handling Unicode encoding errors."""
    try:
        print(text)
    except UnicodeEncodeError:
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

def load_all_markdown_files(base_dir="markdown"):
    """Loads all markdown files from all subdirectories."""
    all_filepaths = []
    all_filenames = []
    all_bodies = []
    all_frontmatters = []
    all_initiatives = []
    
    if not os.path.exists(base_dir):
        safe_print(f"Directory {base_dir} not found.")
        return [], [], [], [], []
    
    # Find all subdirectories
    subdirs = [d for d in os.listdir(base_dir) 
               if os.path.isdir(os.path.join(base_dir, d))]
    
    safe_print(f"Found {len(subdirs)} initiative directories: {subdirs}")
    
    for subdir in subdirs:
        subdir_path = os.path.join(base_dir, subdir)
        files = glob.glob(os.path.join(subdir_path, "*.md"))
        
        safe_print(f"Loading {len(files)} files from {subdir}...")
        
        for f in files:
            try:
                with open(f, 'r', encoding='utf-8') as file:
                    content = file.read()
                    frontmatter, body = parse_frontmatter(content)
                    
                    # Skip if body is too short (likely empty or error)
                    if len(body.strip()) < 100:
                        continue
                    
                    all_filepaths.append(f)
                    all_filenames.append(os.path.basename(f))
                    all_bodies.append(body)
                    all_frontmatters.append(frontmatter)
                    all_initiatives.append(subdir)
            except Exception as e:
                safe_print(f"Error reading {f}: {e}")
    
    safe_print(f"\nTotal submissions loaded: {len(all_filenames)}")
    return all_filepaths, all_filenames, all_bodies, all_frontmatters, all_initiatives

def preprocess_text(text, max_length=8192):
    """Preprocesses text for embedding generation."""
    if not text:
        return ""
    
    # Remove excessive whitespace
    text = re.sub(r'\s+', ' ', text)
    
    # Truncate if too long (sentence-transformers have token limits)
    # Most models handle ~512 tokens, but we'll be conservative
    if len(text) > max_length:
        # Try to truncate at sentence boundary
        truncated = text[:max_length]
        last_period = truncated.rfind('.')
        if last_period > max_length * 0.8:  # If we find a period in the last 20%
            text = truncated[:last_period + 1]
        else:
            text = truncated
    
    return text.strip()

def generate_embeddings(texts: List[str], model_name: str = "all-MiniLM-L6-v2"):
    """Generates embeddings for a list of texts using sentence-transformers."""
    safe_print(f"\nLoading embedding model: {model_name}...")
    model = SentenceTransformer(model_name)
    
    safe_print(f"Generating embeddings for {len(texts)} submissions...")
    
    # Process in batches to show progress
    batch_size = 32
    all_embeddings = []
    
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        batch_embeddings = model.encode(batch, show_progress_bar=False, convert_to_numpy=True)
        all_embeddings.append(batch_embeddings)
        safe_print(f"Processed {min(i + batch_size, len(texts))}/{len(texts)} submissions...")
    
    embeddings = np.vstack(all_embeddings)
    safe_print(f"Generated embeddings with shape: {embeddings.shape}")
    
    return embeddings, model

def compute_similarity_matrix(embeddings: np.ndarray):
    """Computes pairwise cosine similarity matrix."""
    safe_print("\nComputing pairwise similarity matrix...")
    similarity_matrix = cosine_similarity(embeddings)
    safe_print(f"Similarity matrix shape: {similarity_matrix.shape}")
    return similarity_matrix

def identify_clusters(embeddings: np.ndarray, method: str = "kmeans", n_clusters: int = None):
    """Identifies clusters of aligned submissions."""
    safe_print(f"\nIdentifying clusters using {method}...")
    
    if method == "kmeans":
        if n_clusters is None:
            # Heuristic: use sqrt of n/2, but at least 3 and at most 20
            n_clusters = max(3, min(20, int(np.sqrt(len(embeddings) / 2))))
        
        safe_print(f"Using {n_clusters} clusters...")
        kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
        cluster_labels = kmeans.fit_predict(embeddings)
        
    elif method == "dbscan":
        # DBSCAN automatically determines number of clusters
        dbscan = DBSCAN(eps=0.3, min_samples=3, metric='cosine')
        cluster_labels = dbscan.fit_predict(embeddings)
        n_clusters = len(set(cluster_labels)) - (1 if -1 in cluster_labels else 0)
        safe_print(f"DBSCAN identified {n_clusters} clusters (plus {list(cluster_labels).count(-1)} outliers)")
    
    return cluster_labels, n_clusters

def setup_output_directories(base_output_dir: str = "outputs", initiatives: List[str] = None):
    """Creates output directory structure with subfolders for each initiative."""
    if initiatives is None:
        initiatives = []
    
    # Create base output directory
    os.makedirs(base_output_dir, exist_ok=True)
    
    # Create subdirectory for all initiatives (cross-initiative analysis)
    all_initiatives_dir = os.path.join(base_output_dir, "all_initiatives")
    os.makedirs(all_initiatives_dir, exist_ok=True)
    
    # Create embeddings subdirectory
    all_initiatives_emb_dir = os.path.join(all_initiatives_dir, "embeddings")
    os.makedirs(all_initiatives_emb_dir, exist_ok=True)
    
    # Create subdirectories for each unique initiative
    initiative_dirs = {}
    unique_initiatives = set(initiatives) if initiatives else set()
    
    for initiative in unique_initiatives:
        # Sanitize initiative name for filesystem
        safe_name = initiative.replace('/', '_').replace('\\', '_').replace(':', '_')
        initiative_dir = os.path.join(base_output_dir, safe_name)
        os.makedirs(initiative_dir, exist_ok=True)
        
        # Create embeddings subdirectory
        embeddings_dir = os.path.join(initiative_dir, "embeddings")
        os.makedirs(embeddings_dir, exist_ok=True)
        
        initiative_dirs[initiative] = embeddings_dir
    
    return base_output_dir, all_initiatives_emb_dir, initiative_dirs

def generate_alignment_report(
    filenames: List[str],
    initiatives: List[str],
    similarity_matrix: np.ndarray,
    cluster_labels: np.ndarray,
    output_dir: str = "."
):
    """Generates comprehensive alignment reports."""
    
    # Extract organization names (remove .md extension)
    org_names = [os.path.splitext(f)[0] for f in filenames]
    
    # Create DataFrame with similarity scores
    safe_print("\nGenerating alignment reports...")
    
    # 1. Pairwise similarity DataFrame
    similarity_pairs = []
    for i in range(len(org_names)):
        for j in range(i + 1, len(org_names)):
            similarity_pairs.append({
                'Organization_A': org_names[i],
                'Organization_B': org_names[j],
                'Initiative_A': initiatives[i],
                'Initiative_B': initiatives[j],
                'Similarity_Score': similarity_matrix[i, j],
                'Cluster_A': cluster_labels[i],
                'Cluster_B': cluster_labels[j],
                'Same_Cluster': cluster_labels[i] == cluster_labels[j]
            })
    
    similarity_df = pd.DataFrame(similarity_pairs)
    similarity_df = similarity_df.sort_values('Similarity_Score', ascending=False)
    
    # 2. Organization-level summary
    org_summary = []
    for i, org in enumerate(org_names):
        # Get top 5 most similar organizations
        similarities = similarity_matrix[i, :]
        top_indices = np.argsort(similarities)[::-1][1:6]  # Exclude self (index 0)
        
        top_similar = [
            {
                'org': org_names[j],
                'score': float(similarities[j]),
                'cluster': int(cluster_labels[j])
            }
            for j in top_indices
        ]
        
        avg_similarity = float(np.mean(similarities[similarities < 1.0]))  # Exclude self-similarity
        
        org_summary.append({
            'Organization': org,
            'Initiative': initiatives[i],
            'Cluster': int(cluster_labels[i]),
            'Average_Similarity': avg_similarity,
            'Top_5_Similar_Orgs': json.dumps(top_similar)
        })
    
    org_summary_df = pd.DataFrame(org_summary)
    org_summary_df = org_summary_df.sort_values('Average_Similarity', ascending=False)
    
    # 3. Cluster analysis
    cluster_analysis = []
    unique_clusters = sorted(set(cluster_labels))
    
    for cluster_id in unique_clusters:
        if cluster_id == -1:  # DBSCAN outliers
            continue
        
        cluster_orgs = [org_names[i] for i in range(len(org_names)) if cluster_labels[i] == cluster_id]
        cluster_indices = [i for i in range(len(org_names)) if cluster_labels[i] == cluster_id]
        
        # Compute average intra-cluster similarity
        if len(cluster_indices) > 1:
            cluster_similarities = similarity_matrix[np.ix_(cluster_indices, cluster_indices)]
            # Exclude diagonal (self-similarity)
            mask = ~np.eye(len(cluster_indices), dtype=bool)
            avg_intra_similarity = float(np.mean(cluster_similarities[mask]))
        else:
            avg_intra_similarity = 1.0
        
        cluster_analysis.append({
            'Cluster_ID': int(cluster_id),
            'Size': len(cluster_orgs),
            'Average_Intra_Cluster_Similarity': avg_intra_similarity,
            'Organizations': ', '.join(cluster_orgs[:10])  # First 10 orgs
        })
    
    cluster_df = pd.DataFrame(cluster_analysis)
    cluster_df = cluster_df.sort_values('Average_Intra_Cluster_Similarity', ascending=False)
    
    # Save reports
    similarity_csv = os.path.join(output_dir, "embeddings_similarity_pairs.csv")
    similarity_df.to_csv(similarity_csv, index=False)
    safe_print(f"Saved pairwise similarities to {similarity_csv}")
    
    org_summary_csv = os.path.join(output_dir, "embeddings_org_summary.csv")
    org_summary_df.to_csv(org_summary_csv, index=False)
    safe_print(f"Saved organization summary to {org_summary_csv}")
    
    cluster_csv = os.path.join(output_dir, "embeddings_cluster_analysis.csv")
    cluster_df.to_csv(cluster_csv, index=False)
    safe_print(f"Saved cluster analysis to {cluster_csv}")
    
    # Generate markdown report
    md_report = os.path.join(output_dir, "embeddings_analysis_report.md")
    with open(md_report, 'w', encoding='utf-8') as f:
        f.write("# Embeddings-Based Alignment Analysis\n\n")
        f.write(f"Analysed {len(org_names)} submissions across {len(set(initiatives))} initiatives.\n\n")
        
        f.write("## Summary Statistics\n\n")
        f.write(f"- **Total Submissions**: {len(org_names)}\n")
        f.write(f"- **Total Initiatives**: {len(set(initiatives))}\n")
        f.write(f"- **Number of Clusters**: {len(unique_clusters) - (1 if -1 in cluster_labels else 0)}\n")
        f.write(f"- **Average Similarity**: {np.mean(similarity_matrix[similarity_matrix < 1.0]):.3f}\n")
        f.write(f"- **Max Similarity**: {np.max(similarity_matrix[similarity_matrix < 1.0]):.3f}\n")
        f.write(f"- **Min Similarity**: {np.min(similarity_matrix[similarity_matrix < 1.0]):.3f}\n\n")
        
        f.write("## Top 20 Most Aligned Pairs\n\n")
        top_pairs = similarity_df.head(20)
        for _, row in top_pairs.iterrows():
            f.write(f"### {row['Organization_A']} ↔ {row['Organization_B']}\n")
            f.write(f"- **Similarity Score**: {row['Similarity_Score']:.3f}\n")
            f.write(f"- **Initiative A**: {row['Initiative_A']}\n")
            f.write(f"- **Initiative B**: {row['Initiative_B']}\n")
            f.write(f"- **Same Cluster**: {'Yes' if row['Same_Cluster'] else 'No'}\n\n")
        
        f.write("## Cluster Analysis\n\n")
        for _, row in cluster_df.iterrows():
            f.write(f"### Cluster {row['Cluster_ID']} (Size: {row['Size']})\n")
            f.write(f"- **Average Intra-Cluster Similarity**: {row['Average_Intra_Cluster_Similarity']:.3f}\n")
            f.write(f"- **Organizations**: {row['Organizations']}\n\n")
        
        f.write("## Organizations with Highest Average Alignment\n\n")
        top_orgs = org_summary_df.head(20)
        for _, row in top_orgs.iterrows():
            f.write(f"### {row['Organization']}\n")
            f.write(f"- **Initiative**: {row['Initiative']}\n")
            f.write(f"- **Cluster**: {row['Cluster']}\n")
            f.write(f"- **Average Similarity**: {row['Average_Similarity']:.3f}\n")
            top_similar = json.loads(row['Top_5_Similar_Orgs'])
            f.write(f"- **Top Similar Organizations**:\n")
            for sim_org in top_similar:
                f.write(f"  - {sim_org['org']} (score: {sim_org['score']:.3f}, cluster: {sim_org['cluster']})\n")
            f.write("\n")
    
    safe_print(f"Saved markdown report to {md_report}")
    
    return similarity_df, org_summary_df, cluster_df, org_names

def visualize_similarity(similarity_matrix: np.ndarray, org_names: List[str], 
                         cluster_labels: np.ndarray, output_dir: str = "."):
    """Creates visualizations of the similarity matrix."""
    safe_print("\nGenerating visualizations...")
    
    # Limit visualization size if too many organizations
    max_vis = 50
    if len(org_names) > max_vis:
        safe_print(f"Too many organizations ({len(org_names)}) for full visualization.")
        safe_print(f"Creating visualization for top {max_vis} organizations by average similarity...")
        
        # Calculate average similarity for each org
        avg_sims = np.mean(similarity_matrix, axis=1)
        top_indices = np.argsort(avg_sims)[::-1][:max_vis]
        
        vis_matrix = similarity_matrix[np.ix_(top_indices, top_indices)]
        vis_org_names = [org_names[i] for i in top_indices]
        vis_cluster_labels = cluster_labels[top_indices]
    else:
        vis_matrix = similarity_matrix
        vis_org_names = org_names
        vis_cluster_labels = cluster_labels
    
    # Create heatmap
    plt.figure(figsize=(16, 14))
    sns.heatmap(vis_matrix, 
                xticklabels=[name[:30] for name in vis_org_names],  # Truncate long names
                yticklabels=[name[:30] for name in vis_org_names],
                cmap='RdYlGn', 
                vmin=0, 
                vmax=1,
                square=True,
                cbar_kws={'label': 'Cosine Similarity'})
    plt.title('Submission Alignment Heatmap (Embeddings-Based)', fontsize=16, pad=20)
    plt.xlabel('Organization', fontsize=12)
    plt.ylabel('Organization', fontsize=12)
    plt.xticks(rotation=90, ha='right')
    plt.yticks(rotation=0)
    plt.tight_layout()
    
    heatmap_path = os.path.join(output_dir, "embeddings_similarity_heatmap.png")
    plt.savefig(heatmap_path, dpi=300, bbox_inches='tight')
    plt.close()
    safe_print(f"Saved heatmap to {heatmap_path}")
    
    # Create 2D PCA visualization
    if len(org_names) > 2:
        pca = PCA(n_components=2, random_state=42)
        embeddings_2d = pca.fit_transform(similarity_matrix)
        
        plt.figure(figsize=(14, 10))
        
        # Plot by cluster
        unique_clusters = sorted(set(cluster_labels))
        colors = plt.cm.tab20(np.linspace(0, 1, len(unique_clusters)))
        
        for i, cluster_id in enumerate(unique_clusters):
            if cluster_id == -1:
                label = 'Outliers'
                marker = 'x'
            else:
                label = f'Cluster {cluster_id}'
                marker = 'o'
            
            cluster_mask = cluster_labels == cluster_id
            plt.scatter(embeddings_2d[cluster_mask, 0], 
                       embeddings_2d[cluster_mask, 1],
                       c=[colors[i]], 
                       label=label,
                       marker=marker,
                       s=100,
                       alpha=0.6)
        
        plt.xlabel(f'PC1 ({pca.explained_variance_ratio_[0]:.1%} variance)', fontsize=12)
        plt.ylabel(f'PC2 ({pca.explained_variance_ratio_[1]:.1%} variance)', fontsize=12)
        plt.title('Submission Alignment - 2D PCA Projection', fontsize=16, pad=20)
        plt.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
        plt.grid(True, alpha=0.3)
        plt.tight_layout()
        
        pca_path = os.path.join(output_dir, "embeddings_pca_visualization.png")
        plt.savefig(pca_path, dpi=300, bbox_inches='tight')
        plt.close()
        safe_print(f"Saved PCA visualization to {pca_path}")
    else:
        pca_path = None
    
    return heatmap_path, pca_path

def generate_cfg_comparison_table(
    org_names: List[str],
    initiatives: List[str],
    similarity_matrix: np.ndarray,
    cluster_labels: np.ndarray,
    target_org: str = "Centre for Future Generations"
):
    """Creates a comparison table highlighting Centre for Future Generations."""
    # Find all CFG submissions (case-insensitive)
    cfg_indices = []
    cfg_names = []
    for i, org in enumerate(org_names):
        if target_org.lower() in org.lower() or "centre for future" in org.lower():
            cfg_indices.append(i)
            cfg_names.append(org)
    
    if not cfg_indices:
        safe_print(f"Warning: No submissions found for {target_org}")
        return pd.DataFrame()
    
    # Create comparison table
    comparison_data = []
    for cfg_idx in cfg_indices:
        cfg_name = org_names[cfg_idx]
        cfg_initiative = initiatives[cfg_idx]
        cfg_cluster = cluster_labels[cfg_idx]
        
        # Get similarities to all other organizations
        similarities = similarity_matrix[cfg_idx, :]
        
        for i, other_org in enumerate(org_names):
            if i == cfg_idx:  # Skip self
                continue
            
            comparison_data.append({
                'CFG_Submission': cfg_name,
                'CFG_Initiative': cfg_initiative,
                'CFG_Cluster': int(cfg_cluster),
                'Compared_Organization': other_org,
                'Compared_Initiative': initiatives[i],
                'Compared_Cluster': int(cluster_labels[i]),
                'Similarity_Score': float(similarities[i]),
                'Same_Cluster': bool(cluster_labels[i] == cfg_cluster)
            })
    
    comparison_df = pd.DataFrame(comparison_data)
    comparison_df = comparison_df.sort_values('Similarity_Score', ascending=False)
    
    return comparison_df

def generate_pdf_report(
    similarity_df: pd.DataFrame,
    org_summary_df: pd.DataFrame,
    cluster_df: pd.DataFrame,
    org_names: List[str],
    initiatives: List[str],
    similarity_matrix: np.ndarray,
    cluster_labels: np.ndarray,
    heatmap_path: str,
    pca_path: str,
    output_path: str = "embeddings_analysis_report.pdf"
):
    """Generates a comprehensive PDF report with findings, plots, and CFG comparison."""
    
    class PDF(FPDF):
        def header(self):
            self.set_font('Helvetica', 'B', 16)
            self.cell(0, 10, 'Embeddings-Based Alignment Analysis Report', ln=True, align='C')
            self.ln(5)
        
        def footer(self):
            self.set_y(-15)
            self.set_font('Helvetica', 'I', 8)
            self.cell(0, 10, f'Page {self.page_no()}', align='C')
    
    pdf = PDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    
    # Title page
    pdf.set_font('Helvetica', 'B', 20)
    pdf.cell(0, 20, 'Embeddings-Based Alignment Analysis', ln=True, align='C')
    pdf.ln(10)
    pdf.set_font('Helvetica', '', 12)
    pdf.cell(0, 10, f'Analysis of {len(org_names)} Submissions', ln=True, align='C')
    pdf.cell(0, 10, f'Across {len(set(initiatives))} Initiatives', ln=True, align='C')
    pdf.ln(20)
    
    # Summary Statistics
    pdf.set_font('Helvetica', 'B', 16)
    pdf.cell(0, 10, 'Summary Statistics', ln=True)
    pdf.ln(5)
    
    pdf.set_font('Helvetica', '', 10)
    avg_sim = np.mean(similarity_matrix[similarity_matrix < 1.0])
    max_sim = np.max(similarity_matrix[similarity_matrix < 1.0])
    min_sim = np.min(similarity_matrix[similarity_matrix < 1.0])
    unique_clusters = len(set(cluster_labels)) - (1 if -1 in cluster_labels else 0)
    
    stats = [
        f"Total Submissions: {len(org_names)}",
        f"Total Initiatives: {len(set(initiatives))}",
        f"Number of Clusters: {unique_clusters}",
        f"Average Similarity: {avg_sim:.3f}",
        f"Maximum Similarity: {max_sim:.3f}",
        f"Minimum Similarity: {min_sim:.3f}"
    ]
    
    for stat in stats:
        pdf.cell(0, 8, stat, ln=True)
    
    pdf.ln(10)
    
    # Top Aligned Pairs
    pdf.set_font('Helvetica', 'B', 16)
    pdf.set_fill_color(200, 230, 200)
    pdf.cell(0, 10, 'Top 15 Most Aligned Pairs', ln=True, fill=True)
    pdf.ln(5)
    
    pdf.set_font('Helvetica', 'B', 9)
    pdf.set_fill_color(240, 240, 240)
    pdf.cell(70, 7, 'Organization A', border=1, fill=True)
    pdf.cell(70, 7, 'Organization B', border=1, fill=True)
    pdf.cell(25, 7, 'Score', border=1, fill=True, align='C')
    pdf.cell(25, 7, 'Same Cluster', border=1, fill=True, align='C')
    pdf.ln()
    
    pdf.set_font('Helvetica', '', 8)
    top_pairs = similarity_df.head(15)
    for _, row in top_pairs.iterrows():
        org_a = sanitize_for_pdf(str(row['Organization_A'])[:30])
        org_b = sanitize_for_pdf(str(row['Organization_B'])[:30])
        score = f"{row['Similarity_Score']:.3f}"
        same_cluster = "Yes" if row['Same_Cluster'] else "No"
        
        pdf.cell(70, 6, org_a, border=1)
        pdf.cell(70, 6, org_b, border=1)
        pdf.cell(25, 6, score, border=1, align='C')
        pdf.cell(25, 6, same_cluster, border=1, align='C')
        pdf.ln()
    
    # Cluster Analysis
    pdf.add_page()
    pdf.set_font('Helvetica', 'B', 16)
    pdf.set_fill_color(220, 220, 240)
    pdf.cell(0, 10, 'Cluster Analysis', ln=True, fill=True)
    pdf.ln(5)
    
    pdf.set_font('Helvetica', 'B', 9)
    pdf.set_fill_color(240, 240, 240)
    pdf.cell(20, 7, 'Cluster ID', border=1, fill=True, align='C')
    pdf.cell(20, 7, 'Size', border=1, fill=True, align='C')
    pdf.cell(40, 7, 'Avg Similarity', border=1, fill=True, align='C')
    pdf.cell(110, 7, 'Sample Organizations', border=1, fill=True)
    pdf.ln()
    
    pdf.set_font('Helvetica', '', 8)
    for _, row in cluster_df.iterrows():
        pdf.cell(20, 6, str(row['Cluster_ID']), border=1, align='C')
        pdf.cell(20, 6, str(row['Size']), border=1, align='C')
        pdf.cell(40, 6, f"{row['Average_Intra_Cluster_Similarity']:.3f}", border=1, align='C')
        orgs = sanitize_for_pdf(str(row['Organizations'])[:80])
        pdf.cell(110, 6, orgs, border=1)
        pdf.ln()
    
    # Visualizations
    pdf.add_page()
    pdf.set_font('Helvetica', 'B', 16)
    pdf.cell(0, 10, 'Visualizations', ln=True)
    pdf.ln(5)
    
    # Heatmap
    if os.path.exists(heatmap_path):
        pdf.set_font('Helvetica', 'B', 12)
        pdf.cell(0, 8, 'Similarity Heatmap', ln=True)
        pdf.ln(3)
        pdf.set_font('Helvetica', '', 9)
        pdf.cell(0, 6, 'Shows pairwise cosine similarity between all submissions', ln=True)
        pdf.ln(3)
        try:
            pdf.image(heatmap_path, x=10, y=pdf.get_y(), w=190)
            pdf.ln(140)
        except Exception as e:
            safe_print(f"Warning: Could not add heatmap to PDF: {e}")
            pdf.cell(0, 10, f"[Heatmap image could not be loaded: {e}]", ln=True)
    
    # PCA Visualization
    if pca_path and os.path.exists(pca_path):
        pdf.add_page()
        pdf.set_font('Helvetica', 'B', 12)
        pdf.cell(0, 8, '2D PCA Projection', ln=True)
        pdf.ln(3)
        pdf.set_font('Helvetica', '', 9)
        pdf.cell(0, 6, 'Shows clusters of aligned submissions in 2D space', ln=True)
        pdf.ln(3)
        try:
            pdf.image(pca_path, x=10, y=pdf.get_y(), w=190)
            pdf.ln(140)
        except Exception as e:
            safe_print(f"Warning: Could not add PCA visualization to PDF: {e}")
            pdf.cell(0, 10, f"[PCA visualization could not be loaded: {e}]", ln=True)
    
    # Centre for Future Generations Comparison Table
    pdf.add_page()
    pdf.set_font('Helvetica', 'B', 16)
    pdf.set_fill_color(255, 240, 200)
    pdf.cell(0, 10, 'Centre for Future Generations - Alignment Comparison', ln=True, fill=True)
    pdf.ln(5)
    
    cfg_comparison = generate_cfg_comparison_table(org_names, initiatives, similarity_matrix, cluster_labels)
    
    if not cfg_comparison.empty:
        pdf.set_font('Helvetica', '', 9)
        pdf.cell(0, 6, f'Found {len(set(cfg_comparison["CFG_Submission"]))} Centre for Future Generations submission(s)', ln=True)
        pdf.cell(0, 6, f'Comparing against {len(set(cfg_comparison["Compared_Organization"]))} other organizations', ln=True)
        pdf.ln(5)
        
        # Group by CFG submission
        for cfg_submission in set(cfg_comparison['CFG_Submission']):
            cfg_data = cfg_comparison[cfg_comparison['CFG_Submission'] == cfg_submission].head(50)  # Top 50 for each
            
            pdf.set_font('Helvetica', 'B', 12)
            cfg_name = sanitize_for_pdf(cfg_submission)
            pdf.cell(0, 8, f'CFG Submission: {cfg_name}', ln=True)
            pdf.ln(3)
            
            # Table header
            pdf.set_font('Helvetica', 'B', 8)
            pdf.set_fill_color(240, 240, 240)
            pdf.cell(80, 6, 'Compared Organization', border=1, fill=True)
            pdf.cell(30, 6, 'Initiative', border=1, fill=True)
            pdf.cell(25, 6, 'Similarity', border=1, fill=True, align='C')
            pdf.cell(20, 6, 'Cluster', border=1, fill=True, align='C')
            pdf.cell(35, 6, 'Same Cluster', border=1, fill=True, align='C')
            pdf.ln()
            
            # Table rows
            pdf.set_font('Helvetica', '', 7)
            for _, row in cfg_data.iterrows():
                # Highlight high similarity rows
                if row['Similarity_Score'] >= 0.7:
                    pdf.set_fill_color(200, 255, 200)  # Light green
                elif row['Similarity_Score'] >= 0.5:
                    pdf.set_fill_color(255, 255, 200)  # Light yellow
                else:
                    pdf.set_fill_color(255, 255, 255)  # White
                
                org = sanitize_for_pdf(str(row['Compared_Organization'])[:35])
                init = sanitize_for_pdf(str(row['Compared_Initiative'])[:20])
                score = f"{row['Similarity_Score']:.3f}"
                cluster = str(int(row['Compared_Cluster']))
                same_cluster = "Yes" if row['Same_Cluster'] else "No"
                
                pdf.cell(80, 5, org, border=1, fill=True)
                pdf.cell(30, 5, init, border=1, fill=True)
                pdf.cell(25, 5, score, border=1, fill=True, align='C')
                pdf.cell(20, 5, cluster, border=1, fill=True, align='C')
                pdf.cell(35, 5, same_cluster, border=1, fill=True, align='C')
                pdf.ln()
            
            pdf.ln(5)
            
            # Summary for this CFG submission
            pdf.set_font('Helvetica', 'B', 10)
            pdf.cell(0, 8, 'Summary:', ln=True)
            pdf.set_font('Helvetica', '', 9)
            top_10 = cfg_data.head(10)
            avg_sim = cfg_data['Similarity_Score'].mean()
            high_align = len(cfg_data[cfg_data['Similarity_Score'] >= 0.7])
            same_cluster_count = len(cfg_data[cfg_data['Same_Cluster'] == True])
            
            pdf.cell(0, 6, f"Average Similarity: {avg_sim:.3f}", ln=True)
            pdf.cell(0, 6, f"High Alignment (>=0.7): {high_align} organizations", ln=True)
            pdf.cell(0, 6, f"Same Cluster: {same_cluster_count} organizations", ln=True)
            pdf.ln(3)
            pdf.cell(0, 6, "Top 5 Most Aligned:", ln=True)
            pdf.set_font('Helvetica', '', 8)
            for idx, (_, row) in enumerate(top_10.head(5).iterrows(), 1):
                org = sanitize_for_pdf(str(row['Compared_Organization'])[:50])
                pdf.cell(0, 5, f"  {idx}. {org} (Score: {row['Similarity_Score']:.3f})", ln=True)
            
            pdf.ln(10)
            
            # Add page break if needed
            if pdf.get_y() > 250:
                pdf.add_page()
    else:
        pdf.set_font('Helvetica', '', 10)
        pdf.cell(0, 10, 'No Centre for Future Generations submissions found in the dataset.', ln=True)
    
    # Save PDF
    pdf.output(output_path)
    safe_print(f"\nPDF report saved to {output_path}")

def main():
    """Main analysis pipeline."""
    safe_print("=" * 60)
    safe_print("Embeddings-Based Alignment Analysis")
    safe_print("=" * 60)
    
    # Configuration
    base_dir = "markdown"
    model_name = "all-MiniLM-L6-v2"  # Fast, good quality. Alternative: "all-mpnet-base-v2" for better quality
    clustering_method = "kmeans"  # or "dbscan"
    n_clusters = None  # Auto-determined if None
    
    # 1. Load all submissions
    filepaths, filenames, bodies, frontmatters, initiatives = load_all_markdown_files(base_dir)
    
    if len(filenames) == 0:
        safe_print("No markdown files found. Exiting.")
        return
    
    # 2. Setup output directories
    safe_print("\nSetting up output directories...")
    base_output_dir, all_initiatives_dir, initiative_dirs = setup_output_directories("outputs", initiatives)
    safe_print(f"Base output directory: {base_output_dir}")
    safe_print(f"Cross-initiative outputs: {all_initiatives_dir}")
    for initiative, dir_path in initiative_dirs.items():
        safe_print(f"  - {initiative}: {dir_path}")
    
    # 3. Preprocess texts
    safe_print("\nPreprocessing texts...")
    processed_texts = [preprocess_text(body) for body in bodies]
    
    # 4. Generate embeddings
    embeddings, model = generate_embeddings(processed_texts, model_name)
    
    # 5. Compute similarity matrix
    similarity_matrix = compute_similarity_matrix(embeddings)
    
    # 6. Identify clusters
    cluster_labels, n_clusters = identify_clusters(embeddings, method=clustering_method, n_clusters=n_clusters)
    
    # 7. Generate cross-initiative reports (all initiatives combined)
    safe_print("\n--- Generating Cross-Initiative Analysis ---")
    similarity_df, org_summary_df, cluster_df, org_names = generate_alignment_report(
        filenames, initiatives, similarity_matrix, cluster_labels, all_initiatives_dir
    )
    
    # 8. Create cross-initiative visualizations
    heatmap_path = None
    pca_path = None
    try:
        heatmap_path, pca_path = visualize_similarity(similarity_matrix, 
                           [os.path.splitext(f)[0] for f in filenames],
                           cluster_labels,
                           all_initiatives_dir)
    except Exception as e:
        safe_print(f"Warning: Could not generate visualizations: {e}")
        safe_print("Continuing without visualizations...")
    
    # 9. Generate Centre for Future Generations comparison table (cross-initiative)
    try:
        cfg_comparison = generate_cfg_comparison_table(org_names, initiatives, similarity_matrix, cluster_labels)
        if not cfg_comparison.empty:
            cfg_csv = os.path.join(all_initiatives_dir, "embeddings_cfg_comparison.csv")
            cfg_comparison.to_csv(cfg_csv, index=False)
            safe_print(f"Saved Centre for Future Generations comparison to {cfg_csv}")
    except Exception as e:
        safe_print(f"Warning: Could not generate CFG comparison table: {e}")
    
    # 10. Generate cross-initiative PDF report
    try:
        pdf_path = os.path.join(all_initiatives_dir, "embeddings_analysis_report.pdf")
        generate_pdf_report(
            similarity_df,
            org_summary_df,
            cluster_df,
            org_names,
            initiatives,
            similarity_matrix,
            cluster_labels,
            heatmap_path or "",
            pca_path or "",
            pdf_path
        )
    except Exception as e:
        safe_print(f"Warning: Could not generate PDF report: {e}")
        safe_print("Continuing without PDF...")
    
    # 11. Generate initiative-specific analyses
    safe_print("\n--- Generating Initiative-Specific Analyses ---")
    unique_initiatives = set(initiatives)
    
    for initiative in unique_initiatives:
        if initiative not in initiative_dirs:
            continue
        
        initiative_dir = initiative_dirs[initiative]
        safe_print(f"\nAnalyzing initiative: {initiative}")
        
        # Get indices for this initiative
        initiative_indices = [i for i, init in enumerate(initiatives) if init == initiative]
        
        if len(initiative_indices) < 2:
            safe_print(f"  Skipping {initiative}: too few submissions ({len(initiative_indices)})")
            continue
        
        # Extract initiative-specific data
        initiative_filenames = [filenames[i] for i in initiative_indices]
        initiative_org_names = [os.path.splitext(f)[0] for f in initiative_filenames]
        initiative_similarity_matrix = similarity_matrix[np.ix_(initiative_indices, initiative_indices)]
        initiative_cluster_labels = cluster_labels[initiative_indices]
        initiative_embeddings = embeddings[initiative_indices]
        
        # Re-cluster for this initiative
        initiative_cluster_labels, _ = identify_clusters(
            initiative_embeddings, 
            method=clustering_method, 
            n_clusters=None
        )
        
        # Generate initiative-specific reports
        init_similarity_df, init_org_summary_df, init_cluster_df, _ = generate_alignment_report(
            initiative_filenames,
            [initiative] * len(initiative_indices),
            initiative_similarity_matrix,
            initiative_cluster_labels,
            initiative_dir
        )
        
        # Create initiative-specific visualizations
        try:
            init_heatmap_path, init_pca_path = visualize_similarity(
                initiative_similarity_matrix,
                initiative_org_names,
                initiative_cluster_labels,
                initiative_dir
            )
            
            # Generate initiative-specific PDF
            try:
                init_pdf_path = os.path.join(initiative_dir, "embeddings_analysis_report.pdf")
                generate_pdf_report(
                    init_similarity_df,
                    init_org_summary_df,
                    init_cluster_df,
                    initiative_org_names,
                    [initiative] * len(initiative_indices),
                    initiative_similarity_matrix,
                    initiative_cluster_labels,
                    init_heatmap_path or "",
                    init_pca_path or "",
                    init_pdf_path
                )
            except Exception as e:
                safe_print(f"  Warning: Could not generate PDF for {initiative}: {e}")
        except Exception as e:
            safe_print(f"  Warning: Could not generate visualizations for {initiative}: {e}")
    
    safe_print("\n" + "=" * 60)
    safe_print("Analysis Complete!")
    safe_print("=" * 60)
    safe_print(f"\nOutput directory structure:")
    safe_print(f"  {base_output_dir}/")
    safe_print(f"    all_initiatives/embeddings/")
    safe_print(f"      - embeddings_similarity_pairs.csv")
    safe_print(f"      - embeddings_org_summary.csv")
    safe_print(f"      - embeddings_cluster_analysis.csv")
    safe_print(f"      - embeddings_analysis_report.md")
    safe_print(f"      - embeddings_similarity_heatmap.png")
    safe_print(f"      - embeddings_pca_visualization.png")
    safe_print(f"      - embeddings_analysis_report.pdf")
    safe_print(f"      - embeddings_cfg_comparison.csv (if CFG submissions found)")
    safe_print(f"    [Initiative Name]/embeddings/")
    safe_print(f"      - [Same files as above, but initiative-specific]")

if __name__ == "__main__":
    main()
