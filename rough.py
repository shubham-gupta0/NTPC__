import difflib
import csv
import os
import json
from diff_match_patch import diff_match_patch
from config import *

def generate_interactive_html_diff(diffs, text1, text2, comparison_id):
    """
    Generate an interactive HTML diff visualization.
    
    Args:
        diffs (list): List of diffs from diff_match_patch
        text1 (str): Original text
        text2 (str): Modified text
        comparison_id (str): Unique identifier for the comparison
    
    Returns:
        str: HTML string with interactive diff visualization
    """
    # Convert diffs to a JSON string for JavaScript
    diffs_json = json.dumps(diffs)

    html_template = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>Interactive Diff - {comparison_id}</title>
        <style>
            body {{
                font-family: 'Arial', sans-serif;
                margin: 0;
                padding: 0;
                display: flex;
                height: 100vh;
                background-color: #f0f0f0;
            }}
            .sidebar {{
                width: 30%;
                background-color: #f9f9f9;
                border-right: 1px solid #ddd;
                overflow-y: auto;
                padding: 20px;
            }}
            .content {{
                width: 70%;
                overflow-y: auto;
                padding: 20px;
                background-color: white;
            }}
            .changes-container {{
                margin-bottom: 20px;
            }}
            .change-item {{
                cursor: pointer;
                padding: 10px;
                margin-bottom: 5px;
                border-radius: 4px;
                transition: background-color 0.3s ease;
            }}
            .change-item:hover {{
                background-color: #e0e0e0;
            }}
            .change-item.insertion {{
                background-color: #e6f3e6;
                color: #155724;
                border-left: 4px solid #28a745;
            }}
            .change-item.deletion {{
                background-color: #f8d7da;
                color: #721c24;
                border-left: 4px solid #dc3545;
                text-decoration: line-through;
            }}
            .highlight {{
                background-color: #ffff00 !important;
                transition: background-color 0.5s ease;
            }}
            .diff-text {{
                white-space: pre-wrap;
                word-wrap: break-word;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 14px;
                line-height: 1.5;
            }}
            .diff-insert {{
                background-color: #e6f3e6;
                color: #155724;
                text-decoration: underline;
            }}
            .diff-delete {{
                background-color: #f8d7da;
                color: #721c24;
                text-decoration: line-through;
            }}
            .diff-equal {{
                background-color: transparent;
            }}
            .summary {{
                background-color: #f1f1f1;
                padding: 15px;
                margin-bottom: 20px;
                border-radius: 5px;
            }}
        </style>
    </head>
    <body>
        <div class="sidebar">
            <div class="summary">
                <h3>Comparison Summary</h3>
                <p><strong>Original Length:</strong> {text1_length} chars</p>
                <p><strong>Modified Length:</strong> {text2_length} chars</p>
                <p><strong>Insertions:</strong> {insertions}</p>
                <p><strong>Deletions:</strong> {deletions}</p>
            </div>
            <div id="insertionsList" class="changes-container">
                <h3>Insertions</h3>
            </div>
            <div id="deletionsList" class="changes-container">
                <h3>Deletions</h3>
            </div>
        </div>
        <div class="content">
            <h1>Interactive Diff Viewer</h1>
            <div id="diffContent" class="diff-text"></div>
        </div>

        <script>
            // Parsed diffs from Python
            const DIFFS = {diffs_json};
            const TEXT1 = `{text1}`;
            const TEXT2 = `{text2}`;

            function renderDiff() {{
                const diffContent = document.getElementById('diffContent');
                const insertionsList = document.getElementById('insertionsList');
                const deletionsList = document.getElementById('deletionsList');

                // Clear previous content
                diffContent.innerHTML = '';
                insertionsList.innerHTML = '<h3>Insertions</h3>';
                deletionsList.innerHTML = '<h3>Deletions</h3>';

                // Tracking for unique IDs
                let insertionCount = 0;
                let deletionCount = 0;

                // Render diffs and create sidebar items
                DIFFS.forEach((diff, index) => {{
                    const [diffType, diffText] = diff;
                    let spanElement;

                    if (diffType === 1) {{  // Insertion
                        spanElement = document.createElement('span');
                        spanElement.className = 'diff-insert';
                        spanElement.textContent = diffText;
                        spanElement.setAttribute('data-diff-index', index);

                        // Create sidebar item for insertion
                        const insertionItem = document.createElement('div');
                        const insertionId = `insertion-${{insertionCount++}}`;
                        insertionItem.id = insertionId;
                        insertionItem.className = 'change-item insertion';
                        insertionItem.textContent = diffText;
                        insertionItem.addEventListener('click', () => {{
                            clearHighlights();
                            spanElement.classList.add('highlight');
                            spanElement.scrollIntoView({{ behavior: 'smooth', block: 'center' }});
                        }});
                        insertionsList.appendChild(insertionItem);
                    }} else if (diffType === -1) {{  // Deletion
                        spanElement = document.createElement('span');
                        spanElement.className = 'diff-delete';
                        spanElement.textContent = diffText;
                        spanElement.setAttribute('data-diff-index', index);

                        // Create sidebar item for deletion
                        const deletionItem = document.createElement('div');
                        const deletionId = `deletion-${{deletionCount++}}`;
                        deletionItem.id = deletionId;
                        deletionItem.className = 'change-item deletion';
                        deletionItem.textContent = diffText;
                        deletionItem.addEventListener('click', () => {{
                            clearHighlights();
                            spanElement.classList.add('highlight');
                            spanElement.scrollIntoView({{ behavior: 'smooth', block: 'center' }});
                        }});
                        deletionsList.appendChild(deletionItem);
                    }} else {{  // Equal text
                        spanElement = document.createElement('span');
                        spanElement.className = 'diff-equal';
                        spanElement.textContent = diffText;
                    }}

                    // Append to main content
                    diffContent.appendChild(spanElement);
                }});
            }}

            function clearHighlights() {{
                document.querySelectorAll('.highlight').forEach(el => {{
                    el.classList.remove('highlight');
                }});
            }}

            // Initialize on page load
            document.addEventListener('DOMContentLoaded', renderDiff);
        </script>
    </body>
    </html>
    """

    # Count insertions and deletions
    insertions_count = sum(1 for diff in diffs if diff[0] == 1)
    deletions_count = sum(1 for diff in diffs if diff[0] == -1)

    # Format the final HTML
    html_output = html_template.format(
        comparison_id=comparison_id,
        text1_length=len(text1),
        text2_length=len(text2),
        insertions=insertions_count,
        deletions=deletions_count,
        text1=text1.replace('`', '\`'),  # Escape backticks for JavaScript
        text2=text2.replace('`', '\`'),
        diffs_json=diffs_json
    )

    return html_output

def compare_documents(comparison_id, text1_path, text2_path, output_dir=OUTPUT_FOLDER, semantic_cleanup=True):
    """
    Compare two texts using diff-match-patch with comprehensive output options.
    
    Args:
        comparison_id (str): Unique identifier for the comparison
        text1_path (str): Path to the first text file
        text2_path (str): Path to the second text file
        output_dir (str): Directory to save output files
        semantic_cleanup (bool): Apply semantic cleanup
    
    Returns:
        dict: Comparison results including diff and file paths
    """
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)

    # Read text files
    with open(text1_path, 'r', encoding='utf-8') as f1:
        text1 = f1.read()
    with open(text2_path, 'r', encoding='utf-8') as f2:
        text2 = f2.read()

    # Create diff-match-patch instance
    dmp = diff_match_patch()
    
    # Remove timeout and edit cost constraints
    dmp.Diff_Timeout = 0  # No timeout
    dmp.Diff_EditCost = 4  # Minimal edit cost

    # Compute the diff
    diffs = dmp.diff_main(text1, text2)
    diffs = [diff for diff in diffs if diff[1] and diff[1].strip()]
    
    # Apply cleanup methods if selected
    if semantic_cleanup:
        dmp.diff_cleanupSemantic(diffs)
    
    # Generate interactive HTML output
    html_output = generate_interactive_html_diff(diffs, text1, text2, comparison_id)
    
    # Prepare file paths with comparison_id
    html_file_path = os.path.join(output_dir, f'interactive_comparison_{comparison_id}.html')
    insertions_csv_path = os.path.join(output_dir, f'insertions_{comparison_id}.csv')
    deletions_csv_path = os.path.join(output_dir, f'deletions_{comparison_id}.csv')
    
    # Save HTML output
    with open(html_file_path, 'w', encoding='utf-8') as html_file:
        html_file.write(html_output)
    
    # Prepare and save CSV files for insertions and deletions
    insertions = []
    deletions = []
    
    for diff_type, diff_text in diffs:
        # Only add non-empty, non-whitespace strings
        if diff_type == 1 and diff_text and diff_text.strip():  # Insertion
            insertions.append([diff_text])
        elif diff_type == -1 and diff_text and diff_text.strip():  # Deletion
            deletions.append([diff_text])
    
    # Save insertions CSV
    with open(insertions_csv_path, 'w', newline='', encoding='utf-8') as csv_file:
        csv_writer = csv.writer(csv_file)
        csv_writer.writerow(['Inserted Text'])
        csv_writer.writerows(insertions)
    
    # Save deletions CSV
    with open(deletions_csv_path, 'w', newline='', encoding='utf-8') as csv_file:
        csv_writer = csv.writer(csv_file)
        csv_writer.writerow(['Deleted Text'])
        csv_writer.writerows(deletions)
    
    return {
        'diffs': diffs,
        'html_file': html_file_path,
        'insertions_csv': insertions_csv_path,
        'deletions_csv': deletions_csv_path
    }

# Example usage
if __name__ == "__main__":
    result = compare_documents(
        comparison_id="example_comparison",
        text1_path="assets/standard.txt",
        text2_path="output/extracted_text_test1.txt"
    )
    print(f"Comparison complete. HTML file: {result['html_file']}")