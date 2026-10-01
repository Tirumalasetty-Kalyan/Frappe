import shutil
import os

src = '/mnt/c/Users/varshini boda/OneDrive/Desktop/Frappe/valet_parking/valet_parking'
dest1 = '/home/varshini_boda/frappe-bench/apps/valet_parking/valet_parking'
dest2 = '/home/varshini_boda/frappe-bench/apps/valet_parking/valet_parking/valet_parking'

files = [
    'gemini_nlu.py',
    'conversation_memory.py',
    'bot_engine.py',
    'test_gemini_bot.py',
    'api.py',
    'test_whatsapp_webhook.py'
]

for f in files:
    s = os.path.join(src, f)
    if os.path.exists(s):
        shutil.copy(s, os.path.join(dest1, f))
        shutil.copy(s, os.path.join(dest2, f))
        print(f"Copied {f}")

doc_src = os.path.join(src, 'doctype', 'valet_problem_report')
doc_dest1 = os.path.join(dest1, 'doctype', 'valet_problem_report')
doc_dest2 = os.path.join(dest2, 'doctype', 'valet_problem_report')

os.makedirs(doc_dest1, exist_ok=True)
os.makedirs(doc_dest2, exist_ok=True)

for item in os.listdir(doc_src):
    s = os.path.join(doc_src, item)
    if os.path.isfile(s):
        shutil.copy(s, os.path.join(doc_dest1, item))
        shutil.copy(s, os.path.join(doc_dest2, item))
        print(f"Copied doctype file {item}")

print("COMMAND 1: Sync completed successfully!")
