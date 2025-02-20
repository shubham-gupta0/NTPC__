import csv
from pathlib import Path

def parse_csv_file(file_path: str) -> list:
    """
    Parse a CSV file that may contain multi-line fields and return a list of row strings.
    Each row (list of cell values) is joined into a single string separated by a space.
    This output can be stored as the CSV content in the database.
    """
    rows = []
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"{file_path} not found")
    
    # Open file using newline='' to let csv handle newlines within quoted fields.
    with open(path, newline='', encoding='utf-8') as csvfile:
        reader = csv.reader(csvfile, skipinitialspace=True)
        for row in reader:
            # Clean each cell by stripping extra whitespace.
            cleaned = [cell.strip() for cell in row if cell.strip()]
            if cleaned:  # only add non-empty rows
                # Join the individual cells into one string.
                joined_row = " ".join(cleaned)
                rows.append(joined_row)
    return rows


if __name__ == "__main__":
    insertions_file = r"C:\Users\nandg\OneDrive\Desktop\ntpc_backend\output\2\insertions_test1.csv"
    deletions_file = r"C:\Users\nandg\OneDrive\Desktop\ntpc_backend\output\deletions_test1.csv"

    insertions = parse_csv_file(insertions_file)
    deletions = parse_csv_file(deletions_file)

    print("Insertions CSV Parsed Content:")
    for row in insertions:
        print(row)
    print("\nDeletions CSV Parsed Content:")
    for row in deletions:
        print(row)