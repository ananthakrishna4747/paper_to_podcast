# from tqdm import tqdm
# import os
# import os
# import re


# from marker.converters.pdf import PdfConverter
# from marker.models import create_model_dict
# from marker.output import text_from_rendered

# def main():
#     # 1) Initialize the Marker PDF converter
#     converter = PdfConverter(artifact_dict=create_model_dict())

#     # 2) Define input/output directories
#     input_dir = "downloaded_pdfs"
#     output_dir = "output"
#     os.makedirs(output_dir, exist_ok=True)

#     # 3) Loop over 1.pdf … 100.pdf with a progress bar
#     for i in tqdm(range(1, 101), desc="Processing PDFs"):
#         pdf_path = os.path.join(input_dir, f"{i}.pdf")
#         if not os.path.isfile(pdf_path):
#             tqdm.write(f"Skipping missing file: {pdf_path}")
#             continue

#         # 4) Convert PDF → Rendered object
#         rendered = converter(pdf_path)

#         # 5) Extract only the text (tables & images skipped)
#         text, _, _ = text_from_rendered(rendered)

#         # 6) Write the text to a .txt file
#         out_path = os.path.join(output_dir, f"{i}.txt")
#         with open(out_path, "w", encoding="utf-8") as f:
#             f.write(text)

#         tqdm.write(f"Saved {out_path}")

# def remove_references_until_next_heading(text: str) -> str:
#     """
#     Remove the References section (any heading level, bold/italic or plain)
#     and all text up to the next Markdown heading (lines starting with #).
#     """
#     # 1) Find the "References" heading
#     start = re.search(
#         r'(?mi)^\s*#{1,6}\s*\{0,}\s*References\s\{0,}\s:?\s*$', 
#         text
#     )
#     if not start:
#         return text

#     # 2) From the end of that heading, look for the next Markdown heading
#     tail = text[start.end():]
#     end = re.search(r'(?m)^\s*#{1,6}\s+.*$', tail)

#     # 3) Reassemble
#     if end:
#         # keep everything before "References" + from that next heading onward
#         return text[:start.start()].rstrip() + "\n\n" + tail[end.start():].lstrip()
#     else:
#         # no further heading → drop everything from "References" on
#         return text[:start.start()].rstrip()

# def remove_citations_and_tables(text: str) -> str:
#     """
#     Strip out citation markers [1], markdown links, HTML tags, tables, and images.
#     """
#     # a) citation markers like [1], [1,2], [1-3]
#     text = re.sub(r'\[\s*\d+(?:[\s,\-]+\d+)\s\]', '', text)

#     # b) markdown links [text](url)
#     text = re.sub(r'\[.?\]\(.?\)', '', text)

#     # c) HTML superscripts and spans
#     text = re.sub(r'<sup>.*?</sup>', '', text, flags=re.DOTALL)
#     text = re.sub(r'<span[^>]>.?</span>', '', text, flags=re.DOTALL)

#     # d) images ![alt](url)
#     text = re.sub(r'!\[.?\]\(.?\)', '', text)

#     # e) tables (markdown or ASCII)
#     cleaned = []
#     in_table = False
#     for line in text.splitlines():
#         s = line.strip()
#         # detect table start
#         if s.startswith('|') or s.startswith('+') or '-+-' in s:
#             in_table = True
#             continue
#         # detect table end
#         if in_table and not (s.startswith('|') or s.startswith('+') or '-+-' in s):
#             in_table = False
#         # skip table lines/captions
#         if in_table or s.lower().startswith('table ') or s.lower().startswith('figure '):
#             continue
#         cleaned.append(line)
#     return '\n'.join(cleaned)

# def clean_file_contents(text: str) -> str:
#     """
#     Full pipeline: remove References…until next heading, then strip citations/tables/etc.
#     """
#     text = remove_references_until_next_heading(text)
#     text = remove_citations_and_tables(text)
#     return text

# def clean_all_txt(input_dir: str, output_dir: str):
#     """
#     Process all .txt files under input_dir, clean them, and write to output_dir.
#     """
#     os.makedirs(output_dir, exist_ok=True)
#     count = 0

#     for fn in os.listdir(input_dir):
#         if not fn.lower().endswith('.txt'):
#             continue

#         in_path = os.path.join(input_dir, fn)
#         out_path = os.path.join(output_dir, fn)
#         try:
#             with open(in_path, 'r', encoding='utf-8') as f:
#                 raw = f.read()
#             cleaned = clean_file_contents(raw)
#             with open(out_path, 'w', encoding='utf-8') as f:
#                 f.write(cleaned)
#             count += 1
#         except Exception as e:
#             print(f"Error processing {fn}: {e}")

#     print(f"Done! Processed {count} files from '{input_dir}' to '{output_dir}'.")

# if _name_ == '_main_':
#     # Example usage — adjust these paths as needed:
#     clean_all_txt('output', 'cleaned_files')
