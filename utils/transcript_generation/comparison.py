import os
import csv
from win32com.client import Dispatch

def extract_revisions(doc):
        """Extract insertions and deletions from a Word document."""
        insertions = []
        deletions = []
        
        # Process Revisions (insertions and deletions)
        for revision in doc.Revisions:
            try:
                is_insertion = revision.Type == 1
                revision_info = {
                    'author': revision.Author,
                    'date': revision.Date,
                    'text': revision.Range.Text.strip(),
                    'page_number': revision.Range.Information(3)  # 3 is the constant for page number
                }
                
                if revision_info['text']:  # Only add if there's actual content
                    if is_insertion:
                        insertions.append(revision_info)
                    else:
                        deletions.append(revision_info)
            except Exception as e:
                print(f"Error processing revision: {e}")
        
        return insertions, deletions

def save_revisions_to_csv(revisions, output_path, revision_type):
    """Save the revisions (insertions or deletions) to a CSV file."""
    # Define CSV headers
    headers = ['Index', 'Page', 'Author', 'Date', 'Text']
    
    with open(output_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        
        # Write headers
        writer.writerow(headers)
        
        # Write revision data
        for idx, rev in enumerate(revisions, 1):
            writer.writerow([
                idx,
                rev['page_number'],
                rev['author'],
                rev['date'],
                rev['text']
            ])

def compare_documents(id, file1_path, file2_path, output_dir):
    """
    Compare two Word documents and save all outputs:
    - Comparison result as DOCX
    - Comparison result as PDF
    - Insertions as CSV
    - Deletions as CSV
    """
    word = Dispatch("Word.Application")
    word.Visible = False

    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)

    # Define output file paths
    output_docx = os.path.join(output_dir, f"comparison_result_{id}.docx")
    output_pdf = os.path.join(output_dir, f"comparison_result_{id}.pdf")
    insertions_csv = os.path.join(output_dir, f"insertions_{id}.csv")
    deletions_csv = os.path.join(output_dir, f"deletions_{id}.csv")

    original_doc = revised_doc = compared_doc = None

    try:
        # Open documents
        print("Opening documents...")
        original_doc = word.Documents.Open(os.path.abspath(file1_path))
        revised_doc = word.Documents.Open(os.path.abspath(file2_path))

        # Perform comparison
        print("Performing document comparison...")
        compared_doc = word.CompareDocuments(
            OriginalDocument=original_doc,
            RevisedDocument=revised_doc,
            Destination=2,  # wdCompareDestinationNew
            CompareFormatting=True,
            CompareCaseChanges=True,
            CompareWhitespace=True,
            CompareTables=True,
            CompareHeaders=True,
            CompareFootnotes=True,
            CompareTextboxes=True,
            CompareFields=True,
            CompareComments=True,
            RevisedAuthor="Bidder"
        )

        # Extract revisions before saving
        print("Extracting revisions...")
        insertions, deletions = extract_revisions(compared_doc)

        # Save comparison result as DOCX
        print("Saving DOCX comparison result...")
        compared_doc.SaveAs(os.path.abspath(output_docx), FileFormat=16)  # 16 = DOCX

        # Save comparison result as PDF
        print("Saving PDF comparison result...")
        compared_doc.SaveAs(os.path.abspath(output_pdf), FileFormat=17)  # 17 = PDF

        # Save insertions and deletions to CSV files
        print("Saving revision details to CSV files...")
        save_revisions_to_csv(insertions, insertions_csv, "Insertions")
        save_revisions_to_csv(deletions, deletions_csv, "Deletions")

        # Prepare summary of changes
        total_changes = len(insertions) + len(deletions)
        
        # Print summary
        print("\nComparison completed successfully!")
        print(f"\nSummary of changes:")
        print(f"Total changes: {total_changes}")
        print(f"- Insertions: {len(insertions)}")
        print(f"- Deletions: {len(deletions)}")
        print("\nOutput files:")
        print(f"- DOCX: {output_docx}")
        print(f"- PDF: {output_pdf}")
        print(f"- Insertions: {insertions_csv}")
        print(f"- Deletions: {deletions_csv}")

    except Exception as e:
        print(f"\nError during comparison: {str(e)}")
        raise
    finally:
        print("\nCleaning up...")
        # Close all documents
        for doc in [original_doc, revised_doc, compared_doc]:
            if doc:
                try:
                    doc.Close(SaveChanges=False)
                except:
                    pass
        # Quit Word application
        try:
            word.Quit()
        except:
            pass