# NTPC Backend

Transcript Generation Backend

---

## Prerequisites

- Python 3.9.13 is necessary, download it from here.
https://www.python.org/downloads/release/python-3913/
---

## Installation Instructions

### 1. Setup the Repository
First, clone the repository to your local machine:


```bash
git clone https://github.com/Buvan0702/ntpc_backend.git
cd ntpc_backend
python setup.py

\myenv\Scripts\activate                                                                                                  
pip install "fastapi[standard]"
fastapi dev .\main.py  
```
### 2. Docker 
TODOS: GPU SUPPORT and resolve win32 or change base image ??
ig we win32 is resolved now
```bash
docker build -t pdf-transcript-api .
docker run -it --rm -p 8000:8000 pdf-transcript-api
```
### To Generate Transcript
```bash
python main.py
```

### Note
I added a rough.py file to generate a html page for interactive version of transcript, 
works kind of hyperlink thing
