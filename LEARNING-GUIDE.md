# NoteMind — Learning Through Building

NoteMind is a student-built learning prototype. The goal is to understand how a small web app connects a frontend, a Python backend, local browser storage, semantic search, and an AI API. It is **not** presented as a production research platform or a replacement for mature notebook products.

## What is in this project?

- `index.html` — the interface, responsive CSS, file handling, chunking, browser-side embedding storage, similarity search, chat UI, source snippets, study tools, appearance settings, and About pages.
- `index.py` — the Flask API routes. It reads `GEMINI_API_KEY` from the environment (and supports a local-only `secret.py` fallback for development), calls Gemini, and returns JSON to the frontend.
- `.gitignore` — ignores Python cache files, `.env`, `secret.py`, and Vercel build output. Keep API keys out of Git.
- `LEARNING-GUIDE.md` — this guide and a manual regression checklist.

## Current feature map

### Notebook and sources

- Upload TXT, Markdown, text-based or scanned PDF, and supported PNG/JPG/JPEG/WEBP images.
- Extract PDF text with PDF.js; use Gemini OCR for supported images and scanned pages. Scanned PDFs are capped at the first 20 pages for OCR.
- Split extracted text into small overlapping chunks, request embeddings from the backend, and store note chunks plus vectors in IndexedDB.
- Include or exclude each note for retrieval, remove a note, search by file name, and export extracted/indexed text as Markdown.
- A confirmation dialog explains limitations and external AI processing before files are processed.

### Ask and review

- Embed a question and rank stored chunks using cosine similarity in the browser.
- Send the best matching chunks to the Flask `/api/answer` endpoint; show selected source snippets with the answer.
- Create summaries, multiple-choice quizzes, and flashcards from selected notes.
- Save chats in this browser, switch chats, create/clear/delete chats, copy responses, export chats as Markdown, and export flashcards as CSV.

### Interface and accessibility

- Responsive desktop and mobile layouts, a scrollable notes drawer, camera/file-picker entry points, and a focused-reading mode.
- Five color themes: Midnight, Light, Ocean, Forest, and Sunset.
- Three interface treatments: Glass, Studio, and Minimal.
- Compact spacing and reduced-motion options. Appearance preferences are saved on the current device when browser storage is available.

## How the retrieval flow works

1. **Choose a file.** The browser reads supported text or extracts text from a PDF/image.
2. **Split into chunks.** The frontend creates manageable text sections with a small overlap so a topic crossing a boundary is less likely to be lost.
3. **Create vectors.** The browser sends the sections to `POST /api/embed`. The backend keeps the API key server-side and requests embeddings from Gemini.
4. **Store locally.** Text chunks and their vectors are saved in IndexedDB for this browser profile. Chats and note inclusion settings are also stored locally.
5. **Ask a question.** The frontend embeds the question, ranks sections with cosine similarity, and selects the top five.
6. **Generate and inspect.** The `/api/answer` endpoint receives the question and selected context. The UI displays an answer and source snippets from the retrieved sections.

Retrieval is approximate. A source pill tells you which extracted passage the app selected; it does not prove that the AI answer is complete or correct.

## Run locally (optional)

1. Install Python, then install the backend packages:

   ```bash
   python -m pip install flask requests
   ```

2. Set the Gemini API key in the VS Code terminal. In PowerShell:

   ```powershell
   $env:GEMINI_API_KEY = "YOUR_API_KEY_HERE"
   ```

   Do not paste your real key into HTML or commit it to Git. The environment-variable value applies to that terminal session.

3. From the project directory, start Flask:

   ```powershell
   python -m flask --app index run
   ```

4. Open the local address printed by Flask. The frontend calls `/api/...` on the same origin, so run it through Flask rather than opening `index.html` directly from the file system.

For Vercel, set `GEMINI_API_KEY` in the project's environment variables and redeploy after changing backend code. Keep your existing deployment URL and routing configuration unless you intentionally choose to change them.

## Beginner-friendly build path

1. **Learn the page structure:** inspect the header, notebook sidebar, chat panel, and About section in `index.html`.
2. **Learn CSS layout:** experiment with `.app`, `.side`, `#chat`, the `@media` rules, and the scrolling behavior. Change one rule at a time and test at phone and desktop widths.
3. **Trace a file upload:** follow `handleFileInput`, `requestUploadConfirmation`, `addFiles`, `chunk`, and the `/api/embed` request.
4. **Trace one question:** follow `ask`, `norm`, `dot`, the top-five ranking, the `/api/answer` request, and `draw`.
5. **Trace persistence:** inspect `db`, `tx`, `dbPut`, `dbAll`, `saveChats`, and `init` to understand IndexedDB.
6. **Trace an API call:** follow a route in `index.py` and identify where request data is validated, where Gemini is called, and where JSON is returned.
7. **Make one small improvement:** add a loading message, improve a recovery path, or add a test; verify it before moving to the next change.

Useful practice exercises: add a file-type badge; let users rename a note; add a “show only included notes” filter; record quiz scores locally; add a keyboard shortcut guide; write a small test for chunking; or add a “download debug report” that excludes private note content by default.

## Manual regression checklist

After changing the code, test these flows on a desktop and a phone-sized viewport:

- [ ] Upload a `.txt` note and confirm the warning dialog before processing.
- [ ] Upload a text-based PDF, then test an image/scanned PDF if OCR is available.
- [ ] Search for a matching and a non-matching file name.
- [ ] Exclude a note and confirm the included-file count updates.
- [ ] Ask a question, open a source snippet, and copy the answer.
- [ ] Generate a summary, finish a quiz, and flip/export flashcards.
- [ ] Switch chats; export, clear, and delete a chat.
- [ ] Select each theme and interface style, refresh, and confirm preferences persist.
- [ ] Open Project & About, switch between The project and About me, and open the limitations dialog.
- [ ] On mobile, open the notes drawer, scroll to the bottom, use the controls, and close it with the scrim or Escape.
- [ ] Confirm Clear notes is unavailable while indexing is active; remove a ready note and clear notes after processing.

## Known limitations

- This is a prototype without user accounts, private workspaces, server-side note storage, or application-level rate limiting.
- Extracted text and questions are sent to Gemini for embeddings/answers; images and scanned pages may be sent for OCR. Do not use confidential or sensitive files.
- Extraction can fail on encrypted PDFs, unusual encodings, complex tables, handwriting, low-quality scans, or unsupported image formats.
- Notes and chats are tied to the current browser/device. Clearing browser site data can remove them; the app is not a backup system.
- AI outputs may be wrong or incomplete. Check important information against the original material.
- Gemini access, quotas, latency, and available models depend on your API key and current Google AI service settings.

## Keep improving it honestly

Describe NoteMind as a **learning-focused RAG prototype**: a place to practise file processing, embeddings, retrieval, API integration, UI state, persistence, responsive design, error handling, and debugging. Avoid claiming equivalence with NotebookLM or other mature products. The project is valuable because it makes these building blocks visible and gives you something real to test and improve.
