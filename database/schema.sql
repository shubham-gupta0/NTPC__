

-- Users table
CREATE TABLE Users (
    id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    role INTEGER DEFAULT 0,
    total_storage_used INTEGER DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- INSERt

-- Tenders table
CREATE TABLE Tenders (
    id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    user_id INT NOT NULL,
    name TEXT NOT NULL,
    valid_until TIMESTAMP NOT NULL,
    status INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES Users (id) ON DELETE CASCADE
);
-- INSERT
-- INSERT INTO Tenders (user_id, name, valid_until) VALUES (1, 'Tender 1', '2021-12-31 23:59:59');

-- PDF files table
CREATE TABLE PdfFiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    tender_id INT NOT NULL,
    user_id INT NOT NULL,
    file_name VARCHAR(255) NOT NULL,
    file_size BIGINT NOT NULL,
    file_path VARCHAR(255) NOT NULL,
    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (tender_id) REFERENCES Tenders (id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES Users (id) ON DELETE CASCADE
);

-- Transcript files table
CREATE TABLE Transcripts (
    id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    pdf_id INT NOT NULL,
    file_path VARCHAR(255) NOT NULL, -- Path to the fixed transcript file
    errors JSONB, -- Errors as JSON (e.g., [{"type": "deletion", "content": "text"}])
    status INTEGER DEFAULT 0, -- 0: Pending, 1: Fixed, 2: Rejected
    decision VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (pdf_id) REFERENCES PdfFiles (id) ON DELETE CASCADE
);

-- Meta files table
CREATE TABLE MetaFiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    pdf_id INT NOT NULL,
    file_path VARCHAR(255) NOT NULL, -- Path to the fixed metadata file
    status INTEGER DEFAULT 0, -- 0: Pending, 1: Fixed, 2: Rejected
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (pdf_id) REFERENCES PdfFiles (id) ON DELETE CASCADE
);

-- CSV errors table
CREATE TABLE CsvErrors (
    id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    tender_id INT NOT NULL,
    user_id INT NOT NULL,
    row_data TEXT NOT NULL,               -- Content from CSV
    error_type TEXT NOT NULL CHECK(error_type IN ('insertion', 'deletion')),
    decision INTEGER NOT NULL DEFAULT 0,    -- Decision value: 0, 1, or 2
    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (tender_id) REFERENCES Tenders(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES Users(id) ON DELETE CASCADE
);