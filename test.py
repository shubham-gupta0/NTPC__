import sqlite3

def test_sqlite_connection(db_path):
    try:
        connection = sqlite3.connect(db_path)
        print(f"Connected to SQLite database at {db_path} successfully.")
        connection.close()
    except sqlite3.Error as error:
        print("Error while connecting to SQLite:", error)

if __name__ == "__main__":
    # Use ":memory:" for an in-memory database or provide a file path for a disk database
    database_path = "database/app.db"  # or "example.db"
    test_sqlite_connection(database_path)