import os

meta_tok = os.environ.get("META_ACCESS_TOKEN") or os.environ.get("WHATSAPP_ACCESS_TOKEN")
print("ENV TOKEN PRESENT:", bool(meta_tok))
