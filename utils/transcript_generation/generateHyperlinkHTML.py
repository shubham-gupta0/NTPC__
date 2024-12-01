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
    html_template = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>Transcript - {comparison_id}</title>
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
            <h1>Transcript</h1>
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

    # Convert diffs to a JSON string for JavaScript
    import json
    diffs_json = json.dumps(diffs)

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

def save_interactive_html_diff(diffs, text1, text2, comparison_id, output_dir=HYPERLINK_OUTPUTS):
    """
    Save the interactive HTML diff to a file.
    
    Args:
        diffs (list): List of diffs from diff_match_patch
        text1 (str): Original text
        text2 (str): Modified text
        comparison_id (str): Unique identifier for the comparison
        output_dir (str): Directory to save the HTML file
    
    Returns:
        str: Path to the saved HTML file
    """
    import os

    # Ensure the output directory exists
    os.makedirs(output_dir, exist_ok=True)

    # Generate HTML
    html_output = generate_interactive_html_diff(diffs, text1, text2, comparison_id)

    # Prepare file path
    html_file_path = os.path.join(output_dir, f'hyperlink_{comparison_id}.html')

    # Save HTML output
    with open(html_file_path, 'w', encoding='utf-8') as html_file:
        html_file.write(html_output)

    return html_file_path