# How to

1) Install system Tesseract, then Python deps:

        brew install tesseract                 # macOS
        sudo apt-get install tesseract-ocr     # Linux
        choco install tesseract                # Windows

        pip install pillow opencv-python pytesseract pymupdf openai

2) Create `.env`:

        python env_setup.py --write-template
        cp .env.template .env
        # edit .env → set OPENAI_API_KEY

3) Export PDF pages:

        python export.py docs/files.pdf -o images -f png -d 300

4) Fix orientation:

        python orient.py images --lang "srp+srp_latn+eng"

5) Prepare `prompt.txt` and optional `liste.txt`.

6) Run OCR:

        python ocr_batch_submit.py --images images --prompt prompt.txt --out json --list liste.txt

You’ll find one JSON per group in `./json`.

---
